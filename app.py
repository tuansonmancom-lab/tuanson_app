import sqlite3
import pandas as pd
import streamlit as st
import re
import os
from datetime import datetime
from io import BytesIO

# --- HELPER FUNCTIONS ---
def generate_voucher_number(c, column_name, prefix):
    """
    Robustly finds the highest sequence number for a given prefix (e.g., APV, CV, CAV)
    across all relevant tables and columns, ensuring correct sequencing.
    """
    max_num = 0
    queries = [
        f"SELECT {column_name} FROM deliveries WHERE {column_name} LIKE '{prefix}-%'",
        f"SELECT voucher_no FROM journal_entries WHERE voucher_no LIKE '{prefix}-%'"
    ]
    for q in queries:
        try:
            c.execute(q)
            rows = c.fetchall()
            for row in rows:
                if row and row[0]:
                    val = str(row[0]).strip()
                    parts = val.split('-')
                    if len(parts) > 1:
                        try:
                            num = int(parts[-1])
                            if num > max_num:
                                max_num = num
                        except ValueError:
                            numbers = re.findall(r'\d+', val)
                            if numbers:
                                num = int(numbers[-1])
                                if num > max_num:
                                    max_num = num
        except Exception:
            continue
            
    next_num = max_num + 1
    return f"{prefix}-{next_num:05d}"

def get_latest_item_balance(cursor, item_name):
    """Calculates dynamic running balance for an item in inventory_ledger."""
    result = cursor.execute("""
        SELECT balance FROM inventory_ledger 
        WHERE item_description = ? 
        ORDER BY id DESC LIMIT 1
    """, (item_name,)).fetchone()
    return float(result[0]) if result else 0.0

def get_income_statement(conn, start_date, end_date):
    start_str = str(start_date)
    end_str = str(end_date)
    
    query = """
        SELECT 
            c.account_code,
            c.account_name,
            c.account_type,
            COALESCE(SUM(j.debit), 0.0) as total_debit,
            COALESCE(SUM(j.credit), 0.0) as total_credit,
            CASE 
                WHEN c.account_type = 'Revenue' THEN COALESCE(SUM(j.credit - j.debit), 0.0)
                ELSE COALESCE(SUM(j.debit - j.credit), 0.0)
            END as amount
        FROM chart_of_accounts c
        LEFT JOIN journal_entries j ON c.account_code = j.account_code 
            AND DATE(j.entry_date) BETWEEN ? AND ?
        WHERE c.account_type IN ('Revenue', 'Expense')
        GROUP BY c.account_code, c.account_name, c.account_type
        HAVING amount != 0
        ORDER BY c.account_code ASC
    """
    return pd.read_sql_query(query, conn, params=(start_str, end_str))

def get_balance_sheet(conn, as_of_date):
    as_of_str = str(as_of_date)
    
    query = """
        SELECT 
            c.account_code,
            c.account_name,
            c.account_type,
            COALESCE(SUM(j.debit), 0.0) as total_debit,
            COALESCE(SUM(j.credit), 0.0) as total_credit,
            CASE 
                WHEN c.account_type = 'Asset' THEN COALESCE(SUM(j.debit - j.credit), 0.0)
                ELSE COALESCE(SUM(j.credit - j.debit), 0.0)
            END as amount
        FROM chart_of_accounts c
        LEFT JOIN journal_entries j ON c.account_code = j.account_code 
            AND DATE(j.entry_date) <= ?
        WHERE c.account_type IN ('Asset', 'Liability', 'Equity')
        GROUP BY c.account_code, c.account_name, c.account_type
        HAVING amount != 0
        ORDER BY c.account_code ASC
    """
    return pd.read_sql_query(query, conn, params=(as_of_str,))

# --- REPORTLAB PDF GENERATION LIBRARIES ---
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping

    pdfmetrics.registerFont(TTFont('Roboto', 'Roboto-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Roboto-Bold', 'Roboto-Bold.ttf'))
    addMapping('Roboto', 0, 0, 'Roboto')
    addMapping('Roboto', 1, 0, 'Roboto-Bold')

    HAS_REPORTLAB = True
except Exception:
    HAS_REPORTLAB = False

