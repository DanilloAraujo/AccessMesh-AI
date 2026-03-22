"""Shared SlowAPI rate-limiter instance."""

from slowapi import Limiter  # type: ignore[import]
from slowapi.util import get_remote_address  # type: ignore[import]

limiter = Limiter(key_func=get_remote_address)
