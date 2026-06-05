import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure the backend directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock SimilarityIndex.load at import time to prevent trying to load corpus.json
with patch("app.search.SimilarityIndex.load") as mock_load:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.guardrails import get_pii_response, get_advisory_response


class TestMainRouter(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_query_length_limit(self):
        # 301 characters should trigger a validation error (422)
        long_query = "a" * 301
        response = self.client.post("/api/chat", json={"message": long_query})
        self.assertEqual(response.status_code, 422)

        # 300 characters should pass validation
        valid_query = "a" * 300
        with patch("app.main.is_pii", return_value=True):
            response = self.client.post("/api/chat", json={"message": valid_query})
            self.assertEqual(response.status_code, 200)

    def test_pii_interception(self):
        # Queries containing PII must be intercepted immediately
        response = self.client.post("/api/chat", json={"message": "My PAN is ABCDE1234F"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["contains_pii"], True)
        self.assertEqual(data["is_deflected"], False)
        self.assertIn("For your security, please do not share personal information", data["answer"])

    def test_advisory_deflection(self):
        # Queries with advisory intent must be deflected immediately
        response = self.client.post("/api/chat", json={"message": "should I buy Federal Bank shares?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["contains_pii"], False)
        self.assertEqual(data["is_deflected"], True)
        self.assertIn("I am a facts-only assistant designed to provide official stock and fund details", data["answer"])

    @patch("app.main.index.search")
    def test_retrieval_deflection(self, mock_search):
        # If retrieval coordinator returns deflection (out-of-corpus or mismatch)
        mock_search.return_value = ([], True)

        response = self.client.post("/api/chat", json={"message": "What is the NAV of SBI Bluechip?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["contains_pii"], False)
        self.assertEqual(data["is_deflected"], False)
        self.assertEqual(data["answer"], "I do not have this information in my verified records.")

    @patch("app.main.index.search")
    @patch("app.llm.query_groq")
    def test_successful_rag_response_with_citations(self, mock_query_groq, mock_search):
        # Mock retrieval matching Axis Bluechip Fund chunk
        mock_search.return_value = ([
            {
                "chunk_id": "mf_axis_1",
                "type": "mutual_fund",
                "scheme_name": "Axis Bluechip Fund",
                "content": "Axis Bluechip Fund exit load is 1.00%.",
                "source_metadata": {"title": "Axis Bluechip Fund SID (2024)"}
            }
        ], False)

        # Case A: LLM returns cited response
        mock_query_groq.return_value = "The exit load for Axis Bluechip Fund is 1.00% [Source: Axis Bluechip Fund SID (2024)]."
        response = self.client.post("/api/chat", json={"message": "What is the exit load of Axis Bluechip?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["answer"], "The exit load for Axis Bluechip Fund is 1.00% [Source: Axis Bluechip Fund SID (2024)].")

        # Case B: LLM returns response without citation (post-processor should append it)
        mock_query_groq.return_value = "The exit load for Axis Bluechip Fund is 1.00%."
        response = self.client.post("/api/chat", json={"message": "What is the exit load of Axis Bluechip?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["answer"], "The exit load for Axis Bluechip Fund is 1.00%. [Source: Axis Bluechip Fund SID (2024)]")

    @patch("app.main.index.search")
    @patch("app.llm.query_groq")
    def test_groq_timeout_fallback(self, mock_query_groq, mock_search):
        # Mock successful search matching Federal Bank chunk
        mock_search.return_value = ([
            {
                "chunk_id": "stock_fed_1",
                "type": "stock",
                "stock_name": "The Federal Bank Ltd",
                "content": "The Federal Bank Ltd PE is 12.34.",
                "source_metadata": {"title": "Federal Bank Stock Page", "url": "https://groww.in/stocks/the-federal-bank-ltd"}
            }
        ], False)

        # Mock Groq timing out / failing (query_groq returns the fallback traffic warning)
        mock_query_groq.return_value = "The assistant is experiencing high traffic. Please try again shortly."

        response = self.client.post("/api/chat", json={"message": "PE of Federal Bank?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["answer"], "The assistant is experiencing high traffic. Please try again shortly.")
        self.assertEqual(data["contains_pii"], False)
        self.assertEqual(data["is_deflected"], False)


if __name__ == "__main__":
    unittest.main()
