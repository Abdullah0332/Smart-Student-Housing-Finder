import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from pathlib import Path
import json
import traceback
import matplotlib.pyplot as plt

from src.data import load_accommodation_data, validate_data
from src.data import get_university_list, get_university_info, get_university_coords
from src.geo import geocode_dataframe, geocode_university
from src.transport import batch_get_commute_info, batch_get_walkability_info
from src.analysis import calculate_student_suitability_score, analyze_best_areas
from src.analysis import RESEARCH_QUESTIONS, run_all_research_questions
from src.visualization import create_interactive_map, get_map_html
from src.visualization import create_all_visualizations, create_research_question_charts

from config.settings import (
    DEFAULT_ACCOMMODATION_FILE,
    DEFAULT_ENABLED_PROVIDERS,
    SCORING_WEIGHTS,
    UI,
    TRANSPORT_MODES
)

st.set_page_config(
    page_title="Smart Student Housing Finder - Berlin",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .stApp { background-color: #ffffff !important; }
    .main .block-container {
        background-color: #ffffff !important;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
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
        background-color: #f8f9fa !important;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e0e0e0;
    }
    .stButton > button {
        background-color: #1f77b4 !important;
        color: #ffffff !important;
        border: none !important;
    }
    .stButton > button:hover {
        background-color: #1565a0 !important;
    }
    .room-card-clickable {
        background-color: #ffffff !important;
        border: 1px solid #e0e0e0 !important;
    }
    .room-card-clickable:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.15) !important;
        transform: translateY(-2px) !important;
    }
    </style>
