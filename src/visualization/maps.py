import folium
from folium import plugins
import pandas as pd
import numpy as np
from typing import Tuple, Optional
import json
import html
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import MAP, TRANSPORT_MODES


def create_base_map(center: Tuple[float, float], zoom_start: int = None) -> folium.Map:
    zoom_start = zoom_start or MAP['default_zoom']
    
    m = folium.Map(location=center, zoom_start=zoom_start, tiles='OpenStreetMap')
    
    folium.TileLayer('CartoDB positron', name='CartoDB Positron', overlay=False).add_to(m)
    folium.TileLayer('CartoDB dark_matter', name='CartoDB Dark Matter', overlay=False).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    
    return m


def add_apartments_to_map(
    m: folium.Map,
    df: pd.DataFrame,
    color_by: str = 'suitability_score',
    show_popup: bool = True
) -> folium.Map:
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        raise ValueError("DataFrame must have 'latitude' and 'longitude' columns")
    
    colormap = _create_colormap(df, color_by)
    
    valid_coords = df[df['latitude'].notna() & df['longitude'].notna()]
    if len(valid_coords) == 0:
        print("Warning: No apartments with valid coordinates to display on map")
        return m
    
    df = df.copy()
    df['coord_key'] = df.apply(
        lambda row: f"{round(row['latitude'], 5)}_{round(row['longitude'], 5)}"
        if pd.notna(row['latitude']) and pd.notna(row['longitude']) else None,
        axis=1
    )
    
    marker_cluster = plugins.MarkerCluster(
        name='Rooms',
        overlay=True,
        control=False,
        options={
            'maxClusterRadius': MAP['cluster_radius'],
            'spiderfyOnMaxZoom': True,
            'showCoverageOnHover': True,
            'zoomToBoundsOnClick': True
        }
    )
    
    markers_added = 0
    skipped_count = 0
    processed_coords = set()
    
    for coord_key, group_df in df.groupby('coord_key'):
        if coord_key is None or coord_key in processed_coords:
            continue
        
        processed_coords.add(coord_key)
        
        first_row = group_df.iloc[0]
        lat, lon = first_row['latitude'], first_row['longitude']
        
        if pd.isna(lat) or pd.isna(lon) or (lat == 0 and lon == 0):
            skipped_count += len(group_df)
            continue
        
        popup_text = _build_popup_html(group_df, df)
        
        if colormap and color_by in group_df.columns:
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
        
        marker_radius = 12 if len(group_df) > 1 else 10
        
        room_ids = [f"room_{idx}" for idx in group_df.index]
        marker = folium.CircleMarker(
            location=[lat, lon],
            radius=marker_radius,
            popup=folium.Popup(popup_text, max_width=400, parse_html=False) if show_popup else None,
            tooltip=html.escape(
                f"{len(group_df)} room(s) at this location" if len(group_df) > 1
                else str(group_df.iloc[0].get('provider', 'Room'))
            ),
            color='#2c3e50',
            weight=2,
            fillColor=color,
            fillOpacity=0.8
        )
        marker._room_id = ','.join(room_ids)
        marker.add_to(marker_cluster)
        markers_added += 1
    
    marker_cluster.add_to(m)
    
    if 'coord_key' in df.columns:
        df.drop('coord_key', axis=1, inplace=True)
    
    print(f"Added {markers_added} markers to map using clustering (skipped {skipped_count} invalid coordinates)")
    return m


def _create_colormap(df: pd.DataFrame, color_by: str) -> Optional[folium.LinearColormap]:
    if color_by not in df.columns or not df[color_by].notna().any():
        return None
    
    if color_by == 'suitability_score':
        return folium.LinearColormap(
            colors=['red', 'orange', 'yellow', 'green'],
            vmin=df[color_by].min(),
            vmax=df[color_by].max()
        )
    elif color_by == 'rent':
        return folium.LinearColormap(
            colors=['blue', 'cyan', 'yellow', 'red'],
            vmin=df[color_by].min(),
            vmax=df[color_by].max()
        )
    elif color_by == 'total_commute_minutes':
        return folium.LinearColormap(
            colors=['green', 'yellow', 'orange', 'red'],
            vmin=df[color_by].min(),
            vmax=df[color_by].max()
        )
    return None


