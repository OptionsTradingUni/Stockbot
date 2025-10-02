from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, future=True)
metadata = MetaData()

# Rankings cache
rankings_cache = Table(
    "rankings_cache", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("content", String),
    Column("timestamp", DateTime),
    Column("scope", String, default="overall")
)

# Profit posts
posts = Table(
    "posts", metadata,
    Column("id", Integer, primary_key=True),
    Column("symbol", String),
    Column("content", String),
    Column("deposit", Float),
    Column("profit", Float),
    Column("posted_at", DateTime),
    Column("trader_id", String),
)

# Users
users = Table(
    "users", metadata,
    Column("user_id", String, primary_key=True),
    Column("username", String),
    Column("display_name", String),
    Column("wins", Integer),
    Column("total_trades", Integer),
    Column("total_profit", Float, default=0),
    Column("last_login", DateTime),
    Column("login_streak", Integer, default=0)
)

# Success Stories
success_stories = Table(
    "success_stories", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trader_name", String, unique=True),
    Column("gender", String),
    Column("story", String),
    Column("image", String)
)

# Hall of Fame
hall_of_fame = Table(
    "hall_of_fame", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trader_name", String),
    Column("profit", Float),
    Column("scope", String),  # daily, weekly, monthly
    Column("timestamp", DateTime)
)

# Trader Metadata
trader_metadata = Table(
    "trader_metadata", metadata,
    Column("trader_id", String, primary_key=True),
    Column("country", String),
    Column("win_streak", Integer, default=0),
    Column("level", String, default="Rookie"),
    Column("total_deposit", Float, default=0.0),
    Column("total_profit", Float, default=0.0),
    Column("achievements", String)
)

# Trending Tickers
trending_tickers = Table(
    "trending_tickers", metadata,
    Column("symbol", String, primary_key=True),
    Column("count", Integer, default=0),
    Column("last_posted", DateTime)
)

metadata.create_all(engine)
