# nsight-graphics-analyzer

**English** | [简体中文](./README.zh-CN.md)

Nsight Graphics Analyzer is a Windows-only skill and CLI wrapper for **NVIDIA
Nsight Graphics 2026.1+**. It helps Claude Code, Codex, or a human at the
terminal capture GPU frames, export Nsight GPU Trace data, and inspect the
result through small JSON files instead of multi-hundred-MB TSV artifacts.

The Python code uses only the standard library. No `pip install` is required.

[![ci](https://github.com/FrostyLeaves/nsight-graphics-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/FrostyLeaves/nsight-graphics-analyzer/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey)

## Requirements

| Requirement | Notes |
|---|---|
| Windows 10/11 | Required. The wrapper uses Windows process and path APIs. |
| NVIDIA Nsight Graphics 2026.1+ | Install separately from [NVIDIA Developer](https://developer.nvidia.com/nsight-graphics). |
| Python 3.10+ | Standard library only. |
| NVIDIA GPU and supported driver | Required for Nsight capture and replay workflows. |

Run the environment check first:

```powershell
python plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer\scripts\nsight.py doctor
```

If `ngfx_install` is `null`, install Nsight Graphics before trying to capture.

## Quick Start

Capture a short GPU Trace and generate the three compact JSON artifacts:

```powershell
python plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer\scripts\nsight.py gputrace-capture `
  --exe "C:\Path\To\YourApp.exe" --wd "C:\Path\To" `
  --start-after-ms 5000 --max-duration-ms 1000 `
  --architecture Ada --metric-set-name "Throughput Metrics" `
  --time-every-action `
  --out "C:\Path\To\Captures\sample.ngfx-gputrace"
```

The wrapper writes these files next to the trace:

| Artifact | Purpose |
|---|---|
| `*.gputrace.summary.json` | Frame budget, hardware context, dominant subsystem, metric catalog, warnings. |
| `*.gputrace.stages.json` | Top-level NVTX / D3DPERF stages with headline metrics. |
| `*.gputrace.actions.json` | Slowest leaf markers. |

Start with `summary.json`, then drill into the slowest stage:

```powershell
python plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer\scripts\nsight.py gputrace-stages `
  "C:\Path\To\Captures\<session>\sample.ngfx-gputrace" `
  --parent "<stage-name-regex>" --top 10
```

The raw exported `GPUTRACE_REGIMES.xls` can be 300+ MB. Do not open it in an
agent context. Use the drill commands instead.

## Installation

The installable plugin package lives at:

```text
plugins/nsight-graphics-analyzer/
```

The bundled skill is under `plugins/nsight-graphics-analyzer/skills/`.
The repository root holds project docs, tests, CI, and marketplace manifests.

### Codex

Use the Codex plugin marketplace flow. This repository contains the Codex
plugin manifest at `plugins/nsight-graphics-analyzer/.codex-plugin/plugin.json`
and the marketplace metadata at `.agents/plugins/marketplace.json`, so Codex can
discover the skill directly from GitHub:

```powershell
codex plugin marketplace add FrostyLeaves/nsight-graphics-analyzer
codex
```

Inside Codex, open `/plugins`, choose the `nsight-graphics-analyzer`
marketplace, and install **Nsight Graphics Analyzer**. Restart the session if
your Codex build does not load newly installed plugins immediately.

For local development against a clone, add the checkout as a local marketplace:

```powershell
git clone https://github.com/FrostyLeaves/nsight-graphics-analyzer
codex plugin marketplace add .\nsight-graphics-analyzer
codex
```

Then install the plugin from `/plugins`.

If you only need the raw skill fallback, copy it into the global Codex skills
directory:

```powershell
git clone https://github.com/FrostyLeaves/nsight-graphics-analyzer
New-Item -ItemType Directory -Force -Path $HOME\.codex\skills | Out-Null
Copy-Item -Recurse -Force `
  .\nsight-graphics-analyzer\plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer `
  $HOME\.codex\skills\
```

Use a symlink instead of copying only when you want Codex to read your live
working tree:

```powershell
New-Item -ItemType SymbolicLink `
  -Path $HOME\.codex\skills\nsight-graphics-analyzer `
  -Target .\nsight-graphics-analyzer\plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer
```

### Claude Code

This repository ships `.claude-plugin/marketplace.json`, so Claude Code can
install the package under `plugins/nsight-graphics-analyzer/` as a single-plugin
marketplace. From the Claude Code prompt:

```text
/plugin marketplace add FrostyLeaves/nsight-graphics-analyzer
/plugin install nsight-graphics-analyzer@nsight-graphics-analyzer
/reload-plugins
```

`/reload-plugins` lets the current session pick up the new plugin without a
restart. Once loaded, Claude Code activates the skill automatically when the
conversation mentions Nsight, GPU trace, frame capture, or other trigger
phrases declared in `SKILL.md`. You can also invoke it explicitly with
`/nsight-graphics-analyzer:nsight-graphics-analyzer`.

For local development against a clone, point the marketplace at the working
copy instead of GitHub:

```text
/plugin marketplace add .\nsight-graphics-analyzer
/plugin install nsight-graphics-analyzer@nsight-graphics-analyzer
/reload-plugins
```

Uninstall with `/plugin uninstall nsight-graphics-analyzer@nsight-graphics-analyzer`.

### CLI-only

You can use the wrapper directly without installing it as a skill:

```powershell
git clone https://github.com/FrostyLeaves/nsight-graphics-analyzer
cd nsight-graphics-analyzer
python plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer\scripts\nsight.py --help
```

## Common Tasks

| Goal | Command |
|---|---|
| Check local Nsight setup | `doctor` |
| Capture GPU timing and counters | `gputrace-capture` |
| Rebuild JSON from an existing `.ngfx-gputrace` | `gputrace` |
| Inspect top-level stages | `gputrace-stages` |
| Inspect slow leaf markers | `gputrace-actions` |
| Aggregate one hardware metric | `gputrace-metric` |
| Diagnose overdraw | `gputrace-overdraw` |
| Diagnose memory pressure | `gputrace-bandwidth` |
| Diagnose shader / SM bottlenecks | `gputrace-shader-bound` |
| Diagnose geometry pressure | `gputrace-geometry` |
| Diagnose GPU idle and marker coverage | `gputrace-stalls` |
| Diagnose texture cache behavior | `gputrace-texture-cache` |
| Diagnose many small markers / state churn | `gputrace-draws` |
| Export `.ngfx-capture` metadata, API stream, or screenshot | `export-metadata`, `export-functions`, `export-screenshot` |
| Replay a capture and parse timing | `replay-perf`, `replay-analyze` |

Run full help for any command:

```powershell
python plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer\scripts\nsight.py <command> --help
```

## How It Works

Nsight Graphics 2026.1 no longer ships the undocumented `GPUTrace.pyd`
extension that older automation used to read `.ngfx-gputrace` files directly.
The supported programmatic path is `ngfx.exe --auto-export`, which writes a TSV
bundle next to the trace.

This project builds around that boundary:

1. Capture or reuse a trace.
2. Auto-export the TSV bundle.
3. Parse the small TSV files eagerly.
4. Stream the large REGIMES file only through focused queries.
5. Write compact JSON for the agent or user to inspect.

See [SKILL.md](plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/SKILL.md) for the agent-facing
workflow and [DESIGN.md](DESIGN.md) for architecture details and investigation
notes.

## Development

Run the test suite:

```powershell
python -m unittest discover -s tests -v
```

The REGIMES streaming test reads `$env:NSIGHT_SKILL_REGIMES_SAMPLE` and skips
when unset because real REGIMES files are too large to commit.

Project layout:

```text
.agents/plugins/marketplace.json
                         Codex plugin marketplace metadata
.claude-plugin/marketplace.json
                         Claude Code marketplace metadata
plugins/
  nsight-graphics-analyzer/
    .codex-plugin/        Codex plugin manifest
    .claude-plugin/       Claude Code plugin manifest
    skills/
      nsight-graphics-analyzer/
        SKILL.md          Agent-facing contract
        agents/openai.yaml
        scripts/
          nsight.py       CLI entry point
          nsight/         Python package
DESIGN.md                 Maintainer notes
README.md                 Project documentation
tests/                    Unit tests and small TSV fixtures
```

Before opening a PR:

1. Run `python -m unittest discover -s tests -v` on Windows.
2. Keep the three JSON schemas stable; bump `SCHEMA_VERSION` for breaking changes.
3. Read [DESIGN.md](DESIGN.md) before adding a subcommand or analysis facet.
4. Do not add third-party Python dependencies.

## License

[MIT](LICENSE)

## Acknowledgments

- NVIDIA Nsight Graphics for the auto-export TSV bundle.
- The Claude Code and Codex communities for the skill conventions.
