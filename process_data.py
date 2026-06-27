#!/usr/bin/env python3
"""
process_data.py
Spatial data engineering pipeline for school vulnerability and accessibility
mapping in BAY States (Borno, Adamawa, Yobe), Nigeria.
"""

import os
import pandas as pd
import geopandas as gpd
from shapely.ops import unary_union

def clean_names(df):
    """
    Standardizes and verifies name spelling for accuracy (e.g., Girei, Tamuwa).
    """
    for col in ['name', 'School Name']:
        if col in df.columns:
            # Strip trailing/leading whitespaces
            df[col] = df[col].astype(str).str.strip()
            # Correct common name typos / abbreviations
            df[col] = df[col].str.replace(r'\bGiret\b', 'Girei', regex=True)
            df[col] = df[col].str.replace(r'\bTamu\b', 'Tamuwa', regex=True)
    return df

def deduplicate_spatial(gdf, radius_meters=50):
    """
    Deduplicates school entries sharing identical coordinates within a 50-meter radius
    using a greedy spatial index approach.
    """
    sindex = gdf.sindex
    to_drop = set()
    
    for idx, geom in gdf.geometry.items():
        if idx in to_drop:
            continue
        # Find all points within the 50-meter buffer
        possible_matches = sindex.query(geom.buffer(radius_meters), predicate='intersects')
        for match_idx in possible_matches:
            match_id = gdf.index[match_idx]
            if match_id != idx:
                to_drop.add(match_id)
                
    return gdf.drop(index=list(to_drop))

def main():
    # 1. Load school data (open schools) and conflict events
    print("Loading datasets...")
    schools_raw = pd.read_csv('data/raw/nga_bay_schools_with_status.csv')
    conflict_raw = pd.read_csv('data/raw/conflict_data_nga.csv')

    # Filter schools to keep open schools only
    schools = schools_raw[schools_raw['School Status'].str.strip().str.lower() == 'open'].copy()

    # 2. Filter both datasets strictly to keep rows in BAY States (Borno, Adamawa, Yobe)
    print("Filtering datasets to BAY states (Borno, Adamawa, Yobe)...")
    bay_states = {'Borno', 'Adamawa', 'Yobe'}
    
    # Filter schools
    schools = schools[schools['state_name'].str.strip().str.title().isin(bay_states)].copy()
    
    # Filter conflict events (cleaning 'adm_1' column to match state names)
    conflict_raw['state_clean'] = conflict_raw['adm_1'].astype(str).str.replace(r'(?i)\s+state', '', regex=True).str.strip().str.title()
    conflict = conflict_raw[conflict_raw['state_clean'].isin(bay_states)].copy()

    # 3. Clean data: Drop missing coords, drop duplicates, verify names
    print("Cleaning and verifying data...")
    schools = schools.dropna(subset=['latitude', 'longitude'])
    conflict = conflict.dropna(subset=['latitude', 'longitude'])
    
    # Drop exact row duplicates
    schools = schools.drop_duplicates()
    conflict = conflict.drop_duplicates()
    
    # Verify and correct school names
    schools = clean_names(schools)

    # 4. Convert both datasets to GeoDataFrames in EPSG:32632 (UTM Zone 32N)
    print("Converting to GeoDataFrames and projecting to EPSG:32632 (UTM Zone 32N)...")
    gdf_schools = gpd.GeoDataFrame(
        schools, 
        geometry=gpd.points_from_xy(schools['longitude'], schools['latitude']), 
        crs="EPSG:4326"
    ).to_crs("EPSG:32632")
    
    gdf_conflict = gpd.GeoDataFrame(
        conflict, 
        geometry=gpd.points_from_xy(conflict['longitude'], conflict['latitude']), 
        crs="EPSG:4326"
    ).to_crs("EPSG:32632")

    # Spatial deduplication within 50m radius for schools
    print("Deduplicating schools sharing coordinates within 50m...")
    gdf_schools = deduplicate_spatial(gdf_schools, radius_meters=50)

    # 5. Filter active conflict events, buffer by 5km, and create conflict corridors (unary union)
    print("Generating 5km conflict buffers and corridors...")
    active_conflict = gdf_conflict[gdf_conflict['active_year'].astype(str).str.strip().str.lower() == 'true'].copy()
    
    conflict_buffers = active_conflict.geometry.buffer(5000) # 5km = 5000m
    conflict_corridors = unary_union(conflict_buffers)

    # 6. Label school vulnerability based on intersection with conflict corridors
    print("Labeling school vulnerability and accessibility...")
    intersects_corridors = gdf_schools.geometry.intersects(conflict_corridors)
    
    gdf_schools['vulnerability'] = intersects_corridors.map({True: 'High', False: 'Low'})
    gdf_schools['accessibility'] = intersects_corridors.map({True: 'Inaccessible', False: 'Accessible'})

    # 7. Project back to EPSG:4326 and save output
    print("Projecting back to EPSG:4326 and saving to output file...")
    gdf_schools_out = gdf_schools.to_crs("EPSG:4326")
    
    # Ensure processed directory exists
    os.makedirs('data/processed', exist_ok=True)
    gdf_schools_out.to_file('data/processed/bay_schools.geojson', driver='GeoJSON')
    print(f"Pipeline complete! Output saved to 'data/processed/bay_schools.geojson' (Total schools: {len(gdf_schools_out)})")

if __name__ == '__main__':
    main()
