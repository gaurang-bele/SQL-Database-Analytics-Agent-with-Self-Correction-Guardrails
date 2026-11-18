#!/usr/bin/env python3
"""Database Seeder Script for SQL & Database Analytics Agent."""
import sys
import logging
from app.database.seed import seed_database
from app.database.inspector import get_formatted_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    print("Seeding database...")
    seed_database()
    print("Database seeding completed successfully!")
    print("\nReflected Database Schema:")
    print("-" * 50)
    print(get_formatted_schema())
    print("-" * 50)

if __name__ == "__main__":
    main()
