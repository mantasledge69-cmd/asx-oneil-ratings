def clean_ticker(ticker: str) -> str:
    """Remove .AX suffix if present and normalise ticker"""
    if not ticker:
        return ""
    return ticker.replace('.AX', '').replace('.ax', '').strip().upper()
