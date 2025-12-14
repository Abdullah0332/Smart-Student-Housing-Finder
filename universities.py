"""
Berlin Universities Data
========================

Contains a comprehensive list of major public and private universities in Berlin
with their addresses and coordinates for easy selection in the housing finder app.

Urban Technology Relevance:
- Understanding university locations helps analyze student housing demand patterns
- Spatial distribution of educational institutions affects urban mobility patterns
"""

# Berlin Major Universities (Public and Private)
BERLIN_UNIVERSITIES = {
    # Public Universities
    "Technische Universität Berlin (TU Berlin)": {
        "name": "Technische Universität Berlin",
        "address": "Straße des 17. Juni 135, 10623 Berlin, Germany",
        "type": "Public",
        "latitude": 52.5125,
        "longitude": 13.3269,
        "abbreviation": "TU Berlin"
    },
    "Humboldt-Universität zu Berlin": {
        "name": "Humboldt-Universität zu Berlin",
        "address": "Unter den Linden 6, 10117 Berlin, Germany",
        "type": "Public",
        "latitude": 52.5170,
        "longitude": 13.3939,
        "abbreviation": "HU Berlin"
    },
    "Freie Universität Berlin (FU Berlin)": {
        "name": "Freie Universität Berlin",
        "address": "Kaiserswerther Str. 16-18, 14195 Berlin, Germany",
        "type": "Public",
        "latitude": 52.4538,
        "longitude": 13.2900,
        "abbreviation": "FU Berlin"
    },
    "Universität der Künste Berlin (UdK Berlin)": {
        "name": "Universität der Künste Berlin",
        "address": "Einsteinufer 43, 10587 Berlin, Germany",
        "type": "Public",
        "latitude": 52.5156,
        "longitude": 13.3281,
        "abbreviation": "UdK Berlin"
    },
    "Charité - Universitätsmedizin Berlin": {
        "name": "Charité - Universitätsmedizin Berlin",
        "address": "Charitéplatz 1, 10117 Berlin, Germany",
        "type": "Public",
        "latitude": 52.5275,
        "longitude": 13.3786,
        "abbreviation": "Charité"
    },
    
    # Private Universities
    "ESMT Berlin (European School of Management and Technology)": {
        "name": "ESMT Berlin",
        "address": "Schlossplatz 1, 10178 Berlin, Germany",
        "type": "Private",
        "latitude": 52.5163,
        "longitude": 13.4014,
        "abbreviation": "ESMT"
    },
    "Hertie School": {
        "name": "Hertie School",
        "address": "Friedrichstraße 180, 10117 Berlin, Germany",
        "type": "Private",
        "latitude": 52.5156,
        "longitude": 13.3881,
        "abbreviation": "Hertie School"
    },
    "Bard College Berlin": {
        "name": "Bard College Berlin",
        "address": "Platanenstraße 24, 13156 Berlin, Germany",
        "type": "Private",
        "latitude": 52.5856,
        "longitude": 13.4014,
        "abbreviation": "Bard College"
    },
    "SRH Hochschule Berlin": {
        "name": "SRH Hochschule Berlin",
        "address": "Ernst-Reuter-Platz 10, 10587 Berlin, Germany",
        "type": "Private",
        "latitude": 52.5128,
        "longitude": 13.3219,
        "abbreviation": "SRH Berlin"
    },
    "Berlin School of Business and Innovation (BSBI)": {
        "name": "Berlin School of Business and Innovation",
        "address": "Potsdamer Straße 180-182, 10783 Berlin, Germany",
        "type": "Private",
        "latitude": 52.4964,
        "longitude": 13.3600,
        "abbreviation": "BSBI"
    },
    "CODE University of Applied Sciences": {
        "name": "CODE University of Applied Sciences",
        "address": "Lohmühlenstraße 65, 12435 Berlin, Germany",
        "type": "Private",
        "latitude": 52.4908,
        "longitude": 13.4564,
        "abbreviation": "CODE"
    },
    "Berlin International University of Applied Sciences": {
        "name": "Berlin International University of Applied Sciences",
        "address": "Salzufer 6, 10587 Berlin, Germany",
        "type": "Private",
        "latitude": 52.5122,
        "longitude": 13.3231,
        "abbreviation": "BIUAS"
    },
    "BSP Business School Berlin": {
        "name": "BSP Business School Berlin",
        "address": "Calandrellistraße 1-9, 12247 Berlin, Germany",
        "type": "Private",
        "latitude": 52.4400,
        "longitude": 13.3200,
        "abbreviation": "BSP"
    },
    "Hochschule für Technik und Wirtschaft Berlin (HTW Berlin)": {
        "name": "Hochschule für Technik und Wirtschaft Berlin",
        "address": "Treskowallee 8, 10318 Berlin, Germany",
        "type": "Public",
        "latitude": 52.4567,
        "longitude": 13.5314,
        "abbreviation": "HTW Berlin"
    },
    "Hochschule für Wirtschaft und Recht Berlin (HWR Berlin)": {
        "name": "Hochschule für Wirtschaft und Recht Berlin",
        "address": "Badensche Straße 52, 10825 Berlin, Germany",
        "type": "Public",
        "latitude": 52.4800,
        "longitude": 13.3400,
        "abbreviation": "HWR Berlin"
    },
    "Beuth Hochschule für Technik Berlin": {
        "name": "Beuth Hochschule für Technik Berlin",
        "address": "Luxemburger Straße 10, 13353 Berlin, Germany",
        "type": "Public",
        "latitude": 52.5400,
        "longitude": 13.3500,
        "abbreviation": "Beuth"
    },
    "Alice Salomon Hochschule Berlin": {
        "name": "Alice Salomon Hochschule Berlin",
        "address": "Alice-Salomon-Platz 5, 12627 Berlin, Germany",
        "type": "Public",
        "latitude": 52.5400,
        "longitude": 13.5800,
        "abbreviation": "ASH Berlin"
    },
    "Katholische Hochschule für Sozialwesen Berlin": {
        "name": "Katholische Hochschule für Sozialwesen Berlin",
        "address": "Köpenicker Allee 39-57, 10318 Berlin, Germany",
        "type": "Private",
        "latitude": 52.4900,
        "longitude": 13.5300,
        "abbreviation": "KHSB"
    },
    "Hochschule für Musik Hanns Eisler Berlin": {
        "name": "Hochschule für Musik Hanns Eisler Berlin",
        "address": "Charlottenstraße 55, 10117 Berlin, Germany",
        "type": "Public",
        "latitude": 52.5150,
        "longitude": 13.3900,
        "abbreviation": "HfM Berlin"
    }
}


