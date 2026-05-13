import pandas as pd
import csv

# Test E-PRTR loading
print("Testing E-PRTR data structure...")
try:
    eprtr = pd.read_csv(
        'Data/raw/eea_t_ied-eprtr_p_2007-2023_v15_r00/User-friendly-CSV/F1_4_Air_Releases_Facilities.csv',
        nrows=10,
        low_memory=False
    )
    print("E-PRTR columns:", eprtr.columns.tolist())
    if len(eprtr) > 0:
        print("Sample row:")
        print(eprtr.iloc[0][['facilityName', 'countryName', 'EPRTRAnnexIMainActivity', 'Pollutant']].to_dict())
except Exception as e:
    print(f"Error reading E-PRTR: {e}")

# Check what the actual Pollutant values are
print("\nUnique pollutants (first 50 unique values):")
try:
    with open('Data/raw/eea_t_ied-eprtr_p_2007-2023_v15_r00/User-friendly-CSV/F1_4_Air_Releases_Facilities.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        pollutants = set()
        for i, row in enumerate(reader):
            if i >= 100000:  # Sample
                break
            if row['Pollutant']:
                pollutants.add(row['Pollutant'])
        for p in sorted(pollutants)[:30]:
            print(f"  - {p}")
except Exception as e:
    print(f"Error: {e}")

# Check for refineries activity code
print("\nUnique EPRTRAnnexIMainActivity codes (sample):")
try:
    activities = set()
    with open('Data/raw/eea_t_ied-eprtr_p_2007-2023_v15_r00/User-friendly-CSV/F1_4_Air_Releases_Facilities.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 50000:
                break
            if row.get('EPRTRAnnexIMainActivity'):
                activities.add(row['EPRTRAnnexIMainActivity'])
    for a in sorted(activities)[:20]:
        print(f"  - {a}")
except Exception as e:
    print(f"Error: {e}")
