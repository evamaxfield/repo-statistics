#!/usr/bin/env python

import numpy as np

###############################################################################


def _compute_gini(arr: list[int]) -> float:
    # From: https://stackoverflow.com/a/61154922
    if len(arr) == 0:
        return np.nan

    # Convert to numpy array
    np_arr = np.array(arr)

    # Handle case where all values are zero or mean is zero
    mean_val = np.mean(np_arr)
    if mean_val == 0:
        # Perfect equality when all values are zero
        return 0.0

    diffsum = 0
    for i, xi in enumerate(np_arr[:-1], 1):
        diffsum += np.sum(np.abs(xi - np_arr[i:]))
    return diffsum / (len(np_arr) ** 2 * mean_val)
