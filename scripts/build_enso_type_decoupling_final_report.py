#!/usr/bin/env python3
"""Build the final Chinese research report for ENSO type and decoupling."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/type_coupling"
PDF = ROOT / "output/pdf/enso_type_formation_decoupling_final_report_cn.pdf"
MD = OUT / "ENSO_TYPE_FORMATION_DECOUPLING_FINAL_REPORT_CN.md"

OCEAN_STATS = DERIVED / "enso_type_east_ocean_state_correlations.csv"
SEASONAL = DERIVED / "enso_full_year_coupling_event_seasonal.csv"
ALL_YEAR = DERIVED / "enso_full_year_coupling_all_year_seasonal_1982_2023.csv"
OCEAN_CONDITIONED = (
    DERIVED / "enso_ocean_conditioned_decoupling_event_summary.csv"
)
CANDIDATE = DERIVED / "enso_decoupling_candidate_correlations.csv"
FIG_FULL_YEAR = OUT / "enso_full_year_coupling_evolution.png"
FIG_OCEAN_CONDITIONED = OUT / "enso_ocean_conditioned_decoupling.png"


FONT_PATH = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
FONT = "ArialUnicode"
NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2166AC")
PALE_BLUE = colors.HexColor("#EAF2F8")
PALE_ORANGE = colors.HexColor("#FCEFE6")
GRAY = colors.HexColor("#555555")
LIGHT_GRAY = colors.HexColor("#F3F4F5")
RED = colors.HexColor("#B2182B")


def format_link(url: str, label: str) -> str:
    return f'<link href="{url}" color="#2166AC">{label}</link>'


def build_markdown(
    ocean_stats: pd.DataFrame,
    seasonal: pd.DataFrame,
    all_year: pd.DataFrame,
    ocean_conditioned: pd.DataFrame,
    candidate: pd.DataFrame,
) -> str:
    stats = ocean_stats.set_index("variable")
    y2023 = seasonal.loc[seasonal["year"].eq(2023)].set_index("season")
    ranks = all_year.loc[all_year["year"].eq(2023)].set_index("season")
    ocean_2023 = ocean_conditioned.loc[
        (ocean_conditioned["year"].eq(2023))
        & (ocean_conditioned["season"].eq("DJF"))
    ].iloc[0]
    wwv = candidate.loc[
        candidate["predictor"].eq("wwv_west_detrended_z")
    ].set_index("target")
    q = stats.loc["q140_mar_apr_z"]
    d = stats.loc["d140_mar_apr_z"]
    joint = stats.loc["east_ocean_state_z"]
    return f"""# ENSO类型形成与海气脱耦主线研究报告

版本：2026-07-31

## 一句话结论

在已经进入暖事件发展的条件下，3-4月140°W的SODA3暖水热输送Q20和
D20储存状态是目前与成熟EP-CP型态联系最强的海洋量；但海洋建立偏东
型异常并不保证大气反馈接上。2023正是“海洋偏东建立 + 大气效率异常
偏弱”的代表。当前尚未找到一个跨事件稳定、可单独预测脱耦的SODA3
前兆量。

## 核心证据

- Q20与成熟DJF `Niño3-Niño4`：r={q.pearson_r_with_mature_type:+.3f}，
  95% bootstrap CI [{q.bootstrap_ci_low:+.3f}, {q.bootstrap_ci_high:+.3f}]，
  FDR q={q.bh_fdr_q:.4f}。
- D20：r={d.pearson_r_with_mature_type:+.3f}，
  CI [{d.bootstrap_ci_low:+.3f}, {d.bootstrap_ci_high:+.3f}]，
  FDR q={d.bh_fdr_q:.4f}。
- 二者等权海洋状态：r={joint.pearson_r_with_mature_type:+.3f}，
  CI [{joint.bootstrap_ci_low:+.3f}, {joint.bootstrap_ci_high:+.3f}]，
  FDR q={joint.bh_fdr_q:.4f}。
- 删除1982、1997、2015三个经典强EP后，上述相关降为
  {q.non_classic_ep_r:+.3f}、{d.non_classic_ep_r:+.3f}和
  {joint.non_classic_ep_r:+.3f}，说明强度依赖EP端点，不是硬阈值。
- 2023型态调整后的综合耦合残差从AMJ
  {y2023.loc['AMJ', 'coupling_pattern_residual_z']:+.2f} z降至DJF
  {y2023.loc['DJF', 'coupling_pattern_residual_z']:+.2f} z。
- 2023在42年DJF参考分布中，ERA5/GPCP综合排名
  {int(ranks.loc['DJF', 'coupling_pattern_residual_z_lower_rank'])}/42，
  NCEP风压排名
  {int(ranks.loc['DJF', 'ncep_coupling_pattern_residual_z_lower_rank'])}/42，
  GPCP降水排名
  {int(ranks.loc['DJF', 'precip_pattern_residual_z_lower_rank'])}/42。
- 再给定春季海洋状态，2023 DJF综合响应为
  {ocean_2023.coupling_pattern_residual_z_given_ocean_z:+.2f} z，
  是13暖事件最弱；GPCP降水为
  {ocean_2023.precip_pattern_residual_z_given_ocean_z:+.2f} z，
  同样最弱。
