# Smart Student Housing Finder - Complete Documentation

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Data Flow](#data-flow)
4. [Module Documentation](#module-documentation)
5. [User Workflow](#user-workflow)
6. [Caching System](#caching-system)
7. [API Integration](#api-integration)
8. [Scoring Algorithm](#scoring-algorithm)
9. [Visualization](#visualization)
10. [Configuration](#configuration)

---

## 🎯 Project Overview

**Smart Student Housing Finder** is an Urban Technology project that helps students find the best accommodation in Berlin based on:
- **Cost** (rent affordability)
- **Commute Time** (door-to-door travel time to university)
- **BVG Accessibility** (walking distance to public transport)
- **Transport Quality** (number of transfers, transport modes)

The system ranks apartments using a composite suitability score and provides interactive geospatial visualization.

---

## 🏗️ System Architecture

### Module Structure

```
project/
├── app.py                 # Main Streamlit application (UI & orchestration)
├── data_loader.py         # Excel/CSV data loading & preprocessing
├── geocoding.py          # Address → coordinates conversion (Nominatim)
├── transport.py          # BVG API integration (stops & journey planning)
├── transport_cache.py    # BVG API response caching
├── walking.py            # Walking distance calculations (OSMnx)
├── scoring.py            # Multi-criteria scoring & ranking
├── visualization.py      # Interactive maps (Folium)
├── universities.py       # Predefined Berlin universities data
└── requirements.txt     # Python dependencies
```

### Data Flow Diagram

```
Excel/CSV File
    ↓
[data_loader.py] → Filter Berlin → Clean Data → Extract Rent/Address
    ↓
[geocoding.py] → Check Cache → Geocode Addresses → Store Coordinates
    ↓
[transport.py] → Find Nearest Stop → Plan Journey → Calculate Commute
    ↓
[scoring.py] → Calculate Scores → Rank Apartments
    ↓
[visualization.py] → Create Map → Display Results
    ↓
Streamlit UI → User Interaction
```

---

## 📊 Data Flow

### Step 1: Data Loading (`data_loader.py`)

**Input:** Excel/CSV file (`Accomodations.csv`)

**Process:**
1. Load file (handles Excel/CSV formats)
2. Filter rows where city = "Berlin"
3. Identify columns:
   - `address`: "Address", "Location Name", etc.
   - `rent`: "Rent (in €/All-In)", "Rent", "All-In", etc.
   - `provider`: "Provider", "Provider Name"
4. Clean rent values:
   - Remove currency symbols (€, EUR, Euro)
   - Convert commas to dots
   - Extract numeric values
   - Filter out invalid/zero rents
5. Apply preview limit (50 rooms if preview mode enabled)

**Output:** Cleaned DataFrame with columns: `address`, `rent`, `provider`, `city`

**Key Functions:**
- `load_accommodation_data(file_path, limit=None)` → Returns DataFrame

---

### Step 2: Geocoding (`geocoding.py`)

**Input:** DataFrame with `address` column

**Process:**
1. **Cache Check:**
   - Load `geocode_cache.json`
   - Check if address already geocoded
   - If cached, use stored coordinates

2. **Geocoding:**
   - For new addresses, call Nominatim API
   - Add "Berlin, Germany" if not present
   - Retry up to 3 times on failure
   - Store results in cache

3. **Optimization:**
   - Process unique addresses only
   - Apply coordinates to all rows with same address
   - Skip already-geocoded rows

**Output:** DataFrame with `latitude` and `longitude` columns

**Cache File:** `geocode_cache.json`
```json
{
  "Address, Berlin, Germany": [52.5200, 13.4050],
  ...
}
```

**Key Functions:**
- `geocode_address(address, use_cache=True)` → Returns (lat, lon) or None
- `geocode_dataframe(df, progress_callback)` → Returns DataFrame with coordinates

---

### Step 3: Transport Analysis (`transport.py`)

**Input:** DataFrame with coordinates + University coordinates

**Process:**

#### 3.1 Find Nearest Stop
1. **Cache Check:**
   - Check `bvg_cache/` for stop lookup
   - Use cached stop if available

2. **API Call:**
   - Call BVG API: `GET /stops/nearby`
   - Parameters: `latitude`, `longitude`, `radius=1000m`
   - Get top 5 nearest stops
   - Return nearest stop with distance

3. **Calculate Walking:**
   - Distance from apartment to stop
   - Walking time = (distance / 1000) / 5 * 60 minutes
   - (Assumes 5 km/h walking speed)

#### 3.2 Plan Journey
1. **Cache Check:**
   - Check `bvg_cache/` for journey
   - Cache key based on stop coordinates + university coordinates

2. **API Call:**
   - Call BVG API: `GET /journeys`
   - Parameters: from (stop), to (university)
   - Get best route

3. **Extract Journey Info:**
   - Duration (convert seconds to minutes)
   - Number of transfers
   - Transport modes (U-Bahn, S-Bahn, Bus, Tram)
   - Route details (line names, stops)

4. **Calculate Total Commute:**
   - Total = Walking time + Transit time

**Output:** DataFrame with columns:
- `nearest_stop_name`
- `nearest_stop_distance_m`
- `walking_time_minutes`
- `transit_time_minutes`
- `total_commute_minutes`
- `transfers`
- `transport_modes`
- `route_details` (JSON string)

**Cache Directory:** `bvg_cache/`
- Files: `{hash}.json` (MD5 hash of coordinates)
- Structure:
```json
{
  "journey": {
    "duration_minutes": 25,
    "transfers": 1,
    "modes": ["subway", "bus"],
    "route_details": [...]
  }
}
```

**Key Functions:**
- `find_nearest_stop(lat, lon)` → Returns stop dict or None
- `plan_journey(from_lat, from_lon, to_lat, to_lon)` → Returns journey dict or None
- `get_commute_info(apt_lat, apt_lon, uni_lat, uni_lon)` → Returns complete commute info
- `batch_get_commute_info(df, uni_lat, uni_lon, progress_callback)` → Processes all apartments

---

### Step 4: Scoring (`scoring.py`)

**Input:** DataFrame with all commute data

**Process:**
1. **Normalize Values:**
   - Rent: Lower is better → Normalize to 0-100 (inverse)
   - Commute: Lower is better → Normalize to 0-100 (inverse)
   - Walking: Lower is better → Normalize to 0-100 (inverse)
   - Transfers: Lower is better → Normalize to 0-100 (inverse)

2. **Calculate Component Scores:**
   - Rent Score = (1 - normalized_rent) * 100
   - Commute Score = (1 - normalized_commute) * 100
   - Walking Score = (1 - normalized_walking) * 100
   - Transfers Score = (1 - normalized_transfers) * 100

3. **Weighted Composite Score:**
   ```
   Suitability Score = 
     (rent_weight × Rent Score) +
     (commute_weight × Commute Score) +
     (walking_weight × Walking Score) +
     (transfers_weight × Transfers Score)
   ```

4. **Default Weights:**
   - Rent: 0.35 (35%)
   - Commute: 0.40 (40%)
   - Walking: 0.15 (15%)
   - Transfers: 0.10 (10%)

5. **Handle Missing Data:**
   - If component missing, use neutral score (50)
   - Ensures all apartments get a score

**Output:** DataFrame with `suitability_score` column (0-100)

**Key Functions:**
- `calculate_student_suitability_score(df, rent_weight, commute_weight, walking_weight, transfers_weight)` → Returns DataFrame with scores

---

### Step 5: Visualization (`visualization.py`)

**Input:** DataFrame with coordinates, scores, and commute data

**Process:**
1. **Create Base Map:**
   - Center: Average of apartment coordinates + university
   - Zoom: 11
   - Tiles: OpenStreetMap + CartoDB positron

2. **Add University Marker:**
   - Red bookmark icon
   - Popup with university name

3. **Add Apartment Markers:**
   - For each apartment with valid coordinates:
     - CircleMarker (radius 10)
     - Color by: suitability_score, rent, or commute_time
     - Tooltip: Room name + address preview
     - Popup: Full details (see below)

4. **Color Mapping:**
   - Suitability Score: Red (low) → Green (high)
   - Rent: Blue (low) → Red (high)
   - Commute: Green (short) → Red (long)

5. **Add Legend:**
   - LinearColormap showing value range

**Popup Content:**
- Room/Provider name (header)
- Address with location icon
- Rent (€)
- Nearest stop/platform name + distance
- Walking time to stop
- Transport routes (U-Bahn, S-Bahn, Bus, Tram) with:
  - Line names (e.g., "U-Bahn U5", "S-Bahn S1")
  - Route segments (from → to)
  - Color-coded badges
- Transit time
- Total commute time (highlighted)
- Number of transfers
- Suitability score (color-coded)

**Output:** Folium Map object (HTML)

**Key Functions:**
- `create_base_map(center, zoom_start)` → Returns Folium Map
- `add_university_marker(map, coords, name)` → Adds university marker
- `add_apartments_to_map(map, df, color_by)` → Adds all apartment markers
- `create_interactive_map(df, uni_coords, uni_name, color_by)` → Complete map
- `get_map_html(map)` → Returns HTML string

---

## 👤 User Workflow

### 1. Application Startup
- Streamlit loads `app.py`
- Checks for `Accomodations.csv` in current directory
- Initializes session state variables

### 2. Data Configuration
- **File Selection:**
  - Auto-detects `Accomodations.csv`
  - Option to use existing file or upload new
  - Preview mode checkbox (50 rooms default)

- **University Selection:**
  - Dropdown with predefined Berlin universities
  - Shows: Name, Type (Public/Private), Address, Coordinates
  - Option for custom university address

### 3. Run Analysis
User clicks **"Run Full Analysis"** button:

#### Step 1: Geocoding (33% progress)
- Progress bar shows geocoding status
- Displays: "X/Y addresses | Z successful (A cached, B new)"
- Updates every 10 addresses
- Saves cache after completion

#### Step 2: Transport Analysis (33% progress)
- Progress bar shows BVG API calls
- Displays: "X/Y apartments | Z successful (A cached, B new)"
- Checks cache first, then makes API calls
- Saves responses to cache

#### Step 3: Scoring (33% progress)
- Calculates suitability scores
- Ranks apartments
- Progress bar completes (100%)

### 4. Results Display

#### Summary Metrics
- Total Rooms
- Average Rent
- Average Commute Time
- Average Walking Time
- Average Transfers

#### Detailed Table
- Sorted by suitability score (descending)
- Columns: Rank, Score, Provider, Address, Rent, Commute, Walking, Transfers, Stop Name, Distance, Transport Modes
- Formatted values (€, min, m, etc.)

#### Provider Comparison
- Statistics by provider (if available)
- Average rent, commute, score per provider

#### Interactive Map
- All apartments displayed as markers
- Color by: Suitability Score, Rent, or Commute Time
- Click marker → See full popup
- Hover → See tooltip
- University shown as red bookmark

### 5. Download Results
- CSV download button
- Contains all analysis data
- Includes: coordinates, commute times, scores, transport details

---

## 💾 Caching System

### Geocoding Cache (`geocode_cache.json`)

**Purpose:** Avoid repeated Nominatim API calls for same addresses

**Structure:**
```json
{
  "Address, Berlin, Germany": [52.5200, 13.4050],
  "Another Address, Berlin, Germany": [52.5100, 13.4100]
}
```

**Benefits:**
- Instant lookup for cached addresses
- Reduces API rate limiting issues
- Speeds up subsequent runs

**Management:**
- Auto-saves after each geocode
- Persists between runs
- No expiration (addresses don't change)

---

### BVG API Cache (`bvg_cache/` directory)

**Purpose:** Cache transport stop lookups and journey plans

**File Naming:**
- Stop cache: `{hash}.json` (hash of lat, lon, radius)
- Journey cache: `{hash}.json` (hash of from_lat, from_lon, to_lat, to_lon)

**Structure:**
```json
{
  "stops": [...],
  "journey": {
    "duration_minutes": 25,
    "transfers": 1,
    "modes": ["subway"],
    "route_details": [...]
  }
}
```

**Benefits:**
- Eliminates redundant API calls
- Much faster analysis on subsequent runs
- Reduces API load

**Cache Invalidation:**
- Manual: Delete `bvg_cache/` directory
- Automatic: New coordinates generate new cache keys

---

## 🔌 API Integration

### Nominatim (OpenStreetMap Geocoding)

**Endpoint:** `https://nominatim.openstreetmap.org/search`

**Usage:**
- Geocode addresses to coordinates
- Free, no API key required
- Rate limit: 1 request/second (enforced with delays)

**Request:**
```
GET /search?q={address}&format=json&limit=1
```

**Response:**
```json
{
  "lat": "52.5200",
  "lon": "13.4050",
  "display_name": "Address, Berlin, Germany"
}
```

---

### BVG Transport API

**Base URL:** `https://v6.bvg.transport.rest`

**Connection Method:** HTTP GET requests (REST API)

**No API Key Required** - Public, open API

#### How the Connection Works:

1. **System makes HTTP request** to BVG API server
2. **BVG API responds** with JSON data
3. **System extracts** relevant information (stops, routes, times)
4. **Data is cached** to avoid repeated calls

#### 1. Find Nearest Stop
```
GET /stops/nearby?latitude={lat}&longitude={lon}&radius={radius}
```

**What it does:**
- Takes apartment coordinates (lat, lon)
- Searches for BVG stops within radius (default 1000m)
- Returns list of nearby stops sorted by distance

**Response:**
```json
[
  {
    "id": "900000100001",
    "name": "Alexanderplatz",
    "location": {
      "latitude": 52.5219,
      "longitude": 13.4132
    },
    "distance": 150
  }
]
```

**What we extract:**
- Stop name: "Alexanderplatz"
- Stop coordinates: (52.5219, 13.4132)
- Distance: 150 meters

#### 2. Plan Journey
```
GET /journeys?from.latitude={lat}&from.longitude={lon}&to.latitude={lat}&to.longitude={lon}
```

**What it does:**
- Takes start coordinates (nearest stop) and end coordinates (university)
- Plans best public transport route
- Returns journey details with duration, transfers, and route

**Response:**
```json
{
  "journeys": [
    {
      "duration": 1500,  // seconds (25 minutes)
      "legs": [
        {
          "mode": "walking",
          "origin": {...},
          "destination": {...}
        },
        {
          "mode": "subway",
          "line": {
            "product": "subway",
            "name": "U5"
          },
          "origin": {...},
          "destination": {...}
        }
      ]
    }
  ]
}
```

**What we extract:**
- Duration: 1500 seconds = 25 minutes
- Transfers: Count of mode changes
- Transport modes: ["subway", "suburban", "bus", "tram"]
- Route details: Line names (U5, S1, etc.) and stops

#### Complete Flow Example:

```
Apartment (52.5200, 13.4050)
    ↓
[API Call 1] GET /stops/nearby
    ↓
Nearest Stop: "Alexanderplatz" (150m away)
    ↓
[API Call 2] GET /journeys (from stop to university)
    ↓
Journey: U5 → S1, 25 minutes, 1 transfer
    ↓
Total Commute = Walking (1.8 min) + Transit (25 min) = 26.8 min
```

**Error Handling:**
- Retry on 500 errors (3 attempts with exponential backoff)
- Silent failure (returns None)
- Graceful degradation (shows partial data)
- Caching reduces API load and speeds up subsequent runs

**See `BVG_INTEGRATION.md` for detailed connection flow and examples.**

---

## 📈 Scoring Algorithm

### Normalization

All values normalized to 0-1 range:

```python
normalized = (value - min_value) / (max_value - min_value)
```

### Component Scores

Each component scored 0-100:

- **Rent Score:** `(1 - normalized_rent) × 100`
  - Lower rent = Higher score

- **Commute Score:** `(1 - normalized_commute) × 100`
  - Shorter commute = Higher score

- **Walking Score:** `(1 - normalized_walking) × 100`
  - Shorter walk = Higher score

- **Transfers Score:** `(1 - normalized_transfers) × 100`
  - Fewer transfers = Higher score

### Composite Score

```
Suitability Score = 
  (0.35 × Rent Score) +
  (0.40 × Commute Score) +
  (0.15 × Walking Score) +
  (0.10 × Transfers Score)
```

**Result:** 0-100 scale (higher = better)

### Missing Data Handling

- If component missing → Use neutral score (50)
- Ensures all apartments get ranked
- Prevents exclusion due to incomplete data

---

## 🗺️ Visualization

### Map Features

1. **Base Map:**
   - OpenStreetMap tiles
   - CartoDB positron (alternative)
   - Layer control for switching

2. **Markers:**
   - **University:** Red bookmark icon
   - **Apartments:** Colored circles
     - Size: 10px radius
     - Color: Based on selected metric
     - Border: Dark gray, 2px

3. **Interactivity:**
   - **Tooltip:** Room name + address preview (on hover)
   - **Popup:** Full details (on click)
   - **Zoom/Pan:** Standard map controls

4. **Color Schemes:**
   - **Suitability Score:** Red → Orange → Yellow → Green
   - **Rent:** Blue → Cyan → Yellow → Red
   - **Commute:** Green → Yellow → Orange → Red

### Popup Details

Styled HTML popup includes:
- Header with room/provider name
- Address with location icon
- Rent (€)
- Nearest stop/platform with distance
- Walking time
- Transport routes (color-coded badges)
- Transit time
- Total commute (highlighted)
- Transfers count
- Suitability score (color-coded)

---

## ⚙️ Configuration

### Default Settings

**Preview Mode:**
- Enabled by default
- Limit: 50 rooms
- Can be disabled for full dataset

**Scoring Weights:**
- Rent: 0.35 (35%)
- Commute: 0.40 (40%)
- Walking: 0.15 (15%)
- Transfers: 0.10 (10%)

**Filters:**
- Max Rent: Auto-set to 1.5× max rent in data
- Max Commute: 180 minutes
- Max Walking: 2000 meters
- (All set to max by default to show all data)

**University Selection:**
- Predefined list in `universities.py`
- Includes: Name, Type, Address, Coordinates
- Custom address option available

---

## 📁 File Structure

```
project/
├── app.py                    # Main application
├── data_loader.py            # Data loading & preprocessing
├── geocoding.py              # Address geocoding
├── transport.py              # BVG API integration
├── transport_cache.py        # BVG caching system
├── walking.py                # Walking distance (OSMnx)
├── scoring.py                # Scoring algorithm
├── visualization.py          # Map visualization
├── universities.py           # University data
├── requirements.txt          # Dependencies
├── README.md                 # Project overview
├── DOCUMENTATION.md          # This file
├── .gitignore               # Git ignore rules
├── geocode_cache.json       # Geocoding cache (auto-generated)
└── bvg_cache/               # BVG API cache (auto-generated)
    └── *.json               # Cached API responses
```

---

## 🚀 Running the Application

### Prerequisites

```bash
pip install -r requirements.txt
```

### Start Application

```bash
streamlit run app.py
```

### First Run

1. Place `Accomodations.csv` in project directory
2. Open browser to `http://localhost:8501`
3. Select university
4. Click "Run Full Analysis"
5. Wait for geocoding and transport analysis
6. View results and map

### Subsequent Runs

- Much faster due to caching
- Geocoding: Instant (from cache)
- Transport: Only new routes need API calls

---

## 🔧 Troubleshooting

### No Apartments Showing on Map

**Check:**
1. Are coordinates valid? (not 0,0)
2. Are coordinates in Berlin area? (52.3-52.7 lat, 13.0-13.8 lon)
3. Did geocoding complete successfully?
4. Check debug info in map section

### NA Values in Commute Data

**Possible Causes:**
1. No nearby BVG stop found
2. No journey found from stop to university
3. API rate limiting (check cache)

**Solution:**
- Check if addresses are in Berlin
- Verify university coordinates
- Check BVG API status

### Slow Performance

**Optimizations:**
1. Use preview mode (50 rooms)
2. Enable caching (automatic)
3. Check cache files exist
4. Reduce API delay (if rate limits allow)

---

## 📝 Notes

- **Data Privacy:** All data processed locally, no external storage
- **API Limits:** Nominatim: 1 req/sec, BVG: No official limit (be respectful)
- **Cache Management:** Delete cache files to force refresh
- **Error Handling:** Graceful degradation (shows partial data)

---

## 🎓 Urban Technology Relevance

This project demonstrates:
- **Spatial Analysis:** Geocoding and coordinate-based calculations
- **Network Analysis:** Public transport network integration
- **Multi-Criteria Decision Analysis (MCDA):** Composite scoring
- **Geospatial Visualization:** Interactive maps for decision support
- **Data Integration:** Combining multiple data sources (Excel, APIs)
- **Caching Strategies:** Performance optimization for urban analytics
- **Accessibility Metrics:** Measuring transport equity and convenience

---

**Last Updated:** 2024
**Version:** 1.0

