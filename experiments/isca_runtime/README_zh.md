# 本机 Isca 规定 SST 实验环境

## 当前状态

这套环境已经可以直接做“给定海温异常后，大气反馈是否接上”的机制筛选。

- 机器：Apple M2、8 GB 内存。
- 模式：Isca，T42、40 层、真实陆地和地形、RRTM 辐射、Full Betts–Miller
  对流、规定 SST。
- 源码固定在提交 `a290bc376d84d0ee83adbb80eb374b9f629c3534`。
- 独立环境：`env_py312`，不修改系统 Python 或 Anaconda。
- 已通过干 Held–Suarez、完整湿大气 AMIP SST，以及 2023 IA0×FEP0
  自定义 SST 三层测试。
- 自定义 SST 测试正常输出了 `t_surf`、降水、OLR、10 米风和表面动量通量；
  未出现 NaN。

Isca 是机制层级模式，适合先检验因果链条是否成立。它不是 CAM/ECHAM
这类全面 AGCM，因此显著结果之后仍应在 HPC 上用全面 AGCM 复核。

## 文件

- `activate_isca.sh`：激活本机环境。
- `prepare_isca_sst_boundaries.py`：把现有 2023 IA×FEP SST 矩阵转成
  Isca 的月变边界。
- `forcing_isca/`：8 组可直接使用的规定 SST 文件。
- `run_control_spinup.py`：生成各试验共用的 2023-03-01 大气 restart。
- `run_2023_factorial.py`：运行单个事件、单个集合成员。
- `checks/`：编译和端到端验证脚本。
- `data/`：模型输出与 restart。

## 使用

```bash
cd /Users/daiyue/Documents/Maryland
source experiments/isca_runtime/activate_isca.sh
python experiments/isca_runtime/prepare_isca_sst_boundaries.py
```

生成两年共同控制态；默认只保留最新 restart，以节省磁盘：

```bash
python experiments/isca_runtime/run_control_spinup.py --months 24 --cores 4
```

先用某个共同大气 restart 做一个月的试验：

```bash
python experiments/isca_runtime/run_2023_factorial.py \
  --case ia0_fep0 \
  --member 1 \
  --months 1 \
  --cores 4 \
  --restart /absolute/path/to/common_2023-03-01_restart.tar.gz
```

完整主矩阵是 `ia0_fep0`、`ia0_fep1`、`ia1_fep0`、`ia1_fep1`；`iar*`
四组是独立 IA 构造的敏感性试验。省略 `--restart` 只适合技术测试，不能用于
集合间科学比较。加 `--daily-surface` 会保存逐日二维耦合量。

## 推荐的科学运行顺序

1. 用 AMIP 月气候 SST 从 2021-03-01 积分到 2023-03-01，产生共同控制态。
2. 从控制积分中抽取相互间隔足够的 10 个大气初值，先跑四个主矩阵格点。
3. 计算主效应和交互项：

   - IA 主效应：
     `0.5 × [(IA1,FEP0 − IA0,FEP0) + (IA1,FEP1 − IA0,FEP1)]`
   - FEP 主效应：
     `0.5 × [(IA0,FEP1 − IA0,FEP0) + (IA1,FEP1 − IA1,FEP0)]`
   - 交互项：
     `(IA1,FEP1 − IA1,FEP0) − (IA0,FEP1 − IA0,FEP0)`

4. 重点比较 5°S–5°N 的降水/OLR、140°E–140°W 的西风或风应力、
   Niño3/EP 区表面通量，并用集合离散度检验显著性。
5. 若主矩阵显示稳定交互作用，再补 `iar*` 敏感性组并提高到 30 个成员。
6. 最后把最关键的两至四组移植到 CAM/ECHAM 做确认。

这里的规定 SST 实验只回答“大气在给定 SST 空间型后会不会接上”。它不能
直接模拟暖水向东输送、D20 演变和海洋热含量储存；海洋支路仍需 SODA3
诊断或耦合模式试验。

## 性能与存储

本机验证中，T42/40 层、4 个 MPI 进程积分 1 模式日约 19–26 秒。按线性
估算，一个 6 个月成员纯积分约 1–1.3 小时；240 个成员顺序运行约
10–13 天，且逐日全球输出可能超过当前可用磁盘空间。因此应先做
4 格点 × 10 成员的筛选，压缩并只保留必要诊断，再扩展集合。

## 本机兼容修改

仅加入了 macOS arm64 编译模板、NetCDF/MPI 链接设置、一个缺失的 C
函数声明，以及在 macOS 上禁用 Linux 专用 CPU affinity 调用；没有改变
物理参数。编译器仍提示上游 C 代码把部分浮点 `abs` 写成整数版本；目前
测试稳定，但正式论文级批量试验前应在 Linux/HPC 版本做交叉复现。
