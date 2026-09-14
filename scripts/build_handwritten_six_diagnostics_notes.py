#!/usr/bin/env python3
"""Build a handwritten-style Chinese derivation notebook for six diagnostics."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf/ENSO六个诊断_手写推导笔记_20260808.pdf"
FONT = ROOT / "tmp/pdfs/LXGWWenKai-Regular.ttf"

PAGE_W, PAGE_H = A4
INK = colors.HexColor("#173A5E")
INK_2 = colors.HexColor("#245B82")
RED = colors.HexColor("#C74B50")
GREEN = colors.HexColor("#2B7A66")
ORANGE = colors.HexColor("#C77C2E")
PAPER = colors.HexColor("#FFFDF4")
GRID = colors.HexColor("#DCEAF2")
GRID_MAJOR = colors.HexColor("#C8DEE9")
PALE_BLUE = colors.HexColor("#EEF6FA")
PALE_YELLOW = colors.HexColor("#FFF5CC")
PALE_RED = colors.HexColor("#FBEAEC")
PALE_GREEN = colors.HexColor("#EAF5EF")
GREY = colors.HexColor("#6A7480")
LIGHT_GREY = colors.HexColor("#D5D9DC")


def register_fonts() -> None:
    if not FONT.exists():
        raise FileNotFoundError(f"Missing handwriting font: {FONT}")
    pdfmetrics.registerFont(TTFont("WenKai", str(FONT)))
    pdfmetrics.registerFontFamily(
        "WenKai", normal="WenKai", bold="WenKai", italic="WenKai", boldItalic="WenKai"
    )


register_fonts()


styles = getSampleStyleSheet()
BODY = ParagraphStyle(
    "Body",
    parent=styles["BodyText"],
    fontName="WenKai",
    fontSize=10.6,
    leading=17.2,
    textColor=INK,
    spaceAfter=5.5,
    alignment=TA_LEFT,
    wordWrap="CJK",
)
SMALL = ParagraphStyle(
    "Small",
    parent=BODY,
    fontSize=8.8,
    leading=13.2,
    textColor=GREY,
)
SECTION = ParagraphStyle(
    "Section",
    parent=BODY,
    fontSize=19.5,
    leading=24,
    textColor=INK,
    spaceBefore=2,
    spaceAfter=8,
)
SUBSECTION = ParagraphStyle(
    "Subsection",
    parent=BODY,
    fontSize=13.2,
    leading=18,
    textColor=INK_2,
    spaceBefore=5,
    spaceAfter=4,
)
FORMULA = ParagraphStyle(
    "Formula",
    parent=BODY,
    fontSize=13.4,
    leading=19,
    textColor=INK,
    alignment=TA_CENTER,
    spaceAfter=0,
)
TITLE = ParagraphStyle(
    "Title",
    parent=BODY,
    fontSize=27,
    leading=35,
    textColor=INK,
    alignment=TA_CENTER,
)
SUBTITLE = ParagraphStyle(
    "Subtitle",
    parent=BODY,
    fontSize=13,
    leading=20,
    textColor=INK_2,
    alignment=TA_CENTER,
)


def p(text: str, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(text, style)


def body(text: str) -> Paragraph:
    return p(escape(text), BODY)


def small(text: str) -> Paragraph:
    return p(escape(text), SMALL)


def section(number: str, title: str, tag: str | None = None) -> list[Flowable]:
    items: list[Flowable] = []
    if tag:
        tag_table = Table([[p(tag, SMALL)]], colWidths=[55 * mm])
        tag_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PALE_RED),
                    ("BOX", (0, 0), (-1, -1), 0.8, RED),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        items.extend([tag_table, Spacer(1, 3 * mm)])
    items.append(p(f"{number}  {title}", SECTION))
    return items


def sub(title: str) -> Paragraph:
    return p(title, SUBSECTION)


def formula(text: str, label: str | None = None, tint=PALE_BLUE) -> Table:
    safe = escape(text).replace("\n", "<br/>")
    rows = []
    if label:
        rows.append([p(f"{label}", SMALL)])
    rows.append([p(safe, FORMULA)])
    table = Table(rows, colWidths=[166 * mm], hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, -1), tint),
        ("BOX", (0, 0), (-1, -1), 1.0, INK_2),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]
    if label:
        commands.extend(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, GRID_MAJOR),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("TOPPADDING", (0, 0), (-1, 0), 2),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def callout(title: str, text: str, color=RED, tint=PALE_RED) -> Table:
    table = Table(
        [[p(f"<b>{title}</b>", BODY), p(text, BODY)]],
        colWidths=[35 * mm, 131 * mm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), tint),
                ("BOX", (0, 0), (-1, -1), 0.9, color),
                ("LINEAFTER", (0, 0), (0, -1), 0.8, color),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def bullets(items: list[str], color=INK) -> list[Paragraph]:
    style = ParagraphStyle(
        "BulletTemp",
        parent=BODY,
        leftIndent=8 * mm,
        firstLineIndent=-5 * mm,
        bulletIndent=1.5 * mm,
        textColor=color,
        spaceAfter=3.5,
    )
    return [Paragraph(f"• {escape(item)}", style) for item in items]


def note_table(headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    data = [[small(h) for h in headers]] + [[small(c) for c in row] for row in rows]
    table = Table(data, colWidths=[w * mm for w in widths], repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PALE_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), INK),
                ("GRID", (0, 0), (-1, -1), 0.45, GRID_MAJOR),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


class ArrowChain(Flowable):
    def __init__(self, labels: list[str], width: float = 166 * mm, height: float = 34 * mm):
        super().__init__()
        self.labels = labels
        self.width = width
        self.height = height

    def draw(self) -> None:
        c = self.canv
        n = len(self.labels)
        gap = 4 * mm
        box_w = (self.width - gap * (n - 1)) / n
        y = 6 * mm
        h = 20 * mm
        c.setFont("WenKai", 8.7)
        for i, label in enumerate(self.labels):
            x = i * (box_w + gap)
            c.setFillColor(PALE_BLUE if i % 2 == 0 else PALE_GREEN)
            c.setStrokeColor(INK_2)
            c.roundRect(x, y, box_w, h, 3 * mm, fill=1, stroke=1)
            c.setFillColor(INK)
            parts = label.split("\n")
            for j, part in enumerate(parts):
                c.drawCentredString(x + box_w / 2, y + h / 2 + (len(parts) - 1 - 2 * j) * 3.1, part)
            if i < n - 1:
                x1 = x + box_w + 0.7 * mm
                x2 = x + box_w + gap - 0.7 * mm
                ym = y + h / 2
                c.setStrokeColor(RED)
                c.setFillColor(RED)
                c.line(x1, ym, x2, ym)
                c.line(x2, ym, x2 - 2.2 * mm, ym + 1.6 * mm)
                c.line(x2, ym, x2 - 2.2 * mm, ym - 1.6 * mm)


def on_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    step = 7 * mm
    x = 0
    line_no = 0
    while x <= PAGE_W:
        canvas.setStrokeColor(GRID_MAJOR if line_no % 5 == 0 else GRID)
        canvas.setLineWidth(0.35 if line_no % 5 == 0 else 0.2)
        canvas.line(x, 0, x, PAGE_H)
        x += step
        line_no += 1
    y = 0
    line_no = 0
    while y <= PAGE_H:
        canvas.setStrokeColor(GRID_MAJOR if line_no % 5 == 0 else GRID)
        canvas.setLineWidth(0.35 if line_no % 5 == 0 else 0.2)
        canvas.line(0, y, PAGE_W, y)
        y += step
        line_no += 1
    canvas.setStrokeColor(colors.HexColor("#E6A9AB"))
    canvas.setLineWidth(0.75)
    canvas.line(22 * mm, 12 * mm, 22 * mm, PAGE_H - 12 * mm)
    canvas.setFont("WenKai", 8.5)
    canvas.setFillColor(GREY)
    canvas.drawRightString(PAGE_W - 14 * mm, 9 * mm, f"第 {doc.page} 页")
    canvas.drawString(27 * mm, 9 * mm, "ENSO暖量诊断｜推导笔记")
    canvas.restoreState()


def build_story() -> list[Flowable]:
    S: list[Flowable] = []

    # Cover
    S.extend([Spacer(1, 23 * mm), p("ENSO 六个诊断", TITLE), p("从定义、推导到完整物理链", TITLE)])
    S.append(Spacer(1, 7 * mm))
    S.append(p("H₂₀ → Qwarm,20 → 三箱预算 → FEP残差 → 地转/Ekman分解 → 离线换风", SUBTITLE))
    S.append(Spacer(1, 17 * mm))
    S.append(
        callout(
            "这份笔记怎么读",
            "每个诊断都按同一顺序展开：为什么需要它 → 从基础定义逐步推导 → 每个符号和单位 → 代码实际怎么算 → 它回答哪个科学问题 → 如何接到下一步。",
            color=INK_2,
            tint=PALE_BLUE,
        )
    )
    S.append(Spacer(1, 8 * mm))
    S.append(
        note_table(
            ["颜色", "含义"],
            [
                ["蓝色", "本文构造并计算的诊断量"],
                ["灰色", "标准热力学、控制体、地转或Ekman基础关系"],
                ["红色", "符号、边界、阈值非线性和因果措辞陷阱"],
            ],
            [28, 138],
        )
    )
    S.append(Spacer(1, 12 * mm))
    S.append(p("研究主线：暖量来了多少？来了以后去哪？为什么2015和2023走向不同？", SUBTITLE))
    S.append(PageBreak())

    # Big picture
    S.extend(section("0", "先看全图：六个诊断并不是六件孤立的事", "总路线"))
    S.append(ArrowChain(["① 定义\n暖量", "② 追踪\n到达", "③ 核算\n去向", "④ 排除\n表面假象", "⑤ 找出\n动力来源", "⑥ 换风\n做隔离"]))
    S.append(Spacer(1, 4 * mm))
    S.extend(
        bullets(
            [
                "诊断1先规定本文说的“暖量”到底是什么，否则WWV、OHC和能量会混在一起。",
                "诊断2把静态储量变成跨断面的暖量通量，回答暖量是否真正越过140°W到达东部。",
                "诊断3对固定箱体列账，避免把H₂₀下降简单等同于“全部向北跑掉”。",
                "诊断4控制Niño-3.4以后再看FEP，检验“最东部先暖”是不是事件命运的充分条件。",
                "诊断5把5°N总出口拆成地转、Ekman和剩余，找到2015/2023的直接动力差异。",
                "诊断6固定海洋状态只换风，隔离局地风驱对出口的一阶贡献。",
            ]
        )
    )
    S.append(Spacer(1, 3 * mm))
    S.append(
        note_table(
            ["三个中心问题", "所用诊断", "真正得到的答案"],
            [
                ["Q1 暖量来了吗？", "①H₂₀ + ②Qwarm,20", "1997输入最强；2015与2023到达量接近"],
                ["Q2 暖量去哪了？", "③三箱预算", "5°N输出、海表散热、储量和R₂₀共同分配"],
                ["Q3 为什么命运不同？", "④FEP残差 + ⑤分解 + ⑥换风", "FEP先暖不充分；风驱Ekman是关键一阶差异"],
            ],
            [43, 49, 74],
        )
    )
    S.append(PageBreak())

    # Diagnostic 1
    S.extend(section("1", "阈值暖量 H₂₀：把WWV变成能量", "本文核心定义"))
    S.append(sub("1.1 从一个微小水体的热量开始"))
    S.append(body("取一个体积微元 dV。若以20°C作为本文的动力学阈值参考温度 Tᵣ，则该水体相对阈值的温差为 T−Tᵣ。标准显热关系给出："))
    S.append(formula("dEᵣ = ρ₀ cₚ (T − Tᵣ) dV", "灰色基础：相对参考温度的显热"))
    S.append(body("但本文只研究20°C暖水体。若T≤Tᵣ，这个格点不应贡献负“暖量”。因此引入指示函数："))
    S.append(formula("I₂₀(T) = 1，当 T>Tᵣ；I₂₀(T) = 0，当 T≤Tᵣ", "第1步：只保留阈值以上水体"))
    S.append(body("把温差与指示函数相乘，就得到只在暖水体内非零的阈值超温："))
    S.append(formula("χ₂₀(T) = I₂₀(T)(T−Tᵣ) = max(T−Tᵣ, 0)", "第2步：定义阈值超温"))
    S.append(body("于是单位体积阈值相对热含量为 e₂₀=ρ₀cₚχ₂₀。对整个控制体 Ω 积分："))
    S.append(formula("H₂₀(t) = ρ₀ cₚ ∭Ω χ₂₀[T(x,y,d,t)] dV", "第3步：得到本文的H₂₀"))
    S.append(sub("1.2 它和WWV是什么关系？"))
    S.append(formula("WWV = ∭Ω I₂₀ dV", "暖水体积"))
    S.append(formula("ΔT̄₂₀ = (∭Ω χ₂₀ dV) / (∭Ω I₂₀ dV)", "暖水体相对20°C的体积平均超温"))
    S.append(body("把分母WWV移到右边即可得到严格恒等式："))
    S.append(formula("H₂₀ = ρ₀ cₚ · WWV · ΔT̄₂₀", "体积 × 平均超温 × 热容量"))
    S.append(callout("关键区别", "WWV只告诉我们暖水体有多大；H₂₀同时考虑暖水体积和超过20°C多少。它不是传统0–500 m总OHC。"))
    S.append(PageBreak())

    S.extend(section("1", "H₂₀的单位、数据和输出", "诊断1续"))
    S.append(sub("1.3 量纲逐项检查"))
    S.append(formula("[ρ₀][cₚ][χ₂₀][dV] = (kg m⁻³)(J kg⁻¹ K⁻¹)(K)(m³) = J"))
    S.append(body("区域积分后使用ZJ：1 ZJ = 10²¹ J。代码中ρ₀=1025 kg m⁻³，cₚ=3990 J kg⁻¹ K⁻¹，温度来自SODA3三维月平均场。"))
    S.append(sub("1.4 代码实际上做了四步"))
    S.extend(
        bullets(
            [
                "逐格点计算 χ₂₀=max(T−20,0)。",
                "根据模式层上下边界计算精确层厚 dz，而不是把层中心当层厚。",
                "乘以球面网格面积 A(x,y)，得到 dV=A·dz。",
                "在西、中、东三个固定箱体分别求和，并转成ZJ。",
            ]
        )
    )
    S.append(sub("1.5 它在文章里干了什么？"))
    S.append(
        note_table(
            ["事件/合成", "H₂₀结果", "解释"],
            [
                ["CT vs CP发展期", "+7.81 vs +3.71 ZJ", "两类事件都储热，但CT到达更强"],
                ["1997", "Jan–Jun +9.29 ZJ", "盆地支撑最强"],
                ["2015", "Jan–Jun +3.53 ZJ", "东部暖量确实增加"],
                ["2023", "Jan–Jun +3.88 ZJ", "与2015非常接近"],
            ],
            [39, 50, 77],
        )
    )
    S.append(callout("接到下一步", "H₂₀只能说明一个箱体里存了多少暖量，却不能说明暖量从哪条边界进来。因此需要把同一个阈值能量密度放进通量公式。", color=GREEN, tint=PALE_GREEN))
    S.append(PageBreak())

    # Diagnostic 2
    S.extend(section("2", "阈值暖量输送 Qwarm,20：追踪暖量穿过哪里", "本文核心定义"))
    S.append(sub("2.1 从“单位时间穿过断面的体积”推导"))
    S.append(body("在断面Γ上取面积微元dA，法向速度为vₙ。单位时间穿过该微元的体积是："))
    S.append(formula("dV / dt = vₙ dA", "第1步：体积输送率"))
    S.append(body("该水体单位体积携带的阈值能量为e₂₀=ρ₀cₚχ₂₀。因此单位时间穿过dA的暖量为："))
    S.append(formula("dQwarm,20 = e₂₀(dV/dt) = ρ₀cₚ vₙχ₂₀ dA", "第2步：局地暖量通量"))
    S.append(body("对整个断面积分："))
    S.append(formula("Qwarm,20,Γ(t) = ρ₀cₚ ∬Γ vₙ(t)χ₂₀[T(t)] dA", "第3步：断面阈值暖量输送"))
    S.append(sub("2.2 单位为什么是功率？"))
    S.append(formula("(kg m⁻³)(J kg⁻¹ K⁻¹)(m s⁻¹)(K)(m²) = J s⁻¹ = W"))
    S.append(body("月平均通量通常用PW表示，1 PW=10¹⁵ W。对事件阶段积分后："))
    S.append(formula("EΓ(t₁→t₂) = ∫ₜ₁ᵗ² Qwarm,20,Γ(t) dt", "PW经过时间积分后转换为ZJ"))
    S.append(sub("2.3 正方向必须先声明"))
    S.extend(
        bullets(
            [
                "140°W经向断面：向东为正，用来判断暖量是否进入东部箱。",
                "5°N纬向断面：结果图中向北输出为正，用来判断成熟后极向放电。",
                "控制体预算中统一采用入箱为正，因此北边界预算项F₅N与图中的北向输出符号相反。",
            ],
            color=RED,
        )
    )
    S.append(callout("它不是传统热输送", "传统海洋热输送常写成ρ₀cₚ∬vₙT dA；本文用χ₂₀代替T，只输送20°C阈值以上的相对暖量。"))
    S.append(sub("2.4 文章中的实际作用"))
    S.append(body("Jun(0)–Nov(0)跨140°W东向累计输送：CT为+6.25 ZJ，CP为+2.97 ZJ；三事件Jan–Jun分别为1997 +12.13、2015 +3.30、2023 +3.91 ZJ。"))
    S.append(callout("接到下一步", "现在知道暖量确实越过140°W，但“进入量”不等于“储量变化”。要同时处理东西、南北边界和海表交换，必须给固定箱体列完整账。", color=GREEN, tint=PALE_GREEN))
    S.append(PageBreak())

    # Diagnostic 3
    S.extend(section("3", "三箱暖量预算：回答暖量到达后去了哪里", "本文预算框架"))
    S.append(sub("3.1 从固定控制体的一般收支开始"))
    S.append(body("对固定控制体Ω中的标量储量H₂₀，一般形式是“储量变化 = 边界净输入 + 内部/表面源汇 + 未解析项”："))
    S.append(formula("dH₂₀/dt = −∮∂Ω e₂₀(v·n_out)dA + S + R₂₀", "灰色基础：固定控制体收支"))
    S.append(body("其中n_out是箱体外法向。v·n_out>0表示流出；为了让所有预算项统一为“入箱为正”，定义："))
    S.append(formula("FΓ = −ρ₀cₚ ∬Γ (v·n_out)χ₂₀(T)dA", "第1步：统一边界符号"))
    S.append(body("因此FΓ>0表示暖量进入箱体，FΓ<0表示离开箱体。东西边界合并为纬向辐合Cₓ："))
    S.append(formula("Cₓ = Fwest + Feast", "第2步：东西向净输入"))
    S.append(sub("3.2 表面热通量怎样进入阈值预算？"))
    S.append(body("Qnet规定进入海洋为正。本文只把作用于表层Tₛ>20°C区域的净热通量直接计入暖量预算："))
    S.append(formula("Qsurface,warm = ∬A I₂₀(Tₛ) Qnet dA", "第3步：暖层海表热源/热汇"))
    S.append(body("把东西、南北边界和表面项放在一起："))
    S.append(formula("dH₂₀/dt = Cₓ + F₁₀S + F₅N + Qsurface,warm + R₂₀", "第4步：三箱暖量预算"))
    S.append(body("实际计算中，R₂₀不是猜出来的，而是由闭合关系反算："))
    S.append(formula("R₂₀ = dH₂₀/dt − Cₓ − F₁₀S − F₅N − Qsurface,warm", "第5步：定义诊断剩余"))
    S.append(PageBreak())

    S.extend(section("3", "为什么必须保留R₂₀？", "诊断3续"))
    S.append(sub("3.3 阈值函数不是普通线性示踪剂"))
    S.append(body("χ₂₀(T)=max(T−Tᵣ,0)是分段函数。远离阈值时可用链式法则："))
    S.append(formula("Dχ₂₀/Dt = I₂₀(T) · DT/Dt，T≠Tᵣ", "阈值以外的物质导数"))
    S.extend(
        bullets(
            [
                "当T>Tᵣ时，χ₂₀=T−Tᵣ，所以Dχ₂₀/Dt=DT/Dt。",
                "当T<Tᵣ时，χ₂₀=0，所以Dχ₂₀/Dt=0。",
                "当水体因加热、混合、夹卷跨过T=Tᵣ时，阈值水团会生成或消失；月平均资料无法逐项解析。",
            ]
        )
    )
    S.append(body("因此R₂₀共同吸收：跨20°C阈值转换、垂向/斜压交换、混合扩散、涡动协方差、同化增量以及时间与空间离散误差。"))
    S.append(callout("不能过度解释", "R₂₀是“尚未显式解释的闭合项”，不能预先命名为混合、潜沉或某一条洋流。"))
    S.append(sub("3.4 三个固定箱体"))
    S.append(
        note_table(
            ["箱体", "经度范围", "共同范围", "主要作用"],
            [
                ["西箱", "160°E–180°", "10°S–5°N，0–300 m", "盆地西部蓄热/供给"],
                ["中箱", "180°–140°W", "同上", "向东传播和中部预置"],
                ["东箱", "140°W–80°W", "同上", "到达、放电和海气耦合"],
            ],
            [25, 38, 55, 48],
        )
    )
    S.append(sub("3.5 得到的去向"))
    S.append(body("CT成熟–衰减期东部H₂₀减少7.86 ZJ，其中5°N北向输出2.74 ZJ、海表热损失3.69 ZJ、10°S输出0.68 ZJ、剩余约2.09 ZJ。CP东部H₂₀减少3.03 ZJ，但5°N项为−0.96 ZJ，即合成上仍向东部箱输入。"))
    S.append(callout("问题二答案", "东部暖量减少不是单一路径：5°N动力出口、海表热损失、储量调整和R₂₀共同参与；10°S不是稳健主出口。", color=GREEN, tint=PALE_GREEN))
    S.append(PageBreak())

    # Diagnostic 4
    S.extend(section("4", "FEP独立异常：先排除“只是整个ENSO更暖”", "统计诊断"))
    S.append(sub("4.1 为什么不能直接看FEP异常？"))
    S.append(body("FEP定义为5°S–5°N、90°W–80°W的SST异常。Niño-3.4整体增强时，FEP往往也会被动变暖。因此直接比较FEP会混入同期ENSO幅度。"))
    S.append(body("对每个日历月m单独使用1982–2024年样本，写出线性关系："))
    S.append(formula("FEP′(m,y) = aₘ + bₘ N₃.₄′(m,y) + ε(m,y)", "第1步：逐月OLS模型"))
    S.append(sub("4.2 OLS斜率从哪里来？"))
    S.append(body("令X=N₃.₄′，Y=FEP′。最小化Σ[Y−(a+bX)]²，对a、b求导并令其为0，可得："))
    S.append(formula("bₘ = Σᵧ(Xᵧ−X̄)(Yᵧ−Ȳ) / Σᵧ(Xᵧ−X̄)²", "逐月回归斜率"))
    S.append(formula("aₘ = Ȳ − bₘX̄", "逐月回归截距"))
    S.append(body("回归期望值为aₘ+bₘN₃.₄′，实际值减去期望值："))
    S.append(formula("FEPres = FEP′ − [aₘ + bₘN₃.₄′] = ε", "第2步：FEP独立异常"))
    S.append(sub("4.3 它的统计含义"))
    S.extend(
        bullets(
            [
                "FEPres>0：在同样Niño-3.4幅度下，最东部比统计预期更暖。",
                "FEPres<0：在同样Niño-3.4幅度下，最东部比统计预期更冷。",
                "OLS样本内残差与Niño-3.4线性正交，但不代表物理独立或外部强迫。",
            ]
        )
    )
    S.append(callout("关键发现", "2023的FEP残差从2月持续为正，但3–4月中太平洋深对流和西风接通仍弱；2015同样存在先暖却发展成强事件。因此FEP先暖是表面起点，不是充分条件。"))
    S.append(callout("接到下一步", "既然2015和2023都先暖、东部H₂₀到达量也接近，差异必须继续向“风场怎样作用于5°N出口”追。", color=GREEN, tint=PALE_GREEN))
    S.append(PageBreak())

    # Diagnostic 5 geostrophic
    S.extend(section("5", "暖量动力分解：地转部分怎样推出来", "标准动力 + 本文暖量化"))
    S.append(sub("5.1 坐标和正方向"))
    S.extend(
        bullets(
            [
                "x向东、y向北、深度d=−z向下为正。",
                "在5°N，科氏参数f>0；所有断面动力分量规定北向为正。",
                "这里的地转与Ekman关系是标准物理；本文的新步骤是把速度/体积输送转换成Qwarm,20。",
            ]
        )
    )
    S.append(sub("5.2 从地转平衡到经向地转速度"))
    S.append(body("忽略加速度与摩擦后，纬向压力梯度和科氏力平衡："))
    S.append(formula("f v_g = (1/ρ₀) ∂p/∂x", "标准地转关系"))
    S.append(body("向下深度坐标中静力关系为∂p/∂d=ρg。从海表积分到深度d，并把海表高度η产生的压力写出："))
    S.append(formula("p(x,d) = ρ₀gη(x) + g∫₀ᵈ ρ′(x,d′) dd′ + p_ref(d)", "标准静力积分"))
    S.append(body("其中ρ′=ρ−ρref(d)。参考项p_ref只随深度变化，所以对x求导为0："))
    S.append(formula("∂p/∂x = ρ₀g ∂η/∂x + g∫₀ᵈ ∂ρ′/∂x dd′"))
    S.append(body("代回地转关系并除以ρ₀f："))
    S.append(formula("v_g(d) = (g/f)∂η/∂x + [g/(ρ₀f)]∫₀ᵈ ∂ρ′/∂x dd′", "SSH地转 + 密度地转"))
    S.append(body("最后把v_g代入诊断2的暖量输送公式："))
    S.append(formula("Qwarm,20,geo = ρ₀cₚ∫ₓ∫₀³⁰⁰ v_g(x,d)χ₂₀(x,d) dd dx", "本文地转暖量诊断"))
    S.append(callout("为什么写ρ′？", "水平一致的背景密度不产生斜压压力梯度。由于ρref只随深度变化，数值上∂ρ′/∂x=∂ρ/∂x。"))
    S.append(PageBreak())

    # Diagnostic 5 Ekman and decomposition
    S.extend(section("5", "Ekman部分与总量闭合", "诊断5续"))
    S.append(sub("5.3 从纬向风应力到经向Ekman输送"))
    S.append(body("对Ekman层的纬向动量方程做垂向积分，忽略底部应力，可写为："))
    S.append(formula("−f M_y = τₓ / ρ₀", "标准垂向积分Ekman关系"))
    S.append(body("因此："))
    S.append(formula("M_y = −τₓ/(ρ₀f)", "北向为正；M_y单位m² s⁻¹"))
    S.extend(
        bullets(
            [
                "τₓ>0表示向东风应力，因此M_y<0，即南向Ekman输送。",
                "τₓ<0表示向西风应力，因此M_y>0，即北向Ekman输送。",
            ],
            color=RED,
        )
    )
    S.append(body("M_y已经是每单位纬向宽度的垂向积分体积输送。用0–50 m平均阈值超温χ̄₂₀给它加上暖量权重，再沿断面x积分："))
    S.append(formula("Qwarm,20,Ekman = ρ₀cₚ∫ₓ M_y(x)χ̄₂₀,0–50m(x) dx", "本文一阶Ekman暖量输送"))
    S.append(body("原生SODA3经向速度直接给总暖量输送Qtotal。于是定义剩余："))
    S.append(formula("Qres = Qtotal − Qgeo − QEkman"))
    S.append(formula("Qtotal = Qgeo + QEkman + Qres", "诊断恒等式"))
    S.append(sub("5.4 2015与2023为什么不同？"))
    S.append(
        note_table(
            ["事件", "总出口", "Ekman", "地转", "残差"],
            [
                ["1997", "+3.81", "+3.25", "+0.59", "−0.03"],
                ["2015", "+0.88", "+2.44", "−1.28", "−0.28"],
                ["2023", "+0.10", "+1.56", "−1.27", "−0.20"],
            ],
            [31, 33, 33, 33, 36],
        )
    )
    S.append(body("2015和2023的南向地转项几乎完全相同；两者净出口相差0.79 ZJ，而Ekman相差0.88 ZJ。其余分量部分抵消，所以不能说“Ekman克服地转”，应写成“更强Ekman项使合成总出口保持北向”。"))
    S.append(callout("分解的边界", "Qres不是独立动力模态；地转压力场也会响应风和热力过程。因此这个分解说明分量构成，不等同于因果强迫试验。"))
    S.append(PageBreak())
    S.extend(section("5→6", "从“分量构成”推进到“风的隔离”", "过渡页"))
    S.append(formula("2015−2023：ΔQtotal=+0.79 ZJ；ΔQEkman=+0.88 ZJ；ΔQgeo≈0", "分解给出的机制线索"))
    S.append(body("这组数值说明，2015与2023的净出口差异主要落在Ekman项上；但因为地转压力场和风可能共同受海气耦合控制，仅凭分解还不能说风造成了全部差异。"))
    S.append(sub("下一步必须满足三个隔离条件"))
    S.extend(
        bullets(
            [
                "固定事件自身的温度和χ̄₂₀权重，避免暖层结构同时改变。",
                "固定事件自身的SSH、密度和Qgeo，避免压力场跟随新风调整。",
                "固定Qres，只重新计算含τₓ的Ekman项。",
            ]
        )
    )
    S.append(callout("接到下一步", "分解提示差异主要落在风驱Ekman项上。下一步固定海洋状态只换τₓ，看总出口能否随风改变。", color=GREEN, tint=PALE_GREEN))
    S.append(PageBreak())

    # Diagnostic 6
    S.extend(section("6", "离线换风重构：隔离局地风的一阶作用", "离线反事实"))
    S.append(sub("6.1 先写事件i的原始总量"))
    S.append(formula("Qtotal(i) = Qgeo(i) + Qres(i) + QEkman[T(i), τₓ(i)]"))
    S.append(body("现在固定事件i的温度T、SSH、密度、地转项和剩余项，只把风应力换成事件j："))
    S.append(formula("Qrec(i←j) = Qgeo(i) + Qres(i) + QEkman[T(i), τₓ(j)]", "本文离线换风公式"))
    S.append(sub("6.2 为什么这能隔离风的直接贡献？"))
    S.append(body("原状态与换风状态相减，固定项Qgeo(i)和Qres(i)自动消去："))
    S.append(formula("Qrec(i←j) − Qrec(i←i) = QEkman[T(i),τₓ(j)] − QEkman[T(i),τₓ(i)]"))
    S.append(body("再代入M_y=−τₓ/(ρ₀f)，ρ₀约掉："))
    S.append(formula("ΔQrec = −(cₚ/f)∫ₓ[τₓ(j)−τₓ(i)]χ̄₂₀,i dx", "只保留风应力差 × 固定暖层权重"))
    S.append(sub("6.3 结果矩阵（ZJ）"))
    S.append(
        note_table(
            ["固定海洋状态", "1997风", "2015风", "2023风"],
            [
                ["1997", "+3.81", "+2.70", "+1.86"],
                ["2015", "+2.14", "+0.88", "+0.08"],
                ["2023", "+2.10", "+0.88", "+0.10"],
            ],
            [52, 38, 38, 38],
        )
    )
    S.extend(
        bullets(
            [
                "固定2023海洋状态：自身风给0.10 ZJ；换2015风变0.88 ZJ；换1997风变2.10 ZJ。",
                "固定2015海洋状态：自身风给0.88 ZJ；换2023风降到0.08 ZJ。",
            ]
        )
    )
    S.append(callout("可以说什么", "风应力替换能显著改变诊断出口，局地风驱是2015/2023出口差异的重要一阶贡献。", color=GREEN, tint=PALE_GREEN))
    S.append(callout("不能说什么", "温度、SSH、密度和大气都没有响应新风，所以它不是耦合模式意义上的完整因果试验，也不能证明风是唯一原因。"))
    S.append(PageBreak())

    # Chain
    S.extend(section("7", "六个诊断怎样真正串成一篇文章", "逻辑闭环"))
    S.append(sub("7.1 不是按公式编号串，而是按物理问题串"))
    S.append(ArrowChain(["FEP表面\n先暖", "盆地OHC\nD20预置", "H₂₀储量\nQ140W到达", "深对流\n西风接通", "Ekman增强\n合成5°N出口", "预算确认\n最终去向"]))
    S.append(Spacer(1, 3 * mm))
    S.append(
        note_table(
            ["物理环节", "诊断证据", "排除了什么解释"],
            [
                ["表面起点", "FEPres", "不是单纯Niño-3.4更强"],
                ["暖量到达", "H₂₀ + 140°W Qwarm,20", "2023并非没有暖量进入东部"],
                ["到达后分配", "三箱预算", "H₂₀下降不等于单一北向出口"],
                ["动力出口", "geo/Ekman/res", "2015/2023差异并非地转项不同"],
                ["风的一阶作用", "离线换风", "出口差异不是海洋固定项单独决定"],
            ],
            [38, 55, 73],
        )
    )
    S.append(sub("7.2 三个中心问题最终各自闭合在哪里？"))
    S.append(callout("问题一：暖量来了吗？", "来了。1997最强；2015与2023在Jan–Jun跨140°W输入和东部H₂₀增长都很接近。", color=INK_2, tint=PALE_BLUE))
    S.append(callout("问题二：暖量去哪了？", "进入东部后由5°N边界、海表热损失、储量变化和R₂₀共同分配。CT有稳健北向放电，CP没有同样出口。", color=INK_2, tint=PALE_BLUE))
    S.append(callout("问题三：为什么命运不同？", "FEP先暖不充分；盆地次表层预置决定能否组织深对流和西风，风驱Ekman强弱进一步决定合成后的5°N总诊断出口。", color=INK_2, tint=PALE_BLUE))
    S.append(PageBreak())

    # Results summary
    S.extend(section("8", "把关键数字放回逻辑链", "结果速查"))
    S.append(
        note_table(
            ["环节", "1997", "2015", "2023", "结论"],
            [
                ["Jan–Jun 140°W输入", "+12.13", "+3.30", "+3.91", "15/23接近"],
                ["Jan–Jun东部H₂₀", "+9.29", "+3.53", "+3.88", "15/23接近"],
                ["次年1–5月5°N总输出", "+3.81", "+0.88", "+0.10", "强→弱→近闭合"],
                ["次年1–5月Ekman", "+3.25", "+2.44", "+1.56", "主要直接差异"],
                ["次年1–5月地转", "+0.59", "−1.28", "−1.27", "15/23几乎相同"],
                ["固定2023海洋状态", "+2.10", "+0.88", "+0.10", "出口随换风改变"],
            ],
            [43, 25, 25, 25, 48],
        )
    )
    S.append(Spacer(1, 5 * mm))
    S.append(sub("8.1 刚完成的Q500敏感性放在哪里？"))
    S.append(body("Q500=ρ₀cₚ∫₀⁵⁰⁰Tdz是标准固定深度上层OHC，不属于六个自定义诊断。它只作为H₂₀储量定义的敏感性检验。"))
    S.append(
        note_table(
            ["Jan–Jun变化", "H₂₀", "Q500", "排序"],
            [
                ["1997", "+9.29", "+15.78", "第1"],
                ["2015", "+3.53", "+6.43", "第3"],
                ["2023", "+3.88", "+6.46", "第2"],
            ],
            [48, 38, 38, 42],
        )
    )
    S.append(body("尽管绝对幅度增加，月异常相关为0.983，三事件排序和符号不变；2015/2023在Q500下甚至更接近。因此“到达量相近、命运不同”的结论不是H₂₀定义造成的。"))
    S.append(PageBreak())

    # Reviewer traps
    S.extend(section("9", "审稿时最容易被问的六个边界", "措辞保护"))
    S.append(
        note_table(
            ["诊断", "最危险的误写", "稳妥表述"],
            [
                ["H₂₀", "20°C是绝对热力学零点", "20°C是与D20/WWV一致的动力学阈值参考"],
                ["Qwarm,20", "这是传统总海洋热输送", "这是20°C阈值暖水体热能输送"],
                ["三箱预算", "R₂₀就是混合或潜沉", "R₂₀是多种未显式过程的诊断剩余"],
                ["FEPres", "FEP残差是独立外强迫", "它只是控制Niño-3.4后的统计残差"],
                ["动力分解", "Ekman战胜地转", "更强Ekman项使总诊断输出增加"],
                ["离线换风", "已经完成严格因果实验", "只完成固定海洋状态下的一阶敏感性隔离"],
            ],
            [35, 63, 68],
        )
    )
    S.append(Spacer(1, 6 * mm))
    S.append(callout("最重要的原创边界", "可以写“本文定义/构建H₂₀、Qwarm,20及连续诊断链”；不要在未穷尽文献前写“全球首次发明”。地转、静力和Ekman公式必须明确属于标准物理。"))
    S.append(sub("9.1 整条链支持的最强结论"))
    S.append(formula("暖量到达 ≠ 海气耦合已经接通 ≠ 必然形成同样的5°N出口", tint=PALE_YELLOW))
    S.append(body("本文真正推进的是过程层次的分离：跨断面输入不等于箱体储存，箱体储量下降不等于单一去向，表面先暖也不等于深对流—风场已经闭合。"))
    S.append(PageBreak())

    # Symbol dictionary
    S.extend(section("10", "全符号速查", "附录A"))
    S.append(
        note_table(
            ["符号", "含义", "单位/正方向"],
            [
                ["T, Tᵣ", "海温；阈值参考温度20°C", "°C；温差用K"],
                ["χ₂₀", "max(T−Tᵣ,0)，阈值超温", "K"],
                ["I₂₀", "T>Tᵣ时为1，否则0", "无量纲"],
                ["ρ₀, cₚ", "参考密度；定压比热", "1025 kg m⁻³；3990 J kg⁻¹ K⁻¹"],
                ["Ω, Γ, A", "控制体；边界断面；海表面积", "空间区域"],
                ["dV, dA, dx", "体积、断面、纬向长度微元", "m³；m²；m"],
                ["vₙ, v·n_out", "断面法向速度；外法向速度", "m s⁻¹"],
                ["H₂₀", "控制体内阈值相对热含量", "J/ZJ"],
                ["Qwarm,20", "阈值暖量输送", "W/PW；时间积分J/ZJ"],
                ["Cₓ, F₁₀S, F₅N", "纬向辐合；南北边界入箱项", "W/PW；入箱为正"],
                ["Qnet", "净海表热通量", "W m⁻²；海洋吸热为正"],
                ["R₂₀", "三箱暖量预算剩余", "W/PW"],
                ["FEPres", "控制Niño-3.4后的FEP残差", "°C"],
                ["f, g, η", "科氏参数；重力；海表高度", "s⁻¹；m s⁻²；m"],
                ["ρ′, v_g", "密度异常；地转经向速度", "kg m⁻³；m s⁻¹"],
                ["τₓ, M_y", "纬向风应力；经向Ekman输送", "N m⁻²；m² s⁻¹，北向正"],
                ["Qgeo,QEkman,Qres", "地转、Ekman和剩余暖量输送", "W/PW或ZJ"],
                ["Qrec(i←j)", "事件i海洋状态接受事件j风后的重构出口", "ZJ"],
            ],
            [34, 83, 49],
        )
    )
    S.append(PageBreak())

    # Final cheat sheet
    S.extend(section("11", "一页记住全部推导", "附录B"))
    S.append(formula("① χ₂₀=max(T−20,0)  →  H₂₀=ρ₀cₚ∭χ₂₀dV", "定义区域储量"))
    S.append(Spacer(1, 2 * mm))
    S.append(formula("② dV/dt=vₙdA  →  Qwarm,20=ρ₀cₚ∬vₙχ₂₀dA", "定义跨断面输送"))
    S.append(Spacer(1, 2 * mm))
    S.append(formula("③ FΓ=−ρ₀cₚ∬(v·n_out)χ₂₀dA\ndH₂₀/dt=Cₓ+F₁₀S+F₅N+Qsurface,warm+R₂₀", "固定箱体列账"))
    S.append(Spacer(1, 2 * mm))
    S.append(formula("④ FEPres=FEP′−[aₘ+bₘN₃.₄′]", "排除同期ENSO幅度"))
    S.append(Spacer(1, 2 * mm))
    S.append(formula("⑤ f v_g=(1/ρ₀)∂p/∂x；M_y=−τₓ/(ρ₀f)\nQtotal=Qgeo+QEkman+Qres", "找到5°N动力构成"))
    S.append(Spacer(1, 2 * mm))
    S.append(formula("⑥ Qrec(i←j)=Qgeo(i)+Qres(i)+QEkman[T(i),τₓ(j)]", "固定海洋，只换风"))
    S.append(Spacer(1, 7 * mm))
    S.append(
        callout(
            "最后一句话",
            "2015与2023都有FEP先暖，也有近似的东部暖量到达；真正的分叉发生在次表层预置能否组织深对流—风场接通，以及由此产生的Ekman暖量出口是否足以使5°N总诊断输送保持北向。",
            color=GREEN,
            tint=PALE_GREEN,
        )
    )
    S.append(Spacer(1, 10 * mm))
    S.append(p("—— 推导结束：从“暖量是什么”到“暖量为什么走向不同” ——", SUBTITLE))
    return S


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=27 * mm,
        rightMargin=16 * mm,
        topMargin=17 * mm,
        bottomMargin=16 * mm,
        title="ENSO六个诊断：手写推导笔记",
        author="Codex with Dai Yue",
        subject="H20, Qwarm20, three-box budget, FEP residual, dynamical decomposition, wind swap",
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="normal",
    )
    doc.addPageTemplates([PageTemplate(id="notebook", frames=[frame], onPage=on_page)])
    doc.build(build_story())
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
