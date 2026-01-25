import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
GTFS_DIR = BASE_DIR / "GTFS"
GEOCODE_CACHE_FILE = BASE_DIR / "geocode_cache.json"
DEFAULT_ACCOMMODATION_FILE = "data/Accomodations.csv"

SCORING_WEIGHTS = {
    'rent': 0.35,
    'commute': 0.40,
    'walking': 0.15,
    'transfers': 0.10
}

AREA_SCORING_WEIGHTS = {
    'rent': 0.30,
    'commute': 0.30,
    'walking': 0.20,
    'availability': 0.20
}

GEOCODING = {
    'user_agent': 'urban_technology_housing_finder',
    'timeout': 10,
    'max_retries': 3,
    'delay': 0.5,
    'rate_limit': 1.0
}

TRANSPORT = {
    'walking_speed_kmh': 5.0,
    'transit_speed_kmh': 30.0,
    'transfer_penalty_minutes': 5,
    'max_walking_radius_m': 2000,
}

MAP = {
    'default_zoom': 12,
    'detail_zoom': 16,
    'berlin_center': (52.52, 13.405),
    'tile_layers': ['OpenStreetMap', 'CartoDB positron', 'CartoDB dark_matter'],
    'cluster_radius': 50,
}

UI = {
    'rooms_per_page': 50,
    'max_providers_display': 10,
}

BERLIN_BOUNDS = {
    'north': 52.7,
    'south': 52.3,
    'east': 13.8,
    'west': 13.0
}

BERLIN_POSTAL_RANGE = (10115, 14199)

NON_BERLIN_CITIES = [
    'Hoppegarten', 'Potsdam', 'Hamburg', 'Munich', 'München', 'Frankfurt',
    'Cologne', 'Köln', 'Neuenhagen', 'Teltow', 'Schönefeld', 'Ahrensfelde',
    'Hennigsdorf', 'Glienicke', 'Nuthetal', 'Schöneiche', 'Stahnsdorf',
    'Falkensee', 'Blankenfelde-Mahlow', 'Kleinmachnow', 'Schönwalde-Glien',
    'Schulzendorf', 'Zeuthen', 'Bernau', 'Panketal', 'Fredersdorf', 'Großbeeren'
]

TRANSPORT_MODES = {
    'subway': {'display': 'U-Bahn', 'color': '#0066cc'},
    'suburban': {'display': 'S-Bahn', 'color': '#00cc00'},
    'bus': {'display': 'Bus', 'color': '#ff6600'},
    'tram': {'display': 'Tram', 'color': '#cc0000'},
    'ferry': {'display': 'Ferry', 'color': '#0066ff'},
    'public_transport': {'display': 'Public Transport', 'color': '#8e44ad'}
}

COLUMN_MAPPINGS = {
    'rent_keywords': [
        'rent', 'price', 'miete', 'all-in', 'all in', 'all-inclusive',
        'all inclusive', 'cost', 'kosten', 'preis', 'fee', 'charge', 'amount', 'betrag'
    ],
    'address_keywords': [
        ['address', 'adresse'],
        ['street', 'strasse', 'straße', 'weg', 'allee', 'platz'],
        ['location', 'location name'],
        ['city', 'stadt']
    ],
    'provider_keywords': [
        'provider', 'platform', 'source', 'company', 'brand', 'supplier'
    ],
    'city_keywords': ['City', 'city', 'City Name', 'Stadt']
}

DEFAULT_ENABLED_PROVIDERS = [
    '66 Monkeys', 'Havens Living', 'House of CO', 'Neonwood',
    'The Urban Club', 'Wunderflats', 'Zimmerei', 'Mietcampus',
    'My i Live Home', 'The Fizz', 'Ernstl München'
]
