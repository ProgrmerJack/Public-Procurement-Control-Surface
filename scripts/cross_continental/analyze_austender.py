import csv
from collections import defaultdict, Counter

contracts = []
with open(r'C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\raw\austender\austender_contracts.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        contracts.append(row)

print(f'Total contracts: {len(contracts):,}')

methods = Counter(row['procurement_method'] for row in contracts)
print('\nProcurement methods:')
for m, c in methods.most_common(10):
    pct = c/len(contracts)*100
    print(f'  {m}: {c:,} ({pct:.1f}%)')

n_sb = sum(1 for row in contracts if 'limited' in row['procurement_method'].lower() or 'direct' in row['procurement_method'].lower())
print(f'\nSingle-bidder proxy (limited/direct): {n_sb:,} ({n_sb/len(contracts)*100:.1f}%)')

years = defaultdict(lambda: [0, 0, 0.0])
for row in contracts:
    year = row.get('date_signed', row.get('award_date', ''))[:4]
    if year.isdigit() and 2010 <= int(year) <= 2025:
        y = int(year)
        years[y][0] += 1
        method = row['procurement_method'].lower().strip()
        if 'limited' in method or 'direct' in method:
            years[y][1] += 1
        try:
            years[y][2] += float(row.get('amount', 0) or 0)
        except:
            pass

print('\nYear | N | SB_rate | Value_AUD_B')
for y in sorted(years.keys()):
    n, sb, val = years[y]
    sb_rate = sb / n * 100 if n else 0
    print(f'{y} | {n:>8,} | {sb_rate:>5.1f}% | {val/1e9:.2f}B')

sectors = Counter()
for row in contracts:
    code = row.get('unspsc_code', '')[:2]
    if code:
        sectors[code] += 1
print('\nTop UNSPSC sectors:')
for s, c in sectors.most_common(10):
    print(f'  {s}: {c:,}')
