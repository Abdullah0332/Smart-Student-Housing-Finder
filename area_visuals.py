"""
Area Visualization Module
=========================

Creates charts and maps for visualizing district-level analysis results.

Urban Technology Relevance:
- Spatial visualization is essential for understanding urban patterns
- Choropleth maps show geographic distribution of accessibility
- Charts enable comparison of districts across multiple dimensions
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import folium
from folium import plugins
import json
from typing import Dict, Optional, Tuple
from logger_config import setup_logger

logger = setup_logger("area_visuals")

# Berlin district center coordinates for map markers
DISTRICT_COORDS = {
    'Mitte': (52.5200, 13.4050),
    'Friedrichshain-Kreuzberg': (52.5020, 13.4540),
    'Pankow': (52.5690, 13.4010),
    'Charlottenburg-Wilmersdorf': (52.5040, 13.3050),
    'Spandau': (52.5360, 13.1990),
    'Steglitz-Zehlendorf': (52.4340, 13.2580),
    'Tempelhof-Schöneberg': (52.4700, 13.3900),
    'Neukölln': (52.4770, 13.4350),
    'Treptow-Köpenick': (52.4420, 13.5750),
    'Marzahn-Hellersdorf': (52.5360, 13.5750),
    'Lichtenberg': (52.5130, 13.4990),
    'Reinickendorf': (52.5890, 13.3210)
}


def create_score_bar_chart(ranked_areas: pd.DataFrame, top_n: int = 10) -> plt.Figure:
    """
    Create bar chart showing top N districts by Student Area Score.
    
    Parameters:
    -----------
    ranked_areas : pd.DataFrame
        Districts ranked by student_area_score
    top_n : int
        Number of top districts to show
    
    Returns:
    --------
    matplotlib.figure.Figure
        Bar chart figure
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    
    top_districts = ranked_areas.head(top_n)
    
    bars = ax.barh(
        top_districts['district'],
        top_districts['student_area_score'],
        color='steelblue'
    )
    
    ax.set_xlabel('Student Area Score', fontsize=12, fontweight='bold')
    ax.set_title(f'Top {top_n} Berlin Districts by Student Area Score', fontsize=14, fontweight='bold')
    ax.set_xlim(0, 1)
    
    # Add value labels on bars
    for i, (idx, row) in enumerate(top_districts.iterrows()):
        score = row['student_area_score']
        ax.text(score + 0.01, i, f'{score:.3f}', va='center', fontsize=10)
    
    plt.tight_layout()
    return fig


