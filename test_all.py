"""Test script to fetch from Crossref API"""
import sys
import os
from datetime import UTC, datetime

# Change to project directory
os.chdir('F:/K4_Day10_Data-Pipeline-Data-Observability-VuaTuat')
sys.path.insert(0, '.')

# Now import the modules
try:
    from src.core.config import load_settings
    from src.ingestion.crossref import fetch_source_records
    from src.ingestion.cleaning import build_clean_dataframe
    
    print("All modules imported successfully!")
    
    # Load settings
    settings = load_settings()
    print(f"Settings loaded: source_query='{settings.source_query}'")
    print(f"  max_results: {settings.max_results}")
    print(f"  raw_api_response path: {settings.paths.raw_api_response}")
    print(f"  raw_records_json path: {settings.paths.raw_records_json}")
    print(f"  clean_csv path: {settings.paths.clean_csv}")
    print(f"  clean_json path: {settings.paths.clean_json}")
    
    # Try to fetch data
    print("\nAttempting to fetch data from Crossref...")
    records = fetch_source_records(settings)
    print(f"Successfully fetched {len(records)} records!")
    
    # Test cleaning
    print("\nTesting cleaning module...")
    run_date = datetime.now(UTC)
    df = build_clean_dataframe(records, run_date, settings)
    print(f"Cleaned DataFrame created with {len(df)} rows")
    print("\nSample rows:")
    print(df.head())
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()