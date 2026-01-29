import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import AREA_SCORING_WEIGHTS

BERLIN_DISTRICTS = {
    'Mitte': {
        'lat': 52.5200, 'lon': 13.4050,
        'bounds': {'north': 52.55, 'south': 52.49, 'east': 13.45, 'west': 13.35}
    },
    'Friedrichshain-Kreuzberg': {
        'lat': 52.5020, 'lon': 13.4540,
        'bounds': {'north': 52.52, 'south': 52.48, 'east': 13.48, 'west': 13.42}
    },
    'Pankow': {
        'lat': 52.5690, 'lon': 13.4010,
        'bounds': {'north': 52.60, 'south': 52.53, 'east': 13.45, 'west': 13.35}
    },
    'Charlottenburg-Wilmersdorf': {
        'lat': 52.5040, 'lon': 13.3050,
        'bounds': {'north': 52.53, 'south': 52.48, 'east': 13.35, 'west': 13.25}
    },
    'Spandau': {
        'lat': 52.5360, 'lon': 13.1990,
        'bounds': {'north': 52.57, 'south': 52.50, 'east': 13.25, 'west': 13.15}
    },
    'Steglitz-Zehlendorf': {
        'lat': 52.4340, 'lon': 13.2580,
        'bounds': {'north': 52.48, 'south': 52.38, 'east': 13.30, 'west': 13.20}
    },
    'Tempelhof-Schöneberg': {
        'lat': 52.4700, 'lon': 13.3900,
        'bounds': {'north': 52.50, 'south': 52.44, 'east': 13.42, 'west': 13.35}
    },
    'Neukölln': {
        'lat': 52.4770, 'lon': 13.4350,
        'bounds': {'north': 52.50, 'south': 52.45, 'east': 13.48, 'west': 13.40}
    },
    'Treptow-Köpenick': {
        'lat': 52.4420, 'lon': 13.5750,
        'bounds': {'north': 52.50, 'south': 52.38, 'east': 13.65, 'west': 13.50}
    },
    'Marzahn-Hellersdorf': {
        'lat': 52.5360, 'lon': 13.5750,
        'bounds': {'north': 52.57, 'south': 52.50, 'east': 13.65, 'west': 13.50}
    },
    'Lichtenberg': {
        'lat': 52.5130, 'lon': 13.4990,
        'bounds': {'north': 52.54, 'south': 52.48, 'east': 13.55, 'west': 13.45}
    },
    'Reinickendorf': {
        'lat': 52.5890, 'lon': 13.3210,
        'bounds': {'north': 52.62, 'south': 52.55, 'east': 13.40, 'west': 13.25}
    }
}


def assign_apartment_to_district(lat: float, lon: float) -> Optional[str]:
    if pd.isna(lat) or pd.isna(lon):
        return None
    
    for district_name, district_data in BERLIN_DISTRICTS.items():
        bounds = district_data['bounds']
        if (bounds['south'] <= lat <= bounds['north'] and
            bounds['west'] <= lon <= bounds['east']):
            return district_name
    return None


