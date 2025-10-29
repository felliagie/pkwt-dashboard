from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, BackgroundTasks, Response as FastAPIResponse, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
import psycopg2
from typing import Dict, List, Optional
import json
from pydantic import BaseModel
from datetime import date, datetime, timedelta
import pandas as pd
import io
import os
from contract_converter import process_contract_file
from playwright.async_api import async_playwright
import re
import asyncio
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PIL import Image
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
import bcrypt
import uuid
import requests
import base64

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://127.0.0.1:1420"],  # Tauri dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Database connection
DB_URL = "postgresql://postgres.uowdeqqbkuoyxcfxyobv:Ifaassegaf1!@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"

def get_db_connection():
    return psycopg2.connect(DB_URL)

# Helper functions
def log_user_action(user_id: int, action: str, ip_address: str = None, details: str = None):
    """Log user actions to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO contract_pkwt.user_logs (user_id, action, ip_address, details)
        VALUES (%s, %s, %s, %s)
    """, (user_id, action, ip_address, details))
    conn.commit()
    cursor.close()
    conn.close()

def get_user_from_session(session_id: str) -> Optional[Dict]:
    """Get user from session ID"""
    if not session_id:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.user_id, u.email
        FROM contract_pkwt.users u
        JOIN contract_pkwt.user_sessions s ON u.user_id = s.user_id
        WHERE s.session_id = %s AND s.expires_at > NOW()
    """, (session_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result:
        return {"user_id": result[0], "email": result[1]}
    return None

# Pydantic models
class CampaignCreate(BaseModel):
    company: str
    send_date: date
    due_date: date

class LoginRequest(BaseModel):
    email: str
    password: str
    remember: bool = False

class PayrollCampaignCreate(BaseModel):
    company: str
    period: str
    send_at: date

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    with open("static/login.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.post("/api/login")
async def login(request: Request, login_data: LoginRequest):
    client_ip = request.client.host

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get user by email
    cursor.execute("SELECT user_id, email, password_hash FROM contract_pkwt.users WHERE email = %s", (login_data.email,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id, email, password_hash = user

    # Verify password
    if not bcrypt.checkpw(login_data.password.encode('utf-8'), password_hash.encode('utf-8')):
        log_user_action(user_id, "failed_login", client_ip, f"Failed login attempt for {email}")
        cursor.close()
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create session
    session_id = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(days=7 if login_data.remember else 1)

    cursor.execute("""
        INSERT INTO contract_pkwt.user_sessions (session_id, user_id, expires_at)
        VALUES (%s, %s, %s)
    """, (session_id, user_id, expires_at))

    log_user_action(user_id, "login", client_ip, f"Successful login for {email}")

    conn.commit()
    cursor.close()
    conn.close()

    response = JSONResponse(content={"message": "Login successful"})
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=604800 if login_data.remember else 86400,
        samesite="lax"
    )
    return response

@app.post("/api/logout")
async def logout(request: Request, session_id: Optional[str] = Cookie(None)):
    if session_id:
        user = get_user_from_session(session_id)
        if user:
            log_user_action(user["user_id"], "logout", request.client.host, f"Logout for {user['email']}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contract_pkwt.user_sessions WHERE session_id = %s", (session_id,))
        conn.commit()
        cursor.close()
        conn.close()

    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie("session_id")
    return response

@app.get("/", response_class=HTMLResponse)
async def read_root(session_id: Optional[str] = Cookie(None)):
    user = get_user_from_session(session_id)
    if not user:
        return RedirectResponse(url="/login")

    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/campaign", response_class=HTMLResponse)
async def campaign_page(session_id: Optional[str] = Cookie(None)):
    user = get_user_from_session(session_id)
    if not user:
        return RedirectResponse(url="/login")

    with open("static/campaign.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/campaign-manager", response_class=HTMLResponse)
async def campaign_manager_page(session_id: Optional[str] = Cookie(None)):
    user = get_user_from_session(session_id)
    if not user:
        return RedirectResponse(url="/login")

    with open("static/campaign-manager.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/campaign-detail", response_class=HTMLResponse)
async def campaign_detail_page(session_id: Optional[str] = Cookie(None)):
    user = get_user_from_session(session_id)
    if not user:
        return RedirectResponse(url="/login")
    with open("static/campaign-detail.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.get("/signage", response_class=HTMLResponse)
async def signage_page():
    with open("static/signage.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/signed", response_class=HTMLResponse)
async def signed_page():
    with open("static/signed.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/contract-preview", response_class=HTMLResponse)
async def contract_preview():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT html_page FROM contract_pkwt.contract LIMIT 1')
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result:
            return HTMLResponse(content=result[0], status_code=200)
        else:
            return HTMLResponse(content="<h1>No contract found</h1>", status_code=404)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)

@app.get("/payroll", response_class=HTMLResponse)
async def payroll_management_page(session_id: Optional[str] = Cookie(None)):
    user = get_user_from_session(session_id)
    if not user:
        return RedirectResponse(url="/login")

    with open("static/payroll.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/payroll-base", response_class=HTMLResponse)
async def payroll_base_page(session_id: Optional[str] = Cookie(None)):
    user = get_user_from_session(session_id)
    if not user:
        return RedirectResponse(url="/login")

    with open("static/payroll-base.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/payroll-preview/{list_payroll_id}", response_class=HTMLResponse)
async def payroll_preview_page(list_payroll_id: int, session_id: Optional[str] = Cookie(None)):
    user = get_user_from_session(session_id)
    if not user:
        return RedirectResponse(url="/login")

    with open("static/payroll-preview.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/payroll-manager", response_class=HTMLResponse)
async def payroll_manager_page(session_id: Optional[str] = Cookie(None)):
    user = get_user_from_session(session_id)
    if not user:
        return RedirectResponse(url="/login")

    with open("static/payroll-manager.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/payroll-detail", response_class=HTMLResponse)
async def payroll_detail_page(session_id: Optional[str] = Cookie(None)):
    user = get_user_from_session(session_id)
    if not user:
        return RedirectResponse(url="/login")

    with open("static/payroll-detail.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

# Payroll API Endpoints
@app.post("/api/payroll-campaigns")
async def create_payroll_campaign(campaign: PayrollCampaignCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO contract_pkwt.payroll_campaign (company, created_at, send_at, status)
            VALUES (%s, CURRENT_TIMESTAMP, %s, 'active')
            RETURNING payroll_campaign_id
        """, (campaign.company, campaign.send_at))

        payroll_campaign_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

        return {"payroll_campaign_id": payroll_campaign_id, "message": "Payroll campaign created successfully"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.post("/api/payroll-campaigns/upload-payroll")
async def upload_payroll_data(file: UploadFile = File(...), payroll_campaign_id: int = Form(...)):
    try:
        # Read the uploaded file
        contents = await file.read()

        # Parse Excel file - skip 2 header rows, treat first data row as data (not headers)
        df = pd.read_excel(io.BytesIO(contents), skiprows=2, header=None)

        # Remove last row (total row)
        df = df.iloc[:-1]

        # Drop first column (no/sequential number - not needed as list_payroll_id is auto-incremented)
        df = df.iloc[:, 1:]

        # Set proper column names based on position (0-indexed)
        # Note: First column (no) is skipped, starting from employee_id
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

        # Replace NaN and inf values with None for proper JSON serialization
        import numpy as np
        df = df.replace([np.nan, np.inf, -np.inf], None)

        # Convert to list of dictionaries
        data = df.to_dict('records')

        return {"data": data, "count": len(data)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.post("/api/payroll-campaigns/{campaign_id}/finalize")
async def finalize_payroll_campaign(campaign_id: int, request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        data = body.get('data', [])

        conn = get_db_connection()
        cursor = conn.cursor()

        inserted_count = 0

        for employee in data:
            # Insert into list_payroll (list_payroll_id is auto-incremented)
            cursor.execute("""
                INSERT INTO contract_pkwt.list_payroll (
                    payroll_campaign_id, employee_id, employee_name, cost_center, area, nik,
                    beneficiary_bank, bank_account_no, tax_id_no, join_date, join_date_jmax,
                    contract_period, job_titles, sex, marital_status, tax_code, salary_period,
                    basic_pay, basic_pay_bpjs, working_days, overtime, ksd, incentive,
                    end_of_contract, tdk, potongan, tunjangan, total_salary, remarks,
                    jkk_0_24_percent, jht_3_7_percent, jp_2_percent, jkm_0_3_percent,
                    bpjs_kesehatan_4_percent, total_insurance, total_with_bpjs, management_fee,
                    grand_total, jht_2_percent_deduction, jp_1_percent_deduction,
                    bpjs_kesehatan_1_percent_deduction, pph21, total_deduction,
                    reim_kesehatan_karyawan, thp, extra_column
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING list_payroll_id
            """, (
                campaign_id,
                employee.get('employee_id'),
                employee.get('employee_name'),
                employee.get('cost_center'),
                employee.get('area'),
                employee.get('nik'),
                employee.get('beneficiary_bank'),
                employee.get('bank_account_no'),
                employee.get('tax_id_no'),
                employee.get('join_date'),
                employee.get('join_date_jmax'),
                employee.get('contract_period'),
                employee.get('job_titles'),
                employee.get('sex'),
                employee.get('marital_status'),
                employee.get('tax_code'),
                employee.get('salary_period'),
                employee.get('basic_pay'),
                employee.get('basic_pay_bpjs'),
                employee.get('working_days'),
                employee.get('overtime'),
                employee.get('ksd'),
                employee.get('incentive'),
                employee.get('end_of_contract'),
                employee.get('tdk'),
                employee.get('potongan'),
                employee.get('tunjangan'),
                employee.get('total_salary'),
                employee.get('remarks'),
                employee.get('jkk_0_24_percent'),
                employee.get('jht_3_7_percent'),
                employee.get('jp_2_percent'),
                employee.get('jkm_0_3_percent'),
                employee.get('bpjs_kesehatan_4_percent'),
                employee.get('total_insurance'),
                employee.get('total_with_bpjs'),
                employee.get('management_fee'),
                employee.get('grand_total'),
                employee.get('jht_2_percent_deduction'),
                employee.get('jp_1_percent_deduction'),
                employee.get('bpjs_kesehatan_1_percent_deduction'),
                employee.get('pph21'),
                employee.get('total_deduction'),
                employee.get('reim_kesehatan_karyawan'),
                employee.get('thp'),
                employee.get('extra_column')
            ))

            list_payroll_id = cursor.fetchone()[0]

            # Create payroll_status entry without PDF (will be generated in background)
            cursor.execute("""
                INSERT INTO contract_pkwt.payroll_status (
                    payroll_campaign_id, list_payroll_id, send_status
                ) VALUES (%s, %s, FALSE)
            """, (campaign_id, list_payroll_id))

            inserted_count += 1

        # Update payroll campaign with totals and set status to processing
        cursor.execute("""
            UPDATE contract_pkwt.payroll_campaign
            SET pdf_total = %s, pdf_generated = 0, pdf_status = 'processing'
            WHERE payroll_campaign_id = %s
        """, (inserted_count, campaign_id))

        conn.commit()
        cursor.close()
        conn.close()

        # Schedule background PDF generation
        background_tasks.add_task(generate_payroll_pdfs_background, campaign_id)

        return {
            "inserted_count": inserted_count,
            "message": f"Payroll data saved successfully. {inserted_count} records created. PDFs are being generated in the background."
        }
    except Exception as e:
        import traceback
        print("ERROR in finalize_payroll_campaign:")
        print(traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": str(e)})

def generate_payroll_pdfs_background(campaign_id: int):
    """Background task to generate password-protected PDFs for all payroll records in a campaign"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get campaign details
        cursor.execute("""
            SELECT company, send_at
            FROM contract_pkwt.payroll_campaign
            WHERE payroll_campaign_id = %s
        """, (campaign_id,))
        campaign_result = cursor.fetchone()
        if not campaign_result:
            print(f"Campaign {campaign_id} not found")
            return

        company_name = campaign_result[0]
        payment_date = campaign_result[1]
        formatted_date = payment_date.strftime('%d-%b-%y') if payment_date else ''

        # Load and prepare HTML template
        template_path = os.path.join(os.path.dirname(__file__), 'static', 'payroll-base.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            html_template_base = f.read()

        # Convert images to base64
        def image_to_base64(image_path):
            try:
                full_path = os.path.join(os.path.dirname(__file__), 'static', 'images', image_path)
                with open(full_path, 'rb') as img_file:
                    img_data = img_file.read()
                    b64_data = base64.b64encode(img_data).decode('utf-8')
                    ext = image_path.lower().split('.')[-1]
                    mime_type = f'image/{ext}' if ext in ['png', 'jpg', 'jpeg', 'gif'] else 'image/png'
                    return f'data:{mime_type};base64,{b64_data}'
            except Exception as e:
                print(f"Error converting image {image_path}: {e}")
                return ''

        html_template_base = html_template_base.replace('src="/static/images/top-logo.png"', f'src="{image_to_base64("top-logo.png")}"')
        html_template_base = html_template_base.replace('src="/static/images/sign_logo.png"', f'src="{image_to_base64("sign_logo.png")}"')
        html_template_base = html_template_base.replace('src="/static/images/sign.png"', f'src="{image_to_base64("sign.png")}"')

        # Helper functions
        def format_currency(value):
            if value is None or value == 0 or value == '0':
                return '-'
            rounded = round(float(value))
            return 'Rp ' + '{:,}'.format(rounded).replace(',', '.')

        def display_value(value):
            if value is None or value == '':
                return '-'
            return str(value)

        # PDF generation function
        async def generate_pdf_async(html_content, employee_name='Employee'):
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.set_content(html_content, wait_until='networkidle')
                pdf_bytes = await page.pdf(
                    width='8.50in',
                    height='10.80in',
                    landscape=False,
                    margin={'top': '0.25in', 'right': '0.25in', 'bottom': '0.25in', 'left': '0.25in'},
                    print_background=True,
                    display_header_footer=False
                )
                await browser.close()
                return pdf_bytes

        # Get all payroll records for this campaign with birthdate from list_contract
        # Use DISTINCT ON to ensure only one contract per employee (avoids duplicate processing)
        cursor.execute("""
            SELECT DISTINCT ON (lp.list_payroll_id) lp.*, lc.birthdate
            FROM contract_pkwt.list_payroll lp
            LEFT JOIN LATERAL (
                SELECT birthdate
                FROM contract_pkwt.list_contract
                WHERE nik = lp.nik
                ORDER BY contract_id DESC
                LIMIT 1
            ) lc ON true
            WHERE lp.payroll_campaign_id = %s
            ORDER BY lp.list_payroll_id
        """, (campaign_id,))

        columns = [desc[0] for desc in cursor.description]
        payroll_records = cursor.fetchall()

        pdf_generated_count = 0

        for record in payroll_records:
            try:
                # Convert row to dictionary
                employee = dict(zip(columns, record))
                list_payroll_id = employee['list_payroll_id']
                employee_name = employee.get('employee_name', 'Employee')
                birthdate = employee.get('birthdate')

                # Prepare HTML for this employee
                html_template = html_template_base

                bank_display = display_value(employee.get('beneficiary_bank')) + ' (' + display_value(employee.get('bank_account_no')) + ')'
                date_display = payment_date.strftime('%B %d, %Y') if payment_date else ''

                replacements = {
                    'Jein Lumempouw': display_value(employee.get('employee_name')),
                    'M25091060': display_value(employee.get('employee_id')),
                    'BA PIXY Palu': display_value(employee.get('job_titles')),
                    'PT. Mandom Indonesia': company_name,
                    '31-Oct-25': formatted_date,
                    'TK / 0': display_value(employee.get('tax_code')),
                    '25': display_value(employee.get('working_days')),
                    'BRI (043401014645502)': bank_display,
                    'Rp 3.617.000': format_currency(employee.get('basic_pay')),
                    'Rp 2.100.000': format_currency(employee.get('incentive')),
                    'Rp -602.833': format_currency(employee.get('potongan')),
                    'Rp 5.114.167': format_currency(employee.get('total_salary')),
                    'Rp 72.340': format_currency(employee.get('jht_2_percent_deduction')),
                    'Rp 36.170': format_currency(employee.get('jp_1_percent_deduction')),
                    'Rp 144.680': format_currency(employee.get('total_deduction')),
                    'Rp 4.969.487': format_currency(employee.get('thp')),
                    'October 31, 2025': date_display
                }

                for old_val, new_val in replacements.items():
                    html_template = html_template.replace(old_val, new_val)

                # Handle nullable fields
                ksd_val = employee.get('ksd')
                ksd_display = format_currency(ksd_val) if ksd_val and ksd_val != 0 else '-'
                ksd_class = "text-gray-900 font-medium" if ksd_val and ksd_val != 0 else "text-gray-400"
                html_template = html_template.replace('<td class="px-4 py-2 text-right text-gray-400">-</td>', f'<td class="px-4 py-2 text-right {ksd_class}">{ksd_display}</td>', 1)

                tdk_val = employee.get('tdk')
                tdk_display = format_currency(tdk_val) if tdk_val and tdk_val != 0 else '-'
                tdk_class = "text-gray-900 font-medium" if tdk_val and tdk_val != 0 else "text-gray-400"
                html_template = html_template.replace('<td class="px-4 py-2 text-right text-gray-400">-</td>', f'<td class="px-4 py-2 text-right {tdk_class}">{tdk_display}</td>', 1)

                tunjangan_val = employee.get('tunjangan')
                tunjangan_display = format_currency(tunjangan_val) if tunjangan_val and tunjangan_val != 0 else '-'
                tunjangan_class = "text-gray-900 font-medium" if tunjangan_val and tunjangan_val != 0 else "text-gray-400"
                html_template = html_template.replace('<td class="px-4 py-2 text-right text-gray-400">-</td>', f'<td class="px-4 py-2 text-right {tunjangan_class}">{tunjangan_display}</td>', 1)

                pph21_val = employee.get('pph21')
                pph21_display = format_currency(pph21_val) if pph21_val and pph21_val != 0 else '-'
                pph21_class = "text-gray-900 font-medium" if pph21_val and pph21_val != 0 else "text-gray-400"
                html_template = html_template.replace('<td class="px-4 py-2 text-right text-gray-400">-</td>', f'<td class="px-4 py-2 text-right {pph21_class}">{pph21_display}</td>', 1)

                bpjs_kesehatan_val = employee.get('bpjs_kesehatan_1_percent_deduction')
                html_template = html_template.replace('Rp 36.170', format_currency(bpjs_kesehatan_val), 1)

                # Remove action buttons
                html_template = html_template.replace('<div class="mb-6 flex gap-3 justify-end print:hidden">', '<div style="display:none;">')

                # Generate PDF
                pdf_bytes = asyncio.run(generate_pdf_async(html_template, employee_name))

                # Apply password protection
                pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
                pdf_writer = PdfWriter()

                for page in pdf_reader.pages:
                    pdf_writer.add_page(page)

                # Generate password from birthdate (DDMMYY format)
                password = ''
                if birthdate:
                    password = birthdate.strftime('%d%m%y')
                else:
                    # Fallback: use default password if birthdate not found
                    password = '010101'
                    print(f"Warning: No birthdate found for {employee_name}, using default password")

                # Encrypt PDF
                pdf_writer.encrypt(user_password=password, owner_password=password)

                # Set PDF metadata
                salary_period = employee.get('salary_period')
                period_str = salary_period.strftime('%b%y') if salary_period else 'Unknown'
                safe_employee_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in employee_name)
                pdf_title = f"Payroll_{safe_employee_name}_{period_str}"

                pdf_writer.add_metadata({
                    '/Title': pdf_title,
                    '/Author': 'JMax Indonesia',
                    '/Subject': f'Payroll Slip for {employee_name}',
                    '/Creator': 'PKWT Dashboard'
                })

                # Write encrypted PDF to bytes
                output_pdf = io.BytesIO()
                pdf_writer.write(output_pdf)
                encrypted_pdf_bytes = output_pdf.getvalue()

                # Update payroll_status with encrypted PDF
                cursor.execute("""
                    UPDATE contract_pkwt.payroll_status
                    SET pdf_data = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE list_payroll_id = %s
                """, (encrypted_pdf_bytes, list_payroll_id))

                pdf_generated_count += 1

                # Update progress incrementally
                cursor.execute("""
                    UPDATE contract_pkwt.payroll_campaign
                    SET pdf_generated = %s
                    WHERE payroll_campaign_id = %s
                """, (pdf_generated_count, campaign_id))
                conn.commit()

                print(f"Generated password-protected PDF for {employee_name} (password: {password})")

            except Exception as pdf_error:
                import traceback
                print(f"Error generating PDF for list_payroll_id {employee.get('list_payroll_id')}: {pdf_error}")
                print(traceback.format_exc())
                continue

        # Mark campaign as completed
        cursor.execute("""
            UPDATE contract_pkwt.payroll_campaign
            SET pdf_status = 'completed'
            WHERE payroll_campaign_id = %s
        """, (campaign_id,))
        conn.commit()

        cursor.close()
        conn.close()

        print(f"Background PDF generation completed for campaign {campaign_id}. Generated {pdf_generated_count} PDFs.")

    except Exception as e:
        import traceback
        print(f"ERROR in generate_payroll_pdfs_background for campaign {campaign_id}:")
        print(traceback.format_exc())

        # Mark campaign as failed
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE contract_pkwt.payroll_campaign
                SET pdf_status = 'failed'
                WHERE payroll_campaign_id = %s
            """, (campaign_id,))
            conn.commit()
            cursor.close()
            conn.close()
        except:
            pass

@app.get("/api/payroll/{list_payroll_id}")
async def get_payroll_data(list_payroll_id: int, session_id: Optional[str] = Cookie(None)):
    """Get detailed payroll data for a specific employee"""
    user = get_user_from_session(session_id)
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                lp.*,
                pc.company,
                pc.send_at,
                pc.status as campaign_status,
                ps.send_status,
                ps.send_at as pdf_sent_at
            FROM contract_pkwt.list_payroll lp
            JOIN contract_pkwt.payroll_campaign pc ON lp.payroll_campaign_id = pc.payroll_campaign_id
            LEFT JOIN contract_pkwt.payroll_status ps ON lp.list_payroll_id = ps.list_payroll_id
            WHERE lp.list_payroll_id = %s
        """, (list_payroll_id,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return JSONResponse(status_code=404, content={"detail": "Payroll not found"})

        columns = [desc[0] for desc in cursor.description]
        payroll_data = dict(zip(columns, row))

        # Convert date/datetime objects to strings
        for key, value in payroll_data.items():
            if hasattr(value, 'isoformat'):
                payroll_data[key] = value.isoformat()

        conn.close()
        return payroll_data
    except Exception as e:
        import traceback
        print("ERROR in get_payroll_data:")
        print(traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/api/payroll/{list_payroll_id}/pdf")
async def get_payroll_pdf(list_payroll_id: int, session_id: Optional[str] = Cookie(None)):
    """Get PDF for a specific payroll"""
    user = get_user_from_session(session_id)
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ps.pdf_data, lp.employee_name, lp.salary_period
            FROM contract_pkwt.payroll_status ps
            JOIN contract_pkwt.list_payroll lp ON ps.list_payroll_id = lp.list_payroll_id
            WHERE ps.list_payroll_id = %s
        """, (list_payroll_id,))

        row = cursor.fetchone()
        conn.close()

        if not row or not row[0]:
            return JSONResponse(status_code=404, content={"detail": "PDF not found"})

        pdf_data = bytes(row[0])
        employee_name = row[1] or 'Employee'
        salary_period = row[2]

        # Create filename: Payroll_{employee_name}_{period}
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in employee_name)
        period_str = salary_period.strftime('%b%y') if salary_period else 'Unknown'
        filename = f"Payroll_{safe_name}_{period_str}.pdf"

        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'}
        )
    except Exception as e:
        import traceback
        print("ERROR in get_payroll_pdf:")
        print(traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/api/payroll/campaign/{campaign_id}/employees")
async def get_campaign_employees(campaign_id: int, session_id: Optional[str] = Cookie(None)):
    """Get list of all employees in a payroll campaign for navigation"""
    user = get_user_from_session(session_id)
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT list_payroll_id, employee_name, employee_id
            FROM contract_pkwt.list_payroll
            WHERE payroll_campaign_id = %s
            ORDER BY employee_name
        """, (campaign_id,))

        rows = cursor.fetchall()
        conn.close()

        employees = [
            {
                "list_payroll_id": row[0],
                "employee_name": row[1],
                "employee_id": row[2]
            }
            for row in rows
        ]

        return {"employees": employees}
    except Exception as e:
        import traceback
        print("ERROR in get_campaign_employees:")
        print(traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/api/dashboard-stats")
async def get_dashboard_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get total contracts (Target)
        cursor.execute("SELECT COUNT(*) FROM contract_pkwt.list_contract")
        target = cursor.fetchone()[0]

        # Get sent contracts
        cursor.execute("SELECT COUNT(*) FROM contract_pkwt.contract_status WHERE send_status = TRUE")
        sent = cursor.fetchone()[0]

        # Get signed contracts
        cursor.execute("SELECT COUNT(*) FROM contract_pkwt.contract_status WHERE signed_status = TRUE")
        signed = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return {
            "target": target,
            "sent": sent,
            "signed": signed
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/test-db")
async def test_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return {"status": "success", "result": result[0]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/contracts")
async def get_contracts():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM contract_pkwt.list_contract")
        contracts = cursor.fetchall()

        # Get column names
        column_names = [desc[0] for desc in cursor.description]

        # Convert to list of dictionaries
        result = []
        for contract in contracts:
            result.append(dict(zip(column_names, contract)))

        cursor.close()
        conn.close()

        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/contracts-with-status")
async def get_contracts_with_status():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                lc.contract_id,
                lc.campaign_id,
                lc.contract_num_detail,
                lc.nip,
                lc.name,
                lc.nik,
                lc.job_description,
                lc.mobile_number,
                lc.email,
                cs.send_status,
                cs.signed_status,
                cs.signed_at,
                cs.send_at
            FROM contract_pkwt.list_contract lc
            LEFT JOIN contract_pkwt.contract_status cs ON lc.contract_id = cs.contract_id
            ORDER BY lc.contract_id
        """)

        contracts = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        result = []
        for contract in contracts:
            contract_dict = dict(zip(column_names, contract))
            if contract_dict.get('signed_at'):
                contract_dict['signed_at'] = contract_dict['signed_at'].isoformat()
            if contract_dict.get('send_at'):
                contract_dict['send_at'] = contract_dict['send_at'].isoformat()
            result.append(contract_dict)

        cursor.close()
        conn.close()

        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/analytics/hourly")
