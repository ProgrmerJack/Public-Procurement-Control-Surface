#!/usr/bin/env python3
"""
Mechanism Index Module for GPRD

NLP-based analysis of contract text to derive:
- Specification restrictiveness (exclusionary language)
- Complexity (technical jargon, specification length)
- Innovation content (R&D, advanced technology mentions)

Author: Abduxoliq Ashuraliyev
License: MIT
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
import textstat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"

# Keyword dictionaries for classification
RESTRICTIVE_KEYWORDS = [
    # Brand-specific language
    r'\bonly\s+\w+\s+brand\b',
    r'\bmust\s+be\s+\w+\s+certified\b',
    r'\bexclusively\b',
    r'\bsole\s+source\b',
    r'\bproprietary\b',
    r'\bpatented\b',
    r'\bspecific\s+manufacturer\b',
    r'\bno\s+alternative[s]?\b',
    r'\bno\s+substitute[s]?\b',
    r'\bexact\s+match\b',
    r'\bidentical\s+to\b',
    # Exclusionary criteria
    r'\bminimum\s+\d+\s+years?\s+experience\b',
    r'\brequired\s+certification[s]?\b',
    r'\bmust\s+have\s+previous\b',
    r'\bprior\s+contract[s]?\s+with\b',
    r'\blocal\s+presence\s+required\b',
    r'\bdomestic\s+only\b',
]

INNOVATION_KEYWORDS = [
    # R&D terms
    r'\bresearch\s+and\s+development\b',
    r'\br&d\b',
    r'\binnovation\b',
    r'\bnovel\b',
    r'\bcutting[- ]edge\b',
    r'\bstate[- ]of[- ]the[- ]art\b',
    r'\badvanced\s+technology\b',
    r'\bemerging\s+technology\b',
    # Specific technologies
    r'\bartificial\s+intelligence\b',
    r'\bmachine\s+learning\b',
    r'\bdeep\s+learning\b',
    r'\bneural\s+network\b',
    r'\bblockchain\b',
    r'\bquantum\b',
    r'\biot\b',
    r'\b5g\b',
    r'\bcloud\s+computing\b',
    r'\bbig\s+data\b',
    r'\bautomation\b',
    r'\brobotics\b',
    r'\bdrone[s]?\b',
    r'\bsmart\s+\w+\b',
    # Energy/Green tech
    r'\brenewable\s+energy\b',
    r'\bsolar\b',
    r'\bwind\s+power\b',
    r'\belectric\s+vehicle\b',
    r'\bbattery\s+storage\b',
    r'\bgreen\s+technology\b',
    r'\bsustainable\b',
    r'\bcarbon\s+neutral\b',
    r'\bzero\s+emission\b',
    # Medical/Health tech
    r'\bmedical\s+device\b',
    r'\bdiagnostic\b',
    r'\btherapeutic\b',
    r'\bbiopharmaceutical\b',
    r'\bgenomics\b',
    r'\btelemedicine\b',
    r'\bprecision\s+medicine\b',
]

TECHNICAL_TERMS = [
    # Engineering
    r'\bspecification[s]?\b',
    r'\btolerance[s]?\b',
    r'\bcalibration\b',
    r'\bcompliance\b',
    r'\bstandard[s]?\b',
    r'\biso\s+\d+\b',
    r'\bdin\s+\d+\b',
    r'\bastm\b',
    r'\bieee\b',
    # IT
    r'\bapi\b',
    r'\bsdk\b',
    r'\bframework\b',
    r'\binteroperability\b',
    r'\bscalability\b',
    r'\blatency\b',
    r'\bbandwidth\b',
    r'\bencryption\b',
    r'\bauthentication\b',
    # Construction
    r'\bload[- ]bearing\b',
    r'\bstructural\b',
    r'\btensile\s+strength\b',
    r'\bcompressive\s+strength\b',
    r'\bfire\s+rating\b',
    r'\bseismic\b',
]


def calculate_restrictiveness(text: str) -> Tuple[float, int]:
    """
    Calculate specification restrictiveness score.
    
    Returns:
        Tuple of (score 0-1, count of restrictive patterns)
    """
    if not text or not isinstance(text, str):
        return 0.0, 0
    
    text_lower = text.lower()
    matches = 0
    
    for pattern in RESTRICTIVE_KEYWORDS:
        if re.search(pattern, text_lower):
            matches += 1
    
    # Normalize by text length (per 1000 words)
    word_count = len(text_lower.split())
    if word_count > 0:
        score = min(1.0, matches / (word_count / 1000))
    else:
        score = 0.0
    
    return score, matches


def calculate_innovation_score(text: str) -> Tuple[float, int]:
    """
    Calculate innovation content score.
    
    Returns:
        Tuple of (score 0-1, count of innovation keywords)
    """
    if not text or not isinstance(text, str):
        return 0.0, 0
    
    text_lower = text.lower()
    matches = 0
    
    for pattern in INNOVATION_KEYWORDS:
        if re.search(pattern, text_lower):
            matches += 1
    
    # Normalize by text length
    word_count = len(text_lower.split())
    if word_count > 0:
        score = min(1.0, matches / (word_count / 500))
    else:
        score = 0.0
    
    return score, matches


def calculate_complexity(text: str) -> Dict[str, float]:
    """
    Calculate text complexity metrics.
    
    Returns:
        Dictionary with complexity indicators
    """
    if not text or not isinstance(text, str) or len(text.strip()) < 10:
        return {
            "flesch_reading_ease": 0.0,
            "flesch_kincaid_grade": 0.0,
            "gunning_fog": 0.0,
            "complexity_score": 0.0,
            "word_count": 0,
            "sentence_count": 0,
            "avg_word_length": 0.0
        }
    
    # Basic stats
    words = text.split()
    word_count = len(words)
    sentence_count = max(1, text.count('.') + text.count('!') + text.count('?'))
    avg_word_length = np.mean([len(w) for w in words]) if words else 0
    
    # Readability metrics (using textstat)
    try:
        flesch_ease = textstat.flesch_reading_ease(text)
        flesch_kincaid = textstat.flesch_kincaid_grade(text)
        gunning_fog = textstat.gunning_fog(text)
    except Exception:
        flesch_ease = 50.0
        flesch_kincaid = 10.0
        gunning_fog = 10.0
    
    # Normalize to 0-1 complexity score (inverted Flesch ease)
    # Flesch ease: 0-30 = very difficult, 90-100 = very easy
    complexity_score = max(0, min(1, (100 - flesch_ease) / 100))
    
    # Count technical terms
    text_lower = text.lower()
    technical_count = sum(1 for p in TECHNICAL_TERMS if re.search(p, text_lower))
    technical_ratio = technical_count / (word_count / 100) if word_count > 0 else 0
    
    # Adjust complexity for technical density
    complexity_score = min(1.0, complexity_score + technical_ratio * 0.1)
    
    return {
        "flesch_reading_ease": flesch_ease,
        "flesch_kincaid_grade": flesch_kincaid,
        "gunning_fog": gunning_fog,
        "complexity_score": complexity_score,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_word_length": avg_word_length,
        "technical_terms_ratio": technical_ratio
    }


def count_brand_mentions(text: str) -> int:
    """Count brand/trademark mentions in text."""
    if not text or not isinstance(text, str):
        return 0
    
    # Pattern for likely brand names (capitalized words with ® ™ or following "brand")
    brand_patterns = [
        r'\b[A-Z][a-zA-Z]+®\b',
        r'\b[A-Z][a-zA-Z]+™\b',
        r'\bbrand\s+([A-Z][a-zA-Z]+)\b',
        r'\bmanufacturer[:\s]+([A-Z][a-zA-Z]+)\b',
    ]
    
    count = 0
    for pattern in brand_patterns:
        count += len(re.findall(pattern, text))
    
    return count


def check_exclusionary_language(text: str) -> bool:
    """Check if text contains exclusionary language."""
    if not text or not isinstance(text, str):
        return False
    
    exclusionary_patterns = [
        r'\bonly\s+(domestic|local|national)\b',
        r'\bexclude[ds]?\b',
        r'\bnot\s+accept(able|ed)?\b',
        r'\bwill\s+not\s+consider\b',
        r'\bineligible\b',
        r'\bdisqualif(y|ied|ication)\b',
    ]
    
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in exclusionary_patterns)


def compute_mechanism_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute mechanism indices for all records.
    
    Args:
        df: DataFrame with tender_title and tender_description columns
        
    Returns:
        DataFrame with added mechanism index columns
    """
    logger.info("Computing mechanism indices...")
    
    # Combine title and description
    df = df.copy()
    df["_combined_text"] = (
        df["tender_title"].fillna("") + " " + 
        df["tender_description"].fillna("")
    ).str.strip()
    
    # Initialize output columns
    df["text_restrictiveness"] = 0.0
    df["text_complexity"] = 0.0
    df["text_innovation"] = 0.0
    df["word_count"] = 0
    df["technical_terms_ratio"] = 0.0
    df["brand_mentions"] = 0
    df["exclusionary_language"] = False
    
    # Process each record
    for idx in df.index:
        text = df.loc[idx, "_combined_text"]
        
        # Restrictiveness
        restrict_score, _ = calculate_restrictiveness(text)
        df.loc[idx, "text_restrictiveness"] = restrict_score
        
        # Innovation
        innov_score, _ = calculate_innovation_score(text)
        df.loc[idx, "text_innovation"] = innov_score
        
        # Complexity
        complexity = calculate_complexity(text)
        df.loc[idx, "text_complexity"] = complexity["complexity_score"]
        df.loc[idx, "word_count"] = complexity["word_count"]
        df.loc[idx, "technical_terms_ratio"] = complexity.get("technical_terms_ratio", 0)
        
        # Brand mentions
        df.loc[idx, "brand_mentions"] = count_brand_mentions(text)
        
        # Exclusionary language
        df.loc[idx, "exclusionary_language"] = check_exclusionary_language(text)
    
    # Drop temporary column
    df = df.drop(columns=["_combined_text"])
    
    logger.info(f"Computed mechanism indices for {len(df)} records")
    logger.info(f"  Mean restrictiveness: {df['text_restrictiveness'].mean():.3f}")
    logger.info(f"  Mean complexity: {df['text_complexity'].mean():.3f}")
    logger.info(f"  Mean innovation: {df['text_innovation'].mean():.3f}")
    logger.info(f"  Records with exclusionary language: {df['exclusionary_language'].sum()}")
    
    return df


