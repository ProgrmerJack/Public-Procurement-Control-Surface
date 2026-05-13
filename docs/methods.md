# Methodology Documentation

## Overview

This document describes the statistical methodology for estimating causal effects of procurement competition on supply chain carbon intensity.

**Paper:** Ashuraliyev, A. (2026). Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement. *Nature Sustainability*.

## Research Design

### Primary Analysis: Competition-Carbon Correlation

We compare carbon intensity between single-bidder and competitive contracts:

$$\Delta = \bar{C}_{single} - \bar{C}_{multi}$$

Where:
- $\bar{C}_{single}$ = mean carbon intensity for single-bidder contracts
- $\bar{C}_{multi}$ = mean carbon intensity for competitive contracts

Statistical significance is assessed via t-test with effect size (Cohen's d).

### Regression Discontinuity Design (RDD)

We exploit EU procurement thresholds that mandate transparency and competitive procedures as a source of quasi-experimental variation.

#### Setup

- **Running Variable**: Contract value (normalized distance to €139K threshold)
- **Cutoff**: EU procurement threshold (log value ≈ 5.143)
- **Treatment**: Above-threshold transparent procedures
- **Outcome**: Number of bidders (competition), carbon intensity

#### Identification Assumptions

1. **Continuity**: Potential outcomes are continuous at the threshold
2. **No Manipulation**: Buyers cannot precisely sort around the threshold
3. **Local Randomization**: Units near the threshold are comparable

#### Estimation

We estimate the local average treatment effect (LATE):

$$\tau_{RD} = \lim_{x \downarrow c} E[Y|X=x] - \lim_{x \uparrow c} E[Y|X=x]$$

Using local polynomial regression with triangular kernel:

```python
def estimate_rdd(y, x, cutoff, bandwidth, kernel='triangular'):
    # Select observations within bandwidth
    mask = np.abs(x - cutoff) <= bandwidth
    
    # Create treatment indicator
    D = (x >= cutoff).astype(float)
    
    # Kernel weights
    if kernel == 'triangular':
        weights = (1 - np.abs(x - cutoff) / bandwidth) * mask
    
    # Local linear regression
    X = np.column_stack([np.ones(len(x)), x - cutoff, D, D * (x - cutoff)])
    model = WLS(y, X, weights=weights)
    
    return model.fit().params[2]  # Treatment coefficient
```

#### Bandwidth Selection

We use the Imbens-Kalyanaraman (2012) optimal bandwidth:

$$h_{IK} = C_K \cdot \left( \frac{\sigma^2(c)}{\hat{f}(c) \cdot (\hat{m}''_+(c)^2 + \hat{m}''_-(c)^2)} \right)^{1/5} \cdot n^{-1/5}$$

With bias correction following Calonico, Cattaneo, and Titiunik (2014).

### COVID-19 Natural Experiment

The COVID-19 pandemic provides a natural experiment testing the causal mechanism:

- **Pre-COVID (2019)**: Baseline carbon premium ~7%
- **During COVID (2020-2021)**: Emergency procurement → premium tripled to 20%
- **Post-COVID (2022-2023)**: Recovery → premium collapsed to 0.3%

This temporal pattern is inconsistent with reverse causality (high-carbon sectors causing low competition).

### Carbon Intensity Measurement

Carbon intensity is derived from EXIOBASE 3.8.2 multi-regional input-output tables:

$$C_i = \sum_s w_{is} \cdot E_s$$

Where:
- $C_i$ = carbon intensity of contract $i$ (kg CO₂e per €)
- $w_{is}$ = weight of sector $s$ in contract $i$'s supply chain
- $E_s$ = sector $s$ emission factor from EXIOBASE

The mapping uses CPV (Common Procurement Vocabulary) codes to EXIOBASE sectors.

### Mechanism Index

We construct a composite mechanism index from tender text analysis:

$$M_i = w_R \cdot R_i + w_C \cdot C_i + w_I \cdot I_i$$

Where:
- $R_i$ = Restrictiveness score (0-1)
- $C_i$ = Complexity score (0-1)  
- $I_i$ = Innovation orientation score (0-1)
- $w$ = Component weights (equal by default)

#### Restrictiveness Score

$$R_i = \frac{\sum_{k \in \mathcal{K}_R} \mathbf{1}[k \in \text{text}_i]}{|\mathcal{K}_R|}$$

Where $\mathcal{K}_R$ = {"only", "must", "required", "exclusive", "proprietary", ...}

#### Complexity Score

Based on text readability metrics:

$$C_i = 1 - \frac{FRE_i - FRE_{min}}{FRE_{max} - FRE_{min}}$$

Where $FRE$ = Flesch Reading Ease score (0-100, higher = easier)

## Robustness Checks

### Manipulation Testing

McCrary (2008) density test for bunching at threshold:

```python
def mccrary_test(x, cutoff, bandwidth=None):
    """Test for manipulation at cutoff."""
    # Estimate density on each side
    f_left = estimate_density(x[x < cutoff], cutoff)
    f_right = estimate_density(x[x >= cutoff], cutoff)
    
    # Log difference test
    theta = np.log(f_right) - np.log(f_left)
    se = np.sqrt(f_left**(-2) * var_f_left + f_right**(-2) * var_f_right)
    
    return theta / se  # z-statistic
```

### Bandwidth Sensitivity

We report estimates for bandwidth multipliers: [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

### Placebo Cutoffs

Test for effects at false thresholds where no policy change occurs.

### Covariate Balance

Verify pre-determined covariates are smooth at the threshold.

### Donut Hole

Exclude observations within δ% of cutoff to address potential manipulation.

## Standard Errors

All standard errors are clustered at the buyer level to account for:
1. Within-buyer serial correlation
2. Multiple contracts per buyer
3. Buyer-specific unobservables

$$\hat{V}_{cluster} = (X'X)^{-1} \left( \sum_g X_g' \hat{u}_g \hat{u}_g' X_g \right) (X'X)^{-1}$$

## Multiple Hypothesis Testing

We adjust for multiple comparisons using:
- Benjamini-Hochberg (1995) FDR control
- Romano-Wolf (2005) step-down procedure
- Bonferroni correction (conservative)

## Software Implementation

- Bandwidth selection: `rdrobust` (Calonico et al., 2017)
- Staggered DiD: `did` package methodology (Callaway & Sant'Anna, 2021)
- Text analysis: `textstat`, custom NLP pipeline
- Bootstrap: Clustered wild bootstrap (Cameron et al., 2008)

## References

- Calonico, S., Cattaneo, M. D., & Titiunik, R. (2014). Robust nonparametric confidence intervals for regression-discontinuity designs. *Econometrica*, 82(6), 2295-2326.
- Callaway, B., & Sant'Anna, P. H. (2021). Difference-in-differences with multiple time periods. *Journal of Econometrics*, 225(2), 200-230.
- Imbens, G., & Kalyanaraman, K. (2012). Optimal bandwidth choice for the regression discontinuity estimator. *Review of Economic Studies*, 79(3), 933-959.
- McCrary, J. (2008). Manipulation of the running variable in the regression discontinuity design: A density test. *Journal of Econometrics*, 142(2), 698-714.
