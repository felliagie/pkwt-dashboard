import psycopg2
from typing import Optional
import os
from contextlib import contextmanager

DATABASE_URL = "postgresql://neondb_owner:npg_3uDE5TZcNksJ@ep-plain-sky-a11d4k0g-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_connection():
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        raise

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        conn = get_connection()
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def test_connection():
    """Test database connection"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()
            print(f"Connected to database: {version[0]}")
            return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()