def train_restrictiveness_classifier(
    df: pd.DataFrame,
    text_col: str = "tender_description",
    label_col: str = "is_restrictive"
) -> Tuple[TfidfVectorizer, LogisticRegression]:
    """
    Train a classifier for restrictiveness (requires labeled data).
    
    Args:
        df: DataFrame with text and labels
        text_col: Column with text data
        label_col: Column with binary labels
        
    Returns:
        Tuple of (vectorizer, classifier)
    """
    logger.info("Training restrictiveness classifier...")
    
    # Prepare data
    df = df.dropna(subset=[text_col, label_col])
    texts = df[text_col].fillna("")
    labels = df[label_col].astype(int)
    
    # Vectorize
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        stop_words="english"
    )
    X = vectorizer.fit_transform(texts)
    
    # Train classifier
    classifier = LogisticRegression(max_iter=1000, class_weight="balanced")
    
    # Cross-validation
    scores = cross_val_score(classifier, X, labels, cv=5, scoring="roc_auc")
    logger.info(f"Cross-validation AUC: {scores.mean():.3f} (+/- {scores.std()*2:.3f})")
    
    # Fit on full data
    classifier.fit(X, labels)
    
    return vectorizer, classifier


def main():
    """Main entry point for mechanism index computation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Compute mechanism indices")
    parser.add_argument(
        "--input",
        type=Path,
        default=OUTPUT_DIR / "gprd_harmonized.parquet",
        help="Input GPRD file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR / "mechanism_index.parquet",
        help="Output file path"
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Sample size for testing"
    )
    
    args = parser.parse_args()
    
    # Load data
    logger.info(f"Loading data from {args.input}")
    df = pd.read_parquet(args.input)
    
    if args.sample and len(df) > args.sample:
        df = df.sample(args.sample)
        logger.info(f"Sampled {args.sample} records")
    
    # Compute mechanism indices
    df = compute_mechanism_index(df)
    
    # Save results
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.output, index=False)
    logger.info(f"Saved mechanism indices to {args.output}")
    
    # Also save summary statistics
    summary = df[[
        "country", "sector", "year",
        "text_restrictiveness", "text_complexity", "text_innovation",
        "word_count", "brand_mentions", "exclusionary_language"
    ]].groupby(["country", "sector", "year"]).agg({
        "text_restrictiveness": "mean",
        "text_complexity": "mean",
        "text_innovation": "mean",
        "word_count": "mean",
        "brand_mentions": "sum",
        "exclusionary_language": "sum"
    }).reset_index()
    
    summary_path = args.output.with_suffix(".summary.csv")
    summary.to_csv(summary_path, index=False)
    logger.info(f"Saved summary to {summary_path}")


if __name__ == "__main__":
    main()
