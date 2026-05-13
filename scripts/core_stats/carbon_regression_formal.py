#!/usr/bin/env python3
"""
Formal within-sector carbon regression using Eurostat data.

Model (cell level):
  CI_{csy} = β × SB_share_{csy} + α_{c×s} + γ_y + ε_{csy}

Where each observation is a (country, NACE-sector, year) cell.
CI = Eurostat carbon intensity (kg CO2/EUR GVA).
SB_share = fraction of contracts that are single-bidder.
Country-clustered SEs with wild cluster restricted (WCR) bootstrap.
"""
import csv, json, collections, os
import numpy as np
from scipy import stats as sp_stats
import pyarrow.parquet as pq

# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
BASE = _d

# ── Crosswalks ───────────────────────────────────────────────────────────────
CPV_TO_NACE = {
    '03': 'A', '09': 'B', '14': 'C13-C15', '15': 'C10-C12', '16': 'A02',
    '18': 'C13-C15', '19': 'C13-C15', '22': 'C17', '24': 'C20',
    '30': 'C29_C30', '31': 'C26', '32': 'C26', '33': 'C21', '34': 'C29_C30',
    '35': 'C25', '37': 'C28', '38': 'C31_C32', '39': 'C31_C32', '42': 'C28',
    '43': 'C28', '44': 'C24', '45': 'F', '48': 'J62_J63', '50': 'H50',
    '51': 'H51', '55': 'I', '60': 'H49', '63': 'H52', '64': 'J58',
    '66': 'K', '70': 'J62_J63', '71': 'M71', '72': 'J62_J63', '73': 'M72',
    '74': 'M69_M70', '75': 'O', '76': 'M69_M70', '77': 'M69_M70',
    '79': 'N79', '80': 'P', '85': 'Q', '90': 'E', '92': 'R', '98': 'M69_M70',
}
EXIO_TO_NACE = {
    'Agriculture': 'A', 'Chemicals': 'C20', 'Computer equipment': 'C26',
    'Computer services': 'J62_J63', 'Construction': 'F', 'Education': 'P',
    'Electrical equipment': 'C27', 'Financial services': 'K',
    'Food products': 'C10-C12', 'Furniture': 'C31_C32', 'Health services': 'Q',
    'Hotels': 'I', 'Land transport': 'H49', 'Leather': 'C13-C15',
    'Machinery': 'C28', 'Metal products': 'C24', 'Mining': 'B',
    'Motor vehicles': 'C29_C30', 'Office machinery': 'C26',
    'Other business services': 'M69_M70', 'Other manufacturing': 'C31_C32',
    'Other services': 'M69_M70', 'Paper': 'C17', 'Petroleum': 'C19',
    'Pharmaceuticals': 'C21', 'Post and telecommunications': 'J61',
    'Public administration': 'O', 'Publishing': 'J58',
    'Rubber and plastics': 'C22', 'Security services': 'N80',
    'Textiles': 'C13-C15', 'Transport equipment': 'C29_C30',
    'Water transport': 'H50', 'Wood products': 'C16',
    'Non-metallic minerals': 'C23', 'Architectural services': 'M71',
}
DEAD_ZONE_CPVS = {'77', '15', '65', '35', '34', '63'}
EU_COUNTRIES = {
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE',
    'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT',
    'RO', 'SK', 'SI', 'ES', 'SE', 'GB', 'NO', 'CH',
}
COUNTRY_MAP = {'GR': 'EL'}


# ═════════════════════════════════════════════════════════════════════════════
# Data loading
# ═════════════════════════════════════════════════════════════════════════════

def load_eurostat_intensities():
    path = os.path.join(BASE, 'Data', 'processed', 'eurostat_carbon_intensities.csv')
    intensities = {}
    with open(path, 'r') as f:
        for row in csv.DictReader(f):
            key = (row['country'], row['nace'], int(row['year']))
            intensities[key] = float(row['intensity_kg_eur'])
    print(f"Loaded {len(intensities):,} Eurostat intensity cells")
    return intensities


