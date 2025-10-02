import pandas as pd
from db_connection import get_db_connection
from datetime import datetime

def convert_and_populate_contracts():
    """Convert Excel data and populate list_contract table"""

    excel_file = r"C:\Users\felli\PycharmProjects\pkwt-dashboard\data\DATA BASE BASPG 21 SEPT - 20 NOV 2025.xls"

    try:
        # Read Excel file
        df = pd.read_excel(excel_file)
        print(f"Read {len(df)} rows from Excel file")

        # Data conversion and mapping
        df_converted = pd.DataFrame()

        # Map Excel columns to database columns
        df_converted['contract_num_detail'] = df['PKWT NO'].astype(str)
        df_converted['NIP'] = df['NIP'].astype(str)
        df_converted['name'] = df['NAMA'].astype(str)
        df_converted['job_description'] = df['BAGIAN'].astype(str)
        df_converted['location'] = df['LOKASI KERJA'].astype(str)
        df_converted['birthplace'] = df['TTL'].astype(str)

        # Convert birthdate - handle different date formats
        def convert_date(date_val):
            if pd.isna(date_val):
                return None
            try:
                if isinstance(date_val, str):
                    # Try to parse string dates
                    return pd.to_datetime(date_val).date()
                else:
                    # Already datetime object
                    return pd.to_datetime(date_val).date()
            except:
                return None

        df_converted['birthdate'] = df['TGL.LAHIR'].apply(convert_date)
        df_converted['marriage_status'] = df['Status'].astype(str)
        df_converted['gender'] = df['GENDER'].astype(str)
        df_converted['address'] = df['ALAMAT'].astype(str)
        df_converted['nik'] = df['NIK'].astype(str)
        df_converted['tax_status'] = df['STATUS TAX'].astype(str)
        df_converted['npwp'] = df['NPWP'].astype(str)
        df_converted['mobile_number'] = df['HP'].astype(str)
        df_converted['email'] = df['EMAIL'].astype(str)
        df_converted['mothers_name'] = df['NAMA IBU'].astype(str)
        df_converted['bank_account'] = df['NOREK BRI'].astype(str)
        df_converted['gt'] = df['GT'].astype(int)
        df_converted['job_position'] = df['bagian'].astype(str)

        # Set default campaign_id (you may need to adjust this)
        df_converted['campaign_id'] = None  # Will be set to NULL in database

        # Reorder columns to match INSERT statement
        df_converted = df_converted[[
            'campaign_id', 'contract_num_detail', 'NIP', 'name', 'job_description', 'location',
            'birthplace', 'birthdate', 'marriage_status', 'gender', 'address', 'nik',
            'tax_status', 'npwp', 'mobile_number', 'email', 'mothers_name', 'bank_account',
            'gt', 'job_position'
        ]]

        print(f"After conversion: {len(df_converted)} valid rows")

        # Insert into database
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Prepare insert statement
            insert_sql = """
            INSERT INTO contract_pkwt.list_contract (
                campaign_id, contract_num_detail, NIP, name, job_description, location,
                birthplace, birthdate, marriage_status, gender, address, nik,
                tax_status, npwp, mobile_number, email, mothers_name, bank_account,
                gt, job_position
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) ON CONFLICT (contract_id) DO NOTHING
            """

            # Insert data row by row
            inserted_count = 0
            for index, row in df_converted.iterrows():
                try:
                    print(f"Row {index} data:")
                    for col, val in row.items():
                        print(f"  {col}: {val} ({type(val).__name__})")

                    cursor.execute(insert_sql, tuple(row))
                    if cursor.rowcount > 0:
                        inserted_count += 1
                        print(f"  ✓ Successfully inserted row {index}")
                    else:
                        print(f"  - Row {index} skipped (conflict)")
                except Exception as e:
                    print(f"  ✗ Error inserting row {index}: {e}")
                    continue

            conn.commit()
            print(f"Successfully inserted {inserted_count} records into list_contract table")

    except Exception as e:
        print(f"Error processing Excel file: {e}")
        raise

if __name__ == "__main__":
    convert_and_populate_contracts()