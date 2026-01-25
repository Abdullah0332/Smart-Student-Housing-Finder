# Smart Student Housing Finder - Berlin

## 🏠 Urban Technology Project

A comprehensive system for ranking student accommodations in Berlin based on:
- **Cost** (affordability)
- **Commute Time** (BVG public transport)
- **Walking Distance** (to transit stops)
- **Transport Accessibility** (transfers, modes)

---

## 📋 Project Overview

This project demonstrates how **urban mobility data** and **geospatial analysis** can inform housing decisions. It integrates:

- **Local GTFS Data** for realistic journey planning (offline)
- **OpenStreetMap/Nominatim** for geocoding
- **Geospatial network analysis** for distance calculations
- **Multi-criteria decision analysis** for ranking

This qualifies as an **Urban Technology project** by analyzing how transport infrastructure accessibility affects residential desirability and housing market dynamics.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

### 3. Use the Application

1. **Select University**: Choose your university from the dropdown
2. **Data Loading**: Default accommodation data loads automatically
3. **Run Analysis**: Click "Run Full Analysis" (geocoding + transport + scoring)
4. **View Results**: Explore rankings, provider comparisons, and interactive map

---

## 📁 Project Structure

```
project/
├── app.py                      # Main Streamlit application (entry point)
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── .gitignore                  # Git ignore rules
│
├── config/                     # Configuration
│   ├── __init__.py
│   └── settings.py             # App settings, constants, weights
│
├── src/                        # Source code modules
│   ├── __init__.py
│   │
│   ├── data/                   # Data loading and management
│   │   ├── __init__.py
│   │   ├── loader.py           # CSV/Excel data loading
│   │   └── universities.py     # Berlin universities database
│   │
│   ├── geo/                    # Geospatial modules
│   │   ├── __init__.py
│   │   └── geocoding.py        # Address → coordinates (Nominatim)
│   │
│   ├── transport/              # Transport analysis
│   │   ├── __init__.py
│   │   ├── gtfs.py             # GTFS data processing (BVG)
│   │   └── commute.py          # Commute calculation
│   │
│   ├── analysis/               # Analysis and scoring
│   │   ├── __init__.py
│   │   ├── scoring.py          # Student suitability scoring
│   │   ├── area.py             # District-level analysis
│   │   └── research.py         # Research questions analysis
│   │
│   └── visualization/          # Visualization modules
│       ├── __init__.py
│       ├── maps.py             # Folium map visualization
│       └── charts.py           # Matplotlib charts
│
├── data/                       # Data files
│   └── Accomodations.csv       # Accommodation data
│
└── GTFS/                       # GTFS transit data (Berlin BVG)
    ├── stops.txt
    ├── routes.txt
    ├── trips.txt
    └── stop_times.txt
```

---

## 🔧 Key Features

### Data Processing (`src/data/`)
- Loads accommodation data from Excel/CSV
- Filters for Berlin-only accommodations
- Smart column mapping (rent, address, provider)
- Handles missing data gracefully

### Geocoding (`src/geo/`)
- Converts addresses to coordinates using Nominatim
- Provider-specific geocoding functions
- Respects rate limits (1 request/second)
- Persistent caching (geocode_cache.json)

### Transport Analysis (`src/transport/`)
- Uses local GTFS data (offline, fast)
- Finds nearest BVG public transport stops
- Calculates door-to-door commute times
- Identifies transport modes (U-Bahn, S-Bahn, Tram, Bus)
- Counts transfers

### Scoring System (`src/analysis/`)
- **Affordability Score**: Lower rent = higher score (35%)
- **Commute Score**: Shorter commute = higher score (40%)
- **Walking Score**: Shorter walk = higher score (15%)
- **Transfers Score**: Fewer transfers = higher score (10%)
- **Composite Score**: Weighted combination (0-100 scale)

### Visualization (`src/visualization/`)
- Interactive map with apartment locations
- Color-coded by score, rent, or commute time
- University location marker
- Multiple base map layers
- District-level charts and analysis

---

## 📊 Research Questions

The system includes statistical analysis for academic research:

1. **RQ1**: How does public transport accessibility affect housing affordability?
2. **RQ2**: Which Berlin districts offer the best transport-housing balance?
3. **RQ3**: What is the relationship between walking distance and room availability?
4. **RQ4**: How do different platforms vary in transport accessibility?
5. **RQ5**: What is the spatial equity of student housing in Berlin?

---

## ⚙️ Configuration

All configuration is centralized in `config/settings.py`:

### Scoring Weights
```python
SCORING_WEIGHTS = {
    'rent': 0.35,
    'commute': 0.40,
    'walking': 0.15,
    'transfers': 0.10
}
```

### Transport Settings
```python
TRANSPORT = {
    'walking_speed_kmh': 5.0,
    'transit_speed_kmh': 30.0,
    'transfer_penalty_minutes': 5,
    'max_walking_radius_m': 2000,
}
```

---

## 🎓 Urban Technology Relevance

This project demonstrates several key urban technology concepts:

1. **Spatial Accessibility Analysis**: Measuring how accessible locations are via public transport
2. **Transport Equity**: Analyzing how transport infrastructure affects housing choices
3. **Network Analysis**: Using graph theory for route planning and distance calculations
4. **Multi-Criteria Decision Making**: Combining multiple factors for informed decisions
5. **Geospatial Visualization**: Mapping urban patterns and accessibility metrics

---

## 📝 Notes

### Performance
- GTFS data processing is fast and offline
- Geocoding may take time for new addresses (cached for reuse)
- Consider testing with a subset first for large datasets

### Limitations
- Requires GTFS data in the GTFS/ folder
- Some addresses may fail to geocode
- Commute times are estimates based on average speeds

---

## 📚 Dependencies

See `requirements.txt` for complete list. Key libraries:

- **pandas**: Data manipulation
- **streamlit**: Web interface
- **geopy**: Geocoding
- **folium**: Map visualization
- **scipy**: Statistical analysis
- **scikit-learn**: Data normalization
- **matplotlib**: Charts

---

## 🤝 Contributing

This is a course project. For improvements:
1. Test with sample data
2. Ensure proper error handling
3. Add clear documentation
4. Follow the modular structure

---

## 📄 License

Educational project for Urban Technology course.

---

## 🙏 Acknowledgments

- **BVG** for GTFS transit data
- **OpenStreetMap** contributors for geospatial data
- **Nominatim** for geocoding service

---

**Happy apartment hunting! 🏠🚇**
