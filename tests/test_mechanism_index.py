"""
Test suite for mechanism_index module.

Tests NLP-based tender text analysis and mechanism scoring.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch

from scripts.lib.mechanism_index import (
    calculate_restrictiveness,
    calculate_complexity,
    calculate_innovation_score,
    compute_mechanism_index,
    MechanismAnalyzer
)


class TestRestrictivenessScore:
    """Tests for restrictiveness calculation."""
    
    def test_high_restrictiveness(self):
        """Test detection of restrictive language."""
        text = """
        The contractor must use only Brand X equipment.
        Proprietary software from Company Y is required.
        The exact model number ABC-123 must be supplied.
        Only pre-approved vendors may bid.
        """
        
        score = calculate_restrictiveness(text)
        
        # Should be high (>0.6) due to restrictive keywords
        assert score > 0.6
    
    def test_low_restrictiveness(self):
        """Test non-restrictive language gets low score."""
        text = """
        The contractor may supply equivalent equipment.
        Open source or commercial software is acceptable.
        Various brands and models will be considered.
        All qualified vendors are encouraged to participate.
        """
        
        score = calculate_restrictiveness(text)
        
        # Should be low (<0.4)
        assert score < 0.4
    
    def test_empty_text(self):
        """Test handling of empty text."""
        score = calculate_restrictiveness("")
        assert score == 0.0 or np.isnan(score)
    
    def test_score_bounds(self):
        """Test score is bounded between 0 and 1."""
        texts = [
            "Only proprietary must exact specific required exclusive",
            "Any equivalent alternative various multiple options",
            "Standard procurement tender"
        ]
        
        for text in texts:
            score = calculate_restrictiveness(text)
            assert 0 <= score <= 1


class TestComplexityScore:
    """Tests for text complexity calculation."""
    
    def test_complex_text(self):
        """Test detection of complex bureaucratic language."""
        text = """
        Notwithstanding the aforementioned provisions, the procurement 
        authority reserves the right to adjudicate submissions based on 
        multifaceted considerations including but not limited to technical 
        specifications, methodological approaches, and implementation 
        frameworks as delineated in supplementary documentation.
        """
        
        score = calculate_complexity(text)
        
        # Complex text should score high
        assert score > 0.6
    
    def test_simple_text(self):
        """Test simple text gets low complexity score."""
        text = """
        We need to buy 10 computers.
        They must work well.
        The price is important.
        Please send your best offer.
        """
        
        score = calculate_complexity(text)
        
        # Simple text should score low
        assert score < 0.4
    
    def test_flesch_kincaid_correlation(self):
        """Test complexity correlates with readability metrics."""
        simple = "Buy ten computers. They work well."
        complex_text = """
        Procure computational devices characterized by elevated 
        processing capabilities and multifunctional operational parameters.
        """
        
        simple_score = calculate_complexity(simple)
        complex_score = calculate_complexity(complex_text)
        
        assert complex_score > simple_score


class TestInnovationScore:
    """Tests for innovation orientation scoring."""
    
    def test_innovation_keywords(self):
        """Test detection of innovation-oriented language."""
        text = """
        We seek innovative solutions incorporating novel approaches.
        R&D partnerships and prototype development are encouraged.
        Cutting-edge technology and breakthrough methodologies preferred.
        """
        
        score = calculate_innovation_score(text)
        
        assert score > 0.6
    
    def test_standard_procurement(self):
        """Test standard procurement language gets low innovation score."""
        text = """
        Standard office supplies required.
        Conventional equipment meeting baseline specifications.
        Traditional delivery methods acceptable.
        """
        
        score = calculate_innovation_score(text)
        
        assert score < 0.3
    
    def test_r_and_d_detection(self):
        """Test R&D related terms are detected."""
        r_and_d_texts = [
            "Research and development project",
            "R&D collaboration opportunity",
            "Experimental prototype required"
        ]
        
        for text in r_and_d_texts:
            score = calculate_innovation_score(text)
            assert score > 0.3


class TestMechanismIndex:
    """Tests for composite mechanism index."""
    
    @pytest.fixture
    def sample_texts(self):
        """Sample tender texts for testing."""
        return pd.DataFrame({
            'tender_id': ['T001', 'T002', 'T003'],
            'description': [
                "Only Brand X proprietary systems required. Complex technical specifications apply.",
                "Standard office equipment. Simple requirements. Any brand acceptable.",
                "Innovative R&D project. Novel approaches encouraged. Prototype development."
            ],
            'value': [100000, 50000, 200000]
        })
    
    def test_mechanism_index_computation(self, sample_texts):
        """Test composite index computation."""
        results = compute_mechanism_index(
            sample_texts,
            text_col='description',
            weights={'restrictiveness': 0.4, 'complexity': 0.3, 'innovation': 0.3}
        )
        
        assert 'mechanism_index' in results.columns
        assert len(results) == len(sample_texts)
        assert all(results['mechanism_index'].between(0, 1))
    
    def test_component_scores_included(self, sample_texts):
        """Test individual component scores are returned."""
        results = compute_mechanism_index(
            sample_texts,
            text_col='description'
        )
        
        assert 'restrictiveness' in results.columns
        assert 'complexity' in results.columns
        assert 'innovation_score' in results.columns
    
    def test_pca_index(self, sample_texts):
        """Test PCA-based index construction."""
        results = compute_mechanism_index(
            sample_texts,
            text_col='description',
            method='pca',
            n_components=1
        )
        
        assert 'mechanism_index_pca' in results.columns


class TestMechanismAnalyzer:
    """Tests for MechanismAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return MechanismAnalyzer(
            features=['restrictiveness', 'complexity', 'innovation'],
            weighting='equal'
        )
    
    def test_fit_transform(self, analyzer):
        """Test fit_transform pipeline."""
        texts = pd.Series([
            "Only Brand X required exclusively",
            "Any standard equipment acceptable",
            "Innovative R&D prototype needed"
        ])
        
        results = analyzer.fit_transform(texts)
        
        assert len(results) == len(texts)
        assert results.shape[1] >= 3  # At least 3 feature columns
    
    def test_analyze_single(self, analyzer):
        """Test analysis of single document."""
        text = "Standard procurement for office supplies"
        
        result = analyzer.analyze_single(text)
        
        assert 'restrictiveness' in result
        assert 'complexity' in result
        assert 'innovation' in result
        assert 'mechanism_index' in result
    
    def test_batch_processing(self, analyzer):
        """Test efficient batch processing."""
        n = 1000
        texts = pd.Series(["Sample tender text number " + str(i) for i in range(n)])
        
        results = analyzer.fit_transform(texts)
        
        assert len(results) == n


