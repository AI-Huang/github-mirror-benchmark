"""GitHub Mirror Benchmark — measure download speed across GitHub mirrors."""

from __future__ import annotations

import os
import time
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
import httpx
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

# Suppress SSL warnings — this tool benchmarks speed, not security
warnings.filterwarnings("ignore", message=".*Unverified HTTPS.*")
try:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

console = Console()


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip("\"'")


_load_dotenv(Path(__file__).resolve().with_name(".env"))

# ---------------------------------------------------------------------------
# Mirror registry
# ---------------------------------------------------------------------------

MIRRORS: dict[str, str] = {
    # Official
    "github.com (official)": "https://github.com",
    # Direct-replace mirrors (swap github.com domain)
    "kkgithub.com": "https://kkgithub.com",
    "bgithub.xyz": "https://bgithub.xyz",
    "dgithub.xyz": "https://dgithub.xyz",
    "githubfast.com": "https://githubfast.com",
    "hub.gitmirror.com": "https://hub.gitmirror.com",
    "hub.nuaa.cf": "https://hub.nuaa.cf",
    # Proxy mirrors (prepend base to full github URL)
    "gh-proxy.com": "https://gh-proxy.com/https://github.com",
    "ghfast.top": "https://ghfast.top/https://github.com",
    "gh.ddlc.top": "https://gh.ddlc.top/https://github.com",
    "gh.llkk.cc": "https://gh.llkk.cc/https://github.com",
    "ghproxy.net": "https://ghproxy.net/https://github.com",
    "moeyy.cn": "https://gh.moeyy.cn/https://github.com",
    "github.akams.cn": "https://github.akams.cn/https://github.com",
}

# A small but non-trivial release asset used as the benchmark target.
# Path is appended to each mirror base URL.
BENCH_FILE_PATH = os.getenv(
    "BENCH_FILE_PATH",
    "/example-owner/example-repo/releases/download/v0.0.0/example.bin",
)
DEFAULT_TIMEOUT_MS = 10_000
DEFAULT_ENDURANCE_MS = 30_000
OUTPUTS_DIR = Path("outputs")


# ---------------------------------------------------------------------------
# Benchmark logic
# ---------------------------------------------------------------------------


@dataclass
class MirrorResult:
    name: str
    url: str
    status: Optional[int] = None
    ttfb_ms: Optional[float] = None  # time-to-first-byte
    t1k_ms: Optional[float] = None  # time to receive 1 KB
    speed_1k_mbps: Optional[float] = None  # throughput at 1 KB
    t1000k_ms: Optional[float] = None  # time to receive 1000 KiB
    speed_1000k_mbps: Optional[float] = None  # throughput at 1000 KiB
    t10mib_ms: Optional[float] = None  # time to receive 10 MiB
    speed_10mib_mbps: Optional[float] = None  # throughput at 10 MiB
    bytes_downloaded: int = 0
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status is not None and self.status < 400


def _benchmark_mirror(
    name: str,
    base_url: str,
    file_path: str,
    timeout_ms: int,
    endurance_ms: int,
    speed_mbps: bool,
) -> MirrorResult:
    url = base_url.rstrip("/") + file_path
    result = MirrorResult(name=name, url=url)
    timeout_s = timeout_ms / 1000
    target_1k = 1 * 1024
    target_1000k = 1000 * 1024
    target_10mib = 10 * 1024 * 1024
    try:
        with httpx.Client(
            follow_redirects=True, timeout=timeout_s, verify=False
        ) as client:
            t0 = time.perf_counter()
            with client.stream("GET", url) as resp:
                result.ttfb_ms = (time.perf_counter() - t0) * 1000
                result.status = resp.status_code
                if resp.status_code >= 400:
                    result.error = f"HTTP {resp.status_code}"
                    return result
                downloaded = 0
                t_start = time.perf_counter()
                for chunk in resp.iter_bytes(chunk_size=4 * 1024):
                    downloaded += len(chunk)
                    elapsed_ms = (time.perf_counter() - t_start) * 1000
                    if result.t1k_ms is None and downloaded >= target_1k:
                        result.t1k_ms = elapsed_ms
                        result.speed_1k_mbps = _bytes_per_ms_to_mibps(
                            downloaded, elapsed_ms
                        )
                    if result.t1000k_ms is None and downloaded >= target_1000k:
                        result.t1000k_ms = elapsed_ms
                        result.speed_1000k_mbps = _bytes_per_ms_to_mibps(
                            downloaded, elapsed_ms
                        )
                    if result.t10mib_ms is None and downloaded >= target_10mib:
                        result.t10mib_ms = elapsed_ms
                        result.speed_10mib_mbps = _bytes_per_ms_to_mibps(
                            downloaded, elapsed_ms
                        )
                        break
                    if elapsed_ms >= endurance_ms:
                        break
                result.bytes_downloaded = downloaded
                if not speed_mbps:
                    result.speed_1k_mbps = None
                    result.speed_1000k_mbps = None
                    result.speed_10mib_mbps = None
    except httpx.TimeoutException:
        result.error = "timeout"
    except httpx.ConnectError as exc:
        msg = str(exc)
        if "UNEXPECTED_EOF" in msg:
            result.error = "SSL EOF (blocked)"
        elif "CERTIFICATE" in msg:
            result.error = "SSL cert error"
        elif "HANDSHAKE" in msg:
            result.error = "SSL handshake fail"
        else:
            result.error = msg[:40]
    except Exception as exc:  # noqa: BLE001
        result.error = str(exc)[:40]
    return result


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _ms_str(ms: Optional[float]) -> str:
    return "—" if ms is None else f"{ms:.0f} ms"


