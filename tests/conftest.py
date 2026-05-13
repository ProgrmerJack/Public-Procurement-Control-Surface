"""
conftest.py - Shared pytest fixtures and configuration.
"""

import pytest
import numpy as np
import pandas as pd
import tempfile
from pathlib import Path
import json


@pytest.fixture(scope="session")
def test_data_dir():
    """Create temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="session")
def sample_ocds_releases():
    """Generate sample OCDS releases for testing."""
    np.random.seed(42)
    
    releases = []
    for i in range(100):
        value = np.random.lognormal(10, 2)
        
        release = {
            "ocid": f"ocds-test-{i:05d}",
            "id": f"release-{i}",
            "date": f"2020-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}T00:00:00Z",
            "tag": ["tender"] if i % 3 != 0 else ["award"],
            "initiationType": "tender",
            "tender": {
                "id": f"tender-{i}",
                "title": f"Test Procurement {i}",
                "description": f"Description for procurement {i}",
                "status": "complete" if i % 4 == 0 else "active",
                "value": {
                    "amount": value,
                    "currency": "EUR"
                },
                "procurementMethod": "open" if value > 150000 else "limited"
            },
            "buyer": {
                "id": f"buyer-{i % 20}",
                "name": f"Ministry {i % 20}"
            }
        }
        releases.append(release)
    
    return releases


@pytest.fixture
def gprd_dataframe():
    """Generate sample GPRD (Global Procurement Research Database) DataFrame."""
    np.random.seed(42)
    n = 500
    
    # Generate data around thresholds
    distance = np.random.uniform(-0.5, 0.5, n)
    above_threshold = distance >= 0
    
    return pd.DataFrame({
        'tender_id': [f'T{i:05d}' for i in range(n)],
        'country': np.random.choice(['UA', 'CO', 'GB'], n),
        'value_eur': 150000 * (1 + distance),
        'distance_to_threshold': distance,
        'above_threshold': above_threshold,
        'n_bidders': np.random.poisson(3, n) + 1 + above_threshold.astype(int),
        'price_ratio': 1 - 0.05 * above_threshold + np.random.normal(0, 0.1, n),
        'buyer_id': np.random.randint(0, 50, n),
        'sector': np.random.choice(['goods', 'works', 'services'], n),
        'year': np.random.choice([2018, 2019, 2020, 2021, 2022], n),
        'mechanism_index': np.random.beta(2, 5, n),
        'restrictiveness': np.random.beta(2, 5, n),
        'complexity': np.random.beta(3, 3, n),
        'innovation_score': np.random.beta(1, 5, n)
    })


@pytest.fixture
def panel_data():
    """Generate panel data for DiD analysis."""
    np.random.seed(42)
    
    n_units = 100
    n_periods = 12
    treatment_start = 6
    
    data = []
    for unit in range(n_units):
        treated = unit < 50
        unit_fe = np.random.normal(0, 0.5)
        
        for period in range(n_periods):
            time_fe = 0.05 * period
            post = period >= treatment_start
            treat_effect = 0.3 if (treated and post) else 0
            
            outcome = unit_fe + time_fe + treat_effect + np.random.normal(0, 0.2)
            
            data.append({
                'unit_id': unit,
                'period': period,
                'treated': treated,
                'post': post,
                'outcome': outcome
            })
    
    return pd.DataFrame(data)


@pytest.fixture
def tender_texts():
    """Sample tender description texts."""
    return [
        {
            "id": "T001",
            "text": "Only Brand X equipment is required. Must meet exact specification ABC-123.",
            "expected_restrictiveness": "high"
        },
        {
            "id": "T002", 
            "text": "Standard office supplies. Any brand acceptable. Basic requirements.",
            "expected_restrictiveness": "low"
        },
        {
            "id": "T003",
            "text": "Innovative R&D project seeking novel solutions. Prototype development encouraged.",
            "expected_innovation": "high"
        },
        {
            "id": "T004",
            "text": "Notwithstanding the aforementioned provisions, the contracting authority shall adjudicate submissions based on multifaceted considerations.",
            "expected_complexity": "high"
        }
    ]


@pytest.fixture
def mock_api_responses():
    """Mock API responses for testing downloaders."""
    return {
        "ukraine": {
            "data": [
                {"id": "UA-2020-01", "title": "Test Ukraine"},
                {"id": "UA-2020-02", "title": "Test Ukraine 2"}
            ],
            "next_page": {"offset": "abc123"}
        },
        "colombia": [
            {"uid_secopii": "CO-2020-01", "nombre_procedimiento": "Test Colombia"},
            {"uid_secopii": "CO-2020-02", "nombre_procedimiento": "Test Colombia 2"}
        ],
        "uk": {
            "releases": [
                {"ocid": "ocds-b5fd17-UK-001", "tag": ["tender"]},
                {"ocid": "ocds-b5fd17-UK-002", "tag": ["award"]}
            ]
        }
    }


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "api: marks tests that require API access"
    )


@pytest.fixture(autouse=True)
def set_random_seed():
    """Set random seed for reproducibility."""
    np.random.seed(42)
