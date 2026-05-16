#include "xutrix.h"

#include <string.h>

#define TT_SIZE (1u << 20)
#define TT_MASK (TT_SIZE - 1)

#define TT_EMPTY 0
#define TT_EXACT 1
#define TT_LOWER 2
#define TT_UPPER 3
#define HISTORY_MAX 70000
#define NULL_MOVE_MIN_DEPTH 3
#define NULL_MOVE_REDUCTION 2

typedef struct {
    uint64_t key;
    Move best;
    int score;
    int depth;
    uint8_t flag;
} TTEntry;

typedef struct {
    int side_to_move;
    int8_t en_passant;
    int halfmove_clock;
    int fullmove_number;
    uint64_t hash;
    int ply;
} NullMoveUndo;

static TTEntry transposition_table[TT_SIZE];
static uint64_t search_nodes;
static Move killer_moves[MAX_PLY][2];
static int history_moves[2][64][64];

static int move_equal(Move a, Move b) {
    return a.from == b.from && a.to == b.to && a.promotion == b.promotion && a.flags == b.flags;
}

static int is_valid_move(Move move) {
    return move.from < 64 && move.to < 64;
}

static int is_tactical_move(Move move) {
    return (move.flags & (MOVE_CAPTURE | MOVE_PROMOTION)) != 0;
}

static int is_near_mate_score(int score) {
    if (score <= -INF_SCORE || score >= INF_SCORE) {
        return 0;
    }
    int abs_score = score < 0 ? -score : score;
    return abs_score >= MATE_SCORE - MAX_PLY;
}

static int is_mate_window(int alpha, int beta) {
    return is_near_mate_score(alpha) || is_near_mate_score(beta);
}

static int has_non_pawn_material(const Board *board, int side) {
    for (int sq = 0; sq < 64; ++sq) {
        int piece = board->squares[sq];
        if (piece == EMPTY || piece_color(piece) != side) {
            continue;
        }
        int type = piece_type(piece);
        if (type != PAWN && type != KING) {
            return 1;
        }
    }
    return 0;
}

static int make_null_move(Board *board, NullMoveUndo *undo) {
    if (board->ply >= MAX_PLY) {
        return 0;
    }

    undo->side_to_move = board->side_to_move;
    undo->en_passant = board->en_passant;
    undo->halfmove_clock = board->halfmove_clock;
    undo->fullmove_number = board->fullmove_number;
    undo->hash = board->hash;
    undo->ply = board->ply;

    if (board->side_to_move == BLACK) {
        ++board->fullmove_number;
    }
    board->side_to_move = opposite_side(board->side_to_move);
    board->en_passant = -1;
    ++board->halfmove_clock;
    ++board->ply;
    board->hash = board_compute_hash(board);
    return 1;
}

static void undo_null_move(Board *board, const NullMoveUndo *undo) {
    board->side_to_move = undo->side_to_move;
    board->en_passant = undo->en_passant;
    board->halfmove_clock = undo->halfmove_clock;
    board->fullmove_number = undo->fullmove_number;
    board->hash = undo->hash;
    board->ply = undo->ply;
}

static void clear_killers(void) {
    for (int ply = 0; ply < MAX_PLY; ++ply) {
        killer_moves[ply][0] = (Move){255, 255, 0, 0, 0};
        killer_moves[ply][1] = (Move){255, 255, 0, 0, 0};
    }
}

static void clear_history(void) {
    memset(history_moves, 0, sizeof(history_moves));
}

static void store_killer(Move move, int ply) {
    if (ply < 0 || ply >= MAX_PLY || is_tactical_move(move)) {
        return;
    }
    if (move_equal(move, killer_moves[ply][0])) {
        return;
    }
    killer_moves[ply][1] = killer_moves[ply][0];
    killer_moves[ply][0] = move;
}

static void store_history(Move move, int side, int depth) {
    if (side < WHITE || side > BLACK || is_tactical_move(move)) {
        return;
    }
    int bonus = depth * depth;
    int *entry = &history_moves[side][move.from][move.to];
    *entry += bonus;
    if (*entry > HISTORY_MAX) {
        *entry = HISTORY_MAX;
    }
}

void tt_clear(void) {
    memset(transposition_table, 0, sizeof(transposition_table));
}

static int piece_value(int piece) {
    static const int values[7] = {0, 100, 320, 330, 500, 900, 20000};
    return values[piece_type(piece)];
}

static int side_relative_eval(const Board *board) {
    int eval = evaluate_board(board);
    return board->side_to_move == WHITE ? eval : -eval;
}

