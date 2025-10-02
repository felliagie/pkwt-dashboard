from db_connection import get_db_connection
import pandas as pd
import bcrypt

def create_schema_and_tables():
    """Create schema and tables for PKWT contracts"""

    create_schema_sql = """
    CREATE SCHEMA IF NOT EXISTS contract_pkwt;
    """

    create_campaign_sql = """
    CREATE TABLE IF NOT EXISTS contract_pkwt.campaign (
        campaign_id SERIAL PRIMARY KEY,
        company VARCHAR(255),
        created_at DATE NOT NULL,
        send_at DATE NOT NULL,
        due_date DATE NOT NULL,
        pdf_total INTEGER DEFAULT 0,
        pdf_generated INTEGER DEFAULT 0,
        pdf_status VARCHAR(50) DEFAULT 'pending'
    );
    """

    # Create list_contract table matching schema.sql structure
    create_list_contract_sql = """
    CREATE TABLE IF NOT EXISTS contract_pkwt.list_contract (
        contract_id SERIAL PRIMARY KEY,
        campaign_id INTEGER REFERENCES contract_pkwt.campaign(campaign_id),
        contract_num_detail VARCHAR(255) UNIQUE NOT NULL,
        NIP VARCHAR(10),
        name VARCHAR(100) NOT NULL,
        job_description VARCHAR(100) NOT NULL,
        location VARCHAR(100) NOT NULL,
        birthplace VARCHAR(100) NOT NULL,
        birthdate DATE NOT NULL,
        marriage_status VARCHAR(100) NOT NULL,
        gender VARCHAR(100) NOT NULL,
        address VARCHAR(255) NOT NULL,
        nik VARCHAR(20) NOT NULL,
        tax_status VARCHAR(100) NOT NULL,
        npwp VARCHAR(100) NOT NULL,
        mobile_number VARCHAR(100) NOT NULL,
        email VARCHAR(100) NOT NULL,
        mothers_name VARCHAR(100) NOT NULL,
        bank_account VARCHAR(100) NOT NULL,
        gt INTEGER NOT NULL,
        job_position VARCHAR(100) NOT NULL
    );
    """

    create_contract_sql = """
    CREATE TABLE IF NOT EXISTS contract_pkwt.contract (
        base_contract_id INTEGER UNIQUE NOT NULL PRIMARY KEY,
        campaign_id INTEGER REFERENCES contract_pkwt.campaign(campaign_id),
        html_page TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    create_contract_status_sql = """
    CREATE TABLE IF NOT EXISTS contract_pkwt.contract_status (
        status_id SERIAL PRIMARY KEY,
        campaign_id INTEGER REFERENCES contract_pkwt.campaign(campaign_id),
        contract_id INTEGER REFERENCES contract_pkwt.list_contract(contract_id),
        send_status BOOLEAN DEFAULT FALSE,
        signed_status BOOLEAN DEFAULT FALSE,
        signed_at TIMESTAMP DEFAULT NULL,
        send_at TIMESTAMP DEFAULT NULL,
        pdf_data BYTEA
    );
    """

    create_users_sql = """
    CREATE TABLE IF NOT EXISTS contract_pkwt.users (
        user_id SERIAL PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    create_user_sessions_sql = """
    CREATE TABLE IF NOT EXISTS contract_pkwt.user_sessions (
        session_id VARCHAR(255) PRIMARY KEY,
        user_id INTEGER REFERENCES contract_pkwt.users(user_id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL
    );
    """

    create_user_logs_sql = """
    CREATE TABLE IF NOT EXISTS contract_pkwt.user_logs (
        log_id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES contract_pkwt.users(user_id),
        action VARCHAR(255) NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_address VARCHAR(45),
        details TEXT
    );
    """

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(create_schema_sql)
            print("Schema created successfully")

            cursor.execute(create_campaign_sql)
            print("campaign table created successfully")

            cursor.execute(create_list_contract_sql)
            print("list_contract table created successfully")

            cursor.execute(create_contract_sql)
            print("contract table created successfully")

            cursor.execute(create_contract_status_sql)
            print("contract_status table created successfully")

            cursor.execute(create_users_sql)
            print("users table created successfully")

            cursor.execute(create_user_sessions_sql)
            print("user_sessions table created successfully")

            cursor.execute(create_user_logs_sql)
            print("user_logs table created successfully")

            # Create default user
            password = 'testing'
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            cursor.execute("""
                INSERT INTO contract_pkwt.users (email, password_hash)
                VALUES (%s, %s)
                ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
            """, ('hr@jmaxindo.id', password_hash))

            print("Default user created (email: hr@jmaxindo.id, password: testing)")

            conn.commit()

    except Exception as e:
        print(f"Error creating tables: {e}")
        raise

if __name__ == "__main__":
    create_schema_and_tables()