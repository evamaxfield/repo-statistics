#!/usr/bin/env python

from enum import Enum


class FileTypes(str, Enum):
    programming = "programming"
    markup = "markup"
    prose = "prose"
    data = "data"
    unknown = "unknown"
