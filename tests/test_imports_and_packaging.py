import unittest
import importlib

class TestImportsAndPackaging(unittest.TestCase):
    def test_absolute_module_imports(self):
        modules_to_test = [
            "Tackle4LossContentExtraction.core.clustering.cluster_manager",
            "Tackle4LossContentExtraction.core.db.fetch_unprocessed_articles",
            "Tackle4LossContentExtraction.modules.clustering.cluster_articles",
            "Tackle4LossContentExtraction.modules.extraction.extractContent",
            "Tackle4LossContentExtraction.cluster_pipeline",
            "Tackle4LossContentExtraction.cleanup_pipeline",
        ]
        for module_name in modules_to_test:
            with self.subTest(module=module_name):
                try:
                    module = importlib.import_module(module_name)
                    self.assertIsNotNone(module, f"Failed to import {module_name}")
                except ImportError as e:
                    self.fail(f"ImportError when importing {module_name}: {e}")

    def test_specific_imports(self):
        try:
            from Tackle4LossContentExtraction.cluster_pipeline import process_new
            self.assertIsNotNone(process_new, "process_new from cluster_pipeline should not be None")
        except ImportError as e:
            self.fail(f"Failed to import process_new from Tackle4LossContentExtraction.cluster_pipeline: {e}")

        # Test import of a function from cleanup_pipeline if it were refactored
        # For now, we'll try to import a known function if available, or just the module
        # cleanup_pipeline.py executes its main logic in __name__ == "__main__"
        # However, it does import get_unprocessed_articles, we can check that submodule's function
        try:
            from Tackle4LossContentExtraction.core.db.fetch_unprocessed_articles import get_unprocessed_articles
            self.assertIsNotNone(get_unprocessed_articles, "get_unprocessed_articles from core.db.fetch_unprocessed_articles should not be None")
        except ImportError as e:
            self.fail(f"Failed to import get_unprocessed_articles: {e}")

    def test_cluster_pipeline_import(self):
        try:
            module = importlib.import_module("Tackle4LossContentExtraction.cluster_pipeline")
            self.assertIsNotNone(module, "Failed to import Tackle4LossContentExtraction.cluster_pipeline")
        except ImportError as e:
            self.fail(f"ImportError when importing Tackle4LossContentExtraction.cluster_pipeline: {e}")

    def test_cleanup_pipeline_import(self):
        try:
            module = importlib.import_module("Tackle4LossContentExtraction.cleanup_pipeline")
            self.assertIsNotNone(module, "Failed to import Tackle4LossContentExtraction.cleanup_pipeline")
        except ImportError as e:
            self.fail(f"ImportError when importing Tackle4LossContentExtraction.cleanup_pipeline: {e}")

if __name__ == '__main__':
    unittest.main()
