#!/usr/bin/env python3
"""
Master Pipeline Script - Full Analysis Runner

Orchestrates the complete data processing and analysis pipeline:
1. Parse EXIOBASE carbon emission factors
2. Parse EU TED procurement data
3. Parse OCDS (Colombia, UK) procurement data
4. Harmonize all data to GPRD schema
5. Link carbon intensity factors
6. Run causal analysis (RDD, DiD, mediation)
7. Validate manuscript claims
8. Generate publication figures

Run order:
1. parse_exiobase.py → Data/processed/exiobase/
2. parse_eu_ted.py → Data/processed/eu_ted/
3. parse_ocds_jsonl.py → Data/processed/ocds/
4. harmonize_data.py → Data/processed/gprd_master.parquet
5. link_carbon_intensity.py → Data/processed/gprd_with_carbon.parquet
6. run_causal_analysis.py → results/causal_analysis_results.json
7. validate_manuscript.py → results/manuscript_validation.json
8. generate_figures.py → figures/*.pdf

Usage:
    python run_full_pipeline.py [--step STEP] [--from STEP] [--to STEP]
    
    Examples:
    python run_full_pipeline.py                   # Run all steps
    python run_full_pipeline.py --step 5         # Run only step 5
    python run_full_pipeline.py --from 3 --to 6  # Run steps 3-6

Author: Abduxoliq Ashuraliyev
License: MIT
"""

import os
import sys
import subprocess
import argparse
import logging
from pathlib import Path
from datetime import datetime
import json
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base paths
# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
BASE_DIR = _d
SCRIPTS_DIR = BASE_DIR / "scripts"
DATA_DIR = BASE_DIR / "Data"
RESULTS_DIR = BASE_DIR / "results"
FIGURES_DIR = BASE_DIR / "figures"

# Pipeline steps
PIPELINE_STEPS = [
    {
        'step': 1,
        'name': 'Parse EXIOBASE',
        'script': 'parse_exiobase.py',
        'output': DATA_DIR / 'processed' / 'exiobase',
        'description': 'Parse EXIOBASE 3.8 carbon emission factors',
        'estimated_time_min': 30,
    },
    {
        'step': 2,
        'name': 'Parse EU TED',
        'script': 'parse_eu_ted.py',
        'output': DATA_DIR / 'processed' / 'eu_ted',
        'description': 'Parse EU TED CSV procurement data',
        'estimated_time_min': 60,
    },
    {
        'step': 3,
        'name': 'Parse OCDS',
        'script': 'parse_ocds_jsonl.py',
        'output': DATA_DIR / 'processed' / 'ocds',
        'description': 'Parse OCDS JSONL data (Colombia, UK)',
        'estimated_time_min': 45,
    },
    {
        'step': 4,
        'name': 'Harmonize Data',
        'script': 'harmonize_data.py',
        'output': DATA_DIR / 'processed' / 'gprd_master.parquet',
        'description': 'Harmonize all sources to GPRD schema',
        'estimated_time_min': 20,
    },
    {
        'step': 5,
        'name': 'Link Carbon',
        'script': 'link_carbon_intensity.py',
        'output': DATA_DIR / 'processed' / 'gprd_with_carbon.parquet',
        'description': 'Link carbon intensity factors to contracts',
        'estimated_time_min': 15,
    },
    {
        'step': 6,
        'name': 'Causal Analysis',
        'script': 'run_causal_analysis.py',
        'output': RESULTS_DIR / 'causal_analysis_results.json',
        'description': 'Run RDD, DiD, and mediation analysis',
        'estimated_time_min': 30,
    },
    {
        'step': 7,
        'name': 'Validate Claims',
        'script': 'validate_manuscript.py',
        'output': RESULTS_DIR / 'manuscript_validation.json',
        'description': 'Validate manuscript claims against data',
        'estimated_time_min': 5,
    },
    {
        'step': 8,
        'name': 'Generate Figures',
        'script': 'generate_figures.py',
        'output': FIGURES_DIR / 'figure1_rdd.pdf',
        'description': 'Generate publication figures',
        'estimated_time_min': 10,
    },
]


