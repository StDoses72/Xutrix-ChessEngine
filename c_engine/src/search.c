#include "xutrix.h"

#include <string.h>

#define TT_SIZE (1u << 20)
#define TT_MASK (TT_SIZE - 1)

#define TT_EMPTY 0
#define TT_EXACT 1
#define TT_LOWER 2
#define TT_UPPER 3
#define HISTORY_MAX 70000

typedef struct {
    uint64_t key;
    Move best;
    int score;
    int depth;
    uint8_t flag;
} TTEntry;

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
            score += 100000 + 10 * piece_value(captured) - piece_value(attacker);
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

    int stand_pat = side_relative_eval(board);
    if (stand_pat >= beta) {
        return beta;
    }
    if (stand_pat > alpha) {
        alpha = stand_pat;
    }

    MoveList moves;
    generate_legal_moves(board, &moves);
    score_moves(board, &moves, (Move){255, 255, 0, 0, 0}, board->ply);

    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        if (!(move.flags & (MOVE_CAPTURE | MOVE_PROMOTION))) {
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

    if (depth == 0) {
        return quiescence(board, alpha, beta);
    }

    MoveList moves;
    generate_legal_moves(board, &moves);

    if (moves.count == 0) {
        if (in_check(board, board->side_to_move)) {
            return -MATE_SCORE + ply;
        }
        return 0;
    }

    score_moves(board, &moves, tt_move, ply);

    int best_score = -INF_SCORE;
    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        make_move(board, move);
        int score = -negamax(board, depth - 1, -beta, -alpha, ply + 1);
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

SearchResult search_best_move(Board *board, int depth) {
    SearchResult result;
    result.best_move = (Move){255, 255, 0, 0, 0};
    result.score = 0;
    result.nodes = 0;

    if (depth < 1) {
        depth = 1;
    }

    search_nodes = 0;
    clear_history();
    MoveList moves;
    generate_legal_moves(board, &moves);
    clear_killers();
    score_moves(board, &moves, (Move){255, 255, 0, 0, 0}, 0);

    int alpha = -INF_SCORE;
    int beta = INF_SCORE;
    int best_score = -INF_SCORE;

    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        make_move(board, move);
        int score = -negamax(board, depth - 1, -beta, -alpha, 1);
        undo_move(board);
        if (score > best_score) {
            best_score = score;
            result.best_move = move;
        }
        if (score > alpha) {
            alpha = score;
        }
    }

    result.score = best_score;
    result.nodes = search_nodes;
    return result;
}