async def get_hourly_analytics():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                EXTRACT(HOUR FROM send_at::timestamp) as hour,
                COUNT(*) as count
            FROM contract_pkwt.contract_status
            WHERE send_at IS NOT NULL
            GROUP BY EXTRACT(HOUR FROM send_at::timestamp)
            ORDER BY hour
        """)

        emails_sent = cursor.fetchall()

        cursor.execute("""
            SELECT
                EXTRACT(HOUR FROM signed_at::timestamp) as hour,
                COUNT(*) as count
            FROM contract_pkwt.contract_status
            WHERE signed_at IS NOT NULL
            GROUP BY EXTRACT(HOUR FROM signed_at::timestamp)
            ORDER BY hour
        """)

        contracts_signed = cursor.fetchall()

        cursor.close()
        conn.close()

        # Create arrays for all 24 hours
        emails_by_hour = [0] * 24
        signed_by_hour = [0] * 24

        for hour, count in emails_sent:
            emails_by_hour[int(hour)] = count

        for hour, count in contracts_signed:
            signed_by_hour[int(hour)] = count

        return {
            "hours": list(range(24)),
            "emails_sent": emails_by_hour,
            "contracts_signed": signed_by_hour
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/campaigns-list")
async def get_campaigns_list():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                c.campaign_id,
                c.company,
                c.created_at,
                c.send_at,
                c.due_date,
                COUNT(lc.contract_id) as total_contracts,
                COUNT(CASE WHEN cs.send_status = TRUE THEN 1 END) as sent_count
            FROM contract_pkwt.campaign c
            LEFT JOIN contract_pkwt.list_contract lc ON c.campaign_id = lc.campaign_id
            LEFT JOIN contract_pkwt.contract_status cs ON lc.contract_id = cs.contract_id
            GROUP BY c.campaign_id, c.company, c.created_at, c.send_at, c.due_date
            ORDER BY c.created_at DESC
        """)

        campaigns = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        result = []
        for campaign in campaigns:
            campaign_dict = dict(zip(column_names, campaign))
            if campaign_dict.get('created_at'):
                campaign_dict['created_at'] = campaign_dict['created_at'].isoformat()
            if campaign_dict.get('send_at'):
                campaign_dict['send_at'] = campaign_dict['send_at'].isoformat()
            if campaign_dict.get('due_date'):
                campaign_dict['due_date'] = campaign_dict['due_date'].isoformat()
            result.append(campaign_dict)

        cursor.close()
        conn.close()

        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/companies/search")
