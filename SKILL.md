---
name: aspen-plus-simulation
description: 在本机用 Aspen Plus（必要时配合 Cantera、NASA CEA、Fluent、HTRI、Python 手算）建立、运行、诊断化工流程模拟，为非标设备方案和报价提供物料/能量衡算、换热负荷和选型依据。适用于各类化工工艺：天然气重整（SMR/ATR/POX）与变换、甲醇水蒸气重整、甲醇合成、费托合成、PSA、精馏、加氢、等离子体或高温裂解等，也适用于没做过的新工艺。用户说"建个 Aspen 模型""跑一下流程模拟""做物料能量衡算""这个工艺行不行得通""核算换热/压降/转化率/能耗""扫一下工况"，或者给了技术需求书、PFD、反应路线、.inp/.bkp 文件要出模拟结果时，都应使用本技能。也用于：Aspen 跑不起来时诊断原因（COM 卡死、License 报错、收敛不了、结果离谱）；用 Python 通过 COM 批量改参数、做敏感性扫描；修改已有 .bkp；把 .rep/.his 结果提取成 CSV/Excel；判断平衡计算能不能信、该不该叫 Cantera/CEA/Fluent/HTRI 复核。不用于不需要跑模型的纯工艺判断（用 process-engineering-specialist），也不用于 HYSYS 油气/动态模拟项目。
---

# Aspen Plus 化工流程模拟

## 这份技能解决什么

非标设备的方案和报价经常要"跑个模型把数定下来"：物料平衡、能量平衡、换热负荷、压缩功、选型裕量。不管是什么工艺，难点都在三处：

1. **让 Aspen 被脚本驱动。**Aspen 的自动化入口有好几个，同一台机器上有的通、有的不通，失败方式很迷惑（卡死、DCOM 超时、"Unknown licensing error"）。本机只有进程内 COM（`Apwn.Document.IP`）能用，打开、改参数、运行、导出、读警告全部能用脚本完成。P47 项目一开始只试了另一个入口，误判为"只能用 GUI"，绕了一大圈。
2. **把工艺翻译成正确的块和设置。**同一个反应，用 RGibbs、REquil、RStoic 还是 RYield，结果可以差到完全不同。最典型的是平衡块一旦允许生成甲烷，甲醇合成、甲醇重整、变换、费托的结果全部被甲烷化吞掉（实测甲醇合成算出 0 甲醇、46% 甲烷）。Aspen 照样收敛，不报任何错。
3. **判断数字能不能信。**收敛不等于正确。单位错、组分没从数据库查到、反应器假设不成立（淬冷、选择性、动力学控制），都会给出干净但错误的结果。要靠自查和独立路径复核把关。

## 工作流

1. **探环境**：先跑 `scripts/probe_aspen_com.py`，看 COM 能不能用，不要凭记忆假设。
2. **定基准**：从技术需求书、PFD、用户给的参数里列出进料、目标 KPI、约束，分清哪些是确定输入、哪些是工程假设。项目在用 `engineering-project-document-suite` 时，直接用它的参数台账和编号。
3. **定建模方案**：先读 `references/process-recipes.md`。有现成配方的工艺（重整、变换、MSR、甲醇合成、FT、PSA、精馏、加氢、压缩换热）直接按配方；没做过的工艺按它 §1 的七步走：判断反应受什么控制、选块、想清楚允许生成哪些物种、选物性方法。
4. **算锚点**：用 `scripts/equilibrium_check.py`（Cantera，限定物种、标出惰性组分）算平衡，或者手算热平衡，先知道 Aspen 结果应该落在哪个量级。
5. **搭最小模型**：先只放反应器和一个分离，跑通、和锚点对上，再加换热网络、循环和公用工程。块参数和节点见 `references/com-automation.md`、`references/model-building.md`；不确定的关键字用 `options()` 读合法值，用 `tree` 看节点名。
6. **跑和改**：`scripts/aspen_com.py`。每次 `run()` 看返回的 `trusted`：没出结果、有错误、组分物性缺失时它是 False，这时的数字不能用。
7. **自查和复核**：`model-building.md` §6 的五项自查；再按下面"什么时候叫搭档"判断要不要独立复核，见 `references/cross-validation.md`。
8. **取数和交付**：见 `references/report-extraction.md`。

