"""
GTFS Helper Module
==================

Uses GTFS (General Transit Feed Specification) data for route planning.
Provides transport types, line names, and transfer information.

Urban Technology Relevance:
- GTFS is the standard format for public transit data
- Local GTFS data provides offline route planning
- Demonstrates use of open transit data standards
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import os
from math import radians, cos, sin, asin, sqrt
from logger_config import setup_logger

logger = setup_logger("gtfs_helper")

# GTFS directory
GTFS_DIR = "GTFS"

# Cache for GTFS data (loaded once, reused)
_gtfs_stops_cache = None
_gtfs_routes_cache = None
_gtfs_trips_cache = None
_gtfs_stop_times_sample = None

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth (in meters).
    
    Parameters:
    -----------
    lat1, lon1 : float
        Latitude and longitude of first point
    lat2, lon2 : float
        Latitude and longitude of second point
    
    Returns:
    --------
    float
        Distance in meters
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Radius of earth in meters
    return c * r


def load_gtfs_stops() -> Optional[pd.DataFrame]:
    """
    Load GTFS stops data (cached for performance).
    
    Returns:
    --------
    pd.DataFrame or None
        DataFrame with stop_id, stop_name, stop_lat, stop_lon columns
    """
    global _gtfs_stops_cache
    
    # Return cached data if available
    if _gtfs_stops_cache is not None:
        return _gtfs_stops_cache
    
    stops_file = os.path.join(GTFS_DIR, "stops.txt")
    if not os.path.exists(stops_file):
        return None
    
    try:
        stops = pd.read_csv(stops_file)
        # Ensure we have required columns
        required_cols = ['stop_id', 'stop_name', 'stop_lat', 'stop_lon']
        if not all(col in stops.columns for col in required_cols):
            return None
        
        # Filter to Berlin area only for faster processing (approximate bounds)
        # Berlin approximate bounds: lat 52.3-52.7, lon 13.0-13.8
        stops = stops[
            (stops['stop_lat'] >= 52.3) & (stops['stop_lat'] <= 52.7) &
            (stops['stop_lon'] >= 13.0) & (stops['stop_lon'] <= 13.8)
        ].copy()
        
        # Cache the filtered stops
        _gtfs_stops_cache = stops[required_cols].copy()
        logger.info(f"Loaded {len(_gtfs_stops_cache)} GTFS stops")
        return _gtfs_stops_cache
    except Exception as e:
        logger.error(f"Error loading GTFS stops: {e}")
        return None


def find_nearest_gtfs_stop(latitude: float, longitude: float, radius_m: int = 1000) -> Optional[Dict]:
    """
    Find nearest GTFS stop to given coordinates (optimized for speed).
    
    Uses vectorized operations and approximate filtering for faster processing.
    
    Parameters:
    -----------
    latitude : float
        Latitude coordinate
    longitude : float
        Longitude coordinate
    radius_m : int
        Search radius in meters (default: 1000m)
    
    Returns:
    --------
    dict or None
        Stop information including name, coordinates, and distance
    """
    stops_df = load_gtfs_stops()
    if stops_df is None:
        return None
    
    # Quick approximate filter using lat/lon bounds (much faster than haversine for all stops)
    # 1 degree lat ≈ 111km, 1 degree lon ≈ 67km at Berlin latitude
    lat_radius = radius_m / 111000  # Convert meters to degrees
    lon_radius = radius_m / 67000   # Convert meters to degrees (approximate for Berlin)
    
    # Filter stops within approximate bounding box first
    stops_df = stops_df[
        (stops_df['stop_lat'] >= latitude - lat_radius) & 
        (stops_df['stop_lat'] <= latitude + lat_radius) &
        (stops_df['stop_lon'] >= longitude - lon_radius) & 
        (stops_df['stop_lon'] <= longitude + lon_radius)
    ].copy()
    
    if len(stops_df) == 0:
        return None
    
    # Now calculate exact distances only for filtered stops (much faster)
    # Use vectorized operations with numpy for speed
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
    
    # Filter by exact radius
    stops_df = stops_df[stops_df['distance'] <= radius_m]
    
    if len(stops_df) == 0:
        return None
    
    # Get nearest
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
    """Load GTFS routes data (cached)."""
    global _gtfs_routes_cache
    if _gtfs_routes_cache is not None:
        return _gtfs_routes_cache
    
    routes_file = os.path.join(GTFS_DIR, "routes.txt")
    if not os.path.exists(routes_file):
        return None
    
    try:
        routes = pd.read_csv(routes_file)
        _gtfs_routes_cache = routes.copy()
        logger.info(f"Loaded {len(_gtfs_routes_cache)} GTFS routes")
        return _gtfs_routes_cache
    except Exception as e:
        logger.error(f"Error loading GTFS routes: {e}")
        return None


def detect_transport_mode(route_name: str, route_type: int) -> str:
    """
    Detect transport mode from route name and type.
    
    BVG uses non-standard route_type values, so we detect from route names:
    - U1-U9 = U-Bahn (subway)
    - S1-S9, RE, RB = S-Bahn/Regional (rail)
    - M, Bus, numbers = Bus
    - Tram = Tram
    """
    if pd.isna(route_name):
        route_name = ""
    route_name = str(route_name).upper().strip()
    
    # U-Bahn detection
    if route_name.startswith('U') and len(route_name) <= 3:
        return 'subway'  # U-Bahn
    
    # S-Bahn detection
    if route_name.startswith('S') and len(route_name) <= 3:
        return 'suburban'  # S-Bahn
    
    # Regional trains
    if route_name.startswith('RE') or route_name.startswith('RB'):
        return 'suburban'  # Regional rail
    
    # Bus detection (M lines, numbered routes, "Bus")
    if route_name.startswith('M') or route_name.startswith('BUS') or route_name.isdigit():
        return 'bus'
    
    # Tram detection
    if 'TRAM' in route_name or route_name.startswith('T'):
        return 'tram'
    
    # Default based on route_type (if standard)
    if route_type == 1:
        return 'subway'
    elif route_type == 2:
        return 'suburban'
    elif route_type == 3:
        return 'bus'
    elif route_type == 0:
        return 'tram'
    
    # Default to bus
    return 'bus'


def get_routes_at_stop(stop_id: str, max_routes: int = 5) -> List[Dict]:
    """
    Get all routes that serve a given stop.
    
    Returns list of routes with their types and names.
    """
    routes_df = load_gtfs_routes()
    if routes_df is None:
        return []
    
    # Load stop_times sample (file is too large to load fully)
    global _gtfs_stop_times_sample
    if _gtfs_stop_times_sample is None:
        stop_times_file = os.path.join(GTFS_DIR, "stop_times.txt")
        if os.path.exists(stop_times_file):
            try:
                # Load larger sample of stop_times (500k rows for better coverage)
                # This is still a sample but covers more stops
                _gtfs_stop_times_sample = pd.read_csv(
                    stop_times_file, 
                    nrows=500000,
                    usecols=['trip_id', 'stop_id', 'stop_sequence']
                )
                logger.info(f"Loaded {len(_gtfs_stop_times_sample)} stop_times sample")
            except Exception as e:
                logger.error(f"Error loading stop_times: {e}")
                return []
        else:
            return []
    
    # Find trips that stop at this stop_id
    # Note: stop_id formats may differ (stops.txt uses ::2, stop_times.txt uses :2:52)
    # Try exact match first
    trips_at_stop = _gtfs_stop_times_sample[
        _gtfs_stop_times_sample['stop_id'] == stop_id
    ]['trip_id'].unique()
    
    # If no exact match, try matching by base stop ID (before platform codes)
    if len(trips_at_stop) == 0:
        # Extract base stop ID (remove platform-specific parts)
        base_stop_id = stop_id.split('::')[0] if '::' in stop_id else stop_id.split(':')[0] + ':' + stop_id.split(':')[1] if ':' in stop_id else stop_id
        trips_at_stop = _gtfs_stop_times_sample[
            _gtfs_stop_times_sample['stop_id'].str.contains(base_stop_id, na=False, regex=False)
        ]['trip_id'].unique()
    
    if len(trips_at_stop) == 0:
        logger.debug(f"No trips found for stop_id: {stop_id}")
        return []
    
    # Load trips to get route_ids
    global _gtfs_trips_cache
    if _gtfs_trips_cache is None:
        trips_file = os.path.join(GTFS_DIR, "trips.txt")
        if os.path.exists(trips_file):
            try:
                _gtfs_trips_cache = pd.read_csv(
                    trips_file,
                    usecols=['route_id', 'trip_id']
                )
                logger.info(f"Loaded {len(_gtfs_trips_cache)} GTFS trips")
            except Exception as e:
                logger.error(f"Error loading trips: {e}")
                return []
        else:
            return []
    
    # Get route_ids for these trips
    route_ids = _gtfs_trips_cache[
        _gtfs_trips_cache['trip_id'].isin(trips_at_stop)
    ]['route_id'].unique()
    
    # Get route details
    route_info = []
    seen_routes = set()
    for route_id in route_ids[:max_routes * 2]:  # Check more to get unique routes
        if route_id in seen_routes:
            continue
        
        route = routes_df[routes_df['route_id'] == route_id]
        if len(route) > 0:
            route = route.iloc[0]
            route_type = route.get('route_type', 3)
            # Get route name - prefer short_name, fallback to long_name
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
    """
    Find a route connecting two stops (simplified pathfinding).
    
    Returns route information if a direct connection exists.
    """
    routes_df = load_gtfs_routes()
    if routes_df is None:
        return None
    
    # Load stop_times sample
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
    
    # Load trips
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
    
    # Find trips that visit both stops
    from_stops = _gtfs_stop_times_sample[_gtfs_stop_times_sample['stop_id'] == from_stop_id]
    to_stops = _gtfs_stop_times_sample[_gtfs_stop_times_sample['stop_id'] == to_stop_id]
    
    if len(from_stops) == 0 or len(to_stops) == 0:
        return None
    
    # Find trips that have both stops in correct order
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
    
    # Get route info for this trip
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
    # Get route name - prefer short_name, fallback to long_name
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
    """
    Get commute information using GTFS data with actual route planning.
    
    This version:
    1. Finds nearest stop to apartment
    2. Finds nearest stop to university
    3. Attempts to find routes connecting them
    4. Calculates transfers and transport types
    
    Parameters:
    -----------
    apartment_lat : float
        Apartment latitude
    apartment_lon : float
        Apartment longitude
    university_lat : float
        University latitude
    university_lon : float
        University longitude
    
    Returns:
    --------
    dict
        Commute information including routes, transfers, and transport types
    """
    # Find nearest stops
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
    
    # Calculate walking time from apartment to nearest stop
    walking_to_stop_distance_m = from_stop.get('distance', 0)
    walking_to_stop_minutes = (walking_to_stop_distance_m / 1000) / 5 * 60  # 5 km/h walking speed
    
    # Calculate walking time from final stop to university
    walking_from_stop_distance_m = to_stop.get('distance', 0)
    walking_from_stop_minutes = (walking_from_stop_distance_m / 1000) / 5 * 60  # 5 km/h walking speed
    
    # Try to find a route between stops
    route_info = find_route_between_stops(from_stop['id'], to_stop['id'])
    
    route_details = []
    modes = []
    transfers = 0
    
    if route_info and route_info.get('name') and route_info['name'].strip():
        # Direct route found
        route_details.append({
            'mode': route_info['mode'],
            'name': route_info['name'],
            'from': from_stop['name'],
            'to': to_stop['name']
        })
        modes.append(route_info['mode'])
    else:
        # No direct route - try to find routes at each stop and estimate transfer
        from_routes = get_routes_at_stop(from_stop['id'], max_routes=10)
        to_routes = get_routes_at_stop(to_stop['id'], max_routes=10)
        
        logger.debug(f"Found {len(from_routes)} routes at from_stop, {len(to_routes)} routes at to_stop")
        
        if from_routes and to_routes:
            # Try to find a route that connects both stops (same route_id)
            direct_route_found = False
            for from_route in from_routes:
                for to_route in to_routes:
                    if from_route['route_id'] == to_route['route_id']:
                        # Same route connects both stops - no transfer needed
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
                # No direct route - need transfer(s)
                # Try to find intermediate stops that might connect routes
                # For now, use first route from start and first route to destination
                from_route = from_routes[0]
                to_route = to_routes[0]
                
                # Always add route details if route has a name
                if from_route.get('name') and from_route['name'].strip():
                    route_details.append({
                        'mode': from_route['mode'],
                        'name': from_route['name'],
                        'from': from_stop['name'],
                        'to': 'Transfer point 1'
                    })
                
                # Check if we can find a connecting route (simplified - just use to_route)
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
                    
                    # Try to find if we need another transfer (check if to_route doesn't reach destination)
                    # This is simplified - a full implementation would check actual route paths
                    # For now, if distance is very large, estimate 2 transfers
                    stop_to_stop_distance = haversine_distance(
                        from_stop['latitude'], from_stop['longitude'],
                        to_stop['latitude'], to_stop['longitude']
                    )
                    if stop_to_stop_distance > 10000:  # More than 10km - likely needs 2 transfers
                        transfers = 2
                        # Add a third route segment (use another route from to_routes if available)
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
            # Only have route from start stop - still show it!
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
            # Only have route to destination stop - show it!
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
            # Fallback: try to get ANY routes from the nearest stop to show something
            if from_routes:
                # Show at least the first route from the nearest stop
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
                # Show at least the first route to the destination stop
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
                # Fallback: use generic transport
                modes = ['public_transport']
                logger.debug(f"No routes found at either stop")
    
    # Calculate transit time between stops
    stop_to_stop_distance = haversine_distance(
        from_stop['latitude'],
        from_stop['longitude'],
        to_stop['latitude'],
        to_stop['longitude']
    )
    
    # Estimate transit time based on distance and transfers
    # Base speed: 30 km/h, add time for transfers (5 min per transfer)
    base_transit_minutes = (stop_to_stop_distance / 1000) / 30 * 60
    transfer_penalty = transfers * 5  # 5 minutes per transfer
    estimated_transit_minutes = base_transit_minutes + transfer_penalty
    
    # Total commute = walk to stop + transit + walk from stop
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
    
    # Debug: Log what we're returning
    logger.debug(f"Returning commute_info with {len(route_details)} route_details: {route_details}")
