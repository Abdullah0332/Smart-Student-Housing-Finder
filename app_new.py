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
            preview_mode = st.checkbox("Preview mode (100 rooms)", value=False, key="preview_mode", 
                                      help="Load 100 rooms for preview (uncheck for all data)")
        else:
            use_default = False
            preview_mode = False
            st.warning("No default file found. Please upload a file.")
    
    with col2:
        if use_default and file_exists:
            if st.button("🔄 Reload Data"):
                with st.spinner("Reloading..."):
                    limit = 100 if preview_mode else None
                    st.session_state.apartments_df = load_accommodation_data(default_file, limit=limit)
                    validate_data(st.session_state.apartments_df)
                    st.session_state.analysis_complete = False
                mode_text = " (preview: 100 rooms)" if preview_mode else ""
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
            if st.session_state.apartments_df is None:
                with st.spinner("Loading accommodation data..."):
                    limit = 100 if preview_mode else None
                    st.session_state.apartments_df = load_accommodation_data(default_file, limit=limit)
                    validate_data(st.session_state.apartments_df)
                mode_text = " (preview: 100 rooms)" if preview_mode else ""
                st.success(f"✓ Loaded {len(st.session_state.apartments_df)} accommodations{mode_text}")
            else:
                mode_text = " (preview mode)" if preview_mode and len(st.session_state.apartments_df) <= 100 else ""
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
            st.session_state.apartments_df = load_accommodation_data(file_path)
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
        preview_rows = min(100, len(st.session_state.apartments_df))
        with st.expander(f"📊 Preview Data ({len(st.session_state.apartments_df)} total rows, showing first {preview_rows})"):
            st.dataframe(st.session_state.apartments_df.head(preview_rows), use_container_width=True)
            if preview_mode:
                st.info("ℹ️ Preview mode is active - 100 rooms loaded. Uncheck 'Preview mode' to load all data.")
    
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
        
        # Check how many need geocoding
        needs_geocoding = 'latitude' not in df.columns or df['latitude'].isna().any()
        
        if needs_geocoding:
            status_text.text("Geocoding apartment addresses (using cache for speed)...")
            
            # Progress callback for Streamlit
            def update_progress(current, total, cached, new):
                progress = current / total if total > 0 else 0
                progress_bar.progress(progress * 0.33)
                stats_text.text(f"Progress: {current}/{total} addresses | {cached} cached | {new} new geocodes")
            
            df = geocode_dataframe(df, progress_callback=update_progress)
            progress_bar.progress(0.33)
            status_text.success("✓ Geocoding complete!")
        else:
            status_text.text("Using existing coordinates...")
            progress_bar.progress(0.33)
        
        # Step 2: Calculate commute times and distances
        st.header("Step 2: Calculating Commute Times & Distances")
        status_text.text("Querying BVG API for commute times...")
        status_text.warning("⚠️ This will take several minutes due to API rate limiting. Please be patient.")
        
        batch_get_commute_info(
            df,
            st.session_state.university_coords[0],
            st.session_state.university_coords[1],
            delay=0.5
        )
        progress_bar.progress(0.66)
        
        # Step 3: Calculate scores (with default weights)
        st.header("Step 3: Calculating Scores")
        status_text.text("Computing composite suitability scores...")
        df = calculate_student_suitability_score(
            df,
            rent_weight=0.35,
            commute_weight=0.40,
            walking_weight=0.15,
            transfers_weight=0.10
        )
        progress_bar.progress(1.0)
        
        # Store processed dataframe (ALL apartments, no filtering)
        st.session_state.processed_df = df
        st.session_state.analysis_complete = True
        
        status_text.success("✓ Analysis complete!")
        st.balloons()
    
    # Display results
    if st.session_state.analysis_complete and st.session_state.processed_df is not None:
        df = st.session_state.processed_df.copy()
        
        # Show all apartments (no filtering)
        if len(df) == 0:
            st.warning("No apartments found. Please check your data or reload.")
            return
        
        st.header("📊 Results")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Apartments", len(df))
        with col2:
            avg_rent = df['rent'].mean() if 'rent' in df.columns and df['rent'].notna().any() else 0
            st.metric("Average Rent", f"€{avg_rent:.0f}" if avg_rent > 0 else "N/A")
        with col3:
            if 'total_commute_minutes' in df.columns and df['total_commute_minutes'].notna().any():
                avg_commute = df['total_commute_minutes'].mean()
                st.metric("Avg Commute Time", f"{avg_commute:.1f} min")
            else:
                st.metric("Avg Commute Time", "N/A")
        with col4:
            if 'suitability_score' in df.columns and df['suitability_score'].notna().any():
                avg_score = df['suitability_score'].mean()
                st.metric("Avg Suitability Score", f"{avg_score:.1f}/100")
            else:
                st.metric("Avg Score", "N/A")
        
        st.markdown("---")
        
        # Show all apartments (sorted by score if available, otherwise by rent)
        st.subheader("🏆 All Apartments")
        
        # Sort by score if available, otherwise by rent
        if 'suitability_score' in df.columns and df['suitability_score'].notna().any():
            df_sorted = df.sort_values('suitability_score', ascending=False).copy()
            df_sorted['rank'] = range(1, len(df_sorted) + 1)
        else:
            df_sorted = df.sort_values('rent' if 'rent' in df.columns else df.columns[0]).copy()
            df_sorted['rank'] = range(1, len(df_sorted) + 1)
        
        # Prepare display columns
        display_cols = []
        if 'rank' in df_sorted.columns:
            display_cols.append('rank')
        if 'suitability_score' in df_sorted.columns:
            display_cols.append('suitability_score')
        if 'provider' in df_sorted.columns:
            display_cols.append('provider')
        if 'address' in df_sorted.columns:
            display_cols.append('address')
        if 'rent' in df_sorted.columns:
            display_cols.append('rent')
        if 'total_commute_minutes' in df_sorted.columns:
            display_cols.append('total_commute_minutes')
        if 'walking_time_minutes' in df_sorted.columns:
            display_cols.append('walking_time_minutes')
        elif 'nearest_stop_distance_m' in df_sorted.columns:
            display_cols.append('nearest_stop_distance_m')
        if 'transfers' in df_sorted.columns:
            display_cols.append('transfers')
        
        display_df = df_sorted[display_cols].copy()
        
        # Format columns
        if 'rent' in display_df.columns:
            display_df['rent'] = display_df['rent'].apply(lambda x: f"€{x:.0f}" if pd.notna(x) and x > 0 else "N/A")
        if 'total_commute_minutes' in display_df.columns:
            display_df['total_commute_minutes'] = display_df['total_commute_minutes'].apply(
                lambda x: f"{x:.1f} min" if pd.notna(x) and x > 0 else "N/A"
            )
        if 'walking_time_minutes' in display_df.columns:
            display_df['walking_time_minutes'] = display_df['walking_time_minutes'].apply(
                lambda x: f"{x:.1f} min" if pd.notna(x) and x > 0 else "N/A"
            )
        if 'nearest_stop_distance_m' in display_df.columns:
            display_df['nearest_stop_distance_m'] = display_df['nearest_stop_distance_m'].apply(
                lambda x: f"{x:.0f} m" if pd.notna(x) and x > 0 else "N/A"
            )
        if 'suitability_score' in display_df.columns:
            display_df['suitability_score'] = display_df['suitability_score'].apply(
                lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
            )
        if 'transfers' in display_df.columns:
            display_df['transfers'] = display_df['transfers'].apply(
                lambda x: f"{int(x)}" if pd.notna(x) else "N/A"
            )
        
        # Rename columns for display
        rename_map = {
            'rank': 'Rank',
            'suitability_score': 'Score',
            'provider': 'Provider',
            'address': 'Address',
            'rent': 'Rent',
            'total_commute_minutes': 'Commute Time',
            'walking_time_minutes': 'Walking Time',
            'nearest_stop_distance_m': 'Walking Distance',
            'transfers': 'Transfers'
        }
        display_df = display_df.rename(columns=rename_map)
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Provider comparison
        if 'provider' in df.columns:
            st.subheader("📈 Provider Comparison")
            provider_stats = compare_providers(df)
            st.dataframe(provider_stats, use_container_width=True, hide_index=True)
        
        # Map visualization - show ALL apartments
        st.subheader("🗺️ Interactive Map - All Apartments")
        map_color_by = st.selectbox(
            "Color apartments by:",
            ['suitability_score', 'rent', 'total_commute_minutes'],
            key="map_color"
        )
        
        # Show all apartments on map (even if no coordinates, try to use addresses)
        # Filter to apartments with coordinates for map
        df_for_map = df_sorted[df_sorted['latitude'].notna() & df_sorted['longitude'].notna()].copy()
        
        if len(df_for_map) > 0:
            m = create_interactive_map(
                df_for_map,
                st.session_state.university_coords,
                st.session_state.university_name,
                color_by=map_color_by if map_color_by in df_for_map.columns else 'rent'
            )
            
            # Display map
            map_html = get_map_html(m)
            components.html(map_html, height=600, scrolling=True)
            
            st.info(f"Showing {len(df_for_map)} apartments on map (out of {len(df)} total)")
        else:
            st.warning("No apartments with coordinates available for map display. Please run geocoding first.")
        
        # Download results
        st.subheader("💾 Download Results")
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download Full Results (CSV)",
            data=csv,
            file_name="housing_analysis_results.csv",
            mime="text/csv"
        )


if __name__ == "__main__":
    main()

