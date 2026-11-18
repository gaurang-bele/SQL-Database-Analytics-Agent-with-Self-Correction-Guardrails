import os
import pytest
from pathlib import Path
from sqlalchemy import text
from app.database.connection import get_engine
from app.database.seed import seed_database
from app.core.config import settings

@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory):
    """Creates a temporary SQLite database for testing."""
    temp_dir = tmp_path_factory.mktemp("test_db")
    db_file = temp_dir / "test_ecommerce.db"
    db_url = f"sqlite:///{db_file}"
    seed_database(db_url)
    return db_url

@pytest.fixture
def test_db(test_db_path):
    """Provides test database URL."""
    return test_db_path