static void score_moves(const Board *board, MoveList *list, Move tt_move, int ply) {
    for (int i = 0; i < list->count; ++i) {
        Move *move = &list->moves[i];
        int score = 0;
        if (is_valid_move(tt_move) && move_equal(*move, tt_move)) {
            score += 10000000;
        }
        if (move->flags & MOVE_CAPTURE) {
            int captured = (move->flags & MOVE_EN_PASSANT)
                ? (board->side_to_move == WHITE ? BP : WP)
                : board->squares[move->to];
            int attacker = board->squares[move->from];
            int see = see_move(board, *move);
            score += 100000 + 10 * piece_value(captured) - piece_value(attacker) + see;
        }
        if (move->flags & MOVE_PROMOTION) {
            score += 80000 + piece_value(move->promotion);
        }
        if (!is_tactical_move(*move) && ply >= 0 && ply < MAX_PLY) {
            if (move_equal(*move, killer_moves[ply][0])) {
                score += 90000;
            } else if (move_equal(*move, killer_moves[ply][1])) {
                score += 80000;
            }
            score += history_moves[board->side_to_move][move->from][move->to];
        }
        if (move->flags & MOVE_CASTLE) {
            score += 1000;
        }
        move->score = score;
    }

    for (int i = 1; i < list->count; ++i) {
        Move key = list->moves[i];
        int j = i - 1;
        while (j >= 0 && list->moves[j].score < key.score) {
            list->moves[j + 1] = list->moves[j];
            --j;
        }
        list->moves[j + 1] = key;
    }
}

static int quiescence(Board *board, int alpha, int beta) {
    ++search_nodes;

    int checked = in_check(board, board->side_to_move);
    MoveList moves;
    generate_legal_moves(board, &moves);
    if (moves.count == 0) {
        return checked ? -MATE_SCORE + board->ply : 0;
    }

    if (!checked) {
        int stand_pat = side_relative_eval(board);
        if (stand_pat >= beta) {
            return beta;
        }
        if (stand_pat > alpha) {
            alpha = stand_pat;
        }
    }

    score_moves(board, &moves, (Move){255, 255, 0, 0, 0}, board->ply);

    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        if (!checked && !(move.flags & (MOVE_CAPTURE | MOVE_PROMOTION))) {
            continue;
        }
        if (!checked && (move.flags & MOVE_CAPTURE) && !(move.flags & MOVE_PROMOTION) && see_move(board, move) < 0) {
            continue;
        }
        make_move(board, move);
        int score = -quiescence(board, -beta, -alpha);
        undo_move(board);

        if (score >= beta) {
            return beta;
        }
        if (score > alpha) {
            alpha = score;
        }
    }

    return alpha;
}

static int negamax(Board *board, int depth, int alpha, int beta, int ply) {
    ++search_nodes;
    int alpha_original = alpha;
    Move best_move = {255, 255, 0, 0, 0};
    int checked = in_check(board, board->side_to_move);

    TTEntry *entry = &transposition_table[board->hash & TT_MASK];
    Move tt_move = {255, 255, 0, 0, 0};
    if (entry->flag != TT_EMPTY && entry->key == board->hash) {
        tt_move = entry->best;
        if (entry->depth >= depth) {
            if (entry->flag == TT_EXACT) {
                return entry->score;
            }
            if (entry->flag == TT_LOWER && entry->score > alpha) {
                alpha = entry->score;
            } else if (entry->flag == TT_UPPER && entry->score < beta) {
                beta = entry->score;
            }
            if (alpha >= beta) {
                return entry->score;
            }
        }
    }

    MoveList moves;
    generate_legal_moves(board, &moves);

    if (moves.count == 0) {
        if (checked) {
            return -MATE_SCORE + ply;
        }
        return 0;
    }

    if (depth == 0) {
        return quiescence(board, alpha, beta);
    }

    if (depth >= NULL_MOVE_MIN_DEPTH && !checked && !is_mate_window(alpha, beta) &&
        has_non_pawn_material(board, board->side_to_move) && side_relative_eval(board) >= beta) {
        NullMoveUndo undo;
        if (make_null_move(board, &undo)) {
            int reduction = NULL_MOVE_REDUCTION + depth / 6;
            int reduced_depth = depth - 1 - reduction;
            if (reduced_depth < 0) {
                reduced_depth = 0;
            }
            int score = -negamax(board, reduced_depth, -beta, -beta + 1, ply + 1);
            undo_null_move(board, &undo);
            if (score >= beta) {
                return beta;
            }
        }
    }

    score_moves(board, &moves, tt_move, ply);

    int best_score = -INF_SCORE;
    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        make_move(board, move);
        int score;
        if (i == 0) {
            score = -negamax(board, depth - 1, -beta, -alpha, ply + 1);
        } else {
            score = -negamax(board, depth - 1, -alpha - 1, -alpha, ply + 1);
            if (score > alpha && score < beta) {
                score = -negamax(board, depth - 1, -beta, -alpha, ply + 1);
            }
        }
        undo_move(board);

        if (score > best_score) {
            best_score = score;
            best_move = move;
        }
        if (score > alpha) {
            alpha = score;
        }
        if (alpha >= beta) {
            store_killer(move, ply);
            store_history(move, board->side_to_move, depth);
            break;
        }
    }

    entry->key = board->hash;
    entry->best = best_move;
    entry->score = best_score;
    entry->depth = depth;
    if (best_score <= alpha_original) {
        entry->flag = TT_UPPER;
    } else if (best_score >= beta) {
        entry->flag = TT_LOWER;
    } else {
        entry->flag = TT_EXACT;
    }

    return best_score;
}

