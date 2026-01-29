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
    """Only RQ1–RQ5 charts."""
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
    
    commutes = pd.to_numeric(plot_df['total_commute_minutes'], errors='coerce').values
    rents = pd.to_numeric(plot_df['rent'], errors='coerce').values
    
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
    
    walking = pd.to_numeric(plot_df['avg_walking_distance_m'], errors='coerce').values
    rooms = pd.to_numeric(plot_df['total_rooms'], errors='coerce').values
    
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


def create_five_walkability_mobility_charts(df: pd.DataFrame) -> Dict[str, plt.Figure]:
    """Create exactly 5 charts on Walkability–Mobility relationship (POI, transit, commute, bike, districts)."""
    from ..analysis.area import aggregate_transport_metrics
    charts = {}
    transport = aggregate_transport_metrics(df)

    f1 = _wm_poi_vs_walkability(df)
    if f1 is not None:
        charts['wm_1_poi_vs_walkability'] = f1
    f2 = _wm_transit_vs_walkability(df)
    if f2 is not None:
        charts['wm_2_transit_vs_walkability'] = f2
    f3 = _wm_walkability_vs_commute(df)
    if f3 is not None:
        charts['wm_3_walkability_vs_commute'] = f3
    f4 = _wm_bike_vs_walkability(df)
    if f4 is not None:
        charts['wm_4_bike_vs_walkability'] = f4
    f5 = _wm_district_walkability_commute(transport)
    if f5 is not None:
        charts['wm_5_district_walkability_commute'] = f5
    return charts


def _wm_poi_vs_walkability(df: pd.DataFrame) -> Optional[plt.Figure]:
    """Graph 1: POI count (500 m) vs Walkability. More POIs → higher walkability."""
    fig, ax = plt.subplots(figsize=(10, 6))
    d = df[df['total_pois_500m'].notna() & df['walkability_score'].notna()].copy()
    d['poi'] = pd.to_numeric(d['total_pois_500m'], errors='coerce')
    d['walk'] = pd.to_numeric(d['walkability_score'], errors='coerce')
    d = d.dropna(subset=['poi', 'walk'])
    if len(d) < 5:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    ax.scatter(d['poi'], d['walk'], alpha=0.5, s=30, c='#3498db')
    z = np.polyfit(d['poi'], d['walk'], 1)
    xl = np.linspace(d['poi'].min(), d['poi'].max(), 100)
    ax.plot(xl, np.poly1d(z)(xl), 'r--', alpha=0.8, label='Trend')
    ax.set_xlabel('POI count within 500 m')
    ax.set_ylabel('Walkability score (0–100)')
    ax.set_title('1. POI vs Walkability — More amenities → higher walkability')
    ax.legend()
    ax.set_xlim(left=0)
    plt.tight_layout()
    return fig


def _wm_transit_vs_walkability(df: pd.DataFrame) -> Optional[plt.Figure]:
    """Graph 2: Walking distance to transit vs Walkability. Closer to transit → higher walkability."""
    fig, ax = plt.subplots(figsize=(10, 6))
    d = df[df['nearest_stop_distance_m'].notna() & df['walkability_score'].notna()].copy()
    d['dist'] = pd.to_numeric(d['nearest_stop_distance_m'], errors='coerce')
    d['walk'] = pd.to_numeric(d['walkability_score'], errors='coerce')
    d = d[(d['dist'] > 0) & d['walk'].notna()].dropna(subset=['dist', 'walk'])
    if len(d) < 5:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    ax.scatter(d['dist'], d['walk'], alpha=0.5, s=30, c='#2ecc71')
    z = np.polyfit(d['dist'], d['walk'], 1)
    xl = np.linspace(d['dist'].min(), d['dist'].max(), 100)
    ax.plot(xl, np.poly1d(z)(xl), 'r--', alpha=0.8, label='Trend')
    ax.set_xlabel('Walking distance to nearest transit stop (m)')
    ax.set_ylabel('Walkability score (0–100)')
    ax.set_title('2. Transit access vs Walkability — Closer to transit → higher walkability')
    ax.legend()
    ax.set_xlim(left=0)
    plt.tight_layout()
    return fig


