#!/usr/bin/env python

import numpy as np

###############################################################################


def _compute_gini(arr: list[int]) -> float:
    # From: https://stackoverflow.com/a/61154922
    np_arr = np.array(arr)
    diffsum = 0
    for i, xi in enumerate(np_arr[:-1], 1):
        diffsum += np.sum(np.abs(xi - np_arr[i:]))
    return diffsum / (len(np_arr) ** 2 * np.mean(np_arr))
