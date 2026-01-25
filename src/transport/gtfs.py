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


def detect_transport_mode(route_name: str, route_type: int) -> str:
    if pd.isna(route_name):
        route_name = ""
    route_name = str(route_name).upper().strip()
    
    if route_name.startswith('U') and len(route_name) <= 3:
        return 'subway'
    if route_name.startswith('S') and len(route_name) <= 3:
        return 'suburban'
    if route_name.startswith('RE') or route_name.startswith('RB'):
        return 'suburban'
    if route_name.startswith('M') or route_name.startswith('BUS') or route_name.isdigit():
        return 'bus'
    if 'TRAM' in route_name or route_name.startswith('T'):
        return 'tram'
    
    mode_map = {0: 'tram', 1: 'subway', 2: 'suburban', 3: 'bus'}
    return mode_map.get(route_type, 'bus')


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
                stop_times_file, nrows=500000, usecols=['trip_id', 'stop_id', 'stop_sequence']
            )
            return _gtfs_stop_times_sample
        except Exception:
            return None
    return None


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
            mode = detect_transport_mode(route_name, route_type)
            
            route_info.append({
                'route_id': route_id,
                'name': route_name,
                'mode': mode,
                'route_type': route_type
            })
            seen_routes.add(route_id)
            
            if len(route_info) >= max_routes:
                break
    
    return route_info


def find_route_between_stops(from_stop_id: str, to_stop_id: str) -> Optional[Dict]:
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
    
    matching_trips = []
    for trip_id in from_stops['trip_id'].unique():
        from_seq = from_stops[from_stops['trip_id'] == trip_id]['stop_sequence'].values
        to_seq = to_stops[to_stops['trip_id'] == trip_id]['stop_sequence'].values
        
        if len(from_seq) > 0 and len(to_seq) > 0:
            if from_seq[0] < to_seq[0]:
                matching_trips.append(trip_id)
                break
    
    if len(matching_trips) == 0:
        return None
    
    trip_id = matching_trips[0]
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
    mode = detect_transport_mode(route_name, route_type)
    
    return {
        'route_id': route_id,
        'name': route_name,
        'mode': mode,
        'route_type': route_type
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
                    'from': from_stop['name'],
                    'to': to_stop['name']
                })
            modes = [from_route['mode']]
        else:
            modes = ['public_transport']
    
    stop_to_stop_distance = haversine_distance(
        from_stop['latitude'], from_stop['longitude'],
        to_stop['latitude'], to_stop['longitude']
    )
    
    transit_speed_mpm = TRANSPORT['transit_speed_kmh'] * 1000 / 60
    base_transit_minutes = stop_to_stop_distance / transit_speed_mpm
    transfer_penalty = transfers * TRANSPORT['transfer_penalty_minutes']
    estimated_transit_minutes = base_transit_minutes + transfer_penalty
    
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
