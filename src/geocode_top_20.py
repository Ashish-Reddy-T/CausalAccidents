#!/usr/bin/env python3
"""
Geocoding Script for Top 20 High-CATE H3 Cells
==============================================

This script geocodes the top 20 H3 cells identified in the heterogeneity analysis
from HETEROGENEITY_RESULTS.md and PIPELINE_SUMMARY.md.

It converts H3 cell IDs to lat/lon coordinates and then to actual street addresses
using the Nominatim geocoding service (OpenStreetMap).

Usage:
    python geocode_top_cells.py

Output:
    - Prints results to console
    - Saves to: data/top_20_geocoded.csv
"""

import pandas as pd
import h3
import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import sys

# Configuration
DATA_PATH = "../data/cate_by_h3_cells.csv"
OUTPUT_PATH = "../data/top_20_geocoded.csv"
TOP_N = 20
USER_AGENT = "anonymous"


def geocode_with_retry(lat: float, lon: float, geolocator, max_retries: int = 3) -> str:
    """
    Geocode lat/lon to address with retry logic.
    
    Args:
        lat: Latitude
        lon: Longitude
        geolocator: Geopy geolocator instance
        max_retries: Maximum number of retry attempts
        
    Returns:
        Address string or error message
    """
    for attempt in range(max_retries):
        try:
            location = geolocator.reverse((lat, lon), timeout=10)
            if location:
                return location.address
            else:
                return "Address not found"
        except GeocoderTimedOut:
            if attempt < max_retries - 1:
                print(f"  ⏳ Timeout, retrying... (attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            else:
                return "Geocoding timeout"
        except GeocoderServiceError as e:
            return f"Geocoding error: {str(e)}"
        except Exception as e:
            return f"Unknown error: {str(e)}"
    
    return "Geocoding failed after retries"


def main():
    print("=" * 70)
    print("NYC Rain Crash Risk - Top 20 H3 Cell Geocoding")
    print("=" * 70)
    print()
    
    # Load data
    print(f"📂 Loading data from: {DATA_PATH}")
    try:
        df = pd.read_csv(DATA_PATH)
    except FileNotFoundError:
        print(f"❌ Error: File not found: {DATA_PATH}")
        print("   Make sure you're running this from the project root directory.")
        sys.exit(1)
    
    print(f"✓ Loaded {len(df):,} H3 cells")
    print()
    
    # Get top N cells by CATE
    top_cells = df.nlargest(TOP_N, 'cate_mean').copy()
    print(f"🎯 Top {TOP_N} cells by mean CATE:")
    print(f"   Range: {top_cells['cate_mean'].min():.6f} to {top_cells['cate_mean'].max():.6f}")
    print()
    
    # Convert H3 to lat/lon
    print("🗺️  Converting H3 cells to coordinates...")
    top_cells['lat'] = top_cells['h3_index'].apply(lambda x: h3.cell_to_latlng(x)[0])
    top_cells['lon'] = top_cells['h3_index'].apply(lambda x: h3.cell_to_latlng(x)[1])
    print("✓ Conversion complete")
    print()
    
    # Initialize geocoder
    print("🌐 Initializing Nominatim geocoder (OpenStreetMap)...")
    geolocator = Nominatim(user_agent=USER_AGENT)
    print("✓ Geocoder ready")
    print()
    
    # Geocode each cell
    print(f"📍 Geocoding {TOP_N} locations...")
    print("   (This may take a minute - respecting rate limits)")
    print()
    
    addresses = []
    for idx, row in top_cells.iterrows():
        rank = len(addresses) + 1
        h3_id = row['h3_index']
        lat = row['lat']
        lon = row['lon']
        cate = row['cate_mean']
        
        print(f"[{rank:2d}/{TOP_N}] {h3_id}")
        print(f"        CATE: {cate:.6f} ({cate*100:.3f}%)")
        print(f"        Coords: ({lat:.6f}, {lon:.6f})")
        
        # Geocode
        address = geocode_with_retry(lat, lon, geolocator)
        addresses.append(address)
        
        print(f"        📌 {address}")
        print()
        
        # Rate limiting for Nominatim
        if rank < TOP_N:
            time.sleep(1.5)  # 1.5 second delay between requests
    
    # Add addresses to dataframe
    top_cells['address'] = addresses
    
    # Save results
    print("=" * 70)
    print(f"💾 Saving results to: {OUTPUT_PATH}")
    top_cells.to_csv(OUTPUT_PATH, index=False)
    print("✓ Saved successfully")
    print()
    
    # Summary statistics
    print("📊 Summary Statistics:")
    print(f"   • Total cells geocoded: {len(top_cells)}")
    print(f"   • Successful geocodes: {sum('not found' not in addr.lower() and 'error' not in addr.lower() and 'timeout' not in addr.lower() for addr in addresses)}")
    print(f"   • Mean CATE: {top_cells['cate_mean'].mean():.6f}")
    print(f"   • Std CATE: {top_cells['cate_mean'].std():.6f}")
    print()
    
    # Display top 5 for quick reference
    print("🏆 Top 5 Most Vulnerable Locations:")
    print("-" * 70)
    for i, row in top_cells.head(5).iterrows():
        print(f"{row.name + 1}. CATE: {row['cate_mean']:.6f} ({row['cate_mean']*100:.3f}%)")
        print(f"   H3: {row['h3_index']}")
        print(f"   📍 {row['address']}")
        print()
    
    print("=" * 70)
    print("✅ Geocoding complete!")
    print(f"   View full results in: {OUTPUT_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()
