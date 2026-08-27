#include "xutrix.h"
#include "nnue.h"

static const int material[7] = {
    0, 100, 320, 330, 500, 900, 0
};

#define MAX_PHASE 24

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

static int file_of(int sq) {
    return sq & 7;
}

static int rank_of(int sq) {
    return sq >> 3;
}

static int abs_int(int value) {
    return value < 0 ? -value : value;
}

static int on_board(int file, int rank) {
    return file >= 0 && file < 8 && rank >= 0 && rank < 8;
}

static uint64_t square_mask(int sq) {
    return UINT64_C(1) << sq;
}

static uint64_t file_mask(int file) {
    return UINT64_C(0x0101010101010101) << file;
}

static int popcount64(uint64_t bb) {
    int count = 0;
    while (bb) {
        bb &= bb - 1;
        ++count;
    }
    return count;
}

static int pop_lsb(uint64_t *bb) {
    uint64_t bits = *bb;
    int sq = 0;
    while ((bits & UINT64_C(1)) == 0) {
        bits >>= 1;
        ++sq;
    }
    *bb &= *bb - 1;
    return sq;
}

static int first_square(uint64_t bb) {
    if (!bb) {
        return -1;
    }
    return pop_lsb(&bb);
}

static uint64_t pawn_attacks_from(int sq, int side) {
    uint64_t attacks = 0;
    int file = file_of(sq);
    int rank = rank_of(sq);
    if (side == WHITE) {
        if (file > 0 && rank < 7) attacks |= square_mask(sq + 7);
        if (file < 7 && rank < 7) attacks |= square_mask(sq + 9);
    } else {
        if (file > 0 && rank > 0) attacks |= square_mask(sq - 9);
        if (file < 7 && rank > 0) attacks |= square_mask(sq - 7);
    }
    return attacks;
}

static uint64_t knight_attacks_from(int sq) {
    static const int offsets[8][2] = {
        {1, 2}, {2, 1}, {-1, 2}, {-2, 1},
        {1, -2}, {2, -1}, {-1, -2}, {-2, -1}
    };
    uint64_t attacks = 0;
    int file = file_of(sq);
    int rank = rank_of(sq);
    for (int i = 0; i < 8; ++i) {
        int f = file + offsets[i][0];
        int r = rank + offsets[i][1];
        if (on_board(f, r)) {
            attacks |= square_mask(r * 8 + f);
        }
    }
    return attacks;
}

static uint64_t king_attacks_from(int sq) {
    uint64_t attacks = 0;
    int file = file_of(sq);
    int rank = rank_of(sq);
    for (int df = -1; df <= 1; ++df) {
        for (int dr = -1; dr <= 1; ++dr) {
            if (df == 0 && dr == 0) {
                continue;
            }
            int f = file + df;
            int r = rank + dr;
            if (on_board(f, r)) {
                attacks |= square_mask(r * 8 + f);
            }
        }
    }
    return attacks;
}

static uint64_t ray_attacks_from(int sq, int df, int dr, uint64_t occupied) {
    uint64_t attacks = 0;
    int file = file_of(sq) + df;
    int rank = rank_of(sq) + dr;
    while (on_board(file, rank)) {
        int to = rank * 8 + file;
        uint64_t mask = square_mask(to);
        attacks |= mask;
        if (occupied & mask) {
            break;
        }
        file += df;
        rank += dr;
    }
    return attacks;
}

static uint64_t bishop_attacks_from(int sq, uint64_t occupied) {
    return ray_attacks_from(sq, 1, 1, occupied) |
           ray_attacks_from(sq, 1, -1, occupied) |
           ray_attacks_from(sq, -1, 1, occupied) |
           ray_attacks_from(sq, -1, -1, occupied);
}

static uint64_t rook_attacks_from(int sq, uint64_t occupied) {
    return ray_attacks_from(sq, 1, 0, occupied) |
           ray_attacks_from(sq, -1, 0, occupied) |
           ray_attacks_from(sq, 0, 1, occupied) |
           ray_attacks_from(sq, 0, -1, occupied);
}

static uint64_t queen_attacks_from(int sq, uint64_t occupied) {
    return bishop_attacks_from(sq, occupied) | rook_attacks_from(sq, occupied);
}

static uint64_t all_pawn_attacks(const Board *board, int side) {
    uint64_t attacks = 0;
    uint64_t pawns = board->bitboards[side][PAWN];
    while (pawns) {
        attacks |= pawn_attacks_from(pop_lsb(&pawns), side);
    }
    return attacks;
}

static int relative_rank(int side, int sq) {
    int rank = rank_of(sq);
    return side == WHITE ? rank : 7 - rank;
}

static int pawn_on_file(const Board *board, int side, int file) {
    return (board->bitboards[side][PAWN] & file_mask(file)) != 0;
}

