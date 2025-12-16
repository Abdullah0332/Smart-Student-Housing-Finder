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
from logger_config import setup_logger

# Set up logger for this module
logger = setup_logger("transport")

# Try to import GTFS helper
try:
    from gtfs_helper import get_gtfs_commute_info, find_nearest_gtfs_stop
    GTFS_AVAILABLE = True
    logger.info("GTFS helper loaded successfully - will use as fallback")
except ImportError as e:
    GTFS_AVAILABLE = False
    logger.warning(f"GTFS helper not available - will use BVG API only: {e}")


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
        # Handle both old format (direct stops list) and new format (with 'stops' key)
        if isinstance(cached_data, list):
            stops = cached_data
        elif isinstance(cached_data, dict):
            # Check if it's wrapped in 'data' key (new format with metadata)
            if 'data' in cached_data:
                stops_data = cached_data['data']
                if isinstance(stops_data, list):
                    stops = stops_data
                else:
                    stops = stops_data.get('stops', [])
            else:
                stops = cached_data.get('stops', [])
        else:
            stops = []
        
        if stops and len(stops) > 0:
            logger.debug(f"Using cached stop data: ({latitude:.6f}, {longitude:.6f}) [CACHE HIT]")
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
            
            # ALWAYS save API response to cache (even if empty) to avoid repeated API calls
            # Save FULL API response to cache (including raw data)
            cache_data = {
                'stops': stops if stops else [],
                'raw_response': stops if stops else []  # Save complete raw API response
            }
            try:
                save_stop_cache(latitude, longitude, cache_data, radius)
                if stops and len(stops) > 0:
                    logger.info(f"Saved stop data to cache for ({latitude:.6f}, {longitude:.6f}) - {len(stops)} stops found")
                else:
                    logger.info(f"Cached 'no stops found' result for ({latitude:.6f}, {longitude:.6f})")
            except Exception as e:
                logger.error(f"ERROR saving stop cache: {e}")
                import traceback
                logger.error(traceback.format_exc())
            else:
                # Verify cache was saved
                import os
                from transport_cache import get_stop_cache_key, get_cache_path
                cache_key = get_stop_cache_key(latitude, longitude, radius)
                cache_path = get_cache_path(cache_key)
                if os.path.exists(cache_path):
                    size = os.path.getsize(cache_path)
                    logger.debug(f"Verified stop cache file exists: {cache_path} ({size} bytes)")
                else:
                    logger.warning(f"Stop cache file not found after save: {cache_path}")
            
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
        # Handle both old format (direct journey) and new format (with 'journey' key)
        if isinstance(cached_journey, dict):
            # New format with metadata wrapper
            if 'data' in cached_journey:
                journey_data = cached_journey['data']
                if isinstance(journey_data, dict):
                    if journey_data.get('journey'):
                        logger.debug(f"Using cached journey (with metadata): ({from_lat:.6f}, {from_lon:.6f}) → ({to_lat:.6f}, {to_lon:.6f})")
                        return journey_data['journey']
                    elif 'duration_minutes' in journey_data:
                        logger.debug(f"Using cached journey (data wrapper): ({from_lat:.6f}, {from_lon:.6f}) → ({to_lat:.6f}, {to_lon:.6f})")
                        return journey_data
            # Direct format with 'journey' key
            elif cached_journey.get('journey'):
                logger.debug(f"Using cached journey: ({from_lat:.6f}, {from_lon:.6f}) → ({to_lat:.6f}, {to_lon:.6f})")
                return cached_journey['journey']
            # Old format: direct journey data
            elif 'duration_minutes' in cached_journey:
                logger.debug(f"Using cached journey (old format): ({from_lat:.6f}, {from_lon:.6f}) → ({to_lat:.6f}, {to_lon:.6f})")
                return cached_journey
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
                cache_data = {
                    'journey': journey_result,
                    'raw_api_response': raw_api_response  # Save complete raw API response
                }
                try:
                    save_journey_cache(from_lat, from_lon, to_lat, to_lon, cache_data)
                    logger.info(f"Saved journey data to cache: ({from_lat:.6f}, {from_lon:.6f}) → ({to_lat:.6f}, {to_lon:.6f})")
                except Exception as e:
                    logger.error(f"ERROR saving journey cache: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                else:
                    # Verify cache was saved
                    import os
                    from transport_cache import get_cache_key, get_cache_path
                    cache_key = get_cache_key(from_lat, from_lon, to_lat, to_lon)
                    cache_path = get_cache_path(cache_key)
                    if os.path.exists(cache_path):
                        size = os.path.getsize(cache_path)
                        logger.debug(f"Verified cache file exists: {cache_path} ({size} bytes)")
                    else:
                        logger.warning(f"Cache file not found after save: {cache_path}")
                
                return journey_result
            else:
                # No journeys found - ALWAYS cache this result to avoid repeated API calls
                no_journey_result = {
                    'journey': None,
                    'no_journey_found': True,
                    'raw_api_response': raw_api_response
                }
                try:
                    save_journey_cache(from_lat, from_lon, to_lat, to_lon, no_journey_result)
                    logger.info(f"Cached 'no journey found' result: ({from_lat:.6f}, {from_lon:.6f}) → ({to_lat:.6f}, {to_lon:.6f})")
                except Exception as e:
                    logger.error(f"ERROR saving 'no journey' cache: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                else:
                    # Verify cache was saved
                    import os
                    from transport_cache import get_cache_key, get_cache_path
                    cache_key = get_cache_key(from_lat, from_lon, to_lat, to_lon)
                    cache_path = get_cache_path(cache_key)
                    if os.path.exists(cache_path):
                        size = os.path.getsize(cache_path)
                        logger.debug(f"Verified 'no journey' cache file exists: {cache_path} ({size} bytes)")
                    else:
                        logger.warning(f"'No journey' cache file not found after save: {cache_path}")
            
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
    Get complete commute information from apartment to university using GTFS data.
    
    This function uses local GTFS data for fast, offline route planning.
    
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
    # Use GTFS data directly (no API calls)
    if not GTFS_AVAILABLE:
        logger.error("GTFS data not available")
        return {
            'error': 'GTFS data not available',
            'nearest_stop': None,
            'journey': None,
            'total_commute_minutes': None,
            'transfers': None,
            'modes': [],
            'walking_distance_m': None,
            'walking_time_minutes': None
        }
    
    # Get commute info from GTFS
    return get_gtfs_commute_info(apartment_lat, apartment_lon, university_lat, university_lon)


def batch_get_commute_info(
    apartments_df,
    university_lat: float,
    university_lon: float,
    delay: float = 0.0,  # No delay needed for GTFS (local data)
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
    logger.info(f"Calculating commute times for {len(apartments_df)} apartments...")
    logger.info("(Using cache when available - much faster!)")
    
    # Initialize columns
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
        
        # Note: We always recalculate to ensure data is fresh, but cache speeds it up
        
        commute_info = get_commute_info(
            row['latitude'],
            row['longitude'],
            university_lat,
            university_lon
        )
        
        # Always try to populate stop info if available
        if commute_info.get('nearest_stop'):
            apartments_df.at[idx, 'nearest_stop_name'] = commute_info['nearest_stop']['name']
            apartments_df.at[idx, 'nearest_stop_distance_m'] = commute_info.get('walking_distance_m', commute_info['nearest_stop'].get('distance', 0))
            apartments_df.at[idx, 'walking_time_minutes'] = commute_info.get('walking_time_minutes', 0)
            
            # Add final stop and walking from stop info
            if commute_info.get('final_stop'):
                apartments_df.at[idx, 'final_stop_name'] = commute_info['final_stop']['name']
                apartments_df.at[idx, 'final_stop_distance_m'] = commute_info.get('walking_from_stop_distance_m', commute_info['final_stop'].get('distance', 0))
                apartments_df.at[idx, 'walking_from_stop_minutes'] = commute_info.get('walking_from_stop_minutes', 0)
            else:
                apartments_df.at[idx, 'final_stop_name'] = None
                apartments_df.at[idx, 'final_stop_distance_m'] = None
                apartments_df.at[idx, 'walking_from_stop_minutes'] = None
            
            # Store route details FIRST (even if no journey) - route_details come from commute_info directly
            if commute_info.get('route_details'):
                try:
                    apartments_df.at[idx, 'route_details'] = json.dumps(commute_info['route_details'])
                    logger.debug(f"Stored route_details for apartment {idx}: {commute_info['route_details']}")
                except Exception as e:
                    logger.error(f"Error storing route_details: {e}")
                    apartments_df.at[idx, 'route_details'] = None
            else:
                apartments_df.at[idx, 'route_details'] = None
                logger.debug(f"No route_details for apartment {idx}")
            
            if commute_info.get('journey'):
                journey = commute_info['journey']
                apartments_df.at[idx, 'transit_time_minutes'] = commute_info.get('transit_time_minutes', journey.get('duration_minutes', 0))
                apartments_df.at[idx, 'total_commute_minutes'] = commute_info.get('total_commute_minutes', 0)
                apartments_df.at[idx, 'transfers'] = commute_info.get('transfers', journey.get('transfers', 0))
                
                # Transport modes
                modes = commute_info.get('modes', journey.get('modes', []))
                if modes:
                    apartments_df.at[idx, 'transport_modes'] = ', '.join(modes) if isinstance(modes, list) else str(modes)
                else:
                    apartments_df.at[idx, 'transport_modes'] = 'public_transport'  # Default if unknown
                
                # Store journey data with departure/arrival times for popup display
                journey_data = {
                    'departure': journey.get('departure', ''),
                    'arrival': journey.get('arrival', ''),
                    'duration_minutes': journey.get('duration_minutes', 0),
                    'transfers': journey.get('transfers', 0)
                }
                apartments_df.at[idx, 'journey'] = json.dumps(journey_data)
                
                new_count += 1
            else:
                # Has stop but no journey - still set walking time and basic info
                apartments_df.at[idx, 'transit_time_minutes'] = None
                apartments_df.at[idx, 'total_commute_minutes'] = commute_info.get('walking_time_minutes', commute_info.get('total_commute_minutes', 0))
                apartments_df.at[idx, 'transfers'] = commute_info.get('transfers', None)
                
                # Still try to get transport modes and route details from commute_info (even without journey)
                modes = commute_info.get('modes', [])
                if modes:
                    apartments_df.at[idx, 'transport_modes'] = ', '.join(modes) if isinstance(modes, list) else str(modes)
                else:
                    apartments_df.at[idx, 'transport_modes'] = None
                
                # Store route details even if no journey (route_details come from commute_info, not journey)
                if commute_info.get('route_details'):
                    try:
                        apartments_df.at[idx, 'route_details'] = json.dumps(commute_info['route_details'])
                        logger.debug(f"Stored route_details (no journey) for apartment {idx}: {commute_info['route_details']}")
                    except Exception as e:
                        logger.error(f"Error storing route_details (no journey): {e}")
                        apartments_df.at[idx, 'route_details'] = None
                else:
                    apartments_df.at[idx, 'route_details'] = None
                
                # Still count as processed (we have stop info)
                cached_count += 1
        else:
            # No stop found - mark as failed but don't break
            logger.warning(f"No stop found for apartment at ({row['latitude']:.6f}, {row['longitude']:.6f})")
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
        
        # Progress indicator
        if progress_callback:
            progress_callback(processed_count, len(apartments_df), cached_count, new_count)
        elif processed_count % 10 == 0:
            successful = apartments_df['total_commute_minutes'].notna().sum()
            logger.debug(f"Processed {processed_count}/{len(apartments_df)} ({successful} successful)")
        
        # No delay needed for GTFS (local data, very fast)
        # time.sleep removed for maximum speed

