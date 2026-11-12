
import subprocess
from unittest.mock import patch

import pytest

from mp3_quality_scanner.toolchain import (
    ToolchainError,
    check_tool,
    check_toolchain,
)


def test_tool_available() -> None:
    completed = subprocess.CompletedProcess(
        args=["ffmpeg", "-version"],
        returncode=0,
        stdout="ffmpeg version 8.0\nconfiguration...",
        stderr="",
    )

    with (
        patch(
            "mp3_quality_scanner.toolchain.shutil.which",
            return_value="/usr/bin/ffmpeg",
        ),
        patch(
            "mp3_quality_scanner.toolchain.subprocess.run",
            return_value=completed,
        ),
    ):
        result = check_tool("ffmpeg")

    assert result.name == "ffmpeg"
    assert result.path == "/usr/bin/ffmpeg"
    assert result.version == "ffmpeg version 8.0"


def test_tool_missing() -> None:
    with patch(
        "mp3_quality_scanner.toolchain.shutil.which",
        return_value=None,
    ), pytest.raises(ToolchainError, match="not found"):
        check_tool("ffmpeg")


def test_tool_execution_failed() -> None:
    completed = subprocess.CompletedProcess(
        args=["ffprobe", "-version"],
        returncode=1,
        stdout="",
        stderr="Execution failed",
    )

    with (
        patch(
            "mp3_quality_scanner.toolchain.shutil.which",
            return_value="/usr/bin/ffprobe",
        ),
        patch(
            "mp3_quality_scanner.toolchain.subprocess.run",
            return_value=completed,
        ),pytest.raises(ToolchainError, match="exit code 1")
    ):
        check_tool("ffprobe")


def test_toolchain_checks_both_tools() -> None:
    with patch(
        "mp3_quality_scanner.toolchain.check_tool"
    ) as mock_check:
        check_toolchain()

    assert mock_check.call_count == 2
    assert [call.args[0] for call in mock_check.call_args_list] == [
        "ffmpeg",
        "ffprobe",
    ]
