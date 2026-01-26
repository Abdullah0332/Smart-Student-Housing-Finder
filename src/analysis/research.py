import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict

from .area import analyze_best_areas, aggregate_housing_metrics, aggregate_transport_metrics

RESEARCH_QUESTIONS = {
    "RQ1": {
        "question": "How does public transport accessibility affect housing affordability in Berlin?",
        "hypothesis": "Housing prices are inversely correlated with commute time to universities",
        "quantifiable_metric": "Pearson correlation coefficient between rent and commute time",
        "expected_result": "Negative correlation (shorter commute = higher rent)"
    },
    "RQ2": {
        "question": "Which Berlin districts offer the best transport-housing balance for students?",
        "hypothesis": "Some districts combine good transport access with affordable housing",
        "quantifiable_metric": "Student Area Score ranking by district (includes walkability)",
        "expected_result": "Ranked list of districts with composite scores"
    },
    "RQ3": {
        "question": "What is the relationship between walking distance to transit and room availability?",
        "hypothesis": "Areas closer to transit have more available rooms",
        "quantifiable_metric": "Linear regression R² and slope coefficient",
        "expected_result": "Positive correlation (closer to transit = more rooms)"
    },
    "RQ4": {
        "question": "How do different platforms vary in terms of transport accessibility?",
        "hypothesis": "Different platforms target different accessibility profiles",
        "quantifiable_metric": "ANOVA F-statistic and mean commute times per platform",
        "expected_result": "Statistically significant differences between platforms"
    },
    "RQ5": {
        "question": "What is the spatial equity of student housing in Berlin?",
        "hypothesis": "Student housing is unequally distributed across Berlin districts",
        "quantifiable_metric": "Gini coefficient and spatial autocorrelation",
        "expected_result": "Gini coefficient > 0.3 indicates inequality"
    },
    "RQ6": {
        "question": "How does walkability affect housing prices in Berlin?",
        "hypothesis": "Higher walkability scores are positively correlated with rent (premium for walkable areas)",
        "quantifiable_metric": "Pearson correlation coefficient between rent and walkability score",
        "expected_result": "Positive correlation (higher walkability = higher rent)"
    },
    "RQ7": {
        "question": "What is the relationship between walkability and commute time?",
        "hypothesis": "More walkable areas have shorter commute times due to better transit access",
        "quantifiable_metric": "Pearson correlation coefficient between walkability score and commute time",
        "expected_result": "Negative correlation (higher walkability = shorter commute)"
    },
    "RQ8": {
        "question": "How do POI density and amenities affect student housing preferences?",
        "hypothesis": "Areas with more amenities (POIs) have more student housing options",
        "quantifiable_metric": "Linear regression R² between POI density and room availability",
        "expected_result": "Positive correlation (more POIs = more rooms)"
    },
    "RQ9": {
        "question": "What is the relationship between bike accessibility and walkability?",
        "hypothesis": "Areas with better bike infrastructure also have higher walkability scores",
        "quantifiable_metric": "Pearson correlation coefficient between bike and walkability scores",
        "expected_result": "Positive correlation (better bike access = higher walkability)"
    },
    "RQ10": {
        "question": "Which districts offer the best multi-modal mobility (walk + bike + transit)?",
        "hypothesis": "Some districts excel in multiple mobility modes simultaneously",
        "quantifiable_metric": "Composite mobility score ranking by district",
        "expected_result": "Ranked list of districts with best multi-modal access"
    },
    "RQ11": {
        "question": "How do specific amenities (grocery stores, cafes) contribute to walkability scores?",
        "hypothesis": "Areas with more essential amenities (grocery stores, cafes) have higher walkability scores",
        "quantifiable_metric": "Multiple regression R² between amenity counts and walkability score",
        "expected_result": "Positive correlation (more amenities = higher walkability)"
    },
    "RQ12": {
        "question": "What is the relationship between bike infrastructure and commute time?",
        "hypothesis": "Areas with better bike infrastructure have shorter commute times",
        "quantifiable_metric": "Pearson correlation coefficient between bike accessibility and commute time",
        "expected_result": "Negative correlation (better bike access = shorter commute)"
    },
    "RQ13": {
        "question": "How does walkability vary across Berlin districts?",
        "hypothesis": "Walkability scores vary significantly between districts",
        "quantifiable_metric": "ANOVA F-statistic and mean walkability scores by district",
        "expected_result": "Statistically significant differences between districts"
    },
    "RQ14": {
        "question": "What is the relationship between POI density and walkability score?",
        "hypothesis": "Higher POI density is strongly correlated with higher walkability scores",
        "quantifiable_metric": "Pearson correlation coefficient between POI density and walkability",
        "expected_result": "Strong positive correlation (more POIs = higher walkability)"
    },
    "RQ15": {
        "question": "How do essential services (grocery stores, pharmacies) affect housing preferences?",
        "hypothesis": "Proximity to essential services influences student housing choices",
        "quantifiable_metric": "Correlation between essential service counts and room availability",
        "expected_result": "Positive correlation (more essential services = more rooms)"
    },
    "RQ16": {
        "question": "What is the relationship between bike accessibility and housing prices?",
        "hypothesis": "Areas with better bike infrastructure command higher rents",
        "quantifiable_metric": "Pearson correlation coefficient between bike accessibility score and rent",
        "expected_result": "Positive correlation (better bike access = higher rent)"
    },
    "RQ17": {
        "question": "How does walkability affect the number of transfers needed for commute?",
        "hypothesis": "More walkable areas require fewer transfers due to better transit connectivity",
        "quantifiable_metric": "Pearson correlation coefficient between walkability and transfer count",
        "expected_result": "Negative correlation (higher walkability = fewer transfers)"
    },
    "RQ18": {
        "question": "Which districts offer the best walkability-to-affordability ratio?",
        "hypothesis": "Some districts combine high walkability with affordable housing",
        "quantifiable_metric": "Walkability-to-rent ratio ranking by district",
        "expected_result": "Ranked list of districts with best walkability per euro"
    }
}


