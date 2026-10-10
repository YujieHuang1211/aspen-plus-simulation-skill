# 搭模型：输入文件、物性方法、反应器、收敛

## 目录

1. 手写 .inp 的骨架
2. 物性方法怎么选
3. 反应器模型怎么选
4. 收敛不了怎么办
5. 已知良性警告
6. 跑完先做的五项自查

## 1. 手写 .inp 的骨架

Aspen 的关键字输入文件是纯文本，适合由脚本或我直接写，再在 GUI 里打开一次存成 .bkp（见 `com-automation.md` §2）。下面摘自 P47 项目实际跑通的 .inp（全部关键字和写法都在原文件里运行过），删减成一条流程。**删减后的这份骨架本身没有单独运行过**，第一次套用时在 GUI 里打开确认一遍：

```text
TITLE 'Project - BOP HMB'

IN-UNITS MET PRESSURE=bar TEMPERATURE=C DELTA-T=C PDROP=bar  &
        MOLE-FLOW='kmol/hr' MASS-FLOW='kg/hr' ENTHALPY-FLO=kW  &
        POWER=kW HEAT=kJ
OUT-UNITS MET PRESSURE=bar TEMPERATURE=C DELTA-T=C PDROP=bar  &
        MOLE-FLOW='kmol/hr' MASS-FLOW='kg/hr' ENTHALPY-FLO=kW  &
        POWER=kW HEAT=kJ

DEF-STREAMS CONVEN ALL
SIM-OPTIONS MASS-BAL-CHE=YES

DATABANKS 'APV110 PURE37' / 'APV110 AQUEOUS' / 'APV110 SOLIDS'  &
         / 'APV110 INORGANIC' / NOASPENPCD
PROP-SOURCES 'APV110 PURE37' / 'APV110 AQUEOUS' / 'APV110 SOLIDS'  &
         / 'APV110 INORGANIC'

COMPONENTS
    CO2 CO2 /
    CO CO /
    H2 H2 /
    H2O H2O

HENRY-COMPS HC CO2 CO H2

FLOWSHEET
    BLOCK MIX1 IN=CO2-IN H2-IN OUT=FEED
    BLOCK E101 IN=FEED PROD1 OUT=FEEDH PROD2
    BLOCK R101 IN=FEEDH OUT=PROD1
    BLOCK E102 IN=PROD2 OUT=PROD3
    BLOCK V101 IN=PROD3 OUT=SYNGAS COND
    BLOCK RG1 IN=VAL1 OUT=VALO1

PROPERTIES NRTL HENRY-COMPS=HC

; 25 Nm3/h CO2, H2/CO2 = 2
STREAM CO2-IN
    SUBSTREAM MIXED TEMP=25. PRES=2.
    MOLE-FLOW CO2 1.11538
STREAM H2-IN
    SUBSTREAM MIXED TEMP=25. PRES=2.
    MOLE-FLOW H2 2.23076
; equilibrium check feed, not connected to the process
STREAM VAL1
    SUBSTREAM MIXED TEMP=25. PRES=1.01325
    MOLE-FLOW CO2 1. / H2 2.

BLOCK MIX1 MIXER
    PARAM PRES=0.

; feed/product recuperator, feed preheated to 500 C
BLOCK E101 HEATX
    PARAM T-COLD=500. PRES-HOT=-0.02 PRES-COLD=-0.05
    FEEDS HOT=PROD1 COLD=FEED
    PRODUCTS HOT=PROD2 COLD=FEEDH

; reactor: single-pass conversion from the kinetic model, outlet = quench outlet
BLOCK R101 RSTOIC
    PARAM TEMP=700. PRES=1.1
    STOIC 1 MIXED CO2 -1. / H2 -1. / CO 1. / H2O 1.
    CONV 1 MIXED CO2 0.8328

BLOCK E102 HEATER
    PARAM TEMP=40. PRES=-0.03

BLOCK V101 FLASH2
    PARAM TEMP=40. PRES=0.

BLOCK RG1 RGIBBS
    PARAM TEMP=1726.85 PRES=1.01325
```

写法要点：

