import random
from sqlalchemy import select, insert
from db import engine, success_stories
SUCCESS_TRADERS = {
    "male": [
        ("JohnDoeTrader", "John Doe", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male1.jpeg"),
        ("AlexJohnson", "Alex Johnson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male2.jpeg"),
        ("MichaelBrown", "Michael Brown", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male3.jpeg"),
        ("DavidMiller", "David Miller", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male4.jpeg"),
        ("ChrisAnderson", "Chris Anderson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male5.jpeg")
    ],
    "female": [
        ("JaneSmithPro", "Jane Smith", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female1.jpeg"),
        ("EmilyDavis", "Emily Davis", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female2.jpeg"),
        ("SarahWilson", "Sarah Wilson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female3.jpeg"),
        ("LauraTaylor", "Laura Taylor", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female4.jpeg"),
        ("AnnaMartinez", "Anna Martinez", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female5.jpeg")
    ],
}
TEMPLATES = {
    "male": [
        "transformed a modest ${deposit} into ${profit} with an AAPL swing trade.",
        "turned ${deposit} into ${profit} by mastering BTC HODL.",
        "flipped ${deposit} into ${profit} riding a NIKY pump.",
        "secured ${profit} profit with ETH DCA from ${deposit}.",
        "earned ${profit} using SOL arbitrage after ${deposit}.",
    ],
    "female": [
        "grew ${deposit} into ${profit} via TSLA scalps.",
        "boosted ${deposit} into ${profit} after a DOGE snipe.",
        "turned ${deposit} to ${profit} on a SHIB flip.",
        "made ${profit} from NVDA position trading starting with ${deposit}.",
        "grew ${deposit} to ${profit} on a GOOGL day trade.",
    ],
}

def initialize_stories():
    with engine.begin() as conn:
        existing = conn.execute(select(success_stories)).fetchall()
        if existing:
            # already initialized
            pass
        else:
            deposits = [300,400,500,600,700,800,1000,1200,1500,2000]
            random.shuffle(deposits)
            profits_used = set()
            for gender, arr in SUCCESS_TRADERS.items():
                for _, name, img in arr:
                    deposit = deposits.pop()
                    profit = None
                    while not profit or profit in profits_used:
                        raw = deposit * random.uniform(2, 8)
                        profit = int(round(raw / 50) * 50)
                    profits_used.add(profit)
                    story = random.choice(TEMPLATES[gender]).replace("${deposit}", f"${deposit:,}").replace("${profit}", f"${profit:,}")
                    conn.execute(insert(success_stories).values(trader_name=name, gender=gender, story=story, image=img))

    # return simple in-memory structure
    with engine.connect() as conn:
        rows = conn.execute(select(success_stories.c.trader_name, success_stories.c.story, success_stories.c.image, success_stories.c.gender)).fetchall()
    by_gender = {"male": [], "female": []}
    for n, s, img, g in rows:
        by_gender[g].append({"name": n, "story": s, "image": img})
    return by_gender
