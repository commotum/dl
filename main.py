"""Convenience launcher for the default Math Academy image download job."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parent
CAPTURE_SCRIPT = ROOT / "MA" / "capture_images.py"
DEFAULT_ARGS = [
    "--cookies",
    str(ROOT / "MA" / ".auth" / "mathacademy-cookies.txt"),
    "--sync-after-topic",
]


def _load_capture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ma_capture_images", CAPTURE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load capture script from {CAPTURE_SCRIPT}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    module = _load_capture_module()
    extra_args = sys.argv[1:] if argv is None else argv
    return module.run(DEFAULT_ARGS + list(extra_args))


if __name__ == "__main__":
    raise SystemExit(main())
