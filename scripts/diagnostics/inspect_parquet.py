import pandas as pd

df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet')

print('===SHAPE===')
print(f'Rows: {len(df):,}, Columns: {len(df.columns)}')

print('\n===ALL COLUMNS WITH DTYPES===')
for col in df.columns:
    print(f'{col}: {df[col].dtype}')

print('\n===KEY IDENTIFIER COLUMNS===')
print(f'buyer_id: unique={df["buyer_id"].nunique()}, sample={df["buyer_id"].iloc[0]}')
print(f'supplier_id: unique={df["supplier_id"].nunique()}, sample={df["supplier_id"].iloc[0]}')
print(f'record_id: unique={df["record_id"].nunique()}, sample={df["record_id"].iloc[0]}')
print(f'ocid: unique={df["ocid"].nunique()}, sample={df["ocid"].iloc[0]}')

print('\n===CPV CODES (CLASSIFICATION)===')
cpv_samples = df["cpv_code"].dropna().unique()[:10]
print(f'cpv_code: unique={df["cpv_code"].nunique()}')
print(f'  Examples: {list(cpv_samples)}')
cpv_div_samples = df["cpv_division"].dropna().unique()[:10]
print(f'cpv_division: unique={df["cpv_division"].nunique()}')
print(f'  Examples: {list(cpv_div_samples)}')

print('\n===COUNTRY (LOCATION)===')
print(f'country: unique={df["country"].nunique()}')
print(f'  Examples: {list(df["country"].unique())}')

print('\n===SECTORS===')
print(f'sector: unique={df["sector"].nunique()}, nulls={df["sector"].isnull().sum()}')
sector_samples = df["sector"].dropna().unique()[:10]
print(f'  Examples: {list(sector_samples)}')

print(f'\nexiobase_sector: unique={df["exiobase_sector"].nunique()}, nulls={df["exiobase_sector"].isnull().sum()}')
exio_samples = df["exiobase_sector"].dropna().unique()[:10]
print(f'  Examples: {list(exio_samples)}')

print('\n===SAMPLE ROW===')
print(df.iloc[0].to_string())