async def search_companies(q: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Search for companies that contain the query string
        cursor.execute("""
            SELECT DISTINCT company
            FROM contract_pkwt.campaign
            WHERE company ILIKE %s
            ORDER BY company
            LIMIT 10
        """, (f"%{q}%",))

        companies = cursor.fetchall()
        result = [{"company": company[0]} for company in companies]

        cursor.close()
        conn.close()

        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/campaigns")
async def create_campaign(campaign: CampaignCreate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert campaign
        cursor.execute("""
            INSERT INTO contract_pkwt.campaign (company, created_at, send_at, due_date)
            VALUES (%s, CURRENT_DATE, %s, %s)
            RETURNING campaign_id
        """, (campaign.company, campaign.send_date, campaign.due_date))

        campaign_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "campaign_id": campaign_id,
            "message": "Campaign created successfully"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/campaigns/upload-employees")
async def upload_employees(file: UploadFile = File(...), campaign_id: int = Form(...)):
    try:
        # Read file content
        contents = await file.read()

        # Determine file type and read accordingly
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        # Validate that the campaign_id exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT campaign_id FROM contract_pkwt.campaign WHERE campaign_id = %s", (campaign_id,))
        campaign_exists = cursor.fetchone()
        cursor.close()
        conn.close()

        if campaign_exists is None:
            raise HTTPException(status_code=400, detail=f"Campaign with ID {campaign_id} not found")

        # Data conversion and mapping using column indices
        df_converted = pd.DataFrame()

        # First create a column with data to establish row count
        df_converted['contract_num_detail'] = df.iloc[:, 1].astype(str)  # PKWT NO
        df_converted['campaign_id'] = campaign_id
        df_converted = df_converted[['campaign_id', 'contract_num_detail']]  # Reorder columns
        df_converted['NIP'] = df.iloc[:, 2].astype(str)  # NIP
        df_converted['name'] = df.iloc[:, 3].astype(str)  # NAMA
        df_converted['job_description'] = df.iloc[:, 4].astype(str)  # BAGIAN
        df_converted['location'] = df.iloc[:, 5].astype(str)  # LOKASI KERJA
        df_converted['birthplace'] = df.iloc[:, 6].astype(str)  # TTL

        # Convert birthdate
        def convert_date(date_val):
            if pd.isna(date_val):
                return None
            try:
                if isinstance(date_val, str):
                    return pd.to_datetime(date_val, dayfirst=True).date()
                else:
                    return pd.to_datetime(date_val, dayfirst=True).date()
            except:
                return None

        df_converted['birthdate'] = df.iloc[:, 7].apply(convert_date)  # TGL.LAHIR
        df_converted['marriage_status'] = df.iloc[:, 8].astype(str)  # Status
        df_converted['gender'] = df.iloc[:, 9].astype(str)  # GENDER
        df_converted['address'] = df.iloc[:, 10].astype(str)  # ALAMAT
        df_converted['nik'] = df.iloc[:, 11].astype(str)  # NIK
        df_converted['tax_status'] = df.iloc[:, 12].astype(str)  # STATUS TAX
        df_converted['npwp'] = df.iloc[:, 13].astype(str)  # NPWP
        df_converted['mobile_number'] = df.iloc[:, 14].astype(str)  # HP
        df_converted['email'] = df.iloc[:, 15].astype(str)  # EMAIL TERBARU
        df_converted['mothers_name'] = df.iloc[:, 16].astype(str)  # NAMA LENGKAP IBU KANDUNG
        df_converted['bank_account'] = df.iloc[:, 17].astype(str)  # NOREK BRI
        df_converted['gt'] = df.iloc[:, 18].astype(int)  # GT
        df_converted['job_position'] = df.iloc[:, 19].astype(str)  # BAGIAN

        # Insert into database
        conn = get_db_connection()
        cursor = conn.cursor()

        insert_sql = """
        INSERT INTO contract_pkwt.list_contract (
            campaign_id, contract_num_detail, nip, name, job_description, location,
            birthplace, birthdate, marriage_status, gender, address, nik,
            tax_status, npwp, mobile_number, email, mothers_name, bank_account,
            gt, job_position
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """

        inserted_count = 0
        for _, row in df_converted.iterrows():
            try:
                print(f"Inserting row with {len(row)} values:")
                print(f"Values: {tuple(row)}")
                print(f"SQL: {insert_sql}")
                cursor.execute(insert_sql, tuple(row))
                inserted_count += 1
                conn.commit()  # Commit each row individually
            except Exception as e:
                print(f"Error inserting row: {e}")
                conn.rollback()  # Rollback failed transaction
                continue

        cursor.close()
        conn.close()

        return {
            "message": "Employee data uploaded successfully",
            "processed_count": inserted_count
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/campaigns/{campaign_id}/contracts")
async def get_campaign_contracts(campaign_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM contract_pkwt.list_contract WHERE campaign_id = %s", (campaign_id,))
        contracts = cursor.fetchall()

        # Get column names
        column_names = [desc[0] for desc in cursor.description]

        # Convert to list of dictionaries
        result = []
        for contract in contracts:
            result.append(dict(zip(column_names, contract)))

        cursor.close()
        conn.close()

        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.delete("/api/campaigns/{campaign_id}/contracts")
async def delete_campaign_contracts(campaign_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM contract_pkwt.list_contract WHERE campaign_id = %s", (campaign_id,))
        deleted_count = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": f"Deleted {deleted_count} contracts"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

def generate_pdfs_background(campaign_id: int):
    """Background task to generate PDFs for all contracts in a campaign"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get campaign template
        cursor.execute("""
            SELECT html_page FROM contract_pkwt.contract
            WHERE campaign_id = %s
        """, (campaign_id,))
        template_result = cursor.fetchone()

        if not template_result:
            print(f"No template found for campaign_id {campaign_id}")
            cursor.close()
            conn.close()
            return

        html_template_base = template_result[0]

        # Get all contracts for this campaign
        cursor.execute("SELECT * FROM contract_pkwt.list_contract WHERE campaign_id = %s", (campaign_id,))
        contracts = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        if not contracts:
            print(f"No contracts found for campaign_id {campaign_id}")
            cursor.close()
            conn.close()
            return

        # Update campaign with total PDF count and set status to 'processing'
        cursor.execute("""
            UPDATE contract_pkwt.campaign
            SET pdf_total = %s, pdf_generated = 0, pdf_status = 'processing'
            WHERE campaign_id = %s
        """, (len(contracts), campaign_id))
        conn.commit()

        # Helper functions for formatting
        def format_indonesian_date(date_obj):
            if not date_obj:
                return ""
            month_names = [
                'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
            ]
            return f"{date_obj.day:02d} {month_names[date_obj.month - 1]} {date_obj.year}"

        def format_currency(value):
            return f"{value:,}".replace(',', '.')

        # Insert contract status records and generate PDFs
        inserted_count = 0
        pdf_generated_count = 0

        async def generate_pdf_with_playwright(html_content, title='Contract'):
            """Generate PDF from HTML using Playwright"""
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.set_content(html_content, wait_until='networkidle')
                pdf_bytes = await page.pdf(
                    format='A4',
                    margin={'top': '1.5cm', 'right': '1.5cm', 'bottom': '1.5cm', 'left': '1.5cm'},
                    print_background=True,
                    display_header_footer=False
                )
                await browser.close()
                return pdf_bytes

        for contract in contracts:
            contract_dict = dict(zip(column_names, contract))
            contract_id = contract_dict['contract_id']

            try:
                # Insert contract status
                cursor.execute("""
                    INSERT INTO contract_pkwt.contract_status (campaign_id, contract_id, send_status, signed_status, signed_at)
                    VALUES (%s, %s, FALSE, FALSE, NULL)
                    ON CONFLICT DO NOTHING
                """, (campaign_id, contract_id))

                if cursor.rowcount > 0:
                    inserted_count += 1

                # Generate PDF for this contract
                try:
                    html_template = html_template_base

                    # Replace placeholders with employee data
                    for key, value in contract_dict.items():
                        display_value = value if value is not None else ''

                        if key == 'birthdate' and value:
                            display_value = format_indonesian_date(value)
                        elif key == 'gt' and value:
                            display_value = format_currency(value)

                        plain_placeholder = f"{{{key}}}"
                        html_placeholder = f"{{<span class=SpellE>{key}</span>}}"

                        html_template = html_template.replace(plain_placeholder, str(display_value))
                        html_template = html_template.replace(html_placeholder, str(display_value))

                    # Set title to contract_num_detail
                    contract_title = contract_dict.get('contract_num_detail', 'Contract')
                    html_template = re.sub(r'<title>.*?</title>', f'<title>{contract_title}</title>', html_template, flags=re.IGNORECASE)

                    # Convert HTML to PDF using Playwright
                    pdf_bytes = asyncio.run(generate_pdf_with_playwright(html_template, contract_title))

                    # Update contract_status with PDF data
                    cursor.execute("""
                        UPDATE contract_pkwt.contract_status
                        SET pdf_data = %s
                        WHERE contract_id = %s
                    """, (pdf_bytes, contract_id))
                    pdf_generated_count += 1
                    print(f"Generated PDF for contract_id {contract_id}")

                    # Update campaign progress
                    cursor.execute("""
                        UPDATE contract_pkwt.campaign
                        SET pdf_generated = %s
                        WHERE campaign_id = %s
                    """, (pdf_generated_count, campaign_id))
                    conn.commit()

                except Exception as pdf_error:
                    print(f"Error generating PDF for contract_id {contract_id}: {pdf_error}")
                    continue

            except Exception as e:
                print(f"Error inserting contract status for contract_id {contract_id}: {e}")
                continue

        conn.commit()

        # Mark campaign as completed
        cursor.execute("""
            UPDATE contract_pkwt.campaign
            SET pdf_status = 'completed'
            WHERE campaign_id = %s
        """, (campaign_id,))
        conn.commit()

        cursor.close()
        conn.close()

        print(f"Background PDF generation completed: {pdf_generated_count}/{len(contracts)} PDFs generated")

    except Exception as e:
        import traceback
        print(f"Error in background PDF generation: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")

        # Mark campaign as failed
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE contract_pkwt.campaign
                SET pdf_status = 'failed'
                WHERE campaign_id = %s
            """, (campaign_id,))
            conn.commit()
            cursor.close()
            conn.close()
        except:
            pass

@app.post("/api/campaigns/upload-contract")
async def upload_contract(background_tasks: BackgroundTasks, file: UploadFile = File(...), campaign_id: int = Form(...)):
    try:
        # Validate campaign exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT campaign_id FROM contract_pkwt.campaign WHERE campaign_id = %s", (campaign_id,))
        campaign_exists = cursor.fetchone()

        if campaign_exists is None:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=400, detail=f"Campaign with ID {campaign_id} not found")

        # Get employees for this campaign
        cursor.execute("SELECT * FROM contract_pkwt.list_contract WHERE campaign_id = %s", (campaign_id,))
        employees = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        cursor.close()
        conn.close()

        if not employees:
            raise HTTPException(status_code=400, detail="No employees found for this campaign")

        # Read file content
        file_content = await file.read()

        # Convert contract file to HTML (base template for campaign)
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create base template without employee data substitution
        html_content = process_contract_file(file_content, file.filename, {})

        # Insert single contract template into contract table
        cursor.execute("""
            INSERT INTO contract_pkwt.contract (base_contract_id, campaign_id, html_page)
            VALUES (%s, %s, %s)
        """, (campaign_id, campaign_id, html_content))

        conn.commit()

        cursor.close()
        conn.close()

        # Schedule PDF generation in background
        background_tasks.add_task(generate_pdfs_background, campaign_id)

        return {
            "message": "Contract template uploaded successfully. PDFs are being generated in the background.",
            "campaign_id": campaign_id
        }

    except Exception as e:
        import traceback
        print(f"Error in upload_contract: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/campaigns/{campaign_id}/contract-template")
async def get_contract_template(campaign_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT html_page FROM contract_pkwt.contract WHERE campaign_id = %s", (campaign_id,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result:
            return {"html_page": result[0]}
        else:
            return JSONResponse(status_code=404, content={"error": "Contract template not found"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/campaigns/{campaign_id}/populate-status")
async def populate_contract_status(campaign_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if campaign exists
        cursor.execute("SELECT campaign_id FROM contract_pkwt.campaign WHERE campaign_id = %s", (campaign_id,))
        campaign_exists = cursor.fetchone()

        if campaign_exists is None:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Campaign not found"})

        # Get campaign template
        cursor.execute("""
            SELECT html_page FROM contract_pkwt.contract
            WHERE campaign_id = %s
        """, (campaign_id,))
        template_result = cursor.fetchone()

        if not template_result:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Contract template not found for this campaign"})

        html_template_base = template_result[0]

        # Get all contracts for this campaign
        cursor.execute("SELECT * FROM contract_pkwt.list_contract WHERE campaign_id = %s", (campaign_id,))
        contracts = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        if not contracts:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "No contracts found for this campaign"})

        # Helper functions for formatting
        def format_indonesian_date(date_obj):
            if not date_obj:
                return ""
            month_names = [
                'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
            ]
            return f"{date_obj.day:02d} {month_names[date_obj.month - 1]} {date_obj.year}"

        def format_currency(value):
            return f"{value:,}".replace(',', '.')

        # Insert contract status records and generate PDFs
        inserted_count = 0
        pdf_generated_count = 0

        async def generate_pdf_with_playwright(html_content, title='Contract'):
            """Generate PDF from HTML using Playwright"""
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.set_content(html_content, wait_until='networkidle')
                pdf_bytes = await page.pdf(
                    format='A4',
                    margin={'top': '1.5cm', 'right': '1.5cm', 'bottom': '1.5cm', 'left': '1.5cm'},
                    print_background=True,
                    display_header_footer=False
                )
                await browser.close()
                return pdf_bytes

        for contract in contracts:
            contract_dict = dict(zip(column_names, contract))
            contract_id = contract_dict['contract_id']

            try:
                # Insert contract status
                cursor.execute("""
                    INSERT INTO contract_pkwt.contract_status (campaign_id, contract_id, send_status, signed_status, signed_at)
                    VALUES (%s, %s, FALSE, FALSE, NULL)
                    ON CONFLICT DO NOTHING
                """, (campaign_id, contract_id))

                if cursor.rowcount > 0:
                    inserted_count += 1

                    # Generate PDF for this contract
                    try:
                        html_template = html_template_base

                        # Replace placeholders with employee data
                        for key, value in contract_dict.items():
                            display_value = value if value is not None else ''

                            if key == 'birthdate' and value:
                                display_value = format_indonesian_date(value)
                            elif key == 'gt' and value:
                                display_value = format_currency(value)

                            plain_placeholder = f"{{{key}}}"
                            html_placeholder = f"{{<span class=SpellE>{key}</span>}}"

                            html_template = html_template.replace(plain_placeholder, str(display_value))
                            html_template = html_template.replace(html_placeholder, str(display_value))

                        # Set title to contract_num_detail
                        contract_title = contract_dict.get('contract_num_detail', 'Contract')
                        html_template = re.sub(r'<title>.*?</title>', f'<title>{contract_title}</title>', html_template, flags=re.IGNORECASE)

                        # Convert HTML to PDF using Playwright
                        pdf_bytes = await generate_pdf_with_playwright(html_template, contract_title)

                        # Update contract_status with PDF data
                        cursor.execute("""
                            UPDATE contract_pkwt.contract_status
                            SET pdf_data = %s
                            WHERE contract_id = %s
                        """, (pdf_bytes, contract_id))
                        pdf_generated_count += 1

                    except Exception as pdf_error:
                        print(f"Error generating PDF for contract_id {contract_id}: {pdf_error}")
                        continue

            except Exception as e:
                print(f"Error inserting contract status for contract_id {contract_id}: {e}")
                continue

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "message": "Contract status populated and PDFs generated successfully",
            "inserted_count": inserted_count,
            "pdf_generated_count": pdf_generated_count,
            "total_contracts": len(contracts)
        }

    except Exception as e:
        import traceback
        print(f"Error in populate_contract_status: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/payroll-campaigns-with-stats")
async def get_payroll_campaigns_with_stats():
    """Get all payroll campaigns with statistics and PDF generation progress"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get payroll campaigns with statistics
        cursor.execute("""
            SELECT
                pc.payroll_campaign_id,
                pc.company,
                pc.created_at,
                pc.send_at,
                pc.status,
                pc.pdf_total,
                pc.pdf_generated,
                pc.pdf_status,
                COUNT(lp.list_payroll_id) as total_employees,
                COUNT(CASE WHEN ps.send_status = TRUE THEN 1 END) as sent_count
            FROM contract_pkwt.payroll_campaign pc
            LEFT JOIN contract_pkwt.list_payroll lp ON pc.payroll_campaign_id = lp.payroll_campaign_id
            LEFT JOIN contract_pkwt.payroll_status ps ON lp.list_payroll_id = ps.list_payroll_id
            GROUP BY pc.payroll_campaign_id, pc.company, pc.created_at, pc.send_at, pc.status,
                     pc.pdf_total, pc.pdf_generated, pc.pdf_status
            ORDER BY pc.created_at DESC
        """)

        campaigns = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        # Convert to list of dictionaries
        result = []
        for campaign in campaigns:
            campaign_dict = dict(zip(column_names, campaign))
            # Convert dates to strings
            if campaign_dict.get('created_at'):
                campaign_dict['created_at'] = campaign_dict['created_at'].isoformat()
            if campaign_dict.get('send_at'):
                campaign_dict['send_at'] = campaign_dict['send_at'].isoformat()
            result.append(campaign_dict)

        cursor.close()
        conn.close()

        return result
    except Exception as e:
        import traceback
        print("ERROR in get_payroll_campaigns_with_stats:")
        print(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/campaigns-with-stats")
async def get_campaigns_with_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get campaigns with contract statistics
        cursor.execute("""
            SELECT
                c.campaign_id,
                c.company,
                c.created_at,
                c.send_at,
                c.due_date,
                c.pdf_total,
                c.pdf_generated,
                c.pdf_status,
                COUNT(lc.contract_id) as total_contracts,
                COUNT(CASE WHEN cs.send_status = TRUE THEN 1 END) as sent_count,
                COUNT(CASE WHEN cs.signed_status = TRUE THEN 1 END) as signed_count
            FROM contract_pkwt.campaign c
            LEFT JOIN contract_pkwt.list_contract lc ON c.campaign_id = lc.campaign_id
            LEFT JOIN contract_pkwt.contract_status cs ON lc.contract_id = cs.contract_id
            GROUP BY c.campaign_id, c.company, c.created_at, c.send_at, c.due_date, c.pdf_total, c.pdf_generated, c.pdf_status
            ORDER BY c.created_at DESC
        """)

        campaigns = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        # Convert to list of dictionaries
        result = []
        for campaign in campaigns:
            campaign_dict = dict(zip(column_names, campaign))
            # Convert dates to strings
            campaign_dict['created_at'] = campaign_dict['created_at'].isoformat() if campaign_dict['created_at'] else None
            campaign_dict['send_at'] = campaign_dict['send_at'].isoformat() if campaign_dict['send_at'] else None
            campaign_dict['due_date'] = campaign_dict['due_date'].isoformat() if campaign_dict['due_date'] else None
            result.append(campaign_dict)

        cursor.close()
        conn.close()

        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM contract_pkwt.campaign WHERE campaign_id = %s", (campaign_id,))
        campaign = cursor.fetchone()

        if not campaign:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Campaign not found"})

        column_names = [desc[0] for desc in cursor.description]
        campaign_dict = dict(zip(column_names, campaign))

        # Convert dates to strings
        campaign_dict['created_at'] = campaign_dict['created_at'].isoformat() if campaign_dict['created_at'] else None
        campaign_dict['send_at'] = campaign_dict['send_at'].isoformat() if campaign_dict['send_at'] else None
        campaign_dict['due_date'] = campaign_dict['due_date'].isoformat() if campaign_dict['due_date'] else None

        cursor.close()
        conn.close()

        return campaign_dict
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/campaigns/{campaign_id}/contracts-with-status")
async def get_campaign_contracts_with_status(campaign_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                lc.contract_id,
                lc.campaign_id,
                lc.contract_num_detail,
                lc.name,
                lc.mobile_number,
                lc.email,
                lc.nip,
                lc.job_description,
                lc.location,
                lc.birthplace,
                lc.birthdate,
                lc.marriage_status,
                lc.gender,
                lc.address,
                lc.nik,
                lc.tax_status,
                lc.npwp,
                lc.mothers_name,
                lc.bank_account,
                lc.gt,
                lc.job_position,
                cs.send_status,
                cs.signed_status,
                cs.signed_at
            FROM contract_pkwt.list_contract lc
            LEFT JOIN contract_pkwt.contract_status cs ON lc.contract_id = cs.contract_id
            WHERE lc.campaign_id = %s
            ORDER BY lc.contract_id
        """, (campaign_id,))

        contracts = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        # Convert to list of dictionaries
        result = []
        for contract in contracts:
            contract_dict = dict(zip(column_names, contract))
            # Convert dates to strings
            if contract_dict.get('birthdate'):
                contract_dict['birthdate'] = contract_dict['birthdate'].isoformat()
            if contract_dict.get('signed_at'):
                contract_dict['signed_at'] = contract_dict['signed_at'].isoformat()
            result.append(contract_dict)

        cursor.close()
        conn.close()

        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/contract/{contract_id}")
async def get_contract_details(contract_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get contract details with status
        cursor.execute("""
            SELECT
                lc.contract_id,
                lc.campaign_id,
                lc.contract_num_detail,
                lc.name,
                lc.nip,
                lc.job_description,
                lc.location,
                lc.email,
                lc.mobile_number,
                cs.send_status,
                cs.signed_status,
                cs.signed_at
            FROM contract_pkwt.list_contract lc
            LEFT JOIN contract_pkwt.contract_status cs ON lc.contract_id = cs.contract_id
            WHERE lc.contract_id = %s
        """, (contract_id,))

        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result:
            column_names = ['contract_id', 'campaign_id', 'contract_num_detail', 'name', 'nip',
                          'job_description', 'location', 'email', 'mobile_number',
                          'send_status', 'signed_status', 'signed_at']
            contract_dict = dict(zip(column_names, result))

            if contract_dict.get('signed_at'):
                contract_dict['signed_at'] = contract_dict['signed_at'].isoformat()

            return contract_dict
        else:
            return JSONResponse(status_code=404, content={"error": "Contract not found"})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/contracts/{contract_id}/pdf")
async def get_contract_pdf(contract_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get PDF from contract_status
        cursor.execute("""
            SELECT pdf_data FROM contract_pkwt.contract_status
            WHERE contract_id = %s
        """, (contract_id,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result and result[0]:
            return Response(content=bytes(result[0]), media_type="application/pdf")
        else:
            return JSONResponse(status_code=404, content={"error": "PDF not found. Please regenerate contract status."})

    except Exception as e:
        import traceback
        print(f"Error retrieving PDF: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/sign-contract")
async def sign_contract(signature: UploadFile = File(...), contract_id: int = Form(...)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get existing PDF
        cursor.execute("""
            SELECT pdf_data FROM contract_pkwt.contract_status
            WHERE contract_id = %s
        """, (contract_id,))
        result = cursor.fetchone()

        if not result or not result[0]:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "PDF not found"})

        # Read existing PDF
        existing_pdf_bytes = bytes(result[0])
        existing_pdf = io.BytesIO(existing_pdf_bytes)
        pdf_reader = PdfReader(existing_pdf)
        pdf_writer = PdfWriter()

        # Read signature file
        signature_bytes = await signature.read()

        # Determine if SVG or image
        is_svg = signature.filename.endswith('.svg') if signature.filename else False

        # Find last two pages with signature tables (pages 4 and 5, indices 4 and 5)
        signature_pages = []
        total_pages = len(pdf_reader.pages)

        # Check last two pages
        for page_num in [total_pages - 2, total_pages - 1]:
            if page_num >= 0:
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if "PIHAK PERTAMA" in text and "PIHAK KEDUA" in text:
                    signature_pages.append(page_num)

        if not signature_pages:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=400, content={"error": "Could not find signature location in PDF"})

        # Save signature temporarily
        if is_svg:
            sig_path = f"temp_signature_{contract_id}.svg"
            with open(sig_path, 'wb') as f:
                f.write(signature_bytes)
        else:
            sig_path = f"temp_signature_{contract_id}.png"
            signature_image = Image.open(io.BytesIO(signature_bytes))
            signature_image.save(sig_path, "PNG")

        # Define signature positions for each page
        # A4 dimensions: 595 x 842 points
        # Adjust these coordinates for each page
        signature_positions = {
            total_pages - 2: {  # Second to last page (page 4, index 4)
                'x': 380,
                'y': 250,
                'width': 170,
                'height': 100
            },
            total_pages - 1: {  # Last page (page 5, index 5)
                'x': 380,
                'y': 150,
                'width': 170,
                'height': 100
            }
        }

        # Copy all pages and add signature to target pages
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]

            if page_num in signature_pages and page_num in signature_positions:
                # Get position for this specific page
                pos = signature_positions[page_num]

                # Create signature overlay for this page
                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=A4)

                if is_svg:
                    # Convert SVG to RLG drawing
                    drawing = svg2rlg(sig_path)
                    if drawing:
                        # Scale drawing to fit
                        scale_x = pos['width'] / drawing.width
                        scale_y = pos['height'] / drawing.height
                        scale = min(scale_x, scale_y)
                        drawing.width = drawing.width * scale
                        drawing.height = drawing.height * scale
                        drawing.scale(scale, scale)
                        # Draw the SVG
                        renderPDF.draw(drawing, can, pos['x'], pos['y'])
                else:
                    can.drawImage(sig_path, pos['x'], pos['y'], width=pos['width'], height=pos['height'], preserveAspectRatio=True, mask='auto')

                can.save()
                packet.seek(0)
                signature_pdf = PdfReader(packet)
                page.merge_page(signature_pdf.pages[0])

            pdf_writer.add_page(page)

        # Clean up temp file
        if os.path.exists(sig_path):
            os.remove(sig_path)

        # Write signed PDF to bytes
        signed_pdf_bytes = io.BytesIO()
        pdf_writer.write(signed_pdf_bytes)
        signed_pdf_bytes.seek(0)

        # Update database with signed PDF
        cursor.execute("""
            UPDATE contract_pkwt.contract_status
            SET pdf_data = %s, signed_status = TRUE, signed_at = %s
            WHERE contract_id = %s
        """, (signed_pdf_bytes.getvalue(), datetime.now(), contract_id))

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "message": "Contract signed successfully",
            "contract_id": contract_id,
            "signed_at": datetime.now().isoformat()
        }

    except Exception as e:
        import traceback
        print(f"Error signing contract: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})

def get_email_body(contract_id):
    """Generate email body for a contract"""
    # Indonesian month names
    INDONESIAN_MONTHS = {
        1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April',
        5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus',
        9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
    }

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, birthplace, birthdate, nik, location, job_description, contract_num_detail_md5
        FROM contract_pkwt.list_contract
        WHERE contract_id = %s
    """, (contract_id,))

    contract = cursor.fetchone()
    cursor.close()
    conn.close()

    if not contract:
        return None

    name, birthplace, birthdate, nik, location, job_description, contract_num_detail_md5 = contract

    # Format birthdate with Indonesian month
    if birthdate:
        day = birthdate.day
        month = INDONESIAN_MONTHS[birthdate.month]
        year = birthdate.year
        birthdate_str = f'{day} {month} {year}'
    else:
        birthdate_str = '-'

    # Build HTML email body
    html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .info-table {{
            margin: 20px 0;
        }}
        .info-row {{
            display: flex;
            margin: 8px 0;
        }}
        .info-label {{
            min-width: 200px;
            font-weight: 500;
        }}
        .info-value {{
            flex: 1;
        }}
        a {{
            color: #7c3aed;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <p><strong>Penempatan PT Mandom Indonesia Tbk</strong></p>

    <p>Dear {name},</p>

    <p>Selamat datang di PT JMAX Indonesia!</p>

    <p>Kami dengan senang hati menyambut Anda sebagai bagian dari tim kami dalam penempatan PT Mandom Indonesia Tbk. Kehadiran Anda merupakan kontribusi penting dalam mendukung keberhasilan dan kelancaran proyek ini.</p>

    <p>Berikut beberapa informasi awal yang perlu Anda ketahui:</p>

    <div class="info-table">
        <div class="info-row">
            <div class="info-label">🔹 Nama</div>
            <div class="info-value">: {name}</div>
        </div>
        <div class="info-row">
            <div class="info-label">🔹 Tempat/Tanggal Lahir</div>
            <div class="info-value">: {birthplace}, {birthdate_str}</div>
        </div>
        <div class="info-row">
            <div class="info-label">🔹 NIK</div>
            <div class="info-value">: {nik}</div>
        </div>
        <div class="info-row">
            <div class="info-label">🔹 Lokasi Penempatan</div>
            <div class="info-value">: {location}</div>
        </div>
        <div class="info-row">
            <div class="info-label">🔹 Jabatan / Posisi</div>
            <div class="info-value">: {job_description}</div>
        </div>
    </div>

    <p>Untuk melanjutkan proses administrasi, anda harus melengkapi dokumen melalui link:<br>
    <a href="https://pkwt.jmaxindo.id/registrasi/{contract_num_detail_md5}">https://pkwt.jmaxindo.id/registrasi/{contract_num_detail_md5}</a></p>

    <p>Kami percaya bahwa semangat, keahlian, dan dedikasi Anda akan membawa nilai tambah bagi tim dan perusahaan.</p>

    <p>Jika Anda memiliki pertanyaan atau membutuhkan informasi lebih lanjut, jangan ragu untuk menghubungi HRD kami di ebenezer@jmaxindo.com.</p>

    <p>Sekali lagi, selamat bergabung dan mari kita wujudkan kesuksesan bersama!</p>

    <p>Salam hangat,<br>
    Tajunissa Legisa W<br>
    General Manager<br>
    PT JMAX Indonesia<br>
    📧 Lisa@jmaxindo.com</p>
</body>
</html>"""

    # Build plain text version
    text_body = f"""Penempatan PT Mandom Indonesia Tbk

Dear {name},

Selamat datang di PT JMAX Indonesia!

Kami dengan senang hati menyambut Anda sebagai bagian dari tim kami dalam penempatan PT Mandom Indonesia Tbk. Kehadiran Anda merupakan kontribusi penting dalam mendukung keberhasilan dan kelancaran proyek ini.

Berikut beberapa informasi awal yang perlu Anda ketahui:

🔹 Nama                   : {name}
🔹 Tempat/Tanggal Lahir   : {birthplace}, {birthdate_str}
🔹 NIK                    : {nik}
🔹 Lokasi Penempatan      : {location}
🔹 Jabatan / Posisi       : {job_description}

Untuk melanjutkan proses administrasi, anda harus melengkapi dokumen melalui link:
https://pkwt.jmaxindo.id/registrasi/{contract_num_detail_md5}

Kami percaya bahwa semangat, keahlian, dan dedikasi Anda akan membawa nilai tambah bagi tim dan perusahaan.

Jika Anda memiliki pertanyaan atau membutuhkan informasi lebih lanjut, jangan ragu untuk menghubungi HRD kami di ebenezer@jmaxindo.com.

Sekali lagi, selamat bergabung dan mari kita wujudkan kesuksesan bersama!

Salam hangat,
Tajunissa Legisa W
General Manager
PT JMAX Indonesia
📧 Lisa@jmaxindo.com"""

    return {"html": html_body, "text": text_body}

@app.post("/api/email-preview")
async def email_preview(contract_id: int = Form(...)):
    try:
        email_data = get_email_body(contract_id)

        if not email_data:
            return JSONResponse(status_code=404, content={"error": "Contract not found"})

        return {
            "email_body": email_data["html"],
            "recipient": "hr@jmaxindo.id"
        }

    except Exception as e:
        import traceback
        print(f"Error generating email preview: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/send-email")
async def send_email_api(contract_id: int = Form(...)):
    try:
        # Get employee email from list_contract
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT email FROM contract_pkwt.list_contract
            WHERE contract_id = %s
        """, (contract_id,))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if not result or not result[0]:
            return JSONResponse(status_code=404, content={"error": "Employee email not found"})

        employee_email = result[0]

        email_data = get_email_body(contract_id)

        if not email_data:
            return JSONResponse(status_code=404, content={"error": "Contract not found"})

        # Send email via Postmark
        postmark_response = requests.post(
            'https://api.postmarkapp.com/email',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Postmark-Server-Token': 'e3e7715d-2a61-4187-b79e-6c27733c9cda'
            },
            json={
                'From': 'hr@jmaxindo.id',
                'To': employee_email,
                'Subject': 'Selamat Bergabung di PT JMAX Indonesia',
                'HtmlBody': email_data["html"],
                'TextBody': email_data["text"],
                'MessageStream': 'outbound'
            }
        )

        if postmark_response.status_code not in [200, 201]:
            raise Exception(f"Postmark API error: {postmark_response.text}")

        # Update send_status to True
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE contract_pkwt.contract_status
            SET send_status = TRUE, send_at = CURRENT_TIMESTAMP
            WHERE contract_id = %s
        """, (contract_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "message": "Email sent successfully!",
            "contract_id": contract_id
        }

    except Exception as e:
        import traceback
        print(f"Error sending email: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})

class BulkEmailRequest(BaseModel):
    contract_ids: List[int]
    mode: str
    campaign_id: int = None

@app.post("/api/bulk-send-email")
async def bulk_send_email(request: BulkEmailRequest):
    try:
        success = []
        failed = []

        for contract_id in request.contract_ids:
            try:
                # Get employee email from list_contract
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT email FROM contract_pkwt.list_contract
                    WHERE contract_id = %s
                """, (contract_id,))

                result = cursor.fetchone()
                cursor.close()
                conn.close()

                if not result or not result[0]:
                    failed.append({
                        "contract_id": contract_id,
                        "error": "Employee email not found"
                    })
                    continue

                employee_email = result[0]

                email_data = get_email_body(contract_id)

                if not email_data:
                    failed.append({
                        "contract_id": contract_id,
                        "error": "Contract not found"
                    })
                    continue

                # Send email via Postmark
                postmark_response = requests.post(
                    'https://api.postmarkapp.com/email',
                    headers={
                        'Accept': 'application/json',
                        'Content-Type': 'application/json',
                        'X-Postmark-Server-Token': 'e3e7715d-2a61-4187-b79e-6c27733c9cda'
                    },
                    json={
                        'From': 'hr@jmaxindo.id',
                        'To': employee_email,
                        'Subject': 'Selamat Bergabung di PT JMAX Indonesia',
                        'HtmlBody': email_data["html"],
                        'TextBody': email_data["text"],
                        'MessageStream': 'outbound'
                    }
                )

                if postmark_response.status_code not in [200, 201]:
                    error_msg = f"Failed to send email: {postmark_response.text}"
                    failed.append({'contract_id': contract_id, 'error': error_msg})
                    continue

                # Update send_status to True
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE contract_pkwt.contract_status
                    SET send_status = TRUE, send_at = CURRENT_TIMESTAMP
                    WHERE contract_id = %s
                """, (contract_id,))

                conn.commit()
                cursor.close()
                conn.close()

                success.append(contract_id)

            except Exception as e:
                failed.append({
                    "contract_id": contract_id,
                    "error": str(e)
                })

        return {
            "success": success,
            "failed": failed,
            "total": len(request.contract_ids),
            "success_count": len(success),
            "failed_count": len(failed)
        }

    except Exception as e:
        import traceback
        print(f"Error in bulk send email: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/unsigned-active-contracts")
async def get_unsigned_active_contracts():
    """Get active contracts without signatures"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                uc.uid,
                alc.contract_id,
                alc.contract_num_detail,
                alc.name,
                alc.nik,
                alc.nip,
                alc.email,
                alc.job_description,
                alc.mobile_number
            FROM uid_contracts uc
            JOIN authenticated_list_contract alc ON uc.uid = alc.uid
            WHERE uc.active = TRUE
            AND uc.uid NOT IN (
                SELECT DISTINCT uid
                FROM contract_signatures
            )
            ORDER BY alc.name;
        """)

        contracts = cursor.fetchall()
        cursor.close()
        conn.close()

        result = []
        for row in contracts:
            result.append({
                "uid": str(row[0]),
                "contract_id": row[1],
                "contract_num_detail": row[2],
                "name": row[3],
                "nik": row[4],
                "nip": row[5],
                "email": row[6],
                "job_description": row[7],
                "mobile_number": row[8]
            })

        return JSONResponse(content=result)

    except Exception as e:
        import traceback
        print(f"Error getting unsigned active contracts: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


class ReminderRequest(BaseModel):
    uids: List[str]
    names: List[str]
    emails: List[str]

@app.post("/api/send-reminders")
async def send_reminders(request: ReminderRequest):
    """Send reminder emails to selected contracts"""
    try:
        success_count = 0
        failed_count = 0

        conn = get_db_connection()
        cursor = conn.cursor()

        for uid, name, email in zip(request.uids, request.names, request.emails):
            try:
                if not email:
                    failed_count += 1
                    print(f"No email for {name}")
                    continue

                # Get contract_num_detail_md5 for this uid from contract_pkwt.list_contract
                cursor.execute("""
                    SELECT lc.contract_num_detail_md5
                    FROM contract_pkwt.list_contract lc
                    JOIN authenticated_list_contract alc ON lc.contract_num_detail = alc.contract_num_detail
                    WHERE alc.uid = %s
                """, (uid,))

                result = cursor.fetchone()
                contract_num_detail_md5 = result[0] if result else None

                if not contract_num_detail_md5:
                    print(f"No contract_num_detail_md5 found for {name}")
                    failed_count += 1
                    continue

                reminder_text = f"""Kami mengingatkan bahwa proses penandatanganan kontrak kerja waktu tertentu (PKWT) dapat diakses melalui platform digital.

Segera akses laman berikut untuk melakukan penandatanganan kontrak.
https://wa.me/6281220008729?text=ttd_{contract_num_detail_md5}

Terima kasih atas perhatian dan kerja samanya.

Salam hangat,
Tajunissa Legisa W
General Manager
PT JMAX Indonesia
📧 Lisa@jmaxindo.com"""

                html_body = f"<p>{reminder_text.replace(chr(10), '<br>')}</p>"

                postmark_response = requests.post(
                    'https://api.postmarkapp.com/email',
                    headers={
                        'Accept': 'application/json',
                        'Content-Type': 'application/json',
                        'X-Postmark-Server-Token': 'e3e7715d-2a61-4187-b79e-6c27733c9cda'
                    },
                    json={
                        'From': 'hr@jmaxindo.id',
                        'To': 'teguh.hardiansah@proton.me',
                        'Subject': f'Reminder: Penandatanganan PKWT - {name}',
                        'HtmlBody': html_body,
                        'TextBody': reminder_text,
                        'MessageStream': 'outbound'
                    }
                )

                if postmark_response.status_code == 200:
                    success_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                print(f"Error sending reminder for {name}: {str(e)}")
                failed_count += 1

        cursor.close()
        conn.close()

        return JSONResponse(content={
            "success_count": success_count,
            "failed_count": failed_count
        })

    except Exception as e:
        import traceback
        print(f"Error in send reminders: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/send-confirmation")
async def send_confirmation():
    """Send confirmation email for account activation"""
    try:
        confirmation_text = """Kami telah melakukan aktivasi akun atas nama Darwati. Silahkan Bapak/Ibu melakukan login kembali di link berikut untuk melanjutkan proses.
https://pkwt.jmaxindo.id/

Terima kasih atas perhatian dan kerja samanya.

Salam hangat,
Tajunissa Legisa W
General Manager
PT JMAX Indonesia
📧 Lisa@jmaxindo.com"""

        html_body = f"<p>{confirmation_text.replace(chr(10), '<br>')}</p>"

        postmark_response = requests.post(
            'https://api.postmarkapp.com/email',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Postmark-Server-Token': 'e3e7715d-2a61-4187-b79e-6c27733c9cda'
            },
            json={
                'From': 'hr@jmaxindo.id',
                'To': 'gavinpati@gmail.com',
                'Subject': 'Konfirmasi Aktivasi Akun - Darwati',
                'HtmlBody': html_body,
                'TextBody': confirmation_text,
                'MessageStream': 'outbound'
            }
        )

        if postmark_response.status_code in [200, 201]:
            return JSONResponse(content={
                "message": "Confirmation email sent successfully",
                "status": "success"
            })
        else:
            raise Exception(f"Postmark API error: {postmark_response.text}")

    except Exception as e:
        import traceback
        print(f"Error sending confirmation: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/signed-contracts")
async def get_signed_contracts():
    """Get all signed contracts from contract_signatures table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                uid,
                contract_num_detail,
                signer_name,
                signed_at
            FROM contract_signatures
            ORDER BY signed_at DESC
        """)

        contracts = cursor.fetchall()
        cursor.close()
        conn.close()

        result = []
        for row in contracts:
            result.append({
                "uid": str(row[0]),
                "contract_num_detail": row[1],
                "signer_name": row[2],
                "signed_at": row[3].isoformat() if row[3] else None
            })

        return JSONResponse(content=result)

    except Exception as e:
        import traceback
        print(f"Error getting signed contracts: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/signed-contracts/{uid}/pdf")
async def get_signed_contract_pdf(uid: str):
    """Get signed PDF for a specific contract by UID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT signed_pdf
            FROM contract_signatures
            WHERE uid = %s
        """, (uid,))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result and result[0]:
            return Response(content=bytes(result[0]), media_type="application/pdf")
        else:
            return JSONResponse(status_code=404, content={"error": "Signed PDF not found"})

    except Exception as e:
        import traceback
        print(f"Error retrieving signed PDF: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# Mobile signature endpoints - using new_authenticated views
@app.get("/api/mobile/contract-by-md5/{contract_md5}")
async def get_contract_by_md5(contract_md5: str):
    """Get contract details from new_authenticated_list_contract by MD5"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                contract_id,
                contract_num_detail,
                name,
                job_description,
                location,
                contract_num_detail_md5
            FROM public.new_authenticated_list_contract
            WHERE contract_num_detail_md5 = %s
        """, (contract_md5,))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return {
                "contract_id": result[0],
                "contract_num_detail": result[1],
                "name": result[2],
                "job_description": result[3],
                "location": result[4],
                "contract_num_detail_md5": result[5],
                "signed_status": False  # Will be checked separately
            }
        else:
            return JSONResponse(status_code=404, content={"error": "Contract not found"})

    except Exception as e:
        import traceback
        print(f"Error retrieving contract by MD5: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/mobile/contract-pdf-by-md5/{contract_md5}")
