"""Path helpers shared by tests."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# tests are run from the repository root. To make `from nsight import ...`
# resolve regardless of where the user invoked discovery from, we ensure the
# skill's `scripts/` directory is on sys.path.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
_SKILL_DIR = (
    _REPO_ROOT
    / "plugins"
    / "nsight-graphics-analyzer"
    / "skills"
    / "nsight-graphics-analyzer"
)
_SCRIPTS_DIR = _SKILL_DIR / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def sample_bundle_dir() -> Path:
    return _HERE / "data" / "BASE"


def sample_regimes_path() -> Path | None:
    """Path to a real GPUTRACE_REGIMES.xls or None if not configured.

    Set the env var `NSIGHT_SKILL_REGIMES_SAMPLE` to enable tests that need
    the full REGIMES file (it's too big to commit).
    """
    override = os.environ.get("NSIGHT_SKILL_REGIMES_SAMPLE")
    if override and Path(override).is_file():
        return Path(override)
    return None