def create_rooms_bar_chart(housing_metrics: pd.DataFrame) -> plt.Figure:
    """
    Create bar chart showing number of rooms per district.
    
    Parameters:
    -----------
    housing_metrics : pd.DataFrame
        Housing metrics per district
    
    Returns:
    --------
    matplotlib.figure.Figure
        Bar chart figure
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Sort by number of rooms
    sorted_metrics = housing_metrics.sort_values('total_rooms', ascending=True)
    
    bars = ax.barh(
        sorted_metrics['district'],
        sorted_metrics['total_rooms'],
        color='coral'
    )
    
    ax.set_xlabel('Number of Rooms', fontsize=12, fontweight='bold')
    ax.set_title('Room Availability by Berlin District', fontsize=14, fontweight='bold')
    
    # Add value labels
    for i, (idx, row) in enumerate(sorted_metrics.iterrows()):
        rooms = row['total_rooms']
        ax.text(rooms + max(sorted_metrics['total_rooms']) * 0.01, i, 
                f'{int(rooms)}', va='center', fontsize=10)
    
    plt.tight_layout()
    return fig


def create_rent_vs_transport_scatter(ranked_areas: pd.DataFrame) -> plt.Figure:
    """
    Create scatter plot: Average rent vs transport accessibility.
    
    Parameters:
    -----------
    ranked_areas : pd.DataFrame
        Merged data with rent and transport metrics
    
    Returns:
    --------
    matplotlib.figure.Figure
        Scatter plot figure
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Filter to districts with both rent and commute data
    plot_data = ranked_areas[
        ranked_areas['avg_rent'].notna() & 
        ranked_areas['avg_commute_minutes'].notna()
    ].copy()
    
    if len(plot_data) == 0:
        ax.text(0.5, 0.5, 'No data available', 
                ha='center', va='center', transform=ax.transAxes)
        return fig
    
    scatter = ax.scatter(
        plot_data['avg_commute_minutes'],
        plot_data['avg_rent'],
        s=plot_data['total_rooms'] * 10,  # Size by number of rooms
        alpha=0.6,
        c=plot_data['student_area_score'],
        cmap='viridis',
        edgecolors='black',
        linewidth=1
    )
    
    # Add district labels
    for idx, row in plot_data.iterrows():
        ax.annotate(
            row['district'],
            (row['avg_commute_minutes'], row['avg_rent']),
            fontsize=9,
            alpha=0.7
        )
    
    ax.set_xlabel('Average Commute Time (minutes)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Average Rent (€/month)', fontsize=12, fontweight='bold')
    ax.set_title('Rent vs Transport Accessibility by District', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Student Area Score', fontsize=10)
    
    plt.tight_layout()
    return fig


def create_walking_distance_histogram(ranked_areas: pd.DataFrame) -> plt.Figure:
    """
    Create histogram of walking distances to nearest BVG stop.
    
    Parameters:
    -----------
    ranked_areas : pd.DataFrame
        Data with avg_walking_distance_m
    
    Returns:
    --------
    matplotlib.figure.Figure
        Histogram figure
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    walking_data = ranked_areas['avg_walking_distance_m'].dropna()
    
    if len(walking_data) == 0:
        ax.text(0.5, 0.5, 'No walking distance data available', 
                ha='center', va='center', transform=ax.transAxes)
        return fig
    
    ax.hist(walking_data, bins=15, color='skyblue', edgecolor='black', alpha=0.7)
    ax.set_xlabel('Average Walking Distance to Nearest Stop (meters)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Districts', fontsize=12, fontweight='bold')
    ax.set_title('Distribution of Walking Distances to BVG Stops', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    return fig


def create_district_choropleth_map(ranked_areas: pd.DataFrame) -> folium.Map:
    """
    Create choropleth map of Berlin districts colored by Student Area Score.
    
    Note: This creates a simplified map using district center points.
    For a true choropleth, you would need GeoJSON boundaries.
    
    Parameters:
    -----------
    ranked_areas : pd.DataFrame
        Districts with student_area_score
    
    Returns:
    --------
    folium.Map
        Interactive map
    """
    # Create base map centered on Berlin
    m = folium.Map(
        location=[52.5200, 13.4050],
        zoom_start=11,
        tiles='OpenStreetMap'
    )
    
    # Color scale for scores
    max_score = ranked_areas['student_area_score'].max()
    min_score = ranked_areas['student_area_score'].min()
    
    # Add markers for each district
    for idx, row in ranked_areas.iterrows():
        district = row['district']
        score = row['student_area_score']
        
        if district in DISTRICT_COORDS:
            lat, lon = DISTRICT_COORDS[district]
            
            # Color based on score (green = high, red = low)
            if max_score > min_score:
                normalized_score = (score - min_score) / (max_score - min_score)
            else:
                normalized_score = 0.5
            
            # Interpolate color from red (low) to green (high)
            red = int(255 * (1 - normalized_score))
            green = int(255 * normalized_score)
            color = f'#{red:02x}{green:02x}00'
            
            # Create popup with district info
            popup_html = f"""
            <div style="font-family: Arial; min-width: 200px;">
                <h4 style="margin: 5px 0;">{district}</h4>
                <p style="margin: 3px 0;"><strong>Student Area Score:</strong> {score:.3f}</p>
                <p style="margin: 3px 0;"><strong>Total Rooms:</strong> {int(row.get('total_rooms', 0))}</p>
                <p style="margin: 3px 0;"><strong>Avg Rent:</strong> €{row.get('avg_rent', 0):.0f}/month</p>
                <p style="margin: 3px 0;"><strong>Avg Commute:</strong> {row.get('avg_commute_minutes', 0):.1f} min</p>
            </div>
            """
            
            folium.CircleMarker(
                location=[lat, lon],
                radius=15 + (normalized_score * 10),  # Size by score
                popup=folium.Popup(popup_html, max_width=300),
                color='black',
                weight=2,
                fill=True,
                fillColor=color,
                fillOpacity=0.7
            ).add_to(m)
    
    # Add legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 120px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <h4 style="margin: 5px 0;">Student Area Score</h4>
    <p style="margin: 2px 0;"><span style="color: #00ff00;">●</span> High Score</p>
    <p style="margin: 2px 0;"><span style="color: #ffff00;">●</span> Medium Score</p>
    <p style="margin: 2px 0;"><span style="color: #ff0000;">●</span> Low Score</p>
    <p style="margin: 5px 0; font-size: 11px;">Larger circles = higher score</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m


def create_all_visualizations(analysis_results: Dict) -> Dict:
    """
    Create all visualizations for area analysis.
    
    Parameters:
    -----------
    analysis_results : dict
        Results from analyze_best_areas()
    
    Returns:
    --------
    dict
        Dictionary with all figure objects and map
    """
    ranked_areas = analysis_results['ranked_areas']
    housing_metrics = analysis_results['housing_metrics']
    
    if len(ranked_areas) == 0:
        logger.warning("No data for visualizations")
        return {}
    
    visuals = {
        'score_chart': create_score_bar_chart(ranked_areas, top_n=10),
        'rooms_chart': create_rooms_bar_chart(housing_metrics),
        'scatter_plot': create_rent_vs_transport_scatter(ranked_areas),
        'histogram': create_walking_distance_histogram(ranked_areas),
        'map': create_district_choropleth_map(ranked_areas)
    }
    
    return visuals

