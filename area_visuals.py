import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import folium
from folium import plugins
import json
from typing import Dict, Optional, Tuple
from area_analysis import aggregate_housing_metrics, aggregate_transport_metrics

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
    
    for i, (idx, row) in enumerate(top_districts.iterrows()):
        score = row['student_area_score']
        ax.text(score + 0.01, i, f'{score:.3f}', va='center', fontsize=10)
    
    plt.tight_layout()
    return fig

def create_rooms_bar_chart(housing_metrics: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(12, 6))
    
    sorted_metrics = housing_metrics.sort_values('total_rooms', ascending=True)
    
    bars = ax.barh(
        sorted_metrics['district'],
        sorted_metrics['total_rooms'],
        color='coral'
    )
    
    ax.set_xlabel('Number of Rooms', fontsize=12, fontweight='bold')
    ax.set_title('Room Availability by Berlin District', fontsize=14, fontweight='bold')
    
    for i, (idx, row) in enumerate(sorted_metrics.iterrows()):
        rooms = row['total_rooms']
        ax.text(rooms + max(sorted_metrics['total_rooms']) * 0.01, i, 
                f'{int(rooms)}', va='center', fontsize=10)
    
    plt.tight_layout()
    return fig

def create_rent_vs_transport_scatter(ranked_areas: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 8))
    
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
    
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Student Area Score', fontsize=10)
    
    plt.tight_layout()
    return fig

def create_walking_distance_histogram(ranked_areas: pd.DataFrame) -> plt.Figure:
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
    m = folium.Map(
        location=[52.5200, 13.4050],
        zoom_start=11,
        tiles='OpenStreetMap'
    )
    
    max_score = ranked_areas['student_area_score'].max()
    min_score = ranked_areas['student_area_score'].min()
    
    for idx, row in ranked_areas.iterrows():
        district = row['district']
        score = row['student_area_score']
        
        if district in DISTRICT_COORDS:
            lat, lon = DISTRICT_COORDS[district]
            
            if max_score > min_score:
                normalized_score = (score - min_score) / (max_score - min_score)
            else:
                normalized_score = 0.5
            
            red = int(255 * (1 - normalized_score))
            green = int(255 * normalized_score)
            color = f'#{red:02x}{green:02x}00'
            
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
    ranked_areas = analysis_results['ranked_areas']
    housing_metrics = analysis_results['housing_metrics']
    
    if len(ranked_areas) == 0:
        return {}
    
    visuals = {
        'score_chart': create_score_bar_chart(ranked_areas, top_n=10),
        'rooms_chart': create_rooms_bar_chart(housing_metrics),
        'scatter_plot': create_rent_vs_transport_scatter(ranked_areas),
        'histogram': create_walking_distance_histogram(ranked_areas),
        'map': create_district_choropleth_map(ranked_areas)
    }
    
    return visuals

