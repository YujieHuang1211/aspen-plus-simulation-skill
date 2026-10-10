# 用 COM 驱动 Aspen Plus

本文件的结论都在本机 Aspen Plus V11（内部版本号 37.0）上实测过（2026-10-10）。换了版本或机器，先跑 `scripts/probe_aspen_com.py` 再相信这里的任何一条。

## 1. 三条路径的实测结果

| 路径 | 本机结果 | 说明 |
|---|---|---|
| `Apwn.Document.IP`（进程内 COM） | **可用**。Dispatch 1 s，InitNew2 约 17 s（首次加载物性系统），打开 .bkp + 运行约 20 s | 首选。驱动脚本 `scripts/aspen_com.py` |
| `Apwn.Document.37.0`（进程外 COM） | Dispatch 卡死，或报 0x80080005（DCOM 10010 超时） | 以前只试了这一个，于是误判"本机 COM 不可用" |
| 命令行引擎 `aspen <runid>` | `FATAL LICENSING ERROR ... Properties license is not available`，GUI 关着也一样 | 许可证不给批处理引擎用，与 GUI 是否占用无关 |
| GUI | 可用 | 只在两件事上还需要它：把手写 .inp 转成第一个 .bkp；人眼看流程图 |

教训：探测时要把注册表里所有 `Apwn.Document*` 都试一遍，进程内的变体排在前面。只试一个 ProgID 就下结论，会白白多走一整套 GUI + computer use 的流程。

## 2. 标准流程

```text
探测 → 取得种子 .bkp → 复制到工作目录 → COM 打开 → 改输入 → Run2 → 读结果 / 导出 .rep / 读 .his 警告 → SaveAs
```

种子 .bkp 有三个来源，按省事程度排：

1. 用户或以前的项目已经有 .bkp：复制一份再用，不要直接改原件。
2. 手写 .inp（关键字格式，见 `model-building.md` §1），在 GUI 里打开一次，另存为 .bkp。这一步可以交给用户手动做（1 分钟），也可以用 `codex_brief_template.md` 交给 Codex computer use。
3. 完全用 COM 从空白文档搭（`add_components / add_block / connect`，RStoic 反应式用 `add_rstoic_reaction`）。适合小流程；大流程逐个节点写很啰嗦，不如走第 2 条。RStoic 的反应式分在两张表里（反应物在 `Input\COEF`，产物在 `Input\COEF1`，要先插行、设标签再填系数），没有 helper 时要摸索好几轮。

`.inp` 不能直接喂给 COM：`InitFromArchive2` 和 `InitFromFile2` 都会报 `Unable to open file`，因为 .inp 的翻译要过命令行引擎，而引擎拿不到许可证。翻译中途会在目录里留下一个约 10 KB 的残缺 .bkp，它也打不开，直接删掉。

反过来是通的：`Export(4, path)` 能把任意 .bkp 导出为 .inp。改动前后各导一份 .inp 做 diff，是核对"到底改了哪些输入"最快的办法。

## 3. 必须知道的坑

| 坑 | 现象 | 对策 |
|---|---|---|
| 空白文档默认英制 | `InitNew2` 后填 25 会被当成 25 °F，1 当成 1 psia，流量按 lbmol/hr | 先 `set_units('MET')`。空白文档只有 ENG / MET / SI 三套，MET 是 K、atm、kmol/hr、cal/sec；没有 METCBAR。填完任何数都用 `unit(path)` 看一眼单位 |
| MET 的温度是 K | 写这份技能时的冒烟测试：换成 MET 后仍填了 25 和 300，结果是 25 K → 300 K，热负荷 13.2 kW；改成 298.15 / 573.15 K 后为 17.7～18.3 kW，和手算 17.9 kW 一致 | 用 MET 时温度一律 +273.15，热负荷 cal/sec × 4.184 / 1000 = kW。能拿到 GUI 存的 .bkp 时，直接沿用它的 °C / bar 单位集更省事 |
| 一个进程只能开一个文档 | `Close()` 之后同一 Python 进程里再 Dispatch，报 "operation not supported" | 每个模型、每批工况各起一个子进程 |
| .bkp 不带结果 | 打开 .bkp 后直接读 Output 节点，得到 None | 打开后先 `run()` |
| 许可证只有一个席位 | 脚本没 Close 就崩了，GUI 打不开 | 用 `with Aspen(...) as ap:`；脚本崩了就结束 python 进程。运行前确认用户没开着 GUI |
| 多个子代理或脚本同时要用 Aspen | 互相抢许可证，某个运行随机失败 | 每个用 Aspen 的任务前后调用 `scripts/aspen_lock.py acquire/release <任务名>` 排队。代理中途死掉时锁会留着，确认对应进程已结束后用同一任务名手动 release |
| 进程外 Dispatch 超时后留下孤儿进程 | 任务管理器里多一个 AspenPlus.exe | 它通常会自己退出；没退出、又确认不是用户开的 GUI，再结束它 |
| `Visible` 属性 | 进程内对象设置 `Visible` 会抛异常 | 不要设 |
| `SuppressDialogs` | 不设时，运行中弹框会把脚本挂住 | 打开文档后立刻设为 1（驱动脚本已处理） |
| Control Panel 消息 | `Export(6)` 导出的 .cpm 在 COM 下是空文件 | 读 SaveAs 时写在同目录下的 `<名>.his`，里面有完整的 Warning/Error 原文（`warnings()`） |