def _bytes_per_ms_to_mibps(byte_count: int, elapsed_ms: float) -> Optional[float]:
    if elapsed_ms <= 0:
        return None
    return (byte_count / (elapsed_ms / 1000)) / (1024 * 1024)


def _speed_str(mbps: Optional[float]) -> str:
    if mbps is None:
        return "—"
    if mbps >= 1:
        return f"{mbps:.2f} MB/s"
    return f"{mbps * 1024:.1f} KB/s"


def _sorted_results(results: list[MirrorResult]) -> list[MirrorResult]:
    return sorted(
        results,
        key=lambda r: r.t10mib_ms if r.t10mib_ms is not None else float("inf"),
    )


def _validate_mirror_names(
    ctx: click.Context,
    param: click.Parameter,
    values: tuple[str, ...],
) -> tuple[str, ...]:
    for value in values:
        if value.startswith("-"):
            raise click.BadParameter(
                f"missing mirror name before {value!r}", ctx=ctx, param=param
            )
    return values


def _render_table(results: list[MirrorResult], show_speed_mbps: bool) -> None:
    table = Table(title="GitHub Mirror Benchmark Results", show_lines=True)
    table.add_column("Mirror", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("TTFB", justify="right")
    table.add_column("1 KB", justify="right")
    if show_speed_mbps:
        table.add_column("Speed", justify="right", min_width=8)
    table.add_column("1000 KiB", justify="right")
    if show_speed_mbps:
        table.add_column("Speed", justify="right", min_width=8)
    table.add_column("10 MiB", justify="right")
    if show_speed_mbps:
        table.add_column("Speed", justify="right", min_width=8)

    for r in _sorted_results(results):
        status_cell = (
            f"[green]{r.status}[/green]"
            if r.ok
            else f"[red]{r.error or r.status}[/red]"
        )
        row = [
            r.name,
            status_cell,
            _ms_str(r.ttfb_ms),
            _ms_str(r.t1k_ms),
        ]
        if show_speed_mbps:
            row.append(_speed_str(r.speed_1k_mbps))
        row.append(_ms_str(r.t1000k_ms))
        if show_speed_mbps:
            row.append(_speed_str(r.speed_1000k_mbps))
        row.append(_ms_str(r.t10mib_ms))
        if show_speed_mbps:
            row.append(_speed_str(r.speed_10mib_mbps))
        table.add_row(*row)

    console.print(table)


def _md_cell(value: object) -> str:
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return text or "—"


def _write_markdown_report(
    results: list[MirrorResult],
    file_path: str,
    timeout_ms: int,
    endurance_ms: int,
    show_speed_mbps: bool,
) -> Path:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().astimezone()
    report_path = OUTPUTS_DIR / f"benchmark-{generated_at:%Y%m%d-%H%M%S}.md"

    headers = ["Mirror", "Status", "TTFB", "1 KB"]
    if show_speed_mbps:
        headers.append("1 KB Speed")
    headers.append("1000 KiB")
    if show_speed_mbps:
        headers.append("1000 KiB Speed")
    headers.append("10 MiB")
    if show_speed_mbps:
        headers.append("10 MiB Speed")
    headers.append("Bytes Downloaded")

    lines = [
        "# GitHub Mirror Benchmark Report",
        "",
        f"- Generated: {generated_at.isoformat(timespec='seconds')}",
        f"- File: `{file_path}`",
        f"- Timeout: {timeout_ms} ms",
        f"- Endurance: {endurance_ms} ms",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for result in _sorted_results(results):
        status = str(result.status) if result.ok else str(result.error or result.status)
        row = [
            result.name,
            status,
            _ms_str(result.ttfb_ms),
            _ms_str(result.t1k_ms),
        ]
        if show_speed_mbps:
            row.append(_speed_str(result.speed_1k_mbps))
        row.append(_ms_str(result.t1000k_ms))
        if show_speed_mbps:
            row.append(_speed_str(result.speed_1000k_mbps))
        row.append(_ms_str(result.t10mib_ms))
        if show_speed_mbps:
            row.append(_speed_str(result.speed_10mib_mbps))
        row.append(str(result.bytes_downloaded))
        lines.append("| " + " | ".join(_md_cell(value) for value in row) + " |")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Benchmark download speed across GitHub mirrors."""


@cli.command()
@click.option(
    "--file",
    "file_path",
    default=BENCH_FILE_PATH,
    show_default=True,
    help="File path (relative to mirror root) used as the benchmark target.",
)
@click.option(
    "--timeout",
    default=DEFAULT_TIMEOUT_MS,
    show_default=True,
    help="Per-mirror request timeout in milliseconds.",
)
@click.option(
    "--endurance",
    default=DEFAULT_ENDURANCE_MS,
    show_default=True,
    help="Maximum download duration per mirror in milliseconds.",
)
@click.option(
    "--mirror",
    "extra_mirrors",
    multiple=True,
    metavar="NAME=URL",
    help="Add an extra mirror as NAME=URL (repeatable).",
)
@click.option(
    "--only",
    "only_mirrors",
    multiple=True,
    metavar="NAME",
    callback=_validate_mirror_names,
    help="Only benchmark the named mirror(s) from the built-in list.",
)
@click.option(
    "--show-speed-mbps/--no-speed-mbps",
    default=True,
    show_default=True,
    help="Show or hide throughput columns and MB/s calculation.",
)
def run(
    file_path: str,
    timeout: int,
    endurance: int,
    extra_mirrors: tuple[str, ...],
    only_mirrors: tuple[str, ...],
    show_speed_mbps: bool,
) -> None:
    """Run the benchmark: measure time to download 1 KB, 1000 KiB, and 10 MiB."""
    mirrors = dict(MIRRORS)

    for item in extra_mirrors:
        if "=" not in item:
            raise click.BadParameter(
                f"Expected NAME=URL, got: {item!r}", param_hint="--mirror"
            )
        name, _, url = item.partition("=")
        mirrors[name.strip()] = url.strip()

    if only_mirrors:
        mirrors = {k: v for k, v in mirrors.items() if k in only_mirrors}
        if not mirrors:
            console.print("[red]No matching mirrors found.[/red]")
            raise SystemExit(1)

    console.print(f"\n[bold]Benchmarking [cyan]{len(mirrors)}[/cyan] mirror(s)[/bold]")
    console.print(f"  File   : [dim]{file_path}[/dim]")
    console.print("  Metric : [dim]time to 1 KB / 1000 KiB / 10 MiB[/dim]")
    console.print(f"  Timeout: [dim]{timeout} ms[/dim]")
    console.print(f"  Endurance: [dim]{endurance} ms[/dim]\n")

    results: list[MirrorResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Testing mirrors…", total=len(mirrors))
        for name, base_url in mirrors.items():
            progress.update(task, description=f"Testing [cyan]{name}[/cyan]…")
            result = _benchmark_mirror(
                name, base_url, file_path, timeout, endurance, show_speed_mbps
            )
            results.append(result)
            progress.advance(task)

    _render_table(results, show_speed_mbps=show_speed_mbps)
    report_path = _write_markdown_report(
        results, file_path, timeout, endurance, show_speed_mbps=show_speed_mbps
    )
    console.print(f"\n[green]Markdown report written:[/green] [dim]{report_path}[/dim]")


@cli.command("list")
def list_mirrors() -> None:
    """List all built-in mirrors."""
    table = Table(title="Built-in Mirrors", show_lines=True)
    table.add_column("Name", style="cyan")
    table.add_column("Base URL")
    for name, url in MIRRORS.items():
        table.add_row(name, url)
    console.print(table)


if __name__ == "__main__":
    cli()
