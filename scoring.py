"""
Scoring Module
==============

Implements the composite scoring system for ranking student accommodations.
Combines multiple urban mobility and affordability metrics into a single
suitability score.

Urban Technology Relevance:
- Multi-criteria decision analysis (MCDA) is fundamental to urban planning
- Weighted scoring systems enable balanced evaluation of competing factors
- Accessibility metrics influence housing market dynamics and urban equity
- Demonstrates how transport infrastructure shapes residential desirability
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from typing import Dict, Optional


def calculate_student_suitability_score(
    df: pd.DataFrame,
    rent_weight: float = 0.35,
    commute_weight: float = 0.40,
    walking_weight: float = 0.15,
    transfers_weight: float = 0.10
) -> pd.DataFrame:
    """
    Calculate composite Student Suitability Score for each apartment.
    
    The score combines:
    - Affordability (lower rent = higher score)
    - Commute time (shorter commute = higher score)
    - Walking distance (shorter walk = higher score)
    - Number of transfers (fewer transfers = higher score)
    
    Parameters:
    -----------
    df : pd.DataFrame
        Dataframe with apartment data including:
        - rent
        - total_commute_minutes
        - walking_time_minutes or nearest_stop_distance_m
        - transfers
    rent_weight : float
        Weight for affordability component (default: 0.35)
    commute_weight : float
        Weight for commute time component (default: 0.40)
    walking_weight : float
        Weight for walking distance component (default: 0.15)
    transfers_weight : float
        Weight for transfers component (default: 0.10)
    
    Returns:
    --------
    pd.DataFrame
        Dataframe with added 'suitability_score' column (0-100 scale)
    """
    df = df.copy()
    
    # Validate required columns
    required_cols = ['rent']
    if 'total_commute_minutes' not in df.columns:
        required_cols.append('total_commute_minutes')
    
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Normalize weights to sum to 1.0
    total_weight = rent_weight + commute_weight + walking_weight + transfers_weight
    rent_weight /= total_weight
    commute_weight /= total_weight
    walking_weight /= total_weight
    transfers_weight /= total_weight
    
    # Initialize scores
    df['affordability_score'] = 0.0
    df['commute_score'] = 0.0
    df['walking_score'] = 0.0
    df['transfers_score'] = 0.0
    df['suitability_score'] = 0.0
    
    # Filter rows with at least rent data (minimum requirement)
    valid_mask = df['rent'].notna() & (df['rent'] > 0)
    
    valid_df = df[valid_mask].copy()
    
    if len(valid_df) == 0:
        print("Warning: No apartments with rent data for scoring")
        return df
    
    # 1. Affordability Score (lower rent = higher score)
    if valid_df['rent'].max() > valid_df['rent'].min():
        rent_scaler = MinMaxScaler(feature_range=(0, 1))
        valid_df['affordability_score'] = 1 - rent_scaler.fit_transform(
            valid_df[['rent']]
        ).flatten()  # Invert: lower rent = higher score
    else:
        valid_df['affordability_score'] = 1.0
    
    # 2. Commute Score (shorter commute = higher score)
    if 'total_commute_minutes' in valid_df.columns and valid_df['total_commute_minutes'].notna().any():
        commute_data = valid_df[valid_df['total_commute_minutes'].notna() & (valid_df['total_commute_minutes'] > 0)]
        if len(commute_data) > 0:
            max_commute = commute_data['total_commute_minutes'].max()
            min_commute = commute_data['total_commute_minutes'].min()
            if max_commute > min_commute:
                commute_scaler = MinMaxScaler(feature_range=(0, 1))
                commute_scores = 1 - commute_scaler.fit_transform(
                    commute_data[['total_commute_minutes']]
                ).flatten()
                valid_df.loc[commute_data.index, 'commute_score'] = commute_scores
            else:
                valid_df.loc[commute_data.index, 'commute_score'] = 1.0
        # Set neutral score for missing commute data
        valid_df.loc[valid_df['commute_score'] == 0.0, 'commute_score'] = 0.5
    else:
        valid_df['commute_score'] = 0.5  # Neutral if missing
    
    # 3. Walking Score (shorter walk = higher score)
    if 'walking_time_minutes' in valid_df.columns and valid_df['walking_time_minutes'].notna().any():
        walking_col = 'walking_time_minutes'
    elif 'nearest_stop_distance_m' in valid_df.columns and valid_df['nearest_stop_distance_m'].notna().any():
        # Convert distance to time estimate (5 km/h = 83.33 m/min)
        valid_df['walking_time_est'] = valid_df['nearest_stop_distance_m'] / 83.33
        walking_col = 'walking_time_est'
    else:
        walking_col = None
    
    if walking_col:
        walking_data = valid_df[valid_df[walking_col].notna() & (valid_df[walking_col] > 0)]
        if len(walking_data) > 0:
            max_walk = walking_data[walking_col].max()
            min_walk = walking_data[walking_col].min()
            if max_walk > min_walk:
                walk_scaler = MinMaxScaler(feature_range=(0, 1))
                walk_scores = 1 - walk_scaler.fit_transform(
                    walking_data[[walking_col]]
                ).flatten()
                valid_df.loc[walking_data.index, 'walking_score'] = walk_scores
            else:
                valid_df.loc[walking_data.index, 'walking_score'] = 1.0
        # Set neutral score for missing walking data
        valid_df.loc[valid_df['walking_score'] == 0.0, 'walking_score'] = 0.5
    else:
        valid_df['walking_score'] = 0.5  # Neutral if missing
    
    # 4. Transfers Score (fewer transfers = higher score)
    if 'transfers' in valid_df.columns and valid_df['transfers'].notna().any():
        transfers_data = valid_df[valid_df['transfers'].notna()]
        if len(transfers_data) > 0:
            max_transfers = transfers_data['transfers'].max()
            min_transfers = transfers_data['transfers'].min()
            if max_transfers > min_transfers:
                transfers_scaler = MinMaxScaler(feature_range=(0, 1))
                transfer_scores = 1 - transfers_scaler.fit_transform(
                    transfers_data[['transfers']]
                ).flatten()
                valid_df.loc[transfers_data.index, 'transfers_score'] = transfer_scores
            else:
                valid_df.loc[transfers_data.index, 'transfers_score'] = 1.0
        # Set neutral score for missing transfers data
        valid_df.loc[valid_df['transfers_score'] == 0.0, 'transfers_score'] = 0.5
    else:
        valid_df['transfers_score'] = 0.5  # Neutral if missing
    
    # Calculate weighted composite score (0-100 scale) for all valid rows
    valid_df['suitability_score'] = (
        valid_df['affordability_score'] * rent_weight +
        valid_df['commute_score'] * commute_weight +
        valid_df['walking_score'] * walking_weight +
        valid_df['transfers_score'] * transfers_weight
    ) * 100
    
    # Update original dataframe with scores
    for idx in valid_df.index:
        df.at[idx, 'affordability_score'] = valid_df.at[idx, 'affordability_score']
        df.at[idx, 'commute_score'] = valid_df.at[idx, 'commute_score']
        df.at[idx, 'walking_score'] = valid_df.at[idx, 'walking_score']
        df.at[idx, 'transfers_score'] = valid_df.at[idx, 'transfers_score']
        df.at[idx, 'suitability_score'] = valid_df.at[idx, 'suitability_score']
    
    return df


def rank_apartments(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """
    Rank apartments by suitability score.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Dataframe with 'suitability_score' column
    top_n : int
        Number of top apartments to return
    
    Returns:
    --------
    pd.DataFrame
        Top N apartments sorted by suitability score
    """
    if 'suitability_score' not in df.columns:
        raise ValueError("Dataframe must have 'suitability_score' column")
    
    # Sort by suitability score (descending)
    ranked = df.nlargest(top_n, 'suitability_score').copy()
    ranked['rank'] = range(1, len(ranked) + 1)
    
    return ranked


def compare_providers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare accommodation providers by average metrics.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Dataframe with 'provider' column and various metrics
    
    Returns:
    --------
    pd.DataFrame
        Aggregated statistics per provider
    """
    if 'provider' not in df.columns:
        raise ValueError("Dataframe must have 'provider' column")
    
    agg_dict = {
        'rent': 'mean',
        'suitability_score': 'mean'
    }
    
    if 'total_commute_minutes' in df.columns:
        agg_dict['total_commute_minutes'] = 'mean'
    
    if 'transfers' in df.columns:
        agg_dict['transfers'] = 'mean'
    
    if 'walking_time_minutes' in df.columns:
        agg_dict['walking_time_minutes'] = 'mean'
    
    # Count apartments per provider
    agg_dict['apartment_id'] = 'count'
    
    provider_stats = df.groupby('provider').agg(agg_dict).reset_index()
    provider_stats = provider_stats.rename(columns={'apartment_id': 'num_apartments'})
    provider_stats = provider_stats.sort_values('suitability_score', ascending=False)
    
    return provider_stats

