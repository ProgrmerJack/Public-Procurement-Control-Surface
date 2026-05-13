#!/usr/bin/env python3
"""
generate_tables.py - Create publication-quality LaTeX tables.

This script generates all tables for the manuscript:
- Summary statistics
- Main regression results
- Robustness check results
- Mechanism decomposition

Usage:
    python -m scripts.generate_tables summary-stats --input data.parquet --output table.tex
    python -m scripts.generate_tables main-results --rdd-pooled rdd.csv --output table.tex
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd


def stars(pvalue: float) -> str:
    """Convert p-value to significance stars."""
    if pvalue < 0.01:
        return "***"
    elif pvalue < 0.05:
        return "**"
    elif pvalue < 0.10:
        return "*"
    return ""


def format_number(x: float, decimals: int = 3, thousands: bool = True) -> str:
    """Format number for publication."""
    if pd.isna(x):
        return ""
    if thousands and abs(x) >= 1000:
        return f"{x:,.{decimals}f}"
    return f"{x:.{decimals}f}"


def format_coefficient(estimate: float, se: float, pvalue: float, 
                       decimals: int = 3) -> str:
    """Format coefficient with SE in parentheses and stars."""
    star_str = stars(pvalue)
    return f"{estimate:.{decimals}f}{star_str}\n({se:.{decimals}f})"


class LaTeXTableGenerator:
    """Generate publication-quality LaTeX tables."""
    
    def __init__(self, decimal_places: int = 3):
        self.decimals = decimal_places
    
    def summary_statistics(
        self, 
        data: pd.DataFrame,
        variables: List[str],
        labels: Optional[Dict[str, str]] = None,
        by_group: Optional[str] = None
    ) -> str:
        """
        Generate summary statistics table.
        
        Parameters
        ----------
        data : pd.DataFrame
            Input data
        variables : list
            Variables to summarize
        labels : dict, optional
            Variable labels for display
        by_group : str, optional
            Column for group comparison
            
        Returns
        -------
        str
            LaTeX table code
        """
        labels = labels or {}
        
        # Header
        if by_group:
            groups = data[by_group].unique()
            n_cols = 1 + 5 * len(groups)  # Variable + (N, Mean, SD, Min, Max) * groups
            header = f"\\begin{{tabular}}{{l{'c' * (n_cols - 1)}}}\n"
            header += "\\toprule\n"
            header += " & " + " & ".join([f"\\multicolumn{{5}}{{c}}{{{g}}}" for g in groups]) + " \\\\\n"
            header += "\\cmidrule(lr){2-6} " * len(groups) + "\n"
            header += "Variable & " + " & ".join(["N & Mean & SD & Min & Max"] * len(groups)) + " \\\\\n"
            header += "\\midrule\n"
        else:
            header = "\\begin{tabular}{lccccc}\n"
            header += "\\toprule\n"
            header += "Variable & N & Mean & SD & Min & Max \\\\\n"
            header += "\\midrule\n"
        
        # Body
        body = ""
        for var in variables:
            label = labels.get(var, var)
            
            if by_group:
                row = label
                for group in groups:
                    subset = data[data[by_group] == group][var].dropna()
                    row += f" & {len(subset):,d}"
                    row += f" & {subset.mean():.{self.decimals}f}"
                    row += f" & {subset.std():.{self.decimals}f}"
                    row += f" & {subset.min():.{self.decimals}f}"
                    row += f" & {subset.max():.{self.decimals}f}"
                row += " \\\\\n"
            else:
                subset = data[var].dropna()
                row = f"{label} & {len(subset):,d}"
                row += f" & {subset.mean():.{self.decimals}f}"
                row += f" & {subset.std():.{self.decimals}f}"
                row += f" & {subset.min():.{self.decimals}f}"
                row += f" & {subset.max():.{self.decimals}f} \\\\\n"
            
            body += row
        
        # Footer
        footer = "\\bottomrule\n"
        footer += "\\end{tabular}\n"
        
        return header + body + footer
    
    def regression_results(
        self,
        results: List[Dict[str, Any]],
        outcome_labels: Optional[Dict[str, str]] = None,
        note: str = ""
    ) -> str:
        """
        Generate regression results table.
        
        Parameters
        ----------
        results : list of dict
            List of estimation results, each containing:
            - 'model': model name
            - 'estimate': point estimate
            - 'se': standard error
            - 'pvalue': p-value
            - 'n': sample size
            - Additional statistics
        outcome_labels : dict, optional
            Labels for outcome variables
        note : str
            Table note
            
        Returns
        -------
        str
            LaTeX table code
        """
        n_models = len(results)
        
        # Header
        header = f"\\begin{{tabular}}{{l{'c' * n_models}}}\n"
        header += "\\toprule\n"
        header += " & " + " & ".join([f"({i+1})" for i in range(n_models)]) + " \\\\\n"
        if outcome_labels:
            header += " & " + " & ".join([outcome_labels.get(r.get('outcome', ''), '') 
                                           for r in results]) + " \\\\\n"
        header += "\\midrule\n"
        
        # Treatment effect
        body = "Treatment Effect"
        for r in results:
            est = r['estimate']
            se = r['se']
            pval = r.get('pvalue', 1.0)
            star = stars(pval)
            body += f" & {est:.{self.decimals}f}{star}"
        body += " \\\\\n"
        
        # Standard errors
        body += " "
        for r in results:
            body += f" & ({r['se']:.{self.decimals}f})"
        body += " \\\\\n"
        
        # Blank line
        body += " \\\\\n"
        
        # Additional statistics
        stats_to_show = ['bandwidth', 'n_left', 'n_right', 'n']
        stat_labels = {
            'bandwidth': 'Bandwidth',
            'n_left': 'N (left)',
            'n_right': 'N (right)',
            'n': 'Observations'
        }
        
        for stat in stats_to_show:
            if any(stat in r for r in results):
                row = stat_labels.get(stat, stat)
                for r in results:
                    val = r.get(stat, '')
                    if isinstance(val, float):
                        row += f" & {val:.{self.decimals}f}"
                    elif isinstance(val, int):
                        row += f" & {val:,d}"
                    else:
                        row += f" & {val}"
                body += row + " \\\\\n"
        
        # Footer
        footer = "\\bottomrule\n"
        if note:
            footer += f"\\multicolumn{{{n_models + 1}}}{{l}}{{\\footnotesize {note}}} \\\\\n"
        footer += "\\end{tabular}\n"
        
        return header + body + footer
    
    def robustness_table(
        self,
        baseline: Dict[str, float],
        bandwidth_results: pd.DataFrame,
        placebo_results: pd.DataFrame,
        donut_results: pd.DataFrame
    ) -> str:
        """
        Generate robustness checks table.
        
        Parameters
        ----------
        baseline : dict
            Baseline estimate with 'estimate' and 'se'
        bandwidth_results : pd.DataFrame
            Bandwidth sensitivity results
        placebo_results : pd.DataFrame
            Placebo cutoff results  
        donut_results : pd.DataFrame
            Donut hole results
            
        Returns
        -------
        str
            LaTeX table code
        """
        header = "\\begin{tabular}{lcccc}\n"
        header += "\\toprule\n"
        header += "Specification & Estimate & SE & N & Notes \\\\\n"
        header += "\\midrule\n"
        header += "\\multicolumn{5}{l}{\\textit{Panel A: Baseline}} \\\\\n"
        
        # Baseline
        body = f"Main specification & {baseline['estimate']:.{self.decimals}f}{stars(baseline.get('pvalue', 0.01))}"
        body += f" & {baseline['se']:.{self.decimals}f}"
        body += f" & {baseline.get('n', ''):,d} & Optimal bandwidth \\\\\n"
        body += " \\\\\n"
        
        # Bandwidth sensitivity
        body += "\\multicolumn{5}{l}{\\textit{Panel B: Bandwidth Sensitivity}} \\\\\n"
        for _, row in bandwidth_results.iterrows():
            mult = row['bandwidth_mult']
            label = f"{mult:.2f}$\\times$ optimal"
            body += f"{label} & {row['estimate']:.{self.decimals}f}"
            body += f" & {row['se']:.{self.decimals}f}"
            body += f" & {int(row.get('n', 0)):,d} & \\\\\n"
        body += " \\\\\n"
        
        # Placebo cutoffs
        body += "\\multicolumn{5}{l}{\\textit{Panel C: Placebo Cutoffs}} \\\\\n"
        for _, row in placebo_results.iterrows():
            if row['cutoff'] != 0:
                label = f"Cutoff at {row['cutoff']:.1f}"
                body += f"{label} & {row['estimate']:.{self.decimals}f}"
                body += f" & {row['se']:.{self.decimals}f}"
                body += f" & {int(row.get('n', 0)):,d} & False cutoff \\\\\n"
        body += " \\\\\n"
        
        # Donut hole
        body += "\\multicolumn{5}{l}{\\textit{Panel D: Donut Hole}} \\\\\n"
        for _, row in donut_results.iterrows():
            label = f"Exclude {row['donut_size']*100:.0f}\\% around cutoff"
            body += f"{label} & {row['estimate']:.{self.decimals}f}"
            body += f" & {row['se']:.{self.decimals}f}"
            body += f" & {int(row.get('n', 0)):,d} & \\\\\n"
        
        footer = "\\bottomrule\n"
        footer += "\\multicolumn{5}{l}{\\footnotesize * p<0.10, ** p<0.05, *** p<0.01} \\\\\n"
        footer += "\\end{tabular}\n"
        
        return header + body + footer
    
    def mechanism_decomposition(
        self,
        results: pd.DataFrame,
        components: List[str] = ['restrictiveness', 'complexity', 'innovation']
    ) -> str:
        """
        Generate mechanism decomposition table.
        
        Parameters
        ----------
        results : pd.DataFrame
            Results with component effects
        components : list
            Component names
            
        Returns
        -------
        str
            LaTeX table code
        """
        header = "\\begin{tabular}{lcccc}\n"
        header += "\\toprule\n"
        header += " & Composite & " + " & ".join([c.capitalize() for c in components]) + " \\\\\n"
        header += "\\midrule\n"
        
        body = ""
        # Add rows for each country or specification
        for _, row in results.iterrows():
            label = row.get('country', row.get('specification', ''))
            body += f"{label}"
            body += f" & {row.get('composite', 0):.{self.decimals}f}"
            for comp in components:
                val = row.get(comp, 0)
                body += f" & {val:.{self.decimals}f}"
            body += " \\\\\n"
        
        footer = "\\bottomrule\n"
        footer += "\\end{tabular}\n"
        
        return header + body + footer


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Generate publication tables for GPRD analysis'
    )
    subparsers = parser.add_subparsers(dest='command', help='Table type')
    
    # Summary statistics
    sum_parser = subparsers.add_parser('summary-stats', help='Summary statistics')
    sum_parser.add_argument('--input', required=True)
    sum_parser.add_argument('--output', required=True)
    sum_parser.add_argument('--format', default='latex')
    sum_parser.add_argument('--decimal-places', type=int, default=3)
    
    # Main results
    main_parser = subparsers.add_parser('main-results', help='Main regression results')
    main_parser.add_argument('--rdd-pooled', required=True)
    main_parser.add_argument('--did-pooled', required=True)
    main_parser.add_argument('--rdd-countries', nargs='+')
    main_parser.add_argument('--output', required=True)
    main_parser.add_argument('--format', default='latex')
    main_parser.add_argument('--decimal-places', type=int, default=3)
    
    # Robustness
    rob_parser = subparsers.add_parser('robustness', help='Robustness checks')
    rob_parser.add_argument('--bandwidth', required=True)
    rob_parser.add_argument('--placebo', required=True)
    rob_parser.add_argument('--donut', required=True)
    rob_parser.add_argument('--output', required=True)
    rob_parser.add_argument('--format', default='latex')
    rob_parser.add_argument('--decimal-places', type=int, default=3)
    
    # Mechanism decomposition
    mech_parser = subparsers.add_parser('mechanism-decomp', help='Mechanism decomposition')
    mech_parser.add_argument('--inputs', nargs='+', required=True)
    mech_parser.add_argument('--output', required=True)
    mech_parser.add_argument('--format', default='latex')
    mech_parser.add_argument('--decimal-places', type=int, default=3)
    
    args = parser.parse_args()
    
    generator = LaTeXTableGenerator(decimal_places=args.decimal_places if hasattr(args, 'decimal_places') else 3)
    
    if args.command == 'summary-stats':
        data = pd.read_parquet(args.input)
        variables = ['value_eur', 'n_bidders', 'price_ratio', 'mechanism_index',
                     'restrictiveness', 'complexity', 'innovation_score']
        labels = {
            'value_eur': 'Contract Value (EUR)',
            'n_bidders': 'Number of Bidders',
            'price_ratio': 'Price/Estimate Ratio',
            'mechanism_index': 'Mechanism Index',
            'restrictiveness': 'Restrictiveness',
            'complexity': 'Complexity',
            'innovation_score': 'Innovation Score'
        }
        table = generator.summary_statistics(data, variables, labels, by_group='country')
        
        with open(args.output, 'w') as f:
            f.write(table)
        print(f"Saved: {args.output}")
        
    elif args.command == 'main-results':
        rdd = pd.read_csv(args.rdd_pooled).iloc[0].to_dict()
        did = pd.read_csv(args.did_pooled).iloc[0].to_dict()
        
        results = [
            {'model': 'RDD Pooled', **rdd},
            {'model': 'DiD Pooled', **did}
        ]
        
        if args.rdd_countries:
            for f in args.rdd_countries:
                country_results = pd.read_csv(f).iloc[0].to_dict()
                results.append(country_results)
        
        table = generator.regression_results(
            results,
            note="* p<0.10, ** p<0.05, *** p<0.01. Standard errors clustered by buyer."
        )
        
        with open(args.output, 'w') as f:
            f.write(table)
        print(f"Saved: {args.output}")
        
    elif args.command == 'robustness':
        bandwidth = pd.read_csv(args.bandwidth)
        placebo = pd.read_csv(args.placebo)
        donut = pd.read_csv(args.donut)
        
        baseline = bandwidth[bandwidth['bandwidth_mult'] == 1].iloc[0].to_dict()
        
        table = generator.robustness_table(baseline, bandwidth, placebo, donut)
        
        with open(args.output, 'w') as f:
            f.write(table)
        print(f"Saved: {args.output}")
        
    elif args.command == 'mechanism-decomp':
        dfs = [pd.read_csv(f) for f in args.inputs]
        data = pd.concat(dfs, ignore_index=True)
        
        table = generator.mechanism_decomposition(data)
        
        with open(args.output, 'w') as f:
            f.write(table)
        print(f"Saved: {args.output}")
        
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
