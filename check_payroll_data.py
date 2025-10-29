"""
Script to check payroll data for % characters that might cause SQL formatting issues
"""

import pandas as pd
import numpy as np
import sys

def check_excel_for_percent_signs(excel_path):
    """Check if Excel data contains % signs that could cause SQL issues"""

    print(f"Analyzing: {excel_path}\n")

    # Read Excel file
    df = pd.read_excel(excel_path, skiprows=2, header=None)

    # Remove last row (totals)
    df = df.iloc[:-1]

    # Drop first column (sequential number)
    df = df.iloc[:, 1:]

    # Column names
    column_names = [
        'employee_id', 'employee_name', 'cost_center', 'area', 'nik',
        'beneficiary_bank', 'bank_account_no', 'tax_id_no', 'join_date', 'join_date_jmax',
        'contract_period', 'job_titles', 'sex', 'marital_status', 'tax_code', 'salary_period',
        'basic_pay', 'basic_pay_bpjs', 'working_days', 'overtime', 'ksd', 'incentive',
        'end_of_contract', 'tdk', 'potongan', 'tunjangan', 'total_salary', 'remarks',
        'jkk_0_24_percent', 'jht_3_7_percent', 'jp_2_percent', 'jkm_0_3_percent',
        'bpjs_kesehatan_4_percent', 'total_insurance', 'total_with_bpjs', 'management_fee',
        'grand_total', 'jht_2_percent_deduction', 'jp_1_percent_deduction',
        'bpjs_kesehatan_1_percent_deduction', 'pph21', 'total_deduction',
        'reim_kesehatan_karyawan', 'thp', 'extra_column'
    ]

    df.columns = column_names

    # Replace NaN with None
    df = df.replace([np.nan, np.inf, -np.inf], None)

    # Convert to list of dictionaries
    data = df.to_dict('records')

    print(f"Total employees: {len(data)}\n")
    print("="*80)
    print("Checking for % characters in data...")
    print("="*80 + "\n")

    found_percent = False

    for idx, employee in enumerate(data, start=1):
        for key, value in employee.items():
            if value is not None and isinstance(value, str) and '%' in value:
                print(f"Employee #{idx}: {employee.get('employee_name', 'Unknown')}")
                print(f"  Field: {key}")
                print(f"  Value: {value}")
                print()
                found_percent = True

    if not found_percent:
        print("[OK] No % characters found in string data")
    else:
        print("\n" + "="*80)
        print("WARNING: Found % characters that could cause SQL formatting issues!")
        print("="*80)

    print("\n" + "="*80)
    print("Checking INSERT statement parameters count...")
    print("="*80 + "\n")

    # Count columns
    columns_count = len(column_names) + 1  # +1 for campaign_id
    print(f"Columns to insert: {columns_count}")
    print(f"  - payroll_campaign_id (1)")
    print(f"  - employee data columns ({len(column_names)})")

    # The VALUES should have same number of %s
    print(f"\nExpected placeholders (%%s): {columns_count}")

    # Count actual placeholders in our SQL
    sql_values = """
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    """
    actual_placeholders = sql_values.count('%s')
    print(f"Actual placeholders in SQL: {actual_placeholders}")

    if columns_count == actual_placeholders:
        print("\n[OK] Placeholder count matches!")
    else:
        print(f"\n[ERROR] MISMATCH! Expected {columns_count} but got {actual_placeholders}")
        print(f"   Difference: {abs(columns_count - actual_placeholders)}")

if __name__ == "__main__":
    excel_file = ".data/01. REKAP ABSEN BASPG JMAX 1025 PPH 21.xls"

    try:
        check_excel_for_percent_signs(excel_file)
    except FileNotFoundError:
        print(f"Error: File not found: {excel_file}")
        print("\nPlease ensure the Excel file exists at the specified path.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
