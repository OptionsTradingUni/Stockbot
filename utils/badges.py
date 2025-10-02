import random

def assign_badge(total_profit, deposit=1000, win_streak=0):
    badges = []
    if deposit >= 20000:
        badges.append("🐳 Whale")
    if total_profit >= 10000:
        badges.append("💰 Big Winner")
    if win_streak >= 5:
        badges.append("🔥 Streak Master")
    if total_profit / max(deposit, 1) > 20:
        badges.append("🚀 Moonshot King")
    if random.random() < 0.05:
        badges.append("💎 Diamond Hands")
    return f" {random.choice(badges)}" if badges else ""
