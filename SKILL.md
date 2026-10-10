---
name: aspen-plus-simulation
description: 在本机用 Aspen Plus（必要时配合 Cantera、NASA CEA、Fluent、HTRI、Python 手算）建立、运行、诊断化工流程模拟，为非标设备方案和报价提供物料/能量衡算、换热负荷和选型依据。用户说"建个 Aspen 模型""跑一下流程模拟""做物料能量衡算""这个工艺行不行得通""核算一下换热/压降/转化率""扫一下工况"，或者给了技术需求书、PFD、反应路线、.inp/.bkp 文件要出模拟结果时，都应使用本技能。也用于：Aspen 跑不起来时诊断原因（COM 卡死、License 报错、收敛不了）；用 Python 通过 COM 批量改参数、做敏感性扫描；修改已有 .bkp 模型；把 .rep/.his 结果提取成 CSV/Excel；判断等离子体、高温裂解、淬冷控制等非平衡体系该不该叫 Cantera/CEA 复核，或者该不该叫 Fluent/HTRI 补流场和换热校核。不用于不需要跑模型的纯工艺判断（用 process-engineering-specialist），也不用于 HYSYS 油气/动态模拟项目（参考 Codex 侧的 aspen-simulation-designer）。
---

# Aspen Plus 化工流程模拟

## 这份技能解决什么

非标设备的方案和报价经常要"跑个模型把数定下来"。这件事在本机有两个难点：

1. **让 Aspen 被脚本驱动。**Aspen 的自动化入口有好几个，同一台机器上有的通、有的不通，而且失败方式很迷惑（卡死、DCOM 超时、"Unknown licensing error"）。P47 项目一开始只试了一个 ProgID，就误判为"只能用 GUI"，绕了一大圈 Codex computer use；后来查出进程内 COM（`Apwn.Document.IP`）是通的，打开、运行、导出全部能用脚本完成。
2. **判断 Aspen 的数字能不能信。**Aspen 的反应器模型背后是"给定转化率"或"达到化学平衡"两种假设。淬冷控制、停留时间极短、等离子体这类体系不满足这些假设，Aspen 会收敛得很干净，但数字不对。这时要用独立路径复核，不能把收敛当成正确。

## 工作流

1. **探环境**：先跑 `scripts/probe_aspen_com.py`，看 COM 能不能用，不要凭记忆假设。
2. **定基准**：从技术需求书、PFD、用户给的参数里列出进料、目标 KPI、约束，分清哪些是确定输入、哪些是工程假设。项目在用 `engineering-project-document-suite` 时，直接用它的参数台账和编号。
3. **搭模型**：组分、物性方法、反应器模型，见 `references/model-building.md`。
4. **跑和改**：COM 驱动见 `references/com-automation.md` 和 `scripts/aspen_com.py`；收敛问题见 `model-building.md` §4。
5. **自查和复核**：先做 `model-building.md` §6 的五项自查；再按下面的"什么时候叫搭档"判断要不要独立复核，见 `references/cross-validation.md`。
6. **取数和交付**：见 `references/report-extraction.md`。

## 环境探测和驱动方式

本机（Aspen Plus V11 / 37.0）2026-10-10 实测：

| 入口 | 结果 | 怎么用 |
|---|---|---|
| 进程内 COM `Apwn.Document.IP` | 可用 | 首选。`scripts/aspen_com.py` 封装了打开、改值、运行、导出、读警告、工况扫描 |
| 进程外 COM `Apwn.Document.37.0` | Dispatch 卡死或报 0x80080005 | 不用 |
| 命令行引擎 `aspen <runid>` | `Properties license is not available`，与 GUI 开没开无关 | 不用 |
| GUI（手动或 Codex computer use） | 可用 | 只用于：手写 .inp 第一次转成 .bkp；人眼看流程图；COM 整体失效时兜底 |

换版本或换机器后，探测结果可能完全不同，先跑探测脚本。脚本会把注册表里所有 `Apwn.Document*` 按"进程内优先"逐个试，每个都放在带超时的子进程里，卡死也不会把探测本身挂住。

COM 驱动最容易出错的几处（细节见 `com-automation.md` §3）：

- **.inp 不能直接用 COM 打开**：翻译 .inp 要过命令行引擎，而引擎没有许可证。第一个 .bkp 由 GUI 打开 .inp 存出来，或者用 COM 从空白文档搭。之后所有改动和扫描都走 COM。
- **空白文档默认英制，MET 的温度是 K**：填数之前先设单位集，填完用 `unit()` 看一眼。
- **一个 Python 进程只能开一个文档**；打开 .bkp 后要先运行才有结果；脚本没关文档，许可证就一直被占着。
- **.rep 是 latin-1 编码**，数字是省略 E 的 Fortran 格式（`7.6976-02`）；本机控制台是 GBK，脚本前加 `PYTHONIOENCODING=utf-8`。

