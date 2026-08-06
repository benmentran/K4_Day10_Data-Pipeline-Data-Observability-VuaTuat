import sys
if 'src' in sys.path:
    sys.path.remove('src')
if 'src.core' in sys.path:
    sys.path.remove('src.core')
    
# Add the correct path
sys.path.insert(0, '.')

# Now try to import
from src.core.config import load_settings
settings = load_settings()
print('source_query:', settings.source_query)
print('source_filter:', settings.source_filter)
print('max_results:', settings.max_results)
print('raw_api_response path:', settings.paths.raw_api_response)
print('raw_records_json path:', settings.paths.raw_records_json)