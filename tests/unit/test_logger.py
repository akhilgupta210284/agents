"""Unit tests for utils/logger.py"""
import json
import logging
import re
from unittest.mock import MagicMock, patch

import pytest

from utils.logger import _mask_phi, _s3_key, audit


class TestMaskPhi:
    def test_masks_ssn(self):
        result = _mask_phi("SSN is 123-45-6789 in the record")
        assert "123-45-6789" not in result
        assert "***-**-****" in result

    def test_masks_email(self):
        result = _mask_phi("Contact doctor@hospital.org for details")
        assert "doctor@hospital.org" not in result
        assert "[EMAIL_REDACTED]" in result

    def test_masks_phone_with_dashes(self):
        result = _mask_phi("Call 555-867-5309 anytime")
        assert "555-867-5309" not in result
        assert "[PHONE_REDACTED]" in result

    def test_masks_phone_with_dots(self):
        result = _mask_phi("Phone: 555.867.5309")
        assert "555.867.5309" not in result
        assert "[PHONE_REDACTED]" in result

    def test_masks_long_numeric_id(self):
        result = _mask_phi("Patient ID: 1234567890")
        assert "[ID_REDACTED]" in result

    def test_preserves_normal_medical_text(self):
        text = "The patient has type-2 diabetes and hypertension."
        assert _mask_phi(text) == text

    def test_masks_multiple_phi_in_one_string(self):
        text = "User doc@clinic.com, SSN 987-65-4321, phone 800-555-1234"
        result = _mask_phi(text)
        assert "doc@clinic.com" not in result
        assert "987-65-4321" not in result
        assert "800-555-1234" not in result

    def test_empty_string_returns_empty(self):
        assert _mask_phi("") == ""


class TestS3Key:
    def test_key_starts_with_audit_prefix(self):
        key = _s3_key("QUERY")
        assert key.startswith("audit-logs/")

    def test_key_contains_event_type(self):
        assert "ETL_RUN" in _s3_key("ETL_RUN")
        assert "DATA_ACCESS" in _s3_key("DATA_ACCESS")

    def test_key_contains_yyyy_mm_dd_path(self):
        key = _s3_key("QUERY")
        assert re.search(r"\d{4}/\d{2}/\d{2}/", key), f"No date path found in: {key}"

    def test_key_ends_with_json(self):
        assert _s3_key("QUERY").endswith(".json")

    def test_keys_are_unique(self):
        keys = {_s3_key("QUERY") for _ in range(20)}
        assert len(keys) == 20  # uuid suffix ensures uniqueness


class TestAudit:
    def test_audit_emits_log_record(self, caplog):
        with caplog.at_level(logging.INFO, logger="medical-agent"):
            audit("QUERY", user_id="u-001", query="What is aspirin?")
        assert len(caplog.records) >= 1

    def test_audit_log_contains_event_type(self, caplog):
        with caplog.at_level(logging.INFO, logger="medical-agent"):
            audit("DATA_ACCESS", user_id="u-002")
        combined = " ".join(r.message for r in caplog.records)
        assert "DATA_ACCESS" in combined

    def test_audit_masks_phi_in_log(self, caplog):
        with caplog.at_level(logging.INFO, logger="medical-agent"):
            audit("QUERY", user_id="u-003", query="Patient SSN 999-88-7777 asks about aspirin")
        combined = " ".join(r.message for r in caplog.records)
        assert "999-88-7777" not in combined

    @patch("utils.logger.boto3")
    def test_audit_writes_to_s3_when_bucket_configured(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        with patch("utils.logger.AUDIT_LOG_BUCKET", "my-audit-bucket"):
            audit("QUERY", user_id="u-004", query="test")

        mock_s3.put_object.assert_called_once()
        kwargs = mock_s3.put_object.call_args.kwargs
        assert kwargs["Bucket"] == "my-audit-bucket"
        assert kwargs["ContentType"] == "application/json"
        assert kwargs["ServerSideEncryption"] == "aws:kms"

    @patch("utils.logger.boto3")
    def test_audit_s3_record_contains_required_fields(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        with patch("utils.logger.AUDIT_LOG_BUCKET", "my-audit-bucket"):
            audit("TOOL_CALL", user_id="u-005", domain="medicine_study", agent_name="qa")

        body = json.loads(mock_s3.put_object.call_args.kwargs["Body"])
        assert body["event_type"] == "TOOL_CALL"
        assert body["user_id"] == "u-005"
        assert body["domain"] == "medicine_study"
        assert body["agent"] == "qa"
        assert "timestamp" in body
        assert "event_id" in body

    @patch("utils.logger.boto3")
    def test_audit_skips_s3_when_no_bucket(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        with patch("utils.logger.AUDIT_LOG_BUCKET", ""):
            audit("QUERY", user_id="u-006")

        mock_s3.put_object.assert_not_called()

    @patch("utils.logger.boto3")
    def test_audit_does_not_raise_on_s3_failure(self, mock_boto3):
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = Exception("S3 connection refused")
        mock_boto3.client.return_value = mock_s3

        with patch("utils.logger.AUDIT_LOG_BUCKET", "bucket"):
            # Must not propagate the exception
            audit("QUERY", user_id="u-007")
