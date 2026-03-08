from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"
SPEC = importlib.util.spec_from_file_location("dl_main", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
dl_main = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dl_main
SPEC.loader.exec_module(dl_main)


class FakeCaptureModule:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, argv: list[str]) -> int:
        self.calls.append(list(argv))
        return 123


def test_main_uses_capture_images_defaults(monkeypatch) -> None:
    fake_module = FakeCaptureModule()
    monkeypatch.setattr(dl_main, "_load_capture_module", lambda: fake_module)

    exit_code = dl_main.main(["--topic-id", "37"])

    assert exit_code == 123
    assert fake_module.calls == [
        [
            "--cookies",
            str(dl_main.ROOT / "MA" / ".auth" / "mathacademy-cookies.txt"),
            "--sync-after-topic",
            "--topic-id",
            "37",
        ]
    ]
    assert dl_main.CAPTURE_SCRIPT == dl_main.ROOT / "MA" / "capture_images.py"
