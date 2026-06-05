import sys
import os
import unittest
import json
import tempfile
import numpy as np
from unittest.mock import patch, MagicMock

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.search import (
    get_embedding,
    compute_md5,
    SimilarityIndex
)

class TestSearchEngine(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for test corpus and caches
        self.test_dir = tempfile.TemporaryDirectory()
        self.corpus_path = os.path.join(self.test_dir.name, "corpus.json")
        self.cache_path = os.path.join(self.test_dir.name, "embeddings.npy")
        self.hash_path = os.path.join(self.test_dir.name, "corpus_hash.txt")

        # Set up a sample corpus
        self.sample_corpus = [
            {
                "chunk_id": "mf_axis_bluechip_1",
                "type": "mutual_fund",
                "query_type": "exit_load",
                "scheme_name": "Axis Bluechip Fund",
                "content": "Axis Bluechip Fund - The exit load for redemptions within 1 year from allotment is 1.00%.",
                "source_metadata": {"title": "Axis Factsheet"}
            },
            {
                "chunk_id": "mf_ppfas_1",
                "type": "mutual_fund",
                "query_type": "minimum_investment",
                "scheme_name": "Parag Parikh Flexi Cap Fund",
                "content": "Parag Parikh Flexi Cap Fund - The minimum SIP investment is ₹1000.",
                "source_metadata": {"title": "Parag Parikh SID"}
            },
            {
                "chunk_id": "stock_federal_1",
                "type": "stock",
                "query_type": "market_cap",
                "stock_name": "The Federal Bank Ltd",
                "content": "The Federal Bank Ltd has a market cap of approximately ₹34,500 Crores.",
                "source_metadata": {"title": "Federal Bank Stock"}
            }
        ]

        with open(self.corpus_path, "w", encoding="utf-8") as f:
            json.dump(self.sample_corpus, f, indent=2)

    def tearDown(self):
        self.test_dir.cleanup()

    @patch("app.search.requests.post")
    def test_get_embedding_api_success(self, mock_post):
        # Mock /api/embeddings success response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1] * 768}
        mock_post.return_value = mock_response

        emb = get_embedding("test query")
        self.assertEqual(len(emb), 768)
        self.assertEqual(emb[0], 0.1)

    @patch("app.search.requests.post")
    def test_get_embedding_api_fallback(self, mock_post):
        # Mock /api/embeddings failure, but /api/embed success
        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 404
        
        mock_resp_success = MagicMock()
        mock_resp_success.status_code = 200
        mock_resp_success.json.return_value = {"embeddings": [[0.2] * 768]}
        
        mock_post.side_effect = [Exception("404"), mock_resp_success]

        emb = get_embedding("test query")
        self.assertEqual(len(emb), 768)
        self.assertEqual(emb[0], 0.2)

    @patch("app.search.get_embedding")
    def test_similarity_index_load_and_caching(self, mock_get_embedding):
        # Configure mocked embeddings for the 3 chunks:
        # We will make them orthogonal vectors to test search deterministically.
        # Vector size is 768
        vec_axis = [0.0] * 768
        vec_axis[0] = 1.0  # Axis Bluechip Fund vector
        
        vec_ppfas = [0.0] * 768
        vec_ppfas[1] = 1.0  # Parag Parikh Flexi Cap Fund vector
        
        vec_fed = [0.0] * 768
        vec_fed[2] = 1.0  # Federal Bank vector

        mock_get_embedding.side_effect = [vec_axis, vec_ppfas, vec_fed]

        # 1. Initialize and load (this should trigger vectorization and create the cache)
        index = SimilarityIndex(
            corpus_path=self.corpus_path,
            cache_path=self.cache_path,
            hash_path=self.hash_path,
            threshold=0.35
        )
        index.load()

        self.assertEqual(len(index.corpus), 3)
        self.assertIsNotNone(index.normalized_matrix)
        self.assertEqual(index.normalized_matrix.shape, (3, 768))
        self.assertTrue(os.path.exists(self.cache_path))
        self.assertTrue(os.path.exists(self.hash_path))

        # 2. Initialize a second index. It should load from cache, and mock_get_embedding should NOT be called again.
        mock_get_embedding.reset_mock()
        index2 = SimilarityIndex(
            corpus_path=self.corpus_path,
            cache_path=self.cache_path,
            hash_path=self.hash_path,
            threshold=0.35
        )
        index2.load()

        mock_get_embedding.assert_not_called()
        self.assertEqual(index2.normalized_matrix.shape, (3, 768))

    @patch("app.search.get_embedding")
    def test_similarity_search_matching_and_threshold(self, mock_get_embedding):
        # Build vectors
        vec_axis = [0.0] * 768; vec_axis[0] = 1.0
        vec_ppfas = [0.0] * 768; vec_ppfas[1] = 1.0
        vec_fed = [0.0] * 768;   vec_fed[2] = 1.0

        mock_get_embedding.side_effect = [vec_axis, vec_ppfas, vec_fed]

        index = SimilarityIndex(
            corpus_path=self.corpus_path,
            cache_path=self.cache_path,
            hash_path=self.hash_path,
            threshold=0.35
        )
        index.load()

        # Mock the search query vector to align with Parag Parikh (index 1)
        # Query: "What is minimum SIP PPFAS?"
        vec_query = [0.0] * 768
        vec_query[1] = 1.0  # matches index 1 perfectly (score = 1.0)
        mock_get_embedding.side_effect = None
        mock_get_embedding.return_value = vec_query

        results, is_deflected = index.search("What is minimum SIP PPFAS?")
        self.assertFalse(is_deflected)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["chunk_id"], "mf_ppfas_1")
        self.assertAlmostEqual(results[0]["similarity_score"], 1.0)

        # Mock search query with low similarity (under 0.35)
        # Query: "What is the weather?" -> returns a vector that has very low cosine similarity
        vec_query_low = [0.0] * 768
        vec_query_low[10] = 1.0  # orthogonal to all (score = 0.0)
        mock_get_embedding.return_value = vec_query_low

        results, is_deflected = index.search("What is the weather?")
        self.assertTrue(is_deflected)
        self.assertEqual(len(results), 0)

    @patch("app.search.get_embedding")
    def test_entity_alignment_and_out_of_corpus(self, mock_get_embedding):
        # Build vectors
        vec_axis = [0.0] * 768; vec_axis[0] = 1.0
        vec_ppfas = [0.0] * 768; vec_ppfas[1] = 1.0
        vec_fed = [0.0] * 768;   vec_fed[2] = 1.0

        mock_get_embedding.side_effect = [vec_axis, vec_ppfas, vec_fed]

        index = SimilarityIndex(
            corpus_path=self.corpus_path,
            cache_path=self.cache_path,
            hash_path=self.hash_path,
            threshold=0.35
        )
        index.load()

        # Mock query vector matching Federal Bank (index 2)
        vec_query = [0.0] * 768
        vec_query[2] = 1.0
        mock_get_embedding.side_effect = None
        mock_get_embedding.return_value = vec_query

        # Query mentions SBI (out of corpus) -> should deflect immediately
        results, is_deflected = index.search("What is the PE of SBI Bank?")
        self.assertTrue(is_deflected)
        self.assertEqual(len(results), 0)

        # Query mentions Federal Bank, retrieved is Federal Bank -> should succeed
        results, is_deflected = index.search("What is market cap of Federal Bank?")
        self.assertFalse(is_deflected)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["chunk_id"], "stock_federal_1")

        # Query mentions Axis, but query vector returns Federal Bank -> entity mismatch -> should deflect
        results, is_deflected = index.search("PE of Axis Bluechip?")
        self.assertTrue(is_deflected)
        self.assertEqual(len(results), 0)

    # ----------------------------------------------------
    # Integration test (live check - runs if Ollama is running)
    # ----------------------------------------------------
    def test_live_ollama_integration(self):
        import requests
        try:
            # Check if local Ollama is active
            res = requests.get("http://localhost:11434/", timeout=2.0)
            if res.status_code != 200:
                self.skipTest("Ollama is running but returned error code")
        except Exception:
            self.skipTest("Ollama service is not running locally. Skipping live integration test.")

        # If running, check nomic-embed-text is pulled
        try:
            res_tags = requests.get("http://localhost:11434/api/tags", timeout=2.0)
            models = [m["name"] for m in res_tags.json().get("models", [])]
            if "nomic-embed-text:latest" not in models and "nomic-embed-text" not in models:
                self.skipTest("Model 'nomic-embed-text' is not pulled in Ollama. Skipping live test.")
        except Exception:
            self.skipTest("Failed to fetch model list from Ollama. Skipping live test.")

        # Execute live query
        try:
            emb = get_embedding("test live query")
            self.assertEqual(len(emb), 768)
            print("\n[Integration] Successfully pulled live embedding from local Ollama!")
        except Exception as e:
            self.fail(f"Live embedding extraction failed: {e}")

if __name__ == "__main__":
    unittest.main()
