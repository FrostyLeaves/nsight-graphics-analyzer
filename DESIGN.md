# nsight-graphics-analyzer Skill — Design Notes

This document records *why* the skill is shaped the way it is. SKILL.md tells
the agent what to do; DESIGN.md tells the maintainer how to change things
without breaking the contract.

## Goals

1. End-to-end "capture → auto-export → 3 JSON indexes" runs in one command.
2. Every drill-down is **cheap**: small JSON, no recapture, REGIMES streamed
   with column projection.
3. SKILL.md is detailed enough that the agent never needs ngfx documentation
   to pick parameters.
4. Smoke test asserts schema doesn't regress, runs without launching a game.

## Non-goals

Per-API-call timing, HTML/PDF reports, automatic Markdown report templates,
GPUTrace.pyd fallback, cross-platform, GUI launching, auto-installing Nsight,
capture diff, remote rpc, NVTX injection.

## Background — why export-only

NVIDIA Nsight Graphics 2026.1 dropped `GPUTrace.pyd`, the undocumented Python
C extension previous skill versions used to read sample-level metrics and
per-action draw/dispatch records out of `.ngfx-gputrace`. NVIDIA did not
announce this, did not provide a replacement Python or SDK API, and the
official Nsight Graphics SDK is C/C++ injection-only with no offline parser.

The only NVIDIA-supported programmatic path out of a `.ngfx-gputrace` is now
`ngfx.exe --auto-export`, which writes a TSV bundle next to the trace.

Working assumption: pyd is gone for good. NVIDIA's strategic direction is
"export TSV is the official boundary"; a side-by-side 2025.x install would be
a stopgap, and reverse-engineering the proprietary `.ngfx-gputrace` binary
format (magic `WRPV`) is not a path this skill will pursue.

Consequences accepted:

- No per-`vkCmdDraw` / `vkCmdDispatch` timings (the export bundle does not
  carry them).
- No sample-level metric arrays (no `--window NS:NS` queries).
- "Action" is redefined as a *leaf marker* — the deepest node in the
  D3DPERF_EVENTS marker tree. For NVTX-heavy engines this is fine-grained
  (single `ComputeSkinningDispatch` etc.); for unannotated engines it
  degrades to whatever the engine wrapped its work in. The
  `definition` field in `actions.json` documents this.

## Architecture overview

```
                          cli
                           │
        ┌─────┬───────┬────┴────┬────────┬─────────┐
        ▼     ▼       ▼         ▼        ▼         ▼
       env  runner  parse   analyze  queries  artifacts
        │     │       │         │        │         │
        │     │       │     parse,art   parse     _io
        │     └──env──┘
        │
        └────── _io, _version (leaves)
```

- `_io` and `_version` are leaves; everything else may import them.
- `env` (locate / capabilities / process management) imports nothing internal
  except `_io`/`_version`.
- `runner` builds ngfx command lines and runs subprocesses; depends on `env`
  for binary locations and process-tree teardown.
- `parse` reads TSV bundles. Streams REGIMES with column projection.
- `analyze` builds the 3 JSON artifacts; depends on `parse` + `artifacts`.
- `queries` answers drill-down questions on demand; depends on `parse` (and
  reuses `analyze` utility functions like `aggregate_by_name_at_depth`).
- `commands/` are argparse handlers (one per subcommand). They depend on
  whatever subpackage their job needs.
- `cli.py` registers all subparsers and dispatches via lazy import.

This is a strict tree (no cycles). New subcommands add to `cli.py` +
`commands/`; new analysis facets add to `analyze/` + `queries/`. Discovery
or process management changes go in `env/`. ngfx flag-set changes go in
`runner/` (specifically `gpu_trace.py` / `graphics.py` / `cpp.py`) and the
`_WRAPPER_FEATURE_FLAGS` map in `env/caps.py`.

## Why three JSON artifacts (and not two, or one)

The agent's first read is the **smallest** thing that can answer "where do I
drill?". The smallest such thing is `summary.json` — it carries hardware
context, frame-level timing, the full metric catalog, and an `analysis`
block that picks the dominant subsystem and slowest stage. It avoids per-row
data so it stays under ~50 KB.

Beyond summary, agents typically want one of two things:

1. **What stages exist and how big are they?** — that's `stages.json` (top
   depth-1 stages with headline metrics, ~3 KB).
2. **What are the slowest leaf-level actions?** — that's `actions.json`
   (top-20 leaf markers, ~15 KB).

A single big JSON would either bloat (all roll-ups) or push the agent to
parse a hierarchy it doesn't need yet. Two files would force per-stage
metrics into the same blob as the slow-action list. Three files keep the
default reads tight and let the agent pick the second read deliberately.

## Why REGIMES stays out of JSON

`GPUTRACE_REGIMES.xls` is up to 300+ MB on a 40-frame busy capture. We
*never* materialize it. The streaming reader (`parse/regimes.py`) has one
external API — `iter_rows(path, n_frames, wanted_metrics)` — and yields
`(marker_path, {metric_name: [n_frames values]})` tuples one row at a time
with column projection. Memory peaks under 50 MB regardless of file size.

Each drill subcommand makes at most one streaming pass. `gputrace-actions
--with-metrics` and `gputrace-metric --in-marker` both go through this
generator; they don't load the whole file into memory.

## Why v1 schema (fresh start)

The previous in-house skill (`.claude\skills\nsight-capture\`)
landed at `summary.json` schema_version 3 after several internal pivots.
Schema v1 here is intentionally a clean break:

- v1 is the "we know what we want" first version, not the third internal
  attempt.
- The shape diverges in small ways from the legacy skill (e.g. `session`
  block, `generator` field) so callers can detect which generator wrote
  the JSON.
- Future breaks will increment to v2 and include a clear migration note.

`SCHEMA_VERSION` lives in `_version.py`. Changing it is a contract change.

## Subcommand design rationale

### Why drill is split into 3 subcommands, not one

I considered `drill --what {marker,metric,stage,action}` to share argparse
plumbing. Rejected because:

1. **Decision Guide table density.** With one subcommand, every row in the
   table needs `--what X --filter Y --in-marker Z` — agent has to mentally
   intersect flags. Three subcommands keep each row terse.
2. **Mutex matrix gets ugly.** `--filter` is leaf-only; `--parent` is
   stage-only; `--in-marker` is both but means different things; `--depth`
   is stage-only; `--top` is both. Per-subcommand argparse keeps each
   command's mutex obvious.
3. **Future facets stay separate.** Adding `gputrace-events` (frame-level
   event histogram) later doesn't disturb the existing trio.

### Why launch / attach are separate from capture / cpp-capture / gputrace-capture

`launch` and `attach` don't capture anything; they just put ngfx on the
target process. The capture activity is selected by the user via
`--activity`. This matches ngfx's own model.

### Why both `gputrace-capture` and `gputrace`

`gputrace-capture` is destructive (launches the game, waits, writes files).
`gputrace` is pure post-processing: take an existing trace + BASE/, rebuild
the 3 JSON. This split lets the agent reanalyze old captures after a skill
upgrade without re-launching.

### Why the export / replay surface is exposed as separate subcommands

`export-metadata`, `export-functions`, `export-screenshot`, `replay-perf`,
and `replay-analyze` wrap `ngfx-replay.exe` post-capture operations on a
`.ngfx-capture` file. They don't take new captures; they extract metadata
or re-run an existing capture for inspection. They're kept as separate
subcommands (not a single `replay --what X` flag) for the same reason
drill is split: each surface has a different argument shape and a
different output schema. `replay-analyze` is the convenience combinator
that runs several of these in one shot — useful for `--output-dir`-style
batch dumping.

### Why `locate` / `capabilities` / `kill` are top-level subcommands

These are environment-management commands rather than capture / drill
operations:

- `locate` prints the detected Nsight install path. It's the smallest
  possible smoke test ("is Nsight findable?") and is what CI workflows
  call first.
- `capabilities` dumps the per-binary feature flag matrix that
  `caps.require_feature` consults. Surfacing it as a subcommand lets the
  agent (or a curious user) inspect why a given flag is being gated
  without grepping the source.
- `kill` force-terminates residual ngfx processes (entire process tree
  via `taskkill /T /F`). Captures occasionally leak ngfx subprocesses
  when the host crashes or the user `Ctrl-C`s at the wrong moment; this
  is the explicit recovery action.

They're independent of `doctor` (which is a *report*; these are *actions*
or *targeted reports*).

## Error handling matrix

| Failure                                              | Detection                                      | Behavior                                                  |
|------------------------------------------------------|------------------------------------------------|-----------------------------------------------------------|
| Nsight install missing                               | `find_install` finds no `ngfx-capture.exe`     | exit 3 with install instructions                          |
| Conditional ngfx flag absent                         | `caps.require_feature` fails                   | exit 4 with feature key + flag label                      |
| User passes two start triggers                       | argparse mutex group                           | exit 2 (usage)                                            |
| User passes invalid architecture                     | `gpu_trace.GpuTraceConfigError`                | exit 2                                                    |
| ngfx exits non-zero, BASE/ bundle complete           | `_bundle_completeness` reports all TSVs present | exit 0; stderr logs `bundle_complete=True` (ngfx 2026.1.x crashes during cleanup AFTER a valid write — exit code is unreliable, bundle completeness is the source of truth) |
| ngfx exits non-zero, trace written but bundle incomplete | `_bundle_completeness` lists missing TSVs | exit 4; raw trace preserved; re-run `gputrace <trace>` to retry post-process |
| ngfx exits non-zero, no trace file                   | `_find_written_trace` returns None             | exit 4 with rc                                            |
| Wrapper timeout                                      | `subprocess.TimeoutExpired`                    | `taskkill /T /F /PID`, exit 5                             |
| Auto-export bundle missing after success             | `BASE/FRAME.xls` not present                   | log warning, return 0 (raw trace preserved)               |
| `D3DPERF_EVENTS` row sums exceed 1.3 × trace_span    | naive vs paired heuristic                      | switch to paired interpretation; flag `_suspect`          |
| `gputrace-metric` regex matches >1 metric            | `metric_query.query`                           | exit 2 unless `--all-matches`                             |
| `replay-perf` capture file missing                   | path check                                     | exit 2                                                    |
| Anti-cheat injection blocked                         | (currently surfaces as ngfx non-zero rc)       | exit 4; SKILL.md hints at workarounds                     |

## Smoke test strategy

stdlib `unittest` (zero-pip-install). Discovery:

```
python -m unittest discover -s tests
```

Sample data ships under `tests/data/BASE/` — the four small
TSV files (REPRO_INFO ~2 KB, FRAME ~1 KB, GPUTRACE_FRAME ~55 KB,
D3DPERF_EVENTS ~160 KB, ≈ 220 KB total). REGIMES is too big to commit;
tests that need it look at the env var `NSIGHT_SKILL_REGIMES_SAMPLE` and
skip when unset.

Test files:

- `test_tsv.py` — parse_floats edge cases (NaN, Inf, empties, BOM, CRLF)
- `test_d3dperf_events.py` — marker-tree parser, leaf annotation,
  span-clamping
- `test_summary_pipeline.py` — full summary/stages/actions schema on the
  sample
- `test_drill.py` — stages/actions/metric query results
- `test_runner_dryrun.py` — argv mutex enforcement (no real ngfx)
- `test_cli_smoke.py` — `python plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight.py gputrace ...` end to end
- `test_regimes_stream.py` — opt-in: tracemalloc bounds streaming peak
  under 50 MB

The CLI smoke test materializes a `<tmpdir>/fake.ngfx-gputrace` (empty stub
file) plus `<tmpdir>/BASE/<sample files>`, then runs the skill via
`python plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight.py`. This exercises the entry-point bootstrap, the
argparse router, the gputrace handler, and the writer in one shot.

## Data sources (TSV bundle)

| File                  | Used by                                                | Size         | Notes                                                     |
|-----------------------|--------------------------------------------------------|--------------|-----------------------------------------------------------|
| `REPRO_INFO.xls`      | `summary.hardware_context`                             | ~2 KB        | KV map; eagerly parsed                                    |
| `FRAME.xls`           | `summary.frames` + `summary.summary.frame_count`       | <1 KB        | One row, per-frame ms array                               |
| `GPUTRACE_FRAME.xls`  | `summary.metrics` + `gputrace-metric --name`           | ~50 KB       | One row per metric, per-frame averages, no header         |
| `D3DPERF_EVENTS.xls`  | `stages.json` + `actions.json` marker tree, durations  | ~150 KB      | 8-space-indent marker tree, one row per (marker,instance) |
| `GPUTRACE_REGIMES.xls`| Per-stage / per-action / per-marker headline metrics   | **~300 MB**  | Streamed only; column projection by metric name           |

Critical: `GPUTRACE_REGIMES.xls` is never read into memory. Each query
reads the header line, identifies columns for the wanted metrics, streams
rows, and discards everything else.

### D3DPERF_EVENTS row encoding heuristic

NVIDIA's exporter is occasionally inconsistent: most rows store one
duration per column, but a small fraction alternate `(duration_ms,
end_or_start_ms)` pairs. The naive read would over-count those rows.

Heuristic in `parse/d3dperf_events.py`:

```
sum_naive = sum(values)
durations_pair = values[0::2]
sum_pair = sum(durations_pair)
if sum_naive <= 1.3 * trace_span_ms:
    durations = values
elif sum_pair <= 1.3 * trace_span_ms:
    durations = durations_pair
else:
    pick smaller, drop > 0.5 * trace_span outliers, mark _suspect
```

Suspect rows propagate to the row's `_suspect_duration` flag and contribute
to the suspect count surfaced as a warning in `summary.analysis.warnings`.

## Future work

- **Capture diff.** Compare two `.ngfx-gputrace` sessions; surface
  per-stage / per-action / per-metric deltas. Currently out of scope.
- **HTML/PDF reports.** The agent writes Markdown; a `report` subcommand
  would constrain the format. Decided against in v1.
- **SDK integration.** `--start-with-ngfx-sdk` exists in the wrapper but
  hasn't been validated against an actual NGFX_GPUTrace SDK call site.
- **Remote rpc.** ngfx-rpc.exe handling (capture from machine A while game
  runs on machine B) is not wrapped.
- **2025.x fallback parser.** If a user has only Nsight 2025.x installed,
  the wrapper exits 3. We could in principle support side-by-side 2025.x
  for users who haven't upgraded — but the schema would diverge and the
  burden isn't justified yet.
- **Schema v2.** Anticipate breaking changes when ngfx 2026.2+ adds new
  metric families. Bump `SCHEMA_VERSION` and document migration.

## Module-by-module breakdown

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight.py` — entry thunk. Adjusts `sys.path` so the package is
importable without `pip install`, then dispatches to `nsight.cli.main()`.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/_version.py` — single source of truth for `__version__`,
`SCHEMA_VERSION`, `NGFX_TARGET`, `GENERATOR`. Don't sprinkle constants.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/_io.py` — argparse helpers (`int_range` factory plus the
pre-bound `positive_int` / `nonnegative_int` validators, `env_kv`),
`safe_compile` / `user_pattern_or_exit()` for regex-flag validation,
`emit()` for JSON output, and exit-code constants (`EXIT_OK` = 0,
`EXIT_USAGE` = 2, `EXIT_ENV` = 3, `EXIT_TOOL` = 4, `EXIT_TIMEOUT` = 5).
No subpackage imports — must stay at the bottom of the dependency tree.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/cli.py` — argparse router. One `_add_*` helper per
subcommand keeps the file scannable. Handlers are imported lazily via
`importlib` so `--help` doesn't pay for runner/parse/analyze.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/env/locate.py` — Nsight install discovery (env override +
filesystem glob across all fixed drives + Windows uninstall registry,
version-sorted). `find_install(strict=False)` lets `doctor` report a
missing install without aborting.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/env/caps.py` — capabilities probe + on-disk cache. Cache
key: (host_dir, per-binary mtime_ns, max-installed-version). Any change
invalidates the cache, so installing a newer Nsight side-by-side or
upgrading in place is detected automatically.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/env/procs.py` — `IsUserAnAdmin`, `taskkill /T /F /PID`,
residual-ngfx detection via `tasklist`.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/runner/invoke.py` — subprocess wrapper. `run()` for
long-lived captures: **inherits** the wrapper's stdout/stderr so ngfx
writes directly to whatever stdio the wrapper has, with no pipe between
us. A PIPE+drain pattern was tried earlier and caused ngfx 2026.1.x to
crash mid-trace; do not reintroduce it. On timeout, the entire process
tree is force-killed via `taskkill /T /F /PID` (Windows-only). `run()`
also accepts `extra_env` — `gputrace-capture` passes
`NSIGHT_SUGGEST_GRAPHICS_CAPTURE=0` to avoid an ngfx cleanup-phase SEH
crash. `run_capture()` is for short-lived helpers (ngfx-replay metadata
dumps) that produce JSON on stdout. Shutdown-crash salvage is **not** a
function in `invoke.py`; it's implemented inline in
`commands/gputrace_capture.py:run()` and keys on BASE/ bundle
completeness, not on the trace file's existence or ngfx's exit code.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/runner/{gpu_trace,graphics,cpp,attach,replay}.py` — pure
argv builders, one per ngfx activity / replay surface. Each file declares
its own `ConfigError` subclass for mutex violations.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/runner/common.py` — shared argv helpers used by every
builder above: `format_env` (joins `KEY=VALUE` pairs into ngfx's single
`--env "K=V; K2=V2;"` string), `format_args` (quotes program argv via
`subprocess.list2cmdline`), `append_optional` / `append_flag`
(conditional argv emission), `extend_envs` / `extend_program_args`,
`join_iter`. Lives next to the builders rather than in `_io` because
it's ngfx-shaped, not generic argparse plumbing.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/parse/{tsv,repro_info,frame,gputrace_frame,d3dperf_events,regimes}.py`
— one file per `.xls` family. `regimes.py` is the perf-critical one:
header parse + `iter_rows` generator with column projection.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/analyze/{headlines,summary,stages,actions}.py` — the JSON
builders. `headlines.py` owns the metric-substring → key map; the other
three each build one of the artifacts.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/queries/{stages,actions,metric}.py` — drill-down query
implementations. Mirror the structure of `analyze/` but accept regex
filters and sort options.

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/artifacts/{layout,writer}.py` — session directory naming
(`<parent>/<YYYY-MM-DD-HH-MM-SS-mmm>/<file>`), atomic JSON writes (tmp +
`os.replace`).

`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/commands/<subcmd>.py` — one file per subcommand. Each
exports a `run(args: argparse.Namespace) -> int`. The handler is the only
file that ties argparse output to the underlying library functions.

`tests/` — see [Smoke test strategy](#smoke-test-strategy).

## Investigations

Field-notes appendix: 踩坑 records, ngfx-specific behaviors, and wrapper
internals that don't belong in SKILL.md (agent-facing) but matter for
maintainers. Each entry was a multi-hour debug in original discovery;
do not delete without verifying current ngfx behavior.

### `--multi-pass-metrics` + `--auto-export` produces unloadable trace

Verified May 2026 against Nsight Graphics **2025.3.0** and **2026.1.0**,
RTX 4070 Ti / Ada, TestApp.exe.

The combination `--multi-pass-metrics --auto-export` deterministically
produces a `.ngfx-gputrace` that no loader can open. This wrapper
*always* sets `--auto-export` (it's the only NVIDIA-supported path to
TSV output), so passing `--multi-pass-metrics` through this wrapper is
broken by construction.

**Measured failure pattern (3/3 reproducibility):**

- **2026.1**: ngfx hard-crashes at `Loading progress (60)` during the
  "Opening generated GPU Trace report" step with
  `STATUS_STACK_BUFFER_OVERRUN (0xC0000409)` or
  `STATUS_HEAP_CORRUPTION (0xC0000374)`. BASE/ is never created.
- **2025.3**: ngfx makes it to `Loading progress (90)` but catches an
  SEH exception, logs `Failed to load GPU Trace report ..., error: An
  SEH exception was thrown while loading the report.` and exits cleanly
  with rc=1. Same outcome — no BASE/.
- `ngfx-ui.exe` GUI also cannot open these traces; this proves the bug
  is in ngfx's *writer*, not in the auto-export reader.

**Measured success pattern (4/4 reproducibility)** — same parameters,
ONLY `--multi-pass-metrics` removed: complete BASE/, all 5 TSVs, full
JSON drill-down output. ngfx still hits the cleanup-phase crash but
data is intact (see next entry).

**Cost of removing `--multi-pass-metrics`**: lose the extra hardware
counter detail that multi-pass replay adds (some SM/L1TEX sub-items).
Per-stage timing, per-action timing, throughput rankings, NVTX marker
tree, frame budget, and the 5 headline metrics are all preserved. This
loss is acceptable for nearly all perf-analysis workflows.

The wrapper still accepts `--multi-pass-metrics` for forensic /
bug-report purposes but prints a `WARNING:` line and returns
`bundle_complete=False`. Code comment + reasoning are archived in
`plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/commands/gputrace_capture.py` near
`_warn_multi_pass_incompatible`.

### ngfx 2026.1.x cleanup-phase crash

On some environments ngfx.exe exits with `STATUS_STACK_BUFFER_OVERRUN`
(0xC0000409) or `STATUS_HEAP_CORRUPTION` (0xC0000374) **after** writing
the trace, during the post-trace cleanup/validation phase (DLL involved
is `WarpVizPlugin.dll`). NVIDIA has not publicly acknowledged this bug.

**Mitigation**: the wrapper sets `NSIGHT_SUGGEST_GRAPHICS_CAPTURE=0` for
the ngfx child process — this flips ngfx into the code path that
exports the TSV bundle BEFORE the cleanup phase, so even when ngfx
still crashes, the BASE/ artifacts have already landed.

**Business-result judgment is based on BASE/ completeness, NOT ngfx
rc**: with a complete bundle the data is intact and analyzable; the
wrapper returns exit 0 + a clear WARNING line that prints the actual
ngfx rc. `bundle_complete=True` → trust the JSON artifacts.
`bundle_complete=False` is a real failure (the export step itself was
aborted) — re-capture.

### Wrapper auto-cleanup of launched game

After every capture command (`gputrace-capture` / `capture` /
`cpp-capture`), the wrapper enumerates processes whose Image Name
matches `Path(--exe).name` and StartTime ≥ the wrapper-start time,
and force-kills them via `taskkill /T /F` to prevent residuals from
holding GPU performance counters open.

This matches by `(exe basename, start time)` — independent runs of the
same game on the same machine are NOT touched. `launch` and `attach`
do not perform cleanup (their purpose is to leave the process running).

### Process tree on timeout / Ctrl-C

Wrapper-side `--timeout` (when set) uses `taskkill /T /F /PID` to kill
the entire ngfx process tree. If the user Ctrl-C's the wrapper, the
target game may still be running — `kill --all` cleans up residuals.

### Trigger flags are mutually exclusive

`gputrace-capture` requires exactly one `--start-after-*`. Argparse
rejects multi-trigger calls before reaching ngfx; no need to handle
this beyond the argparse mutex group declaration in `cli.py`.

### `--metric-set-name` is GPU-architecture-specific

Names that work on Ada ("Throughput Metrics", "Async Compute Triage",
"Top-Level Triage") don't all exist on Blackwell GB20x ("Top-Level
Triage" is the only one shared). When in doubt run `capabilities` —
the per-arch JSON config under `plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/scripts/nsight/env/caps.py` has the
authoritative list.

### `--hes-enabled 1` on non-GB20x is silently ignored

Hardware Event System is only effective on GB20x+ (`Blackwell GB20x` /
`T25x GB20x` / `Thor GB10B`). On Ada/Ampere ngfx prints `HES is not
supported on architecture 'X'.` and silently ignores the flag.

The wrapper detects this combination at argv-build time and emits a
`[nsight] WARNING` before launch so you don't waste a capture wondering
why HES rows are empty.

### Long captures and `--timeout` default

With `--multi-pass-metrics`, the trace window is the short part —
multi-pass replay after capture takes minutes. The wrapper-side
`--timeout` is **unset by default** (no hard cap) so a 5-minute game
load + multi-pass replay won't be cut off prematurely. Only set
`--timeout SEC` when you specifically need a hard ceiling (e.g. CI).
Ctrl-C still works to abort.

### stderr progress markers

When monitoring a running capture, grep stderr for:

- `Connection Established` — game attached
- `STARTING CAPTURE`
- `Capturing N Frame`
- `ENDING CAPTURE`
- `Bundling the replayer` — multi-pass replay phase
- `Saved to <path>`
- `[nsight] captured <path>` — wrapper-side success line