""", unsafe_allow_html=True)


def init_session_state():
    defaults = {
        'apartments_df': None,
        'university_coords': None,
        'university_name': None,
        'processed_df': None,
        'analysis_complete': False,
        'current_page': 1,
        'selected_providers': []
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


def main():
    config_col1, config_col2 = st.columns([1, 1])
    
    with config_col1:
        st.subheader("🎓 Select University")
        render_university_selector()
    
    with config_col2:
        st.subheader("📁 Accommodation Data")
        render_data_loader()
    
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run_analysis = st.button(
            "🚀 Run Full Analysis",
            type="primary",
            use_container_width=True,
            help="Start the complete analysis (geocoding + transport API + distance calculation)"
        )
    
    if st.session_state.apartments_df is None:
        st.info("👈 Please load accommodation data above to begin")
        return
    
    if st.session_state.university_coords is None:
        st.warning("⚠️ Please select a university above")
        return
    
    if run_analysis:
        run_full_analysis()
    
    if st.session_state.analysis_complete and st.session_state.processed_df is not None:
        render_results()


def render_university_selector():
    university_list = get_university_list()
    
    default_uni = "Technische Universität Berlin (TU Berlin)"
    try:
        default_idx = university_list.index(default_uni)
    except ValueError:
        default_idx = 0
    
    formatted_options = []
    uni_mapping = {}
    
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
    
    if selected_formatted:
        selected_university = uni_mapping[selected_formatted]
        uni_info = get_university_info(selected_university)
        
        if uni_info:
            st.session_state.university_coords = (uni_info['latitude'], uni_info['longitude'])
            st.session_state.university_name = uni_info['name']


def render_data_loader():
    default_file = DEFAULT_ACCOMMODATION_FILE
    file_exists = Path(default_file).exists()
    
    if file_exists:
        try:
            df_temp = pd.read_csv(default_file, sep=';', encoding='latin-1')
            if 'City' in df_temp.columns:
                berlin_df = df_temp[df_temp['City'].str.contains('Berlin', case=False, na=False)]
                total_records = len(berlin_df)
            else:
                total_records = len(df_temp)
        except:
            total_records = 0
        
        st.markdown(f"""
            <div style="background-color: #f8f9fa; padding: 3px 20px; border-radius: 8px; border: 1px solid #e0e0e0; text-align: center;">
                <h3 style="margin: 0; color: #262730;">Total Records: {total_records:,}</h3>
            </div>
        """, unsafe_allow_html=True)
        
        load_default_data(default_file)
    else:
        st.warning("No default file found.")
        uploaded_file = st.file_uploader(
            "Upload Excel or CSV file",
            type=['csv', 'xlsx', 'xls'],
            help="Upload your accommodation data file"
        )
        if uploaded_file:
            load_uploaded_data(uploaded_file)


def load_default_data(file_path: str):
    try:
        df_temp = pd.read_csv(file_path, sep=';', encoding='latin-1')
        if 'City' in df_temp.columns:
            berlin_df = df_temp[df_temp['City'].str.contains('Berlin', case=False, na=False)]
            if 'Provider' in berlin_df.columns:
                all_providers = sorted(berlin_df['Provider'].dropna().unique().tolist())
            else:
                all_providers = DEFAULT_ENABLED_PROVIDERS
        else:
            all_providers = DEFAULT_ENABLED_PROVIDERS
    except:
        all_providers = DEFAULT_ENABLED_PROVIDERS
    
    selected_providers = [p for p in all_providers if p in DEFAULT_ENABLED_PROVIDERS]
    provider_filter = ', '.join(selected_providers) if selected_providers else None
    
    st.session_state.provider_filter = provider_filter
    
    current_filter = provider_filter or ""
    last_filter = st.session_state.get('last_provider_filter', "")
    
    if current_filter != last_filter:
        st.session_state.apartments_df = None
        st.session_state.processed_df = None
        st.session_state.analysis_complete = False
        st.session_state.last_provider_filter = current_filter
    
    if st.session_state.apartments_df is None:
        with st.spinner("Loading accommodation data..."):
            provider = st.session_state.get('provider_filter', None)
            if provider and provider.strip():
                provider = provider.strip()
            else:
                provider = None
            
            st.session_state.apartments_df = load_accommodation_data(
                file_path, 
                limit=None, 
                provider_filter=provider
            )
            validate_data(st.session_state.apartments_df)
        
        provider_text = f" from selected providers" if provider else ""
        st.success(f"✓ Loaded {len(st.session_state.apartments_df)} accommodations{provider_text}")
    else:
        st.success(f"✓ {len(st.session_state.apartments_df)} accommodations loaded")


def load_uploaded_data(uploaded_file):
    try:
        file_path = f"temp_{uploaded_file.name}"
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.session_state.apartments_df = load_accommodation_data(file_path, provider_filter=None)
        validate_data(st.session_state.apartments_df)
        
        st.success(f"✓ Loaded {len(st.session_state.apartments_df)} accommodations")
    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        st.session_state.apartments_df = None


def run_full_analysis():
    df = st.session_state.apartments_df.copy()
    
    if len(df) == 0:
        st.error("No apartments found. Please check your data or reload.")
        return
    
    st.header("Processing Data")
    progress_bar = st.progress(0)
    status_text = st.empty()
    progress_details = st.empty()
    
    status_text.text("📍 Step 1/2: Geocoding Apartments")
    progress_details.text("Initializing...")
    
    needs_geocoding = True
    if 'latitude' in df.columns and 'longitude' in df.columns:
        has_coords = df['latitude'].notna() & df['longitude'].notna()
        needs_geocoding = not has_coords.all()
    
    if needs_geocoding:
        def update_geocoding_progress(current, total, cached, new):
            progress = (current / total) * 0.5 if total > 0 else 0
            progress_bar.progress(progress)
            successful = cached + new
            progress_details.text(f"📍 Step 1/2: Geocoding | Progress: {current}/{total} addresses | {successful} successful ({cached} cached, {new} new)")
        
        if 'latitude' not in df.columns:
            df['latitude'] = None
        if 'longitude' not in df.columns:
            df['longitude'] = None
        
        df = geocode_dataframe(df, progress_callback=update_geocoding_progress)
        
        geocoded_count = df['latitude'].notna().sum() if 'latitude' in df.columns else 0
        progress_bar.progress(0.5)
        progress_details.text(f"✓ Step 1/2 Complete: {geocoded_count}/{len(df)} rooms geocoded")
    else:
        progress_bar.progress(0.5)
        geocoded_count = df['latitude'].notna().sum() if 'latitude' in df.columns else 0
        progress_details.text(f"✓ Step 1/2 Complete: Using existing coordinates ({geocoded_count} rooms)")
    
    status_text.text("🚇 Step 2/3: Calculating Commute Times & Distances")
    progress_details.text("Using local GTFS data for fast, offline route planning...")
    
    successful_count = 0
    
    def update_commute_progress(idx, total, cached, new):
        nonlocal successful_count
        successful_count = cached + new
        progress = 0.5 + (idx / total) * 0.33 if total > 0 else 0.5
        progress_bar.progress(progress)
        progress_details.text(f"🚇 Step 2/3: Calculating Commute | Progress: {idx}/{total} apartments | {successful_count} successful")
    
    batch_get_commute_info(
        df,
        st.session_state.university_coords[0],
        st.session_state.university_coords[1],
        delay=0.0,
        progress_callback=update_commute_progress
    )
    
    progress_bar.progress(0.66)
    progress_details.text(f"✓ Step 2/3 Complete: Processed {len(df)} apartments using GTFS data")
    
    status_text.text("🚶 Step 3/3: Analyzing Walkability & Mobility")
    progress_details.text("Fetching live OpenStreetMap data for walkability metrics...")
    
    def update_walkability_progress(processed, total):
        progress = 0.66 + (processed / total) * 0.24 if total > 0 else 0.66
        progress_bar.progress(progress)
        progress_details.text(f"🚶 Step 3/3: Walkability Analysis | Progress: {processed}/{total} apartments | Fetching POIs, bike infrastructure...")
    
    batch_get_walkability_info(
        df,
        delay=1.0,  # Rate limiting for Overpass API
        progress_callback=update_walkability_progress
    )
    
    progress_bar.progress(0.9)
    progress_details.text(f"✓ Step 3/3 Complete: Analyzed walkability for {len(df)} apartments")
    
    status_text.text("⭐ Calculating Scores...")
    progress_details.text("Computing composite suitability scores...")
    
    df = calculate_student_suitability_score(
        df,
        rent_weight=SCORING_WEIGHTS['rent'],
        commute_weight=SCORING_WEIGHTS['commute'],
        walking_weight=SCORING_WEIGHTS['walking'],
        transfers_weight=SCORING_WEIGHTS['transfers']
    )
    
    progress_bar.progress(1.0)
    
    st.session_state.processed_df = df.copy()
    st.session_state.analysis_complete = True
    
    if 'provider' in df.columns:
        provider_counts = df['provider'].value_counts()
        status_text.success(f"✓ Analysis complete! Processed {len(df)} rooms from {len(provider_counts)} providers")
    else:
        status_text.success("✓ Analysis complete!")
    
    st.balloons()
    st.rerun()


def render_results():
    df = st.session_state.processed_df.copy()
    
    if len(df) == 0:
        st.warning("No apartments found. Please check your data or reload.")
        return
    
    if 'provider' in df.columns:
        df = render_provider_filter(df)
    
    st.markdown("---")
    df_sorted = render_sorting(df)
    
    df_paginated, start_idx, end_idx, total_pages = paginate_data(df_sorted)
    
    st.subheader("🗺️ Map View")
    render_map(df_paginated)
    
    st.markdown("---")
    st.subheader("🏠 Rooms List")
    render_room_cards(df_paginated)
    
    if len(df_sorted) > UI['rooms_per_page']:
        render_pagination(start_idx, end_idx, total_pages, len(df_sorted))
    
    st.markdown("---")
    render_area_analysis_button()


def render_provider_filter(df: pd.DataFrame) -> pd.DataFrame:
    provider_breakdown = df['provider'].value_counts()
    all_providers = sorted(provider_breakdown.index.tolist())
    
    st.markdown("---")
    st.subheader("🔍 Filter by Platform/Provider")
    
    st.info("📊 Showing apartments with rent between €250 - €1200/month")
    
    if 'selected_providers' not in st.session_state or len(st.session_state.selected_providers) == 0:
        st.session_state.selected_providers = all_providers
    
    valid_selected = [p for p in st.session_state.selected_providers if p in all_providers]
    if len(valid_selected) != len(st.session_state.selected_providers):
        st.session_state.selected_providers = valid_selected if len(valid_selected) > 0 else all_providers
    
    selected_providers = st.multiselect(
        "Select platform(s) to display:",
        options=all_providers,
        default=st.session_state.selected_providers,
        key="provider_filter_multiselect",
        help="Select one or more platforms to filter the room list and map."
    )
    
    if set(selected_providers) != set(st.session_state.selected_providers):
        st.session_state.selected_providers = selected_providers
        st.session_state.current_page = 1
    
    if len(selected_providers) > 0:
        df = df[df['provider'].isin(selected_providers)].copy()
        st.success(f"✓ Showing {len(df)} rooms from {len(selected_providers)} platform(s)")
    else:
        st.info("ℹ️ No providers selected. Showing all rooms.")
    
    return df


def render_sorting(df: pd.DataFrame) -> pd.DataFrame:
    sort_option = st.selectbox(
        "Sort by:",
        ['Rent (Low to High)', 'Rent (High to Low)', 
         'Size (Small to Large)', 'Size (Large to Small)',
         'Commute Time (Short to Long)', 'Commute Time (Long to Short)',
         'Distance (Near to Far)', 'Distance (Far to Near)'],
        key="sort_option"
    )
    
    sort_configs = {
        'Rent (Low to High)': ('rent', True),
        'Rent (High to Low)': ('rent', False),
        'Size (Small to Large)': ('size_sqm', True),
        'Size (Large to Small)': ('size_sqm', False),
        'Distance (Near to Far)': ('nearest_stop_distance_m', True),
        'Distance (Far to Near)': ('nearest_stop_distance_m', False),
        'Commute Time (Short to Long)': ('total_commute_minutes', True),
        'Commute Time (Long to Short)': ('total_commute_minutes', False)
    }
    
    sort_col, ascending = sort_configs.get(sort_option, ('rent', True))
    
    if sort_col in df.columns:
        return df.sort_values(sort_col, ascending=ascending, na_position='last').copy()
    return df.copy()


def paginate_data(df: pd.DataFrame):
    rooms_per_page = UI['rooms_per_page']
    total_rooms = len(df)
    total_pages = max(1, (total_rooms + rooms_per_page - 1) // rooms_per_page)
    
    if st.session_state.current_page > total_pages:
        st.session_state.current_page = 1
    
    start_idx = (st.session_state.current_page - 1) * rooms_per_page
    end_idx = start_idx + rooms_per_page
    df_paginated = df.iloc[start_idx:end_idx].copy()
    
    return df_paginated, start_idx, end_idx, total_pages


def render_map(df: pd.DataFrame):
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        st.error("⚠️ Missing coordinate columns!")
        return
    
    df_for_map = df.copy()
    df_for_map['latitude'] = pd.to_numeric(df_for_map['latitude'], errors='coerce')
    df_for_map['longitude'] = pd.to_numeric(df_for_map['longitude'], errors='coerce')
    
    valid_coords_mask = (
        df_for_map['latitude'].notna() &
        df_for_map['longitude'].notna() &
        (df_for_map['latitude'] != 0) &
        (df_for_map['longitude'] != 0) &
        (df_for_map['latitude'] >= -90) &
        (df_for_map['latitude'] <= 90) &
        (df_for_map['longitude'] >= -180) &
        (df_for_map['longitude'] <= 180)
    )
    
    df_for_map = df_for_map[valid_coords_mask].copy()
    
    if len(df_for_map) > 0:
        try:
            map_color_by = 'suitability_score' if 'suitability_score' in df_for_map.columns else 'rent'
            
            m = create_interactive_map(
                df_for_map,
                st.session_state.university_coords,
                st.session_state.university_name,
                color_by=map_color_by
            )
            
            map_html = get_map_html(m)
            components.html(map_html, height=600, scrolling=True)
            
            st.caption(f"📍 Showing {len(df_for_map)} rooms with valid coordinates + 1 university on map")
        except Exception as e:
            st.error(f"Error creating map: {str(e)}")
    else:
        st.warning("⚠️ No rooms with valid coordinates for map display.")


def render_room_cards(df: pd.DataFrame):
    from streamlit.components.v1 import html as components_html
    
    if 'provider' not in df.columns or df['provider'].isna().all():
        rooms_html = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; padding: 10px 0;">'
        for idx, row in df.iterrows():
            rooms_html += build_room_card_html(idx, row, show_provider=True)
        rooms_html += '</div>'
        rooms_html += get_click_script()
        # Wrap in complete HTML document for components.html
        full_html = f'<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>{rooms_html}</body></html>'
        components_html(full_html, height=600, scrolling=True)
        return
    
    grouped = df.groupby('provider', sort=True)
    rooms_html = ''
    
    provider_colors = [
        {'bg': '#e8f4f8', 'border': '#2980b9', 'text': '#2980b9'},
        {'bg': '#f0f9ff', 'border': '#0ea5e9', 'text': '#0369a1'},
        {'bg': '#fef3c7', 'border': '#f59e0b', 'text': '#d97706'},
        {'bg': '#f3e8ff', 'border': '#9333ea', 'text': '#7e22ce'},
        {'bg': '#d1fae5', 'border': '#10b981', 'text': '#059669'},
        {'bg': '#fee2e2', 'border': '#ef4444', 'text': '#dc2626'},
        {'bg': '#fce7f3', 'border': '#ec4899', 'text': '#db2777'},
        {'bg': '#e0e7ff', 'border': '#6366f1', 'text': '#4f46e5'},
    ]
    
    for provider_idx, (provider_name, provider_df) in enumerate(grouped):
        color_scheme = provider_colors[provider_idx % len(provider_colors)]
        room_count = len(provider_df)
        
        provider_display = escape_html(str(provider_name))
        
        rooms_html += f'''
        <div style="margin-bottom: 40px;">
            <div style="background: linear-gradient(135deg, {color_scheme['bg']} 0%, {color_scheme['bg']}dd 100%); 
                        border-left: 5px solid {color_scheme['border']}; 
                        padding: 15px 20px; 
                        margin-bottom: 20px; 
                        border-radius: 8px;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <h3 style="margin: 0; color: {color_scheme['text']}; font-size: 22px; font-weight: 700; display: flex; align-items: center; gap: 10px;">
                    <span style="background: {color_scheme['border']}; color: white; padding: 5px 12px; border-radius: 20px; font-size: 14px; font-weight: 600;">{room_count}</span>
                    {provider_display}
                </h3>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; padding: 0 10px;">
        '''
        
        for idx, row in provider_df.iterrows():
            rooms_html += build_room_card_html(idx, row, show_provider=False)
        
        rooms_html += '</div></div>'
    
    rooms_html += get_click_script()
    # Wrap in complete HTML document for components.html
    from streamlit.components.v1 import html as components_html
    full_html = f'<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>{rooms_html}</body></html>'
    components_html(full_html, height=600, scrolling=True)


def escape_html(text):
    """Escape HTML special characters to prevent JavaScript syntax errors."""
    if pd.isna(text) or text is None:
        return ''
    text = str(text)
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#x27;'))


def build_room_card_html(idx, row, show_provider: bool = True) -> str:
    has_coords = pd.notna(row.get('latitude')) and pd.notna(row.get('longitude'))
    
    bg_color = '#ffffff' if has_coords else '#fffbf0'
    border_color = '#4a90e2' if has_coords else '#ffc107'
    text_color = '#262730'
    
    provider_name = str(row.get('provider', f'Room #{idx}')) if pd.notna(row.get('provider')) else f'Room #{idx}'
    provider_name = escape_html(provider_name)
    
    address_text = str(row.get('address', '')) if pd.notna(row.get('address')) else ''
    address_text = escape_html(address_text)
    
    room_id = f"room_{idx}"
    
    card_html = f'<div id="{room_id}" class="room-card-clickable" style="border: 2px solid {border_color}; border-radius: 8px; padding: 15px; background-color: {bg_color}; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'
    
    apt_type = row.get('apartment_type')
    room_cat = row.get('room_category')
    size_sqm = row.get('size_sqm')
    
    if show_provider:
        card_html += f'<h4 style="margin-top: 0; color: {text_color}; margin-bottom: 10px; font-weight: 600;">{provider_name}</h4>'
    else:
        apartment_title = ""
        if pd.notna(apt_type) and str(apt_type).strip() and str(apt_type) != 'nan':
            apartment_title = str(apt_type).strip()
        if not apartment_title and pd.notna(room_cat) and str(room_cat).strip() and str(room_cat) != 'nan':
            apartment_title = str(room_cat).strip()
        if not apartment_title:
            apartment_title = f"Apartment #{idx + 1}"
        
        apartment_title = escape_html(apartment_title)
        card_html += f'<h4 style="margin-top: 0; color: {text_color}; margin-bottom: 10px; font-weight: 600;">{apartment_title}</h4>'
    
    details_parts = []
    if pd.notna(apt_type) and str(apt_type).strip() and str(apt_type) != 'nan':
        apt_type_escaped = escape_html(str(apt_type).strip())
        details_parts.append(f"🏠 {apt_type_escaped}")
    if pd.notna(room_cat) and str(room_cat).strip() and str(room_cat) != 'nan':
        room_cat_escaped = escape_html(str(room_cat).strip())
        details_parts.append(f"👤 {room_cat_escaped}")
    if pd.notna(size_sqm) and float(size_sqm) > 0:
        details_parts.append(f"📐 {int(size_sqm)} m²")
    
    if details_parts:
        details_text = " • ".join(details_parts)
        card_html += f'<p style="margin: 5px 0; color: #8e44ad; font-size: 13px; font-weight: 500;">{details_text}</p>'
    
    if address_text:
        card_html += f'<p style="margin: 5px 0; color: #555; font-size: 14px;">📍 {address_text}</p>'
    
    if not has_coords:
        card_html += '<p style="margin: 5px 0; color: #d68910; font-size: 12px; font-weight: 500;">⚠️ No coordinates</p>'
    
    rent_val = row.get('rent')
    if pd.notna(rent_val) and float(rent_val) > 0:
        rent_formatted = f"{float(rent_val):.0f}"
        # Use HTML entity for Euro symbol to avoid encoding issues
        card_html += f'<p style="margin: 8px 0 5px 0; font-size: 18px; font-weight: bold; color: #27ae60;">💰 &euro;{rent_formatted}/month</p>'
    else:
        card_html += '<p style="margin: 8px 0 5px 0; font-size: 14px; color: #999;">💰 Rent: N/A</p>'
    
    card_html += '<hr style="margin: 10px 0; border: none; border-top: 1px solid #e0e0e0;">'
    
    # Commute Time Section
    card_html += '<div style="background: #f5f7fa; padding: 10px; border-radius: 5px; margin-top: 8px; margin-bottom: 10px;">'
    if pd.notna(row.get('total_commute_minutes')) and row['total_commute_minutes'] > 0:
        card_html += f'<p style="margin: 0; font-size: 16px; font-weight: bold; color: #2980b9; background: #e8f4f8; padding: 8px; border-radius: 4px; text-align: center;">⏱️ Commute Time: {row["total_commute_minutes"]:.1f} min</p>'
    else:
        card_html += '<p style="margin: 0; font-size: 14px; color: #999; text-align: center;">⏱️ Commute Time: N/A</p>'
    card_html += '</div>'
    
    # Walkability Score will be shown at the end
    
    # POIs Section
    card_html += '<div style="background: #ffffff; border: 1px solid #e0e0e0; padding: 10px; border-radius: 5px; margin-bottom: 10px;">'
    card_html += '<p style="margin: 0 0 8px 0; font-size: 13px; font-weight: 600; color: #555;">📍 Nearby Amenities (500m):</p>'
    
    poi_items = []
    if pd.notna(row.get('grocery_stores_500m')) and row['grocery_stores_500m'] > 0:
        poi_items.append(f'🛒 Grocery: {int(row["grocery_stores_500m"])}')
    if pd.notna(row.get('cafes_500m')) and row['cafes_500m'] > 0:
        poi_items.append(f'☕ Cafes: {int(row["cafes_500m"])}')
    if pd.notna(row.get('restaurants_500m')) and row['restaurants_500m'] > 0:
        poi_items.append(f'🍽️ Restaurants: {int(row["restaurants_500m"])}')
    if pd.notna(row.get('gyms_500m')) and row['gyms_500m'] > 0:
        poi_items.append(f'💪 Gyms: {int(row["gyms_500m"])}')
    if pd.notna(row.get('pharmacies_500m')) and row['pharmacies_500m'] > 0:
        poi_items.append(f'💊 Pharmacies: {int(row["pharmacies_500m"])}')
    if pd.notna(row.get('banks_500m')) and row['banks_500m'] > 0:
        poi_items.append(f'🏦 Banks: {int(row["banks_500m"])}')
    if pd.notna(row.get('libraries_500m')) and row['libraries_500m'] > 0:
        poi_items.append(f'📚 Libraries: {int(row["libraries_500m"])}')
    if pd.notna(row.get('bars_500m')) and row['bars_500m'] > 0:
        poi_items.append(f'🍺 Bars: {int(row["bars_500m"])}')
    
    if poi_items:
        card_html += '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 5px; font-size: 12px; color: #666;">'
        for item in poi_items[:8]:  # Show max 8 items
            card_html += f'<p style="margin: 2px 0;">{item}</p>'
        card_html += '</div>'
        
        if pd.notna(row.get('total_pois_500m')) and row['total_pois_500m'] > 0:
            card_html += f'<p style="margin: 5px 0 0 0; font-size: 11px; color: #999; font-weight: 500;">Total POIs: {int(row["total_pois_500m"])}</p>'
    else:
        card_html += '<p style="margin: 0; font-size: 12px; color: #999;">No amenities found nearby</p>'
    
    card_html += '</div>'
    
    # Bike Accessibility Section
    bike_score = row.get('bike_accessibility_score')
    if pd.notna(bike_score) and bike_score is not None and bike_score > 0:
        bike_color = '#27ae60' if bike_score >= 50 else '#f39c12' if bike_score >= 30 else '#e74c3c'
        card_html += f'''
        <div style="background: #f0f9ff; border-left: 4px solid {bike_color}; 
                    padding: 10px; border-radius: 5px; margin-bottom: 10px;">
            <p style="margin: 0 0 5px 0; font-size: 13px; font-weight: 600; color: #555;">🚴 Bike Accessibility:</p>
            <p style="margin: 0; font-size: 14px; color: {bike_color}; font-weight: bold;">
                Score: {int(bike_score)}/100
            </p>
        '''
        
        bike_details = []
        if pd.notna(row.get('nearest_bike_lane_m')) and row['nearest_bike_lane_m'] is not None:
            bike_details.append(f'Bike lane: {int(row["nearest_bike_lane_m"])}m')
        if pd.notna(row.get('nearest_bike_share_m')) and row['nearest_bike_share_m'] is not None:
            bike_details.append(f'Bike share: {int(row["nearest_bike_share_m"])}m')
        
        if bike_details:
            card_html += f'<p style="margin: 5px 0 0 0; font-size: 11px; color: #666;">{" • ".join(bike_details)}</p>'
        
        card_html += '</div>'
    
    # Nearest Amenities Section
    nearest_items = []
    if pd.notna(row.get('nearest_grocery_m')) and row['nearest_grocery_m'] is not None:
        nearest_items.append(f'🛒 Grocery: {int(row["nearest_grocery_m"])}m')
    if pd.notna(row.get('nearest_cafe_m')) and row['nearest_cafe_m'] is not None:
        nearest_items.append(f'☕ Cafe: {int(row["nearest_cafe_m"])}m')
    if pd.notna(row.get('nearest_gym_m')) and row['nearest_gym_m'] is not None:
        nearest_items.append(f'💪 Gym: {int(row["nearest_gym_m"])}m')
    
    if nearest_items:
        card_html += '<div style="background: #fff9e6; padding: 8px; border-radius: 5px; margin-bottom: 10px;">'
        card_html += '<p style="margin: 0 0 5px 0; font-size: 12px; font-weight: 600; color: #555;">📍 Nearest:</p>'
        card_html += '<div style="font-size: 11px; color: #666;">'
        for item in nearest_items:
            card_html += f'<p style="margin: 2px 0;">{item}</p>'
        card_html += '</div></div>'
    
    # Scores at the end
    card_html += '<hr style="margin: 15px 0; border: none; border-top: 2px solid #e0e0e0;">'
    
    # Walkability Score
    walkability_score = row.get('walkability_score')
    if pd.notna(walkability_score) and walkability_score is not None:
        score_color = '#27ae60' if walkability_score >= 70 else '#f39c12' if walkability_score >= 50 else '#e74c3c'
        card_html += f'''
        <div style="background: linear-gradient(135deg, {score_color}15 0%, {score_color}05 100%); 
                    border-left: 4px solid {score_color}; 
                    padding: 10px; 
                    border-radius: 5px; 
                    margin-bottom: 10px;">
            <p style="margin: 0; font-size: 15px; font-weight: bold; color: {score_color};">
                🚶 Walkability Score: <span style="font-size: 18px;">{int(walkability_score)}/100</span>
            </p>
        </div>
        '''
    
    # Suitability Score
    suitability_score = row.get('suitability_score')
    if pd.notna(suitability_score) and suitability_score is not None:
        score_color = '#27ae60' if suitability_score >= 70 else '#f39c12' if suitability_score >= 50 else '#e74c3c'
        card_html += f'''
        <div style="background: linear-gradient(135deg, {score_color}15 0%, {score_color}05 100%); 
                    border-left: 4px solid {score_color}; 
                    padding: 10px; 
                    border-radius: 5px; 
                    margin-bottom: 10px;">
            <p style="margin: 0; font-size: 15px; font-weight: bold; color: {score_color};">
                ⭐ Suitability Score: <span style="font-size: 18px;">{int(suitability_score)}/100</span>
            </p>
        </div>
        '''
    
    card_html += '</div>'
    
    return card_html


def get_click_script() -> str:
    return """
    <script>
    document.addEventListener('click', function(event) {
        const card = event.target.closest('.room-card-clickable');
        if (card) {
            const roomId = card.id;
            card.style.border = '3px solid #007bff';
            card.style.boxShadow = '0 4px 12px rgba(0,123,255,0.3)';
            card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });
    </script>
    """


def render_pagination(start_idx: int, end_idx: int, total_pages: int, total_rooms: int):
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
            key="page_input"
        )
        if page_input != st.session_state.current_page:
            st.session_state.current_page = page_input
            st.rerun()
    
    with pagination_col3:
        if st.button("Next ▶", disabled=(st.session_state.current_page == total_pages), key="next_page"):
            st.session_state.current_page = min(total_pages, st.session_state.current_page + 1)
            st.rerun()
    
    st.caption(f"Showing rooms {start_idx + 1}-{min(end_idx, total_rooms)} of {total_rooms}")


def render_area_analysis_button():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        show_area_analysis = st.button(
            "🏆 Analyze Best Areas in Berlin",
            type="secondary",
            use_container_width=True,
            help="View district-level analysis of transport accessibility and room availability"
        )
    
    if show_area_analysis:
        render_area_analysis()


def render_area_analysis():
    with st.expander("🏆 Best Areas in Berlin Analysis", expanded=True):
        st.header("📊 District-Level Analysis")
        st.markdown("""
        This analysis identifies the best areas (districts) in Berlin for students based on:
        - **Transport Accessibility**: Commute time to university, walking distance to stops
        - **Room Availability**: Number of available rooms and providers
        - **Affordability**: Average rent per district
        - **Composite Score**: Combined metric for overall student suitability
        """)
        
        with st.spinner("Analyzing districts..."):
            analysis_results = analyze_best_areas(st.session_state.processed_df)
            
            ranked_areas = analysis_results['ranked_areas']
            top_5_areas = analysis_results['top_5_areas']
            
            if len(ranked_areas) == 0:
                st.error("No district data available.")
                return
            
            st.subheader("🥇 Top 5 Best Areas for Students")
            if top_5_areas:
                top5_cols = st.columns(5)
                medals = ["🥇", "🥈", "🥉", "4.", "5."]
                colors = [("#FFD700", "#FFA500"), ("#C0C0C0", "#808080"), ("#CD7F32", "#8B4513"), ("#E8F4F8", "#3498db"), ("#E8F4F8", "#3498db")]
                
                for i, (col, district) in enumerate(zip(top5_cols, top_5_areas)):
                    district_data = ranked_areas[ranked_areas['district'] == district].iloc[0]
                    bg_color, border_color = colors[i]
                    
                    with col:
                        st.markdown(f"""
                        <div style="background-color: {bg_color}; border: 3px solid {border_color}; 
                        border-radius: 10px; padding: 15px; text-align: center; margin-bottom: 10px;">
                        <h3 style="margin: 5px 0; color: #262730;">{medals[i]}</h3>
                        <h4 style="margin: 10px 0; color: #262730; font-weight: bold;">{district}</h4>
                        <p style="margin: 5px 0; font-size: 14px; color: #262730;"><strong>Score:</strong> {district_data['student_area_score']:.3f}</p>
                        <p style="margin: 5px 0; font-size: 12px; color: #555;">🏠 {int(district_data.get('total_rooms', 0))} rooms</p>
                        <p style="margin: 5px 0; font-size: 12px; color: #555;">💰 €{district_data.get('avg_rent', 0):.0f}/mo</p>
                        <p style="margin: 5px 0; font-size: 12px; color: #555;">🚇 {district_data.get('avg_commute_minutes', 0):.1f} min</p>
                        </div>
                        """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.subheader("📋 Complete District Rankings")
            
            display_df = ranked_areas[[
                'district', 'student_area_score', 'total_rooms',
                'avg_rent', 'avg_commute_minutes', 'avg_walking_distance_m'
            ]].copy()
            display_df.columns = [
                'District', 'Student Area Score', 'Total Rooms',
                'Avg Rent (€)', 'Avg Commute (min)', 'Avg Walking (m)'
            ]
            display_df = display_df.round({
                'Student Area Score': 3,
                'Avg Rent (€)': 0,
                'Avg Commute (min)': 1,
                'Avg Walking (m)': 0
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("📈 Visualizations")
            
            try:
                visuals = create_all_visualizations(analysis_results)
                
                col1, col2 = st.columns(2)
                with col1:
                    if visuals.get('score_chart'):
                        st.pyplot(visuals['score_chart'])
                    if visuals.get('histogram'):
                        st.pyplot(visuals['histogram'])
                
                with col2:
                    if visuals.get('rooms_chart'):
                        st.pyplot(visuals['rooms_chart'])
                    if visuals.get('scatter_plot'):
                        st.pyplot(visuals['scatter_plot'])
                
                try:
                    rq_results = run_all_research_questions(st.session_state.processed_df)
                    rq_charts = create_research_question_charts(rq_results, st.session_state.processed_df)
                    
                    if rq_charts:
                        st.markdown("---")
                        st.subheader("📊 Research Questions Analysis")
                        
                        # Original Research Questions
                        st.markdown("### Original Research Questions")
                        rq_col1, rq_col2 = st.columns(2)
                        with rq_col1:
                            if 'rq1_scatter' in rq_charts:
                                st.pyplot(rq_charts['rq1_scatter'])
                            if 'rq4_bar' in rq_charts:
                                st.pyplot(rq_charts['rq4_bar'])
                        with rq_col2:
                            if 'rq3_scatter' in rq_charts:
                                st.pyplot(rq_charts['rq3_scatter'])
                            if 'rq5_bar' in rq_charts:
                                st.pyplot(rq_charts['rq5_bar'])
                        
                        # Walkability & Mobility Research Questions
                        if any(key.startswith('rq6') or key.startswith('rq7') or key.startswith('rq8') or key.startswith('rq9') or key.startswith('rq10') for key in rq_charts.keys()):
                            st.markdown("---")
                            st.markdown("### Walkability & Mobility Research Questions")
                            
                            rq_walk_col1, rq_walk_col2 = st.columns(2)
                            with rq_walk_col1:
                                if 'rq6_scatter' in rq_charts:
                                    st.pyplot(rq_charts['rq6_scatter'])
                                if 'rq8_scatter' in rq_charts:
                                    st.pyplot(rq_charts['rq8_scatter'])
                                if 'rq10_bar' in rq_charts:
                                    st.pyplot(rq_charts['rq10_bar'])
                            with rq_walk_col2:
                                if 'rq7_scatter' in rq_charts:
                                    st.pyplot(rq_charts['rq7_scatter'])
                                if 'rq9_scatter' in rq_charts:
                                    st.pyplot(rq_charts['rq9_scatter'])
                        
                        # Display research question results
                        st.markdown("---")
                        st.markdown("### Research Question Results")
                        
                        for rq_key, rq_result in rq_results.items():
                            if rq_result.get('status') == 'success':
                                with st.expander(f"📋 {rq_key.replace('_', ' ').title()}"):
                                    if 'interpretation' in rq_result:
                                        st.write(rq_result['interpretation'])
                                    if 'correlation_coefficient' in rq_result:
                                        st.metric("Correlation", f"{rq_result['correlation_coefficient']:.3f}")
                                        st.metric("P-value", f"{rq_result['p_value']:.4f}")
                                        st.metric("Significant", "Yes" if rq_result.get('statistically_significant') else "No")
                                    if 'r_squared' in rq_result:
                                        st.metric("R²", f"{rq_result['r_squared']:.3f}")
                                        st.metric("P-value", f"{rq_result['p_value']:.4f}")
                                    if 'top_5_districts' in rq_result:
                                        st.dataframe(pd.DataFrame(rq_result['top_5_districts']))
                                    if 'gini_coefficient' in rq_result:
                                        st.metric("Gini Coefficient", f"{rq_result['gini_coefficient']:.3f}")
                                        st.metric("Equity Level", rq_result.get('equity_level', 'N/A'))
                except Exception as e:
                    st.warning(f"Could not generate research question charts: {str(e)}")
                
                st.markdown("---")
                st.subheader("🗺️ District Map")
                if 'map' in visuals and visuals['map'] is not None:
                    map_html = get_map_html(visuals['map'])
                    components.html(map_html, height=600, scrolling=False)
                
            except Exception as e:
                st.error(f"Error creating visualizations: {str(e)}")


if __name__ == "__main__":
    main()
