#include "xutrix.h"

#include <ctype.h>
#include <stdlib.h>
#include <string.h>

#if defined(_MSC_VER)
#include <intrin.h>
#endif

#define NOT_FILE_A UINT64_C(0xfefefefefefefefe)
#define NOT_FILE_H UINT64_C(0x7f7f7f7f7f7f7f7f)

static uint64_t knight_attack_table[BOARD_SQUARES];
static uint64_t king_attack_table[BOARD_SQUARES];
static uint64_t pawn_attack_table[2][BOARD_SQUARES];
static uint64_t between_table[BOARD_SQUARES][BOARD_SQUARES];
static int attack_tables_initialized = 0;

static int file_of(int sq) {
    return sq & 7;
}

static int rank_of(int sq) {
    return sq >> 3;
}

static int on_board(int file, int rank) {
    return file >= 0 && file < 8 && rank >= 0 && rank < 8;
}

static uint64_t square_mask(int sq) {
    return UINT64_C(1) << sq;
}

static int bit_scan_forward(uint64_t bb) {
#if defined(_MSC_VER)
    unsigned long index = 0;
    _BitScanForward64(&index, bb);
    return (int)index;
#elif defined(__GNUC__) || defined(__clang__)
    return __builtin_ctzll(bb);
#else
    int sq = 0;
    while ((bb & square_mask(sq)) == 0) {
        ++sq;
    }
    return sq;
#endif
}

static int pop_lsb(uint64_t *bb) {
    int sq = bit_scan_forward(*bb);
    *bb &= *bb - 1;
    return sq;
}

static int popcount64(uint64_t bb) {
    int count = 0;
    while (bb) {
        bb &= bb - 1;
        ++count;
    }
    return count;
}

static void bitboard_add_piece(Board *board, int piece, int sq, uint64_t *hash) {
    if (piece == EMPTY) {
        return;
    }
    int side = piece_color(piece);
    int type = piece_type(piece);
    uint64_t mask = square_mask(sq);
    board->bitboards[side][type] |= mask;
    board->occupancy[side] |= mask;
    board->occupied |= mask;
    if (hash) {
        *hash ^= board_hash_piece(piece, sq);
    }
}

static void bitboard_remove_piece(Board *board, int piece, int sq, uint64_t *hash) {
    if (piece == EMPTY) {
        return;
    }
    int side = piece_color(piece);
    int type = piece_type(piece);
    uint64_t mask = square_mask(sq);
    board->bitboards[side][type] &= ~mask;
    board->occupancy[side] &= ~mask;
    board->occupied &= ~mask;
    if (hash) {
        *hash ^= board_hash_piece(piece, sq);
    }
}

static void put_piece(Board *board, int piece, int sq, uint64_t *hash) {
    board->squares[sq] = (int8_t)piece;
    bitboard_add_piece(board, piece, sq, hash);
}

static void clear_piece(Board *board, int piece, int sq, uint64_t *hash) {
    board->squares[sq] = EMPTY;
    bitboard_remove_piece(board, piece, sq, hash);
}

static void add_move(MoveList *list, int from, int to, int promotion, int flags) {
    if (list->count >= MAX_MOVES) {
        return;
    }
    Move *move = &list->moves[list->count++];
    move->from = (uint8_t)from;
    move->to = (uint8_t)to;
    move->promotion = (uint8_t)promotion;
    move->flags = (uint8_t)flags;
    move->score = 0;
}

static void add_promotion_moves(MoveList *list, int from, int to, int flags) {
    add_move(list, from, to, QUEEN, flags | MOVE_PROMOTION);
    add_move(list, from, to, ROOK, flags | MOVE_PROMOTION);
    add_move(list, from, to, BISHOP, flags | MOVE_PROMOTION);
    add_move(list, from, to, KNIGHT, flags | MOVE_PROMOTION);
}

