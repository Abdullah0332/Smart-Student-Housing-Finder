import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import os
from math import radians, cos, sin, asin, sqrt

GTFS_DIR = "GTFS"

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
    r = 6371000  # Radius of earth in meters
    return c * r

def load_gtfs_stops() -> Optional[pd.DataFrame]:
    global _gtfs_stops_cache
    
    if _gtfs_stops_cache is not None:
        return _gtfs_stops_cache
    
    stops_file = os.path.join(GTFS_DIR, "stops.txt")
    if not os.path.exists(stops_file):
        return None
    
    try:
        stops = pd.read_csv(stops_file)
        required_cols = ['stop_id', 'stop_name', 'stop_lat', 'stop_lon']
        if not all(col in stops.columns for col in required_cols):
            return None
        
        stops = stops[
            (stops['stop_lat'] >= 52.3) & (stops['stop_lat'] <= 52.7) &
            (stops['stop_lon'] >= 13.0) & (stops['stop_lon'] <= 13.8)
        ].copy()
        
        _gtfs_stops_cache = stops[required_cols].copy()
        return _gtfs_stops_cache
    except Exception as e:
        return None

def find_nearest_gtfs_stop(latitude: float, longitude: float, radius_m: int = 1000) -> Optional[Dict]:
    stops_df = load_gtfs_stops()
    if stops_df is None:
        return None
    
    lat_radius = radius_m / 111000  # Convert meters to degrees
    lon_radius = radius_m / 67000   # Convert meters to degrees (approximate for Berlin)
    
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
    distances = 6371000 * c  # Radius of earth in meters
    
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

def load_gtfs_routes() -> Optional[pd.DataFrame]:
    global _gtfs_routes_cache
    if _gtfs_routes_cache is not None:
        return _gtfs_routes_cache
    
    routes_file = os.path.join(GTFS_DIR, "routes.txt")
    if not os.path.exists(routes_file):
        return None
    
    try:
        routes = pd.read_csv(routes_file)
        _gtfs_routes_cache = routes.copy()
        return _gtfs_routes_cache
    except Exception as e:
        return None

def detect_transport_mode(route_name: str, route_type: int) -> str:
    if pd.isna(route_name):
        route_name = ""
    route_name = str(route_name).upper().strip()
    
    if route_name.startswith('U') and len(route_name) <= 3:
        return 'subway'  # U-Bahn
    
    if route_name.startswith('S') and len(route_name) <= 3:
        return 'suburban'  # S-Bahn
    
    if route_name.startswith('RE') or route_name.startswith('RB'):
        return 'suburban'  # Regional rail
    
    if route_name.startswith('M') or route_name.startswith('BUS') or route_name.isdigit():
        return 'bus'
    
    if 'TRAM' in route_name or route_name.startswith('T'):
        return 'tram'
    
    if route_type == 1:
        return 'subway'
    elif route_type == 2:
        return 'suburban'
    elif route_type == 3:
        return 'bus'
    elif route_type == 0:
        return 'tram'
    
    return 'bus'

