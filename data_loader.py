"""
Data Loader Module
==================

This module handles loading and preprocessing accommodation data from Excel/CSV files.
Filters for Berlin-only accommodations and prepares data for urban mobility analysis.

Urban Technology Relevance:
- Spatial data preprocessing is fundamental to urban analytics
- Filtering by geographic boundaries enables location-specific accessibility analysis
"""

import pandas as pd
import numpy as np


def load_accommodation_data(file_path, city_filter='Berlin', limit=None, provider_filter=None):
    """
    Load accommodation data from Excel or CSV file.
    
    Parameters:
    -----------
    file_path : str
        Path to the accommodation data file (Excel or CSV)
    city_filter : str
        City name to filter accommodations (default: 'Berlin')
    limit : int, optional
        Limit the number of rows returned (useful for preview/testing)
    provider_filter : str, optional
        Filter by provider/platform name (e.g., 'Neonwood')
    
    Returns:
    --------
    pd.DataFrame
        Filtered dataframe containing only Berlin accommodations
    """
    try:
        # Try reading as CSV first (semicolon-separated based on data structure)
        if file_path.endswith('.csv'):
            # Try different encodings and separators
            try:
                df = pd.read_csv(file_path, sep=';', encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, sep=';', encoding='latin-1')
        else:
            # Excel file
            df = pd.read_excel(file_path)
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Filter for Berlin only
        # Check common city column names
        city_column = None
        for col in ['City', 'city', 'City Name', 'Stadt']:
            if col in df.columns:
                city_column = col
                break
        
        if city_column:
            df = df[df[city_column].str.contains(city_filter, case=False, na=False)]
        
        # Rename columns to standard names with flexible matching
        column_mapping = {}
        
        # DYNAMIC: Find rent column - try multiple strategies with flexible matching
        rent_found = False
        rent_keywords = ['rent', 'price', 'miete', 'all-in', 'all in', 'all-inclusive', 'all inclusive', 
                        'cost', 'kosten', 'preis', 'fee', 'charge', 'amount', 'betrag']
        
        for col in df.columns:
            col_lower = col.lower()
            # Match rent-related columns dynamically
            if any(keyword in col_lower for keyword in rent_keywords):
                column_mapping[col] = 'rent'
                rent_found = True
                break
        
        # DYNAMIC: Find address column - flexible matching with priority order
        address_found = False
        address_keywords_priority = [
            ['address', 'adresse'],  # Exact matches first
            ['street', 'strasse', 'straße', 'weg', 'allee', 'platz'],  # Street-related
            ['location', 'location name'],  # Location-related
            ['city', 'stadt'],  # City-related (fallback)
        ]
        
        for keyword_group in address_keywords_priority:
            if address_found:
                break
            for col in df.columns:
                col_lower = col.lower()
                if any(keyword in col_lower for keyword in keyword_group):
                    column_mapping[col] = 'address'
                    address_found = True
                    break
        
        # DYNAMIC: Find provider column - flexible matching
        provider_found = False
        provider_keywords = ['provider', 'platform', 'source', 'company', 'brand', 'supplier']
        
        for col in df.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in provider_keywords):
                column_mapping[col] = 'provider'
                provider_found = True
                break
        
        df = df.rename(columns=column_mapping)
        
        # Note: Warnings are handled in validate_data function
        
        # Clean rent column - remove currency symbols and convert to numeric
        # IMPORTANT: Don't filter out rooms without rent - just set them to NaN
        # This allows all rooms to be displayed even if rent data is missing
        if 'rent' in df.columns:
            # Convert to string first
            df['rent'] = df['rent'].astype(str)
            # Remove various currency symbols and characters
            df['rent'] = df['rent'].str.replace('€', '', regex=False)
            df['rent'] = df['rent'].str.replace('EUR', '', regex=False, case=False)
            df['rent'] = df['rent'].str.replace('Euro', '', regex=False, case=False)
            # Replace comma with dot for decimal
            df['rent'] = df['rent'].str.replace(',', '.', regex=False)
            # Remove any remaining non-numeric characters except dots
            df['rent'] = df['rent'].str.replace(r'[^\d.]', '', regex=True)
            # Strip whitespace
            df['rent'] = df['rent'].str.strip()
            # Convert to numeric (keep NaN for invalid values, don't filter out)
            df['rent'] = pd.to_numeric(df['rent'], errors='coerce')
            # DO NOT filter out rooms without rent - allow all rooms to be displayed
            # Rooms without rent will show as "N/A" in the UI
        
        # Clean address column with comprehensive regex patterns
        # IMPORTANT: For apartment names (like "BERLIN MITTE-WEDDING Classic Long Term 1"),
        # we preserve the full address to keep them unique, and let geocoding extract the location
        if 'address' in df.columns:
            import re
            df['address'] = df['address'].astype(str).str.strip()
            
            # Remove newlines, carriage returns, tabs
            df['address'] = df['address'].str.replace(r'[\n\r\t]+', ' ', regex=True)
            
            # Fix "BerlinGermany" -> "Berlin, Germany" (multiple variations)
            df['address'] = df['address'].str.replace(r'BerlinGermany', 'Berlin, Germany', regex=False)
            df['address'] = df['address'].str.replace(r'Berlin\s+Germany', 'Berlin, Germany', regex=True)
            df['address'] = df['address'].str.replace(r'Berlin\s*,?\s*Germany', 'Berlin, Germany', regex=True)
            
            # Remove provider names and unwanted text (case-insensitive)
            df['address'] = df['address'].str.replace(r'THE\s+URBAN\s+CLUB', '', regex=True, flags=re.IGNORECASE)
            df['address'] = df['address'].str.replace(r'URBAN\s+CLUB', '', regex=True, flags=re.IGNORECASE)
            
            # Remove "Plönzeile" variations (with umlauts and without)
            df['address'] = df['address'].str.replace(r'-\s*Pl[öo]n?zeile', '', regex=True, flags=re.IGNORECASE)
            df['address'] = df['address'].str.replace(r'Pl[öo]n?zeile\s*', '', regex=True, flags=re.IGNORECASE)
            df['address'] = df['address'].str.replace(r'\s*Pl[öo]n?zeile', '', regex=True, flags=re.IGNORECASE)
            
            # For apartment name patterns (like "BERLIN MITTE-WEDDING Classic Long Term 1"),
            # DO NOT remove the apartment-specific parts - keep them to preserve uniqueness
            # The geocoding function will extract the location name for geocoding
            
            # Fix postal code formats (ensure space before postal code)
            df['address'] = df['address'].str.replace(r',\s*(\d{5})', r', \1', regex=True)
            df['address'] = df['address'].str.replace(r'(\d{5})\s*Berlin', r'\1 Berlin', regex=True)
            
            # Remove multiple consecutive spaces
            df['address'] = df['address'].str.replace(r'\s+', ' ', regex=True)
            df['address'] = df['address'].str.strip()
            
            # Remove leading/trailing commas and clean up
            df['address'] = df['address'].str.replace(r'^,\s*', '', regex=True)
            df['address'] = df['address'].str.replace(r'\s*,+$', '', regex=True)
            df['address'] = df['address'].str.replace(r',\s*,+', ',', regex=True)
            
            # Ensure Berlin, Germany is at the end if not present
            # BUT: For apartment name patterns, keep the full name and let geocoding handle it
            for idx in df.index:
                addr = df.at[idx, 'address']
                if pd.notna(addr) and addr != '' and addr != 'nan':
                    # Check if it's an apartment name pattern (like "BERLIN MITTE-WEDDING Classic...")
                    is_apartment_name = re.match(r'^BERLIN\s+[A-ZÄÖÜ\s\-]+(?:Classic|Long|Term|Balcony|Silver|Neon)', addr, re.IGNORECASE)
                    
                    if is_apartment_name:
                        # For apartment names, ensure it ends with ", Germany" if needed
                        if not re.search(r'Germany', addr, re.IGNORECASE):
                            df.at[idx, 'address'] = f"{addr}, Germany"
                        # Keep the full address as-is (don't remove apartment-specific parts)
                        continue
                    
                    # For regular addresses, add Berlin, Germany if missing
                    if not re.search(r'Berlin', addr, re.IGNORECASE):
                        if not addr.endswith('Berlin'):
                            df.at[idx, 'address'] = f"{addr}, Berlin, Germany"
                    elif re.search(r'Berlin', addr, re.IGNORECASE) and not re.search(r'Germany', addr, re.IGNORECASE):
                        # Has Berlin but not Germany - add Germany
                        if not addr.endswith('Germany'):
                            # Insert ", Germany" before any trailing postal code or at end
                            if re.search(r'\d{5}\s*$', addr):
                                df.at[idx, 'address'] = re.sub(r'(\d{5})\s*$', r'\1, Germany', addr)
                            else:
                                df.at[idx, 'address'] = f"{addr}, Germany"
        
        # Filter by provider if specified (supports multiple providers separated by comma)
        if provider_filter and 'provider' in df.columns:
            # Split by comma and create filter for any matching provider
            provider_list = [p.strip() for p in provider_filter.split(',')]
            if len(provider_list) == 1:
                # Single provider
                df = df[df['provider'].str.contains(provider_list[0], case=False, na=False)]
                print(f"✓ Filtered to provider: {provider_list[0]} ({len(df)} rooms)")
            else:
                # Multiple providers
                filter_mask = df['provider'].str.contains(provider_list[0], case=False, na=False)
                for provider in provider_list[1:]:
                    filter_mask = filter_mask | df['provider'].str.contains(provider.strip(), case=False, na=False)
                df = df[filter_mask]
                print(f"✓ Filtered to providers: {', '.join(provider_list)} ({len(df)} rooms)")
        
        # Limit rows if specified (for preview/testing)
        if limit is not None and limit > 0:
            df = df.head(limit)
            print(f"✓ Limited to {limit} rows for preview")
        
        # Add index column for tracking
        df = df.reset_index(drop=True)
        df['apartment_id'] = df.index
        
        print(f"✓ Loaded {len(df)} accommodations from {city_filter}")
        
        return df
    
    except Exception as e:
        raise Exception(f"Error loading accommodation data: {str(e)}")


def validate_data(df):
    """
    Validate that the loaded data has required fields.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Accommodation dataframe
    
    Returns:
    --------
    bool
        True if data is valid, raises exception otherwise
    """
    # Rent column is optional - rooms without rent will show as "N/A"
    # Only check that we have some data
    if len(df) == 0:
        raise ValueError("No accommodations found after filtering")
    
    # Warn if rent column is missing, but don't fail
    if 'rent' not in df.columns:
        print("⚠ Warning: 'rent' column not found. Rooms will be displayed without rent information.")
    
    return True