static uint64_t build_knight_attacks(int sq) {
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

static uint64_t build_king_attacks(int sq) {
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

static uint64_t build_pawn_attacks(int sq, int side) {
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

static int step_toward(int from, int to, int *df, int *dr) {
    int from_file = file_of(from);
    int from_rank = rank_of(from);
    int to_file = file_of(to);
    int to_rank = rank_of(to);
    int file_delta = to_file - from_file;
    int rank_delta = to_rank - from_rank;

    *df = 0;
    *dr = 0;
    if (from == to) {
        return 0;
    }
    if (file_delta == 0) {
        *dr = rank_delta > 0 ? 1 : -1;
        return 1;
    }
    if (rank_delta == 0) {
        *df = file_delta > 0 ? 1 : -1;
        return 1;
    }
    if (abs(file_delta) == abs(rank_delta)) {
        *df = file_delta > 0 ? 1 : -1;
        *dr = rank_delta > 0 ? 1 : -1;
        return 1;
    }
    return 0;
}

static uint64_t build_between(int from, int to) {
    int df = 0;
    int dr = 0;
    if (!step_toward(from, to, &df, &dr)) {
        return 0;
    }

    uint64_t mask = 0;
    int file = file_of(from) + df;
    int rank = rank_of(from) + dr;
    while (on_board(file, rank)) {
        int sq = rank * 8 + file;
        if (sq == to) {
            break;
        }
        mask |= square_mask(sq);
        file += df;
        rank += dr;
    }
    return mask;
}

void movegen_init_attack_tables(void) {
    if (attack_tables_initialized) {
        return;
    }
    for (int sq = 0; sq < BOARD_SQUARES; ++sq) {
        knight_attack_table[sq] = build_knight_attacks(sq);
        king_attack_table[sq] = build_king_attacks(sq);
        pawn_attack_table[WHITE][sq] = build_pawn_attacks(sq, WHITE);
        pawn_attack_table[BLACK][sq] = build_pawn_attacks(sq, BLACK);
        for (int to = 0; to < BOARD_SQUARES; ++to) {
            between_table[sq][to] = build_between(sq, to);
        }
    }
    attack_tables_initialized = 1;
}

static uint64_t knight_attacks_from(int sq) {
    return knight_attack_table[sq];
}

static uint64_t king_attacks_from(int sq) {
    return king_attack_table[sq];
}

static uint64_t pawn_attacks_from(int sq, int side) {
    return pawn_attack_table[side][sq];
}

static uint64_t ray_attacks_from(int sq, int df, int dr, uint64_t occupied) {
    uint64_t attacks = 0;
    int file = file_of(sq) + df;
    int rank = rank_of(sq) + dr;
    while (on_board(file, rank)) {
        int to = rank * 8 + file;
        uint64_t to_mask = square_mask(to);
        attacks |= to_mask;
        if (occupied & to_mask) {
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

static void add_targets_from_mask(const Board *board, MoveList *list, int from, int piece,
                                  uint64_t targets, int noisy_only) {
    int side = piece_color(piece);
    uint64_t enemy = board->occupancy[opposite_side(side)];
    targets &= ~board->occupancy[side];
    if (noisy_only) {
        targets &= enemy;
    }
    while (targets) {
        int to = pop_lsb(&targets);
        int flags = (enemy & square_mask(to)) ? MOVE_CAPTURE : 0;
        add_move(list, from, to, 0, flags);
    }
}

static uint64_t attackers_to_square(const Board *board, int sq, int by_side, uint64_t occupied) {
    uint64_t attackers = 0;
    attackers |= pawn_attacks_from(sq, opposite_side(by_side)) & board->bitboards[by_side][PAWN];
    attackers |= knight_attacks_from(sq) & board->bitboards[by_side][KNIGHT];
    attackers |= bishop_attacks_from(sq, occupied) &
                 (board->bitboards[by_side][BISHOP] | board->bitboards[by_side][QUEEN]);
    attackers |= rook_attacks_from(sq, occupied) &
                 (board->bitboards[by_side][ROOK] | board->bitboards[by_side][QUEEN]);
    attackers |= king_attacks_from(sq) & board->bitboards[by_side][KING];
    return attackers;
}

static int is_square_attacked_with_occupancy(const Board *board, int sq, int by_side, uint64_t occupied) {
    return attackers_to_square(board, sq, by_side, occupied) != 0;
}

int is_square_attacked(const Board *board, int sq, int by_side) {
    movegen_init_attack_tables();
    return is_square_attacked_with_occupancy(board, sq, by_side, board->occupied);
}

int in_check(const Board *board, int side) {
    uint64_t king_bb = board->bitboards[side][KING];
    if (king_bb) {
        return is_square_attacked(board, bit_scan_forward(king_bb), opposite_side(side));
    }
    return 0;
}

static void generate_pawn_moves(const Board *board, MoveList *list, int sq, int piece, int noisy_only) {
    int side = piece_color(piece);
    int file = file_of(sq);
    int rank = rank_of(sq);
    uint64_t occupied = board->occupied;
    uint64_t enemy = board->occupancy[opposite_side(side)];

    if (side == WHITE) {
        int one = sq + 8;
        if (rank < 7 && !(occupied & square_mask(one))) {
            if (rank == 6) {
                add_promotion_moves(list, sq, one, 0);
            } else if (!noisy_only) {
                add_move(list, sq, one, 0, 0);
                if (rank == 1 && !(occupied & square_mask(sq + 16))) {
                    add_move(list, sq, sq + 16, 0, MOVE_DOUBLE_PAWN);
                }
            }
        }
        if (file > 0 && rank < 7) {
            int to = sq + 7;
            if (enemy & square_mask(to)) {
                if (rank == 6) add_promotion_moves(list, sq, to, MOVE_CAPTURE);
                else add_move(list, sq, to, 0, MOVE_CAPTURE);
            }
            if (to == board->en_passant) {
                add_move(list, sq, to, 0, MOVE_EN_PASSANT | MOVE_CAPTURE);
            }
        }
        if (file < 7 && rank < 7) {
            int to = sq + 9;
            if (enemy & square_mask(to)) {
                if (rank == 6) add_promotion_moves(list, sq, to, MOVE_CAPTURE);
                else add_move(list, sq, to, 0, MOVE_CAPTURE);
            }
            if (to == board->en_passant) {
                add_move(list, sq, to, 0, MOVE_EN_PASSANT | MOVE_CAPTURE);
            }
        }
    } else {
        int one = sq - 8;
        if (rank > 0 && !(occupied & square_mask(one))) {
            if (rank == 1) {
                add_promotion_moves(list, sq, one, 0);
            } else if (!noisy_only) {
                add_move(list, sq, one, 0, 0);
                if (rank == 6 && !(occupied & square_mask(sq - 16))) {
                    add_move(list, sq, sq - 16, 0, MOVE_DOUBLE_PAWN);
                }
            }
        }
        if (file > 0 && rank > 0) {
            int to = sq - 9;
            if (enemy & square_mask(to)) {
                if (rank == 1) add_promotion_moves(list, sq, to, MOVE_CAPTURE);
                else add_move(list, sq, to, 0, MOVE_CAPTURE);
            }
            if (to == board->en_passant) {
                add_move(list, sq, to, 0, MOVE_EN_PASSANT | MOVE_CAPTURE);
            }
        }
        if (file < 7 && rank > 0) {
            int to = sq - 7;
            if (enemy & square_mask(to)) {
                if (rank == 1) add_promotion_moves(list, sq, to, MOVE_CAPTURE);
                else add_move(list, sq, to, 0, MOVE_CAPTURE);
            }
            if (to == board->en_passant) {
                add_move(list, sq, to, 0, MOVE_EN_PASSANT | MOVE_CAPTURE);
            }
        }
    }
}

static void generate_knight_moves(const Board *board, MoveList *list, int sq, int piece, int noisy_only) {
    add_targets_from_mask(board, list, sq, piece, knight_attacks_from(sq), noisy_only);
}

static void generate_slider_moves(const Board *board, MoveList *list, int sq, int piece,
                                  const int dirs[][2], int dir_count, int noisy_only) {
    uint64_t targets = 0;
    for (int i = 0; i < dir_count; ++i) {
        targets |= ray_attacks_from(sq, dirs[i][0], dirs[i][1], board->occupied);
    }
    add_targets_from_mask(board, list, sq, piece, targets, noisy_only);
}

static void generate_king_moves(const Board *board, MoveList *list, int sq, int piece, int noisy_only) {
    int side = piece_color(piece);
    add_targets_from_mask(board, list, sq, piece, king_attacks_from(sq), noisy_only);

    if (noisy_only) {
        return;
    }

    if (side == WHITE && sq == 4 && !in_check(board, WHITE)) {
        if ((board->castling & CASTLE_WHITE_KING) && (board->bitboards[WHITE][ROOK] & square_mask(7)) &&
            !(board->occupied & (square_mask(5) | square_mask(6))) &&
            !is_square_attacked(board, 5, BLACK) && !is_square_attacked(board, 6, BLACK)) {
            add_move(list, 4, 6, 0, MOVE_CASTLE);
        }
        if ((board->castling & CASTLE_WHITE_QUEEN) && (board->bitboards[WHITE][ROOK] & square_mask(0)) &&
            !(board->occupied & (square_mask(3) | square_mask(2) | square_mask(1))) &&
            !is_square_attacked(board, 3, BLACK) && !is_square_attacked(board, 2, BLACK)) {
            add_move(list, 4, 2, 0, MOVE_CASTLE);
        }
    } else if (side == BLACK && sq == 60 && !in_check(board, BLACK)) {
        if ((board->castling & CASTLE_BLACK_KING) && (board->bitboards[BLACK][ROOK] & square_mask(63)) &&
            !(board->occupied & (square_mask(61) | square_mask(62))) &&
            !is_square_attacked(board, 61, WHITE) && !is_square_attacked(board, 62, WHITE)) {
            add_move(list, 60, 62, 0, MOVE_CASTLE);
        }
        if ((board->castling & CASTLE_BLACK_QUEEN) && (board->bitboards[BLACK][ROOK] & square_mask(56)) &&
            !(board->occupied & (square_mask(59) | square_mask(58) | square_mask(57))) &&
            !is_square_attacked(board, 59, WHITE) && !is_square_attacked(board, 58, WHITE)) {
            add_move(list, 60, 58, 0, MOVE_CASTLE);
        }
    }
}

static void generate_pseudo_moves_impl(const Board *board, MoveList *list, int noisy_only) {
    movegen_init_attack_tables();
    list->count = 0;
    static const int bishop_dirs[4][2] = {
        {1, 1}, {1, -1}, {-1, 1}, {-1, -1}
    };
    static const int rook_dirs[4][2] = {
        {1, 0}, {-1, 0}, {0, 1}, {0, -1}
    };
    static const int queen_dirs[8][2] = {
        {1, 1}, {1, -1}, {-1, 1}, {-1, -1},
        {1, 0}, {-1, 0}, {0, 1}, {0, -1}
    };

    int side = board->side_to_move;
    for (int type = PAWN; type <= KING; ++type) {
        uint64_t pieces = board->bitboards[side][type];
        int piece = side == WHITE ? type : -type;
        while (pieces) {
            int sq = pop_lsb(&pieces);
            switch (type) {
            case PAWN:
                generate_pawn_moves(board, list, sq, piece, noisy_only);
                break;
            case KNIGHT:
                generate_knight_moves(board, list, sq, piece, noisy_only);
                break;
            case BISHOP:
                generate_slider_moves(board, list, sq, piece, bishop_dirs, 4, noisy_only);
                break;
            case ROOK:
                generate_slider_moves(board, list, sq, piece, rook_dirs, 4, noisy_only);
                break;
            case QUEEN:
                generate_slider_moves(board, list, sq, piece, queen_dirs, 8, noisy_only);
                break;
            case KING:
                generate_king_moves(board, list, sq, piece, noisy_only);
                break;
            default:
                break;
            }
        }
    }
}

void generate_pseudo_moves(const Board *board, MoveList *list) {
    generate_pseudo_moves_impl(board, list, 0);
}

static void generate_pseudo_noisy_moves(const Board *board, MoveList *list) {
    generate_pseudo_moves_impl(board, list, 1);
}

int make_move(Board *board, Move move) {
    if (board->ply >= MAX_PLY) {
        return 0;
    }

    int piece = board->squares[move.from];
    if (piece == EMPTY || piece_color(piece) != board->side_to_move) {
        return 0;
    }

    Undo *undo = &board->history[board->ply++];
    undo->move = move;
    undo->castling = board->castling;
    undo->en_passant = board->en_passant;
    undo->halfmove_clock = board->halfmove_clock;
    undo->hash = board->hash;
    undo->captured = board->squares[move.to];

    uint64_t hash = board->hash;
    hash ^= board_hash_castling(board->castling);
    hash ^= board_hash_en_passant(board->en_passant);

    int captured_square = move.to;
    if (move.flags & MOVE_EN_PASSANT) {
        captured_square = board->side_to_move == WHITE ? move.to - 8 : move.to + 8;
        undo->captured = board->squares[captured_square];
        clear_piece(board, undo->captured, captured_square, &hash);
    } else if (undo->captured != EMPTY) {
        clear_piece(board, undo->captured, move.to, &hash);
    }

    clear_piece(board, piece, move.from, &hash);
    int placed_piece = piece;
    if (move.flags & MOVE_PROMOTION) {
        placed_piece = board->side_to_move == WHITE ? move.promotion : -move.promotion;
    }
    put_piece(board, placed_piece, move.to, &hash);

    if (move.flags & MOVE_CASTLE) {
        if (move.to == 6) {
            clear_piece(board, WR, 7, &hash);
            put_piece(board, WR, 5, &hash);
        } else if (move.to == 2) {
            clear_piece(board, WR, 0, &hash);
            put_piece(board, WR, 3, &hash);
        } else if (move.to == 62) {
            clear_piece(board, BR, 63, &hash);
            put_piece(board, BR, 61, &hash);
        } else if (move.to == 58) {
            clear_piece(board, BR, 56, &hash);
            put_piece(board, BR, 59, &hash);
        }
    }

    if (piece == WK) {
        board->castling &= (uint8_t)~(CASTLE_WHITE_KING | CASTLE_WHITE_QUEEN);
    } else if (piece == BK) {
        board->castling &= (uint8_t)~(CASTLE_BLACK_KING | CASTLE_BLACK_QUEEN);
    } else if (piece == WR) {
        if (move.from == 0) board->castling &= (uint8_t)~CASTLE_WHITE_QUEEN;
        if (move.from == 7) board->castling &= (uint8_t)~CASTLE_WHITE_KING;
    } else if (piece == BR) {
        if (move.from == 56) board->castling &= (uint8_t)~CASTLE_BLACK_QUEEN;
        if (move.from == 63) board->castling &= (uint8_t)~CASTLE_BLACK_KING;
    }

    if (captured_square == 0) board->castling &= (uint8_t)~CASTLE_WHITE_QUEEN;
    if (captured_square == 7) board->castling &= (uint8_t)~CASTLE_WHITE_KING;
    if (captured_square == 56) board->castling &= (uint8_t)~CASTLE_BLACK_QUEEN;
    if (captured_square == 63) board->castling &= (uint8_t)~CASTLE_BLACK_KING;

    board->en_passant = -1;
    if (move.flags & MOVE_DOUBLE_PAWN) {
        board->en_passant = (int8_t)((move.from + move.to) / 2);
    }

    if (piece_type(piece) == PAWN || undo->captured != EMPTY) {
        board->halfmove_clock = 0;
    } else {
        ++board->halfmove_clock;
    }

    if (board->side_to_move == BLACK) {
        ++board->fullmove_number;
    }
    board->side_to_move = opposite_side(board->side_to_move);
    hash ^= board_hash_side_to_move();
    hash ^= board_hash_castling(board->castling);
    hash ^= board_hash_en_passant(board->en_passant);
    board->hash = hash;
    return 1;
}

void undo_move(Board *board) {
    if (board->ply <= 0) {
        return;
    }

    Undo *undo = &board->history[--board->ply];
    Move move = undo->move;

    board->side_to_move = opposite_side(board->side_to_move);
    if (board->side_to_move == BLACK && board->fullmove_number > 1) {
        --board->fullmove_number;
    }

    int moved_piece = board->squares[move.to];
    if (move.flags & MOVE_PROMOTION) {
        moved_piece = board->side_to_move == WHITE ? WP : BP;
    }

    clear_piece(board, board->squares[move.to], move.to, NULL);
    put_piece(board, moved_piece, move.from, NULL);

    if (move.flags & MOVE_EN_PASSANT) {
        board->squares[move.to] = EMPTY;
        int captured_square = board->side_to_move == WHITE ? move.to - 8 : move.to + 8;
        put_piece(board, undo->captured, captured_square, NULL);
    } else if (undo->captured != EMPTY) {
        put_piece(board, undo->captured, move.to, NULL);
    }

    if (move.flags & MOVE_CASTLE) {
        if (move.to == 6) {
            clear_piece(board, WR, 5, NULL);
            put_piece(board, WR, 7, NULL);
        } else if (move.to == 2) {
            clear_piece(board, WR, 3, NULL);
            put_piece(board, WR, 0, NULL);
        } else if (move.to == 62) {
            clear_piece(board, BR, 61, NULL);
            put_piece(board, BR, 63, NULL);
        } else if (move.to == 58) {
            clear_piece(board, BR, 59, NULL);
            put_piece(board, BR, 56, NULL);
        }
    }

    board->castling = undo->castling;
    board->en_passant = undo->en_passant;
    board->halfmove_clock = undo->halfmove_clock;
    board->hash = undo->hash;
}

static void filter_legal_moves(Board *board, const MoveList *pseudo, MoveList *list) {
    MoveList legal;
    legal.count = 0;

    int moving_side = board->side_to_move;
    for (int i = 0; i < pseudo->count; ++i) {
        if (!make_move(board, pseudo->moves[i])) {
            continue;
        }
        if (!in_check(board, moving_side)) {
            legal.moves[legal.count++] = pseudo->moves[i];
        }
        undo_move(board);
    }
    *list = legal;
}

void generate_legal_moves_filtered(Board *board, MoveList *list) {
    MoveList pseudo;
    generate_pseudo_moves(board, &pseudo);
    filter_legal_moves(board, &pseudo, list);
}

void generate_legal_noisy_moves_filtered(Board *board, MoveList *list) {
    MoveList pseudo;
    generate_pseudo_noisy_moves(board, &pseudo);
    filter_legal_moves(board, &pseudo, list);
}

typedef struct {
    int side;
    int enemy;
    int king_sq;
    int check_count;
    uint64_t own;
    uint64_t enemy_occ;
    uint64_t occupied;
    uint64_t occupied_without_king;
    uint64_t checkers;
    uint64_t evasion_mask;
    uint64_t pin_masks[BOARD_SQUARES];
} LegalContext;

static int slider_matches_direction(int piece_type_value, int df, int dr) {
    int diagonal = df != 0 && dr != 0;
    if (diagonal) {
        return piece_type_value == BISHOP || piece_type_value == QUEEN;
    }
    return piece_type_value == ROOK || piece_type_value == QUEEN;
}

static void compute_pin_masks(const Board *board, LegalContext *ctx) {
    static const int dirs[8][2] = {
        {1, 0}, {-1, 0}, {0, 1}, {0, -1},
        {1, 1}, {1, -1}, {-1, 1}, {-1, -1}
    };

    for (int i = 0; i < BOARD_SQUARES; ++i) {
        ctx->pin_masks[i] = 0;
    }

    for (int dir = 0; dir < 8; ++dir) {
        int df = dirs[dir][0];
        int dr = dirs[dir][1];
        int file = file_of(ctx->king_sq) + df;
        int rank = rank_of(ctx->king_sq) + dr;
        int blocker_sq = -1;

        while (on_board(file, rank)) {
            int sq = rank * 8 + file;
            int piece = board->squares[sq];
            if (piece == EMPTY) {
                file += df;
                rank += dr;
                continue;
            }

            if (piece_color(piece) == ctx->side) {
                if (blocker_sq >= 0) {
                    break;
                }
                blocker_sq = sq;
                file += df;
                rank += dr;
                continue;
            }

            if (blocker_sq >= 0 && slider_matches_direction(piece_type(piece), df, dr)) {
                ctx->pin_masks[blocker_sq] = between_table[ctx->king_sq][sq] | square_mask(sq);
            }
            break;
        }
    }
}

static int init_legal_context(const Board *board, LegalContext *ctx) {
    movegen_init_attack_tables();
    memset(ctx, 0, sizeof(*ctx));
    ctx->side = board->side_to_move;
    ctx->enemy = opposite_side(ctx->side);
    uint64_t king = board->bitboards[ctx->side][KING];
    if (!king) {
        return 0;
    }

    ctx->king_sq = bit_scan_forward(king);
    ctx->own = board->occupancy[ctx->side];
    ctx->enemy_occ = board->occupancy[ctx->enemy];
    ctx->occupied = board->occupied;
    ctx->occupied_without_king = board->occupied & ~square_mask(ctx->king_sq);
    ctx->checkers = attackers_to_square(board, ctx->king_sq, ctx->enemy, ctx->occupied);
    ctx->check_count = popcount64(ctx->checkers);
    ctx->evasion_mask = UINT64_MAX;
    if (ctx->check_count == 1) {
        int checker_sq = bit_scan_forward(ctx->checkers);
        ctx->evasion_mask = between_table[ctx->king_sq][checker_sq] | square_mask(checker_sq);
    } else if (ctx->check_count > 1) {
        ctx->evasion_mask = 0;
    }
    compute_pin_masks(board, ctx);
    return 1;
}

static uint64_t constrained_targets(const LegalContext *ctx, int from, uint64_t targets, int noisy_only) {
    targets &= ~ctx->own;
    if (noisy_only) {
        targets &= ctx->enemy_occ;
    }
    if (ctx->pin_masks[from]) {
        targets &= ctx->pin_masks[from];
    }
    if (ctx->check_count > 0) {
        targets &= ctx->evasion_mask;
    }
    return targets;
}

static void add_direct_targets(const Board *board, const LegalContext *ctx, MoveList *list,
                               int from, int piece, uint64_t targets, int noisy_only) {
    targets = constrained_targets(ctx, from, targets, noisy_only);
    while (targets) {
        int to = pop_lsb(&targets);
        int flags = (ctx->enemy_occ & square_mask(to)) ? MOVE_CAPTURE : 0;
        add_move(list, from, to, 0, flags);
    }
    (void)board;
    (void)piece;
}

static int target_allowed_for_piece(const LegalContext *ctx, int from, int to) {
    uint64_t target = square_mask(to);
    if (ctx->pin_masks[from] && !(ctx->pin_masks[from] & target)) {
        return 0;
    }
    if (ctx->check_count > 0 && !(ctx->evasion_mask & target)) {
        return 0;
    }
    return 1;
}

static int en_passant_is_legal(const Board *board, int from, int to, int side) {
    int moving_piece = side == WHITE ? WP : BP;
    int captured_piece = side == WHITE ? BP : WP;
    int captured_sq = side == WHITE ? to - 8 : to + 8;
    if (captured_sq < 0 || captured_sq >= BOARD_SQUARES ||
        board->squares[from] != moving_piece || board->squares[captured_sq] != captured_piece) {
        return 0;
    }

    Board temp = *board;
    clear_piece(&temp, moving_piece, from, NULL);
    clear_piece(&temp, captured_piece, captured_sq, NULL);
    put_piece(&temp, moving_piece, to, NULL);
    return !in_check(&temp, side);
}

static void add_direct_pawn_push(const LegalContext *ctx, MoveList *list, int from, int to,
                                 int promotion_rank, int noisy_only) {
    if (!target_allowed_for_piece(ctx, from, to)) {
        return;
    }
    if (rank_of(from) == promotion_rank) {
        add_promotion_moves(list, from, to, 0);
    } else if (!noisy_only) {
        add_move(list, from, to, 0, 0);
    }
}

static void add_direct_pawn_capture(const LegalContext *ctx, MoveList *list, int from, int to,
                                    int promotion_rank) {
    if (!(ctx->enemy_occ & square_mask(to)) || !target_allowed_for_piece(ctx, from, to)) {
        return;
    }
    if (rank_of(from) == promotion_rank) {
        add_promotion_moves(list, from, to, MOVE_CAPTURE);
    } else {
        add_move(list, from, to, 0, MOVE_CAPTURE);
    }
}

static void generate_direct_pawn_moves(const Board *board, const LegalContext *ctx, MoveList *list,
                                       int from, int noisy_only) {
    int file = file_of(from);
    int rank = rank_of(from);

    if (ctx->side == WHITE) {
        int one = from + 8;
        if (rank < 7 && !(ctx->occupied & square_mask(one))) {
            add_direct_pawn_push(ctx, list, from, one, 6, noisy_only);
            if (!noisy_only && rank == 1 && !(ctx->occupied & square_mask(from + 16)) &&
                target_allowed_for_piece(ctx, from, from + 16)) {
                add_move(list, from, from + 16, 0, MOVE_DOUBLE_PAWN);
            }
        }
        if (file > 0 && rank < 7) {
            add_direct_pawn_capture(ctx, list, from, from + 7, 6);
            if (from + 7 == board->en_passant &&
                en_passant_is_legal(board, from, from + 7, ctx->side)) {
                add_move(list, from, from + 7, 0, MOVE_EN_PASSANT | MOVE_CAPTURE);
            }
        }
        if (file < 7 && rank < 7) {
            add_direct_pawn_capture(ctx, list, from, from + 9, 6);
            if (from + 9 == board->en_passant &&
                en_passant_is_legal(board, from, from + 9, ctx->side)) {
                add_move(list, from, from + 9, 0, MOVE_EN_PASSANT | MOVE_CAPTURE);
            }
        }
    } else {
        int one = from - 8;
        if (rank > 0 && !(ctx->occupied & square_mask(one))) {
            add_direct_pawn_push(ctx, list, from, one, 1, noisy_only);
            if (!noisy_only && rank == 6 && !(ctx->occupied & square_mask(from - 16)) &&
                target_allowed_for_piece(ctx, from, from - 16)) {
                add_move(list, from, from - 16, 0, MOVE_DOUBLE_PAWN);
            }
        }
        if (file > 0 && rank > 0) {
            add_direct_pawn_capture(ctx, list, from, from - 9, 1);
            if (from - 9 == board->en_passant &&
                en_passant_is_legal(board, from, from - 9, ctx->side)) {
                add_move(list, from, from - 9, 0, MOVE_EN_PASSANT | MOVE_CAPTURE);
            }
        }
        if (file < 7 && rank > 0) {
            add_direct_pawn_capture(ctx, list, from, from - 7, 1);
            if (from - 7 == board->en_passant &&
                en_passant_is_legal(board, from, from - 7, ctx->side)) {
                add_move(list, from, from - 7, 0, MOVE_EN_PASSANT | MOVE_CAPTURE);
            }
        }
    }
}

static void generate_direct_king_moves(const Board *board, const LegalContext *ctx, MoveList *list,
                                       int noisy_only) {
    uint64_t targets = king_attacks_from(ctx->king_sq) & ~ctx->own;
    if (noisy_only) {
        targets &= ctx->enemy_occ;
    }
    while (targets) {
        int to = pop_lsb(&targets);
        if (is_square_attacked_with_occupancy(board, to, ctx->enemy, ctx->occupied_without_king)) {
            continue;
        }
        int flags = (ctx->enemy_occ & square_mask(to)) ? MOVE_CAPTURE : 0;
        add_move(list, ctx->king_sq, to, 0, flags);
    }

    if (noisy_only || ctx->check_count > 0) {
        return;
    }

    if (ctx->side == WHITE && ctx->king_sq == 4) {
        if ((board->castling & CASTLE_WHITE_KING) && (board->bitboards[WHITE][ROOK] & square_mask(7)) &&
            !(ctx->occupied & (square_mask(5) | square_mask(6))) &&
            !is_square_attacked_with_occupancy(board, 5, BLACK, ctx->occupied_without_king) &&
            !is_square_attacked_with_occupancy(board, 6, BLACK, ctx->occupied_without_king)) {
            add_move(list, 4, 6, 0, MOVE_CASTLE);
        }
        if ((board->castling & CASTLE_WHITE_QUEEN) && (board->bitboards[WHITE][ROOK] & square_mask(0)) &&
            !(ctx->occupied & (square_mask(3) | square_mask(2) | square_mask(1))) &&
            !is_square_attacked_with_occupancy(board, 3, BLACK, ctx->occupied_without_king) &&
            !is_square_attacked_with_occupancy(board, 2, BLACK, ctx->occupied_without_king)) {
            add_move(list, 4, 2, 0, MOVE_CASTLE);
        }
    } else if (ctx->side == BLACK && ctx->king_sq == 60) {
        if ((board->castling & CASTLE_BLACK_KING) && (board->bitboards[BLACK][ROOK] & square_mask(63)) &&
            !(ctx->occupied & (square_mask(61) | square_mask(62))) &&
            !is_square_attacked_with_occupancy(board, 61, WHITE, ctx->occupied_without_king) &&
            !is_square_attacked_with_occupancy(board, 62, WHITE, ctx->occupied_without_king)) {
            add_move(list, 60, 62, 0, MOVE_CASTLE);
        }
        if ((board->castling & CASTLE_BLACK_QUEEN) && (board->bitboards[BLACK][ROOK] & square_mask(56)) &&
            !(ctx->occupied & (square_mask(59) | square_mask(58) | square_mask(57))) &&
            !is_square_attacked_with_occupancy(board, 59, WHITE, ctx->occupied_without_king) &&
            !is_square_attacked_with_occupancy(board, 58, WHITE, ctx->occupied_without_king)) {
            add_move(list, 60, 58, 0, MOVE_CASTLE);
        }
    }
}

static void generate_legal_moves_direct_impl(Board *board, MoveList *list, int noisy_only) {
    LegalContext ctx;
    list->count = 0;
    if (!init_legal_context(board, &ctx)) {
        return;
    }

    generate_direct_king_moves(board, &ctx, list, noisy_only);
    if (ctx.check_count > 1) {
        return;
    }

    int side = ctx.side;
    uint64_t pieces = board->bitboards[side][PAWN];
    while (pieces) {
        int from = pop_lsb(&pieces);
        generate_direct_pawn_moves(board, &ctx, list, from, noisy_only);
    }

    pieces = board->bitboards[side][KNIGHT];
    while (pieces) {
        int from = pop_lsb(&pieces);
        int piece = side == WHITE ? WN : BN;
        add_direct_targets(board, &ctx, list, from, piece, knight_attacks_from(from), noisy_only);
    }

    pieces = board->bitboards[side][BISHOP];
    while (pieces) {
        int from = pop_lsb(&pieces);
        int piece = side == WHITE ? WB : BB;
        add_direct_targets(board, &ctx, list, from, piece, bishop_attacks_from(from, ctx.occupied), noisy_only);
    }

    pieces = board->bitboards[side][ROOK];
    while (pieces) {
        int from = pop_lsb(&pieces);
        int piece = side == WHITE ? WR : BR;
        add_direct_targets(board, &ctx, list, from, piece, rook_attacks_from(from, ctx.occupied), noisy_only);
    }

    pieces = board->bitboards[side][QUEEN];
    while (pieces) {
        int from = pop_lsb(&pieces);
        int piece = side == WHITE ? WQ : BQ;
        add_direct_targets(board, &ctx, list, from, piece, queen_attacks_from(from, ctx.occupied), noisy_only);
    }
}

void generate_legal_moves(Board *board, MoveList *list) {
    generate_legal_moves_direct_impl(board, list, 0);
}

void generate_legal_noisy_moves(Board *board, MoveList *list) {
    generate_legal_moves_direct_impl(board, list, 1);
}

static int same_move_text(Move move, const char *text) {
    char buf[6];
    move_to_uci(move, buf);
    return strcmp(buf, text) == 0;
}

int parse_uci_move(Board *board, const char *text, Move *move) {
    if (!text || strlen(text) < 4) {
        return 0;
    }

    char lowered[8] = {0};
    size_t n = strlen(text);
    if (n >= sizeof(lowered)) {
        return 0;
    }
    for (size_t i = 0; i < n; ++i) {
        lowered[i] = (char)tolower((unsigned char)text[i]);
    }

    MoveList list;
    generate_legal_moves(board, &list);
    for (int i = 0; i < list.count; ++i) {
        if (same_move_text(list.moves[i], lowered)) {
            *move = list.moves[i];
            return 1;
        }
    }
    return 0;
}

void move_to_uci(Move move, char out[6]) {
    char from[3];
    char to[3];
    square_to_string(move.from, from);
    square_to_string(move.to, to);
    out[0] = from[0];
    out[1] = from[1];
    out[2] = to[0];
    out[3] = to[1];
    out[4] = '\0';
    if (move.flags & MOVE_PROMOTION) {
        char promo = 'q';
        if (move.promotion == ROOK) promo = 'r';
        else if (move.promotion == BISHOP) promo = 'b';
        else if (move.promotion == KNIGHT) promo = 'n';
        out[4] = promo;
        out[5] = '\0';
    }
}

static int see_piece_value(int piece) {
    static const int values[7] = {0, 100, 320, 330, 500, 900, 20000};
    return values[piece_type(piece)];
}

static int piece_attacks_square(const Board *board, int from, int target, int piece) {
    uint64_t target_mask = square_mask(target);

    switch (piece_type(piece)) {
        case PAWN:
            return (pawn_attacks_from(from, piece_color(piece)) & target_mask) != 0;
        case KNIGHT:
            return (knight_attacks_from(from) & target_mask) != 0;
        case BISHOP:
            return (bishop_attacks_from(from, board->occupied) & target_mask) != 0;
        case ROOK:
            return (rook_attacks_from(from, board->occupied) & target_mask) != 0;
        case QUEEN:
            return (queen_attacks_from(from, board->occupied) & target_mask) != 0;
        case KING:
            return (king_attacks_from(from) & target_mask) != 0;
        default:
            return 0;
    }
}

static int lowest_attacker(const Board *board, int target, int side) {
    for (int type = PAWN; type <= KING; ++type) {
        uint64_t pieces = board->bitboards[side][type];
        int piece = side == WHITE ? type : -type;
        while (pieces) {
            int sq = pop_lsb(&pieces);
            if (piece_attacks_square(board, sq, target, piece)) {
                return sq;
            }
        }
    }

    return -1;
}

int see_move(const Board *board, Move move) {
    if (!(move.flags & MOVE_CAPTURE)) {
        return 0;
    }
    movegen_init_attack_tables();

    Board temp = *board;
    int side = piece_color(temp.squares[move.from]);
    int target = move.to;
    int captured_square = target;

    if (move.flags & MOVE_EN_PASSANT) {
        captured_square = side == WHITE ? target - 8 : target + 8;
    }

    int captured_piece = temp.squares[captured_square];
    int attacker = temp.squares[move.from];
    int gain[32];
    int depth = 0;

    gain[depth] = see_piece_value(captured_piece);

    clear_piece(&temp, captured_piece, captured_square, NULL);
    clear_piece(&temp, attacker, move.from, NULL);
    int placed_piece = attacker;
    if (move.flags & MOVE_PROMOTION) {
        placed_piece = side == WHITE ? move.promotion : -move.promotion;
    }
    put_piece(&temp, placed_piece, target, NULL);

    side = opposite_side(side);
    while (depth + 1 < 32) {
        int from = lowest_attacker(&temp, target, side);
        if (from < 0) {
            break;
        }

        ++depth;
        int moving_piece = temp.squares[from];
        gain[depth] = see_piece_value(temp.squares[target]) - gain[depth - 1];

        clear_piece(&temp, temp.squares[target], target, NULL);
        clear_piece(&temp, moving_piece, from, NULL);
        put_piece(&temp, moving_piece, target, NULL);
        side = opposite_side(side);
    }

    while (depth > 0) {
        --depth;
        int next = -gain[depth + 1];
        if (next < gain[depth]) {
            gain[depth] = next;
        }
    }

    return gain[0];
}