## 环境探测和驱动方式

本机（Aspen Plus V11 / 37.0）2026-10-10 实测：

| 入口 | 结果 | 怎么用 |
|---|---|---|
| 进程内 COM `Apwn.Document.IP` | 可用 | 首选。`scripts/aspen_com.py` 封装了打开/新建、改值、运行、导出、读警告、扫描、加反应、读选项 |
| 进程外 COM `Apwn.Document.37.0` | Dispatch 卡死或报 0x80080005 | 不用 |
| 命令行引擎 `aspen <runid>` | `Properties license is not available`，与 GUI 开没开无关 | 不用 |
| GUI（手动或 Codex computer use） | 可用 | 只用于：手写 .inp 第一次转成 .bkp；人眼看流程图；COM 整体失效时兜底 |

换版本或换机器后，探测结果可能完全不同，先跑探测脚本。它把注册表里所有 `Apwn.Document*` 按"进程内优先"逐个试，每个都放在带超时的子进程里。

COM 驱动最容易出错的几处（细节见 `com-automation.md` §3）：

- **.inp 不能直接用 COM 打开**：翻译 .inp 要过命令行引擎，而引擎没有许可证。第一个 .bkp 由 GUI 打开 .inp 存出来，或者用 COM 从空白文档搭。
- **单位**：空白文档默认英制；MET 单位集里温度是 K、热负荷是 cal/sec，但压缩机轴功是 kW。同一单位集里不同的量单位不同，读数和填数都用 `unit()` 看一眼。
- **组分要用数据库里的名字**：甲醇是 `METHANOL` 或 `CH4O`，写成 `CH3OH` 不报错，但运行时物性全缺（"MW MISSING"），`run()['trusted']` 会变成 False。
- **改了输入不运行，读到的是旧结果**：取数前一律 `run()`。
- **一个 Python 进程只能开一个文档**；许可证只有一个席位，多个任务同时要用 Aspen 时用 `scripts/aspen_lock.py` 排队。
- **.rep 是 latin-1 编码**，数字是省略 E 的 Fortran 格式（`7.6976-02`）；本机控制台是 GBK，脚本前加 `PYTHONIOENCODING=utf-8`。

需要 GUI 时，先问用户能不能自己点（转 .bkp 只要一两分钟）；用户不方便时，用 `scripts/codex_brief_template.md` 交给 Codex computer use。

## 什么时候叫搭档

