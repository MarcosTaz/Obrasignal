from __future__ import annotations

import re


CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
CASE_ID_ADDRESSABILITY_ERROR = (
    "case_id must be URL-addressable: 1-200 letters, digits, dot, underscore, colon, or hyphen"
)


def is_addressable_case_id(value) -> bool:
    return isinstance(value, str) and CASE_ID_PATTERN.fullmatch(value) is not None
