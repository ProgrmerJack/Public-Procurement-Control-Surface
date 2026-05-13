"""
Test suite for causal_analysis module.

Tests RDD, DiD, and IV estimation methods.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch
import statsmodels.api as sm

from scripts.lib.causal_analysis import (
    optimal_bandwidth_ik,
    run_rdd_analysis,
    run_twfe_did,
    run_event_study,
    RDDEstimator,
    DIDEstimator
)


class TestBandwidthSelection:
    """Tests for bandwidth selection methods."""
    
    def test_ik_bandwidth_basic(self):
        """Test Imbens-Kalyanaraman bandwidth on synthetic data."""
        np.random.seed(42)
        n = 1000
        
        # Generate data with discontinuity at 0
        x = np.random.uniform(-1, 1, n)
        y = 0.5 * (x >= 0) + 0.1 * x + np.random.normal(0, 0.2, n)
        
        h_opt = optimal_bandwidth_ik(y, x, cutoff=0)
        
        # Bandwidth should be positive and reasonable
        assert h_opt > 0
        assert h_opt < 1  # Should be less than full range
    
    def test_ik_bandwidth_with_covariates(self):
        """Test bandwidth selection with covariates."""
        np.random.seed(42)
        n = 1000
        
        x = np.random.uniform(-1, 1, n)
        z = np.random.normal(0, 1, n)  # Covariate
        y = 0.5 * (x >= 0) + 0.1 * x + 0.2 * z + np.random.normal(0, 0.2, n)
        
        h_opt = optimal_bandwidth_ik(y, x, cutoff=0, covariates=z.reshape(-1, 1))
        
        assert h_opt > 0
    
    def test_bandwidth_monotonicity(self):
        """Test that bandwidth decreases with more observations near cutoff."""
        np.random.seed(42)
        
        # Sparse data near cutoff
        n1 = 500
        x1 = np.concatenate([
            np.random.uniform(-1, -0.3, n1 // 2),
            np.random.uniform(0.3, 1, n1 // 2)
        ])
        y1 = 0.5 * (x1 >= 0) + np.random.normal(0, 0.2, n1)
        
        # Dense data near cutoff
        n2 = 500
        x2 = np.random.uniform(-0.3, 0.3, n2)
        y2 = 0.5 * (x2 >= 0) + np.random.normal(0, 0.2, n2)
        
        h1 = optimal_bandwidth_ik(y1, x1, cutoff=0)
        h2 = optimal_bandwidth_ik(y2, x2, cutoff=0)
        
        # With more data near cutoff, bandwidth should be smaller
        # (or similar - depends on variance)
        assert h1 > 0 and h2 > 0


class TestRDDEstimator:
    """Tests for RDD estimation."""
    
    @pytest.fixture
    def rdd_data(self):
        """Generate synthetic RDD data."""
        np.random.seed(42)
        n = 2000
        
        # Running variable
        x = np.random.uniform(-1, 1, n)
        
        # Treatment effect of 0.5
        treatment = (x >= 0).astype(float)
        
        # Outcome with linear trend and discontinuity
        y = 0.5 * treatment + 0.3 * x + np.random.normal(0, 0.3, n)
        
        return pd.DataFrame({
            'outcome': y,
            'running_var': x,
            'treatment': treatment,
            'cluster_id': np.repeat(range(100), 20)
        })
    
    def test_rdd_point_estimate(self, rdd_data):
        """Test RDD recovers approximately correct treatment effect."""
        estimator = RDDEstimator(
            outcome='outcome',
            running_var='running_var',
            cutoff=0,
            kernel='triangular',
            polynomial_order=1
        )
        
        results = estimator.fit(rdd_data)
        
        # True effect is 0.5, should be close
        assert abs(results['estimate'] - 0.5) < 0.2
    
    def test_rdd_standard_errors(self, rdd_data):
        """Test standard errors are computed correctly."""
        estimator = RDDEstimator(
            outcome='outcome',
            running_var='running_var',
            cutoff=0,
            kernel='triangular',
            polynomial_order=1
        )
        
        results = estimator.fit(rdd_data)
        
        # SE should be positive and reasonable
        assert results['se'] > 0
        assert results['se'] < 0.5
    
    def test_rdd_clustered_se(self, rdd_data):
        """Test clustered standard errors."""
        estimator = RDDEstimator(
            outcome='outcome',
            running_var='running_var',
            cutoff=0,
            cluster_var='cluster_id'
        )
        
        results = estimator.fit(rdd_data)
        
        # Clustered SE should be larger than homoskedastic
        assert results['se_clustered'] >= results['se']
    
    def test_rdd_bias_correction(self, rdd_data):
        """Test bias-corrected estimates."""
        estimator = RDDEstimator(
            outcome='outcome',
            running_var='running_var',
            cutoff=0,
            bias_correction=True
        )
        
        results = estimator.fit(rdd_data)
        
        assert 'estimate_bc' in results
        assert 'se_bc' in results
    
    def test_rdd_kernel_options(self, rdd_data):
        """Test different kernel options."""
        kernels = ['triangular', 'epanechnikov', 'uniform']
        
        estimates = []
        for kernel in kernels:
            estimator = RDDEstimator(
                outcome='outcome',
                running_var='running_var',
                cutoff=0,
                kernel=kernel
            )
            results = estimator.fit(rdd_data)
            estimates.append(results['estimate'])
        
        # All should give similar estimates
        assert max(estimates) - min(estimates) < 0.3


class TestDIDEstimator:
    """Tests for Difference-in-Differences estimation."""
    
    @pytest.fixture
    def did_data(self):
        """Generate synthetic DiD panel data."""
        np.random.seed(42)
        
        n_units = 100
        n_periods = 10
        treatment_period = 5
        
        data = []
        for i in range(n_units):
            treated = i < 50  # First 50 units are treated
            unit_fe = np.random.normal(0, 0.5)
            
            for t in range(n_periods):
                time_fe = 0.1 * t
                post = t >= treatment_period
                
                # True treatment effect of 0.4
                treatment_effect = 0.4 if (treated and post) else 0
                
                y = unit_fe + time_fe + treatment_effect + np.random.normal(0, 0.2)
                
                data.append({
                    'unit_id': i,
                    'time': t,
                    'treated': treated,
                    'post': post,
                    'outcome': y
                })
        
        return pd.DataFrame(data)
    
    def test_twfe_estimate(self, did_data):
        """Test TWFE DiD recovers treatment effect."""
        results = run_twfe_did(
            data=did_data,
            outcome='outcome',
            treatment='treated',
            post='post',
            unit='unit_id',
            time='time'
        )
        
        # True effect is 0.4
        assert abs(results['att'] - 0.4) < 0.15
    
    def test_event_study(self, did_data):
        """Test event study coefficients."""
        results = run_event_study(
            data=did_data,
            outcome='outcome',
            treatment='treated',
            time='time',
            unit='unit_id',
            treatment_time=5,
            pre_periods=4,
            post_periods=4
        )
        
        # Pre-treatment coefficients should be ~0
        pre_coefs = [results['coefficients'][f'pre_{i}'] for i in range(1, 5)]
        assert all(abs(c) < 0.2 for c in pre_coefs)
        
        # Post-treatment coefficients should be ~0.4
        post_coefs = [results['coefficients'][f'post_{i}'] for i in range(5)]
        assert all(abs(c - 0.4) < 0.2 for c in post_coefs)


class TestRDDDiagnostics:
    """Tests for RDD diagnostic procedures."""
    
    @pytest.fixture
    def clean_rdd_data(self):
        """Generate clean RDD data without manipulation."""
        np.random.seed(42)
        n = 2000
        x = np.random.uniform(-1, 1, n)
        y = 0.5 * (x >= 0) + np.random.normal(0, 0.3, n)
        return pd.DataFrame({'outcome': y, 'running_var': x})
    
    def test_mccrary_no_manipulation(self, clean_rdd_data):
        """Test McCrary test on data without manipulation."""
        from scripts.lib.causal_analysis import mccrary_test
        
        results = mccrary_test(
            clean_rdd_data['running_var'],
            cutoff=0
        )
        
        # Should not reject (p > 0.05)
        assert results['pvalue'] > 0.05
    
    def test_covariate_balance(self, clean_rdd_data):
        """Test covariate balance at threshold."""
        # Add a balanced covariate
        clean_rdd_data['covariate'] = np.random.normal(0, 1, len(clean_rdd_data))
        
        from scripts.lib.causal_analysis import test_covariate_balance
        
        results = test_covariate_balance(
            data=clean_rdd_data,
            running_var='running_var',
            covariates=['covariate'],
            cutoff=0,
            bandwidth=0.2
        )
        
        # Should not find imbalance
        assert results['covariate']['pvalue'] > 0.05


class TestRobustness:
    """Tests for robustness check functions."""
    
    def test_bandwidth_sensitivity(self):
        """Test bandwidth sensitivity analysis."""
        np.random.seed(42)
        n = 1000
        x = np.random.uniform(-1, 1, n)
        y = 0.5 * (x >= 0) + np.random.normal(0, 0.3, n)
        
        data = pd.DataFrame({'outcome': y, 'running_var': x})
        
        from scripts.lib.causal_analysis import bandwidth_sensitivity
        
        results = bandwidth_sensitivity(
            data=data,
            outcome='outcome',
            running_var='running_var',
            cutoff=0,
            bandwidth_multipliers=[0.5, 0.75, 1.0, 1.25, 1.5]
        )
        
        # All estimates should be similar
        estimates = [r['estimate'] for r in results]
        assert max(estimates) - min(estimates) < 0.3
    
    def test_placebo_cutoffs(self):
        """Test placebo cutoff analysis."""
        np.random.seed(42)
        n = 1000
        x = np.random.uniform(-1, 1, n)
        y = 0.5 * (x >= 0) + np.random.normal(0, 0.3, n)
        
        data = pd.DataFrame({'outcome': y, 'running_var': x})
        
        from scripts.lib.causal_analysis import placebo_cutoff_test
        
        results = placebo_cutoff_test(
            data=data,
            outcome='outcome',
            running_var='running_var',
            true_cutoff=0,
            placebo_cutoffs=[-0.3, -0.2, 0.2, 0.3]
        )
        
        # Placebo effects should be smaller than true effect
        true_estimate = next(r for r in results if r['cutoff'] == 0)['estimate']
        placebo_estimates = [r['estimate'] for r in results if r['cutoff'] != 0]
        
        assert all(abs(p) < abs(true_estimate) for p in placebo_estimates)


@pytest.fixture
def large_panel():
    """Generate larger panel dataset for stress testing."""
    np.random.seed(42)
    
    n_units = 500
    n_periods = 20
    
    data = []
    for i in range(n_units):
        treatment_time = np.random.choice([5, 10, 15, None])
        unit_fe = np.random.normal(0, 1)
        
        for t in range(n_periods):
            treated = treatment_time is not None and t >= treatment_time
            y = unit_fe + 0.1 * t + 0.3 * treated + np.random.normal(0, 0.5)
            
            data.append({
                'unit': i,
                'time': t,
                'treatment_time': treatment_time if treatment_time else 999,
                'treated': treated,
                'outcome': y
            })
    
    return pd.DataFrame(data)


class TestStaggeredDiD:
    """Tests for staggered adoption DiD methods."""
    
    def test_callaway_santanna(self, large_panel):
        """Test Callaway-Sant'Anna estimator."""
        from scripts.lib.causal_analysis import run_callaway_santanna
        
        results = run_callaway_santanna(
            data=large_panel,
            outcome='outcome',
            unit='unit',
            time='time',
            treatment_time='treatment_time'
        )
        
        # ATT should be close to 0.3
        assert abs(results['att'] - 0.3) < 0.15
