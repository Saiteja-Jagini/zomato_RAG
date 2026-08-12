import csv
import pathlib
import sqlite3
import uuid

ROOT = pathlib.Path(__file__).resolve().parent
CSV_PATH = ROOT / "enhanced_zomato_dataset_clean.csv"
DB_PATH = ROOT / "database" / "database.db"


def new_id():
    return str(uuid.uuid4())


def text(value):
    value = (value or "").strip()
    return value or None


def integer(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


with sqlite3.connect(DB_PATH) as connection:
    connection.execute("PRAGMA foreign_keys = ON")

    # Avoid importing the entire CSV twice.
    existing = connection.execute(
        "SELECT COUNT(*) FROM menu_items"
    ).fetchone()[0]

    if existing:
        raise RuntimeError(
            f"Database already contains {existing} menu items. "
            "Import was stopped to prevent duplicates."
        )

    city_ids = {}
    place_ids = {}
    restaurant_ids = {}
    cuisine_ids = {}
    rated_restaurants = set()

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        for row_number, row in enumerate(reader, start=2):
            city_name = text(row["City"])
            place_name = text(row["Place_Name"])
            restaurant_name = text(row["Restaurant_Name"])
            cuisine_name = text(row["Cuisine"])
            item_name = text(row["Item_Name"])

            if not all(
                [city_name, place_name, restaurant_name, cuisine_name, item_name]
            ):
                print(f"Skipping incomplete CSV row {row_number}")
                continue

            # City
            if city_name not in city_ids:
                city_id = new_id()
                connection.execute(
                    """
                    INSERT OR IGNORE INTO cities (city_id, city_name)
                    VALUES (?, ?)
                    """,
                    (city_id, city_name),
                )
                city_id = connection.execute(
                    "SELECT city_id FROM cities WHERE city_name = ?",
                    (city_name,),
                ).fetchone()[0]

                city_ids[city_name] = city_id

            city_id = city_ids[city_name]

            # Place
            place_key = (city_id, place_name)

            if place_key not in place_ids:
                place_id = new_id()
                connection.execute(
                    """
                    INSERT INTO places (place_id, place_name, city_id)
                    VALUES (?, ?, ?)
                    """,
                    (place_id, place_name, city_id),
                )
                place_ids[place_key] = place_id

            place_id = place_ids[place_key]

            # Restaurant
            restaurant_key = (place_id, restaurant_name)

            if restaurant_key not in restaurant_ids:
                restaurant_id = new_id()
                connection.execute(
                    """
                    INSERT INTO restaurants
                        (restaurant_id, restaurant_name, place_id)
                    VALUES (?, ?, ?)
                    """,
                    (restaurant_id, restaurant_name, place_id),
                )
                restaurant_ids[restaurant_key] = restaurant_id

            restaurant_id = restaurant_ids[restaurant_key]

            # Cuisine
            if cuisine_name not in cuisine_ids:
                cuisine_id = new_id()
                connection.execute(
                    """
                    INSERT OR IGNORE INTO cuisines (cuisine_id, cuisine_name)
                    VALUES (?, ?)
                    """,
                    (cuisine_id, cuisine_name),
                )
                cuisine_id = connection.execute(
                    """
                    SELECT cuisine_id
                    FROM cuisines
                    WHERE cuisine_name = ?
                    """,
                    (cuisine_name,),
                ).fetchone()[0]

                cuisine_ids[cuisine_name] = cuisine_id

            cuisine_id = cuisine_ids[cuisine_name]

            connection.execute(
                """
                INSERT OR IGNORE INTO restaurant_cuisines
                    (restaurant_id, cuisine_id)
                VALUES (?, ?)
                """,
                (restaurant_id, cuisine_id),
            )

            # One ratings row per restaurant
            if restaurant_id not in rated_restaurants:
                connection.execute(
                    """
                    INSERT INTO restaurant_ratings (
                        rating_id,
                        restaurant_id,
                        dining_rating,
                        delivery_rating,
                        dining_votes,
                        delivery_votes
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id(),
                        restaurant_id,
                        number(row["Dining_Rating"]),
                        number(row["Delivery_Rating"]),
                        integer(row["Dining_Votes"]),
                        integer(row["Delivery_Votes"]),
                    ),
                )
                rated_restaurants.add(restaurant_id)

            # Menu item
            item_id = new_id()
            connection.execute(
                """
                INSERT INTO menu_items (
                    item_id,
                    restaurant_id,
                    item_name,
                    price,
                    best_seller
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    restaurant_id,
                    item_name,
                    number(row["Prices"]) or 0,
                    1 if text(row["Best_Seller"]) == "BESTSELLER" else 0,
                ),
            )

            # Menu-item metrics
            connection.execute(
                """
                INSERT INTO menu_item_metrics (
                    metric_id,
                    item_id,
                    votes,
                    average_rating,
                    total_votes,
                    price_per_vote,
                    log_price,
                    is_bestseller,
                    is_highly_rated,
                    is_expensive
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id(),
                    item_id,
                    integer(row["Votes"]),
                    number(row["Average_Rating"]),
                    integer(row["Total_Votes"]),
                    number(row["Price_per_Vote"]),
                    number(row["Log_Price"]),
                    integer(row["Is_Bestseller"]),
                    integer(row["Is_Highly_Rated"]),
                    integer(row["Is_Expensive"]),
                ),
            )

    connection.commit()

    for table in [
        "cities",
        "places",
        "restaurants",
        "cuisines",
        "restaurant_cuisines",
        "menu_items",
        "restaurant_ratings",
        "menu_item_metrics",
    ]:
        count = connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        print(f"{table}: {count}")
