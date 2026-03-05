from __future__ import annotations

import json

import pytest
from requestkit import SessionConfig

from downloadkit import DownloadConfig, fetch
from downloadkit.cli import main


def test_fetch_downloads_file_and_replaces_temp(http_server, tmp_path):
    output = tmp_path / "artifact.bin"
    result = fetch(http_server["base_url"] + "/file", DownloadConfig(output=output))

    assert result.status == "downloaded"
    assert output.read_bytes() == http_server["data"]
    assert not (tmp_path / ".artifact.bin.part").exists()


def test_fetch_resumes_existing_part_file(http_server, tmp_path):
    output = tmp_path / "artifact.bin"
    part = tmp_path / ".artifact.bin.part"
    part.write_bytes(http_server["data"][:10])

    result = fetch(http_server["base_url"] + "/range", DownloadConfig(output=output, resume=True))

    assert result.status == "resumed"
    assert output.read_bytes() == http_server["data"]
    assert http_server["state"]["range_headers"][-1] == "bytes=10-"


def test_fetch_rejects_html_for_binary_output(http_server, tmp_path):
    output = tmp_path / "artifact.bin"

    with pytest.raises(Exception) as excinfo:
        fetch(http_server["base_url"] + "/html", DownloadConfig(output=output))

    assert "HTML" in str(excinfo.value)
    assert not output.exists()


def test_fetch_uses_fallback_url(http_server, tmp_path):
    output = tmp_path / "artifact.bin"
    result = fetch(
        http_server["base_url"] + "/primary-fail",
        DownloadConfig(
            output=output,
            fallback_urls=(http_server["base_url"] + "/fallback-file",),
            request=SessionConfig(retries=0),
        ),
    )

    assert result.used_fallback is True
    assert result.used_url.endswith("/fallback-file")
    assert output.read_bytes() == http_server["data"]


def test_cli_fetch_json(http_server, tmp_path, capsys):
    output = tmp_path / "artifact.bin"
    exit_code = main(["fetch", http_server["base_url"] + "/file", "-o", str(output), "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "downloaded"
    assert payload["output"] == str(output)
