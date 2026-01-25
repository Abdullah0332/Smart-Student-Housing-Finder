import time
import json
import os
import re
from pathlib import Path
from typing import Tuple, Optional, Dict, Callable

import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import GEOCODING, NON_BERLIN_CITIES, BERLIN_POSTAL_RANGE, GEOCODE_CACHE_FILE

_geocode_cache = None


def load_geocode_cache() -> Dict[str, Tuple[float, float]]:
    cache_file = str(GEOCODE_CACHE_FILE)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                result = {}
                for k, v in cache.items():
                    if isinstance(v, (list, tuple)) and len(v) == 2:
                        try:
                            result[k] = (float(v[0]), float(v[1]))
                        except (ValueError, TypeError):
                            continue
                    elif isinstance(v, dict) and 'lat' in v and 'lon' in v:
                        try:
                            result[k] = (float(v['lat']), float(v['lon']))
                        except (ValueError, TypeError):
                            continue
                return result
        except Exception:
            return {}
    return {}


def save_geocode_cache(cache: Dict[str, Tuple[float, float]]) -> None:
    try:
        cache_serializable = {
            k: list(v) for k, v in cache.items()
            if isinstance(v, (tuple, list)) and len(v) == 2
        }
        with open(str(GEOCODE_CACHE_FILE), 'w', encoding='utf-8') as f:
            json.dump(cache_serializable, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_geocode_cache() -> Dict[str, Tuple[float, float]]:
    global _geocode_cache
    if _geocode_cache is None:
        _geocode_cache = load_geocode_cache()
    return _geocode_cache


def clear_geocode_cache() -> None:
    global _geocode_cache
    _geocode_cache = None


def _clean_address(address: str) -> str:
    address_clean = str(address).strip()
    address_clean = re.sub(r'[\n\r\t]+', ' ', address_clean)
    address_clean = re.sub(r'BerlinGermany', 'Berlin, Germany', address_clean)
    address_clean = re.sub(r'Berlin\s+Germany', 'Berlin, Germany', address_clean)
    address_clean = re.sub(r'Berlin\s*,?\s*Germany', 'Berlin, Germany', address_clean)
    address_clean = re.sub(r'THE\s+URBAN\s+CLUB', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'URBAN\s+CLUB', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'-\s*Pl[öo]n?zeile', '', address_clean, flags=re.IGNORECASE)
    address_clean = re.sub(r'Pl[öo]n?zeile\s*', '', address_clean, flags=re.IGNORECASE)
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
    
    return address_clean


def _is_berlin_postal(postal_code: str) -> bool:
    try:
        postal_int = int(postal_code)
        return BERLIN_POSTAL_RANGE[0] <= postal_int <= BERLIN_POSTAL_RANGE[1]
    except ValueError:
        return False


def _generate_address_variations(address_clean: str) -> list:
    variations = []
    
    location_match = re.search(
        r'BERLIN\s+([A-ZÄÖÜ][A-ZÄÖÜ\s\-]+?)(?:\s+(?:Classic|Long|Term|Balcony|Silver|Neon|Premium|Standard))',
        address_clean, re.IGNORECASE
    )
    
    if location_match:
        location_name = location_match.group(1).strip()
        location_name = re.sub(r'\s+', ' ', location_name).strip()
        location_name_title = location_name.title()
        
        if re.search(r'FRANKFURTER\s+TOR', location_name, re.IGNORECASE):
            variations.extend([
                "Frankfurter Tor, Berlin, Germany",
                "Frankfurter Tor, Friedrichshain, Berlin, Germany",
                "Frankfurter Allee, Berlin, Germany"
            ])
        
        variations.append(f"{location_name_title}, Berlin, Germany")
        variations.append(f"{location_name}, Berlin, Germany")
        
        if '-' in location_name:
            parts = location_name.split('-')
            for part in parts:
                part = part.strip().title()
                if part:
                    variations.append(f"{part}, Berlin, Germany")
    
    street_patterns = [
        r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|str\.?|weg|Weg|platz|Platz|allee|Allee|damm|Damm|steig|Steig|wall|Wall))',
    ]
    
    for pattern in street_patterns:
        street_match = re.search(pattern, address_clean, re.IGNORECASE)
        if street_match:
            street = street_match.group(1).strip()
            street = re.sub(r'\s*0[,\.]\d+', '', street).strip()
            if street and len(street) > 3:
                variations.append(f"{street}, Berlin, Germany")
                break
    
    if 'Berlin' in address_clean or 'Germany' in address_clean:
        if address_clean not in variations:
            variations.append(address_clean)
    else:
        variations.append(f"{address_clean}, Berlin, Germany")
    
    return variations


