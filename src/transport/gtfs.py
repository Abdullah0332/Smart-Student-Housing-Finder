import os
from pathlib import Path
from math import radians, cos, sin, asin, sqrt
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import GTFS_DIR, BERLIN_BOUNDS, TRANSPORT

_gtfs_stops_cache = None
_gtfs_routes_cache = None
_gtfs_trips_cache = None
_gtfs_stop_times_sample = None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371000 * c


def get_transport_mode_from_route_type(route_type: int) -> str:
    """
    Maps GTFS route_type to transport mode using official GTFS specification.
    Uses live GTFS data instead of hardcoded route name detection.
    """
    standard_map = {
        0: 'tram',
        1: 'subway',
        2: 'rail',
        3: 'bus',
        4: 'ferry',
        5: 'cable_tram',
        6: 'aerial_lift',
        7: 'funicular',
        11: 'trolleybus',
        12: 'monorail'
    }
    
    extended_map = {
        100: 'rail',
        106: 'rail',
        109: 'rail',
        400: 'subway',
        700: 'bus',
        900: 'tram',
        1000: 'rail'
    }
    
    if route_type in extended_map:
        return extended_map[route_type]
    
    return standard_map.get(route_type, 'bus')


def load_gtfs_stops() -> Optional[pd.DataFrame]:
    global _gtfs_stops_cache
    
    if _gtfs_stops_cache is not None:
        return _gtfs_stops_cache
    
    stops_file = os.path.join(str(GTFS_DIR), "stops.txt")
    if not os.path.exists(stops_file):
        return None
    
    try:
        stops = pd.read_csv(stops_file)
        required_cols = ['stop_id', 'stop_name', 'stop_lat', 'stop_lon']
        if not all(col in stops.columns for col in required_cols):
            return None
        
        stops = stops[
            (stops['stop_lat'] >= BERLIN_BOUNDS['south']) & 
            (stops['stop_lat'] <= BERLIN_BOUNDS['north']) &
            (stops['stop_lon'] >= BERLIN_BOUNDS['west']) & 
            (stops['stop_lon'] <= BERLIN_BOUNDS['east'])
        ].copy()
        
        _gtfs_stops_cache = stops[required_cols].copy()
        return _gtfs_stops_cache
    except Exception:
        return None


def load_gtfs_routes() -> Optional[pd.DataFrame]:
    global _gtfs_routes_cache
    if _gtfs_routes_cache is not None:
        return _gtfs_routes_cache
    
    routes_file = os.path.join(str(GTFS_DIR), "routes.txt")
    if not os.path.exists(routes_file):
        return None
    
    try:
        routes = pd.read_csv(routes_file)
        _gtfs_routes_cache = routes.copy()
        return _gtfs_routes_cache
    except Exception:
        return None


def _load_stop_times_sample() -> Optional[pd.DataFrame]:
    global _gtfs_stop_times_sample
    if _gtfs_stop_times_sample is not None:
        return _gtfs_stop_times_sample
    
    stop_times_file = os.path.join(str(GTFS_DIR), "stop_times.txt")
    if os.path.exists(stop_times_file):
        try:
            _gtfs_stop_times_sample = pd.read_csv(
                stop_times_file, nrows=500000, usecols=['trip_id', 'stop_id', 'stop_sequence', 'arrival_time', 'departure_time']
            )
            return _gtfs_stop_times_sample
        except Exception:
            return None
    return None


def _parse_gtfs_time(time_str: str) -> Optional[float]:
    """
    Parse GTFS time format (HH:MM:SS or H:MM:SS) to minutes since midnight.
    Handles times that may exceed 24 hours (e.g., 25:30:00 = next day 1:30 AM).
    """
    if pd.isna(time_str) or not time_str or str(time_str).strip() == '':
        return None
    
    try:
        parts = str(time_str).strip().split(':')
        if len(parts) != 3:
            return None
        
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        
        total_minutes = hours * 60 + minutes + seconds / 60.0
        return total_minutes
    except (ValueError, IndexError):
        return None


