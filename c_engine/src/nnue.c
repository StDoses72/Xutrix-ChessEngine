#include "nnue.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NNUE_MAGIC "XNNUE001"
#define NNUE_MAX_HIDDEN 512
#define NNUE_CLIP 127

typedef struct {
    int hidden;
    int scale;
    int16_t *feature_weights;
    int16_t *hidden_bias;
    int16_t *output_weights;
    int32_t output_bias;
    int loaded;
} NNUE;

typedef struct {
    char magic[8];
    int32_t feature_count;
    int32_t hidden;
    int32_t scale;
} NNUEFileHeader;

static NNUE net = {0};

static int feature_index_for_piece(int piece, int square) {
    int offset;
    switch (piece) {
        case WP: offset = 0; break;
        case WN: offset = 1; break;
        case WB: offset = 2; break;
        case WR: offset = 3; break;
        case WQ: offset = 4; break;
        case WK: offset = 5; break;
        case BP: offset = 6; break;
        case BN: offset = 7; break;
        case BB: offset = 8; break;
        case BR: offset = 9; break;
        case BQ: offset = 10; break;
        case BK: offset = 11; break;
        default: return -1;
    }
    return offset * 64 + square;
}

static int clipped_relu(int value) {
    if (value < 0) {
        return 0;
    }
    if (value > NNUE_CLIP) {
        return NNUE_CLIP;
    }
    return value;
}

void nnue_unload(void) {
    free(net.feature_weights);
    free(net.hidden_bias);
    free(net.output_weights);
    memset(&net, 0, sizeof(net));
}

int nnue_is_loaded(void) {
    return net.loaded;
}

int nnue_load(const char *path) {
    FILE *file = fopen(path, "rb");
    if (!file) {
        return 0;
    }

    NNUEFileHeader header;
    if (fread(&header, sizeof(header), 1, file) != 1) {
        fclose(file);
        return 0;
    }
    if (memcmp(header.magic, NNUE_MAGIC, sizeof(header.magic)) != 0 ||
        header.feature_count != NNUE_FEATURE_COUNT ||
        header.hidden <= 0 ||
        header.hidden > NNUE_MAX_HIDDEN ||
        header.scale <= 0) {
        fclose(file);
        return 0;
    }

    int hidden = header.hidden;
    size_t feature_weight_count = (size_t)NNUE_FEATURE_COUNT * (size_t)hidden;

    int16_t *feature_weights = (int16_t *)malloc(feature_weight_count * sizeof(int16_t));
    int16_t *hidden_bias = (int16_t *)malloc((size_t)hidden * sizeof(int16_t));
    int16_t *output_weights = (int16_t *)malloc((size_t)hidden * sizeof(int16_t));
    if (!feature_weights || !hidden_bias || !output_weights) {
        free(feature_weights);
        free(hidden_bias);
        free(output_weights);
        fclose(file);
        return 0;
    }

    int32_t output_bias = 0;
    int ok =
        fread(hidden_bias, sizeof(int16_t), (size_t)hidden, file) == (size_t)hidden &&
        fread(feature_weights, sizeof(int16_t), feature_weight_count, file) == feature_weight_count &&
        fread(output_weights, sizeof(int16_t), (size_t)hidden, file) == (size_t)hidden &&
        fread(&output_bias, sizeof(int32_t), 1, file) == 1;
    fclose(file);

    if (!ok) {
        free(feature_weights);
        free(hidden_bias);
        free(output_weights);
        return 0;
    }

    nnue_unload();
    net.hidden = hidden;
    net.scale = header.scale;
    net.feature_weights = feature_weights;
    net.hidden_bias = hidden_bias;
    net.output_weights = output_weights;
    net.output_bias = output_bias;
    net.loaded = 1;
    return 1;
}

int nnue_try_load_from_env(void) {
    const char *path = getenv("XUTRIX_NNUE");
    if (!path || !*path) {
        return 0;
    }
    return nnue_load(path);
}

int nnue_evaluate_board(const Board *board) {
    if (!net.loaded) {
        return evaluate_classic_board(board);
    }

    int32_t *accumulator = (int32_t *)malloc((size_t)net.hidden * sizeof(int32_t));
    if (!accumulator) {
        return evaluate_classic_board(board);
    }

    for (int i = 0; i < net.hidden; ++i) {
        accumulator[i] = net.hidden_bias[i];
    }

    for (int sq = 0; sq < 64; ++sq) {
        int piece = board->squares[sq];
        int feature = feature_index_for_piece(piece, sq);
        if (feature < 0) {
            continue;
        }
        const int16_t *weights = &net.feature_weights[(size_t)feature * (size_t)net.hidden];
        for (int i = 0; i < net.hidden; ++i) {
            accumulator[i] += weights[i];
        }
    }

    int32_t output = net.output_bias;
    for (int i = 0; i < net.hidden; ++i) {
        output += clipped_relu(accumulator[i]) * net.output_weights[i];
    }
    free(accumulator);

    return (int)(output / net.scale);
}
