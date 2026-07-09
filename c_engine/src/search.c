#include "xutrix.h"

#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <pthread.h>
#include <stdatomic.h>
#endif

#define TT_SIZE (1u << 20)
#define TT_MASK (TT_SIZE - 1)
#define TT_LOCK_COUNT (1u << 12)
#define TT_LOCK_MASK (TT_LOCK_COUNT - 1)
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
    int worker_id;
    int lock_tt;
    int stopped;
#ifdef _WIN32
    volatile LONG *stop;
#else
    atomic_int *stop;
#endif
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
static XMutex tt_locks[TT_LOCK_COUNT];
static int tt_locks_ready;

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

static void tt_locks_init_once(void) {
    if (tt_locks_ready) {
        return;
    }
    for (uint32_t i = 0; i < TT_LOCK_COUNT; ++i) {
        xmutex_init(&tt_locks[i]);
    }
    tt_locks_ready = 1;
}

static int context_uses_shared_tt(const SearchContext *ctx) {
    return ctx && ctx->lock_tt && ctx->tt == transposition_table;
}

static XMutex *tt_lock_for_hash(uint64_t hash) {
    return &tt_locks[hash & TT_LOCK_MASK];
}

static int xatomic_load_stop(
#ifdef _WIN32
    volatile LONG *stop
#else
    atomic_int *stop
#endif
) {
    if (!stop) {
        return 0;
    }
#ifdef _WIN32
    return InterlockedCompareExchange(stop, 0, 0) != 0;
#else
    return atomic_load_explicit(stop, memory_order_relaxed) != 0;
#endif
}

static void xatomic_store_stop(
#ifdef _WIN32
    volatile LONG *stop
#else
    atomic_int *stop
#endif
) {
    if (!stop) {
        return;
    }
#ifdef _WIN32
    InterlockedExchange(stop, 1);
#else
    atomic_store_explicit(stop, 1, memory_order_relaxed);
#endif
}

static int search_should_stop(SearchContext *ctx) {
    if (ctx && xatomic_load_stop(ctx->stop)) {
        ctx->stopped = 1;
        return 1;
    }
    return 0;
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
    return board->bitboards[side][KNIGHT] || board->bitboards[side][BISHOP] ||
           board->bitboards[side][ROOK] || board->bitboards[side][QUEEN];
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
    if (tt == transposition_table) {
        tt_locks_init_once();
    }
    clear_killers(ctx);
}

static int tt_read(SearchContext *ctx, uint64_t hash, TTEntry *out) {
    if (!ctx->tt) {
        return 0;
    }

    TTEntry *entry = &ctx->tt[hash & ctx->tt_mask];
    if (context_uses_shared_tt(ctx)) {
        XMutex *lock = tt_lock_for_hash(hash);
        xmutex_lock(lock);
        *out = *entry;
        xmutex_unlock(lock);
    } else {
        *out = *entry;
    }
    return 1;
}

static void tt_write(SearchContext *ctx, uint64_t hash, const TTEntry *value) {
    if (!ctx->tt) {
        return;
    }

    TTEntry *entry = &ctx->tt[hash & ctx->tt_mask];
    if (context_uses_shared_tt(ctx)) {
        XMutex *lock = tt_lock_for_hash(hash);
        xmutex_lock(lock);
        *entry = *value;
        xmutex_unlock(lock);
    } else {
        *entry = *value;
    }
}

static int tt_probe(SearchContext *ctx, uint64_t hash, int depth, int *alpha, int *beta,
                    Move *tt_move, int *score) {
    TTEntry entry;
    if (!tt_read(ctx, hash, &entry) || entry.flag == TT_EMPTY || entry.key != hash) {
        return 0;
    }

    *tt_move = entry.best;
    if (entry.depth < depth) {
        return 0;
    }

    if (entry.flag == TT_EXACT) {
        *score = entry.score;
        return 1;
    }
    if (entry.flag == TT_LOWER && entry.score > *alpha) {
        *alpha = entry.score;
    } else if (entry.flag == TT_UPPER && entry.score < *beta) {
        *beta = entry.score;
    }
    if (*alpha >= *beta) {
        *score = entry.score;
        return 1;
    }
    return 0;
}

