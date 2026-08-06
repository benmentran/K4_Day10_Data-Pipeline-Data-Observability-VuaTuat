"""Direct import of crossref and cleaning modules to test"""
import sys
import importlib.util

# Import crossref module directly
spec = importlib.util.spec_from_file_location('crossref', 'F:\\K4_Day10_Data-Pipeline-Data-Observability-VuaTuat\\src\\ingestion\\crossref.py')
crossref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crossref)

# Import cleaning module directly
spec = importlib.util.spec_from_file_location('cleaning', 'F:\\K4_Day10_Data-Pipeline-Data-Observability-VuaTuat\\src\\ingestion\\cleaning.py')
cleaning = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleaning)

# Import config module directly
spec = importlib.util.spec_from_file_location('config', 'F:\\K4_Day10_Data-Pipeline-Data-Observability-VuaTuat\\src\\core\\config.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

# Now test the modules
print("Config loaded successfully!")
print("Config has load_settings:", hasattr(config, 'load_settings'))

print("\nCrossref module has:")
print("  PaperRecord:", hasattr(crossref, 'PaperRecord'))
print("  parse_crossref_payload:", hasattr(crossref, 'parse_crossref_payload'))
print("  fetch_source_records:", hasattr(crossref, 'fetch_source_records'))

print("\nCleaning module has:")
print("  build_clean_dataframe:", hasattr(cleaning, 'build_clean_dataframe'))
print("  _strip_html_tags:", hasattr(cleaning, '_strip_html_tags'))

# Try to load settings
settings = config.load_settings()
print(f"\nSettings loaded:")
print(f"  source_query: {settings.source_query}")
print(f"  source_filter: {settings.source_filter}")
print(f"  max_results: {settings.max_results}")