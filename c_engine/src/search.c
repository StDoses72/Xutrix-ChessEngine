#include "xutrix.h"

#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <pthread.h>
#include <stdatomic.h>
#include <sys/time.h>
#endif

#define TT_BUCKET_SIZE 4
#define TT_DEFAULT_MB 32
#define TT_MIN_MB 1
#define TT_MAX_MB 4096
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
#define LMR_MIN_DEPTH 3
#define LMR_MIN_MOVE_INDEX 3
#define TIME_CHECK_INTERVAL 2048

typedef struct {
    uint64_t key;
    Move best;
    int score;
    int depth;
    uint8_t flag;
    uint8_t generation;
} TTEntry;

typedef struct {
    TTEntry entries[TT_BUCKET_SIZE];
} TTBucket;

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
    SearchStats stats;
    Move killer_moves[MAX_PLY][2];
    Move counter_moves[2][7][64];
    int history_moves[2][64][64];
    TTBucket *tt;
    uint64_t tt_mask;
    int worker_id;
    int lock_tt;
    int stopped;
    int completed_depth;
    int root_mate_checked;
    uint64_t deadline_ms;
    uint32_t time_check_counter;
    Move root_mate_move;
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

static TTBucket *transposition_table;
static uint64_t tt_bucket_count;
static uint64_t tt_mask;
static int tt_configured_mb = TT_DEFAULT_MB;
static uint8_t tt_generation = 1;
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

