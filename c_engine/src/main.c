#include "xutrix.h"
#include "nnue.h"

#include <ctype.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static void uci_loop(void);

static void print_usage(void) {
    printf("Xutrix C Engine\n\n");
    printf("Usage:\n");
    printf("  xutrix perft <depth> [fen]\n");
    printf("  xutrix divide <depth> [fen]\n");
    printf("  xutrix moves [fen]\n");
    printf("  xutrix best <depth> [fen]\n");
    printf("  xutrix eval [fen]\n");
    printf("  xutrix play [depth] [fen]\n");
    printf("  xutrix uci\n\n");
    printf("Examples:\n");
    printf("  xutrix perft 3\n");
    printf("  xutrix best 4\n");
}

static void trim_in_place(char *buffer) {
    char *start = buffer;
    while (*start && isspace((unsigned char)*start)) {
        ++start;
    }
    char *end = start + strlen(start);
    while (end > start && isspace((unsigned char)end[-1])) {
        --end;
    }
    *end = '\0';
    if (start != buffer) {
        memmove(buffer, start, strlen(start) + 1);
    }
}

static void append_token(char *dst, size_t dst_size, const char *token) {
    if (dst[0] != '\0') {
        strncat(dst, " ", dst_size - strlen(dst) - 1);
    }
    strncat(dst, token, dst_size - strlen(dst) - 1);
}

static const char *fen_from_args(int argc, char **argv, int start_index, char *buffer, size_t buffer_size) {
    buffer[0] = '\0';
    if (start_index >= argc) {
        return START_FEN;
    }
    for (int i = start_index; i < argc; ++i) {
        append_token(buffer, buffer_size, argv[i]);
    }
    return buffer;
}

static void command_perft(int argc, char **argv) {
    int depth = argc >= 3 ? atoi(argv[2]) : 1;
    char fen[512];
    Board board;
    if (!board_from_fen(&board, fen_from_args(argc, argv, 3, fen, sizeof(fen)))) {
        fprintf(stderr, "Invalid FEN.\n");
        return;
    }

    clock_t start = clock();
    uint64_t nodes = perft(&board, depth);
    double seconds = (double)(clock() - start) / CLOCKS_PER_SEC;
    printf("perft(%d) = %" PRIu64 "\n", depth, nodes);
    printf("time = %.3f sec\n", seconds);
    if (seconds > 0.0) {
        printf("nps = %.0f\n", nodes / seconds);
    }
}

static void command_best(int argc, char **argv) {
    int depth = argc >= 3 ? atoi(argv[2]) : 4;
    char fen[512];
    Board board;
    if (!board_from_fen(&board, fen_from_args(argc, argv, 3, fen, sizeof(fen)))) {
        fprintf(stderr, "Invalid FEN.\n");
        return;
    }

    clock_t start = clock();
    SearchResult result = search_best_move(&board, depth);
    double seconds = (double)(clock() - start) / CLOCKS_PER_SEC;
    char move_text[6] = "0000";
    if (result.best_move.from < 64) {
        move_to_uci(result.best_move, move_text);
    }
    printf("bestmove %s\n", move_text);
    printf("score cp %d\n", result.score);
    printf("nodes %" PRIu64 "\n", result.nodes);
    printf("time %.3f sec\n", seconds);
}

static void command_eval(int argc, char **argv) {
    char fen[512];
    Board board;
    if (!board_from_fen(&board, fen_from_args(argc, argv, 2, fen, sizeof(fen)))) {
        fprintf(stderr, "Invalid FEN.\n");
        return;
    }

    printf("classic cp %d\n", evaluate_classic_board(&board));
    if (nnue_is_loaded()) {
        printf("nnue cp %d\n", nnue_evaluate_board(&board));
        printf("active evaluator nnue\n");
    } else {
        printf("nnue not loaded; set XUTRIX_NNUE to a weight file to enable it\n");
        printf("active evaluator classic\n");
    }
}

static void command_moves(int argc, char **argv) {
    char fen[512];
    Board board;
    if (!board_from_fen(&board, fen_from_args(argc, argv, 2, fen, sizeof(fen)))) {
        fprintf(stderr, "Invalid FEN.\n");
        return;
    }

    MoveList moves;
    generate_legal_moves(&board, &moves);
    for (int i = 0; i < moves.count; ++i) {
        char text[6];
        move_to_uci(moves.moves[i], text);
        printf("%s\n", text);
    }
    printf("count %d\n", moves.count);
}

