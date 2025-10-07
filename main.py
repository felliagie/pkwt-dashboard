from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, BackgroundTasks, Response as FastAPIResponse, Cookie
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

app = FastAPI()

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
                    return pd.to_datetime(date_val).date()
                else:
                    return pd.to_datetime(date_val).date()
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

@app.post("/api/send-reminders")
async def send_reminders(request: ReminderRequest):
    """Send reminder emails to selected contracts"""
    try:
        success_count = 0
        failed_count = 0

        conn = get_db_connection()
        cursor = conn.cursor()

        for uid, name in zip(request.uids, request.names):
            try:
                # Get contract_num_detail_md5 for this uid
                cursor.execute("""
                    SELECT contract_num_detail_md5
                    FROM authenticated_list_contract
                    WHERE uid = %s
                    LIMIT 1
                """, (uid,))

                result = cursor.fetchone()
                if not result or not result[0]:
                    failed_count += 1
                    continue

                contract_hash = result[0]
                login_url = f"https://pkwt.jmaxindo.id/{contract_hash}"

                reminder_text = f"""Kami mengingatkan bahwa proses penandatanganan kontrak kerja waktu tertentu (PKWT) dijadwalkan untuk dilakukan hari ini 7 Oktober 2025, melalui platform digital.

Mohon agar Saudara/i segera mengakses lampiran PKWT berikut untuk melakukan penandatanganan.
{login_url}

Batas waktu penandatanganan adalah hari ini pukul 20:00.

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
                        'To': 'felliayp@gmail.com',
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)