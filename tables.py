import pathlib
import sqlite3

from skill_store import initialize_skill_store

db_path = (
    pathlib.Path(__file__).resolve().parent
    / "database"
    / "database.db"
)

schema = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cities (
    city_id TEXT PRIMARY KEY NOT NULL,
    city_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS places (
    place_id TEXT PRIMARY KEY NOT NULL,
    place_name TEXT NOT NULL,
    city_id TEXT NOT NULL,
    FOREIGN KEY (city_id) REFERENCES cities(city_id)
);

CREATE TABLE IF NOT EXISTS restaurants (
    restaurant_id TEXT PRIMARY KEY NOT NULL,
    restaurant_name TEXT NOT NULL,
    place_id TEXT NOT NULL,
    FOREIGN KEY (place_id) REFERENCES places(place_id)
);

CREATE TABLE IF NOT EXISTS cuisines (
    cuisine_id TEXT PRIMARY KEY NOT NULL,
    cuisine_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS restaurant_cuisines (
    restaurant_id TEXT NOT NULL,
    cuisine_id TEXT NOT NULL,
    PRIMARY KEY (restaurant_id, cuisine_id),
    FOREIGN KEY (restaurant_id)
        REFERENCES restaurants(restaurant_id) ON DELETE CASCADE,
    FOREIGN KEY (cuisine_id)
        REFERENCES cuisines(cuisine_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS menu_items (
    item_id TEXT PRIMARY KEY NOT NULL,
    restaurant_id TEXT NOT NULL,
    item_name TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0),
    best_seller INTEGER NOT NULL DEFAULT 0
        CHECK (best_seller IN (0, 1)),
    FOREIGN KEY (restaurant_id)
        REFERENCES restaurants(restaurant_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS restaurant_ratings (
    rating_id TEXT PRIMARY KEY NOT NULL,
    restaurant_id TEXT NOT NULL,
    dining_rating REAL,
    delivery_rating REAL,
    dining_votes INTEGER NOT NULL DEFAULT 0,
    delivery_votes INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (restaurant_id)
        REFERENCES restaurants(restaurant_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS menu_item_metrics (
    metric_id TEXT PRIMARY KEY NOT NULL,
    item_id TEXT NOT NULL,
    votes INTEGER NOT NULL DEFAULT 0,
    average_rating REAL,
    total_votes INTEGER NOT NULL DEFAULT 0,
    price_per_vote REAL,
    log_price REAL,
    is_bestseller INTEGER NOT NULL DEFAULT 0
        CHECK (is_bestseller IN (0, 1)),
    is_highly_rated INTEGER NOT NULL DEFAULT 0
        CHECK (is_highly_rated IN (0, 1)),
    is_expensive INTEGER NOT NULL DEFAULT 0
        CHECK (is_expensive IN (0, 1)),
    FOREIGN KEY (item_id)
        REFERENCES menu_items(item_id) ON DELETE CASCADE
);
"""

db_path.parent.mkdir(parents=True, exist_ok=True)

with sqlite3.connect(db_path) as connection:
    connection.executescript(schema)

initialize_skill_store(db_path=db_path)

print(f"Tables created in: {db_path}")
