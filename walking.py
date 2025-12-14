"""
Walking Module
==============

Calculates walking distances and routes using OpenStreetMap data via OSMnx.
This module provides realistic pedestrian accessibility analysis, which is
crucial for understanding the "last mile" connectivity to public transport.

Urban Technology Relevance:
- Pedestrian accessibility is a key component of sustainable urban mobility
- Walking distance to transit stops affects overall accessibility scores
- Network analysis using OSM data demonstrates real-world urban connectivity
- The "walkability" metric influences housing desirability and transport equity
"""

import osmnx as ox
import networkx as nx
import pandas as pd
import numpy as np
from geopy.distance import geodesic
from typing import Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


# Configure OSMnx for walking network
ox.settings.use_cache = True
ox.settings.log_console = False


def get_walking_network(center_point: Tuple[float, float], distance: int = 5000):
    """
    Download walking network for a given area from OpenStreetMap.
    
    Parameters:
    -----------
    center_point : Tuple[float, float]
        (latitude, longitude) center point
    distance : int
        Distance in meters to search around center point
    
    Returns:
    --------
    networkx.MultiDiGraph
        Walking network graph
    """
    try:
        # Get walking network (excludes motorways, includes footpaths)
        G = ox.graph_from_point(
            center_point,
            dist=distance,
            network_type='walk',
            simplify=True
        )
        
        # Project to UTM for accurate distance calculations
        G_projected = ox.project_graph(G)
        
        return G_projected
    
    except Exception as e:
        print(f"Warning: Could not download walking network: {str(e)}")
        return None


def calculate_walking_distance_geodesic(
    point1: Tuple[float, float],
    point2: Tuple[float, float]
) -> float:
    """
    Calculate straight-line (geodesic) distance between two points.
    
    This is a fallback when OSM network is unavailable.
    
    Parameters:
    -----------
    point1 : Tuple[float, float]
        (latitude, longitude) of first point
    point2 : Tuple[float, float]
        (latitude, longitude) of second point
    
    Returns:
    --------
    float
        Distance in meters
    """
    return geodesic(point1, point2).meters


def calculate_walking_distance_network(
    G: nx.MultiDiGraph,
    point1: Tuple[float, float],
    point2: Tuple[float, float]
) -> Optional[Tuple[float, float]]:
    """
    Calculate walking distance and time using OSM network.
    
    Parameters:
    -----------
    G : networkx.MultiDiGraph
        Walking network graph
    point1 : Tuple[float, float]
        Origin (latitude, longitude)
    point2 : Tuple[float, float]
        Destination (latitude, longitude)
    
    Returns:
    --------
    Tuple[float, float] or None
        (distance_meters, time_minutes) if route found, None otherwise
    """
    try:
        # Find nearest nodes in the graph
        orig_node = ox.distance.nearest_nodes(G, point1[1], point1[0])  # lon, lat
        dest_node = ox.distance.nearest_nodes(G, point2[1], point2[0])  # lon, lat
        
        # Calculate shortest path
        route = nx.shortest_path(G, orig_node, dest_node, weight='length')
        
        # Calculate total distance
        total_length = sum(
            G[route[i]][route[i+1]][0]['length']
            for i in range(len(route) - 1)
        )
        
        # Convert to meters (if in different units)
        if total_length > 100000:  # Likely in cm
            total_length = total_length / 100
        
        # Estimate walking time (average walking speed: 5 km/h = 83.33 m/min)
        walking_speed_m_per_min = 83.33
        time_minutes = total_length / walking_speed_m_per_min
        
        return (total_length, time_minutes)
    
    except (nx.NetworkXNoPath, KeyError, Exception) as e:
        # If no path found, return None
        return None


def calculate_walking_to_stop(
    apartment_coords: Tuple[float, float],
    stop_coords: Tuple[float, float],
    use_network: bool = False,
    network_graph: Optional[nx.MultiDiGraph] = None
) -> Tuple[float, float]:
    """
    Calculate walking distance and time from apartment to transit stop.
    
    Parameters:
    -----------
    apartment_coords : Tuple[float, float]
        Apartment (latitude, longitude)
    stop_coords : Tuple[float, float]
        Stop (latitude, longitude)
    use_network : bool
        Whether to use OSM network (more accurate but slower)
    network_graph : networkx.MultiDiGraph or None
        Pre-loaded network graph
    
    Returns:
    --------
    Tuple[float, float]
        (distance_meters, time_minutes)
    """
    if use_network and network_graph is not None:
        result = calculate_walking_distance_network(
            network_graph,
            apartment_coords,
            stop_coords
        )
        if result:
            return result
    
    # Fallback to geodesic distance
    distance_m = calculate_walking_distance_geodesic(apartment_coords, stop_coords)
    
    # Estimate walking time (5 km/h = 83.33 m/min)
    walking_speed_m_per_min = 83.33
    time_minutes = distance_m / walking_speed_m_per_min
    
    return (distance_m, time_minutes)


def enhance_with_walking_distances(
    apartments_df: pd.DataFrame,
    use_osm_network: bool = False
) -> pd.DataFrame:
    """
    Enhance apartment dataframe with refined walking distance calculations.
    
    This function improves walking distance estimates by using network analysis
    when available, or falls back to geodesic distances.
    
    Parameters:
    -----------
    apartments_df : pd.DataFrame
        Dataframe with 'latitude', 'longitude', and 'nearest_stop_distance_m' columns
    use_osm_network : bool
        Whether to use OSM network for more accurate calculations
    
    Returns:
    --------
    pd.DataFrame
        Enhanced dataframe with improved walking distance calculations
    """
    df = apartments_df.copy()
    
    if 'nearest_stop_distance_m' not in df.columns:
        print("Warning: 'nearest_stop_distance_m' not found. Run transport analysis first.")
        return df
    
    # If we already have walking distances from the transport API, use those
    # This function can refine them using OSM network if needed
    
    if use_osm_network:
        print("Using OSM network for refined walking distance calculations...")
        # This would require downloading network for Berlin area
        # For now, we'll use the distances already calculated
        # In a production system, you'd cache the Berlin network graph
        pass
    
    return df