def _build_popup_html(group_df: pd.DataFrame, full_df: pd.DataFrame) -> str:
    popup_text = '<div style="font-family: Arial, sans-serif; max-width: 350px; max-height: 500px; overflow-y: auto;">'
    
    if len(group_df) > 1:
        popup_text += f'<h3 style="margin: 0 0 10px 0; color: #2c3e50;">📍 {len(group_df)} Rooms at This Location</h3>'
    
    for room_idx, (idx, row) in enumerate(group_df.iterrows()):
        if len(group_df) > 1:
            popup_text += f'<div style="border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-bottom: 10px;">'
            popup_text += f'<h4 style="margin: 0 0 5px 0; color: #3498db;">Room {room_idx + 1}</h4>'
        
        if 'provider' in full_df.columns and pd.notna(row.get('provider')):
            provider_escaped = html.escape(str(row['provider']))
            popup_text += f'<p style="margin: 0 0 5px 0; font-weight: bold; color: #2c3e50;">{provider_escaped}</p>'
        
        if 'address' in full_df.columns and pd.notna(row.get('address')):
            address_escaped = html.escape(str(row['address']))
            popup_text += f'<p style="margin: 0 0 5px 0; color: #7f8c8d; font-size: 11px;"><strong>📍 Address:</strong> {address_escaped}</p>'
        
        if 'rent' in full_df.columns and pd.notna(row.get('rent')):
            popup_text += f'<p style="margin: 0 0 5px 0;"><strong>💰 Rent:</strong> €{row["rent"]:.0f}/month</p>'
        
        popup_text += '<div style="background: #f8f9fa; padding: 8px; border-radius: 5px; margin: 5px 0;">'
        
        if 'nearest_stop_name' in full_df.columns and pd.notna(row.get('nearest_stop_name')):
            stop_name = html.escape(str(row['nearest_stop_name']))
            distance = row.get('nearest_stop_distance_m', 0)
            if pd.notna(distance) and distance > 0:
                popup_text += f'<p style="margin: 0 0 5px 0; font-size: 12px;"><strong>🚉 Nearest Stop:</strong> {stop_name}<br><small style="color: #666;">Distance: {distance:.0f}m</small></p>'
            else:
                popup_text += f'<p style="margin: 0 0 5px 0; font-size: 12px;"><strong>🚉 Nearest Stop:</strong> {stop_name}</p>'
        
        if 'walking_time_minutes' in full_df.columns and pd.notna(row.get('walking_time_minutes')):
            popup_text += f'<p style="margin: 0 0 5px 0; font-size: 12px;"><strong>🚶 Walking Time:</strong> {row["walking_time_minutes"]:.1f} min</p>'
        
        if 'total_commute_minutes' in full_df.columns and pd.notna(row.get('total_commute_minutes')):
            popup_text += f'<p style="margin: 5px 0; padding: 5px; background: #e3f2fd; border-radius: 3px; font-size: 12px; font-weight: bold;"><strong>⏱️ Total Commute:</strong> {row["total_commute_minutes"]:.1f} min</p>'
        
        if 'transfers' in full_df.columns and pd.notna(row.get('transfers')):
            popup_text += f'<p style="margin: 0 0 5px 0; font-size: 12px;"><strong>🔄 Transfers:</strong> {int(row["transfers"])}</p>'
        
        popup_text += '</div>'
        
        if 'suitability_score' in full_df.columns and pd.notna(row.get('suitability_score')):
            score = row['suitability_score']
            score_color = '#27ae60' if score >= 70 else '#f39c12' if score >= 50 else '#e74c3c'
            popup_text += f'<p style="margin: 5px 0 0 0; font-size: 12px;"><strong>⭐ Score:</strong> <span style="color: {score_color}; font-weight: bold;">{score:.1f}/100</span></p>'
        
        if len(group_df) > 1:
            popup_text += "</div>"
    
    popup_text += "</div>"
    return popup_text


def add_university_marker(
    m: folium.Map,
    university_coords: Tuple[float, float],
    university_name: str = "University"
) -> folium.Map:
    folium.Marker(
        location=university_coords,
        popup=folium.Popup(f"<b>{html.escape(str(university_name))}</b>", max_width=200),
        icon=folium.Icon(color='red', icon='bookmark', prefix='glyphicon')
    ).add_to(m)
    return m


def add_transit_stops_to_map(m: folium.Map, df: pd.DataFrame) -> folium.Map:
    return m


def create_interactive_map(
    apartments_df: pd.DataFrame,
    university_coords: Tuple[float, float],
    university_name: str = "University",
    color_by: str = 'suitability_score',
    highlight_room_id: Optional[str] = None
) -> folium.Map:
    valid_apartments = apartments_df[apartments_df['latitude'].notna() & apartments_df['longitude'].notna()]
    if len(valid_apartments) > 0:
        avg_lat = valid_apartments['latitude'].mean()
        avg_lon = valid_apartments['longitude'].mean()
        center = ((avg_lat + university_coords[0]) / 2, (avg_lon + university_coords[1]) / 2)
    else:
        center = university_coords
    
    m = create_base_map(center, zoom_start=11)
    m = add_university_marker(m, university_coords, university_name)
    m = add_apartments_to_map(m, apartments_df, color_by=color_by)
    
    focus_script = _create_focus_script()
    m.get_root().html.add_child(folium.Element(focus_script))
    
    if highlight_room_id:
        room_data = apartments_df[apartments_df.index.astype(str).str.replace('room_', '') == highlight_room_id.replace('room_', '')]
        if len(room_data) > 0:
            room = room_data.iloc[0]
            if pd.notna(room['latitude']) and pd.notna(room['longitude']):
                m.fit_bounds([[room['latitude'], room['longitude']], [room['latitude'], room['longitude']]], padding=(50, 50))
    
    return m


def _create_focus_script() -> str:
    return """
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
                if (!mapReady) initMapInteraction();
                return;
            }
            
            mapInstance.setView([lat, lon], 16, {animate: true, duration: 0.5});
            
            mapInstance.eachLayer(function(layer) {
                if (!layer._room_id) return;
                var layerRoomIds = layer._room_id.split(',');
                if (layerRoomIds.indexOf(roomId) !== -1) {
                    if (layer.setRadius) {
                        var originalRadius = layer.options.radius || 10;
                        layer.setRadius(originalRadius + 5);
                        layer.setStyle({color: '#ff0000', weight: 4, fillOpacity: 1.0});
                        if (layer.openPopup) layer.openPopup();
                        setTimeout(function() {
                            layer.setRadius(originalRadius);
                            layer.setStyle({color: '#2c3e50', weight: 2, fillOpacity: 0.8});
                        }, 3000);
                    }
                }
            });
        }
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initMapInteraction);
        } else {
            initMapInteraction();
        }
    })();
    </script>
    """


def save_map(m: folium.Map, filepath: str) -> None:
    m.save(filepath)


def get_map_html(m: folium.Map) -> str:
    return m._repr_html_()
