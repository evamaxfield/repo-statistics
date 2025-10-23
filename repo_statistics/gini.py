#!/usr/bin/env python

import numpy as np

###############################################################################

def _compute_gini(arr: list[int]) -> float:
    # From: https://stackoverflow.com/a/61154922
    arr = np.array(arr)
    diffsum = 0
    for i, xi in enumerate(arr[:-1], 1):
        diffsum += np.sum(np.abs(xi - arr[i:]))
    return diffsum / (len(arr)**2 * np.mean(arr))