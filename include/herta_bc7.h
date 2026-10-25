/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef HERTA_BC7_H
#define HERTA_BC7_H
#ifndef HERTA_FREESTANDING_WINDOWS
#include <stddef.h>
#include <stdint.h>
#endif
#if defined(_WIN32)
#ifdef HERTA_BC7_BUILD
#define HERTA_BC7_API __declspec(dllexport)
#else
#define HERTA_BC7_API __declspec(dllimport)
#endif
#else
#define HERTA_BC7_API __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
#endif

HERTA_BC7_API unsigned herta_dds_abi_version(void);

/* Input is BC7 base-mip BLOCK DATA, without the DDS container header.
 * Decode returns packed RGBA8 in source row order. capacity is in bytes.
 * Pool returns packed RGB float64 means (0..255). count is in doubles.
 * Pool boundaries are floor(i * input_dimension / output_dimension).
 * All pixels contribute; output dimensions must not exceed the input.
 * Both functions return 1 on success, 0 on invalid input/capacity.
 * A reserved BC7 block decodes to transparent black, matching the reference.
 * Calls are reentrant. Inputs/outputs must not overlap. The caller owns buffers.
 */
HERTA_BC7_API int herta_dds_decode_bc7(
    const uint8_t *src, size_t size, unsigned w, unsigned h,
    uint8_t *dst, size_t capacity);
HERTA_BC7_API int herta_dds_pool_bc7(
    const uint8_t *src, size_t size, unsigned w, unsigned h,
    unsigned ow, unsigned oh, double *dst, size_t count);

#ifdef __cplusplus
}
#endif
#endif
