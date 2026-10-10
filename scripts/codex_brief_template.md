# Codex computer use 操作 Aspen GUI 的任务书模板

COM（`Apwn.Document.IP`）可用时，GUI 只剩两件事要做：把手写的 .inp 转成第一个 .bkp，以及人眼看流程图。这两件事用户手动做只要一两分钟，先问用户愿不愿意自己点；用户不在或不方便时，再用下面的模板交给 Codex。COM 整体失效时，才用模板 B 把整个运行过程交给 GUI。

调用前的检查：

- Codex 桌面版开着时，它常驻的 `node_repl.exe` 会占住文件，`codex exec` 初始化沙箱时报 os error 32，computer use 起不来。先请用户关掉 Codex 桌面版。
- 本机 Windows 沙箱初始化也失败过（`windows sandbox failed: helper_unknown_error: setup refresh had errors`），P47 是用户授权后以 `danger-full-access` 运行才成功的。不要自己提权，先问用户。
- 一次只开一个 Aspen 实例，运行前确认没有 COM 脚本占着许可证；有其他任务也在用 Aspen 时，先 `python scripts/aspen_lock.py acquire <任务名>` 排队，结束后 release。
- 本机 Codex 做只读送审时，需要加 `-c windows.sandbox="unelevated"` 才能读文件（P47 汇报 PPT 送审时确认）。computer use 加这个参数能否成功没有验证过，P47 的 computer use 是在 `danger-full-access` 下跑通的。G: 盘（Google Drive）上的文件先拷到 E: 本地再交给 Codex，沙箱在 G: 上会静默失败。

`<尖括号>` 内的内容按项目替换。

---

## 模板 A：把 .inp 转成 .bkp

```markdown
# 任务：在 Aspen Plus <版本> 图形界面中打开一个输入文件并另存为 .bkp（用 computer use 操作桌面）

只做操作和记录，不改模型的工程内容。

## 文件

- 输入：`<绝对路径>\<名>.inp`
- 输出放在同一文件夹：`<名>.bkp`

## 步骤

1. 找到已打开的 Aspen Plus 窗口；没有就从开始菜单启动 "Aspen Plus <版本>"。
   - 窗口里如果有别的模型：名字是 `<上一轮本任务的文件名>` 时，提示保存选"否"；是其他名字时，不保存也不丢弃，停下来说明情况。
   - 只开一个 Aspen 实例。
2. File > Open 打开上面的 .inp（文件类型选 Input Files 或 All Files）。
3. 进入 Properties 环境，点功能区的 Retrieve Parameters。
4. 回到 Simulation 环境，运行一次（Run 或 F5）。弹出"输入不完整"时，记下缺的输入项，不要自己编数补上。
5. File > Save As，类型选 "Aspen Plus Backup Files (*.bkp)"，文件名 `<名>.bkp`。
6. 关闭 Aspen（File > Exit），释放许可证，后续由脚本接手。

## 回复内容

- 运行状态（Results Available / with warnings / with errors / input incomplete）；
- 若有 Error，抄原文和所在 block；Warning 不用抄，脚本会从 .his 读；
- 生成文件的完整路径；
- 操作中遇到的异常（弹窗原文、截图位置）。
```

---

## 模板 B：COM 不可用时，完整运行一轮

脱胎于 P47 的两轮实际任务书（`E:\18_Numerical_Simulation\P47_Plasma_CO2\01_AspenPlus\brief_aspen_run1.md`、`brief_aspen_run2.md`）。

```markdown
# 任务：在 Aspen Plus <版本> 图形界面中打开并运行一个输入文件（用 computer use 操作桌面）

本机的 Aspen Plus 当前只能通过图形界面使用，需要你操作桌面完成以下步骤。只做操作和记录，不改模型的工程内容。

## 文件

- 输入：`<绝对路径>\<名>.inp`
- 所有产出放在同一文件夹 `<绝对路径>\`

## 步骤

1. 找到已打开的 Aspen Plus 窗口；没有就从开始菜单启动。
   - 窗口里是 `<上一轮本任务的文件名>` 时，提示保存选"否"。是其他名字的模型时，不保存也不丢弃，停下来说明情况。
   - 许可证只允许一个用户，不要开第二个 Aspen 实例。
2. File > Open 打开 .inp（文件类型选 Input Files 或 All Files）。
3. 进入 Properties 环境，点 Retrieve Parameters。提示已有参数时选补齐或保留。然后看 Methods > Parameters > Binary Interaction，确认 <需要的参数表，如 HENRY-1、NRTL-1> 是否有数值。
4. 回到 Simulation 环境运行（Run 或 F5）。弹出"输入不完整"时，记下缺的输入项，不要自己编数补上；能执行的部分照常运行。
5. 打开 Control Panel，把所有 Error 和 Warning 原文逐条抄下来，包括所在 block 名。
6. 保存成果（同一文件夹）：
   - File > Save As，类型 "Aspen Plus Backup Files (*.bkp)"，文件名 `<名>.bkp`；
   - File > Export，类型 "Report Files (*.rep)"，文件名 `<名>.rep`；
   - Export 菜单里有 Summary（*.sum）时，一并导出 `<名>.sum`。
7. <保持 Aspen 窗口开着 / 关闭 Aspen 释放许可证>。

## 回复内容（写在最后一条消息里）

- 运行状态；
- Control Panel 的 Error 和 Warning 原文清单；
- 第 3 步中出现了哪些参数表，是否都有数值；
- 已生成文件的完整路径清单；
- 操作中遇到的异常（弹窗原文、截图位置）。
```

第二轮起在任务书末尾加一段，省得重复抄已知警告：

```markdown
补充：这是第 <N> 轮运行（<本轮改动，如：新增 Train B，即 MIX-B/E101B/R101B/E102B/V101B>）。上一轮的警告类型已知，不必逐条截图；只列新出现的 Error，以及与上一轮不同的 Warning。
```

---

## 调用方式

```bash
codex exec -C "<工作目录>" -s <workspace-write | danger-full-access（须用户授权）> \
  -c model_reasoning_effort="medium" "$(cat brief.md)" > codex_run<N>.log 2>&1
```

拿到回复后：

- 核对它列出的文件确实存在、修改时间是本次运行；
- 读回 .rep 的 PROBLEM STATUS，和它报的运行状态对一遍；
- 它报"没有异常"但文件缺失，或者 log 里有 `node_repl` / `sandbox` 报错，就是没跑成，不能当作已运行。P47 第一次尝试就是这样：日志写明在枚举窗口之前就失败了，没有打开任何模型。
