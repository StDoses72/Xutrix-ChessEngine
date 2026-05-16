#ifndef XUTRIX_H
#define XUTRIX_H

#include <stdint.h>
#include <stdio.h>

#define BOARD_SQUARES 64
#define MAX_MOVES 256
#define MAX_PLY 256
#define START_FEN "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

#define WHITE 0
#define BLACK 1

#define EMPTY 0
#define PAWN 1
#define KNIGHT 2
#define BISHOP 3
#define ROOK 4
#define QUEEN 5
#define KING 6

#define WP 1
#define WN 2
#define WB 3
#define WR 4
#define WQ 5
#define WK 6
#define BP -1
#define BN -2
#define BB -3
#define BR -4
#define BQ -5
#define BK -6

#define CASTLE_WHITE_KING 1
#define CASTLE_WHITE_QUEEN 2
#define CASTLE_BLACK_KING 4
#define CASTLE_BLACK_QUEEN 8

#define MOVE_CAPTURE 1
#define MOVE_DOUBLE_PAWN 2
#define MOVE_EN_PASSANT 4
#define MOVE_CASTLE 8
#define MOVE_PROMOTION 16

#define INF_SCORE 100000000
#define MATE_SCORE 1000000

typedef struct {
    uint8_t from;
    uint8_t to;
    uint8_t promotion;
    uint8_t flags;
    int score;
} Move;

typedef struct {
    Move move;
    int8_t captured;
    uint8_t castling;
    int8_t en_passant;
    int halfmove_clock;
    uint64_t hash;
} Undo;

typedef struct {
    Move moves[MAX_MOVES];
    int count;
} MoveList;

typedef struct {
    int8_t squares[BOARD_SQUARES];
    int side_to_move;
    uint8_t castling;
    int8_t en_passant;
    int halfmove_clock;
    int fullmove_number;
    uint64_t hash;
    Undo history[MAX_PLY];
    int ply;
} Board;

typedef struct {
    Move best_move;
    int score;
    uint64_t nodes;
} SearchResult;

void xutrix_init(void);

int piece_color(int piece);
int piece_type(int piece);
int opposite_side(int side);
char piece_to_char(int piece);
int char_to_piece(char ch);
int square_from_string(const char *s);
void square_to_string(int sq, char out[3]);

void board_clear(Board *board);
int board_from_fen(Board *board, const char *fen);
void board_set_startpos(Board *board);
void board_print(const Board *board);
uint64_t board_compute_hash(const Board *board);

int is_square_attacked(const Board *board, int sq, int by_side);
int in_check(const Board *board, int side);
void generate_pseudo_moves(const Board *board, MoveList *list);
void generate_legal_moves(Board *board, MoveList *list);
int make_move(Board *board, Move move);
void undo_move(Board *board);
int parse_uci_move(Board *board, const char *text, Move *move);
void move_to_uci(Move move, char out[6]);
int see_move(const Board *board, Move move);

int evaluate_board(const Board *board);
int evaluate_classic_board(const Board *board);

void tt_clear(void);
uint64_t perft(Board *board, int depth);
SearchResult search_best_move(Board *board, int depth);
SearchResult search_iterative(Board *board, int max_depth);

#endif
