from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from cookiekit import save_cookies_txt
from requests.cookies import create_cookie


MODULE_PATH = Path(__file__).resolve().parents[1] / "MA" / "capture_images.py"
SPEC = importlib.util.spec_from_file_location("capture_images", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
capture_images = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = capture_images
SPEC.loader.exec_module(capture_images)

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-data"
SVG_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"


def write_file(path: Path, contents: str | bytes = "x") -> None:
    if isinstance(contents, bytes):
        path.write_bytes(contents)
    else:
        path.write_text(contents, encoding="utf-8")


class FakeResponse:
    def __init__(self, status_code: int, url: str, body: bytes, content_type: str) -> None:
        self.status_code = status_code
        self.url = url
        self.content = body
        self.headers = {"Content-Type": content_type}


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(self, responses: dict[str, list[FakeResponse]]) -> None:
        self.responses = {url: list(queue) for url, queue in responses.items()}
        self.requests: list[dict[str, object]] = []
        self.session = FakeSession()

    def request(self, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append({"url": url, **kwargs})
        queue = self.responses.get(url)
        if not queue:
            raise AssertionError(f"Unexpected request for {url}")
        return queue.pop(0)


def test_sync_completed_topic_copies_outputs_and_runs_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_root = tmp_path / "graphics"
    topic_dir = output_root / "10"
    topic_dir.mkdir(parents=True)
    write_file(topic_dir / "alpha.png", PNG_BYTES)
    write_file(topic_dir / capture_images.IMAGE_METADATA_FILE, '{"ok": true}\n')

    state_file = output_root / "_image_state.jsonl"
    write_file(state_file, '{"topic_id":"10","status":"completed"}\n')

    mirror_dir = tmp_path / "mirror" / "Images"
    source_repo = tmp_path / "source-repo"
    dest_repo = tmp_path / "dest-repo"
    source_repo.mkdir()
    dest_repo.mkdir()

    commands: list[tuple[tuple[str, ...], str]] = []

    def fake_run(command, cwd, text, capture_output, timeout, check):  # type: ignore[no-untyped-def]
        del text, capture_output, timeout, check
        commands.append((tuple(command), cwd))
        if command[:5] == ["git", "diff", "--cached", "--quiet", "--exit-code"]:
            return subprocess.CompletedProcess(command, 1, "", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(capture_images.subprocess, "run", fake_run)

    args = capture_images.argparse.Namespace(
        output_root=output_root,
        sync_copy_dest=mirror_dir,
        sync_source_repo=source_repo,
        sync_dest_repo=dest_repo,
        sync_commit_prefix="images",
        sync_command_timeout_seconds=30.0,
    )
    job = capture_images.TopicImageJob(
        topic_id="10",
        name="Topic Ten",
        url="https://mathacademy.test/topics/10",
        images=(capture_images.ImageRecord(topic_id="10", img_src="/graphics/alpha"),),
    )

    capture_images.sync_completed_topic(job, state_file, args)

    assert (mirror_dir / "10" / "alpha.png").read_bytes() == PNG_BYTES
    assert (mirror_dir / capture_images.DEFAULT_STATE_FILE).read_text(encoding="utf-8") == (
        '{"topic_id":"10","status":"completed"}\n'
    )
    assert commands == [
        (("git", "add", "."), str(source_repo)),
        (("git", "diff", "--cached", "--quiet", "--exit-code"), str(source_repo)),
        (("git", "commit", "-m", "images topic 10"), str(source_repo)),
        (("git", "push"), str(source_repo)),
        (("git", "add", "."), str(dest_repo)),
        (("git", "diff", "--cached", "--quiet", "--exit-code"), str(dest_repo)),
        (("git", "commit", "-m", "images topic 10"), str(dest_repo)),
        (("git", "push"), str(dest_repo)),
    ]


def test_topic_complete_accepts_metadata_files(tmp_path: Path) -> None:
    topic_dir = tmp_path / "101"
    topic_dir.mkdir()
    write_file(topic_dir / "alpha.png", PNG_BYTES)
    write_file(topic_dir / "beta.svg", SVG_BYTES)

    metadata = {
        "topic_id": "101",
        "image_count": 2,
        "images": [
            {"img_src": "/graphics/alpha", "filename": "alpha.png"},
            {"img_src": "/graphics/beta", "filename": "beta.svg"},
        ],
    }
    (topic_dir / capture_images.IMAGE_METADATA_FILE).write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    images = (
        capture_images.ImageRecord(topic_id="101", img_src="/graphics/alpha"),
        capture_images.ImageRecord(topic_id="101", img_src="/graphics/beta"),
    )

    assert capture_images.topic_complete(topic_dir, images)


def test_topic_complete_accepts_existing_files_without_metadata(tmp_path: Path) -> None:
    topic_dir = tmp_path / "202"
    topic_dir.mkdir()
    write_file(topic_dir / "alpha.png", PNG_BYTES)
    write_file(topic_dir / "beta.svg", SVG_BYTES)

    images = (
        capture_images.ImageRecord(topic_id="202", img_src="/graphics/alpha"),
        capture_images.ImageRecord(topic_id="202", img_src="/graphics/beta"),
    )

    assert capture_images.topic_complete(topic_dir, images)


def test_run_downloads_images_with_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_url = "https://mathacademy.test"
    topic_url = f"{base_url}/topics/10"

    topics_csv = tmp_path / "Topics.csv"
    topics_csv.write_text(
        "topic-id,name,url\n10,Topic Ten," + topic_url + "\n",
        encoding="utf-8",
    )

    images_csv = tmp_path / "Images.csv"
    images_csv.write_text(
        "topic-id,img-src\n10,/graphics/alpha\n10,/graphics/beta\n",
        encoding="utf-8",
    )

    cookie_path = tmp_path / "cookies.txt"
    save_cookies_txt(
        cookie_path,
        [create_cookie(name="sessionid", value="abc123", domain=".mathacademy.test", path="/")],
    )

    output_root = tmp_path / "graphics"
    fake_client = FakeClient(
        {
            f"{base_url}/graphics/alpha": [
                FakeResponse(429, f"{base_url}/graphics/alpha", b"slow down", "text/plain; charset=utf-8"),
                FakeResponse(200, f"{base_url}/graphics/alpha", PNG_BYTES, "application/octet-stream"),
            ],
            f"{base_url}/graphics/beta": [
                FakeResponse(200, f"{base_url}/graphics/beta", SVG_BYTES, "image/svg+xml"),
            ],
        }
    )
    captured: dict[str, object] = {}

    def fake_build_client(cookies, args):  # type: ignore[no-untyped-def]
        captured["cookies"] = cookies
        captured["args"] = args
        return fake_client

    monkeypatch.setattr(capture_images, "build_client", fake_build_client)

    exit_code = capture_images.run(
        [
            "--topics-csv",
            str(topics_csv),
            "--images-csv",
            str(images_csv),
            "--output-root",
            str(output_root),
            "--cookies",
            str(cookie_path),
            "--cookie-domain",
            "mathacademy.test",
            "--base-url",
            base_url,
            "--sleep-topic-min",
            "0",
            "--sleep-topic-max",
            "0",
            "--sleep-image-min",
            "0",
            "--sleep-image-max",
            "0",
            "--rest-every",
            "0",
            "--retries",
            "1",
            "--retry-base-seconds",
            "0",
            "--retry-max-seconds",
            "0",
            "--no-progress",
        ]
    )

    assert exit_code == 0
    assert (output_root / "10" / "alpha.png").read_bytes() == PNG_BYTES
    assert (output_root / "10" / "beta.svg").read_bytes() == SVG_BYTES

    metadata = json.loads((output_root / "10" / capture_images.IMAGE_METADATA_FILE).read_text(encoding="utf-8"))
    assert metadata["image_count"] == 2
    assert [entry["filename"] for entry in metadata["images"]] == ["alpha.png", "beta.svg"]

    assert len(captured["cookies"]) == 1
    assert [request["url"] for request in fake_client.requests] == [
        f"{base_url}/graphics/alpha",
        f"{base_url}/graphics/alpha",
        f"{base_url}/graphics/beta",
    ]
    assert all(request["headers"]["Referer"] == topic_url for request in fake_client.requests)
    assert all(request["headers"]["Accept"] == capture_images.IMAGE_ACCEPT_HEADER for request in fake_client.requests)
    assert fake_client.session.closed is True


def test_run_stops_on_login_response(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_url = "https://mathacademy.test"
    topic_url = f"{base_url}/topics/11"

    topics_csv = tmp_path / "Topics.csv"
    topics_csv.write_text(
        "topic-id,name,url\n11,Topic Eleven," + topic_url + "\n",
        encoding="utf-8",
    )

    images_csv = tmp_path / "Images.csv"
    images_csv.write_text(
        "topic-id,img-src\n11,/graphics/login\n",
        encoding="utf-8",
    )

    cookie_path = tmp_path / "cookies.txt"
    save_cookies_txt(
        cookie_path,
        [create_cookie(name="sessionid", value="abc123", domain=".mathacademy.test", path="/")],
    )

    output_root = tmp_path / "graphics"
    state_file = output_root / "_image_state.jsonl"
    fake_client = FakeClient(
        {
            f"{base_url}/graphics/login": [
                FakeResponse(
                    200,
                    f"{base_url}/login",
                    b"<html><body><form><input type='password'></form></body></html>",
                    "text/html; charset=utf-8",
                ),
            ],
        }
    )

    monkeypatch.setattr(capture_images, "build_client", lambda cookies, args: fake_client)

    exit_code = capture_images.run(
        [
            "--topics-csv",
            str(topics_csv),
            "--images-csv",
            str(images_csv),
            "--output-root",
            str(output_root),
            "--cookies",
            str(cookie_path),
            "--cookie-domain",
            "mathacademy.test",
            "--base-url",
            base_url,
            "--sleep-topic-min",
            "0",
            "--sleep-topic-max",
            "0",
            "--sleep-image-min",
            "0",
            "--sleep-image-max",
            "0",
            "--rest-every",
            "0",
            "--retry-base-seconds",
            "0",
            "--retry-max-seconds",
            "0",
            "--no-progress",
        ]
    )

    assert exit_code == 2
    lines = [json.loads(line) for line in state_file.read_text(encoding="utf-8").splitlines()]
    assert lines[-1]["status"] == "auth_failed"
    assert [request["url"] for request in fake_client.requests] == [f"{base_url}/graphics/login"]
    assert fake_client.session.closed is True