static void search_stats_add(SearchStats *dst, const SearchStats *src) {
    dst->tt_probes += src->tt_probes;
    dst->tt_hits += src->tt_hits;
    dst->tt_cutoffs += src->tt_cutoffs;
    dst->qnodes += src->qnodes;
    dst->q_stand_pat_cutoffs += src->q_stand_pat_cutoffs;
    dst->q_see_prunes += src->q_see_prunes;
    dst->q_beta_cutoffs += src->q_beta_cutoffs;
    dst->null_attempts += src->null_attempts;
    dst->null_searches += src->null_searches;
    dst->null_cutoffs += src->null_cutoffs;
    dst->lmr_attempts += src->lmr_attempts;
    dst->lmr_reductions += src->lmr_reductions;
    dst->lmr_researches += src->lmr_researches;
    dst->pvs_researches += src->pvs_researches;
    dst->beta_cutoffs += src->beta_cutoffs;
    dst->aspiration_fail_low += src->aspiration_fail_low;
    dst->aspiration_fail_high += src->aspiration_fail_high;
    dst->aspiration_researches += src->aspiration_researches;
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

static uint64_t floor_power_of_two_u64(uint64_t value) {
    uint64_t result = 1;
    while (result <= value / 2) {
        result <<= 1;
    }
    return result;
}

static uint64_t tt_bucket_count_for_mb(int mb) {
    if (mb < TT_MIN_MB) {
        mb = TT_MIN_MB;
    }
    uint64_t bytes = (uint64_t)mb * 1024u * 1024u;
    uint64_t buckets = bytes / (uint64_t)sizeof(TTBucket);
    if (buckets < 1) {
        buckets = 1;
    }
    return floor_power_of_two_u64(buckets);
}

static int tt_mb_for_bucket_count(uint64_t buckets) {
    uint64_t bytes = buckets * (uint64_t)sizeof(TTBucket);
    uint64_t mb = bytes / (1024u * 1024u);
    if (mb < 1) {
        mb = 1;
    }
    if (mb > (uint64_t)TT_MAX_MB) {
        mb = TT_MAX_MB;
    }
    return (int)mb;
}

static void tt_next_generation(void) {
    ++tt_generation;
    if (tt_generation == 0) {
        tt_generation = 1;
    }
}

int tt_resize_mb(int mb) {
    if (mb < TT_MIN_MB) {
        mb = TT_MIN_MB;
    }
    if (mb > TT_MAX_MB) {
        mb = TT_MAX_MB;
    }

    uint64_t buckets = tt_bucket_count_for_mb(mb);
    TTBucket *new_table = NULL;
    while (buckets >= 1) {
        new_table = (TTBucket *)calloc((size_t)buckets, sizeof(TTBucket));
        if (new_table) {
            break;
        }
        buckets >>= 1;
    }
    if (!new_table) {
        return 0;
    }

    free(transposition_table);
    transposition_table = new_table;
    tt_bucket_count = buckets;
    tt_mask = buckets - 1;
    tt_configured_mb = tt_mb_for_bucket_count(buckets);
    tt_next_generation();
    return tt_configured_mb;
}

static void tt_ensure_initialized(void) {
    if (!transposition_table) {
        (void)tt_resize_mb(tt_configured_mb);
    }
}

int tt_hash_mb(void) {
    tt_ensure_initialized();
    return tt_configured_mb;
}

static TTBucket *tt_shared_table(void) {
    tt_ensure_initialized();
    return transposition_table;
}

static uint64_t tt_shared_mask(void) {
    tt_ensure_initialized();
    return tt_mask;
}

static void tt_start_search(void) {
    tt_ensure_initialized();
    tt_next_generation();
}

static int context_uses_shared_tt(const SearchContext *ctx) {
    return ctx && ctx->lock_tt && ctx->tt == transposition_table;
}

static XMutex *tt_lock_for_hash(uint64_t hash) {
    return &tt_locks[hash & TT_LOCK_MASK];
}

static uint64_t wall_time_ms(void) {
#ifdef _WIN32
    return GetTickCount64();
#else
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (uint64_t)tv.tv_sec * 1000u + (uint64_t)tv.tv_usec / 1000u;
#endif
}

static uint64_t deadline_from_time_ms(int time_ms) {
    if (time_ms <= 0) {
        return 0;
    }
    return wall_time_ms() + (uint64_t)time_ms;
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
    if (!ctx) {
        return 0;
    }
    if (xatomic_load_stop(ctx->stop)) {
        ctx->stopped = 1;
        return 1;
    }
    if (ctx->deadline_ms != 0 &&
        (ctx->time_check_counter++ & (TIME_CHECK_INTERVAL - 1)) == 0 &&
        wall_time_ms() >= ctx->deadline_ms) {
        ctx->stopped = 1;
        xatomic_store_stop(ctx->stop);
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

static int lmr_reduction(int depth, int move_index, Move move, int checked, int gives_check,
                         int alpha, int beta) {
    if (depth < LMR_MIN_DEPTH || move_index < LMR_MIN_MOVE_INDEX || checked || gives_check ||
        is_tactical_move(move) || (move.flags & MOVE_CASTLE) || is_mate_window(alpha, beta)) {
        return 0;
    }

    if (move.score >= 80000) {
        return 0;
    }

    int reduction = 1;
    if (depth >= 6 && move_index >= 6) {
        ++reduction;
    }
    if (depth >= 10 && move_index >= 12) {
        ++reduction;
    }
    if (move.score > 0 && reduction > 1) {
        --reduction;
    }
    if (reduction >= depth) {
        reduction = depth - 1;
    }
    return reduction;
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

static void clear_countermoves(SearchContext *ctx) {
    Move invalid = invalid_move();
    for (int side = WHITE; side <= BLACK; ++side) {
        for (int piece = PAWN; piece <= KING; ++piece) {
            for (int to = 0; to < 64; ++to) {
                ctx->counter_moves[side][piece][to] = invalid;
            }
        }
    }
}

static void search_context_init(SearchContext *ctx, TTBucket *tt, uint64_t mask) {
    memset(ctx, 0, sizeof(*ctx));
    ctx->tt = tt;
    ctx->tt_mask = mask;
    if (tt == transposition_table) {
        tt_locks_init_once();
    }
    clear_killers(ctx);
    clear_countermoves(ctx);
    ctx->root_mate_move = invalid_move();
}

static int tt_read(SearchContext *ctx, uint64_t hash, TTEntry *out) {
    if (!ctx->tt) {
        return 0;
    }

    TTBucket *bucket = &ctx->tt[hash & ctx->tt_mask];
    int found = 0;
    for (int i = 0; i < TT_BUCKET_SIZE; ++i) {
        TTEntry entry = bucket->entries[i];
        if (entry.flag != TT_EMPTY && entry.key == hash) {
            *out = entry;
            found = 1;
            break;
        }
    }
    return found;
}

static int tt_replacement_value(const TTEntry *entry) {
    if (entry->flag == TT_EMPTY) {
        return -1000000;
    }
    int value = entry->depth * 8;
    if (entry->flag == TT_EXACT) {
        value += 8;
    }
    if (entry->generation == tt_generation) {
        value += 64;
    }
    return value;
}

static void tt_assign_entry(TTEntry *dst, const TTEntry *src) {
    dst->flag = TT_EMPTY;
    dst->key = src->key;
    dst->best = src->best;
    dst->score = src->score;
    dst->depth = src->depth;
    dst->generation = src->generation;
    dst->flag = src->flag;
}

static void tt_store_entry(TTEntry *dst, const TTEntry *src, int safe_publish) {
    if (safe_publish) {
        tt_assign_entry(dst, src);
    } else {
        *dst = *src;
    }
}

static void tt_write_bucket(TTBucket *bucket, const TTEntry *value, int safe_publish) {
    TTEntry *replace = &bucket->entries[0];
    int replace_value = tt_replacement_value(replace);

    for (int i = 0; i < TT_BUCKET_SIZE; ++i) {
        TTEntry *entry = &bucket->entries[i];
        if (entry->flag != TT_EMPTY && entry->key == value->key) {
            if (value->depth >= entry->depth || value->flag == TT_EXACT || entry->generation != tt_generation) {
                tt_store_entry(entry, value, safe_publish);
            } else if (is_valid_move(value->best)) {
                entry->best = value->best;
                entry->generation = tt_generation;
            }
            return;
        }
        int candidate_value = tt_replacement_value(entry);
        if (candidate_value < replace_value) {
            replace = entry;
            replace_value = candidate_value;
        }
    }

    tt_store_entry(replace, value, safe_publish);
}

static void tt_write(SearchContext *ctx, uint64_t hash, const TTEntry *value) {
    if (!ctx->tt) {
        return;
    }

    TTBucket *bucket = &ctx->tt[hash & ctx->tt_mask];
    if (context_uses_shared_tt(ctx)) {
        XMutex *lock = tt_lock_for_hash(hash);
        xmutex_lock(lock);
        tt_write_bucket(bucket, value, 1);
        xmutex_unlock(lock);
    } else {
        tt_write_bucket(bucket, value, 0);
    }
}

static int tt_probe(SearchContext *ctx, uint64_t hash, int depth, int *alpha, int *beta,
                    Move *tt_move, int *score) {
    ++ctx->stats.tt_probes;
    TTEntry entry;
    if (!tt_read(ctx, hash, &entry)) {
        return 0;
    }
    ++ctx->stats.tt_hits;

    *tt_move = entry.best;
    if (entry.depth < depth) {
        return 0;
    }

    if (entry.flag == TT_EXACT) {
        *score = entry.score;
        ++ctx->stats.tt_cutoffs;
        return 1;
    }
    if (entry.flag == TT_LOWER && entry.score > *alpha) {
        *alpha = entry.score;
    } else if (entry.flag == TT_UPPER && entry.score < *beta) {
        *beta = entry.score;
    }
    if (*alpha >= *beta) {
        *score = entry.score;
        ++ctx->stats.tt_cutoffs;
        return 1;
    }
    return 0;
}

static Move tt_best_move(SearchContext *ctx, uint64_t hash) {
    TTEntry entry;
    if (!tt_read(ctx, hash, &entry)) {
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
    entry.generation = tt_generation;
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
    if (*entry + bonus > HISTORY_MAX) {
        int abs_bonus = bonus < 0 ? -bonus : bonus;
        *entry += bonus - (int)(((long long)*entry * abs_bonus) / HISTORY_MAX);
    } else {
        *entry += bonus;
    }
    if (*entry > HISTORY_MAX) {
        *entry = HISTORY_MAX;
    } else if (*entry < -HISTORY_MAX) {
        *entry = -HISTORY_MAX;
    }
}

static int counter_key_piece(const Board *board, Move previous_move) {
    if (!is_valid_move(previous_move)) {
        return EMPTY;
    }
    int piece = board->squares[previous_move.to];
    if (piece == EMPTY || piece_color(piece) == board->side_to_move) {
        return EMPTY;
    }
    return piece_type(piece);
}

static void store_countermove(SearchContext *ctx, const Board *board, Move previous_move, Move move, int side) {
    if (!ctx || side < WHITE || side > BLACK || is_tactical_move(move)) {
        return;
    }
    int previous_piece = counter_key_piece(board, previous_move);
    if (previous_piece == EMPTY) {
        return;
    }
    ctx->counter_moves[side][previous_piece][previous_move.to] = move;
}

void tt_clear(void) {
    tt_locks_init_once();
    tt_ensure_initialized();
    if (transposition_table && tt_bucket_count > 0) {
        memset(transposition_table, 0, (size_t)tt_bucket_count * sizeof(TTBucket));
    }
    tt_next_generation();
}

static int piece_value(int piece) {
    static const int values[7] = {0, 100, 320, 330, 500, 900, 20000};
    return values[piece_type(piece)];
}

static int side_relative_eval(Board *board) {
    int eval = evaluate_board(board);
    return board->side_to_move == WHITE ? eval : -eval;
}

static SearchResult fallback_search_result(Board *board) {
    SearchResult result;
    memset(&result, 0, sizeof(result));
    result.best_move = invalid_move();
    result.score = 0;
    result.nodes = 0;
    result.depth = 0;

    MoveList moves;
    generate_legal_moves(board, &moves);
    if (moves.count > 0) {
        result.best_move = moves.moves[0];
        result.score = side_relative_eval(board);
    }
    return result;
}

static int move_delivers_checkmate(Board *board, Move move) {
    make_move(board, move);
    int defender = board->side_to_move;
    int checkmate = 0;
    if (in_check(board, defender)) {
        MoveList replies;
        generate_legal_moves(board, &replies);
        checkmate = replies.count == 0;
    }
    undo_move(board);
    return checkmate;
}

static Move find_mate_in_one(Board *board, const MoveList *moves) {
    for (int i = 0; i < moves->count; ++i) {
        Move move = moves->moves[i];
        if (move_delivers_checkmate(board, move)) {
            return move;
        }
    }
    return invalid_move();
}

static void score_moves(SearchContext *ctx, const Board *board, MoveList *list, Move tt_move, int ply,
                        Move previous_move) {
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
            int history = ctx ? ctx->history_moves[board->side_to_move][move->from][move->to] : 0;
            if (ctx && move_equal(*move, ctx->killer_moves[ply][0])) {
                score += 90000;
            } else if (ctx && move_equal(*move, ctx->killer_moves[ply][1])) {
                score += 80000;
            } else if (ctx) {
                int previous_piece = counter_key_piece(board, previous_move);
                if (ply <= 2 && history > 0 && previous_piece != EMPTY &&
                    move_equal(*move, ctx->counter_moves[board->side_to_move][previous_piece][previous_move.to])) {
                    score += 1;
                }
            }
            score += history;
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

static int quiescence(SearchContext *ctx, Board *board, int alpha, int beta, int ply) {
    if (search_should_stop(ctx)) {
        return 0;
    }
    ++ctx->nodes;
    ++ctx->stats.qnodes;

    int checked = in_check(board, board->side_to_move);
    MoveList moves;
    if (checked) {
        generate_legal_moves(board, &moves);
        if (moves.count == 0) {
            return -MATE_SCORE + ply;
        }
    } else {
        int stand_pat = side_relative_eval(board);
        if (stand_pat >= beta) {
            ++ctx->stats.q_stand_pat_cutoffs;
            ++ctx->stats.q_beta_cutoffs;
            return beta;
        }
        if (stand_pat > alpha) {
            alpha = stand_pat;
        }
        generate_legal_noisy_moves(board, &moves);
    }

    score_moves(ctx, board, &moves, invalid_move(), ply, invalid_move());

    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        if (!checked && (move.flags & MOVE_CAPTURE) && !(move.flags & MOVE_PROMOTION) && see_move(board, move) < 0) {
            ++ctx->stats.q_see_prunes;
            continue;
        }
        make_move(board, move);
        int score = -quiescence(ctx, board, -beta, -alpha, ply + 1);
        undo_move(board);
        if (ctx->stopped) {
            return 0;
        }

        if (score >= beta) {
            ++ctx->stats.q_beta_cutoffs;
            return beta;
        }
        if (score > alpha) {
            alpha = score;
        }
    }

    return alpha;
}

static int negamax(SearchContext *ctx, Board *board, int depth, int alpha, int beta, int ply, Move previous_move) {
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

    if (depth == 0) {
        return quiescence(ctx, board, alpha, beta, ply);
    }

    MoveList moves;
    generate_legal_moves(board, &moves);

    if (moves.count == 0) {
        if (checked) {
            return -MATE_SCORE + ply;
        }
        return 0;
    }

    if (depth >= NULL_MOVE_MIN_DEPTH && !checked && !is_mate_window(alpha, beta) &&
        has_non_pawn_material(board, board->side_to_move)) {
        ++ctx->stats.null_attempts;
        if (side_relative_eval(board) >= beta) {
            NullMoveUndo undo;
            if (make_null_move(board, &undo)) {
                ++ctx->stats.null_searches;
                int reduction = NULL_MOVE_REDUCTION + depth / 6;
                int reduced_depth = depth - 1 - reduction;
                if (reduced_depth < 0) {
                    reduced_depth = 0;
                }
                int score = -negamax(ctx, board, reduced_depth, -beta, -beta + 1, ply + 1, invalid_move());
                undo_null_move(board, &undo);
                if (ctx->stopped) {
                    return 0;
                }
                if (score >= beta) {
                    ++ctx->stats.null_cutoffs;
                    return beta;
                }
            }
        }
    }

    score_moves(ctx, board, &moves, tt_move, ply, previous_move);

    int best_score = -INF_SCORE;
    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        make_move(board, move);
        int score;
        if (i == 0) {
            score = -negamax(ctx, board, depth - 1, -beta, -alpha, ply + 1, move);
        } else {
            int child_depth = depth - 1;
            int gives_check = in_check(board, board->side_to_move);
            ++ctx->stats.lmr_attempts;
            int reduction = lmr_reduction(depth, i, move, checked, gives_check, alpha, beta);
            if (reduction > 0 && child_depth - reduction > 0) {
                ++ctx->stats.lmr_reductions;
                score = -negamax(ctx, board, child_depth - reduction, -alpha - 1, -alpha, ply + 1, move);
                if (!ctx->stopped && score > alpha) {
                    ++ctx->stats.lmr_researches;
                    score = -negamax(ctx, board, child_depth, -alpha - 1, -alpha, ply + 1, move);
                }
            } else {
                score = -negamax(ctx, board, child_depth, -alpha - 1, -alpha, ply + 1, move);
            }
            if (score > alpha && score < beta) {
                ++ctx->stats.pvs_researches;
                score = -negamax(ctx, board, child_depth, -beta, -alpha, ply + 1, move);
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
            ++ctx->stats.beta_cutoffs;
            store_killer(ctx, move, ply);
            store_history(ctx, move, board->side_to_move, depth);
            store_countermove(ctx, board, previous_move, move, board->side_to_move);
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

uint64_t perft_filtered(Board *board, int depth) {
    if (depth == 0) {
        return 1;
    }

    MoveList moves;
    generate_legal_moves_filtered(board, &moves);
    if (depth == 1) {
        return (uint64_t)moves.count;
    }

    uint64_t nodes = 0;
    for (int i = 0; i < moves.count; ++i) {
        make_move(board, moves.moves[i]);
        nodes += perft_filtered(board, depth - 1);
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
    memset(&result, 0, sizeof(result));
    result.best_move = invalid_move();
    result.score = 0;
    result.nodes = ctx->nodes;
    result.depth = 0;

    if (search_should_stop(ctx)) {
        result.nodes = ctx->nodes;
        result.stats = ctx->stats;
        return result;
    }

    if (depth < 1) {
        depth = 1;
    }

    if (reset_heuristics) {
        clear_history(ctx);
        clear_killers(ctx);
        clear_countermoves(ctx);
    }

    int alpha_original = alpha;
    MoveList moves;
    generate_legal_moves(board, &moves);
    if (moves.count == 0) {
        result.score = in_check(board, board->side_to_move) ? -MATE_SCORE : 0;
        result.nodes = ctx->nodes;
        result.depth = depth;
        result.stats = ctx->stats;
        return result;
    }

    if (!ctx->root_mate_checked) {
        ctx->root_mate_move = find_mate_in_one(board, &moves);
        ctx->root_mate_checked = 1;
    }
    if (is_valid_move(ctx->root_mate_move)) {
        result.best_move = ctx->root_mate_move;
        result.score = MATE_SCORE - 1;
        result.nodes = ctx->nodes;
        result.depth = depth;
        result.stats = ctx->stats;
        tt_store(ctx, board->hash, ctx->root_mate_move, result.score, depth, TT_EXACT);
        return result;
    }

    Move tt_move = tt_best_move(ctx, board->hash);

    score_moves(ctx, board, &moves, tt_move, 0, invalid_move());

    int best_score = -INF_SCORE;

    for (int i = 0; i < moves.count; ++i) {
        Move move = moves.moves[i];
        make_move(board, move);
        int score;
        if (i == 0) {
            score = -negamax(ctx, board, depth - 1, -beta, -alpha, 1, move);
        } else {
            score = -negamax(ctx, board, depth - 1, -alpha - 1, -alpha, 1, move);
            if (score > alpha && score < beta) {
                ++ctx->stats.pvs_researches;
                score = -negamax(ctx, board, depth - 1, -beta, -alpha, 1, move);
            }
        }
        undo_move(board);
        if (ctx->stopped) {
            result.best_move = invalid_move();
            result.nodes = ctx->nodes;
            result.depth = 0;
            result.stats = ctx->stats;
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
    result.depth = depth;
    result.stats = ctx->stats;
    return result;
}

SearchResult search_best_move(Board *board, int depth) {
    SearchContext ctx;
    tt_start_search();
    search_context_init(&ctx, tt_shared_table(), tt_shared_mask());
    return search_root(&ctx, board, depth, -INF_SCORE, INF_SCORE, 1);
}

static SearchResult search_iterative_with_context(SearchContext *ctx, Board *board, int max_depth) {
    SearchResult final_result = fallback_search_result(board);
    ctx->completed_depth = 0;

    if (max_depth < 1) {
        max_depth = 1;
    }

    uint64_t total_nodes = 0;
    int previous_score = 0;
    clear_history(ctx);
    clear_killers(ctx);
    clear_countermoves(ctx);

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
                final_result.nodes = total_nodes;
                final_result.stats = ctx->stats;
                return final_result;
            }

            if (depth == 1 || (current.score > alpha && current.score < beta)) {
                break;
            }

            int failed_low = current.score <= alpha;
            if (failed_low) {
                ++ctx->stats.aspiration_fail_low;
            } else {
                ++ctx->stats.aspiration_fail_high;
            }
            ++attempts;
            ++ctx->stats.aspiration_researches;
            if (attempts >= 4) {
                alpha = -INF_SCORE;
                beta = INF_SCORE;
            } else if (failed_low) {
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
        ctx->completed_depth = current.depth;
        if (current.best_move.from >= 64) {
            break;
        }
        if (current.score >= MATE_SCORE - 1) {
            break;
        }
    }

    final_result.stats = ctx->stats;
    return final_result;
}

SearchResult search_iterative(Board *board, int max_depth) {
    SearchContext ctx;
    tt_start_search();
    search_context_init(&ctx, tt_shared_table(), tt_shared_mask());
    return search_iterative_with_context(&ctx, board, max_depth);
}

SearchResult search_iterative_timed(Board *board, int max_depth, int time_ms) {
    SearchContext ctx;
    tt_start_search();
    search_context_init(&ctx, tt_shared_table(), tt_shared_mask());
    ctx.deadline_ms = deadline_from_time_ms(time_ms);
    return search_iterative_with_context(&ctx, board, max_depth);
}

typedef struct {
    const Board *board;
    int max_depth;
    int worker_id;
    uint64_t deadline_ms;
#ifdef _WIN32
    volatile LONG *stop;
#else
    atomic_int *stop;
#endif
    SearchContext ctx;
    SearchResult result;
    int completed;
    int completed_depth;
} LazySmpWorker;

static XThreadReturn XTHREAD_CALL lazy_smp_worker_main(void *arg) {
    LazySmpWorker *worker = (LazySmpWorker *)arg;
    Board board = *worker->board;
    search_context_init(&worker->ctx, tt_shared_table(), tt_shared_mask());
    worker->ctx.worker_id = worker->worker_id;
    worker->ctx.lock_tt = 1;
    worker->ctx.stop = worker->stop;
    worker->ctx.deadline_ms = worker->deadline_ms;
    worker->result = search_iterative_with_context(&worker->ctx, &board, worker->max_depth);
    worker->completed_depth = worker->ctx.completed_depth;
    worker->completed = !worker->ctx.stopped && worker->completed_depth >= worker->max_depth &&
                        worker->result.best_move.from < 64;
    if (worker->completed) {
        xatomic_store_stop(worker->stop);
    }
    return XTHREAD_RETURN;
}

static int lazy_smp_worker_has_result(const LazySmpWorker *worker) {
    return worker->completed_depth > 0 && worker->result.best_move.from < 64;
}

static int lazy_smp_worker_is_better(const LazySmpWorker *candidate, const LazySmpWorker *current) {
    if (!lazy_smp_worker_has_result(candidate)) {
        return 0;
    }
    if (!current || !lazy_smp_worker_has_result(current)) {
        return 1;
    }
    if (candidate->completed_depth != current->completed_depth) {
        return candidate->completed_depth > current->completed_depth;
    }
    if (candidate->worker_id == 0 && current->worker_id != 0) {
        return 1;
    }
    if (candidate->worker_id != 0 && current->worker_id == 0) {
        return 0;
    }
    if (candidate->completed != current->completed) {
        return candidate->completed;
    }
    if (candidate->result.nodes != current->result.nodes) {
        return candidate->result.nodes > current->result.nodes;
    }
    return candidate->result.score > current->result.score;
}

static SearchResult search_iterative_parallel_with_limit(Board *board, int max_depth, int threads, int time_ms) {
    MoveList moves;
    generate_legal_moves(board, &moves);
    threads = normalize_thread_count(threads, moves.count);
    if (threads <= 1 || moves.count <= 1) {
        return time_ms > 0 ? search_iterative_timed(board, max_depth, time_ms) : search_iterative(board, max_depth);
    }

    tt_start_search();
    tt_locks_init_once();

    XThread *handles = (XThread *)calloc((size_t)threads, sizeof(XThread));
    LazySmpWorker *workers = (LazySmpWorker *)calloc((size_t)threads, sizeof(LazySmpWorker));
    if (!handles || !workers) {
        free(handles);
        free(workers);
        return time_ms > 0 ? search_iterative_timed(board, max_depth, time_ms) : search_iterative(board, max_depth);
    }

    uint64_t deadline_ms = deadline_from_time_ms(time_ms);

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
        workers[i].deadline_ms = deadline_ms;
        workers[i].stop = &stop;
        memset(&workers[i].result, 0, sizeof(workers[i].result));
        workers[i].result.best_move = invalid_move();
        workers[i].result.score = 0;
        workers[i].result.nodes = 0;
        workers[i].result.depth = 0;
        if (!xthread_create(&handles[i], lazy_smp_worker_main, &workers[i])) {
            xatomic_store_stop(&stop);
            for (int j = 0; j < started; ++j) {
                xthread_join(handles[j]);
            }
            free(handles);
            free(workers);
            return time_ms > 0 ? search_iterative_timed(board, max_depth, time_ms) : search_iterative(board, max_depth);
        }
        ++started;
    }

    SearchResult best;
    best.best_move = invalid_move();
    best.score = -INF_SCORE;
    best.nodes = 0;
    best.depth = 0;
    int best_worker = -1;
    uint64_t total_nodes = 0;
    SearchStats total_stats = {0};

    for (int i = 0; i < threads; ++i) {
        xthread_join(handles[i]);
        total_nodes += workers[i].result.nodes;
        search_stats_add(&total_stats, &workers[i].result.stats);
        LazySmpWorker *current = best_worker >= 0 ? &workers[best_worker] : NULL;
        if (lazy_smp_worker_is_better(&workers[i], current)) {
            best_worker = i;
        }
    }

    if (best_worker >= 0) {
        best = workers[best_worker].result;
        best.nodes = total_nodes;
        best.stats = total_stats;
        free(handles);
        free(workers);
        return best;
    }

    free(handles);
    free(workers);
    return fallback_search_result(board);
}

SearchResult search_iterative_parallel(Board *board, int max_depth, int threads) {
    return search_iterative_parallel_with_limit(board, max_depth, threads, 0);
}

SearchResult search_iterative_parallel_timed(Board *board, int max_depth, int threads, int time_ms) {
    return search_iterative_parallel_with_limit(board, max_depth, threads, time_ms);
}

SearchResult search_best_move_parallel(Board *board, int depth, int threads) {
    return search_iterative_parallel(board, depth, threads);
}