def build_cells(intensities):
    """
    Collapse contracts to (country, matched_nace, year) cells.

    Match quality tracking:
      - 'exact': CI found at the contract's NACE level
      - 'parent': CI found at parent NACE letter (e.g. C20→C)
    Cell key uses matched_nace (the level at which CI was actually observed)
    to avoid pseudo-replication.

    Dead-zone status is classified per contract at the CPV level, then
    aggregated to a cell-level dz_share.
    """
    path = os.path.join(BASE, 'Data', 'processed', 'gprd_with_carbon.parquet')
    table = pq.read_table(path, columns=[
        'country', 'year', 'cpv_division', 'exiobase_sector',
        'single_bidder', 'value_eur',
    ])
    N = table.num_rows
    print(f"Loaded {N:,} contracts")

    countries = table.column('country').to_pylist()
    years_raw = table.column('year').to_pylist()
    cpvs     = table.column('cpv_division').to_pylist()
    exios    = table.column('exiobase_sector').to_pylist()
    sb_col   = table.column('single_bidder').to_pylist()
    val_col  = table.column('value_eur').to_pylist()

    # cell key: (eu_country, matched_nace, year)
    # cell value dict:
    #   ci, n_sb, n_mb, val_sb, val_mb, match_quality, n_dz, original_nace
    cells = {}
    stats = {'matched_exact': 0, 'matched_parent': 0,
             'unmatched_nace': 0, 'unmatched_ci': 0, 'skipped': 0}

    for i in range(N):
        c = countries[i]
        if not c or c not in EU_COUNTRIES:
            stats['skipped'] += 1
            continue
        try:
            yr = int(float(years_raw[i]))
        except (TypeError, ValueError):
            stats['skipped'] += 1
            continue
        if yr < 2008 or yr > 2023:
            stats['skipped'] += 1
            continue

        sb = sb_col[i]
        if sb is None:
            stats['skipped'] += 1
            continue

        cpv = cpvs[i]
        exio = exios[i]
        cpv_str = str(cpv).zfill(2) if cpv else ''

        # Map to NACE
        nace = CPV_TO_NACE.get(cpv_str) if cpv_str else None
        if not nace and exio:
            nace = EXIO_TO_NACE.get(exio)
        if not nace:
            stats['unmatched_nace'] += 1
            continue

        # Eurostat lookup: exact first, then parent
        eu_c = COUNTRY_MAP.get(c, c)
        exact_key = (eu_c, nace, yr)
        ci = intensities.get(exact_key)
        if ci is not None:
            matched_nace = nace
            match_quality = 'exact'
        else:
            parent = nace[0] if len(nace) > 1 else None
            if parent:
                ci = intensities.get((eu_c, parent, yr))
            if ci is not None:
                matched_nace = parent
                match_quality = 'parent'
            else:
                stats['unmatched_ci'] += 1
                continue

        stats[f'matched_{match_quality}'] += 1

        # Contract value
        v = val_col[i]
        try:
            v = float(v)
            if v <= 0 or np.isnan(v):
                v = 0.0
        except (TypeError, ValueError):
            v = 0.0

        # Dead-zone at CPV level
        is_dz = 1 if cpv_str in DEAD_ZONE_CPVS else 0

        # Accumulate into cell keyed at matched_nace level
        cell_key = (eu_c, matched_nace, yr)
        if cell_key not in cells:
            cells[cell_key] = {
                'ci': ci, 'n_sb': 0, 'n_mb': 0,
                'val_sb': 0.0, 'val_mb': 0.0,
                'match_quality': match_quality,
                'n_dz': 0, 'n_total': 0,
                'original_nace': nace,
            }
        cell = cells[cell_key]
        cell['n_total'] += 1
        cell['n_dz'] += is_dz
        if sb:
            cell['n_sb'] += 1
            cell['val_sb'] += v
        else:
            cell['n_mb'] += 1
            cell['val_mb'] += v

    print(f"Match stats: {json.dumps(stats, indent=2)}")
    print(f"Unique cells: {len(cells):,}")

    # Separate by match quality
    exact_cells = {k: v for k, v in cells.items() if v['match_quality'] == 'exact'}
    all_cells = cells
    print(f"  Exact-match cells: {len(exact_cells):,}")
    print(f"  All cells (exact+parent): {len(all_cells):,}")
    return exact_cells, all_cells, stats


# ═════════════════════════════════════════════════════════════════════════════
# Two-way FE demeaning (vectorised)
# ═════════════════════════════════════════════════════════════════════════════

def group_demean(arr, gids, ng, w=None):
    """Demean arr by group; optionally weighted."""
    if w is None:
        s = np.bincount(gids, weights=arr, minlength=ng)
        c = np.bincount(gids, minlength=ng).astype(np.float64)
        m = np.divide(s, c, out=np.zeros(ng), where=c > 0)
        return arr - m[gids]
    else:
        ws = np.bincount(gids, weights=w * arr, minlength=ng)
        wt = np.bincount(gids, weights=w, minlength=ng)
        wm = np.divide(ws, wt, out=np.zeros(ng), where=wt > 0)
        return arr - wm[gids]


