import pandas as pd

# Check null rates for buyer_id and supplier_id in main file
df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet')
print('gprd_with_carbon.parquet ID fields:')
print(f'  buyer_id nulls: {df["buyer_id"].isnull().sum():,} ({df["buyer_id"].isnull().sum()/len(df)*100:.1f}%)')
print(f'  supplier_id nulls: {df["supplier_id"].isnull().sum():,} ({df["supplier_id"].isnull().sum()/len(df)*100:.1f}%)')
