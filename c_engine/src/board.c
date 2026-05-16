#include "xutrix.h"

#include <ctype.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>

static uint64_t zobrist_piece[12][64];
static uint64_t zobrist_castling[16];
static uint64_t zobrist_ep_file[8];
static uint64_t zobrist_black_to_move;

static uint64_t splitmix64_next(uint64_t *state) {
    uint64_t z = (*state += UINT64_C(0x9e3779b97f4a7c15));
    z = (z ^ (z >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    z = (z ^ (z >> 27)) * UINT64_C(0x94d049bb133111eb);
    return z ^ (z >> 31);
}

static int zobrist_piece_index(int piece) {
    switch (piece) {
        case WP: return 0;
        case WN: return 1;
        case WB: return 2;
        case WR: return 3;
        case WQ: return 4;
        case WK: return 5;
        case BP: return 6;
        case BN: return 7;
        case BB: return 8;
        case BR: return 9;
        case BQ: return 10;
        case BK: return 11;
        default: return -1;
    }
}

void xutrix_init(void) {
    static int initialized = 0;
    if (initialized) {
        return;
    }

    uint64_t seed = UINT64_C(0x1123581321345589);
    for (int p = 0; p < 12; ++p) {
        for (int sq = 0; sq < 64; ++sq) {
            zobrist_piece[p][sq] = splitmix64_next(&seed);
        }
    }
    for (int i = 0; i < 16; ++i) {
        zobrist_castling[i] = splitmix64_next(&seed);
    }
    for (int i = 0; i < 8; ++i) {
        zobrist_ep_file[i] = splitmix64_next(&seed);
    }
    zobrist_black_to_move = splitmix64_next(&seed);
    initialized = 1;
}

int piece_color(int piece) {
    if (piece > 0) {
        return WHITE;
    }
    if (piece < 0) {
        return BLACK;
    }
    return -1;
}

int piece_type(int piece) {
    return piece < 0 ? -piece : piece;
}

int opposite_side(int side) {
    return side == WHITE ? BLACK : WHITE;
}

char piece_to_char(int piece) {
    switch (piece) {
        case WP: return 'P';
        case WN: return 'N';
        case WB: return 'B';
        case WR: return 'R';
        case WQ: return 'Q';
        case WK: return 'K';
        case BP: return 'p';
        case BN: return 'n';
        case BB: return 'b';
        case BR: return 'r';
        case BQ: return 'q';
        case BK: return 'k';
        default: return '.';
    }
}

int char_to_piece(char ch) {
    switch (ch) {
        case 'P': return WP;
        case 'N': return WN;
        case 'B': return WB;
        case 'R': return WR;
        case 'Q': return WQ;
        case 'K': return WK;
        case 'p': return BP;
        case 'n': return BN;
        case 'b': return BB;
        case 'r': return BR;
        case 'q': return BQ;
        case 'k': return BK;
        default: return EMPTY;
    }
}

int square_from_string(const char *s) {
    if (!s || s[0] < 'a' || s[0] > 'h' || s[1] < '1' || s[1] > '8') {
        return -1;
    }
    int file = s[0] - 'a';
    int rank = s[1] - '1';
    return rank * 8 + file;
}

void square_to_string(int sq, char out[3]) {
    out[0] = (char)('a' + (sq % 8));
    out[1] = (char)('1' + (sq / 8));
    out[2] = '\0';
}

void board_clear(Board *board) {
    xutrix_init();
    memset(board, 0, sizeof(*board));
    for (int i = 0; i < 64; ++i) {
        board->squares[i] = EMPTY;
    }
    board->side_to_move = WHITE;
    board->en_passant = -1;
    board->fullmove_number = 1;
    board->hash = board_compute_hash(board);
}

uint64_t board_compute_hash(const Board *board) {
    uint64_t h = 0;
    for (int sq = 0; sq < 64; ++sq) {
        int idx = zobrist_piece_index(board->squares[sq]);
        if (idx >= 0) {
            h ^= zobrist_piece[idx][sq];
        }
    }
    if (board->side_to_move == BLACK) {
        h ^= zobrist_black_to_move;
    }
    h ^= zobrist_castling[board->castling & 15];
    if (board->en_passant >= 0) {
        h ^= zobrist_ep_file[board->en_passant % 8];
    }
    return h;
}

int board_from_fen(Board *board, const char *fen) {
    board_clear(board);
    if (!fen || !*fen) {
        fen = START_FEN;
    }

    int rank = 7;
    int file = 0;
    const char *p = fen;

    while (*p && *p != ' ') {
        if (*p == '/') {
            if (file != 8) {
                return 0;
            }
            --rank;
            file = 0;
        } else if (isdigit((unsigned char)*p)) {
            int empty = *p - '0';
            if (empty < 1 || empty > 8 || file + empty > 8) {
                return 0;
            }
            file += empty;
        } else {
            int piece = char_to_piece(*p);
            if (piece == EMPTY || rank < 0 || file >= 8) {
                return 0;
            }
            board->squares[rank * 8 + file] = (int8_t)piece;
            ++file;
        }
        ++p;
    }

    if (rank != 0 || file != 8 || *p != ' ') {
        return 0;
    }
    ++p;

    if (*p == 'w') {
        board->side_to_move = WHITE;
    } else if (*p == 'b') {
        board->side_to_move = BLACK;
    } else {
        return 0;
    }
    while (*p && *p != ' ') {
        ++p;
    }
    if (*p != ' ') {
        return 0;
    }
    ++p;

    board->castling = 0;
    if (*p == '-') {
        ++p;
    } else {
        while (*p && *p != ' ') {
            if (*p == 'K') board->castling |= CASTLE_WHITE_KING;
            else if (*p == 'Q') board->castling |= CASTLE_WHITE_QUEEN;
            else if (*p == 'k') board->castling |= CASTLE_BLACK_KING;
            else if (*p == 'q') board->castling |= CASTLE_BLACK_QUEEN;
            else return 0;
            ++p;
        }
    }
    if (*p != ' ') {
        return 0;
    }
    ++p;

    if (*p == '-') {
        board->en_passant = -1;
        ++p;
    } else {
        int sq = square_from_string(p);
        if (sq < 0) {
            return 0;
        }
        board->en_passant = (int8_t)sq;
        p += 2;
    }

    if (*p == ' ') {
        ++p;
        board->halfmove_clock = atoi(p);
        while (*p && *p != ' ') {
            ++p;
        }
    }
    if (*p == ' ') {
        ++p;
        board->fullmove_number = atoi(p);
        if (board->fullmove_number <= 0) {
            board->fullmove_number = 1;
        }
    }

    board->ply = 0;
    board->hash = board_compute_hash(board);
    return 1;
}

void board_set_startpos(Board *board) {
    (void)board_from_fen(board, START_FEN);
}

void board_print(const Board *board) {
    printf("\n");
    for (int rank = 7; rank >= 0; --rank) {
        printf("%d  ", rank + 1);
        for (int file = 0; file < 8; ++file) {
            printf("%c ", piece_to_char(board->squares[rank * 8 + file]));
        }
        printf("\n");
    }
    printf("\n   a b c d e f g h\n");
    printf("side: %s  castling: %c%c%c%c  ep: ",
           board->side_to_move == WHITE ? "white" : "black",
           (board->castling & CASTLE_WHITE_KING) ? 'K' : '-',
           (board->castling & CASTLE_WHITE_QUEEN) ? 'Q' : '-',
           (board->castling & CASTLE_BLACK_KING) ? 'k' : '-',
           (board->castling & CASTLE_BLACK_QUEEN) ? 'q' : '-');
    if (board->en_passant >= 0) {
        char sq[3];
        square_to_string(board->en_passant, sq);
        printf("%s", sq);
    } else {
        printf("-");
    }
    printf("  hash: 0x%016" PRIx64 "\n", board->hash);
}
