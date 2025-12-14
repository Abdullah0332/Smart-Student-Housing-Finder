# How the System Connects to BVG API

## 🔗 BVG Integration Overview

The system connects to **BVG (Berliner Verkehrsbetriebe)** - Berlin's public transport authority - through their REST API to get real-time transport data.

---

## 🌐 BVG API Connection

### Base URL
```
https://v6.bvg.transport.rest
```

**No API key required** - It's a public, open API for Berlin transport data.

---

## 📡 Two Main API Calls

### 1. Find Nearest Stop (`/stops/nearby`)

**Purpose:** Find the closest BVG public transport stop to an apartment

**How it works:**

```
Apartment Coordinates (lat, lon)
    ↓
HTTP GET Request
    ↓
https://v6.bvg.transport.rest/stops/nearby?latitude=52.5200&longitude=13.4050&radius=1000
    ↓
BVG API Server
    ↓
Response: List of nearby stops
    ↓
Extract: Nearest stop name, coordinates, distance
```

**Example Request:**
```python
url = "https://v6.bvg.transport.rest/stops/nearby"
params = {
    'latitude': 52.5200,      # Apartment latitude
    'longitude': 13.4050,     # Apartment longitude
    'radius': 1000,           # Search within 1000 meters
    'results': 5              # Get top 5 nearest stops
}

response = requests.get(url, params=params)
stops = response.json()
```

**Example Response:**
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
  },
  {
    "id": "900000100002",
    "name": "Hackescher Markt",
    "location": {
      "latitude": 52.5225,
      "longitude": 13.4025
    },
    "distance": 320
  }
]
```

**What we extract:**
- Stop name: "Alexanderplatz"
- Stop coordinates: (52.5219, 13.4132)
- Distance from apartment: 150 meters

---

### 2. Plan Journey (`/journeys`)

**Purpose:** Get the best public transport route from stop to university

**How it works:**

```
Nearest Stop Coordinates (from)
    +
University Coordinates (to)
    ↓
HTTP GET Request
    ↓
https://v6.bvg.transport.rest/journeys?from.latitude=52.5219&from.longitude=13.4132&to.latitude=52.4500&to.longitude=13.2800
    ↓
BVG API Server
    ↓
Response: Journey plan with route, duration, transfers
    ↓
Extract: Duration, transfers, transport modes, line names
```

**Example Request:**
```python
url = "https://v6.bvg.transport.rest/journeys"
params = {
    'from.latitude': 52.5219,    # Nearest stop to apartment
    'from.longitude': 13.4132,
    'to.latitude': 52.4500,      # University coordinates
    'to.longitude': 13.2800,
    'results': 1                 # Get best route only
}

response = requests.get(url, params=params)
journey_data = response.json()
```

**Example Response:**
```json
{
  "journeys": [
    {
      "duration": 1500,  // Total journey time in seconds (25 minutes)
      "legs": [
        {
          "mode": "walking",
          "origin": {
            "name": "Alexanderplatz"
          },
          "destination": {
            "name": "Alexanderplatz"
          }
        },
        {
          "mode": "subway",
          "line": {
            "product": "subway",
            "name": "U5"
          },
          "origin": {
            "name": "Alexanderplatz"
          },
          "destination": {
            "name": "Hauptbahnhof"
          }
        },
        {
          "mode": "suburban",
          "line": {
            "product": "suburban",
            "name": "S1"
          },
          "origin": {
            "name": "Hauptbahnhof"
          },
          "destination": {
            "name": "Universität"
          }
        }
      ]
    }
  ]
}
```

**What we extract:**
- **Duration:** 1500 seconds = 25 minutes
- **Transfers:** 1 (changed from U5 to S1 at Hauptbahnhof)
- **Transport Modes:** ["subway", "suburban"]
- **Route Details:**
  - U-Bahn U5: Alexanderplatz → Hauptbahnhof
  - S-Bahn S1: Hauptbahnhof → Universität

---

## 🔄 Complete Flow: Apartment → University

Here's how the system uses BVG API for each apartment:

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Apartment has coordinates (from geocoding)          │
│         52.5200, 13.4050                                   │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Call BVG API - Find Nearest Stop                   │
│                                                              │
│ GET /stops/nearby?latitude=52.5200&longitude=13.4050        │
│                                                              │
│ Response: "Alexanderplatz" (150m away)                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Calculate Walking Time                            │
│                                                              │
│ Distance: 150 meters                                        │
│ Walking Speed: 5 km/h = 1.39 m/s                          │
│ Walking Time: 150 / 1.39 = 108 seconds = 1.8 minutes      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Call BVG API - Plan Journey                        │
│                                                              │
│ GET /journeys?from=Alexanderplatz&to=University            │
│                                                              │
│ Response:                                                    │
│ - Duration: 25 minutes                                      │
│ - Route: U5 → S1                                            │
│ - Transfers: 1                                              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 5: Calculate Total Commute                            │
│                                                              │
│ Total = Walking (1.8 min) + Transit (25 min) = 26.8 min    │
└─────────────────────────────────────────────────────────────┘
```

