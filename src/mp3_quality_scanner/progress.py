
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from mp3_quality_scanner.scanner import (
    ScanEvent,
    ScanEventType,
)


class ScanProgress:
    def __init__(self, console: Console) -> None:
        self.console = console

        self.progress = Progress(
            TextColumn("[bold blue]Scanning"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        )

        self.task_id = self.progress.add_task(
            "Scanning",
            total=0,
        )

        self.analyzed = 0
        self.cached = 0
        self.errors = 0
        self.warnings = 0
        self.active: set[str] = set()

        self.live = Live(
            self._render(),
            console=console,
            refresh_per_second=4,
        )

    def __enter__(self) -> "ScanProgress":
        self.live.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.live.stop()

    def on_event(self, event: ScanEvent) -> None:
        if event.type == ScanEventType.DISCOVERED:
            self.progress.update(
                self.task_id,
                total=event.total or 0,
            )

        elif event.type == ScanEventType.STARTED:
            if event.path is not None:
                self.active.add(event.path)

        elif event.type == ScanEventType.SKIPPED:
            self.cached += 1
            self.progress.advance(self.task_id)

        elif event.type == ScanEventType.COMPLETED:
            self.analyzed += 1

            if event.path is not None:
                self.active.discard(event.path)

            if event.status == "error":
                self.errors += 1
            elif event.status == "warning":
                self.warnings += 1

            self.progress.advance(self.task_id)

        elif event.type == ScanEventType.FAILED:
            self.errors += 1
            self.progress.advance(self.task_id)

        self.live.update(self._render())

    def _render(self) -> Panel:
        summary = Table.grid(padding=(0, 2))
        summary.add_row(
            f"Analyzed: {self.analyzed}",
            f"Cached: {self.cached}",
            f"Errors: {self.errors}",
            f"Warnings: {self.warnings}",
        )

        active = Table.grid()
        active.add_row("[bold]Active files:[/bold]")

        for index, path in enumerate(sorted(self.active), start=1):
            active.add_row(f"  {index:02d}  {path}")

        return Panel(
            Group(
                self.progress,
                summary,
                active,
            ),
            title="MP3 Quality Scanner",
        )
