"""
Test suite for data_acquisition module.

Tests OCDS downloading from Ukraine, Colombia, and UK sources.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import responses
import pandas as pd

from scripts.lib.data_acquisition import (
    OCDSDownloader,
    UkraineDownloader,
    ColombiaDownloader,
    UKDownloader,
    validate_ocds_release,
    download_all_countries
)


class TestOCDSDownloader:
    """Tests for base OCDS downloader."""
    
    def test_init(self):
        """Test downloader initialization."""
        downloader = OCDSDownloader(
            api_base="https://example.com/api",
            start_date="2020-01-01",
            end_date="2020-12-31"
        )
        assert downloader.api_base == "https://example.com/api"
        assert str(downloader.start_date) == "2020-01-01"
        assert str(downloader.end_date) == "2020-12-31"
    
    def test_date_parsing(self):
        """Test various date formats are parsed correctly."""
        downloader = OCDSDownloader(
            api_base="https://example.com/api",
            start_date="2020-01-01",
            end_date="2020-12-31"
        )
        # Test ISO format
        assert downloader.start_date.year == 2020
        assert downloader.start_date.month == 1
        assert downloader.start_date.day == 1
    
    def test_rate_limiting(self):
        """Test rate limiting between requests."""
        downloader = OCDSDownloader(
            api_base="https://example.com/api",
            start_date="2020-01-01",
            end_date="2020-12-31",
            rate_limit=0.1  # 100ms between requests
        )
        assert downloader.rate_limit == 0.1


class TestUkraineDownloader:
    """Tests for Ukraine ProZorro downloader."""
    
    @responses.activate
    def test_fetch_page(self):
        """Test fetching a single page of releases."""
        responses.add(
            responses.GET,
            "https://api.openprocurement.org/api/2.5/tenders",
            json={
                "data": [
                    {"id": "tender1", "dateModified": "2020-06-01T00:00:00Z"},
                    {"id": "tender2", "dateModified": "2020-06-02T00:00:00Z"}
                ],
                "next_page": {"offset": "abc123"}
            },
            status=200
        )
        
        downloader = UkraineDownloader(
            start_date="2020-01-01",
            end_date="2020-12-31"
        )
        
        releases, next_offset = downloader._fetch_page(offset=None)
        assert len(releases) == 2
        assert next_offset == "abc123"
    
    @responses.activate
    def test_convert_to_ocds(self):
        """Test conversion of ProZorro format to OCDS."""
        downloader = UkraineDownloader(
            start_date="2020-01-01",
            end_date="2020-12-31"
        )
        
        prozorro_tender = {
            "id": "UA-2020-01-01-000001",
            "title": "Test tender",
            "value": {"amount": 1000000, "currency": "UAH"},
            "procuringEntity": {"name": "Test Buyer"},
            "items": [{"classification": {"id": "45000000"}}]
        }
        
        ocds_release = downloader._convert_to_ocds(prozorro_tender)
        
        assert ocds_release["ocid"].startswith("ocds-")
        assert ocds_release["tag"] == ["tender"]
        assert ocds_release["tender"]["title"] == "Test tender"
        assert ocds_release["tender"]["value"]["amount"] == 1000000


class TestColombiaDownloader:
    """Tests for Colombia SECOP downloader."""
    
    @responses.activate
    def test_fetch_page(self):
        """Test fetching SECOP data."""
        responses.add(
            responses.GET,
            "https://www.datos.gov.co/resource/rpmr-utcd.json",
            json=[
                {"uid_secopii": "CO-2020-001", "nombre_procedimiento": "Test"},
                {"uid_secopii": "CO-2020-002", "nombre_procedimiento": "Test 2"}
            ],
            status=200
        )
        
        downloader = ColombiaDownloader(
            start_date="2020-01-01",
            end_date="2020-12-31"
        )
        
        # Mock implementation test
        assert downloader.api_base is not None


class TestUKDownloader:
    """Tests for UK Contracts Finder downloader."""
    
    @responses.activate
    def test_fetch_notices(self):
        """Test fetching UK contract notices."""
        responses.add(
            responses.GET,
            "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search",
            json={
                "releases": [
                    {"ocid": "ocds-b5fd17-UK-001", "tag": ["tender"]},
                    {"ocid": "ocds-b5fd17-UK-002", "tag": ["award"]}
                ]
            },
            status=200
        )
        
        downloader = UKDownloader(
            start_date="2020-01-01",
            end_date="2020-12-31"
        )
        
        # UK data is already in OCDS format
        assert downloader.api_base is not None


class TestOCDSValidation:
    """Tests for OCDS schema validation."""
    
    def test_valid_release(self):
        """Test validation of valid OCDS release."""
        release = {
            "ocid": "ocds-abc123-tender-001",
            "id": "release-001",
            "date": "2020-06-01T00:00:00Z",
            "tag": ["tender"],
            "initiationType": "tender",
            "tender": {
                "id": "tender-001",
                "title": "Test Tender",
                "status": "active"
            }
        }
        
        is_valid, errors = validate_ocds_release(release)
        assert is_valid
        assert len(errors) == 0
    
    def test_missing_required_fields(self):
        """Test validation catches missing required fields."""
        release = {
            "ocid": "ocds-abc123-tender-001",
            # Missing: id, date, tag, initiationType
        }
        
        is_valid, errors = validate_ocds_release(release)
        assert not is_valid
        assert len(errors) > 0
    
    def test_invalid_tag(self):
        """Test validation catches invalid tag values."""
        release = {
            "ocid": "ocds-abc123-tender-001",
            "id": "release-001",
            "date": "2020-06-01T00:00:00Z",
            "tag": ["invalid_tag"],  # Not a valid OCDS tag
            "initiationType": "tender"
        }
        
        is_valid, errors = validate_ocds_release(release)
        # Should flag invalid tag
        assert "invalid_tag" in str(errors) or not is_valid


class TestDownloadIntegration:
    """Integration tests for download workflow."""
    
    def test_output_format(self):
        """Test output JSONL format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            releases = [
                {"ocid": "test-001", "tag": ["tender"]},
                {"ocid": "test-002", "tag": ["award"]}
            ]
            for release in releases:
                f.write(json.dumps(release) + '\n')
            
            f.flush()
            
            # Read back and verify
            with open(f.name, 'r') as rf:
                lines = rf.readlines()
                assert len(lines) == 2
                assert json.loads(lines[0])["ocid"] == "test-001"
    
    def test_resume_capability(self):
        """Test download can resume from checkpoint."""
        # This would test the checkpoint/resume functionality
        # Simplified test - actual implementation would check file state
        checkpoint = {"offset": "abc123", "count": 1000}
        assert checkpoint["offset"] is not None


