# API Reference

This document provides API documentation for the library modules in `scripts/lib/`.

These modules are the reusable core of the procurement causal inference pipeline. Only the four current modules are documented: `data_acquisition`, `mechanism_index`, and `causal_analysis` (plus `__init__.py`).

---

## Table of Contents

- [data_acquisition](#data_acquisition)
- [mechanism_index](#mechanism_index)
- [causal_analysis](#causal_analysis)

---

## data_acquisition

Module for downloading OCDS-formatted procurement data from government sources.

**Location:** `scripts/lib/data_acquisition.py`

### Classes

#### `OCDSDownloader`

Base class for OCDS data acquisition.

```python
class OCDSDownloader:
    """Abstract base class for OCDS downloaders."""
    
    def __init__(self, output_dir: str, cache_dir: str = None):
        """
        Initialize downloader.
        
        Parameters
        ----------
        output_dir : str
            Directory to save downloaded data
        cache_dir : str, optional
            Directory for caching API responses
        """
        
    def fetch_releases(self, start_date: str, end_date: str) -> Iterator[dict]:
        """
        Fetch OCDS releases in date range.
        
        Parameters
        ----------
        start_date : str
            Start date in YYYY-MM-DD format
        end_date : str
            End date in YYYY-MM-DD format
            
        Yields
        ------
        dict
            OCDS release package
        """
        
    def save_releases(self, releases: Iterator[dict], output_path: str) -> int:
        """
        Save releases to JSONL file.
        
        Parameters
        ----------
        releases : Iterator[dict]
            Iterator of OCDS releases
        output_path : str
            Path to output JSONL file
            
        Returns
        -------
        int
            Number of releases saved
        """
```

#### `ProZorroDownloader`

Ukrainian ProZorro API client.

```python
class ProZorroDownloader(OCDSDownloader):
    """Download data from Ukraine's ProZorro system."""
    
    BASE_URL = "https://api.prozorro.gov.ua/api/2.5"
    
    def __init__(self, output_dir: str, api_key: str = None):
        """
        Initialize ProZorro downloader.
        
        Parameters
        ----------
        output_dir : str
            Directory for output files
        api_key : str, optional
            ProZorro API key (optional, increases rate limits)
        """
        
    def fetch_by_cpv(self, cpv_codes: List[str], **kwargs) -> Iterator[dict]:
        """
        Fetch releases filtered by CPV codes.
        
        Parameters
        ----------
        cpv_codes : List[str]
            List of CPV codes to filter by
        **kwargs
            Additional filters passed to fetch_releases
        """
```

#### `SECOPDownloader`

Colombian SECOP II API client.

```python
class SECOPDownloader(OCDSDownloader):
    """Download data from Colombia's SECOP II system."""
    
    BASE_URL = "https://api.colombiacompra.gov.co/ocds"
    
    def fetch_by_buyer(self, buyer_ids: List[str], **kwargs) -> Iterator[dict]:
        """
        Fetch releases filtered by buyer (entity) IDs.
        
        Parameters
        ----------
        buyer_ids : List[str]
            List of buyer identifiers
        """
```

#### `ContractsFinderDownloader`

UK Contracts Finder API client.

```python
class ContractsFinderDownloader(OCDSDownloader):
    """Download data from UK's Contracts Finder."""
    
    BASE_URL = "https://www.contractsfinder.service.gov.uk/api/2"
    
    def fetch_above_threshold(self, threshold_gbp: float = 25000) -> Iterator[dict]:
        """
        Fetch releases above value threshold.
        
        Parameters
        ----------
        threshold_gbp : float
            Value threshold in GBP (default: 25000)
        """
```

### Functions

#### `download_exchange_rates`

```python
def download_exchange_rates(
    currencies: List[str],
    start_date: str,
    end_date: str,
    output_path: str
) -> pd.DataFrame:
    """
    Download daily exchange rates from ECB API.
    
    Parameters
    ----------
    currencies : List[str]
        Currency codes (e.g., ['UAH', 'COP', 'GBP'])
    start_date : str
        Start date YYYY-MM-DD
    end_date : str
        End date YYYY-MM-DD
    output_path : str
        Path to save CSV
        
    Returns
    -------
    pd.DataFrame
        DataFrame with columns: date, currency, rate_to_eur
    """
```

---

## mechanism_index

Module for computing text-based mechanism indices from tender documentation.

**Location:** `scripts/lib/mechanism_index.py`

### Classes

#### `MechanismAnalyzer`

```python
class MechanismAnalyzer:
    """Analyze tender documents for governance mechanisms."""
    
    MECHANISM_KEYWORDS = {
        'transparency': ['public', 'disclose', 'publish', ...],
        'competition': ['competitive', 'bidder', 'auction', ...],
        'accountability': ['audit', 'review', 'compliance', ...]
    }
    
    def __init__(self, language: str = 'en'):
        """
        Initialize analyzer.
        
        Parameters
        ----------
        language : str
            Language code for text processing ('en', 'uk', 'es')
        """
        
    def compute_mechanism_index(self, texts: List[str]) -> Dict[str, float]:
        """
        Compute mechanism index from tender texts.
        
        Parameters
        ----------
        texts : List[str]
            List of document texts (descriptions, specifications)
            
        Returns
        -------
        Dict[str, float]
            Dictionary with keys:
            - 'transparency': [0, 1]
            - 'competition': [0, 1]
            - 'accountability': [0, 1]
            - 'composite': [0, 1] weighted average
        """
```

### Functions

#### `add_mechanism_index`

```python
def add_mechanism_index(
    gprd_df: pd.DataFrame,
    text_column: str = 'tender_description'
) -> pd.DataFrame:
    """
    Add mechanism index columns to GPRD DataFrame.
    
    Parameters
    ----------
    gprd_df : pd.DataFrame
        GPRD DataFrame
    text_column : str
        Column containing tender description text
        
    Returns
    -------
    pd.DataFrame
        DataFrame with added mechanism_* columns
    """
```

#### `compute_complexity_score`

```python
def compute_complexity_score(text: str) -> float:
    """
    Compute document complexity using readability metrics.
    
    Parameters
    ----------
    text : str
        Document text
        
    Returns
    -------
    float
        Complexity score [0, 1] based on Flesch-Kincaid, etc.
    """
```

---

## causal_analysis

Module for regression discontinuity and difference-in-differences estimation.

**Location:** `scripts/lib/causal_analysis.py`

### Classes

#### `RDDEstimator`

```python
class RDDEstimator:
    """Regression discontinuity design estimation."""
    
    def __init__(
        self,
        bandwidth_method: str = 'IK',
        kernel: str = 'triangular',
        polynomial_order: int = 1
    ):
        """
        Initialize RDD estimator.
        
        Parameters
        ----------
        bandwidth_method : str
            Method for optimal bandwidth: 'IK' (Imbens-Kalyanaraman),
            'CCT' (Calonico-Cattaneo-Titiunik), 'CV' (cross-validation)
        kernel : str
            Kernel for local regression: 'triangular', 'uniform', 'epanechnikov'
        polynomial_order : int
            Order of polynomial for local regression
        """
        
    def fit(
        self,
        y: np.ndarray,
        running_var: np.ndarray,
        cutoff: float = 0.0,
        covariates: np.ndarray = None
    ) -> 'RDDResult':
        """
        Fit RDD model.
        
        Parameters
        ----------
        y : np.ndarray
            Outcome variable
        running_var : np.ndarray
            Running variable (normalized to cutoff = 0)
        cutoff : float
            Discontinuity cutoff (default 0 if normalized)
        covariates : np.ndarray, optional
            Additional covariates for covariate-adjusted RDD
            
        Returns
        -------
        RDDResult
            Results object with estimates and diagnostics
        """
        
    def compute_bandwidth(
        self,
        y: np.ndarray,
        running_var: np.ndarray
    ) -> float:
        """
        Compute optimal bandwidth.
        
        Returns
        -------
        float
            Optimal bandwidth (same units as running_var)
        """
```

#### `RDDResult`

```python
@dataclass
class RDDResult:
    """Container for RDD estimation results."""
    
    estimate: float          # Treatment effect at cutoff
    std_error: float         # Robust standard error
    ci_lower: float          # 95% CI lower bound
    ci_upper: float          # 95% CI upper bound
    bandwidth: float         # Bandwidth used
    n_effective: int         # Observations within bandwidth
    n_left: int              # Observations below cutoff
    n_right: int             # Observations above cutoff
    p_value: float           # Two-sided p-value
    kernel: str              # Kernel used
    polynomial_order: int    # Polynomial order
    
    def summary(self) -> str:
        """Return formatted summary string."""
        
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
```

#### `DiDEstimator`

```python
class DiDEstimator:
    """Difference-in-differences estimation."""
    
    def __init__(
        self,
        method: str = 'cs',
        anticipation: int = 0,
        parallel_trends_test: bool = True
    ):
        """
        Initialize DiD estimator.
        
        Parameters
        ----------
        method : str
            Estimation method:
            - 'twfe': Two-way fixed effects (classic)
            - 'cs': Callaway-Sant'Anna (heterogeneous treatment timing)
            - 'sun_abraham': Sun-Abraham interaction weights
        anticipation : int
            Number of pre-treatment periods for anticipation effects
        parallel_trends_test : bool
            Whether to compute pre-trends test
        """
        
    def fit(
        self,
        y: np.ndarray,
        treat: np.ndarray,
        time: np.ndarray,
        unit: np.ndarray,
        first_treat: np.ndarray = None,
        covariates: np.ndarray = None
    ) -> 'DiDResult':
        """
        Fit DiD model.
        
        Parameters
        ----------
        y : np.ndarray
            Outcome variable
        treat : np.ndarray
            Treatment indicator (0/1)
        time : np.ndarray
            Time period indicators
        unit : np.ndarray
            Unit identifiers
        first_treat : np.ndarray, optional
            First treatment period for each unit (for staggered)
        covariates : np.ndarray, optional
            Time-varying covariates
            
        Returns
        -------
        DiDResult
            Results object with ATT and event study coefficients
        """
```

### Functions

#### `run_rdd_analysis`

```python
def run_rdd_analysis(
    gprd_df: pd.DataFrame,
    outcome: str,
    running_var: str = 'value_running',
    config: dict = None
) -> Dict[str, RDDResult]:
    """
    Run complete RDD analysis pipeline.
    
    Parameters
    ----------
    gprd_df : pd.DataFrame
        GPRD DataFrame with mechanism columns
    outcome : str
        Outcome column name (e.g., 'n_bidders', 'mechanism_composite')
    running_var : str
        Running variable column
    config : dict, optional
        Configuration overrides
        
    Returns
    -------
    Dict[str, RDDResult]
        Dictionary mapping specification names to results
    """
```

#### `run_did_analysis`

```python
def run_did_analysis(
    gprd_df: pd.DataFrame,
    outcome: str,
    treatment_col: str = 'above_threshold',
    time_col: str = 'quarter',
    config: dict = None
) -> Dict[str, DiDResult]:
    """
    Run complete DiD analysis pipeline.
    
    Parameters
    ----------
    gprd_df : pd.DataFrame
        GPRD DataFrame
    outcome : str
        Outcome column name
    treatment_col : str
        Treatment indicator column
    time_col : str
        Time period column
    config : dict, optional
        Configuration overrides
        
    Returns
    -------
    Dict[str, DiDResult]
        Dictionary mapping specification names to results
    """
```

---

## Usage Examples

### Complete Pipeline

```python
from scripts.lib.data_acquisition import ProZorroDownloader
from scripts.lib.mechanism_index import add_mechanism_index
from scripts.lib.causal_analysis import run_rdd_analysis

# Download data
downloader = ProZorroDownloader("data/raw/ukraine")
releases = downloader.fetch_releases("2018-01-01", "2023-12-31")
downloader.save_releases(releases, "data/raw/ukraine/releases.jsonl")

# Harmonize
config = {"threshold_eur": 5555555, "currency": "UAH"}
gprd_df = harmonize_to_gprd(
    "data/raw/ukraine/releases.jsonl",
    country_code="UA",
    config=config,
    output_path="data/processed/ukraine/gprd.parquet"
)

# Add mechanism index
gprd_df = add_mechanism_index(gprd_df)

# Run RDD
results = run_rdd_analysis(gprd_df, outcome="n_bidders")
```

### Pooled Analysis

```python
from scripts.lib.causal_analysis import RDDEstimator

# Load pooled data
import pandas as pd
pooled = pd.read_parquet("Data/processed/gprd_with_carbon.parquet")

# RDD with country fixed effects
estimator = RDDEstimator(bandwidth_method='CCT')
result = estimator.fit(
    y=pooled["n_bidders"].values,
    running_var=pooled["value_running"].values,
    covariates=pd.get_dummies(pooled["country"]).values
)
```

---

## Type Definitions

```python
from typing import TypedDict, List, Optional

class GPRDRecord(TypedDict):
    """Type definition for GPRD record."""
    ocid: str
    release_id: str
    country: str
    tender_id: str
    tender_title: str
    tender_description: str
    tender_value_eur: float
    tender_value_local: float
    threshold_eur: float
    value_running: float  # Normalized: (value - threshold) / threshold
    above_threshold: bool
    n_bidders: int
    award_value_eur: Optional[float]
    buyer_id: str
    buyer_name: str
    supplier_id: Optional[str]
    supplier_name: Optional[str]
    procurement_method: str
    tender_date: str  # ISO format
    award_date: Optional[str]
    cpv_main: str
    cpv_division: str
    mechanism_transparency: Optional[float]
    mechanism_competition: Optional[float]
    mechanism_accountability: Optional[float]
    mechanism_composite: Optional[float]
```
