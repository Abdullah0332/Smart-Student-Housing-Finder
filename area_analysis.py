import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import json

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
        lambda row: assign_apartment_to_district(
            row.get('latitude'), 
            row.get('longitude')
        ), 
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
        
        walking_distances = pd.to_numeric(
            district_df.get('nearest_stop_distance_m', pd.Series()), 
            errors='coerce'
        )
        valid_walking = walking_distances[walking_distances.notna() & (walking_distances > 0)]
        
        commute_times = pd.to_numeric(
            district_df.get('total_commute_minutes', pd.Series()), 
            errors='coerce'
        )
        valid_commute = commute_times[commute_times.notna() & (commute_times > 0)]
        
        transfers = pd.to_numeric(
            district_df.get('transfers', pd.Series()), 
            errors='coerce'
        )
        valid_transfers = transfers[transfers.notna()]
        
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
    merged = pd.merge(
        housing_df,
        transport_df,
        on='district',
        how='outer'
    )
    
    if len(merged) == 0:
        return pd.DataFrame()
    
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
    
    merged['student_area_score'] = (
        merged['affordability_score'].fillna(0) * rent_weight +
        merged['commute_score'].fillna(0) * commute_weight +
        merged['walking_score'].fillna(0) * walking_weight +
        merged['availability_score'].fillna(0) * availability_weight
    )
    
    merged = merged.sort_values('student_area_score', ascending=False)
    
    return merged

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

