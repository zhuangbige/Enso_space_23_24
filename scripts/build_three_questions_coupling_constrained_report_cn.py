#!/usr/bin/env python3
"""Build the revised complete three-question ENSO warm-heat DOCX report.

The research-question numbering remains arrival--fate--coupling, while the
physical sequence is written explicitly as arrival (Q1) -> coupling gate (Q3)
-> fate allocation (Q2).  This prevents a late 5N export diagnostic from being
misrepresented as the established cause of an earlier Jiang northeasterly.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

import build_warm_heat_fate_complete_report_cn as style


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs/research_2026/reports"
OUTPUT = OUT_DIR / "三个核心问题_海气耦合约束闭环_完整报告_20260808.docx"

style.FIGURES.update(
    {
        "h20_hov": ROOT / "outputs/research_2026/soda3_h20/soda3_h20_hovmoller_1997_2015_2023.png",
        "ctcp_fate": ROOT / "outputs/research_2026/three_questions_figure_package_20260805/01_main_figures/Fig02_CT_CP_three_box_arrival_and_fate.png",
        "event_fate": ROOT / "outputs/research_2026/three_questions_figure_package_20260805/01_main_figures/Fig03_event_arrival_export_surface_loss.png",
        "dynamic": ROOT / "outputs/research_2026/three_questions_figure_package_20260805/01_main_figures/Fig04_event_5N_dynamical_decomposition.png",
        "precondition": ROOT / "outputs/research_2026/three_questions_figure_package_20260805/01_main_figures/Fig05_FEP_subsurface_preconditioning.png",
        "atmosphere": ROOT / "outputs/research_2026/three_questions_figure_package_20260805/01_main_figures/Fig06_FEP_atmospheric_closure.png",
        "two_stage": ROOT / "outputs/research_2026/jiang_two_stage_coupling_path/jiang_two_stage_coupling_to_h20_export.png",
        "direction": ROOT / "outputs/research_2026/h20_outflow_ne_feedback/h20_outflow_ne_spatial_sensitivity.png",
        "three_event_sequence": ROOT / "outputs/research_2026/h20_outflow_ne_feedback/h20_outflow_ne_three_event_sequence.png",
    }
)


def set_header_footer(doc: Document) -> None:
    section = doc.sections[0]
    for paragraph in section.header.paragraphs:
        paragraph.text = ""
    hp = section.header.paragraphs[0]
    hp.paragraph_format.first_line_indent = Pt(0)
    hp.paragraph_format.space_after = Pt(0)
    style.set_run_font(hp.add_run("ENSO三个核心问题｜海气耦合约束闭环"), size=8.5, bold=True, color=style.MUTED)
    for table in section.footer.tables:
        for cell in table._cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    if "厄尔尼诺暖量去向与海气耦合闭环" in run.text:
                        run.text = run.text.replace("厄尔尼诺暖量去向与海气耦合闭环", "暖量到达—耦合接通—暖量分配")
                        style.set_run_font(run, size=8.5, color=style.MUTED)


def cover(doc: Document) -> None:
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(92)
    kicker = doc.add_paragraph()
    kicker.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kicker.paragraph_format.first_line_indent = Pt(0)
    kicker.paragraph_format.space_after = Pt(16)
    style.set_run_font(kicker.add_run("完整研究报告  |  2026年8月"), size=11, bold=True, color=style.GOLD)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.first_line_indent = Pt(0)
    title.paragraph_format.space_after = Pt(10)
    style.set_run_font(title.add_run("厄尔尼诺暖量的到达、去向与耦合命运"), size=27, bold=True, color=style.NAVY)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.first_line_indent = Pt(0)
    subtitle.paragraph_format.space_after = Pt(8)
    style.set_run_font(subtitle.add_run("三个固定科学问题的海气耦合约束修订版"), size=15, bold=True, color=style.DARK_BLUE)

    desc = doc.add_paragraph()
    desc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    desc.paragraph_format.first_line_indent = Pt(0)
    desc.paragraph_format.space_after = Pt(64)
    style.set_run_font(
        desc.add_run("SODA3.15.2 · OISST · ERA5 · GPCP/OLR · 1997/2015/2023事件对照"),
        size=10.8,
        italic=True,
        color=style.MUTED,
    )

    status = doc.add_paragraph()
    status.alignment = WD_ALIGN_PARAGRAPH.CENTER
    status.paragraph_format.first_line_indent = Pt(0)
    status.paragraph_format.space_after = Pt(5)
    style.set_run_font(status.add_run("研究状态：三问主体闭合；反馈方向与因果措辞已重新约束"), size=11, bold=True, color=style.GREEN)
    date = doc.add_paragraph()
    date.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date.paragraph_format.first_line_indent = Pt(0)
    style.set_run_font(date.add_run("2026年8月8日"), size=10.5, color=style.MUTED)
    doc.add_page_break()


def add_framework(doc: Document) -> None:
    style.add_section_heading(doc, "1 研究结论与三个问题的正确连接")
    style.add_para(
        doc,
        "本报告保留已经固定的三个问题：第一问追踪暖量是否到达东太平洋，第二问量化到达后的暖量去向，第三问解释相似FEP先暖和相似输入为何产生不同的海气耦合与暖量命运。但研究问题的编号顺序不等于物理因果顺序。新完成的双向检验表明，5°N暖量输出不能被预设为Jiang型东北风异常的上游原因。",
    )
    style.add_callout(
        doc,
        "物理机制顺序",
        "暖量到达（问题一：海洋燃料） → 海气耦合接通或受阻（问题三：点火效率） → 风应力、海表通量和SSH压力场重新分配暖量（问题二：耦合后果） → 储量变化反馈事件维持或衰减。",
        fill=style.LIGHT_BLUE,
    )
    style.add_table(
        doc,
        "表1  三个固定科学问题及其对海气耦合的约束",
        ["问题", "中心内容", "对海气耦合的约束", "当前完成度"],
        [
            ["问题一", "暖量是否、以及通过什么路径到达东太平洋？", "给出海洋能否支持耦合的必要热量基础；不等同于耦合已经建立", "主体解决"],
            ["问题二", "暖量在北向、南向、海表散热和储存之间如何分配？", "主要诊断耦合建立后的海洋响应，并约束事件维持和衰减；不是单向上游原因", "主要通道解决"],
            ["问题三", "为什么相似FEP先暖和东部输入产生不同暖量命运？", "判定海洋热量能否转化为深对流、SLP和风应力响应，并连接到后期出口", "过程链解决；上游根因待模式试验"],
        ],
        [1000, 2940, 3280, 2140],
        font_size=8.2,
    )
    style.add_para(
        doc,
        "全文最重要的判断是：暖量到达决定有没有燃料；海气接通决定能否点火；暖量分配记录点火以后燃料如何被保存、释放或带走。2015和2023具有接近的东部输入和储热，却形成不同风场与出口，因此构成检验这一逻辑的关键对照。",
    )

    doc.add_heading("1.1 从Chakravorty等（2021）推进到当前问题", level=2)
    style.add_para(
        doc,
        "Chakravorty等（2021）利用SODA2.1.6中的WWV、170°E纬向暖水输送以及5°N和10°S经向暖水输送，指出冷舌型（CT）厄尔尼诺具有更清楚的西太平洋蓄热、赤道东传和成熟期向极放电，而中央太平洋型（CP）事件的充放电循环较弱。本研究不重复证明暖水能够向东传播，而是把标准化暖水体积输送推进为固定断面的能量输送、固定区域的暖量储存及后续去向。",
    )
    style.add_para(
        doc,
        "由此产生三个缺口：暖量是否继续越过140°W；进入东部后在边界输出、海表热交换和储量之间如何分配；以及相似输入为什么没有产生相似的对流—风场响应。第三个缺口使问题从纯海洋充放电推进到海气耦合效率。",
    )
    style.add_callout(
        doc,
        "一句话答案",
        "暖量到达是海气耦合的必要海洋条件但不是充分条件；耦合是否接通决定风驱Ekman支路，而SSH/密度压力场决定该风驱能否转化为净出口。",
        fill=style.LIGHT_FILL,
    )


def add_data_methods(doc: Document) -> None:
    style.add_section_heading(doc, "2 数据、阶段与方法", page_break=True)
    style.add_para(
        doc,
        "资料设计遵循“海洋同化产品负责动力一致性、独立观测和大气再分析负责外部约束”。SODA3是主线，因为温度、盐度、流速、SSH、风应力和净加热位于一致网格，可计算固定断面输送和控制体预算；OISST、ERA5、GPCP与OLR用于检验海表、对流和风场响应是否独立成立。",
    )
    style.add_table(
        doc,
        "表2  核心资料及其在三个问题中的作用",
        ["资料", "主要变量", "具体作用", "对应问题"],
        [
            ["SODA3.15.2", "温度、盐度、u/v、SSH、D20、风应力、net_heating", "H20/Qwarm,20、三箱预算、OHC/D20和5°N动力分解", "Q1/Q2/Q3"],
            ["OISST v2.1", "SST、FEP、Niño-3.4", "独立约束表面增暖和FEP residual", "Q1/Q3"],
            ["ERA5", "925/850 hPa风、SLP、表面风应力与热通量", "判定大气接通、Jiang东北风和风驱出口", "Q2/Q3"],
            ["GPCP / OLR", "降水、顶层长波辐射", "判断深对流和降水偶极是否形成", "Q3"],
            ["TAO / ORAS5", "OHC、D20、温度断面", "关键时序与符号的独立敏感性约束", "Q1/Q3稳健性"],
        ],
        [1300, 2720, 3700, 1640],
        font_size=8.0,
    )

    doc.add_heading("2.1 区域与阶段", level=2)
    style.add_para(
        doc,
        "CT/CP三箱预算采用10°S—5°N、0—300 m，并分为西箱160°E—180°、中箱180°—140°W和东箱140°W—80°W。合成发展期为Jun(0)—Nov(0)，成熟—衰减期为Dec(0)—May(+1)。1997、2015和2023扩展对照的发展阶段使用Jan(0)—Jun(0)，后期出口使用Jan(+1)—May(+1)。发展期Jiang东北风反馈检验则严格限制在Apr(0)—Jul(0)，不能与次年出口混写。",
    )
    style.add_para(
        doc,
        "所有月异常扣除日历月气候态并去除线性趋势。逐月双向反馈检验覆盖1982—2022年，控制同期Niño-3.4、SST型态和FEP SST，按完整年份置换和bootstrap，避免把同一年Apr—Jun当作独立事件。",
    )

    doc.add_heading("2.2 H20与Qwarm,20：把WWV推进到能量量纲", level=2)
    style.add_equation(
        doc,
        "χ₂₀(T) = max(T − Tᵣ, 0),     Tᵣ = 20 °C",
        "χ₂₀表示温度超过20°C的部分；20°C来自D20和WWV动力学框架，不被解释为绝对热力学零点。",
    )
    style.add_equation(
        doc,
        "H₂₀(t) = ρ₀ cₚ ∭Ω χ₂₀[T(t)] dV",
        "H₂₀是固定区域Ω内20°C阈值以上的相对热含量，单位换算为ZJ。ρ₀=1025 kg m⁻³，cₚ=3990 J kg⁻¹ K⁻¹。",
    )
    style.add_equation(
        doc,
        "Qwarm,₂₀(t) = ρ₀ cₚ ∬Γ vₙ(t) χ₂₀[T(t)] dA",
        "Qwarm,₂₀是穿过固定断面Γ的阈值暖量输送，vₙ为断面法向速度；瞬时单位PW，按每月实际秒数积分后得到ZJ。它不是传统的总海洋热输送ρ₀cₚ∬vₙT dA。",
    )

    doc.add_heading("2.3 固定控制体预算：回答暖量去了哪里", level=2)
    style.add_equation(
        doc,
        "dH₂₀/dt = Cₓ + F₁₀S + F₅N + Qsurface,warm + R₂₀",
        "所有边界项统一以入箱为正；结果部分为了直观讨论，会把5°N北向输出和海表热损失改写为正。Cₓ为东西边界暖量辐合，R₂₀由储量倾向减去全部显式项定义。",
    )
    style.add_para(
        doc,
        "R₂₀不是一种已经识别的物理去向，也不是独立闭合验证。它共同包含垂向交换、混合扩散、跨20°C阈值转换、涡动协方差、同化增量和月平均离散误差。因此第二问能够识别主要显式通道，但不能声称每一焦耳已经获得唯一归宿。",
    )

    doc.add_heading("2.4 海气接通与5°N动力分解", level=2)
    style.add_equation(
        doc,
        "FEPres(m,y) = FEP′(m,y) − [aₘ + bₘ Niño-3.4′(m,y)]",
        "FEPres去除同月Niño-3.4线性相关部分，用于判断远东太平洋是否存在额外先暖；它是统计残差，不自动等同于独立物理强迫。",
    )
    style.add_equation(
        doc,
        "Qtotal = Qgeo + QEkman + Qres,     Mᵧ = −τₓ/(ρ₀f)",
        "5°N总暖量输送分成地转、Ekman和剩余项。τₓ向东为正，北半球西向风应力异常对应北向Ekman输送。Qres按总量减去前两项定义，因此是诊断余量而不是完整动力模态。",
    )
    style.add_table(
        doc,
        "表3  主要符号与物理含义",
        ["符号", "含义", "单位/符号约定"],
        [
            ["T、Tᵣ", "海水温度与20°C参考阈值", "°C"],
            ["χ₂₀", "超过20°C的超温max(T−20,0)", "K"],
            ["H₂₀", "固定箱体20°C以上相对热含量", "ZJ"],
            ["Qwarm,₂₀", "断面阈值暖量输送", "PW；时间积分为ZJ"],
            ["FΓ", "边界Γ对箱体的暖量输入", "入箱为正"],
            ["Cₓ", "东西边界暖量辐合", "入箱为正"],
            ["Qsurface,warm", "作用于暖表层的净表面加热", "海洋吸热为正"],
            ["R₂₀", "未显式解析过程和离散误差的诊断剩余", "不可命名为单一物理过程"],
            ["τₓ、f、Mᵧ", "纬向风应力、科氏参数、经向Ekman体积输送", "τₓ向东为正；Mᵧ向北为正"],
            ["Qgeo/QEkman/Qres", "地转、第一阶Ekman和剩余暖量输送", "三者代数和等于总量"],
        ],
        [1500, 5060, 2800],
        font_size=8.2,
    )


def add_question_one(doc: Document) -> None:
    style.add_section_heading(doc, "3 问题一：暖量是否、以及如何到达东太平洋？", page_break=True)
    style.add_para(
        doc,
        "判断“到达”需要两项同时成立：140°W东向Qwarm,20为正，证明暖量跨越固定断面；东部H20增加，证明固定区域发生储热。两者不要求完全相等，因为东部同时受到南北边界、海表通量和阈值转换影响。OHC、D20和SSH用于补充判断次表层结构是否完成向东调整。",
    )
    style.add_table(
        doc,
        "表4  CT/CP合成的发展期暖量到达（Jun(0)—Nov(0)）",
        ["类型", "140°W东向输入", "东部H20增长", "结论"],
        [
            ["CT", "+6.25 ZJ", "+7.81 ZJ", "输入和储热均较强"],
            ["CP", "+2.97 ZJ", "+3.71 ZJ", "暖量也能到达，但强度较弱"],
        ],
        [1300, 2100, 2100, 3860],
        font_size=8.5,
    )
    style.add_table(
        doc,
        "表5  三个事件的发展期到达（Jan(0)—Jun(0)）",
        ["事件", "140°W东向输入", "东部H20增长", "东部SST", "东部D20"],
        [
            ["1997", "+12.13 ZJ", "+9.29 ZJ", "+0.35°C", "+17.27 m"],
            ["2015", "+3.30 ZJ", "+3.53 ZJ", "+0.98°C", "+15.09 m"],
            ["2023", "+3.91 ZJ", "+3.88 ZJ", "+0.93°C", "+12.03 m"],
        ],
        [1050, 2050, 2050, 2050, 2160],
        font_size=8.3,
    )
    style.add_figure(
        doc,
        "h20_hov",
        "图1  SODA3 H20异常经度—时间演变。1997的暖量东传和东部积累最强；2015与2023均出现东部暖量增加，但幅度和盆地结构不同。本图为项目计算。",
        width=6.25,
    )
    style.add_figure(
        doc,
        "ctcp_fate",
        "图2  CT与CP的三箱暖量到达和成熟—衰减期去向。CT与CP都能把暖量送入东部，但CT具有更强的输入和后期北向放电。本图为项目计算。",
        width=6.1,
    )
    style.add_callout(
        doc,
        "问题一的答案",
        "暖量确实通过赤道上层海洋并越过140°W到达东太平洋；CT强于CP，1997最强，而2015和2023的发展期输入与东部储热非常接近。因此，2023后续较弱不能解释为“暖量没有到达”。",
        fill=style.LIGHT_BLUE,
    )
    style.add_para(
        doc,
        "问题一对海气耦合的约束是提供海洋“燃料条件”：若没有跨140°W输入和东部储热，强耦合难以维持；但有了暖量并不意味着深对流和风场一定响应。2015与2023的相似到达量正好把后续差异收束到“海洋状态如何被大气看见”。",
    )


def add_question_two(doc: Document) -> None:
    style.add_section_heading(doc, "4 问题二：到达后的暖量去了哪里？", page_break=True)
    style.add_para(
        doc,
        "问题二使用成熟—衰减期控制体预算，把东部H20减少分解为5°N北向输出、10°S边界项、海表热损失和剩余项。储量变化是箱体状态变化，不应与边界“通道”等同；剩余项也不能被直接命名为已识别去向。",
    )
    style.add_table(
        doc,
        "表6  CT/CP成熟—衰减期东部暖量分配（Dec(0)—May(+1)）",
        ["类型", "H20变化", "5°N北向输出", "10°S南向输出", "海表热损失", "预算剩余"],
        [
            ["CT", "−7.86", "+2.74", "+0.68", "+3.69", "+2.09"],
            ["CP", "−3.03", "−0.96", "−0.48", "+1.76", "+0.82"],
        ],
        [960, 1380, 1780, 1660, 1700, 1880],
        font_size=8.2,
    )
    style.add_para(doc, "表中单位均为ZJ；输出和热损失以正值展示。CP的5°N负值表示该阶段异常输送仍指向箱内。", indent=False, italic=True, color=style.MUTED, after=6)
    style.add_table(
        doc,
        "表7  三事件次年Jan—May的东部释放",
        ["事件", "5°N总输出", "海表热损失", "东部H20变化", "动力状态"],
        [
            ["1997", "+3.81 ZJ", "+4.37 ZJ", "−9.73 ZJ", "强排放"],
            ["2015", "+0.88 ZJ", "+1.16 ZJ", "−11.10 ZJ", "部分排放"],
            ["2023", "+0.10 ZJ", "+0.40 ZJ", "−9.14 ZJ", "出口受抑或近闭合"],
        ],
        [1050, 1700, 1700, 1900, 3010],
        font_size=8.3,
    )
    style.add_figure(
        doc,
        "event_fate",
        "图3  1997、2015和2023的发展期输入、东部储热、次年5°N输出及海表热损失。2015与2023具有相似输入，但后期去向明显分叉。本图为项目计算。",
        width=6.1,
    )
    style.add_figure(
        doc,
        "dynamic",
        "图4  三事件5°N总暖量输送的Ekman、地转和剩余项分解。1997为地转—Ekman同向排暖；2015由较强Ekman抵消南向地转项；2023的Ekman较弱且被相近的南向地转项抵消。本图为项目计算。",
        width=6.05,
    )
    style.add_callout(
        doc,
        "问题二的答案",
        "东部暖量主要在5°N北向输出、海表热损失和上层海洋储量变化之间重新分配，10°S不是稳健主出口。1997为强排放，2015为部分排放，2023出口近闭合；剩余项仍阻止“每一焦耳完全闭合”的表述。",
        fill=style.LIGHT_BLUE,
    )
    style.add_para(
        doc,
        "问题二对海气耦合的作用必须写成双向关系。发展期和成熟期形成的风应力、表面通量与SSH压力场决定暖量如何分配；随后储量保留或快速排出又影响SST持续性和事件衰减。因此Q2既是耦合后果，也可能构成后期反馈，但不能把所有出口项都当作大气异常的先行原因。",
    )


def add_question_three(doc: Document) -> None:
    style.add_section_heading(doc, "5 问题三：为什么相似到达量产生不同耦合与暖量命运？", page_break=True)
    style.add_para(
        doc,
        "第三问比较的不是“谁的FEP最暖”，而是表面先暖能否获得盆地尺度次表层支撑，并进一步转化为深对流、SLP和风应力响应。海洋侧需要足够的OHC库存以及向东调整的D20/SSH结构；大气侧需要对流能够迁移到中东太平洋并形成持续西风。",
    )
    style.add_table(
        doc,
        "表8  三事件的海洋预置、耦合响应和5°N出口",
        ["事件", "FEP", "中太OHC", "中太u850", "Ekman输出", "地转输出", "总输出"],
        [
            ["1997", "+0.77°C", "+1.73 GJ m⁻²", "+5.25 m s⁻¹", "+3.25 ZJ", "+0.59 ZJ", "+3.81 ZJ"],
            ["2015", "+0.48°C", "+1.44 GJ m⁻²", "+3.37 m s⁻¹", "+2.44 ZJ", "−1.28 ZJ", "+0.88 ZJ"],
            ["2023", "+1.49°C", "+0.50 GJ m⁻²", "+0.29 m s⁻¹", "+1.56 ZJ", "−1.27 ZJ", "+0.10 ZJ"],
        ],
        [950, 1150, 1600, 1500, 1410, 1330, 1420],
        font_size=7.8,
    )
    style.add_figure(
        doc,
        "precondition",
        "图5  FEP表面先暖与盆地次表层预置。2023的FEP很暖，但中太平洋OHC和D20/SSH支撑弱于1997和2015，说明表面起点相似或更强并不代表相同海洋状态。本图为项目计算。",
        width=6.15,
    )
    style.add_figure(
        doc,
        "atmosphere",
        "图6  FEP后的大气接通。1997和2015更容易形成对流东移和中太平洋西风，2023则表现为接通晚、覆盖小、维持短。本图为项目计算。",
        width=6.2,
    )

    doc.add_heading("5.1 Jiang东北风与后期出口是两个阶段的风门", level=2)
    style.add_para(
        doc,
        "Jiang等（2026）提出的发展期东北风位于MJJ、3°—7°N、180°—130°W。项目检验表明，它与同季海面向西风应力高度相关，并能压低中太平洋赤道西风，但没有直接延续成次年Jan—May的5°N局地风应力。因此不能写成“同一股东北风从发展期持续到衰减期并打开出口”。",
    )
    style.add_figure(
        doc,
        "two_stage",
        "图7  两阶段风门：MJJ Jiang型东北风首先约束发展期赤道西风和Bjerknes反馈；成熟—衰减期重新形成的5°N局地应力控制Ekman支路，而SSH/密度压力场控制地转支路。本图为项目计算。",
        width=6.05,
    )

    doc.add_heading("5.2 新的双向检验：暖量流出是否反过来制造东北风？", level=2)
    style.add_para(
        doc,
        "为检验用户提出的反馈假设，进一步计算发展期Q5N(t)是否导致下一月5°—12°N北侧H20增量、SST、降水偶极、SLP梯度和Jiang NE925。全边界Q5N与下一月北侧H20增量近零（r=−0.01）；北侧H20与SST关系稳定（r=+0.42），但H20与降水偶极、SLP梯度和NE925分别约为−0.00、−0.06和−0.03。所需的“储热—大气响应”中介链没有成立。",
    )
    style.add_para(
        doc,
        "东西分区后，110°W—80°W东段出现较弱的Q5N—H20正关系（r=+0.22，p=0.023），但多重检验后q=0.063；该东段H20与NE925仍为r=−0.08。与Jiang区域重叠的140°W—130°W段没有形成H20增量，却具有Q5N(t)—NE925(t+1)关系（r=+0.35，FDR q约0.002）。这说明领先相关不是由已观测到的北侧暖量沉积解释。",
    )
    style.add_figure(
        doc,
        "direction",
        "图8  “5°N流出—北侧增暖—东北风”空间方向检验。西段和Jiang重叠段的Q5N与下一月NE925相关，但没有匹配的H20沉积；东段H20能够投影到SST，却不能继续解释降水、SLP或东北风。本图为项目计算。",
        width=6.25,
    )
    style.add_para(
        doc,
        "反向动力证据更强：NE925与同期Q5N为r=+0.64；控制May Q5N后，May NE925仍能预测June Q5N（r=+0.38）。所以当前最稳妥的结论是，发展期东北风和表面风应力驱动或调制5°N暖量输送；Q5N领先下月东北风的关系可能包含共同大气持续性或双向反馈，但不能写成暖量沉积已经造成东北风。",
    )
    style.add_figure(
        doc,
        "three_event_sequence",
        "图9  1997、2015和2023发展期的Q5N、北侧SST、降水偶极和NE925逐月演变。三个事件不存在统一的“更多北向暖量—更暖北侧SST—更强东北风”排序。本图为项目计算。",
        width=5.75,
    )
    style.add_callout(
        doc,
        "问题三的答案",
        "FEP先暖只描述表面起点。暖量能否形成强耦合取决于盆地尺度次表层支撑和大气可接通背景；成功接通后的风应力直接约束Ekman支路，SSH/密度结构决定地转支路。5°N出口是这一耦合—动力过程的结果和后期反馈，不是Jiang发展期东北风的已证实上游原因。",
        fill=style.LIGHT_BLUE,
    )


def add_synthesis(doc: Document) -> None:
    style.add_section_heading(doc, "6 三事件综合解释与论文逻辑", page_break=True)
    style.add_table(
        doc,
        "表9  1997、2015和2023的“燃料—点火—分配”对照",
        ["事件", "问题一：海洋燃料", "问题三：耦合接通", "问题二：暖量分配", "最终解释"],
        [
            ["1997", "输入和东部储热最强，盆地OHC与D20/SSH支撑完整", "对流和西风较早、较强并持续", "Ekman与地转同向，北向输出和散热均强", "强协同排放"],
            ["2015", "输入约为1997三分之一，但次表层预置充分", "大气接通较完整", "Ekman较强，克服南向地转项后仍有净输出", "风驱部分排放"],
            ["2023", "输入和东部储热与2015接近，但中太OHC支撑弱", "接通晚、覆盖小、维持短", "Ekman较弱且被南向地转项抵消，出口近闭合", "到达但未高效转化"],
        ],
        [900, 2250, 2000, 2480, 1730],
        font_size=7.8,
    )
    style.add_para(
        doc,
        "因此全文不应按“到达—去向—最后再补耦合”的单向叙述书写，而应在问题编号不变的前提下采用机制顺序1→3→2：先建立海洋燃料基础，再判断耦合是否接通，最后解释风应力、表面热通量和压力场如何决定成熟—衰减期去向。",
    )
    style.add_callout(
        doc,
        "论文主命题",
        "相似的东部暖量到达可以产生不同的ENSO命运，因为海洋热量转化为大气对流—风场响应的效率不同；这种耦合效率随后通过Ekman—地转竞争控制5°N暖量出口和事件衰减。",
        fill=style.LIGHT_FILL,
    )

    doc.add_heading("6.1 可以支持的结论", level=2)
    style.add_table(
        doc,
        "表10  结论强度与允许措辞",
        ["结论", "支撑程度", "建议措辞"],
        [
            ["暖量越过140°W并进入东部", "强", "CT和CP均有到达，CT更强；2015与2023输入近似"],
            ["主要显式去向为5°N输出、海表热损失和储量变化", "中—强", "主要通道已量化，但剩余项尚未物理拆分"],
            ["2015/2023后期出口差异主要投影到Ekman项", "诊断框架内强", "风驱暖量输送增强使净出口超过或未超过南向地转项"],
            ["5°N流出导致Jiang东北风", "不支持", "发展期东北风更可能驱动/调制输送；未发现北侧储热中介"],
            ["外海盆或某单一因素决定2023", "尚不足", "列为候选上游背景，等待受控模式集合"],
        ],
        [2500, 1400, 5460],
        font_size=8.0,
    )

    doc.add_heading("6.2 尚未解决的边界", level=2)
    style.add_table(
        doc,
        "表11  当前不足与下一步",
        ["不足", "对当前结论的影响", "下一步"],
        [
            ["欧拉预算而非拉格朗日水团追踪", "证明控制体通道，不能证明同一水团连续轨迹", "粒子/水团标签或伴随诊断"],
            ["R₂₀仍包含多种过程", "不能声称每一焦耳获得唯一归宿", "五日三维热收支、垂向通量和同化增量"],
            ["2024年5°N通量面对温度插值敏感", "2023净方向可变，但出口受抑稳健", "独立再分析、TAO及多种通量面"],
            ["事件样本有限", "统计关系不能自动变成普适因果定律", "延长资料并做多产品重复"],
            ["离线换风不允许海洋响应", "只能隔离局地风驱敏感性", "耦合模式或AGCM/海洋模式因子试验"],
        ],
        [2700, 3900, 2760],
        font_size=8.0,
    )
    style.add_callout(
        doc,
        "最终完成度",
        "问题一主体解决；问题二主要显式通道解决但残差未完全拆分；问题三已形成“次表层支撑—大气接通—Ekman/地转出口”的机制证据，同时排除了把5°N出口直接写成Jiang东北风上游原因的简单反馈链。",
        fill=style.LIGHT_BLUE,
    )


def add_references(doc: Document) -> None:
    style.add_section_heading(doc, "参考文献", page_break=True)
    refs = [
        ("Jin, F.-F. (1997). An equatorial ocean recharge paradigm for ENSO. Part I: Conceptual model. Journal of the Atmospheric Sciences, 54, 811–829.", "https://doi.org/10.1175/1520-0469(1997)054%3C0811:AEORPF%3E2.0.CO;2"),
        ("Meinen, C. S., & McPhaden, M. J. (2000). Observations of warm water volume changes in the equatorial Pacific and their relationship to El Niño and La Niña. Journal of Climate, 13, 3551–3559.", "https://doi.org/10.1175/1520-0442(2000)013%3C3551:OOWWVC%3E2.0.CO;2"),
        ("Bosc, C., & Delcroix, T. (2008). Observed equatorial Rossby waves and ENSO-related warm water volume changes in the equatorial Pacific Ocean. Journal of Geophysical Research: Oceans, 113, C06003.", "https://doi.org/10.1029/2007JC004613"),
        ("Carton, J. A., Chepurin, G. A., & Chen, L. (2018). SODA3: A new ocean climate reanalysis. Journal of Climate, 31, 6967–6983.", "https://doi.org/10.1175/JCLI-D-18-0149.1"),
        ("Huguenin, M. F., Holmes, R. M., & England, M. H. (2020). Key role of diabatic processes in regulating warm water volume variability over ENSO events. Journal of Climate, 33, 9783–9801.", "https://doi.org/10.1175/JCLI-D-20-0198.1"),
        ("Chakravorty, S., Perez, R. C., Gnanaseelan, C., & Anderson, B. T. (2021). Revisiting the recharge and discharge processes for different flavors of El Niño. Journal of Geophysical Research: Oceans, 126, e2020JC017075.", "https://doi.org/10.1029/2020JC017075"),
        ("Verdy, A., Mazloff, M. R., Cornuelle, B. D., & Kim, S. B. (2023). Balancing volume, temperature, and salinity budgets during 2014–2018 in the Tropical Pacific Ocean State Estimate. Journal of Geophysical Research: Oceans, 128, e2022JC019576.", "https://doi.org/10.1029/2022JC019576"),
        ("Peng, Q., et al. (2025). Strong 2023–2024 El Niño generated by ocean dynamics. Nature Geoscience, 18, 471–478.", "https://doi.org/10.1038/s41561-025-01700-9"),
        ("Jiang, L., Chen, H.-C., Zhang, W., & Tseng, Y.-H. (2026). Geophysical Research Letters.", "https://doi.org/10.1029/2026GL123227"),
    ]
    for index, (citation, url) in enumerate(refs, start=1):
        style.add_reference(doc, index, citation, url)
    style.add_para(
        doc,
        "图件来源说明：图1—图9均由本项目脚本从SODA3、OISST、ERA5、GPCP/OLR等本地数据产物绘制；正文未直接复制外部论文图件。",
        indent=False,
        italic=True,
        color=style.MUTED,
    )


def build_report() -> Path:
    doc = Document()
    style.configure_document(doc)
    set_header_footer(doc)
    props = doc.core_properties
    props.title = "厄尔尼诺暖量的到达、去向与耦合命运：三个核心问题完整报告"
    props.subject = "以海气耦合约束重新连接暖量到达、耦合接通与暖量分配"
    props.author = "Daiyue"
    props.keywords = "ENSO; SODA3; H20; Qwarm20; warm heat fate; air-sea coupling; Jiang northeasterly; Ekman; geostrophic"
    props.comments = "Revised complete three-question report generated from verified project outputs on 2026-08-08."

    cover(doc)
    add_framework(doc)
    add_data_methods(doc)
    add_question_one(doc)
    add_question_two(doc)
    add_question_three(doc)
    add_synthesis(doc)
    add_references(doc)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(build_report())