async def get_contract_pdf_by_md5(contract_md5: str):
    """Get contract PDF from new_authenticated_pdf_contract by MD5"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # First get contract_id from new_authenticated_list_contract
        cursor.execute("""
            SELECT contract_id
            FROM public.new_authenticated_list_contract
            WHERE contract_num_detail_md5 = %s
        """, (contract_md5,))

        contract_result = cursor.fetchone()

        if not contract_result:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Contract not found"})

        contract_id = contract_result[0]

        # Get PDF from new_authenticated_pdf_contract
        cursor.execute("""
            SELECT pdf_data
            FROM public.new_authenticated_pdf_contract
            WHERE contract_id = %s
        """, (contract_id,))

        pdf_result = cursor.fetchone()
        cursor.close()
        conn.close()

        if pdf_result and pdf_result[0]:
            return Response(content=bytes(pdf_result[0]), media_type="application/pdf")
        else:
            return JSONResponse(status_code=404, content={"error": "PDF not found"})

    except Exception as e:
        import traceback
        print(f"Error retrieving PDF by MD5: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ===== PAYROLL EMAIL FUNCTIONS =====

def get_payroll_email_body(list_payroll_id):
    """Generate email body for a payroll"""
    # Indonesian month names
    INDONESIAN_MONTHS = {
        1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April',
        5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus',
        9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
    }

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            lp.employee_name,
            lp.employee_id,
            lp.nik,
            lc.email,
            pc.company,
            pc.send_at,
            lp.thp
        FROM contract_pkwt.list_payroll lp
        JOIN contract_pkwt.payroll_campaign pc ON lp.payroll_campaign_id = pc.payroll_campaign_id
        LEFT JOIN contract_pkwt.list_contract lc ON lp.nik = lc.nik AND lc.contract_id > 137
        WHERE lp.list_payroll_id = %s
    """, (list_payroll_id,))

    payroll = cursor.fetchone()
    cursor.close()
    conn.close()

    if not payroll:
        return None

    employee_name, employee_id, nik, email, company, send_at, thp = payroll

    # Format period from send_at date
    if send_at:
        month = INDONESIAN_MONTHS[send_at.month]
        year = send_at.year
        period_str = f'{month} {year}'
    else:
        period_str = '-'

    # Format THP (Take Home Pay) with thousand separator
    if thp:
        thp_formatted = f"Rp {thp:,.0f}".replace(",", ".")
    else:
        thp_formatted = "Rp 0"

    subject = f"Payroll {company}"

    # Build HTML email body
    html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
    </style>
