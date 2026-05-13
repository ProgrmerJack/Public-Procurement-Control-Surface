"""
Deep analysis to address 5 Fatal Flaws - loads actual parquet data
"""
import pandas as pd
import numpy as np
import json
import os

os.chdir(r'C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface')

print("Loading parquet file...")
df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet')
print(f"Loaded: {len(df):,} rows, {df.columns.tolist()}")
print(f"Columns: {list(df.columns)}")
print(f"Memory: {df.memory_usage(deep=True).sum() / 1e9:.2f} GB")
print()

# Check what columns exist
print("Sample data (5 rows):")
print(df.head())
print()
print("Data types:")
print(df.dtypes)
print()

# Key columns we need
print("Unique countries:", df['country'].nunique() if 'country' in df.columns else 'N/A')
if 'country' in df.columns:
    print("Countries:", sorted(df['country'].unique()))
print()

# Check for single-bidder and carbon intensity columns
for col in ['single_bidder', 'is_single_bidder', 'nb_tenders_received', 'n_bidders',
            'carbon_intensity', 'carbon_intensity_kg_usd', 'ci_kg_usd',
            'cpv_division', 'cpv_2', 'sector', 'year', 'contract_value', 'value_eur']:
    if col in df.columns:
        print(f"  {col}: dtype={df[col].dtype}, nulls={df[col].isna().sum()}, sample={df[col].iloc[0]}")

# Save column info
with open('results/other/parquet_schema.json', 'w') as f:
    json.dump({
        'n_rows': len(df),
        'columns': list(df.columns),
        'dtypes': {c: str(df[c].dtype) for c in df.columns},
        'memory_gb': df.memory_usage(deep=True).sum() / 1e9
    }, f, indent=2)

print("\nSchema saved to results/parquet_schema.json")
