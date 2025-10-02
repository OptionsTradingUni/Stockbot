# Traders mapped to specific countries
COUNTRY_TRADERS = {
    "USA": [
        ("RobertGarcia", "Robert Garcia"),
        ("JamesLopez", "James Lopez"),
        ("WilliamRodriguez", "William Rodriguez"),
        ("DanielPerez", "Daniel Perez"),
        ("MatthewRamirez", "Matthew Ramirez"),
        ("EthanLee", "Ethan Lee"),
        ("BenjaminScott", "Benjamin Scott"),
        ("LucasBaker", "Lucas Baker"),
    ],
    "Nigeria": [
        ("ChineduOkafor", "Chinedu Okafor"),
        ("ToluChris", "Tolu Chris"),
        ("EmekaIfeanyi", "Emeka Ifeanyi"),
        ("NgoziOkeke", "Ngozi Okeke"),
        ("BlessingAdebayo", "Blessing Adebayo"),
        ("OluwaseunAdeyemi", "Oluwaseun Adeyemi"),
        ("AmakaNwosu", "Amaka Nwosu"),
        ("SamuelEze", "Samuel Eze"),
    ],
    "UK": [
        ("HenryAllen", "Henry Allen"),
        ("SamuelGreen", "Samuel Green"),
        ("ThomasClark", "Thomas Clark"),
        ("JosephTurner", "Joseph Turner"),
        ("NathanielReed", "Nathaniel Reed"),
        ("AnthonyKing", "Anthony King"),
        ("DavidWright", "David Wright"),
        ("ChristopherHill", "Christopher Hill"),
    ],
    "India": [
        ("RajeshKumar", "Rajesh Kumar"),
        ("AmitSharma", "Amit Sharma"),
        ("PriyaPatel", "Priya Patel"),
        ("AnjaliVerma", "Anjali Verma"),
        ("RahulSingh", "Rahul Singh"),
        ("DeepakMehta", "Deepak Mehta"),
        ("SnehaReddy", "Sneha Reddy"),
        ("ArjunGupta", "Arjun Gupta"),
    ],
    "China": [
        ("LiWei", "Li Wei"),
        ("ZhangWei", "Zhang Wei"),
        ("WangFang", "Wang Fang"),
        ("ChenMing", "Chen Ming"),
        ("LiuYang", "Liu Yang"),
        ("ZhaoHui", "Zhao Hui"),
        ("SunLei", "Sun Lei"),
        ("WuXiao", "Wu Xiao"),
    ],
    "Brazil": [
        ("CarlosMendez", "Carlos Mendez"),
        ("MateoVargas", "Mateo Vargas"),
        ("AndresMorales", "Andres Morales"),
        ("JoseMartinez", "Jose Martinez"),
        ("PedroLopez", "Pedro Lopez"),
        ("VictorSantos", "Victor Santos"),
        ("RicardoAlvarez", "Ricardo Alvarez"),
        ("FelipeSilva", "Felipe Silva"),
    ],
    "France": [
        ("JulienMoreau", "Julien Moreau"),
        ("ClaireDubois", "Claire Dubois"),
        ("AntoineLefevre", "Antoine Lefevre"),
        ("CamilleGirard", "Camille Girard"),
        ("LouisMartin", "Louis Martin"),
        ("SophieLaurent", "Sophie Laurent"),
        ("HugoRoux", "Hugo Roux"),
        ("EliseMercier", "Elise Mercier"),
    ],
    # You can continue defining for UK, Japan, Russia, Germany, etc.
}

# Flattened list (all traders, still useful in leaderboards/rankings)
RANKING_TRADERS = [trader for country, traders in COUNTRY_TRADERS.items() for trader in traders]
SUCCESS_TRADERS = {
    "male": [
        ("JohnDoeTrader", "John Doe", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male1.jpeg"),
        ("AlexJohnson", "Alex Johnson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male2.jpeg"),
        ("MichaelBrown", "Michael Brown", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male3.jpeg"),
        ("DavidMiller", "David Miller", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male4.jpeg"),
        ("ChrisAnderson", "Chris Anderson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male5.jpeg"),
    ],
    "female": [
        ("JaneSmithPro", "Jane Smith", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female1.jpeg"),
        ("EmilyDavis", "Emily Davis", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female2.jpeg"),
        ("SarahWilson", "Sarah Wilson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female3.jpeg"),
        ("LauraTaylor", "Laura Taylor", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female4.jpeg"),
        ("AnnaMartinez", "Anna Martinez", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female5.jpeg"),
    ],
}

SUCCESS_STORY_TEMPLATES = {
    "male": [
        "transformed a modest ${deposit} investment into an impressive ${profit} through a meticulously planned swing trade on AAPL.",
        "turned ${deposit} into a remarkable ${profit} by mastering the art of BTC HODL.",
        "flipped a ${deposit} stake into ${profit} with a bold NIKY pump riding move.",
        "achieved a stunning ${profit} profit from a strategic ETH DCA plan starting with ${deposit}.",
        "earned ${profit} through a clever SOL arbitrage play after investing ${deposit}.",
    ],
    "female": [
        "grew a ${deposit} investment into ${profit} with a disciplined TSLA scalping strategy.",
        "boosted ${deposit} into ${profit} with an early sniping move on DOGE.",
        "turned ${deposit} into ${profit} via a SHIB community flip.",
        "made ${profit} from a NVDA position trade starting with ${deposit}.",
        "grew ${deposit} into ${profit} with a GOOGL day trading plan.",
    ],
}

NEWS_CATALYSTS = {
    "stocks": [
        "surged after strong earnings",
        "climbed on analyst upgrade",
        "rallied on new product launch",
        "gained on partnership news",
        "spiked with positive sentiment",
    ],
    "crypto": [
        "pumped after whale accumulation",
        "rose on adoption news",
        "surged on protocol upgrade",
        "gained after exchange listing",
        "spiked with DeFi integration",
    ],
    "meme_coins": [
        "mooned after viral tweet",
        "pumped on community hype",
        "surged with influencer shoutout",
        "rocketed after Reddit buzz",
        "spiked on meme-driven volume",
    ],
}
