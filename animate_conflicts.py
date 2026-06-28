#!/usr/bin/env python3
"""
animate_conflicts.py

Uses Folium's HeatMapWithTime plugin to animate ACLED conflict points in
the BAY states of Nigeria over the latest 12 months available in the dataset.
Overlays school locations as static markers.
"""

import os
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import HeatMapWithTime

def main():
    print("Starting animation compilation pipeline...")
    
    # 1. Load conflict and school data
    conflict_path = 'data/raw/conflict_data_nga.csv'
    schools_geojson_path = 'data/processed/bay_schools.geojson'
    
    if not os.path.exists(conflict_path):
        raise FileNotFoundError("Raw conflict data not found. Please run the process_data.py script first.")
    
    conflict_df = pd.read_csv(conflict_path)
    
    # Load schools - fallback if geojson isn't processed yet
    if os.path.exists(schools_geojson_path):
        schools_gdf = gpd.read_file(schools_geojson_path)
    else:
        print("Processed schools not found. Processing raw data...")
        from upgrade_map import process_spatial_data
        schools_gdf, _, _ = process_spatial_data()

    # 2. Filter conflicts to BAY States and parse dates
    print("Filtering and formatting conflict dates...")
    bay_states = {'Borno', 'Adamawa', 'Yobe'}
    conflict_df['state_clean'] = conflict_df['adm_1'].astype(str).str.replace(
        r'(?i)\s+state', '', regex=True
    ).str.strip().str.title()
    
    conflict_df = conflict_df[
        conflict_df['state_clean'].isin(bay_states) & 
        conflict_df['latitude'].notna() & 
        conflict_df['longitude'].notna()
    ].copy()
    
    conflict_df['date'] = pd.to_datetime(conflict_df['date_start'])

    # 3. Restrict to the latest 12 months in the dataset
    max_date = conflict_df['date'].max()
    start_date = max_date - pd.DateOffset(months=12)
    print(f"Data ranges from {conflict_df['date'].min().strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}.")
    print(f"Filtering last 12 months: {start_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
    
    recent_conflicts = conflict_df[
        (conflict_df['date'] >= start_date) & 
        (conflict_df['date'] <= max_date)
    ].copy()
    
    # 4. Group data by Month
    recent_conflicts['year_month'] = recent_conflicts['date'].dt.to_period('M')
    sorted_months = sorted(recent_conflicts['year_month'].unique())
    
    time_data = []
    time_index = []
    
    for month in sorted_months:
        month_df = recent_conflicts[recent_conflicts['year_month'] == month]
        # Extract points as [latitude, longitude] pairs for the HeatMap
        points = month_df[['latitude', 'longitude']].values.tolist()
        time_data.append(points)
        time_index.append(month.strftime('%Y-%B'))
        print(f" - {month.strftime('%Y-%B')}: {len(points)} conflict events")

    # 5. Initialize dark Folium Map centered on BAY region
    m = folium.Map(
        location=[11.5, 13.0], 
        zoom_start=7.5, 
        tiles='cartodb dark_matter',
        control_scale=True
    )

    # 6. Add the Animated HeatMap layer
    print("Adding HeatMapWithTime layer...")
    # radius controls heat radius, max_opacity controls max opacity, auto_play auto-starts
    heatmap_animated = HeatMapWithTime(
        data=time_data,
        index=time_index,
        radius=14,
        max_opacity=0.75,
        auto_play=True,
        display_index=True,
        name='Animated Conflict Heatmap (Last 12 Months)'
    )
    heatmap_animated.add_to(m)

    # 7. Add GRID3 Schools as a Static Overlay Layer
    print("Overlaying static school markers...")
    schools_layer = folium.FeatureGroup(name='GRID3 School Locations (Static)', show=True)
    
    for _, row in schools_gdf.iterrows():
        lat = row['geometry'].y
        lng = row['geometry'].x
        name = row.get('School Name', 'Unnamed School')
        vuln = row.get('vulnerability', 'Low')
        
        # Color coding matching previous system (Red = High Vulnerability, Green = Low)
        color = '#ef4444' if vuln == 'High' else '#10b981'
        
        # Add Circle Marker
        folium.CircleMarker(
            location=[lat, lng],
            radius=2.5,
            color='#020617', # Outline
            weight=0.5,
            fill_color=color,
            fill_opacity=0.9,
            tooltip=f"{name} ({vuln} Vulnerability)"
        ).add_to(schools_layer)
        
    schools_layer.add_to(m)

    # Add layer control to toggle layers
    folium.LayerControl(collapsed=False).add_to(m)

    # 8. Save map
    os.makedirs('docs', exist_ok=True)
    output_path = 'docs/conflict_animation.html'
    m.save(output_path)
    print(f"Animation created successfully! Saved to '{output_path}'")

if __name__ == '__main__':
    main()
