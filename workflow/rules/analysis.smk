# =============================================================================
# Analysis Rules
# =============================================================================
# Handles causal inference analysis (RDD, DiD, IV)

rule rdd_heterogeneity:
    """RDD analysis with heterogeneity by sector and buyer size."""
    input:
        PROC_DIR / "{country}" / "gprd_mechanism.parquet"
    output:
        RESULTS_DIR / "rdd_hetero_{country}.csv"
    log:
        "logs/rdd_hetero_{country}.log"
    threads: 4
    resources:
        mem_mb=8000
    shell:
        """
        python -m src.causal_analysis rdd-heterogeneity \
            --input {input} \
            --output {output} \
            --subgroups sector,buyer_size,year \
            --bandwidth-method {config[rdd][bandwidth_method]} \
            2>&1 | tee {log}
        """

rule iv_analysis:
    """Instrumental variable analysis using distance to threshold."""
    input:
        PROC_DIR / "{country}" / "gprd_mechanism.parquet"
    output:
        RESULTS_DIR / "iv_{country}.csv"
    log:
        "logs/iv_{country}.log"
    threads: 4
    resources:
        mem_mb=8000
    shell:
        """
        python -m src.causal_analysis iv \
            --input {input} \
            --output {output} \
            --instrument distance_to_threshold \
            --endogenous mechanism_index \
            --outcome competition_count,price_ratio \
            2>&1 | tee {log}
        """

rule quantile_rdd:
    """Quantile RDD for distributional effects."""
    input:
        PROC_DIR / "gprd_pooled.parquet"
    output:
        RESULTS_DIR / "quantile_rdd.csv"
    log:
        "logs/quantile_rdd.log"
    threads: 8
    resources:
        mem_mb=16000
    shell:
        """
        python -m src.causal_analysis quantile-rdd \
            --input {input} \
            --output {output} \
            --quantiles 0.1,0.25,0.5,0.75,0.9 \
            --bandwidth-method {config[rdd][bandwidth_method]} \
            2>&1 | tee {log}
        """

rule bounds_analysis:
    """Lee bounds for sample selection."""
    input:
        PROC_DIR / "gprd_pooled.parquet"
    output:
        RESULTS_DIR / "lee_bounds.csv"
    log:
        "logs/lee_bounds.log"
    threads: 4
    resources:
        mem_mb=8000
    shell:
        """
        python -m src.causal_analysis lee-bounds \
            --input {input} \
            --output {output} \
            --selection-var has_award \
            --outcome price_ratio \
            2>&1 | tee {log}
        """
