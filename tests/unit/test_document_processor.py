"""Unit tests for etl/document_processor.py"""
import pytest

from etl.document_processor import _split_words, chunk_document, process_documents


# ─── Helper ──────────────────────────────────────────────────────────────────

def _make_doc(text: str, domain: str = "disease_study", **extra) -> dict:
    return {
        "text": text,
        "domain": domain,
        "s3_key": f"medical-docs/{domain}/test.pdf",
        "filename": "test.pdf",
        **extra,
    }


# ─── _split_words ─────────────────────────────────────────────────────────────

class TestSplitWords:
    def test_single_chunk_when_text_fits_in_window(self):
        words = " ".join(["word"] * 50)
        chunks = _split_words(words, size=100, overlap=10)
        assert len(chunks) == 1

    def test_multiple_chunks_produced_for_long_text(self):
        words = " ".join([f"w{i}" for i in range(200)])
        chunks = _split_words(words, size=50, overlap=10)
        assert len(chunks) > 1

    def test_overlap_shares_words_between_adjacent_chunks(self):
        words = " ".join([f"w{i}" for i in range(100)])
        chunks = _split_words(words, size=30, overlap=10)
        tail = chunks[0].split()[-10:]
        head = chunks[1].split()[:10]
        assert tail == head

    def test_zero_overlap_no_shared_words(self):
        words = " ".join([f"w{i}" for i in range(60)])
        chunks = _split_words(words, size=20, overlap=0)
        for i in range(len(chunks) - 1):
            assert set(chunks[i].split()).isdisjoint(set(chunks[i + 1].split()))

    def test_empty_string_returns_empty_list(self):
        assert _split_words("", size=100, overlap=10) == []

    def test_exact_size_text_produces_one_chunk(self):
        words = " ".join([f"w{i}" for i in range(10)])
        chunks = _split_words(words, size=10, overlap=0)
        assert len(chunks) == 1
        assert len(chunks[0].split()) == 10

    def test_chunk_word_count_does_not_exceed_size(self):
        words = " ".join([f"w{i}" for i in range(500)])
        chunks = _split_words(words, size=50, overlap=5)
        for chunk in chunks:
            assert len(chunk.split()) <= 50


# ─── chunk_document ───────────────────────────────────────────────────────────

class TestChunkDocument:
    def test_returns_list_of_dicts(self):
        doc = _make_doc(" ".join(["word"] * 600))
        chunks = chunk_document(doc, chunk_size=100, overlap=10)
        assert isinstance(chunks, list)
        assert all(isinstance(c, dict) for c in chunks)

    def test_every_chunk_has_required_keys(self):
        doc = _make_doc("hello world foo bar baz qux")
        chunks = chunk_document(doc, chunk_size=3, overlap=1)
        for chunk in chunks:
            for key in ("text", "domain", "filename", "chunk_index", "total_chunks"):
                assert key in chunk, f"Missing key '{key}' in chunk"

    def test_domain_preserved_on_every_chunk(self):
        doc = _make_doc("some medical content here today", domain="medicine_study")
        chunks = chunk_document(doc)
        for chunk in chunks:
            assert chunk["domain"] == "medicine_study"

    def test_filename_preserved_on_every_chunk(self):
        doc = _make_doc("text " * 50)
        doc["filename"] = "aspirin_study.pdf"
        chunks = chunk_document(doc)
        for chunk in chunks:
            assert chunk["filename"] == "aspirin_study.pdf"

    def test_chunk_index_is_sequential_from_zero(self):
        doc = _make_doc(" ".join([f"word{i}" for i in range(300)]))
        chunks = chunk_document(doc, chunk_size=50, overlap=10)
        assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))

    def test_total_chunks_is_consistent(self):
        doc = _make_doc(" ".join([f"word{i}" for i in range(300)]))
        chunks = chunk_document(doc, chunk_size=50, overlap=10)
        for chunk in chunks:
            assert chunk["total_chunks"] == len(chunks)

    def test_phi_keys_stripped_from_metadata(self):
        doc = _make_doc(
            "content " * 20,
            patient_id="P-99",
            mrn="MRN-888",
            ssn="000-11-2222",
        )
        chunks = chunk_document(doc)
        for chunk in chunks:
            assert "patient_id" not in chunk
            assert "mrn" not in chunk
            assert "ssn" not in chunk

    def test_empty_text_produces_no_chunks(self):
        doc = _make_doc("   \n\t  ")
        assert chunk_document(doc) == []

    def test_whitespace_only_chunks_skipped(self):
        doc = _make_doc("real content here " + "   " * 100 + " more real content")
        chunks = chunk_document(doc, chunk_size=5, overlap=0)
        for chunk in chunks:
            assert chunk["text"].strip() != ""

    def test_custom_chunk_size_and_overlap(self):
        doc = _make_doc(" ".join([f"w{i}" for i in range(200)]))
        chunks = chunk_document(doc, chunk_size=40, overlap=5)
        assert all(len(c["text"].split()) <= 40 for c in chunks)


# ─── process_documents ────────────────────────────────────────────────────────

class TestProcessDocuments:
    def test_empty_list_returns_empty(self):
        assert process_documents([]) == []

    def test_processes_multiple_documents(self):
        docs = [
            _make_doc("alpha " * 100, domain="disease_study"),
            _make_doc("beta " * 100, domain="medicine_study"),
        ]
        chunks = process_documents(docs)
        domains = {c["domain"] for c in chunks}
        assert "disease_study" in domains
        assert "medicine_study" in domains

    def test_total_chunk_count_across_documents(self):
        docs = [_make_doc(" ".join([f"w{i}" for i in range(200)]))] * 3
        chunks = process_documents(docs)
        assert len(chunks) >= 3  # each doc produces at least one chunk
