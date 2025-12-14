"""
Transport Module
================

Integrates with BVG (Berlin Public Transport) API to calculate journey times,
find nearest stops, and plan routes. This module enables realistic commute time
calculations using real public transport schedules.

Urban Technology Relevance:
- Public transport accessibility is a key urban mobility metric
- Journey planning APIs provide realistic travel time estimates
- Integration with transit networks enables data-driven housing decisions
- Demonstrates how transport infrastructure affects urban accessibility
"""

import requests
import time
import pandas as pd
from typing import Dict, List, Optional, Tuple
import json
from transport_cache import load_journey_cache, save_journey_cache, load_stop_cache, save_stop_cache


# BVG API base URL (no API key required)
BVG_API_BASE = "https://v6.bvg.transport.rest"


def find_nearest_stop(latitude: float, longitude: float, radius: int = 1000) -> Optional[Dict]:
    """
    Find the nearest BVG public transport stop to given coordinates.
    
    Parameters:
    -----------
    latitude : float
        Latitude coordinate
    longitude : float
        Longitude coordinate
    radius : int
        Search radius in meters (default: 1000m)
    
    Returns:
    --------
    dict or None
        Stop information including name, coordinates, and distance
    """
    # Check cache first
    cached_data = load_stop_cache(latitude, longitude, radius)
    if cached_data:
        stops = cached_data.get('stops', [])
        if stops and len(stops) > 0:
            print(f"  ✓ Using cached stop data: ({latitude:.6f}, {longitude:.6f})")
            nearest = stops[0]
            return {
                'name': nearest.get('name', 'Unknown'),
                'latitude': nearest.get('location', {}).get('latitude'),
                'longitude': nearest.get('location', {}).get('longitude'),
                'distance': nearest.get('distance', 0),
                'id': nearest.get('id', '')
            }
        return None
    
    # Not in cache, make API call
    url = f"{BVG_API_BASE}/stops/nearby"
    
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'radius': radius,
        'results': 5  # Get top 5 nearest stops
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=15)
            
            # Handle 500 errors with retry
            if response.status_code == 500:
                if attempt < max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    # Last attempt failed, return None
                    return None
            
            response.raise_for_status()
            
            stops = response.json()
            
            # Save FULL API response to cache (including raw data)
            save_stop_cache(latitude, longitude, {
                'stops': stops,
                'raw_response': stops  # Save complete raw API response
            }, radius)
            
            if stops and len(stops) > 0:
                # Return the nearest stop
                nearest = stops[0]
                return {
                    'name': nearest.get('name', 'Unknown'),
                    'latitude': nearest.get('location', {}).get('latitude'),
                    'longitude': nearest.get('location', {}).get('longitude'),
                    'distance': nearest.get('distance', 0),
                    'id': nearest.get('id', '')
                }
            
            return None
        
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(1.0 * (attempt + 1))
                continue
            # Don't print error for every failed attempt, only log silently
            return None
    
    return None