需要 GUI 时，先问用户能不能自己点（转 .bkp 只要一两分钟）；用户不方便时，用 `scripts/codex_brief_template.md` 交给 Codex computer use，调用前的检查也写在那里。

## 什么时候叫搭档

| 信号 | Aspen 单算的问题 | 叫谁 | 分工 |
|---|---|---|---|
| 产物靠淬冷"冻结"（等离子体、电弧、燃烧后急冷） | RGibbs 给的是某个温度下的平衡组成，真实组成取决于冻结温度和降温速率 | Cantera | Cantera 算反应区单程转化率，填进 Aspen 的 RStoic；Aspen 算 BOP |
| 温度高于约 3000 K 或有电离 | Aspen 数据库在这个区间多半是外推 | NASA CEA（`ions=True`） | 同一组 T、P、进料，三方比平衡组成 |
| 平衡转化率要写进对外文件 | 单一程序的数据库可能有系统偏差 | CEA 或 Cantera 平衡态 | 至少一条独立路径 |
| 毫秒级停留时间、明显的冷热分区 | 单元模块是集总参数，不解流场 | Fluent | 给停留时间分布，检验"充分混合"假设 |
| 非标换热器，或压降、振动是卖点 | HeatX 用简化关联式 | HTRI | 负荷取 Aspen，传热系数和压降以 HTRI 为准 |
| 数字要拿去报价或写保证值 | — | Python 手算 | 独立重算 BOP 焓平衡和元素守恒 |

上表都不满足时，Aspen 单算加五项自查就够了。

判据：两条独立路径偏差在 1%～2% 以内并能说清来源，才算互证成立；差一个量级必有一方错，找第三条路径，不许挑顺眼的用。比对前各自先把结果落盘，这和 `codex-review` 模式 B 的纪律一样。

## 交付物

| 产物 | 为什么要留 |
|---|---|
| 工作副本 .bkp（不改用户原件）和关键工况的 .rep | 可追溯、可回滚 |
| 改动前后各导一份 .inp（`Export(4)`） | diff 一下就知道改了哪些输入 |
| 结果 CSV / Excel，注明来源文件、运行日期、运行状态 | 报告里的数字能追到文件 |
| 警告清单和处理结论（`.his` 原文 + 判断） | 下一轮能对比新增了什么 |
| 复核记录（`cross-validation.md` §6 的格式） | 交叉验证的价值在于写下来 |
| 简要报告：收敛状态、关键结果、未处理的警告、工程假设清单 | 假设值和计算值分开标，不把规格书的"希望值"写成保证值 |

## 常见错误

| 错误 | 后果 | 正确做法 |
|---|---|---|
| 只试一个 ProgID 就认定 COM 不可用 | 白走一整套 GUI + computer use 流程 | 跑探测脚本，把注册表里的 ProgID 都试一遍 |
| 不看单位就填数 | 25 ℃ 变成 25 °F 或 25 K，结果差几十个百分点 | 先设单位集，填完用 `unit()` 核对；做五项自查里的量级检查 |
| 把收敛当成结果正确 | 非平衡体系得到精确但错误的数字 | 看"什么时候叫搭档"表 |
| 从 GUI 界面上读数抄进报告 | 下次改模型对不上账 | 从节点或 .rep 取数，落成 CSV |
| 直接改用户的 .bkp | 回不去 | 复制到工作目录再改 |
| 已知良性警告每轮重新研究一遍 | 真正的新问题被淹没 | 对照 `model-building.md` §5，只看新增和变化的警告 |
| 把 RStoic 的转化率当成模型算出来的 | 输入当输出，报告里来源说不清 | 写明转化率的来源和信息状态 |
| 没做的复核留白 | 读者以为做过 | 写明"未做、原因、哪个阶段做" |

## 参考文件

- `references/com-automation.md`：本机三条入口的实测结果、标准流程、坑表、运行状态码、导出代码、常用节点路径、工况扫描
- `references/model-building.md`：手写 .inp 骨架、物性方法选型、反应器模型选型、收敛排错、已知良性警告、跑完五项自查
- `references/cross-validation.md`：Aspen 与 Cantera / CEA / Fluent / HTRI / Python 的分工、各工具的坑、P47 实例、复核记录格式
- `references/report-extraction.md`：.rep / .sum / .his 的格式、各类块的结果项名、解析脚本用法
- `scripts/probe_aspen_com.py`：探测 COM 入口，带超时，给出诊断和下一步
- `scripts/aspen_com.py`：COM 驱动（打开 / 新建、改值、运行、导出、读警告、浏览节点、扫描）
- `scripts/parse_rep_template.py`：解析 .rep，输出块结果和物流表 CSV
- `scripts/codex_brief_template.md`：需要 GUI 时交给 Codex computer use 的任务书模板和调用前检查