def demean_twoway(variables, fe1, nf1, fe2, nf2, w=None,
                  tol=1e-12, maxiter=500):
    """Alternating-projection demeaning for two crossed FE sets."""
    dm = [v.copy() for v in variables]
    for it in range(maxiter):
        prev = [v.copy() for v in dm]
        for k in range(len(dm)):
            dm[k] = group_demean(dm[k], fe1, nf1, w)
            dm[k] = group_demean(dm[k], fe2, nf2, w)
        delta = max(np.max(np.abs(dm[k] - prev[k])) for k in range(len(dm)))
        if delta < tol:
            return dm, it + 1
    print(f"  WARNING: demeaning did not converge (Δ={delta:.2e})")
    return dm, maxiter


def demean_threeway(variables, fe1, nf1, fe2, nf2, fe3, nf3, w=None,
                    tol=1e-12, maxiter=1000):
    """Alternating-projection demeaning for three crossed FE sets."""
    dm = [v.copy() for v in variables]
    for it in range(maxiter):
        prev = [v.copy() for v in dm]
        for k in range(len(dm)):
            dm[k] = group_demean(dm[k], fe1, nf1, w)
            dm[k] = group_demean(dm[k], fe2, nf2, w)
            dm[k] = group_demean(dm[k], fe3, nf3, w)
        delta = max(np.max(np.abs(dm[k] - prev[k])) for k in range(len(dm)))
        if delta < tol:
            return dm, it + 1
    print(f"  WARNING: 3-way demeaning did not converge (Δ={delta:.2e})")
    return dm, maxiter


# ═════════════════════════════════════════════════════════════════════════════
# Clustered inference
# ═════════════════════════════════════════════════════════════════════════════

def crve_scalar(x_dm, resid, cl, G, n, k=1):
    """Cluster-robust variance for a single regressor (scalar β)."""
    xpx = np.dot(x_dm, x_dm)
    if xpx == 0:
        return np.nan
    scores = np.bincount(cl, weights=x_dm * resid, minlength=G)
    meat = np.dot(scores, scores)
    correction = (G / (G - 1.0)) * ((n - 1.0) / (n - k))
    return np.sqrt(meat * correction) / xpx


def crve_multi(X_dm, resid, cl, G, n):
    """Cluster-robust covariance for k regressors. Returns SEs."""
    k = X_dm.shape[1]
    XtX = X_dm.T @ X_dm
    try:
        XtXi = np.linalg.inv(XtX)
    except np.linalg.LinAlgError:
        return np.full(k, np.nan)
    xe = X_dm * resid[:, None]
    scores = np.zeros((G, k))
    for g in range(G):
        mask = cl == g
        scores[g] = xe[mask].sum(axis=0)
    meat = scores.T @ scores
    correction = (G / (G - 1.0)) * ((n - 1.0) / (n - k))
    V = XtXi @ meat @ XtXi * correction
    return np.sqrt(np.diag(V))


def wild_cluster_bootstrap(y_dm, x_dm, cl, G, n_boot=9999, seed=42):
    """
    Wild cluster restricted (WCR) bootstrap for H0: β=0 (scalar regressor).
    Under H0 the restricted residuals are y_dm itself.
    Rademacher weights: v_g ∈ {-1, +1}.
    Returns bootstrap p-value.
    """
    rng = np.random.RandomState(seed)
    xpx = np.dot(x_dm, x_dm)
    if xpx == 0:
        return np.nan

    # Observed statistic
    beta_obs = np.dot(x_dm, y_dm) / xpx
    resid_obs = y_dm - beta_obs * x_dm
    se_obs = crve_scalar(x_dm, resid_obs, cl, G, len(y_dm))
    if np.isnan(se_obs) or se_obs == 0:
        return np.nan
    t_obs = abs(beta_obs / se_obs)

    # Restricted residuals (under H0: β=0)
    e_r = y_dm.copy()

    # Pre-compute cluster membership
    cl_members = [np.where(cl == g)[0] for g in range(G)]

    count_ge = 0
    for _ in range(n_boot):
        # Rademacher weights per cluster
        v = rng.choice([-1.0, 1.0], size=G)
        y_star = np.empty_like(y_dm)
        for g in range(G):
            idx = cl_members[g]
            y_star[idx] = v[g] * e_r[idx]

        beta_star = np.dot(x_dm, y_star) / xpx
        resid_star = y_star - beta_star * x_dm
        se_star = crve_scalar(x_dm, resid_star, cl, G, len(y_dm))
        if np.isnan(se_star) or se_star == 0:
            continue
        t_star = abs(beta_star / se_star)
        if t_star >= t_obs:
            count_ge += 1

    return (count_ge + 1) / (n_boot + 1)  # +1 includes observed


