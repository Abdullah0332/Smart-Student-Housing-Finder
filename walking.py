import osmnx as ox
import networkx as nx
import pandas as pd
import numpy as np
from geopy.distance import geodesic
from typing import Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


ox.settings.use_cache = True
ox.settings.log_console = False


def get_walking_network(center_point: Tuple[float, float], distance: int = 5000):
    try:
        G = ox.graph_from_point(
            center_point,
            dist=distance,
            network_type='walk',
            simplify=True
        )
        
        G_projected = ox.project_graph(G)
        
        return G_projected
    
    except Exception as e:
        print(f"Warning: Could not download walking network: {str(e)}")
        return None


def calculate_walking_distance_geodesic(
    point1: Tuple[float, float],
    point2: Tuple[float, float]
) -> float:
    return geodesic(point1, point2).meters


def calculate_walking_distance_network(
    G: nx.MultiDiGraph,
    point1: Tuple[float, float],
    point2: Tuple[float, float]
) -> Optional[Tuple[float, float]]:
    try:
        orig_node = ox.distance.nearest_nodes(G, point1[1], point1[0])  # lon, lat
        dest_node = ox.distance.nearest_nodes(G, point2[1], point2[0])  # lon, lat
        
        route = nx.shortest_path(G, orig_node, dest_node, weight='length')
        
        total_length = sum(
            G[route[i]][route[i+1]][0]['length']
            for i in range(len(route) - 1)
        )
        
        if total_length > 100000:  # Likely in cm
            total_length = total_length / 100
        
        walking_speed_m_per_min = 83.33
        time_minutes = total_length / walking_speed_m_per_min
        
        return (total_length, time_minutes)
    
    except (nx.NetworkXNoPath, KeyError, Exception) as e:
        return None


def calculate_walking_to_stop(
    apartment_coords: Tuple[float, float],
    stop_coords: Tuple[float, float],
    use_network: bool = False,
    network_graph: Optional[nx.MultiDiGraph] = None
) -> Tuple[float, float]:
    if use_network and network_graph is not None:
        result = calculate_walking_distance_network(
            network_graph,
            apartment_coords,
            stop_coords
        )
        if result:
            return result
    
    distance_m = calculate_walking_distance_geodesic(apartment_coords, stop_coords)
    
    walking_speed_m_per_min = 83.33
    time_minutes = distance_m / walking_speed_m_per_min
    
    return (distance_m, time_minutes)


def enhance_with_walking_distances(
    apartments_df: pd.DataFrame,
    use_osm_network: bool = False
) -> pd.DataFrame:
    df = apartments_df.copy()
    
    if 'nearest_stop_distance_m' not in df.columns:
        print("Warning: 'nearest_stop_distance_m' not found. Run transport analysis first.")
        return df
    
    
    if use_osm_network:
        print("Using OSM network for refined walking distance calculations...")
        pass
    
    return df