def analyze_rq1_affordability_vs_accessibility(df: pd.DataFrame) -> Dict:
    analysis_df = df[
        df['rent'].notna() &
        df['total_commute_minutes'].notna() &
        (pd.to_numeric(df['rent'], errors='coerce') > 0) &
        (pd.to_numeric(df['total_commute_minutes'], errors='coerce') > 0)
    ].copy()
    
    if len(analysis_df) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 rooms with both rent and commute data'}
    
    rents = pd.to_numeric(analysis_df['rent'], errors='coerce')
    commutes = pd.to_numeric(analysis_df['total_commute_minutes'], errors='coerce')
    
    # Remove NaN values first
    valid_mask = rents.notna() & commutes.notna()
    rents_clean = rents[valid_mask]
    commutes_clean = commutes[valid_mask]
    
    if len(rents_clean) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 valid data points after cleaning'}
    
    # Remove outliers
    rent_mean, rent_std = rents_clean.mean(), rents_clean.std()
    commute_mean, commute_std = commutes_clean.mean(), commutes_clean.std()
    
    if rent_std > 0 and commute_std > 0:
        outlier_mask = (
            (rents_clean >= rent_mean - 3*rent_std) & (rents_clean <= rent_mean + 3*rent_std) &
            (commutes_clean >= commute_mean - 3*commute_std) & (commutes_clean <= commute_mean + 3*commute_std)
        )
        rents_clean = rents_clean[outlier_mask]
        commutes_clean = commutes_clean[outlier_mask]
    
    if len(rents_clean) < 10:
        rents_clean = rents[rents.notna() & commutes.notna()]
        commutes_clean = commutes[rents.notna() & commutes.notna()]
    
    # Ensure numeric arrays
    rents_clean = rents_clean.values.astype(float)
    commutes_clean = commutes_clean.values.astype(float)
    
    correlation, p_value = stats.pearsonr(rents_clean, commutes_clean)
    
    strength = _interpret_correlation_strength(abs(correlation))
    direction = "negative" if correlation < 0 else "positive"
    significant = p_value < 0.05
    
    return {
        'status': 'success',
        'correlation_coefficient': float(correlation),
        'p_value': float(p_value),
        'statistically_significant': significant,
        'strength': strength,
        'direction': direction,
        'sample_size': len(rents_clean),
        'interpretation': f"There is a {strength} {direction} correlation (r={correlation:.3f}) between rent and commute time. "
                         f"This relationship is {'statistically significant' if significant else 'not statistically significant'} (p={p_value:.4f})."
    }