# ═════════════════════════════════════════════════════════════════════════════
# Build numpy arrays from cell dict
# ═════════════════════════════════════════════════════════════════════════════

def cells_to_arrays(cells):
    """Convert cell dict to structured numpy arrays + FE index maps."""
    keys = [k for k, v in cells.items() if (v['n_sb'] + v['n_mb']) > 0]
    n = len(keys)

    ci       = np.zeros(n)
    sb_share = np.zeros(n)
    dz_share = np.zeros(n)
    n_contr  = np.zeros(n)
    tot_val  = np.zeros(n)
    fe1      = np.zeros(n, dtype=np.int32)  # country×NACE
    fe2      = np.zeros(n, dtype=np.int32)  # year
    fe_cy    = np.zeros(n, dtype=np.int32)  # country×year  (for 3-way)
    fe_sy    = np.zeros(n, dtype=np.int32)  # NACE×year     (for 3-way)
    clust    = np.zeros(n, dtype=np.int32)  # country

    cs_map, yr_map, c_map = {}, {}, {}
    cy_map, sy_map = {}, {}

    for idx, k in enumerate(keys):
        eu_c, nace, yr = k
        cell = cells[k]
        nt = cell['n_sb'] + cell['n_mb']

        ci[idx]       = cell['ci']
        sb_share[idx] = cell['n_sb'] / nt
        dz_share[idx] = cell['n_dz'] / nt
        n_contr[idx]  = nt
        tot_val[idx]  = cell['val_sb'] + cell['val_mb']

        # FE indices
        cs = (eu_c, nace)
        if cs not in cs_map: cs_map[cs] = len(cs_map)
        fe1[idx] = cs_map[cs]

        if yr not in yr_map: yr_map[yr] = len(yr_map)
        fe2[idx] = yr_map[yr]

        if eu_c not in c_map: c_map[eu_c] = len(c_map)
        clust[idx] = c_map[eu_c]

        cy = (eu_c, yr)
        if cy not in cy_map: cy_map[cy] = len(cy_map)
        fe_cy[idx] = cy_map[cy]

        sy = (nace, yr)
        if sy not in sy_map: sy_map[sy] = len(sy_map)
        fe_sy[idx] = sy_map[sy]

    info = {
        'n': n, 'n_fe_cs': len(cs_map), 'n_fe_yr': len(yr_map),
        'n_fe_cy': len(cy_map), 'n_fe_sy': len(sy_map),
        'n_clusters': len(c_map),
        'total_contracts': int(n_contr.sum()),
    }
    return dict(ci=ci, sb=sb_share, dz=dz_share, n_contr=n_contr,
                tot_val=tot_val, fe1=fe1, fe2=fe2, fe_cy=fe_cy,
                fe_sy=fe_sy, clust=clust, info=info)


def reindex(ids):
    u = np.unique(ids)
    m = {old: new for new, old in enumerate(u)}
    return np.array([m[x] for x in ids], dtype=np.int32), len(u)


# ═════════════════════════════════════════════════════════════════════════════
# Run one specification
# ═════════════════════════════════════════════════════════════════════════════

