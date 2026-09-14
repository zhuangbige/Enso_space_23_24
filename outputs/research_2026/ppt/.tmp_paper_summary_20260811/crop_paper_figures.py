from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parent
PAGES = ROOT / "paper-pages"
OUT = ROOT / "paper-figures"
OUT.mkdir(parents=True, exist_ok=True)


def crop(source: str, box: tuple[int, int, int, int], target: str) -> None:
    image = Image.open(PAGES / source).convert("RGB")
    figure = image.crop(box)
    figure = ImageOps.expand(figure, border=10, fill="white")
    figure.save(OUT / target, dpi=(180, 180), quality=95)


crop("chak-p12.png", (210, 190, 1220, 615), "chakravorty_fig8.png")
crop("mhw-p15.png", (235, 315, 1145, 770), "mhw_fig3a.png")
crop("jiang-p4.png", (100, 175, 1405, 870), "leishan_jiang_fig1.png")
