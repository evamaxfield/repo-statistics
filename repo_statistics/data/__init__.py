"""Stored data loaders."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import yaml

###############################################################################
# Local storage paths

DATA_FILES_DIR = Path(__file__).parent / "files"

LINGUIST_LANGUAGES_YML = DATA_FILES_DIR / "linguist.yml"
ADDITIONAL_FORMATS_YML = DATA_FILES_DIR / "additional-formats.yml"

###############################################################################


def load_file_formats_dataframe() -> pl.DataFrame:
    """
    Read the GitHub Linguist languages YAML file into a Polars DataFrame.

    Returns:
        A Polars DataFrame containing programming language data from the
        GitHub Linguist repository.
    """
    with open(LINGUIST_LANGUAGES_YML) as open_file:
        data = yaml.safe_load(open_file)

    # Construct dataframe
    records = []
    for language, attributes in data.items():
        filenames = attributes.get("filenames", [])
        extensions = attributes.get("extensions", [])

        if not filenames and not extensions:
            records.append(
                {
                    "language": language,
                    "filename": None,
                    "extension": None,
                    "type": attributes.get("type", None),
                }
            )

        else:
            if filenames:
                if extensions:
                    for filename in filenames:
                        for extension in extensions:
                            records.append(
                                {
                                    "language": language,
                                    "filename": str(filename).lower(),
                                    "extension": str(extension).lower(),
                                    "type": attributes.get("type", None),
                                }
                            )

                else:
                    for filename in filenames:
                        records.append(
                            {
                                "language": language,
                                "filename": filename,
                                "extension": None,
                                "type": attributes.get("type", None),
                            }
                        )

            else:
                if extensions:
                    for extension in extensions:
                        records.append(
                            {
                                "language": language,
                                "filename": None,
                                "extension": extension,
                                "type": attributes.get("type", None),
                            }
                        )

    # Load the additional formats and append them to the records
    with open(ADDITIONAL_FORMATS_YML) as open_file:
        additional_data = yaml.safe_load(open_file)

    # This is much simpler structure
    # It is a list of dicts with
    for dtype, extension_list in additional_data.items():
        for extension in extension_list:
            records.append(
                {
                    "language": None,
                    "filename": None,
                    "extension": f".{extension}",
                    "type": dtype,
                }
            )

    return pl.DataFrame(records)


FILE_FORMATS_TO_DTYPE_DF = load_file_formats_dataframe()
