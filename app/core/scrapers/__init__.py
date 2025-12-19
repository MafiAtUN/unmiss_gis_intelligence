"""Web scrapers for village location data."""
from app.core.scrapers.base import BaseScraper
from app.core.scrapers.osm_scraper import OSMScraper

__all__ = ["BaseScraper", "OSMScraper"]