def get_university_list():
    """
    Get list of universities formatted for dropdown display.
    
    Returns:
    --------
    list
        List of university display names
    """
    return list(BERLIN_UNIVERSITIES.keys())


def get_university_info(university_name: str):
    """
    Get information for a specific university.
    
    Parameters:
    -----------
    university_name : str
        Full name of the university (as in BERLIN_UNIVERSITIES keys)
    
    Returns:
    --------
    dict or None
        University information including name, address, coordinates, type
    """
    return BERLIN_UNIVERSITIES.get(university_name)


def get_university_coords(university_name: str):
    """
    Get coordinates for a specific university.
    
    Parameters:
    -----------
    university_name : str
        Full name of the university
    
    Returns:
    --------
    tuple or None
        (latitude, longitude) if found
    """
    info = get_university_info(university_name)
    if info:
        return (info['latitude'], info['longitude'])
    return None


def get_universities_by_type(university_type: str = None):
    """
    Get universities filtered by type (Public or Private).
    
    Parameters:
    -----------
    university_type : str or None
        'Public', 'Private', or None for all
    
    Returns:
    --------
    dict
        Filtered dictionary of universities
    """
    if university_type is None:
        return BERLIN_UNIVERSITIES
    
    return {
        name: info for name, info in BERLIN_UNIVERSITIES.items()
        if info['type'] == university_type
    }

