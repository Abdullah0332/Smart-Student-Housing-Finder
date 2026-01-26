import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import folium
from typing import Dict, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import MAP
from ..analysis.area import BERLIN_DISTRICTS


def create_all_visualizations(analysis_results: Dict) -> Dict:
    ranked_areas = analysis_results.get('ranked_areas', pd.DataFrame())
    visuals = {}
    
    if len(ranked_areas) == 0:
        return visuals
    
    visuals['score_chart'] = _create_score_bar_chart(ranked_areas)
    visuals['rooms_chart'] = _create_rooms_bar_chart(ranked_areas)
    visuals['scatter_plot'] = _create_rent_commute_scatter(ranked_areas)
    visuals['histogram'] = _create_score_histogram(ranked_areas)
    visuals['map'] = _create_district_map(ranked_areas)
    
    return visuals


def _create_score_bar_chart(df: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 6))
    
    sorted_df = df.sort_values('student_area_score', ascending=True)
    colors = plt.cm.RdYlGn(sorted_df['student_area_score'] / sorted_df['student_area_score'].max())
    
    ax.barh(sorted_df['district'], sorted_df['student_area_score'], color=colors)
    ax.set_xlabel('Student Area Score')
    ax.set_title('Berlin Districts Ranked by Student Suitability')
    ax.set_xlim(0, 1)
    
    plt.tight_layout()
    return fig


def _create_rooms_bar_chart(df: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 6))
    
    sorted_df = df.sort_values('total_rooms', ascending=True)
    ax.barh(sorted_df['district'], sorted_df['total_rooms'], color='steelblue')
    ax.set_xlabel('Number of Available Rooms')
    ax.set_title('Room Availability by District')
    
    plt.tight_layout()
    return fig


def _create_rent_commute_scatter(df: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 6))
    
    plot_df = df[df['avg_rent'].notna() & df['avg_commute_minutes'].notna()].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    sizes = plot_df['total_rooms'].fillna(1) * 10
    colors = plot_df['student_area_score']
    
    scatter = ax.scatter(
        plot_df['avg_commute_minutes'],
        plot_df['avg_rent'],
        s=sizes,
        c=colors,
        cmap='RdYlGn',
        alpha=0.7,
        edgecolors='black',
        linewidths=0.5
    )
    
    for idx, row in plot_df.iterrows():
        ax.annotate(row['district'][:10], (row['avg_commute_minutes'], row['avg_rent']), fontsize=8, alpha=0.7)
    
    ax.set_xlabel('Average Commute Time (minutes)')
    ax.set_ylabel('Average Rent (€)')
    ax.set_title('Rent vs Commute Time by District')
    
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Student Area Score')
    
    plt.tight_layout()
    return fig


def _create_score_histogram(df: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 5))
    
    ax.hist(df['student_area_score'], bins=10, color='steelblue', edgecolor='black', alpha=0.7)
    ax.set_xlabel('Student Area Score')
    ax.set_ylabel('Number of Districts')
    ax.set_title('Distribution of Student Area Scores')
    
    mean_score = df['student_area_score'].mean()
    ax.axvline(mean_score, color='red', linestyle='--', label=f'Mean: {mean_score:.3f}')
    ax.legend()
    
    plt.tight_layout()
    return fig


def _create_district_map(df: pd.DataFrame) -> folium.Map:
    center = MAP['berlin_center']
    m = folium.Map(location=center, zoom_start=11, tiles='CartoDB positron')
    
    for idx, row in df.iterrows():
        district = row['district']
        if district not in BERLIN_DISTRICTS:
            continue
        
        district_data = BERLIN_DISTRICTS[district]
        lat, lon = district_data['lat'], district_data['lon']
        score = row['student_area_score']
        
        if score >= 0.7:
            color = 'green'
        elif score >= 0.5:
            color = 'orange'
        else:
            color = 'red'
        
        folium.CircleMarker(
            location=[lat, lon],
            radius=15,
            popup=f"<b>{district}</b><br>Score: {score:.3f}<br>Rooms: {int(row.get('total_rooms', 0))}<br>Avg Rent: €{row.get('avg_rent', 0):.0f}",
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.6
        ).add_to(m)
    
    return m