def check_dependencies():
    """Check if required Python packages are installed."""
    required = ['pandas', 'numpy', 'scipy', 'statsmodels', 'tqdm', 'matplotlib', 'pyarrow']
    missing = []
    
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        logger.warning(f"Missing packages: {missing}")
        logger.info("Install with: pip install " + " ".join(missing))
        return False
    
    return True


def check_data_exists():
    """Check if raw data directories exist."""
    required_data = [
        DATA_DIR / 'raw' / 'exiobase',
        DATA_DIR / 'raw' / 'ocds',
    ]
    
    missing = []
    for path in required_data:
        if not path.exists():
            missing.append(path)
    
    if missing:
        logger.warning(f"Missing data directories:")
        for p in missing:
            logger.warning(f"  - {p}")
        return False
    
    return True


def run_step(step_info: dict) -> dict:
    """
    Run a single pipeline step.
    
    Args:
        step_info: Dictionary with step configuration
        
    Returns:
        Dictionary with execution results
    """
    step_num = step_info['step']
    script_name = step_info['script']
    script_path = SCRIPTS_DIR / script_name
    
    result = {
        'step': step_num,
        'name': step_info['name'],
        'script': script_name,
        'success': False,
        'error': None,
        'duration_sec': 0,
    }
    
    if not script_path.exists():
        result['error'] = f"Script not found: {script_path}"
        return result
    
    logger.info("=" * 60)
    logger.info(f"Step {step_num}: {step_info['name']}")
    logger.info(f"Script: {script_name}")
    logger.info(f"Description: {step_info['description']}")
    logger.info(f"Estimated time: ~{step_info['estimated_time_min']} minutes")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    try:
        # Get Python executable - use the configured venv
        python_exe = r"C:\Users\Jack0\GitHub\.venv\Scripts\python.exe" if os.path.exists(r"C:\Users\Jack0\GitHub\.venv\Scripts\python.exe") else sys.executable
        
        # Run the script
        process = subprocess.run(
            [python_exe, str(script_path)],
            cwd=str(BASE_DIR),  # Run from project root for proper relative paths
            capture_output=True,
            text=True,
            timeout=step_info['estimated_time_min'] * 60 * 3  # 3x timeout
        )
        
        duration = time.time() - start_time
        result['duration_sec'] = duration
        
        if process.returncode == 0:
            result['success'] = True
            logger.info(f"✓ Completed in {duration/60:.1f} minutes")
            
            # Log last lines of output
            if process.stdout:
                lines = process.stdout.strip().split('\n')
                if len(lines) > 5:
                    logger.info(f"Last 5 lines of output:")
                    for line in lines[-5:]:
                        logger.info(f"  {line}")
        else:
            result['error'] = process.stderr if process.stderr else process.stdout
            logger.error(f"✗ Failed after {duration/60:.1f} minutes")
            logger.error(f"Return code: {process.returncode}")
            
            # Show both stdout and stderr for debugging
            if process.stdout:
                lines = process.stdout.strip().split('\n')
                logger.error(f"Last 20 lines of output:")
                for line in lines[-20:]:
                    logger.error(f"  {line}")
            
            if process.stderr:
                lines = process.stderr.strip().split('\n')
                logger.error(f"Error output:")
                for line in lines[:30]:  # First 30 lines of error
                    logger.error(f"  {line}")
                
    except subprocess.TimeoutExpired:
        result['error'] = "Timeout exceeded"
        logger.error("✗ Step timed out")
        
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"✗ Exception: {e}")
    
    return result


