"""
Geocoding Module
================

Converts street addresses to geographic coordinates (latitude, longitude) using
Nominatim (OpenStreetMap's geocoding service). This is essential for spatial analysis
and integration with transport networks.

Urban Technology Relevance:
- Geocoding enables spatial analysis and visualization
- Coordinates are required for distance calculations and network analysis
- Address-to-coordinates conversion is fundamental to location-based services
"""

import time
import requests
import pandas as pd
import json
import os
from typing import Tuple, Optional, Dict
import geopy.geocoders
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


# Cache file for geocoding results
GEOCODE_CACHE_FILE = "geocode_cache.json"

def load_geocode_cache() -> Dict[str, Tuple[float, float]]:
    """Load geocoding cache from file."""
    if os.path.exists(GEOCODE_CACHE_FILE):
        try:
            with open(GEOCODE_CACHE_FILE, 'r') as f:
                cache = json.load(f)
                # Convert list values back to tuples
                return {k: tuple(v) for k, v in cache.items()}
        except:
            return {}
    return {}

def save_geocode_cache(cache: Dict[str, Tuple[float, float]]):
    """Save geocoding cache to file."""
    try:
        # Convert tuples to lists for JSON serialization
        cache_serializable = {k: list(v) for k, v in cache.items()}
        with open(GEOCODE_CACHE_FILE, 'w') as f:
            json.dump(cache_serializable, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save geocode cache: {e}")

# Global cache
_geocode_cache = None

def get_geocode_cache() -> Dict[str, Tuple[float, float]]:
    """Get or load geocoding cache."""
    global _geocode_cache
    if _geocode_cache is None:
        _geocode_cache = load_geocode_cache()
    return _geocode_cache


def geocode_address(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    """
    Geocode a single address to latitude and longitude using Nominatim.
    Tries multiple address variations if initial geocoding fails.
    
    Parameters:
    -----------
    address : str
        Street address to geocode
    max_retries : int
        Maximum number of retry attempts
    delay : float
        Delay between requests (seconds) to respect rate limits
    
    Returns:
    --------
    Tuple[float, float] or None
        (latitude, longitude) if successful, None otherwise
    """
    # Clean and normalize address with comprehensive regex patterns
    import re
    address_clean = str(address).strip()
    
    # Remove newlines, carriage returns, tabs
    address_clean = re.sub(r'[\n\r\t]+', ' ', address_clean)
    
    # Fix "BerlinGermany" -> "Berlin, Germany" (multiple variations)
    address_clean = re.sub(r'BerlinGermany', 'Berlin, Germany', address_clean)
    address_clean = re.sub(r'Berlin\s+Germany', 'Berlin, Germany', address_clean)
    address_clean = re.sub(r'Berlin\s*,?\s*Germany', 'Berlin, Germany', address_clean)
    
    # Remove provider names and unwanted text (case-insensitive)
    address_clean = re.sub(r'THE\s+URBAN\s+CLUB', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'URBAN\s+CLUB', '', address_clean, flags=re.IGNORECASE)
    
    # Remove "Plönzeile" variations
    address_clean = re.sub(r'-\s*Pl[öo]n?zeile', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'Pl[öo]n?zeile\s*', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'\s*Pl[öo]n?zeile', '', address_clean, flags=re.IGNORECASE)
    
    # Remove common apartment name patterns BUT preserve location names
    # Don't remove if it's part of a location name (e.g., "FRANKFURTER TOR" should stay)
    # Only remove if it's clearly an apartment descriptor
    if not re.search(r'BERLIN\s+[A-ZÄÖÜ\s\-]+(?:Classic|Long|Term|Balcony|Silver|Neon)', address_clean, re.IGNORECASE):
        # Not an apartment name pattern, safe to remove descriptors
        address_clean = re.sub(r'\s*(?:Classic|Long|Term|Balcony|Silver|Neon)\s*\d*', '', address_clean, flags=re.IGNORECASE)
    
    # Fix postal code formats
    address_clean = re.sub(r',\s*(\d{5})', r', \1', address_clean)
    address_clean = re.sub(r'(\d{5})\s*Berlin', r'\1 Berlin', address_clean)
    
    # Remove multiple consecutive spaces
    address_clean = re.sub(r'\s+', ' ', address_clean).strip()
    
    # Remove leading/trailing commas
    address_clean = re.sub(r'^,\s*', '', address_clean)
    address_clean = re.sub(r'\s*,+$', '', address_clean)
    address_clean = re.sub(r',\s*,+', ',', address_clean)
    
    # Handle addresses with wrong city (like "Heinrich-Heine-Straße 0,8, Hamburg, Berlin, Germany")
    if 'Hamburg' in address_clean and 'Berlin' in address_clean:
        # Extract street name and use it with Berlin
        street_match = re.search(r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|weg|Weg|platz|Platz|allee|Allee|str\.?))', address_clean, re.IGNORECASE)
        if street_match:
            street_name = street_match.group(1).strip()
            # Remove "0,8" or similar house number issues
            street_name = re.sub(r'\s*0[,\.]\d+', '', street_name).strip()
            address_clean = f"{street_name}, Berlin, Germany"
            print(f"  Fixed address with wrong city: {street_name}, Berlin, Germany")
        else:
            # Just remove Hamburg
            address_clean = re.sub(r'Hamburg,?', '', address_clean, flags=re.IGNORECASE)
            address_clean = re.sub(r'\s+', ' ', address_clean).strip()
            print(f"  Removed Hamburg from address")
    
    # Try multiple address variations
    address_variations = []
    
    # Handle addresses with Hamburg (wrong city) - add variations
    if 'Hamburg' in address_clean or 'Heinrich-Heine' in address_clean:
        # Extract street name
        street_match = re.search(r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|weg|Weg|platz|Platz|allee|Allee))', address_clean, re.IGNORECASE)
        if street_match:
            street_name = street_match.group(1).strip()
            street_name = re.sub(r'\s*0[,\.]\d+', '', street_name).strip()
            address_variations.append(f"{street_name}, Berlin, Germany")
            # Also try common Berlin districts with this street name
            address_variations.append("Heinrich-Heine-Straße, Berlin, Germany")
            address_variations.append("Heinrich-Heine-Straße, Mitte, Berlin, Germany")
    
    # Handle apartment name addresses (like "BERLIN MITTE-WEDDING Classic Long Term 1")
    # Also handle addresses that are just location names (like "BERLIN FRANKFURTER TOR, Germany")
    location_match = re.search(r'BERLIN\s+([A-ZÄÖÜ][A-ZÄÖÜ\s\-]+?)(?:\s+(?:Classic|Long|Term|Balcony|Silver|Neon|Premium|Standard))', address_clean, re.IGNORECASE)
    
    # Also check if address is just "BERLIN [LOCATION], Germany" pattern (without apartment descriptors)
    location_match_simple = re.search(r'BERLIN\s+([A-ZÄÖÜ][A-ZÄÖÜ\s\-]+?)(?:,?\s+Germany)?$', address_clean, re.IGNORECASE)
    
    if location_match:
        location_name = location_match.group(1).strip()
        location_name = re.sub(r'\s+', ' ', location_name).strip()
    elif location_match_simple:
        location_name = location_match_simple.group(1).strip()
        location_name = re.sub(r'\s+', ' ', location_name).strip()
    else:
        location_name = None
    
    if location_name:
        # Convert to title case for better geocoding (e.g., "FRANKFURTER TOR" -> "Frankfurter Tor")
        location_name_title = location_name.title()
        
        # Special handling for "FRANKFURTER TOR" - try this FIRST as it's a known location
        if re.search(r'FRANKFURTER\s+TOR', location_name, re.IGNORECASE):
            # Try "Frankfurter Tor" variations first (most likely to work)
            if "Frankfurter Tor, Berlin, Germany" not in address_variations:
                address_variations.insert(0, "Frankfurter Tor, Berlin, Germany")  # Try FIRST
            if "Frankfurter Tor, Friedrichshain, Berlin, Germany" not in address_variations:
                address_variations.insert(1, "Frankfurter Tor, Friedrichshain, Berlin, Germany")
            if "Frankfurter Allee, Berlin, Germany" not in address_variations:
                address_variations.insert(2, "Frankfurter Allee, Berlin, Germany")
            # Also try without "Berlin, Germany" - sometimes just the place name works
            if "Frankfurter Tor" not in address_variations:
                address_variations.insert(3, "Frankfurter Tor")
        
        # Try location name in title case first
        if f"{location_name_title}, Berlin, Germany" not in address_variations:
            address_variations.append(f"{location_name_title}, Berlin, Germany")
        
        # Also try without "Berlin, Germany" for well-known places
        if f"{location_name_title}" not in address_variations and len(location_name_title.split()) <= 3:
            address_variations.append(f"{location_name_title}")
        
        # Also try original location name (in case title case doesn't work)
        if f"{location_name}, Berlin, Germany" not in address_variations:
            address_variations.append(f"{location_name}, Berlin, Germany")
        
        # DYNAMIC: Extract district names using pattern matching
        # This dynamically detects Berlin districts/neighborhoods from the location name
        districts = []
        
        # Common Berlin districts/neighborhoods mapping (can be extended dynamically)
        berlin_districts = [
            ('Mitte', ['Mitte']),
            ('Wedding', ['Wedding']),
            ('Kreuzberg', ['Kreuzberg']),
            ('Friedrichshain', ['Friedrichshain', 'Frankfurter']),
            ('Prenzlauer Berg', ['Prenzlauer', 'Prenzlauerberg']),
            ('Charlottenburg', ['Charlottenburg']),
            ('Neukölln', ['Neukölln', 'Neukoelln']),
            ('Schöneberg', ['Schöneberg', 'Schoeneberg']),
            ('Tempelhof', ['Tempelhof']),
            ('Steglitz', ['Steglitz']),
            ('Zehlendorf', ['Zehlendorf']),
            ('Wilmersdorf', ['Wilmersdorf']),
            ('Spandau', ['Spandau']),
            ('Reinickendorf', ['Reinickendorf']),
            ('Lichtenberg', ['Lichtenberg']),
            ('Marzahn', ['Marzahn']),
            ('Hellersdorf', ['Hellersdorf']),
            ('Treptow', ['Treptow']),
            ('Köpenick', ['Köpenick', 'Koepenick']),
        ]
        
        # Special handling for known landmarks/places
        special_places = {
            'Frankfurter Tor': ['Frankfurter Tor, Berlin, Germany',
                               'Frankfurter Tor, Friedrichshain, Berlin, Germany',
                               'Frankfurter Allee, Berlin, Germany'],
            'Alexanderplatz': ['Alexanderplatz, Berlin, Germany', 'Alexanderplatz, Mitte, Berlin, Germany'],
            'Potsdamer Platz': ['Potsdamer Platz, Berlin, Germany', 'Potsdamer Platz, Mitte, Berlin, Germany'],
            'Brandenburg Gate': ['Brandenburger Tor, Berlin, Germany', 'Brandenburger Tor, Mitte, Berlin, Germany'],
        }
        
        # Check for special places first
        for place_name, place_variations in special_places.items():
            if re.search(place_name.replace(' ', r'\s+'), location_name, re.IGNORECASE):
                districts.extend(place_variations)
        
        # Check for districts dynamically
        for district_name, keywords in berlin_districts:
            for keyword in keywords:
                if re.search(keyword, location_name, re.IGNORECASE):
                    district_variation = f"{district_name}, Berlin, Germany"
                    if district_variation not in districts:
                        districts.append(district_variation)
                    break
        
        # Add district variations (only if not already in the list)
        for district in districts:
            if district not in address_variations:
                address_variations.append(district)
        
        # Try hyphenated locations (e.g., "Mitte-Wedding" -> try both)
        if '-' in location_name:
            parts = location_name.split('-')
            for part in parts:
                part = part.strip()
                if part:
                    variation = f"{part.title()}, Berlin, Germany"
                    if variation not in address_variations:
                        address_variations.append(variation)
    
    # Variation 1: Original cleaned address
    if 'Berlin' in address_clean or 'Germany' in address_clean:
        if address_clean not in address_variations:
            address_variations.append(address_clean)
    else:
        if f"{address_clean}, Berlin, Germany" not in address_variations:
            address_variations.append(f"{address_clean}, Berlin, Germany")
    
    # Variation 2: Extract street name with German street suffixes
    # Match patterns like "Mühlenstraße 25" or "Heidestr. 19/19 A"
    street_patterns = [
        r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|str\.?|weg|Weg|platz|Platz|allee|Allee|damm|Damm))\s*[\d/]*',
        r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|str\.?|weg|Weg|platz|Platz|allee|Allee|damm|Damm))',
    ]
    
    for pattern in street_patterns:
        street_match = re.search(pattern, address_clean, re.IGNORECASE)
        if street_match:
            street = street_match.group(1).strip()
            # Remove problematic house numbers like "0,8"
            street = re.sub(r'\s*0[,\.]\d+', '', street).strip()
            if street and len(street) > 3:
                # Try with postal code if available
                postal_match = re.search(r'(\d{5})', address_clean)
                if postal_match:
                    postal = postal_match.group(1)
                    variation = f"{street}, {postal} Berlin, Germany"
                    if variation not in address_variations:
                        address_variations.append(variation)
                # Also try without postal code
                variation = f"{street}, Berlin, Germany"
                if variation not in address_variations:
                    address_variations.append(variation)
                break
    
    # Variation 3: Extract street + postal code pattern (e.g., "Street 123, 12345")
    street_postal_match = re.search(r'([A-Za-zÄÖÜäöüß\s\-]+(?:\d+[a-z]?)?),?\s*(\d{5})', address_clean)
    if street_postal_match:
        street = street_postal_match.group(1).strip()
        postal = street_postal_match.group(2)
        variation = f"{street}, {postal} Berlin, Germany"
        if variation not in address_variations:
            address_variations.append(variation)
    
    # Variation 4: Just street name + Berlin (remove postal code and other parts)
    street_only = re.sub(r',\s*\d{5}.*', '', address_clean).strip()
    street_only = re.sub(r'\s+\d{5}.*', '', street_only).strip()
    if street_only and len(street_only) > 5 and not street_only.startswith('BERLIN'):
        variation = f"{street_only}, Berlin, Germany"
        if variation not in address_variations:
            address_variations.append(variation)
    
    # Check cache first for all variations
    if use_cache:
        cache = get_geocode_cache()
        for addr_var in address_variations:
            if addr_var in cache:
                return cache[addr_var]
    
    # Add user agent as required by Nominatim
    geolocator = Nominatim(user_agent="urban_technology_housing_finder")
    
    # Try each address variation
    for addr_var in address_variations:
        for attempt in range(max_retries):
            try:
                location = geolocator.geocode(addr_var, timeout=10)
                
                if location:
                    coords = (location.latitude, location.longitude)
                    # Save to cache for ALL variations AND original address
                    if use_cache:
                        cache = get_geocode_cache()
                        # Cache the successful variation
                        cache[addr_var] = coords
                        # Also cache all other variations to avoid future API calls
                        for addr in address_variations:
                            if addr not in cache:
                                cache[addr] = coords
                        # Cache the original cleaned address too
                        cache[address_clean] = coords
                        # Cache the original input address if different
                        if address_clean != str(address).strip():
                            cache[str(address).strip()] = coords
                        save_geocode_cache(cache)
                    print(f"✓ Geocoded: {address_clean[:50]}... → ({coords[0]:.6f}, {coords[1]:.6f}) [CACHED]")
                    return coords
                
                time.sleep(delay)  # Respect rate limits
                
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))
                    continue
                break  # Try next variation
            except Exception as e:
                break  # Try next variation
    
    # If all variations failed, log it
    print(f"⚠ Failed to geocode: {address_clean[:50]}...")
    return None


