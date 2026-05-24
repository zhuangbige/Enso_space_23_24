import tempfile
import unittest
from pathlib import Path

from el_nino_decoupling.zenodo import (
    DEFAULT_RECORD_ID,
    ZenodoFile,
    build_download_url,
    classify_files,
    record_files_from_metadata,
    write_manifest,
)


class ZenodoAcquisitionTest(unittest.TestCase):
    def test_build_download_url_uses_record_file_endpoint(self):
        url = build_download_url("Fig1.py")

        self.assertEqual(
            url,
            f"https://zenodo.org/records/{DEFAULT_RECORD_ID}/files/Fig1.py?download=1",
        )

    def test_record_files_from_metadata_reads_current_and_legacy_shapes(self):
        metadata = {
            "files": [
                {
                    "key": "Fig1.py",
                    "size": 123,
                    "checksum": "md5:abc",
                    "links": {"self": "https://example.test/Fig1.py"},
                },
                {
                    "filename": "Fig1.mat",
                    "filesize": 456,
                    "checksum": "md5:def",
                    "links": {"download": "https://example.test/Fig1.mat"},
                },
            ]
        }

        files = record_files_from_metadata(metadata)

        self.assertEqual(files[0], ZenodoFile("Fig1.py", 123, "md5:abc", "https://example.test/Fig1.py"))
        self.assertEqual(files[1], ZenodoFile("Fig1.mat", 456, "md5:def", "https://example.test/Fig1.mat"))

    def test_classify_files_groups_main_extended_and_supplementary(self):
        groups = classify_files(
            [
                ZenodoFile("Fig1.py", 1, "md5:a", "url"),
                ZenodoFile("Extended_Data_Fig1.mat", 1, "md5:b", "url"),
                ZenodoFile("Supplementary_Fig1.py", 1, "md5:c", "url"),
                ZenodoFile("readme.txt", 1, "md5:d", "url"),
            ]
        )

        self.assertEqual(groups["main"], ["Fig1.py"])
        self.assertEqual(groups["extended"], ["Extended_Data_Fig1.mat"])
        self.assertEqual(groups["supplementary"], ["Supplementary_Fig1.py"])
        self.assertEqual(groups["helpers"], ["readme.txt"])

    def test_write_manifest_creates_small_reproducible_inventory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = Path(tmpdir) / "manifest.csv"
            write_manifest(
                [
                    ZenodoFile("Fig1.py", 123, "md5:abc", "https://example.test/Fig1.py"),
                    ZenodoFile("Fig1.mat", 456, "md5:def", "https://example.test/Fig1.mat"),
                ],
                manifest,
            )

            text = manifest.read_text(encoding="utf-8")

        self.assertIn("name,size,checksum,download_url", text)
        self.assertIn("Fig1.py,123,md5:abc,https://example.test/Fig1.py", text)


if __name__ == "__main__":
    unittest.main()