# --- DATABASE SETUP ---
@st.cache_resource
def get_db_connection():
    try:
        db_url = st.secrets.get("TURSO_DATABASE_URL", os.getenv("TURSO_DATABASE_URL", "inventory.db"))
        auth_token = st.secrets.get("TURSO_AUTH_TOKEN", os.getenv("TURSO_AUTH_TOKEN", ""))
    except Exception:
        db_url = os.getenv("TURSO_DATABASE_URL", "inventory.db")
        auth_token = os.getenv("TURSO_AUTH_TOKEN", "")

    if str(db_url).startswith("libsql://") or str(db_url).startswith("https://") or str(db_url).startswith("wss://"):
        try:
            import libsql_experimental as turso_sqlite
            return turso_sqlite.connect(db_url, auth_token=auth_token)
        except ImportError:
            st.error("Please install `libsql-experimental` to connect to Turso. Run: pip install libsql-experimental")
            st.stop()
    else:
        return sqlite3.connect(db_url, check_same_thread=False)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute("PRAGMA journal_mode = WAL;")
        c.execute("PRAGMA synchronous = NORMAL;")
        c.execute("PRAGMA busy_timeout = 5000;")
    except Exception:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT UNIQUE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                activity_name TEXT,
                qty REAL DEFAULT 1.0,
                unit TEXT DEFAULT 'lot',
                contract_amount REAL DEFAULT 0.0,
                FOREIGN KEY(project_id) REFERENCES projects(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS materials (
                item_no TEXT PRIMARY KEY,
                description TEXT,
                unit TEXT,
                category TEXT DEFAULT 'Direct Materials')''')

    c.execute('''CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_name TEXT UNIQUE,
                location TEXT,
                contact_person TEXT,
                contact_number TEXT,
                tin_number TEXT,
                vat_type TEXT,
                terms_days INTEGER DEFAULT 0)''')

    c.execute('''CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                project_name TEXT,
                activity TEXT,
                item_no TEXT,
                description TEXT,
                category TEXT DEFAULT 'Direct Materials',
                qty REAL,
                unit TEXT,
                price REAL,
                amount REAL,
                email_address TEXT,
                status TEXT,
                supplier TEXT,
                pono TEXT,
                approved_by TEXT,
                approved_timestamp DATETIME,
                payment_status TEXT DEFAULT 'Unpaid',
                received_status TEXT DEFAULT 'Pending',
                received_timestamp DATETIME,
                requester_name TEXT,
                rejection_reason TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pono TEXT,
                supplier TEXT,
                project_name TEXT,
                dr_number TEXT,
                total_amount REAL,
                received_date DATETIME,
                payment_status TEXT DEFAULT 'Unpaid',
                receipt_image BLOB,
                file_name TEXT,
                apv_number TEXT,
                apv_date DATETIME,
                cv_number TEXT,
                cv_date DATETIME,
                payment_method TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS signatories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                role TEXT,
                signature_path TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                role1 TEXT, role2 TEXT, role3 TEXT, role4 TEXT, role5 TEXT, role6 TEXT,
                status TEXT DEFAULT 'Active',
                can_add_act TEXT DEFAULT 'No',
                can_add_item TEXT DEFAULT 'No')''')

    c.execute('''CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date DATETIME,
                voucher_no TEXT,
                account_code TEXT,
                account_name TEXT,
                debit REAL DEFAULT 0.0,
                credit REAL DEFAULT 0.0,
                ref_no TEXT,
                description TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS chart_of_accounts (
                account_code TEXT PRIMARY KEY,
                account_name TEXT NOT NULL,
                account_type TEXT NOT NULL,
                status TEXT DEFAULT 'Active')''')

    c.execute('''CREATE TABLE IF NOT EXISTS inventory_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ref_no TEXT NOT NULL,
                item_description TEXT NOT NULL,
                qty_in REAL DEFAULT 0.0,
                qty_out REAL DEFAULT 0.0,
                balance REAL DEFAULT 0.0,
                location TEXT,
                remarks TEXT,
                status TEXT DEFAULT 'Completed')''')

    for col in ["location", "contact_person", "contact_number", "tin_number", "vat_type"]:
        try:
            c.execute(f"ALTER TABLE suppliers ADD COLUMN {col} TEXT")
        except Exception:
            pass

    for col_sql in [
        ("materials", "category", "TEXT DEFAULT 'Direct Materials'"),
        ("requests", "category", "TEXT DEFAULT 'Direct Materials'"),
        ("requests", "rejection_reason", "TEXT"),
        ("suppliers", "terms_days", "INTEGER DEFAULT 0"),
        ("requests", "payment_status", "TEXT DEFAULT 'Unpaid'"),
        ("requests", "received_status", "TEXT DEFAULT 'Pending'"),
        ("requests", "received_timestamp", "DATETIME"),
        ("requests", "requester_name", "TEXT"),
        ("activities", "contract_amount", "REAL DEFAULT 0.0"),
        ("activities", "qty", "REAL DEFAULT 1.0"),
        ("activities", "unit", "TEXT DEFAULT 'lot'"),
        ("deliveries", "receipt_image", "BLOB"),
        ("deliveries", "file_name", "TEXT"),
        ("deliveries", "apv_number", "TEXT"),
        ("deliveries", "apv_date", "DATETIME"),
        ("deliveries", "cv_number", "TEXT"),
        ("deliveries", "cv_date", "DATETIME"),
        ("deliveries", "payment_method", "TEXT"),
        ("users", "can_add_act", "TEXT DEFAULT 'No'"),
        ("users", "can_add_item", "TEXT DEFAULT 'No'"),
        ("users", "role6", "TEXT DEFAULT ''"),
        ("inventory_ledger", "status", "TEXT DEFAULT 'Completed'")
    ]:
        try:
            c.execute(f"ALTER TABLE {col_sql[0]} ADD COLUMN {col_sql[1]} {col_sql[2]}")
        except Exception:
            pass

    c.execute("SELECT COUNT(*) FROM projects")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO projects (project_name) VALUES (?)", 
                    [('Punta',), ('Suba',), ('Basak',), ('Dumanjug',), ('MOTORPOOL',)])
        
        c.executemany("INSERT INTO activities (project_id, activity_name, qty, unit, contract_amount) VALUES (?, ?, ?, ?, ?)", [
            (1, 'painting', 1.0, 'lot', 0.0), 
            (2, 'FORM WORKS', 1.0, 'lot', 0.0), 
            (3, 'LINTEL BEAM', 1.0, 'lot', 0.0), 
            (3, 'CHB LAYING', 1.0, 'lot', 0.0), 
            (3, 'COLUMN CORRECTION', 1.0, 'lot', 0.0), 
            (4, 'PCCP', 1.0, 'lot', 0.0), 
            (5, 'RENEWAL REGISTRATION', 1.0, 'lot', 0.0)
        ])
        
        c.executemany("INSERT INTO materials (item_no, description, unit, category) VALUES (?, ?, ?, ?)", [
            ('00001', 'PORTLAND CEMENT', 'BAGS', 'Direct Materials'),
            ('00002', 'DEF. BARS 12MM X 9M', 'LENGTH', 'Direct Materials'),
            ('00003', 'DEF. BARS 10MM X 6M', 'LENGTH', 'Direct Materials'),
            ('00004', 'STEEL MATTING', 'SHEET', 'Direct Materials'),
            ('00005', 'MCAB - JAR - 8507', 'LOT', 'Equipment & Rental'),
            ('00006', 'SELFLOADER - MEJ - 598', 'LOT', 'Equipment & Rental')
        ])

        c.executemany("""INSERT INTO suppliers 
            (supplier_name, location, contact_person, contact_number, tin_number, vat_type, terms_days) 
            VALUES (?, ?, ?, ?, ?, ?, ?)""", [
            ('NOEL A. FARIOLEN', 'Cebu City', 'Noel Fariolen', '0917-000-0001', '000-000-000-000', 'VAT Registered', 0),
            ('CENTRAL LUMBER CORP.', 'Mandaue City', 'Sales Department', '0917-000-0002', '123-456-789-000', 'VAT Registered', 30),
            ('FILMON HARDWARE, INC.', 'Cebu City', 'Customer Desk', '0917-000-0003', '987-654-321-000', 'VAT Registered', 15), 
            ('DANILO LUMBER SUPPLY', 'Consolacion', 'Danilo', '0917-000-0004', '111-222-333-000', 'Non-VAT', 0),
            ('CEBU DIAMOND INDUSTRIAL', 'Mandaue City', 'Operations', '0917-000-0005', '444-555-666-000', 'VAT Registered', 30),
            ('GDSM MARKETING', 'Lapu-Lapu City', 'Manager', '0917-000-0006', '777-888-999-000', 'Non-VAT', 0)
        ])

    c.execute("SELECT COUNT(*) FROM signatories")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO signatories (name, role, signature_path) VALUES (?, ?, ?)", [
            ('BRAZEL M. DELA CERNA', 'Preparer', ''),
            ('LEIZEL A. CABUNILAS', 'Approver', 'Leizel_signature.png')
        ])

    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.executemany("""INSERT INTO users 
            (username, password, role1, role2, role3, role4, role5, role6, status) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", [
            ('Vergel', '1234', 'Purchaser', '', '', '', '', '', 'Active'),
            ('Glance', '5641', 'Requisitor', 'Purchaser', '', 'Office Manager', 'Admin View All', '', 'Active'),
            ('Brazel', '12181', 'Requisitor', 'Purchaser', 'Approver', 'Office Manager', 'Admin View All', 'Accounting', 'Active'),
            ('Leizel', '5874', '', '', 'Approver', 'Office Manager', '', '', 'Active'),
            ('AccountingUser', '1234', 'Accounting', '', '', '', '', '', 'Active'),
            ('Admin', 'admin', 'Admin View All', '', '', '', '', '', 'Active') 
        ])

    c.execute("SELECT COUNT(*) FROM chart_of_accounts")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO chart_of_accounts (account_code, account_name, account_type) VALUES (?, ?, ?)", [
            ('10100', 'Cash on Hand', 'Asset'),
            ('10310', 'Cash in Bank MBTC', 'Asset'),
            ('10320', 'Cash in Bank CHINA', 'Asset'),
            ('10330', 'Cash in Bank BDO', 'Asset'),
            ('10340', 'Cash in Bank Landbank', 'Asset'),
            ('13100', 'Construction Materials', 'Asset'),
            ('20100', 'Accounts Payable-Trade', 'Liability'),
            ('60200', 'Direct Cost Materials', 'Expense')
        ])

    conn.commit()

init_db()

# --- PDF GENERATOR FUNCTIONS ---
def create_po_pdf(pono, date_str, supplier, project, po_items):
    prep_name = "VERGEL W. MANCIA"
    prep_sig_path = "Vergel_signature.png"
    appr_name = "LEIZEL A. CABUNILAS"
    appr_sig_path = "Leizel_signature.png"

    try:
        pdf_conn = get_db_connection()
        cursor = pdf_conn.cursor()
        cursor.execute("SELECT name, role, signature_path FROM signatories")
        sigs = cursor.fetchall()
        for name, role, sig_path in sigs:
            if role and role.strip().lower() == "preparer":
                if name: prep_name = name
                if sig_path: prep_sig_path = sig_path.strip()
            elif role and role.strip().lower() == "approver":
                if name: appr_name = name
                if sig_path: appr_sig_path = sig_path.strip()
    except Exception:
        pass

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()
    
    company_style = ParagraphStyle('CompanyRed', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, leading=20, textColor=colors.HexColor("#CC0000"))
    po_title_style = ParagraphStyle('POTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=16, alignment=1, textColor=colors.black)
    po_no_style = ParagraphStyle('PONumber', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=16, alignment=2, textColor=colors.black)
    meta_label_style = ParagraphStyle('MetaLabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.black)
    meta_val_style = ParagraphStyle('MetaVal', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, textColor=colors.black)
    hdr_style = ParagraphStyle('HdrStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=1, textColor=colors.black)
    cell_style = ParagraphStyle('CellBody', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10)
    center_cell_style = ParagraphStyle('CenterCell', parent=cell_style, alignment=1)
    right_cell_style = ParagraphStyle('RightCell', parent=cell_style, alignment=2)

    company_text = Paragraph(
        "**TUANSON CONSTRUCTION** 162 P. Labuca St., Cansojong, Talisay City, Cebu Tel: 032 273-1187