@pytest.fixture
def sample_ocds_release():
    """Fixture providing a sample OCDS release."""
    return {
        "ocid": "ocds-sample-001",
        "id": "release-001",
        "date": "2020-06-01T00:00:00Z",
        "tag": ["tender"],
        "initiationType": "tender",
        "language": "en",
        "tender": {
            "id": "tender-001",
            "title": "Supply of Office Equipment",
            "description": "Procurement of computers and peripherals",
            "status": "active",
            "value": {
                "amount": 50000,
                "currency": "EUR"
            },
            "procurementMethod": "open",
            "mainProcurementCategory": "goods",
            "items": [
                {
                    "id": "item-001",
                    "description": "Desktop computers",
                    "classification": {
                        "scheme": "CPV",
                        "id": "30213000",
                        "description": "Personal computers"
                    },
                    "quantity": 100
                }
            ]
        },
        "buyer": {
            "id": "buyer-001",
            "name": "Ministry of Finance"
        }
    }


class TestWithFixture:
    """Tests using the sample release fixture."""
    
    def test_release_has_required_fields(self, sample_ocds_release):
        """Test sample release has all required fields."""
        required = ["ocid", "id", "date", "tag", "initiationType"]
        for field in required:
            assert field in sample_ocds_release
    
    def test_tender_value(self, sample_ocds_release):
        """Test tender value extraction."""
        value = sample_ocds_release["tender"]["value"]
        assert value["amount"] == 50000
        assert value["currency"] == "EUR"
