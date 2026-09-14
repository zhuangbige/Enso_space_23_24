# Isca P0 完成审计清单

更新时间：2026-08-01 18:34（北京时间）

只有下列项目全部具有权威证据时，P0云端任务才可判定完成并停止实例。

| 要求 | 判定标准 | 云端权威证据 | 当前状态 |
|---|---|---|---|
| Linux运行环境 | `isca.x`动态库均指向隔离运行环境，单月端到端成功 | `ldd isca.x`；技术成员99日志和输出 | 已证明 |
| 六个月稳定性 | 6/6月文件与6/6重启有效，变量有限 | `logs/benchmark_6months.log`；`logs/benchmark_6months_validation.json` | 已证明 |
| SST四格 | 4文件完整，仅3—8月不同，SST交互为0 | `results/p0_screening/factorial_sst_validation.json` | 已证明 |
| 并发性能 | 6个4核作业均完成并通过正式变量验收 | `logs/parallel_6_benchmark/*.log`；`parallel_benchmark_validation.json` | 已证明；恢复总墙钟907秒、加速5.68倍 |
| 真正SLP | 6/6基准输出含`slp`且有限 | `parallel_benchmark_validation.json`中6个`slp`范围 | 已证明 |
| 独立天气种子 | 10/10内部状态哈希唯一、月文件有效 | `ensemble_restart_pool_validation.json` | 已证明，但这些只是不同月份种子 |
| 共同日期初值 | 10/10重启内部日期均为2023-03-01，状态10/10唯一，最终月文件有效 | `march_aligned_pool_validation.json` | 已证明；正式JSON为`complete=true`、日期10/10正确、状态10/10唯一、错误0；独立逐包审计同样得到10个文件和10个唯一哈希 |
| 配对设计 | 四情景同编号成员使用同一个共同日期重启 | `run_p0_screening.sh`和40个成员日志中的重启路径 | 运行中证明；成员1四情景均读取`res0001.tar.gz`，成员2已启动两情景均读取`res0002.tar.gz`；最终仍需40日志全量审计 |
| 正式矩阵 | 4情景×10成员均正常结束 | `logs/p0_screening_master.log`及40个成员日志 | 运行中；18:33:37启动，并发6，首批6日志已实际进入Isca，失败文件为空 |
| 文件总数 | 240/240个`atmos_monthly.nc`存在且非空 | `p0_verification.json`：`expected_files=valid_files=240` | 待运行 |
| 科学变量 | 每文件128×64×40，SST、降水、OLR、风、风应力、ps、slp均有限 | `p0_verification.json`逐文件审计 | 待运行 |
| 因子统计 | 月效应、MJJ配对效应、20,000次成员bootstrap完成 | `p0_monthly_metrics.csv`、`p0_paired_monthly_effects.csv`、`p0_mjj_factorial_summary.csv` | 待运行 |
| 图件 | 月度配对响应和MJJ因子效应均有PNG 400 dpi与PDF；绘图输入必须为240条唯一有限月记录和30条完整因子记录 | `results/p0_screening/figures/`；绘图脚本输入门槛 | 脚本已通过远程合成输入测试；正式图待运行 |
| 成本与性能 | 初值对齐、P0墙钟、并发数和费用可追溯 | `pipeline_summary.txt`及AutoDL计费 | 待汇总 |
| 本地备份 | JSON、CSV、PDF/PNG、日志摘要、运行脚本、SHA-256清单和最终报告已复制到本项目 | `p0_key_artifacts.tar.gz`、`reports/`与最终结果目录 | 打包脚本已同步并通过语法/哈希检查；已将符号安全因子表、解释JSON/Markdown及其生成脚本加入强制打包清单；待正式结果完成后执行和下载 |
| 科学边界 | 明确P0只检验给定SST后的大气门控，不声称完成海洋类型转换 | 最终报告结论与局限性 | 待最终审阅 |

## 最终停机条件

1. `march_aligned_pool_validation.json`为`complete=true`、日期10/10正确、状态哈希10/10唯一；
2. `p0_verification.json`为`complete=true`、240/240有效、错误0；
3. 两张主图的PNG与PDF均可正常渲染；
4. 关键结果和证据已备份到本地；
5. 运行记录、科学解释、费用和局限性写入最终报告。

任一条件缺失时不得以日志中出现`P0_SCREENING_COMPLETE`替代完整验收。
