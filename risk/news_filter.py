from datetime import datetime

def is_news_blackout(current_time: datetime, config):
    """
    Checks if the current time falls within a configured news blackout window.
    """
    if not hasattr(config, "NEWS_BLACKOUT_WINDOWS") or not config.NEWS_BLACKOUT_WINDOWS:
        return False
        
    current_day = current_time.weekday()
    current_time_str = current_time.strftime("%H:%M")
    
    for window in config.NEWS_BLACKOUT_WINDOWS:
        if window["day"] == current_day:
            if window["start"] <= current_time_str <= window["end"]:
                return True
                
    return False