uint64_t perft(Board *board, int depth) {
    if (depth == 0) {
        return 1;
    }

    MoveList moves;
    generate_legal_moves(board, &moves);
    if (depth == 1) {
        return (uint64_t)moves.count;
    }

    uint64_t nodes = 0;
    for (int i = 0; i < moves.count; ++i) {
        make_move(board, moves.moves[i]);
        nodes += perft(board, depth - 1);
        undo_move(board);
    }
    return nodes;
}

static SearchResult search_root(Board *board, int depth, int alpha, int beta, int reset_heuristics) {
    SearchResult result;
    result.best_move = (Move){255, 255, 0, 0, 0};
    result.score = 0;
    result.nodes = search_nodes;

    if (depth < 1) {
        depth = 1;
    }

    if (reset_heuristics) {
        clear_history();
        clear_killers();
    }

    int alpha_original = alpha;
    MoveList moves;
    generate_legal_moves(board, &moves);
    if (moves.count == 0) {
        result.score = in_check(board, board->side_to_move) ? -MATE_SCORE : 0;
        result.nodes = search_nodes;
        return result;
    }

    Move tt_move = (Move){255, 255, 0, 0, 0};
    TTEntry *entry = &transposition_table[board->hash & TT_MASK];
    if (entry->flag != TT_EMPTY && entry->key == board->hash) {
        tt_move = entry->best;
    }

    score_moves(board, &moves, tt_move, 0);

    int best_score = -INF_SCORE;

    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        make_move(board, move);
        int score;
        if (i == 0) {
            score = -negamax(board, depth - 1, -beta, -alpha, 1);
        } else {
            score = -negamax(board, depth - 1, -alpha - 1, -alpha, 1);
            if (score > alpha && score < beta) {
                score = -negamax(board, depth - 1, -beta, -alpha, 1);
            }
        }
        undo_move(board);
        if (score > best_score) {
            best_score = score;
            result.best_move = move;
        }
        if (score > alpha) {
            alpha = score;
        }
    }

    entry->key = board->hash;
    entry->best = result.best_move;
    entry->score = best_score;
    entry->depth = depth;
    if (best_score <= alpha_original) {
        entry->flag = TT_UPPER;
    } else if (best_score >= beta) {
        entry->flag = TT_LOWER;
    } else {
        entry->flag = TT_EXACT;
    }

    result.score = best_score;
    result.nodes = search_nodes;
    return result;
}

SearchResult search_best_move(Board *board, int depth) {
    search_nodes = 0;
    return search_root(board, depth, -INF_SCORE, INF_SCORE, 1);
}

SearchResult search_iterative(Board *board, int max_depth) {
    SearchResult final_result;
    final_result.best_move = (Move){255, 255, 0, 0, 0};
    final_result.score = 0;
    final_result.nodes = 0;

    if (max_depth < 1) {
        max_depth = 1;
    }

    uint64_t total_nodes = 0;
    int previous_score = 0;
    clear_history();
    clear_killers();

    for (int depth = 1; depth <= max_depth; ++depth) {
        int alpha = -INF_SCORE;
        int beta = INF_SCORE;
        int window = 50;
        int attempts = 0;
        SearchResult current = final_result;

        if (depth > 1) {
            alpha = previous_score - window;
            beta = previous_score + window;
        }

        while (1) {
            search_nodes = 0;
            current = search_root(board, depth, alpha, beta, 0);
            total_nodes += current.nodes;

            if (depth == 1 || (current.score > alpha && current.score < beta)) {
                break;
            }

            ++attempts;
            if (attempts >= 4) {
                alpha = -INF_SCORE;
                beta = INF_SCORE;
            } else if (current.score <= alpha) {
                alpha -= window;
                window *= 2;
            } else {
                beta += window;
                window *= 2;
            }
        }

        final_result = current;
        final_result.nodes = total_nodes;
        previous_score = current.score;
        if (current.best_move.from >= 64) {
            break;
        }
    }

    return final_result;
}
