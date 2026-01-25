import json
from typing import Dict, Callable, Optional

import pandas as pd

from .gtfs import get_gtfs_commute_info, find_nearest_gtfs_stop


def get_commute_info(
    apartment_lat: float,
    apartment_lon: float,
    university_lat: float,
    university_lon: float
) -> Dict:
    return get_gtfs_commute_info(apartment_lat, apartment_lon, university_lat, university_lon)


def batch_get_commute_info(
    apartments_df: pd.DataFrame,
    university_lat: float,
    university_lon: float,
    delay: float = 0.0,
    progress_callback: Optional[Callable] = None
) -> None:
    apartments_df['nearest_stop_name'] = None
    apartments_df['nearest_stop_distance_m'] = None
    apartments_df['walking_time_minutes'] = None
    apartments_df['final_stop_name'] = None
    apartments_df['final_stop_distance_m'] = None
    apartments_df['walking_from_stop_minutes'] = None
    apartments_df['transit_time_minutes'] = None
    apartments_df['total_commute_minutes'] = None
    apartments_df['transfers'] = None
    apartments_df['transport_modes'] = None
    apartments_df['route_details'] = None
    
    cached_count = 0
    new_count = 0
    processed_count = 0
    
    for idx, row in apartments_df.iterrows():
        if pd.isna(row['latitude']) or pd.isna(row['longitude']):
            continue
        
        commute_info = get_commute_info(
            row['latitude'],
            row['longitude'],
            university_lat,
            university_lon
        )
        
        if commute_info.get('nearest_stop'):
            apartments_df.at[idx, 'nearest_stop_name'] = commute_info['nearest_stop']['name']
            apartments_df.at[idx, 'nearest_stop_distance_m'] = commute_info.get(
                'walking_distance_m', commute_info['nearest_stop'].get('distance', 0)
            )
            apartments_df.at[idx, 'walking_time_minutes'] = commute_info.get('walking_time_minutes', 0)
            
            if commute_info.get('final_stop'):
                apartments_df.at[idx, 'final_stop_name'] = commute_info['final_stop']['name']
                apartments_df.at[idx, 'final_stop_distance_m'] = commute_info.get(
                    'walking_from_stop_distance_m', commute_info['final_stop'].get('distance', 0)
                )
                apartments_df.at[idx, 'walking_from_stop_minutes'] = commute_info.get('walking_from_stop_minutes', 0)
            
            if commute_info.get('route_details'):
                try:
                    apartments_df.at[idx, 'route_details'] = json.dumps(commute_info['route_details'])
                except Exception:
                    apartments_df.at[idx, 'route_details'] = None
            
            if commute_info.get('journey'):
                journey = commute_info['journey']
                apartments_df.at[idx, 'transit_time_minutes'] = commute_info.get(
                    'transit_time_minutes', journey.get('duration_minutes', 0)
                )
                apartments_df.at[idx, 'total_commute_minutes'] = commute_info.get('total_commute_minutes', 0)
                apartments_df.at[idx, 'transfers'] = commute_info.get('transfers', journey.get('transfers', 0))
                
                modes = commute_info.get('modes', journey.get('modes', []))
                if modes:
                    apartments_df.at[idx, 'transport_modes'] = ', '.join(modes) if isinstance(modes, list) else str(modes)
                else:
                    apartments_df.at[idx, 'transport_modes'] = 'public_transport'
                
                new_count += 1
            else:
                apartments_df.at[idx, 'transit_time_minutes'] = None
                apartments_df.at[idx, 'total_commute_minutes'] = commute_info.get(
                    'walking_time_minutes', commute_info.get('total_commute_minutes', 0)
                )
                apartments_df.at[idx, 'transfers'] = commute_info.get('transfers', None)
                
                modes = commute_info.get('modes', [])
                if modes:
                    apartments_df.at[idx, 'transport_modes'] = ', '.join(modes) if isinstance(modes, list) else str(modes)
                
                cached_count += 1
        else:
            apartments_df.at[idx, 'nearest_stop_name'] = None
            apartments_df.at[idx, 'nearest_stop_distance_m'] = None
            apartments_df.at[idx, 'walking_time_minutes'] = None
            apartments_df.at[idx, 'final_stop_name'] = None
            apartments_df.at[idx, 'final_stop_distance_m'] = None
            apartments_df.at[idx, 'walking_from_stop_minutes'] = None
            apartments_df.at[idx, 'transit_time_minutes'] = None
            apartments_df.at[idx, 'total_commute_minutes'] = None
            apartments_df.at[idx, 'transfers'] = None
            apartments_df.at[idx, 'transport_modes'] = None
            apartments_df.at[idx, 'route_details'] = None
        
        processed_count += 1
        
        if progress_callback:
            progress_callback(processed_count, len(apartments_df), cached_count, new_count)
