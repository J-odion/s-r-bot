# Mock news feed to be replaced with a real ForexFactory API integration
from datetime import datetime

def get_upcoming_news(config):
    """
    Returns a list of upcoming news events.
    In a real implementation, this would fetch from a calendar API.
    Format: {"event": "NFP", "time": datetime, "forecast": X, "actual": Y, "impact": "high"}
    """
    # For now, return an empty list to avoid blocking execution in v1 without API
    return []

def get_news_bias(event):
    """
    Classifies a news event as bullish, bearish, or neutral based on actual vs forecast.
    """
    if event.get("actual") is None or event.get("forecast") is None:
        return "neutral"
        
    diff = event["actual"] - event["forecast"]
    
    # Very simplified heuristics based on spec
    if event["event"] == "NFP":
        return "bearish" if diff > 0 else "bullish"
    elif event["event"] == "CPI":
        return "bearish" if diff > 0 else "bullish"
    elif event["event"] == "FOMC":
        return "bearish" if diff > 0 else "bullish" # Hawkish = higher rate = bearish gold
        
    return "neutral"