def run_pipeline(steps_to_run: list) -> dict:
    """
    Run the specified pipeline steps.
    
    Args:
        steps_to_run: List of step numbers to run
        
    Returns:
        Dictionary with pipeline results
    """
    pipeline_result = {
        'start_time': datetime.now().isoformat(),
        'steps_requested': steps_to_run,
        'steps_completed': [],
        'steps_failed': [],
        'total_duration_sec': 0,
    }
    
    total_start = time.time()
    
    for step_info in PIPELINE_STEPS:
        if step_info['step'] not in steps_to_run:
            continue
        
        result = run_step(step_info)
        
        if result['success']:
            pipeline_result['steps_completed'].append(result)
        else:
            pipeline_result['steps_failed'].append(result)
            logger.warning(f"Step {result['step']} failed. Continuing with next step...")
    
    pipeline_result['total_duration_sec'] = time.time() - total_start
    pipeline_result['end_time'] = datetime.now().isoformat()
    
    return pipeline_result


def print_summary(results: dict):
    """Print pipeline execution summary."""
    logger.info("\n" + "=" * 70)
    logger.info("PIPELINE EXECUTION SUMMARY")
    logger.info("=" * 70)
    
    logger.info(f"\nStart: {results['start_time']}")
    logger.info(f"End: {results['end_time']}")
    logger.info(f"Total duration: {results['total_duration_sec']/60:.1f} minutes")
    
    logger.info(f"\nSteps requested: {len(results['steps_requested'])}")
    logger.info(f"Steps completed: {len(results['steps_completed'])}")
    logger.info(f"Steps failed: {len(results['steps_failed'])}")
    
    if results['steps_completed']:
        logger.info("\n✓ Completed steps:")
        for step in results['steps_completed']:
            logger.info(f"  {step['step']}. {step['name']} ({step['duration_sec']/60:.1f} min)")
    
    if results['steps_failed']:
        logger.info("\n✗ Failed steps:")
        for step in results['steps_failed']:
            logger.info(f"  {step['step']}. {step['name']}")
            logger.info(f"     Error: {step['error'][:100]}...")
    
    logger.info("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Run the full procurement analysis pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_full_pipeline.py                   # Run all steps
  python run_full_pipeline.py --step 5         # Run only step 5
  python run_full_pipeline.py --from 3 --to 6  # Run steps 3-6
  python run_full_pipeline.py --list           # List all steps
        """
    )
    
    parser.add_argument('--step', type=int, help='Run only this step')
    parser.add_argument('--from', dest='from_step', type=int, default=1, 
                       help='Start from this step (default: 1)')
    parser.add_argument('--to', dest='to_step', type=int, default=8,
                       help='End at this step (default: 8)')
    parser.add_argument('--list', action='store_true', help='List all pipeline steps')
    parser.add_argument('--check', action='store_true', help='Check dependencies only')
    
    args = parser.parse_args()
    
    # List steps
    if args.list:
        print("\nPipeline Steps:")
        print("-" * 60)
        for step in PIPELINE_STEPS:
            print(f"  {step['step']}. {step['name']}")
            print(f"     Script: {step['script']}")
            print(f"     Description: {step['description']}")
            print(f"     Estimated time: ~{step['estimated_time_min']} min")
            print()
        return
    
    # Check dependencies
    logger.info("Checking dependencies...")
    if not check_dependencies():
        logger.error("Please install missing packages before running.")
        sys.exit(1)
    
    if args.check:
        logger.info("Dependencies OK!")
        check_data_exists()
        return
    
    # Check data exists
    if not check_data_exists():
        logger.warning("Some raw data is missing. Pipeline may fail.")
    
    # Determine steps to run
    if args.step:
        steps_to_run = [args.step]
    else:
        steps_to_run = list(range(args.from_step, args.to_step + 1))
    
    logger.info(f"\nWill run steps: {steps_to_run}")
    
    # Create output directories
    (DATA_DIR / 'processed').mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Run pipeline
    results = run_pipeline(steps_to_run)
    
    # Print summary
    print_summary(results)
    
    # Save execution log
    log_path = RESULTS_DIR / f"pipeline_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"\nExecution log saved: {log_path}")
    
    # Exit code
    if results['steps_failed']:
        sys.exit(1)


if __name__ == "__main__":
    main()
