"""
Area Analysis Module
===================

Identifies and analyzes the best areas (districts) in Berlin for students based on:
- Public transport accessibility
- Room availability and affordability
- Walking distance to transit stops
- Commute time to universities

Urban Technology Relevance:
- Demonstrates spatial equity analysis in urban planning
- Shows how transport infrastructure affects housing desirability
- Combines mobility data with housing availability for decision-making
- Illustrates multi-criteria spatial analysis for urban accessibility
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import json
from logger_config import setup_logger

logger = setup_logger("area_analysis")

# Berlin districts (Bezirke) with approximate center coordinates
# These are used for spatial assignment when exact boundaries aren't available
BERLIN_DISTRICTS = {
    'Mitte': {'lat': 52.5200, 'lon': 13.4050, 'bounds': {'north': 52.55, 'south': 52.49, 'east': 13.45, 'west': 13.35}},
    'Friedrichshain-Kreuzberg': {'lat': 52.5020, 'lon': 13.4540, 'bounds': {'north': 52.52, 'south': 52.48, 'east': 13.48, 'west': 13.42}},
    'Pankow': {'lat': 52.5690, 'lon': 13.4010, 'bounds': {'north': 52.60, 'south': 52.53, 'east': 13.45, 'west': 13.35}},
    'Charlottenburg-Wilmersdorf': {'lat': 52.5040, 'lon': 13.3050, 'bounds': {'north': 52.53, 'south': 52.48, 'east': 13.35, 'west': 13.25}},
    'Spandau': {'lat': 52.5360, 'lon': 13.1990, 'bounds': {'north': 52.57, 'south': 52.50, 'east': 13.25, 'west': 13.15}},
    'Steglitz-Zehlendorf': {'lat': 52.4340, 'lon': 13.2580, 'bounds': {'north': 52.48, 'south': 52.38, 'east': 13.30, 'west': 13.20}},
    'Tempelhof-Schöneberg': {'lat': 52.4700, 'lon': 13.3900, 'bounds': {'north': 52.50, 'south': 52.44, 'east': 13.42, 'west': 13.35}},
    'Neukölln': {'lat': 52.4770, 'lon': 13.4350, 'bounds': {'north': 52.50, 'south': 52.45, 'east': 13.48, 'west': 13.40}},
    'Treptow-Köpenick': {'lat': 52.4420, 'lon': 13.5750, 'bounds': {'north': 52.50, 'south': 52.38, 'east': 13.65, 'west': 13.50}},
    'Marzahn-Hellersdorf': {'lat': 52.5360, 'lon': 13.5750, 'bounds': {'north': 52.57, 'south': 52.50, 'east': 13.65, 'west': 13.50}},
    'Lichtenberg': {'lat': 52.5130, 'lon': 13.4990, 'bounds': {'north': 52.54, 'south': 52.48, 'east': 13.55, 'west': 13.45}},
    'Reinickendorf': {'lat': 52.5890, 'lon': 13.3210, 'bounds': {'north': 52.62, 'south': 52.55, 'east': 13.40, 'west': 13.25}}
}


def assign_apartment_to_district(lat: float, lon: float) -> Optional[str]:
    """
    Assign an apartment to a Berlin district based on coordinates.
    
    Uses bounding box method when exact GeoJSON boundaries aren't available.
    This is a simplified spatial join that works for most cases in Berlin.
    
    Parameters:
    -----------
    lat : float
        Latitude coordinate
    lon : float
        Longitude coordinate
    
    Returns:
    --------
    str or None
        District name if coordinates fall within a district, None otherwise
    """
    if pd.isna(lat) or pd.isna(lon):
        return None
    
    # Check each district's bounding box
    for district_name, district_data in BERLIN_DISTRICTS.items():
        bounds = district_data['bounds']
        if (bounds['south'] <= lat <= bounds['north'] and 
            bounds['west'] <= lon <= bounds['east']):
            return district_name
    
    return None


def aggregate_housing_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate housing metrics per Berlin district.
    
    Calculates:
    - Total number of rooms
    - Average rent
    - Minimum and maximum rent
    - Number of unique providers
    - Room density (rooms per district area - simplified)
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with apartment data including latitude, longitude, rent, provider
    
    Returns:
    --------
    pd.DataFrame
        Aggregated metrics per district
    """
    # Assign districts to apartments
    df = df.copy()
    df['district'] = df.apply(
        lambda row: assign_apartment_to_district(
            row.get('latitude'), 
            row.get('longitude')
        ), 
        axis=1
    )
    
    # Filter to apartments with valid districts
    df_with_districts = df[df['district'].notna()].copy()
    
    if len(df_with_districts) == 0:
        logger.warning("No apartments could be assigned to districts")
        return pd.DataFrame()
    
    # Aggregate metrics per district
    housing_metrics = []
    
    for district in df_with_districts['district'].unique():
        district_df = df_with_districts[df_with_districts['district'] == district]
        
        # Calculate rent metrics
        rents = pd.to_numeric(district_df['rent'], errors='coerce')
        valid_rents = rents[rents.notna() & (rents > 0)]
        
        metrics = {
            'district': district,
            'total_rooms': len(district_df),
            'avg_rent': valid_rents.mean() if len(valid_rents) > 0 else None,
            'min_rent': valid_rents.min() if len(valid_rents) > 0 else None,
            'max_rent': valid_rents.max() if len(valid_rents) > 0 else None,
            'num_providers': district_df['provider'].nunique() if 'provider' in district_df.columns else 0,
            'rooms_with_rent': len(valid_rents)
        }
        
        housing_metrics.append(metrics)
    
    return pd.DataFrame(housing_metrics)