- 去趋势西太平洋WWV与DJF综合残差只有
  r={wwv.loc['coupling_pattern_residual_z', 'pearson_r']:+.2f}
  （FDR q={wwv.loc['coupling_pattern_residual_z', 'bh_fdr_q']:.2f}），
  不能作为通用脱耦指标。

## 研究框架

### 1. 海洋分型坐标

`Q20_140W = rho*Cp*integral[u*max(T-20°C,0) dz dy]`

区域为5°S-5°N、0-300 m，正值表示向东。D20是20°C等温面深度。
Q20表示暖水是否送到140°W，D20表示到达后是否形成持续储存。

### 2. 大气耦合效率坐标

逐日历月用1982-2014历史资料拟合：

`A = beta0 + beta1*year + beta2*Nino3.4 + beta3*(Nino3-Nino4) + error`

标准化残差 `error/sigma` 为型态调整后的耦合效率。A分别取GPCP热带
太平洋降水、ERA5西减东SLP梯度、ERA5中西太平洋纬向风应力；另用
NCEP中太平洋近地层纬向风和Tahiti-Darwin压力差独立检查。

### 3. 反馈链定位

分别估计SST梯度到降水、降水到SLP、SLP到风应力的历史条件残差。
2023 AMJ-JJA首先表现为风端偏弱；SON-DJF时最主要异常转移到
SST到降水/对流端。

## 关键否证

1. `140°W减去日界线/170°W`的相对穿透分数与类型相关很弱，因为强EP
   同时加深中太平洋D20，做差删掉了共同的盆地调整。
2. 1-6月资料不足以称2023“强脱耦”；真正罕见的综合异常在JJA后发展，
   DJF最清楚。
3. CP不等于脱耦。加入EP-CP型态以后，CP复合响应接近历史预期。
4. 西太平洋WWV解释2023/2009路径有物理意义，但跨13事件没有通过FDR。
5. 这些结果是观测诊断，不是因果实验，也不是厄尔尼诺发生预测器。

## 权威研究对照

- Chen et al. (2015)：西风爆发与初始海洋态共同塑造ENSO多样性。
- Li et al. (2024)：将Bjerknes反馈拆成SST-降水加热-气压-风应力过程，
  并指出2000年后反馈中心西移。
- Kim et al. (2025)：2023春季持续东风、西部热量滞留、负NPMM及
  菲律宾海D20加深。
- Peng et al. (2025)：海洋初值可在4月后无风反馈时解释6-12月增暖的
  87%，印度洋/大西洋增暖及背景趋势抑制太平洋风响应。
- Zhao et al. (2025)：2023年7月印度季风-海洋大陆和TNA异常加热共同
  造成中西太平洋异常东风。
- Zhang et al. (2025)：2023/24热带太平洋降水异常仅约三个超级
  厄尔尼诺的三分之一，导致PNA遥相关异常弱。
- Fan et al. (2026)：多年拉尼娜积累西部暖水，减弱西部非线性动力
  冷却，使增暖向西延伸和上升运动更均匀，从而压低西风。
- Jiang et al. (2026)：残余FEP暖异常可产生经向降水偶极和进入中太平洋
  的偏北风，抵消西风。

这些机制并不互斥。本研究的观测时序支持“先风响应偏弱，后成熟对流
加热显著不足”，但当前箱平均指标不能区分外部海盆强迫、热带太平洋
内部机制和FEP经向偶极各自的因果贡献。

## 最终判断

本主线已经形成观测诊断闭环：

`西部预条件 -> 140°W暖水输送 -> D20/热含量储存 -> 成熟SST位置`

与

`SST幅度和位置 -> 降水加热 -> SLP/Walker环流 -> 西风应力`

必须分开。经典EP通常两条都强；CP主要是第一条停在中部，而第二条
对其空间型态可以正常；2023第一条足以建立偏东暖事件，但第二条从
夏季开始偏弱，成熟期在降水端达到极端。

尚未完成的是因果闭环。下一步最有价值的新增量不是继续优化单一TSI，
而是加入印度洋/大西洋SST和加热、印度季风-海洋大陆降水、TNA降水、
NPMM、FEP经向降水偶极、西风爆发和西太平洋非线性热收支，并用AGCM
敏感性试验和伪实时检验判断哪些量真正提供独立预测信息。

## 产出

