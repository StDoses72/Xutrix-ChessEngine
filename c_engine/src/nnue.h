#ifndef XUTRIX_NNUE_H
#define XUTRIX_NNUE_H

#include "xutrix.h"

#define NNUE_FEATURE_COUNT (12 * 64)

int nnue_load(const char *path);
void nnue_unload(void);
int nnue_is_loaded(void);
uint32_t nnue_generation(void);
void nnue_refresh_accumulator(Board *board);
void nnue_accumulator_add_piece(Board *board, int piece, int square);
void nnue_accumulator_remove_piece(Board *board, int piece, int square);
int nnue_evaluate_board(Board *board);
int nnue_try_load_from_env(void);

#endif
