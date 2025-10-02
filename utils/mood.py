import random

def market_mood():
    # Weighted, smoother, not scammy swingy
    # 50% Neutral, 30% Mild Bull, 15% Mild Bear, 5% Extreme
    r = random.random()
    if r < 0.5:
        return "🟡 Neutral (48–52/100)"
    if r < 0.8:
        return "🐂 Mild Bullish (55–65/100)"
    if r < 0.95:
        return "🐻 Mild Bearish (35–45/100)"
    return random.choice(["🚀 Greed Spike (70–80/100)", "⛔ Fear Spike (20–30/100)"])
