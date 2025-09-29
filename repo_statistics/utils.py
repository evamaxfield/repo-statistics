#!/usr/bin/env python

from pathlib import Path
from . import constants
from .data import FILE_FORMATS_TO_DTYPE_DF
import polars as pl
from functools import lru_cache

###############################################################################

@lru_cache(2**14)
def get_file_type(fp: str | Path) -> str:
    """
    Determine the file type based on its extension using the Linguist data.
    """
    # Extract the filename from the path
    filename = Path(fp).name.lower()
    
    # Check if there is an exact filename match in the data
    filename_match = FILE_FORMATS_TO_DTYPE_DF.filter(
        pl.col("filename") == filename
    )
    if not filename_match.is_empty():
        matched_types = filename_match["type"].unique()
        if len(matched_types) == 1:
            return matched_types[0]
        
    # Check for extension match in the data
    extension = Path(fp).suffix.lower()
    matched = FILE_FORMATS_TO_DTYPE_DF.filter(
        pl.col("extension") == extension
    )
    if matched.is_empty():
        return constants.FileTypes.unknown
    
    matched_types = matched["type"].unique()

    # Handle single type match
    if len(matched_types) == 1:
        return matched_types[0]
    
    # Check if multiple types matched;
    # default to priority order: "prose", "data", "markup", "programming", "unknown"
    if len(matched_types) > 1:
        for dtype in [
            constants.FileTypes.prose,
            constants.FileTypes.data,
            constants.FileTypes.markup,
            constants.FileTypes.programming,
        ]:
            if dtype in matched_types:
                return dtype
    
    return constants.FileTypes.unknown