import pandas as pd

# Check EU TED sample to see if it has names
print("===eu_ted_sample_10000.csv columns===")
try:
    df_ted_sample = pd.read_csv('Data/processed/eu_ted/eu_ted_sample_10000.csv')
    print(f'Shape: {df_ted_sample.shape}')
    print('Columns:')
    for col in df_ted_sample.columns:
        print(f'  {col}')
    print(f'\nFirst row (first 20 columns):')
    print(df_ted_sample.iloc[0, :20])
except Exception as e:
    print(f'Error: {e}')

print("\n===ocds/uk_sample_10000.csv columns===")
try:
    df_uk = pd.read_csv('Data/processed/ocds/uk_sample_10000.csv')
    print(f'Shape: {df_uk.shape}')
    print('Columns:')
    for col in df_uk.columns:
        print(f'  {col}')
    print(f'\nFirst row:')
    print(df_uk.iloc[0])
except Exception as e:
    print(f'Error: {e}')

print("\n===ocds/colombia_sample_10000.csv columns===")
try:
    df_col = pd.read_csv('Data/processed/ocds/colombia_sample_10000.csv')
    print(f'Shape: {df_col.shape}')
    print('Columns:')
    for col in df_col.columns:
        print(f'  {col}')
except Exception as e:
    print(f'Error: {e}')
