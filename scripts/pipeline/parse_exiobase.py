#!/usr/bin/env python3
"""
EXIOBASE 3.8 Parser for Carbon Intensity Factors

Parses EXIOBASE Industry-by-Industry (IOT) tables to extract carbon emission 
factors (CO2 equivalent) per sector per year for linking to procurement data.

The script reads:
- F.txt from air_emissions satellite accounts (emission factors by industry)
- Sector classifications for mapping to CPV codes
- Multiple years (1995-2022) for time-varying emission factors

Output:
- Data/processed/exiobase/carbon_factors_by_year.parquet
- Data/processed/exiobase/sector_emission_trends.parquet

Author: Abduxoliq Ashuraliyev
License: MIT
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import json

import numpy as np
import pandas as pd
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base paths
# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
BASE_DIR = _d
DATA_DIR = BASE_DIR / "Data"
RAW_EXIOBASE = DATA_DIR / "raw" / "exiobase"
OUTPUT_DIR = DATA_DIR / "processed" / "exiobase"

# EXIOBASE sector to GPRD sector mapping
# Based on EXIOBASE 3.8 industry classifications
EXIOBASE_TO_GPRD = {
    # Agriculture (A01-A03)
    "Cultivation of paddy rice": "AGRICULTURE",
    "Cultivation of wheat": "AGRICULTURE",
    "Cultivation of cereal grains nec": "AGRICULTURE",
    "Cultivation of vegetables, fruit, nuts": "AGRICULTURE",
    "Cultivation of oil seeds": "AGRICULTURE",
    "Cultivation of sugar cane, sugar beet": "AGRICULTURE",
    "Cultivation of plant-based fibers": "AGRICULTURE",
    "Cultivation of crops nec": "AGRICULTURE",
    "Cattle farming": "AGRICULTURE",
    "Pigs farming": "AGRICULTURE",
    "Poultry farming": "AGRICULTURE",
    "Meat animals nec": "AGRICULTURE",
    "Animal products nec": "AGRICULTURE",
    "Raw milk": "AGRICULTURE",
    "Wool, silk-worm cocoons": "AGRICULTURE",
    "Manure treatment (conventional), storage and land application": "AGRICULTURE",
    "Manure treatment (biogas), storage and land application": "AGRICULTURE",
    "Forestry, logging and related service activities": "AGRICULTURE",
    "Fishing, operating of fish hatcheries and fish farms; service activities incidental to fishing": "AGRICULTURE",
    
    # Mining (B05-B09)
    "Mining of coal and lignite; extraction of peat": "MINING",
    "Extraction of crude petroleum and services related to crude oil extraction, excluding surveying": "ENERGY",
    "Extraction of natural gas and services related to natural gas extraction, excluding surveying": "ENERGY",
    "Extraction, liquefaction, and regasification of other petroleum and gaseous materials": "ENERGY",
    "Mining of uranium and thorium ores": "MINING",
    "Mining of iron ores": "MINING",
    "Mining of copper ores and concentrates": "MINING",
    "Mining of nickel ores and concentrates": "MINING",
    "Mining of aluminium ores and concentrates": "MINING",
    "Mining of precious metal ores and concentrates": "MINING",
    "Mining of lead, zinc and tin ores and concentrates": "MINING",
    "Mining of other non-ferrous metal ores and concentrates": "MINING",
    "Quarrying of stone": "MINING",
    "Quarrying of sand and clay": "MINING",
    "Mining of chemical and fertilizer minerals, production of salt, other mining and quarrying n.e.c.": "MINING",
    
    # Food and Beverages (C10-C12)
    "Processing of meat cattle": "AGRICULTURE",
    "Processing of meat pigs": "AGRICULTURE",
    "Processing of meat poultry": "AGRICULTURE",
    "Production of meat products nec": "AGRICULTURE",
    "Processing vegetable oils and fats": "AGRICULTURE",
    "Processing of dairy products": "AGRICULTURE",
    "Processed rice": "AGRICULTURE",
    "Sugar refining": "AGRICULTURE",
    "Processing of Food products nec": "AGRICULTURE",
    "Manufacture of beverages": "AGRICULTURE",
    "Manufacture of fish products": "AGRICULTURE",
    "Manufacture of tobacco products": "OTHER",
    
    # Textiles (C13-C15)
    "Manufacture of textiles": "TEXTILES",
    "Manufacture of wearing apparel; dressing and dyeing of fur": "TEXTILES",
    "Tanning and dressing of leather; manufacture of luggage, handbags, saddlery, harness and footwear": "TEXTILES",
    
    # Wood and Paper (C16-C18)
    "Manufacture of wood and of products of wood and cork, except furniture; manufacture of articles of straw and plaiting materials": "CONSTRUCTION",
    "Re-processing of secondary wood material into new wood material": "CONSTRUCTION",
    "Pulp": "OFFICE",
    "Re-processing of secondary paper into new pulp": "OFFICE",
    "Paper": "OFFICE",
    "Publishing, printing and reproduction of recorded media": "OFFICE",
    
    # Chemicals (C19-C23)
    "Manufacture of coke oven products": "ENERGY",
    "Petroleum Refinery": "ENERGY",
    "Processing of nuclear fuel": "ENERGY",
    "Plastics, basic": "CHEMICALS",
    "Re-processing of secondary plastic into new plastic": "CHEMICALS",
    "N-fertiliser": "CHEMICALS",
    "P- and other fertiliser": "CHEMICALS",
    "Chemicals nec": "CHEMICALS",
    "Manufacture of rubber and plastic products": "CHEMICALS",
    "Manufacture of glass and glass products": "CHEMICALS",
    "Re-processing of secondary glass into new glass": "CHEMICALS",
    "Manufacture of ceramic goods": "CONSTRUCTION",
    "Manufacture of bricks, tiles and construction products, in baked clay": "CONSTRUCTION",
    "Manufacture of cement, lime and plite": "CONSTRUCTION",
    "Re-processing of ash intoite materials": "CONSTRUCTION",
    "Manufacture of other non-metallic mineral products n.e.c.": "CONSTRUCTION",
    
    # Metals (C24-C25)
    "Manufacture of basic iron and steel and of ferro-alloys and first products thereof": "MANUFACTURING",
    "Re-processing of secondary steel into new steel": "MANUFACTURING",
    "Precious metals production": "MANUFACTURING",
    "Aluminium production": "MANUFACTURING",
    "Re-processing of secondary aluminium into new aluminium": "MANUFACTURING",
    "Lead, zinc and tin production": "MANUFACTURING",
    "Re-processing of secondary lead into new lead, zinc and tin": "MANUFACTURING",
    "Copper production": "MANUFACTURING",
    "Re-processing of secondary copper into new copper": "MANUFACTURING",
    "Other non-ferrous metal production": "MANUFACTURING",
    "Re-processing of secondary other non-ferrous metals into new other non-ferrous metals": "MANUFACTURING",
    "Casting of metals": "MANUFACTURING",
    "Manufacture of fabricated metal products, except machinery and equipment": "MANUFACTURING",
    
    # Machinery (C26-C33)
    "Manufacture of machinery and equipment n.e.c.": "MANUFACTURING",
    "Manufacture of office machinery and computers": "TECH",
    "Manufacture of electrical machinery and apparatus n.e.c.": "MANUFACTURING",
    "Manufacture of radio, television and communication equipment and apparatus": "TECH",
    "Manufacture of medical, precision and optical instruments, watches and clocks": "HEALTH",
    "Manufacture of motor vehicles, trailers and semi-trailers": "TRANSPORT",
    "Manufacture of other transport equipment": "TRANSPORT",
    "Manufacture of furniture; manufacturing n.e.c.": "CONSTRUCTION",
    "Recycling of waste and scrap": "UTILITIES",
    "Recycling of bottles by direct reuse": "UTILITIES",
    
    # Electricity and Gas (D35)
    "Production of electricity by coal": "ENERGY",
    "Production of electricity by gas": "ENERGY",
    "Production of electricity by nuclear": "ENERGY",
    "Production of electricity by hydro": "ENERGY",
    "Production of electricity by wind": "ENERGY",
    "Production of electricity by petroleum and other oil derivatives": "ENERGY",
    "Production of electricity by biomass and waste": "ENERGY",
    "Production of electricity by solar photovoltaic": "ENERGY",
    "Production of electricity by solar thermal": "ENERGY",
    "Production of electricity by tide, wave, ocean": "ENERGY",
    "Production of electricity by Geothermal": "ENERGY",
    "Production of electricity nec": "ENERGY",
    "Transmission of electricity": "UTILITIES",
    "Distribution of electricity": "UTILITIES",
    "Manufacture of gas; distribution of gaseous fuels through mains": "UTILITIES",
    "Steam and hot water supply": "UTILITIES",
    
    # Water and Waste (E36-E39)
    "Collection, purification and distribution of water": "UTILITIES",
    "Sewage treatment and disposal": "UTILITIES",
    "Collection, treatment and disposal of other waste": "UTILITIES",
    "Collection, treatment and disposal of hazardous waste": "UTILITIES",
    "Biogasification of food waste, incl. land application": "UTILITIES",
    "Biogasification of paper, incl. land application": "UTILITIES",
    "Biogasification of sewage sludge, incl. land application": "UTILITIES",
    "Composting of food waste, incl. land application": "UTILITIES",
    "Composting of paper and wood, incl. land application": "UTILITIES",
    "Landfill of waste and scrap": "UTILITIES",
    "Incineration of waste: Food": "UTILITIES",
    "Incineration of waste: Paper": "UTILITIES",
    "Incineration of waste: Plastics": "UTILITIES",
    "Incineration of waste: Metals and Inert materials": "UTILITIES",
    "Incineration of waste: Textiles": "UTILITIES",
    "Incineration of waste: Wood": "UTILITIES",
    "Incineration of waste: Oil/Hazardous waste": "UTILITIES",
    
    # Construction (F41-F43)
    "Construction": "CONSTRUCTION",
    "Re-processing of secondary construction material into aggregates": "CONSTRUCTION",
    
    # Trade and Transport (G-H)
    "Sale, maintenance, repair of motor vehicles, motor vehicles parts, motorcycles, motor cycles parts and accessoiries": "TRANSPORT",
    "Retail sale of automotive fuel": "ENERGY",
    "Wholesale trade and commission trade, except of motor vehicles and motorcycles": "SERVICES",
    "Retail trade, except of motor vehicles and motorcycles; repair of personal and household goods": "SERVICES",
    "Hotels and restaurants": "SERVICES",
    "Transport via railways": "TRANSPORT",
    "Other land transport": "TRANSPORT",
    "Transport via pipelines": "TRANSPORT",
    "Sea and coastal water transport": "TRANSPORT",
    "Inland water transport": "TRANSPORT",
    "Air transport": "TRANSPORT",
    "Supporting and auxiliary transport activities; activities of travel agencies": "TRANSPORT",
    "Post and telecommunications": "SERVICES",
    
    # Finance and Real Estate (K-L)
    "Financial intermediation, except insurance and pension funding": "SERVICES",
    "Insurance and pension funding, except compulsory social security": "SERVICES",
    "Activities auxiliary to financial intermediation": "SERVICES",
    "Real estate activities": "CONSTRUCTION",
    "Renting of machinery and equipment without operator and of personal and household goods": "SERVICES",
    
    # Professional Services (M-N)
    "Computer and related activities": "TECH",
    "Research and development": "TECH",
    "Other business activities": "SERVICES",
    
    # Public Administration (O-Q)
    "Public administration and defence; compulsory social security": "DEFENSE",
    "Education": "SERVICES",
    "Health and social work": "HEALTH",
    
    # Other Services (R-T)
    "Activities of membership organisation n.e.c.": "SERVICES",
    "Recreational, cultural and sporting activities": "SERVICES",
    "Other service activities": "SERVICES",
    "Private households with employed persons": "SERVICES",
    "Extra-territorial organizations and bodies": "SERVICES",
}

# CO2 equivalent row names in EXIOBASE F matrix (air emissions)
CO2_EMISSIONS = [
    "CO2 - combustion - air",
    "CO2 - non combustion - Cement production - air",
    "CO2 - non combustion - Calciumite and calcium oxide production - air",
    "CO2 - agriculture - peat decay - air",
    "CO2 - waste - loss of soil carbon by cultivation, pasture - air",
    "CO2 - waste - biogenic - air",
    "CO2 - short-cycle organic - loss soil carbon - air",
]

# GHG emissions to include (convert to CO2-eq using GWP)
GHG_EMISSIONS = {
    "CH4 - combustion - air": 28.0,  # GWP-100 from IPCC AR5
    "CH4 - non combustion - air": 28.0,
    "CH4 - agriculture - air": 28.0,
    "N2O - combustion - air": 265.0,
    "N2O - non combustion - air": 265.0,
    "N2O - agriculture - air": 265.0,
}


def read_exiobase_matrix(folder: Path, matrix_name: str) -> pd.DataFrame:
    """
    Read EXIOBASE matrix file (txt format with tab separation).
    
    Args:
        folder: Path to IOT year folder (e.g., IOT_2020_pxp)
        matrix_name: Name of matrix file (e.g., 'A', 'F', 'Y')
        
    Returns:
        DataFrame with matrix data
    """
    if matrix_name in ['F', 'F_Y']:
        file_path = folder / "air_emissions" / f"{matrix_name}.txt"
    else:
        file_path = folder / f"{matrix_name}.txt"
    
    if not file_path.exists():
        raise FileNotFoundError(f"Matrix file not found: {file_path}")
    
    logger.info(f"Reading {file_path}...")
    
    # EXIOBASE uses tab separation, first column is row labels
    df = pd.read_csv(file_path, sep='\t', index_col=0, header=0, low_memory=False)
    
    return df


def read_exiobase_units(folder: Path, subfolder: str = None) -> pd.DataFrame:
    """Read unit file for EXIOBASE matrix."""
    if subfolder:
        unit_path = folder / subfolder / "unit.txt"
    else:
        unit_path = folder / "unit.txt"
    
    if not unit_path.exists():
        return None
    
    return pd.read_csv(unit_path, sep='\t', header=None, names=['category', 'unit'])


def extract_co2_emissions_by_sector(F_matrix: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Extract CO2 equivalent emissions by sector from F matrix.
    
    Args:
        F_matrix: EXIOBASE F matrix (emissions by industry)
        year: Year of data
        
    Returns:
        DataFrame with CO2 emissions by GPRD sector
    """
    records = []
    
    # Get row index (emission categories)
    emission_rows = F_matrix.index.tolist()
    
    # Get column index (sectors - multi-level: country + sector)
    sector_cols = F_matrix.columns.tolist()
    
    # Identify CO2 rows
    co2_rows = [r for r in emission_rows if any(e in str(r) for e in ['CO2', 'co2'])]
    ghg_rows = [r for r in emission_rows if any(e in str(r) for e in ['CH4', 'N2O', 'ch4', 'n2o'])]
    
    if not co2_rows:
        logger.warning(f"No CO2 emission rows found in F matrix for year {year}")
        logger.debug(f"Available rows: {emission_rows[:20]}...")
        return pd.DataFrame()
    
    logger.info(f"Found {len(co2_rows)} CO2 rows and {len(ghg_rows)} other GHG rows")
    
    # Sum CO2 emissions across all CO2 categories
    co2_totals = F_matrix.loc[co2_rows].sum(axis=0)
    
    # Add GHG emissions converted to CO2-eq
    for ghg_row in ghg_rows:
        for ghg_name, gwp in GHG_EMISSIONS.items():
            if ghg_name.lower() in str(ghg_row).lower():
                try:
                    co2_totals += F_matrix.loc[ghg_row] * gwp
                except:
                    pass
    
    # Parse sector names from columns (handle multi-index or string columns)
    for col in sector_cols:
        try:
            # Column format: "CountryCode_SectorName" or tuple (Country, Sector)
            if isinstance(col, tuple):
                country, sector_name = col[0], col[1]
            else:
                parts = str(col).split('_', 1) if '_' in str(col) else [str(col)[:2], str(col)]
                country = parts[0] if len(parts) > 1 else 'XX'
                sector_name = parts[1] if len(parts) > 1 else str(col)
            
            emission_value = co2_totals[col]
            
            # Map to GPRD sector
            gprd_sector = EXIOBASE_TO_GPRD.get(sector_name, "OTHER")
            
            records.append({
                'year': year,
                'country': country,
                'exiobase_sector': sector_name,
                'gprd_sector': gprd_sector,
                'co2_kg': emission_value,
            })
        except Exception as e:
            logger.debug(f"Error processing column {col}: {e}")
            continue
    
    return pd.DataFrame(records)


