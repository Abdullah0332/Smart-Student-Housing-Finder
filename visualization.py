"""
Visualization Module
====================

Creates interactive maps and visualizations using Folium. Visualizes apartment
locations, transport stops, routes, and accessibility metrics on a map.

Urban Technology Relevance:
- Geospatial visualization enables spatial understanding of urban patterns
- Map-based interfaces help users understand location context
- Visualizing transport accessibility reveals spatial equity patterns
- Interactive maps are essential tools for urban planning and decision-making
"""

import folium
from folium import plugins
import pandas as pd
import numpy as np
from typing import Tuple, Optional, List
import json


def create_base_map(center: Tuple[float, float], zoom_start: int = 12) -> folium.Map:
    """
    Create a base Folium map centered on Berlin.
    
    Parameters:
    -----------
    center : Tuple[float, float]
        (latitude, longitude) for map center
    zoom_start : int
        Initial zoom level
    
    Returns:
    --------
    folium.Map
        Base map object
    """
    m = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles='OpenStreetMap'
    )
    
    # Add alternative tile layers
    folium.TileLayer('CartoDB positron').add_to(m)
    folium.TileLayer('CartoDB dark_matter').add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    return m


def add_apartments_to_map(
    m: folium.Map,
    df: pd.DataFrame,
    color_by: str = 'suitability_score',
    show_popup: bool = True
) -> folium.Map:
    """
    Add apartment markers to the map.
    
    Parameters:
    -----------
    m : folium.Map
        Map object
    df : pd.DataFrame
        Dataframe with 'latitude', 'longitude', and other columns
    color_by : str
        Column name to use for coloring markers (default: 'suitability_score')
    show_popup : bool
        Whether to show popup information
    
    Returns:
    --------
    folium.Map
        Map with apartment markers added
    """
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        raise ValueError("Dataframe must have 'latitude' and 'longitude' columns")
    
    # Create color scale if needed
    if color_by in df.columns and df[color_by].notna().any():
        if color_by == 'suitability_score':
            # Green (high) to Red (low)
            colormap = folium.LinearColormap(
                colors=['red', 'orange', 'yellow', 'green'],
                vmin=df[color_by].min(),
                vmax=df[color_by].max()
            )
        elif color_by == 'rent':
            # Blue (low) to Red (high)
            colormap = folium.LinearColormap(
                colors=['blue', 'cyan', 'yellow', 'red'],
                vmin=df[color_by].min(),
                vmax=df[color_by].max()
            )
        elif color_by == 'total_commute_minutes':
            # Green (short) to Red (long)
            colormap = folium.LinearColormap(
                colors=['green', 'yellow', 'orange', 'red'],
                vmin=df[color_by].min(),
                vmax=df[color_by].max()
            )
        else:
            colormap = None
    
    # Debug: Check if we have valid coordinates
    valid_coords = df[df['latitude'].notna() & df['longitude'].notna()]
    if len(valid_coords) == 0:
        print("Warning: No apartments with valid coordinates to display on map")
    else:
        colormap = None
    
    # Add markers
    markers_added = 0
    skipped_count = 0
    for idx, row in df.iterrows():
        if pd.isna(row['latitude']) or pd.isna(row['longitude']):
            skipped_count += 1
            continue
        
        # Validate coordinates - only skip if clearly invalid
        lat, lon = row['latitude'], row['longitude']
        # Only skip if coordinates are clearly wrong (0,0 or NaN)
        if (lat == 0 and lon == 0) or pd.isna(lat) or pd.isna(lon):
            skipped_count += 1
            continue  # Skip invalid coordinates
        # Don't filter by Berlin bounds - show all valid coordinates
        # (Some addresses might geocode slightly outside strict bounds)
        
        # Debug: Log if this is "Urban Club"
        provider_name = row.get('provider', '') if 'provider' in df.columns else ''
        if 'urban club' in str(provider_name).lower():
            print(f"Adding Urban Club marker: {provider_name} at ({lat}, {lon})")
        
        # Determine marker color
        if colormap and color_by in df.columns and pd.notna(row.get(color_by)):
            try:
                color = colormap(row[color_by])
            except:
                color = 'blue'
        else:
            color = 'blue'
        
        # Create popup text with detailed information
        popup_text = "<div style='font-family: Arial, sans-serif; max-width: 300px;'>"
        
        # Room/Provider name
        if 'provider' in df.columns and pd.notna(row.get('provider')):
            popup_text += f"<h3 style='margin: 0 0 10px 0; color: #2c3e50;'>{row['provider']}</h3>"
        else:
            popup_text += f"<h3 style='margin: 0 0 10px 0; color: #2c3e50;'>Room #{idx}</h3>"
        
        # Address
        if 'address' in df.columns and pd.notna(row.get('address')):
            popup_text += f"<p style='margin: 0 0 10px 0; color: #7f8c8d; font-size: 12px;'><strong>📍 Address:</strong><br>{row['address']}</p>"
        
        # Rent
        if 'rent' in df.columns and pd.notna(row.get('rent')):
            popup_text += f"<p style='margin: 0 0 10px 0;'><strong>💰 Rent:</strong> €{row['rent']:.0f}</p>"
        
        # Nearest Platform/Stop
        if 'nearest_stop_name' in df.columns and pd.notna(row.get('nearest_stop_name')):
            stop_name = row['nearest_stop_name']
            distance = row.get('nearest_stop_distance_m', 0)
            popup_text += f"<p style='margin: 0 0 10px 0;'><strong>🚉 Nearest Stop:</strong><br>{stop_name}<br><small>Distance: {distance:.0f}m</small></p>"
        
        # Walking time
        if 'walking_time_minutes' in df.columns and pd.notna(row.get('walking_time_minutes')):
            walking_time = row['walking_time_minutes']
            popup_text += f"<p style='margin: 0 0 10px 0;'><strong>🚶 Walking:</strong> {walking_time:.1f} min</p>"
        
        # Transport details
        if 'route_details' in df.columns and pd.notna(row.get('route_details')):
            import json
            try:
                route_details = json.loads(row['route_details'])
                if route_details:
                    popup_text += "<p style='margin: 0 0 10px 0;'><strong>🚇 Transport Routes:</strong><br>"
                    for i, route in enumerate(route_details):
                        mode = route.get('mode', 'unknown')
                        name = route.get('name', '')
                        from_stop = route.get('from', '')
                        to_stop = route.get('to', '')
                        
                        # Map mode to display name and color
                        mode_map = {
                            'subway': ('U-Bahn', '#0066cc'),
                            'suburban': ('S-Bahn', '#00cc00'),
                            'bus': ('Bus', '#ff6600'),
                            'tram': ('Tram', '#cc0000'),
                            'ferry': ('Ferry', '#0066ff')
                        }
                        mode_display, mode_color = mode_map.get(mode.lower(), (mode.title(), '#3498db'))
                        
                        if name:
                            popup_text += f"<span style='display: inline-block; background: {mode_color}; color: white; padding: 3px 8px; border-radius: 4px; margin: 2px 0; font-size: 11px; font-weight: bold;'>{mode_display} {name}</span>"
                            if from_stop and to_stop:
                                popup_text += f"<br><small style='color: #7f8c8d; font-size: 10px;'>{from_stop} → {to_stop}</small>"
                            popup_text += "<br>"
                        else:
                            popup_text += f"<span style='display: inline-block; background: {mode_color}; color: white; padding: 3px 8px; border-radius: 4px; margin: 2px 0; font-size: 11px; font-weight: bold;'>{mode_display}</span><br>"
                    popup_text += "</p>"
            except Exception as e:
                # If route_details can't be parsed, try to show transport_modes
                if 'transport_modes' in df.columns and pd.notna(row.get('transport_modes')):
                    modes = str(row['transport_modes']).split(', ')
                    popup_text += "<p style='margin: 0 0 10px 0;'><strong>🚇 Transport:</strong> "
                    popup_text += ", ".join(modes)
                    popup_text += "</p>"
        
        # Transit time
        if 'transit_time_minutes' in df.columns and pd.notna(row.get('transit_time_minutes')):
            transit_time = row['transit_time_minutes']
            popup_text += f"<p style='margin: 0 0 10px 0;'><strong>🚊 Transit:</strong> {transit_time:.1f} min</p>"
        
        # Total commute
        if 'total_commute_minutes' in df.columns and pd.notna(row.get('total_commute_minutes')):
            total_commute = row['total_commute_minutes']
            popup_text += f"<p style='margin: 0 0 10px 0; background: #ecf0f1; padding: 5px; border-radius: 3px;'><strong>⏱️ Total Commute:</strong> {total_commute:.1f} min</p>"
        
        # Transfers
        if 'transfers' in df.columns and pd.notna(row.get('transfers')):
            transfers = int(row['transfers'])
            popup_text += f"<p style='margin: 0 0 10px 0;'><strong>🔄 Transfers:</strong> {transfers}</p>"
        
        # Suitability score
        if 'suitability_score' in df.columns and pd.notna(row.get('suitability_score')):
            score = row['suitability_score']
            score_color = '#27ae60' if score >= 70 else '#f39c12' if score >= 50 else '#e74c3c'
            popup_text += f"<p style='margin: 0;'><strong>⭐ Score:</strong> <span style='color: {score_color}; font-weight: bold;'>{score:.1f}/100</span></p>"
        
        popup_text += "</div>"
        
        # Add marker with better styling
        marker = folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=10,  # Slightly larger for better visibility
            popup=folium.Popup(popup_text, max_width=350) if show_popup else None,
            tooltip=f"{row.get('provider', f'Room #{idx}')} - {row.get('address', '')[:30]}..." if 'provider' in df.columns and pd.notna(row.get('provider')) else f"Room #{idx}",
            color='#2c3e50',
            weight=2,
            fillColor=color,
            fillOpacity=0.8
        )
        marker.add_to(m)
        markers_added += 1
    
    print(f"Added {markers_added} markers to map (skipped {skipped_count} invalid coordinates)")
    if skipped_count > 0:
        print(f"Warning: {skipped_count} rooms were skipped due to missing/invalid coordinates")
    return m