static int major_on_file(const Board *board, int side, int file) {
    uint64_t majors = board->bitboards[side][ROOK] | board->bitboards[side][QUEEN];
    return (majors & file_mask(file)) != 0;
}

static int pawn_defended_by_pawn(const Board *board, int side, int sq) {
    int file = file_of(sq);
    int rank = rank_of(sq);
    int pawn = side == WHITE ? WP : BP;
    if (side == WHITE) {
        if (rank > 0 && file > 0 && board->squares[sq - 9] == pawn) return 1;
        if (rank > 0 && file < 7 && board->squares[sq - 7] == pawn) return 1;
    } else {
        if (rank < 7 && file > 0 && board->squares[sq + 7] == pawn) return 1;
        if (rank < 7 && file < 7 && board->squares[sq + 9] == pawn) return 1;
    }
    return 0;
}

static int pawn_has_neighbor(const Board *board, int side, int sq) {
    int file = file_of(sq);
    int rank = rank_of(sq);
    int pawn = side == WHITE ? WP : BP;
    for (int df = -1; df <= 1; df += 2) {
        int f = file + df;
        if (f < 0 || f >= 8) {
            continue;
        }
        for (int dr = -1; dr <= 1; ++dr) {
            int r = rank + dr;
            if (r >= 0 && r < 8 && board->squares[r * 8 + f] == pawn) {
                return 1;
            }
        }
    }
    return 0;
}

static int is_passed_pawn(const Board *board, int side, int sq) {
    int file = file_of(sq);
    int rank = rank_of(sq);
    int enemy_pawn = side == WHITE ? BP : WP;
    for (int f = file - 1; f <= file + 1; ++f) {
        if (f < 0 || f >= 8) {
            continue;
        }
        if (side == WHITE) {
            for (int r = rank + 1; r < 8; ++r) {
                if (board->squares[r * 8 + f] == enemy_pawn) {
                    return 0;
                }
            }
        } else {
            for (int r = rank - 1; r >= 0; --r) {
                if (board->squares[r * 8 + f] == enemy_pawn) {
                    return 0;
                }
            }
        }
    }
    return 1;
}

static int game_phase(int piece_counts[2][7]) {
    int phase = 0;
    for (int side = WHITE; side <= BLACK; ++side) {
        phase += piece_counts[side][KNIGHT];
        phase += piece_counts[side][BISHOP];
        phase += 2 * piece_counts[side][ROOK];
        phase += 4 * piece_counts[side][QUEEN];
    }
    if (phase > MAX_PHASE) {
        phase = MAX_PHASE;
    }
    return phase;
}

static int pst_value(int type, int sq, int phase) {
    switch (type) {
        case PAWN: return pawn_pst[sq];
        case KNIGHT: return knight_pst[sq];
        case BISHOP: return bishop_pst[sq];
        case ROOK: return rook_pst[sq];
        case QUEEN: return queen_pst[sq];
        case KING: return (king_mid_pst[sq] * phase + king_end_pst[sq] * (MAX_PHASE - phase)) / MAX_PHASE;
        default: return 0;
    }
}

static int evaluate_pawns(const Board *board, int side, int phase) {
    static const int passed_bonus[8] = {0, 0, 8, 16, 28, 45, 75, 0};
    int file_counts[8] = {0};
    int score = 0;
    uint64_t pawns = board->bitboards[side][PAWN];

    uint64_t tmp = pawns;
    while (tmp) {
        int sq = pop_lsb(&tmp);
        ++file_counts[file_of(sq)];
    }

    int islands = 0;
    int in_island = 0;
    for (int file = 0; file < 8; ++file) {
        if (file_counts[file] > 0) {
            if (!in_island) {
                ++islands;
                in_island = 1;
            }
            if (file_counts[file] > 1) {
                score -= 10 * (file_counts[file] - 1);
            }
        } else {
            in_island = 0;
        }
    }
    if (islands > 1) {
        score -= 4 * (islands - 1);
    }

    while (pawns) {
        int sq = pop_lsb(&pawns);
        int file = file_of(sq);
        int has_left = file > 0 && file_counts[file - 1] > 0;
        int has_right = file < 7 && file_counts[file + 1] > 0;
        int rr = relative_rank(side, sq);

        if (!has_left && !has_right) {
            score -= 9;
        }
        if (pawn_has_neighbor(board, side, sq)) {
            score += 4;
        }
        if (is_passed_pawn(board, side, sq)) {
            int bonus = passed_bonus[rr];
            bonus += bonus * (MAX_PHASE - phase) / MAX_PHASE;
            if (pawn_defended_by_pawn(board, side, sq)) {
                bonus += 8 + 2 * rr;
            }
            score += bonus;
        }
    }

    return score;
}

