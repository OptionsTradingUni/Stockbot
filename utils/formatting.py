def money(n: float) -> str:
    sign = "-" if n < 0 else ""
    return f"{sign}${abs(n):,.0f}"

def pct(n: float) -> str:
    return f"{n:.1f}%"

def top_list(lines):
    return "\n".join(lines)