static void command_divide(int argc, char **argv) {
    int depth = argc >= 3 ? atoi(argv[2]) : 1;
    char fen[512];
    Board board;
    if (!board_from_fen(&board, fen_from_args(argc, argv, 3, fen, sizeof(fen)))) {
        fprintf(stderr, "Invalid FEN.\n");
        return;
    }

    MoveList moves;
    generate_legal_moves(&board, &moves);
    uint64_t total = 0;
    for (int i = 0; i < moves.count; ++i) {
        make_move(&board, moves.moves[i]);
        uint64_t nodes = perft(&board, depth - 1);
        undo_move(&board);
        char text[6];
        move_to_uci(moves.moves[i], text);
        printf("%s: %" PRIu64 "\n", text, nodes);
        total += nodes;
    }
    printf("total: %" PRIu64 "\n", total);
}

static void command_play(int argc, char **argv) {
    int depth = argc >= 3 ? atoi(argv[2]) : 4;
    char fen[512];
    Board board;
    if (!board_from_fen(&board, fen_from_args(argc, argv, 3, fen, sizeof(fen)))) {
        fprintf(stderr, "Invalid FEN.\n");
        return;
    }

    printf("Human plays white. Enter UCI moves like e2e4, or q to quit.\n");
    char input[128];
    while (1) {
        board_print(&board);
        MoveList legal;
        generate_legal_moves(&board, &legal);
        if (legal.count == 0) {
            printf("%s\n", in_check(&board, board.side_to_move) ? "checkmate" : "stalemate");
            break;
        }

        if (board.side_to_move == WHITE) {
            printf("your move> ");
            if (!fgets(input, sizeof(input), stdin)) {
                break;
            }
            input[strcspn(input, "\r\n")] = '\0';
            trim_in_place(input);
            if (strcmp(input, "q") == 0 || strcmp(input, "quit") == 0) {
                break;
            }
            Move move;
            if (!parse_uci_move(&board, input, &move)) {
                printf("Illegal move: %s\n", input);
                continue;
            }
            make_move(&board, move);
        } else {
            SearchResult result = search_best_move(&board, depth);
            if (result.best_move.from >= 64) {
                printf("No engine move.\n");
                break;
            }
            char move_text[6];
            move_to_uci(result.best_move, move_text);
            printf("engine: %s  score=%d  nodes=%" PRIu64 "\n", move_text, result.score, result.nodes);
            make_move(&board, result.best_move);
        }
    }
}

static int read_menu_choice(char *buffer, size_t size) {
    printf("\nChoose:\n");
    printf("  1. Play against engine, choose depth\n");
    printf("  2. Search best move, depth 6\n");
    printf("  3. Run startpos perft 4\n");
    printf("  4. Evaluate start position\n");
    printf("  5. UCI mode\n");
    printf("  q. Quit\n");
    printf("> ");
    if (!fgets(buffer, size, stdin)) {
        return 0;
    }
    buffer[strcspn(buffer, "\r\n")] = '\0';
    trim_in_place(buffer);
    return 1;
}

static int read_depth_or_default(int default_depth) {
    char input[32];
    printf("Depth [%d]> ", default_depth);
    if (!fgets(input, sizeof(input), stdin)) {
        return default_depth;
    }
    input[strcspn(input, "\r\n")] = '\0';
    trim_in_place(input);
    char *start = input;
    if (*start == '\0') {
        return default_depth;
    }

    int depth = atoi(start);
    if (depth < 1) {
        printf("Using default depth %d.\n", default_depth);
        return default_depth;
    }
    if (depth > 64) {
        printf("Depth capped at 64.\n");
        return 64;
    }
    return depth;
}

static void interactive_menu(void) {
    char input[32];
    char depth_text[16];

    printf("Xutrix C Engine\n");
    printf("Tip: command-line usage still works, for example: xutrix.exe best 8\n");

    while (read_menu_choice(input, sizeof(input))) {
        if (strcmp(input, "1") == 0) {
            int depth = read_depth_or_default(4);
            snprintf(depth_text, sizeof(depth_text), "%d", depth);
            char *args[] = {"xutrix", "play", depth_text};
            command_play(3, args);
        } else if (strcmp(input, "2") == 0) {
            char *args[] = {"xutrix", "best", "6"};
            command_best(3, args);
        } else if (strcmp(input, "3") == 0) {
            char *args[] = {"xutrix", "perft", "4"};
            command_perft(3, args);
        } else if (strcmp(input, "4") == 0) {
            char *args[] = {"xutrix", "eval"};
            command_eval(2, args);
        } else if (strcmp(input, "5") == 0) {
            printf("Entering UCI mode. Type quit to exit.\n");
            uci_loop();
        } else if (strcmp(input, "q") == 0 || strcmp(input, "quit") == 0) {
            break;
        } else {
            printf("Unknown choice: %s\n", input);
        }
    }

    printf("Press Enter to close...");
    (void)fgets(input, sizeof(input), stdin);
}

