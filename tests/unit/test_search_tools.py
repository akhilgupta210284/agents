"""Unit tests for tools/search_tools.py"""
from unittest.mock import MagicMock, patch

import pytest

from tools.search_tools import _rrf_merge


# ─── _rrf_merge (pure function — no mocking needed) ──────────────────────────

class TestRrfMerge:
    def test_empty_inputs_return_empty_list(self):
        assert _rrf_merge([], []) == []

    def test_single_lexical_hit_ranked_correctly(self):
        hits = [
            {"_id": "a", "_source": {"text": "doc a"}},
            {"_id": "b", "_source": {"text": "doc b"}},
        ]
        result = _rrf_merge(hits, [])
        assert result[0]["id"] == "a"
        assert result[1]["id"] == "b"

    def test_single_semantic_hit_ranked_correctly(self):
        hits = [
            {"_id": "x", "_source": {"text": "doc x"}},
            {"_id": "y", "_source": {"text": "doc y"}},
        ]
        result = _rrf_merge([], hits)
        assert result[0]["id"] == "x"

    def test_doc_in_both_lists_outranks_doc_in_one_list(self):
        shared = {"_id": "shared", "_source": {"text": "in both"}}
        only_lex = {"_id": "only_lex", "_source": {"text": "lexical only"}}
        only_sem = {"_id": "only_sem", "_source": {"text": "semantic only"}}

        result = _rrf_merge([shared, only_lex], [shared, only_sem])
        assert result[0]["id"] == "shared"

    def test_result_contains_source_fields(self):
        hits = [{"_id": "doc1", "_source": {"text": "content", "filename": "f.pdf"}}]
        result = _rrf_merge(hits, [])
        assert result[0]["text"] == "content"
        assert result[0]["filename"] == "f.pdf"

    def test_result_contains_id_and_score(self):
        hits = [{"_id": "d1", "_source": {"text": "t"}}]
        result = _rrf_merge(hits, [])
        assert "id" in result[0]
        assert "score" in result[0]
        assert result[0]["id"] == "d1"

    def test_scores_are_positive(self):
        hits = [{"_id": str(i), "_source": {"text": f"doc {i}"}} for i in range(5)]
        result = _rrf_merge(hits, hits)
        for r in result:
            assert r["score"] > 0

    def test_higher_ranked_doc_has_higher_score(self):
        hits = [{"_id": str(i), "_source": {"text": f"doc {i}"}} for i in range(5)]
        result = _rrf_merge(hits, [])
        # Scores must be in descending order
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_custom_k_changes_score_magnitude_not_order(self):
        hits = [{"_id": str(i), "_source": {"text": f"doc {i}"}} for i in range(5)]
        order_k60 = [r["id"] for r in _rrf_merge(hits, [], k=60)]
        order_k1 = [r["id"] for r in _rrf_merge(hits, [], k=1)]
        assert order_k60 == order_k1

    def test_deduplicates_documents_across_lists(self):
        shared = {"_id": "dup", "_source": {"text": "duplicate"}}
        result = _rrf_merge([shared], [shared])
        ids = [r["id"] for r in result]
        assert ids.count("dup") == 1


# ─── _hybrid_search (requires mocking OpenSearch + Bedrock) ──────────────────

