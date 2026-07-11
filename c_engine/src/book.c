#include "xutrix.h"

#include <string.h>
#include <time.h>

#define BOOK_MAX_CANDIDATES 32

typedef struct {
    const char *move;
    int weight;
} BookCandidate;

static const char *builtin_book_lines[] = {
    /* 1. e4 e5: Ruy Lopez / Italian family */
    "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6 e1g1 f8e7 f1e1 b7b5 a4b3 d7d6 c2c3 e8g8 h2h3",
    "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 c2c3 g8f6 d2d4 e5d4 c3d4 c5b4 b1c3 e8g8 e1g1",
    "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 d2d3 f8c5 c2c3 d7d6 e1g1 e8g8 f1e1 a7a6",
    "e2e4 e7e5 g1f3 b8c6 d2d4 e5d4 f3d4 g8f6 b1c3 f8b4 d4c6 b7c6 f1d3 d7d5",

    /* Sicilian structures */
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6 c1e3 e7e5 d4b3 c8e6 f2f3 f8e7 d1d2 e8g8 e1c1",
    "e2e4 c7c5 g1f3 b8c6 d2d4 c5d4 f3d4 g8f6 b1c3 d7d6 c1g5 e7e6 d1d2 f8e7 e1c1 e8g8",
    "e2e4 c7c5 g1f3 e7e6 d2d4 c5d4 f3d4 b8c6 b1c3 d7d6 c1e3 g8f6 f2f3 f8e7 d1d2 e8g8 e1c1",
    "e2e4 c7c5 g1f3 g7g6 d2d4 c5d4 f3d4 f8g7 c2c4 b8c6 c1e3 g8f6 b1c3 e8g8 f1e2",

    /* French / Caro-Kann */
    "e2e4 e7e6 d2d4 d7d5 b1c3 g8f6 e4e5 f6d7 f2f4 c7c5 g1f3 b8c6 c1e3 f8e7 d1d2 e8g8",
    "e2e4 e7e6 d2d4 d7d5 e4d5 e6d5 g1f3 g8f6 f1d3 f8d6 e1g1 e8g8 c1g5 c7c6",
    "e2e4 c7c6 d2d4 d7d5 e4e5 c8f5 g1f3 e7e6 f1e2 c6c5 e1g1 b8c6 c2c3",
    "e2e4 c7c6 d2d4 d7d5 b1c3 d5e4 c3e4 c8f5 e4g3 f5g6 h2h4 h7h6 g1f3 b8d7",

    /* 1. d4 main lines */
    "d2d4 g8f6 c2c4 e7e6 g1f3 d7d5 b1c3 f8e7 c1f4 e8g8 e2e3 c7c5 d4c5 e7c5",
    "d2d4 g8f6 c2c4 e7e6 b1c3 f8b4 e2e3 e8g8 f1d3 d7d5 g1f3 c7c5 e1g1",
    "d2d4 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6 g1f3 e8g8 f1e2 e7e5 e1g1 b8c6",
    "d2d4 d7d5 c2c4 e7e6 b1c3 g8f6 c1g5 f8e7 e2e3 e8g8 g1f3 h7h6 g5h4",
    "d2d4 d7d5 c2c4 c7c6 g1f3 g8f6 b1c3 d5c4 a2a4 c8f5 e2e3 e7e6 f1c4",

    /* English / Reti */
    "c2c4 e7e5 b1c3 g8f6 g2g3 d7d5 c4d5 f6d5 f1g2 d5b6 g1f3 b8c6 e1g1 f8e7",
    "c2c4 g8f6 b1c3 e7e6 g1f3 d7d5 d2d4 f8e7 c1f4 e8g8 e2e3 c7c5",
    "g1f3 d7d5 d2d4 g8f6 c2c4 e7e6 b1c3 f8e7 c1g5 e8g8 e2e3 h7h6",
    "g1f3 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6 d2d4 e8g8 f1e2 e7e5",
};

static int move_text_from_history(const Board *board, int ply, char out[6]) {
    if (ply < 0 || ply >= board->ply) {
        return 0;
    }
    move_to_uci(board->history[ply].move, out);
    return 1;
}

