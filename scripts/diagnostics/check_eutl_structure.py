#!/usr/bin/env python3
import pandas as pd
import zipfile

eutl_zip = 'Data/eutl_data.zip'
with zipfile.ZipFile(eutl_zip, 'r') as z:
    installation_df = pd.read_csv(z.open('installation.csv'))
    activity_df = pd.read_csv(z.open('activity_type.csv'))
    compliance_df = pd.read_csv(z.open('compliance.csv'))

print("Installation columns:")
print(installation_df.columns.tolist())

print("\nActivity columns:")
print(activity_df.columns.tolist())

print("\nCompliance columns:")
print(compliance_df.columns.tolist())

print("\nSample installation row:")
print(installation_df.iloc[0])

print("\nSample activity row:")
print(activity_df.iloc[0])

print("\nSample compliance row:")
print(compliance_df.iloc[0])