def add_transit_stops_to_map(
    m: folium.Map,
    df: pd.DataFrame
) -> folium.Map:
    """
    Add nearest transit stop markers to the map.
    
    Parameters:
    -----------
    m : folium.Map
        Map object
    df : pd.DataFrame
        Dataframe with stop coordinates (if available)
    
    Returns:
    --------
    folium.Map
        Map with transit stops added
    """
    # Note: We'd need stop coordinates in the dataframe
    # For now, this is a placeholder - stops would be added if we had their coordinates
    
    return m


def add_university_marker(
    m: folium.Map,
    university_coords: Tuple[float, float],
    university_name: str = "University"
) -> folium.Map:
    """
    Add university location marker to the map.
    
    Parameters:
    -----------
    m : folium.Map
        Map object
    university_coords : Tuple[float, float]
        (latitude, longitude) of university
    university_name : str
        Name of the university
    
    Returns:
    --------
    folium.Map
        Map with university marker added
    """
    folium.Marker(
        location=university_coords,
        popup=folium.Popup(f"<b>{university_name}</b>", max_width=200),
        icon=folium.Icon(color='red', icon='bookmark', prefix='glyphicon')
    ).add_to(m)
    
    return m


def create_interactive_map(
    apartments_df: pd.DataFrame,
    university_coords: Tuple[float, float],
    university_name: str = "University",
    color_by: str = 'suitability_score'
) -> folium.Map:
    """
    Create a complete interactive map with all features.
    
    Parameters:
    -----------
    apartments_df : pd.DataFrame
        Dataframe with apartment data including coordinates
    university_coords : Tuple[float, float]
        University (latitude, longitude)
    university_name : str
        University name
    color_by : str
        Column to use for coloring
    
    Returns:
    --------
    folium.Map
        Complete interactive map
    """
    # Calculate map center (average of apartments and university)
    valid_apartments = apartments_df[apartments_df['latitude'].notna() & apartments_df['longitude'].notna()]
    if len(valid_apartments) > 0:
        avg_lat = valid_apartments['latitude'].mean()
        avg_lon = valid_apartments['longitude'].mean()
        center = ((avg_lat + university_coords[0]) / 2, (avg_lon + university_coords[1]) / 2)
    else:
        center = university_coords
    
    # Create base map
    m = create_base_map(center, zoom_start=11)
    
    # Add university marker
    m = add_university_marker(m, university_coords, university_name)
    
    # Add apartments
    m = add_apartments_to_map(m, apartments_df, color_by=color_by)
    
    # Add legend
    if color_by in apartments_df.columns and apartments_df[color_by].notna().any():
        if color_by == 'suitability_score':
            colormap = folium.LinearColormap(
                colors=['red', 'orange', 'yellow', 'green'],
                vmin=apartments_df[color_by].min(),
                vmax=apartments_df[color_by].max(),
                caption=f'{color_by.replace("_", " ").title()}'
            )
            colormap.add_to(m)
    
    return m


def save_map(m: folium.Map, filepath: str):
    """
    Save map to HTML file.
    
    Parameters:
    -----------
    m : folium.Map
        Map object
    filepath : str
        Path to save HTML file
    """
    m.save(filepath)


def get_map_html(m: folium.Map) -> str:
    """
    Get HTML string representation of the map.
    
    Parameters:
    -----------
    m : folium.Map
        Map object
    
    Returns:
    --------
    str
        HTML string of the map
    """
    return m._repr_html_()

