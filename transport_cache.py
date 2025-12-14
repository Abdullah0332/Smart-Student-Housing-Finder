"""
BVG API Cache Module
====================

Caches BVG API responses to JSON files to avoid repeated API calls.
This significantly speeds up analysis and reduces API load.

Urban Technology Relevance:
- Caching transport data enables faster iteration and testing
- Reduces dependency on external API availability
- Demonstrates data persistence strategies in urban analytics
"""

import json
import os
import hashlib
from typing import Dict, Optional
import pandas as pd


# Cache directory
CACHE_DIR = "bvg_cache"
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_key(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> str:
    """
    Generate a cache key for a journey request.
    
    Parameters:
    -----------
    from_lat, from_lon : float
        Origin coordinates
    to_lat, to_lon : float
        Destination coordinates
    
    Returns:
    --------
    str
        Cache key (filename)
    """
    # Round coordinates to 6 decimal places for cache key
    key_str = f"{from_lat:.6f}_{from_lon:.6f}_{to_lat:.6f}_{to_lon:.6f}"
    # Create hash for filename
    key_hash = hashlib.md5(key_str.encode()).hexdigest()
    return f"{key_hash}.json"


def get_cache_path(cache_key: str) -> str:
    """Get full path to cache file."""
    return os.path.join(CACHE_DIR, cache_key)


def load_journey_cache(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> Optional[Dict]:
    """
    Load cached journey data if available.
    
    Parameters:
    -----------
    from_lat, from_lon : float
        Origin coordinates
    to_lat, to_lon : float
        Destination coordinates
    
    Returns:
    --------
    dict or None
        Cached journey data if found
    """
    cache_key = get_cache_key(from_lat, from_lon, to_lat, to_lon)
    cache_path = get_cache_path(cache_key)
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cached = json.load(f)
                # Handle both old format (direct data) and new format (with metadata)
                if 'data' in cached:
                    return cached['data']
                return cached
        except:
            return None
    return None


def save_journey_cache(from_lat: float, from_lon: float, to_lat: float, to_lon: float, journey_data: Dict):
    """
    Save journey data to cache.
    
    Parameters:
    -----------
    from_lat, from_lon : float
        Origin coordinates
    to_lat, to_lon : float
        Destination coordinates
    journey_data : dict
        Journey data to cache
    """
    cache_key = get_cache_key(from_lat, from_lon, to_lat, to_lon)
    cache_path = get_cache_path(cache_key)
    
    try:
        # Add metadata
        cache_data = {
            'metadata': {
                'from_latitude': from_lat,
                'from_longitude': from_lon,
                'to_latitude': to_lat,
                'to_longitude': to_lon,
                'cached_at': pd.Timestamp.now().isoformat()
            },
            'data': journey_data
        }
        
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f, indent=2)
        print(f"✓ Saved journey cache: {cache_path}")
        print(f"   Cache file size: {os.path.getsize(cache_path)} bytes")
    except Exception as e:
        print(f"Warning: Could not save journey cache: {e}")


def get_stop_cache_key(lat: float, lon: float, radius: int = 1000) -> str:
    """Generate cache key for stop lookup."""
    key_str = f"stop_{lat:.6f}_{lon:.6f}_{radius}"
    key_hash = hashlib.md5(key_str.encode()).hexdigest()
    return f"{key_hash}.json"


def load_stop_cache(lat: float, lon: float, radius: int = 1000) -> Optional[Dict]:
    """Load cached stop data."""
    cache_key = get_stop_cache_key(lat, lon, radius)
    cache_path = get_cache_path(cache_key)
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cached = json.load(f)
                # Handle both old format (direct data) and new format (with metadata)
                if 'data' in cached:
                    return cached['data']
                return cached
        except:
            return None
    return None


def save_stop_cache(lat: float, lon: float, stop_data: Dict, radius: int = 1000):
    """Save stop data to cache."""
    cache_key = get_stop_cache_key(lat, lon, radius)
    cache_path = get_cache_path(cache_key)
    
    try:
        # Add metadata
        cache_data = {
            'metadata': {
                'latitude': lat,
                'longitude': lon,
                'radius': radius,
                'cached_at': pd.Timestamp.now().isoformat()
            },
            'data': stop_data
        }
        
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f, indent=2)
        print(f"✓ Saved stop cache: {cache_path}")
        print(f"   Cache file size: {os.path.getsize(cache_path)} bytes")
    except Exception as e:
        print(f"Warning: Could not save stop cache: {e}")