static Move tt_best_move(SearchContext *ctx, uint64_t hash) {
    TTEntry entry;
    if (!tt_read(ctx, hash, &entry) || entry.flag == TT_EMPTY || entry.key != hash) {
        return invalid_move();
    }
    return entry.best;
}

static void tt_store(SearchContext *ctx, uint64_t hash, Move best_move, int score, int depth, int flag) {
    TTEntry entry;
    entry.key = hash;
    entry.best = best_move;
    entry.score = score;
    entry.depth = depth;
    entry.flag = (uint8_t)flag;
    tt_write(ctx, hash, &entry);
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
    tt_locks_init_once();
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
        if (ctx && ctx->worker_id > 0 && ply == 0 && !move_equal(*move, tt_move)) {
            int seed = move->from * 67 + move->to * 13 + move->promotion * 31 + ctx->worker_id * 97;
            score += seed & 2047;
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
    if (search_should_stop(ctx)) {
        return 0;
    }
    ++ctx->nodes;

    int checked = in_check(board, board->side_to_move);
    MoveList moves;
    if (checked) {
        generate_legal_moves(board, &moves);
        if (moves.count == 0) {
            return -MATE_SCORE + board->ply;
        }
    } else {
        int stand_pat = side_relative_eval(board);
        if (stand_pat >= beta) {
            return beta;
        }
        if (stand_pat > alpha) {
            alpha = stand_pat;
        }
        generate_legal_noisy_moves(board, &moves);
    }

    score_moves(ctx, board, &moves, invalid_move(), board->ply);

    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        if (!checked && (move.flags & MOVE_CAPTURE) && !(move.flags & MOVE_PROMOTION) && see_move(board, move) < 0) {
            continue;
        }
        make_move(board, move);
        int score = -quiescence(ctx, board, -beta, -alpha);
        undo_move(board);
        if (ctx->stopped) {
            return 0;
        }

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
    if (search_should_stop(ctx)) {
        return 0;
    }
    ++ctx->nodes;
    int alpha_original = alpha;
    Move best_move = invalid_move();
    int checked = in_check(board, board->side_to_move);

    Move tt_move = invalid_move();
    int tt_score = 0;
    if (tt_probe(ctx, board->hash, depth, &alpha, &beta, &tt_move, &tt_score)) {
        return tt_score;
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
            if (ctx->stopped) {
                return 0;
            }
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
        if (ctx->stopped) {
            return 0;
        }

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

    int flag = TT_EXACT;
    if (best_score <= alpha_original) {
        flag = TT_UPPER;
    } else if (best_score >= beta) {
        flag = TT_LOWER;
    }
    tt_store(ctx, board->hash, best_move, best_score, depth, flag);

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

    if (search_should_stop(ctx)) {
        result.nodes = ctx->nodes;
        return result;
    }

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

    Move tt_move = tt_best_move(ctx, board->hash);

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
        if (ctx->stopped) {
            result.best_move = invalid_move();
            result.nodes = ctx->nodes;
            return result;
        }
        if (score > best_score) {
            best_score = score;
            result.best_move = move;
        }
        if (score > alpha) {
            alpha = score;
        }
    }

    int flag = TT_EXACT;
    if (best_score <= alpha_original) {
        flag = TT_UPPER;
    } else if (best_score >= beta) {
        flag = TT_LOWER;
    }
    tt_store(ctx, board->hash, result.best_move, best_score, depth, flag);

    result.score = best_score;
    result.nodes = ctx->nodes;
    return result;
}

SearchResult search_best_move(Board *board, int depth) {
    SearchContext ctx;
    search_context_init(&ctx, transposition_table, TT_MASK);
    return search_root(&ctx, board, depth, -INF_SCORE, INF_SCORE, 1);
}

static SearchResult search_iterative_with_context(SearchContext *ctx, Board *board, int max_depth) {
    SearchResult final_result;
    final_result.best_move = invalid_move();
    final_result.score = 0;
    final_result.nodes = 0;

    if (max_depth < 1) {
        max_depth = 1;
    }

    uint64_t total_nodes = 0;
    int previous_score = 0;
    clear_history(ctx);
    clear_killers(ctx);

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
            ctx->nodes = 0;
            current = search_root(ctx, board, depth, alpha, beta, 0);
            total_nodes += current.nodes;
            if (ctx->stopped) {
                final_result.best_move = invalid_move();
                final_result.nodes = total_nodes;
                return final_result;
            }

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

SearchResult search_iterative(Board *board, int max_depth) {
    SearchContext ctx;
    search_context_init(&ctx, transposition_table, TT_MASK);
    return search_iterative_with_context(&ctx, board, max_depth);
}

typedef struct {
    const Board *board;
    int max_depth;
    int worker_id;
#ifdef _WIN32
    volatile LONG *stop;
#else
    atomic_int *stop;
#endif
    SearchContext ctx;
    SearchResult result;
    int completed;
} LazySmpWorker;

static XThreadReturn XTHREAD_CALL lazy_smp_worker_main(void *arg) {
    LazySmpWorker *worker = (LazySmpWorker *)arg;
    Board board = *worker->board;
    search_context_init(&worker->ctx, transposition_table, TT_MASK);
    worker->ctx.worker_id = worker->worker_id;
    worker->ctx.lock_tt = 1;
    worker->ctx.stop = worker->stop;
    worker->result = search_iterative_with_context(&worker->ctx, &board, worker->max_depth);
    if (!worker->ctx.stopped && worker->result.best_move.from < 64) {
        worker->completed = 1;
        xatomic_store_stop(worker->stop);
    }
    return XTHREAD_RETURN;
}

SearchResult search_iterative_parallel(Board *board, int max_depth, int threads) {
    MoveList moves;
    generate_legal_moves(board, &moves);
    threads = normalize_thread_count(threads, moves.count);
    if (threads <= 1 || moves.count <= 1) {
        return search_iterative(board, max_depth);
    }

    tt_locks_init_once();

    XThread *handles = (XThread *)calloc((size_t)threads, sizeof(XThread));
    LazySmpWorker *workers = (LazySmpWorker *)calloc((size_t)threads, sizeof(LazySmpWorker));
    if (!handles || !workers) {
        free(handles);
        free(workers);
        return search_iterative(board, max_depth);
    }

#ifdef _WIN32
    volatile LONG stop = 0;
#else
    atomic_int stop;
    atomic_init(&stop, 0);
#endif

    int started = 0;
    for (int i = 0; i < threads; ++i) {
        workers[i].board = board;
        workers[i].max_depth = max_depth;
        workers[i].worker_id = i;
        workers[i].stop = &stop;
        workers[i].result.best_move = invalid_move();
        if (!xthread_create(&handles[i], lazy_smp_worker_main, &workers[i])) {
            xatomic_store_stop(&stop);
            for (int j = 0; j < started; ++j) {
                xthread_join(handles[j]);
            }
            free(handles);
            free(workers);
            return search_iterative(board, max_depth);
        }
        ++started;
    }

    SearchResult best;
    best.best_move = invalid_move();
    best.score = -INF_SCORE;
    best.nodes = 0;

    for (int i = 0; i < threads; ++i) {
        xthread_join(handles[i]);
        best.nodes += workers[i].result.nodes;
        if (workers[i].completed && workers[i].result.best_move.from < 64 &&
            (best.best_move.from >= 64 || workers[i].result.score > best.score)) {
            best.best_move = workers[i].result.best_move;
            best.score = workers[i].result.score;
        }
    }

    free(handles);
    free(workers);

    if (best.best_move.from >= 64) {
        return search_iterative(board, max_depth);
    }
    return best;
}

SearchResult search_best_move_parallel(Board *board, int depth, int threads) {
    return search_iterative_parallel(board, depth, threads);
}
