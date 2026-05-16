#include "xutrix.h"

#include <ctype.h>
#include <stdlib.h>
#include <string.h>

static int file_of(int sq) {
    return sq & 7;
}

static int rank_of(int sq) {
    return sq >> 3;
}

static int on_board(int file, int rank) {
    return file >= 0 && file < 8 && rank >= 0 && rank < 8;
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

int is_square_attacked(const Board *board, int sq, int by_side) {
    int file = file_of(sq);
    int rank = rank_of(sq);

    if (by_side == WHITE) {
        if (file > 0 && rank > 0 && board->squares[sq - 9] == WP) return 1;
        if (file < 7 && rank > 0 && board->squares[sq - 7] == WP) return 1;
    } else {
        if (file > 0 && rank < 7 && board->squares[sq + 7] == BP) return 1;
        if (file < 7 && rank < 7 && board->squares[sq + 9] == BP) return 1;
    }

    static const int knight_offsets[8][2] = {
        {1, 2}, {2, 1}, {-1, 2}, {-2, 1},
        {1, -2}, {2, -1}, {-1, -2}, {-2, -1}
    };
    int knight = by_side == WHITE ? WN : BN;
    for (int i = 0; i < 8; ++i) {
        int f = file + knight_offsets[i][0];
        int r = rank + knight_offsets[i][1];
        if (on_board(f, r) && board->squares[r * 8 + f] == knight) {
            return 1;
        }
    }

    static const int bishop_dirs[4][2] = {
        {1, 1}, {1, -1}, {-1, 1}, {-1, -1}
    };
    int bishop = by_side == WHITE ? WB : BB;
    int queen = by_side == WHITE ? WQ : BQ;
    for (int i = 0; i < 4; ++i) {
        int f = file + bishop_dirs[i][0];
        int r = rank + bishop_dirs[i][1];
        while (on_board(f, r)) {
            int piece = board->squares[r * 8 + f];
            if (piece != EMPTY) {
                if (piece == bishop || piece == queen) {
                    return 1;
                }
                break;
            }
            f += bishop_dirs[i][0];
            r += bishop_dirs[i][1];
        }
    }

    static const int rook_dirs[4][2] = {
        {1, 0}, {-1, 0}, {0, 1}, {0, -1}
    };
    int rook = by_side == WHITE ? WR : BR;
    for (int i = 0; i < 4; ++i) {
        int f = file + rook_dirs[i][0];
        int r = rank + rook_dirs[i][1];
        while (on_board(f, r)) {
            int piece = board->squares[r * 8 + f];
            if (piece != EMPTY) {
                if (piece == rook || piece == queen) {
                    return 1;
                }
                break;
            }
            f += rook_dirs[i][0];
            r += rook_dirs[i][1];
        }
    }

    int king = by_side == WHITE ? WK : BK;
    for (int df = -1; df <= 1; ++df) {
        for (int dr = -1; dr <= 1; ++dr) {
            if (df == 0 && dr == 0) {
                continue;
            }
            int f = file + df;
            int r = rank + dr;
            if (on_board(f, r) && board->squares[r * 8 + f] == king) {
                return 1;
            }
        }
    }

    return 0;
}

int in_check(const Board *board, int side) {
    int king = side == WHITE ? WK : BK;
    for (int sq = 0; sq < 64; ++sq) {
        if (board->squares[sq] == king) {
            return is_square_attacked(board, sq, opposite_side(side));
        }
    }
    return 0;
}

static void generate_pawn_moves(const Board *board, MoveList *list, int sq, int piece) {
    int side = piece_color(piece);
    int file = file_of(sq);
    int rank = rank_of(sq);

    if (side == WHITE) {
        int one = sq + 8;
        if (rank < 7 && board->squares[one] == EMPTY) {
            if (rank == 6) {
                add_promotion_moves(list, sq, one, 0);
            } else {
                add_move(list, sq, one, 0, 0);
                if (rank == 1 && board->squares[sq + 16] == EMPTY) {
                    add_move(list, sq, sq + 16, 0, MOVE_DOUBLE_PAWN);
                }
            }
        }
        if (file > 0 && rank < 7) {
            int to = sq + 7;
            if (piece_color(board->squares[to]) == BLACK) {
                if (rank == 6) add_promotion_moves(list, sq, to, MOVE_CAPTURE);
                else add_move(list, sq, to, 0, MOVE_CAPTURE);
            }
            if (to == board->en_passant) {
                add_move(list, sq, to, 0, MOVE_EN_PASSANT | MOVE_CAPTURE);
            }
        }
        if (file < 7 && rank < 7) {
            int to = sq + 9;
            if (piece_color(board->squares[to]) == BLACK) {
                if (rank == 6) add_promotion_moves(list, sq, to, MOVE_CAPTURE);
                else add_move(list, sq, to, 0, MOVE_CAPTURE);
            }
            if (to == board->en_passant) {
                add_move(list, sq, to, 0, MOVE_EN_PASSANT | MOVE_CAPTURE);
            }
        }
    } else {
        int one = sq - 8;
        if (rank > 0 && board->squares[one] == EMPTY) {
            if (rank == 1) {
                add_promotion_moves(list, sq, one, 0);
            } else {
                add_move(list, sq, one, 0, 0);
                if (rank == 6 && board->squares[sq - 16] == EMPTY) {
                    add_move(list, sq, sq - 16, 0, MOVE_DOUBLE_PAWN);
                }
            }
        }
        if (file > 0 && rank > 0) {
            int to = sq - 9;
            if (piece_color(board->squares[to]) == WHITE) {
                if (rank == 1) add_promotion_moves(list, sq, to, MOVE_CAPTURE);
                else add_move(list, sq, to, 0, MOVE_CAPTURE);
            }
            if (to == board->en_passant) {
                add_move(list, sq, to, 0, MOVE_EN_PASSANT | MOVE_CAPTURE);
            }
        }
        if (file < 7 && rank > 0) {
            int to = sq - 7;
            if (piece_color(board->squares[to]) == WHITE) {
                if (rank == 1) add_promotion_moves(list, sq, to, MOVE_CAPTURE);
                else add_move(list, sq, to, 0, MOVE_CAPTURE);
            }
            if (to == board->en_passant) {
                add_move(list, sq, to, 0, MOVE_EN_PASSANT | MOVE_CAPTURE);
            }
        }
    }
}

static void generate_knight_moves(const Board *board, MoveList *list, int sq, int piece) {
    static const int offsets[8][2] = {
        {1, 2}, {2, 1}, {-1, 2}, {-2, 1},
        {1, -2}, {2, -1}, {-1, -2}, {-2, -1}
    };
    int side = piece_color(piece);
    int file = file_of(sq);
    int rank = rank_of(sq);
    for (int i = 0; i < 8; ++i) {
        int f = file + offsets[i][0];
        int r = rank + offsets[i][1];
        if (!on_board(f, r)) {
            continue;
        }
        int to = r * 8 + f;
        int target_side = piece_color(board->squares[to]);
        if (target_side != side) {
            add_move(list, sq, to, 0, target_side == -1 ? 0 : MOVE_CAPTURE);
        }
    }
}

static void generate_slider_moves(const Board *board, MoveList *list, int sq, int piece,
                                  const int dirs[][2], int dir_count) {
    int side = piece_color(piece);
    int file = file_of(sq);
    int rank = rank_of(sq);
    for (int i = 0; i < dir_count; ++i) {
        int f = file + dirs[i][0];
        int r = rank + dirs[i][1];
        while (on_board(f, r)) {
            int to = r * 8 + f;
            int target_side = piece_color(board->squares[to]);
            if (target_side == side) {
                break;
            }
            add_move(list, sq, to, 0, target_side == -1 ? 0 : MOVE_CAPTURE);
            if (target_side != -1) {
                break;
            }
            f += dirs[i][0];
            r += dirs[i][1];
        }
    }
}

static void generate_king_moves(const Board *board, MoveList *list, int sq, int piece) {
    int side = piece_color(piece);
    int file = file_of(sq);
    int rank = rank_of(sq);
    for (int df = -1; df <= 1; ++df) {
        for (int dr = -1; dr <= 1; ++dr) {
            if (df == 0 && dr == 0) {
                continue;
            }
            int f = file + df;
            int r = rank + dr;
            if (!on_board(f, r)) {
                continue;
            }
            int to = r * 8 + f;
            int target_side = piece_color(board->squares[to]);
            if (target_side != side) {
                add_move(list, sq, to, 0, target_side == -1 ? 0 : MOVE_CAPTURE);
            }
        }
    }

    if (side == WHITE && sq == 4 && !in_check(board, WHITE)) {
        if ((board->castling & CASTLE_WHITE_KING) && board->squares[7] == WR &&
            board->squares[5] == EMPTY && board->squares[6] == EMPTY &&
            !is_square_attacked(board, 5, BLACK) && !is_square_attacked(board, 6, BLACK)) {
            add_move(list, 4, 6, 0, MOVE_CASTLE);
        }
        if ((board->castling & CASTLE_WHITE_QUEEN) && board->squares[0] == WR &&
            board->squares[3] == EMPTY && board->squares[2] == EMPTY && board->squares[1] == EMPTY &&
            !is_square_attacked(board, 3, BLACK) && !is_square_attacked(board, 2, BLACK)) {
            add_move(list, 4, 2, 0, MOVE_CASTLE);
        }
    } else if (side == BLACK && sq == 60 && !in_check(board, BLACK)) {
        if ((board->castling & CASTLE_BLACK_KING) && board->squares[63] == BR &&
            board->squares[61] == EMPTY && board->squares[62] == EMPTY &&
            !is_square_attacked(board, 61, WHITE) && !is_square_attacked(board, 62, WHITE)) {
            add_move(list, 60, 62, 0, MOVE_CASTLE);
        }
        if ((board->castling & CASTLE_BLACK_QUEEN) && board->squares[56] == BR &&
            board->squares[59] == EMPTY && board->squares[58] == EMPTY && board->squares[57] == EMPTY &&
            !is_square_attacked(board, 59, WHITE) && !is_square_attacked(board, 58, WHITE)) {
            add_move(list, 60, 58, 0, MOVE_CASTLE);
        }
    }
}

void generate_pseudo_moves(const Board *board, MoveList *list) {
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

    for (int sq = 0; sq < 64; ++sq) {
        int piece = board->squares[sq];
        if (piece == EMPTY || piece_color(piece) != board->side_to_move) {
            continue;
        }

        switch (piece_type(piece)) {
            case PAWN:
                generate_pawn_moves(board, list, sq, piece);
                break;
            case KNIGHT:
                generate_knight_moves(board, list, sq, piece);
                break;
            case BISHOP:
                generate_slider_moves(board, list, sq, piece, bishop_dirs, 4);
                break;
            case ROOK:
                generate_slider_moves(board, list, sq, piece, rook_dirs, 4);
                break;
            case QUEEN:
                generate_slider_moves(board, list, sq, piece, queen_dirs, 8);
                break;
            case KING:
                generate_king_moves(board, list, sq, piece);
                break;
            default:
                break;
        }
    }
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

    int captured_square = move.to;
    if (move.flags & MOVE_EN_PASSANT) {
        captured_square = board->side_to_move == WHITE ? move.to - 8 : move.to + 8;
        undo->captured = board->squares[captured_square];
        board->squares[captured_square] = EMPTY;
    }

    board->squares[move.to] = board->squares[move.from];
    board->squares[move.from] = EMPTY;

    if (move.flags & MOVE_PROMOTION) {
        board->squares[move.to] = (int8_t)(board->side_to_move == WHITE ? move.promotion : -move.promotion);
    }

    if (move.flags & MOVE_CASTLE) {
        if (move.to == 6) {
            board->squares[5] = WR;
            board->squares[7] = EMPTY;
        } else if (move.to == 2) {
            board->squares[3] = WR;
            board->squares[0] = EMPTY;
        } else if (move.to == 62) {
            board->squares[61] = BR;
            board->squares[63] = EMPTY;
        } else if (move.to == 58) {
            board->squares[59] = BR;
            board->squares[56] = EMPTY;
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
    board->hash = board_compute_hash(board);
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

    board->squares[move.from] = (int8_t)moved_piece;
    board->squares[move.to] = undo->captured;

    if (move.flags & MOVE_EN_PASSANT) {
        board->squares[move.to] = EMPTY;
        int captured_square = board->side_to_move == WHITE ? move.to - 8 : move.to + 8;
        board->squares[captured_square] = undo->captured;
    }

    if (move.flags & MOVE_CASTLE) {
        if (move.to == 6) {
            board->squares[7] = WR;
            board->squares[5] = EMPTY;
        } else if (move.to == 2) {
            board->squares[0] = WR;
            board->squares[3] = EMPTY;
        } else if (move.to == 62) {
            board->squares[63] = BR;
            board->squares[61] = EMPTY;
        } else if (move.to == 58) {
            board->squares[56] = BR;
            board->squares[59] = EMPTY;
        }
    }

    board->castling = undo->castling;
    board->en_passant = undo->en_passant;
    board->halfmove_clock = undo->halfmove_clock;
    board->hash = undo->hash;
}

void generate_legal_moves(Board *board, MoveList *list) {
    MoveList pseudo;
    MoveList legal;
    generate_pseudo_moves(board, &pseudo);
    legal.count = 0;

    int moving_side = board->side_to_move;
    for (int i = 0; i < pseudo.count; ++i) {
        if (!make_move(board, pseudo.moves[i])) {
            continue;
        }
        if (!in_check(board, moving_side)) {
            legal.moves[legal.count++] = pseudo.moves[i];
        }
        undo_move(board);
    }
    *list = legal;
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
