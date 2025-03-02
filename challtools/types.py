from __future__ import annotations
from typing import TypedDict, Any

JsonDict = dict[str, Any]


class ValidatorMessage(TypedDict):
    """The type of messages returned by validators."""

    code: str
    field: str | None
    name: str
    level: int
    message: str