</head>
<body>
    <p>Dear {employee_name},</p>

    <p>Berikut kami lampirkan payroll untuk periode {period_str}.</p>

    <p>Untuk keamanan dokumen, silakan masukkan password sesuai tanggal lahir anda dengan format "ddmmyy".<br>
    Contoh: 19-02-1992 menjadi 190292.</p>

    <p>Jika Anda memiliki pertanyaan atau membutuhkan informasi lebih lanjut, hubungi HRD kami di ebenezer@jmaxindo.com.</p>

    <p>Salam hangat,<br>
    Tajunissa Legisa W<br>
    General Manager<br>
    PT JMAX Indonesia<br>
    📧 Lisa@jmaxindo.com</p>
</body>
</html>"""

    # Build plain text version
    text_body = f"""Dear {employee_name},

Berikut kami lampirkan payroll untuk periode {period_str}.

Untuk keamanan dokumen, silakan masukkan password sesuai tanggal lahir anda dengan format "ddmmyy".
Contoh: 19-02-1992 menjadi 190292.

Jika Anda memiliki pertanyaan atau membutuhkan informasi lebih lanjut, hubungi HRD kami di ebenezer@jmaxindo.com.

Salam hangat,
Tajunissa Legisa W
General Manager
PT JMAX Indonesia
📧 Lisa@jmaxindo.com"""

    return {"html": html_body, "text": text_body, "subject": subject}


@app.get("/api/payroll-campaigns/{campaign_id}")
async def get_payroll_campaign(campaign_id: int):
    """Get payroll campaign details by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                payroll_campaign_id,
                company,
                created_at,
                send_at,
                status,
                pdf_total,
                pdf_generated,
                pdf_status
            FROM contract_pkwt.payroll_campaign
            WHERE payroll_campaign_id = %s
        """, (campaign_id,))

        campaign = cursor.fetchone()
        cursor.close()
        conn.close()

        if not campaign:
            return JSONResponse(status_code=404, content={"error": "Campaign not found"})

        return {
            "payroll_campaign_id": campaign[0],
            "company": campaign[1],
            "created_at": campaign[2].isoformat() if campaign[2] else None,
            "send_at": campaign[3].isoformat() if campaign[3] else None,
            "status": campaign[4],
            "pdf_total": campaign[5],
            "pdf_generated": campaign[6],
            "pdf_status": campaign[7]
        }

    except Exception as e:
        import traceback
        print(f"Error getting payroll campaign: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/payroll-campaigns/{campaign_id}/payrolls")
async def get_payroll_list(campaign_id: int):
    """Get all payroll records with send status for a campaign"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                lp.list_payroll_id,
                lp.employee_id,
                lp.employee_name,
                lp.nik,
                lc.email,
                lp.thp,
                COALESCE(ps.send_status, FALSE) as send_status,
                ps.send_at
            FROM contract_pkwt.list_payroll lp
            LEFT JOIN contract_pkwt.payroll_status ps ON lp.list_payroll_id = ps.list_payroll_id
            LEFT JOIN contract_pkwt.list_contract lc ON lp.nik = lc.nik AND lc.contract_id > 137
            WHERE lp.payroll_campaign_id = %s
            ORDER BY lp.list_payroll_id
        """, (campaign_id,))

        payrolls = cursor.fetchall()
        cursor.close()
        conn.close()

        result = []
        for row in payrolls:
            result.append({
                "list_payroll_id": row[0],
                "employee_id": row[1],
                "employee_name": row[2],
                "nik": row[3],
                "email": row[4],
                "thp": float(row[5]) if row[5] else 0,
                "send_status": row[6],
                "send_at": row[7].isoformat() if row[7] else None
            })

        return result

    except Exception as e:
        import traceback
        print(f"Error getting payroll list: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


class PayrollEmailPreviewRequest(BaseModel):
    list_payroll_id: int

@app.post("/api/payroll-email-preview")
async def payroll_email_preview(request: PayrollEmailPreviewRequest):
    """Preview email for a payroll"""
    try:
        email_data = get_payroll_email_body(request.list_payroll_id)

        if not email_data:
            return JSONResponse(status_code=404, content={"error": "Payroll not found"})

        # Get employee email
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT lc.email
            FROM contract_pkwt.list_payroll lp
            LEFT JOIN contract_pkwt.list_contract lc ON lp.nik = lc.nik AND lc.contract_id > 137
            WHERE lp.list_payroll_id = %s
        """, (request.list_payroll_id,))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        recipient = result[0] if result and result[0] else "N/A"

        return {
            "email_subject": email_data["subject"],
            "email_body": email_data["html"],
            "recipient": recipient
        }

    except Exception as e:
        import traceback
        print(f"Error generating payroll email preview: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


class SendPayrollEmailRequest(BaseModel):
    list_payroll_id: int
    test_mode: bool = False

@app.post("/api/send-payroll-email")
async def send_payroll_email(request: SendPayrollEmailRequest):
    """Send payroll email with PDF attachment"""
    try:
        # Get employee email and payroll data
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT lc.email, lp.employee_name
            FROM contract_pkwt.list_payroll lp
            LEFT JOIN contract_pkwt.list_contract lc ON lp.nik = lc.nik AND lc.contract_id > 137
            WHERE lp.list_payroll_id = %s
        """, (request.list_payroll_id,))

        result = cursor.fetchone()

        if not result or not result[0]:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Employee email not found"})

        employee_email = result[0]
        employee_name = result[1]

        # HARDCODED TO felliayp@gmail.com FOR SAFETY - DO NOT REMOVE UNTIL CONFIRMED WORKING
        actual_recipient = employee_email
        employee_email = 'felliayp@gmail.com'
        print(f"HARDCODED SAFETY: Email for {actual_recipient} will be sent to felliayp@gmail.com")

        # Get email content
        email_data = get_payroll_email_body(request.list_payroll_id)

        if not email_data:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "Payroll not found"})

        # Get PDF from payroll_status
        cursor.execute("""
            SELECT pdf_data
            FROM contract_pkwt.payroll_status
            WHERE list_payroll_id = %s
        """, (request.list_payroll_id,))

        pdf_result = cursor.fetchone()

        if not pdf_result or not pdf_result[0]:
            cursor.close()
            conn.close()
            return JSONResponse(status_code=404, content={"error": "PDF not found for this payroll"})

        # Convert PDF bytea to base64 for Postmark
        pdf_data = bytes(pdf_result[0])
        pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')

        cursor.close()
        conn.close()

        # Prepare subject with test prefix if needed
        subject = email_data["subject"]
        if request.test_mode:
            subject = f"[TEST] {subject}"

        # Send email via Postmark with attachment
        postmark_response = requests.post(
            'https://api.postmarkapp.com/email',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Postmark-Server-Token': 'e3e7715d-2a61-4187-b79e-6c27733c9cda'
            },
            json={
                'From': 'hr@jmaxindo.id',
                'To': employee_email,
                'Subject': subject,
                'HtmlBody': email_data["html"],
                'TextBody': email_data["text"],
                'MessageStream': 'outbound',
                'Attachments': [
                    {
                        'Name': f'Payslip_{employee_name}.pdf',
                        'Content': pdf_base64,
                        'ContentType': 'application/pdf'
                    }
                ]
            }
        )

        if postmark_response.status_code not in [200, 201]:
            raise Exception(f"Postmark API error: {postmark_response.text}")

        # Update send_status to True (only if not test mode)
        if not request.test_mode:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE contract_pkwt.payroll_status
                SET send_status = TRUE, send_at = CURRENT_TIMESTAMP
                WHERE list_payroll_id = %s
            """, (request.list_payroll_id,))

            conn.commit()
            cursor.close()
            conn.close()

        return {
            "message": "Payroll email sent successfully!",
            "list_payroll_id": request.list_payroll_id,
            "test_mode": request.test_mode,
            "recipient": employee_email
        }

    except Exception as e:
        import traceback
        print(f"Error sending payroll email: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


class BulkSendPayrollEmailRequest(BaseModel):
    list_payroll_ids: List[int]
    test_mode: bool = False
    campaign_id: int = None

@app.post("/api/bulk-send-payroll-email")
async def bulk_send_payroll_email(request: BulkSendPayrollEmailRequest):
    """Send multiple payroll emails with test mode support"""
    try:
        success = []
        failed = []

        for list_payroll_id in request.list_payroll_ids:
            try:
                # Get employee email and payroll data
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT lc.email, lp.employee_name
                    FROM contract_pkwt.list_payroll lp
                    LEFT JOIN contract_pkwt.list_contract lc ON lp.nik = lc.nik AND lc.contract_id > 137
                    WHERE lp.list_payroll_id = %s
                """, (list_payroll_id,))

                result = cursor.fetchone()

                if not result or not result[0]:
                    cursor.close()
                    conn.close()
                    failed.append({
                        "list_payroll_id": list_payroll_id,
                        "error": "Employee email not found"
                    })
                    continue

                employee_email = result[0]
                employee_name = result[1]

                # HARDCODED TO felliayp@gmail.com FOR SAFETY - DO NOT REMOVE UNTIL CONFIRMED WORKING
                actual_recipient = employee_email
                employee_email = 'felliayp@gmail.com'
                print(f"HARDCODED SAFETY: Email for {actual_recipient} will be sent to felliayp@gmail.com")

                # Get email content
                email_data = get_payroll_email_body(list_payroll_id)

                if not email_data:
                    cursor.close()
                    conn.close()
                    failed.append({
                        "list_payroll_id": list_payroll_id,
                        "error": "Payroll not found"
                    })
                    continue

                # Get PDF from payroll_status
                cursor.execute("""
                    SELECT pdf_data
                    FROM contract_pkwt.payroll_status
                    WHERE list_payroll_id = %s
                """, (list_payroll_id,))

                pdf_result = cursor.fetchone()

                if not pdf_result or not pdf_result[0]:
                    cursor.close()
                    conn.close()
                    failed.append({
                        "list_payroll_id": list_payroll_id,
                        "error": "PDF not found"
                    })
                    continue

                # Convert PDF bytea to base64 for Postmark
                pdf_data = bytes(pdf_result[0])
                pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')

                cursor.close()
                conn.close()

                # Prepare subject with test prefix if needed
                subject = email_data["subject"]
                if request.test_mode:
                    subject = f"[TEST] {subject}"

                # Send email via Postmark with attachment
                postmark_response = requests.post(
                    'https://api.postmarkapp.com/email',
                    headers={
                        'Accept': 'application/json',
                        'Content-Type': 'application/json',
                        'X-Postmark-Server-Token': 'e3e7715d-2a61-4187-b79e-6c27733c9cda'
                    },
                    json={
                        'From': 'hr@jmaxindo.id',
                        'To': employee_email,
                        'Subject': subject,
                        'HtmlBody': email_data["html"],
                        'TextBody': email_data["text"],
                        'MessageStream': 'outbound',
                        'Attachments': [
                            {
                                'Name': f'Payslip_{employee_name}.pdf',
                                'Content': pdf_base64,
                                'ContentType': 'application/pdf'
                            }
                        ]
                    }
                )

                if postmark_response.status_code not in [200, 201]:
                    error_msg = f"Failed to send email: {postmark_response.text}"
                    failed.append({'list_payroll_id': list_payroll_id, 'error': error_msg})
                    continue

                # Update send_status to True (only if not test mode)
                if not request.test_mode:
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    cursor.execute("""
                        UPDATE contract_pkwt.payroll_status
                        SET send_status = TRUE, send_at = CURRENT_TIMESTAMP
                        WHERE list_payroll_id = %s
                    """, (list_payroll_id,))

                    conn.commit()
                    cursor.close()
                    conn.close()

                success.append(list_payroll_id)

            except Exception as e:
                failed.append({
                    "list_payroll_id": list_payroll_id,
                    "error": str(e)
                })

        return {
            "success": success,
            "failed": failed,
            "total": len(request.list_payroll_ids),
            "success_count": len(success),
            "failed_count": len(failed),
            "test_mode": request.test_mode
        }

    except Exception as e:
        import traceback
        print(f"Error in bulk send payroll email: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"error": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)