static int evaluate_rooks(const Board *board, int side) {
    int score = 0;
    int enemy = opposite_side(side);
    uint64_t rooks = board->bitboards[side][ROOK];
    int enemy_king = first_square(board->bitboards[enemy][KING]);
    int enemy_back_rank = enemy == WHITE ? 0 : 7;

    while (rooks) {
        int sq = pop_lsb(&rooks);
        int file = file_of(sq);
        if (!pawn_on_file(board, side, file)) {
            score += pawn_on_file(board, enemy, file) ? 10 : 18;
        }
        if (relative_rank(side, sq) == 6) {
            score += 12;
            if (enemy_king >= 0 && rank_of(enemy_king) == enemy_back_rank) {
                score += 8;
            }
        }
    }

    return score;
}

static int evaluate_mobility_and_outposts(const Board *board, int side) {
    int score = 0;
    uint64_t own = board->occupancy[side];
    uint64_t occupied = board->occupied;
    uint64_t enemy_pawn_attacks = all_pawn_attacks(board, opposite_side(side));

    uint64_t pieces = board->bitboards[side][KNIGHT];
    while (pieces) {
        int sq = pop_lsb(&pieces);
        uint64_t targets = knight_attacks_from(sq) & ~own;
        int safe_count = popcount64(targets & ~enemy_pawn_attacks);
        score += (safe_count - 4) * 4;

        int file = file_of(sq);
        int rr = relative_rank(side, sq);
        if (file >= 2 && file <= 5 && rr >= 3 && rr <= 5 &&
            pawn_defended_by_pawn(board, side, sq) && !(enemy_pawn_attacks & square_mask(sq))) {
            score += 18;
        }
    }

    pieces = board->bitboards[side][BISHOP];
    while (pieces) {
        int sq = pop_lsb(&pieces);
        int count = popcount64(bishop_attacks_from(sq, occupied) & ~own);
        score += (count - 7) * 3;
    }

    pieces = board->bitboards[side][ROOK];
    while (pieces) {
        int sq = pop_lsb(&pieces);
        int count = popcount64(rook_attacks_from(sq, occupied) & ~own);
        score += (count - 7) * 2;
    }

    pieces = board->bitboards[side][QUEEN];
    while (pieces) {
        int sq = pop_lsb(&pieces);
        int count = popcount64(queen_attacks_from(sq, occupied) & ~own);
        score += count - 14;
    }

    return score;
}

static int evaluate_threats(const Board *board, int side) {
    int score = 0;
    int enemy = opposite_side(side);
    uint64_t enemy_minors = board->bitboards[enemy][KNIGHT] | board->bitboards[enemy][BISHOP];
    uint64_t enemy_rooks = board->bitboards[enemy][ROOK];
    uint64_t enemy_queen = board->bitboards[enemy][QUEEN];
    uint64_t occupied = board->occupied;

    uint64_t attacks = all_pawn_attacks(board, side);
    score += 12 * popcount64(attacks & enemy_minors);
    score += 25 * popcount64(attacks & enemy_rooks);
    score += 40 * popcount64(attacks & enemy_queen);

    uint64_t pieces = board->bitboards[side][KNIGHT];
    while (pieces) {
        int sq = pop_lsb(&pieces);
        attacks = knight_attacks_from(sq);
        score += 12 * popcount64(attacks & enemy_rooks);
        score += 25 * popcount64(attacks & enemy_queen);
    }

    pieces = board->bitboards[side][BISHOP];
    while (pieces) {
        int sq = pop_lsb(&pieces);
        attacks = bishop_attacks_from(sq, occupied);
        score += 12 * popcount64(attacks & enemy_rooks);
        score += 25 * popcount64(attacks & enemy_queen);
    }

    pieces = board->bitboards[side][ROOK];
    while (pieces) {
        int sq = pop_lsb(&pieces);
        attacks = rook_attacks_from(sq, occupied);
        score += 18 * popcount64(attacks & enemy_queen);
    }

    return score;
}

static int attack_units_to_ring(const Board *board, int side, uint64_t ring) {
    int units = 0;
    uint64_t occupied = board->occupied;
    uint64_t pieces = board->bitboards[side][PAWN];
    while (pieces) {
        units += popcount64(pawn_attacks_from(pop_lsb(&pieces), side) & ring);
    }

    pieces = board->bitboards[side][KNIGHT];
    while (pieces) {
        if (knight_attacks_from(pop_lsb(&pieces)) & ring) {
            units += 2;
        }
    }

    pieces = board->bitboards[side][BISHOP];
    while (pieces) {
        if (bishop_attacks_from(pop_lsb(&pieces), occupied) & ring) {
            units += 2;
        }
    }

    pieces = board->bitboards[side][ROOK];
    while (pieces) {
        if (rook_attacks_from(pop_lsb(&pieces), occupied) & ring) {
            units += 3;
        }
    }

    pieces = board->bitboards[side][QUEEN];
    while (pieces) {
        if (queen_attacks_from(pop_lsb(&pieces), occupied) & ring) {
            units += 5;
        }
    }

    return units;
}

