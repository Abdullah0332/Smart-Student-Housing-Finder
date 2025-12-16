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
from logger_config import setup_logger

# Set up logger for this module
logger = setup_logger("geocoding")


# Cache file for geocoding results
GEOCODE_CACHE_FILE = "geocode_cache.json"

def load_geocode_cache() -> Dict[str, Tuple[float, float]]:
    """Load geocoding cache from file."""
    if os.path.exists(GEOCODE_CACHE_FILE):
        try:
            with open(GEOCODE_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                # Convert list values back to tuples, handle both formats
                result = {}
                for k, v in cache.items():
                    if isinstance(v, (list, tuple)) and len(v) == 2:
                        try:
                            result[k] = (float(v[0]), float(v[1]))
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid cache entry for '{k}': {v}")
                            continue
                    elif isinstance(v, dict) and 'lat' in v and 'lon' in v:
                        # Handle alternative format
                        try:
                            result[k] = (float(v['lat']), float(v['lon']))
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid cache entry for '{k}': {v}")
                            continue
                logger.info(f"Loaded {len(result)} entries from geocode cache")
                return result
        except Exception as e:
            logger.error(f"Error loading geocode cache: {e}")
            return {}
    else:
        logger.info("Geocode cache file not found, starting with empty cache")
    return {}

def save_geocode_cache(cache: Dict[str, Tuple[float, float]]):
    """Save geocoding cache to file."""
    try:
        # Convert tuples to lists for JSON serialization
        cache_serializable = {k: list(v) for k, v in cache.items() if isinstance(v, (tuple, list)) and len(v) == 2}
        with open(GEOCODE_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_serializable, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved {len(cache_serializable)} entries to geocode cache")
    except Exception as e:
        logger.error(f"Could not save geocode cache: {e}")
        import traceback
        logger.error(traceback.format_exc())

# Global cache
_geocode_cache = None

def get_geocode_cache() -> Dict[str, Tuple[float, float]]:
    """Get or load geocoding cache."""
    global _geocode_cache
    if _geocode_cache is None:
        _geocode_cache = load_geocode_cache()
    return _geocode_cache

def clear_geocode_cache():
    """Clear the in-memory cache (force reload from file)."""
    global _geocode_cache
    _geocode_cache = None


# ============================================================================
# PROVIDER-SPECIFIC GEOCODING FUNCTIONS
# ============================================================================
# Each provider has unique address formats, so we use separate functions
# to handle their specific patterns and avoid mixing up formats.

def geocode_wunderflats(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    """
    Geocode Wunderflats addresses.
    
    Wunderflats format: Standard street addresses with postal codes
    Examples: "Rigaer Straße, 10247, Berlin", "BER M mit Balkon Gürtelstraße, 10247, Berlin"
    Also handles incomplete addresses: "Angerstraße, 12529," (street + postal code only)
    
    Special patterns to handle:
    - "BER M mit Balkon" / "BER S mit Balkon"
    - "ES City studio" / "ES L studio"
    - "2 Zimmer mit Balkon"
    - "Sequoia Classic Balcony"
    """
    import re
    from geopy.geocoders import Nominatim
    import time
    
    address_clean = str(address).strip()
    
    # Remove Wunderflats-specific patterns
    address_clean = re.sub(r'BER\s+[MS]\s+mit\s+Balkon\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'BER\s+[MS]\s+mit\s+Balkon', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'ES\s+(?:City\s+studio|L\s+studio)\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'ES\s+City\s+studio\s+river\s+view\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'river\s+view\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'\d+\s+Zimmer\s+mit\s+Balkon,?\s*', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'Sequoia\s+Classic\s+Balcony\s+\d+-\d+\s+Month\s+/?\s*', '', address_clean, flags=re.IGNORECASE)
    
    # Remove trailing commas
    address_clean = re.sub(r',\s*$', '', address_clean).strip()
    address_clean = re.sub(r',\s*,+', ',', address_clean)  # Remove double commas
    
    # Clean up whitespace
    address_clean = re.sub(r'\s+', ' ', address_clean).strip()
    
    # Check cache first
    if use_cache:
        cache = get_geocode_cache()
        if address_clean in cache:
            cached_value = cache[address_clean]
            if isinstance(cached_value, (list, tuple)) and len(cached_value) == 2:
                logger.debug(f"Wunderflats cache HIT: '{address_clean}'")
                return tuple(cached_value)
    
    # Extract street name and postal code for incomplete addresses
    # Pattern: "StreetName, 12345," or "StreetName, 12345"
    street_postal_match = re.match(r'^([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|weg|Weg|platz|Platz|allee|Allee|blick|Blick|steig|Steig|wall|Wall)),?\s*(\d{5}),?\s*$', address_clean, re.IGNORECASE)
    
    if street_postal_match:
        # Incomplete address: only street name + postal code (no house number)
        street_name = street_postal_match.group(1).strip()
        postal_code = street_postal_match.group(2).strip()
        
        # Try variations for incomplete addresses
        address_variations = [
            f"{street_name}, {postal_code} Berlin, Germany",
            f"{street_name}, Berlin, Germany",
            f"{street_name} {postal_code}, Berlin, Germany",
        ]
        
        # Check cache for variations
        if use_cache:
            cache = get_geocode_cache()
            for var in address_variations:
                if var in cache:
                    cached_value = cache[var]
                    if isinstance(cached_value, (list, tuple)) and len(cached_value) == 2:
                        logger.debug(f"Wunderflats cache HIT (variation): '{var}'")
                        # Cache the original address too
                        cache[address_clean] = cached_value
                        save_geocode_cache(cache)
                        return tuple(cached_value)
        
        # Try geocoding variations
        geolocator = Nominatim(user_agent="urban_technology_housing_finder")
        for addr_var in address_variations:
            try:
                location = geolocator.geocode(addr_var, timeout=10)
                if location:
                    coords = (location.latitude, location.longitude)
                    if use_cache:
                        cache = get_geocode_cache()
                        cache[address_clean] = coords
                        for var in address_variations:
                            cache[var] = coords
                        save_geocode_cache(cache)
                    logger.info(f"Wunderflats geocoded (incomplete address): {address_clean[:50]}... → ({coords[0]:.6f}, {coords[1]:.6f}) using '{addr_var}'")
                    return coords
            except Exception as e:
                logger.debug(f"Geocoding attempt failed for '{addr_var}': {e}")
                continue
            time.sleep(delay)
    
    # Use base geocoding function for complete addresses
    return _geocode_base(address_clean, max_retries, delay, use_cache, provider='Wunderflats')


def geocode_neonwood(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    """
    Geocode Neonwood addresses.
    
    Neonwood format: Apartment name patterns with location names
    Examples: "BERLIN MITTE-WEDDING Classic Long Term 1", "TÜBINGEN TÜBINGEN - TÜ3 Comfort Study A Long Term 2"
    
    Strategy: Extract location name from apartment descriptor pattern
    """
    import re
    address_clean = str(address).strip()
    
    # Extract location name from pattern: "BERLIN [LOCATION] [DESCRIPTOR]"
    location_match = re.search(r'BERLIN\s+([A-ZÄÖÜ][A-ZÄÖÜ\s\-]+?)(?:\s+(?:Classic|Long|Term|Balcony|Silver|Neon|Comfort|Study|Premium|Standard))', address_clean, re.IGNORECASE)
    
    if location_match:
        location_name = location_match.group(1).strip()
        location_name = re.sub(r'\s+', ' ', location_name).strip()
        
        # Convert to title case
        location_name_title = location_name.title()
        
        # Try location name variations
        address_variations = [
            f"{location_name_title}, Berlin, Germany",
            f"{location_name}, Berlin, Germany",
        ]
        
        # Handle hyphenated locations (e.g., "Mitte-Wedding")
        if '-' in location_name:
            parts = location_name.split('-')
            for part in parts:
                part = part.strip().title()
                if part:
                    address_variations.append(f"{part}, Berlin, Germany")
        
        # Check cache first
        if use_cache:
            cache = get_geocode_cache()
            for var in address_variations:
                if var in cache:
                    cached_value = cache[var]
                    if isinstance(cached_value, (list, tuple)) and len(cached_value) == 2:
                        logger.debug(f"Neonwood cache HIT: '{var}'")
                        return tuple(cached_value)
        
        # Try geocoding
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="urban_technology_housing_finder")
        
        for addr_var in address_variations:
            try:
                location = geolocator.geocode(addr_var, timeout=10)
                if location:
                    coords = (location.latitude, location.longitude)
                    if use_cache:
                        cache = get_geocode_cache()
                        for var in address_variations:
                            cache[var] = coords
                        cache[address_clean] = coords
                        save_geocode_cache(cache)
                    logger.info(f"Neonwood geocoded: {location_name_title} → ({coords[0]:.6f}, {coords[1]:.6f})")
                    return coords
            except Exception:
                continue
            time.sleep(delay)
    
    # Fallback to base function
    return _geocode_base(address_clean, max_retries, delay, use_cache, provider='Neonwood')


def geocode_zimmerei(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    """
    Geocode Zimmerei addresses.
    
    Zimmerei format: May have wrong cities (e.g., "Hamburg") or malformed addresses
    Examples: "Heinrich-Heine-Straße 0,8, Hamburg, Berlin, Germany", "Hamburg Central"
    
    Strategy: Remove wrong cities, extract street names, fix house numbers
    """
    import re
    address_clean = str(address).strip()
    
    # Remove wrong cities (especially Hamburg)
    address_clean = re.sub(r',\s*Hamburg', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'Hamburg\s*,?', '', address_clean, flags=re.IGNORECASE)
    
    # Fix problematic house numbers like "0,8"
    address_clean = re.sub(r'\s*0[,\.]\d+', '', address_clean)
    
    # Extract street name
    street_match = re.search(r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|weg|Weg|platz|Platz|allee|Allee))', address_clean, re.IGNORECASE)
    
    if street_match:
        street_name = street_match.group(1).strip()
        address_clean = f"{street_name}, Berlin, Germany"
    
    # Clean up
    address_clean = re.sub(r'\s+', ' ', address_clean).strip()
    address_clean = re.sub(r',\s*,+', ',', address_clean)
    
    return _geocode_base(address_clean, max_retries, delay, use_cache, provider='Zimmerei')


def geocode_urban_club(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    """
    Geocode The Urban Club addresses.
    
    Urban Club format: Simple district/area names
    Examples: "Berlin Tegel", "Berlin Charlottenburg"
    
    Strategy: Handle district names, remove provider text
    """
    import re
    address_clean = str(address).strip()
    
    # Remove provider names
    address_clean = re.sub(r'THE\s+URBAN\s+CLUB', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'URBAN\s+CLUB', '', address_clean, flags=re.IGNORECASE)
    
    # Remove "Plönzeile" variations
    address_clean = re.sub(r'-\s*Pl[öo]n?zeile', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'Pl[öo]n?zeile\s*', '', address_clean, flags=re.IGNORECASE)
    
    # Clean up
    address_clean = re.sub(r'\s+', ' ', address_clean).strip()
    
    # Ensure "Berlin, Germany" format
    if 'Berlin' not in address_clean:
        address_clean = f"{address_clean}, Berlin, Germany"
    elif 'Germany' not in address_clean:
        address_clean = address_clean.replace('Berlin', 'Berlin, Germany')
    
    return _geocode_base(address_clean, max_retries, delay, use_cache, provider='The Urban Club')


def geocode_havens_living(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    """
    Geocode Havens Living addresses.
    
    Havens format: Simple district names
    Examples: "Berlin Charlottenburg"
    
    Strategy: Handle district names
    """
    import re
    address_clean = str(address).strip()
    
    # Ensure "Berlin, Germany" format
    if 'Berlin' not in address_clean:
        address_clean = f"{address_clean}, Berlin, Germany"
    elif 'Germany' not in address_clean:
        address_clean = address_clean.replace('Berlin', 'Berlin, Germany')
    
    return _geocode_base(address_clean, max_retries, delay, use_cache, provider='Havens Living')


def geocode_66_monkeys(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    """
    Geocode 66 Monkeys addresses.
    
    66 Monkeys format: Standard street addresses
    Examples: "Mühlenstraße, Berlin"
    
    Strategy: Standard geocoding
    """
    import re
    address_clean = str(address).strip()
    
    # Ensure "Berlin, Germany" format
    if 'Berlin' not in address_clean:
        address_clean = f"{address_clean}, Berlin, Germany"
    elif 'Germany' not in address_clean:
        address_clean = address_clean.replace('Berlin', 'Berlin, Germany')
    
    return _geocode_base(address_clean, max_retries, delay, use_cache, provider='66 Monkeys')


def _geocode_base(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True, provider: str = 'Unknown') -> Optional[Tuple[float, float]]:
    """
    Base geocoding function used by all provider-specific functions.
    Calls the comprehensive geocode_address function after provider-specific preprocessing.
    """
    # Use the comprehensive geocode_address function (defined below)
    # This avoids code duplication and ensures all providers benefit from the full logic
    return geocode_address(address, max_retries, delay, use_cache)


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
    
    # Remove "BER M mit Balkon" and "BER S mit Balkon" patterns (Wunderflats)
    address_clean = re.sub(r'BER\s+[MS]\s+mit\s+Balkon\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'BER\s+[MS]\s+mit\s+Balkon', '', address_clean, flags=re.IGNORECASE)
    
    # Remove "ES City studio" and "ES L studio" patterns (Wunderflats)
    address_clean = re.sub(r'ES\s+(?:City\s+studio|L\s+studio)\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'ES\s+City\s+studio\s+river\s+view\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'river\s+view\s+', '', address_clean, flags=re.IGNORECASE)
    
    # Remove "2 Zimmer mit Balkon" pattern
    address_clean = re.sub(r'\d+\s+Zimmer\s+mit\s+Balkon,?\s*', '', address_clean, flags=re.IGNORECASE)
    
    # Remove "Sequoia Classic Balcony" pattern
    address_clean = re.sub(r'Sequoia\s+Classic\s+Balcony\s+\d+-\d+\s+Month\s+/?\s*', '', address_clean, flags=re.IGNORECASE)
    
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
    # Also handle addresses with non-Berlin cities (like "Farmersteg, 15366, Hoppegarten, Berlin, Germany")
    non_berlin_cities = ['Hamburg', 'Hoppegarten', 'Potsdam', 'Munich', 'München', 'Frankfurt', 'Cologne', 'Köln', 'Neuenhagen', 'Teltow', 'Schönefeld', 'Ahrensfelde', 'Hennigsdorf', 'Glienicke', 'Nuthetal', 'Schöneiche', 'Stahnsdorf', 'Falkensee', 'Blankenfelde-Mahlow', 'Kleinmachnow', 'Schönwalde-Glien', 'Schulzendorf', 'Zeuthen', 'Bernau', 'Panketal', 'Fredersdorf', 'Großbeeren']
    
    # Track the actual city if found (for fallback geocoding)
    actual_city = None
    
    # Check postal code first - Berlin postal codes are 10115-14199
    postal_match = re.search(r'(\d{5})', address_clean)
    postal_code = None
    is_berlin_postal = False
    if postal_match:
        postal_code = postal_match.group(1)
        try:
            postal_int = int(postal_code)
            # Berlin postal codes: 10115-14199
            is_berlin_postal = (10115 <= postal_int <= 14199)
            if not is_berlin_postal:
                # Non-Berlin postal code - remove it from address
                address_clean = re.sub(r',?\s*\d{5},?', '', address_clean)
                address_clean = re.sub(r'\s+', ' ', address_clean).strip()
                address_clean = re.sub(r',\s*,+', ',', address_clean)  # Remove double commas
                logger.debug(f"Removed non-Berlin postal code {postal_code} from address")
        except ValueError:
            pass
    
    # Extract street name BEFORE removing cities (for fallback geocoding)
    # Try to extract street name from original address
    original_address = address_clean
    extracted_street_name = None
    
    # Try patterns with and without street suffixes
    street_patterns = [
        r'^([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|weg|Weg|platz|Platz|allee|Allee|str\.?|steig|Steig|wall|Wall))',
        r'^([A-Za-zÄÖÜäöüß\s\-]+?)(?:\s*,\s*\d{5}|,|$)',  # Match until comma or postal code
    ]
    
    for pattern in street_patterns:
        street_match = re.search(pattern, original_address, re.IGNORECASE)
        if street_match:
            extracted_street_name = street_match.group(1).strip()
            extracted_street_name = re.sub(r'\s*0[,\.]\d+', '', extracted_street_name).strip()
            if extracted_street_name and len(extracted_street_name) > 2:
                break
    
    for wrong_city in non_berlin_cities:
        # Check if wrong city is in address (with or without Berlin)
        if wrong_city in address_clean:
            actual_city = wrong_city  # Remember the actual city for fallback
            # If Berlin is also in the address, we'll remove the wrong city
            # But if only wrong city is present, we'll use it for fallback geocoding
            # Extract street name
            street_match = re.search(r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|weg|Weg|platz|Platz|allee|Allee|str\.?|steig|Steig|wall|Wall))', address_clean, re.IGNORECASE)
            
            if street_match:
                street_name = street_match.group(1).strip()
                # Remove "0,8" or similar house number issues
                street_name = re.sub(r'\s*0[,\.]\d+', '', street_name).strip()
                
                # If we have a Berlin postal code, use it
                if is_berlin_postal and postal_code:
                    address_clean = f"{street_name}, {postal_code} Berlin, Germany"
                    logger.debug(f"Fixed address: {street_name}, {postal_code} Berlin, Germany (removed {wrong_city})")
                else:
                    # No valid Berlin postal code - try with just street name and Berlin
                    address_clean = f"{street_name}, Berlin, Germany"
                    logger.debug(f"Fixed address: {street_name}, Berlin, Germany (removed {wrong_city})")
            elif extracted_street_name:
                # Use extracted street name from original address
                street_name = extracted_street_name
                if is_berlin_postal and postal_code:
                    address_clean = f"{street_name}, {postal_code} Berlin, Germany"
                    logger.debug(f"Fixed address: {street_name}, {postal_code} Berlin, Germany (removed {wrong_city})")
                else:
                    address_clean = f"{street_name}, Berlin, Germany"
                    logger.debug(f"Fixed address: {street_name}, Berlin, Germany (removed {wrong_city})")
            else:
                # Just remove the wrong city
                address_clean = re.sub(f'{wrong_city},?', '', address_clean, flags=re.IGNORECASE)
                address_clean = re.sub(r'\s+', ' ', address_clean).strip()
                address_clean = re.sub(r',\s*,+', ',', address_clean)  # Remove double commas
                logger.debug(f"Removed {wrong_city} from address")
            break  # Only fix the first matching wrong city
    
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
    # Match patterns like "Mühlenstraße 25" or "Heidestr. 19/19 A" or "Farmersteg"
    street_patterns = [
        r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|str\.?|weg|Weg|platz|Platz|allee|Allee|damm|Damm|steig|Steig|wall|Wall))\s*[\d/]*',
        r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|str\.?|weg|Weg|platz|Platz|allee|Allee|damm|Damm|steig|Steig|wall|Wall))',
    ]
    
    for pattern in street_patterns:
        street_match = re.search(pattern, address_clean, re.IGNORECASE)
        if street_match:
            street = street_match.group(1).strip()
            # Remove problematic house numbers like "0,8"
            street = re.sub(r'\s*0[,\.]\d+', '', street).strip()
            if street and len(street) > 3:
                # Check if we have a valid Berlin postal code
                if is_berlin_postal and postal_code:
                    variation = f"{street}, {postal_code} Berlin, Germany"
                    if variation not in address_variations:
                        address_variations.append(variation)
                # Always try without postal code
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
                    logger.info(f"Geocoded: {address_clean[:50]}... → ({coords[0]:.6f}, {coords[1]:.6f}) [CACHED]")
                    return coords
                
                time.sleep(delay)  # Respect rate limits
                
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))
                    continue
                break  # Try next variation
            except Exception as e:
                break  # Try next variation
    
    # If all Berlin variations failed and we have an actual city, try geocoding to that city
    # OR if address contains non-Berlin city (even without Berlin), try geocoding to that city
    if actual_city or any(city in address_clean for city in non_berlin_cities):
        # Determine the actual city
        if not actual_city:
            # Find which non-Berlin city is in the address
            for city in non_berlin_cities:
                if city in address_clean:
                    actual_city = city
                    break
        
        if actual_city:
            # Use extracted street name from original address (before cleaning)
            street_name_for_fallback = extracted_street_name
            
            # If we don't have extracted street name, try to extract from cleaned address
            if not street_name_for_fallback:
                # Try multiple patterns to extract street name
                street_patterns = [
                    r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|weg|Weg|platz|Platz|allee|Allee|str\.?|steig|Steig|wall|Wall|gasse|Gasse|anger|Anger|chaussee|Chaussee|eichen|Eichen))',
                    r'^([A-Za-zÄÖÜäöüß\s\-]+?)(?:\s*,\s*\d{5}|,|$)',  # Extract before comma or postal code
                    r'^([A-Za-zÄÖÜäöüß\s\-]+?)(?:\s+Berlin|$)',  # Extract before "Berlin"
                    r'^([A-Za-zÄÖÜäöüß\s\-]+?)(?:\s+' + re.escape(actual_city) + r'|$)',  # Extract before actual city name
                ]
                
                for pattern in street_patterns:
                    street_match = re.search(pattern, address_clean, re.IGNORECASE)
                    if street_match:
                        street_name_for_fallback = street_match.group(1).strip()
                        # Clean the street name
                        street_name_for_fallback = re.sub(r'ES\s+(?:City\s+studio|L\s+studio)\s+', '', street_name_for_fallback, flags=re.IGNORECASE)
                        street_name_for_fallback = re.sub(r'river\s+view\s+', '', street_name_for_fallback, flags=re.IGNORECASE)
                        street_name_for_fallback = re.sub(r'\d+\s+Zimmer\s+mit\s+Balkon', '', street_name_for_fallback, flags=re.IGNORECASE)
                        street_name_for_fallback = re.sub(r'Sequoia\s+Classic\s+Balcony.*?/', '', street_name_for_fallback, flags=re.IGNORECASE)
                        # Remove the actual city name if it's in the street name
                        street_name_for_fallback = re.sub(re.escape(actual_city), '', street_name_for_fallback, flags=re.IGNORECASE)
                        street_name_for_fallback = re.sub(r'\s+', ' ', street_name_for_fallback).strip()
                        if street_name_for_fallback and len(street_name_for_fallback) > 2:
                            break
            
            if street_name_for_fallback and len(street_name_for_fallback) > 2:
                street_name_for_fallback = re.sub(r'\s*0[,\.]\d+', '', street_name_for_fallback).strip()
                # Try with actual city (e.g., "Rathausgasse, Schönefeld, Germany")
                fallback_address = f"{street_name_for_fallback}, {actual_city}, Germany"
                logger.debug(f"Trying fallback geocoding to actual city: {fallback_address}")
                try:
                    location = geolocator.geocode(fallback_address, timeout=10)
                    if location:
                        coords = (location.latitude, location.longitude)
                        # Cache the fallback result
                        if use_cache:
                            cache = get_geocode_cache()
                            cache[fallback_address] = coords
                            cache[address_clean] = coords
                            cache[str(address).strip()] = coords
                            save_geocode_cache(cache)
                        logger.info(f"Geocoded to actual city ({actual_city}): {address_clean[:50]}... → ({coords[0]:.6f}, {coords[1]:.6f})")
                        return coords
                except Exception as e:
                    pass  # Fallback also failed
            
            # Also try just the city name or "Alt [City]" pattern
            city_fallback_variations = [
                f"{actual_city}, Germany",
                f"Alt {actual_city}, Germany" if 'Alt' in address_clean else None,
            ]
            
            for city_fallback in city_fallback_variations:
                if city_fallback:
                    logger.debug(f"Trying fallback with city: {city_fallback}")
                    try:
                        location = geolocator.geocode(city_fallback, timeout=10)
                        if location:
                            coords = (location.latitude, location.longitude)
                            if use_cache:
                                cache = get_geocode_cache()
                                cache[city_fallback] = coords
                                cache[address_clean] = coords
                                cache[str(address).strip()] = coords
                                save_geocode_cache(cache)
                            logger.info(f"Geocoded to city ({actual_city}): {address_clean[:50]}... → ({coords[0]:.6f}, {coords[1]:.6f})")
                            return coords
                    except Exception as e:
                        pass  # Fallback also failed
    
    # If all variations failed, try one more time with just the first word (street name)
    # This helps with addresses like "Farmersteg" that don't match patterns
    if address_clean:
        # Extract first meaningful word (skip common prefixes)
        first_word_match = re.search(r'^([A-Za-zÄÖÜäöüß]+)', address_clean)
        if first_word_match:
            first_word = first_word_match.group(1)
            if len(first_word) > 3:  # Only if it's a meaningful word
                # Try with Berlin
                final_attempt = f"{first_word}, Berlin, Germany"
                logger.debug(f"Trying final fallback: {final_attempt}")
                try:
                    location = geolocator.geocode(final_attempt, timeout=10)
                    if location:
                        coords = (location.latitude, location.longitude)
                        if use_cache:
                            cache = get_geocode_cache()
                            cache[final_attempt] = coords
                            cache[address_clean] = coords
                            cache[str(address).strip()] = coords
                            save_geocode_cache(cache)
                        logger.info(f"Geocoded with fallback: {address_clean[:50]}... → ({coords[0]:.6f}, {coords[1]:.6f})")
                        return coords
                except Exception as e:
                    pass  # Final attempt failed
    
    # If all variations failed, log it
    logger.warning(f"Failed to geocode: {address_clean[:50]}...")
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
    
    # Load cache (reload to get latest)
    clear_geocode_cache()
    cache = get_geocode_cache()
    cache_hits = 0
    new_geocodes = 0
    logger.info(f"Starting geocoding with {len(cache)} cached entries")
    
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
    logger.info(f"Geocoding {total_unique} unique addresses (out of {len(df)} total rows)...")
    
    processed = 0
    for address_str, indices in addresses_to_geocode.items():
        # Get provider for this address (if available)
        provider = None
        provider_name = 'Unknown'
        geocode_func = geocode_address  # Default to base function
        
        if 'provider' in df.columns:
            # Get provider from first row with this address
            first_idx = indices[0]
            provider = df.at[first_idx, 'provider'] if pd.notna(df.at[first_idx, 'provider']) else None
            
            # Route to appropriate provider-specific function
            if provider:
                provider_name = str(provider)
                provider_lower = provider_name.lower()
                if 'wunderflats' in provider_lower:
                    geocode_func = geocode_wunderflats
                elif 'neonwood' in provider_lower:
                    geocode_func = geocode_neonwood
                elif 'zimmerei' in provider_lower:
                    geocode_func = geocode_zimmerei
                elif 'urban club' in provider_lower or 'urban_club' in provider_lower:
                    geocode_func = geocode_urban_club
                elif 'havens' in provider_lower:
                    geocode_func = geocode_havens_living
                elif '66' in provider_lower and 'monkey' in provider_lower:
                    geocode_func = geocode_66_monkeys
        
        # Use geocode_address which handles all cleaning and variations
        # Check cache first for the original address
        address_normalized = str(address_str).strip()
        coords = None
        cache_key = None
        
        # Comprehensive cache lookup - check multiple variations
        import re
        
        # Build list of all possible variations to check
        address_variations_to_check = [
            address_normalized,  # Original
            f"{address_normalized}, Berlin, Germany",  # With Berlin, Germany
            address_normalized.replace(', Germany', ''),  # Without Germany
            address_normalized.replace('Berlin, Germany', 'Berlin'),  # Without comma
            address_normalized.replace(', Berlin, Germany', ''),  # Just street
        ]
        
        # Also try cleaned versions (remove non-Berlin cities, postal codes, etc.)
        cleaned_variations = []
        
        # Remove non-Berlin cities (comprehensive list)
        non_berlin_cities_list = ['Teltow', 'Schönefeld', 'Ahrensfelde', 'Hoppegarten', 'Potsdam', 'Hamburg', 
                                  'Hennigsdorf', 'Glienicke', 'Nuthetal', 'Schöneiche', 'Stahnsdorf', 'Falkensee',
                                  'Blankenfelde-Mahlow', 'Kleinmachnow', 'Schönwalde-Glien', 'Schulzendorf', 
                                  'Zeuthen', 'Bernau', 'Panketal', 'Fredersdorf', 'Großbeeren', 'Neuenhagen']
        
        for city in non_berlin_cities_list:
            if city in address_normalized:
                # Remove city name
                cleaned = re.sub(f'{re.escape(city)},?', '', address_normalized, flags=re.IGNORECASE)
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                cleaned = re.sub(r',\s*,+', ',', cleaned)
                if cleaned and cleaned not in cleaned_variations:
                    cleaned_variations.append(cleaned)
                    cleaned_variations.append(f"{cleaned}, Berlin, Germany")
        
        # Remove "BER M mit Balkon" and "BER S mit Balkon" patterns
        if 'BER' in address_normalized.upper() and 'mit' in address_normalized.lower():
            cleaned = re.sub(r'BER\s+[MS]\s+mit\s+Balkon\s*', '', address_normalized, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if cleaned and cleaned not in cleaned_variations:
                cleaned_variations.append(cleaned)
                cleaned_variations.append(f"{cleaned}, Berlin, Germany")
        
        # Remove "ES City studio" patterns
        if 'ES City' in address_normalized or 'ES L studio' in address_normalized:
            cleaned = re.sub(r'ES\s+(?:City\s+studio|L\s+studio)\s+', '', address_normalized, flags=re.IGNORECASE)
            cleaned = re.sub(r'river\s+view\s+', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if cleaned and cleaned not in cleaned_variations:
                cleaned_variations.append(cleaned)
                cleaned_variations.append(f"{cleaned}, Berlin, Germany")
        
        # Remove "2 Zimmer mit Balkon" pattern
        if 'Zimmer mit Balkon' in address_normalized:
            cleaned = re.sub(r'\d+\s+Zimmer\s+mit\s+Balkon,?\s*', '', address_normalized, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if cleaned and cleaned not in cleaned_variations:
                cleaned_variations.append(cleaned)
                cleaned_variations.append(f"{cleaned}, Berlin, Germany")
        
        # Remove "Sequoia Classic Balcony" pattern
        if 'Sequoia' in address_normalized:
            cleaned = re.sub(r'Sequoia\s+Classic\s+Balcony\s+\d+-\d+\s+Month\s+/?\s*', '', address_normalized, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if cleaned and cleaned not in cleaned_variations:
                cleaned_variations.append(cleaned)
                cleaned_variations.append(f"{cleaned}, Berlin, Germany")
        
        # Extract just street name (before first comma or postal code)
        street_match = re.search(r'^([^,]+?)(?:\s*,\s*\d{5}|,|$)', address_normalized)
        if street_match:
            street_only = street_match.group(1).strip()
            # Clean street name
            street_only = re.sub(r'BER\s+[MS]\s+mit\s+Balkon\s*', '', street_only, flags=re.IGNORECASE)
            street_only = re.sub(r'ES\s+(?:City\s+studio|L\s+studio)\s+', '', street_only, flags=re.IGNORECASE)
            street_only = re.sub(r'\d+\s+Zimmer\s+mit\s+Balkon', '', street_only, flags=re.IGNORECASE)
            street_only = re.sub(r'Sequoia\s+Classic\s+Balcony.*?/', '', street_only, flags=re.IGNORECASE)
            street_only = re.sub(r'\s+', ' ', street_only).strip()
            if street_only and len(street_only) > 3:
                cleaned_variations.append(f"{street_only}, Berlin, Germany")
        
        # Combine all variations
        all_variations = address_variations_to_check + cleaned_variations
        
        # Check cache for all variations (exact match first)
        for var in all_variations:
            if var in cache:
                cached_value = cache[var]
                # Handle both tuple and list formats
                if isinstance(cached_value, (list, tuple)) and len(cached_value) == 2:
                    coords = tuple(cached_value)
                    cache_key = var
                    cache_hits += 1
                    logger.debug(f"Cache HIT (exact): '{var}'")
                    break
        
        # If still not found, try case-insensitive and partial matching
        if not coords:
            var_lower = address_normalized.lower()
            # Extract street name from normalized address
            street1_match = re.search(r'^([A-Za-zÄÖÜäöüß\s\-]+?)(?:\s*,\s*\d{5}|,|$)', address_normalized, re.IGNORECASE)
            street1_name = street1_match.group(1).strip().lower() if street1_match else None
            
            for key in cache.keys():
                key_lower = key.lower()
                # Check if addresses are similar (same street name)
                if street1_name and street1_name in key_lower:
                    # Extract street name from cache key
                    street2_match = re.search(r'^([A-Za-zÄÖÜäöüß\s\-]+?)(?:\s*,\s*\d{5}|,|$)', key, re.IGNORECASE)
                    if street2_match:
                        street2_name = street2_match.group(1).strip().lower()
                        # Check if street names match (allowing for minor differences)
                        if street1_name == street2_name or (len(street1_name) > 5 and street1_name in street2_name) or (len(street2_name) > 5 and street2_name in street1_name):
                            cached_value = cache[key]
                            if isinstance(cached_value, (list, tuple)) and len(cached_value) == 2:
                                coords = tuple(cached_value)
                                cache_key = key
                                cache_hits += 1
                                logger.debug(f"Cache HIT (partial): '{address_normalized}' -> '{key}'")
                                break
        
        if not coords:
            # Geocode using provider-specific function
            logger.debug(f"Cache MISS - geocoding ({provider_name}): '{address_normalized}'")
            try:
                coords = geocode_func(address_str, delay=0.3, use_cache=True)
            except Exception as e:
                logger.error(f"Error in {provider_name} geocoding: {e}")
                # Fallback to base function
                coords = geocode_address(address_str, delay=0.3, use_cache=True)
            if coords:
                new_geocodes += 1
                logger.info(f"New geocode: '{address_normalized}' -> ({coords[0]:.6f}, {coords[1]:.6f})")
                # Cache the result for original address and all variations
                cache[address_normalized] = coords
                # Also cache common variations
                for var in [f"{address_normalized}, Berlin, Germany", address_normalized.replace(', Germany', '')]:
                    if var not in cache:
                        cache[var] = coords
                # Save cache immediately after each new geocode
                try:
                    save_geocode_cache(cache)
                    logger.debug(f"Saved to cache: '{address_normalized}'")
                except Exception as e:
                    logger.error(f"Failed to save cache: {e}")
            else:
                logger.warning(f"Geocoding failed for: '{address_normalized}'")
        
        # Apply coordinates to all rows with this address
        if coords:
            for idx in indices:
                df.at[idx, 'latitude'] = float(coords[0])
                df.at[idx, 'longitude'] = float(coords[1])
        else:
            # Log failed geocoding for debugging
            logger.warning(f"Failed to geocode address: {address_str[:60]}...")
        
        processed += 1
        
        # Progress update (every 10 addresses or at end)
        successful = cache_hits + new_geocodes
        if progress_callback:
            progress_callback(processed, total_unique, cache_hits, new_geocodes)
        elif processed % 10 == 0 or processed == total_unique:
            logger.info(f"Progress: {processed}/{total_unique} addresses | {successful} successful ({cache_hits} cached, {new_geocodes} new)")
        
        # Reload cache periodically to pick up new entries (every 50 addresses)
        if processed % 50 == 0 and new_geocodes > 0:
            clear_geocode_cache()
            cache = get_geocode_cache()
            logger.debug(f"Reloaded cache: now {len(cache)} entries")
    
    # Save cache at end
    save_geocode_cache(cache)
    
    geocoded_count = df['latitude'].notna().sum()
    logger.info(f"Successfully geocoded {geocoded_count}/{len(df)} addresses ({cache_hits} from cache, {new_geocodes} new)")
    
    # Log ALL rooms with coordinates
    logger.info(f"\n{'='*80}")
    logger.info(f"ALL ROOMS WITH COORDINATES ({geocoded_count} total):")
    logger.info(f"{'='*80}")
    
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
            
            logger.info(f"  [{idx:3d}] {provider:20s} | {address[:50]:50s} | Rent: {rent_str:>10s} | ({lat:.6f}, {lon:.6f})")
    else:
        logger.warning("  No rooms with coordinates found!")
    
    # Log rooms WITHOUT coordinates
    missing_coords = df[df['latitude'].isna() | df['longitude'].isna()]
    if len(missing_coords) > 0:
        logger.warning(f"\n{'='*80}")
        logger.warning(f"ROOMS WITHOUT COORDINATES ({len(missing_coords)} total):")
        logger.warning(f"{'='*80}")
        for idx, row in missing_coords.iterrows():
            provider = row.get('provider', 'N/A') if 'provider' in df.columns else 'N/A'
            address = row.get('address', 'N/A')
            logger.warning(f"  [{idx:3d}] {provider:20s} | {address[:50]}")
    
    logger.info(f"{'='*80}\n")
    
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
        logger.info(f"Geocoded university: {university_name_or_address}")
        logger.info(f"  Coordinates: ({coords[0]:.6f}, {coords[1]:.6f})")
    
    return coords