def create_research_question_charts(rq_results: Dict, df: pd.DataFrame) -> Dict:
    charts = {}
    
    rq1 = rq_results.get('RQ1_affordability_vs_accessibility', {})
    if rq1.get('status') == 'success':
        charts['rq1_scatter'] = _create_rq1_scatter(df)
    
    rq3 = rq_results.get('RQ3_walking_vs_availability', {})
    if rq3.get('status') == 'success':
        charts['rq3_scatter'] = _create_rq3_scatter(df)
    
    rq4 = rq_results.get('RQ4_platform_differences', {})
    if rq4.get('status') == 'success':
        charts['rq4_bar'] = _create_rq4_bar(rq4)
    
    rq5 = rq_results.get('RQ5_spatial_equity', {})
    if rq5.get('status') == 'success':
        charts['rq5_bar'] = _create_rq5_bar(df)
    
    # New walkability/mobility research questions
    rq6 = rq_results.get('RQ6_walkability_vs_rent', {})
    if rq6.get('status') == 'success':
        charts['rq6_scatter'] = _create_rq6_scatter(df)
    
    rq7 = rq_results.get('RQ7_walkability_vs_commute', {})
    if rq7.get('status') == 'success':
        charts['rq7_scatter'] = _create_rq7_scatter(df)
    
    rq8 = rq_results.get('RQ8_poi_vs_availability', {})
    if rq8.get('status') == 'success':
        charts['rq8_scatter'] = _create_rq8_scatter(df)
    
    rq9 = rq_results.get('RQ9_bike_vs_walkability', {})
    if rq9.get('status') == 'success':
        charts['rq9_scatter'] = _create_rq9_scatter(df)
    
    rq10 = rq_results.get('RQ10_multimodal_mobility', {})
    if rq10.get('status') == 'success':
        charts['rq10_bar'] = _create_rq10_bar(rq10)
    
    # Additional mobility and walkability research questions
    rq11 = rq_results.get('RQ11_amenities_vs_walkability', {})
    if rq11.get('status') == 'success':
        charts['rq11_scatter'] = _create_rq11_scatter(df)
    
    rq12 = rq_results.get('RQ12_bike_vs_commute', {})
    if rq12.get('status') == 'success':
        charts['rq12_scatter'] = _create_rq12_scatter(df)
    
    rq13 = rq_results.get('RQ13_walkability_by_district', {})
    if rq13.get('status') == 'success':
        charts['rq13_bar'] = _create_rq13_bar(rq13, df)
    
    rq14 = rq_results.get('RQ14_poi_density_vs_walkability', {})
    if rq14.get('status') == 'success':
        charts['rq14_scatter'] = _create_rq14_scatter(df)
    
    rq15 = rq_results.get('RQ15_essential_services_vs_availability', {})
    if rq15.get('status') == 'success':
        charts['rq15_scatter'] = _create_rq15_scatter(df)
    
    rq16 = rq_results.get('RQ16_bike_vs_rent', {})
    if rq16.get('status') == 'success':
        charts['rq16_scatter'] = _create_rq16_scatter(df)
    
    rq17 = rq_results.get('RQ17_walkability_vs_transfers', {})
    if rq17.get('status') == 'success':
        charts['rq17_scatter'] = _create_rq17_scatter(df)
    
    rq18 = rq_results.get('RQ18_walkability_affordability_ratio', {})
    if rq18.get('status') == 'success':
        charts['rq18_bar'] = _create_rq18_bar(rq18)
    
    return charts