static int evaluate_king_safety(const Board *board, int side, int phase) {
    int king_sq = first_square(board->bitboards[side][KING]);
    if (king_sq < 0 || phase == 0) {
        return 0;
    }

    int score = 0;
    int enemy = opposite_side(side);
    int file = file_of(king_sq);
    int rank = rank_of(king_sq);
    int pawn = side == WHITE ? WP : BP;

    if (file >= 2 && file <= 5) {
        score -= 10;
    }

    for (int df = -1; df <= 1; ++df) {
        int f = file + df;
        if (f < 0 || f >= 8) {
            continue;
        }

        int shield = 0;
        for (int step = 1; step <= 2; ++step) {
            int r = side == WHITE ? rank + step : rank - step;
            if (r >= 0 && r < 8 && board->squares[r * 8 + f] == pawn) {
                shield = 1;
                break;
            }
        }

        score += shield ? 4 : -10;
        if (!pawn_on_file(board, side, f)) {
            score -= 8;
            if (major_on_file(board, enemy, f)) {
                score -= 10;
            }
        }
    }

    uint64_t ring = king_attacks_from(king_sq);
    int units = attack_units_to_ring(board, enemy, ring);
    int attack_penalty = units * units / 2;
    if (attack_penalty > 80) {
        attack_penalty = 80;
    }
    score -= attack_penalty;

    return score * phase / MAX_PHASE;
}

static int evaluate_mop_up(const Board *board, int side, const int side_material[2], int phase) {
    if (phase > 8 || side_material[side] - side_material[opposite_side(side)] < 250) {
        return 0;
    }

    int enemy = opposite_side(side);
    int own_king = first_square(board->bitboards[side][KING]);
    int enemy_king = first_square(board->bitboards[enemy][KING]);
    if (own_king < 0 || enemy_king < 0) {
        return 0;
    }

    int enemy_file = file_of(enemy_king);
    int enemy_rank = rank_of(enemy_king);
    int own_file = file_of(own_king);
    int own_rank = rank_of(own_king);
    int file_center_distance = enemy_file < 4 ? 3 - enemy_file : enemy_file - 4;
    int rank_center_distance = enemy_rank < 4 ? 3 - enemy_rank : enemy_rank - 4;
    int king_distance = abs_int(own_file - enemy_file) + abs_int(own_rank - enemy_rank);
    int closeness = 14 - king_distance;
    int bonus = (file_center_distance + rank_center_distance) * 8 + closeness * 2;

    return bonus * (MAX_PHASE - phase) / MAX_PHASE;
}

static int evaluate_side_features(const Board *board, int side, int phase,
                                  int piece_counts[2][7], const int side_material[2]) {
    int score = 0;
    score += piece_counts[side][BISHOP] >= 2 ? 30 : 0;
    score += evaluate_pawns(board, side, phase);
    score += evaluate_rooks(board, side);
    score += evaluate_mobility_and_outposts(board, side);
    score += evaluate_threats(board, side);
    score += evaluate_king_safety(board, side, phase);
    score += evaluate_mop_up(board, side, side_material, phase);
    return score;
}

int evaluate_classic_board(const Board *board) {
    int score = 0;
    int piece_counts[2][7] = {{0}};
    int side_material[2] = {0};

    for (int sq = 0; sq < 64; ++sq) {
        int piece = board->squares[sq];
        if (piece == EMPTY) {
            continue;
        }
        int type = piece_type(piece);
        int side = piece_color(piece);
        ++piece_counts[side][type];
        side_material[side] += material[type];
    }

    int phase = game_phase(piece_counts);

    for (int sq = 0; sq < 64; ++sq) {
        int piece = board->squares[sq];
        if (piece == EMPTY) {
            continue;
        }
        int type = piece_type(piece);
        int eval_sq = piece > 0 ? sq : mirror_square(sq);
        int value = material[type] + pst_value(type, eval_sq, phase);
        score += piece > 0 ? value : -value;
    }

    score += evaluate_side_features(board, WHITE, phase, piece_counts, side_material);
    score -= evaluate_side_features(board, BLACK, phase, piece_counts, side_material);

    score += board->side_to_move == WHITE ? 8 : -8;

    return score;
}

int evaluate_board(Board *board) {
    if (nnue_is_loaded()) {
        return nnue_evaluate_board(board);
    }
    return evaluate_classic_board(board);
}
