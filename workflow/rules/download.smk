# =============================================================================
# Download Rules
# =============================================================================
# Handles data acquisition from OCDS APIs

rule download_exchange_rates:
    """Download historical exchange rates for currency conversion."""
    output:
        RAW_DIR / "exchange_rates.csv"
    log:
        "logs/download_exchange_rates.log"
    shell:
        """
        python -m scripts.download_data exchange-rates \
            --output {output} \
            --start-year 2015 \
            --end-year 2024 \
            --source world_bank \
            2>&1 | tee {log}
        """

rule download_cpv_codes:
    """Download CPV code taxonomy for sector classification."""
    output:
        RAW_DIR / "cpv_taxonomy.json"
    log:
        "logs/download_cpv.log"
    shell:
        """
        python -m scripts.download_data cpv-codes \
            --output {output} \
            2>&1 | tee {log}
        """

rule download_gdp_data:
    """Download GDP data for country-level controls."""
    output:
        RAW_DIR / "gdp_data.csv"
    log:
        "logs/download_gdp.log"
    shell:
        """
        python -m scripts.download_data gdp \
            --output {output} \
            --countries UA,CO,GB \
            --start-year 2010 \
            --end-year 2024 \
            2>&1 | tee {log}
        """

rule validate_ocds:
    """Validate downloaded OCDS data against schema."""
    input:
        RAW_DIR / "{country}" / "releases.jsonl"
    output:
        RAW_DIR / "{country}" / "validation_report.json"
    log:
        "logs/validate_{country}.log"
    shell:
        """
        python -m scripts.download_data validate-ocds \
            --input {input} \
            --output {output} \
            --schema-version 1.1 \
            2>&1 | tee {log}
        """