- `IN-UNITS MET` 后逐项改成 °C、bar、kW，结果和输入同一套单位，读数时不用换算。
- 数据库名带版本号（V11 是 `APV110`，V12 是 `APV120`）。换版本时先改这里，否则 GUI 打开时报找不到数据库。
- 每个块和物流前用 `;` 写一行注释，说明工程含义和数值来源（"转化率来自 Cantera 0 维模型""换热温差按 30 K 取"）。三个月后回头看，或别人接手时，这行注释比模型本身更有用。
- 块里的 `PRES`：正值是出口绝对压力，`0.` 表示无压降，负值表示压降（`-0.03` 即降 0.03 bar）。物流里的 `PRES` 永远是绝对压力。两者容易写混。
- 多个方案并排算时，用后缀区分（Train R / B / K / C），同一个文件跑完，对比起来最方便。P47 就是一份 .inp 里放了 4 条流程和 4 个 RGibbs 平衡校核块。

## 2. 物性方法怎么选

先回答两个问题：体系里有没有极性组分（水、醇、酸、胺）；压力高不高（>10 bar 算高）。

| 体系 | 推荐方法 | 说明 |
|---|---|---|
| 非极性或弱极性烃类、轻气体，任意压力 | PENG-ROB 或 RK-SOAVE | 天然气、合成气、炼厂气、空分 |
| 轻气体 + 水，低压，只关心水冷凝 | NRTL + Henry 组分（轻气体设为 Henry 组分） | P47 用的就是这套。NRTL 二元参数缺失会报警，只有水一个可凝组分时影响很小 |
| 极性液体混合物，低压 | NRTL、UNIQUAC、WILSON | 先 Retrieve Parameters 看二元参数是否齐全；缺参数时用 UNIFAC 估算，并在报告里注明 |
| 极性组分 + 高压 | SR-POLAR、PSRK、或带混合规则的 PR（PR-WS / PRMHV2） | 甲醇合成回路、高压水煤气变换 |
| 电解质溶液（胺法脱碳、酸性水、碱液） | ELECNRTL（先跑电解质向导） | 不用电解质模型，pH 和离子平衡全错 |
| 纯水和蒸汽系统 | STEAMNBS 或 IAPWS-95 | 锅炉、蒸汽管网、余热回收 |
| 高温气相（>1500 K）且只关心气相平衡 | IDEAL 或 PENG-ROB 均可 | 高温下非理想性很小，但要确认数据库的 Cp 拟合范围覆盖到这个温度，否则用 NASA 多项式（Cantera/CEA）复核 |

选完之后：

- 在 Properties 环境里点 Retrieve Parameters，看 Binary Interaction 里每对组分有没有数值。没有数值的组分对要么补数据，要么在报告里写清楚"该组分对按理想处理"。
- 有液液分相可能时（水-烃），确认用的是能预测分相的方法和参数集（NRTL 的 LLE 参数和 VLE 参数不同）。
- 物性方法的选择要写进报告的假设清单，不要只留在模型里。

## 3. 反应器模型怎么选

| 模型 | 需要你给什么 | 适用 | 不适用 |
|---|---|---|---|
| RStoic | 化学计量 + 转化率 | 转化率已知（试验、文献、动力学模型算出的），只需要物料和能量平衡 | 想让模型告诉你转化率是多少 |
| RYield | 产物收率分布 | 裂解、气化、FT 等产物复杂、计量关系不明确的过程 | 工况一变收率就该变的场合（收率是固定输入，不随温度压力变）；Aspen 按质量归一，元素守恒要自己核对 |
| REquil | 化学计量 + 可选趋近平衡温度 | 少数几个已知反应达到平衡 | 多相、反应网络不清楚 |
| RGibbs | 只需要组分列表 | 高温下快速达到平衡的体系；作为"热力学上限"的校核 | 动力学控制或淬冷冻结的体系（结果偏乐观） |
| RCSTR / RPlug / RBatch | 动力学方程和参数 | 动力学已知，需要算体积、停留时间 | 拿不到可信的动力学参数 |

三条经验：

- **平衡块别让催化剂不促进的反应发生。**低温催化工艺（甲醇合成、甲醇重整、变换、FT、加氢）用 RGibbs 时，只要允许生成 CH₄，结果就全部变成甲烷（实测甲醇合成 0 甲醇、46% 甲烷），模型照样收敛。用 REquil 只写目标反应，详见 `process-recipes.md` §2。
- **RGibbs 给的是上限，不是预测。**它假设无限停留时间和充分混合。真实反应器如果靠淬冷"冻结"产物（等离子体、高温裂解、燃烧），出口组成取决于降温速率，RGibbs 算不出来。P47 的做法：RGibbs 只用于校核平衡上限，反应器块用 RStoic，转化率从 Cantera 有限速率模型拿过来（`cross-validation.md`）。
- **RStoic 的转化率是输入，不是结果。**报告里引用 RStoic 下游的数字时，必须同时写清楚转化率从哪来、状态是什么（试验值、文献值、计算值、工程假设）。

