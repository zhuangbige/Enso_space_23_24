from __future__ import annotations

import re
import shutil
from pathlib import Path


def patch_author_script(source: Path, target: Path, data_dir: Path, figure_dir: Path) -> None:
    text = source.read_text(encoding="utf-8")
    data_dir = data_dir.resolve()
    figure_dir = figure_dir.resolve()
    figure_dir.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)

    def replace_yourpath(match: re.Match[str]) -> str:
        filename = match.group(1)
        if filename.lower().endswith(".mat"):
            path = data_dir / filename
        else:
            path = figure_dir / filename
        return repr(str(path))

    text = re.sub(r"r'Yourpath\\([^']+)'", replace_yourpath, text)
    text = re.sub(
        r"ax1\.text\(([^,\n]+?\[idx\]),\s*([^,\n]+?\[idx\][^,]*),",
        r"ax1.text(float(np.squeeze(\1)), float(np.squeeze(\2)),",
        text,
    )
    text = text.replace("import matplotlib as mpl", "import matplotlib\nmatplotlib.use('Agg')\nimport matplotlib as mpl", 1)
    text = text.replace("plt.show()", "# interactive display disabled for non-interactive reproduction")
    target.write_text(text, encoding="utf-8")


def prepare_reproduction_tree(
    source_dir: Path,
    target_dir: Path,
    figure_dir: Path,
    filenames: list[str] | None = None,
) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    if filenames is None:
        filenames = [path.name for path in sorted(source_dir.glob("*.py"))]

    prepared = []
    for name in filenames:
        source = source_dir / name
        target = target_dir / name
        if name.endswith(".py"):
            patch_author_script(source, target, data_dir=source_dir, figure_dir=figure_dir)
        else:
            shutil.copy2(source, target)
        prepared.append(target)
    return prepared
