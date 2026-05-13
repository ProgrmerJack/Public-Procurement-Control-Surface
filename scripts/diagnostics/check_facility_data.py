#!/usr/bin/env python3
import pandas as pd
import zipfile
import os

print("\n=== CHECKING FOR FACILITY-LEVEL DATA ===\n")

# First, check the current CSV data
df_ets = pd.read_csv('Data/eu_ets.csv')
print(f"EU ETS CSV - Rows: {len(df_ets)}, Cols: {len(df_ets.columns)}")
print(f"Columns: {df_ets.columns.tolist()}")

# Check a subset
subset = df_ets[(df_ets['country']=='Germany') & (df_ets['main activity sector name']=='Production of pig iron or steel')]
print(f"\nSample - Germany Steel Sector:")
print(f"  Rows: {len(subset)}")
print(f"  Years: {sorted(subset['year'].unique())}")
print(f"  ETS Info types: {subset['ETS information'].unique()}")

# Check if EUTL zip contains facility data
print("\n\n=== CHECKING EUTL DATA ===\n")

eutl_zip = 'Data/eutl_data.zip'
if os.path.exists(eutl_zip):
    with zipfile.ZipFile(eutl_zip, 'r') as z:
        files = z.namelist()
        print(f"Files in EUTL zip: {len(files)} files")
        for f in files[:20]:
            print(f"  - {f}")
        
        # Try to load a CSV if present
        csv_files = [f for f in files if f.endswith('.csv')]
        if csv_files:
            print(f"\nCSV files found: {len(csv_files)}")
            # Try reading first CSV to see structure
            try:
                with z.open(csv_files[0]) as f:
                    df_sample = pd.read_csv(f, nrows=100)
                    print(f"\nFirst CSV ({csv_files[0]}):")
                    print(f"  Shape: {df_sample.shape}")
                    print(f"  Columns: {df_sample.columns.tolist()[:10]}")
                    print(f"  First row: {df_sample.iloc[0]}")
            except Exception as e:
                print(f"  Could not read: {e}")

print("\n\n=== CHECKING E-PRTR DATA ===\n")

eprtr_dir = 'Data/eprtr'
if os.path.isdir(eprtr_dir):
    files = os.listdir(eprtr_dir)
    print(f"Files in eprtr directory: {len(files)}")
    for f in files[:20]:
        print(f"  - {f}")
