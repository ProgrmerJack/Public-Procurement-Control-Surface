"""Test script to verify dtype conversions work."""
import pandas as pd
import numpy as np
from pathlib import Path

# Simulate the problematic column scenario
df = pd.DataFrame({
    'time_to_award_days': [30.0, None, 45.0, '60', None],  # Mixed types
    'n_bidders': [3, None, 5, 2, None],
    'value_usd': [1000.0, 2000.0, None, 4000.0, 5000.0],
    'is_framework': [True, False, None, True, False],
    'country': ['US', 'UK', 'DE', 'FR', 'ES']
})

print("Before conversion:")
print(df.dtypes)
print("\nData:")
print(df)

# Apply the same conversion logic as harmonize_data.py
numeric_cols = ['time_to_award_days', 'n_bidders', 'value_usd']
for col in numeric_cols:
    if col in df.columns and df[col].dtype == 'object':
        print(f"\nConverting {col} from object to numeric...")
        df[col] = pd.to_numeric(df[col], errors='coerce')

bool_cols = ['is_framework']
for col in bool_cols:
    if col in df.columns:
        print(f"Converting {col} to boolean...")
        df[col] = df[col].astype('boolean')

print("\nAfter conversion:")
print(df.dtypes)
print("\nData:")
print(df)

# Try to save to parquet
test_path = Path('C:/Users/Jack0/GitHub/Public-Procurement-Control-Surface/Data/processed/test_dtype.parquet')
try:
    df.to_parquet(test_path)
    print(f"\n✅ Successfully saved to {test_path}")
    print(f"File size: {test_path.stat().st_size} bytes")
    
    # Read it back
    df_read = pd.read_parquet(test_path)
    print("\nRead back dtypes:")
    print(df_read.dtypes)
    
    # Clean up
    test_path.unlink()
    print("\n✅ Test passed! Dtype conversion works correctly.")
except Exception as e:
    print(f"\n❌ Error: {e}")
