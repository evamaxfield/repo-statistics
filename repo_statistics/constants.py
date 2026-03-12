#!/usr/bin/env python

from enum import StrEnum


class FileTypes(StrEnum):
    programming = "programming"
    markup = "markup"
    prose = "prose"
    data = "data"
    unknown = "unknown"