def _create_rq1_scatter(df: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 6))
    
    plot_df = df[
        df['rent'].notna() &
        df['total_commute_minutes'].notna() &
        (pd.to_numeric(df['rent'], errors='coerce') > 0) &
        (pd.to_numeric(df['total_commute_minutes'], errors='coerce') > 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    commutes = pd.to_numeric(plot_df['total_commute_minutes'], errors='coerce').values
    rents = pd.to_numeric(plot_df['rent'], errors='coerce').values
    
    # Remove NaN
    valid_mask = ~(np.isnan(commutes) | np.isnan(rents))
    commutes = commutes[valid_mask]
    rents = rents[valid_mask]
    
    if len(commutes) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    ax.scatter(commutes, rents, alpha=0.5, s=30, c='steelblue')
    
    z = np.polyfit(commutes, rents, 1)
    p = np.poly1d(z)
    x_line = np.linspace(commutes.min(), commutes.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label='Trend line')
    
    ax.set_xlabel('Commute Time (minutes)')
    ax.set_ylabel('Rent (€/month)')
    ax.set_title('RQ1: Relationship between Rent and Commute Time')
    ax.legend()
    
    plt.tight_layout()
    return fig


def _create_rq3_scatter(df: pd.DataFrame) -> plt.Figure:
    from ..analysis.area import aggregate_housing_metrics, aggregate_transport_metrics
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    housing = aggregate_housing_metrics(df)
    transport = aggregate_transport_metrics(df)
    
    if len(housing) == 0 or len(transport) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    merged = pd.merge(housing, transport, on='district', how='inner')
    plot_df = merged[
        merged['avg_walking_distance_m'].notna() & 
        merged['total_rooms'].notna() &
        (pd.to_numeric(merged['avg_walking_distance_m'], errors='coerce') > 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    walking = pd.to_numeric(plot_df['avg_walking_distance_m'], errors='coerce').values
    rooms = pd.to_numeric(plot_df['total_rooms'], errors='coerce').values
    
    # Remove NaN
    valid_mask = ~(np.isnan(walking) | np.isnan(rooms))
    walking = walking[valid_mask]
    rooms = rooms[valid_mask]
    plot_df_valid = plot_df.iloc[valid_mask]
    
    if len(walking) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    ax.scatter(walking, rooms, s=100, c='steelblue', alpha=0.7)
    
    for idx, row in plot_df_valid.iterrows():
        ax.annotate(row['district'][:10], (row['avg_walking_distance_m'], row['total_rooms']), fontsize=8)
    
    ax.set_xlabel('Average Walking Distance to Transit (m)')
    ax.set_ylabel('Number of Available Rooms')
    ax.set_title('RQ3: Walking Distance vs Room Availability by District')
    
    plt.tight_layout()
    return fig


def _create_rq4_bar(rq4_results: Dict) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(12, 6))
    
    platform_means = rq4_results.get('platform_means', {})
    if not platform_means:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    platforms = list(platform_means.keys())
    means = [platform_means[p]['mean'] for p in platforms]
    stds = [platform_means[p]['std'] for p in platforms]
    
    x = range(len(platforms))
    ax.bar(x, means, yerr=stds, capsize=5, color='steelblue', alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(platforms, rotation=45, ha='right')
    ax.set_ylabel('Average Commute Time (minutes)')
    ax.set_title('RQ4: Commute Time Comparison by Platform')
    
    plt.tight_layout()
    return fig


def _create_rq5_bar(df: pd.DataFrame) -> plt.Figure:
    from ..analysis.area import aggregate_housing_metrics
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    housing = aggregate_housing_metrics(df)
    if len(housing) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    sorted_df = housing.sort_values('total_rooms', ascending=False)
    
    ax.bar(sorted_df['district'], sorted_df['total_rooms'], color='steelblue', alpha=0.7)
    ax.set_xticklabels(sorted_df['district'], rotation=45, ha='right')
    ax.set_ylabel('Number of Rooms')
    ax.set_title('RQ5: Spatial Distribution of Student Housing by District')
    
    plt.tight_layout()
    return fig


def _create_rq6_scatter(df: pd.DataFrame) -> plt.Figure:
    """RQ6: Walkability vs Rent"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    plot_df = df[
        df['rent'].notna() &
        df['walkability_score'].notna() &
        (pd.to_numeric(df['rent'], errors='coerce') > 0) &
        (pd.to_numeric(df['walkability_score'], errors='coerce') >= 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    walkability = pd.to_numeric(plot_df['walkability_score'], errors='coerce').values
    rents = pd.to_numeric(plot_df['rent'], errors='coerce').values
    
    # Remove NaN
    valid_mask = ~(np.isnan(walkability) | np.isnan(rents))
    walkability = walkability[valid_mask]
    rents = rents[valid_mask]
    
    if len(walkability) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    ax.scatter(walkability, rents, alpha=0.5, s=30, c='green')
    
    z = np.polyfit(walkability, rents, 1)
    p = np.poly1d(z)
    x_line = np.linspace(walkability.min(), walkability.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label='Trend line')
    
    ax.set_xlabel('Walkability Score (0-100)')
    ax.set_ylabel('Rent (€/month)')
    ax.set_title('RQ6: Relationship between Walkability and Rent')
    ax.legend()
    
    plt.tight_layout()
    return fig


def _create_rq7_scatter(df: pd.DataFrame) -> plt.Figure:
    """RQ7: Walkability vs Commute Time"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    plot_df = df[
        df['walkability_score'].notna() &
        df['total_commute_minutes'].notna() &
        (pd.to_numeric(df['walkability_score'], errors='coerce') >= 0) &
        (pd.to_numeric(df['total_commute_minutes'], errors='coerce') > 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    walkability = pd.to_numeric(plot_df['walkability_score'], errors='coerce').values
    commutes = pd.to_numeric(plot_df['total_commute_minutes'], errors='coerce').values
    
    # Remove NaN
    valid_mask = ~(np.isnan(walkability) | np.isnan(commutes))
    walkability = walkability[valid_mask]
    commutes = commutes[valid_mask]
    
    if len(walkability) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    ax.scatter(walkability, commutes, alpha=0.5, s=30, c='purple')
    
    z = np.polyfit(walkability, commutes, 1)
    p = np.poly1d(z)
    x_line = np.linspace(walkability.min(), walkability.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label='Trend line')
    
    ax.set_xlabel('Walkability Score (0-100)')
    ax.set_ylabel('Commute Time (minutes)')
    ax.set_title('RQ7: Relationship between Walkability and Commute Time')
    ax.legend()
    
    plt.tight_layout()
    return fig


def _create_rq8_scatter(df: pd.DataFrame) -> plt.Figure:
    """RQ8: POI Density vs Room Availability"""
    from ..analysis.area import aggregate_housing_metrics, aggregate_transport_metrics
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    housing = aggregate_housing_metrics(df)
    transport = aggregate_transport_metrics(df)
    
    if len(housing) == 0 or len(transport) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    merged = pd.merge(housing, transport, on='district', how='inner')
    plot_df = merged[
        merged['avg_poi_density'].notna() & 
        merged['total_rooms'].notna() &
        (pd.to_numeric(merged['avg_poi_density'], errors='coerce') >= 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    poi_density = pd.to_numeric(plot_df['avg_poi_density'], errors='coerce').values
    rooms = pd.to_numeric(plot_df['total_rooms'], errors='coerce').values
    
    # Remove NaN
    valid_mask = ~(np.isnan(poi_density) | np.isnan(rooms))
    poi_density = poi_density[valid_mask]
    rooms = rooms[valid_mask]
    plot_df_valid = plot_df.iloc[valid_mask]
    
    if len(poi_density) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    ax.scatter(poi_density, rooms, s=100, c='orange', alpha=0.7)
    
    for idx, row in plot_df_valid.iterrows():
        ax.annotate(row['district'][:10], (row['avg_poi_density'], row['total_rooms']), fontsize=8)
    
    z = np.polyfit(poi_density, rooms, 1)
    p = np.poly1d(z)
    x_line = np.linspace(poi_density.min(), poi_density.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label='Trend line')
    
    ax.set_xlabel('Average POI Density (500m radius)')
    ax.set_ylabel('Number of Available Rooms')
    ax.set_title('RQ8: POI Density vs Room Availability by District')
    ax.legend()
    
    plt.tight_layout()
    return fig


def _create_rq9_scatter(df: pd.DataFrame) -> plt.Figure:
    """RQ9: Bike Accessibility vs Walkability"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    plot_df = df[
        df['bike_accessibility_score'].notna() &
        df['walkability_score'].notna() &
        (pd.to_numeric(df['bike_accessibility_score'], errors='coerce') >= 0) &
        (pd.to_numeric(df['walkability_score'], errors='coerce') >= 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    bike_scores = pd.to_numeric(plot_df['bike_accessibility_score'], errors='coerce').values
    walkability = pd.to_numeric(plot_df['walkability_score'], errors='coerce').values
    
    # Remove NaN
    valid_mask = ~(np.isnan(bike_scores) | np.isnan(walkability))
    bike_scores = bike_scores[valid_mask]
    walkability = walkability[valid_mask]
    
    if len(bike_scores) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    ax.scatter(bike_scores, walkability, alpha=0.5, s=30, c='teal')
    
    z = np.polyfit(bike_scores, walkability, 1)
    p = np.poly1d(z)
    x_line = np.linspace(bike_scores.min(), bike_scores.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label='Trend line')
    
    ax.set_xlabel('Bike Accessibility Score (0-100)')
    ax.set_ylabel('Walkability Score (0-100)')
    ax.set_title('RQ9: Relationship between Bike Accessibility and Walkability')
    ax.legend()
    
    plt.tight_layout()
    return fig


def _create_rq10_bar(rq10_results: Dict) -> plt.Figure:
    """RQ10: Multi-Modal Mobility by District"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    top_5 = rq10_results.get('top_5_districts', [])
    if not top_5:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    districts = [d['district'] for d in top_5]
    scores = [float(d.get('multimodal_score', 0)) for d in top_5]
    
    # Ensure scores are valid numbers
    scores = np.array([s for s in scores if not np.isnan(s) and s >= 0])
    districts = [districts[i] for i in range(len(districts)) if i < len(scores)]
    
    if len(scores) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    max_score = max(scores) if len(scores) > 0 else 100
    colors = plt.cm.RdYlGn(scores / max_score) if max_score > 0 else plt.cm.RdYlGn([0.5] * len(scores))
    ax.barh(districts, scores, color=colors, alpha=0.7)
    ax.set_xlabel('Multi-Modal Mobility Score (0-100)')
    ax.set_title('RQ10: Top 5 Districts by Multi-Modal Mobility')
    ax.set_xlim(0, 100)
    
    plt.tight_layout()
    return fig


def _create_rq11_scatter(df: pd.DataFrame) -> plt.Figure:
    """RQ11: Amenities vs Walkability"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    plot_df = df[
        df['walkability_score'].notna() &
        df['grocery_stores_500m'].notna() &
        df['cafes_500m'].notna() &
        (pd.to_numeric(df['walkability_score'], errors='coerce') >= 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    walkability = pd.to_numeric(plot_df['walkability_score'], errors='coerce').values
    grocery = pd.to_numeric(plot_df['grocery_stores_500m'], errors='coerce').values
    cafes = pd.to_numeric(plot_df['cafes_500m'], errors='coerce').values
    
    # Remove NaN
    valid_mask = ~(np.isnan(walkability) | np.isnan(grocery) | np.isnan(cafes))
    walkability = walkability[valid_mask]
    grocery = grocery[valid_mask]
    cafes = cafes[valid_mask]
    
    if len(walkability) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Create combined amenity score
    amenity_score = grocery + cafes
    
    ax.scatter(amenity_score, walkability, alpha=0.5, s=30, c='coral')
    
    z = np.polyfit(amenity_score, walkability, 1)
    p = np.poly1d(z)
    x_line = np.linspace(amenity_score.min(), amenity_score.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label='Trend line')
    
    ax.set_xlabel('Combined Amenities (Grocery Stores + Cafes)')
    ax.set_ylabel('Walkability Score')
    ax.set_title('RQ11: Relationship between Amenities and Walkability')
    ax.legend()
    plt.tight_layout()
    return fig


def _create_rq12_scatter(df: pd.DataFrame) -> plt.Figure:
    """RQ12: Bike Accessibility vs Commute Time"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    plot_df = df[
        df['bike_accessibility_score'].notna() &
        df['total_commute_minutes'].notna() &
        (pd.to_numeric(df['bike_accessibility_score'], errors='coerce') >= 0) &
        (pd.to_numeric(df['total_commute_minutes'], errors='coerce') > 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    bike_scores = pd.to_numeric(plot_df['bike_accessibility_score'], errors='coerce').values
    commutes = pd.to_numeric(plot_df['total_commute_minutes'], errors='coerce').values
    
    # Remove NaN
    valid_mask = ~(np.isnan(bike_scores) | np.isnan(commutes))
    bike_scores = bike_scores[valid_mask]
    commutes = commutes[valid_mask]
    
    if len(bike_scores) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    ax.scatter(bike_scores, commutes, alpha=0.5, s=30, c='cyan')
    
    z = np.polyfit(bike_scores, commutes, 1)
    p = np.poly1d(z)
    x_line = np.linspace(bike_scores.min(), bike_scores.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label='Trend line')
    
    ax.set_xlabel('Bike Accessibility Score')
    ax.set_ylabel('Commute Time (minutes)')
    ax.set_title('RQ12: Relationship between Bike Infrastructure and Commute Time')
    ax.legend()
    plt.tight_layout()
    return fig


def _create_rq13_bar(rq13_results: Dict, df: pd.DataFrame) -> plt.Figure:
    """RQ13: Walkability by District"""
    from ..analysis.area import aggregate_transport_metrics
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    transport_metrics = aggregate_transport_metrics(df)
    plot_df = transport_metrics[
        transport_metrics['avg_walkability_score'].notna() &
        (pd.to_numeric(transport_metrics['avg_walkability_score'], errors='coerce') >= 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    walkability = pd.to_numeric(plot_df['avg_walkability_score'], errors='coerce').values
    districts = plot_df['district'].values
    
    # Remove NaN
    valid_mask = ~np.isnan(walkability)
    walkability = walkability[valid_mask]
    districts = districts[valid_mask]
    plot_df = plot_df.iloc[valid_mask]
    
    if len(walkability) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Sort by walkability
    sorted_idx = np.argsort(walkability)
    districts_sorted = districts[sorted_idx]
    walkability_sorted = walkability[sorted_idx]
    
    colors = plt.cm.viridis(walkability_sorted / walkability_sorted.max() if walkability_sorted.max() > 0 else 0.5)
    ax.barh(districts_sorted, walkability_sorted, color=colors, alpha=0.7)
    ax.set_xlabel('Average Walkability Score')
    ax.set_title('RQ13: Walkability Variation Across Berlin Districts')
    plt.tight_layout()
    return fig


def _create_rq14_scatter(df: pd.DataFrame) -> plt.Figure:
    """RQ14: POI Density vs Walkability"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    plot_df = df[
        df['total_pois_500m'].notna() &
        df['walkability_score'].notna() &
        (pd.to_numeric(df['total_pois_500m'], errors='coerce') >= 0) &
        (pd.to_numeric(df['walkability_score'], errors='coerce') >= 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    poi_density = pd.to_numeric(plot_df['total_pois_500m'], errors='coerce').values
    walkability = pd.to_numeric(plot_df['walkability_score'], errors='coerce').values
    
    # Remove NaN
    valid_mask = ~(np.isnan(poi_density) | np.isnan(walkability))
    poi_density = poi_density[valid_mask]
    walkability = walkability[valid_mask]
    
    if len(poi_density) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    ax.scatter(poi_density, walkability, alpha=0.5, s=30, c='magenta')
    
    z = np.polyfit(poi_density, walkability, 1)
    p = np.poly1d(z)
    x_line = np.linspace(poi_density.min(), poi_density.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label='Trend line')
    
    ax.set_xlabel('POI Density (total POIs within 500m)')
    ax.set_ylabel('Walkability Score')
    ax.set_title('RQ14: Relationship between POI Density and Walkability')
    ax.legend()
    plt.tight_layout()
    return fig


def _create_rq15_scatter(df: pd.DataFrame) -> plt.Figure:
    """RQ15: Essential Services vs Room Availability"""
    from ..analysis.area import aggregate_housing_metrics, aggregate_transport_metrics
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    housing = aggregate_housing_metrics(df)
    transport = aggregate_transport_metrics(df)
    
    if len(housing) == 0 or len(transport) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    merged = pd.merge(housing, transport, on='district', how='inner')
    plot_df = merged[
        merged['avg_grocery_stores_500m'].notna() & 
        merged['total_rooms'].notna() &
        (pd.to_numeric(merged['avg_grocery_stores_500m'], errors='coerce') >= 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    grocery = pd.to_numeric(plot_df['avg_grocery_stores_500m'], errors='coerce').values
    rooms = pd.to_numeric(plot_df['total_rooms'], errors='coerce').values
    
    # Remove NaN
    valid_mask = ~(np.isnan(grocery) | np.isnan(rooms))
    grocery = grocery[valid_mask]
    rooms = rooms[valid_mask]
    plot_df_valid = plot_df.iloc[valid_mask]
    
    if len(grocery) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    ax.scatter(grocery, rooms, s=100, c='orange', alpha=0.7)
    
    for idx, row in plot_df_valid.iterrows():
        ax.annotate(row['district'][:10], (row['avg_grocery_stores_500m'], row['total_rooms']), fontsize=8)
    
    z = np.polyfit(grocery, rooms, 1)
    p = np.poly1d(z)
    x_line = np.linspace(grocery.min(), grocery.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label='Trend line')
    
    ax.set_xlabel('Average Grocery Stores within 500m')
    ax.set_ylabel('Total Rooms Available')
    ax.set_title('RQ15: Essential Services vs Room Availability')
    ax.legend()
    plt.tight_layout()
    return fig


def _create_rq16_scatter(df: pd.DataFrame) -> plt.Figure:
    """RQ16: Bike Accessibility vs Rent"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    plot_df = df[
        df['rent'].notna() &
        df['bike_accessibility_score'].notna() &
        (pd.to_numeric(df['rent'], errors='coerce') > 0) &
        (pd.to_numeric(df['bike_accessibility_score'], errors='coerce') >= 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    bike_scores = pd.to_numeric(plot_df['bike_accessibility_score'], errors='coerce').values
    rents = pd.to_numeric(plot_df['rent'], errors='coerce').values
    
    # Remove NaN
    valid_mask = ~(np.isnan(bike_scores) | np.isnan(rents))
    bike_scores = bike_scores[valid_mask]
    rents = rents[valid_mask]
    
    if len(bike_scores) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    ax.scatter(bike_scores, rents, alpha=0.5, s=30, c='lime')
    
    z = np.polyfit(bike_scores, rents, 1)
    p = np.poly1d(z)
    x_line = np.linspace(bike_scores.min(), bike_scores.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label='Trend line')
    
    ax.set_xlabel('Bike Accessibility Score')
    ax.set_ylabel('Rent (€/month)')
    ax.set_title('RQ16: Relationship between Bike Accessibility and Rent')
    ax.legend()
    plt.tight_layout()
    return fig


def _create_rq17_scatter(df: pd.DataFrame) -> plt.Figure:
    """RQ17: Walkability vs Transfers"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    plot_df = df[
        df['walkability_score'].notna() &
        df['transfers'].notna() &
        (pd.to_numeric(df['walkability_score'], errors='coerce') >= 0) &
        (pd.to_numeric(df['transfers'], errors='coerce') >= 0)
    ].copy()
    
    if len(plot_df) == 0:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Ensure numeric types
    walkability = pd.to_numeric(plot_df['walkability_score'], errors='coerce').values
    transfers = pd.to_numeric(plot_df['transfers'], errors='coerce').values
    
    # Remove NaN
    valid_mask = ~(np.isnan(walkability) | np.isnan(transfers))
    walkability = walkability[valid_mask]
    transfers = transfers[valid_mask]
    
    if len(walkability) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    ax.scatter(walkability, transfers, alpha=0.5, s=30, c='gold')
    
    z = np.polyfit(walkability, transfers, 1)
    p = np.poly1d(z)
    x_line = np.linspace(walkability.min(), walkability.max(), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label='Trend line')
    
    ax.set_xlabel('Walkability Score')
    ax.set_ylabel('Number of Transfers')
    ax.set_title('RQ17: Relationship between Walkability and Transfer Count')
    ax.legend()
    plt.tight_layout()
    return fig


def _create_rq18_bar(rq18_results: Dict) -> plt.Figure:
    """RQ18: Walkability-to-Affordability Ratio by District"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    top_5 = rq18_results.get('top_5_districts', [])
    if not top_5:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    districts = [d['district'] for d in top_5]
    ratios = [float(d.get('walkability_rent_ratio', 0)) for d in top_5]
    
    # Ensure ratios are valid numbers
    ratios = np.array([r for r in ratios if not np.isnan(r) and r >= 0])
    districts = [districts[i] for i in range(len(districts)) if i < len(ratios)]
    
    if len(ratios) == 0:
        ax.text(0.5, 0.5, 'No valid data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    
    max_ratio = max(ratios) if len(ratios) > 0 else 1
    colors = plt.cm.RdYlGn(ratios / max_ratio) if max_ratio > 0 else plt.cm.RdYlGn([0.5] * len(ratios))
    ax.barh(districts, ratios, color=colors, alpha=0.7)
    ax.set_xlabel('Walkability-to-Rent Ratio (Walkability Score per Euro)')
    ax.set_title('RQ18: Top 5 Districts by Walkability-to-Affordability Ratio')
    plt.tight_layout()
    return fig