static void set_position(Board *board, char *line) {
    char *cursor = line;
    while (*cursor && !isspace((unsigned char)*cursor)) {
        ++cursor;
    }
    while (*cursor && isspace((unsigned char)*cursor)) {
        ++cursor;
    }

    if (strncmp(cursor, "startpos", 8) == 0) {
        board_set_startpos(board);
        cursor += 8;
    } else if (strncmp(cursor, "fen", 3) == 0) {
        cursor += 3;
        while (*cursor && isspace((unsigned char)*cursor)) {
            ++cursor;
        }
        char fen[512] = {0};
        char *moves_marker = strstr(cursor, " moves ");
        if (moves_marker) {
            size_t len = (size_t)(moves_marker - cursor);
            if (len >= sizeof(fen)) {
                len = sizeof(fen) - 1;
            }
            memcpy(fen, cursor, len);
            fen[len] = '\0';
            cursor = moves_marker + 7;
        } else {
            strncpy(fen, cursor, sizeof(fen) - 1);
            cursor = NULL;
        }
        if (!board_from_fen(board, fen)) {
            board_set_startpos(board);
        }
    }

    char *moves = strstr(line, " moves ");
    if (moves) {
        moves += 7;
        char *token = strtok(moves, " \t\r\n");
        while (token) {
            Move move;
            if (parse_uci_move(board, token, &move)) {
                make_move(board, move);
            }
            token = strtok(NULL, " \t\r\n");
        }
    } else if (cursor && *cursor) {
        char *token = strtok(cursor, " \t\r\n");
        while (token) {
            Move move;
            if (parse_uci_move(board, token, &move)) {
                make_move(board, move);
            }
            token = strtok(NULL, " \t\r\n");
        }
    }
}

static void uci_loop(void) {
    Board board;
    board_set_startpos(&board);
    char line[1024];

    while (fgets(line, sizeof(line), stdin)) {
        line[strcspn(line, "\r\n")] = '\0';

        if (strcmp(line, "uci") == 0) {
            printf("id name Xutrix C\n");
            printf("id author XiangCheng Xu and Codex\n");
            printf("uciok\n");
        } else if (strcmp(line, "isready") == 0) {
            printf("readyok\n");
        } else if (strcmp(line, "ucinewgame") == 0) {
            tt_clear();
            board_set_startpos(&board);
        } else if (strncmp(line, "position", 8) == 0) {
            set_position(&board, line);
        } else if (strncmp(line, "go", 2) == 0) {
            int depth = 4;
            char *depth_text = strstr(line, "depth");
            if (depth_text) {
                depth = atoi(depth_text + 5);
                if (depth < 1) {
                    depth = 1;
                }
            }
            SearchResult result = search_best_move(&board, depth);
            char best[6] = "0000";
            if (result.best_move.from < 64) {
                move_to_uci(result.best_move, best);
            }
            printf("info depth %d score cp %d nodes %" PRIu64 "\n", depth, result.score, result.nodes);
            printf("bestmove %s\n", best);
        } else if (strcmp(line, "d") == 0) {
            board_print(&board);
        } else if (strcmp(line, "quit") == 0) {
            break;
        }
        fflush(stdout);
    }
}

int main(int argc, char **argv) {
    xutrix_init();
    if (nnue_try_load_from_env()) {
        fprintf(stderr, "Loaded NNUE from XUTRIX_NNUE.\n");
    }

    if (argc < 2) {
        interactive_menu();
        return 0;
    }

    if (strcmp(argv[1], "perft") == 0) {
        command_perft(argc, argv);
    } else if (strcmp(argv[1], "divide") == 0) {
        command_divide(argc, argv);
    } else if (strcmp(argv[1], "moves") == 0) {
        command_moves(argc, argv);
    } else if (strcmp(argv[1], "best") == 0) {
        command_best(argc, argv);
    } else if (strcmp(argv[1], "eval") == 0) {
        command_eval(argc, argv);
    } else if (strcmp(argv[1], "play") == 0) {
        command_play(argc, argv);
    } else if (strcmp(argv[1], "uci") == 0) {
        uci_loop();
    } else {
        print_usage();
    }

    return 0;
}
