"""
Smart Student Housing Finder - Streamlit App
============================================

Main application interface for ranking student apartments in Berlin by:
- Cost (affordability)
- Commute time to university (BVG public transport)
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

# Page configuration
st.set_page_config(
    page_title="Smart Student Housing Finder - Berlin",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        padding-bottom: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
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


def main():
    """Main application function"""
    
    # Header
    st.markdown('<p class="main-header">🏠 Smart Student Housing Finder</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Ranking Apartments in Berlin by Cost, Commute Time & BVG Accessibility</p>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Main Configuration Section (No Tabs)
    st.header("⚙️ Configuration")
    
    # Data Section
    st.subheader("📁 Accommodation Data")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Check for existing file in directory
        default_file = "Accomodations.csv"
        file_exists = Path(default_file).exists()
        
        if file_exists:
            st.info(f"📁 Found: `{default_file}`")
            use_default = st.checkbox("Use existing file", value=True, key="use_default_file")
            
            # Provider selection from code configuration
            # ============================================
            # DYNAMIC: Auto-detect all providers from CSV, then enable/disable below
            # ============================================
            import pandas as pd
            default_file = "Accomodations.csv"
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
            # Set to True to include, False to exclude
            # YOU CAN ENABLE MULTIPLE PROVIDERS AT ONCE!
            # ============================================
            # List of providers you want to enable (add/remove provider names as needed)
            PROVIDERS_TO_ENABLE = ['Neonwood', 'Zimmerei']  # <-- EDIT THIS LIST
            
            ENABLED_PROVIDERS = {}
            for provider in all_providers_dynamic:
                # Enable providers that are in the PROVIDERS_TO_ENABLE list
                ENABLED_PROVIDERS[provider] = (provider in PROVIDERS_TO_ENABLE)
            # ============================================
            # EXAMPLE: To enable more providers, add them to the list:
            # PROVIDERS_TO_ENABLE = ['Neonwood', 'Zimmerei', 'The Urban Club', 'Havens Living', '66 Monkeys']
            # ============================================
            
            # Get selected providers from configuration
            selected_providers = [provider for provider, enabled in ENABLED_PROVIDERS.items() if enabled]
            
            if selected_providers:
                provider_filter = ', '.join(selected_providers)
                st.info(f"✅ **Enabled Providers:** {', '.join(selected_providers)} ({len(selected_providers)} total)")
            else:
                provider_filter = None
                st.warning("⚠️ No providers enabled in code configuration. Please edit ENABLED_PROVIDERS in app.py")
            
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
                st.info("🔄 Provider configuration changed. Reloading data...")
                st.rerun()
            
            preview_mode = st.checkbox("Preview mode (50 rooms)", value=False, key="preview_mode", 
                                      help="Load 50 rooms for preview (uncheck for all data)")
        else:
            use_default = False
            preview_mode = False
            st.warning("No default file found. Please upload a file.")
    
    with col2:
        if use_default and file_exists:
            if st.button("🔄 Reload Data"):
                with st.spinner("Reloading..."):
                    limit = 50 if preview_mode else None
                    # Use provider filter from session state
                    provider = st.session_state.get('provider_filter', None)
                    if provider and provider.strip():
                        provider = provider.strip()
                    else:
                        provider = None
                    st.session_state.apartments_df = load_accommodation_data(default_file, limit=limit, provider_filter=provider)
                    validate_data(st.session_state.apartments_df)
                    st.session_state.analysis_complete = False
                    mode_text = " (preview: 50 rooms)" if preview_mode else ""
                st.success(f"✓ Reloaded {len(st.session_state.apartments_df)} accommodations{mode_text}")
                st.rerun()
    
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
    
    # University Selection (in same section)
    st.subheader("🎓 Select University")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
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
            help="Choose from major Berlin universities (public and private)"
        )
        
        # Get university name from mapping
        if selected_formatted:
            selected_university = uni_mapping[selected_formatted]
            uni_info = get_university_info(selected_university)
            
            if uni_info:
                # Set university coordinates (pre-stored, no geocoding needed)
                st.session_state.university_coords = (uni_info['latitude'], uni_info['longitude'])
                st.session_state.university_name = uni_info['name']
                st.success(f"✓ {uni_info['name']} selected - {uni_info['address']}")
    
    # Show preview if data is loaded
    if st.session_state.apartments_df is not None:
        preview_rows = min(50, len(st.session_state.apartments_df))
        with st.expander(f"📊 Preview Data ({len(st.session_state.apartments_df)} total rows, showing first {preview_rows})"):
            st.dataframe(st.session_state.apartments_df.head(preview_rows))
            if preview_mode:
                st.info("ℹ️ Preview mode is active - 50 rooms loaded. Uncheck 'Preview mode' to load all data.")
    
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
        
        # Step 1: Geocode apartments
        st.header("Step 1: Geocoding Apartments")
        progress_bar = st.progress(0)
        status_text = st.empty()
        stats_text = st.empty()
        
        # Check how many need geocoding - ALWAYS geocode if columns don't exist or any are missing
        needs_geocoding = True
        if 'latitude' in df.columns and 'longitude' in df.columns:
            # Check if ALL addresses have coordinates
            has_coords = df['latitude'].notna() & df['longitude'].notna()
            needs_geocoding = not has_coords.all()  # Need geocoding if ANY are missing
        
        if needs_geocoding:
            status_text.text("Geocoding apartment addresses (using cache for speed)...")
            
            # Progress callback for Streamlit
            def update_progress(current, total, cached, new):
                progress = current / total if total > 0 else 0
                progress_bar.progress(progress * 0.33)
                successful = cached + new
                stats_text.text(f"Progress: {current}/{total} addresses | {successful} successful ({cached} cached, {new} new)")
            
            # Ensure latitude/longitude columns exist before geocoding
            if 'latitude' not in df.columns:
                df['latitude'] = None
            if 'longitude' not in df.columns:
                df['longitude'] = None
            
            df = geocode_dataframe(df, progress_callback=update_progress)
            progress_bar.progress(0.33)
            
            # Show summary of geocoded rooms
            geocoded_count = df['latitude'].notna().sum() if 'latitude' in df.columns else 0
            total_count = len(df)
            
            if geocoded_count == total_count:
                status_text.success(f"✓ Geocoding complete! All {geocoded_count} rooms have coordinates.")
            else:
                status_text.warning(f"✓ Geocoding complete! {geocoded_count}/{total_count} rooms have coordinates.")
            
            # Display all rooms with coordinates in expander
            with st.expander(f"📋 View All {geocoded_count} Rooms with Coordinates", expanded=False):
                if geocoded_count > 0:
                    # Create display dataframe
                    display_df = df[df['latitude'].notna()].copy()
                    if 'provider' in display_df.columns:
                        display_df = display_df.sort_values(['provider', 'address'])
                    
                    # Select columns to show
                    cols_to_show = []
                    if 'provider' in display_df.columns:
                        cols_to_show.append('provider')
                    if 'address' in display_df.columns:
                        cols_to_show.append('address')
                    if 'rent' in display_df.columns:
                        cols_to_show.append('rent')
                    cols_to_show.extend(['latitude', 'longitude'])
                    
                    st.dataframe(
                        display_df[cols_to_show],
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.warning("No rooms with coordinates found.")
        else:
            status_text.text("Using existing coordinates...")
            progress_bar.progress(0.33)
        
        # Step 2: Calculate commute times and distances
        st.header("Step 2: Calculating Commute Times & Distances")
        status_text.text("Querying BVG API for commute times (using cache when available)...")
        status_text.info("ℹ️ All BVG API responses are automatically saved to JSON files in bvg_cache/ directory for faster future runs")
        
        # Debug: Check coordinates before BVG processing
        coords_before = df['latitude'].notna().sum() if 'latitude' in df.columns else 0
        status_text.text(f"🔍 Debug: {coords_before} rooms have coordinates before BVG processing")
        
        # Progress tracking for BVG API
        bvg_progress_text = st.empty()
        total_apartments = len(df)
        cached_journeys = 0
        new_journeys = 0
        
        def update_bvg_progress(idx, total, cached, new):
            nonlocal cached_journeys, new_journeys
            cached_journeys = cached
            new_journeys = new
            progress = 0.33 + (idx / total) * 0.33 if total > 0 else 0.33
            progress_bar.progress(progress)
            bvg_progress_text.text(f"Progress: {idx}/{total} apartments | {cached + new} successful ({cached} cached, {new} new)")
        
        # Ensure coordinates are preserved - batch_get_commute_info modifies df in place
        batch_get_commute_info(
            df,
            st.session_state.university_coords[0],
            st.session_state.university_coords[1],
            delay=0.5,
            progress_callback=update_bvg_progress
        )
        
        # Debug: Check coordinates after BVG processing
        coords_after = df['latitude'].notna().sum() if 'latitude' in df.columns else 0
        status_text.text(f"🔍 Debug: {coords_after} rooms have coordinates after BVG processing")
        
        progress_bar.progress(0.66)
        bvg_progress_text.success(f"✓ Processed {total_apartments} apartments ({cached_journeys} cached, {new_journeys} new)")
        
        # Step 3: Calculate scores (with default weights)
        st.header("Step 3: Calculating Scores")
        status_text.text("Computing composite suitability scores...")
        
        # Debug: Check coordinates before scoring
        coords_before_scoring = df['latitude'].notna().sum() if 'latitude' in df.columns else 0
        status_text.text(f"🔍 Debug: {coords_before_scoring} rooms have coordinates before scoring")
        
        df = calculate_student_suitability_score(
            df,
            rent_weight=0.35,
            commute_weight=0.40,
            walking_weight=0.15,
            transfers_weight=0.10
        )
        
        # Debug: Check coordinates after scoring
        coords_after_scoring = df['latitude'].notna().sum() if 'latitude' in df.columns else 0
        status_text.text(f"🔍 Debug: {coords_after_scoring} rooms have coordinates after scoring")
        
        progress_bar.progress(1.0)
        
        # Store processed dataframe (ALL apartments, no filtering)
        # Ensure coordinates are preserved - use .copy() to ensure we have a fresh copy
        if 'latitude' not in df.columns or 'longitude' not in df.columns:
            st.error(f"⚠️ ERROR: Coordinates missing after processing! Columns: {list(df.columns)}")
        else:
            coords_in_final = df['latitude'].notna().sum()
            st.info(f"🔍 Final check: {coords_in_final} rooms with coordinates in final dataframe")
        
        st.session_state.processed_df = df.copy()  # Use .copy() to ensure we have a fresh copy
        st.session_state.analysis_complete = True
        
        # Debug: Show provider breakdown after processing
        if 'provider' in df.columns:
            provider_counts = df['provider'].value_counts()
            status_text.success(f"✓ Analysis complete! Processed {len(df)} rooms from {len(provider_counts)} providers: {', '.join(provider_counts.index.tolist())}")
        else:
            status_text.success("✓ Analysis complete!")
        st.balloons()
    
    # Display results - Simplified UI: Room List + Map
    if st.session_state.analysis_complete and st.session_state.processed_df is not None:
        df = st.session_state.processed_df.copy()
        
        # Show all apartments (no filtering) - INCLUDING those without coordinates
        if len(df) == 0:
            st.warning("No apartments found. Please check your data or reload.")
            return
        
        # Debug: Show what we have
        if 'provider' in df.columns:
            st.info(f"📊 **Displaying {len(df)} rooms from {df['provider'].nunique()} providers**")
            provider_breakdown = df['provider'].value_counts()
            st.write(f"**Providers:** {', '.join(provider_breakdown.index.tolist())}")
            
            # Show which have coordinates
            with_coords = df[df['latitude'].notna()].shape[0]
            without_coords = df[df['latitude'].isna()].shape[0]
            st.write(f"✓ {with_coords} with coordinates, ⚠️ {without_coords} without coordinates (will still show in list)")
        
        # Two column layout: Left = Room List, Right = Map
        left_col, right_col = st.columns([1, 1.5])
        
        with left_col:
            st.subheader("🏠 Rooms List")
            
            # Sort options
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
            
            # Debug: Show provider breakdown
            if 'provider' in df_sorted.columns:
                provider_counts = df_sorted['provider'].value_counts()
                st.write(f"📊 **Total rooms: {len(df_sorted)} from {len(provider_counts)} providers**")
                st.write(f"**Providers:** {', '.join(provider_counts.index.tolist())}")
            
            # Create scrollable container for room cards
            # Use a clean HTML structure
            rooms_html = '<div style="height: 800px; overflow-y: auto; padding-right: 10px;">'
            
            # Display room cards - SHOW ALL ROOMS (even without coordinates)
            rooms_displayed = 0
            for idx, row in df_sorted.iterrows():
                rooms_displayed += 1
                
                # Check if has coordinates (for styling)
                has_coords = pd.notna(row.get('latitude')) and pd.notna(row.get('longitude'))
                bg_color = '#f9f9f9' if has_coords else '#fff3cd'  # Yellow background if no coordinates
                border_color = '#ddd' if has_coords else '#ffc107'  # Yellow border if no coordinates
                
                # Escape HTML in text fields to prevent rendering issues
                provider_name = str(row.get('provider', f'Room #{idx}')) if pd.notna(row.get('provider')) else f'Room #{idx}'
                provider_name = provider_name.replace('<', '&lt;').replace('>', '&gt;')
                address_text = str(row.get('address', '')) if pd.notna(row.get('address')) else ''
                address_text = address_text.replace('<', '&lt;').replace('>', '&gt;')
                
                # Room card - build complete HTML string
                warning_icon = '⚠️' if not has_coords else ''
                card_html = f'<div style="border: 2px solid {border_color}; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: {bg_color};">'
                card_html += f'<h4 style="margin-top: 0; color: #2c3e50; margin-bottom: 10px;">{provider_name} {warning_icon}</h4>'
                
                # Address
                if pd.notna(row.get('address')):
                    card_html += f'<p style="margin: 5px 0; color: #7f8c8d; font-size: 14px;">📍 {address_text}</p>'
                
                # Show coordinate status (only once)
                if not has_coords:
                    card_html += f'<p style="margin: 5px 0; color: #856404; font-size: 12px;">⚠️ No coordinates</p>'
                else:
                    lat = row.get('latitude', 'N/A')
                    lon = row.get('longitude', 'N/A')
                    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                        card_html += f'<p style="margin: 5px 0; color: #28a745; font-size: 11px;">✓ ({lat:.6f}, {lon:.6f})</p>'
                
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
                card_html += '<hr style="margin: 10px 0; border: none; border-top: 1px solid #ddd;">'
                
                # Transport Information Section
                transport_section = False
                
                # Nearest Stop
                if pd.notna(row.get('nearest_stop_name')):
                    stop_name = str(row["nearest_stop_name"]).replace('<', '&lt;').replace('>', '&gt;')
                    distance = row.get('nearest_stop_distance_m', 0)
                    if pd.notna(distance) and distance > 0:
                        card_html += f'<p style="margin: 5px 0; font-size: 13px;"><strong>🚉 Stop:</strong> {stop_name} ({distance:.0f}m)</p>'
                    else:
                        card_html += f'<p style="margin: 5px 0; font-size: 13px;"><strong>🚉 Stop:</strong> {stop_name}</p>'
                    transport_section = True
                
                # Walking Time
                if pd.notna(row.get('walking_time_minutes')) and row['walking_time_minutes'] > 0:
                    card_html += f'<p style="margin: 5px 0; font-size: 13px;"><strong>🚶 Walking:</strong> {row["walking_time_minutes"]:.1f} min</p>'
                    transport_section = True
                
                # Transport Modes
                if pd.notna(row.get('transport_modes')) and row['transport_modes']:
                    modes = str(row['transport_modes']).replace('<', '&lt;').replace('>', '&gt;')
                    card_html += f'<p style="margin: 5px 0; font-size: 13px;"><strong>🚇 Transport:</strong> {modes}</p>'
                    transport_section = True
                
                # Transit Time
                if pd.notna(row.get('transit_time_minutes')) and row['transit_time_minutes'] > 0:
                    card_html += f'<p style="margin: 5px 0; font-size: 13px;"><strong>🚊 Transit:</strong> {row["transit_time_minutes"]:.1f} min</p>'
                    transport_section = True
                
                # Total Commute
                if pd.notna(row.get('total_commute_minutes')) and row['total_commute_minutes'] > 0:
                    card_html += f'<p style="margin: 8px 0 5px 0; font-size: 15px; font-weight: bold; color: #3498db;">⏱️ Total Commute: {row["total_commute_minutes"]:.1f} min</p>'
                    transport_section = True
                
                # Transfers
                if pd.notna(row.get('transfers')):
                    transfers = int(row['transfers']) if pd.notna(row['transfers']) else 0
                    card_html += f'<p style="margin: 5px 0; font-size: 13px;"><strong>🔄 Transfers:</strong> {transfers}</p>'
                    transport_section = True
                
                # Show N/A if no transport data
                if not transport_section and has_coords:
                    card_html += '<p style="margin: 5px 0; font-size: 12px; color: #999;">Transport data: N/A</p>'
                elif not transport_section and not has_coords:
                    card_html += '<p style="margin: 5px 0; font-size: 12px; color: #999;">Transport data: N/A (no coordinates)</p>'
                
                # Close card div
                card_html += '</div>'
                rooms_html += card_html
            
            rooms_html += '</div>'
            
            # Render HTML properly - ensure it's all in one markdown call
            st.markdown(rooms_html, unsafe_allow_html=True)
            
            # Debug info
            st.caption(f"Displayed {rooms_displayed} room cards out of {len(df_sorted)} total rooms")
        
        with right_col:
            st.subheader("🗺️ Map View")
            
            # Filter to apartments with coordinates for map
            # Check if latitude/longitude columns exist
            if 'latitude' not in df.columns or 'longitude' not in df.columns:
                st.error(f"⚠️ Missing coordinate columns! Available columns: {list(df.columns)}")
                st.warning("⚠️ No rooms with valid coordinates for map display.")
                return
            
            apartments_with_coords = df['latitude'].notna() & df['longitude'].notna()
            df_for_map = df[apartments_with_coords].copy()
            
            # Debug: Show how many have coordinates
            st.write(f"🔍 Debug: {len(df_for_map)} rooms have coordinates out of {len(df)} total")
            
            if len(df_for_map) > 0:
                # Check coordinate types and values
                st.write(f"🔍 Coordinate types: lat={df_for_map['latitude'].dtype}, lon={df_for_map['longitude'].dtype}")
                st.write(f"🔍 Sample coordinates: {df_for_map[['latitude', 'longitude']].head(3).to_dict('records')}")
            
            # Ensure coordinates are valid numbers (not 0,0) - show ALL valid coordinates
            df_for_map = df_for_map[
                (df_for_map['latitude'].notna()) & 
                (df_for_map['longitude'].notna()) &
                (df_for_map['latitude'] != 0) &
                (df_for_map['longitude'] != 0)
            ].copy()
            
            # Additional check: ensure coordinates are numeric
            if len(df_for_map) > 0:
                df_for_map['latitude'] = pd.to_numeric(df_for_map['latitude'], errors='coerce')
                df_for_map['longitude'] = pd.to_numeric(df_for_map['longitude'], errors='coerce')
                df_for_map = df_for_map[
                    (df_for_map['latitude'].notna()) & 
                    (df_for_map['longitude'].notna())
                ].copy()
            
            st.write(f"🔍 Debug: {len(df_for_map)} rooms pass validation (will show on map)")
            
            # Debug: Check for "The Urban Club" specifically
            if 'provider' in df_for_map.columns:
                urban_club = df_for_map[df_for_map['provider'].str.contains('Urban Club', case=False, na=False)]
                if len(urban_club) > 0:
                    st.write(f"✅ Found {len(urban_club)} 'Urban Club' room(s) in map data")
                    st.write("Urban Club coordinates:", urban_club[['provider', 'address', 'latitude', 'longitude']].to_dict('records'))
                else:
                    st.write("⚠️ 'Urban Club' not found in map data. Checking full dataset...")
                    urban_club_all = df[df['provider'].str.contains('Urban Club', case=False, na=False)] if 'provider' in df.columns else pd.DataFrame()
                    if len(urban_club_all) > 0:
                        st.write(f"Found {len(urban_club_all)} 'Urban Club' in full dataset:")
                        st.write(urban_club_all[['provider', 'address', 'latitude', 'longitude']].to_dict('records'))
            
            # Show sample coordinates for debugging
            if len(df_for_map) > 0:
                st.write("Sample coordinates:", df_for_map[['provider', 'address', 'latitude', 'longitude']].head(3).to_dict('records'))
            else:
                st.write(f"⚠️ Debug: No rooms with valid coordinates!")
                if 'latitude' in df.columns and 'longitude' in df.columns:
                    st.write(f"Non-null coordinates: {df['latitude'].notna().sum()} lat, {df['longitude'].notna().sum()} lon")
                    st.write("Sample data:", df[['address', 'latitude', 'longitude']].head(5))
            
            if len(df_for_map) > 0:
                # Color option
                map_color_by = st.selectbox(
                    "Color by:",
                    ['suitability_score', 'rent', 'total_commute_minutes'],
                    key="map_color"
                )
                
                try:
                    m = create_interactive_map(
                        df_for_map,
                        st.session_state.university_coords,
                        st.session_state.university_name,
                        color_by=map_color_by if map_color_by in df_for_map.columns else 'rent'
                    )
                    
                    # Display map
                    map_html = get_map_html(m)
                    components.html(map_html, height=800, scrolling=True)
                    
                    st.info(f"📍 Showing {len(df_for_map)} rooms + 1 university on map")
                except Exception as e:
                    st.error(f"Error creating map: {str(e)}")
            else:
                st.warning("⚠️ No rooms with valid coordinates for map display.")


if __name__ == "__main__":
    main()