## 4. 运行状态和导出代码

`\Data\Results Summary\Run-Status\Output\UOSSTAT2`，实测值：

| 值 | 含义 |
|---|---|
| 8 | 正常完成，无警告 |
| 10 | 完成但有警告（Results Available with Warnings） |
| 其他 | 没有实测过，读 `warnings()` 和 .rep 末尾 PROBLEM STATUS 再判断 |

`doc.Export(code, path)`，路径不带扩展名，Aspen 自己加：1 → .bkp，2 → .rep，3 → .sum，4 → .inp，6 → .cpm（COM 下为空）。

## 5. 常用节点路径

已实测（V11）：

| 量 | 路径 |
|---|---|
| 物流输入温度 / 压力 | `\Data\Streams\<S>\Input\TEMP\MIXED`、`...\PRES\MIXED` |
| 物流组分流量（输入） | `\Data\Streams\<S>\Input\FLOW\MIXED\<组分>` |
| 物流出口摩尔分数 | `\Data\Streams\<S>\Output\MOLEFRAC\MIXED\<组分>` |
| HEATER / RSTOIC 热负荷 | `\Data\Blocks\<B>\Output\QCALC` |
| HEATX 热负荷 | `\Data\Blocks\<B>\Output\HX_DUTY` |
| FLASH2 气相分率 | `\Data\Blocks\<B>\Output\B_VFRAC` |
| HEATER 设定温度 / 压力 | `\Data\Blocks\<B>\Input\TEMP`、`...\Input\PRES` |
| RSTOIC 第 1 个反应的转化率 | `\Data\Blocks\<B>\Input\CONV\1` |
| RSTOIC 反应式系数 | 反应物 `...\Input\COEF\<反应号>\<组分>\MIXED`（负值），产物 `...\Input\COEF1\<反应号>\<组分>\MIXED`；关键组分 `...\Input\KEY_CID\<反应号>` |
| 全局物性方法 | `\Data\Properties\Specifications\Input\GBASEOPSET` |
| 输入 / 输出单位集 | `\Data\Setup\Global\Input\INSET`、`...\OUTSET` |

没把握的路径不要猜，按下面两种办法查：

- `python aspen_com.py tree model.bkp "\Data\Blocks\R101" 3` 列出该块下的节点名和当前值。
- GUI 里 Customize → Variable Explorer，可以看到任意变量的完整路径，复制即可。

物流结果的其他常用节点名（未逐个实测，用前 tree 确认）：`TEMP_OUT\MIXED`、`PRES_OUT\MIXED`、`MOLEFLMX\MIXED`（总摩尔流量）、`MASSFLMX\MIXED`、`VFRAC_OUT\MIXED`。

## 6. 工况扫描

单变量扫描直接用命令行：

```bash
PYTHONIOENCODING=utf-8 python aspen_com.py scan work.bkp "\Data\Blocks\R101R\Input\CONV\1" 0.80 0.83 0.86 -- \
    "\Data\Blocks\R101R\Output\QCALC" "\Data\Streams\SYNG-R\Output\MOLEFRAC\MIXED\CO"
```

本机实测三个点共约 30 s。多变量或要导出每个工况的 .rep 时，自己写一个循环脚本，每个工况 `run()` 后 `export('rep', ...)`，再用 `parse_rep_template.py` 汇总。Aspen 自带的 Sensitivity / Case Study 也能做，但结果要回 GUI 看；用 COM 循环，结果直接是 CSV。

## 7. 什么时候还要 GUI

- 手写 .inp 要变成第一个 .bkp（见 §2）。
- 交付前看一眼流程图有没有连错。COM 搭的模型在 GUI 里的布局效果还没实测过，第一次用时确认一下。
- 本文件的路径全部失效（换版本、重装后），需要人工确认 Aspen 本身还正常。

这几种情况下才写 Codex 任务书，模板见 `scripts/codex_brief_template.md`。
