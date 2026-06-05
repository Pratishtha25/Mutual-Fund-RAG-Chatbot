import sys
import os
import unittest
import json
import tempfile
from unittest.mock import patch, MagicMock

# Ensure the backend and ingestion directories are in the path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(backend_path, "ingestion"))
sys.path.insert(0, backend_path)

# Pre-mock index.load to prevent actual file system load during FastAPI import
with patch("app.search.SimilarityIndex.load") as mock_load:
    from app.main import app, sync_data_job, scheduler, index
    from ingestion.corpus_compiler import compile_corpus


class TestScheduler(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.temp_corpus_path = os.path.join(self.test_dir.name, "corpus.json")
        
        # Patch SimilarityIndex.load globally for tests to prevent real vectorization
        self.load_patcher = patch("app.search.SimilarityIndex.load")
        self.mock_load = self.load_patcher.start()

    def tearDown(self):
        self.load_patcher.stop()
        self.test_dir.cleanup()

    @patch("ingestion.corpus_compiler.get_all_stocks_data")
    @patch("ingestion.corpus_compiler.parse_documents_in_directory")
    def test_atomic_compile_writes(self, mock_parse_docs, mock_get_stocks):
        # Setup mocks
        mock_get_stocks.return_value = {
            "test_stock": {
                "name": "Test Stock Ltd",
                "url": "https://groww.in/stocks/test-stock",
                "market_cap": "₹10,000 Cr",
                "pe_ratio": "15.0",
                "dividend_yield": "1.0%",
                "fifty_two_week_high_low": "100 / 50",
                "industry": "Finance",
                "overview": "Overview of Test Stock",
                "management": [{"name": "Jane Doe", "designation": "CEO"}]
            }
        }
        mock_parse_docs.return_value = []

        # Run compile_corpus
        compile_corpus(
            raw_docs_dir=self.test_dir.name,  # empty raw directory
            output_corpus_path=self.temp_corpus_path
        )

        # Check that corpus file was created and is valid JSON
        self.assertTrue(os.path.exists(self.temp_corpus_path))
        with open(self.temp_corpus_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(len(data), 5)  # 5 chunks created for the stock
        self.assertEqual(data[0]["stock_name"], "Test Stock Ltd")
        
        # Verify no .tmp file remains
        self.assertFalse(os.path.exists(self.temp_corpus_path + ".tmp"))

    @patch("app.main.compile_corpus")
    @patch("app.main.index.load")
    @patch("app.main.logger")
    def test_sync_data_job_flow(self, mock_logger, mock_index_load, mock_compile):
        # Run sync_data_job
        sync_data_job()

        # Check compilation and index reload were triggered in order
        mock_compile.assert_called_once_with(
            "backend/data/raw_documents",
            "backend/data/corpus.json"
        )
        mock_index_load.assert_called_once()
        
        # Check logs show reload success
        mock_logger.info.assert_any_call("Scheduler: Fresh corpus compiled.")
        mock_logger.info.assert_any_call("Scheduler: In-memory SimilarityIndex reloaded.")

    @patch("app.main.scheduler.start")
    @patch("app.main.scheduler.shutdown")
    @patch("app.main.scheduler.add_job")
    def test_scheduler_lifespan_lifecycle(self, mock_add_job, mock_shutdown, mock_start):
        from fastapi.testclient import TestClient
        
        # Instantiate test client within context to trigger startup and shutdown lifespans
        with TestClient(app) as client:
            # Scheduler should be started on startup
            mock_start.assert_called_once()
            self.assertEqual(mock_add_job.call_count, 2)  # Daily and weekly sync jobs
            
        # Scheduler should be shut down on client exit
        mock_shutdown.assert_called_once()


if __name__ == "__main__":
    unittest.main()