class TestTextPreprocessing:
    """Tests for text preprocessing utilities."""
    
    def test_language_detection(self):
        """Test handling of different languages."""
        from scripts.lib.mechanism_index import preprocess_text
        
        english = "Standard procurement procedure"
        spanish = "Procedimiento de contratación estándar"
        ukrainian = "Стандартна процедура закупівлі"
        
        # All should be processable
        for text in [english, spanish, ukrainian]:
            processed = preprocess_text(text)
            assert len(processed) > 0
    
    def test_special_characters(self):
        """Test handling of special characters."""
        from scripts.lib.mechanism_index import preprocess_text
        
        text = "Price: €50,000 (VAT incl.) — delivery: 30 days"
        processed = preprocess_text(text)
        
        assert processed is not None
    
    def test_html_removal(self):
        """Test HTML tag removal."""
        from scripts.lib.mechanism_index import preprocess_text
        
        text = "<p>Standard <b>procurement</b> procedure</p>"
        processed = preprocess_text(text)
        
        assert '<' not in processed
        assert '>' not in processed


class TestKeywordDetection:
    """Tests for keyword-based detection."""
    
    def test_restrictive_keyword_list(self):
        """Test restrictive keyword detection."""
        from scripts.lib.mechanism_index import RESTRICTIVE_KEYWORDS
        
        expected = ['only', 'must', 'required', 'exclusive', 'proprietary', 'specific']
        
        for keyword in expected:
            assert keyword in RESTRICTIVE_KEYWORDS or keyword.lower() in [k.lower() for k in RESTRICTIVE_KEYWORDS]
    
    def test_innovation_keyword_list(self):
        """Test innovation keyword detection."""
        from scripts.lib.mechanism_index import INNOVATION_KEYWORDS
        
        expected = ['innovative', 'novel', 'r&d', 'prototype', 'cutting-edge']
        
        for keyword in expected:
            assert keyword in INNOVATION_KEYWORDS or keyword.lower() in [k.lower() for k in INNOVATION_KEYWORDS]
    
    def test_custom_keywords(self):
        """Test using custom keyword lists."""
        analyzer = MechanismAnalyzer(
            custom_keywords={
                'restrictive': ['bespoke', 'tailored', 'custom-made'],
                'innovation': ['ai', 'machine learning', 'blockchain']
            }
        )
        
        text = "AI-powered bespoke solution with blockchain integration"
        result = analyzer.analyze_single(text)
        
        assert result['restrictiveness'] > 0
        assert result['innovation'] > 0


@pytest.fixture
def procurement_corpus():
    """Large corpus of procurement texts for testing."""
    np.random.seed(42)
    
    templates = [
        "Supply of {} for {} department",
        "Procurement of {} equipment",
        "Construction of {} facility",
        "Consultancy services for {} project",
        "Maintenance of {} systems"
    ]
    
    items = ['IT', 'medical', 'office', 'transport', 'security']
    depts = ['health', 'education', 'defense', 'finance', 'environment']
    
    texts = []
    for _ in range(500):
        template = np.random.choice(templates)
        item = np.random.choice(items)
        dept = np.random.choice(depts)
        texts.append(template.format(item, dept))
    
    return pd.Series(texts)


class TestScalability:
    """Tests for scalability with large datasets."""
    
    def test_large_corpus(self, procurement_corpus):
        """Test processing of large corpus."""
        analyzer = MechanismAnalyzer()
        
        import time
        start = time.time()
        results = analyzer.fit_transform(procurement_corpus)
        elapsed = time.time() - start
        
        assert len(results) == len(procurement_corpus)
        assert elapsed < 60  # Should complete in under a minute
    
    def test_memory_efficiency(self, procurement_corpus):
        """Test memory usage is reasonable."""
        import sys
        
        analyzer = MechanismAnalyzer()
        results = analyzer.fit_transform(procurement_corpus)
        
        # Results should not be excessively large
        size_mb = sys.getsizeof(results) / (1024 * 1024)
        assert size_mb < 100  # Less than 100MB
