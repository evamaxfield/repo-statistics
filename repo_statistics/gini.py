#!/usr/bin/env python

import numpy as np

###############################################################################


def _compute_gini(arr: list[int]) -> float:
    if len(arr) == 0:
        return np.nan

    x = np.asarray(arr, dtype=float)
    if np.all(x == 0):
        return np.nan

    sorted_x = np.sort(x)
    n = len(sorted_x)
    cumx = np.cumsum(sorted_x)
    return float((n + 1 - 2 * np.sum(cumx) / cumx[-1]) / n)
