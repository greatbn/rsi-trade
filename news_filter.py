import requests
import logging
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)

class NewsFilter:
    def __init__(self, config):
        self.config = config
        self.events = []
        self.last_fetch_time = None
        self.cache_duration = timedelta(hours=4)
        self.impact_levels = ['High'] # Default to High only
        if config.get('include_medium', False):
            self.impact_levels.append('Medium')

    def get_affected_currencies(self, symbol):
        """
        Map symbol to list of currencies.
        """
        # Basic Forex mapping
        if len(symbol) == 6:
            return [symbol[:3], symbol[3:]]
        
        # Gold/Indices
        if "XAU" in symbol or "GOLD" in symbol:
            return ['USD']
        if "BTC" in symbol:
            return ['USD']
        if "US30" in symbol or "DJI" in symbol:
            return ['USD']
            
        return ['USD'] # Default fallback

    def fetch_calendar(self):
        """
        Fetch calendar from public JSON endpoint.
        """
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                self.events = response.json()
                self.last_fetch_time = datetime.now()
                logger.info(f"Fetched {len(self.events)} news events.")
            else:
                logger.error(f"Failed to fetch calendar: {response.status_code}")
        except Exception as e:
            logger.error(f"Exception fetching calendar: {e}")

    def is_news_imminent(self, symbol):
        """
        Check if high-impact news is imminent for the symbol.
        Returns: (bool, event_title, minutes_to_event)
        """
        # Refresh cache if needed
        if not self.last_fetch_time or datetime.now() - self.last_fetch_time > self.cache_duration:
            self.fetch_calendar()

        if not self.events:
            return False, None, None

        currencies = self.get_affected_currencies(symbol)
        now = datetime.now().astimezone() # Aware datetime
        
        minutes_before = self.config.get('minutes_before', 30)
        minutes_after = self.config.get('minutes_after', 30)

        for event in self.events:
            # Filter by Currency
            if event['country'] not in currencies and event['country'] != 'All':
                continue
                
            # Filter by Impact
            if event['impact'] not in self.impact_levels:
                continue

            # Parse Date
            try:
                # Format: "2025-11-25T08:30:00-05:00"
                # Python 3.7+ supports fromisoformat
                event_time = datetime.fromisoformat(event['date'])
            except ValueError:
                continue

            # Check Time Window
            # Event is in future (or recent past)
            # We pause if: event_time - before <= now <= event_time + after
            
            start_pause = event_time - timedelta(minutes=minutes_before)
            end_pause = event_time + timedelta(minutes=minutes_after)

            if start_pause <= now <= end_pause:
                time_to_event = (event_time - now).total_seconds() / 60
                return True, event['title'], time_to_event

        return False, None, None