def create_research_question_charts(rq_results: Dict, df: pd.DataFrame) -> Dict:
    charts = {}
    
    if rq_results.get('RQ1_affordability_vs_accessibility', {}).get('status') == 'success':
        fig, ax = plt.subplots(figsize=(10, 6))
        
        analysis_df = df[
            df['rent'].notna() & 
            df['total_commute_minutes'].notna() &
            (pd.to_numeric(df['rent'], errors='coerce') > 0) &
            (pd.to_numeric(df['total_commute_minutes'], errors='coerce') > 0)
        ].copy()
        
        rents = pd.to_numeric(analysis_df['rent'], errors='coerce')
        commutes = pd.to_numeric(analysis_df['total_commute_minutes'], errors='coerce')
        
        ax.scatter(commutes, rents, alpha=0.5, s=50, c='steelblue', edgecolors='black', linewidth=0.5)
        
        z = np.polyfit(commutes, rents, 1)
        p = np.poly1d(z)
        ax.plot(commutes, p(commutes), "r--", alpha=0.8, linewidth=2, label='Trend Line')
        
        result = rq_results['RQ1_affordability_vs_accessibility']
        ax.set_xlabel('Commute Time (minutes)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Rent (€/month)', fontsize=12, fontweight='bold')
        ax.set_title(f'Rent vs Commute Time\n(r={result["correlation_coefficient"]:.3f}, p={result["p_value"]:.4f})', 
                    fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend()
        plt.tight_layout()
        charts['rq1_scatter'] = fig
    
    if rq_results.get('RQ3_walking_vs_availability', {}).get('status') == 'success':
        fig, ax = plt.subplots(figsize=(10, 6))
        
        housing_metrics = aggregate_housing_metrics(df)
        transport_metrics = aggregate_transport_metrics(df)
        merged = pd.merge(housing_metrics, transport_metrics, on='district', how='inner')
        analysis_df = merged[
            merged['avg_walking_distance_m'].notna() & 
            merged['total_rooms'].notna() &
            (merged['avg_walking_distance_m'] > 0)
        ].copy()
        
        ax.scatter(analysis_df['avg_walking_distance_m'], analysis_df['total_rooms'], 
                  alpha=0.7, s=100, c='coral', edgecolors='black', linewidth=1)
        
        walking = analysis_df['avg_walking_distance_m'].values
        rooms = analysis_df['total_rooms'].values
        z = np.polyfit(walking, rooms, 1)
        p = np.poly1d(z)
        ax.plot(walking, p(walking), "r--", alpha=0.8, linewidth=2, label='Trend Line')
        
        result = rq_results['RQ3_walking_vs_availability']
        ax.set_xlabel('Average Walking Distance to Stop (meters)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Total Rooms Available', fontsize=12, fontweight='bold')
        ax.set_title(f'Walking Distance vs Room Availability\n(R²={result["r_squared"]:.3f}, p={result["p_value"]:.4f})', 
                    fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend()
        plt.tight_layout()
        charts['rq3_scatter'] = fig
    
    if rq_results.get('RQ4_platform_differences', {}).get('status') == 'success':
        fig, ax = plt.subplots(figsize=(12, 6))
        
        result = rq_results['RQ4_platform_differences']
        platform_means = result.get('platform_means', {})
        
        if platform_means:
            platforms = list(platform_means.keys())
            means = [platform_means[p]['mean'] for p in platforms]
            stds = [platform_means[p]['std'] for p in platforms]
            
            bars = ax.bar(platforms, means, yerr=stds, capsize=5, color='steelblue', alpha=0.7, edgecolor='black')
            
            ax.set_xlabel('Platform', fontsize=12, fontweight='bold')
            ax.set_ylabel('Average Commute Time (minutes)', fontsize=12, fontweight='bold')
            ax.set_title(f'Platform Comparison - Commute Times\n(F={result["f_statistic"]:.3f}, p={result["p_value"]:.4f})', 
                        fontsize=14, fontweight='bold')
            ax.tick_params(axis='x', rotation=45)
            ax.grid(True, alpha=0.3, axis='y')
            
            for i, (bar, mean) in enumerate(zip(bars, means)):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + stds[i] + 1,
                       f'{mean:.1f}', ha='center', va='bottom', fontsize=9)
            
            plt.tight_layout()
            charts['rq4_bar'] = fig
    
    if rq_results.get('RQ5_spatial_equity', {}).get('status') == 'success':
        fig, ax = plt.subplots(figsize=(12, 6))
        
        housing_metrics = aggregate_housing_metrics(df)
        housing_metrics = housing_metrics.sort_values('total_rooms', ascending=True)
        
        bars = ax.barh(housing_metrics['district'], housing_metrics['total_rooms'], 
                      color='skyblue', edgecolor='black', alpha=0.7)
        
        result = rq_results['RQ5_spatial_equity']
        ax.set_xlabel('Number of Rooms', fontsize=12, fontweight='bold')
        ax.set_ylabel('District', fontsize=12, fontweight='bold')
        ax.set_title(f'Spatial Equity - Room Distribution\n(Gini={result["gini_coefficient"]:.3f}, {result["equity_level"]})', 
                    fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='x')
        
        for i, (idx, row) in enumerate(housing_metrics.iterrows()):
            ax.text(row['total_rooms'] + max(housing_metrics['total_rooms']) * 0.01, i,
                   f'{int(row["total_rooms"])}', va='center', fontsize=10)
        
        plt.tight_layout()
        charts['rq5_bar'] = fig
    
    return charts

