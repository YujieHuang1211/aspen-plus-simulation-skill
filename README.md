# aspen-plus-simulation

Claude Code 技能：用 Aspen Plus 建立、运行、诊断化工流程模拟，为非标设备方案和报价提供物料/能量衡算、换热负荷和选型依据；需要时配合 Cantera、NASA CEA、Fluent、HTRI 和 Python 手算做独立复核。由 P47 等离子体 CO₂ 还原项目（Aspen Plus V11）的经验整理而成。

入口是 `SKILL.md`。工作流、驱动方式、"什么时候叫搭档"的判据和常见错误都在里面。

要点：本机 Aspen 用进程内 COM（`Apwn.Document.IP`）可以完全由脚本驱动；进程外 COM 会卡死，命令行引擎没有许可证。手写的 `.inp` 不能直接经 COM 打开，要先在 GUI 里打开一次存成 `.bkp`（或用 COM 从空白文档搭），之后改参数、扫工况、导出全部走脚本。换版本或换机器先跑探测脚本，不要照搬这里的结论。

## 结构

| 路径 | 说明 |
|---|---|
| `SKILL.md` | 工作流、入口实测结果、搭档工具分工、交付物、常见错误 |
| `references/com-automation.md` | COM 标准流程、坑表、运行状态码、导出代码、常用节点路径、工况扫描 |
| `references/model-building.md` | 手写 `.inp` 骨架、物性方法与反应器选型、收敛排错、已知良性警告、跑完五项自查 |
| `references/cross-validation.md` | 与 Cantera / CEA / Fluent / HTRI / Python 的分工、各工具的坑、P47 实例、复核记录格式 |
| `references/report-extraction.md` | `.rep` / `.sum` / `.his` 格式、各类块的结果项名、解析脚本用法 |
| `scripts/probe_aspen_com.py` | 探测 COM 入口（进程内优先、每个带超时），给出诊断和下一步 |
| `scripts/aspen_com.py` | COM 驱动：打开/新建、改值、运行、导出、读 `.his` 警告、浏览节点、RStoic 反应式、扫描 |
| `scripts/parse_rep_template.py` | 解析 `.rep`，输出块结果和物流表 CSV |
| `scripts/aspen_lock.py` | 单许可证排队锁，多个代理或脚本同时要用 Aspen 时使用 |
| `scripts/codex_brief_template.md` | 需要 GUI 时交给 Codex computer use 的任务书模板和调用前检查 |
| `evals/evals.json` | 评测题和检查项 |

## 安装

```
git clone https://github.com/YujieHuang1211/aspen-plus-simulation-skill.git %USERPROFILE%\.claude\skills\aspen-plus-simulation
```

只装在 Claude Code 侧。Codex 侧已有通用的 `aspen-simulation-designer` 技能，本仓库没有镜像过去，只在它的 `references/aspen-plus.md` 末尾追加了本机专属说明，所以这里没有 `agents/openai.yaml`。

## 运行环境

- Aspen Plus V11（37.0），Sentinel RMS 本机许可证，各功能并发 1
- Python 3，需 pywin32；交叉验证另需 Cantera 3.x 和 NASA CEA Python 包（`cea`）
- 控制台为 GBK，打印中文的脚本前设 `PYTHONIOENCODING=utf-8`
- 仿真工作目录用纯 ASCII 路径（Aspen、Fluent 对中文路径不友好）

## 评测

2026-10-10 第一轮：3 道题（转化率扫描、`.rep` 转 Excel、新建等离子体裂解模型），每题有技能、无技能各跑一次。结果是有技能 24/24、无技能 20/24。差距全在"能否真正跑起 Aspen"：对照组只试了进程外 COM 和命令行引擎，失败后改用手算；两组的工程判断相当。`.rep` 转 Excel 一题两组都满分，下一轮应换成更难的题。工作区（含逐条评分和对比页 `review.html`）在 `~/.claude/skills/aspen-plus-simulation-workspace/`，不放入仓库。

再跑评测时，多个子代理会同时用 Aspen，任务提示里要求它们用 `scripts/aspen_lock.py` 排队。
