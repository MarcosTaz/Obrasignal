from __future__ import annotations

import re
import shlex
import unicodedata

from .contracts import BangInvocation

MAX_COMMAND_LENGTH = 2048
MAX_ARGS = 32
MAX_ARG_LENGTH = 512
_COMMAND_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


class BangParseError(ValueError):
    pass


def _contains_control_or_format(text: str) -> bool:
    return any(unicodedata.category(ch) in {"Cc", "Cf"} for ch in text)


def parse_bang(text: str) -> BangInvocation:
    if not isinstance(text, str):
        raise BangParseError("command must be text")
    if not text:
        raise BangParseError("empty command")
    if len(text) > MAX_COMMAND_LENGTH:
        raise BangParseError("command too large")
    if _contains_control_or_format(text):
        raise BangParseError("control or format characters are not allowed")
    if not text.startswith("!"):
        raise BangParseError("bang command must start with !")
    try:
        tokens = shlex.split(text, posix=True)
    except ValueError as exc:
        raise BangParseError("malformed command") from exc
    if not tokens:
        raise BangParseError("empty command")
    head = tokens[0]
    if not head.startswith("!") or head.count("!") != 1:
        raise BangParseError("malformed command name")
    command = head[1:].lower()
    if not _COMMAND_RE.fullmatch(command):
        raise BangParseError("invalid command name")
    args = tuple(tokens[1:])
    if len(args) > MAX_ARGS:
        raise BangParseError("too many arguments")
    if any(len(arg) > MAX_ARG_LENGTH for arg in args):
        raise BangParseError("argument too large")
    return BangInvocation(command=command, args=args, raw=text)