def aggregate_transport_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate transport accessibility metrics per district.
    
    Calculates:
    - Average walking distance to nearest stop
    - Average commute time to university
    - Average number of transfers
    - Transport mode diversity
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with transport data including walking_time_minutes, 
        total_commute_minutes, transfers, transport_modes
    
    Returns:
    --------
    pd.DataFrame
        Aggregated transport metrics per district
    """
    # Assign districts
    df = df.copy()
    df['district'] = df.apply(
        lambda row: assign_apartment_to_district(
            row.get('latitude'), 
            row.get('longitude')
        ), 
        axis=1
    )
    
    df_with_districts = df[df['district'].notna()].copy()
    
    if len(df_with_districts) == 0:
        return pd.DataFrame()
    
    transport_metrics = []
    
    for district in df_with_districts['district'].unique():
        district_df = df_with_districts[df_with_districts['district'] == district]
        
        # Walking distance metrics
        walking_distances = pd.to_numeric(
            district_df.get('nearest_stop_distance_m', pd.Series()), 
            errors='coerce'
        )
        valid_walking = walking_distances[walking_distances.notna() & (walking_distances > 0)]
        
        # Commute time metrics
        commute_times = pd.to_numeric(
            district_df.get('total_commute_minutes', pd.Series()), 
            errors='coerce'
        )
        valid_commute = commute_times[commute_times.notna() & (commute_times > 0)]
        
        # Transfer metrics
        transfers = pd.to_numeric(
            district_df.get('transfers', pd.Series()), 
            errors='coerce'
        )
        valid_transfers = transfers[transfers.notna()]
        
        # Count unique transport modes
        transport_modes_list = []
        if 'transport_modes' in district_df.columns:
            for modes_str in district_df['transport_modes'].dropna():
                if isinstance(modes_str, str):
                    transport_modes_list.extend([m.strip() for m in modes_str.split(',')])
        
        unique_modes = len(set(transport_modes_list)) if transport_modes_list else 0
        
        metrics = {
            'district': district,
            'avg_walking_distance_m': valid_walking.mean() if len(valid_walking) > 0 else None,
            'avg_commute_minutes': valid_commute.mean() if len(valid_commute) > 0 else None,
            'avg_transfers': valid_transfers.mean() if len(valid_transfers) > 0 else None,
            'transport_mode_diversity': unique_modes,
            'rooms_with_transport_data': len(district_df[district_df['total_commute_minutes'].notna()])
        }
        
        transport_metrics.append(metrics)
    
    return pd.DataFrame(transport_metrics)


def calculate_student_area_score(
    housing_df: pd.DataFrame,
    transport_df: pd.DataFrame,
    rent_weight: float = 0.30,
    commute_weight: float = 0.30,
    walking_weight: float = 0.20,
    availability_weight: float = 0.20
) -> pd.DataFrame:
    """
    Calculate composite Student Area Score per district.
    
    Combines:
    - Affordability (lower rent = higher score)
    - Commute accessibility (shorter commute = higher score)
    - Walking accessibility (shorter walk = higher score)
    - Room availability (more rooms = higher score)
    
    All components are normalized to 0-1 scale before scoring.
    
    Parameters:
    -----------
    housing_df : pd.DataFrame
        Housing metrics per district
    transport_df : pd.DataFrame
        Transport metrics per district
    rent_weight : float
        Weight for affordability component
    commute_weight : float
        Weight for commute time component
    walking_weight : float
        Weight for walking distance component
    availability_weight : float
        Weight for room availability component
    
    Returns:
    --------
    pd.DataFrame
        Districts with Student Area Score and component scores
    """
    # Merge housing and transport metrics
    merged = pd.merge(
        housing_df,
        transport_df,
        on='district',
        how='outer'
    )
    
    if len(merged) == 0:
        return pd.DataFrame()
    
    # Normalize components for scoring
    # 1. Affordability score (lower rent = higher score)
    valid_rents = merged['avg_rent'].dropna()
    if len(valid_rents) > 0:
        max_rent = valid_rents.max()
        min_rent = valid_rents.min()
        if max_rent > min_rent:
            merged['affordability_score'] = 1 - (merged['avg_rent'] - min_rent) / (max_rent - min_rent)
        else:
            merged['affordability_score'] = 0.5
    else:
        merged['affordability_score'] = 0
    
    # 2. Commute accessibility (shorter commute = higher score)
    valid_commute = merged['avg_commute_minutes'].dropna()
    if len(valid_commute) > 0:
        max_commute = valid_commute.max()
        min_commute = valid_commute.min()
        if max_commute > min_commute:
            merged['commute_score'] = 1 - (merged['avg_commute_minutes'] - min_commute) / (max_commute - min_commute)
        else:
            merged['commute_score'] = 0.5
    else:
        merged['commute_score'] = 0
    
    # 3. Walking accessibility (shorter walk = higher score)
    valid_walking = merged['avg_walking_distance_m'].dropna()
    if len(valid_walking) > 0:
        max_walking = valid_walking.max()
        min_walking = valid_walking.min()
        if max_walking > min_walking:
            merged['walking_score'] = 1 - (merged['avg_walking_distance_m'] - min_walking) / (max_walking - min_walking)
        else:
            merged['walking_score'] = 0.5
    else:
        merged['walking_score'] = 0
    
    # 4. Room availability (more rooms = higher score)
    valid_rooms = merged['total_rooms'].dropna()
    if len(valid_rooms) > 0:
        max_rooms = valid_rooms.max()
        min_rooms = valid_rooms.min()
        if max_rooms > min_rooms:
            merged['availability_score'] = (merged['total_rooms'] - min_rooms) / (max_rooms - min_rooms)
        else:
            merged['availability_score'] = 0.5
    else:
        merged['availability_score'] = 0
    
    # Calculate composite score
    merged['student_area_score'] = (
        merged['affordability_score'].fillna(0) * rent_weight +
        merged['commute_score'].fillna(0) * commute_weight +
        merged['walking_score'].fillna(0) * walking_weight +
        merged['availability_score'].fillna(0) * availability_weight
    )
    
    # Sort by score
    merged = merged.sort_values('student_area_score', ascending=False)
    
    return merged


def analyze_best_areas(df: pd.DataFrame) -> Dict:
    """
    Complete area analysis pipeline.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Complete apartment DataFrame with coordinates, rent, transport data
    
    Returns:
    --------
    dict
        Dictionary containing:
        - housing_metrics: DataFrame with housing metrics per district
        - transport_metrics: DataFrame with transport metrics per district
        - ranked_areas: DataFrame with districts ranked by Student Area Score
        - top_5_areas: List of top 5 district names
    """
    logger.info("Starting area analysis...")
    
    # Aggregate metrics
    housing_metrics = aggregate_housing_metrics(df)
    transport_metrics = aggregate_transport_metrics(df)
    
    if len(housing_metrics) == 0:
        logger.warning("No housing metrics calculated")
        return {
            'housing_metrics': pd.DataFrame(),
            'transport_metrics': pd.DataFrame(),
            'ranked_areas': pd.DataFrame(),
            'top_5_areas': []
        }
    
    # Calculate scores
    ranked_areas = calculate_student_area_score(housing_metrics, transport_metrics)
    
    # Get top 5
    top_5_areas = ranked_areas.head(5)['district'].tolist() if len(ranked_areas) > 0 else []
    
    logger.info(f"Area analysis complete. Found {len(ranked_areas)} districts with data")
    
    return {
        'housing_metrics': housing_metrics,
        'transport_metrics': transport_metrics,
        'ranked_areas': ranked_areas,
        'top_5_areas': top_5_areas
    }