def run_spec(y, x, fe1, nf1, fe2, nf2, cl, G, weights=None,
             label="", bootstrap=True, n_boot=9999):
    """
    OLS / WLS with two-way FE, CRVE, and wild cluster bootstrap.
    x may be 1-D (scalar) or 2-D (multivariate).
    """
    n = len(y)
    scalar = (x.ndim == 1)

    if n < 20:
        print(f"  [{label}] Too few obs ({n}), skipping")
        return None

    print(f"\n  [{label}] N={n:,}  FE1={nf1}  FE2={nf2}  G={G}")

    # ── Demean ───────────────────────────────────────────────────────────
    if scalar:
        variables = [y, x]
    else:
        variables = [y] + [x[:, j] for j in range(x.shape[1])]

    dms, iters = demean_twoway(variables, fe1, nf1, fe2, nf2, w=weights)
    print(f"  Demeaning converged in {iters} iterations")

    if weights is not None:
        sw = np.sqrt(weights)
        dms = [v * sw for v in dms]

    y_dm = dms[0]
    if scalar:
        x_dm = dms[1]
    else:
        x_dm = np.column_stack(dms[1:])

    # ── OLS ──────────────────────────────────────────────────────────────
    if scalar:
        xpx = np.dot(x_dm, x_dm)
        if xpx == 0:
            print(f"  [{label}] No variation in X after demeaning")
            return None
        beta = np.dot(x_dm, y_dm) / xpx
        resid = y_dm - beta * x_dm
        betas = np.array([beta])
    else:
        XtX = x_dm.T @ x_dm
        try:
            betas = np.linalg.solve(XtX, x_dm.T @ y_dm)
        except np.linalg.LinAlgError:
            print(f"  [{label}] Singular XtX")
            return None
        resid = y_dm - x_dm @ betas

    # ── Fit stats ────────────────────────────────────────────────────────
    ss_res = np.dot(resid, resid)
    ss_tot = np.dot(y_dm - np.mean(y_dm), y_dm - np.mean(y_dm))
    r2w = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # ── CRVE ─────────────────────────────────────────────────────────────
    if scalar:
        se_crve = crve_scalar(x_dm, resid, cl, G, n)
        ses = np.array([se_crve])
    else:
        ses = crve_multi(x_dm, resid, cl, G, n)

    t_stats = betas / ses
    df = G - 1
    p_asymp = 2.0 * sp_stats.t.sf(np.abs(t_stats), df)

    # ── Wild cluster bootstrap ───────────────────────────────────────────
    if bootstrap and scalar:
        p_boot = wild_cluster_bootstrap(
            y_dm if weights is None else dms[0] * np.sqrt(weights),
            x_dm, cl, G, n_boot=n_boot)
        # Handle the case where weights changed the demeaned variables
        # We already incorporated weights above, so pass the transformed data
        p_boot = wild_cluster_bootstrap(y_dm, x_dm, cl, G, n_boot=n_boot)
    else:
        p_boot = None

    # ── Report ───────────────────────────────────────────────────────────
    result = {
        'n_obs': n,
        'n_fe_country_sector': nf1,
        'n_fe_year': nf2,
        'n_clusters': G,
        'r2_within': round(float(r2w), 6),
        'mean_dep_var': round(float(np.mean(y)), 4),
    }

    if scalar:
        sig = _sigstars(p_asymp[0])
        print(f"  β = {betas[0]:.6f}  SE = {ses[0]:.6f}  "
              f"t = {t_stats[0]:.3f}  p(asymp) = {p_asymp[0]:.4f} {sig}")
        if p_boot is not None:
            print(f"  p(WCR bootstrap, {n_boot} draws) = {p_boot:.4f}")
        result.update({
            'beta_sb': round(float(betas[0]), 6),
            'se_clustered': round(float(ses[0]), 6),
            't_stat': round(float(t_stats[0]), 4),
            'p_asymptotic': round(float(p_asymp[0]), 6),
            'p_wild_cluster_bootstrap': round(float(p_boot), 4) if p_boot is not None else None,
        })
    else:
        for j in range(len(betas)):
            sig = _sigstars(p_asymp[j])
            print(f"  β_{j} = {betas[j]:.6f}  SE = {ses[j]:.6f}  "
                  f"t = {t_stats[j]:.3f}  p = {p_asymp[j]:.4f} {sig}")

    print(f"  R²(within) = {r2w:.6f}")
    return result, betas, ses, t_stats, p_asymp, p_boot


