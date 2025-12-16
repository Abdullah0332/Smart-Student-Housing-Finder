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
import html


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
    # Create map with OpenStreetMap as default (explicitly set)
    m = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles='OpenStreetMap'  # Default tile layer - OpenStreetMap
    )
    
    # Add alternative tile layers (user can switch via layer control)
    # These are optional - OpenStreetMap remains the default
    folium.TileLayer('CartoDB positron', name='CartoDB Positron', overlay=False).add_to(m)
    folium.TileLayer('CartoDB dark_matter', name='CartoDB Dark Matter', overlay=False).add_to(m)
    
    # Add layer control (allows switching between tile layers)
    # OpenStreetMap will be the default/base layer
    folium.LayerControl(collapsed=False).add_to(m)
    
    return m


def add_apartments_to_map(
    m: folium.Map,
    df: pd.DataFrame,
    color_by: str = 'suitability_score',
    show_popup: bool = True
) -> folium.Map:
    """
    Add apartment markers to the map.
    Groups rooms at the same location into a single marker with all rooms listed in popup.
    """
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
        return m
    
    # Group rooms by coordinates (round to 5 decimal places to handle slight variations)
    df['coord_key'] = df.apply(
        lambda row: f"{round(row['latitude'], 5)}_{round(row['longitude'], 5)}" 
        if pd.notna(row['latitude']) and pd.notna(row['longitude']) else None,
        axis=1
    )
    
    # Use MarkerCluster for better performance with large numbers of markers (2000+)
    # This groups nearby markers together and only shows individual markers when zoomed in
    marker_cluster = plugins.MarkerCluster(
        name='Rooms',
        overlay=True,
        control=False,  # Set to False to avoid LayerControl conflicts
        options={
            'maxClusterRadius': 50,  # Radius in pixels to cluster markers
            'spiderfyOnMaxZoom': True,  # Show all markers when zoomed in
            'showCoverageOnHover': True,  # Show area covered by cluster
            'zoomToBoundsOnClick': True  # Zoom to bounds when cluster clicked
        }
    )
    
    # Add markers - group by coordinates
    markers_added = 0
    skipped_count = 0
    processed_coords = set()
    
    for coord_key, group_df in df.groupby('coord_key'):
        if coord_key is None or coord_key in processed_coords:
            continue
        
        processed_coords.add(coord_key)
        
        # Get first row for coordinates
        first_row = group_df.iloc[0]
        lat, lon = first_row['latitude'], first_row['longitude']
        
        if pd.isna(lat) or pd.isna(lon) or (lat == 0 and lon == 0):
            skipped_count += len(group_df)
            continue
        
        # Create popup text with ALL rooms at this location
        # Use double quotes for style attributes to avoid conflicts with single quotes in data
        popup_text = '<div style="font-family: Arial, sans-serif; max-width: 350px; max-height: 500px; overflow-y: auto;">'
        
        # If multiple rooms, show count
        if len(group_df) > 1:
            popup_text += f'<h3 style="margin: 0 0 10px 0; color: #2c3e50;">📍 {len(group_df)} Rooms at This Location</h3>'
        
        # List all rooms at this location
        for room_idx, (idx, row) in enumerate(group_df.iterrows()):
            if len(group_df) > 1:
                popup_text += f'<div style="border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-bottom: 10px;">'
                popup_text += f'<h4 style="margin: 0 0 5px 0; color: #3498db;">Room {room_idx + 1}</h4>'
            
            # Room/Provider name - escape HTML
            if 'provider' in df.columns and pd.notna(row.get('provider')):
                provider_escaped = html.escape(str(row['provider']))
                popup_text += f'<p style="margin: 0 0 5px 0; font-weight: bold; color: #2c3e50;">{provider_escaped}</p>'
            else:
                popup_text += f'<p style="margin: 0 0 5px 0; font-weight: bold; color: #2c3e50;">Room #{idx}</p>'
            
            # Address - escape HTML
            if 'address' in df.columns and pd.notna(row.get('address')):
                address_escaped = html.escape(str(row['address']))
                popup_text += f'<p style="margin: 0 0 5px 0; color: #7f8c8d; font-size: 11px;"><strong>📍 Address:</strong> {address_escaped}</p>'
            
            # Rent
            if 'rent' in df.columns and pd.notna(row.get('rent')):
                popup_text += f'<p style="margin: 0 0 5px 0;"><strong>💰 Rent:</strong> €{row["rent"]:.0f}/month</p>'
            
            # BVG Transport Information Section
            popup_text += '<div style="background: #f8f9fa; padding: 8px; border-radius: 5px; margin: 5px 0;">'
            
            # Nearest Stop with Distance - escape HTML
            if 'nearest_stop_name' in df.columns and pd.notna(row.get('nearest_stop_name')):
                stop_name = html.escape(str(row['nearest_stop_name']))
                distance = row.get('nearest_stop_distance_m', 0)
                if pd.notna(distance) and distance > 0:
                    popup_text += f'<p style="margin: 0 0 5px 0; font-size: 12px;"><strong>🚉 Nearest Stop:</strong> {stop_name}<br><small style="color: #666;">Distance: {distance:.0f}m</small></p>'
                else:
                    popup_text += f'<p style="margin: 0 0 5px 0; font-size: 12px;"><strong>🚉 Nearest Stop:</strong> {stop_name}</p>'
            
            # Walking time
            if 'walking_time_minutes' in df.columns and pd.notna(row.get('walking_time_minutes')):
                walking_time = row['walking_time_minutes']
                popup_text += f'<p style="margin: 0 0 5px 0; font-size: 12px;"><strong>🚶 Walking Time:</strong> {walking_time:.1f} min</p>'
            
            # Transport Routes with detailed information
            if 'route_details' in df.columns and pd.notna(row.get('route_details')):
                import json
                try:
                    route_details = json.loads(row['route_details']) if isinstance(row['route_details'], str) else row['route_details']
                    if route_details and len(route_details) > 0:
                        popup_text += '<p style="margin: 5px 0; font-size: 12px;"><strong>🚇 Transport Routes:</strong></p>'
                        for route in route_details:
                            mode = route.get('mode', 'unknown')
                            name = html.escape(str(route.get('name', '')))
                            from_stop = html.escape(str(route.get('from', '')))
                            to_stop = html.escape(str(route.get('to', '')))
                            
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
                                # Escape all dynamic content to prevent JavaScript syntax errors
                                name_escaped = html.escape(str(name))
                                from_stop_escaped = html.escape(str(from_stop)) if from_stop else ''
                                to_stop_escaped = html.escape(str(to_stop)) if to_stop else ''
                                popup_text += f'<div style="margin: 3px 0; padding: 4px; background: {mode_color}; color: white; border-radius: 4px; font-size: 11px; font-weight: bold;">{mode_display} {name_escaped}</div>'
                                if from_stop_escaped and to_stop_escaped:
                                    popup_text += f'<p style="margin: 2px 0 5px 0; font-size: 10px; color: #666;">{from_stop_escaped} → {to_stop_escaped}</p>'
                except Exception as e:
                    # Fallback to transport_modes - escape HTML
                    if 'transport_modes' in df.columns and pd.notna(row.get('transport_modes')):
                        modes = html.escape(str(row['transport_modes']))
                        popup_text += f'<p style="margin: 0 0 5px 0; font-size: 12px;"><strong>🚇 Transport:</strong> {modes}</p>'
            
            # Departure and Arrival Times (if available)
            if 'journey' in row or 'departure' in row or 'arrival' in row:
                # Check if we have journey data with timing
                journey_data = None
                if 'journey' in row and pd.notna(row.get('journey')):
                    import json
                    try:
                        journey_data = json.loads(row['journey']) if isinstance(row['journey'], str) else row['journey']
                    except:
                        pass
                
                if journey_data:
                    departure = html.escape(str(journey_data.get('departure', '')))
                    arrival = html.escape(str(journey_data.get('arrival', '')))
                    if departure:
                        popup_text += f'<p style="margin: 0 0 5px 0; font-size: 11px;"><strong>🕐 Departure:</strong> {departure}</p>'
                    if arrival:
                        popup_text += f'<p style="margin: 0 0 5px 0; font-size: 11px;"><strong>🕐 Arrival:</strong> {arrival}</p>'
            
            # Transit time
            if 'transit_time_minutes' in df.columns and pd.notna(row.get('transit_time_minutes')):
                transit_time = row['transit_time_minutes']
                popup_text += f'<p style="margin: 0 0 5px 0; font-size: 12px;"><strong>🚊 Transit Time:</strong> {transit_time:.1f} min</p>'
            
            # Total commute
            if 'total_commute_minutes' in df.columns and pd.notna(row.get('total_commute_minutes')):
                total_commute = row['total_commute_minutes']
                popup_text += f'<p style="margin: 5px 0; padding: 5px; background: #e3f2fd; border-radius: 3px; font-size: 12px; font-weight: bold;"><strong>⏱️ Total Commute:</strong> {total_commute:.1f} min</p>'
            
            # Transfers
            if 'transfers' in df.columns and pd.notna(row.get('transfers')):
                transfers = int(row['transfers'])
                popup_text += f'<p style="margin: 0 0 5px 0; font-size: 12px;"><strong>🔄 Transfers:</strong> {transfers}</p>'
            
            popup_text += '</div>'  # Close transport info div
            
            # Suitability score
            if 'suitability_score' in df.columns and pd.notna(row.get('suitability_score')):
                score = row['suitability_score']
                score_color = '#27ae60' if score >= 70 else '#f39c12' if score >= 50 else '#e74c3c'
                popup_text += f'<p style="margin: 5px 0 0 0; font-size: 12px;"><strong>⭐ Score:</strong> <span style="color: {score_color}; font-weight: bold;">{score:.1f}/100</span></p>'
            
            if len(group_df) > 1:
                popup_text += "</div>"  # Close room div
        
        popup_text += "</div>"
        
        # Determine marker color (use average or first room's color)
        if colormap and color_by in group_df.columns:
            # Use first room's value for color
            color_val = group_df.iloc[0].get(color_by)
            if pd.notna(color_val):
                try:
                    color = colormap(color_val)
                except:
                    color = 'blue'
            else:
                color = 'blue'
        else:
            color = 'blue'
        
        # Make marker slightly larger if multiple rooms
        marker_radius = 12 if len(group_df) > 1 else 10
        
        # Create marker with all rooms
        room_ids = [f"room_{idx}" for idx in group_df.index]
        marker = folium.CircleMarker(
            location=[lat, lon],
            radius=marker_radius,
            popup=folium.Popup(popup_text, max_width=400, parse_html=False) if show_popup else None,
            tooltip=html.escape(f"{len(group_df)} room(s) at this location" if len(group_df) > 1 else str(group_df.iloc[0].get('provider', 'Room'))),
            color='#2c3e50',
            weight=2,
            fillColor=color,
            fillOpacity=0.8
        )
        # Store room IDs (comma-separated for multiple rooms)
        marker._room_id = ','.join(room_ids)
        # Add to marker cluster instead of directly to map (better performance for 2000+ markers)
        marker.add_to(marker_cluster)
        markers_added += 1
    
    # Add marker cluster to map
    marker_cluster.add_to(m)
    
    # Clean up temporary column
    if 'coord_key' in df.columns:
        df.drop('coord_key', axis=1, inplace=True)
    
    print(f"Added {markers_added} markers to map using clustering (skipped {skipped_count} invalid coordinates)")
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
        popup=folium.Popup(f"<b>{html.escape(str(university_name))}</b>", max_width=200),
        icon=folium.Icon(color='red', icon='bookmark', prefix='glyphicon')
    ).add_to(m)
    
    return m


