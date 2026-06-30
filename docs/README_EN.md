# github-mirror-benchmark

Benchmark download speed across GitHub mirrors to find the fastest one for your location.

## Features

- Tests multiple popular GitHub mirrors with live progress
- Measures **time-to-first-byte (latency)**, staged download times, and per-stage **throughput (MB/s)**
- Ranks mirrors by speed
- Supports custom mirrors and per-run file targets
- Writes a Markdown table report to `outputs/` after each run
- Clean terminal output via [Rich](https://github.com/Textualize/rich)

## Installation

Requires Python >= 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url>
cd github-mirror-benchmark
uv sync
```

## Usage

```bash
# Run benchmark with default settings
uv run python main.py run

# Each run writes outputs/benchmark-YYYYMMDD-HHMMSS.md

# Use a larger fake example file for more accurate throughput measurement
uv run python main.py run --file /example-owner/example-repo/releases/download/v0.0.0/example.bin

# Hide throughput and only show staged download times
uv run python main.py run --no-speed-mbps

# Test only specific mirrors
uv run python main.py run --only "github.com (official)" --only "ghproxy.com"

# Add a custom mirror
uv run python main.py run --mirror "my-mirror=https://my.proxy.example.com/https://github.com"

# Adjust timeout and per-mirror endurance (milliseconds)
uv run python main.py run --timeout 10000 --endurance 30000

# List all built-in mirrors
uv run python main.py list
```

## Built-in Mirrors

| Name | Base URL |
| --- | --- |
| github.com (official) | <https://github.com> |
| gh-proxy.com | <https://gh-proxy.com> |
| ghfast.top | <https://ghfast.top> |
| gh.ddlc.top | <https://gh.ddlc.top> |
| gh.llkk.cc | <https://gh.llkk.cc> |
| ghproxy.net | <https://ghproxy.net> |
| moeyy.cn | <https://gh.moeyy.cn> |
| github.akams.cn | <https://github.akams.cn> |
| kkgithub.com | <https://kkgithub.com> |
| bgithub.xyz | <https://bgithub.xyz> |
| dgithub.xyz | <https://dgithub.xyz> |
| githubfast.com | <https://githubfast.com> |
| hub.gitmirror.com | <https://hub.gitmirror.com> |
| hub.nuaa.cf | <https://hub.nuaa.cf> |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--file` | `BENCH_FILE_PATH` from `.env` | File path relative to mirror root |
| `--timeout` | `10000` | Request timeout in milliseconds |
| `--endurance` | `30000` | Maximum download duration per mirror in milliseconds |
| `--mirror NAME=URL` | - | Add extra mirror (repeatable) |
| `--only NAME` | - | Limit to named mirror(s) (repeatable) |
| `--show-speed-mbps / --no-speed-mbps` | `true` | Show or hide throughput columns and MB/s calculation |