def _sigstars(p):
    if p < 0.001: return '***'
    if p < 0.01:  return '**'
    if p < 0.05:  return '*'
    return ''


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 72)
    print("FORMAL WITHIN-SECTOR CARBON REGRESSION (Eurostat) — Cell Level")
    print("=" * 72)

    intensities = load_eurostat_intensities()
    exact_cells, all_cells, match_stats = build_cells(intensities)

    results = {'_metadata': {
        'model': 'CI_eurostat = β × SB_share + α_{country×NACE} + γ_{year} + ε',
        'unit_of_observation': 'country × NACE-sector × year cell',
        'dep_var': 'Eurostat carbon intensity (kg CO2 / EUR GVA)',
        'indep_var': 'Single-bidder share (fraction of contracts)',
        'clustering': 'country',
        'inference': 'CRVE + Wild Cluster Restricted bootstrap (Rademacher, 9999 draws)',
        'match_stats': match_stats,
    }}

    # ── Build arrays ─────────────────────────────────────────────────────
    E = cells_to_arrays(exact_cells)
    A = cells_to_arrays(all_cells)

    print(f"\n── EXACT-MATCH SAMPLE ──")
    print(f"  Cells: {E['info']['n']:,}")
    print(f"  Contracts represented: {E['info']['total_contracts']:,}")
    print(f"  Country×NACE FE: {E['info']['n_fe_cs']}")
    print(f"  Year FE: {E['info']['n_fe_yr']}")
    print(f"  Clusters: {E['info']['n_clusters']}")

    # ==================================================================
    # SPEC 1  Main — exact match, unweighted
    # ==================================================================
    print("\n" + "=" * 72)
    print("SPEC 1: Main — Exact Match, Unweighted")
    print("=" * 72)
    r1 = run_spec(E['ci'], E['sb'], E['fe1'], E['info']['n_fe_cs'],
                  E['fe2'], E['info']['n_fe_yr'],
                  E['clust'], E['info']['n_clusters'],
                  label="Main unweighted")
    if r1:
        res = r1[0]
        res['specification'] = 'CI = β×SB_share + α_{c×s} + γ_y (unweighted, exact match)'
        res['total_contracts'] = E['info']['total_contracts']
        results['spec1_main_unweighted'] = res

    # ==================================================================
    # SPEC 2  Main — exact match, value-weighted (WLS)
    # ==================================================================
    print("\n" + "=" * 72)
    print("SPEC 2: Main — Exact Match, Value-Weighted")
    print("=" * 72)
    vmask = E['tot_val'] > 0
    if vmask.sum() > 20:
        sub = {k: v[vmask] if isinstance(v, np.ndarray) else v
               for k, v in E.items()}
        fe1r, nf1r = reindex(sub['fe1'])
        fe2r, nf2r = reindex(sub['fe2'])
        clr,  ncl  = reindex(sub['clust'])
        r2 = run_spec(sub['ci'], sub['sb'], fe1r, nf1r, fe2r, nf2r,
                       clr, ncl, weights=sub['tot_val'],
                       label="Value-weighted")
        if r2:
            res = r2[0]
            res['specification'] = 'WLS: CI = β×SB_share + FE, weights=cell_total_value'
            results['spec2_value_weighted'] = res

    # ==================================================================
    # SPEC 3  Main — exact match, contract-count-weighted
    # ==================================================================
    print("\n" + "=" * 72)
    print("SPEC 3: Main — Exact Match, Contract-Count Weighted")
    print("=" * 72)
    r3 = run_spec(E['ci'], E['sb'], E['fe1'], E['info']['n_fe_cs'],
                  E['fe2'], E['info']['n_fe_yr'],
                  E['clust'], E['info']['n_clusters'],
                  weights=E['n_contr'],
                  label="Contract-count weighted")
    if r3:
        res = r3[0]
        res['specification'] = 'WLS: CI = β×SB_share + FE, weights=n_contracts'
        res['note'] = 'Equivalent to contract-level OLS (CI constant within cell)'
        res['total_contracts'] = E['info']['total_contracts']
        results['spec3_contract_weighted'] = res

    # ==================================================================
    # SPEC 4  Dead Zone subsample (dz_share > 0.5)
    # ==================================================================
    print("\n" + "=" * 72)
    print("SPEC 4: Dead Zone Cells (dz_share > 0.5)")
    print("=" * 72)
    dz_mask = E['dz'] > 0.5
    print(f"  Dead-zone cells: {dz_mask.sum()}")
    if dz_mask.sum() > 20:
        fe1r, nf1r = reindex(E['fe1'][dz_mask])
        fe2r, nf2r = reindex(E['fe2'][dz_mask])
        clr,  ncl  = reindex(E['clust'][dz_mask])
        r4 = run_spec(E['ci'][dz_mask], E['sb'][dz_mask],
                       fe1r, nf1r, fe2r, nf2r, clr, ncl,
                       label="Dead Zone")
        if r4:
            res = r4[0]
            res['specification'] = 'Dead-zone cells (>50% contracts from DZ CPVs)'
            res['dead_zone_cpvs'] = sorted(list(DEAD_ZONE_CPVS))
            results['spec4_dead_zone'] = res

    # ==================================================================
    # SPEC 5  Non-Dead Zone subsample
    # ==================================================================
    print("\n" + "=" * 72)
    print("SPEC 5: Non-Dead Zone Cells (dz_share ≤ 0.5)")
    print("=" * 72)
    ndz_mask = E['dz'] <= 0.5
    if ndz_mask.sum() > 20:
        fe1r, nf1r = reindex(E['fe1'][ndz_mask])
        fe2r, nf2r = reindex(E['fe2'][ndz_mask])
        clr,  ncl  = reindex(E['clust'][ndz_mask])
        r5 = run_spec(E['ci'][ndz_mask], E['sb'][ndz_mask],
                       fe1r, nf1r, fe2r, nf2r, clr, ncl,
                       label="Non-Dead Zone")
        if r5:
            res = r5[0]
            res['specification'] = 'Non-dead-zone cells (≤50% DZ contracts)'
            results['spec5_non_dead_zone'] = res

    # ==================================================================
    # SPEC 6  Interaction: SB × DZ_share
    # ==================================================================
    print("\n" + "=" * 72)
    print("SPEC 6: Interaction — SB_share × DZ_share")
    print("=" * 72)
    interaction = E['sb'] * E['dz']
    X_int = np.column_stack([E['sb'], E['dz'], interaction])
    r6 = run_spec(E['ci'], X_int,
                  E['fe1'], E['info']['n_fe_cs'],
                  E['fe2'], E['info']['n_fe_yr'],
                  E['clust'], E['info']['n_clusters'],
                  label="Interaction", bootstrap=False)
    if r6:
        res = r6[0]
        betas, ses, ts, ps = r6[1], r6[2], r6[3], r6[4]
        labels = ['SB_share', 'DZ_share', 'SB_share×DZ_share']
        for j, lab in enumerate(labels):
            res[f'beta_{lab}'] = round(float(betas[j]), 6)
            res[f'se_{lab}'] = round(float(ses[j]), 6)
            res[f't_{lab}'] = round(float(ts[j]), 4)
            res[f'p_{lab}'] = round(float(ps[j]), 6)
        res['specification'] = 'CI = β₁SB + β₂DZ + β₃(SB×DZ) + FE'
        res['note'] = 'DZ main effect largely absorbed by country×NACE FE; β₃ is the heterogeneity test'
        results['spec6_interaction'] = res

    # ==================================================================
    # ROBUSTNESS 1  Exact + parent-NACE fallback, unweighted
    # ==================================================================
    print("\n" + "=" * 72)
    print("ROBUSTNESS 1: All Matches (exact + parent NACE), Unweighted")
    print("=" * 72)
    rr1 = run_spec(A['ci'], A['sb'], A['fe1'], A['info']['n_fe_cs'],
                   A['fe2'], A['info']['n_fe_yr'],
                   A['clust'], A['info']['n_clusters'],
                   label="All matches unweighted")
    if rr1:
        res = rr1[0]
        res['specification'] = 'Robustness: exact + parent-NACE fallback (unweighted)'
        res['total_contracts'] = A['info']['total_contracts']
        results['robustness_all_matches_unweighted'] = res

    # ==================================================================
    # ROBUSTNESS 2  Exact + parent, value-weighted
    # ==================================================================
    print("\n" + "=" * 72)
    print("ROBUSTNESS 2: All Matches, Value-Weighted")
    print("=" * 72)
    vmask_a = A['tot_val'] > 0
    if vmask_a.sum() > 20:
        fe1r, nf1r = reindex(A['fe1'][vmask_a])
        fe2r, nf2r = reindex(A['fe2'][vmask_a])
        clr,  ncl  = reindex(A['clust'][vmask_a])
        rr2 = run_spec(A['ci'][vmask_a], A['sb'][vmask_a],
                        fe1r, nf1r, fe2r, nf2r, clr, ncl,
                        weights=A['tot_val'][vmask_a],
                        label="All matches value-weighted")
        if rr2:
            res = rr2[0]
            res['specification'] = 'Robustness: exact + parent, value-weighted'
            results['robustness_all_matches_value_weighted'] = res

    # ==================================================================
    # ROBUSTNESS 3  Three-way FE: country×NACE + country×year + NACE×year
    # ==================================================================
    print("\n" + "=" * 72)
    print("ROBUSTNESS 3: Three-Way FE (country×NACE + country×year + NACE×year)")
    print("=" * 72)
    results['robustness_threeway_fe'] = run_threeway_fe(E)

    # ══════════════════════════════════════════════════════════════════════
    # SAVE
    # ══════════════════════════════════════════════════════════════════════
    out_path = os.path.join(BASE, 'results', 'core_stats', 'carbon_regression_results.json')
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n{'=' * 72}")
    print(f"Results saved to {out_path}")

    # ── Summary table ────────────────────────────────────────────────────
    print(f"\n{'=' * 72}")
    print("SUMMARY TABLE")
    print(f"{'=' * 72}")
    hdr = f"{'Specification':<42s} {'β':>9s} {'SE':>9s} {'t':>7s} {'p(asy)':>8s} {'p(WCR)':>8s} {'N':>7s}"
    print(hdr)
    print("-" * len(hdr))
    for key in ['spec1_main_unweighted', 'spec2_value_weighted',
                'spec3_contract_weighted', 'spec4_dead_zone',
                'spec5_non_dead_zone',
                'robustness_all_matches_unweighted',
                'robustness_all_matches_value_weighted',
                'robustness_threeway_fe']:
        r = results.get(key)
        if not r or not isinstance(r, dict) or 'beta_sb' not in r:
            continue
        pw = r.get('p_wild_cluster_bootstrap')
        pw_s = f"{pw:.4f}" if pw is not None else "  n/a"
        sig = _sigstars(r['p_asymptotic'])
        print(f"{key:<42s} {r['beta_sb']:>9.4f} {r['se_clustered']:>9.4f} "
              f"{r['t_stat']:>7.3f} {r['p_asymptotic']:>8.4f} {pw_s:>8s} "
              f"{r['n_obs']:>7,d} {sig}")
    print()


