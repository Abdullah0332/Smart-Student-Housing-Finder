"""
Smart Student Housing Finder - Streamlit App
============================================

Main application interface for ranking student apartments in Berlin by:
- Cost (affordability)
- Commute time to university (GTFS public transport data)
- Walking distance to transit stops
- Transport accessibility

Urban Technology Project:
This application demonstrates how urban mobility data, public transport APIs,
and geospatial analysis can inform housing decisions. It shows how transport
infrastructure accessibility affects residential desirability and student
housing choices in Berlin.

Author: Urban Technology Course Project
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import time
from pathlib import Path
import sys

# Import custom modules
from data_loader import load_accommodation_data, validate_data
from geocoding import geocode_dataframe, geocode_university
from transport import batch_get_commute_info
from scoring import calculate_student_suitability_score, rank_apartments, compare_providers
from visualization import create_interactive_map, save_map, get_map_html
from universities import get_university_list, get_university_info, get_university_coords, get_universities_by_type
from logger_config import setup_logger

logger = setup_logger("app")

# Page configuration
st.set_page_config(
    page_title="Smart Student Housing Finder - Berlin",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - Light Mode Theme
st.markdown("""
    <style>
    /* Force light mode background */
    .stApp {
        background-color: #ffffff !important;
    }
    
    /* Main content area */
    .main .block-container {
        background-color: #ffffff !important;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Headers */
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
        background-color: #ffffff !important;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        padding-bottom: 2rem;
        background-color: #ffffff !important;
    }
    
    /* Metrics and info boxes */
    .stMetric {
        background-color: #f8f9fa !important;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e0e0e0;
    }
    
    /* Info, success, warning boxes */
    .stInfo, .stSuccess, .stWarning {
        background-color: #f8f9fa !important;
        border: 1px solid #e0e0e0 !important;
    }
    
    /* Text colors for light mode */
    .stMarkdown, p, div, span, h1, h2, h3, h4, h5, h6 {
        color: #262730 !important;
    }
    
    /* Input fields */
    .stSelectbox, .stMultiselect, .stNumberInput, .stTextInput {
        background-color: #ffffff !important;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #1f77b4 !important;
        color: #ffffff !important;
        border: none !important;
    }
    .stButton > button:hover {
        background-color: #1565a0 !important;
    }
    
    /* Room cards */
    .room-card-clickable {
        background-color: #ffffff !important;
        border: 1px solid #e0e0e0 !important;
    }
    .room-card-clickable:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.15) !important;
        transform: translateY(-2px) !important;
        background-color: #f8f9fa !important;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background-color: #f8f9fa !important;
    }
    
    /* Tables */
    .stDataFrame {
        background-color: #ffffff !important;
    }
    
    /* Ensure all backgrounds are light */
    body {
        background-color: #ffffff !important;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'apartments_df' not in st.session_state:
    st.session_state.apartments_df = None
if 'university_coords' not in st.session_state:
    st.session_state.university_coords = None
if 'university_name' not in st.session_state:
    st.session_state.university_name = None
if 'processed_df' not in st.session_state:
    st.session_state.processed_df = None
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1
if 'selected_providers' not in st.session_state:
    st.session_state.selected_providers = []


def main():
    """Main application function"""
    
    # Configuration Section - Two columns: University (left) and Accommodation Data (right)
    config_col1, config_col2 = st.columns([1, 1])
    
    with config_col1:
        # University Selection
        st.subheader("🎓 Select University")
        
        # Get university list
        university_list = get_university_list()
        
        # Find default index (TU Berlin)
        default_uni = "Technische Universität Berlin (TU Berlin)"
        try:
            default_idx = university_list.index(default_uni)
        except ValueError:
            default_idx = 0
        
        # Create formatted options with type labels and mapping
        formatted_options = []
        uni_mapping = {}  # Map formatted string to original university name
        
        for uni in university_list:
            uni_info = get_university_info(uni)
            type_label = "🏛️" if uni_info['type'] == 'Public' else "🏢"
            formatted = f"{type_label} {uni} ({uni_info['type']})"
            formatted_options.append(formatted)
            uni_mapping[formatted] = uni
        
        selected_formatted = st.selectbox(
            "Select your university",
            options=formatted_options,
            index=default_idx,
            help="Choose from major Berlin universities (public and private)",
            key="university_select"
        )
        
        # Get university name from mapping
        if selected_formatted:
            selected_university = uni_mapping[selected_formatted]
            uni_info = get_university_info(selected_university)
            
            if uni_info:
                # Set university coordinates (pre-stored, no geocoding needed)
                st.session_state.university_coords = (uni_info['latitude'], uni_info['longitude'])
                st.session_state.university_name = uni_info['name']
    
    with config_col2:
        # Accommodation Data Card
        st.subheader("📁 Accommodation Data")
        
        default_file = "Accomodations.csv"
        file_exists = Path(default_file).exists()
        
        if file_exists:
            # Load data to get total count
            try:
                import pandas as pd
                df_temp = pd.read_csv(default_file, sep=';', encoding='latin-1')
                if 'City' in df_temp.columns:
                    berlin_df = df_temp[df_temp['City'].str.contains('Berlin', case=False, na=False)]
                    total_records = len(berlin_df)
                else:
                    total_records = len(df_temp)
            except:
                total_records = 0
            
            # Display total records in a card
            st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 3px 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center;">
                    <h3 style="margin: 0; color: #262730;">Total Records: {total_records:,}</h3>
                </div>
            """, unsafe_allow_html=True)
            
            use_default = True
        else:
            st.warning("No default file found.")
            use_default = False
            total_records = 0
    
    # Provider configuration and data loading (runs in background, hidden from main UI)
    if file_exists:
        # Provider selection from code configuration
        import pandas as pd
        all_providers_dynamic = []
        
        try:
            if Path(default_file).exists():
                df_temp = pd.read_csv(default_file, sep=';', encoding='latin-1')
                if 'City' in df_temp.columns:
                    berlin_df = df_temp[df_temp['City'].str.contains('Berlin', case=False, na=False)]
                    if 'Provider' in berlin_df.columns:
                        all_providers_dynamic = sorted(berlin_df['Provider'].dropna().unique().tolist())
        except Exception as e:
            # Fallback to common providers if auto-detection fails
            all_providers_dynamic = ['66 Monkeys', 'Havens Living', 'House of CO', 'Neonwood', 
                                    'The Urban Club', 'Wunderflats', 'Zimmerei', 'Mietcampus', 
                                    'My i Live Home', 'The Fizz', 'Ernstl München']
        
        # EDIT THIS LIST TO ENABLE/DISABLE PROVIDERS:
        PROVIDERS_TO_ENABLE = ['66 Monkeys', 'Havens Living', 'House of CO', 'Neonwood', 
                                'The Urban Club', 'Wunderflats', 'Zimmerei', 'Mietcampus', 
                                'My i Live Home', 'The Fizz', 'Ernstl München']
        
        ENABLED_PROVIDERS = {}
        for provider in all_providers_dynamic:
            ENABLED_PROVIDERS[provider] = (provider in PROVIDERS_TO_ENABLE)
        
        # Get selected providers from configuration
        selected_providers = [provider for provider, enabled in ENABLED_PROVIDERS.items() if enabled]
        
        if selected_providers:
            provider_filter = ', '.join(selected_providers)
        else:
            provider_filter = None
        
        # Store provider filter in session state
        st.session_state.provider_filter = provider_filter
        
        # Check if provider filter changed - if so, clear data and reload
        current_filter = provider_filter if provider_filter else ""
        last_filter = st.session_state.get('last_provider_filter', "")
        
        if current_filter != last_filter:
            # Provider configuration changed - clear data and reload
            st.session_state.apartments_df = None
            st.session_state.processed_df = None
            st.session_state.analysis_complete = False
            st.session_state.last_provider_filter = current_filter
        
        preview_mode = False  # No preview mode in simplified UI
    else:
        use_default = False
        preview_mode = False
        provider_filter = None
    
    if not use_default:
        uploaded_file = st.file_uploader(
            "Upload Excel or CSV file",
            type=['csv', 'xlsx', 'xls'],
            help="Upload your accommodation data file"
        )
    else:
        uploaded_file = None
    
    # Load data
    if use_default and file_exists:
        try:
            # Auto-load on first run or if data not loaded
            # Check if we need to reload (data is None or provider filter changed)
            should_reload = st.session_state.apartments_df is None
            
            if should_reload:
                with st.spinner("Loading accommodation data..."):
                    limit = 50 if preview_mode else None
                    # Use provider filter from session state
                    provider = st.session_state.get('provider_filter', None)
                    if provider and provider.strip():
                        provider = provider.strip()
                    else:
                        provider = None
                    st.session_state.apartments_df = load_accommodation_data(default_file, limit=limit, provider_filter=provider)
                    validate_data(st.session_state.apartments_df)
                    mode_text = " (preview: 50 rooms)" if preview_mode else ""
                    provider_text = f" from {provider}" if provider else ""
                st.success(f"✓ Loaded {len(st.session_state.apartments_df)} accommodations{provider_text}{mode_text}")
            else:
                mode_text = " (preview mode)" if preview_mode and len(st.session_state.apartments_df) <= 50 else ""
                st.success(f"✓ {len(st.session_state.apartments_df)} accommodations loaded{mode_text}")
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")
            st.session_state.apartments_df = None
    
    elif uploaded_file is not None:
        try:
            # Save uploaded file temporarily
            file_path = f"temp_{uploaded_file.name}"
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Load data
            st.session_state.apartments_df = load_accommodation_data(file_path, provider_filter=None)
            validate_data(st.session_state.apartments_df)
            
            st.success(f"✓ Loaded {len(st.session_state.apartments_df)} accommodations")
        
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")
            st.session_state.apartments_df = None
    
    # University selection is now in config_col1 above
    
    # Run analysis button - prominent on main screen
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run_analysis = st.button(
            "🚀 Run Full Analysis",
            type="primary",
            use_container_width=True,
            help="Start the complete analysis (geocoding + transport API + distance calculation)"
        )
    
    # Main content area
    if st.session_state.apartments_df is None:
        st.info("👈 Please load accommodation data above to begin")
        return
    
    if st.session_state.university_coords is None:
        st.warning("⚠️ Please select a university above")
        return
    
    # Run analysis (filters set to max - show all data)
    if run_analysis:
        df = st.session_state.apartments_df.copy()
        
        # NO FILTERS - show all apartments
        # Filters are set to max by default (implicitly)
        
        if len(df) == 0:
            st.error("No apartments found. Please check your data or reload.")
            return
        
        # Unified Progress Display for Steps 1 & 2
        st.header("Processing Data")
        progress_bar = st.progress(0)
        status_text = st.empty()
        progress_details = st.empty()
        
        # Step 1: Geocode apartments
        status_text.text("📍 Step 1/2: Geocoding Apartments")
        progress_details.text("Initializing...")
        
        # Check how many need geocoding - ALWAYS geocode if columns don't exist or any are missing
        needs_geocoding = True
        if 'latitude' in df.columns and 'longitude' in df.columns:
            # Check if ALL addresses have coordinates
            has_coords = df['latitude'].notna() & df['longitude'].notna()
            needs_geocoding = not has_coords.all()  # Need geocoding if ANY are missing
        
        if needs_geocoding:
            # Progress callback for Streamlit
            def update_geocoding_progress(current, total, cached, new):
                progress = (current / total) * 0.5 if total > 0 else 0
                progress_bar.progress(progress)
                successful = cached + new
                progress_details.text(f"📍 Step 1/2: Geocoding | Progress: {current}/{total} addresses | {successful} successful ({cached} cached, {new} new)")
            
            # Ensure latitude/longitude columns exist before geocoding
            if 'latitude' not in df.columns:
                df['latitude'] = None
            if 'longitude' not in df.columns:
                df['longitude'] = None
            
            df = geocode_dataframe(df, progress_callback=update_geocoding_progress)
            
            # Show summary of geocoded rooms
            geocoded_count = df['latitude'].notna().sum() if 'latitude' in df.columns else 0
            total_count = len(df)
            progress_bar.progress(0.5)
            progress_details.text(f"✓ Step 1/2 Complete: {geocoded_count}/{total_count} rooms geocoded")
        else:
            progress_bar.progress(0.5)
            geocoded_count = df['latitude'].notna().sum() if 'latitude' in df.columns else 0
            progress_details.text(f"✓ Step 1/2 Complete: Using existing coordinates ({geocoded_count} rooms)")
        
        # Step 2: Calculate commute times and distances
        status_text.text("🚇 Step 2/2: Calculating Commute Times & Distances")
        progress_details.text("Using local GTFS data for fast, offline route planning...")
        
        total_apartments = len(df)
        successful_count = 0
        
        def update_commute_progress(idx, total, cached, new):
            nonlocal successful_count
            successful_count = cached + new
            progress = 0.5 + (idx / total) * 0.5 if total > 0 else 0.5
            progress_bar.progress(progress)
            progress_details.text(f"🚇 Step 2/2: Calculating Commute | Progress: {idx}/{total} apartments | {successful_count} successful")
        
        # Process using GTFS data (fast, local processing)
        batch_get_commute_info(
            df,
            st.session_state.university_coords[0],
            st.session_state.university_coords[1],
            delay=0.0,  # No delay for local GTFS data
            progress_callback=update_commute_progress
        )
        
        progress_bar.progress(1.0)
        progress_details.text(f"✓ Step 2/2 Complete: Processed {total_apartments} apartments using GTFS data")
        
        # Step 3: Calculate scores (with default weights)
        status_text.text("⭐ Calculating Scores...")
        progress_details.text("Computing composite suitability scores...")
        
        # Check coordinates before scoring
        coords_before_scoring = df['latitude'].notna().sum() if 'latitude' in df.columns else 0
        
        df = calculate_student_suitability_score(
            df,
            rent_weight=0.35,
            commute_weight=0.40,
            walking_weight=0.15,
            transfers_weight=0.10
        )
        
        # Check coordinates after scoring
        coords_after_scoring = df['latitude'].notna().sum() if 'latitude' in df.columns else 0
        
        progress_bar.progress(1.0)
        
        # Store processed dataframe (ALL apartments, no filtering)
        # Ensure coordinates are preserved - use .copy() to ensure we have a fresh copy
        if 'latitude' not in df.columns or 'longitude' not in df.columns:
            st.error(f"⚠️ ERROR: Coordinates missing after processing! Columns: {list(df.columns)}")
        else:
            coords_in_final = df['latitude'].notna().sum()
        
        st.session_state.processed_df = df.copy()  # Use .copy() to ensure we have a fresh copy
        st.session_state.analysis_complete = True
        
        # Show provider breakdown after processing
        if 'provider' in df.columns:
            provider_counts = df['provider'].value_counts()
            status_text.success(f"✓ Analysis complete! Processed {len(df)} rooms from {len(provider_counts)} providers: {', '.join(provider_counts.index.tolist())}")
        else:
            status_text.success("✓ Analysis complete!")
        st.balloons()
        
        # Force rerun to show results immediately
        st.rerun()
    
    # Display results - Simplified UI: Room List + Map
    if st.session_state.analysis_complete and st.session_state.processed_df is not None:
        df = st.session_state.processed_df.copy()
        
        # Show all apartments (no filtering) - INCLUDING those without coordinates
        if len(df) == 0:
            st.warning("No apartments found. Please check your data or reload.")
            return
        
        # Get provider breakdown for filter (but don't display it)
        if 'provider' in df.columns:
            provider_breakdown = df['provider'].value_counts()
            all_providers = sorted(provider_breakdown.index.tolist())
        
        # Provider Filter - Multi-select
        if 'provider' in df.columns:
            st.markdown("---")
            st.subheader("🔍 Filter by Platform/Provider")
            
            # Initialize selected providers in session state (default: all providers)
            if 'selected_providers' not in st.session_state or len(st.session_state.selected_providers) == 0:
                st.session_state.selected_providers = all_providers  # Default: all providers selected
            
            # Ensure selected providers are still valid (in case data changed)
            valid_selected = [p for p in st.session_state.selected_providers if p in all_providers]
            if len(valid_selected) != len(st.session_state.selected_providers):
                st.session_state.selected_providers = valid_selected if len(valid_selected) > 0 else all_providers
            
            # Multi-select widget for providers
            selected_providers = st.multiselect(
                "Select platform(s) to display:",
                options=all_providers,
                default=st.session_state.selected_providers,
                key="provider_filter_multiselect",
                help="Select one or more platforms to filter the room list and map. Leave empty to show all."
            )
            
            # Update session state and reset page if filter changed
            if set(selected_providers) != set(st.session_state.selected_providers):
                st.session_state.selected_providers = selected_providers
                st.session_state.current_page = 1  # Reset to page 1 when filter changes
            
            # Apply provider filter
            if len(selected_providers) > 0:
                df = df[df['provider'].isin(selected_providers)].copy()
                st.success(f"✓ Filtered to {len(df)} rooms from {len(selected_providers)} platform(s): {', '.join(selected_providers)}")
            else:
                st.info("ℹ️ No providers selected. Showing all rooms.")
                # If no providers selected, show all (df remains unchanged)
        
        st.markdown("---")
        
        # Sort options (before column layout so both columns can access df_sorted)
        sort_option = st.selectbox(
            "Sort by:",
            ['Rent (Low to High)', 'Rent (High to Low)', 'Distance (Near to Far)', 'Distance (Far to Near)', 
             'Commute Time (Short to Long)', 'Commute Time (Long to Short)'],
            key="sort_option"
        )
        
        # Apply sorting
        if sort_option == 'Rent (Low to High)':
            df_sorted = df.sort_values('rent', ascending=True, na_position='last').copy()
        elif sort_option == 'Rent (High to Low)':
            df_sorted = df.sort_values('rent', ascending=False, na_position='last').copy()
        elif sort_option == 'Distance (Near to Far)':
            if 'nearest_stop_distance_m' in df.columns:
                df_sorted = df.sort_values('nearest_stop_distance_m', ascending=True, na_position='last').copy()
            else:
                df_sorted = df.copy()
        elif sort_option == 'Distance (Far to Near)':
            if 'nearest_stop_distance_m' in df.columns:
                df_sorted = df.sort_values('nearest_stop_distance_m', ascending=False, na_position='last').copy()
            else:
                df_sorted = df.copy()
        elif sort_option == 'Commute Time (Short to Long)':
            if 'total_commute_minutes' in df.columns:
                df_sorted = df.sort_values('total_commute_minutes', ascending=True, na_position='last').copy()
            else:
                df_sorted = df.copy()
        elif sort_option == 'Commute Time (Long to Short)':
            if 'total_commute_minutes' in df.columns:
                df_sorted = df.sort_values('total_commute_minutes', ascending=False, na_position='last').copy()
            else:
                df_sorted = df.copy()
        else:
            df_sorted = df.copy()
        
        # Pagination - Show if more than 400 rooms (before column layout)
        ROOMS_PER_PAGE = 50
        total_rooms = len(df_sorted)
        total_pages = max(1, (total_rooms + ROOMS_PER_PAGE - 1) // ROOMS_PER_PAGE)  # Ceiling division
        
        # Reset page if it's out of bounds
        if st.session_state.current_page > total_pages:
            st.session_state.current_page = 1
        
        # Calculate pagination slice (before column layout)
        start_idx = (st.session_state.current_page - 1) * ROOMS_PER_PAGE
        end_idx = start_idx + ROOMS_PER_PAGE
        df_paginated = df_sorted.iloc[start_idx:end_idx].copy()
        
        # New Layout: Map first (full width), then room cards in grid below
        # Map Section - Full Width
        st.subheader("🗺️ Map View")
        
        # Filter to apartments with coordinates for map
        if 'latitude' not in df.columns or 'longitude' not in df.columns:
            st.error(f"⚠️ Missing coordinate columns! Available columns: {list(df.columns)}")
            st.warning("⚠️ No rooms with valid coordinates for map display.")
        else:
            # Apply pagination to map - use the same paginated dataframe (already calculated above)
            # First, ensure coordinates are numeric BEFORE filtering
            df_paginated_for_map = df_paginated.copy()
            
            # Convert coordinates to numeric (handle strings, etc.)
            if 'latitude' in df_paginated_for_map.columns and 'longitude' in df_paginated_for_map.columns:
                df_paginated_for_map['latitude'] = pd.to_numeric(df_paginated_for_map['latitude'], errors='coerce')
                df_paginated_for_map['longitude'] = pd.to_numeric(df_paginated_for_map['longitude'], errors='coerce')
            
            # Filter to apartments with valid coordinates from paginated data
            valid_coords_mask = (
                df_paginated_for_map['latitude'].notna() & 
                df_paginated_for_map['longitude'].notna() &
                (df_paginated_for_map['latitude'] != 0) &
                (df_paginated_for_map['longitude'] != 0) &
                (df_paginated_for_map['latitude'] >= -90) &
                (df_paginated_for_map['latitude'] <= 90) &
                (df_paginated_for_map['longitude'] >= -180) &
                (df_paginated_for_map['longitude'] <= 180)
            )
            
            df_for_map = df_paginated_for_map[valid_coords_mask].copy()
            
            if len(df_for_map) > 0:
                try:
                    # Get selected room from session state (if any)
                    selected_room_id = st.session_state.get('selected_room_id', None)
                    
                    # Default color by suitability_score, fallback to rent if not available
                    map_color_by = 'suitability_score' if 'suitability_score' in df_for_map.columns else 'rent'
                    
                    m = create_interactive_map(
                        df_for_map,
                        st.session_state.university_coords,
                        st.session_state.university_name,
                        color_by=map_color_by,
                        highlight_room_id=selected_room_id
                    )
                    
                    # Display map (full width)
                    map_html = get_map_html(m)
                    components.html(map_html, height=600, scrolling=True)
                    
                    if total_rooms > ROOMS_PER_PAGE:
                        total_in_page = len(df_paginated)
                        st.caption(f"📍 Showing {len(df_for_map)} rooms with valid coordinates (Page {st.session_state.current_page}/{total_pages}, {total_in_page} total in page) + 1 university on map")
                    else:
                        st.caption(f"📍 Showing {len(df_for_map)} rooms with valid coordinates + 1 university on map")
                except Exception as e:
                    st.error(f"Error creating map: {str(e)}")
            else:
                st.warning("⚠️ No rooms with valid coordinates for map display.")
        
        st.markdown("---")
        
        # Room Cards Section - Grid Layout
        st.subheader("🏠 Rooms List")
        
        # Create grid container for room cards
        rooms_html = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; padding: 10px 0;">'
        
        # Display room cards - SHOW ONLY CURRENT PAGE ROOMS
        rooms_displayed = 0
        for idx, row in df_paginated.iterrows():
            rooms_displayed += 1
            
            # Check if has coordinates (for styling)
            has_coords = pd.notna(row.get('latitude')) and pd.notna(row.get('longitude'))
            # Light mode color scheme with better contrast
            bg_color = '#ffffff' if has_coords else '#fffbf0'  # White for normal, very light yellow for no coords
            border_color = '#4a90e2' if has_coords else '#ffc107'  # Blue border for normal, yellow for no coords
            text_color = '#262730'  # Dark text for good contrast in light mode
            
            # Escape HTML in text fields to prevent rendering issues
            provider_name = str(row.get('provider', f'Room #{idx}')) if pd.notna(row.get('provider')) else f'Room #{idx}'
            provider_name = provider_name.replace('<', '&lt;').replace('>', '&gt;')
            address_text = str(row.get('address', '')) if pd.notna(row.get('address')) else ''
            address_text = address_text.replace('<', '&lt;').replace('>', '&gt;')
            
            # Room card - build complete HTML string with click handler
            warning_icon = '⚠️' if not has_coords else ''
            room_id = f"room_{idx}"
            # Make card clickable if it has coordinates
            cursor_style = 'cursor: pointer;' if has_coords else ''
            hover_style = 'transition: all 0.3s ease;' if has_coords else ''
            data_attrs = ''
            if has_coords:
                lat = row.get('latitude')
                lon = row.get('longitude')
                if pd.notna(lat) and pd.notna(lon):
                    # Use data attributes instead of onclick to avoid React errors
                    data_attrs = f'data-room-id="{room_id}" data-room-lat="{lat}" data-room-lon="{lon}" class="room-card-clickable"'
                else:
                    data_attrs = 'class="room-card"'
            else:
                data_attrs = 'class="room-card"'
            
            # Use data attributes for event delegation (no inline onclick to avoid React errors)
            # Card styling for grid layout
            card_html = f'<div id="{room_id}" {data_attrs} style="border: 2px solid {border_color}; border-radius: 8px; padding: 15px; background-color: {bg_color}; {cursor_style} {hover_style}; box-shadow: 0 2px 4px rgba(0,0,0,0.1); height: 100%; display: flex; flex-direction: column;">'
            card_html += f'<h4 style="margin-top: 0; color: {text_color}; margin-bottom: 10px; font-weight: 600;">{provider_name} {warning_icon}</h4>'
            
            # Address
            if pd.notna(row.get('address')):
                card_html += f'<p style="margin: 5px 0; color: #555; font-size: 14px;">📍 {address_text}</p>'
            
            # Show coordinate status (only once)
            if not has_coords:
                card_html += f'<p style="margin: 5px 0; color: #d68910; font-size: 12px; font-weight: 500;">⚠️ No coordinates</p>'
            else:
                lat = row.get('latitude', 'N/A')
                lon = row.get('longitude', 'N/A')
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    card_html += f'<p style="margin: 5px 0; color: #27ae60; font-size: 11px;">✓ Coordinates available</p>'
            
            # Transport Information Section - Check if we have any transport data first
            transport_section = False
            has_transport_data = (
                pd.notna(row.get('nearest_stop_name')) or
                pd.notna(row.get('walking_time_minutes')) or
                pd.notna(row.get('walking_from_stop_minutes')) or
                pd.notna(row.get('route_details')) or
                pd.notna(row.get('transport_modes')) or
                pd.notna(row.get('transit_time_minutes')) or
                pd.notna(row.get('total_commute_minutes')) or
                pd.notna(row.get('transfers'))
            )
            
            # Rent - handle both valid rent and missing rent
            rent_val = row.get('rent')
            
            if pd.notna(rent_val):
                try:
                    rent_float = float(rent_val)
                    if rent_float > 0:
                        card_html += f'<p style="margin: 8px 0 5px 0; font-size: 18px; font-weight: bold; color: #27ae60;">💰 €{rent_float:.0f}/month</p>'
                    else:
                        card_html += '<p style="margin: 8px 0 5px 0; font-size: 14px; color: #999;">💰 Rent: N/A</p>'
                except (ValueError, TypeError):
                    card_html += '<p style="margin: 8px 0 5px 0; font-size: 14px; color: #999;">💰 Rent: N/A</p>'
            else:
                card_html += '<p style="margin: 8px 0 5px 0; font-size: 14px; color: #999;">💰 Rent: N/A</p>'
            
            # Divider line
            card_html += '<hr style="margin: 10px 0; border: none; border-top: 1px solid #e0e0e0;">'
            
            # Transport details container (always visible)
            if has_transport_data:
                card_html += f'<div style="background: #f5f7fa; padding: 10px; border-radius: 5px; margin-top: 8px;">'
            
            # Nearest Stop
            if pd.notna(row.get('nearest_stop_name')):
                stop_name = str(row["nearest_stop_name"]).replace('<', '&lt;').replace('>', '&gt;')
                distance = row.get('nearest_stop_distance_m', 0)
                if pd.notna(distance) and distance > 0:
                    card_html += f'<p style="margin: 5px 0; font-size: 13px; color: {text_color};"><strong style="color: #2980b9;">🚉 Stop:</strong> {stop_name} <span style="color: #7f8c8d;">({distance:.0f}m)</span></p>'
                else:
                    card_html += f'<p style="margin: 5px 0; font-size: 13px; color: {text_color};"><strong style="color: #2980b9;">🚉 Stop:</strong> {stop_name}</p>'
                transport_section = True
            
            # Walking Time to Station
            if pd.notna(row.get('walking_time_minutes')) and row['walking_time_minutes'] > 0:
                distance = row.get('nearest_stop_distance_m', 0)
                if pd.notna(distance) and distance > 0:
                    card_html += f'<p style="margin: 5px 0; font-size: 13px; color: {text_color};"><strong style="color: #16a085;">🚶 To Station:</strong> {row["walking_time_minutes"]:.1f} min ({distance:.0f}m)</p>'
                else:
                    card_html += f'<p style="margin: 5px 0; font-size: 13px; color: {text_color};"><strong style="color: #16a085;">🚶 To Station:</strong> {row["walking_time_minutes"]:.1f} min</p>'
                transport_section = True
            
            # Walking Time from Final Station to University
            if pd.notna(row.get('walking_from_stop_minutes')) and row['walking_from_stop_minutes'] > 0:
                distance = row.get('final_stop_distance_m', 0)
                if pd.notna(distance) and distance > 0:
                    card_html += f'<p style="margin: 5px 0; font-size: 13px; color: {text_color};"><strong style="color: #16a085;">🚶 From Station:</strong> {row["walking_from_stop_minutes"]:.1f} min ({distance:.0f}m)</p>'
                else:
                    card_html += f'<p style="margin: 5px 0; font-size: 13px; color: {text_color};"><strong style="color: #16a085;">🚶 From Station:</strong> {row["walking_from_stop_minutes"]:.1f} min</p>'
                transport_section = True
            
            # Route Details - Show transport types and line names
            route_details_value = row.get('route_details')
            route_details_displayed = False  # Track if we displayed route_details
            # Debug: Check what we have
            if pd.notna(route_details_value) and route_details_value and str(route_details_value).strip() != '' and str(route_details_value).lower() != 'none':
                try:
                    import json
                    route_details_str = str(route_details_value)
                    # Try to parse as JSON
                    if route_details_str.startswith('[') or route_details_str.startswith('{'):
                        route_details = json.loads(route_details_str)
                    else:
                        route_details = route_details_value
                    
                    if route_details and len(route_details) > 0:
                        logger.debug(f"Displaying route_details: {route_details}")
                        card_html += '<p style="margin: 8px 0 5px 0; font-size: 13px; color: ' + text_color + ';"><strong style="color: #8e44ad;">🚇 Routes:</strong></p>'
                        route_details_displayed = True
                        transport_section = True
                        
                        # Show route count if multiple routes
                        if len(route_details) > 1:
                            card_html += f'<p style="margin: 5px 0; font-size: 12px; color: #666;"><em>{len(route_details)} route segments with {len(route_details)-1} transfer(s)</em></p>'
                        
                        for idx, route in enumerate(route_details):
                            mode = route.get('mode', 'unknown')
                            name = route.get('name', '')
                            from_stop = route.get('from', '')
                            to_stop = route.get('to', '')
                            
                            # Map mode to display name
                            mode_display_map = {
                                'subway': 'U-Bahn',
                                'suburban': 'S-Bahn',
                                'bus': 'Bus',
                                'tram': 'Tram',
                                'public_transport': 'Public Transport'
                            }
                            mode_display = mode_display_map.get(mode.lower(), mode.title())
                            
                            # Color coding
                            mode_colors = {
                                'subway': '#0066cc',
                                'suburban': '#00cc00',
                                'bus': '#ff6600',
                                'tram': '#cc0000'
                            }
                            mode_color = mode_colors.get(mode.lower(), '#8e44ad')
                            
                            # Escape HTML in route components first
                            name_escaped = str(name).replace('<', '&lt;').replace('>', '&gt;').strip() if name and str(name) != 'nan' else ''
                            from_stop_escaped = str(from_stop).replace('<', '&lt;').replace('>', '&gt;') if from_stop and str(from_stop) != 'nan' else ''
                            to_stop_escaped = str(to_stop).replace('<', '&lt;').replace('>', '&gt;') if to_stop and str(to_stop) != 'nan' else ''
                            
                            # Build route text - always show mode and name if available
                            route_text = f"{mode_display}"
                            if name_escaped:
                                route_text += f" <strong>{name_escaped}</strong>"
                            
                            # Show route segment if available
                            if from_stop_escaped and to_stop_escaped:
                                route_text += f"<br><span style='font-size: 11px; opacity: 0.9;'>{from_stop_escaped} → {to_stop_escaped}</span>"
                            
                            # Add step number if multiple routes
                            if len(route_details) > 1:
                                step_num = idx + 1
                                route_text = f"<span style='background: rgba(255,255,255,0.2); padding: 2px 6px; border-radius: 10px; margin-right: 5px; font-size: 10px;'>Step {step_num}</span>" + route_text
                            
                            card_html += f'<p style="margin: 3px 0; padding: 6px; background: {mode_color}; color: white; border-radius: 4px; font-size: 12px; font-weight: bold; line-height: 1.4;">{route_text}</p>'
                except Exception as e:
                    # Log error for debugging
                    import traceback
                    logger.error(f"Error parsing route_details: {e}")
                    logger.error(traceback.format_exc())
                    # Fallback to transport_modes if route_details parsing fails
                    pass
            
            # Transport Modes - format nicely (fallback if route_details not available or empty)
            # Show transport modes as colored badges if route_details weren't displayed
            if not route_details_displayed and pd.notna(row.get('transport_modes')) and row['transport_modes']:
                modes_str = str(row['transport_modes'])
                # Convert mode names to display format
                mode_display_map = {
                    'subway': 'U-Bahn',
                    'suburban': 'S-Bahn',
                    'bus': 'Bus',
                    'tram': 'Tram',
                    'public_transport': 'Public Transport'
                }
                modes_list = [m.strip() for m in modes_str.split(',')]
                formatted_modes = [mode_display_map.get(m.lower(), m.title()) for m in modes_list]
                modes_display = ', '.join(formatted_modes)
                modes_display = modes_display.replace('<', '&lt;').replace('>', '&gt;')
                
                # Show as colored badges similar to route_details
                if not transport_section:
                    card_html += '<p style="margin: 8px 0 5px 0; font-size: 13px; color: ' + text_color + ';"><strong style="color: #8e44ad;">🚇 Transport Types:</strong></p>'
                
                # Create badges for each mode
                for mode in modes_list:
                    mode_lower = mode.lower().strip()
                    mode_colors = {
                        'subway': '#0066cc',
                        'suburban': '#00cc00',
                        'bus': '#ff6600',
                        'tram': '#cc0000'
                    }
                    mode_color = mode_colors.get(mode_lower, '#8e44ad')
                    mode_display_name = mode_display_map.get(mode_lower, mode.title())
                    card_html += f'<p style="margin: 3px 0; padding: 6px; background: {mode_color}; color: white; border-radius: 4px; font-size: 12px; font-weight: bold;">{mode_display_name}</p>'
                
                transport_section = True
            
            # Transit Time
            if pd.notna(row.get('transit_time_minutes')) and row['transit_time_minutes'] > 0:
                card_html += f'<p style="margin: 5px 0; font-size: 13px; color: {text_color};"><strong style="color: #e67e22;">🚊 Transit:</strong> {row["transit_time_minutes"]:.1f} min</p>'
                transport_section = True
            
            # Total Commute
            if pd.notna(row.get('total_commute_minutes')) and row['total_commute_minutes'] > 0:
                card_html += f'<p style="margin: 8px 0 5px 0; font-size: 15px; font-weight: bold; color: #2980b9; background: #e8f4f8; padding: 6px; border-radius: 4px;">⏱️ Total Commute: {row["total_commute_minutes"]:.1f} min</p>'
                transport_section = True
            
            # Transfers
            if pd.notna(row.get('transfers')):
                transfers = int(row['transfers']) if pd.notna(row['transfers']) else 0
                card_html += f'<p style="margin: 5px 0; font-size: 13px; color: {text_color};"><strong style="color: #c0392b;">🔄 Transfers:</strong> {transfers}</p>'
                transport_section = True
            
            # Show N/A if no transport data - but be more helpful
            if not transport_section and has_transport_data:
                if has_coords:
                    # Check if we at least have a stop name
                    if pd.notna(row.get('nearest_stop_name')):
                        stop_name = str(row.get('nearest_stop_name'))
                        distance = row.get('nearest_stop_distance_m', 0)
                        if pd.notna(distance) and distance > 0:
                            card_html += f'<p style="margin: 5px 0; font-size: 13px; color: {text_color};"><strong style="color: #2980b9;">🚉 Nearest Stop:</strong> {stop_name} <span style="color: #7f8c8d;">({distance:.0f}m)</span></p>'
                        else:
                            card_html += f'<p style="margin: 5px 0; font-size: 13px; color: {text_color};"><strong style="color: #2980b9;">🚉 Nearest Stop:</strong> {stop_name}</p>'
                    else:
                        card_html += f'<p style="margin: 5px 0; font-size: 12px; color: #95a5a6;">Transport data: N/A (no nearby stop found)</p>'
                else:
                    card_html += f'<p style="margin: 5px 0; font-size: 12px; color: #95a5a6;">Transport data: N/A (no coordinates)</p>'
            
            # Close transport section only if it was opened
            if has_transport_data:
                card_html += '</div>'  # Close transport details div
            
            # Close card div
            card_html += '</div>'
            rooms_html += card_html
        
        rooms_html += '</div>'
        
        # Add JavaScript for room card click handling
        click_script = """
        <script>
        // Event delegation for room card clicks (avoids React errors with inline onclick)
            document.addEventListener('click', function(event) {
                const card = event.target.closest('.room-card-clickable');
                if (card) {
                    const roomId = card.getAttribute('data-room-id');
                    const lat = parseFloat(card.getAttribute('data-room-lat'));
                    const lon = parseFloat(card.getAttribute('data-room-lon'));
                    
                    if (roomId && !isNaN(lat) && !isNaN(lon)) {
                        focusRoomOnMap(roomId, lat, lon);
                    }
                }
            });
            
            function focusRoomOnMap(roomId, lat, lon) {
                // Highlight the clicked card
                const card = document.getElementById(roomId);
                if (card) {
                    document.querySelectorAll('.room-card-clickable, .room-card').forEach(c => {
                        const originalBorder = c.getAttribute('data-original-border') || '2px solid #ddd';
                        c.style.border = originalBorder;
                        c.style.boxShadow = 'none';
                    });
                    
                    if (!card.getAttribute('data-original-border')) {
                        card.setAttribute('data-original-border', card.style.border || '2px solid #ddd');
                    }
                    
                    card.style.border = '3px solid #007bff';
                    card.style.boxShadow = '0 4px 12px rgba(0,123,255,0.3)';
                    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
                
                // Send message to map iframe
                setTimeout(function() {
                    const mapFrames = document.querySelectorAll('iframe');
                    mapFrames.forEach(function(frame) {
                        if (frame.contentWindow) {
                            try {
                                frame.contentWindow.postMessage({
                                    type: 'focusRoom',
                                    roomId: roomId,
                                    lat: lat,
                                    lon: lon
                                }, '*');
                            } catch(e) {}
                        }
                    });
                }, 100);
            }
            </script>
            """
        rooms_html += click_script
        
        # Render HTML properly - ensure it's all in one markdown call
        st.markdown(rooms_html, unsafe_allow_html=True)
        
        # Pagination controls at the bottom
        if total_rooms > ROOMS_PER_PAGE:
                st.markdown("---")
                pagination_col1, pagination_col2, pagination_col3 = st.columns([1, 2, 1])
                
                with pagination_col1:
                    if st.button("◀ Previous", disabled=(st.session_state.current_page == 1), key="prev_page"):
                        st.session_state.current_page = max(1, st.session_state.current_page - 1)
                        st.rerun()
                
                with pagination_col2:
                    page_input = st.number_input(
                        f"Page {st.session_state.current_page} of {total_pages}",
                        min_value=1,
                        max_value=total_pages,
                        value=st.session_state.current_page,
                        key="page_input",
                        on_change=lambda: setattr(st.session_state, 'current_page', st.session_state.page_input)
                    )
                    if page_input != st.session_state.current_page:
                        st.session_state.current_page = page_input
                        st.rerun()
                
                with pagination_col3:
                    if st.button("Next ▶", disabled=(st.session_state.current_page == total_pages), key="next_page"):
                        st.session_state.current_page = min(total_pages, st.session_state.current_page + 1)
                        st.rerun()
                
                st.caption(f"Showing rooms {start_idx + 1}-{min(end_idx, total_rooms)} of {total_rooms} (Page {st.session_state.current_page}/{total_pages})")


if __name__ == "__main__":
    main()

