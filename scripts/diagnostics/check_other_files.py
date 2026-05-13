import pandas as pd

print("===gprd_master.parquet===")
try:
    df_master = pd.read_parquet('Data/processed/gprd_master.parquet')
    print(f'Columns: {df_master.shape}')
    print('Columns:')
    for col in df_master.columns:
        print(f'  {col}: {df_master[col].dtype}')
except Exception as e:
    print(f'Error: {e}')

print("\n===eu_ted_harmonized.parquet===")
try:
    df_ted = pd.read_parquet('Data/processed/eu_ted/eu_ted_harmonized.parquet')
    print(f'Shape: {df_ted.shape}')
    print('Columns:')
    for col in df_ted.columns:
        print(f'  {col}: {df_ted[col].dtype}')
except Exception as e:
    print(f'Error: {e}')

print("\n===Checking CSV samples===")
try:
    df_sample = pd.read_csv('Data/processed/gprd_sample_10000.csv')
    print(f'\ngprd_sample_10000.csv columns:')
    for col in df_sample.columns:
        print(f'  {col}: {df_sample[col].dtype}')
except Exception as e:
    print(f'Error: {e}')

print("\n===Checking reference data===")
try:
    df_cpv = pd.read_csv('Data/reference/cpv_sectors.csv')
    print(f'\ncpv_sectors.csv shape: {df_cpv.shape}')
    print('Columns:')
    for col in df_cpv.columns:
        print(f'  {col}')
    print(f'\nFirst 5 rows:')
    print(df_cpv.head())
except Exception as e:
    print(f'Error: {e}')

print("\n===Checking country metadata===")
try:
    df_country = pd.read_csv('Data/reference/country_metadata.csv')
    print(f'\ncountry_metadata.csv columns:')
    for col in df_country.columns:
        print(f'  {col}')
except Exception as e:
    print(f'Error: {e}')
