import pandas as pd
import numpy as np
import re
from pathlib import Path
from typing import Optional, List

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import COLUMN_MAPPINGS, NON_BERLIN_CITIES, DEFAULT_ACCOMMODATION_FILE


def load_accommodation_data(
    file_path: str,
    city_filter: str = 'Berlin',
    limit: Optional[int] = None,
    provider_filter: Optional[str] = None
) -> pd.DataFrame:
    try:
        if file_path.endswith('.csv'):
            try:
                df = pd.read_csv(file_path, sep=';', encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, sep=';', encoding='latin-1')
        else:
            df = pd.read_excel(file_path)
        
        df.columns = df.columns.str.strip()
        df = _filter_by_city(df, city_filter)
        df = _map_columns(df)
        df = _clean_rent_column(df)
        df = _clean_address_column(df)
        df = _filter_by_provider(df, provider_filter)
        
        if limit is not None and limit > 0:
            df = df.head(limit)
            print(f"✓ Limited to {limit} rows for preview")
        
        df = df.reset_index(drop=True)
        df['apartment_id'] = df.index
        print(f"✓ Loaded {len(df)} accommodations from {city_filter}")
        return df
    
    except Exception as e:
        raise Exception(f"Error loading accommodation data: {str(e)}")


def _filter_by_city(df: pd.DataFrame, city_filter: str) -> pd.DataFrame:
    city_column = None
    for col in COLUMN_MAPPINGS['city_keywords']:
        if col in df.columns:
            city_column = col
            break
    
    if city_column:
        df = df[df[city_column].str.contains(city_filter, case=False, na=False)]
    return df


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    column_mapping = {}
    
    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in COLUMN_MAPPINGS['rent_keywords']):
            column_mapping[col] = 'rent'
            break
    
    for keyword_group in COLUMN_MAPPINGS['address_keywords']:
        found = False
        for col in df.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in keyword_group):
                column_mapping[col] = 'address'
                found = True
                break
        if found:
            break
    
    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in COLUMN_MAPPINGS['provider_keywords']):
            column_mapping[col] = 'provider'
            break
    
    return df.rename(columns=column_mapping)


def _clean_rent_column(df: pd.DataFrame) -> pd.DataFrame:
    if 'rent' in df.columns:
        df['rent'] = df['rent'].astype(str)
        df['rent'] = df['rent'].str.replace('€', '', regex=False)
        df['rent'] = df['rent'].str.replace('EUR', '', regex=False, case=False)
        df['rent'] = df['rent'].str.replace('Euro', '', regex=False, case=False)
        df['rent'] = df['rent'].str.replace(',', '.', regex=False)
        df['rent'] = df['rent'].str.replace(r'[^\d.]', '', regex=True)
        df['rent'] = df['rent'].str.strip()
        df['rent'] = pd.to_numeric(df['rent'], errors='coerce')
    return df


def _clean_address_column(df: pd.DataFrame) -> pd.DataFrame:
    if 'address' not in df.columns:
        return df
    
    df['address'] = df['address'].astype(str).str.strip()
    df['address'] = df['address'].str.replace(r'[\n\r\t]+', ' ', regex=True)
    df['address'] = df['address'].str.replace(r'BerlinGermany', 'Berlin, Germany', regex=False)
    df['address'] = df['address'].str.replace(r'Berlin\s+Germany', 'Berlin, Germany', regex=True)
    df['address'] = df['address'].str.replace(r'Berlin\s*,?\s*Germany', 'Berlin, Germany', regex=True)
    df['address'] = df['address'].str.replace(r'THE\s+URBAN\s+CLUB', '', regex=True, flags=re.IGNORECASE)
    df['address'] = df['address'].str.replace(r'URBAN\s+CLUB', '', regex=True, flags=re.IGNORECASE)
    df['address'] = df['address'].str.replace(r'-\s*Pl[öo]n?zeile', '', regex=True, flags=re.IGNORECASE)
    df['address'] = df['address'].str.replace(r'Pl[öo]n?zeile\s*', '', regex=True, flags=re.IGNORECASE)
    df['address'] = df['address'].str.replace(r',\s*(\d{5})', r', \1', regex=True)
    df['address'] = df['address'].str.replace(r'(\d{5})\s*Berlin', r'\1 Berlin', regex=True)
    df['address'] = df['address'].str.replace(r'\s+', ' ', regex=True)
    df['address'] = df['address'].str.strip()
    df['address'] = df['address'].str.replace(r'^,\s*', '', regex=True)
    df['address'] = df['address'].str.replace(r'\s*,+$', '', regex=True)
    df['address'] = df['address'].str.replace(r',\s*,+', ',', regex=True)
    
    for idx in df.index:
        addr = df.at[idx, 'address']
        if pd.notna(addr) and addr != '' and addr != 'nan':
            addr = _clean_single_address(addr)
            df.at[idx, 'address'] = addr
    
    return df


def _clean_single_address(addr: str) -> str:
    addr = re.sub(r'BER\s+[MS]\s+mit\s+Balkon\s+', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r'BER\s+[MS]\s+mit\s+Balkon', '', addr, flags=re.IGNORECASE)
    
    for wrong_city in NON_BERLIN_CITIES:
        if wrong_city in addr:
            addr = re.sub(f'{wrong_city},?', '', addr, flags=re.IGNORECASE)
            addr = re.sub(r'\s+', ' ', addr).strip()
            addr = re.sub(r',\s*,+', ',', addr)
    
    is_apartment_name = re.match(
        r'^BERLIN\s+[A-ZÄÖÜ\s\-]+(?:Classic|Long|Term|Balcony|Silver|Neon)',
        addr, re.IGNORECASE
    )
    
    if is_apartment_name:
        if not re.search(r'Germany', addr, re.IGNORECASE):
            addr = f"{addr}, Germany"
        return addr
    
    if not re.search(r'Berlin', addr, re.IGNORECASE):
        if not addr.endswith('Berlin'):
            addr = f"{addr}, Berlin, Germany"
    elif not re.search(r'Germany', addr, re.IGNORECASE):
        if not addr.endswith('Germany'):
            if re.search(r'\d{5}\s*$', addr):
                addr = re.sub(r'(\d{5})\s*$', r'\1, Germany', addr)
            else:
                addr = f"{addr}, Germany"
    
    return addr


def _filter_by_provider(df: pd.DataFrame, provider_filter: Optional[str]) -> pd.DataFrame:
    if not provider_filter or 'provider' not in df.columns:
        return df
    
    provider_list = [p.strip() for p in provider_filter.split(',')]
    
    if len(provider_list) == 1:
        df = df[df['provider'].str.contains(provider_list[0], case=False, na=False)]
        print(f"✓ Filtered to provider: {provider_list[0]} ({len(df)} rooms)")
    else:
        filter_mask = df['provider'].str.contains(provider_list[0], case=False, na=False)
        for provider in provider_list[1:]:
            filter_mask = filter_mask | df['provider'].str.contains(provider.strip(), case=False, na=False)
        df = df[filter_mask]
        print(f"✓ Filtered to providers: {', '.join(provider_list)} ({len(df)} rooms)")
    
    return df


def validate_data(df: pd.DataFrame) -> bool:
    if len(df) == 0:
        raise ValueError("No accommodations found after filtering")
    
    if 'rent' not in df.columns:
        print("⚠ Warning: 'rent' column not found. Rooms will be displayed without rent information.")
    
    return True
