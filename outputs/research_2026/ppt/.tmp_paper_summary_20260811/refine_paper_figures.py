from pathlib import Path
from PIL import Image

ROOT = Path("/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_paper_summary_20260811/paper-figures")

# Remove only excess top/bottom whitespace from the original Figure 3a panel.
mhw = Image.open(ROOT / "mhw_fig3a.png").convert("RGB")
mhw.crop((0, 48, mhw.width, mhw.height)).save(ROOT / "mhw_fig3a_wide.png", quality=95)

# Select the two original panels that directly support the current hypothesis:
# Figure 1b (2023 longitude-time evolution) and Figure 1f (2023 MJJ map).
jiang = Image.open(ROOT / "leishan_jiang_fig1.png").convert("RGB")
panel_b = jiang.crop((305, 25, 585, 455))
panel_f = jiang.crop((420, 470, 815, jiang.height))

canvas = Image.new("RGB", (960, 400), "white")
panel_b.thumbnail((285, 390), Image.Resampling.LANCZOS)
panel_f.thumbnail((650, 335), Image.Resampling.LANCZOS)
canvas.paste(panel_b, (8, (400 - panel_b.height) // 2))
canvas.paste(panel_f, (305, (400 - panel_f.height) // 2 + 4))
canvas.save(ROOT / "leishan_jiang_fig1bf.png", quality=95)