class TestHybridSearch:
    @patch("tools.search_tools.get_opensearch_client")
    @patch("tools.search_tools._embed_query")
    def test_unknown_domain_returns_error_message(self, mock_embed, mock_client):
        from tools.search_tools import _hybrid_search
        result = _hybrid_search("nonexistent_domain", "some query")
        assert "Unknown domain" in result
        mock_embed.assert_not_called()

    @patch("tools.search_tools.get_opensearch_client")
    @patch("tools.search_tools._embed_query")
    def test_no_results_returns_not_found_message(self, mock_embed, mock_os_client):
        from tools.search_tools import _hybrid_search
        mock_embed.return_value = [0.0] * 1024
        mock_client = MagicMock()
        mock_client.search.return_value = {"hits": {"hits": []}}
        mock_os_client.return_value = mock_client

        result = _hybrid_search("disease_study", "obscure nonexistent condition")
        assert "No relevant documents found" in result

    @patch("tools.search_tools.get_opensearch_client")
    @patch("tools.search_tools._embed_query")
    def test_result_contains_filename_and_text(self, mock_embed, mock_os_client):
        from tools.search_tools import _hybrid_search
        mock_embed.return_value = [0.1] * 1024
        hit = {
            "_id": "doc1",
            "_source": {
                "text": "Aspirin reduces inflammation via COX inhibition.",
                "filename": "aspirin_study.pdf",
                "domain": "medicine_study",
                "chunk_index": 0,
            },
        }
        mock_client = MagicMock()
        mock_client.search.return_value = {"hits": {"hits": [hit]}}
        mock_os_client.return_value = mock_client

        result = _hybrid_search("medicine_study", "aspirin mechanism")
        assert "aspirin_study.pdf" in result
        assert "Aspirin reduces inflammation" in result

    @patch("tools.search_tools.get_opensearch_client")
    @patch("tools.search_tools._embed_query")
    def test_both_bm25_and_knn_queries_are_issued(self, mock_embed, mock_os_client):
        from tools.search_tools import _hybrid_search
        mock_embed.return_value = [0.1] * 1024
        mock_client = MagicMock()
        mock_client.search.return_value = {"hits": {"hits": []}}
        mock_os_client.return_value = mock_client

        _hybrid_search("disease_study", "fever")
        assert mock_client.search.call_count == 2  # once lexical, once semantic

    @patch("tools.search_tools.get_opensearch_client")
    @patch("tools.search_tools._embed_query")
    def test_top_k_limits_results(self, mock_embed, mock_os_client):
        from tools.search_tools import _hybrid_search
        mock_embed.return_value = [0.1] * 1024
        hits = [
            {"_id": str(i), "_source": {"text": f"text {i}", "filename": f"f{i}.pdf", "chunk_index": i}}
            for i in range(10)
        ]
        mock_client = MagicMock()
        mock_client.search.return_value = {"hits": {"hits": hits}}
        mock_os_client.return_value = mock_client

        result = _hybrid_search("disease_study", "query", top_k=3)
        # Result is a joined string; verify at most 3 separator blocks
        assert result.count("[Source:") <= 3


# ─── Strands @tool wrappers (smoke tests — no OpenSearch required) ────────────

class TestSearchToolWrappers:
    @patch("tools.search_tools._hybrid_search")
    def test_search_disease_study_delegates_correctly(self, mock_search):
        from tools.search_tools import search_disease_study
        mock_search.return_value = "results"
        result = search_disease_study("fever symptoms")
        mock_search.assert_called_once_with("disease_study", "fever symptoms", 5)
        assert result == "results"

    @patch("tools.search_tools._hybrid_search")
    def test_search_medicine_study_delegates_correctly(self, mock_search):
        from tools.search_tools import search_medicine_study
        mock_search.return_value = "drug results"
        search_medicine_study("aspirin dosage", top_k=3)
        mock_search.assert_called_once_with("medicine_study", "aspirin dosage", 3)

    @patch("tools.search_tools._hybrid_search")
    def test_search_medicine_expiry_delegates_correctly(self, mock_search):
        from tools.search_tools import search_medicine_expiry
        mock_search.return_value = "expiry results"
        search_medicine_expiry("shelf life penicillin")
        mock_search.assert_called_once_with("medicine_expiry", "shelf life penicillin", 5)

    @patch("tools.search_tools._hybrid_search")
    def test_search_equipment_study_delegates_correctly(self, mock_search):
        from tools.search_tools import search_equipment_study
        mock_search.return_value = "device results"
        search_equipment_study("calibration MRI scanner", top_k=10)
        mock_search.assert_called_once_with("equipment_study", "calibration MRI scanner", 10)
