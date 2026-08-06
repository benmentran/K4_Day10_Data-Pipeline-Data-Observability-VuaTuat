import sys

# Remove the problematic src from sys.path (the one from site-packages)
sys.path = [p for p in sys.path if 'site-packages' not in p or 'src' not in p]

# Add the current directory to the path
sys.path.insert(0, '.')

# Now import
from src.core.config import load_settings
settings = load_settings()
print('source_query:', settings.source_query)
print('source_filter:', settings.source_filter)
print('max_results:', settings.max_results)
print('raw_api_response path:', settings.paths.raw_api_response)
print('raw_records_json path:', settings.paths.raw_records_json)