def _calculate_trip_duration_minutes(from_stop_time: str, to_stop_time: str) -> Optional[float]:
    """
    Calculate actual trip duration in minutes from GTFS scheduled times.
    """
    from_minutes = _parse_gtfs_time(from_stop_time)
    to_minutes = _parse_gtfs_time(to_stop_time)
    
    if from_minutes is None or to_minutes is None:
        return None
    
    if to_minutes < from_minutes:
        to_minutes += 1440
    
    duration = to_minutes - from_minutes
    return duration if duration >= 0 else None


def _load_trips() -> Optional[pd.DataFrame]:
    global _gtfs_trips_cache
    if _gtfs_trips_cache is not None:
        return _gtfs_trips_cache
    
    trips_file = os.path.join(str(GTFS_DIR), "trips.txt")
    if os.path.exists(trips_file):
        try:
            _gtfs_trips_cache = pd.read_csv(trips_file, usecols=['route_id', 'trip_id'])
            return _gtfs_trips_cache
        except Exception:
            return None
    return None


def find_nearest_gtfs_stop(latitude: float, longitude: float, radius_m: int = None) -> Optional[Dict]:
    radius_m = radius_m or TRANSPORT['max_walking_radius_m']
    
    stops_df = load_gtfs_stops()
    if stops_df is None:
        return None
    
    lat_radius = radius_m / 111000
    lon_radius = radius_m / 67000
    
    stops_df = stops_df[
        (stops_df['stop_lat'] >= latitude - lat_radius) & 
        (stops_df['stop_lat'] <= latitude + lat_radius) &
        (stops_df['stop_lon'] >= longitude - lon_radius) & 
        (stops_df['stop_lon'] <= longitude + lon_radius)
    ].copy()
    
    if len(stops_df) == 0:
        return None
    
    lat_rad = np.radians(latitude)
    lon_rad = np.radians(longitude)
    stops_lat_rad = np.radians(stops_df['stop_lat'].values)
    stops_lon_rad = np.radians(stops_df['stop_lon'].values)
    
    dlat = stops_lat_rad - lat_rad
    dlon = stops_lon_rad - lon_rad
    
    a = np.sin(dlat/2)**2 + np.cos(lat_rad) * np.cos(stops_lat_rad) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    distances = 6371000 * c
    
    stops_df['distance'] = distances
    stops_df = stops_df[stops_df['distance'] <= radius_m]
    
    if len(stops_df) == 0:
        return None
    
    nearest_idx = stops_df['distance'].idxmin()
    nearest = stops_df.loc[nearest_idx]
    
    return {
        'name': nearest['stop_name'],
        'latitude': nearest['stop_lat'],
        'longitude': nearest['stop_lon'],
        'distance': int(nearest['distance']),
        'id': str(nearest['stop_id'])
    }


