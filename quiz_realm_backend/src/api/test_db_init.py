"""
Test for database initialization and table creation.

Run this script to validate that the database session works and all tables are created.
"""

from database import init_db, session_context
from sqlmodel import inspect
from models import User, Room, Question, Response, Score, MatchHistory

if __name__ == "__main__":
    init_db()
    with session_context() as session:
        inspector = inspect(session.connection())
        # Get all tables that should exist
        expected_tables = {
            User.__tablename__,
            Room.__tablename__,
            Question.__tablename__,
            Response.__tablename__,
            Score.__tablename__,
            MatchHistory.__tablename__,
        }
        db_tables = set(inspector.get_table_names())
        print("Existing tables:", db_tables)
        print("Expected tables:", expected_tables)
        missing = expected_tables - db_tables
        if not missing:
            print("✅ All required tables have been created successfully.")
        else:
            print("❌ Missing tables:", missing)
