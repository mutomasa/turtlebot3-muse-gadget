"""Keep stdout clean: Muse parses stdout as a single JSON object."""

from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Iterator


@contextlib.contextmanager
def stdout_to_stderr() -> Iterator[None]:
    """Redirect fd 1 (including native DDS/rcl output) to stderr temporarily."""
    sys.stdout.flush()
    saved = os.dup(1)
    try:
        os.dup2(2, 1)
        with contextlib.redirect_stdout(sys.stderr):
            yield
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(saved)