static int token_matches_history(const Board *board, int ply, const char *token, int token_len) {
    char played[6];
    if (!move_text_from_history(board, ply, played)) {
        return 0;
    }
    return (int)strlen(played) == token_len && strncmp(played, token, (size_t)token_len) == 0;
}

static const char *next_token_after_prefix(const Board *board, const char *line, char out[6]) {
    const char *cursor = line;
    int token_index = 0;

    while (*cursor) {
        while (*cursor == ' ') {
            ++cursor;
        }
        if (*cursor == '\0') {
            break;
        }

        const char *token = cursor;
        int token_len = 0;
        while (cursor[token_len] && cursor[token_len] != ' ') {
            ++token_len;
        }

        if (token_index < board->ply) {
            if (!token_matches_history(board, token_index, token, token_len)) {
                return NULL;
            }
        } else {
            if (token_len < 4 || token_len >= 6) {
                return NULL;
            }
            memcpy(out, token, (size_t)token_len);
            out[token_len] = '\0';
            return out;
        }

        cursor += token_len;
        ++token_index;
    }

    return NULL;
}

static void add_candidate(BookCandidate *candidates, int *count, const char *move) {
    for (int i = 0; i < *count; ++i) {
        if (strcmp(candidates[i].move, move) == 0) {
            ++candidates[i].weight;
            return;
        }
    }
    if (*count >= BOOK_MAX_CANDIDATES) {
        return;
    }
    candidates[*count].move = move;
    candidates[*count].weight = 1;
    ++*count;
}

static uint64_t book_mix(uint64_t value) {
    value ^= value >> 33;
    value *= UINT64_C(0xff51afd7ed558ccd);
    value ^= value >> 33;
    value *= UINT64_C(0xc4ceb9fe1a85ec53);
    value ^= value >> 33;
    return value;
}

static uint64_t book_random_next(void) {
    static uint64_t state = 0;
    if (state == 0) {
        state = (uint64_t)time(NULL) ^ ((uint64_t)clock() << 32) ^ UINT64_C(0x72d0c0de7a11b00c);
    }
    state += UINT64_C(0x9e3779b97f4a7c15);
    return book_mix(state);
}

int opening_book_pick_move(Board *board, int max_ply, Move *move) {
    if (!board || !move || max_ply <= 0 || board->ply < 0 || board->ply >= max_ply) {
        return 0;
    }
    if (in_check(board, board->side_to_move)) {
        return 0;
    }

    BookCandidate candidates[BOOK_MAX_CANDIDATES];
    char candidate_storage[BOOK_MAX_CANDIDATES][6];
    int candidate_count = 0;

    const int line_count = (int)(sizeof(builtin_book_lines) / sizeof(builtin_book_lines[0]));
    for (int i = 0; i < line_count; ++i) {
        char next[6];
        if (!next_token_after_prefix(board, builtin_book_lines[i], next)) {
            continue;
        }

        Move legal;
        if (!parse_uci_move(board, next, &legal)) {
            continue;
        }

        int existing = -1;
        for (int j = 0; j < candidate_count; ++j) {
            if (strcmp(candidate_storage[j], next) == 0) {
                existing = j;
                break;
            }
        }
        if (existing >= 0) {
            ++candidates[existing].weight;
            continue;
        }
        if (candidate_count >= BOOK_MAX_CANDIDATES) {
            continue;
        }
        strcpy(candidate_storage[candidate_count], next);
        add_candidate(candidates, &candidate_count, candidate_storage[candidate_count]);
    }

    if (candidate_count == 0) {
        return 0;
    }

    int total_weight = 0;
    for (int i = 0; i < candidate_count; ++i) {
        total_weight += candidates[i].weight;
    }
    if (total_weight <= 0) {
        return 0;
    }

    uint64_t mixed = book_mix(board->hash ^ book_random_next() ^
                              ((uint64_t)board->ply * UINT64_C(0x9e3779b97f4a7c15)));
    int pick = (int)(mixed % (uint64_t)total_weight);
    const char *chosen = candidates[0].move;
    for (int i = 0; i < candidate_count; ++i) {
        if (pick < candidates[i].weight) {
            chosen = candidates[i].move;
            break;
        }
        pick -= candidates[i].weight;
    }

    return parse_uci_move(board, chosen, move);
}
