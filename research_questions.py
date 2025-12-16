import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, Tuple, Optional
from area_analysis import analyze_best_areas, aggregate_housing_metrics, aggregate_transport_metrics

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
        "quantifiable_metric": "Student Area Score ranking by district",
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
        return {
            'status': 'insufficient_data',
            'message': 'Need at least 10 rooms with both rent and commute data'
        }
    
    rents = pd.to_numeric(analysis_df['rent'], errors='coerce')
    commutes = pd.to_numeric(analysis_df['total_commute_minutes'], errors='coerce')
    
    rent_mean = rents.mean()
    rent_std = rents.std()
    commute_mean = commutes.mean()
    commute_std = commutes.std()
    
    valid_mask = (
        (rents >= rent_mean - 3*rent_std) & (rents <= rent_mean + 3*rent_std) &
        (commutes >= commute_mean - 3*commute_std) & (commutes <= commute_mean + 3*commute_std)
    )
    
    rents_clean = rents[valid_mask]
    commutes_clean = commutes[valid_mask]
    
    if len(rents_clean) < 10:
        rents_clean = rents
        commutes_clean = commutes
    
    correlation, p_value = stats.pearsonr(rents_clean, commutes_clean)
    
    if abs(correlation) < 0.1:
        strength = "negligible"
    elif abs(correlation) < 0.3:
        strength = "weak"
    elif abs(correlation) < 0.5:
        strength = "moderate"
    elif abs(correlation) < 0.7:
        strength = "strong"
    else:
        strength = "very strong"
    
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
            'interpretation': f"Top 5 districts ranked by composite Student Area Score combining affordability, commute time, walking distance, and room availability."
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
        
        walking = analysis_df['avg_walking_distance_m'].values
        rooms = analysis_df['total_rooms'].values
        
        slope, intercept, r_value, p_value, std_err = stats.linregress(walking, rooms)
        r_squared = r_value ** 2
        
        if r_squared < 0.1:
            fit_quality = "poor"
        elif r_squared < 0.3:
            fit_quality = "weak"
        elif r_squared < 0.5:
            fit_quality = "moderate"
        elif r_squared < 0.7:
            fit_quality = "good"
        else:
            fit_quality = "excellent"
        
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
    
    platform_counts = analysis_df['provider'].value_counts()
    valid_platforms = platform_counts[platform_counts >= 5].index.tolist()
    
    if len(valid_platforms) < 2:
        return {'status': 'insufficient_data', 'message': 'Need at least 2 platforms with 5+ rooms each'}
    
    analysis_df = analysis_df[analysis_df['provider'].isin(valid_platforms)]
    
    platform_groups = [analysis_df[analysis_df['provider'] == platform]['commute'].values 
                       for platform in valid_platforms]
    
    f_statistic, p_value = stats.f_oneway(*platform_groups)
    
    platform_means = analysis_df.groupby('provider')['commute'].agg(['mean', 'std', 'count']).to_dict('index')
    
    significant = p_value < 0.05
    
    return {
        'status': 'success',
        'f_statistic': float(f_statistic),
        'p_value': float(p_value),
        'statistically_significant': significant,
        'platforms_compared': len(valid_platforms),
        'platform_means': {k: {'mean': float(v['mean']), 'std': float(v['std']), 'count': int(v['count'])} 
                          for k, v in platform_means.items()},
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
        rooms = rooms[rooms > 0]  # Remove zeros
        
        if len(rooms) < 2:
            return {'status': 'insufficient_data', 'message': 'Need at least 2 districts with rooms'}
        
        rooms_sorted = np.sort(rooms)
        n = len(rooms_sorted)
        
        cumsum = np.cumsum(rooms_sorted)
        gini = (2 * np.sum((np.arange(1, n+1)) * rooms_sorted)) / (n * np.sum(rooms_sorted)) - (n + 1) / n
        
        if gini < 0.2:
            equity_level = "highly equitable"
        elif gini < 0.3:
            equity_level = "relatively equitable"
        elif gini < 0.4:
            equity_level = "moderately unequal"
        elif gini < 0.5:
            equity_level = "unequal"
        else:
            equity_level = "highly unequal"
        
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

def run_all_research_questions(df: pd.DataFrame) -> Dict:
    results = {
        'RQ1_affordability_vs_accessibility': analyze_rq1_affordability_vs_accessibility(df),
        'RQ2_district_balance': analyze_rq2_district_balance(df),
        'RQ3_walking_vs_availability': analyze_rq3_walking_vs_availability(df),
        'RQ4_platform_differences': analyze_rq4_platform_differences(df),
        'RQ5_spatial_equity': analyze_rq5_spatial_equity(df)
    }
    
    return results