def get_routes_at_stop(stop_id: str, max_routes: int = 5) -> List[Dict]:
    routes_df = load_gtfs_routes()
    if routes_df is None:
        return []
    
    stop_times = _load_stop_times_sample()
    if stop_times is None:
        return []
    
    trips = _load_trips()
    if trips is None:
        return []
    
    trips_at_stop = stop_times[stop_times['stop_id'] == stop_id]['trip_id'].unique()
    
    if len(trips_at_stop) == 0:
        base_stop_id = stop_id.split('::')[0] if '::' in stop_id else stop_id.split(':')[0] + ':' + stop_id.split(':')[1] if ':' in stop_id else stop_id
        trips_at_stop = stop_times[
            stop_times['stop_id'].str.contains(base_stop_id, na=False, regex=False)
        ]['trip_id'].unique()
    
    if len(trips_at_stop) == 0:
        return []
    
    route_ids = trips[trips['trip_id'].isin(trips_at_stop)]['route_id'].unique()
    
    route_info = []
    seen_routes = set()
    
    for route_id in route_ids[:max_routes * 2]:
        if route_id in seen_routes:
            continue
        
        route = routes_df[routes_df['route_id'] == route_id]
        if len(route) > 0:
            route = route.iloc[0]
            route_type = route.get('route_type', 3)
            route_short = str(route.get('route_short_name', '')) if pd.notna(route.get('route_short_name')) else ''
            route_long = str(route.get('route_long_name', '')) if pd.notna(route.get('route_long_name')) else ''
            route_name = route_short if route_short and route_short != 'nan' else (route_long if route_long and route_long != 'nan' else '')
            
            if not route_name or route_name == 'nan' or route_name.strip() == '':
                continue
            
            route_name = route_name.strip()
            mode = get_transport_mode_from_route_type(route_type)
            
            route_color = str(route.get('route_color', '')).strip() if pd.notna(route.get('route_color')) and str(route.get('route_color', '')).strip() else None
            route_text_color = str(route.get('route_text_color', '')).strip() if pd.notna(route.get('route_text_color')) and str(route.get('route_text_color', '')).strip() else None
            route_long_name = str(route.get('route_long_name', '')).strip() if pd.notna(route.get('route_long_name')) and str(route.get('route_long_name', '')).strip() and str(route.get('route_long_name', '')).strip() != 'nan' else None
            route_desc = str(route.get('route_desc', '')).strip() if pd.notna(route.get('route_desc')) and str(route.get('route_desc', '')).strip() and str(route.get('route_desc', '')).strip() != 'nan' else None
            
            if route_color and not route_color.startswith('#'):
                route_color = f'#{route_color}'
            if route_text_color and not route_text_color.startswith('#'):
                route_text_color = f'#{route_text_color}'
            
            route_info.append({
                'route_id': route_id,
                'name': route_name,
                'long_name': route_long_name,
                'description': route_desc,
                'mode': mode,
                'route_type': route_type,
                'color': route_color,
                'text_color': route_text_color
            })
            seen_routes.add(route_id)
            
            if len(route_info) >= max_routes:
                break
    
    return route_info


def find_route_between_stops(from_stop_id: str, to_stop_id: str) -> Optional[Dict]:
    """
    Find a route between two stops and calculate ACTUAL trip duration from GTFS scheduled times.
    Returns route info with actual transit time in minutes.
    """
    routes_df = load_gtfs_routes()
    if routes_df is None:
        return None
    
    stop_times = _load_stop_times_sample()
    if stop_times is None:
        return None
    
    trips = _load_trips()
    if trips is None:
        return None
    
    from_stops = stop_times[stop_times['stop_id'] == from_stop_id]
    to_stops = stop_times[stop_times['stop_id'] == to_stop_id]
    
    if len(from_stops) == 0 or len(to_stops) == 0:
        return None
    
    best_trip = None
    best_duration = None
    
    for trip_id in from_stops['trip_id'].unique():
        trip_from = from_stops[from_stops['trip_id'] == trip_id]
        trip_to = to_stops[to_stops['trip_id'] == trip_id]
        
        if len(trip_from) == 0 or len(trip_to) == 0:
            continue
        
        from_seq = trip_from['stop_sequence'].values[0]
        to_seq = trip_to['stop_sequence'].values[0]
        
        if from_seq < to_seq:
            from_departure = trip_from['departure_time'].values[0]
            to_arrival = trip_to['arrival_time'].values[0]
            
            duration = _calculate_trip_duration_minutes(from_departure, to_arrival)
            
            if duration is not None:
                if best_duration is None or duration < best_duration:
                    best_trip = trip_id
                    best_duration = duration
    
    if best_trip is None or best_duration is None:
        return None
    
    trip_id = best_trip
    route_ids = trips[trips['trip_id'] == trip_id]['route_id'].values
    if len(route_ids) == 0:
        return None
    
    route_id = route_ids[0]
    route = routes_df[routes_df['route_id'] == route_id]
    if len(route) == 0:
        return None
    
    route = route.iloc[0]
    route_type = route.get('route_type', 3)
    route_short = str(route.get('route_short_name', '')) if pd.notna(route.get('route_short_name')) else ''
    route_long = str(route.get('route_long_name', '')) if pd.notna(route.get('route_long_name')) else ''
    route_name = route_short if route_short and route_short != 'nan' else (route_long if route_long and route_long != 'nan' else '')
    
    if not route_name or route_name.strip() == '':
        return None
    
    route_name = route_name.strip()
    mode = get_transport_mode_from_route_type(route_type)
    
    route_color = str(route.get('route_color', '')).strip() if pd.notna(route.get('route_color')) and str(route.get('route_color', '')).strip() else None
    route_text_color = str(route.get('route_text_color', '')).strip() if pd.notna(route.get('route_text_color')) and str(route.get('route_text_color', '')).strip() else None
    route_long_name = str(route.get('route_long_name', '')).strip() if pd.notna(route.get('route_long_name')) and str(route.get('route_long_name', '')).strip() and str(route.get('route_long_name', '')).strip() != 'nan' else None
    route_desc = str(route.get('route_desc', '')).strip() if pd.notna(route.get('route_desc')) and str(route.get('route_desc', '')).strip() and str(route.get('route_desc', '')).strip() != 'nan' else None
    
    if route_color and not route_color.startswith('#'):
        route_color = f'#{route_color}'
    if route_text_color and not route_text_color.startswith('#'):
        route_text_color = f'#{route_text_color}'
    
    return {
        'route_id': route_id,
        'name': route_name,
        'long_name': route_long_name,
        'description': route_desc,
        'mode': mode,
        'route_type': route_type,
        'color': route_color,
        'text_color': route_text_color,
        'trip_duration_minutes': best_duration
    }


