# SODA3西部暖水—风应力相抵消临界点验证

> **修正说明（2026-08-03）**：本报告把受力代理与Q20输送的水平/正负直接比较，只能检验“净力能否判别输送方向”，不能检验受力平衡本身。动力学上净力对应的是输送变化率 `dM/dt`；修正检验见 [SODA3_FORCE_BALANCE_TENDENCY_RESULT_CN.md](/Users/daiyue/Documents/Maryland/outputs/research_2026/soda3_force_balance/SODA3_FORCE_BALANCE_TENDENCY_RESULT_CN.md)。因此，下文约0.51的方向分类准确率不应被解释为“不存在受力平衡点”。

## 结论先行

本次检验支持“存在竞争”这个物理框架，但**没有支持一个可直接使用的、固定的零净动力临界点**。

- 西部暖层截面异常与向东SSH压力梯度的相关为 `+0.72`，事件聚类95%区间 `[+0.47, +0.89]`。
- 西部暖层与SODA3风应力异常的相关为 `-0.29`；与外部ERA5风异常的相关为 `-0.39`，区间 `[-0.56, -0.10]`。
- 净动力代理与日界线Q20异常的相关为 `+0.13`，区间 `[-0.02, +0.26]`。
- 直接以 `A_net>0` 判定日界线Q20异常为正，平衡准确率只有 `0.513`。这说明摩擦、平流、Kelvin波相位和暖量位置不能忽略。
- 改变东西箱位置并把有效深度改为100、150、200 m后，净动力—Q20相关范围为 `+0.08`—`+0.19`，零线平衡准确率范围为 `0.501`—`0.523`。

因此，资料支持的是**临界带/分界面**，而不是“西太平洋OHC达到某个数值就必然抵消”的单一阈值。

## 海洋释放门

使用13次暖事件、1—6月五日资料。压力项由150°—170°E与190°—210°E的SSH异常差计算；风项为180°—140°W的SODA3风应力异常除以20°C暖层有效深度。实际响应为日界线20°C相对热输送Q20。

### 同期机制识别

- 仅风模型Brier：`0.2655`。
- 压力+风模型Brier：`0.2722`。
- 相对仅风变化：`+0.0067`，事件聚类95%区间 `[+0.0015, +0.0128]`。

### 提前10日外推

- 仅风模型Brier：`0.2613`。
- 压力+风模型Brier：`0.2576`。
- 相对仅风变化：`-0.0037`，95%区间 `[-0.0285, +0.0231]`。
- 压力项在 `100%` 的留一折中为正，风项在 `100%` 的留一折中为正。

## 外部ERA5一致性复核

十个事件用ERA5逐日10 m纬向风替换SODA3风应力。预测未来10日日界线Q20正异常。需要注意，SODA3.15.2使用ERA5大气强迫，所以这属于外部场一致性复核，而不是完全独立的风强迫验证。

- ERA5仅风Brier：`0.2599`。
- 加入SODA3压力梯度后Brier：`0.2603`。
- Brier变化：`+0.0003`，95%区间 `[-0.0167, +0.0191]`。

只有当外部资料复核也稳定改善，并进一步得到TAO等独立观测支持时，才可把“压力克服风阻力”写成可移植预测门；否则它只能作为机制图像。

## 第二道大气耦合门

五日中央减西部近表层温度异常与ERA5 u10的相关为 `+0.54`，事件聚类95%区间 `[+0.32, +0.66]`。

- 仅季节模型Brier：`0.2529`。
- 加入温度梯度Brier：`0.2052`。
- Brier变化：`-0.0477`，95%区间 `[-0.0890, -0.0084]`。
- 经验50%西风概率阈值为 `+0.19 °C`，事件自助区间 `[-0.03, +0.37] °C`；斜率为正的自助样本比例 `100.0%`。

如果阈值区间很宽或跨越不合理范围，就不能把该数值当作普适常数，只能把温度梯度视作概率性门。

## 科学判断

1. “西部暖水既增加东向释放势能，又可能维持不利风场”的双重作用可以分开检验；不能把暖量本身直接当作风的机械原因。
2. 海洋释放首先取决于压力项与风项的竞争，但零和线不是完整动力临界点。
3. 即使暖量已经东传，仍需中央—西部表面温度梯度足以促使对流和西风东移，才能完成第二道大气门。
4. 本结果是再分析观测约束下的诊断验证，不是因果扰动实验。严格因果仍需要固定海洋初态、单独改变风应力或西部热含量的敏感性试验。

## 输出

- 主图：`/Users/daiyue/Documents/Maryland/output/pdf/soda3_compensation_threshold_verification.pdf`
- 1997/2015/2023路径图：`/Users/daiyue/Documents/Maryland/output/pdf/soda3_compensation_threshold_event_paths.pdf`
- 五日诊断表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_compensation_threshold_pentads.csv`
- 留一评分：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_compensation_threshold_loeo_skill.csv`
- 事件摘要：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_compensation_threshold_event_summary.csv`
- 自助检验：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_compensation_threshold_bootstrap_summary.csv`
- 区域与有效深度敏感性：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_compensation_threshold_region_depth_sensitivity.csv`