def calculate_carbon_intensity(emissions_df: pd.DataFrame, output_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate carbon intensity (kg CO2 per unit of economic output).
    
    Args:
        emissions_df: CO2 emissions by sector
        output_df: Economic output by sector (from x.txt or Y matrix)
        
    Returns:
        DataFrame with carbon intensity factors
    """
    # Merge emissions with output
    merged = emissions_df.merge(
        output_df,
        on=['year', 'country', 'exiobase_sector'],
        how='left'
    )
    
    # Calculate intensity (avoid division by zero)
    merged['output_meur'] = merged['output_meur'].replace(0, np.nan)
    merged['carbon_intensity_kg_per_meur'] = merged['co2_kg'] / merged['output_meur']
    merged['carbon_intensity_kg_per_usd'] = merged['carbon_intensity_kg_per_meur'] / 1e6 * 1.1  # EUR to USD approx
    
    return merged


def process_all_years(years: List[int] = None, variant: str = 'pxp') -> pd.DataFrame:
    """
    Process EXIOBASE data for all available years.
    
    Args:
        years: List of years to process (default: all available)
        variant: 'pxp' (product-by-product) or 'ixi' (industry-by-industry)
        
    Returns:
        Combined DataFrame with emission factors for all years
    """
    if years is None:
        # Find all available year folders
        years = []
        for folder in RAW_EXIOBASE.iterdir():
            if folder.is_dir() and folder.name.startswith('IOT_') and variant in folder.name:
                try:
                    year = int(folder.name.split('_')[1])
                    years.append(year)
                except:
                    continue
        years = sorted(years)
    
    if not years:
        logger.error("No EXIOBASE year folders found!")
        return pd.DataFrame()
    
    logger.info(f"Processing years: {years}")
    
    all_emissions = []
    all_outputs = []
    
    for year in tqdm(years, desc="Processing EXIOBASE years"):
        folder = RAW_EXIOBASE / f"IOT_{year}_{variant}"
        
        if not folder.exists():
            logger.warning(f"Folder not found: {folder}")
            continue
        
        try:
            # Read F matrix (emissions by industry)
            F = read_exiobase_matrix(folder, 'F')
            emissions = extract_co2_emissions_by_sector(F, year)
            all_emissions.append(emissions)
            
            # Read output vector (total output by sector)
            try:
                x = read_exiobase_matrix(folder, 'x')
                # x is typically a column vector, convert to usable format
                output_records = []
                for idx, val in x.iloc[:, 0].items():
                    if isinstance(idx, tuple):
                        country, sector = idx[0], idx[1]
                    else:
                        parts = str(idx).split('_', 1)
                        country = parts[0] if len(parts) > 1 else 'XX'
                        sector = parts[1] if len(parts) > 1 else str(idx)
                    
                    output_records.append({
                        'year': year,
                        'country': country,
                        'exiobase_sector': sector,
                        'output_meur': float(val)
                    })
                all_outputs.append(pd.DataFrame(output_records))
            except Exception as e:
                logger.warning(f"Could not read output vector for {year}: {e}")
                
        except Exception as e:
            logger.error(f"Error processing year {year}: {e}")
            continue
    
    # Combine all years
    if not all_emissions:
        logger.error("No emissions data extracted!")
        return pd.DataFrame()
    
    emissions_df = pd.concat(all_emissions, ignore_index=True)
    
    if all_outputs:
        outputs_df = pd.concat(all_outputs, ignore_index=True)
        emissions_df = calculate_carbon_intensity(emissions_df, outputs_df)
    
    return emissions_df


def aggregate_to_gprd_sectors(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate EXIOBASE sectors to GPRD sector classification.
    
    Returns sector-level emission factors suitable for linking to CPV codes.
    """
    if df.empty:
        return df
    
    # Ensure numeric columns
    df['co2_kg'] = pd.to_numeric(df['co2_kg'], errors='coerce')
    if 'output_meur' in df.columns:
        df['output_meur'] = pd.to_numeric(df['output_meur'], errors='coerce')
    
    # Aggregate by GPRD sector and year
    agg_dict = {'co2_kg': 'sum'}
    if 'output_meur' in df.columns:
        agg_dict['output_meur'] = 'sum'
    if 'carbon_intensity_kg_per_usd' in df.columns:
        agg_dict['carbon_intensity_kg_per_usd'] = 'mean'
    
    agg_df = df.groupby(['year', 'gprd_sector']).agg(agg_dict).reset_index()
    
    # Recalculate intensity if we have output data
    if 'output_meur' in agg_df.columns:
        agg_df['output_meur'] = agg_df['output_meur'].replace(0, np.nan)
        agg_df['carbon_intensity_kg_per_meur'] = agg_df['co2_kg'] / agg_df['output_meur']
        agg_df['carbon_intensity_kg_per_usd'] = agg_df['carbon_intensity_kg_per_meur'] / 1e6 * 1.1
    else:
        # Without output data, create a default intensity based on total CO2
        # This is a simplified approach - assumes equal distribution
        logger.warning("No output data available - using simplified carbon intensity calculation")
        total_co2 = agg_df.groupby('year')['co2_kg'].transform('sum')
        agg_df['carbon_intensity_kg_per_usd'] = agg_df['co2_kg'] / total_co2 * 0.1  # Simplified factor
    
    return agg_df


def create_cpv_carbon_lookup(sector_factors: pd.DataFrame, cpv_mapping: pd.DataFrame) -> pd.DataFrame:
    """
    Create lookup table mapping CPV codes to carbon intensity factors.
    
    Args:
        sector_factors: GPRD sector emission factors by year
        cpv_mapping: CPV to sector mapping
        
    Returns:
        DataFrame with CPV-level carbon factors
    """
    # Merge CPV mapping with sector factors
    cpv_factors = cpv_mapping.merge(
        sector_factors,
        left_on='sector',
        right_on='gprd_sector',
        how='left'
    )
    
    # Fill missing with 'OTHER' sector factors
    other_factors = sector_factors[sector_factors['gprd_sector'] == 'OTHER']
    if not other_factors.empty:
        default_intensity = other_factors['carbon_intensity_kg_per_usd'].mean()
        cpv_factors['carbon_intensity_kg_per_usd'] = cpv_factors['carbon_intensity_kg_per_usd'].fillna(default_intensity)
    
    return cpv_factors


def main():
    """Main processing function."""
    logger.info("=" * 60)
    logger.info("EXIOBASE Carbon Factor Extraction")
    logger.info("=" * 60)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Check for EXIOBASE data
    if not RAW_EXIOBASE.exists():
        logger.error(f"EXIOBASE data directory not found: {RAW_EXIOBASE}")
        logger.info("Please download EXIOBASE 3.8 data from https://zenodo.org/record/5589597")
        sys.exit(1)
    
    # Process all available years
    logger.info("\n1. Extracting CO2 emissions from EXIOBASE...")
    emissions_df = process_all_years(variant='pxp')
    
    if emissions_df.empty:
        logger.error("No emissions data extracted. Check EXIOBASE data structure.")
        sys.exit(1)
    
    logger.info(f"Extracted {len(emissions_df):,} emission records")
    
    # Save detailed emissions
    detailed_path = OUTPUT_DIR / "exiobase_emissions_detailed.parquet"
    emissions_df.to_parquet(detailed_path)
    logger.info(f"Saved detailed emissions: {detailed_path}")
    
    # Aggregate to GPRD sectors
    logger.info("\n2. Aggregating to GPRD sectors...")
    sector_factors = aggregate_to_gprd_sectors(emissions_df)
    
    sector_path = OUTPUT_DIR / "carbon_factors_by_year.parquet"
    sector_factors.to_parquet(sector_path)
    logger.info(f"Saved sector factors: {sector_path}")
    
    # Also save as CSV for inspection
    sector_factors.to_csv(OUTPUT_DIR / "carbon_factors_by_year.csv", index=False)
    
    # Load CPV mapping and create lookup
    logger.info("\n3. Creating CPV to carbon intensity lookup...")
    cpv_mapping_path = DATA_DIR / "reference" / "cpv_sectors.csv"
    if cpv_mapping_path.exists():
        cpv_mapping = pd.read_csv(cpv_mapping_path)
        cpv_factors = create_cpv_carbon_lookup(sector_factors, cpv_mapping)
        
        cpv_path = OUTPUT_DIR / "cpv_carbon_factors.parquet"
        cpv_factors.to_parquet(cpv_path)
        cpv_factors.to_csv(OUTPUT_DIR / "cpv_carbon_factors.csv", index=False)
        logger.info(f"Saved CPV carbon factors: {cpv_path}")
    else:
        logger.warning(f"CPV mapping not found: {cpv_mapping_path}")
    
    # Generate summary statistics
    logger.info("\n4. Generating summary statistics...")
    summary = {
        'years_processed': sorted(emissions_df['year'].unique().tolist()),
        'n_exiobase_sectors': emissions_df['exiobase_sector'].nunique(),
        'n_gprd_sectors': sector_factors['gprd_sector'].nunique(),
        'total_co2_kg': float(emissions_df['co2_kg'].sum()),
        'mean_carbon_intensity': float(sector_factors['carbon_intensity_kg_per_usd'].mean()),
    }
    
    with open(OUTPUT_DIR / "exiobase_processing_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Years processed: {summary['years_processed']}")
    logger.info(f"EXIOBASE sectors: {summary['n_exiobase_sectors']}")
    logger.info(f"GPRD sectors: {summary['n_gprd_sectors']}")
    
    # Print sector-level summary for latest year
    latest_year = max(summary['years_processed'])
    latest_factors = sector_factors[sector_factors['year'] == latest_year]
    
    logger.info(f"\nCarbon intensity factors for {latest_year}:")
    logger.info("-" * 50)
    for _, row in latest_factors.sort_values('carbon_intensity_kg_per_usd', ascending=False).iterrows():
        logger.info(f"  {row['gprd_sector']:<15}: {row['carbon_intensity_kg_per_usd']:.4f} kg CO2/USD")
    
    logger.info("\n" + "=" * 60)
    logger.info("EXIOBASE processing complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
