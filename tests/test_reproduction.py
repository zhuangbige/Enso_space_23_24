import tempfile
import unittest
from pathlib import Path

from el_nino_decoupling.reproduction import patch_author_script


class ReproductionPreparationTest(unittest.TestCase):
    def test_patch_author_script_rewrites_paths_and_backend(self):
        source = "\n".join(
            [
                "import matplotlib as mpl",
                "mat_contents = scio.loadmat(r'Yourpath\\Fig1.mat')",
                "ax1.text(sstanomnino3JuntoJan[idx], uwindCWPJuntoJan[idx]-0.62, annotations[year])",
                "plt.show()",
                "fig.savefig(r'Yourpath\\Fig1.png', dpi=500)",
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "Fig1.py"
            input_path.write_text(source, encoding="utf-8")
            output_path = root / "patched" / "Fig1.py"

            patch_author_script(
                input_path,
                output_path,
                data_dir=root / "data",
                figure_dir=root / "figures",
            )

            patched = output_path.read_text(encoding="utf-8")

        self.assertIn("matplotlib.use('Agg')", patched)
        self.assertIn(str(root / "data" / "Fig1.mat"), patched)
        self.assertIn(str(root / "figures" / "Fig1.png"), patched)
        self.assertIn("ax1.text(float(np.squeeze(sstanomnino3JuntoJan[idx]))", patched)
        self.assertNotIn("plt.show()", patched)


if __name__ == "__main__":
    unittest.main()
