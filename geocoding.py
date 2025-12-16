import time
import requests
import pandas as pd
import json
import os
import re
import traceback
from typing import Tuple, Optional, Dict
import geopy.geocoders
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from logger_config import setup_logger

logger = setup_logger("geocoding")


GEOCODE_CACHE_FILE = "geocode_cache.json"

def load_geocode_cache() -> Dict[str, Tuple[float, float]]:
    if os.path.exists(GEOCODE_CACHE_FILE):
        try:
            with open(GEOCODE_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                result = {}
                for k, v in cache.items():
                    if isinstance(v, (list, tuple)) and len(v) == 2:
                        try:
                            result[k] = (float(v[0]), float(v[1]))
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid cache entry for '{k}': {v}")
                            continue
                    elif isinstance(v, dict) and 'lat' in v and 'lon' in v:
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
    try:
        cache_serializable = {k: list(v) for k, v in cache.items() if isinstance(v, (tuple, list)) and len(v) == 2}
        with open(GEOCODE_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_serializable, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved {len(cache_serializable)} entries to geocode cache")
    except Exception as e:
        logger.error(f"Could not save geocode cache: {e}")
        logger.error(traceback.format_exc())

_geocode_cache = None

def get_geocode_cache() -> Dict[str, Tuple[float, float]]:
    global _geocode_cache
    if _geocode_cache is None:
        _geocode_cache = load_geocode_cache()
    return _geocode_cache

def clear_geocode_cache():
    global _geocode_cache
    _geocode_cache = None

def geocode_wunderflats(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    
    address_clean = str(address).strip()
    
    address_clean = re.sub(r'BER\s+[MS]\s+mit\s+Balkon\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'BER\s+[MS]\s+mit\s+Balkon', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'ES\s+(?:City\s+studio|L\s+studio)\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'ES\s+City\s+studio\s+river\s+view\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'river\s+view\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'\d+\s+Zimmer\s+mit\s+Balkon,?\s*', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'Sequoia\s+Classic\s+Balcony\s+\d+-\d+\s+Month\s+/?\s*', '', address_clean, flags=re.IGNORECASE)
    
    address_clean = re.sub(r',\s*$', '', address_clean).strip()
    address_clean = re.sub(r',\s*,+', ',', address_clean)  # Remove double commas
    
    address_clean = re.sub(r'\s+', ' ', address_clean).strip()
    
    if use_cache:
        cache = get_geocode_cache()
        if address_clean in cache:
            cached_value = cache[address_clean]
            if isinstance(cached_value, (list, tuple)) and len(cached_value) == 2:
                logger.debug(f"Wunderflats cache HIT: '{address_clean}'")
                return tuple(cached_value)
    
    street_postal_match = re.match(r'^([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|weg|Weg|platz|Platz|allee|Allee|blick|Blick|steig|Steig|wall|Wall)),?\s*(\d{5}),?\s*$', address_clean, re.IGNORECASE)
    
    if street_postal_match:
        street_name = street_postal_match.group(1).strip()
        postal_code = street_postal_match.group(2).strip()
        
        address_variations = [
            f"{street_name}, {postal_code} Berlin, Germany",
            f"{street_name}, Berlin, Germany",
            f"{street_name} {postal_code}, Berlin, Germany",
        ]
        
        if use_cache:
            cache = get_geocode_cache()
            for var in address_variations:
                if var in cache:
                    cached_value = cache[var]
                    if isinstance(cached_value, (list, tuple)) and len(cached_value) == 2:
                        logger.debug(f"Wunderflats cache HIT (variation): '{var}'")
                        cache[address_clean] = cached_value
                        save_geocode_cache(cache)
                        return tuple(cached_value)
        
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
    
    return _geocode_base(address_clean, max_retries, delay, use_cache, provider='Wunderflats')


def geocode_neonwood(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    address_clean = str(address).strip()
    
    location_match = re.search(r'BERLIN\s+([A-ZÄÖÜ][A-ZÄÖÜ\s\-]+?)(?:\s+(?:Classic|Long|Term|Balcony|Silver|Neon|Comfort|Study|Premium|Standard))', address_clean, re.IGNORECASE)
    
    if location_match:
        location_name = location_match.group(1).strip()
        location_name = re.sub(r'\s+', ' ', location_name).strip()
        
        location_name_title = location_name.title()
        
        address_variations = [
            f"{location_name_title}, Berlin, Germany",
            f"{location_name}, Berlin, Germany",
        ]
        
        if '-' in location_name:
            parts = location_name.split('-')
            for part in parts:
                part = part.strip().title()
                if part:
                    address_variations.append(f"{part}, Berlin, Germany")
        
        if use_cache:
            cache = get_geocode_cache()
            for var in address_variations:
                if var in cache:
                    cached_value = cache[var]
                    if isinstance(cached_value, (list, tuple)) and len(cached_value) == 2:
                        logger.debug(f"Neonwood cache HIT: '{var}'")
                        return tuple(cached_value)
        
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
    
    return _geocode_base(address_clean, max_retries, delay, use_cache, provider='Neonwood')


def geocode_zimmerei(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    address_clean = str(address).strip()
    
    address_clean = re.sub(r',\s*Hamburg', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'Hamburg\s*,?', '', address_clean, flags=re.IGNORECASE)
    
    address_clean = re.sub(r'\s*0[,\.]\d+', '', address_clean)
    
    street_match = re.search(r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|weg|Weg|platz|Platz|allee|Allee))', address_clean, re.IGNORECASE)
    
    if street_match:
        street_name = street_match.group(1).strip()
        address_clean = f"{street_name}, Berlin, Germany"
    
    address_clean = re.sub(r'\s+', ' ', address_clean).strip()
    address_clean = re.sub(r',\s*,+', ',', address_clean)
    
    return _geocode_base(address_clean, max_retries, delay, use_cache, provider='Zimmerei')


def geocode_urban_club(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    address_clean = str(address).strip()
    
    address_clean = re.sub(r'THE\s+URBAN\s+CLUB', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'URBAN\s+CLUB', '', address_clean, flags=re.IGNORECASE)
    
    address_clean = re.sub(r'-\s*Pl[öo]n?zeile', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'Pl[öo]n?zeile\s*', '', address_clean, flags=re.IGNORECASE)
    
    address_clean = re.sub(r'\s+', ' ', address_clean).strip()
    
    if 'Berlin' not in address_clean:
        address_clean = f"{address_clean}, Berlin, Germany"
    elif 'Germany' not in address_clean:
        address_clean = address_clean.replace('Berlin', 'Berlin, Germany')
    
    return _geocode_base(address_clean, max_retries, delay, use_cache, provider='The Urban Club')


def geocode_havens_living(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    address_clean = str(address).strip()
    
    if 'Berlin' not in address_clean:
        address_clean = f"{address_clean}, Berlin, Germany"
    elif 'Germany' not in address_clean:
        address_clean = address_clean.replace('Berlin', 'Berlin, Germany')
    
    return _geocode_base(address_clean, max_retries, delay, use_cache, provider='Havens Living')


def geocode_66_monkeys(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    address_clean = str(address).strip()
    
    if 'Berlin' not in address_clean:
        address_clean = f"{address_clean}, Berlin, Germany"
    elif 'Germany' not in address_clean:
        address_clean = address_clean.replace('Berlin', 'Berlin, Germany')
    
    return _geocode_base(address_clean, max_retries, delay, use_cache, provider='66 Monkeys')


def _geocode_base(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True, provider: str = 'Unknown') -> Optional[Tuple[float, float]]:
    return geocode_address(address, max_retries, delay, use_cache)


def geocode_address(address: str, max_retries: int = 3, delay: float = 0.5, use_cache: bool = True) -> Optional[Tuple[float, float]]:
    address_clean = str(address).strip()
    
    address_clean = re.sub(r'[\n\r\t]+', ' ', address_clean)
    
    address_clean = re.sub(r'BerlinGermany', 'Berlin, Germany', address_clean)
    address_clean = re.sub(r'Berlin\s+Germany', 'Berlin, Germany', address_clean)
    address_clean = re.sub(r'Berlin\s*,?\s*Germany', 'Berlin, Germany', address_clean)
    
    address_clean = re.sub(r'THE\s+URBAN\s+CLUB', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'URBAN\s+CLUB', '', address_clean, flags=re.IGNORECASE)
    
    address_clean = re.sub(r'-\s*Pl[öo]n?zeile', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'Pl[öo]n?zeile\s*', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'\s*Pl[öo]n?zeile', '', address_clean, flags=re.IGNORECASE)
    
    address_clean = re.sub(r'BER\s+[MS]\s+mit\s+Balkon\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'BER\s+[MS]\s+mit\s+Balkon', '', address_clean, flags=re.IGNORECASE)
    
    address_clean = re.sub(r'ES\s+(?:City\s+studio|L\s+studio)\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'ES\s+City\s+studio\s+river\s+view\s+', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'river\s+view\s+', '', address_clean, flags=re.IGNORECASE)
    
    address_clean = re.sub(r'\d+\s+Zimmer\s+mit\s+Balkon,?\s*', '', address_clean, flags=re.IGNORECASE)
    
    address_clean = re.sub(r'Sequoia\s+Classic\s+Balcony\s+\d+-\d+\s+Month\s+/?\s*', '', address_clean, flags=re.IGNORECASE)
    
    if not re.search(r'BERLIN\s+[A-ZÄÖÜ\s\-]+(?:Classic|Long|Term|Balcony|Silver|Neon)', address_clean, re.IGNORECASE):
        address_clean = re.sub(r'\s*(?:Classic|Long|Term|Balcony|Silver|Neon)\s*\d*', '', address_clean, flags=re.IGNORECASE)
    
    address_clean = re.sub(r',\s*(\d{5})', r', \1', address_clean)
    address_clean = re.sub(r'(\d{5})\s*Berlin', r'\1 Berlin', address_clean)
    
    address_clean = re.sub(r'\s+', ' ', address_clean).strip()
    
    address_clean = re.sub(r'^,\s*', '', address_clean)
    address_clean = re.sub(r'\s*,+$', '', address_clean)
    address_clean = re.sub(r',\s*,+', ',', address_clean)
    
    non_berlin_cities = ['Hamburg', 'Hoppegarten', 'Potsdam', 'Munich', 'München', 'Frankfurt', 'Cologne', 'Köln', 'Neuenhagen', 'Teltow', 'Schönefeld', 'Ahrensfelde', 'Hennigsdorf', 'Glienicke', 'Nuthetal', 'Schöneiche', 'Stahnsdorf', 'Falkensee', 'Blankenfelde-Mahlow', 'Kleinmachnow', 'Schönwalde-Glien', 'Schulzendorf', 'Zeuthen', 'Bernau', 'Panketal', 'Fredersdorf', 'Großbeeren']
    
    actual_city = None
    
    postal_match = re.search(r'(\d{5})', address_clean)
    postal_code = None
    is_berlin_postal = False
    if postal_match:
        postal_code = postal_match.group(1)
        try:
            postal_int = int(postal_code)
            is_berlin_postal = (10115 <= postal_int <= 14199)
            if not is_berlin_postal:
                address_clean = re.sub(r',?\s*\d{5},?', '', address_clean)
                address_clean = re.sub(r'\s+', ' ', address_clean).strip()
                address_clean = re.sub(r',\s*,+', ',', address_clean)  # Remove double commas
                logger.debug(f"Removed non-Berlin postal code {postal_code} from address")
        except ValueError:
            pass
    
    original_address = address_clean
    extracted_street_name = None
    
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
        if wrong_city in address_clean:
            actual_city = wrong_city  # Remember the actual city for fallback
            street_match = re.search(r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|weg|Weg|platz|Platz|allee|Allee|str\.?|steig|Steig|wall|Wall))', address_clean, re.IGNORECASE)
            
            if street_match:
                street_name = street_match.group(1).strip()
                street_name = re.sub(r'\s*0[,\.]\d+', '', street_name).strip()
                
                if is_berlin_postal and postal_code:
                    address_clean = f"{street_name}, {postal_code} Berlin, Germany"
                    logger.debug(f"Fixed address: {street_name}, {postal_code} Berlin, Germany (removed {wrong_city})")
                else:
                    address_clean = f"{street_name}, Berlin, Germany"
                    logger.debug(f"Fixed address: {street_name}, Berlin, Germany (removed {wrong_city})")
            elif extracted_street_name:
                street_name = extracted_street_name
                if is_berlin_postal and postal_code:
                    address_clean = f"{street_name}, {postal_code} Berlin, Germany"
                    logger.debug(f"Fixed address: {street_name}, {postal_code} Berlin, Germany (removed {wrong_city})")
                else:
                    address_clean = f"{street_name}, Berlin, Germany"
                    logger.debug(f"Fixed address: {street_name}, Berlin, Germany (removed {wrong_city})")
            else:
                address_clean = re.sub(f'{wrong_city},?', '', address_clean, flags=re.IGNORECASE)
                address_clean = re.sub(r'\s+', ' ', address_clean).strip()
                address_clean = re.sub(r',\s*,+', ',', address_clean)  # Remove double commas
                logger.debug(f"Removed {wrong_city} from address")
            break  # Only fix the first matching wrong city
    
    address_variations = []
    
    if 'Hamburg' in address_clean or 'Heinrich-Heine' in address_clean:
        street_match = re.search(r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|weg|Weg|platz|Platz|allee|Allee))', address_clean, re.IGNORECASE)
        if street_match:
            street_name = street_match.group(1).strip()
            street_name = re.sub(r'\s*0[,\.]\d+', '', street_name).strip()
            address_variations.append(f"{street_name}, Berlin, Germany")
            address_variations.append("Heinrich-Heine-Straße, Berlin, Germany")
            address_variations.append("Heinrich-Heine-Straße, Mitte, Berlin, Germany")
    
    location_match = re.search(r'BERLIN\s+([A-ZÄÖÜ][A-ZÄÖÜ\s\-]+?)(?:\s+(?:Classic|Long|Term|Balcony|Silver|Neon|Premium|Standard))', address_clean, re.IGNORECASE)
    
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
        location_name_title = location_name.title()
        
        if re.search(r'FRANKFURTER\s+TOR', location_name, re.IGNORECASE):
            if "Frankfurter Tor, Berlin, Germany" not in address_variations:
                address_variations.insert(0, "Frankfurter Tor, Berlin, Germany")  # Try FIRST
            if "Frankfurter Tor, Friedrichshain, Berlin, Germany" not in address_variations:
                address_variations.insert(1, "Frankfurter Tor, Friedrichshain, Berlin, Germany")
            if "Frankfurter Allee, Berlin, Germany" not in address_variations:
                address_variations.insert(2, "Frankfurter Allee, Berlin, Germany")
            if "Frankfurter Tor" not in address_variations:
                address_variations.insert(3, "Frankfurter Tor")
        
        if f"{location_name_title}, Berlin, Germany" not in address_variations:
            address_variations.append(f"{location_name_title}, Berlin, Germany")
        
        if f"{location_name_title}" not in address_variations and len(location_name_title.split()) <= 3:
            address_variations.append(f"{location_name_title}")
        
        if f"{location_name}, Berlin, Germany" not in address_variations:
            address_variations.append(f"{location_name}, Berlin, Germany")
        
        districts = []
        
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
        
        special_places = {
            'Frankfurter Tor': ['Frankfurter Tor, Berlin, Germany',
                               'Frankfurter Tor, Friedrichshain, Berlin, Germany',
                               'Frankfurter Allee, Berlin, Germany'],
            'Alexanderplatz': ['Alexanderplatz, Berlin, Germany', 'Alexanderplatz, Mitte, Berlin, Germany'],
            'Potsdamer Platz': ['Potsdamer Platz, Berlin, Germany', 'Potsdamer Platz, Mitte, Berlin, Germany'],
            'Brandenburg Gate': ['Brandenburger Tor, Berlin, Germany', 'Brandenburger Tor, Mitte, Berlin, Germany'],
        }
        
        for place_name, place_variations in special_places.items():
            if re.search(place_name.replace(' ', r'\s+'), location_name, re.IGNORECASE):
                districts.extend(place_variations)
        
        for district_name, keywords in berlin_districts:
            for keyword in keywords:
                if re.search(keyword, location_name, re.IGNORECASE):
                    district_variation = f"{district_name}, Berlin, Germany"
                    if district_variation not in districts:
                        districts.append(district_variation)
                    break
        
        for district in districts:
            if district not in address_variations:
                address_variations.append(district)
        
        if '-' in location_name:
            parts = location_name.split('-')
            for part in parts:
                part = part.strip()
                if part:
                    variation = f"{part.title()}, Berlin, Germany"
                    if variation not in address_variations:
                        address_variations.append(variation)
    
    if 'Berlin' in address_clean or 'Germany' in address_clean:
        if address_clean not in address_variations:
            address_variations.append(address_clean)
    else:
        if f"{address_clean}, Berlin, Germany" not in address_variations:
            address_variations.append(f"{address_clean}, Berlin, Germany")
    
    street_patterns = [
        r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|str\.?|weg|Weg|platz|Platz|allee|Allee|damm|Damm|steig|Steig|wall|Wall))\s*[\d/]*',
        r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|str\.?|weg|Weg|platz|Platz|allee|Allee|damm|Damm|steig|Steig|wall|Wall))',
    ]
    
    for pattern in street_patterns:
        street_match = re.search(pattern, address_clean, re.IGNORECASE)
        if street_match:
            street = street_match.group(1).strip()
            street = re.sub(r'\s*0[,\.]\d+', '', street).strip()
            if street and len(street) > 3:
                if is_berlin_postal and postal_code:
                    variation = f"{street}, {postal_code} Berlin, Germany"
                    if variation not in address_variations:
                        address_variations.append(variation)
                variation = f"{street}, Berlin, Germany"
                if variation not in address_variations:
                    address_variations.append(variation)
                break
    
    street_postal_match = re.search(r'([A-Za-zÄÖÜäöüß\s\-]+(?:\d+[a-z]?)?),?\s*(\d{5})', address_clean)
    if street_postal_match:
        street = street_postal_match.group(1).strip()
        postal = street_postal_match.group(2)
        variation = f"{street}, {postal} Berlin, Germany"
        if variation not in address_variations:
            address_variations.append(variation)
    
    street_only = re.sub(r',\s*\d{5}.*', '', address_clean).strip()
    street_only = re.sub(r'\s+\d{5}.*', '', street_only).strip()
    if street_only and len(street_only) > 5 and not street_only.startswith('BERLIN'):
        variation = f"{street_only}, Berlin, Germany"
        if variation not in address_variations:
            address_variations.append(variation)
    
    if use_cache:
        cache = get_geocode_cache()
        for addr_var in address_variations:
            if addr_var in cache:
                return cache[addr_var]
    
    geolocator = Nominatim(user_agent="urban_technology_housing_finder")
    
    for addr_var in address_variations:
        for attempt in range(max_retries):
            try:
                location = geolocator.geocode(addr_var, timeout=10)
                
                if location:
                    coords = (location.latitude, location.longitude)
                    if use_cache:
                        cache = get_geocode_cache()
                        cache[addr_var] = coords
                        for addr in address_variations:
                            if addr not in cache:
                                cache[addr] = coords
                        cache[address_clean] = coords
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
    
    if actual_city or any(city in address_clean for city in non_berlin_cities):
        if not actual_city:
            for city in non_berlin_cities:
                if city in address_clean:
                    actual_city = city
                    break
        
        if actual_city:
            street_name_for_fallback = extracted_street_name
            
            if not street_name_for_fallback:
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
                        street_name_for_fallback = re.sub(r'ES\s+(?:City\s+studio|L\s+studio)\s+', '', street_name_for_fallback, flags=re.IGNORECASE)
                        street_name_for_fallback = re.sub(r'river\s+view\s+', '', street_name_for_fallback, flags=re.IGNORECASE)
                        street_name_for_fallback = re.sub(r'\d+\s+Zimmer\s+mit\s+Balkon', '', street_name_for_fallback, flags=re.IGNORECASE)
                        street_name_for_fallback = re.sub(r'Sequoia\s+Classic\s+Balcony.*?/', '', street_name_for_fallback, flags=re.IGNORECASE)
                        street_name_for_fallback = re.sub(re.escape(actual_city), '', street_name_for_fallback, flags=re.IGNORECASE)
                        street_name_for_fallback = re.sub(r'\s+', ' ', street_name_for_fallback).strip()
                        if street_name_for_fallback and len(street_name_for_fallback) > 2:
                            break
            
            if street_name_for_fallback and len(street_name_for_fallback) > 2:
                street_name_for_fallback = re.sub(r'\s*0[,\.]\d+', '', street_name_for_fallback).strip()
                fallback_address = f"{street_name_for_fallback}, {actual_city}, Germany"
                logger.debug(f"Trying fallback geocoding to actual city: {fallback_address}")
                try:
                    location = geolocator.geocode(fallback_address, timeout=10)
                    if location:
                        coords = (location.latitude, location.longitude)
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
    
    if address_clean:
        first_word_match = re.search(r'^([A-Za-zÄÖÜäöüß]+)', address_clean)
        if first_word_match:
            first_word = first_word_match.group(1)
            if len(first_word) > 3:  # Only if it's a meaningful word
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
    
    logger.warning(f"Failed to geocode: {address_clean[:50]}...")
    return None


def geocode_dataframe(df: pd.DataFrame, address_column: str = 'address', progress_callback=None) -> pd.DataFrame:
    if address_column not in df.columns:
        raise ValueError(f"Address column '{address_column}' not found in dataframe")
    
    df = df.copy()
    
    if 'latitude' not in df.columns:
        df['latitude'] = None
    if 'longitude' not in df.columns:
        df['longitude'] = None
    
    clear_geocode_cache()
    cache = get_geocode_cache()
    cache_hits = 0
    new_geocodes = 0
    logger.info(f"Starting geocoding with {len(cache)} cached entries")
    
    addresses_to_geocode = {}
    for idx, row in df.iterrows():
        address = row[address_column]
        
        if pd.isna(address) or address == '':
            continue
        
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
        provider = None
        provider_name = 'Unknown'
        geocode_func = geocode_address  # Default to base function
        
        if 'provider' in df.columns:
            first_idx = indices[0]
            provider = df.at[first_idx, 'provider'] if pd.notna(df.at[first_idx, 'provider']) else None
            
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
        
        address_normalized = str(address_str).strip()
        coords = None
        cache_key = None
        
        address_variations_to_check = [
            address_normalized,  # Original
            f"{address_normalized}, Berlin, Germany",  # With Berlin, Germany
            address_normalized.replace(', Germany', ''),  # Without Germany
            address_normalized.replace('Berlin, Germany', 'Berlin'),  # Without comma
            address_normalized.replace(', Berlin, Germany', ''),  # Just street
        ]
        
        cleaned_variations = []
        
        non_berlin_cities_list = ['Teltow', 'Schönefeld', 'Ahrensfelde', 'Hoppegarten', 'Potsdam', 'Hamburg', 
                                  'Hennigsdorf', 'Glienicke', 'Nuthetal', 'Schöneiche', 'Stahnsdorf', 'Falkensee',
                                  'Blankenfelde-Mahlow', 'Kleinmachnow', 'Schönwalde-Glien', 'Schulzendorf', 
                                  'Zeuthen', 'Bernau', 'Panketal', 'Fredersdorf', 'Großbeeren', 'Neuenhagen']
        
        for city in non_berlin_cities_list:
            if city in address_normalized:
                cleaned = re.sub(f'{re.escape(city)},?', '', address_normalized, flags=re.IGNORECASE)
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                cleaned = re.sub(r',\s*,+', ',', cleaned)
                if cleaned and cleaned not in cleaned_variations:
                    cleaned_variations.append(cleaned)
                    cleaned_variations.append(f"{cleaned}, Berlin, Germany")
        
        if 'BER' in address_normalized.upper() and 'mit' in address_normalized.lower():
            cleaned = re.sub(r'BER\s+[MS]\s+mit\s+Balkon\s*', '', address_normalized, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if cleaned and cleaned not in cleaned_variations:
                cleaned_variations.append(cleaned)
                cleaned_variations.append(f"{cleaned}, Berlin, Germany")
        
        if 'ES City' in address_normalized or 'ES L studio' in address_normalized:
            cleaned = re.sub(r'ES\s+(?:City\s+studio|L\s+studio)\s+', '', address_normalized, flags=re.IGNORECASE)
            cleaned = re.sub(r'river\s+view\s+', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if cleaned and cleaned not in cleaned_variations:
                cleaned_variations.append(cleaned)
                cleaned_variations.append(f"{cleaned}, Berlin, Germany")
        
        if 'Zimmer mit Balkon' in address_normalized:
            cleaned = re.sub(r'\d+\s+Zimmer\s+mit\s+Balkon,?\s*', '', address_normalized, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if cleaned and cleaned not in cleaned_variations:
                cleaned_variations.append(cleaned)
                cleaned_variations.append(f"{cleaned}, Berlin, Germany")
        
        if 'Sequoia' in address_normalized:
            cleaned = re.sub(r'Sequoia\s+Classic\s+Balcony\s+\d+-\d+\s+Month\s+/?\s*', '', address_normalized, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if cleaned and cleaned not in cleaned_variations:
                cleaned_variations.append(cleaned)
                cleaned_variations.append(f"{cleaned}, Berlin, Germany")
        
        street_match = re.search(r'^([^,]+?)(?:\s*,\s*\d{5}|,|$)', address_normalized)
        if street_match:
            street_only = street_match.group(1).strip()
            street_only = re.sub(r'BER\s+[MS]\s+mit\s+Balkon\s*', '', street_only, flags=re.IGNORECASE)
            street_only = re.sub(r'ES\s+(?:City\s+studio|L\s+studio)\s+', '', street_only, flags=re.IGNORECASE)
            street_only = re.sub(r'\d+\s+Zimmer\s+mit\s+Balkon', '', street_only, flags=re.IGNORECASE)
            street_only = re.sub(r'Sequoia\s+Classic\s+Balcony.*?/', '', street_only, flags=re.IGNORECASE)
            street_only = re.sub(r'\s+', ' ', street_only).strip()
            if street_only and len(street_only) > 3:
                cleaned_variations.append(f"{street_only}, Berlin, Germany")
        
        all_variations = address_variations_to_check + cleaned_variations
        
        for var in all_variations:
            if var in cache:
                cached_value = cache[var]
                if isinstance(cached_value, (list, tuple)) and len(cached_value) == 2:
                    coords = tuple(cached_value)
                    cache_key = var
                    cache_hits += 1
                    logger.debug(f"Cache HIT (exact): '{var}'")
                    break
        
        if not coords:
            var_lower = address_normalized.lower()
            street1_match = re.search(r'^([A-Za-zÄÖÜäöüß\s\-]+?)(?:\s*,\s*\d{5}|,|$)', address_normalized, re.IGNORECASE)
            street1_name = street1_match.group(1).strip().lower() if street1_match else None
            
            for key in cache.keys():
                key_lower = key.lower()
                if street1_name and street1_name in key_lower:
                    street2_match = re.search(r'^([A-Za-zÄÖÜäöüß\s\-]+?)(?:\s*,\s*\d{5}|,|$)', key, re.IGNORECASE)
                    if street2_match:
                        street2_name = street2_match.group(1).strip().lower()
                        if street1_name == street2_name or (len(street1_name) > 5 and street1_name in street2_name) or (len(street2_name) > 5 and street2_name in street1_name):
                            cached_value = cache[key]
                            if isinstance(cached_value, (list, tuple)) and len(cached_value) == 2:
                                coords = tuple(cached_value)
                                cache_key = key
                                cache_hits += 1
                                logger.debug(f"Cache HIT (partial): '{address_normalized}' -> '{key}'")
                                break
        
        if not coords:
            logger.debug(f"Cache MISS - geocoding ({provider_name}): '{address_normalized}'")
            try:
                coords = geocode_func(address_str, delay=0.3, use_cache=True)
            except Exception as e:
                logger.error(f"Error in {provider_name} geocoding: {e}")
                coords = geocode_address(address_str, delay=0.3, use_cache=True)
            if coords:
                new_geocodes += 1
                logger.info(f"New geocode: '{address_normalized}' -> ({coords[0]:.6f}, {coords[1]:.6f})")
                cache[address_normalized] = coords
                for var in [f"{address_normalized}, Berlin, Germany", address_normalized.replace(', Germany', '')]:
                    if var not in cache:
                        cache[var] = coords
                try:
                    save_geocode_cache(cache)
                    logger.debug(f"Saved to cache: '{address_normalized}'")
                except Exception as e:
                    logger.error(f"Failed to save cache: {e}")
            else:
                logger.warning(f"Geocoding failed for: '{address_normalized}'")
        
        if coords:
            for idx in indices:
                df.at[idx, 'latitude'] = float(coords[0])
                df.at[idx, 'longitude'] = float(coords[1])
        else:
            logger.warning(f"Failed to geocode address: {address_str[:60]}...")
        
        processed += 1
        
        successful = cache_hits + new_geocodes
        if progress_callback:
            progress_callback(processed, total_unique, cache_hits, new_geocodes)
        elif processed % 10 == 0 or processed == total_unique:
            logger.info(f"Progress: {processed}/{total_unique} addresses | {successful} successful ({cache_hits} cached, {new_geocodes} new)")
        
        if processed % 50 == 0 and new_geocodes > 0:
            clear_geocode_cache()
            cache = get_geocode_cache()
            logger.debug(f"Reloaded cache: now {len(cache)} entries")
    
    save_geocode_cache(cache)
    
    geocoded_count = df['latitude'].notna().sum()
    logger.info(f"Successfully geocoded {geocoded_count}/{len(df)} addresses ({cache_hits} from cache, {new_geocodes} new)")
    
    logger.info(f"\n{'='*80}")
    logger.info(f"ALL ROOMS WITH COORDINATES ({geocoded_count} total):")
    logger.info(f"{'='*80}")
    
    if geocoded_count > 0:
        if 'provider' in df.columns:
            df_sorted = df[df['latitude'].notna()].sort_values(['provider', 'address']).copy()
        else:
            df_sorted = df[df['latitude'].notna()].sort_values('address').copy()
        
        for idx, row in df_sorted.iterrows():
            provider = row.get('provider', 'N/A') if 'provider' in df.columns else 'N/A'
            address = row.get('address', 'N/A')
            lat = row['latitude']
            lon = row['longitude']
            
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
    if 'Berlin' not in university_name_or_address:
        query = f"{university_name_or_address}, Berlin, Germany"
    else:
        query = university_name_or_address
    
    coords = geocode_address(query)
    
    if coords:
        logger.info(f"Geocoded university: {university_name_or_address}")
        logger.info(f"  Coordinates: ({coords[0]:.6f}, {coords[1]:.6f})")
    
    return coords