def analyze_rq2_district_balance(df: pd.DataFrame) -> Dict:
    try:
        results = analyze_best_areas(df)
        ranked_areas = results['ranked_areas']
        
        if len(ranked_areas) == 0:
            return {'status': 'insufficient_data', 'message': 'No district data available'}
        
        top_5 = ranked_areas.head(5)
        
        return {
            'status': 'success',
            'top_5_districts': top_5[['district', 'student_area_score', 'avg_rent', 'avg_commute_minutes']].to_dict('records'),
            'total_districts_analyzed': len(ranked_areas),
            'interpretation': "Top 5 districts ranked by composite Student Area Score combining affordability, commute time, walking distance, and room availability."
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def analyze_rq3_walking_vs_availability(df: pd.DataFrame) -> Dict:
    try:
        housing_metrics = aggregate_housing_metrics(df)
        transport_metrics = aggregate_transport_metrics(df)
        
        if len(housing_metrics) == 0 or len(transport_metrics) == 0:
            return {'status': 'insufficient_data', 'message': 'Need district-level aggregation'}
        
        merged = pd.merge(housing_metrics, transport_metrics, on='district', how='inner')
        
        analysis_df = merged[
            merged['avg_walking_distance_m'].notna() &
            merged['total_rooms'].notna() &
            (merged['avg_walking_distance_m'] > 0)
        ].copy()
        
        if len(analysis_df) < 5:
            return {'status': 'insufficient_data', 'message': 'Need at least 5 districts with data'}
        
        # Ensure numeric types
        walking = pd.to_numeric(analysis_df['avg_walking_distance_m'], errors='coerce').values
        rooms = pd.to_numeric(analysis_df['total_rooms'], errors='coerce').values
        
        # Remove NaN values
        valid_mask = ~(np.isnan(walking) | np.isnan(rooms))
        walking = walking[valid_mask].astype(float)
        rooms = rooms[valid_mask].astype(float)
        
        if len(walking) < 5:
            return {'status': 'insufficient_data', 'message': 'Need at least 5 valid data points after cleaning'}
        
        slope, intercept, r_value, p_value, std_err = stats.linregress(walking, rooms)
        r_squared = r_value ** 2
        
        fit_quality = _interpret_r_squared(r_squared)
        significant = p_value < 0.05
        
        return {
            'status': 'success',
            'r_squared': float(r_squared),
            'slope': float(slope),
            'intercept': float(intercept),
            'p_value': float(p_value),
            'statistically_significant': significant,
            'fit_quality': fit_quality,
            'sample_size': len(analysis_df),
            'interpretation': f"Walking distance explains {r_squared*100:.1f}% of variance in room availability (R²={r_squared:.3f}). "
                             f"The relationship is {'statistically significant' if significant else 'not statistically significant'} (p={p_value:.4f}). "
                             f"Slope: {slope:.2f} rooms per meter (negative = closer to transit = more rooms)."
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def analyze_rq4_platform_differences(df: pd.DataFrame) -> Dict:
    if 'provider' not in df.columns or 'total_commute_minutes' not in df.columns:
        return {'status': 'insufficient_data', 'message': 'Missing provider or commute data'}
    
    analysis_df = df[
        df['provider'].notna() &
        df['total_commute_minutes'].notna() &
        (pd.to_numeric(df['total_commute_minutes'], errors='coerce') > 0)
    ].copy()
    
    analysis_df['commute'] = pd.to_numeric(analysis_df['total_commute_minutes'], errors='coerce')
    
    # Remove NaN values
    analysis_df = analysis_df[analysis_df['commute'].notna()].copy()
    
    platform_counts = analysis_df['provider'].value_counts()
    valid_platforms = platform_counts[platform_counts >= 5].index.tolist()
    
    if len(valid_platforms) < 2:
        return {'status': 'insufficient_data', 'message': 'Need at least 2 platforms with 5+ rooms each'}
    
    analysis_df = analysis_df[analysis_df['provider'].isin(valid_platforms)]
    
    platform_groups = []
    for platform in valid_platforms:
        platform_data = analysis_df[analysis_df['provider'] == platform]['commute'].values
        # Ensure numeric and remove NaN
        platform_data = pd.to_numeric(platform_data, errors='coerce')
        platform_data = platform_data[~np.isnan(platform_data)].astype(float)
        if len(platform_data) > 0:
            platform_groups.append(platform_data)
    
    if len(platform_groups) < 2:
        return {'status': 'insufficient_data', 'message': 'Need at least 2 platforms with valid numeric data'}
    
    f_statistic, p_value = stats.f_oneway(*platform_groups)
    platform_means = analysis_df.groupby('provider')['commute'].agg(['mean', 'std', 'count']).to_dict('index')
    significant = p_value < 0.05
    
    return {
        'status': 'success',
        'f_statistic': float(f_statistic),
        'p_value': float(p_value),
        'statistically_significant': significant,
        'platforms_compared': len(valid_platforms),
        'platform_means': {
            k: {'mean': float(v['mean']), 'std': float(v['std']), 'count': int(v['count'])}
            for k, v in platform_means.items()
        },
        'interpretation': f"ANOVA shows {'statistically significant' if significant else 'no statistically significant'} "
                         f"differences in commute times across platforms (F={f_statistic:.3f}, p={p_value:.4f}). "
                         f"Compared {len(valid_platforms)} platforms."
    }


def analyze_rq5_spatial_equity(df: pd.DataFrame) -> Dict:
    try:
        housing_metrics = aggregate_housing_metrics(df)
        
        if len(housing_metrics) == 0:
            return {'status': 'insufficient_data', 'message': 'No district data available'}
        
        rooms = housing_metrics['total_rooms'].values
        rooms = rooms[rooms > 0]
        
        if len(rooms) < 2:
            return {'status': 'insufficient_data', 'message': 'Need at least 2 districts with rooms'}
        
        rooms_sorted = np.sort(rooms)
        n = len(rooms_sorted)
        
        gini = (2 * np.sum((np.arange(1, n+1)) * rooms_sorted)) / (n * np.sum(rooms_sorted)) - (n + 1) / n
        equity_level = _interpret_gini(gini)
        
        top_20_percent = int(np.ceil(n * 0.2))
        top_20_rooms = np.sum(rooms_sorted[-top_20_percent:])
        total_rooms = np.sum(rooms_sorted)
        concentration_ratio = top_20_rooms / total_rooms if total_rooms > 0 else 0
        
        return {
            'status': 'success',
            'gini_coefficient': float(gini),
            'concentration_ratio': float(concentration_ratio),
            'districts_analyzed': n,
            'total_rooms': int(total_rooms),
            'equity_level': equity_level,
            'interpretation': f"Gini coefficient of {gini:.3f} indicates {equity_level} distribution of student housing across Berlin districts. "
                             f"Top 20% of districts contain {concentration_ratio*100:.1f}% of all rooms."
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def analyze_rq6_walkability_vs_rent(df: pd.DataFrame) -> Dict:
    """RQ6: How does walkability affect housing prices?"""
    analysis_df = df[
        df['rent'].notna() &
        df['walkability_score'].notna() &
        (pd.to_numeric(df['rent'], errors='coerce') > 0) &
        (pd.to_numeric(df['walkability_score'], errors='coerce') >= 0)
    ].copy()
    
    if len(analysis_df) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 rooms with both rent and walkability data'}
    
    rents = pd.to_numeric(analysis_df['rent'], errors='coerce')
    walkability = pd.to_numeric(analysis_df['walkability_score'], errors='coerce')
    
    # Remove NaN values
    valid_mask = rents.notna() & walkability.notna()
    rents_clean = rents[valid_mask]
    walkability_clean = walkability[valid_mask]
    
    if len(rents_clean) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 valid data points after cleaning'}
    
    # Remove outliers
    rent_mean, rent_std = rents_clean.mean(), rents_clean.std()
    walk_mean, walk_std = walkability_clean.mean(), walkability_clean.std()
    
    if rent_std > 0 and walk_std > 0:
        outlier_mask = (
            (rents_clean >= rent_mean - 3*rent_std) & (rents_clean <= rent_mean + 3*rent_std) &
            (walkability_clean >= walk_mean - 3*walk_std) & (walkability_clean <= walk_mean + 3*walk_std)
        )
        rents_clean = rents_clean[outlier_mask]
        walkability_clean = walkability_clean[outlier_mask]
    
    if len(rents_clean) < 10:
        rents_clean = rents[rents.notna() & walkability.notna()]
        walkability_clean = walkability[rents.notna() & walkability.notna()]
    
    # Ensure numeric arrays
    rents_clean = rents_clean.values.astype(float)
    walkability_clean = walkability_clean.values.astype(float)
    
    correlation, p_value = stats.pearsonr(rents_clean, walkability_clean)
    
    strength = _interpret_correlation_strength(abs(correlation))
    direction = "negative" if correlation < 0 else "positive"
    significant = p_value < 0.05
    
    return {
        'status': 'success',
        'correlation_coefficient': float(correlation),
        'p_value': float(p_value),
        'statistically_significant': significant,
        'strength': strength,
        'direction': direction,
        'sample_size': len(rents_clean),
        'interpretation': f"There is a {strength} {direction} correlation (r={correlation:.3f}) between rent and walkability score. "
                         f"This relationship is {'statistically significant' if significant else 'not statistically significant'} (p={p_value:.4f}). "
                         f"{'Higher walkability is associated with higher rent' if correlation > 0 else 'Higher walkability is associated with lower rent'}."
    }


def analyze_rq7_walkability_vs_commute(df: pd.DataFrame) -> Dict:
    """RQ7: What is the relationship between walkability and commute time?"""
    analysis_df = df[
        df['walkability_score'].notna() &
        df['total_commute_minutes'].notna() &
        (pd.to_numeric(df['walkability_score'], errors='coerce') >= 0) &
        (pd.to_numeric(df['total_commute_minutes'], errors='coerce') > 0)
    ].copy()
    
    if len(analysis_df) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 rooms with both walkability and commute data'}
    
    walkability = pd.to_numeric(analysis_df['walkability_score'], errors='coerce')
    commutes = pd.to_numeric(analysis_df['total_commute_minutes'], errors='coerce')
    
    # Remove NaN values and ensure numeric
    valid_mask = walkability.notna() & commutes.notna()
    walkability_clean = walkability[valid_mask].values.astype(float)
    commutes_clean = commutes[valid_mask].values.astype(float)
    
    if len(walkability_clean) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 valid data points after cleaning'}
    
    correlation, p_value = stats.pearsonr(walkability_clean, commutes_clean)
    
    strength = _interpret_correlation_strength(abs(correlation))
    direction = "negative" if correlation < 0 else "positive"
    significant = p_value < 0.05
    
    return {
        'status': 'success',
        'correlation_coefficient': float(correlation),
        'p_value': float(p_value),
        'statistically_significant': significant,
        'strength': strength,
        'direction': direction,
        'sample_size': len(analysis_df),
        'interpretation': f"There is a {strength} {direction} correlation (r={correlation:.3f}) between walkability score and commute time. "
                         f"This relationship is {'statistically significant' if significant else 'not statistically significant'} (p={p_value:.4f}). "
                         f"{'Higher walkability is associated with shorter commute' if correlation < 0 else 'Higher walkability is associated with longer commute'}."
    }


def analyze_rq8_poi_vs_availability(df: pd.DataFrame) -> Dict:
    """RQ8: How do POI density and amenities affect student housing preferences?"""
    try:
        housing_metrics = aggregate_housing_metrics(df)
        transport_metrics = aggregate_transport_metrics(df)
        
        if len(housing_metrics) == 0 or len(transport_metrics) == 0:
            return {'status': 'insufficient_data', 'message': 'Need district-level aggregation'}
        
        merged = pd.merge(housing_metrics, transport_metrics, on='district', how='inner')
        
        analysis_df = merged[
            merged['avg_poi_density'].notna() &
            merged['total_rooms'].notna() &
            (merged['avg_poi_density'] >= 0)
        ].copy()
        
        if len(analysis_df) < 5:
            return {'status': 'insufficient_data', 'message': 'Need at least 5 districts with POI data'}
        
        # Ensure numeric types
        poi_density = pd.to_numeric(analysis_df['avg_poi_density'], errors='coerce').values
        rooms = pd.to_numeric(analysis_df['total_rooms'], errors='coerce').values
        
        # Remove NaN values
        valid_mask = ~(np.isnan(poi_density) | np.isnan(rooms))
        poi_density = poi_density[valid_mask].astype(float)
        rooms = rooms[valid_mask].astype(float)
        
        if len(poi_density) < 5:
            return {'status': 'insufficient_data', 'message': 'Need at least 5 valid data points after cleaning'}
        
        slope, intercept, r_value, p_value, std_err = stats.linregress(poi_density, rooms)
        r_squared = r_value ** 2
        
        fit_quality = _interpret_r_squared(r_squared)
        significant = p_value < 0.05
        
        return {
            'status': 'success',
            'r_squared': float(r_squared),
            'slope': float(slope),
            'intercept': float(intercept),
            'p_value': float(p_value),
            'statistically_significant': significant,
            'fit_quality': fit_quality,
            'sample_size': len(analysis_df),
            'interpretation': f"POI density explains {r_squared*100:.1f}% of variance in room availability (R²={r_squared:.3f}). "
                             f"The relationship is {'statistically significant' if significant else 'not statistically significant'} (p={p_value:.4f}). "
                             f"Slope: {slope:.2f} rooms per POI (positive = more POIs = more rooms)."
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def analyze_rq9_bike_vs_walkability(df: pd.DataFrame) -> Dict:
    """RQ9: What is the relationship between bike accessibility and walkability?"""
    analysis_df = df[
        df['bike_accessibility_score'].notna() &
        df['walkability_score'].notna() &
        (pd.to_numeric(df['bike_accessibility_score'], errors='coerce') >= 0) &
        (pd.to_numeric(df['walkability_score'], errors='coerce') >= 0)
    ].copy()
    
    if len(analysis_df) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 rooms with both bike and walkability data'}
    
    bike_scores = pd.to_numeric(analysis_df['bike_accessibility_score'], errors='coerce')
    walkability = pd.to_numeric(analysis_df['walkability_score'], errors='coerce')
    
    # Remove NaN values and ensure numeric
    valid_mask = bike_scores.notna() & walkability.notna()
    bike_scores_clean = bike_scores[valid_mask].values.astype(float)
    walkability_clean = walkability[valid_mask].values.astype(float)
    
    if len(bike_scores_clean) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 valid data points after cleaning'}
    
    correlation, p_value = stats.pearsonr(bike_scores_clean, walkability_clean)
    
    strength = _interpret_correlation_strength(abs(correlation))
    direction = "negative" if correlation < 0 else "positive"
    significant = p_value < 0.05
    
    return {
        'status': 'success',
        'correlation_coefficient': float(correlation),
        'p_value': float(p_value),
        'statistically_significant': significant,
        'strength': strength,
        'direction': direction,
        'sample_size': len(analysis_df),
        'interpretation': f"There is a {strength} {direction} correlation (r={correlation:.3f}) between bike accessibility and walkability scores. "
                         f"This relationship is {'statistically significant' if significant else 'not statistically significant'} (p={p_value:.4f}). "
                         f"{'Better bike infrastructure is associated with higher walkability' if correlation > 0 else 'Better bike infrastructure is associated with lower walkability'}."
    }


def analyze_rq10_multimodal_mobility(df: pd.DataFrame) -> Dict:
    """RQ10: Which districts offer the best multi-modal mobility?"""
    try:
        transport_metrics = aggregate_transport_metrics(df)
        
        if len(transport_metrics) == 0:
            return {'status': 'insufficient_data', 'message': 'No district data available'}
        
        analysis_df = transport_metrics[
            transport_metrics['avg_walkability_score'].notna() &
            transport_metrics['avg_bike_accessibility_score'].notna() &
            transport_metrics['avg_commute_minutes'].notna()
        ].copy()
        
        if len(analysis_df) < 3:
            return {'status': 'insufficient_data', 'message': 'Need at least 3 districts with mobility data'}
        
        # Ensure numeric types
        analysis_df['avg_walkability_score'] = pd.to_numeric(analysis_df['avg_walkability_score'], errors='coerce')
        analysis_df['avg_bike_accessibility_score'] = pd.to_numeric(analysis_df['avg_bike_accessibility_score'], errors='coerce')
        analysis_df['avg_commute_minutes'] = pd.to_numeric(analysis_df['avg_commute_minutes'], errors='coerce')
        
        # Normalize scores (0-1)
        def normalize_score(series):
            series_clean = pd.to_numeric(series, errors='coerce')
            valid = series_clean.dropna()
            if len(valid) == 0:
                return pd.Series(0.0, index=series.index, dtype=float)
            min_val = valid.min()
            max_val = valid.max()
            if max_val > min_val:
                return ((series_clean - min_val) / (max_val - min_val)).fillna(0.0)
            return pd.Series(0.5, index=series.index, dtype=float)
        
        # Inverse normalize commute (shorter is better)
        def normalize_commute(series):
            series_clean = pd.to_numeric(series, errors='coerce')
            valid = series_clean.dropna()
            if len(valid) == 0:
                return pd.Series(0.0, index=series.index, dtype=float)
            min_val = valid.min()
            max_val = valid.max()
            if max_val > min_val:
                return (1 - (series_clean - min_val) / (max_val - min_val)).fillna(0.0)
            return pd.Series(0.5, index=series.index, dtype=float)
        
        analysis_df['walkability_normalized'] = normalize_score(analysis_df['avg_walkability_score'])
        analysis_df['bike_normalized'] = normalize_score(analysis_df['avg_bike_accessibility_score'])
        analysis_df['commute_normalized'] = normalize_commute(analysis_df['avg_commute_minutes'])
        
        # Composite multi-modal mobility score (equal weights)
        analysis_df['multimodal_score'] = (
            analysis_df['walkability_normalized'].fillna(0) * 0.4 +
            analysis_df['bike_normalized'].fillna(0) * 0.3 +
            analysis_df['commute_normalized'].fillna(0) * 0.3
        ) * 100
        
        # Ensure multimodal_score is numeric
        analysis_df['multimodal_score'] = pd.to_numeric(analysis_df['multimodal_score'], errors='coerce')
        
        analysis_df = analysis_df.sort_values('multimodal_score', ascending=False)
        
        top_5_df = analysis_df.head(5)[['district', 'multimodal_score', 'avg_walkability_score', 
                                         'avg_bike_accessibility_score', 'avg_commute_minutes']].copy()
        
        # Ensure all numeric columns are properly converted
        top_5_df['multimodal_score'] = pd.to_numeric(top_5_df['multimodal_score'], errors='coerce')
        top_5_df['avg_walkability_score'] = pd.to_numeric(top_5_df['avg_walkability_score'], errors='coerce')
        top_5_df['avg_bike_accessibility_score'] = pd.to_numeric(top_5_df['avg_bike_accessibility_score'], errors='coerce')
        top_5_df['avg_commute_minutes'] = pd.to_numeric(top_5_df['avg_commute_minutes'], errors='coerce')
        
        top_5 = []
        for idx, row in top_5_df.iterrows():
            top_5.append({
                'district': str(row['district']),
                'multimodal_score': float(row['multimodal_score']) if pd.notna(row['multimodal_score']) else 0.0,
                'avg_walkability_score': float(row['avg_walkability_score']) if pd.notna(row['avg_walkability_score']) else None,
                'avg_bike_accessibility_score': float(row['avg_bike_accessibility_score']) if pd.notna(row['avg_bike_accessibility_score']) else None,
                'avg_commute_minutes': float(row['avg_commute_minutes']) if pd.notna(row['avg_commute_minutes']) else None
            })
        
        return {
            'status': 'success',
            'top_5_districts': top_5,
            'total_districts_analyzed': len(analysis_df),
            'interpretation': f"Top 5 districts ranked by composite Multi-Modal Mobility Score combining walkability (40%), bike accessibility (30%), and commute time (30%). "
                             f"Analyzed {len(analysis_df)} districts with complete mobility data."
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def analyze_rq11_amenities_vs_walkability(df: pd.DataFrame) -> Dict:
    """RQ11: How do specific amenities contribute to walkability scores?"""
    analysis_df = df[
        df['walkability_score'].notna() &
        df['grocery_stores_500m'].notna() &
        df['cafes_500m'].notna() &
        (pd.to_numeric(df['walkability_score'], errors='coerce') >= 0)
    ].copy()
    
    if len(analysis_df) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 rooms with walkability and amenity data'}
    
    walkability = pd.to_numeric(analysis_df['walkability_score'], errors='coerce')
    grocery = pd.to_numeric(analysis_df['grocery_stores_500m'], errors='coerce')
    cafes = pd.to_numeric(analysis_df['cafes_500m'], errors='coerce')
    
    # Remove NaN values
    valid_mask = walkability.notna() & grocery.notna() & cafes.notna()
    walkability_clean = walkability[valid_mask].values.astype(float)
    grocery_clean = grocery[valid_mask].values.astype(float)
    cafes_clean = cafes[valid_mask].values.astype(float)
    
    if len(walkability_clean) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 valid data points after cleaning'}
    
    # Multiple regression using numpy
    X = np.column_stack([grocery_clean, cafes_clean, np.ones(len(grocery_clean))])
    y = walkability_clean
    
    try:
        coeffs = np.linalg.lstsq(X, y, rcond=None)[0]
        y_pred = X @ coeffs
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return {
            'status': 'success',
            'r_squared': float(r_squared),
            'grocery_coefficient': float(coeffs[0]),
            'cafe_coefficient': float(coeffs[1]),
            'sample_size': len(walkability_clean),
            'interpretation': f"Grocery stores and cafes explain {r_squared*100:.1f}% of variance in walkability scores (R²={r_squared:.3f}). "
                             f"Grocery coefficient: {coeffs[0]:.2f}, Cafe coefficient: {coeffs[1]:.2f}."
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def analyze_rq12_bike_vs_commute(df: pd.DataFrame) -> Dict:
    """RQ12: What is the relationship between bike infrastructure and commute time?"""
    analysis_df = df[
        df['bike_accessibility_score'].notna() &
        df['total_commute_minutes'].notna() &
        (pd.to_numeric(df['bike_accessibility_score'], errors='coerce') >= 0) &
        (pd.to_numeric(df['total_commute_minutes'], errors='coerce') > 0)
    ].copy()
    
    if len(analysis_df) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 rooms with both bike and commute data'}
    
    bike_scores = pd.to_numeric(analysis_df['bike_accessibility_score'], errors='coerce')
    commutes = pd.to_numeric(analysis_df['total_commute_minutes'], errors='coerce')
    
    # Remove NaN values and ensure numeric
    valid_mask = bike_scores.notna() & commutes.notna()
    bike_scores_clean = bike_scores[valid_mask].values.astype(float)
    commutes_clean = commutes[valid_mask].values.astype(float)
    
    if len(bike_scores_clean) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 valid data points after cleaning'}
    
    correlation, p_value = stats.pearsonr(bike_scores_clean, commutes_clean)
    
    strength = _interpret_correlation_strength(abs(correlation))
    direction = "negative" if correlation < 0 else "positive"
    significant = p_value < 0.05
    
    return {
        'status': 'success',
        'correlation_coefficient': float(correlation),
        'p_value': float(p_value),
        'statistically_significant': significant,
        'strength': strength,
        'direction': direction,
        'sample_size': len(bike_scores_clean),
        'interpretation': f"There is a {strength} {direction} correlation (r={correlation:.3f}) between bike accessibility and commute time. "
                         f"This relationship is {'statistically significant' if significant else 'not statistically significant'} (p={p_value:.4f}). "
                         f"{'Better bike infrastructure is associated with shorter commute' if correlation < 0 else 'Better bike infrastructure is associated with longer commute'}."
    }


def analyze_rq13_walkability_by_district(df: pd.DataFrame) -> Dict:
    """RQ13: How does walkability vary across Berlin districts?"""
    try:
        transport_metrics = aggregate_transport_metrics(df)
        
        if len(transport_metrics) == 0:
            return {'status': 'insufficient_data', 'message': 'No district data available'}
        
        analysis_df = transport_metrics[
            transport_metrics['avg_walkability_score'].notna() &
            (pd.to_numeric(transport_metrics['avg_walkability_score'], errors='coerce') >= 0)
        ].copy()
        
        if len(analysis_df) < 3:
            return {'status': 'insufficient_data', 'message': 'Need at least 3 districts with walkability data'}
        
        walkability_scores = pd.to_numeric(analysis_df['avg_walkability_score'], errors='coerce')
        districts = analysis_df['district'].values
        
        # Remove NaN
        valid_mask = ~np.isnan(walkability_scores)
        walkability_scores = walkability_scores[valid_mask].astype(float)
        districts = districts[valid_mask]
        
        if len(walkability_scores) < 3:
            return {'status': 'insufficient_data', 'message': 'Need at least 3 valid districts after cleaning'}
        
        # Calculate statistics
        mean_score = float(np.mean(walkability_scores))
        std_score = float(np.std(walkability_scores))
        min_score = float(np.min(walkability_scores))
        max_score = float(np.max(walkability_scores))
        
        # Find top and bottom districts
        top_district_idx = np.argmax(walkability_scores)
        bottom_district_idx = np.argmin(walkability_scores)
        
        return {
            'status': 'success',
            'mean_walkability': mean_score,
            'std_walkability': std_score,
            'min_walkability': min_score,
            'max_walkability': max_score,
            'top_district': str(districts[top_district_idx]),
            'bottom_district': str(districts[bottom_district_idx]),
            'sample_size': len(walkability_scores),
            'interpretation': f"Walkability varies across districts (mean={mean_score:.1f}, std={std_score:.1f}). "
                             f"Highest: {districts[top_district_idx]} ({max_score:.1f}), Lowest: {districts[bottom_district_idx]} ({min_score:.1f})."
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def analyze_rq14_poi_density_vs_walkability(df: pd.DataFrame) -> Dict:
    """RQ14: What is the relationship between POI density and walkability score?"""
    analysis_df = df[
        df['total_pois_500m'].notna() &
        df['walkability_score'].notna() &
        (pd.to_numeric(df['total_pois_500m'], errors='coerce') >= 0) &
        (pd.to_numeric(df['walkability_score'], errors='coerce') >= 0)
    ].copy()
    
    if len(analysis_df) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 rooms with both POI and walkability data'}
    
    poi_density = pd.to_numeric(analysis_df['total_pois_500m'], errors='coerce')
    walkability = pd.to_numeric(analysis_df['walkability_score'], errors='coerce')
    
    # Remove NaN values and ensure numeric
    valid_mask = poi_density.notna() & walkability.notna()
    poi_density_clean = poi_density[valid_mask].values.astype(float)
    walkability_clean = walkability[valid_mask].values.astype(float)
    
    if len(poi_density_clean) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 valid data points after cleaning'}
    
    correlation, p_value = stats.pearsonr(poi_density_clean, walkability_clean)
    
    strength = _interpret_correlation_strength(abs(correlation))
    direction = "negative" if correlation < 0 else "positive"
    significant = p_value < 0.05
    
    return {
        'status': 'success',
        'correlation_coefficient': float(correlation),
        'p_value': float(p_value),
        'statistically_significant': significant,
        'strength': strength,
        'direction': direction,
        'sample_size': len(poi_density_clean),
        'interpretation': f"There is a {strength} {direction} correlation (r={correlation:.3f}) between POI density and walkability score. "
                         f"This relationship is {'statistically significant' if significant else 'not statistically significant'} (p={p_value:.4f}). "
                         f"{'Higher POI density is associated with higher walkability' if correlation > 0 else 'Higher POI density is associated with lower walkability'}."
    }


def analyze_rq15_essential_services_vs_availability(df: pd.DataFrame) -> Dict:
    """RQ15: How do essential services affect housing preferences?"""
    try:
        housing_metrics = aggregate_housing_metrics(df)
        transport_metrics = aggregate_transport_metrics(df)
        
        if len(housing_metrics) == 0 or len(transport_metrics) == 0:
            return {'status': 'insufficient_data', 'message': 'Need district-level aggregation'}
        
        merged = pd.merge(housing_metrics, transport_metrics, on='district', how='inner')
        
        analysis_df = merged[
            merged['avg_grocery_stores_500m'].notna() &
            merged['total_rooms'].notna() &
            (pd.to_numeric(merged['avg_grocery_stores_500m'], errors='coerce') >= 0)
        ].copy()
        
        if len(analysis_df) < 5:
            return {'status': 'insufficient_data', 'message': 'Need at least 5 districts with essential service data'}
        
        # Ensure numeric types
        grocery = pd.to_numeric(analysis_df['avg_grocery_stores_500m'], errors='coerce').values
        rooms = pd.to_numeric(analysis_df['total_rooms'], errors='coerce').values
        
        # Remove NaN
        valid_mask = ~(np.isnan(grocery) | np.isnan(rooms))
        grocery = grocery[valid_mask].astype(float)
        rooms = rooms[valid_mask].astype(float)
        
        if len(grocery) < 5:
            return {'status': 'insufficient_data', 'message': 'Need at least 5 valid data points after cleaning'}
        
        correlation, p_value = stats.pearsonr(grocery, rooms)
        
        strength = _interpret_correlation_strength(abs(correlation))
        direction = "negative" if correlation < 0 else "positive"
        significant = p_value < 0.05
        
        return {
            'status': 'success',
            'correlation_coefficient': float(correlation),
            'p_value': float(p_value),
            'statistically_significant': significant,
            'strength': strength,
            'direction': direction,
            'sample_size': len(grocery),
            'interpretation': f"There is a {strength} {direction} correlation (r={correlation:.3f}) between essential services (grocery stores) and room availability. "
                             f"This relationship is {'statistically significant' if significant else 'not statistically significant'} (p={p_value:.4f}). "
                             f"{'More essential services are associated with more available rooms' if correlation > 0 else 'More essential services are associated with fewer available rooms'}."
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def analyze_rq16_bike_vs_rent(df: pd.DataFrame) -> Dict:
    """RQ16: What is the relationship between bike accessibility and housing prices?"""
    analysis_df = df[
        df['rent'].notna() &
        df['bike_accessibility_score'].notna() &
        (pd.to_numeric(df['rent'], errors='coerce') > 0) &
        (pd.to_numeric(df['bike_accessibility_score'], errors='coerce') >= 0)
    ].copy()
    
    if len(analysis_df) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 rooms with both rent and bike accessibility data'}
    
    rents = pd.to_numeric(analysis_df['rent'], errors='coerce')
    bike_scores = pd.to_numeric(analysis_df['bike_accessibility_score'], errors='coerce')
    
    # Remove NaN values
    valid_mask = rents.notna() & bike_scores.notna()
    rents_clean = rents[valid_mask]
    bike_scores_clean = bike_scores[valid_mask]
    
    if len(rents_clean) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 valid data points after cleaning'}
    
    # Remove outliers
    rent_mean, rent_std = rents_clean.mean(), rents_clean.std()
    bike_mean, bike_std = bike_scores_clean.mean(), bike_scores_clean.std()
    
    if rent_std > 0 and bike_std > 0:
        outlier_mask = (
            (rents_clean >= rent_mean - 3*rent_std) & (rents_clean <= rent_mean + 3*rent_std) &
            (bike_scores_clean >= bike_mean - 3*bike_std) & (bike_scores_clean <= bike_mean + 3*bike_std)
        )
        rents_clean = rents_clean[outlier_mask]
        bike_scores_clean = bike_scores_clean[outlier_mask]
    
    if len(rents_clean) < 10:
        rents_clean = rents[rents.notna() & bike_scores.notna()]
        bike_scores_clean = bike_scores[rents.notna() & bike_scores.notna()]
    
    # Ensure numeric arrays
    rents_clean = rents_clean.values.astype(float)
    bike_scores_clean = bike_scores_clean.values.astype(float)
    
    correlation, p_value = stats.pearsonr(rents_clean, bike_scores_clean)
    
    strength = _interpret_correlation_strength(abs(correlation))
    direction = "negative" if correlation < 0 else "positive"
    significant = p_value < 0.05
    
    return {
        'status': 'success',
        'correlation_coefficient': float(correlation),
        'p_value': float(p_value),
        'statistically_significant': significant,
        'strength': strength,
        'direction': direction,
        'sample_size': len(rents_clean),
        'interpretation': f"There is a {strength} {direction} correlation (r={correlation:.3f}) between bike accessibility and rent. "
                         f"This relationship is {'statistically significant' if significant else 'not statistically significant'} (p={p_value:.4f}). "
                         f"{'Better bike infrastructure is associated with higher rent' if correlation > 0 else 'Better bike infrastructure is associated with lower rent'}."
    }


def analyze_rq17_walkability_vs_transfers(df: pd.DataFrame) -> Dict:
    """RQ17: How does walkability affect the number of transfers needed for commute?"""
    analysis_df = df[
        df['walkability_score'].notna() &
        df['transfers'].notna() &
        (pd.to_numeric(df['walkability_score'], errors='coerce') >= 0) &
        (pd.to_numeric(df['transfers'], errors='coerce') >= 0)
    ].copy()
    
    if len(analysis_df) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 rooms with both walkability and transfer data'}
    
    walkability = pd.to_numeric(analysis_df['walkability_score'], errors='coerce')
    transfers = pd.to_numeric(analysis_df['transfers'], errors='coerce')
    
    # Remove NaN values and ensure numeric
    valid_mask = walkability.notna() & transfers.notna()
    walkability_clean = walkability[valid_mask].values.astype(float)
    transfers_clean = transfers[valid_mask].values.astype(float)
    
    if len(walkability_clean) < 10:
        return {'status': 'insufficient_data', 'message': 'Need at least 10 valid data points after cleaning'}
    
    correlation, p_value = stats.pearsonr(walkability_clean, transfers_clean)
    
    strength = _interpret_correlation_strength(abs(correlation))
    direction = "negative" if correlation < 0 else "positive"
    significant = p_value < 0.05
    
    return {
        'status': 'success',
        'correlation_coefficient': float(correlation),
        'p_value': float(p_value),
        'statistically_significant': significant,
        'strength': strength,
        'direction': direction,
        'sample_size': len(walkability_clean),
        'interpretation': f"There is a {strength} {direction} correlation (r={correlation:.3f}) between walkability and number of transfers. "
                         f"This relationship is {'statistically significant' if significant else 'not statistically significant'} (p={p_value:.4f}). "
                         f"{'Higher walkability is associated with fewer transfers' if correlation < 0 else 'Higher walkability is associated with more transfers'}."
    }


def analyze_rq18_walkability_affordability_ratio(df: pd.DataFrame) -> Dict:
    """RQ18: Which districts offer the best walkability-to-affordability ratio?"""
    try:
        housing_metrics = aggregate_housing_metrics(df)
        transport_metrics = aggregate_transport_metrics(df)
        
        if len(housing_metrics) == 0 or len(transport_metrics) == 0:
            return {'status': 'insufficient_data', 'message': 'Need district-level aggregation'}
        
        merged = pd.merge(housing_metrics, transport_metrics, on='district', how='inner')
        
        analysis_df = merged[
            merged['avg_walkability_score'].notna() &
            merged['avg_rent'].notna() &
            (pd.to_numeric(merged['avg_walkability_score'], errors='coerce') >= 0) &
            (pd.to_numeric(merged['avg_rent'], errors='coerce') > 0)
        ].copy()
        
        if len(analysis_df) < 3:
            return {'status': 'insufficient_data', 'message': 'Need at least 3 districts with walkability and rent data'}
        
        # Ensure numeric types
        walkability = pd.to_numeric(analysis_df['avg_walkability_score'], errors='coerce')
        rent = pd.to_numeric(analysis_df['avg_rent'], errors='coerce')
        
        # Remove NaN
        valid_mask = walkability.notna() & rent.notna()
        walkability = walkability[valid_mask]
        rent = rent[valid_mask]
        analysis_df = analysis_df.iloc[valid_mask]
        
        if len(walkability) < 3:
            return {'status': 'insufficient_data', 'message': 'Need at least 3 valid districts after cleaning'}
        
        # Calculate walkability-to-rent ratio (walkability per euro)
        ratio = (walkability.values / rent.values).astype(float)
        analysis_df = analysis_df.copy()
        analysis_df['walkability_rent_ratio'] = ratio
        
        analysis_df = analysis_df.sort_values('walkability_rent_ratio', ascending=False)
        
        top_5 = analysis_df.head(5)[['district', 'walkability_rent_ratio', 'avg_walkability_score', 'avg_rent']].copy()
        
        # Ensure all numeric columns are properly converted
        top_5['walkability_rent_ratio'] = pd.to_numeric(top_5['walkability_rent_ratio'], errors='coerce')
        top_5['avg_walkability_score'] = pd.to_numeric(top_5['avg_walkability_score'], errors='coerce')
        top_5['avg_rent'] = pd.to_numeric(top_5['avg_rent'], errors='coerce')
        
        top_5_list = []
        for idx, row in top_5.iterrows():
            top_5_list.append({
                'district': str(row['district']),
                'walkability_rent_ratio': float(row['walkability_rent_ratio']) if pd.notna(row['walkability_rent_ratio']) else 0.0,
                'avg_walkability_score': float(row['avg_walkability_score']) if pd.notna(row['avg_walkability_score']) else None,
                'avg_rent': float(row['avg_rent']) if pd.notna(row['avg_rent']) else None
            })
        
        return {
            'status': 'success',
            'top_5_districts': top_5_list,
            'total_districts_analyzed': len(analysis_df),
            'interpretation': f"Top 5 districts ranked by walkability-to-affordability ratio (walkability score per euro of rent). "
                             f"Analyzed {len(analysis_df)} districts with complete data."
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def run_all_research_questions(df: pd.DataFrame) -> Dict:
    return {
        'RQ1_affordability_vs_accessibility': analyze_rq1_affordability_vs_accessibility(df),
        'RQ2_district_balance': analyze_rq2_district_balance(df),
        'RQ3_walking_vs_availability': analyze_rq3_walking_vs_availability(df),
        'RQ4_platform_differences': analyze_rq4_platform_differences(df),
        'RQ5_spatial_equity': analyze_rq5_spatial_equity(df),
        'RQ6_walkability_vs_rent': analyze_rq6_walkability_vs_rent(df),
        'RQ7_walkability_vs_commute': analyze_rq7_walkability_vs_commute(df),
        'RQ8_poi_vs_availability': analyze_rq8_poi_vs_availability(df),
        'RQ9_bike_vs_walkability': analyze_rq9_bike_vs_walkability(df),
        'RQ10_multimodal_mobility': analyze_rq10_multimodal_mobility(df),
        'RQ11_amenities_vs_walkability': analyze_rq11_amenities_vs_walkability(df),
        'RQ12_bike_vs_commute': analyze_rq12_bike_vs_commute(df),
        'RQ13_walkability_by_district': analyze_rq13_walkability_by_district(df),
        'RQ14_poi_density_vs_walkability': analyze_rq14_poi_density_vs_walkability(df),
        'RQ15_essential_services_vs_availability': analyze_rq15_essential_services_vs_availability(df),
        'RQ16_bike_vs_rent': analyze_rq16_bike_vs_rent(df),
        'RQ17_walkability_vs_transfers': analyze_rq17_walkability_vs_transfers(df),
        'RQ18_walkability_affordability_ratio': analyze_rq18_walkability_affordability_ratio(df)
    }


def _interpret_correlation_strength(abs_r: float) -> str:
    if abs_r < 0.1:
        return "negligible"
    elif abs_r < 0.3:
        return "weak"
    elif abs_r < 0.5:
        return "moderate"
    elif abs_r < 0.7:
        return "strong"
    else:
        return "very strong"


def _interpret_r_squared(r_squared: float) -> str:
    if r_squared < 0.1:
        return "poor"
    elif r_squared < 0.3:
        return "weak"
    elif r_squared < 0.5:
        return "moderate"
    elif r_squared < 0.7:
        return "good"
    else:
        return "excellent"


def _interpret_gini(gini: float) -> str:
    if gini < 0.2:
        return "highly equitable"
    elif gini < 0.3:
        return "relatively equitable"
    elif gini < 0.4:
        return "moderately unequal"
    elif gini < 0.5:
        return "unequal"
    else:
        return "highly unequal"