def get_gtfs_commute_info(
    apartment_lat: float,
    apartment_lon: float,
    university_lat: float,
    university_lon: float
) -> Dict:
    from_stop = find_nearest_gtfs_stop(apartment_lat, apartment_lon)
    to_stop = find_nearest_gtfs_stop(university_lat, university_lon)
    
    if not from_stop or not to_stop:
        return {
            'error': 'No nearby GTFS stops found',
            'nearest_stop': from_stop,
            'journey': None,
            'walking_distance_m': from_stop.get('distance', 0) if from_stop else None,
            'walking_time_minutes': None,
            'transit_time_minutes': None,
            'total_commute_minutes': None,
            'transfers': None,
            'modes': [],
            'route_details': []
        }
    
    walking_speed_mps = TRANSPORT['walking_speed_kmh'] * 1000 / 60
    
    walking_to_stop_distance_m = from_stop.get('distance', 0)
    walking_to_stop_minutes = walking_to_stop_distance_m / walking_speed_mps
    
    walking_from_stop_distance_m = to_stop.get('distance', 0)
    walking_from_stop_minutes = walking_from_stop_distance_m / walking_speed_mps
    
    route_info = find_route_between_stops(from_stop['id'], to_stop['id'])
    
    route_details = []
    modes = []
    transfers = 0
    
    if route_info and route_info.get('name') and route_info['name'].strip():
        route_details.append({
            'mode': route_info['mode'],
            'name': route_info['name'],
            'long_name': route_info.get('long_name'),
            'description': route_info.get('description'),
            'color': route_info.get('color'),
            'text_color': route_info.get('text_color'),
            'route_type': route_info.get('route_type'),
            'from': from_stop['name'],
            'to': to_stop['name']
        })
        modes.append(route_info['mode'])
    else:
        from_routes = get_routes_at_stop(from_stop['id'], max_routes=10)
        to_routes = get_routes_at_stop(to_stop['id'], max_routes=10)
        
        if from_routes and to_routes:
            direct_route_found = False
            for from_route in from_routes:
                for to_route in to_routes:
                    if from_route['route_id'] == to_route['route_id']:
                        if from_route.get('name') and from_route['name'].strip():
                            route_details.append({
                                'mode': from_route['mode'],
                                'name': from_route['name'],
                                'long_name': from_route.get('long_name'),
                                'description': from_route.get('description'),
                                'color': from_route.get('color'),
                                'text_color': from_route.get('text_color'),
                                'route_type': from_route.get('route_type'),
                                'from': from_stop['name'],
                                'to': to_stop['name']
                            })
                            modes = [from_route['mode']]
                            direct_route_found = True
                            break
                if direct_route_found:
                    break
            
            if not direct_route_found and from_routes:
                from_route = from_routes[0]
                if from_route.get('name') and from_route['name'].strip():
                    route_details.append({
                        'mode': from_route['mode'],
                        'name': from_route['name'],
                        'long_name': from_route.get('long_name'),
                        'description': from_route.get('description'),
                        'color': from_route.get('color'),
                        'text_color': from_route.get('text_color'),
                        'route_type': from_route.get('route_type'),
                        'from': from_stop['name'],
                        'to': 'Transfer point'
                    })
                
                if to_routes:
                    to_route = to_routes[0]
                    if from_route['route_id'] != to_route['route_id']:
                        transfers = 1
                        if to_route.get('name') and to_route['name'].strip():
                            route_details.append({
                                'mode': to_route['mode'],
                                'name': to_route['name'],
                                'long_name': to_route.get('long_name'),
                                'description': to_route.get('description'),
                                'color': to_route.get('color'),
                                'text_color': to_route.get('text_color'),
                                'route_type': to_route.get('route_type'),
                                'from': 'Transfer point',
                                'to': to_stop['name']
                            })
                            modes = [from_route['mode'], to_route['mode']]
                    else:
                        modes = [from_route['mode']]
        elif from_routes:
            from_route = from_routes[0]
            if from_route.get('name') and from_route['name'].strip():
                route_details.append({
                    'mode': from_route['mode'],
                    'name': from_route['name'],
                    'long_name': from_route.get('long_name'),
                    'description': from_route.get('description'),
                    'color': from_route.get('color'),
                    'text_color': from_route.get('text_color'),
                    'route_type': from_route.get('route_type'),
                    'from': from_stop['name'],
                    'to': to_stop['name']
                })
            modes = [from_route['mode']]
        else:
            modes = ['public_transport']
    
    actual_transit_minutes = None
    if route_info and route_info.get('trip_duration_minutes') is not None:
        actual_transit_minutes = route_info['trip_duration_minutes']
    
    if actual_transit_minutes is None:
        stop_to_stop_distance = haversine_distance(
            from_stop['latitude'], from_stop['longitude'],
            to_stop['latitude'], to_stop['longitude']
        )
        transit_speed_mpm = TRANSPORT['transit_speed_kmh'] * 1000 / 60
        base_transit_minutes = stop_to_stop_distance / transit_speed_mpm
        transfer_penalty = transfers * TRANSPORT['transfer_penalty_minutes']
        estimated_transit_minutes = base_transit_minutes + transfer_penalty
    else:
        transfer_penalty = transfers * TRANSPORT['transfer_penalty_minutes']
        estimated_transit_minutes = actual_transit_minutes + transfer_penalty
    
    total_commute = walking_to_stop_minutes + estimated_transit_minutes + walking_from_stop_minutes
    
    return {
        'nearest_stop': from_stop,
        'final_stop': to_stop,
        'journey': {
            'duration_minutes': int(estimated_transit_minutes),
            'transfers': transfers,
            'modes': modes,
            'route_details': route_details,
            'departure': '',
            'arrival': ''
        },
        'walking_distance_m': int(walking_to_stop_distance_m),
        'walking_time_minutes': walking_to_stop_minutes,
        'walking_from_stop_distance_m': int(walking_from_stop_distance_m),
        'walking_from_stop_minutes': walking_from_stop_minutes,
        'transit_time_minutes': estimated_transit_minutes,
        'total_commute_minutes': total_commute,
        'transfers': transfers,
        'modes': modes,
        'route_details': route_details
    }
