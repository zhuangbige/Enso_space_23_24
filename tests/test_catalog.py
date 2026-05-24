import unittest

from el_nino_decoupling.catalog import (
    CORE_DATASET_IDS,
    EXPANSION_DATASET_IDS,
    PAPER_DATASET_IDS,
    get_dataset,
    list_datasets,
)


class DataCatalogTest(unittest.TestCase):
    def test_core_catalog_contains_required_priority_datasets(self):
        datasets = list_datasets(priority="core")
        dataset_ids = {dataset.id for dataset in datasets}

        self.assertEqual(set(CORE_DATASET_IDS), dataset_ids)
        self.assertIn("era5", dataset_ids)
        self.assertIn("oisst_v2_1", dataset_ids)
        self.assertIn("ersst_v5", dataset_ids)
        self.assertIn("gpcp", dataset_ids)
        self.assertIn("noaa_olr", dataset_ids)
        self.assertIn("oras5", dataset_ids)
        self.assertIn("tao_triton", dataset_ids)

    def test_expansion_catalog_keeps_optional_products_separate(self):
        datasets = list_datasets(priority="expansion")
        dataset_ids = {dataset.id for dataset in datasets}

        self.assertEqual(set(EXPANSION_DATASET_IDS), dataset_ids)
        self.assertIn("glorys12v1", dataset_ids)
        self.assertIn("argo", dataset_ids)
        self.assertIn("duacs", dataset_ids)

    def test_source_paper_catalog_contains_declared_data_availability(self):
        datasets = list_datasets(priority="paper")
        dataset_ids = {dataset.id for dataset in datasets}

        self.assertEqual(set(PAPER_DATASET_IDS), dataset_ids)
        self.assertIn("paper_zenodo", dataset_ids)
        self.assertIn("godas", dataset_ids)
        self.assertIn("cesm_lens2", dataset_ids)

    def test_dataset_records_include_access_and_research_use(self):
        era5 = get_dataset("era5")

        self.assertEqual(era5.priority, "core")
        self.assertIn("u850", era5.variables)
        self.assertIn("slp", era5.variables)
        self.assertIn("velocity_potential_200", era5.variables)
        self.assertTrue(era5.official_url.startswith("https://"))
        self.assertIn("Walker", era5.research_use)

    def test_source_paper_records_capture_figure_or_methods_use(self):
        archive = get_dataset("paper_zenodo")
        godas = get_dataset("godas")

        self.assertEqual(archive.priority, "paper")
        self.assertIn("figure data", archive.research_use)
        self.assertIn("temperature", godas.variables)
        self.assertIn("Methods", godas.access_notes)


if __name__ == "__main__":
    unittest.main()
