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
    
    st.markdown("---")
    
    # Main Configuration Section
    st.header("⚙️ Configuration")
    
    # Data Section
    st.subheader("📁 Accommodation Data")
    
    col1, col2 = st.columns([2, 1])
        st.subheader("📁 Accommodation Data")
        
        # Check for existing file in directory
        default_file = "Accomodations.csv"
        file_exists = Path(default_file).exists()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if file_exists:
                st.info(f"📁 Found: `{default_file}`")
                use_default = st.checkbox("Use existing file", value=True, key="use_default_file")
                # Preview mode option
                preview_mode = st.checkbox("Preview mode (100 rooms)", value=True, key="preview_mode", 
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
                    mode_text = " (preview mode)" if preview_mode and len(st.session_state.apartments_df) <= 20 else ""
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
        
        # Show preview if data is loaded
        if st.session_state.apartments_df is not None:
            preview_rows = min(100, len(st.session_state.apartments_df))
            with st.expander(f"📊 Preview Data ({len(st.session_state.apartments_df)} total rows, showing first {preview_rows})"):
                st.dataframe(st.session_state.apartments_df.head(preview_rows), use_container_width=True)
                if preview_mode:
                    st.info("ℹ️ Preview mode is active - 100 rooms loaded. Uncheck 'Preview mode' to load all data.")
    
    with tab2:
        st.subheader("2. Select University")
        
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
                # Display university information in columns
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**University Information:**")
                    st.markdown(f"**Name:** {uni_info['name']}")
                    st.markdown(f"**Type:** {uni_info['type']}")
                    st.markdown(f"**Abbreviation:** {uni_info['abbreviation']}")
                
                with col2:
                    st.markdown("**Location Details:**")
                    st.markdown(f"**Address:** {uni_info['address']}")
                    st.markdown(f"**Coordinates:** {uni_info['latitude']:.6f}, {uni_info['longitude']:.6f}")
                
                # Set university coordinates (pre-stored, no geocoding needed)
                st.session_state.university_coords = (uni_info['latitude'], uni_info['longitude'])
                st.session_state.university_name = uni_info['name']
                
                st.success(f"✓ {uni_info['name']} selected")
        
        # Option to use custom address
        with st.expander("🌍 Or enter custom university address"):
            custom_address = st.text_input(
                "Custom university name or address",
                help="If your university is not in the list, enter it here"
            )
            
            if st.button("📍 Geocode Custom University", type="secondary"):
                if custom_address:
                    with st.spinner("Geocoding university..."):
                        coords = geocode_university(custom_address)
                        if coords:
                            st.session_state.university_coords = coords
                            st.session_state.university_name = custom_address
                            st.success(f"✓ University geocoded: {coords[0]:.6f}, {coords[1]:.6f}")
                        else:
                            st.error("Could not geocode university. Please try a different address.")
                else:
                    st.warning("Please enter a university name or address")
    
    with tab3:
        st.subheader("3. Analysis Filters")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Get max rent from data if available, otherwise use default
            if st.session_state.apartments_df is not None and 'rent' in st.session_state.apartments_df.columns:
                data_max_rent = st.session_state.apartments_df['rent'].max()
                if pd.notna(data_max_rent) and data_max_rent > 0:
                    default_max_rent = int(max(data_max_rent * 1.2, 2500))  # 20% above max or 2500 minimum
                    slider_max = int(max(data_max_rent * 1.5, 5000))
                else:
                    default_max_rent = 3000
                    slider_max = 5000
            else:
                default_max_rent = 3000
                slider_max = 5000
            
            # Use session state to persist slider value
            if 'max_rent_filter' not in st.session_state:
                st.session_state.max_rent_filter = default_max_rent
            
            max_rent = st.slider(
                "Max Rent (€)",
                min_value=0,
                max_value=slider_max,
                value=st.session_state.max_rent_filter,
                step=50,
                help="Filter apartments by maximum rent",
                key="max_rent_slider"
            )
            st.session_state.max_rent_filter = max_rent
            st.metric("Max Rent", f"€{max_rent}")
        
        with col2:
            max_commute = st.slider(
                "Max Commute Time (minutes)",
                min_value=0,
                max_value=180,
                value=120,
                step=5,
                help="Filter by maximum commute time"
            )
            st.metric("Max Commute", f"{max_commute} min")
        
        with col3:
            max_walking = st.slider(
                "Max Walking Distance (meters)",
                min_value=0,
                max_value=2000,
                value=1000,
                step=100,
                help="Filter by maximum walking distance to transit"
            )
            st.metric("Max Walking", f"{max_walking} m")
    
    with tab4:
        st.subheader("4. Scoring Weights")
        st.markdown("Adjust the importance of each factor in the suitability score calculation.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            rent_weight = st.slider(
                "💰 Affordability Weight",
                0.0, 1.0, 0.35, 0.05,
                help="How important is low rent?"
            )
            commute_weight = st.slider(
                "🚇 Commute Time Weight",
                0.0, 1.0, 0.40, 0.05,
                help="How important is short commute time?"
            )
        
        with col2:
            walking_weight = st.slider(
                "🚶 Walking Distance Weight",
                0.0, 1.0, 0.15, 0.05,
                help="How important is short walking distance?"
            )
            transfers_weight = st.slider(
                "🔄 Transfers Weight",
                0.0, 1.0, 0.10, 0.05,
                help="How important are fewer transfers?"
            )
        
        # Normalize weights
        total_weight = rent_weight + commute_weight + walking_weight + transfers_weight
        if total_weight > 0:
            rent_weight /= total_weight
            commute_weight /= total_weight
            walking_weight /= total_weight
            transfers_weight /= total_weight
        
        # Show normalized weights
        st.markdown("**Normalized Weights:**")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Affordability", f"{rent_weight*100:.1f}%")
        with col2:
            st.metric("Commute", f"{commute_weight*100:.1f}%")
        with col3:
            st.metric("Walking", f"{walking_weight*100:.1f}%")
        with col4:
            st.metric("Transfers", f"{transfers_weight*100:.1f}%")
    
    # Run analysis button - prominent on main screen
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run_analysis = st.button(
            "🚀 Run Full Analysis",
            type="primary",
            use_container_width=True,
            help="Start the complete analysis (geocoding + transport API + scoring)"
        )
    
    # Main content area
    if st.session_state.apartments_df is None:
        st.info("👈 Please load accommodation data in the **Data** tab above to begin")
        st.markdown("""
        ### About This Application
        
        This **Urban Technology** project helps students find the best accommodation in Berlin by analyzing:
        
        1. **Affordability** - Rent prices
        2. **Commute Time** - Door-to-door travel time using BVG public transport
        3. **Walking Distance** - Distance to nearest transit stop
        4. **Transport Accessibility** - Number of transfers and transport modes
        
        The system uses:
        - **BVG Transport API** for realistic journey planning
        - **OpenStreetMap/Nominatim** for geocoding
        - **Geospatial analysis** for distance calculations
        - **Multi-criteria decision analysis** for ranking
        
        This demonstrates how urban mobility data can inform housing decisions and reveal
        spatial patterns in transport accessibility.
        """)
        return
    
    if st.session_state.university_coords is None:
        st.warning("⚠️ Please select a university in the **University** tab above")
        return
    
    # Run analysis
    if run_analysis:
        df = st.session_state.apartments_df.copy()
        
        # Filter by max rent (only if filter is reasonable)
        if 'rent' in df.columns and max_rent > 0:
            original_count = len(df)
            df_filtered = df[df['rent'] <= max_rent].copy()
            filtered_count = len(df_filtered)
            
            # Only apply filter if it doesn't remove all apartments
            if filtered_count > 0:
                df = df_filtered
            elif original_count > 0:
                # Filter removed all apartments, show warning but keep original data
                st.warning(f"⚠️ Max rent filter (€{max_rent}) would remove all apartments. Showing all {original_count} apartments without rent filter.")
                # Keep original df (no filtering)
            # If filtered_count == 0 and original_count == 0, df is already empty
        
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
        
        # Step 2: Calculate commute times
        st.header("Step 2: Calculating Commute Times")
        status_text.text("Querying BVG API for commute times...")
        status_text.warning("⚠️ This will take several minutes due to API rate limiting. Please be patient.")
        
        batch_get_commute_info(
            df,
            st.session_state.university_coords[0],
            st.session_state.university_coords[1],
            delay=0.5
        )
        progress_bar.progress(0.66)
        
        # Filter by commute and walking distance
        if 'total_commute_minutes' in df.columns:
            df = df[df['total_commute_minutes'] <= max_commute]
        
        if 'nearest_stop_distance_m' in df.columns:
            df = df[df['nearest_stop_distance_m'] <= max_walking]
        
        # Step 3: Calculate scores
        st.header("Step 3: Calculating Suitability Scores")
        status_text.text("Computing composite suitability scores...")
        df = calculate_student_suitability_score(
            df,
            rent_weight=rent_weight,
            commute_weight=commute_weight,
            walking_weight=walking_weight,
            transfers_weight=transfers_weight
        )
        progress_bar.progress(1.0)
        
        # Store processed dataframe
        st.session_state.processed_df = df
        st.session_state.analysis_complete = True
        
        status_text.success("✓ Analysis complete!")
        st.balloons()
    
    # Display results
    if st.session_state.analysis_complete and st.session_state.processed_df is not None:
        df = st.session_state.processed_df.copy()
        
        # Show all apartments, even if they don't have complete data
        if len(df) == 0:
            st.warning("No apartments found. Please adjust filters.")
            return
        
        # Show info if some apartments don't have scores
        apartments_with_scores = df['suitability_score'].notna().sum() if 'suitability_score' in df.columns else 0
        if apartments_with_scores < len(df):
            st.info(f"Showing {len(df)} apartments ({apartments_with_scores} with complete scores, {len(df) - apartments_with_scores} with partial data)")
        
        st.header("📊 Results")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Apartments", len(df))
        with col2:
            avg_rent = df['rent'].mean() if 'rent' in df.columns else 0
            st.metric("Average Rent", f"€{avg_rent:.0f}")
        with col3:
            avg_commute = df['total_commute_minutes'].mean() if 'total_commute_minutes' in df.columns else 0
            st.metric("Avg Commute Time", f"{avg_commute:.1f} min")
        with col4:
            avg_score = df['suitability_score'].mean()
            st.metric("Avg Suitability Score", f"{avg_score:.1f}/100")
        
        st.markdown("---")
        
        # Top apartments - show all if less than 10, otherwise top 10
        st.subheader("🏆 Recommended Apartments")
        
        # Sort by score if available, otherwise by rent
        if 'suitability_score' in df.columns and df['suitability_score'].notna().any():
            # Show top apartments with scores
            df_with_scores = df[df['suitability_score'].notna()].copy()
            if len(df_with_scores) > 0:
                top_apartments = rank_apartments(df_with_scores, top_n=min(10, len(df_with_scores)))
            else:
                # No scores, just show first 10
                top_apartments = df.head(10).copy()
                top_apartments['rank'] = range(1, len(top_apartments) + 1)
        else:
            # No scores available, sort by rent and show top 10
            df_sorted = df.sort_values('rent' if 'rent' in df.columns else df.columns[0]).head(10).copy()
            df_sorted['rank'] = range(1, len(df_sorted) + 1)
            top_apartments = df_sorted
        
        # Prepare display columns
        display_cols = []
        if 'rank' in top_apartments.columns:
            display_cols.append('rank')
        if 'suitability_score' in top_apartments.columns:
            display_cols.append('suitability_score')
        if 'provider' in top_apartments.columns:
            display_cols.append('provider')
        if 'address' in top_apartments.columns:
            display_cols.append('address')
        if 'rent' in top_apartments.columns:
            display_cols.append('rent')
        if 'total_commute_minutes' in top_apartments.columns:
            display_cols.append('total_commute_minutes')
        if 'walking_time_minutes' in top_apartments.columns:
            display_cols.append('walking_time_minutes')
        elif 'nearest_stop_distance_m' in top_apartments.columns:
            display_cols.append('nearest_stop_distance_m')
        if 'transfers' in top_apartments.columns:
            display_cols.append('transfers')
        
        display_df = top_apartments[display_cols].copy()
        
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
        display_df = display_df.rename(columns={
            'rank': 'Rank',
            'suitability_score': 'Score',
            'provider': 'Provider',
            'address': 'Address',
            'rent': 'Rent',
            'total_commute_minutes': 'Commute Time',
            'walking_time_minutes': 'Walking Time',
            'transfers': 'Transfers'
        })
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Provider comparison
        st.subheader("📈 Provider Comparison")
        if 'provider' in df.columns:
            provider_stats = compare_providers(df)
            st.dataframe(provider_stats, use_container_width=True, hide_index=True)
        
        # Map visualization
        st.subheader("🗺️ Interactive Map")
        map_color_by = st.selectbox(
            "Color apartments by:",
            ['suitability_score', 'rent', 'total_commute_minutes'],
            key="map_color"
        )
        
        m = create_interactive_map(
            top_apartments,
            st.session_state.university_coords,
            st.session_state.university_name,
            color_by=map_color_by
        )
        
        # Display map
        map_html = get_map_html(m)
        components.html(map_html, height=600, scrolling=True)
        
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

