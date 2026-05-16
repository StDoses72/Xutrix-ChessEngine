#ifndef XUTRIX_NNUE_H
#define XUTRIX_NNUE_H

#include "xutrix.h"

#define NNUE_FEATURE_COUNT (12 * 64)

int nnue_load(const char *path);
void nnue_unload(void);
int nnue_is_loaded(void);
int nnue_evaluate_board(const Board *board);
int nnue_try_load_from_env(void);

#endif