def geocode_address(
    address: str,
    max_retries: int = None,
    delay: float = None,
    use_cache: bool = True
) -> Optional[Tuple[float, float]]:
    max_retries = max_retries or GEOCODING['max_retries']
    delay = delay or GEOCODING['delay']
    
    address_clean = _clean_address(address)
    
    for wrong_city in NON_BERLIN_CITIES:
        if wrong_city in address_clean:
            street_match = re.search(
                r'([A-Za-zÄÖÜäöüß\s\-]+(?:straße|strasse|Straße|Strasse|weg|Weg|platz|Platz|allee|Allee))',
                address_clean, re.IGNORECASE
            )
            if street_match:
                street_name = street_match.group(1).strip()
                address_clean = f"{street_name}, Berlin, Germany"
            break
    
    address_variations = _generate_address_variations(address_clean)
    
    if use_cache:
        cache = get_geocode_cache()
        for addr_var in address_variations:
            if addr_var in cache:
                return cache[addr_var]
    
    geolocator = Nominatim(user_agent=GEOCODING['user_agent'])
    
    for addr_var in address_variations:
        for attempt in range(max_retries):
            try:
                location = geolocator.geocode(addr_var, timeout=GEOCODING['timeout'])
                
                if location:
                    coords = (location.latitude, location.longitude)
                    if use_cache:
                        cache = get_geocode_cache()
                        cache[addr_var] = coords
                        cache[address_clean] = coords
                        if address_clean != str(address).strip():
                            cache[str(address).strip()] = coords
                        save_geocode_cache(cache)
                    return coords
                
                time.sleep(delay)
                
            except (GeocoderTimedOut, GeocoderServiceError):
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))
                    continue
                break
            except Exception:
                break
    
    return None


def geocode_dataframe(
    df: pd.DataFrame,
    address_column: str = 'address',
    progress_callback: Optional[Callable] = None
) -> pd.DataFrame:
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
    processed = 0
    
    for address_str, indices in addresses_to_geocode.items():
        address_normalized = str(address_str).strip()
        coords = None
        
        cache_variations = [
            address_normalized,
            f"{address_normalized}, Berlin, Germany",
            address_normalized.replace(', Germany', ''),
        ]
        
        for var in cache_variations:
            if var in cache:
                cached_value = cache[var]
                if isinstance(cached_value, (list, tuple)) and len(cached_value) == 2:
                    coords = tuple(cached_value)
                    cache_hits += 1
                    break
        
        if not coords:
            coords = geocode_address(address_str, delay=0.3, use_cache=True)
            if coords:
                new_geocodes += 1
                cache[address_normalized] = coords
                save_geocode_cache(cache)
        
        if coords:
            for idx in indices:
                df.at[idx, 'latitude'] = float(coords[0])
                df.at[idx, 'longitude'] = float(coords[1])
        
        processed += 1
        
        if progress_callback:
            progress_callback(processed, total_unique, cache_hits, new_geocodes)
        
        if processed % 50 == 0 and new_geocodes > 0:
            clear_geocode_cache()
            cache = get_geocode_cache()
    
    save_geocode_cache(cache)
    return df


def geocode_university(university_name_or_address: str) -> Optional[Tuple[float, float]]:
    if 'Berlin' not in university_name_or_address:
        query = f"{university_name_or_address}, Berlin, Germany"
    else:
        query = university_name_or_address
    return geocode_address(query)