def plan_journey(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    departure_time: Optional[str] = None
) -> Optional[Dict]:
    """
    Plan a journey using BVG public transport.
    
    Parameters:
    -----------
    from_lat : float
        Origin latitude
    from_lon : float
        Origin longitude
    to_lat : float
        Destination latitude
    to_lon : float
        Destination longitude
    departure_time : str or None
        Desired departure time (ISO format), None for next available
    
    Returns:
    --------
    dict or None
        Journey information including duration, transfers, and route details
    """
    url = f"{BVG_API_BASE}/journeys"
    
    params = {
        'from.latitude': from_lat,
        'from.longitude': from_lon,
        'to.latitude': to_lat,
        'to.longitude': to_lon,
        'results': 1  # Get best route
    }
    
    if departure_time:
        params['departure'] = departure_time
    
    # Check cache first
    cached_journey = load_journey_cache(from_lat, from_lon, to_lat, to_lon)
    if cached_journey:
        # Reconstruct journey dict from cache
        if cached_journey.get('journey'):
            print(f"  ✓ Using cached journey: ({from_lat:.6f}, {from_lon:.6f}) → ({to_lat:.6f}, {to_lon:.6f})")
            return cached_journey['journey']
        return None
    
    # Not in cache, make API call
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=15)
            
            # Handle 500 errors with retry
            if response.status_code == 500:
                if attempt < max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    # Last attempt failed, return None
                    return None
            
            response.raise_for_status()
            
            data = response.json()
            
            # Save FULL raw API response first
            raw_api_response = data.copy()
            
            if 'journeys' in data and len(data['journeys']) > 0:
                journey = data['journeys'][0]
                
                # Extract journey information
                legs = journey.get('legs', [])
                
                # Calculate total duration (in minutes)
                departure_time_str = journey.get('legs', [{}])[0].get('departure', '')
                arrival_time_str = journey.get('legs', [-1])[-1].get('arrival', '')
                
                duration_minutes = journey.get('duration', 0) // 60  # Convert seconds to minutes
                
                # Count transfers
                transfers = sum(1 for leg in legs if leg.get('transfer') == True)
                
                # Extract transport modes
                modes = []
                for leg in legs:
                    if leg.get('mode') and leg.get('mode') != 'walking':
                        mode = leg.get('mode', 'unknown')
                        if mode not in modes:
                            modes.append(mode)
                    elif leg.get('line'):
                        line_type = leg.get('line', {}).get('product', 'unknown')
                        if line_type not in modes:
                            modes.append(line_type)
                
                # Get line information
                route_details = []
                for leg in legs:
                    if leg.get('line'):
                        line = leg.get('line')
                        route_details.append({
                            'mode': line.get('product', 'unknown'),
                            'name': line.get('name', ''),
                            'from': leg.get('origin', {}).get('name', ''),
                            'to': leg.get('destination', {}).get('name', '')
                        })
                
                journey_result = {
                    'duration_minutes': duration_minutes,
                    'transfers': transfers,
                    'modes': modes,
                    'route_details': route_details,
                    'departure': departure_time_str,
                    'arrival': arrival_time_str,
                    'legs': legs
                }
                
                # Save to cache - include both processed and raw data
                save_journey_cache(from_lat, from_lon, to_lat, to_lon, {
                    'journey': journey_result,
                    'raw_api_response': raw_api_response  # Save complete raw API response
                })
                
                return journey_result
            
            return None
        
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(1.0 * (attempt + 1))
                continue
            # Don't print error for every failed attempt
            return None
    
    return None


def get_commute_info(
    apartment_lat: float,
    apartment_lon: float,
    university_lat: float,
    university_lon: float
) -> Dict:
    """
    Get complete commute information from apartment to university.
    
    This function combines:
    1. Finding nearest stop to apartment
    2. Planning journey from apartment stop to university
    
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
        Complete commute information including walking and transit times
    """
    # Find nearest stop to apartment
    nearest_stop = find_nearest_stop(apartment_lat, apartment_lon)
    
    if not nearest_stop:
        return {
            'error': 'No nearby stop found',
            'nearest_stop': None,
            'journey': None,
            'total_commute_minutes': None,
            'transfers': None,
            'modes': []
        }
    
    # Plan journey from nearest stop to university
    journey = plan_journey(
        nearest_stop['latitude'],
        nearest_stop['longitude'],
        university_lat,
        university_lon
    )
    
    if not journey:
        # Still return stop info even if journey fails
        walking_distance_m = nearest_stop.get('distance', 0)
        walking_time_minutes = (walking_distance_m / 1000) / 5 * 60
        return {
            'error': 'No journey found',
            'nearest_stop': nearest_stop,
            'journey': None,
            'walking_distance_m': walking_distance_m,
            'walking_time_minutes': walking_time_minutes,
            'transit_time_minutes': None,
            'total_commute_minutes': None,
            'transfers': None,
            'modes': []
        }
    
    # Total commute includes walking to stop + transit journey
    # Walking time estimated from distance (assuming 5 km/h walking speed)
    walking_distance_m = nearest_stop.get('distance', 0)
    walking_time_minutes = (walking_distance_m / 1000) / 5 * 60  # Convert to minutes
    
    total_commute = walking_time_minutes + journey['duration_minutes']
    
    return {
        'nearest_stop': nearest_stop,
        'journey': journey,
        'walking_distance_m': walking_distance_m,
        'walking_time_minutes': walking_time_minutes,
        'transit_time_minutes': journey['duration_minutes'],
        'total_commute_minutes': total_commute,
        'transfers': journey['transfers'],
        'modes': journey['modes'],
        'route_details': journey.get('route_details', [])
    }


