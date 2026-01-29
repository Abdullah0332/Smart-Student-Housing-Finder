"""
Walkability and Mobility Analysis Module
Uses OpenStreetMap (OSM) data to calculate location-specific walkability and mobility metrics.
"""
import time
import requests
from typing import Dict, List, Optional
from math import radians, cos, sin, asin, sqrt

import pandas as pd
import numpy as np

from config.settings import TRANSPORT


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371000 * c


def query_overpass_api(query: str, timeout: int = 25) -> Optional[Dict]:
    """
    Query Overpass API (OpenStreetMap data) with rate limiting.
    """
    url = "https://overpass-api.de/api/interpreter"
    
    try:
        response = requests.post(url, data={'data': query}, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Overpass API error: {e}")
        return None


def get_pois_within_radius(
    latitude: float,
    longitude: float,
    radius_m: int = 500,
    poi_types: Optional[List[str]] = None
) -> Dict:
    """
    Get Points of Interest (POIs) within radius using Overpass API.
    
    Args:
        latitude: Location latitude
        longitude: Location longitude
        radius_m: Search radius in meters
        poi_types: List of POI types to search for
        
    Returns:
        Dictionary with POI counts and distances
    """
    if poi_types is None:
        poi_types = ['supermarket', 'restaurant', 'cafe', 'gym', 'pharmacy', 'bank', 'library', 'bar']
    
    query = f"""
    [out:json][timeout:25];
    (
        node["shop"="supermarket"](around:{radius_m},{latitude},{longitude});
        way["shop"="supermarket"](around:{radius_m},{latitude},{longitude});
        relation["shop"="supermarket"](around:{radius_m},{latitude},{longitude});
        
        node["amenity"="restaurant"](around:{radius_m},{latitude},{longitude});
        way["amenity"="restaurant"](around:{radius_m},{latitude},{longitude});
        
        node["amenity"="cafe"](around:{radius_m},{latitude},{longitude});
        way["amenity"="cafe"](around:{radius_m},{latitude},{longitude});
        
        node["leisure"="fitness_centre"](around:{radius_m},{latitude},{longitude});
        node["amenity"="gym"](around:{radius_m},{latitude},{longitude});
        way["leisure"="fitness_centre"](around:{radius_m},{latitude},{longitude});
        
        node["amenity"="pharmacy"](around:{radius_m},{latitude},{longitude});
        way["amenity"="pharmacy"](around:{radius_m},{latitude},{longitude});
        
        node["amenity"="bank"](around:{radius_m},{latitude},{longitude});
        way["amenity"="bank"](around:{radius_m},{latitude},{longitude});
        
        node["amenity"="library"](around:{radius_m},{latitude},{longitude});
        way["amenity"="library"](around:{radius_m},{latitude},{longitude});
        
        node["amenity"="bar"](around:{radius_m},{latitude},{longitude});
        way["amenity"="bar"](around:{radius_m},{latitude},{longitude});
    );
    out body;
    """
    
    result = query_overpass_api(query)
    if not result or 'elements' not in result:
        return {
            'grocery_stores_500m': 0,
            'restaurants_500m': 0,
            'cafes_500m': 0,
            'gyms_500m': 0,
            'pharmacies_500m': 0,
            'banks_500m': 0,
            'libraries_500m': 0,
            'bars_500m': 0,
            'total_pois_500m': 0,
            'nearest_grocery_m': None,
            'nearest_cafe_m': None,
            'nearest_gym_m': None
        }
    
    elements = result['elements']
    
    grocery_stores = []
    restaurants = []
    cafes = []
    gyms = []
    pharmacies = []
    banks = []
    libraries = []
    bars = []
    
    for element in elements:
        if 'lat' not in element or 'lon' not in element:
            if 'center' in element:
                lat = element['center']['lat']
                lon = element['center']['lon']
            else:
                continue
        else:
            lat = element['lat']
            lon = element['lon']
        
        tags = element.get('tags', {})
        distance = haversine_distance(latitude, longitude, lat, lon)
        
        if tags.get('shop') == 'supermarket':
            grocery_stores.append(distance)
        elif tags.get('amenity') == 'restaurant':
            restaurants.append(distance)
        elif tags.get('amenity') == 'cafe':
            cafes.append(distance)
        elif tags.get('leisure') == 'fitness_centre' or tags.get('amenity') == 'gym':
            gyms.append(distance)
        elif tags.get('amenity') == 'pharmacy':
            pharmacies.append(distance)
        elif tags.get('amenity') == 'bank':
            banks.append(distance)
        elif tags.get('amenity') == 'library':
            libraries.append(distance)
        elif tags.get('amenity') == 'bar':
            bars.append(distance)
    
    nearest_grocery = min(grocery_stores) if grocery_stores else None
    nearest_cafe = min(cafes) if cafes else None
    nearest_gym = min(gyms) if gyms else None
    
    total_pois = (
        len(grocery_stores) + len(restaurants) + len(cafes) + 
        len(gyms) + len(pharmacies) + len(banks) + len(libraries) + len(bars)
    )
    
    return {
        'grocery_stores_500m': len(grocery_stores),
        'restaurants_500m': len(restaurants),
        'cafes_500m': len(cafes),
        'gyms_500m': len(gyms),
        'pharmacies_500m': len(pharmacies),
        'banks_500m': len(banks),
        'libraries_500m': len(libraries),
        'bars_500m': len(bars),
        'total_pois_500m': total_pois,
        'nearest_grocery_m': int(nearest_grocery) if nearest_grocery else None,
        'nearest_cafe_m': int(nearest_cafe) if nearest_cafe else None,
        'nearest_gym_m': int(nearest_gym) if nearest_gym else None
    }


def get_bike_infrastructure(
    latitude: float,
    longitude: float,
    radius_m: int = 1000
) -> Dict:
    """
    Get bike infrastructure (bike lanes, bike share stations) within radius.
    
    Args:
        latitude: Location latitude
        longitude: Location longitude
        radius_m: Search radius in meters
        
    Returns:
        Dictionary with bike infrastructure metrics
    """
    query = f"""
    [out:json][timeout:25];
    (
        way["highway"="cycleway"](around:{radius_m},{latitude},{longitude});
        way["cycleway"](around:{radius_m},{latitude},{longitude});
        way["bicycle"="designated"](around:{radius_m},{latitude},{longitude});
        
        node["amenity"="bicycle_rental"](around:{radius_m},{latitude},{longitude});
        node["amenity"="bicycle_parking"](around:{radius_m},{latitude},{longitude});
    );
    out body;
    """
    
    result = query_overpass_api(query)
    if not result or 'elements' not in result:
        return {
            'bike_lanes_1000m': 0,
            'bike_share_stations_1000m': 0,
            'nearest_bike_lane_m': None,
            'nearest_bike_share_m': None,
            'bike_accessibility_score': 0
        }
    
    elements = result['elements']
    
    bike_lanes = []
    bike_share_stations = []
    
    for element in elements:
        if 'lat' not in element or 'lon' not in element:
            if 'center' in element:
                lat = element['center']['lat']
                lon = element['center']['lon']
            else:
                continue
        else:
            lat = element['lat']
            lon = element['lon']
        
        distance = haversine_distance(latitude, longitude, lat, lon)
        tags = element.get('tags', {})
        
        if element['type'] == 'way' and (
            tags.get('highway') == 'cycleway' or 
            tags.get('cycleway') or 
            tags.get('bicycle') == 'designated'
        ):
            bike_lanes.append(distance)
        elif tags.get('amenity') == 'bicycle_rental':
            bike_share_stations.append(distance)
    
    nearest_bike_lane = min(bike_lanes) if bike_lanes else None
    nearest_bike_share = min(bike_share_stations) if bike_share_stations else None
    
    bike_score = 0
    if nearest_bike_lane:
        if nearest_bike_lane <= 100:
            bike_score += 40
        elif nearest_bike_lane <= 300:
            bike_score += 30
        elif nearest_bike_lane <= 500:
            bike_score += 20
        elif nearest_bike_lane <= 1000:
            bike_score += 10
    
    if nearest_bike_share:
        if nearest_bike_share <= 200:
            bike_score += 30
        elif nearest_bike_share <= 500:
            bike_score += 20
        elif nearest_bike_share <= 1000:
            bike_score += 10
    
    bike_score = min(100, bike_score)
    
    return {
        'bike_lanes_1000m': len(bike_lanes),
        'bike_share_stations_1000m': len(bike_share_stations),
        'nearest_bike_lane_m': int(nearest_bike_lane) if nearest_bike_lane else None,
        'nearest_bike_share_m': int(nearest_bike_share) if nearest_bike_share else None,
        'bike_accessibility_score': bike_score
    }


def calculate_walkability_score(
    latitude: float,
    longitude: float,
    poi_data: Dict,
    bike_data: Dict,
    walking_distance_to_stop: Optional[float] = None
) -> Dict:
    """
    Calculate composite walkability score (0-100) based on multiple factors.
    
    Args:
        latitude: Location latitude
        longitude: Location longitude
        poi_data: POI data from get_pois_within_radius
        bike_data: Bike infrastructure data from get_bike_infrastructure
        walking_distance_to_stop: Distance to nearest transit stop in meters
        
    Returns:
        Dictionary with walkability score and breakdown
    """
    score = 0
    max_score = 100
    
    total_pois = poi_data.get('total_pois_500m', 0)
    if total_pois >= 20:
        poi_score = 40
    elif total_pois >= 15:
        poi_score = 35
    elif total_pois >= 10:
        poi_score = 30
    elif total_pois >= 5:
        poi_score = 20
    elif total_pois >= 3:
        poi_score = 10
    else:
        poi_score = 0
    
    score += poi_score
    
    essential_score = 0
    if poi_data.get('grocery_stores_500m', 0) >= 2:
        essential_score += 10
    elif poi_data.get('grocery_stores_500m', 0) >= 1:
        essential_score += 5
    
    if poi_data.get('pharmacies_500m', 0) >= 1:
        essential_score += 5
    
    if poi_data.get('banks_500m', 0) >= 1:
        essential_score += 5
    
    if poi_data.get('cafes_500m', 0) >= 3:
        essential_score += 10
    elif poi_data.get('cafes_500m', 0) >= 1:
        essential_score += 5
    
    score += essential_score
    
    if walking_distance_to_stop:
        if walking_distance_to_stop <= 200:
            transit_score = 20
        elif walking_distance_to_stop <= 400:
            transit_score = 15
        elif walking_distance_to_stop <= 600:
            transit_score = 10
        elif walking_distance_to_stop <= 1000:
            transit_score = 5
        else:
            transit_score = 0
        score += transit_score
    
    bike_score = bike_data.get('bike_accessibility_score', 0) / 10
    score += bike_score
    
    score = min(100, max(0, score))
    
    return {
        'walkability_score': int(score),
        'poi_density_score': poi_score,
        'essential_services_score': essential_score,
        'transit_accessibility_score': transit_score if walking_distance_to_stop else 0,
        'bike_contribution_score': bike_score
    }


def get_walkability_mobility_info(
    latitude: float,
    longitude: float,
    walking_distance_to_stop: Optional[float] = None,
    delay: float = 0.5
) -> Dict:
    """
    Get comprehensive walkability and mobility information for a location.
    
    Args:
        latitude: Location latitude
        longitude: Location longitude
        walking_distance_to_stop: Distance to nearest transit stop in meters
        delay: Delay between API calls (rate limiting)
        
    Returns:
        Complete walkability and mobility metrics dictionary
    """
    time.sleep(delay)
    
    poi_data = get_pois_within_radius(latitude, longitude, radius_m=500)
    
    time.sleep(delay)
    
    bike_data = get_bike_infrastructure(latitude, longitude, radius_m=1000)
    
    walkability = calculate_walkability_score(
        latitude, longitude, poi_data, bike_data, walking_distance_to_stop
    )
    
    result = {
        **poi_data,
        **bike_data,
        **walkability
    }
    
    return result


def batch_get_walkability_info(
    apartments_df: pd.DataFrame,
    delay: float = 1.0,
    progress_callback: Optional[callable] = None
) -> None:
    """
    Batch process walkability and mobility metrics for all apartments.
    
    Args:
        apartments_df: DataFrame with 'latitude' and 'longitude' columns
        delay: Delay between API calls (rate limiting)
        progress_callback: Optional callback function(processed, total)
    """
    walkability_columns = [
        'grocery_stores_500m', 'restaurants_500m', 'cafes_500m', 'gyms_500m',
        'pharmacies_500m', 'banks_500m', 'libraries_500m', 'bars_500m',
        'total_pois_500m', 'nearest_grocery_m', 'nearest_cafe_m', 'nearest_gym_m',
        'bike_lanes_1000m', 'bike_share_stations_1000m', 'nearest_bike_lane_m',
        'nearest_bike_share_m', 'bike_accessibility_score',
        'walkability_score', 'poi_density_score', 'essential_services_score',
        'transit_accessibility_score', 'bike_contribution_score'
    ]
    
    for col in walkability_columns:
        if col not in apartments_df.columns:
            apartments_df[col] = None
    
    processed = 0
    total = len(apartments_df)
    
    for idx, row in apartments_df.iterrows():
        if pd.isna(row.get('latitude')) or pd.isna(row.get('longitude')):
            continue
        
        try:
            walking_dist = row.get('nearest_stop_distance_m')
            if pd.isna(walking_dist):
                walking_dist = None
            
            walkability_info = get_walkability_mobility_info(
                row['latitude'],
                row['longitude'],
                walking_distance_to_stop=walking_dist,
                delay=delay
            )
            
            for key, value in walkability_info.items():
                if key in apartments_df.columns:
                    apartments_df.at[idx, key] = value
            
            processed += 1
            
            if progress_callback:
                progress_callback(processed, total)
                
        except Exception as e:
            print(f"Error processing walkability for row {idx}: {e}")
            continue
