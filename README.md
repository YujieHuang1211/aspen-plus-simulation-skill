# aspen-plus-simulation

Claude Code 技能：用 Aspen Plus 建立、运行、诊断化工流程模拟，为非标设备方案和报价提供物料/能量衡算、换热负荷、压缩功和选型依据。覆盖天然气重整与变换、甲醇水蒸气重整、甲醇合成、费托合成、PSA、精馏、加氢、等离子体/高温裂解等工艺，也给出没做过的工艺怎么上手的通用步骤；需要时配合 Cantera、NASA CEA、Fluent、HTRI 和 Python 手算做独立复核。

入口是 `SKILL.md`。工作流、驱动方式、"什么时候叫搭档"的判据和常见错误都在里面；各工艺的建模配方在 `references/process-recipes.md`。

要点：

- 本机 Aspen 用进程内 COM（`Apwn.Document.IP`）可以完全由脚本驱动；进程外 COM 会卡死，命令行引擎没有许可证。手写的 `.inp` 要先在 GUI 里打开一次存成 `.bkp`（或用 COM 从空白文档搭），之后改参数、扫工况、导出全部走脚本。
- 低温催化工艺用平衡块时，只要允许生成甲烷，结果就全部变成甲烷（实测甲醇合成 0 甲醇、46% 甲烷），模型照样收敛。配方里写了怎么避开，以及怎么用 Cantera 先算锚点。
- 每条信息都标明是本机实测、典型值还是未实测；实测的部分由 `scripts/selftest.py` 固化，换版本或换机器先跑一遍。

## 结构

| 路径 | 说明 |
|---|---|
| `SKILL.md` | 工作流、入口实测结果、搭档工具分工、交付物、常见错误 |
| `references/process-recipes.md` | 新工艺上手七步、甲烷化陷阱、重整与变换 / MSR / 甲醇合成 / FT / PSA / 精馏 / 加氢 / 压缩换热配方、验证状态汇总 |
| `references/com-automation.md` | COM 标准流程、坑表、运行状态码、导出代码、常用节点路径、工况扫描 |
| `references/model-building.md` | 手写 `.inp` 骨架、物性方法与反应器选型、收敛排错、已知良性警告、跑完五项自查 |
| `references/cross-validation.md` | 与 Cantera / CEA / Fluent / HTRI / Python 的分工、各工具的坑、P47 实例、复核记录格式 |
| `references/report-extraction.md` | `.rep` / `.sum` / `.his` 格式、各类块的结果项名、解析脚本用法 |
| `scripts/probe_aspen_com.py` | 探测 COM 入口（进程内优先、每个带超时），给出诊断和下一步 |
| `scripts/aspen_com.py` | COM 驱动：打开/新建、改值、运行并判断可信度、导出、读 `.his` 警告、浏览节点、读选项、加组分和块、RStoic/REquil 反应、扫描 |
| `scripts/equilibrium_check.py` | Cantera 理想气体平衡锚点：限定物种、标出惰性组分、温度扫描 |
| `scripts/selftest.py` | 回归测试：从空白文档搭 9 个小模型，和技能里记录的实测值比对，输出 PASS / FAIL |
| `scripts/parse_rep_template.py` | 解析 `.rep`，输出块结果和物流表 CSV |
| `scripts/aspen_lock.py` | 单许可证排队锁，多个代理或脚本同时要用 Aspen 时使用 |
| `scripts/codex_brief_template.md` | 需要 GUI 时交给 Codex computer use 的任务书模板和调用前检查 |
| `evals/evals.json` | 评测题和检查项 |

## 安装

```
git clone https://github.com/YujieHuang1211/aspen-plus-simulation-skill.git %USERPROFILE%\.claude\skills\aspen-plus-simulation
```

只装在 Claude Code 侧。Codex 侧已有通用的 `aspen-simulation-designer` 技能，本仓库没有镜像过去，只在它的 `references/aspen-plus.md` 末尾追加了本机专属说明，所以这里没有 `agents/openai.yaml`。

装好后先跑一遍：

```
set PYTHONIOENCODING=utf-8
python scripts\probe_aspen_com.py
python scripts\selftest.py
```

## 运行环境

- Aspen Plus V11（37.0），Sentinel RMS 本机许可证，各功能并发 1
- Python 3，需 pywin32；平衡锚点和交叉验证另需 Cantera 3.x、NASA CEA Python 包（`cea`）
- 控制台为 GBK，打印中文的脚本前设 `PYTHONIOENCODING=utf-8`
- 仿真工作目录用纯 ASCII 路径（Aspen、Fluent 对中文路径不友好）

## 测试与评测

**回归测试**（`scripts/selftest.py`，2026-10-10，13 项全部通过）：SMR 平衡转化率、甲烷化陷阱、REquil 甲醇合成、MSR、变换、RadFrac 甲醇–水精馏、Sep（PSA 简化）、压缩机（含轴功单位）、错误组分名被 `trusted` 标出。参考值来自本机 Aspen，并与 Cantera 或手算对过，偏差见 `process-recipes.md` §11。

**评测**（2026-10-10 第一轮）：3 道题（转化率扫描、`.rep` 转 Excel、新建等离子体裂解模型），有技能、无技能各跑一次。有技能 24/24、无技能 20/24，差距全在"能否真正跑起 Aspen"。这一轮是在加入工艺配方、`trusted` 判断和回归测试**之前**做的；`.rep` 转 Excel 一题两组都满分，下一轮应换成配方相关的题（例如甲醇合成或 MSR 建模）。工作区（逐条评分和对比页 `review.html`）在 `~/.claude/skills/aspen-plus-simulation-workspace/`，不放入仓库。再跑评测时，多个子代理会同时用 Aspen，任务提示里要求它们用 `scripts/aspen_lock.py` 排队。
