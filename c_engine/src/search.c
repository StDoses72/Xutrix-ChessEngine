#include "xutrix.h"

#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <pthread.h>
#endif

#define TT_SIZE (1u << 20)
#define TT_MASK (TT_SIZE - 1)
#define PARALLEL_TT_SIZE (1u << 16)
#define MAX_SEARCH_THREADS 64

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

typedef struct {
    uint64_t nodes;
    Move killer_moves[MAX_PLY][2];
    int history_moves[2][64][64];
    TTEntry *tt;
    uint64_t tt_mask;
    int owns_tt;
} SearchContext;

#ifdef _WIN32
typedef HANDLE XThread;
typedef CRITICAL_SECTION XMutex;
typedef DWORD XThreadReturn;
#define XTHREAD_CALL WINAPI
#define XTHREAD_RETURN 0
#else
typedef pthread_t XThread;
typedef pthread_mutex_t XMutex;
typedef void *XThreadReturn;
#define XTHREAD_CALL
#define XTHREAD_RETURN NULL
#endif

static TTEntry transposition_table[TT_SIZE];

static int move_equal(Move a, Move b) {
    return a.from == b.from && a.to == b.to && a.promotion == b.promotion && a.flags == b.flags;
}

static Move invalid_move(void) {
    return (Move){255, 255, 0, 0, 0};
}

static int is_valid_move(Move move) {
    return move.from < 64 && move.to < 64;
}

static int normalize_thread_count(int threads, int work_count) {
    if (threads < 1) {
        threads = 1;
    }
    if (threads > MAX_SEARCH_THREADS) {
        threads = MAX_SEARCH_THREADS;
    }
    if (work_count > 0 && threads > work_count) {
        threads = work_count;
    }
    return threads;
}

static int xthread_create(XThread *thread, XThreadReturn (XTHREAD_CALL *fn)(void *), void *arg) {
#ifdef _WIN32
    *thread = CreateThread(NULL, 0, fn, arg, 0, NULL);
    return *thread != NULL;
#else
    return pthread_create(thread, NULL, fn, arg) == 0;
#endif
}

static void xthread_join(XThread thread) {
#ifdef _WIN32
    WaitForSingleObject(thread, INFINITE);
    CloseHandle(thread);
#else
    pthread_join(thread, NULL);
#endif
}

static void xmutex_init(XMutex *mutex) {
#ifdef _WIN32
    InitializeCriticalSection(mutex);
#else
    pthread_mutex_init(mutex, NULL);
#endif
}

static void xmutex_destroy(XMutex *mutex) {
#ifdef _WIN32
    DeleteCriticalSection(mutex);
#else
    pthread_mutex_destroy(mutex);
#endif
}

static void xmutex_lock(XMutex *mutex) {
#ifdef _WIN32
    EnterCriticalSection(mutex);
#else
    pthread_mutex_lock(mutex);
#endif
}