def aggregate_housing_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['district'] = df.apply(
        lambda row: assign_apartment_to_district(row.get('latitude'), row.get('longitude')),
        axis=1
    )
    
    df_with_districts = df[df['district'].notna()].copy()
    
    if len(df_with_districts) == 0:
        return pd.DataFrame()
    
    housing_metrics = []
    
    for district in df_with_districts['district'].unique():
        district_df = df_with_districts[df_with_districts['district'] == district]
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
    df = df.copy()
    df['district'] = df.apply(
        lambda row: assign_apartment_to_district(row.get('latitude'), row.get('longitude')),
        axis=1
    )
    
    df_with_districts = df[df['district'].notna()].copy()
    
    if len(df_with_districts) == 0:
        return pd.DataFrame()
    
    transport_metrics = []
    
    for district in df_with_districts['district'].unique():
        district_df = df_with_districts[df_with_districts['district'] == district]
        
        walking_distances = pd.to_numeric(
            district_df.get('nearest_stop_distance_m', pd.Series()), errors='coerce'
        )
        valid_walking = walking_distances[walking_distances.notna() & (walking_distances > 0)]
        
        commute_times = pd.to_numeric(
            district_df.get('total_commute_minutes', pd.Series()), errors='coerce'
        )
        valid_commute = commute_times[commute_times.notna() & (commute_times > 0)]
        
        transfers = pd.to_numeric(district_df.get('transfers', pd.Series()), errors='coerce')
        valid_transfers = transfers[transfers.notna()]
        
        transport_modes_list = []
        if 'transport_modes' in district_df.columns:
            for modes_str in district_df['transport_modes'].dropna():
                if isinstance(modes_str, str):
                    transport_modes_list.extend([m.strip() for m in modes_str.split(',')])
        
        unique_modes = len(set(transport_modes_list)) if transport_modes_list else 0
        
        walkability_scores = pd.to_numeric(district_df.get('walkability_score', pd.Series()), errors='coerce')
        valid_walkability = walkability_scores[walkability_scores.notna() & (walkability_scores >= 0)]
        
        poi_densities = pd.to_numeric(district_df.get('total_pois_500m', pd.Series()), errors='coerce')
        valid_pois = poi_densities[poi_densities.notna() & (poi_densities >= 0)]
        
        bike_scores = pd.to_numeric(district_df.get('bike_accessibility_score', pd.Series()), errors='coerce')
        valid_bike = bike_scores[bike_scores.notna() & (bike_scores >= 0)]
        
        grocery_counts = pd.to_numeric(district_df.get('grocery_stores_500m', pd.Series()), errors='coerce')
        valid_grocery = grocery_counts[grocery_counts.notna() & (grocery_counts >= 0)]
        
        cafe_counts = pd.to_numeric(district_df.get('cafes_500m', pd.Series()), errors='coerce')
        valid_cafes = cafe_counts[cafe_counts.notna() & (cafe_counts >= 0)]
        
        transit_acc = pd.to_numeric(district_df.get('transit_accessibility_score', pd.Series()), errors='coerce')
        valid_transit_acc = transit_acc[transit_acc.notna() & (transit_acc >= 0)]
        bike_contrib = pd.to_numeric(district_df.get('bike_contribution_score', pd.Series()), errors='coerce')
        valid_bike_contrib = bike_contrib[bike_contrib.notna() & (bike_contrib >= 0)]
        poi_dens = pd.to_numeric(district_df.get('poi_density_score', pd.Series()), errors='coerce')
        valid_poi_dens = poi_dens[poi_dens.notna() & (poi_dens >= 0)]
        essential = pd.to_numeric(district_df.get('essential_services_score', pd.Series()), errors='coerce')
        valid_essential = essential[essential.notna() & (essential >= 0)]
        
        metrics = {
            'district': district,
            'avg_walking_distance_m': valid_walking.mean() if len(valid_walking) > 0 else None,
            'avg_commute_minutes': valid_commute.mean() if len(valid_commute) > 0 else None,
            'avg_transfers': valid_transfers.mean() if len(valid_transfers) > 0 else None,
            'transport_mode_diversity': unique_modes,
            'rooms_with_transport_data': len(district_df[district_df['total_commute_minutes'].notna()]),
            'avg_walkability_score': valid_walkability.mean() if len(valid_walkability) > 0 else None,
            'avg_poi_density': valid_pois.mean() if len(valid_pois) > 0 else None,
            'avg_bike_accessibility_score': valid_bike.mean() if len(valid_bike) > 0 else None,
            'avg_grocery_stores_500m': valid_grocery.mean() if len(valid_grocery) > 0 else None,
            'avg_cafes_500m': valid_cafes.mean() if len(valid_cafes) > 0 else None,
            'rooms_with_walkability_data': len(district_df[district_df['walkability_score'].notna()]) if 'walkability_score' in district_df.columns else 0,
            'avg_transit_accessibility_score': valid_transit_acc.mean() if len(valid_transit_acc) > 0 else None,
            'avg_bike_contribution_score': valid_bike_contrib.mean() if len(valid_bike_contrib) > 0 else None,
            'avg_poi_density_score': valid_poi_dens.mean() if len(valid_poi_dens) > 0 else None,
            'avg_essential_services_score': valid_essential.mean() if len(valid_essential) > 0 else None,
        }
        transport_metrics.append(metrics)
    
    return pd.DataFrame(transport_metrics)