def batch_get_commute_info(
    apartments_df,
    university_lat: float,
    university_lon: float,
    delay: float = 0.5,
    progress_callback=None
) -> None:
    """
    Batch process commute information for all apartments.
    
    Adds commute information columns to the dataframe in-place.
    
    Parameters:
    -----------
    apartments_df : pd.DataFrame
        Dataframe with 'latitude' and 'longitude' columns
    university_lat : float
        University latitude
    university_lon : float
        University longitude
    delay : float
        Delay between API calls (seconds) to respect rate limits
    """
    print(f"Calculating commute times for {len(apartments_df)} apartments...")
    print("(Using cache when available - much faster!)")
    
    # Initialize columns
    apartments_df['nearest_stop_name'] = None
    apartments_df['nearest_stop_distance_m'] = None
    apartments_df['walking_time_minutes'] = None
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
        
        # Note: We always recalculate to ensure data is fresh, but cache speeds it up
        
        commute_info = get_commute_info(
            row['latitude'],
            row['longitude'],
            university_lat,
            university_lon
        )
        
        if commute_info.get('nearest_stop'):
            apartments_df.at[idx, 'nearest_stop_name'] = commute_info['nearest_stop']['name']
            apartments_df.at[idx, 'nearest_stop_distance_m'] = commute_info.get('walking_distance_m', 0)
            apartments_df.at[idx, 'walking_time_minutes'] = commute_info.get('walking_time_minutes', 0)
            
            if commute_info.get('journey'):
                apartments_df.at[idx, 'transit_time_minutes'] = commute_info['transit_time_minutes']
                apartments_df.at[idx, 'total_commute_minutes'] = commute_info['total_commute_minutes']
                apartments_df.at[idx, 'transfers'] = commute_info['transfers']
                apartments_df.at[idx, 'transport_modes'] = ', '.join(commute_info['modes'])
                
                # Store route details as JSON string for display
                if commute_info.get('route_details'):
                    try:
                        apartments_df.at[idx, 'route_details'] = json.dumps(commute_info['route_details'])
                    except:
                        apartments_df.at[idx, 'route_details'] = None
                else:
                    apartments_df.at[idx, 'route_details'] = None
                
                new_count += 1
            else:
                # Has stop but no journey - still set walking time
                apartments_df.at[idx, 'transit_time_minutes'] = None
                apartments_df.at[idx, 'total_commute_minutes'] = commute_info.get('walking_time_minutes', 0)
                apartments_df.at[idx, 'transfers'] = None
                apartments_df.at[idx, 'transport_modes'] = None
                apartments_df.at[idx, 'route_details'] = None
                cached_count += 1
        
        processed_count += 1
        
        # Progress indicator
        if progress_callback:
            progress_callback(processed_count, len(apartments_df), cached_count, new_count)
        elif processed_count % 10 == 0:
            successful = apartments_df['total_commute_minutes'].notna().sum()
            print(f"  Processed {processed_count}/{len(apartments_df)} ({successful} successful)")
        
        # Rate limiting - only delay if we made new API calls
        # Cache is checked inside get_commute_info, so we delay for all to be safe
        time.sleep(delay * 0.3)  # Reduced delay since cache speeds things up

