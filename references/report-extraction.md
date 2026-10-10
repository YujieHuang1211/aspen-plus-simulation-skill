# 从 .rep / .sum / .his 里取数

## 1. 取数的原则

报告、计算书里的每个模拟数字都应该能追到一个文件：哪个 .rep（或哪次 COM 运行）、哪个块或物流、哪一项。不要从 GUI 界面上读数抄进文件，下一次改模型时对不上账。

COM 可用时，优先直接读节点（`aspen_com.py` 的 `get()`），同时导出一份 .rep 存档。COM 不可用、只能拿到 GUI 导出的 .rep 时，用 `scripts/parse_rep_template.py` 解析。

## 2. 三种文件

| 文件 | 怎么得到 | 里面有什么 | 用途 |
|---|---|---|---|
| `.rep` | GUI：File → Export → Report；COM：`Export(2, path)` | 全部块的输入回显和结果、全部物流表、运行状态 | 主要取数来源，人也能直接读 |
| `.sum` | GUI：Export → Summary；COM：`Export(3, path)` | 机器格式的结果摘要 | 很少直接用；需要大量物流数据时比 .rep 好解析，但格式没有文档 |
| `.his` | SaveAs 或运行时自动生成在 .bkp 同目录 | 运行历史，含 Control Panel 的全部 Warning / Error 原文 | 警告清单，`aspen_com.py` 的 `warnings()` 读的就是它 |

## 3. .rep 的格式要点（V11 实测）

- 编码 `latin-1`，不是 UTF-8。打印中文的脚本前加 `PYTHONIOENCODING=utf-8`（本机控制台是 GBK）。
- 数字是 Fortran 格式，可能省略 E：`7.6976-02` 是 0.076976，`-2.3300+04` 是 -23300；HEATX 的物流示意图里还会出现 `7.0000D+02`。解析脚本的 `to_float()` 统一处理。
- 每页开头有三行页眉（版本、标题、所在章节），跨页的块会重复出现 `BLOCK:  X  MODEL: Y (CONTINUED)`。先删页眉，再按块名合并。
- 目录（TABLE OF CONTENTS）里把每个章节名和块名都列了一遍。按"第一次出现的章节名"切分会切到目录里。真正的块标题是行首恰好一个空格的 `\n BLOCK:  `，物流表以 `\n STREAM ID ` 开头。
- 章节顺序：RUN CONTROL → FLOWSHEET → CONVERGENCE → PHYSICAL PROPERTIES → U-O-S BLOCK → STREAM → PROBLEM STATUS。

## 4. 各类块的结果项名

块结果从 `***  RESULTS  ***`（HEATX 是 `***  OVERALL RESULTS  ***`）之后开始，格式是"名称　单位　数值"。

| 块类型 | 常用结果项（.rep 原文） |
|---|---|
| HEATER | `OUTLET TEMPERATURE`、`OUTLET PRESSURE`、`HEAT DUTY`、`VAPOR FRACTION` |
| HEATX | `CALCULATED HEAT DUTY`、`CALCULATED (REQUIRED) AREA`、`AVERAGE COEFFICIENT (DIRTY)`、`UA (DIRTY)`、`LMTD (CORRECTED)`、`HOTSIDE, TOTAL`（压降）、`COLDSIDE, TOTAL` |
| FLASH2 | `OUTLET TEMPERATURE`、`OUTLET PRESSURE`、`HEAT DUTY`、`VAPOR FRACTION` |
| RSTOIC | `OUTLET TEMPERATURE`、`HEAT DUTY`、`VAPOR FRACTION`；`REACTION EXTENTS` 表 |
| RGIBBS | `TEMPERATURE`、`PRESSURE`、`HEAT DUTY`；`FLUID PHASE MOLE FRACTIONS` 下逐个组分的摩尔分数 |
| MIXER | 没有 RESULTS 段，只有物料平衡表 |
| 压缩机、泵（未实测，名称来自手册） | `NET WORK REQUIRED`、`BRAKE HORSEPOWER`、`OUTLET TEMPERATURE` |

每个块开头都有 `MASS AND ENERGY BALANCE` 表（IN / OUT / RELATIVE DIFF.），可以直接拿来做物料平衡自查。

## 5. 物流表

物流表每页 5 股物流并排，分段如下（段名就是 `stream()` 返回字典的键）：

```text
COMPONENTS: KMOL/HR      各组分摩尔流量
COMPONENTS: MOLE FRAC    摩尔分数
COMPONENTS: KG/HR        质量流量
TOTAL FLOW               KMOL/HR、KG/HR、L/MIN
STATE VARIABLES          TEMP C、PRES BAR、VFRAC、LFRAC、SFRAC
ENTHALPY                 CAL/MOL、CAL/GM、KW
ENTROPY / DENSITY / AVG MW
```

单位跟着模型的 OUT-UNITS 走。P47 的 .inp 把温度、压力、焓流改成了 °C、bar、kW，换一个模型要先看物流表头再取数。

## 6. 解析脚本用法

```bash
PYTHONIOENCODING=utf-8 python scripts/parse_rep_template.py model.rep out_dir
# -> out_dir/model_streams.csv（stream, section, item, value）
#    out_dir/model_blocks.csv（block, model, item, value, unit）
#    屏幕打印 PROBLEM STATUS
```

项目里要取特定数字时，导入后按名称取：

```python
from parse_rep_template import Rep
rep = Rep('p47_bop_r2.rep')
rep.block_value('E101R', 'CALCULATED HEAT DUTY')          # 15.2579
rep.stream('PROD3-K')['STATE VARIABLES']['VFRAC']          # 0.7447
rep.stream('SYNG-R')['COMPONENTS: MOLE FRAC']['CO']
rep.status()                                               # 运行状态和带警告的块
```

脚本在 P47 的两份 .rep（GUI 导出和 COM 导出各一份）上验证过：21 个块、37 股物流，取出的负荷和 COM 直接读节点的值一致。块结果表里的多列表格（K 值表、分区温度表）会被跳过，需要时按 P47 原脚本的写法用正则单独取。

## 7. 写进交付文件时

- 生成一份 CSV 或 Excel，文件里写明来源 .rep 的文件名和运行日期，以及运行状态和警告的处理结论（参考 P47 的 `H_aspen_results.csv` 末尾的 note 行）。
- 有效数字按工程用途取，热负荷一般保留到 0.1 kW，摩尔分数 3～4 位。不要把 Aspen 输出的 7 位数字原样写进报价文件，看起来很精确，其实输入条件本身没有这么准。