def geocode_dataframe(df: pd.DataFrame, address_column: str = 'address', progress_callback=None) -> pd.DataFrame:
    """
    Geocode all addresses in a dataframe with caching and optimization.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Dataframe containing addresses
    address_column : str
        Name of the column containing addresses
    progress_callback : callable, optional
        Function to call with progress updates (current, total, cached, new)
    
    Returns:
    --------
    pd.DataFrame
        Dataframe with added 'latitude' and 'longitude' columns
    """
    if address_column not in df.columns:
        raise ValueError(f"Address column '{address_column}' not found in dataframe")
    
    df = df.copy()
    
    # Initialize columns if not present
    if 'latitude' not in df.columns:
        df['latitude'] = None
    if 'longitude' not in df.columns:
        df['longitude'] = None
    
    # Load cache
    cache = get_geocode_cache()
    cache_hits = 0
    new_geocodes = 0
    
    # Get unique addresses to geocode (skip already geocoded)
    addresses_to_geocode = {}
    for idx, row in df.iterrows():
        address = row[address_column]
        
        if pd.isna(address) or address == '':
            continue
        
        # Skip if already geocoded
        if pd.notna(row.get('latitude')) and pd.notna(row.get('longitude')):
            continue
        
        address_str = str(address).strip()
        if address_str not in addresses_to_geocode:
            addresses_to_geocode[address_str] = []
        addresses_to_geocode[address_str].append(idx)
    
    total_unique = len(addresses_to_geocode)
    print(f"Geocoding {total_unique} unique addresses (out of {len(df)} total rows)...")
    
    processed = 0
    for address_str, indices in addresses_to_geocode.items():
        # Use geocode_address which handles all cleaning and variations
        # Check cache first for the original address
        address_normalized = str(address_str).strip()
        coords = None
        
        # Try cache with original address and variations
        coords = None
        cache_key = None
        
        # Check cache for original address
        if address_normalized in cache:
            coords = cache[address_normalized]
            cache_key = address_normalized
            cache_hits += 1
        else:
            # Also check common variations in cache
            address_variations_to_check = [
                address_normalized,
                f"{address_normalized}, Berlin, Germany",
                address_normalized.replace(', Germany', ''),
            ]
            
            # Check if any variation is in cache
            for var in address_variations_to_check:
                if var in cache:
                    coords = cache[var]
                    cache_key = var
                    cache_hits += 1
                    break
        
        if not coords:
            # Geocode using improved function (handles all cleaning and variations)
            coords = geocode_address(address_str, delay=0.3, use_cache=True)
            if coords:
                new_geocodes += 1
                # Cache the result for original address and all variations
                cache[address_normalized] = coords
                # Also cache common variations
                for var in [f"{address_normalized}, Berlin, Germany", address_normalized.replace(', Germany', '')]:
                    if var not in cache:
                        cache[var] = coords
                save_geocode_cache(cache)
        
        # Apply coordinates to all rows with this address
        if coords:
            for idx in indices:
                df.at[idx, 'latitude'] = float(coords[0])
                df.at[idx, 'longitude'] = float(coords[1])
        else:
            # Log failed geocoding for debugging
            print(f"⚠ Failed to geocode address: {address_str[:60]}...")
        
        processed += 1
        
        # Progress update
        successful = cache_hits + new_geocodes
        if progress_callback:
            progress_callback(processed, total_unique, cache_hits, new_geocodes)
        elif processed % 50 == 0 or processed == total_unique:
            print(f"  Processed {processed}/{total_unique} addresses ({successful} successful: {cache_hits} cached, {new_geocodes} new)")
    
    # Save cache at end
    save_geocode_cache(cache)
    
    geocoded_count = df['latitude'].notna().sum()
    print(f"✓ Successfully geocoded {geocoded_count}/{len(df)} addresses ({cache_hits} from cache, {new_geocodes} new)")
    
    # Log ALL rooms with coordinates
    print(f"\n{'='*80}")
    print(f"ALL ROOMS WITH COORDINATES ({geocoded_count} total):")
    print(f"{'='*80}")
    
    if geocoded_count > 0:
        # Sort by provider if available, then by address
        if 'provider' in df.columns:
            df_sorted = df[df['latitude'].notna()].sort_values(['provider', 'address']).copy()
        else:
            df_sorted = df[df['latitude'].notna()].sort_values('address').copy()
        
        for idx, row in df_sorted.iterrows():
            provider = row.get('provider', 'N/A') if 'provider' in df.columns else 'N/A'
            address = row.get('address', 'N/A')
            lat = row['latitude']
            lon = row['longitude']
            
            # Format rent (handle both numeric and string)
            if 'rent' in df.columns and pd.notna(row.get('rent')):
                rent_val = row['rent']
                if isinstance(rent_val, (int, float)):
                    rent_str = f"€{rent_val:.0f}"
                else:
                    rent_str = str(rent_val)
            else:
                rent_str = "N/A"
            
            print(f"  [{idx:3d}] {provider:20s} | {address[:50]:50s} | Rent: {rent_str:>10s} | ({lat:.6f}, {lon:.6f})")
    else:
        print("  No rooms with coordinates found!")
    
    # Log rooms WITHOUT coordinates
    missing_coords = df[df['latitude'].isna() | df['longitude'].isna()]
    if len(missing_coords) > 0:
        print(f"\n{'='*80}")
        print(f"ROOMS WITHOUT COORDINATES ({len(missing_coords)} total):")
        print(f"{'='*80}")
        for idx, row in missing_coords.iterrows():
            provider = row.get('provider', 'N/A') if 'provider' in df.columns else 'N/A'
            address = row.get('address', 'N/A')
            print(f"  [{idx:3d}] {provider:20s} | {address[:50]}")
    
    print(f"{'='*80}\n")
    
    return df


def geocode_university(university_name_or_address: str) -> Optional[Tuple[float, float]]:
    """
    Geocode a university address or name.
    
    Parameters:
    -----------
    university_name_or_address : str
        University name or address
    
    Returns:
    --------
    Tuple[float, float] or None
        (latitude, longitude) if successful
    """
    # Add Berlin context if not present
    if 'Berlin' not in university_name_or_address:
        query = f"{university_name_or_address}, Berlin, Germany"
    else:
        query = university_name_or_address
    
    coords = geocode_address(query)
    
    if coords:
        print(f"✓ Geocoded university: {university_name_or_address}")
        print(f"  Coordinates: ({coords[0]:.6f}, {coords[1]:.6f})")
    
    return coords