def create_interactive_map(
    apartments_df: pd.DataFrame,
    university_coords: Tuple[float, float],
    university_name: str = "University",
    color_by: str = 'suitability_score',
    highlight_room_id: Optional[str] = None
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
    
    # Legend removed - no color scale bar on map
    
    # Add JavaScript to handle room selection and map focusing
    focus_script = """
    <script>
    (function() {
        var mapReady = false;
        var pendingFocus = null;
        
        function initMapInteraction() {
            if (typeof L === 'undefined') {
                setTimeout(initMapInteraction, 100);
                return;
            }
            
            var mapContainer = document.querySelector('.folium-map');
            if (!mapContainer) {
                setTimeout(initMapInteraction, 100);
                return;
            }
            
            var checkMap = setInterval(function() {
                var mapInstance = null;
                if (L._mapContainer && Object.keys(L._mapContainer).length > 0) {
                    var mapId = Object.keys(L._mapContainer)[0];
                    mapInstance = L._mapContainer[mapId];
                }
                
                if (mapInstance) {
                    clearInterval(checkMap);
                    mapReady = true;
                    
                    if (pendingFocus) {
                        focusRoom(pendingFocus.roomId, pendingFocus.lat, pendingFocus.lon, mapInstance);
                        pendingFocus = null;
                    }
                    
                    window.addEventListener('message', function(event) {
                        if (event.data && event.data.type === 'focusRoom') {
                            focusRoom(event.data.roomId, event.data.lat, event.data.lon, mapInstance);
                        }
                    });
                }
            }, 100);
            
            setTimeout(function() {
                clearInterval(checkMap);
            }, 5000);
        }
        
        function focusRoom(roomId, lat, lon, mapInstance) {
            if (!mapInstance) {
                pendingFocus = {roomId: roomId, lat: lat, lon: lon};
                if (!mapReady) {
                    initMapInteraction();
                }
                return;
            }
            
            // Zoom to the location
            mapInstance.setView([lat, lon], 16, {animate: true, duration: 0.5});
            
            // Find and highlight the marker
            var markerFound = false;
            mapInstance.eachLayer(function(layer) {
                if (!layer._room_id) return;
                
                // Check if this marker contains the room ID (handles comma-separated IDs for grouped markers)
                var layerRoomIds = layer._room_id.split(',');
                if (layerRoomIds.indexOf(roomId) !== -1) {
                    markerFound = true;
                    if (layer.setRadius) {
                        // Make marker larger and highlight it
                        var originalRadius = layer.options.radius || 10;
                        layer.setRadius(originalRadius + 5);
                        layer.setStyle({color: '#ff0000', weight: 4, fillOpacity: 1.0});
                        
                        // Open popup
                        if (layer.openPopup) {
                            layer.openPopup();
                        }
                        
                        // Reset after 3 seconds
                        setTimeout(function() {
                            layer.setRadius(originalRadius);
                            layer.setStyle({color: '#2c3e50', weight: 2, fillOpacity: 0.8});
                        }, 3000);
                    }
                }
            });
            
            // If marker not found, still zoom to location
            if (!markerFound) {
                console.log('Marker not found for room:', roomId);
            }
        }
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initMapInteraction);
        } else {
            initMapInteraction();
        }
    })();
    </script>
    """
    
    m.get_root().html.add_child(folium.Element(focus_script))
    
    if highlight_room_id:
        room_data = apartments_df[apartments_df.index.astype(str).str.replace('room_', '') == highlight_room_id.replace('room_', '')]
        if len(room_data) > 0:
            room = room_data.iloc[0]
            if pd.notna(room['latitude']) and pd.notna(room['longitude']):
                m.fit_bounds([[room['latitude'], room['longitude']], [room['latitude'], room['longitude']]], padding=(50, 50))
    
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

