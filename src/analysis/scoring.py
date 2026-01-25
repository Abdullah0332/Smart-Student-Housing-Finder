import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from typing import Dict, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import SCORING_WEIGHTS


def calculate_student_suitability_score(
    df: pd.DataFrame,
    rent_weight: float = None,
    commute_weight: float = None,
    walking_weight: float = None,
    transfers_weight: float = None
) -> pd.DataFrame:
    rent_weight = rent_weight or SCORING_WEIGHTS['rent']
    commute_weight = commute_weight or SCORING_WEIGHTS['commute']
    walking_weight = walking_weight or SCORING_WEIGHTS['walking']
    transfers_weight = transfers_weight or SCORING_WEIGHTS['transfers']
    
    df = df.copy()
    
    if 'rent' not in df.columns:
        raise ValueError("Missing required column: rent")
    
    total_weight = rent_weight + commute_weight + walking_weight + transfers_weight
    rent_weight /= total_weight
    commute_weight /= total_weight
    walking_weight /= total_weight
    transfers_weight /= total_weight
    
    df['affordability_score'] = 0.0
    df['commute_score'] = 0.0
    df['walking_score'] = 0.0
    df['transfers_score'] = 0.0
    df['suitability_score'] = 0.0
    
    valid_mask = df['rent'].notna() & (df['rent'] > 0)
    valid_df = df[valid_mask].copy()
    
    if len(valid_df) == 0:
        print("Warning: No apartments with rent data for scoring")
        return df
    
    valid_df['affordability_score'] = _calculate_inverse_score(valid_df, 'rent')
    
    if 'total_commute_minutes' in valid_df.columns and valid_df['total_commute_minutes'].notna().any():
        valid_df['commute_score'] = _calculate_inverse_score(valid_df, 'total_commute_minutes')
    else:
        valid_df['commute_score'] = 0.5
    
    walking_col = _get_walking_column(valid_df)
    if walking_col:
        valid_df['walking_score'] = _calculate_inverse_score(valid_df, walking_col)
    else:
        valid_df['walking_score'] = 0.5
    
    if 'transfers' in valid_df.columns and valid_df['transfers'].notna().any():
        valid_df['transfers_score'] = _calculate_inverse_score(valid_df, 'transfers')
    else:
        valid_df['transfers_score'] = 0.5
    
    valid_df['suitability_score'] = (
        valid_df['affordability_score'] * rent_weight +
        valid_df['commute_score'] * commute_weight +
        valid_df['walking_score'] * walking_weight +
        valid_df['transfers_score'] * transfers_weight
    ) * 100
    
    for idx in valid_df.index:
        df.at[idx, 'affordability_score'] = valid_df.at[idx, 'affordability_score']
        df.at[idx, 'commute_score'] = valid_df.at[idx, 'commute_score']
        df.at[idx, 'walking_score'] = valid_df.at[idx, 'walking_score']
        df.at[idx, 'transfers_score'] = valid_df.at[idx, 'transfers_score']
        df.at[idx, 'suitability_score'] = valid_df.at[idx, 'suitability_score']
    
    return df


def _calculate_inverse_score(df: pd.DataFrame, column: str) -> pd.Series:
    result = pd.Series(0.5, index=df.index)
    
    data = df[df[column].notna() & (df[column] > 0)]
    if len(data) == 0:
        return result
    
    max_val = data[column].max()
    min_val = data[column].min()
    
    if max_val > min_val:
        scaler = MinMaxScaler(feature_range=(0, 1))
        scores = 1 - scaler.fit_transform(data[[column]]).flatten()
        result.loc[data.index] = scores
    else:
        result.loc[data.index] = 1.0
    
    result.loc[result == 0.0] = 0.5
    return result


def _get_walking_column(df: pd.DataFrame) -> Optional[str]:
    if 'walking_time_minutes' in df.columns and df['walking_time_minutes'].notna().any():
        return 'walking_time_minutes'
    elif 'nearest_stop_distance_m' in df.columns and df['nearest_stop_distance_m'].notna().any():
        df['walking_time_est'] = df['nearest_stop_distance_m'] / 83.33
        return 'walking_time_est'
    return None


def rank_apartments(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if 'suitability_score' not in df.columns:
        raise ValueError("DataFrame must have 'suitability_score' column")
    
    ranked = df.nlargest(top_n, 'suitability_score').copy()
    ranked['rank'] = range(1, len(ranked) + 1)
    return ranked


def compare_providers(df: pd.DataFrame) -> pd.DataFrame:
    if 'provider' not in df.columns:
        raise ValueError("DataFrame must have 'provider' column")
    
    agg_dict = {'rent': 'mean', 'suitability_score': 'mean'}
    
    if 'total_commute_minutes' in df.columns:
        agg_dict['total_commute_minutes'] = 'mean'
    if 'transfers' in df.columns:
        agg_dict['transfers'] = 'mean'
    if 'walking_time_minutes' in df.columns:
        agg_dict['walking_time_minutes'] = 'mean'
    
    agg_dict['apartment_id'] = 'count'
    
    provider_stats = df.groupby('provider').agg(agg_dict).reset_index()
    provider_stats = provider_stats.rename(columns={'apartment_id': 'num_apartments'})
    provider_stats = provider_stats.sort_values('suitability_score', ascending=False)
    return provider_stats
