#include "xutrix.h"
#include "nnue.h"

static const int material[7] = {
    0, 100, 320, 330, 500, 900, 0
};

static const int pawn_pst[64] = {
      0,   0,   0,   0,   0,   0,   0,   0,
     50,  50,  50,  55,  55,  50,  50,  50,
     10,  10,  20,  35,  35,  20,  10,  10,
      5,   5,  10,  30,  30,  10,   5,   5,
      0,   0,   0,  22,  22,   0,   0,   0,
      5,  -5, -10,   0,   0, -10,  -5,   5,
      5,  10,  10, -25, -25,  10,  10,   5,
      0,   0,   0,   0,   0,   0,   0,   0
};

static const int knight_pst[64] = {
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -30,   5,  12,  18,  18,  12,   5, -30,
    -30,   0,  18,  24,  24,  18,   0, -30,
    -30,   5,  18,  24,  24,  18,   5, -30,
    -30,   0,  12,  18,  18,  12,   0, -30,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50
};

static const int bishop_pst[64] = {
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   0,  10,  15,  15,  10,   0, -10,
    -10,   5,  10,  15,  15,  10,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20
};

static const int rook_pst[64] = {
      0,   0,   5,  10,  10,   5,   0,   0,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
      5,  10,  10,  10,  10,  10,  10,   5,
      0,   0,   0,  10,  10,   0,   0,   0
};

static const int queen_pst[64] = {
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
     -5,   0,   5,   8,   8,   5,   0,  -5,
      0,   0,   5,   8,   8,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   0, -10,
    -10,   0,   5,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20
};

static const int king_mid_pst[64] = {
     20,  30,  10,   0,   0,  10,  30,  20,
     20,  20,   0,   0,   0,   0,  20,  20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30
};

static const int king_end_pst[64] = {
    -50, -30, -30, -30, -30, -30, -30, -50,
    -30, -10, -10, -10, -10, -10, -10, -30,
    -30, -10,  20,  25,  25,  20, -10, -30,
    -30, -10,  25,  40,  40,  25, -10, -30,
    -30, -10,  25,  40,  40,  25, -10, -30,
    -30, -10,  20,  25,  25,  20, -10, -30,
    -30, -10, -10, -10, -10, -10, -10, -30,
    -50, -30, -30, -30, -30, -30, -30, -50
};

static int mirror_square(int sq) {
    int file = sq & 7;
    int rank = sq >> 3;
    return (7 - rank) * 8 + file;
}

static int pst_value(int type, int sq, int endgame) {
    switch (type) {
        case PAWN: return pawn_pst[sq];
        case KNIGHT: return knight_pst[sq];
        case BISHOP: return bishop_pst[sq];
        case ROOK: return rook_pst[sq];
        case QUEEN: return queen_pst[sq];
        case KING: return endgame ? king_end_pst[sq] : king_mid_pst[sq];
        default: return 0;
    }
}

int evaluate_classic_board(const Board *board) {
    int score = 0;
    int non_pawn_material = 0;

    for (int sq = 0; sq < 64; ++sq) {
        int piece = board->squares[sq];
        if (piece == EMPTY) {
            continue;
        }
        int type = piece_type(piece);
        if (type != PAWN && type != KING) {
            non_pawn_material += material[type];
        }
    }

    int endgame = non_pawn_material <= 2600;

    for (int sq = 0; sq < 64; ++sq) {
        int piece = board->squares[sq];
        if (piece == EMPTY) {
            continue;
        }
        int type = piece_type(piece);
        int eval_sq = piece > 0 ? sq : mirror_square(sq);
        int value = material[type] + pst_value(type, eval_sq, endgame);
        score += piece > 0 ? value : -value;
    }

    return score;
}

int evaluate_board(const Board *board) {
    if (nnue_is_loaded()) {
        return nnue_evaluate_board(board);
    }
    return evaluate_classic_board(board);
}