def calculate_student_area_score(
    housing_df: pd.DataFrame,
    transport_df: pd.DataFrame,
    rent_weight: float = None,
    commute_weight: float = None,
    walking_weight: float = None,
    availability_weight: float = None
) -> pd.DataFrame:
    rent_weight = rent_weight or AREA_SCORING_WEIGHTS['rent']
    commute_weight = commute_weight or AREA_SCORING_WEIGHTS['commute']
    walking_weight = walking_weight or AREA_SCORING_WEIGHTS['walking']
    availability_weight = availability_weight or AREA_SCORING_WEIGHTS['availability']
    
    merged = pd.merge(housing_df, transport_df, on='district', how='outer')
    
    if len(merged) == 0:
        return pd.DataFrame()
    
    merged['affordability_score'] = _normalize_inverse(merged, 'avg_rent')
    merged['commute_score'] = _normalize_inverse(merged, 'avg_commute_minutes')
    merged['walking_score'] = _normalize_inverse(merged, 'avg_walking_distance_m')
    merged['availability_score'] = _normalize_direct(merged, 'total_rooms')
    
    if 'avg_walkability_score' in merged.columns:
        merged['walkability_score'] = _normalize_direct(merged, 'avg_walkability_score')
        total_weight = rent_weight + commute_weight + walking_weight + availability_weight
        walkability_weight = 0.1
        adjusted_total = total_weight + walkability_weight
        
        merged['student_area_score'] = (
            merged['affordability_score'].fillna(0) * (rent_weight / adjusted_total) +
            merged['commute_score'].fillna(0) * (commute_weight / adjusted_total) +
            merged['walking_score'].fillna(0) * (walking_weight / adjusted_total) +
            merged['availability_score'].fillna(0) * (availability_weight / adjusted_total) +
            merged['walkability_score'].fillna(0) * (walkability_weight / adjusted_total)
        )
    else:
        merged['student_area_score'] = (
            merged['affordability_score'].fillna(0) * rent_weight +
            merged['commute_score'].fillna(0) * commute_weight +
            merged['walking_score'].fillna(0) * walking_weight +
            merged['availability_score'].fillna(0) * availability_weight
        )
    
    merged = merged.sort_values('student_area_score', ascending=False)
    return merged


def _normalize_inverse(df: pd.DataFrame, column: str) -> pd.Series:
    valid = df[column].dropna()
    if len(valid) == 0:
        return pd.Series(0, index=df.index)
    
    max_val = valid.max()
    min_val = valid.min()
    
    if max_val > min_val:
        return 1 - (df[column] - min_val) / (max_val - min_val)
    else:
        return pd.Series(0.5, index=df.index)


def _normalize_direct(df: pd.DataFrame, column: str) -> pd.Series:
    valid = df[column].dropna()
    if len(valid) == 0:
        return pd.Series(0, index=df.index)
    
    max_val = valid.max()
    min_val = valid.min()
    
    if max_val > min_val:
        return (df[column] - min_val) / (max_val - min_val)
    else:
        return pd.Series(0.5, index=df.index)


def analyze_best_areas(df: pd.DataFrame) -> Dict:
    housing_metrics = aggregate_housing_metrics(df)
    transport_metrics = aggregate_transport_metrics(df)
    
    if len(housing_metrics) == 0:
        return {
            'housing_metrics': pd.DataFrame(),
            'transport_metrics': pd.DataFrame(),
            'ranked_areas': pd.DataFrame(),
            'top_5_areas': []
        }
    
    ranked_areas = calculate_student_area_score(housing_metrics, transport_metrics)
    top_5_areas = ranked_areas.head(5)['district'].tolist() if len(ranked_areas) > 0 else []
    
    return {
        'housing_metrics': housing_metrics,
        'transport_metrics': transport_metrics,
        'ranked_areas': ranked_areas,
        'top_5_areas': top_5_areas
    }
