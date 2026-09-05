import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

FF_XML_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"

# Cache variables to prevent 429 Too Many Requests
_news_cache = []
_last_fetch_time = None
_CACHE_DURATION_HOURS = 4

def get_upcoming_news(config):
    """
    Fetches the ForexFactory XML calendar and parses it for High-Impact USD and Gold events.
    Uses a cache to avoid hitting the API too frequently.
    """
    global _news_cache, _last_fetch_time
    
    if _last_fetch_time is not None:
        if (datetime.now() - _last_fetch_time).total_seconds() < _CACHE_DURATION_HOURS * 3600:
            return _news_cache

    upcoming_events = []
    try:
        response = requests.get(FF_XML_URL, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        
        for event in root.findall('event'):
            country = event.find('country').text
            impact = event.find('impact').text
            title = event.find('title').text
            date_str = event.find('date').text
            time_str = event.find('time').text
            forecast = event.find('forecast').text
            actual = event.find('previous').text # Using previous as actual is not available until the event
            
            # We care about High Impact (High) USD news
            if country == "USD" and impact == "High":
                try:
                    # FF uses Eastern time, let's parse it as naive for now and let the system handle localization if needed
                    # Format is date: "09-06-2026", time: "8:30am"
                    dt_str = f"{date_str} {time_str}"
                    event_time = datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p")
                    
                    upcoming_events.append({
                        "event": title,
                        "time": event_time,
                        "forecast": forecast,
                        "actual": actual,
                        "impact": "high",
                        "currency": country
                    })
                except Exception as e:
                    logger.warning(f"Error parsing date/time for event {title}: {e}")
                    
        _news_cache = upcoming_events
        _last_fetch_time = datetime.now()
                    
    except Exception as e:
        logger.error(f"Failed to fetch or parse ForexFactory XML: {e}")
        
    return _news_cache

def get_news_bias(event):
    """
    Classifies a news event as bullish, bearish, or neutral based on actual vs forecast.
    """
    if event.get("actual") is None or event.get("forecast") is None:
        return "neutral"
        
    try:
        # Some values might be "1.2%" or "500K", we need to strip non-numeric
        def parse_val(val_str):
            import re
            num_str = re.sub(r'[^\d.-]', '', str(val_str))
            return float(num_str) if num_str else 0.0

        actual = parse_val(event["actual"])
        forecast = parse_val(event["forecast"])
        diff = actual - forecast
        
        title = event["event"].lower()
        
        if "nfp" in title or "non-farm" in title:
            return "bearish" if diff > 0 else "bullish"
        elif "cpi" in title:
            return "bearish" if diff > 0 else "bullish"
        elif "fomc" in title or "rate" in title:
            return "bearish" if diff > 0 else "bullish"
            
        return "neutral"
    except Exception as e:
        logger.warning(f"Error calculating news bias: {e}")
        return "neutral"
