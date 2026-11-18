import logging
from datetime import date, timedelta
from typing import Optional
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, MetaData, String, Table
from app.database.connection import get_engine

logger = logging.getLogger(__name__)

metadata = MetaData()

# Define tables
customers = Table(
    "customers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("email", String, nullable=False),
    Column("country", String, nullable=False),
    Column("signup_date", Date, nullable=False)
)

orders = Table(
    "orders",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("order_date", Date, nullable=False),  # Note: specifically named order_date as per test case requirements
    Column("customer_id", Integer, ForeignKey("customers.id"), nullable=False),
    Column("total_amount", Float, nullable=False),
    Column("status", String, nullable=False)
)

products = Table(
    "products",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("category", String, nullable=False),
    Column("price", Float, nullable=False),
    Column("stock_quantity", Integer, nullable=False)
)

order_items = Table(
    "order_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("order_id", Integer, ForeignKey("orders.id"), nullable=False),
    Column("product_id", Integer, ForeignKey("products.id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("unit_price", Float, nullable=False)
)


def seed_database(db_url: Optional[str] = None) -> None:
    """Create and seed sample tables into the target database."""
    engine = get_engine(db_url)
    
    # Create all tables
    metadata.create_all(engine)
    logger.info("Created schema tables: customers, orders, products, order_items.")
    
    with engine.begin() as conn:
        # Check if already seeded
        result = conn.execute(customers.select().limit(1)).fetchall()
        if result:
            logger.info("Database already seeded with data. Skipping insert.")
            return

        # Seed Customers
        customer_rows = [
            {"id": 1, "name": "Alice Smith", "email": "alice@example.com", "country": "USA", "signup_date": date(2023, 1, 15)},
            {"id": 2, "name": "Bob Johnson", "email": "bob@example.com", "country": "Canada", "signup_date": date(2023, 2, 20)},
            {"id": 3, "name": "Charlie Brown", "email": "charlie@example.com", "country": "UK", "signup_date": date(2023, 3, 10)},
            {"id": 4, "name": "Diana Prince", "email": "diana@example.com", "country": "Germany", "signup_date": date(2023, 4, 5)},
            {"id": 5, "name": "Evan Wright", "email": "evan@example.com", "country": "USA", "signup_date": date(2023, 5, 12)},
        ]
        conn.execute(customers.insert(), customer_rows)

        # Seed Products
        product_rows = [
            {"id": 1, "name": "Ultra Laptop Pro", "category": "Electronics", "price": 1299.99, "stock_quantity": 45},
            {"id": 2, "name": "Noise Cancelling Headphones", "category": "Electronics", "price": 199.50, "stock_quantity": 120},
            {"id": 3, "name": "Ergonomic Desk Chair", "category": "Furniture", "price": 349.00, "stock_quantity": 30},
            {"id": 4, "name": "Mechanical Gaming Keyboard", "category": "Electronics", "price": 129.99, "stock_quantity": 85},
            {"id": 5, "name": "Stainless Steel Water Bottle", "category": "Accessories", "price": 25.00, "stock_quantity": 300},
            {"id": 6, "name": "Organic Cotton Hoodie", "category": "Apparel", "price": 59.95, "stock_quantity": 150},
        ]
        conn.execute(products.insert(), product_rows)

        # Seed Orders with explicit id and order_date
        base_date = date(2024, 1, 1)
        order_rows = [
            {"id": 101, "order_date": base_date + timedelta(days=2), "customer_id": 1, "total_amount": 1499.49, "status": "Completed"},
            {"id": 102, "order_date": base_date + timedelta(days=5), "customer_id": 2, "total_amount": 199.50, "status": "Completed"},
            {"id": 103, "order_date": base_date + timedelta(days=12), "customer_id": 1, "total_amount": 349.00, "status": "Shipped"},
            {"id": 104, "order_date": base_date + timedelta(days=18), "customer_id": 3, "total_amount": 129.99, "status": "Completed"},
            {"id": 105, "order_date": base_date + timedelta(days=25), "customer_id": 4, "total_amount": 84.95, "status": "Cancelled"},
            {"id": 106, "order_date": base_date + timedelta(days=32), "customer_id": 5, "total_amount": 1499.49, "status": "Completed"},
            {"id": 107, "order_date": base_date + timedelta(days=40), "customer_id": 2, "total_amount": 478.99, "status": "Processing"},
            {"id": 108, "order_date": base_date + timedelta(days=55), "customer_id": 3, "total_amount": 59.95, "status": "Completed"},
        ]
        conn.execute(orders.insert(), order_rows)

        # Seed Order Items
        order_item_rows = [
            {"id": 1, "order_id": 101, "product_id": 1, "quantity": 1, "unit_price": 1299.99},
            {"id": 2, "order_id": 101, "product_id": 2, "quantity": 1, "unit_price": 199.50},
            {"id": 3, "order_id": 102, "product_id": 2, "quantity": 1, "unit_price": 199.50},
            {"id": 4, "order_id": 103, "product_id": 3, "quantity": 1, "unit_price": 349.00},
            {"id": 5, "order_id": 104, "product_id": 4, "quantity": 1, "unit_price": 129.99},
            {"id": 6, "order_id": 105, "product_id": 5, "quantity": 1, "unit_price": 25.00},
            {"id": 7, "order_id": 105, "product_id": 6, "quantity": 1, "unit_price": 59.95},
            {"id": 8, "order_id": 106, "product_id": 1, "quantity": 1, "unit_price": 1299.99},
            {"id": 9, "order_id": 106, "product_id": 2, "quantity": 1, "unit_price": 199.50},
            {"id": 10, "order_id": 107, "product_id": 3, "quantity": 1, "unit_price": 349.00},
            {"id": 11, "order_id": 107, "product_id": 4, "quantity": 1, "unit_price": 129.99},
            {"id": 12, "order_id": 108, "product_id": 6, "quantity": 1, "unit_price": 59.95},
        ]
        conn.execute(order_items.insert(), order_item_rows)

    logger.info("Successfully seeded database with sample eCommerce data.")
