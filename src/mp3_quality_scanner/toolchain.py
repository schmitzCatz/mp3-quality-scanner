
import shutil
import subprocess
from dataclasses import dataclass


class ToolchainError(RuntimeError):
    """Required external audio tools are unavailable."""


@dataclass(frozen=True)
class ToolInfo:
    name: str
    path: str
    version: str


def check_tool(name: str) -> ToolInfo:
    """Check whether an executable is available and working."""
    executable = shutil.which(name)

    if executable is None:
        raise ToolchainError(
            f"{name} was not found in PATH. "
            "Please install FFmpeg and ensure its binaries are accessible."
        )

    try:
        result = subprocess.run(
            [executable, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolchainError(
            f"Failed to execute {name}: {exc}"
        ) from exc

    if result.returncode != 0:
        raise ToolchainError(
            f"{name} returned exit code {result.returncode}: "
            f"{result.stderr.strip()}"
        )

    version = result.stdout.splitlines()

    if not version:
        raise ToolchainError(
            f"{name} returned no version information"
        )

    return ToolInfo(
        name=name,
        path=executable,
        version=version[0],
    )


def check_toolchain() -> list[ToolInfo]:
    """Validate all required audio tools."""
    return [
        check_tool("ffmpeg"),
        check_tool("ffprobe"),
    ]
