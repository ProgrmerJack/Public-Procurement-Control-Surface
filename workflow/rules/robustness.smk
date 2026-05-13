# =============================================================================
# Robustness Rules
# =============================================================================
# Comprehensive robustness and sensitivity checks

rule permutation_test:
    """Permutation-based inference for RDD."""
    input:
        PROC_DIR / "gprd_pooled.parquet"
    output:
        RESULTS_DIR / "permutation_inference.csv"
    log:
        "logs/permutation_test.log"
    threads: 8
    resources:
        mem_mb=16000
    shell:
        """
        python -m src.robustness_checks permutation-test \
            --input {input} \
            --output {output} \
            --n-permutations {config[robustness][n_bootstrap]} \
            --seed 42 \
            2>&1 | tee {log}
        """

rule manipulation_test:
    """McCrary density test for manipulation at threshold."""
    input:
        PROC_DIR / "{country}" / "gprd_mechanism.parquet"
    output:
        RESULTS_DIR / "mccrary_{country}.csv"
    log:
        "logs/mccrary_{country}.log"
    threads: 2
    resources:
        mem_mb=4000
    shell:
        """
        python -m src.robustness_checks mccrary \
            --input {input} \
            --output {output} \
            --running-var distance_to_threshold \
            --cutoff 0 \
            2>&1 | tee {log}
        """

rule covariate_balance:
    """Test covariate balance around threshold."""
    input:
        PROC_DIR / "gprd_pooled.parquet"
    output:
        RESULTS_DIR / "covariate_balance.csv"
    log:
        "logs/covariate_balance.log"
    threads: 4
    resources:
        mem_mb=8000
    shell:
        """
        python -m src.robustness_checks covariate-balance \
            --input {input} \
            --output {output} \
            --covariates year,sector,buyer_region,contract_type \
            --bandwidth-method {config[rdd][bandwidth_method]} \
            2>&1 | tee {log}
        """

rule loo_country:
    """Leave-one-country-out sensitivity analysis."""
    input:
        PROC_DIR / "gprd_pooled.parquet"
    output:
        RESULTS_DIR / "loo_country.csv"
    log:
        "logs/loo_country.log"
    threads: 8
    resources:
        mem_mb=16000
    shell:
        """
        python -m src.robustness_checks leave-one-out \
            --input {input} \
            --output {output} \
            --variable country \
            2>&1 | tee {log}
        """

rule loo_year:
    """Leave-one-year-out sensitivity analysis."""
    input:
        PROC_DIR / "gprd_pooled.parquet"
    output:
        RESULTS_DIR / "loo_year.csv"
    log:
        "logs/loo_year.log"
    threads: 8
    resources:
        mem_mb=16000
    shell:
        """
        python -m src.robustness_checks leave-one-out \
            --input {input} \
            --output {output} \
            --variable year \
            2>&1 | tee {log}
        """

rule multiple_hypotheses:
    """Multiple hypothesis testing correction."""
    input:
        expand(RESULTS_DIR / "rdd_{country}_{threshold}.csv", 
               country=COUNTRIES, threshold=THRESHOLDS),
        RESULTS_DIR / "rdd_pooled.csv"
    output:
        RESULTS_DIR / "mht_corrected.csv"
    log:
        "logs/mht_correction.log"
    shell:
        """
        python -m src.robustness_checks mht-correction \
            --inputs {input} \
            --output {output} \
            --method {config[robustness][correction_method]} \
            2>&1 | tee {log}
        """

rule specification_curve:
    """Specification curve analysis across many specifications."""
    input:
        PROC_DIR / "gprd_pooled.parquet"
    output:
        RESULTS_DIR / "specification_curve.csv",
        FIG_DIR / "specification_curve.pdf"
    log:
        "logs/specification_curve.log"
    threads: 8
    resources:
        mem_mb=32000
    shell:
        """
        python -m src.robustness_checks specification-curve \
            --input {input} \
            --output {output[0]} \
            --figure {output[1]} \
            --n-specifications 500 \
            2>&1 | tee {log}
        """
