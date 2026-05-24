import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ScriptEntryPointTest(unittest.TestCase):
    def test_scripts_run_from_repository_root(self):
        commands = (
            ("scripts/list_data_sources.py", "--priority", "core"),
            ("scripts/list_data_sources.py", "--priority", "paper"),
            ("scripts/make_agcm_matrix.py", "--include-optional"),
            ("scripts/diagnostic_checklist.py",),
        )

        for command in commands:
            with self.subTest(command=command[0]):
                result = subprocess.run(
                    [sys.executable, *command],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("ModuleNotFoundError", result.stderr)


if __name__ == "__main__":
    unittest.main()
