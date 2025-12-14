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

- **BVG Transport API** for realistic journey planning
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

1. **Upload Data**: Upload your accommodation Excel/CSV file in the sidebar
2. **Select University**: Enter your university name or address
3. **Configure Parameters**: Adjust filters and scoring weights
4. **Run Analysis**: Click "Run Full Analysis" (this may take several minutes)
5. **View Results**: Explore rankings, provider comparisons, and interactive map

---

## 📁 Project Structure

```
project/
├── app.py                 # Streamlit UI (main application)
├── data_loader.py         # Excel/CSV data loading and filtering
├── geocoding.py           # Address → coordinates (Nominatim)
├── transport.py           # BVG API integration
├── walking.py             # OSMnx walking routes
├── scoring.py             # Ranking and scoring logic
├── visualization.py       # Folium map visualization
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

---

## 🔧 Key Features

### Data Processing
- Loads accommodation data from Excel/CSV
- Filters for Berlin-only accommodations
- Handles missing data gracefully

### Geocoding
- Converts addresses to coordinates using Nominatim
- Respects rate limits (1 request/second)
- Provides progress indicators

### Transport Analysis
- Finds nearest BVG public transport stops
- Calculates door-to-door commute times
- Identifies transport modes (U-Bahn, S-Bahn, Tram, Bus)
- Counts transfers

### Scoring System
- **Affordability Score**: Lower rent = higher score
- **Commute Score**: Shorter commute = higher score
- **Walking Score**: Shorter walk = higher score
- **Transfers Score**: Fewer transfers = higher score
- **Composite Score**: Weighted combination (0-100 scale)

### Visualization
- Interactive map with apartment locations
- Color-coded by score, rent, or commute time
- University location marker
- Multiple base map layers

---

## 📊 Input Data Format

Your accommodation data should include columns such as:
- `City` or `city` - Must contain "Berlin" for filtering
- `Address` or `address` - Street address
- `Provider` or `provider` - Accommodation provider name
- `Rent (in €/All-In)` or `rent` - Monthly rent price

The system will automatically detect and map common column names.

---

## 🔌 API Usage

### BVG Transport API
- **Base URL**: `https://v6.bvg.transport.rest`
- **No API key required**
- Rate limiting: ~0.5 seconds between requests recommended
- Endpoints used:
  - `/stops/nearby` - Find nearest stops
  - `/journeys` - Plan routes

### Nominatim (Geocoding)
- **Service**: OpenStreetMap Nominatim
- **No API key required**
- Rate limiting: 1 request/second
- User agent required

---

## ⚙️ Configuration

### Scoring Weights

Adjust weights in the sidebar:
- **Affordability Weight** (default: 0.35)
- **Commute Time Weight** (default: 0.40)
- **Walking Distance Weight** (default: 0.15)
- **Transfers Weight** (default: 0.10)

Weights are automatically normalized to sum to 1.0.

### Filters

- **Max Rent**: Filter apartments by maximum rent (€)
- **Max Commute Time**: Filter by maximum commute (minutes)
- **Max Walking Distance**: Filter by maximum walking distance (meters)

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
- Geocoding may take several minutes for large datasets (1 second per address)
- Transport API calls may take 10-30 minutes for 100+ apartments
- Consider testing with a subset first

### Limitations
- Requires internet connection for API calls
- Rate limits may slow down processing
- Some addresses may fail to geocode

### Future Enhancements
- Cache geocoding results
- Batch API requests more efficiently
- Add more transport modes (bike, car)
- Include neighborhood amenities
- Historical price trends

---

## 📚 Dependencies

See `requirements.txt` for complete list. Key libraries:

- **pandas**: Data manipulation
- **streamlit**: Web interface
- **requests**: API calls
- **geopy**: Geocoding
- **osmnx**: Network analysis
- **folium**: Map visualization
- **scikit-learn**: Data normalization

---

## 🤝 Contributing

This is a course project. For improvements:
1. Test with sample data
2. Ensure API rate limits are respected
3. Add clear documentation
4. Handle errors gracefully

---

## 📄 License

Educational project for Urban Technology course.

---

## 🙏 Acknowledgments

- **BVG** for public transport API
- **OpenStreetMap** contributors for geospatial data
- **Nominatim** for geocoding service

---

## ❓ Troubleshooting

### "No accommodations found"
- Check that your data has a "City" column containing "Berlin"
- Verify the file format is CSV or Excel

### "Geocoding failed"
- Check internet connection
- Verify addresses are valid Berlin addresses
- Wait between large batches (rate limiting)

### "API error"
- BVG API may be temporarily unavailable
- Check internet connection
- Reduce batch size or increase delays

### Map not displaying
- Ensure folium is installed
- Check browser console for errors
- Try a different browser

---

**Happy apartment hunting! 🏠🚇**

