# nsight-graphics-analyzer

[English](./README.md) | **简体中文**

Nsight Graphics Analyzer 是一个 Windows 专用的 **NVIDIA Nsight Graphics
2026.1+** 封装工具。它既可以作为 Claude Code / Codex 的 skill 使用，也可以
直接在命令行运行，用来抓取 GPU Trace、导出 Nsight 数据，并把几百 MB 的原始
TSV 转成适合阅读和下钻的小 JSON。

代码只依赖 Python 标准库，不需要 `pip install`。

[![ci](https://github.com/FrostyLeaves/nsight-graphics-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/FrostyLeaves/nsight-graphics-analyzer/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey)

## 环境要求

| 要求 | 说明 |
|---|---|
| Windows 10/11 | 必需。封装脚本依赖 Windows 进程和路径 API。 |
| NVIDIA Nsight Graphics 2026.1+ | 需要从 [NVIDIA Developer](https://developer.nvidia.com/nsight-graphics) 单独安装。 |
| Python 3.10+ | 只使用标准库。 |
| NVIDIA GPU 和匹配驱动 | Nsight 抓取和回放流程需要。 |

先运行环境检查：

```powershell
python plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer\scripts\nsight.py doctor
```

如果输出里的 `ngfx_install` 是 `null`，先安装 Nsight Graphics。

## 快速开始

抓取一段短 GPU Trace，并生成三个小 JSON：

```powershell
python plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer\scripts\nsight.py gputrace-capture `
  --exe "C:\Path\To\YourApp.exe" --wd "C:\Path\To" `
  --start-after-ms 5000 --max-duration-ms 1000 `
  --architecture Ada --metric-set-name "Throughput Metrics" `
  --time-every-action `
  --out "C:\Path\To\Captures\sample.ngfx-gputrace"
```

封装脚本会在 trace 旁边写出：

| 文件 | 用途 |
|---|---|
| `*.gputrace.summary.json` | 帧预算、硬件信息、主要瓶颈子系统、指标目录、警告。 |
| `*.gputrace.stages.json` | 顶层 NVTX / D3DPERF 阶段和关键指标。 |
| `*.gputrace.actions.json` | 最慢的叶子 marker。 |

先看 `summary.json`，再下钻最慢阶段：

```powershell
python plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer\scripts\nsight.py gputrace-stages `
  "C:\Path\To\Captures\<session>\sample.ngfx-gputrace" `
  --parent "<stage-name-regex>" --top 10
```

导出的 `GPUTRACE_REGIMES.xls` 可能超过 300 MB。不要把它直接交给智能体读；
需要下钻时用本项目的 drill 命令。

## 安装

真正可安装的 plugin package 位于：

```text
plugins/nsight-graphics-analyzer/
```

内置 skill 位于 `plugins/nsight-graphics-analyzer/skills/`。
仓库根目录只放项目文档、测试、CI 和 marketplace manifest。

### Codex

建议走 Codex plugin marketplace 流程安装。仓库包含
`plugins/nsight-graphics-analyzer/.codex-plugin/plugin.json` 和
`.agents/plugins/marketplace.json`，Codex 可以直接从 GitHub 发现并安装这个
skill：

```powershell
codex plugin marketplace add FrostyLeaves/nsight-graphics-analyzer
codex
```

进入 Codex 后打开 `/plugins`，选择 `nsight-graphics-analyzer` marketplace，
安装 **Nsight Graphics Analyzer**。如果当前 Codex 版本不会立刻加载新装 plugin，
重启当前会话。

本地开发时，可以把 checkout 作为本地 marketplace 加进去：

```powershell
git clone https://github.com/FrostyLeaves/nsight-graphics-analyzer
codex plugin marketplace add .\nsight-graphics-analyzer
codex
```

然后在 `/plugins` 里安装这个 plugin。

如果只需要 raw skill 兼容安装，可以复制到全局 Codex skills 目录：

```powershell
git clone https://github.com/FrostyLeaves/nsight-graphics-analyzer
New-Item -ItemType Directory -Force -Path $HOME\.codex\skills | Out-Null
Copy-Item -Recurse -Force `
  .\nsight-graphics-analyzer\plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer `
  $HOME\.codex\skills\
```

只有在希望 Codex 直接读取当前工作区最新代码时，才改用软链接：

```powershell
New-Item -ItemType SymbolicLink `
  -Path $HOME\.codex\skills\nsight-graphics-analyzer `
  -Target .\nsight-graphics-analyzer\plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer
```

### Claude Code

仓库已包含 `.claude-plugin/marketplace.json`，Claude Code 可以把
`plugins/nsight-graphics-analyzer/` 作为单 plugin package 直接安装。在 Claude
Code 提示行依次执行：

```text
/plugin marketplace add FrostyLeaves/nsight-graphics-analyzer
/plugin install nsight-graphics-analyzer@nsight-graphics-analyzer
/reload-plugins
```

`/reload-plugins` 让当前会话识别新装的 plugin，无需重启 Claude Code。装好后，
对话中出现 Nsight、GPU trace、帧抓取等 `SKILL.md` 里登记的触发词时，
Claude Code 会自动加载这个 skill；也可以用
`/nsight-graphics-analyzer:nsight-graphics-analyzer` 显式调用。

本地开发时，可以把 marketplace 指向本地 clone，而不是 GitHub：

```text
/plugin marketplace add .\nsight-graphics-analyzer
/plugin install nsight-graphics-analyzer@nsight-graphics-analyzer
/reload-plugins
```

卸载用 `/plugin uninstall nsight-graphics-analyzer@nsight-graphics-analyzer`。

### 只用命令行

不安装 skill 也可以直接使用 CLI：

```powershell
git clone https://github.com/FrostyLeaves/nsight-graphics-analyzer
cd nsight-graphics-analyzer
python plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer\scripts\nsight.py --help
```

## 常见任务

| 目标 | 命令 |
|---|---|
| 检查本机 Nsight 环境 | `doctor` |
| 抓取 GPU 计时和硬件指标 | `gputrace-capture` |
| 从已有 `.ngfx-gputrace` 重新生成 JSON | `gputrace` |
| 查看顶层阶段 | `gputrace-stages` |
| 查看最慢叶子 marker | `gputrace-actions` |
| 聚合某个硬件指标 | `gputrace-metric` |
| 诊断 overdraw | `gputrace-overdraw` |
| 诊断显存/带宽压力 | `gputrace-bandwidth` |
| 诊断 shader / SM 瓶颈 | `gputrace-shader-bound` |
| 诊断几何压力 | `gputrace-geometry` |
| 诊断 GPU 空闲和 marker 覆盖率 | `gputrace-stalls` |
| 诊断纹理缓存 | `gputrace-texture-cache` |
| 诊断小 marker 过多或状态切换开销 | `gputrace-draws` |
| 导出 `.ngfx-capture` 元数据、API 流或截图 | `export-metadata`, `export-functions`, `export-screenshot` |
| 回放 capture 并解析耗时 | `replay-perf`, `replay-analyze` |

查看某个命令的完整参数：

```powershell
python plugins\nsight-graphics-analyzer\skills\nsight-graphics-analyzer\scripts\nsight.py <command> --help
```

## 工作方式

Nsight Graphics 2026.1 不再提供旧工具依赖的未公开 `GPUTrace.pyd` 扩展，因此
无法直接用 Python 读取 `.ngfx-gputrace`。目前可用的程序化出口是
`ngfx.exe --auto-export`，它会把 TSV bundle 导出到 trace 旁边。

本项目围绕这个边界设计：

1. 抓取或复用 trace。
2. 自动导出 TSV bundle。
3. 直接解析较小 TSV。
4. 只通过聚焦查询流式读取大型 REGIMES 文件。
5. 写出适合智能体或用户阅读的小 JSON。

面向智能体的使用契约见
[SKILL.md](plugins/nsight-graphics-analyzer/skills/nsight-graphics-analyzer/SKILL.md)，架构细节和排查记录见
[DESIGN.md](DESIGN.md)。

## 开发

运行测试：

```powershell
python -m unittest discover -s tests -v
```

REGIMES 流式测试会读取 `$env:NSIGHT_SKILL_REGIMES_SAMPLE`；未设置时自动跳过，
因为真实 REGIMES 文件太大，不适合提交进仓库。

项目结构：

```text
.agents/plugins/marketplace.json
                         Codex plugin marketplace 元数据
.claude-plugin/marketplace.json
                         Claude Code marketplace 元数据
plugins/
  nsight-graphics-analyzer/
    .codex-plugin/        Codex plugin manifest
    .claude-plugin/       Claude Code plugin manifest
    skills/
      nsight-graphics-analyzer/
        SKILL.md          面向智能体的使用契约
        agents/openai.yaml
        scripts/
          nsight.py       CLI 入口
          nsight/         Python 包
DESIGN.md                 维护者说明
README.md                 项目文档
tests/                    单元测试和小型 TSV fixture
```

提交 PR 前：

1. 在 Windows 上运行 `python -m unittest discover -s tests -v`。
2. 保持三个 JSON schema 稳定；破坏性变更需要提升 `SCHEMA_VERSION`。
3. 新增子命令或分析维度前先读 [DESIGN.md](DESIGN.md)。
4. 不引入第三方 Python 依赖。

## 许可证

[MIT](LICENSE)

## 致谢

- NVIDIA Nsight Graphics 提供 auto-export TSV bundle。
- Claude Code 和 Codex 社区沉淀的 skill 约定。
