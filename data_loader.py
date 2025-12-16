import pandas as pd
import numpy as np
import re

def load_accommodation_data(file_path, city_filter='Berlin', limit=None, provider_filter=None):
    try:
        if file_path.endswith('.csv'):
            try:
                df = pd.read_csv(file_path, sep=';', encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, sep=';', encoding='latin-1')
        else:
            df = pd.read_excel(file_path)
        
        df.columns = df.columns.str.strip()
        
        city_column = None
        for col in ['City', 'city', 'City Name', 'Stadt']:
            if col in df.columns:
                city_column = col
                break
        
        if city_column:
            df = df[df[city_column].str.contains(city_filter, case=False, na=False)]
        
        column_mapping = {}
        
        rent_found = False
        rent_keywords = ['rent', 'price', 'miete', 'all-in', 'all in', 'all-inclusive', 'all inclusive', 
                        'cost', 'kosten', 'preis', 'fee', 'charge', 'amount', 'betrag']
        
        for col in df.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in rent_keywords):
                column_mapping[col] = 'rent'
                rent_found = True
                break
        
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
        
        provider_found = False
        provider_keywords = ['provider', 'platform', 'source', 'company', 'brand', 'supplier']
        
        for col in df.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in provider_keywords):
                column_mapping[col] = 'provider'
                provider_found = True
                break
        
        df = df.rename(columns=column_mapping)
        
        
        if 'rent' in df.columns:
            df['rent'] = df['rent'].astype(str)
            df['rent'] = df['rent'].str.replace('€', '', regex=False)
            df['rent'] = df['rent'].str.replace('EUR', '', regex=False, case=False)
            df['rent'] = df['rent'].str.replace('Euro', '', regex=False, case=False)
            df['rent'] = df['rent'].str.replace(',', '.', regex=False)
            df['rent'] = df['rent'].str.replace(r'[^\d.]', '', regex=True)
            df['rent'] = df['rent'].str.strip()
            df['rent'] = pd.to_numeric(df['rent'], errors='coerce')
        
        if 'address' in df.columns:
            df['address'] = df['address'].astype(str).str.strip()
            
            df['address'] = df['address'].str.replace(r'[\n\r\t]+', ' ', regex=True)
            
            df['address'] = df['address'].str.replace(r'BerlinGermany', 'Berlin, Germany', regex=False)
            df['address'] = df['address'].str.replace(r'Berlin\s+Germany', 'Berlin, Germany', regex=True)
            df['address'] = df['address'].str.replace(r'Berlin\s*,?\s*Germany', 'Berlin, Germany', regex=True)
            
            df['address'] = df['address'].str.replace(r'THE\s+URBAN\s+CLUB', '', regex=True, flags=re.IGNORECASE)
            df['address'] = df['address'].str.replace(r'URBAN\s+CLUB', '', regex=True, flags=re.IGNORECASE)
            
            df['address'] = df['address'].str.replace(r'-\s*Pl[öo]n?zeile', '', regex=True, flags=re.IGNORECASE)
            df['address'] = df['address'].str.replace(r'Pl[öo]n?zeile\s*', '', regex=True, flags=re.IGNORECASE)
            df['address'] = df['address'].str.replace(r'\s*Pl[öo]n?zeile', '', regex=True, flags=re.IGNORECASE)
            
            
            df['address'] = df['address'].str.replace(r',\s*(\d{5})', r', \1', regex=True)
            df['address'] = df['address'].str.replace(r'(\d{5})\s*Berlin', r'\1 Berlin', regex=True)
            
            df['address'] = df['address'].str.replace(r'\s+', ' ', regex=True)
            df['address'] = df['address'].str.strip()
            
            df['address'] = df['address'].str.replace(r'^,\s*', '', regex=True)
            df['address'] = df['address'].str.replace(r'\s*,+$', '', regex=True)
            df['address'] = df['address'].str.replace(r',\s*,+', ',', regex=True)
            
            non_berlin_cities = ['Hoppegarten', 'Potsdam', 'Hamburg', 'Munich', 'München', 'Frankfurt', 'Cologne', 'Köln', 'Neuenhagen', 'Teltow', 'Schönefeld', 'Ahrensfelde', 'Hennigsdorf', 'Glienicke', 'Nuthetal', 'Schöneiche', 'Stahnsdorf', 'Falkensee', 'Blankenfelde-Mahlow', 'Kleinmachnow', 'Schönwalde-Glien', 'Schulzendorf', 'Zeuthen', 'Bernau', 'Panketal', 'Fredersdorf', 'Großbeeren']
            
            for idx in df.index:
                addr = df.at[idx, 'address']
                if pd.notna(addr) and addr != '' and addr != 'nan':
                    addr = re.sub(r'BER\s+[MS]\s+mit\s+Balkon\s+', '', addr, flags=re.IGNORECASE)
                    addr = re.sub(r'BER\s+[MS]\s+mit\s+Balkon', '', addr, flags=re.IGNORECASE)
                    
                    for wrong_city in non_berlin_cities:
                        if wrong_city in addr:
                            addr = re.sub(f'{wrong_city},?', '', addr, flags=re.IGNORECASE)
                            addr = re.sub(r'\s+', ' ', addr).strip()
                            addr = re.sub(r',\s*,+', ',', addr)  # Remove double commas
                    
                    is_apartment_name = re.match(r'^BERLIN\s+[A-ZÄÖÜ\s\-]+(?:Classic|Long|Term|Balcony|Silver|Neon)', addr, re.IGNORECASE)
                    
                    if is_apartment_name:
                        if not re.search(r'Germany', addr, re.IGNORECASE):
                            df.at[idx, 'address'] = f"{addr}, Germany"
                        continue
                    
                    if not re.search(r'Berlin', addr, re.IGNORECASE):
                        if not addr.endswith('Berlin'):
                            df.at[idx, 'address'] = f"{addr}, Berlin, Germany"
                    elif re.search(r'Berlin', addr, re.IGNORECASE) and not re.search(r'Germany', addr, re.IGNORECASE):
                        if not addr.endswith('Germany'):
                            if re.search(r'\d{5}\s*$', addr):
                                df.at[idx, 'address'] = re.sub(r'(\d{5})\s*$', r'\1, Germany', addr)
                            else:
                                df.at[idx, 'address'] = f"{addr}, Germany"
                    
                    df.at[idx, 'address'] = addr
        
        if provider_filter and 'provider' in df.columns:
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
            
        
        if limit is not None and limit > 0:
            df = df.head(limit)
            print(f"✓ Limited to {limit} rows for preview")
        
        df = df.reset_index(drop=True)
        df['apartment_id'] = df.index
        
        print(f"✓ Loaded {len(df)} accommodations from {city_filter}")
        
        return df
    
    except Exception as e:
        raise Exception(f"Error loading accommodation data: {str(e)}")

def validate_data(df):
    if len(df) == 0:
        raise ValueError("No accommodations found after filtering")
    
    if 'rent' not in df.columns:
        print("⚠ Warning: 'rent' column not found. Rooms will be displayed without rent information.")
    
    return True

