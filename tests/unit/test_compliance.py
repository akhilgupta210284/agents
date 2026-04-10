"""Unit tests for utils/compliance.py"""
import pytest
from unittest.mock import MagicMock

from utils.compliance import (
    ALLOWED_DOMAINS_BY_ROLE,
    SENSITIVE_METADATA_KEYS,
    assert_tls_endpoint,
    check_domain_access,
    delete_user_data,
    strip_sensitive_metadata,
)


class TestCheckDomainAccess:
    def test_clinician_allowed_domains(self):
        assert check_domain_access("clinician", "disease_study") is True
        assert check_domain_access("clinician", "medicine_study") is True
        assert check_domain_access("clinician", "medicine_expiry") is True

    def test_clinician_blocked_from_equipment(self):
        assert check_domain_access("clinician", "equipment_study") is False

    def test_lab_technician_allowed_domains(self):
        assert check_domain_access("lab_technician", "equipment_study") is True
        assert check_domain_access("lab_technician", "medicine_study") is True

    def test_lab_technician_blocked_from_disease(self):
        assert check_domain_access("lab_technician", "disease_study") is False

    def test_administrator_has_full_access(self):
        for domain in ["disease_study", "medicine_study", "medicine_expiry", "equipment_study"]:
            assert check_domain_access("administrator", domain) is True

    def test_researcher_has_full_access(self):
        for domain in ["disease_study", "medicine_study", "medicine_expiry", "equipment_study"]:
            assert check_domain_access("researcher", domain) is True

    def test_unknown_role_has_no_access(self):
        assert check_domain_access("unknown_role", "disease_study") is False
        assert check_domain_access("", "medicine_study") is False

    def test_invalid_domain_returns_false(self):
        assert check_domain_access("administrator", "nonexistent_domain") is False


class TestStripSensitiveMetadata:
    def test_removes_patient_id(self):
        meta = {"patient_id": "123", "title": "Study A", "domain": "disease_study"}
        result = strip_sensitive_metadata(meta)
        assert "patient_id" not in result
        assert result["title"] == "Study A"
        assert result["domain"] == "disease_study"

    def test_removes_all_sensitive_keys(self):
        phi_meta = {
            "patient_id": "P123",
            "mrn": "MRN456",
            "dob": "1990-01-01",
            "ssn": "123-45-6789",
            "nhs_number": "NHS123",
        }
        safe_meta = {"domain": "medicine_study", "filename": "drug.pdf", "page": 1}
        result = strip_sensitive_metadata({**phi_meta, **safe_meta})
        for key in SENSITIVE_METADATA_KEYS:
            assert key not in result
        assert result == safe_meta

    def test_empty_dict_returns_empty(self):
        assert strip_sensitive_metadata({}) == {}

    def test_no_sensitive_keys_unchanged(self):
        meta = {"domain": "equipment_study", "filename": "device.pdf", "chunk_index": 0}
        assert strip_sensitive_metadata(meta) == meta

    def test_does_not_mutate_original(self):
        meta = {"patient_id": "P99", "domain": "disease_study"}
        _ = strip_sensitive_metadata(meta)
        assert "patient_id" in meta  # original untouched


class TestAssertTlsEndpoint:
    def test_localhost_allowed_without_https(self):
        # Must not raise — localhost is always allowed (local dev)
        assert_tls_endpoint("localhost")

    def test_https_remote_host_passes(self):
        assert_tls_endpoint("https://search.us-east-1.es.amazonaws.com")

    def test_plain_hostname_raises_value_error(self):
        with pytest.raises(ValueError, match="HIPAA"):
            assert_tls_endpoint("search.us-east-1.es.amazonaws.com")

    def test_http_prefix_not_sufficient(self):
        # http:// is not https:// — should raise
        with pytest.raises(ValueError):
            assert_tls_endpoint("http://search.example.com")


class TestDeleteUserData:
    def test_calls_delete_by_query_for_every_index(self):
        mock_client = MagicMock()
        mock_client.delete_by_query.return_value = {"deleted": 5}

        from config.settings import OPENSEARCH_INDICES
        result = delete_user_data("user-123", mock_client)

        assert mock_client.delete_by_query.call_count == len(OPENSEARCH_INDICES)
        assert set(result.keys()) == set(OPENSEARCH_INDICES.keys())

    def test_returns_deleted_counts_per_domain(self):
        mock_client = MagicMock()
        mock_client.delete_by_query.return_value = {"deleted": 7}
        result = delete_user_data("user-abc", mock_client)
        for count in result.values():
            assert count == 7

    def test_handles_zero_deletions(self):
        mock_client = MagicMock()
        mock_client.delete_by_query.return_value = {"deleted": 0}
        result = delete_user_data("ghost-user", mock_client)
        for count in result.values():
            assert count == 0

    def test_query_uses_correct_user_id(self):
        mock_client = MagicMock()
        mock_client.delete_by_query.return_value = {"deleted": 0}
        delete_user_data("target-user-xyz", mock_client)
        for call in mock_client.delete_by_query.call_args_list:
            body = call.kwargs.get("body") or call.args[1]
            assert body["query"]["term"]["user_id"] == "target-user-xyz"
