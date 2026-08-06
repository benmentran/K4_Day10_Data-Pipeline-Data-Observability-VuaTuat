"""Check settings and test Crossref fetch"""
from src.core.config import load_settings

settings = load_settings()
print("source_query:", settings.source_query)
print("source_filter:", settings.source_filter)
print("max_results:", settings.max_results)