static void xmutex_unlock(XMutex *mutex) {
#ifdef _WIN32
    LeaveCriticalSection(mutex);
#else
    pthread_mutex_unlock(mutex);
#endif
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

static void clear_killers(SearchContext *ctx) {
    for (int ply = 0; ply < MAX_PLY; ++ply) {
        ctx->killer_moves[ply][0] = invalid_move();
        ctx->killer_moves[ply][1] = invalid_move();
    }
}

static void clear_history(SearchContext *ctx) {
    memset(ctx->history_moves, 0, sizeof(ctx->history_moves));
}

static void search_context_init(SearchContext *ctx, TTEntry *tt, uint64_t tt_mask) {
    memset(ctx, 0, sizeof(*ctx));
    ctx->tt = tt;
    ctx->tt_mask = tt_mask;
    clear_killers(ctx);
}

static void search_context_init_worker(SearchContext *ctx) {
    search_context_init(ctx, NULL, 0);
    ctx->tt = (TTEntry *)calloc(PARALLEL_TT_SIZE, sizeof(TTEntry));
    if (ctx->tt) {
        ctx->tt_mask = PARALLEL_TT_SIZE - 1;
        ctx->owns_tt = 1;
    }
}

static void search_context_destroy(SearchContext *ctx) {
    if (ctx->owns_tt) {
        free(ctx->tt);
    }
    ctx->tt = NULL;
    ctx->tt_mask = 0;
    ctx->owns_tt = 0;
}

static TTEntry *context_tt_entry(SearchContext *ctx, uint64_t hash) {
    if (!ctx->tt) {
        return NULL;
    }
    return &ctx->tt[hash & ctx->tt_mask];
}

static void store_killer(SearchContext *ctx, Move move, int ply) {
    if (ply < 0 || ply >= MAX_PLY || is_tactical_move(move)) {
        return;
    }
    if (move_equal(move, ctx->killer_moves[ply][0])) {
        return;
    }
    ctx->killer_moves[ply][1] = ctx->killer_moves[ply][0];
    ctx->killer_moves[ply][0] = move;
}

static void store_history(SearchContext *ctx, Move move, int side, int depth) {
    if (side < WHITE || side > BLACK || is_tactical_move(move)) {
        return;
    }
    int bonus = depth * depth;
    int *entry = &ctx->history_moves[side][move.from][move.to];
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

static void score_moves(SearchContext *ctx, const Board *board, MoveList *list, Move tt_move, int ply) {
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
            if (ctx && move_equal(*move, ctx->killer_moves[ply][0])) {
                score += 90000;
            } else if (ctx && move_equal(*move, ctx->killer_moves[ply][1])) {
                score += 80000;
            }
            if (ctx) {
                score += ctx->history_moves[board->side_to_move][move->from][move->to];
            }
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

static int quiescence(SearchContext *ctx, Board *board, int alpha, int beta) {
    ++ctx->nodes;

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

    score_moves(ctx, board, &moves, invalid_move(), board->ply);

    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        if (!checked && !(move.flags & (MOVE_CAPTURE | MOVE_PROMOTION))) {
            continue;
        }
        if (!checked && (move.flags & MOVE_CAPTURE) && !(move.flags & MOVE_PROMOTION) && see_move(board, move) < 0) {
            continue;
        }
        make_move(board, move);
        int score = -quiescence(ctx, board, -beta, -alpha);
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

static int negamax(SearchContext *ctx, Board *board, int depth, int alpha, int beta, int ply) {
    ++ctx->nodes;
    int alpha_original = alpha;
    Move best_move = invalid_move();
    int checked = in_check(board, board->side_to_move);

    TTEntry *entry = context_tt_entry(ctx, board->hash);
    Move tt_move = invalid_move();
    if (entry && entry->flag != TT_EMPTY && entry->key == board->hash) {
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
        return quiescence(ctx, board, alpha, beta);
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
            int score = -negamax(ctx, board, reduced_depth, -beta, -beta + 1, ply + 1);
            undo_null_move(board, &undo);
            if (score >= beta) {
                return beta;
            }
        }
    }

    score_moves(ctx, board, &moves, tt_move, ply);

    int best_score = -INF_SCORE;
    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        make_move(board, move);
        int score;
        if (i == 0) {
            score = -negamax(ctx, board, depth - 1, -beta, -alpha, ply + 1);
        } else {
            score = -negamax(ctx, board, depth - 1, -alpha - 1, -alpha, ply + 1);
            if (score > alpha && score < beta) {
                score = -negamax(ctx, board, depth - 1, -beta, -alpha, ply + 1);
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
            store_killer(ctx, move, ply);
            store_history(ctx, move, board->side_to_move, depth);
            break;
        }
    }

    if (entry) {
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

typedef struct {
    const Board *board;
    const MoveList *moves;
    int depth;
    int worker_index;
    int worker_count;
    uint64_t nodes;
} PerftWorker;

static XThreadReturn XTHREAD_CALL perft_worker_main(void *arg) {
    PerftWorker *worker = (PerftWorker *)arg;
    uint64_t nodes = 0;

    for (int i = worker->worker_index; i < worker->moves->count; i += worker->worker_count) {
        Board copy = *worker->board;
        make_move(&copy, worker->moves->moves[i]);
        nodes += perft(&copy, worker->depth - 1);
    }

    worker->nodes = nodes;
    return XTHREAD_RETURN;
}

uint64_t perft_parallel(Board *board, int depth, int threads) {
    if (depth <= 1 || threads <= 1) {
        return perft(board, depth);
    }

    MoveList moves;
    generate_legal_moves(board, &moves);
    if (moves.count == 0) {
        return 0;
    }

    threads = normalize_thread_count(threads, moves.count);
    if (threads <= 1) {
        return perft(board, depth);
    }

    XThread *handles = (XThread *)calloc((size_t)threads, sizeof(XThread));
    PerftWorker *workers = (PerftWorker *)calloc((size_t)threads, sizeof(PerftWorker));
    if (!handles || !workers) {
        free(handles);
        free(workers);
        return perft(board, depth);
    }

    int started = 0;
    for (int i = 0; i < threads; ++i) {
        workers[i].board = board;
        workers[i].moves = &moves;
        workers[i].depth = depth;
        workers[i].worker_index = i;
        workers[i].worker_count = threads;
        if (!xthread_create(&handles[i], perft_worker_main, &workers[i])) {
            for (int j = 0; j < started; ++j) {
                xthread_join(handles[j]);
            }
            free(handles);
            free(workers);
            return perft(board, depth);
        }
        ++started;
    }

    uint64_t nodes = 0;
    for (int i = 0; i < threads; ++i) {
        xthread_join(handles[i]);
        nodes += workers[i].nodes;
    }

    free(handles);
    free(workers);
    return nodes;
}

static SearchResult search_root(SearchContext *ctx, Board *board, int depth, int alpha, int beta, int reset_heuristics) {
    SearchResult result;
    result.best_move = invalid_move();
    result.score = 0;
    result.nodes = ctx->nodes;

    if (depth < 1) {
        depth = 1;
    }

    if (reset_heuristics) {
        clear_history(ctx);
        clear_killers(ctx);
    }

    int alpha_original = alpha;
    MoveList moves;
    generate_legal_moves(board, &moves);
    if (moves.count == 0) {
        result.score = in_check(board, board->side_to_move) ? -MATE_SCORE : 0;
        result.nodes = ctx->nodes;
        return result;
    }

    Move tt_move = invalid_move();
    TTEntry *entry = context_tt_entry(ctx, board->hash);
    if (entry && entry->flag != TT_EMPTY && entry->key == board->hash) {
        tt_move = entry->best;
    }

    score_moves(ctx, board, &moves, tt_move, 0);

    int best_score = -INF_SCORE;

    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        make_move(board, move);
        int score;
        if (i == 0) {
            score = -negamax(ctx, board, depth - 1, -beta, -alpha, 1);
        } else {
            score = -negamax(ctx, board, depth - 1, -alpha - 1, -alpha, 1);
            if (score > alpha && score < beta) {
                score = -negamax(ctx, board, depth - 1, -beta, -alpha, 1);
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

    if (entry) {
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
    }

    result.score = best_score;
    result.nodes = ctx->nodes;
    return result;
}

typedef struct {
    const Board *board;
    const MoveList *moves;
    int depth;
    int beta;
    int next_index;
    int alpha;
    Move best_move;
    int best_score;
    XMutex mutex;
} RootSearchShared;

typedef struct {
    RootSearchShared *shared;
    SearchContext ctx;
} RootSearchWorker;

static XThreadReturn XTHREAD_CALL root_search_worker_main(void *arg) {
    RootSearchWorker *worker = (RootSearchWorker *)arg;
    RootSearchShared *shared = worker->shared;

    while (1) {
        xmutex_lock(&shared->mutex);
        if (shared->next_index >= shared->moves->count) {
            xmutex_unlock(&shared->mutex);
            break;
        }
        int move_index = shared->next_index++;
        int alpha_snapshot = shared->alpha;
        xmutex_unlock(&shared->mutex);

        Move move = shared->moves->moves[move_index];
        Board copy = *shared->board;
        make_move(&copy, move);
        int score = -negamax(&worker->ctx, &copy, shared->depth - 1, -alpha_snapshot - 1, -alpha_snapshot, 1);
        if (score > alpha_snapshot && score < shared->beta) {
            copy = *shared->board;
            make_move(&copy, move);
            score = -negamax(&worker->ctx, &copy, shared->depth - 1, -shared->beta, -alpha_snapshot, 1);
        }

        xmutex_lock(&shared->mutex);
        if (score > shared->best_score) {
            shared->best_score = score;
            shared->best_move = move;
            if (score > shared->alpha) {
                shared->alpha = score;
            }
        }
        xmutex_unlock(&shared->mutex);
    }

    return XTHREAD_RETURN;
}

static void destroy_root_workers(RootSearchWorker *workers, int count) {
    if (!workers) {
        return;
    }
    for (int i = 0; i < count; ++i) {
        search_context_destroy(&workers[i].ctx);
    }
}

static SearchResult search_root_parallel(Board *board, int depth, int alpha, int beta, int threads) {
    SearchResult result;
    result.best_move = invalid_move();
    result.score = 0;
    result.nodes = 0;
    int alpha_original = alpha;

    if (depth < 1) {
        depth = 1;
    }

    MoveList moves;
    generate_legal_moves(board, &moves);
    if (moves.count == 0) {
        result.score = in_check(board, board->side_to_move) ? -MATE_SCORE : 0;
        return result;
    }

    threads = normalize_thread_count(threads, moves.count);
    if (threads <= 1) {
        SearchContext fallback;
        search_context_init(&fallback, transposition_table, TT_MASK);
        return search_root(&fallback, board, depth, alpha, beta, 1);
    }

    Move tt_move = invalid_move();
    TTEntry *entry = &transposition_table[board->hash & TT_MASK];
    if (entry->flag != TT_EMPTY && entry->key == board->hash) {
        tt_move = entry->best;
    }
    score_moves(NULL, board, &moves, tt_move, 0);

    SearchContext first_ctx;
    search_context_init_worker(&first_ctx);
    Board first_copy = *board;
    make_move(&first_copy, moves.moves[0]);
    int best_score = -negamax(&first_ctx, &first_copy, depth - 1, -beta, -alpha, 1);
    result.best_move = moves.moves[0];
    if (best_score > alpha) {
        alpha = best_score;
    }

    if (moves.count == 1) {
        result.score = best_score;
        result.nodes = first_ctx.nodes;
        search_context_destroy(&first_ctx);
        return result;
    }

    int worker_count = normalize_thread_count(threads, moves.count - 1);
    XThread *handles = (XThread *)calloc((size_t)worker_count, sizeof(XThread));
    RootSearchWorker *workers = (RootSearchWorker *)calloc((size_t)worker_count, sizeof(RootSearchWorker));
    if (!handles || !workers) {
        free(handles);
        free(workers);
        search_context_destroy(&first_ctx);
        SearchContext fallback;
        search_context_init(&fallback, transposition_table, TT_MASK);
        return search_root(&fallback, board, depth, alpha, beta, 1);
    }

    RootSearchShared shared;
    shared.board = board;
    shared.moves = &moves;
    shared.depth = depth;
    shared.beta = beta;
    shared.next_index = 1;
    shared.alpha = alpha;
    shared.best_move = result.best_move;
    shared.best_score = best_score;
    xmutex_init(&shared.mutex);

    for (int i = 0; i < worker_count; ++i) {
        search_context_init_worker(&workers[i].ctx);
        workers[i].shared = &shared;
    }

    int started = 0;
    for (int i = 0; i < worker_count; ++i) {
        if (!xthread_create(&handles[i], root_search_worker_main, &workers[i])) {
            for (int j = 0; j < started; ++j) {
                xthread_join(handles[j]);
            }
            xmutex_destroy(&shared.mutex);
            destroy_root_workers(workers, worker_count);
            free(handles);
            free(workers);
            search_context_destroy(&first_ctx);
            SearchContext fallback;
            search_context_init(&fallback, transposition_table, TT_MASK);
            return search_root(&fallback, board, depth, alpha, beta, 1);
        }
        ++started;
    }

    uint64_t nodes = first_ctx.nodes;
    for (int i = 0; i < worker_count; ++i) {
        xthread_join(handles[i]);
        nodes += workers[i].ctx.nodes;
    }

    best_score = shared.best_score;
    result.best_move = shared.best_move;

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
    result.nodes = nodes;

    xmutex_destroy(&shared.mutex);
    search_context_destroy(&first_ctx);
    destroy_root_workers(workers, worker_count);
    free(handles);
    free(workers);
    return result;
}

SearchResult search_best_move(Board *board, int depth) {
    SearchContext ctx;
    search_context_init(&ctx, transposition_table, TT_MASK);
    return search_root(&ctx, board, depth, -INF_SCORE, INF_SCORE, 1);
}

SearchResult search_best_move_parallel(Board *board, int depth, int threads) {
    if (threads <= 1) {
        return search_best_move(board, depth);
    }
    return search_root_parallel(board, depth, -INF_SCORE, INF_SCORE, threads);
}

SearchResult search_iterative(Board *board, int max_depth) {
    SearchResult final_result;
    final_result.best_move = invalid_move();
    final_result.score = 0;
    final_result.nodes = 0;

    if (max_depth < 1) {
        max_depth = 1;
    }

    uint64_t total_nodes = 0;
    int previous_score = 0;
    SearchContext ctx;
    search_context_init(&ctx, transposition_table, TT_MASK);
    clear_history(&ctx);
    clear_killers(&ctx);

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
            ctx.nodes = 0;
            current = search_root(&ctx, board, depth, alpha, beta, 0);
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

SearchResult search_iterative_parallel(Board *board, int max_depth, int threads) {
    if (threads <= 1) {
        return search_iterative(board, max_depth);
    }

    SearchResult final_result;
    final_result.best_move = invalid_move();
    final_result.score = 0;
    final_result.nodes = 0;

    if (max_depth < 1) {
        max_depth = 1;
    }

    uint64_t total_nodes = 0;
    int previous_score = 0;

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
            current = search_root_parallel(board, depth, alpha, beta, threads);
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