def run_threeway_fe(E):
    """Three-way FE: country×NACE + country×year + NACE×year."""
    n = E['info']['n']
    print(f"  N={n:,}  FE_cs={E['info']['n_fe_cs']}  "
          f"FE_cy={E['info']['n_fe_cy']}  FE_sy={E['info']['n_fe_sy']}")

    dms, iters = demean_threeway(
        [E['ci'], E['sb']],
        E['fe1'], E['info']['n_fe_cs'],
        E['fe_cy'], E['info']['n_fe_cy'],
        E['fe_sy'], E['info']['n_fe_sy'],
    )
    print(f"  Three-way demeaning converged in {iters} iterations")

    y_dm, x_dm = dms
    xpx = np.dot(x_dm, x_dm)
    if xpx == 0:
        print("  No variation in X after 3-way demeaning")
        return None
    beta = np.dot(x_dm, y_dm) / xpx
    resid = y_dm - beta * x_dm

    ss_res = np.dot(resid, resid)
    ss_tot = np.dot(y_dm - np.mean(y_dm), y_dm - np.mean(y_dm))
    r2w = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    G = E['info']['n_clusters']
    se = crve_scalar(x_dm, resid, E['clust'], G, n)
    t = beta / se if se > 0 and not np.isnan(se) else np.nan
    p_asy = 2.0 * sp_stats.t.sf(abs(t), G - 1) if not np.isnan(t) else np.nan

    p_boot = wild_cluster_bootstrap(y_dm, x_dm, E['clust'], G)

    sig = _sigstars(p_asy)
    print(f"  β = {beta:.6f}  SE = {se:.6f}  t = {t:.3f}  "
          f"p(asy) = {p_asy:.4f}  p(WCR) = {p_boot:.4f} {sig}")
    print(f"  R²(within) = {r2w:.6f}")

    return {
        'beta_sb': round(float(beta), 6),
        'se_clustered': round(float(se), 6),
        't_stat': round(float(t), 4),
        'p_asymptotic': round(float(p_asy), 6),
        'p_wild_cluster_bootstrap': round(float(p_boot), 4),
        'r2_within': round(float(r2w), 6),
        'n_obs': n,
        'n_fe_country_sector': E['info']['n_fe_cs'],
        'n_fe_country_year': E['info']['n_fe_cy'],
        'n_fe_nace_year': E['info']['n_fe_sy'],
        'n_clusters': G,
        'mean_dep_var': round(float(np.mean(E['ci'])), 4),
        'specification': 'Robustness: CI = β×SB + α_{c×s} + δ_{c×y} + φ_{s×y}',
    }


if __name__ == '__main__':
    main()