def _wm_walkability_vs_commute(df: pd.DataFrame) -> Optional[plt.Figure]:
    """Graph 3: Walkability vs Commute time. Relationship between walkability and mobility."""
    fig, ax = plt.subplots(figsize=(10, 6))
    d = df[df['walkability_score'].notna() & df['total_commute_minutes'].notna()].copy()
    d['walk'] = pd.to_numeric(d['walkability_score'], errors='coerce')
    d['commute'] = pd.to_numeric(d['total_commute_minutes'], errors='coerce')
    d = d[(d['commute'] > 0) & d['walk'].notna()].dropna(subset=['walk', 'commute'])
    if len(d) < 5:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    ax.scatter(d['walk'], d['commute'], alpha=0.5, s=30, c='#9b59b6')
    z = np.polyfit(d['walk'], d['commute'], 1)
    xl = np.linspace(d['walk'].min(), d['walk'].max(), 100)
    ax.plot(xl, np.poly1d(z)(xl), 'r--', alpha=0.8, label='Trend')
    ax.set_xlabel('Walkability score (0–100)')
    ax.set_ylabel('Commute time (min)')
    ax.set_title('3. Walkability vs Commute — How walkability relates to mobility (commute)')
    ax.legend()
    plt.tight_layout()
    return fig


def _wm_bike_vs_walkability(df: pd.DataFrame) -> Optional[plt.Figure]:
    """Graph 4: Bike accessibility vs Walkability. Better bike infra → higher walkability."""
    fig, ax = plt.subplots(figsize=(10, 6))
    d = df[df['bike_accessibility_score'].notna() & df['walkability_score'].notna()].copy()
    d['bike'] = pd.to_numeric(d['bike_accessibility_score'], errors='coerce')
    d['walk'] = pd.to_numeric(d['walkability_score'], errors='coerce')
    d = d[(d['bike'] >= 0) & d['walk'].notna()].dropna(subset=['bike', 'walk'])
    if len(d) < 5:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return fig
    ax.scatter(d['bike'], d['walk'], alpha=0.5, s=30, c='#e67e22')
    z = np.polyfit(d['bike'], d['walk'], 1)
    xl = np.linspace(d['bike'].min(), d['bike'].max(), 100)
    ax.plot(xl, np.poly1d(z)(xl), 'r--', alpha=0.8, label='Trend')
    ax.set_xlabel('Bike accessibility score (0–100)')
    ax.set_ylabel('Walkability score (0–100)')
    ax.set_title('4. Bike vs Walkability — Better bike infra → higher walkability')
    ax.legend()
    plt.tight_layout()
    return fig


def _wm_district_walkability_commute(transport: pd.DataFrame) -> Optional[plt.Figure]:
    """Graph 5: District-level Walkability vs Commute. Best districts = high walkability + short commute."""
    fig, ax = plt.subplots(figsize=(10, 6))
    d = transport[transport['avg_walkability_score'].notna() & transport['avg_commute_minutes'].notna()].copy()
    d['walk'] = pd.to_numeric(d['avg_walkability_score'], errors='coerce')
    d['commute'] = pd.to_numeric(d['avg_commute_minutes'], errors='coerce')
    d = d.dropna(subset=['walk', 'commute'])
    if len(d) < 3:
        return None
    ax.scatter(d['walk'], d['commute'], s=80, c='#1abc9c', alpha=0.8, edgecolors='#16a085')
    for _, r in d.iterrows():
        ax.annotate(r['district'][:12], (r['walk'], r['commute']), fontsize=8, alpha=0.9)
    z = np.polyfit(d['walk'], d['commute'], 1)
    xl = np.linspace(d['walk'].min(), d['walk'].max(), 50)
    ax.plot(xl, np.poly1d(z)(xl), 'r--', alpha=0.8, label='Trend')
    ax.set_xlabel('Avg walkability score')
    ax.set_ylabel('Avg commute time (min)')
    ax.set_title('5. District-level: Walkability vs Commute — Top-right = best of both')
    ax.legend()
    plt.tight_layout()
    return fig