## 4. 收敛不了怎么办

先看 Control Panel（或 .his）里第一条 Error，后面的多半是它引起的连锁报错。

| 现象 | 常见原因 | 处置 |
|---|---|---|
| 闪蒸不收敛（FLASH FAILED） | 物流在临界点附近；规定的 T/P 下根本不存在两相；物性方法不合适 | 换成规定 T 和气相分率，或放宽 FLASH-TOL；检查是不是对超临界物流规定了两相闪蒸 |
| 循环回路（撕裂流）不收敛 | 初值离解太远；回路中组分只进不出，越积越多 | 给撕裂流一个合理初值（先断开回路单程跑一遍，把出口值抄回来）；检查每个组分在回路里都有出口（吹扫气）；把 Wegstein 换成 Broyden，或加大最大迭代次数 |
| 设计规定（Design Spec）不收敛 | 目标值超出可达范围；操纵变量上下限太窄 | 先用 Sensitivity 扫一遍操纵变量，确认目标值落在范围内，再把上下限设到这个范围 |
| 换热器 T 交叉 / 最小温差违反 | 规定的出口温度在热力学上做不到 | 改成规定负荷或最小温差，让模型自己算出口温度 |
| 组分平衡误差大（MASS-BAL-CHE 报警） | 反应计量写错；RStoic 计量不配平 | 逐个元素核对计量系数 |
| 能跑通但结果明显不合理 | 单位错（最常见是 °F/°C、psia/bar、lbmol/kmol） | 回 `com-automation.md` §3 第一条 |

收敛顺序有问题时，用 Convergence → Sequence 手动指定计算顺序，从进料端往下游排。

## 5. 已知良性警告

下面这些警告在 P47 里逐条核过，结果不受影响。新项目遇到同样的警告，先对照这里，再判断是否需要处理；不在表里的警告要逐条看。

| 警告原文（摘） | 出现条件 | 为什么可以接受 | 何时不能接受 |
|---|---|---|---|
| `NRTL BINARY PARAMETERS FOR ALL COMPONENT PAIRS ARE ZERO` | NRTL + 轻气体都设为 Henry 组分，只剩水是可凝组分 | 只有一个可凝组分，没有组分对需要 NRTL 参数 | 有两个以上可凝组分（水 + 甲醇等）时，必须补参数 |
| `ALL COMPONENTS ARE DEFINED AS HENRY COMPONENTS ... AT LEAST ONE OF THEM IS SUB-CRITICAL (" CO2 ")` | 纯气相物流（没有水）做初始焓计算或报告时 | 这些物流气相分率为 1，没有液相，警告针对的液相计算并未发生 | 该物流在低温高压下可能出现 CO₂ 液相 |
| `AT LEAST ONE FEED HAS ZERO FLOW / BLOCK BYPASSED`（HEATX） | 回热器所在回路第一次迭代，撕裂流还没有流量 | 收敛后的最终结果里该块正常计算 | 最终结果里该块仍然是 bypassed |
| `COLD FEED TEMPERATURE MAY BE UNRELIABLE DUE TO THE FLASH PROBLEM`（HEATX） | 同第二条，冷侧是纯气相 | 同第二条 | 同第二条 |

## 6. 跑完先做的五项自查

不做这五项，不要把数字写进任何文件。

1. **单位**：随机挑三个输入值，`unit()` 或 GUI 里看单位对不对。
2. **总物料平衡**：进出总质量差 < 0.01%；每个元素（C、H、O、N）进出守恒。
3. **能量平衡**：所有块的热负荷加上功，等于进出物流焓差。P47 用 Python 独立算了一遍，偏差 < 1%。
4. **量级**：关键数字和手算估计在同一量级（比如 1 kmol/h 水从 25 ℃ 蒸发到 300 ℃ 约 15 kW）。差一个数量级必有一方错。
5. **趋势**：改一个输入（转化率、温度），输出朝预期方向变。P47 的 COM 扫描：转化率 0.80 → 0.86，反应器负荷 15.6 → 16.3 kW，合成气 CO 摩尔分数 0.338 → 0.374，方向和幅度都合理。
