import psycopg2
import hashlib

DB_URL = "postgresql://postgres.uowdeqqbkuoyxcfxyobv:Ifaassegaf1!@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"

def add_hash_column():
    """Add contract_num_detail_md5 column and populate with MD5 hashes"""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        # Add column if it doesn't exist
        cursor.execute("""
            ALTER TABLE contract_pkwt.list_contract
            ADD COLUMN IF NOT EXISTS contract_num_detail_md5 VARCHAR(32)
        """)
        print("Column contract_num_detail_md5 added successfully")

        # Get all contracts
        cursor.execute("""
            SELECT contract_id, contract_num_detail
            FROM contract_pkwt.list_contract
        """)
        contracts = cursor.fetchall()

        print(f"Found {len(contracts)} contracts to update")

        # Update each record with MD5 hash
        updated_count = 0
        for contract_id, contract_num_detail in contracts:
            md5_hash = hashlib.md5(contract_num_detail.encode()).hexdigest()

            cursor.execute("""
                UPDATE contract_pkwt.list_contract
                SET contract_num_detail_md5 = %s
                WHERE contract_id = %s
            """, (md5_hash, contract_id))

            updated_count += 1
            if updated_count % 10 == 0:
                print(f"Updated {updated_count}/{len(contracts)} records...")

        conn.commit()
        print(f"\nSuccessfully updated {updated_count} records with MD5 hashes")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    add_hash_column()