- `output/pdf/enso_full_year_coupling_evolution.pdf`
- `output/pdf/enso_ocean_conditioned_decoupling.pdf`
- `data/derived/research_2026/enso_type_east_ocean_state_correlations.csv`
- `data/derived/research_2026/enso_full_year_coupling_all_year_seasonal_1982_2023.csv`
- `data/derived/research_2026/enso_ocean_conditioned_decoupling_event_summary.csv`
- `data/derived/research_2026/enso_decoupling_candidate_correlations.csv`
"""


def register_font() -> None:
    if not FONT_PATH.exists():
        raise FileNotFoundError(FONT_PATH)
    pdfmetrics.registerFont(TTFont(FONT, str(FONT_PATH)))


def paragraph_text(text: str) -> str:
    replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\n": "<br/>",
    }
    output = text
    for old, new in replacements.items():
        output = output.replace(old, new)
    return output


def report_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "CNTitle",
            parent=base["Title"],
            fontName=FONT,
            fontSize=23,
            leading=31,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "CNSubtitle",
            parent=base["Normal"],
            fontName=FONT,
            fontSize=10.5,
            leading=16,
            textColor=GRAY,
            alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "CNH1",
            parent=base["Heading1"],
            fontName=FONT,
            fontSize=16,
            leading=23,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "CNH2",
            parent=base["Heading2"],
            fontName=FONT,
            fontSize=12.5,
            leading=18,
            textColor=BLUE,
            spaceBefore=8,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "CNBody",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9.3,
            leading=15,
            textColor=colors.HexColor("#222222"),
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "CNBullet",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9.1,
            leading=14.2,
            leftIndent=14,
            firstLineIndent=-9,
            bulletIndent=4,
            spaceAfter=3,
        ),
        "callout": ParagraphStyle(
            "CNCallout",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=11,
            leading=18,
            textColor=NAVY,
            leftIndent=12,
            rightIndent=12,
            spaceBefore=8,
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "CNCaption",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=7.8,
            leading=11.5,
            textColor=GRAY,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "small": ParagraphStyle(
            "CNSmall",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=7.6,
            leading=11.5,
            textColor=GRAY,
        ),
    }


def make_table(
    data: list[list[str]],
    widths: list[float],
    styles: dict[str, ParagraphStyle],
    header: bool = True,
) -> Table:
    converted = []
    for row_index, row in enumerate(data):
        style = styles["small"]
        converted.append(
            [Paragraph(paragraph_text(str(cell)), style) for cell in row]
        )
    table = Table(
        converted,
        colWidths=widths,
        repeatRows=1 if header else 0,
        hAlign="LEFT",
    )
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9CDD2")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ]
    table.setStyle(TableStyle(commands))
    return table


def add_bullets(
    story: list,
    items: list[str],
    styles: dict[str, ParagraphStyle],
) -> None:
    for item in items:
        story.append(
            Paragraph(
                "• " + paragraph_text(item),
                styles["bullet"],
            )
        )


def add_paragraphs(
    story: list,
    paragraphs: list[str],
    styles: dict[str, ParagraphStyle],
) -> None:
    for text in paragraphs:
        story.append(Paragraph(paragraph_text(text), styles["body"]))


def page_decor(canvas, doc) -> None:
    canvas.saveState()
    page = canvas.getPageNumber()
    width, height = A4
    if page > 1:
        canvas.setStrokeColor(colors.HexColor("#D5D9DE"))
        canvas.line(1.7 * cm, height - 1.25 * cm, width - 1.7 * cm, height - 1.25 * cm)
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(GRAY)
        canvas.drawString(
            1.7 * cm,
            height - 1.02 * cm,
            "ENSO类型形成与海气脱耦主线研究",
        )
        canvas.drawRightString(
            width - 1.7 * cm,
            0.85 * cm,
            f"{page}",
        )
    canvas.restoreState()


def build_pdf(
    ocean_stats: pd.DataFrame,
    seasonal: pd.DataFrame,
    all_year: pd.DataFrame,
    ocean_conditioned: pd.DataFrame,
    candidate: pd.DataFrame,
) -> None:
    register_font()
    styles = report_styles()
    doc = SimpleDocTemplate(
        str(PDF),
        pagesize=A4,
        rightMargin=1.65 * cm,
        leftMargin=1.65 * cm,
        topMargin=1.55 * cm,
        bottomMargin=1.45 * cm,
        title="ENSO类型形成与海气脱耦主线研究报告",
        author="Codex research workflow",
    )
    story: list = []
    stats = ocean_stats.set_index("variable")
    q = stats.loc["q140_mar_apr_z"]
    d = stats.loc["d140_mar_apr_z"]
    joint = stats.loc["east_ocean_state_z"]
    y2023 = seasonal.loc[seasonal["year"].eq(2023)].set_index("season")
    ranks = all_year.loc[all_year["year"].eq(2023)].set_index("season")
    ocean_2023 = ocean_conditioned.loc[
        (ocean_conditioned["year"].eq(2023))
        & (ocean_conditioned["season"].eq("DJF"))
    ].iloc[0]
    groups = (
        seasonal.loc[
            seasonal["group"].isin(
                ["classic EP", "CP", "2023 weak-coupling EP"]
            )
        ]
        .groupby(["group", "season"], as_index=False)
        .mean(numeric_only=True)
    )

    story += [
        Spacer(1, 2.1 * cm),
        Paragraph("ENSO类型形成与海气脱耦", styles["title"]),
        Paragraph("主线研究报告", styles["title"]),
        Spacer(1, 0.45 * cm),
        Paragraph(
            "SODA3 - OISST - GPCP - ERA5 - NCEP<br/>"
            "1982-2024观测与再分析诊断",
            styles["subtitle"],
        ),
        Spacer(1, 1.1 * cm),
        Table(
            [[Paragraph(
                "核心判断：EP-CP分型首先取决于暖水是否送到并储存在中东"
                "太平洋；海气耦合效率是另一维度。2023不是“海洋没有"
                "形成EP”，而是“海洋已偏东、大气后来没有按通常效率接上”。",
                styles["callout"],
            )]],
            colWidths=[16.0 * cm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                    ("BOX", (0, 0), (-1, -1), 1.0, BLUE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
                ]
            ),
        ),
        Spacer(1, 2.2 * cm),
        Paragraph("最终版：2026-07-31", styles["subtitle"]),
        Paragraph(
            "研究性质：事件条件下的机制诊断，不是厄尔尼诺发生预测器",
            styles["subtitle"],
        ),
        PageBreak(),
    ]

    story.append(Paragraph("执行摘要", styles["h1"]))
    evidence_rows = [
        ["研究问题", "最强证据", "结论边界"],
        [
            "CP还是EP？",
            f"3-4月Q20@140°W r={q.pearson_r_with_mature_type:+.3f}；"
            f"D20 r={d.pearson_r_with_mature_type:+.3f}；联合"
            f"r={joint.pearson_r_with_mature_type:+.3f}",
            "13个暖事件；依赖经典强EP端点；不是固定阈值",
        ],
        [
            "CP是否等于脱耦？",
            "加入Niño3-Niño4型态后，CP复合响应接近历史预期",
            "CP主要是响应位置偏中部，不能自动叫弱耦合",
        ],
        [
            "2023何时脱耦？",
            "AMJ不异常；JJA先出现风不足；DJF综合第3/42、降水第1/42",
            "季节顺序是观测诊断，不能单独证明因果",
        ],
        [
            "西部WWV能否预测脱耦？",
            "去趋势WWV与DJF综合残差r=-0.20，未通过FDR",
            "能解释2023/2009路径，尚不是跨事件通用指标",
        ],
    ]
    story.append(make_table(evidence_rows, [3.0 * cm, 7.6 * cm, 5.4 * cm], styles))
    story.append(Spacer(1, 0.3 * cm))
    add_paragraphs(
        story,
        [
            "本研究最终没有把TSI继续包装成单一预测量，而是将问题拆成"
            "“海洋分型”和“大气耦合效率”两个正交坐标。这个拆分解决了"
            "此前最容易混淆的地方：FEP偏暖、总WWV偏高、形成EP型、出现"
            "强Bjerknes反馈并不是同一件事。",
            "观测闭环已经完成：我们能说明暖水从哪里通过、在哪里储存，"
            "也能说明大气响应从哪个季节、哪一环开始偏离历史关系。因果"
            "闭环尚未完成：外部海盆加热、热带太平洋内部西向增暖机制与"
            "FEP经向对流偶极需要通过敏感性试验分离。",
        ],
        styles,
    )

    story.append(Paragraph("1. 科学问题与两个坐标", styles["h1"]))
    story.append(Paragraph("1.1 海洋分型坐标", styles["h2"]))
    add_paragraphs(
        story,
        [
            "成熟类型采用去趋势DJF Niño3-Niño4连续指标。正值偏EP，"
            "负值偏CP。主海洋量取3-4月140°W：Q20表示暖水是否继续"
            "向东输送，D20表示到达后温跃层是否加深并形成储存。",
            "Q20定义为 rho*Cp*integral[u*max(T-20°C,0) dz dy]，"
            "区域为5°S-5°N、0-300 m，正值为向东。联合状态只用于"
            "机制摘要；物理解释和敏感性检验始终保留Q20与D20两项。",
        ],
        styles,
    )
    story.append(Paragraph("1.2 大气耦合效率坐标", styles["h2"]))
    add_paragraphs(
        story,
        [
            "逐日历月用1982-2014建立历史条件关系：A = beta0 + "
            "beta1*year + beta2*Niño3.4 + beta3*(Niño3-Niño4) + error。"
            "标准化error表示在控制SST总体幅度和EP-CP位置后，大气响应"
            "比历史关系强或弱多少。",
            "A分别取GPCP 180°-110°W热带太平洋降水、ERA5西减东"
            "SLP梯度和ERA5 160°E-140°W表面纬向风应力。NCEP近地层"
            "中太平洋纬向风及Tahiti-Darwin压力差作为独立检查。",
        ],
        styles,
    )
    story.append(PageBreak())

    story.append(Paragraph("2. 数据、样本与检验", styles["h1"]))
    data_rows = [
        ["资料", "用途", "时间/处理"],
        ["SODA3.15.2", "Q20、D20、热含量与暖水体", "1980-2024；同月异常"],
        ["OISST", "Niño3、Niño4、Niño3.4与SST梯度", "1982-2024；年趋势入模"],
        ["GPCP v2.3", "热带太平洋降水与东西梯度", "1982-2024"],
        ["ERA5", "SLP与表面纬向风应力", "1982-2024"],
        ["NCEP", "独立风与压力/SOI型检查", "1982-2024"],
    ]
    story.append(make_table(data_rows, [3.0 * cm, 7.1 * cm, 5.9 * cm], styles))
    story.append(Spacer(1, 0.25 * cm))
    add_bullets(
        story,
        [
            "暖事件共13个：1982、1986、1991、1994、1997、2002、"
            "2004、2006、2009、2015、2018、2019、2023。",
            "经典EP复合：1982、1997、2015；CP复合：1994、2004、2019。"
            "成熟类型仍以连续指标报告，不把边界事件硬塞入二元类别。",
            "历史期内对目标年采用留一年拟合；海洋状态相关用40,000次"
            "置换、20,000次bootstrap和Benjamini-Hochberg FDR。",
            "42年排名使用每个季节完全相同的条件残差，1/42代表最弱。"
            "给定海洋状态后的事件残差再做留一事件拟合。",
        ],
        styles,
    )
    story.append(Paragraph("3. 先记录失败的假设", styles["h1"]))
    failure_rows = [
        ["假设", "结果", "保留的认识"],
        [
            "140°W减日界线/170°W越大越EP",
            "联合相对穿透与类型r=+0.158，FDR q=0.789",
            "强EP也加深中太平洋，做差删掉共同信号；改用绝对Q20、D20",
        ],
        [
            "2023春季已经强脱耦",
            "AMJ型态调整综合残差+0.18 z，42年排24/42",
            "春季不异常；必须延伸到全年",
        ],
        [
            "CP就是海气脱耦",
            "CP型态调整后JJA、SON、DJF接近或略高于零",
            "响应中心不同不等于效率低",
        ],
        [
            "西太平洋WWV是通用脱耦前兆",
            "DJF综合r=-0.20；NCEP风压r=-0.34；均未通过FDR",
            "是特定路径机制，不是单量通用预测器",
        ],
    ]
    story.append(make_table(failure_rows, [4.0 * cm, 5.5 * cm, 6.5 * cm], styles))
    story.append(PageBreak())

    story.append(Paragraph("4. CP-EP分型结果", styles["h1"]))
    ocean_rows = [
        ["量", "Pearson r", "95% bootstrap CI", "FDR q", "删去3强EP后的r"],
        [
            "Q20@140°W",
            f"{q.pearson_r_with_mature_type:+.3f}",
            f"[{q.bootstrap_ci_low:+.3f}, {q.bootstrap_ci_high:+.3f}]",
            f"{q.bh_fdr_q:.4f}",
            f"{q.non_classic_ep_r:+.3f}",
        ],
        [
            "D20@140°W",
            f"{d.pearson_r_with_mature_type:+.3f}",
            f"[{d.bootstrap_ci_low:+.3f}, {d.bootstrap_ci_high:+.3f}]",
            f"{d.bh_fdr_q:.4f}",
            f"{d.non_classic_ep_r:+.3f}",
        ],
        [
            "等权东部海洋状态",
            f"{joint.pearson_r_with_mature_type:+.3f}",
            f"[{joint.bootstrap_ci_low:+.3f}, {joint.bootstrap_ci_high:+.3f}]",
            f"{joint.bh_fdr_q:.4f}",
            f"{joint.non_classic_ep_r:+.3f}",
        ],
    ]
    story.append(make_table(ocean_rows, [4.1 * cm, 2.2 * cm, 4.0 * cm, 2.0 * cm, 3.7 * cm], styles))
    add_paragraphs(
        story,
        [
            "逐一删除任一事件后，Q20、D20和联合状态的最低相关仍分别为"
            f"{q.leave_one_out_min_r:+.3f}、{d.leave_one_out_min_r:+.3f}和"
            f"{joint.leave_one_out_min_r:+.3f}。所以信号不是由某一个"
            "事件单独制造；但删除三个强EP后明显衰减，说明它更擅长识别"
            "典型或强EP端点，而不是在所有边界事件间给出硬分类。",
            "物理解释因此应写成两步：暖水先穿过140°W，然后当地D20和"
            "上层热含量建立。西部总WWV只说明盆地是否有可用暖水，不"
            "决定这些暖水最后停在中部还是继续进入东部。",
        ],
        styles,
    )
    story.append(Spacer(1, 0.15 * cm))
    if FIG_FULL_YEAR.exists():
        image = Image(str(FIG_FULL_YEAR))
        aspect = image.imageHeight / image.imageWidth
        image.drawWidth = 16.7 * cm
        image.drawHeight = aspect * image.drawWidth
        story.append(image)
        story.append(
            Paragraph(
                "图1. 全年演变把类型形成与耦合效率分开。左下为2023"
                "反馈链，右下为Q20-D20二维海洋状态。",
                styles["caption"],
            )
        )
    story.append(PageBreak())

    story.append(Paragraph("5. 2023脱耦的季节顺序", styles["h1"]))
    season_rows = [["季节", "综合残差", "GPCP降水", "ERA5 SLP", "ERA5风应力", "NCEP风", "42年综合排名"]]
    for season in ["AMJ", "JJA", "SON", "DJF"]:
        row = y2023.loc[season]
        rank = ranks.loc[season]
        season_rows.append(
            [
                season,
                f"{row.coupling_pattern_residual_z:+.2f}",
                f"{row.precip_pattern_residual_z:+.2f}",
                f"{row.slp_pattern_residual_z:+.2f}",
                f"{row.tau_pattern_residual_z:+.2f}",
                f"{row.ncep_u_pattern_residual_z:+.2f}",
                f"{int(rank.coupling_pattern_residual_z_lower_rank)}/42",
            ]
        )
    story.append(
        make_table(
            season_rows,
            [1.6 * cm, 2.5 * cm, 2.4 * cm, 2.2 * cm, 2.3 * cm, 2.2 * cm, 2.8 * cm],
            styles,
        )
    )
    story.append(Spacer(1, 0.25 * cm))
    chain_rows = [["季节", "SST→降水", "降水→SLP", "SLP→风应力", "最弱环节"]]
    for season in ["AMJ", "JJA", "SON", "DJF"]:
        row = y2023.loc[season]
        values = {
            "SST→降水": row.sst_to_precip_residual_z,
            "降水→SLP": row.precip_to_slp_residual_z,
            "SLP→风应力": row.slp_to_tau_residual_z,
        }
        weakest = min(values, key=values.get)
        chain_rows.append(
            [
                season,
                f"{values['SST→降水']:+.2f}",
                f"{values['降水→SLP']:+.2f}",
                f"{values['SLP→风应力']:+.2f}",
                weakest,
            ]
        )
    story.append(make_table(chain_rows, [2.0 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm, 5.0 * cm], styles))
    add_paragraphs(
        story,
        [
            "AMJ的综合响应并不异常。JJA时独立NCEP风已降到-0.92 z，"
            "在42年同季节中排第6弱；SON进一步到第5弱。此时更像是"
            "压力场存在响应，但中西太平洋西风没有完全接上。",
            "到SON-DJF，SST到降水的条件残差转为显著负值。成熟DJF中"
            "综合残差和NCEP风压均排第3/42，GPCP降水为-1.75 z并排"
            "第1/42。因此完整时序是“夏季风响应先不足，成熟期主要"
            "失配集中到对流加热”。",
        ],
        styles,
    )
    story.append(Paragraph("6. 给定海洋状态后的异常", styles["h1"]))
    ocean_condition_rows = [
        ["2023 DJF量", "给定海洋状态后的残差", "13暖事件下尾排名"],
        [
            "ERA5/GPCP综合",
            f"{ocean_2023.coupling_pattern_residual_z_given_ocean_z:+.2f} z",
            f"{int(ocean_2023.coupling_pattern_residual_z_given_ocean_z_lower_rank)}/13",
        ],
        [
            "NCEP风压综合",
            f"{ocean_2023.ncep_coupling_pattern_residual_z_given_ocean_z:+.2f} z",
            f"{int(ocean_2023.ncep_coupling_pattern_residual_z_given_ocean_z_lower_rank)}/13",
        ],
        [
            "GPCP降水",
            f"{ocean_2023.precip_pattern_residual_z_given_ocean_z:+.2f} z",
            f"{int(ocean_2023.precip_pattern_residual_z_given_ocean_z_lower_rank)}/13",
        ],
        [
            "NCEP纬向风",
            f"{ocean_2023.ncep_u_pattern_residual_z_given_ocean_z:+.2f} z",
            f"{int(ocean_2023.ncep_u_pattern_residual_z_given_ocean_z_lower_rank)}/13",
        ],
    ]
    story.append(make_table(ocean_condition_rows, [5.2 * cm, 6.0 * cm, 4.8 * cm], styles))
    add_paragraphs(
        story,
        [
            "2023春季联合东部海洋状态为+0.70 z，不是低值。与13暖事件"
            "中同等海洋状态通常对应的大气响应相比，2023成熟期综合"
            "响应为-2.89 z，GPCP降水为-3.38 z。这个二次条件检验把"
            "“海洋足够偏东”和“大气反馈仍然很弱”同时表达出来。",
            "这里的z值来自只有12个训练事件的留一拟合，只适合作为事件"
            "内异常度，不应解释成总体重现概率。",
        ],
        styles,
    )
    story.append(PageBreak())

    story.append(Paragraph("7. 通用脱耦前兆检验", styles["h1"]))
    candidate_rows = [["春季候选量", "成熟响应", "Pearson r", "95% CI", "FDR q"]]
    for _, row in candidate.iterrows():
        candidate_rows.append(
            [
                "西部WWV" if row.predictor == "wwv_west_detrended_z" else "东减西SST梯度",
                {
                    "coupling_pattern_residual_z": "ERA5/GPCP",
                    "ncep_coupling_pattern_residual_z": "NCEP风压",
                    "precip_pattern_residual_z": "GPCP降水",
                    "ncep_u_pattern_residual_z": "NCEP风",
                }[row.target],
                f"{row.pearson_r:+.2f}",
                f"[{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}]",
                f"{row.bh_fdr_q:.2f}",
            ]
        )
    story.append(make_table(candidate_rows, [3.7 * cm, 3.2 * cm, 2.1 * cm, 4.1 * cm, 2.9 * cm], styles))
    add_paragraphs(
        story,
        [
            "八个预先限定的候选关系均未通过FDR。西部WWV对NCEP风的"
            "方向最符合“暖水越多、后期西风越弱”的假设，但r=-0.45、"
            "FDR q=0.67，不能升格为跨事件预测量。",
            "这并不否定Fan等提出的2023/2009机制。它说明多年拉尼娜"
            "历史、暖水空间分布、非线性冷却、外部海盆加热和大气内部"
            "变率需要共同考虑；单独把WWV总量拿出来会丢失路径信息。",
        ],
        styles,
    )
    if FIG_OCEAN_CONDITIONED.exists():
        image = Image(str(FIG_OCEAN_CONDITIONED))
        aspect = image.imageHeight / image.imageWidth
        image.drawWidth = 16.7 * cm
        image.drawHeight = aspect * image.drawWidth
        story.append(image)
        story.append(
            Paragraph(
                "图2. 给定海洋状态后的2023异常、候选量FDR检验与42年"
                "季节排名。风异常早于成熟期降水异常。",
                styles["caption"],
            )
        )
    story.append(PageBreak())

    story.append(Paragraph("8. 与权威研究的对照", styles["h1"]))
    literature_rows = [
        ["研究", "主要机制/实验", "本研究的关系"],
        [
            "Chen et al. 2015",
            "WWB与初始海洋态共同塑造ENSO多样性",
            "Q20把“西风事件是否真正转化成向东暖水输送”显式化",
        ],
        [
            "Li et al. 2024",
            "拆分SST-降水-气压-风应力；2000年后反馈西移",
            "支持逐环残差；也提醒固定历史关系可能随年代变化",
        ],
        [
            "Kim et al. 2025",
            "2023持续东风、负NPMM、菲律宾海D20加深和热量滞留",
            "与JJA/SON风端先失配一致",
        ],
        [
            "Peng et al. 2025",
            "海洋初值主导；外部海盆和背景趋势压低太平洋风",
            "与海洋偏东但大气弱的二维诊断一致；观测不能归因",
        ],
        [
            "Zhao et al. 2025",
            "印度季风-海洋大陆与TNA异常加热造成2023年7月东风",
            "解释早期风端失配；相应加热指数尚未加入",
        ],
        [
            "Zhang et al. 2025",
            "成熟期热带太平洋降水和PNA异常弱",
            "与GPCP DJF残差42年最低相互印证",
        ],
        [
            "Fan et al. 2026",
            "多年拉尼娜-西部WWV-弱非线性冷却-西向增暖-弱西风",
            "解释特定路径；单独WWV未成为通用事件指标",
        ],
        [
            "Jiang et al. 2026",
            "残余FEP暖异常产生经向对流偶极和偏北风抵消西风",
            "当前东西箱平均会漏掉该经向结构，需单独检验",
        ],
    ]
    story.append(make_table(literature_rows, [3.0 * cm, 6.6 * cm, 6.4 * cm], styles))
    add_paragraphs(
        story,
        [
            "这些解释并不必然互斥。外部海盆可以改变Walker环流背景，"
            "多年拉尼娜可以预先塑造西部热含量和温度梯度，FEP残余暖"
            "异常又可以通过经向对流结构局地抵消西风。我们的时序结果"
            "约束了“异常何时出现”，但不具备像AGCM试验那样隔离强迫"
            "来源的能力。",
        ],
        styles,
    )
    story.append(Paragraph("9. 结论：闭环到哪一步", styles["h1"]))
    conclusion_table = Table(
        [
            [
                Paragraph(
                    "海洋路径<br/><br/>西部预条件 → 140°W Q20 → "
                    "D20/热含量储存 → 成熟SST位置",
                    styles["callout"],
                ),
                Paragraph(
                    "大气路径<br/><br/>SST幅度与位置 → 降水加热 → "
                    "SLP/Walker环流 → 西风应力",
                    styles["callout"],
                ),
            ]
        ],
        colWidths=[8.0 * cm, 8.0 * cm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), PALE_BLUE),
                ("BACKGROUND", (1, 0), (1, 0), PALE_ORANGE),
                ("BOX", (0, 0), (0, 0), 0.9, BLUE),
                ("BOX", (1, 0), (1, 0), 0.9, RED),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        ),
    )
    story.append(conclusion_table)
    story.append(Spacer(1, 0.25 * cm))
    add_bullets(
        story,
        [
            "经典EP：海洋向东输送和储存强，大气链通常正常或增强。",
            "CP：海洋异常主要停在中部；考虑SST位置后，大气响应并不"
            "必然偏弱。",
            "2023：春季海洋已经建立中等偏强的东部状态；夏季风反馈"
            "先不足；成熟期对流加热成为最异常环节。",
            "因此不存在一个仅由FEP或WWV决定的单一“转变点”。更合理"
            "的是一个由海洋到达/储存与大气响应效率共同决定的二维"
            "决策面。",
        ],
        styles,
    )
    story.append(Paragraph("10. 下一阶段的决定性工作", styles["h1"]))
    next_rows = [
        ["优先级", "新增诊断/实验", "能回答的问题"],
        [
            "1",
            "印度洋、大西洋、TNA、印度季风-海洋大陆加热指数",
            "外部海盆是否提供独立的早期风响应信息？",
        ],
        [
            "2",
            "FEP赤道-10°N降水偶极、偏北风及涡度",
            "Jiang机制能否解释早期SLP到风的失配？",
        ],
        [
            "3",
            "SODA3/ORAS5西太平洋线性与非线性混合层热收支",
            "Fan机制是否跨多个多年拉尼娜后事件稳定？",
        ],
        [
            "4",
            "WWB频次、幅度和Q20响应效率",
            "风事件为何在有些年份转化为向东热输送、有些没有？",
        ],
        [
            "5",
            "AGCM分区SST强迫 + 耦合海洋初值敏感性试验",
            "分离外部海盆、FEP与太平洋内部路径的因果贡献",
        ],
        [
            "6",
            "扩展样本、年代分层、伪实时验证",
            "哪些量在未来事件上真正增加预测技巧？",
        ],
    ]
    story.append(make_table(next_rows, [1.5 * cm, 7.4 * cm, 7.1 * cm], styles))
    story.append(PageBreak())

    story.append(Paragraph("参考文献与可复核链接", styles["h1"]))
    references = [
        (
            "Chen et al. (2015), Strong influence of westerly wind bursts "
            "on El Niño diversity.",
            "https://www.nature.com/articles/ngeo2399",
        ),
        (
            "Li et al. (2024), On the Westward Shift and Strengthening of "
            "the Atmosphere-To-Ocean Bjerknes Feedback.",
            "https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2024GL109874",
        ),
        (
            "Kim, Tian & Yu (2025), Unusual and persistent easterlies "
            "restrained the 2023/24 El Niño.",
            "https://www.nature.com/articles/s41612-024-00890-0",
        ),
        (
            "Peng et al. (2025), Strong 2023-2024 El Niño generated by "
            "ocean dynamics.",
            "https://www.nature.com/articles/s41561-025-01700-9",
        ),
        (
            "Zhao, Li & Pan (2025), Why zonal wind anomalies were "
            "decoupled to El Niño in July 2023.",
            "https://link.springer.com/article/10.1007/s00382-025-07625-8",
        ),
        (
            "Zhang et al. (2025), The 2023/24 El Niño event exhibited "
            "unusually weak extratropical teleconnections.",
            "https://www.nature.com/articles/s43247-025-02584-8",
        ),
        (
            "Fan et al. (2026), Multi-year La Niña dampens the Southern "
            "Oscillation during subsequent El Niño.",
            "https://www.the-innovation.org/article/doi/10.59717/j.xinn-geo.2026.100224",
        ),
        (
            "Jiang et al. (2026), Early Establishment of Far Eastern "
            "Pacific Warming Shapes Distinctive Air-Sea Coupling.",
            "https://doi.org/10.1029/2026GL123227",
        ),
        (
            "Vialard et al. (2025), The ENSO Recharge Oscillator "
            "Conceptual Model: Achievements and Future Prospects.",
            "https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2024RG000843",
        ),
    ]
    for index, (label, url) in enumerate(references, start=1):
        story.append(
            Paragraph(
                f"{index}. {format_link(url, label)}",
                styles["body"],
            )
        )
    story.append(Paragraph("本地可复核产出", styles["h2"]))
    add_bullets(
        story,
        [
            "output/pdf/enso_full_year_coupling_evolution.pdf",
            "output/pdf/enso_ocean_conditioned_decoupling.pdf",
            "data/derived/research_2026/enso_type_east_ocean_state_correlations.csv",
            "data/derived/research_2026/enso_full_year_coupling_all_year_seasonal_1982_2023.csv",
            "data/derived/research_2026/enso_ocean_conditioned_decoupling_event_summary.csv",
            "data/derived/research_2026/enso_decoupling_candidate_correlations.csv",
            "scripts/analyze_full_year_enso_coupling_evolution.py",
            "scripts/analyze_ocean_conditioned_enso_decoupling.py",
        ],
        styles,
    )
    add_paragraphs(
        story,
        [
            "所有结论均保留了负结果、样本量边界和因果限制。报告中的"
            "“排名”表示在本地参考分布中的经验位置，不是总体概率；"
            "“相关”表示统计联系，不自动等于物理因果。",
        ],
        styles,
    )

    PDF.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story, onFirstPage=page_decor, onLaterPages=page_decor)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ocean_stats = pd.read_csv(OCEAN_STATS)
    seasonal = pd.read_csv(SEASONAL)
    all_year = pd.read_csv(ALL_YEAR)
    ocean_conditioned = pd.read_csv(OCEAN_CONDITIONED)
    candidate = pd.read_csv(CANDIDATE)
    MD.write_text(
        build_markdown(
            ocean_stats,
            seasonal,
            all_year,
            ocean_conditioned,
            candidate,
        ),
        encoding="utf-8",
    )
    build_pdf(
        ocean_stats,
        seasonal,
        all_year,
        ocean_conditioned,
        candidate,
    )
    print(MD)
    print(PDF)


if __name__ == "__main__":
    main()