def get_routes_at_stop(stop_id: str, max_routes: int = 5) -> List[Dict]:
    routes_df = load_gtfs_routes()
    if routes_df is None:
        return []
    
    global _gtfs_stop_times_sample
    if _gtfs_stop_times_sample is None:
        stop_times_file = os.path.join(GTFS_DIR, "stop_times.txt")
        if os.path.exists(stop_times_file):
            try:
                _gtfs_stop_times_sample = pd.read_csv(
                    stop_times_file, 
                    nrows=500000,
                    usecols=['trip_id', 'stop_id', 'stop_sequence']
                )
            except Exception as e:
                return []
        else:
            return []
    
    trips_at_stop = _gtfs_stop_times_sample[
        _gtfs_stop_times_sample['stop_id'] == stop_id
    ]['trip_id'].unique()
    
    if len(trips_at_stop) == 0:
        base_stop_id = stop_id.split('::')[0] if '::' in stop_id else stop_id.split(':')[0] + ':' + stop_id.split(':')[1] if ':' in stop_id else stop_id
        trips_at_stop = _gtfs_stop_times_sample[
            _gtfs_stop_times_sample['stop_id'].str.contains(base_stop_id, na=False, regex=False)
        ]['trip_id'].unique()
    
    if len(trips_at_stop) == 0:
        return []
    
    global _gtfs_trips_cache
    if _gtfs_trips_cache is None:
        trips_file = os.path.join(GTFS_DIR, "trips.txt")
        if os.path.exists(trips_file):
            try:
                _gtfs_trips_cache = pd.read_csv(
                    trips_file,
                    usecols=['route_id', 'trip_id']
                )
            except Exception as e:
                return []
        else:
            return []
    
    route_ids = _gtfs_trips_cache[
        _gtfs_trips_cache['trip_id'].isin(trips_at_stop)
    ]['route_id'].unique()
    
    route_info = []
    seen_routes = set()
    for route_id in route_ids[:max_routes * 2]:  # Check more to get unique routes
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
    
    global _gtfs_stop_times_sample
    if _gtfs_stop_times_sample is None:
        stop_times_file = os.path.join(GTFS_DIR, "stop_times.txt")
        if os.path.exists(stop_times_file):
            try:
                _gtfs_stop_times_sample = pd.read_csv(
                    stop_times_file,
                    nrows=500000,
                    usecols=['trip_id', 'stop_id', 'stop_sequence']
                )
            except:
                return None
        else:
            return None
    
    global _gtfs_trips_cache
    if _gtfs_trips_cache is None:
        trips_file = os.path.join(GTFS_DIR, "trips.txt")
        if os.path.exists(trips_file):
            try:
                _gtfs_trips_cache = pd.read_csv(
                    trips_file,
                    usecols=['route_id', 'trip_id']
                )
            except:
                return None
        else:
            return None
    
    from_stops = _gtfs_stop_times_sample[_gtfs_stop_times_sample['stop_id'] == from_stop_id]
    to_stops = _gtfs_stop_times_sample[_gtfs_stop_times_sample['stop_id'] == to_stop_id]
    
    if len(from_stops) == 0 or len(to_stops) == 0:
        return None
    
    matching_trips = []
    for trip_id in from_stops['trip_id'].unique():
        from_seq = from_stops[from_stops['trip_id'] == trip_id]['stop_sequence'].values
        to_seq = to_stops[to_stops['trip_id'] == trip_id]['stop_sequence'].values
        
        if len(from_seq) > 0 and len(to_seq) > 0:
            if from_seq[0] < to_seq[0]:  # From stop comes before to stop
                matching_trips.append(trip_id)
                break  # Take first match
    
    if len(matching_trips) == 0:
        return None
    
    trip_id = matching_trips[0]
    route_ids = _gtfs_trips_cache[_gtfs_trips_cache['trip_id'] == trip_id]['route_id'].values
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
    from_stop = find_nearest_gtfs_stop(apartment_lat, apartment_lon, radius_m=2000)
    to_stop = find_nearest_gtfs_stop(university_lat, university_lon, radius_m=2000)
    
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
    
    walking_to_stop_distance_m = from_stop.get('distance', 0)
    walking_to_stop_minutes = (walking_to_stop_distance_m / 1000) / 5 * 60  # 5 km/h walking speed
    
    walking_from_stop_distance_m = to_stop.get('distance', 0)
    walking_from_stop_minutes = (walking_from_stop_distance_m / 1000) / 5 * 60  # 5 km/h walking speed
    
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
            
            if not direct_route_found:
                from_route = from_routes[0]
                to_route = to_routes[0]
                
                if from_route.get('name') and from_route['name'].strip():
                    route_details.append({
                        'mode': from_route['mode'],
                        'name': from_route['name'],
                        'from': from_stop['name'],
                        'to': 'Transfer point 1'
                    })
                
                if from_route['route_id'] != to_route['route_id']:
                    transfers = 1
                    if to_route.get('name') and to_route['name'].strip():
                        route_details.append({
                            'mode': to_route['mode'],
                            'name': to_route['name'],
                            'from': 'Transfer point 1',
                            'to': to_stop['name']
                        })
                    modes = [from_route['mode'], to_route['mode']]
                    
                    stop_to_stop_distance = haversine_distance(
                        from_stop['latitude'], from_stop['longitude'],
                        to_stop['latitude'], to_stop['longitude']
                    )
                    if stop_to_stop_distance > 10000:  # More than 10km - likely needs 2 transfers
                        transfers = 2
                        if len(to_routes) > 1:
                            third_route = to_routes[1]
                            if third_route.get('name') and third_route['name'].strip() and third_route['route_id'] != to_route['route_id']:
                                route_details[-1]['to'] = 'Transfer point 2'  # Update previous route
                                route_details.append({
                                    'mode': third_route['mode'],
                                    'name': third_route['name'],
                                    'from': 'Transfer point 2',
                                    'to': to_stop['name']
                                })
                                modes.append(third_route['mode'])
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
        elif to_routes:
            to_route = to_routes[0]
            if to_route.get('name') and to_route['name'].strip():
                route_details.append({
                    'mode': to_route['mode'],
                    'name': to_route['name'],
                    'from': from_stop['name'],
                    'to': to_stop['name']
                })
            modes = [to_route['mode']]
        else:
            if from_routes:
                from_route = from_routes[0]
                if from_route.get('name') and from_route['name'].strip():
                    route_details.append({
                        'mode': from_route['mode'],
                        'name': from_route['name'],
                        'from': from_stop['name'],
                        'to': to_stop['name'] + ' (estimated)'
                    })
                    modes = [from_route['mode']]
                else:
                    modes = ['public_transport']
            elif to_routes:
                to_route = to_routes[0]
                if to_route.get('name') and to_route['name'].strip():
                    route_details.append({
                        'mode': to_route['mode'],
                        'name': to_route['name'],
                        'from': from_stop['name'] + ' (estimated)',
                        'to': to_stop['name']
                    })
                    modes = [to_route['mode']]
            else:
                modes = ['public_transport']
    stop_to_stop_distance = haversine_distance(
        from_stop['latitude'],
        from_stop['longitude'],
        to_stop['latitude'],
        to_stop['longitude']
    )
    
    base_transit_minutes = (stop_to_stop_distance / 1000) / 30 * 60
    transfer_penalty = transfers * 5  # 5 minutes per transfer
    estimated_transit_minutes = base_transit_minutes + transfer_penalty
    
    total_commute = walking_to_stop_minutes + estimated_transit_minutes + walking_from_stop_minutes
    
    return {
        'nearest_stop': from_stop,
        'final_stop': to_stop,  # Add final stop info
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
    