---

## 💾 Caching System

To avoid making the same API calls repeatedly, responses are cached:

### Stop Cache
**Location:** `bvg_cache/{hash}.json`

**Cache Key:** Based on apartment coordinates
```python
# Example: Apartment at 52.5200, 13.4050
cache_key = md5("52.520000_13.405000_1000")  # Includes radius
# Result: "abc123def456.json"
```

**Cache Content:**
```json
{
  "stops": [
    {
      "name": "Alexanderplatz",
      "location": {...},
      "distance": 150
    }
  ]
}
```

### Journey Cache
**Location:** `bvg_cache/{hash}.json`

**Cache Key:** Based on stop coordinates + university coordinates
```python
# Example: From stop (52.5219, 13.4132) to university (52.4500, 13.2800)
cache_key = md5("52.521900_13.413200_52.450000_13.280000")
# Result: "xyz789ghi012.json"
```

**Cache Content:**
```json
{
  "journey": {
    "duration_minutes": 25,
    "transfers": 1,
    "modes": ["subway", "suburban"],
    "route_details": [...]
  }
}
```

**Benefits:**
- ✅ Same apartment analyzed again? → Use cached stop
- ✅ Same route calculated again? → Use cached journey
- ✅ Much faster on subsequent runs
- ✅ Reduces API load

---

## 🔧 Code Implementation

### In `transport.py`:

```python
# 1. Define BVG API base URL
BVG_API_BASE = "https://v6.bvg.transport.rest"

# 2. Find nearest stop function
def find_nearest_stop(latitude, longitude):
    # Check cache first
    cached = load_stop_cache(latitude, longitude)
    if cached:
        return cached  # Use cached result
    
    # Make API call
    url = f"{BVG_API_BASE}/stops/nearby"
    response = requests.get(url, params={
        'latitude': latitude,
        'longitude': longitude,
        'radius': 1000
    })
    
    stops = response.json()
    
    # Save to cache
    save_stop_cache(latitude, longitude, stops)
    
    return stops[0]  # Return nearest stop

# 3. Plan journey function
def plan_journey(from_lat, from_lon, to_lat, to_lon):
    # Check cache first
    cached = load_journey_cache(from_lat, from_lon, to_lat, to_lon)
    if cached:
        return cached  # Use cached result
    
    # Make API call
    url = f"{BVG_API_BASE}/journeys"
    response = requests.get(url, params={
        'from.latitude': from_lat,
        'from.longitude': from_lon,
        'to.latitude': to_lat,
        'to.longitude': to_lon
    })
    
    journey = response.json()
    
    # Save to cache
    save_journey_cache(from_lat, from_lon, to_lat, to_lon, journey)
    
    return journey
```

---

## 📊 What Data We Get from BVG

### From Stop Lookup:
- ✅ Stop name (e.g., "Alexanderplatz", "Hackescher Markt")
- ✅ Stop coordinates
- ✅ Distance from apartment (meters)
- ✅ Stop ID

### From Journey Planning:
- ✅ Total journey duration (seconds → converted to minutes)
- ✅ Number of transfers
- ✅ Transport modes used (U-Bahn, S-Bahn, Bus, Tram)
- ✅ Line names (U5, S1, M5, etc.)
- ✅ Route segments (from → to for each leg)
- ✅ Departure and arrival times

---

## 🎯 Why BVG Integration Matters

1. **Real Transport Data:** Uses actual BVG schedules and routes
2. **Accurate Commute Times:** Not estimates, but real journey planning
3. **Transport Modes:** Identifies U-Bahn, S-Bahn, Bus, Tram usage
4. **Transfer Information:** Counts how many transfers needed
5. **Route Details:** Shows which lines to take

This makes the housing analysis **realistic and practical** for students who need to commute daily!

---

## 🔍 Testing the Connection

You can test the BVG API directly in your browser:

**Find nearest stop:**
```
https://v6.bvg.transport.rest/stops/nearby?latitude=52.5200&longitude=13.4050&radius=1000
```

**Plan a journey:**
```
https://v6.bvg.transport.rest/journeys?from.latitude=52.5200&from.longitude=13.4050&to.latitude=52.4500&to.longitude=13.2800
```

---

## ⚠️ Important Notes

1. **No API Key Required:** BVG API is public and free
2. **Rate Limiting:** Be respectful - we add delays between requests
3. **Error Handling:** System retries on failures (up to 3 times)
4. **Caching:** Responses saved to avoid repeated calls
5. **Internet Required:** Needs active internet connection

---

**Summary:** The system connects to BVG API via HTTP GET requests to get real Berlin public transport data, which is then used to calculate accurate commute times and transport accessibility for each apartment.