| 信号 | Aspen 单算的问题 | 叫谁 | 分工 |
|---|---|---|---|
| 低温催化工艺用了平衡块（RGibbs/REquil） | 平衡解是热力学最低点，可能全变甲烷，而催化剂是有选择性的 | Cantera（`equilibrium_check.py`，限定物种） | 两边用同样的物种限定算一遍平衡，量级对上再往下走 |
| 产物靠淬冷"冻结"（等离子体、电弧、燃烧后急冷） | RGibbs 给的是某个温度下的平衡组成，真实组成取决于冻结温度和降温速率 | Cantera 动力学 | Cantera 算反应区单程转化率，填进 Aspen 的 RStoic；Aspen 算 BOP |
| 温度高于约 3000 K 或有电离 | Aspen 数据库的 Cp 拟合可能已在外推（实测 CO₂ 裂解 3000～3500 K 时 RGibbs 与 CEA 仍只差 ≤0.3 个百分点，但不能默认别的体系也这样） | NASA CEA（电离显著时 `ions=True`） | 同一组 T、P、进料，三方比平衡组成 |
| 平衡转化率要写进对外文件 | 单一程序的数据库可能有系统偏差 | CEA 或 Cantera 平衡态 | 至少一条独立路径 |
| 毫秒级停留时间、明显的冷热分区 | 单元模块是集总参数，不解流场 | Fluent | 给停留时间分布，检验"充分混合"假设 |
| 非标换热器，或压降、振动是卖点 | HeatX 用简化关联式 | HTRI | 负荷取 Aspen，传热系数和压降以 HTRI 为准 |
| 吸附（PSA）、膜分离的性能 | Aspen Plus 只能用 Sep 块给回收率，不算周期和床层 | 厂家数据（或 Aspen Adsorption） | Sep 块的分率取厂家性能，标为外部输入 |
| 数字要拿去报价或写保证值 | — | Python 手算 | 独立重算焓平衡和元素守恒 |

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
| 低温催化工艺用平衡块，又允许生成甲烷 | 甲醇、氢气、长链烃全部算成甲烷，模型照样收敛 | 用 REquil 只写目标反应，或组分表里不放不该生成的物种；先用 `equilibrium_check.py` 算锚点 |
| 凭记忆写关键字或组分名 | 设置被拒，或者更糟，被接受但没生效（组分物性全缺） | `options()` 读合法值，`tree` 看节点；看 `run()['trusted']` |
| 不看单位就填数、读数 | 25 ℃ 变成 25 °F 或 25 K；功率按热负荷的单位换算，差两个数量级 | 每个量都用 `unit()` 看；做五项自查里的量级检查 |
| 一上来搭全流程 | 出了问题分不清是哪一块 | 先搭反应器 + 一个分离，对上锚点再扩 |
| 把收敛当成结果正确 | 非平衡体系得到精确但错误的数字 | 看"什么时候叫搭档"表 |
| 从 GUI 界面上读数抄进报告 | 下次改模型对不上账 | 从节点或 .rep 取数，落成 CSV |
| 直接改用户的 .bkp | 回不去 | 复制到工作目录再改 |
| 已知良性警告每轮重新研究一遍 | 真正的新问题被淹没 | 对照 `model-building.md` §5，只看新增和变化的警告 |
| 把 RStoic / RYield / Sep 的输入当成模型算出来的 | 转化率、收率、回收率的来源说不清 | 写明来源和信息状态（试验值、文献值、厂家数据、工程假设） |
| 没做的复核留白 | 读者以为做过 | 写明"未做、原因、哪个阶段做" |

## 参考文件

- `references/process-recipes.md`：没做过的工艺怎么上手（七步）；甲烷化陷阱；重整与变换、MSR、甲醇合成、FT、PSA、精馏、加氢、压缩换热的配方；每条标明实测还是典型值
- `references/com-automation.md`：本机三条入口的实测结果、标准流程、坑表、运行状态码、导出代码、常用节点路径、工况扫描
- `references/model-building.md`：手写 .inp 骨架、物性方法选型、反应器模型选型、收敛排错、已知良性警告、跑完五项自查
- `references/cross-validation.md`：Aspen 与 Cantera / CEA / Fluent / HTRI / Python 的分工、各工具的坑、P47 实例、复核记录格式
- `references/report-extraction.md`：.rep / .sum / .his 的格式、各类块的结果项名、解析脚本用法
- `scripts/probe_aspen_com.py`：探测 COM 入口，带超时，给出诊断和下一步
- `scripts/aspen_com.py`：COM 驱动（打开/新建、改值、运行并判断可信度、导出、读警告、浏览节点、读选项、加组分和块、RStoic/REquil 反应、扫描）
- `scripts/equilibrium_check.py`：Cantera 理想气体平衡锚点，限定物种、标出惰性组分、温度扫描
- `scripts/parse_rep_template.py`：解析 .rep，输出块结果和物流表 CSV
- `scripts/aspen_lock.py`：单许可证排队锁；多个代理或脚本同时要用 Aspen 时，每个任务前后 acquire / release
- `scripts/codex_brief_template.md`：需要 GUI 时交给 Codex computer use 的任务书模板和调用前检查
