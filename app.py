import sqlite3
import pandas as pd
import streamlit as st
import re
import os
from datetime import datetime
from io import BytesIO

def format_cheque_date(date_str):
    """Formats '2026-09-18' into spaced digits: '0 9   1 8   2 0 2 6' for check date boxes."""
    if not date_str or date_str == "[ PENDING ]":
        return ""
    try:
        dt = datetime.strptime(date_str.split()[0], "%Y-%m-%d")
        m, d, y = f"{dt.month:02d}", f"{dt.day:02d}", f"{dt.year:04d}"
        return f"{m[0]} {m[1]}   {d[0]} {d[1]}   {y[0]} {y[1]} {y[2]} {y[3]}"
    except Exception:
        return date_str

def cheque_amount_to_words(amount):
    """Formats amount into cheque words without 'PHILIPPINE PESO' prefix."""
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return "ZERO PESOS ONLY"
    
    pesos = int(amount)
    cents = int(round((amount - pesos) * 100))
    
    units = ["", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", 
             "TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN", 
             "SEVENTEEN", "EIGHTEEN", "NINETEEN"]
    tens = ["", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY"]

    def _convert(n):
        words = []
        if n >= 100:
            words.append(units[n // 100] + " HUNDRED")
            n %= 100
        if 1 <= n <= 19:
            words.append(units[n])
        elif n >= 20:
            words.append(tens[n // 10] + (" " + units[n % 10] if (n % 10) != 0 else ""))
        return " ".join(words)

    if pesos == 0:
        words_str = "ZERO"
    else:
        parts = []
        if pesos >= 1_000_000:
            parts.append(_convert(pesos // 1_000_000) + " MILLION")
            pesos %= 1_000_000
        if pesos >= 1_000:
            parts.append(_convert(pesos // 1_000) + " THOUSAND")
            pesos %= 1_000
        if pesos > 0:
            parts.append(_convert(pesos))
        words_str = " ".join(parts)

    if cents > 0:
        return f"*** {words_str} & {cents:02d}/100 PESOS ONLY ***"
    return f"*** {words_str} PESOS ONLY ***"

import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Roboto fonts for Philippine Peso symbol support
def register_roboto_font():
    try:
        # Update paths if your .ttf files are in a subfolder (e.g., 'fonts/Roboto-Regular.ttf')
        pdfmetrics.registerFont(TTFont('Roboto', 'Roboto-Regular.ttf'))
        pdfmetrics.registerFont(TTFont('Roboto-Bold', 'Roboto-Bold.ttf'))
        return True
    except Exception as e:
        print(f"Font registration warning: {e}")
        return False

# Run registration on app startup
ROBOTO_READY = register_roboto_font()


def amount_to_words(amount):
    """Converts numeric amounts to formal Philippine Currency words."""
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return "ZERO PESOS ONLY"
    
    pesos = int(amount)
    cents = int(round((amount - pesos) * 100))
    
    units = ["", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", 
             "TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN", 
             "SEVENTEEN", "EIGHTEEN", "NINETEEN"]
    tens = ["", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY"]

    def _convert_below_thousand(n):
        words = []
        if n >= 100:
            words.append(units[n // 100] + " HUNDRED")
            n %= 100
        if 1 <= n <= 19:
            words.append(units[n])
        elif n >= 20:
            words.append(tens[n // 10] + (" " + units[n % 10] if (n % 10) != 0 else ""))
        return " ".join(words)

    if pesos == 0:
        words_str = "ZERO"
    else:
        parts = []
        if pesos >= 1_000_000:
            parts.append(_convert_below_thousand(pesos // 1_000_000) + " MILLION")
            pesos %= 1_000_000
        if pesos >= 1_000:
            parts.append(_convert_below_thousand(pesos // 1_000) + " THOUSAND")
            pesos %= 1_000
        if pesos > 0:
            parts.append(_convert_below_thousand(pesos))
        words_str = " ".join(parts)

    cents_str = f"{cents:02d}/100"
    return f"PHILIPPINE PESO {words_str} AND {cents_str} ONLY"

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
                            import re
                            numbers = re.findall(r'\d+', val)
                            if numbers:
                                num = int(numbers[-1])
                                if num > max_num:
                                    max_num = num
        except Exception:
            continue
            
    next_num = max_num + 1
    return f"{prefix}-{next_num:05d}"
#=================================================================    

def get_income_statement(conn, start_date, end_date):
    # Convert date objects to text strings for Turso parameter binding
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

    # --- REGISTER THE ROBOTO FONTS ---
    # (Ensure Roboto-Regular.ttf and Roboto-Bold.ttf are in the same folder as this script)
    pdfmetrics.registerFont(TTFont('Roboto', 'Roboto-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Roboto-Bold', 'Roboto-Bold.ttf'))

    # Tell ReportLab that Roboto-Bold is the bold version of Roboto
    addMapping('Roboto', 0, 0, 'Roboto')       # Normal
    addMapping('Roboto', 1, 0, 'Roboto-Bold')  # Bold

    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False



# --- DATABASE SETUP (Turso / SQLite Integrated) ---
@st.cache_resource
def get_db_connection():
    """Dynamically connects to Turso if configured, otherwise falls back to local SQLite."""
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
        pass # Turso/libsql may safely ignore some PRAGMA statements

    # 1. Projects Master Table
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT UNIQUE
              )''')
    
    # 2. Activities Master Table
    c.execute('''CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                activity_name TEXT,
                qty REAL DEFAULT 1.0,
                unit TEXT DEFAULT 'lot',
                contract_amount REAL DEFAULT 0.0,
                FOREIGN KEY(project_id) REFERENCES projects(id))'''
              )

    # 3. Materials Master Table
    c.execute('''CREATE TABLE IF NOT EXISTS materials (
                item_no TEXT PRIMARY KEY,
                description TEXT,
                unit TEXT,
                category TEXT DEFAULT 'Direct Materials')''')

    # 4. Suppliers Master Table
    c.execute('''CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_name TEXT UNIQUE,
                location TEXT,
                contact_person TEXT,
                contact_number TEXT,
                tin_number TEXT,
                vat_type TEXT,
                terms_days INTEGER DEFAULT 0)''')

    # 5. Transaction Requests Table
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
                requester_name TEXT)''')

    # 6. Deliveries / Receiving Master Table
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

    # 7. Signatories Master Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS signatories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            role TEXT,
            signature_path TEXT
        )
    ''')

    # 8. Users Master Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role1 TEXT,
            role2 TEXT,
            role3 TEXT,
            role4 TEXT,
            role5 TEXT,
            role6 TEXT,
            status TEXT DEFAULT 'Active',
            can_add_act TEXT DEFAULT 'No',
            can_add_item TEXT DEFAULT 'No'
        )
    ''')

    # 9. General Ledger / Journal Entries Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date DATETIME,
            voucher_no TEXT,
            account_code TEXT,
            account_name TEXT,
            debit REAL DEFAULT 0.0,
            credit REAL DEFAULT 0.0,
            ref_no TEXT,
            description TEXT
        )
    ''')

    # 10. Chart of Accounts Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chart_of_accounts (
            account_code TEXT PRIMARY KEY,
            account_name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            status TEXT DEFAULT 'Active'
        )
    ''')

    # 11. Inventory Ledger Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS inventory_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            ref_no TEXT NOT NULL,
            item_description TEXT NOT NULL,
            qty_in REAL DEFAULT 0.0,
            qty_out REAL DEFAULT 0.0,
            balance REAL DEFAULT 0.0,
            location TEXT,
            remarks TEXT,
            status TEXT DEFAULT 'Completed'
        )
    ''')

    # --- AUTO-MIGRATIONS FOR EXISTING DATABASES ---
    for col in ["location", "contact_person", "contact_number", "tin_number", "vat_type"]:
        try:
            c.execute(f"ALTER TABLE suppliers ADD COLUMN {col} TEXT")
        except Exception:
            pass

    for col_sql in [
        ("materials", "category", "TEXT DEFAULT 'Direct Materials'"),
        ("requests", "category", "TEXT DEFAULT 'Direct Materials'"),
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

    # --- SEED INITIAL DATA ---
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

# --- HELPER FUNCTIONS ---
def get_latest_item_balance(cursor, item_name):
    """Calculates dynamic running balance for an item in inventory_ledger."""
    result = cursor.execute("""
        SELECT balance FROM inventory_ledger 
        WHERE item_description = ? 
        ORDER BY id DESC LIMIT 1
    """, (item_name,)).fetchone()
    return float(result[0]) if result else 0.0

def generate_voucher_number(cursor, column_name, prefix):
    query = f"SELECT {column_name} FROM deliveries WHERE {column_name} IS NOT NULL AND {column_name} LIKE '{prefix}-%' ORDER BY id DESC LIMIT 1"
    last_voucher = cursor.execute(query).fetchone()
    
    if last_voucher and last_voucher[0]:
        match = re.search(r'(\d+)$', last_voucher[0])
        if match:
            number_str = match.group(1)
            next_number = str(int(number_str) + 1).zfill(len(number_str))
            return f"{prefix}-{next_number}"
    return f"{prefix}-00001"

# --- PDF GENERATOR FUNCTION ---
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
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=36, 
        leftMargin=36, 
        topMargin=36, 
        bottomMargin=36
    )
    elements = []
    styles = getSampleStyleSheet()
    
    company_style = ParagraphStyle(
        'CompanyRed',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=20,
        textColor=colors.HexColor("#CC0000")
    )
    
    po_title_style = ParagraphStyle(
        'POTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=16,
        alignment=1,
        textColor=colors.black
    )
    
    po_no_style = ParagraphStyle(
        'PONumber',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=16,
        alignment=2,
        textColor=colors.black
    )
    
    meta_label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.black
    )
    
    meta_val_style = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.black
    )

    hdr_style = ParagraphStyle(
        'HdrStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=1,
        textColor=colors.black
    )
    
    cell_style = ParagraphStyle(
        'CellBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10
    )
    
    center_cell_style = ParagraphStyle(
        'CenterCell',
        parent=cell_style,
        alignment=1
    )
    
    right_cell_style = ParagraphStyle(
        'RightCell',
        parent=cell_style,
        alignment=2
    )

    company_text = Paragraph(
        "<b>TUANSON CONSTRUCTION</b> <font size=7 color='black'>162 P. Labuca St., Cansojong, Talisay City, Cebu Tel: 032 273-1187</font><br/>"
        "<font size=7 color='black'>web: www.tuansoncons.com, email: ric_tuanson@yahoo.com.ph</font>",
        company_style
    )

    logo_filename = "logo.png"
    if os.path.exists(logo_filename):
        logo_img = Image(logo_filename, width=40, height=40)
        hdr_table = Table([[logo_img, company_text]], colWidths=[45, 495])
        hdr_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
        elements.append(hdr_table)
    else:
        elements.append(company_text)

    elements.append(Spacer(1, 10))

    title_table = Table([
        [Paragraph("<b>PURCHASE ORDER</b>", po_title_style), Paragraph(f"P.O. NO. &nbsp;&nbsp;&nbsp;&nbsp; <b>{pono}</b>", po_no_style)]
    ], colWidths=[340, 200])
    title_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    elements.append(title_table)

    elements.append(Spacer(1, 8))

    meta_data = [
        [Paragraph("PAYEE:", meta_label_style), Paragraph(str(supplier), meta_val_style), Paragraph("DATE:", meta_label_style), Paragraph(str(date_str), meta_val_style)],
        [Paragraph("PROJECT NAME:", meta_label_style), Paragraph(str(project), meta_val_style), "", ""]
    ]
    meta_table = Table(meta_data, colWidths=[90, 310, 50, 90])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('SPAN', (1, 1), (3, 1)), 
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(meta_table)

    elements.append(Spacer(1, 8))

    table_data = [[
        Paragraph("NO.", hdr_style),
        Paragraph("QTY", hdr_style),
        Paragraph("UNIT", hdr_style),
        Paragraph("ACTIVITY", hdr_style),
        Paragraph("PARTICULAR'S", hdr_style),
        Paragraph("UNIT PRICE", hdr_style),
        Paragraph("AMOUNT", hdr_style)
    ]]
    
    grand_total = 0.0
    
    for idx, item in enumerate(po_items, 1):
        qty, unit, desc, act, price, amount = item
        grand_total += amount
        table_data.append([
            Paragraph(str(idx), center_cell_style),
            Paragraph(f"{qty:,.2f}", center_cell_style),
            Paragraph(str(unit), center_cell_style),
            Paragraph(str(act), cell_style),
            Paragraph(str(desc), cell_style),
            Paragraph(f"{price:,.2f}", right_cell_style),
            Paragraph(f"{amount:,.2f}", right_cell_style)
        ])
        
    table_data.append([
        "", "", "", 
        Paragraph("<b>*************NF*************</b>", center_cell_style),
        Paragraph("<b>*************NF*************</b>", center_cell_style),
        "", ""
    ])

    for _ in range(3):
        table_data.append(["", "", "", "", "", "", ""])

    col_widths = [25, 45, 45, 120, 165, 70, 70]
    
    po_table = Table(table_data, colWidths=col_widths)
    po_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black), 
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(po_table)

    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    prep_element = Paragraph(f"<b>{prep_name}</b><br/>Prepared by:", center_cell_style)
    if prep_sig_path and os.path.exists(prep_sig_path):
        prep_img = Image(prep_sig_path, width=90, height=30)
        prep_element = [prep_img, Paragraph(f"<b>{prep_name}</b><br/>Prepared by:", center_cell_style)]
        
    appr_element = Paragraph(f"<b>{appr_name}</b><br/>Approved by:", center_cell_style)
    if appr_sig_path and os.path.exists(appr_sig_path):
        appr_img = Image(appr_sig_path, width=90, height=30)
        appr_element = [appr_img, Paragraph(f"<b>{appr_name}</b><br/>Approved by:", center_cell_style)]

    footer_data = [
        [
            Paragraph("<b>NOTES:</b>", cell_style),
            "",
            Paragraph("<b>GRAND TOTAL:</b>", right_cell_style),
            Paragraph(f"<b>P {grand_total:,.2f}</b>", right_cell_style)
        ],
        [
            "",
            "",
            prep_element,
            appr_element
        ],
        [
            "",
            "",
            "",
            Paragraph(f"<font size=6 color='gray'>Date Print: {current_time_str}</font>", right_cell_style)
        ]
    ]

    footer_table = Table(footer_data, colWidths=[200, 40, 150, 150])
    footer_table.setStyle(TableStyle([
        ('BOX', (0, 0), (0, 1), 0.5, colors.black), 
        ('GRID', (2, 0), (3, 0), 0.5, colors.black), 
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 1), (-1, 1), 8),
    ]))

    elements.append(footer_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# --- APV PDF GENERATOR FUNCTION ---
def create_apv_pdf(apv_no, apv_date, dr_number, po_number, supplier, project, total_amount, conn=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    
    # Styles using Roboto
    title_style = ParagraphStyle('Title', fontName='Roboto-Bold', fontSize=16, leading=18, alignment=1, textColor=colors.HexColor("#CC0000"))
    subtitle_style = ParagraphStyle('Subtitle', fontName='Roboto', fontSize=8, leading=10, alignment=1)
    normal_style = ParagraphStyle('Normal', fontName='Roboto', fontSize=9, leading=12)
    bold_style = ParagraphStyle('Bold', fontName='Roboto-Bold', fontSize=9, leading=12)
    
    # Custom styles for the accounting table
    header_style = ParagraphStyle('HeaderStyle', fontName='Roboto-Bold', fontSize=9, textColor=colors.white)
    right_align_normal = ParagraphStyle('RightNormal', fontName='Roboto', fontSize=9, alignment=2)
    right_align_bold = ParagraphStyle('RightBold', fontName='Roboto-Bold', fontSize=9, alignment=2)
    
    # Header
    elements.append(Paragraph("<b>TUANSON CONSTRUCTION</b>", title_style))
    elements.append(Paragraph("Accounts Payable Voucher (APV)", subtitle_style))
    elements.append(Spacer(1, 15))
    
    # Meta Data Table
    meta_data = [
        [Paragraph("<b>APV NO:</b>", bold_style), Paragraph(str(apv_no), normal_style), Paragraph("<b>APV DATE:</b>", bold_style), Paragraph(str(apv_date), normal_style)],
        [Paragraph("<b>SUPPLIER:</b>", bold_style), Paragraph(str(supplier), normal_style), Paragraph("<b>PROJECT:</b>", bold_style), Paragraph(str(project), normal_style)],
        [Paragraph("<b>PO NUMBER:</b>", bold_style), Paragraph(str(po_number), normal_style), Paragraph("<b>DR NUMBER:</b>", bold_style), Paragraph(str(dr_number), normal_style)]
    ]
    meta_table = Table(meta_data, colWidths=[90, 180, 90, 180])
    meta_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    elements.append(meta_table)
    elements.append(Spacer(1, 15))
    
    # Accounting Entries Title
    elements.append(Paragraph("<b>Accounting Entries (General Ledger Distribution)</b>", bold_style))
    elements.append(Spacer(1, 8))
    
    # Double-Entry Table Data
    table_data = [
        [Paragraph("<b>Account Code & Name</b>", header_style), 
         Paragraph("<b>Description</b>", header_style), 
         Paragraph("<b>Debit ₱</b>", header_style), 
         Paragraph("<b>Credit ₱</b>", header_style)],
         
        # Debit Row (Direct Cost Materials)
        [Paragraph("<b>60200</b> - Direct Cost Materials", normal_style), 
         Paragraph(f"APV setup for DR #{dr_number} ({supplier})", normal_style), 
         Paragraph(f"₱{total_amount:,.2f}", right_align_normal), 
         Paragraph("-", right_align_normal)],
         
        # Credit Row (Accounts Payable-Trade)
        [Paragraph("<b>20100</b> - Accounts Payable-Trade", normal_style), 
         Paragraph(f"APV liability accrued for DR #{dr_number}", normal_style), 
         Paragraph("-", right_align_normal), 
         Paragraph(f"₱{total_amount:,.2f}", right_align_normal)],
         
        # Total Row
        [Paragraph("<b>TOTAL</b>", bold_style), 
         "", 
         Paragraph(f"<b>₱{total_amount:,.2f}</b>", right_align_bold), 
         Paragraph(f"<b>₱{total_amount:,.2f}</b>", right_align_bold)]
    ]
    
    apv_table = Table(table_data, colWidths=[160, 200, 90, 90])
    apv_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c4356')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,-1), (-1,-1), colors.whitesmoke)
    ]))
    
    elements.append(apv_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# --- CV PDF GENERATOR FUNCTION ---
def create_cv_pdf(cv_no, cv_date, apv_no, supplier, pay_method, total_amt, conn=None):
    import io
    from datetime import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    font_regular = "Roboto" if ROBOTO_READY else "Helvetica"
    font_bold = "Roboto-Bold" if ROBOTO_READY else "Helvetica-Bold"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, leading=18, alignment=1, fontName=font_bold)
    company_style = ParagraphStyle('CompanyHeader', parent=styles['Normal'], fontSize=12, leading=14, alignment=1, fontName=font_bold)
    sub_style = ParagraphStyle('SubHeader', parent=styles['Normal'], fontSize=8, leading=10, alignment=1, fontName=font_regular)
    
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, leading=10, fontName=font_regular)
    cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontSize=8, leading=10, fontName=font_bold)
    cell_right = ParagraphStyle('CellRight', parent=styles['Normal'], fontSize=8, leading=10, alignment=2, fontName=font_regular)
    cell_right_bold = ParagraphStyle('CellRightBold', parent=styles['Normal'], fontSize=8, leading=10, alignment=2, fontName=font_bold)
    cell_center_bold = ParagraphStyle('CellCenterBold', parent=styles['Normal'], fontSize=8, leading=10, alignment=1, fontName=font_bold)

    elements = []

    # 1. Company Header
    elements.append(Paragraph("Tuanson Construction", company_style))
    elements.append(Paragraph("162 P. Labuca St., Cansojong, Talisay City, Cebu", sub_style))
    elements.append(Paragraph("Tel: - Fax: -", sub_style))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Payment Voucher", title_style))
    elements.append(Spacer(1, 10))

    # Defaults
    po_no = ""
    project_name = "General Site Works"
    bank_code = "10330"
    bank_name = "Cash in Bank BDO"
    cheque_no = "---"
    cheque_date_val = "[ PENDING ]"
    
    # Query updated cheque info directly from deliveries table
    if conn and cv_no:
        try:
            cur = conn.cursor()
            row = cur.execute("""
                SELECT pono, project_name, cheque_no, cheque_date 
                FROM deliveries 
                WHERE cv_number = ?
            """, (cv_no,)).fetchone()
            
            if row:
                po_no = row[0] or ""
                project_name = row[1] or "General Site Works"
                if row[2] and str(row[2]).strip():
                    cheque_no = str(row[2]).strip()
                if row[3] and str(row[3]).strip():
                    cheque_date_val = str(row[3]).strip()
        except Exception:
            pass

    date_formatted = cv_date.split()[0] if cv_date else datetime.now().strftime('%Y-%m-%d')

    # 2. Payee & Voucher Metadata (Uses updated cheque_date_val)
    payee_text = f"<b>{supplier}</b><br/>Cebu, Philippines"
    voucher_meta = f"<b>NO.:</b> {cv_no}<br/><b>DATE:</b> {date_formatted}<br/><b>CHEQUE NO.:</b> {cheque_no} / {cheque_date_val}"

    info_table = Table([
        [Paragraph(payee_text, cell_style), Paragraph(voucher_meta, cell_style)]
    ], colWidths=[360, 180])
    info_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 8))

    # 3. Account Particulars
    desc_str = f"Payment for materials / services for {project_name}" + (f" (PO#{po_no})" if po_no else "")
    acct_data = [
        [Paragraph("<b>A/C CODE</b>", cell_bold), Paragraph("<b>A/C NAME</b>", cell_bold), Paragraph("<b>DESCRIPTION</b>", cell_bold), Paragraph("<b>AMOUNT</b>", cell_right_bold)],
        [Paragraph("20100", cell_style), Paragraph(supplier, cell_style), Paragraph(desc_str, cell_style), Paragraph(f"₱{total_amt:,.2f}", cell_right)]
    ]
    acct_table = Table(acct_data, colWidths=[70, 150, 220, 100])
    acct_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ('LINEBELOW', (0,0), (-1,0), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(acct_table)
    elements.append(Spacer(1, 8))

    # 4. Journals Table
    elements.append(Paragraph("<b>Journals:</b>", cell_bold))
    elements.append(Spacer(1, 2))
    
    journal_data = [
        [Paragraph("<b>Doc No.</b>", cell_bold), Paragraph("<b>Date</b>", cell_bold), Paragraph("<b>Account #</b>", cell_bold), Paragraph("<b>Account Name</b>", cell_bold), Paragraph("<b>Debit</b>", cell_right_bold), Paragraph("<b>Credit</b>", cell_right_bold)],
        [Paragraph(cv_no, cell_style), Paragraph(date_formatted, cell_style), Paragraph("20100", cell_style), Paragraph(f"Accounts Payable - {supplier}", cell_style), Paragraph(f"{total_amt:,.2f}", cell_right), Paragraph("", cell_right)],
        [Paragraph(cv_no, cell_style), Paragraph(date_formatted, cell_style), Paragraph(bank_code, cell_style), Paragraph(f"{bank_code}: {bank_name}", cell_style), Paragraph("", cell_right), Paragraph(f"{total_amt:,.2f}", cell_right)],
        [Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("<b>TOTAL</b>", cell_right_bold), Paragraph(f"<b>{total_amt:,.2f}</b>", cell_right_bold), Paragraph(f"<b>{total_amt:,.2f}</b>", cell_right_bold)]
    ]
    journal_table = Table(journal_data, colWidths=[65, 60, 60, 185, 85, 85])
    journal_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ('LINEBELOW', (0,0), (-1,0), 0.5, colors.black),
        ('LINEABOVE', (0,-1), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(journal_table)
    elements.append(Spacer(1, 8))

    # 5. Payment Details Table
    elements.append(Paragraph("<b>PAYMENT DETAILS</b>", cell_bold))
    elements.append(Spacer(1, 2))
    
    pay_det_data = [
        [Paragraph("<b>Type</b>", cell_bold), Paragraph("<b>Doc. No.</b>", cell_bold), Paragraph("<b>Doc. Date</b>", cell_bold), Paragraph("<b>Description</b>", cell_bold), Paragraph("<b>Orig. Amount</b>", cell_right_bold), Paragraph("<b>Paid Amount</b>", cell_right_bold)],
        [Paragraph("BIL", cell_style), Paragraph(f"PO#{po_no}" if po_no else f"APV#{apv_no}", cell_style), Paragraph(date_formatted, cell_style), Paragraph(f"PAYABLE FOR MATERIALS FOR \"{project_name.upper()}\"", cell_style), Paragraph(f"{total_amt:,.2f}", cell_right), Paragraph(f"{total_amt:,.2f}", cell_right)]
    ]
    pay_det_table = Table(pay_det_data, colWidths=[40, 75, 65, 200, 80, 80])
    pay_det_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ('LINEBELOW', (0,0), (-1,0), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(pay_det_table)
    elements.append(Spacer(1, 10))

    # 6. Summary & Amount in Words
    amt_words = amount_to_words(total_amt)
    summary_data = [
        [
            Paragraph(f"<b>AMOUNT IN WORDS:</b><br/>{amt_words}", cell_style),
            Paragraph(f"<b>SUB TOTAL:</b> ₱{total_amt:,.2f}<br/><b>ROUNDING ADJ:</b> 0.00<br/><b>NET TOTAL PHP:</b> ₱{total_amt:,.2f}", cell_right_bold)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[370, 170])
    summary_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 30))

    # 7. Signatures
    sig_data = [
        [
            Paragraph("_______________________________<br/><b>APPROVED BY</b>", cell_center_bold),
            Paragraph("_______________________________<br/><b>RECEIVED BY</b>", cell_center_bold)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[270, 270])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

#===========================================================================
from datetime import datetime

# --- HELPER 1: EXACT CHEQUE DATE SPACING ---
def format_cheque_date_exact(date_str):
    """Replicates your Google Apps Script custom date spacing for cheque boxes."""
    if not date_str or date_str == "[ PENDING ]":
        return ""
    try:
        dt = datetime.strptime(str(date_str).split()[0], "%Y-%m-%d")
        month = f"{dt.month:02d}"
        day = f"{dt.day:02d}"
        year = f"{dt.year:04d}"

        # Digits separated by 3 spaces
        spaced_month = (" " * 3).join(list(month))
        spaced_day = (" " * 3).join(list(day))
        spaced_year = (" " * 3).join(list(year))

        # Gaps: 6 spaces between Month & Day, 5 spaces between Day & Year
        return f"{spaced_month}{' ' * 6}{spaced_day}{' ' * 5}{spaced_year}"
    except Exception:
        return str(date_str)


# --- HELPER 2: CHEQUE AMOUNT IN WORDS ---
def cheque_amount_to_words(amount):
    """Formats amount into cheque words without 'PHILIPPINE PESO' prefix."""
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return "ZERO PESOS"
    
    pesos = int(amount)
    cents = int(round((amount - pesos) * 100))
    
    units = ["", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", 
             "TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN", 
             "SEVENTEEN", "EIGHTEEN", "NINETEEN"]
    tens = ["", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY"]

    def _convert(n):
        words = []
        if n >= 100:
            words.append(units[n // 100] + " HUNDRED")
            n %= 100
        if 1 <= n <= 19:
            words.append(units[n])
        elif n >= 20:
            words.append(tens[n // 10] + (" " + units[n % 10] if (n % 10) != 0 else ""))
        return " ".join(words)

    if pesos == 0:
        words_str = "ZERO"
    else:
        parts = []
        if pesos >= 1_000_000:
            parts.append(_convert(pesos // 1_000_000) + " MILLION")
            pesos %= 1_000_000
        if pesos >= 1_000:
            parts.append(_convert(pesos // 1_000) + " THOUSAND")
            pesos %= 1_000
        if pesos > 0:
            parts.append(_convert(pesos))
        words_str = " ".join(parts)

    if cents > 0:
        return f"{words_str} & {cents:02d}/100."
    return f"{words_str} PESOS"
#===========================================================================
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.pdfgen import canvas

def create_cheque_pdf(supplier, total_amt, cheque_date_str):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    
    font_bold = "Roboto-Bold" if ROBOTO_READY else "Helvetica-Bold"

    # --- GOOGLE SHEETS MARGINS: left=0.745", top=0.40" ---
    left_margin = 0.745 * inch   # ~18.92 mm
    top_margin  = 0.400 * inch   # ~10.16 mm
    
    # A4 Page Height = 297mm. Top anchor Y-coordinate in ReportLab:
    top_y = (297 * mm) - top_margin  # ~286.84 mm

    # --- COORDINATES MATCHING D4:J10 GRID ---
    date_x     = left_margin + (133 * mm)   # Column for Date
    date_y     = top_y - (4 * mm)           # Date Row

    payee_x    = left_margin + (12 * mm)    # Column for Payee
    payee_y    = top_y - (11 * mm)          # Payee Row

    amt_num_x  = left_margin + (127 * mm)   # Column for Numeric Amount
    amt_num_y  = top_y - (11 * mm)          # Same row as Payee

    words_x    = left_margin + (5 * mm)     # Column for Amount in Words
    words_y    = top_y - (20 * mm)          # Words Row

    # 1. Print Date with your exact Google Apps Script spacing
    spaced_date = format_cheque_date_exact(cheque_date_str)
    pdf.setFont(font_bold, 10)
    pdf.drawString(date_x, date_y, spaced_date)

    # 2. Print Payee Name
    pdf.setFont(font_bold, 9)
    pdf.drawString(payee_x, payee_y, str(supplier).upper())

    # 3. Print Numeric Amount
    pdf.setFont(font_bold, 10)
    pdf.drawString(amt_num_x, amt_num_y, f"{total_amt:,.2f}")

    # 4. Print Amount in Words
    words_text = cheque_amount_to_words(total_amt)
    pdf.setFont(font_bold, 9)
    pdf.drawString(words_x, words_y, words_text)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
    #==============================================================

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import io

def create_payment_voucher_pdf(cv_no, cv_date, cheque_no, cheque_date, supplier, supplier_address, project_name, pono, amount, ewt_amount):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=16, alignment=1, textColor=colors.HexColor('#8B0000'))
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, alignment=1)
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10)
    bold_body = ParagraphStyle('BoldBodyStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10)

    # 1. Company Header
    story.append(Paragraph("Tuanson Construction", title_style))
    story.append(Paragraph("GST Reg. No.: ___ | Sales Tax Reg. No.: ___ | Service Tax Reg. No.: ___", subtitle_style))
    story.append(Paragraph("162 P. Labuca St., Cansojong, Talisay City, Cebu", subtitle_style))
    story.append(Paragraph("Tel : - Fax : ___ | URL : ___ | Email : ___", subtitle_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("**Payment Voucher**", ParagraphStyle('PVTitle', parent=title_style, fontSize=12, textColor=colors.black)))
    story.append(Spacer(1, 10))

    # 2. Vendor & Voucher Meta Data Table
    net_total = amount - ewt_amount
    meta_data = [[Paragraph(supplier, bold_body), Paragraph("NO.:", bold_body), Paragraph(cv_no, body_style)]]
    
    # FIX: Initialize meta_table before styling it
    meta_table = Table(meta_data, colWidths=[350, 40, 150])
    meta_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 3. Main A/C Code Table
    ac_data = [
        [Paragraph("A/C CODE", header_style), Paragraph("A/C NAME", header_style), Paragraph("DESCRIPTION", header_style), Paragraph("AMOUNT", header_style)],
        [
            Paragraph("VEN-M0034", body_style),
            Paragraph(f"{supplier}", body_style),
            Paragraph(f"Payment for materials at {project_name}", body_style),
            Paragraph(f"₱{amount:,.2f}", body_style)
        ]
    ]
    ac_table = Table(ac_data, colWidths=[70, 130, 260, 80])
    ac_table.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,0), 1, colors.black),
        ('LINEBELOW', (0,1), (-1,1), 0.5, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(ac_table)
    story.append(Spacer(1, 10))

    # 4. Journals Section
    story.append(Paragraph("**Journals:**", bold_body))
    story.append(Paragraph("******************************", body_style))
    
    journal_data = [
        [Paragraph("Doc No.", header_style), Paragraph("Date", header_style), Paragraph("Account #", header_style), Paragraph("Account Name", header_style), Paragraph("Debit", header_style), Paragraph("Credit", header_style)],
        [Paragraph(cv_no, body_style), Paragraph(cv_date, body_style), Paragraph("VEN-M0034", body_style), Paragraph(f"VEN-M0034: {supplier}", body_style), Paragraph(f"₱{amount:,.2f}", body_style), Paragraph("-", body_style)],
        [Paragraph(cv_no, body_style), Paragraph(cv_date, body_style), Paragraph("100-0004", body_style), Paragraph("100-0004: CIB-BDO1", body_style), Paragraph("-", body_style), Paragraph(f"₱{amount:,.2f}", body_style)],
        [Paragraph("", body_style), Paragraph("", body_style), Paragraph("", body_style), Paragraph("", body_style), Paragraph(f"**₱{amount:,.2f}**", body_style), Paragraph(f"**₱{amount:,.2f}**", body_style)],
    ]
    journal_table = Table(journal_data, colWidths=[65, 65, 75, 175, 60, 60])
    journal_table.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,0), 1, colors.black),
        ('LINEBELOW', (0,-1), (-1,-1), 1, colors.black),
        ('LINEABOVE', (0,-1), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(journal_table)
    story.append(Spacer(1, 10))

    # 5. Payment Details Section
    story.append(Paragraph("**PAYMENT DETAILS**", bold_body))
    pay_details_data = [
        [Paragraph("Type", header_style), Paragraph("Doc. No.", header_style), Paragraph("Doc. Date", header_style), Paragraph("Description", header_style), Paragraph("Orig. Amount", header_style), Paragraph("Paid Amount", header_style)],
        [Paragraph("BIL", body_style), Paragraph(f"PO#{pono}", body_style), Paragraph(cv_date, body_style), Paragraph(f"PAYABLE FOR PURCHASE OF MATERIALS FOR {project_name.upper()}", body_style), Paragraph(f"{amount:,.2f}", body_style), Paragraph(f"{amount:,.2f}", body_style)],
    ]
    pay_table = Table(pay_details_data, colWidths=[40, 70, 65, 185, 70, 70])
    pay_table.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,0), 1, colors.black),
        ('LINEBELOW', (0,-1), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(pay_table)
    story.append(Spacer(1, 15))

    # 6. Totals & Notes Section (FIXED & COMPLETED)
    totals_data = [
        [
            Paragraph(f"**Notes:** Less (1%) EWT ₱{ewt_amount:,.2f}", body_style),
            Paragraph("**SUB TOTAL**", bold_body),
            Paragraph(f"**₱{amount:,.2f}**", bold_body)
        ],
        [
            Paragraph("", body_style),
            Paragraph("**NET TOTAL**", bold_body),
            Paragraph(f"**₱{net_total:,.2f}**", bold_body)
        ]
    ]
    totals_table = Table(totals_data, colWidths=[340, 90, 70])
    totals_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LINEABOVE', (1,1), (-1,1), 0.5, colors.black),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 40))

    # 7. Signatures Section (ADDED)
    sig_data = [
        [Paragraph("Prepared By:", body_style), Paragraph("Checked By:", body_style), Paragraph("Approved By:", body_style), Paragraph("Received By:", body_style)],
        [Spacer(1, 30), Spacer(1, 30), Spacer(1, 30), Spacer(1, 30)], 
        [Paragraph("_________________", body_style), Paragraph("_________________", body_style), Paragraph("_________________", body_style), Paragraph("_________________", body_style)]
    ]
    sig_table = Table(sig_data, colWidths=[135, 135, 135, 135])
    story.append(sig_table)

    # FIX: Build the document and return the buffer
    doc.build(story)
    buffer.seek(0)
    return buffer
                      
# --- APP LAYOUT & LOGIN SYSTEM ---
st.set_page_config(page_title="Tuanson Construction System", layout="wide")

conn = get_db_connection()
c = conn.cursor()

# --- LOGIN SYSTEM ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.available_roles = []
    st.session_state.can_add_act = "No"
    st.session_state.can_add_item = "No"

if not st.session_state.logged_in:
    st.title("🏗️ Tuanson Construction Enterprise System")
    st.caption("Integrated Procurement, Inventory & Double-Entry Accounting System")
    st.write("---")

    # Split the screen into two columns
    col_login, col_flow = st.columns([1, 1.2], gap="large")

    with col_login:
        st.subheader("🔒 User Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_btn = st.form_submit_button("Login", use_container_width=True)

            if submit_btn:
                user_data = c.execute("SELECT id, username, password, role1, role2, role3, role4, role5, role6, status, can_add_act, can_add_item FROM users WHERE username=? AND password=? AND status='Active'", (username, password)).fetchone()
                if user_data:
                    st.session_state.logged_in = True
                    st.session_state.current_user = user_data[1] 
                    
                    raw_roles = user_data[3:9]
                    roles = [r for r in raw_roles if r and str(r).strip() != ""]
                    st.session_state.available_roles = roles
                    
                    st.session_state.can_add_act = user_data[10]
                    st.session_state.can_add_item = user_data[11]
                    st.rerun()
                else:
                    st.error("Invalid Username/Password or Account is Inactive.")

    with col_flow:
        st.subheader("🔄 System Workflow Process")
        st.markdown(
            """
                📝 Requisitor

                Creates Purchase Requisition floaters for site material needs.
                
                ⬇️
                
                🛒 Purchaser
                
                Requests supplier quotes and generates Purchase Orders (PO).
                
                ⬇️
                
                👔 Approver / Manager
                
                Reviews budget alignment, approves POs, and authorizes releases.
                
                ⬇️
                
                🚚 Purchaser & Receiving
                
                Logs Delivery Receipts (DR) and updates inventory ledgers.
                
                ⬇️
                
                📑 Accounting
                
                Issues AP Vouchers (APV), 1% EWT deductions, and Payment Vouchers (CV).
                
                        """,
                        unsafe_allow_html=True
                    )
                
        st.stop() 

# --- IF LOGGED IN: SHOW MAIN APP ---

st.title("🏗️ Tuanson Construction - Procurement & Inventory")

st.sidebar.write(f"👤 **Logged in as:** {st.session_state.current_user}")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.available_roles = []
    st.session_state.can_add_act = "No"
    st.session_state.can_add_item = "No"
    st.rerun()

st.sidebar.markdown("---")

if not st.session_state.available_roles:
    st.warning("You have no roles assigned. Please contact the Admin.")
    st.stop()
    
role = st.sidebar.selectbox("🔑 Select Your Active Role", st.session_state.available_roles)

# --- ROLE 1: REQUISITOR ---
if role == "Requisitor":
    st.subheader(f"📋 Requisitor Dashboard - {st.session_state.current_user}")
    
    tab_request, tab_track, tab_receive = st.tabs(["📝 New Material Request", "🔍 Track My Requests", "📦 Receive Incoming Items"])
    
    with tab_request:
        if "request_cart" not in st.session_state:
            st.session_state.request_cart = []
        
        col_proj, col_act = st.columns(2)
        
        projects = [r[0] for r in c.execute("SELECT project_name FROM projects").fetchall()]
        if not projects:
            projects = ["No projects available"]
        selected_project = col_proj.selectbox("Project Name", projects)
        
        act_query = """SELECT a.activity_name FROM activities a 
                       JOIN projects p ON a.project_id = p.id WHERE p.project_name = ?"""
        activities = [r[0] for r in c.execute(act_query, (selected_project,)).fetchall()]
        
        activity_options = list(activities)
        if st.session_state.get('can_add_act') == 'Yes':
            activity_options.append("➕ Add New Activity...")
            
        if not activity_options:
            activity_options = ["No activities available"]
            
        selected_activity_option = col_act.selectbox("Activity", activity_options)
        
        selected_activity = selected_activity_option
        if selected_activity_option == "➕ Add New Activity...":
            new_activity_input = st.text_input("Enter New Activity Name")
            selected_activity = new_activity_input.strip()

        materials = c.execute("SELECT item_no, description, unit, COALESCE(category, 'Direct Materials') FROM materials").fetchall()
        mat_options = {f"[{m[0]}] {m[1]}": (m[0], m[1], m[2], m[3]) for m in materials} if materials else {}
        
        mat_label_options = list(mat_options.keys())
        if st.session_state.get('can_add_item') == 'Yes':
            mat_label_options.append("➕ Add New Item...")
            
        if not mat_label_options:
            mat_label_options = ["No items available"]
             
        selected_mat_label = st.selectbox("Select Item", mat_label_options)
        
        if selected_mat_label == "➕ Add New Item...":
            st.info("💡 Registering a new item for this request:")
            col_ni1, col_ni2 = st.columns(2)
            item_no = col_ni1.text_input("New Item Number (e.g., 00007 or custom code)")
            description = col_ni2.text_input("Item Description")
            default_unit = "PCS"
            default_category = "Direct Materials"
        elif selected_mat_label == "No items available":
            item_no, description, default_unit, default_category = "", "", "PCS", "Direct Materials"
            st.warning("⚠️ No materials exist in the database yet. Contact an admin to add items.")
        else:
            item_no, description, default_unit, default_category = mat_options[selected_mat_label]
        
        suppliers = [r[0] for r in c.execute("SELECT supplier_name FROM suppliers").fetchall()]
        supplier_options = ["No Preference"] + suppliers

        with st.form("request_form"):
            category_options = ["Direct Materials", "Equipment & Rental", "Tools & Consumables", "Fuel & Lubricants", "Subcontract & Services"]
            cat_index = category_options.index(default_category) if default_category in category_options else 0
            
            col_cat, col_unit = st.columns(2)
            category = col_cat.selectbox("Category (Accounting Tag)", category_options, index=cat_index)
            unit = col_unit.text_input("Unit", value=default_unit)
            
            col1, col2, col3 = st.columns([1, 1, 1.5])
            qty = col1.number_input("Quantity", min_value=1.0, step=1.0)
            price = col2.number_input("Estimated Price (Optional)", min_value=0.0, step=10.0)
            suggested_supplier = col3.selectbox("Suggested Supplier (Optional)", supplier_options, index=0)
            
            email = st.text_input("Requester Email", value="requester@tuanson.com")
            
            add_to_list = st.form_submit_button("➕ Add to Temporary List")
            
            if add_to_list:
                if selected_mat_label == "No items available":
                    st.error("⚠️ Cannot add to list. No materials selected.")
                elif selected_activity_option == "➕ Add New Activity..." and not selected_activity:
                    st.error("⚠️ Please type a valid name for the new activity.")
                elif selected_mat_label == "➕ Add New Item..." and (not item_no.strip() or not description.strip()):
                    st.error("⚠️ Please provide both a valid Item Number and Description for the new item.")
                else:
                    if selected_activity_option == "➕ Add New Activity...":
                        proj_id_row = c.execute("SELECT id FROM projects WHERE project_name = ?", (selected_project,)).fetchone()
                        if proj_id_row:
                            c.execute("""
                                INSERT OR IGNORE INTO activities (project_id, activity_name, qty, unit, contract_amount) 
                                VALUES (?, ?, 1.0, ?, 0.0)
                            """, (proj_id_row[0], selected_activity, unit))
                            conn.commit()

                    if selected_mat_label == "➕ Add New Item...":
                        c.execute("""
                            INSERT INTO materials (item_no, description, unit, category)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(item_no) DO UPDATE SET
                                description = excluded.description,
                                unit = excluded.unit,
                                category = excluded.category
                        """, (item_no.strip(), description.strip(), unit.strip(), category))
                        conn.commit()

                    st.session_state.request_cart.append({
                        "Project": selected_project,
                        "Activity": selected_activity,
                        "Item No": item_no.strip(),
                        "Description": description.strip(),
                        "Category": category,
                        "Qty": qty,
                        "Unit": unit,
                        "Price": price,
                        "supplier": suggested_supplier,
                        "Email": email
                    })
                    st.success(f"Added {qty} {unit} of {description} to your list!")
                    st.rerun()

        if len(st.session_state.request_cart) > 0:
            st.markdown("---")
            st.subheader("🛒 Review & Edit Temporary List")
            st.info("💡 You can edit quantities, change categories, or delete rows before finalizing.")
            
            cart_df = pd.DataFrame(st.session_state.request_cart)
            edited_cart_df = st.data_editor(
                cart_df, 
                num_rows="dynamic",
                use_container_width=True,
                key="cart_editor"
            )
            
            st.session_state.request_cart = edited_cart_df.to_dict('records')
            
            if st.button("🚀 Submit All Requests to Purchasing"):
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                for item in st.session_state.request_cart:
                    amount = item["Qty"] * item["Price"]
                    c.execute("""INSERT INTO requests 
                                 (timestamp, project_name, activity, item_no, description, category, qty, unit, price, amount, email_address, status, supplier, requester_name)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending Purchaser', ?, ?)""",
                              (now, item["Project"], item["Activity"], item["Item No"], item["Description"], 
                               item["Category"], item["Qty"], item["Unit"], item["Price"], amount, item["Email"], item["supplier"], st.session_state.current_user))
                
                conn.commit()
                st.session_state.request_cart = [] 
                st.success("All items successfully submitted to Purchasing!")
                st.rerun()

    with tab_track:
        st.write(f"### 🔍 Request History for {st.session_state.current_user}")
        st.info("Track the live status of all your submitted material requests here.")
        
        history_df = pd.read_sql_query("""
            SELECT 
                timestamp AS 'Date Submitted',
                project_name AS 'Project',
                description AS 'Item Description',
                qty AS 'Qty',
                unit AS 'Unit',
                status AS 'Purchasing/Approval Status',
                pono AS 'P.O. Number',
                received_status AS 'Delivery Status'
            FROM requests
            WHERE requester_name = ?
            ORDER BY timestamp DESC
        """, conn, params=(st.session_state.current_user,))
        
        if not history_df.empty:
            st.dataframe(history_df, use_container_width=True, hide_index=True)
        else:
            st.info("You haven't submitted any material requests yet.")

    with tab_receive:
        st.write("### 📦 Receive Incoming Site Dispatches")
        st.info("Confirm the physical receipt of materials dispatched to your project site.")
        
        if st.button("🔄 Refresh Dispatches", key="btn_refresh_receiving"):
            st.rerun()
            
        user_projects_df = pd.read_sql_query("""
            SELECT DISTINCT project_name 
            FROM requests 
            WHERE requester_name = ? AND project_name IS NOT NULL AND project_name != ''
        """, conn, params=(st.session_state.current_user,))
        
        user_projects = user_projects_df['project_name'].tolist() if not user_projects_df.empty else []
        
        if not user_projects:
            st.warning("⚠️ No project history found for your account in requests. Please ensure you have made a project request first.")
        else:
            placeholders = ','.join(['?'] * len(user_projects))
            query = f"""
                SELECT 
                    id,
                    date AS 'Dispatch Date',
                    ref_no AS 'Ref / MIF No.',
                    item_description AS 'Item Description',
                    qty_out AS 'Qty Dispatched',
                    location AS 'Destination Project',
                    remarks AS 'Remarks'
                FROM inventory_ledger
                WHERE qty_out > 0 
                  AND status = 'Pending'
                  AND location IN ({placeholders})
            """
            
            pending_ledger_df = pd.read_sql_query(query, conn, params=tuple(user_projects))
            
            if not pending_ledger_df.empty:
                st.dataframe(pending_ledger_df.drop(columns=['id']), use_container_width=True, hide_index=True)
                
                st.write("#### ✅ Confirm Physical Receipt")
                
                options_dict = {
                    row['id']: f"ID: {row['id']} | {row['Item Description']} ({row['Qty Dispatched']} units) - Ref: {row['Ref / MIF No.']} @ {row['Destination Project']}"
                    for _, row in pending_ledger_df.iterrows()
                }
                
                item_to_receive = st.selectbox(
                    "Select Dispatch to Confirm", 
                    options=list(options_dict.keys()),
                    format_func=lambda x: options_dict[x]
                )
                
                if st.button("Confirm Physical Receipt", type="primary"):
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    c.execute("""
                        UPDATE inventory_ledger 
                        SET status = 'Completed', 
                            remarks = remarks || ' | Confirmed received on ' || ? 
                        WHERE id = ?
                    """, (current_time, item_to_receive))
                    
                    conn.commit()
                    st.success("✅ Material receipt confirmed successfully!")
                    st.rerun()
            else:
                st.info(f"🎉 No pending dispatches awaiting confirmation for your projects: {', '.join(user_projects)}.")
                    
# --- ROLE 2: PURCHASER ---
elif role == "Purchaser":
    st.subheader("🛒 Purchaser Dashboard")
    
    tab_create_po, tab_receive, tab_ledger = st.tabs([
        "📝 Create Purchase Orders", 
        "📦 Receive Deliveries", 
        "📊 Inventory Ledger & Issuance"
    ])
    
    with tab_create_po:
        st.write("### 🛒 Batch Create P.O.")
        
        if st.button("🔄 Refresh Pending Requests", key="btn_refresh_create_po"):
            st.rerun()
        
        pending_df = pd.read_sql_query(
            "SELECT id, project_name, activity, item_no, description, qty, unit, price AS est_price, supplier FROM requests WHERE status = 'Pending Purchaser'", 
            conn
        )
        
        last_po_query = "SELECT pono FROM requests WHERE pono IS NOT NULL AND pono != '' ORDER BY id DESC LIMIT 1"
        last_po_result = c.execute(last_po_query).fetchone()
        
        last_po = last_po_result[0] if last_po_result else None
        suggested_po = ""
        
        if last_po:
            match = re.search(r'(\d+)$', last_po)
            if match:
                number_str = match.group(1)
                prefix = last_po[:match.start()]
                next_number = str(int(number_str) + 1).zfill(len(number_str))
                suggested_po = f"{prefix}{next_number}"
            else:
                suggested_po = f"{last_po}-1"
        
        if pending_df.empty:
            st.info("No pending requests waiting for Purchasing.")
        else:
            last_prices = []
            default_confirmed_prices = []
            
            for _, row in pending_df.iterrows():
                item_no = row['item_no']
                est = row['est_price'] if pd.notnull(row['est_price']) else 0.0
                
                res = c.execute("""
                    SELECT price FROM requests 
                    WHERE item_no = ? AND price > 0 AND status != 'Pending Purchaser' 
                    ORDER BY id DESC LIMIT 1
                """, (item_no,)).fetchone()
                
                last_paid = res[0] if res else 0.0
                last_prices.append(last_paid)
                default_price = last_paid if last_paid > 0 else est
                default_confirmed_prices.append(default_price)
                
            pending_df["Last Purchase Price"] = last_prices
            pending_df["Confirmed Price"] = default_confirmed_prices
            
            st.write("#### 📝 1. Set P.O. Details")
            col1, col2 = st.columns(2)
            
            suppliers_master = [s[0] for s in c.execute("SELECT supplier_name FROM suppliers").fetchall()]
            if not suppliers_master:
                suppliers_master = ["No suppliers available"]

            default_vendor_index = 0
            if not pending_df.empty and suppliers_master != ["No suppliers available"]:
                first_row_suggestion = pending_df.iloc[0]["supplier"]
                if first_row_suggestion and first_row_suggestion in suppliers_master:
                    default_vendor_index = suppliers_master.index(first_row_suggestion)
            
            selected_supplier = col1.selectbox("Select Supplier for this Order", suppliers_master, index=default_vendor_index)
            po_number = col2.text_input("Enter P.O. Number", value=suggested_po)
            
            if last_po:
                col2.caption(f"💡 *Last used P.O. Number was:* **{last_po}**")
            else:
                col2.caption("💡 *No previous P.O. numbers found in the system.*")
                
            st.markdown("---")
            st.write("#### 📦 2. Select Items for this P.O.")
            st.info("Check the **'Add to PO'** box and verify the **'Confirmed Price'**.")
            
            pending_df.insert(0, "Add to PO", False) 
            pending_df.rename(columns={"supplier": "Suggested Supplier"}, inplace=True)
            
            edited_df = st.data_editor(
                pending_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Add to PO": st.column_config.CheckboxColumn("Add to PO", default=False),
                    "Suggested Supplier": st.column_config.TextColumn("Suggested Supplier"),
                    "Last Purchase Price": st.column_config.NumberColumn("Last Purchase Price", format="₱%.2f"),
                    "Confirmed Price": st.column_config.NumberColumn("Confirmed Price", min_value=0.0, step=0.01, format="₱%.2f"),
                    "est_price": None,
                    "id": None, 
                },
                disabled=["project_name", "activity", "item_no", "description", "qty", "unit", "Suggested Supplier", "Last Purchase Price"] 
            )
            
            if st.button("✅ Submit Purchase Order", type="primary"):
                if not po_number.strip():
                    st.error("⚠️ Please enter a valid P.O. Number before submitting.")
                elif selected_supplier == "No suppliers available":
                    st.error("⚠️ Please register a supplier before submitting a Purchase Order.")
                else:
                    selected_items = edited_df[edited_df["Add to PO"] == True]
                    
                    if selected_items.empty:
                        st.warning("⚠️ You haven't selected any items to include in this P.O.")
                    else:
                        for index, row in selected_items.iterrows():
                            req_id = row['id']
                            qty = float(row['qty'])
                            final_price = round(float(row['Confirmed Price']), 2)
                            total_amt = round(qty * final_price, 2)
                            
                            c.execute("""UPDATE requests 
                                         SET supplier = ?, pono = ?, price = ?, amount = ?, status = 'Pending Approval'
                                         WHERE id = ?""", 
                                      (selected_supplier, po_number, final_price, total_amt, req_id))
                        
                        conn.commit()
                        st.success(f"Successfully created P.O. #{po_number} with {len(selected_items)} item(s)!")
                        st.rerun()
                        

    st.subheader("⚠️ Rejected Purchase Orders (Action Required)")

    # Fetch rejected POs and include the new rejection_reason column
    rejected_pos = c.execute("""
        SELECT pono, supplier, project_name, rejection_reason
        FROM requests 
        WHERE status = 'Rejected' AND pono IS NOT NULL AND pono != ''
        GROUP BY pono
    """).fetchall()

    if not rejected_pos:
        st.info("No rejected Purchase Orders at this time.")
    else:
        for po in rejected_pos:
            pono, supplier, proj, reason = po
            
            with st.expander(f"❌ PO #{pono} | {supplier} | Needs Revision", expanded=True):
                # Display the reason you typed in earlier!
                st.error(f"**Rejection Reason:** {reason}") 
                
                # Fetch items. We include 'rowid' so we can update specific rows safely.
                po_items_df = pd.read_sql_query(
                    "SELECT rowid, item_no, description, qty, unit, price, amount FROM requests WHERE pono = ? AND status = 'Rejected'", 
                    conn, params=(pono,)
                )
                
                st.write("Update the unit price(s) below:")

                # st.data_editor lets the Purchaser edit the table directly on the screen
                edited_df = st.data_editor(
                    po_items_df, 
                    disabled=["rowid", "item_no", "description", "qty", "unit", "amount"], # Lock everything except 'price'
                    hide_index=True,
                    use_container_width=True,
                    column_config={"id": None}, # Hides the ID column from the user interface
                    key=f"edit_price_{pono}"
                )
                
                if st.button("💾 Save Prices & Resubmit PO", key=f"resubmit_{pono}", type="primary"):
                    # Loop through the edited dataframe and update the database
                    for index, row in edited_df.iterrows():
                        new_price = float(row['price'])
                        new_amount = float(row['qty']) * new_price 
                        row_id = row['id'] # <-- Changed from 'rowid' to 'id'
                        
                        c.execute("""
                            UPDATE requests
                            SET price = ?, amount = ?, status = 'Pending Approval', rejection_reason = NULL
                            WHERE rowid = ?
                        """, (new_price, new_amount, row_id))
                    
                    conn.commit()
                    st.success(f"PO #{pono} resubmitted successfully!")
                    import time
                    time.sleep(1)
                    st.rerun()
    
    with tab_receive:
        st.write("### 🚚 Record Supplier Deliveries")
        st.info("Log items that have arrived on-site and upload attached Delivery Receipts (DR), Sales Invoices (SI), or Official Receipts (OR).")

        if st.button("🔄 Refresh Deliveries", key="btn_refresh_receive_deliveries"):
            st.rerun()
        
        if "receive_success_msg" in st.session_state:
            st.success(st.session_state.pop("receive_success_msg"))

        pending_recv_df = pd.read_sql_query("""
            SELECT 
                pono AS 'PO Number', 
                supplier AS 'Supplier', 
                project_name AS 'Project', 
                SUM(amount) AS 'Total Amount', 
                approved_timestamp AS 'Date Approved'
            FROM requests
            WHERE status = 'Approved / Ongoing' AND received_status = 'Pending'
            GROUP BY pono
            ORDER BY approved_timestamp ASC
        """, conn)
        
        if not pending_recv_df.empty:
            st.dataframe(
                pending_recv_df.style.format({"Total Amount": "₱{:,.2f}"}), 
                use_container_width=True, 
                hide_index=True
            )
            
            st.markdown("---")
            st.write("#### ✅ Confirm Delivery Receipt")
            
            recv_col1, recv_col2 = st.columns(2)
            po_to_receive = recv_col1.selectbox("Select PO Number", pending_recv_df['PO Number'].tolist(), key="select_po_to_receive")
            
            # Document prefix selector and number input side-by-side
            sub_col1, sub_col2 = recv_col2.columns([1, 2])
            doc_prefix = sub_col1.selectbox("Type", ["DR", "CSI", "SI", "OR"], key="doc_type_prefix")
            raw_doc_no = sub_col2.text_input("Document No.", placeholder="e.g. 00001", key="doc_num_raw")
            
            # Automatically combine them (e.g., "DR#00001")
            dr_number = f"{doc_prefix}#{raw_doc_no}" if raw_doc_no else ""
            
            uploaded_file = st.file_uploader(
                "📎 Attach File for DR / SI / OR (Photo or PDF)", 
                type=["png", "jpg", "jpeg", "pdf"],
                key="receipt_file_uploader"
            )
            
            if uploaded_file is not None and uploaded_file.type.startswith("image/"):
                st.image(uploaded_file, caption="Preview of attached document", width=250)
            
            if st.button("Confirm Receiving", type="primary", key="btn_confirm_receiving"):
                if raw_doc_no.strip():
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    po_details = pending_recv_df[pending_recv_df['PO Number'] == po_to_receive].iloc[0]
                    
                    receipt_blob = uploaded_file.getvalue() if uploaded_file else None
                    file_name = uploaded_file.name if uploaded_file else None
                    
                    c.execute("""INSERT INTO deliveries 
                                 (pono, supplier, project_name, dr_number, total_amount, received_date, receipt_image, file_name) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                              (po_to_receive, po_details['Supplier'], po_details['Project'], dr_number.strip(), 
                               po_details['Total Amount'], current_time, receipt_blob, file_name))
                    
                    c.execute("UPDATE requests SET received_status = 'Received', received_timestamp = ? WHERE pono = ?", 
                              (current_time, po_to_receive))
                    
                    received_items = c.execute("SELECT description, qty FROM requests WHERE pono = ?", (po_to_receive,)).fetchall()
                    for item_desc, r_qty in received_items:
                        qty_val = float(r_qty or 0.0)
                        prev_bal = get_latest_item_balance(c, item_desc)
                        new_bal = prev_bal + qty_val
                        c.execute("""
                            INSERT INTO inventory_ledger (date, ref_no, item_description, qty_in, qty_out, balance, location, remarks, status)
                            VALUES (?, ?, ?, ?, 0.0, ?, ?, ?, 'Completed')
                        """, (current_time, dr_number.strip(), item_desc, qty_val, new_bal, po_details['Project'], f"Received via {dr_number.strip()} (PO #{po_to_receive})"))

                    conn.commit()
                    st.session_state["receive_success_msg"] = f"✅ PO #{po_to_receive} received under Doc #{dr_number}! Added to Inventory Ledger and forwarded to Accounting."
                    st.rerun()
                else:
                    st.warning("⚠️ Please input the document number.")
        else:
            st.success("🎉 No pending deliveries! All approved POs have been physically received.")

        st.markdown("---")
        st.write("### 📜 Received Deliveries History & Attachment Viewer")

        history_df = pd.read_sql_query("""
            SELECT 
                id,
                pono AS 'PO Number',
                supplier AS 'Supplier',
                project_name AS 'Project',
                dr_number AS 'DR / SI / OR No.',
                total_amount AS 'Total Amount',
                received_date AS 'Date Received',
                file_name AS 'File Name'
            FROM deliveries
            ORDER BY received_date DESC
        """, conn)

        if not history_df.empty:
            st.dataframe(
                history_df[["PO Number", "Supplier", "Project", "DR / SI / OR No.", "Total Amount", "Date Received", "File Name"]].style.format({"Total Amount": "₱{:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )

            st.write("#### 🔍 Select Item to View Attachment")
            options = {
                f"PO #{row['PO Number']} | {row['DR / SI / OR No.']} | {row['Supplier']} ({row['Project']})": row['id']
                for _, row in history_df.iterrows()
            }
            
            selected_label = st.selectbox("Choose a delivery record:", list(options.keys()), key="select_history_record")
            selected_id = options[selected_label]

            selected_record = c.execute("SELECT receipt_image, file_name FROM deliveries WHERE id = ?", (selected_id,)).fetchone()

            if selected_record and selected_record[0]:
                image_blob, fname = selected_record[0], selected_record[1]
                if fname and fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                    st.image(image_blob, caption=f"📷 Attached Receipt: {fname}", width=450)
                elif fname and fname.lower().endswith('.pdf'):
                    st.info(f"📄 PDF Document attached: **{fname}**")
                    st.download_button(label="📥 Download PDF Document", data=image_blob, file_name=fname, mime="application/pdf", key=f"dl_pdf_{selected_id}")
                else:
                    try:
                        st.image(image_blob, caption=f"📷 Attached Receipt: {fname or 'Image'}", width=450)
                    except Exception:
                        st.download_button(label=f"📥 Download Attached File ({fname or 'file'})", data=image_blob, file_name=fname or "receipt_file", key=f"dl_file_{selected_id}")
            else:
                st.warning("⚠️ No image or document file was attached for this receiving record.")
        else:
            st.info("No received deliveries recorded yet.")

    with tab_ledger:
        st.write("### 🚚 Issue Materials to Site (Qty Out)")
        
        if st.button("🔄 Refresh Ledger Data", key="btn_refresh_inventory_ledger"):
            st.rerun()
        
        items_db = c.execute("SELECT DISTINCT item_description FROM inventory_ledger").fetchall()
        item_list = [i[0] for i in items_db] if items_db else []

        if item_list:
            with st.form("issue_material_form"):
                col1, col2 = st.columns(2)
                selected_item = col1.selectbox("Select Item", item_list)
                
                current_stock = get_latest_item_balance(c, selected_item)
                col1.caption(f"Current Stock Available: **{current_stock:,.2f}**")
                
                qty_to_issue = col2.number_input("Qty Out", min_value=0.1, max_value=float(current_stock) if current_stock > 0 else 1.0, step=1.0)
                mif_ref = col1.text_input("MIF / Dispatch Ref No.", value="MIF-0001")
                site_location = col2.text_input("Destination Site / Location", placeholder="e.g. Suba Project Site")
                issuance_remarks = st.text_input("Remarks", placeholder="e.g. Dispatched via Flatbed Truck 1")
                
                submit_issue = st.form_submit_button("📤 Confirm Material Dispatch")
                
                if submit_issue:
                    if current_stock < qty_to_issue:
                        st.error("⚠️ Insufficient stock available!")
                    else:
                        dispatch_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        new_bal = current_stock - qty_to_issue
                        
                        c.execute("""
                            INSERT INTO inventory_ledger (date, ref_no, item_description, qty_in, qty_out, balance, location, remarks, status)
                            VALUES (?, ?, ?, 0.0, ?, ?, ?, ?, 'Pending')
                        """, (dispatch_time, mif_ref.strip(), selected_item, qty_to_issue, new_bal, site_location.strip(), issuance_remarks.strip()))
                        conn.commit()
                        st.success(f"✅ Dispatched {qty_to_issue} units of {selected_item} to {site_location}! Awaiting site confirmation.")
                        st.rerun()
        else:
            st.info("No stock recorded in inventory ledger yet. Receive deliveries first to populate stock.")

        st.markdown("---")
        st.write("### 📊 Inventory Ledger Table")

        ledger_df = pd.read_sql_query("""
            SELECT 
                date AS 'Date',
                ref_no AS 'Ref',
                item_description AS 'Item',
                qty_in AS 'Qty in',
                qty_out AS 'Qty Out',
                balance AS 'Balance',
                location AS 'Location',
                remarks AS 'Remarks',
                status AS 'Confirmation Status'
            FROM inventory_ledger
            ORDER BY id DESC
        """, conn)

        if not ledger_df.empty:
            st.dataframe(
                ledger_df.style.format({
                    "Qty in": "{:,.2f}",
                    "Qty Out": "{:,.2f}",
                    "Balance": "{:,.2f}"
                }),
                use_container_width=True,
                hide_index=True
            )
            
            csv_ledger = ledger_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Inventory Ledger as CSV",
                data=csv_ledger,
                file_name=f"inventory_ledger_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("Inventory ledger is currently empty.")

    st.markdown("---")
    st.subheader("🖨️ Approved Purchase Orders (Ready for Printing)")
    
    approved_pos = c.execute("""
        SELECT pono, supplier, project_name, MAX(approved_timestamp) as app_time 
        FROM requests 
        WHERE status = 'Approved / Ongoing' AND pono IS NOT NULL AND pono != ''
        GROUP BY pono
        ORDER BY app_time DESC
    """).fetchall()
    
    if approved_pos and HAS_REPORTLAB:
        for idx, po in enumerate(approved_pos):
            pono, supplier, proj, app_time = po
            col_info, col_btn = st.columns([3, 1])
            col_info.write(f"📄 **PO Number:** {pono} | **Supplier:** {supplier} | **Project:** {proj} | **Approved:** {app_time}")
            
            po_items = c.execute("SELECT qty, unit, description, activity, price, amount FROM requests WHERE pono = ?", (pono,)).fetchall()
            pdf_bytes = create_po_pdf(pono, datetime.now().strftime("%Y/%m/%d"), supplier, proj, po_items)
            
            col_btn.download_button(
                label=f"🖨️ Print PO #{pono}",
                data=pdf_bytes,
                file_name=f"PO_{pono}.pdf",
                mime="application/pdf",
                key=f"purchaser_print_po_{pono}_{idx}"
            )
    elif not approved_pos:
        st.info("No approved purchase orders currently available for printing.")

# --- ROLE 3: APPROVER ---
elif role == "Approver":
    st.subheader("✅ Approver Dashboard (Leizel Cabunilas)")

    if st.button("🔄 Refresh Approval Queue", key="btn_refresh_approver_queue"):
        st.rerun()
        
    st.subheader("⏳ Pending Approval Queue")
    pending_pos = c.execute("""
        SELECT pono, supplier, project_name, MAX(timestamp) as req_time 
        FROM requests 
        WHERE status = 'Pending Approval' AND pono IS NOT NULL AND pono != ''
        GROUP BY pono
        ORDER BY req_time DESC
    """).fetchall()
    
    if not pending_pos:
        st.info("No Purchase Orders currently awaiting approval.")
    else:
        for po in pending_pos:
            pono, supplier, proj, req_time = po
            
            with st.expander(f"📄 PO #{pono} | Supplier: {supplier} | Project: {proj} | Submitted: {req_time}", expanded=True):
                po_items_df = pd.read_sql_query(
                    "SELECT item_no, description, qty, unit, price, amount FROM requests WHERE pono = ? AND status = 'Pending Approval'", 
                    conn, params=(pono,)
                )
                
                st.dataframe(po_items_df, use_container_width=True, hide_index=True)
                total_amount = po_items_df["amount"].sum()
                st.markdown(f"### **Grand Total: ₱{total_amount:,.2f}**")
                
                col_app, col_rej, _ = st.columns([1, 1, 3])
                
                if col_app.button("✅ Approve PO", key=f"app_{pono}", type="primary"):
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("""
                        UPDATE requests 
                        SET status = 'Approved / Ongoing', approved_by = 'Leizel Cabunilas', approved_timestamp = ?
                        WHERE pono = ? AND status = 'Pending Approval'
                    """, (now_str, pono))
                    conn.commit()
                    st.success(f"PO #{pono} has been approved successfully!")
                    st.rerun()
                
                # --- NEW TWO-STEP REJECTION LOGIC ---
                with col_rej.popover("❌ Reject PO"):
                    st.markdown(f"**Are you sure you want to reject PO #{pono}?**")
                    reject_reason = st.text_area("Reason for rejection (Required):", key=f"reason_{pono}")
                    
                    if st.button("🚨 Confirm Rejection", key=f"confirm_rej_{pono}"):
                        if not reject_reason.strip():
                            st.error("Please provide a reason to reject this PO.")
                        else:
                            # UPDATED: Now saving the reject_reason to your new database column
                            c.execute("""
                                UPDATE requests 
                                SET status = 'Rejected', rejection_reason = ?
                                WHERE pono = ? AND status = 'Pending Approval'
                            """, (reject_reason, pono))
                            conn.commit()
                            
                            st.success(f"PO #{pono} was rejected.")
                            import time
                            time.sleep(1) 
                            st.rerun()

    st.markdown("---")
    st.subheader("🖨️ Approved Purchase Orders (Ready for Printing)")
    
    approved_pos = c.execute("""
        SELECT pono, supplier, project_name, MAX(approved_timestamp) as app_time 
        FROM requests 
        WHERE status = 'Approved / Ongoing' AND pono IS NOT NULL AND pono != ''
        GROUP BY pono
        ORDER BY app_time DESC
    """).fetchall()
    
    if approved_pos and HAS_REPORTLAB:
        for idx, po in enumerate(approved_pos):
            pono, supplier, proj, app_time = po
            col_info, col_btn = st.columns([3, 1])
            col_info.write(f"📄 **PO Number:** {pono} | **Supplier:** {supplier} | **Project:** {proj} | **Approved:** {app_time}")
            
            po_items = c.execute("SELECT qty, unit, description, activity, price, amount FROM requests WHERE pono = ?", (pono,)).fetchall()
            pdf_bytes = create_po_pdf(pono, datetime.now().strftime("%Y/%m/%d"), supplier, proj, po_items)
            
            col_btn.download_button(
                label=f"🖨️ Print PO #{pono}",
                data=pdf_bytes,
                file_name=f"PO_{pono}.pdf",
                mime="application/pdf",
                key=f"approver_pdf_{pono}_{idx}"
            )
    elif not approved_pos:
        st.info("No approved purchase orders available for printing.")

# --- ROLE 4: OFFICE MANAGER ---
elif role == "Office Manager":
    st.subheader("📊 Office Manager Dashboard - Project Status & Expenses")

    if st.button("🔄 Refresh Financial Data", key="btn_refresh_office_manager"):
        st.rerun()
    
    st.write("### 📈 Real-Time Project Financial Monitoring")
    
    projects_df = pd.read_sql_query("""
        SELECT 
            p.id as 'No.', 
            p.project_name as 'Project Name', 
            COALESCE(SUM(a.contract_amount), 0) as 'CONTRACT Amount'
        FROM projects p
        LEFT JOIN activities a ON p.id = a.project_id
        GROUP BY p.id, p.project_name
    """, conn)
    
    expenses_df = pd.read_sql_query("""
        SELECT 
            project_name, 
            category, 
            SUM(amount) as cost
        FROM requests
        WHERE status IN ('Approved / Ongoing', 'Received', 'Paid')
        GROUP BY project_name, category
    """, conn)
    
    if not expenses_df.empty:
        pivot_exp = expenses_df.pivot_table(index='project_name', columns='category', values='cost', fill_value=0).reset_index()
    else:
        pivot_exp = pd.DataFrame(columns=['project_name'])
        
    merged_df = pd.merge(projects_df, pivot_exp, left_on='Project Name', right_on='project_name', how='left').fillna(0)
    
    def safe_get_cat(df, cat_name):
        return df[cat_name] if cat_name in df.columns else 0.0

    merged_df['MATERIALS Amount'] = safe_get_cat(merged_df, 'Direct Materials') + safe_get_cat(merged_df, 'Tools & Consumables')
    merged_df['SUBCON'] = safe_get_cat(merged_df, 'Subcontract & Services')
    merged_df['EQPT Amount'] = safe_get_cat(merged_df, 'Equipment & Rental') + safe_get_cat(merged_df, 'Fuel & Lubricants')
    
    merged_df['Labor Amount'] = 0.0  
    merged_df['ADMIN'] = 0.0
    merged_df['REVISED Amount'] = merged_df['CONTRACT Amount'] 
    merged_df['Implementing Budget Amount'] = merged_df['CONTRACT Amount'] * 0.42 
    merged_df['Implementing Budget %'] = 0.42 
    
    merged_df['TOTAL Amount'] = (merged_df['MATERIALS Amount'] + merged_df['Labor Amount'] + 
                                 merged_df['ADMIN'] + merged_df['SUBCON'] + merged_df['EQPT Amount'])
    
    for col, target in [('MATERIALS Amount', 'Mat %'), ('Labor Amount', 'Lab %'), 
                        ('EQPT Amount', 'Eqpt %'), ('TOTAL Amount', 'Total %')]:
        merged_df[target] = (merged_df[col] / merged_df['Implementing Budget Amount']).replace([float('inf'), -float('inf')], 0.0).fillna(0.0)
        
    final_columns = [
        'No.', 'Project Name', 'CONTRACT Amount', 'REVISED Amount',
        'Implementing Budget %', 'Implementing Budget Amount',
        'Mat %', 'MATERIALS Amount', 'Lab %', 'Labor Amount', 'ADMIN', 'SUBCON',
        'Eqpt %', 'EQPT Amount', 'Total %', 'TOTAL Amount'
    ]
    
    for col in final_columns:
        if col not in merged_df.columns:
            merged_df[col] = 0.0
            
    final_df = merged_df[final_columns]
    
    final_df.columns = pd.MultiIndex.from_tuples([
        ('Project Details', 'No.'),
        ('Project Details', 'Project Name'),
        ('Project Details', 'CONTRACT Amount'),
        ('Project Details', 'REVISED Amount'),
        ('Implementing Budget', '%'),
        ('Implementing Budget', 'Amount'),
        ('Running Expenses', 'Mat %'),
        ('Running Expenses', 'MATERIALS Amount'),
        ('Running Expenses', 'Lab %'),
        ('Running Expenses', 'Labor Amount'),
        ('Running Expenses', 'ADMIN'),
        ('Running Expenses', 'SUBCON'),
        ('Running Expenses', 'Eqpt %'),
        ('Running Expenses', 'EQPT Amount'),
        ('Running Expenses', 'Total %'),
        ('Running Expenses', 'TOTAL Amount')
    ])
    
    styled_df = final_df.style.format({
        ('Project Details', 'CONTRACT Amount'): "₱{:,.2f}",
        ('Project Details', 'REVISED Amount'): "₱{:,.2f}",
        ('Implementing Budget', '%'): "{:.2%}",
        ('Implementing Budget', 'Amount'): "₱{:,.2f}",
        ('Running Expenses', 'Mat %'): "{:.2%}",
        ('Running Expenses', 'MATERIALS Amount'): "₱{:,.2f}",
        ('Running Expenses', 'Lab %'): "{:.2%}",
        ('Running Expenses', 'Labor Amount'): "₱{:,.2f}",
        ('Running Expenses', 'ADMIN'): "₱{:,.2f}",
        ('Running Expenses', 'SUBCON'): "₱{:,.2f}",
        ('Running Expenses', 'Eqpt %'): "{:.2%}",
        ('Running Expenses', 'EQPT Amount'): "₱{:,.2f}",
        ('Running Expenses', 'Total %'): "{:.2%}",
        ('Running Expenses', 'TOTAL Amount'): "₱{:,.2f}",
    })
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    col_dl1, col_dl2 = st.columns([1, 4])
    
    export_df = final_df.copy()
    export_df.columns = ['_'.join(col).strip() for col in export_df.columns.values]
    
    csv_summary = export_df.to_csv(index=False).encode('utf-8')
    col_dl1.download_button(
        label="📥 Download Summary (CSV)",
        data=csv_summary,
        file_name=f"project_financial_summary_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

# --- ROLE 5: ACCOUNTING ---
elif role == "Accounting":

    # Automatic schema migration for cheque tracking
    for col_def in ["cheque_no TEXT", "cheque_date TEXT"]:
        try:
            c.execute(f"ALTER TABLE deliveries ADD COLUMN {col_def}")
            conn.commit()
        except Exception:
            pass
        
    from datetime import datetime, timedelta
    
    # Automatic schema migration check for project_name column
    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN project_name TEXT")
        conn.commit()
    except Exception:
        pass

    st.subheader("🧾 Accounting Dashboard - Payables & Financial Reports")
    
    if st.button("🔄 Refresh Accounting Data", key="btn_refresh_accounting"):
        st.rerun()
    
    tab_coa, tab_apv, tab_payment, tab_gl, tab_fs = st.tabs([
        "📊 Chart of Accounts", 
        "📝 Accounts Payable Voucher (APV)", 
        "💸 Check / Payment Voucher (CV)", 
        "📖 General Ledger Entries",
        "📈 Financial Statements"
    ])
    
    # --- TAB 0: CHART OF ACCOUNTS ---
    with tab_coa:
        st.subheader("📊 Manage Chart of Accounts")
        st.info("View, add, or manage financial account codes used across General Ledger postings and vouchers.")
        
        with st.expander("➕ Add New Account Code"):
            with st.form("add_coa_form", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                new_acc_code = col1.text_input("Account Code (e.g., 10500)")
                new_acc_name = col2.text_input("Account Name (e.g., Accounts Receivable)")
                new_acc_type = col3.selectbox("Account Type", ["Asset", "Liability", "Equity", "Revenue", "Expense"])
                
                submitted_coa = st.form_submit_button("Save Account Code", type="primary")
                if submitted_coa:
                    if new_acc_code.strip() and new_acc_name.strip():
                        try:
                            c.execute("""
                                INSERT INTO chart_of_accounts (account_code, account_name, account_type)
                                VALUES (?, ?, ?)
                            """, (new_acc_code.strip(), new_acc_name.strip(), new_acc_type))
                            conn.commit()
                            st.success(f"Account {new_acc_code.strip()} - {new_acc_name.strip()} added successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Account Code '{new_acc_code.strip()}' already exists or error occurred.")
                    else:
                        st.warning("⚠️ Please provide both an Account Code and Account Name.")

        df_coa = pd.read_sql_query("""
            SELECT account_code AS 'Account Code', account_name AS 'Account Name', 
                   account_type AS 'Account Type', status AS 'Status'
            FROM chart_of_accounts
            ORDER BY account_code ASC
        """, conn)
        
        if not df_coa.empty:
            st.dataframe(df_coa, use_container_width=True, hide_index=True)
        else:
            st.info("No accounts found in the Chart of Accounts.")

    # --- TAB 1: ACCOUNTS PAYABLE VOUCHER (APV) ---
    with tab_apv:
        st.write("### 📦 Received Deliveries Awaiting APV Generation")
        st.info("Receiving tab logs received items. Generate APV here to record Accounts Payable in the General Ledger.")
        
        apv_df = pd.read_sql_query("""
            SELECT id, pono AS 'PO Number', dr_number AS 'DR Number', supplier AS 'Supplier', 
                   project_name AS 'Project', total_amount AS 'Total Amount', received_date AS 'Date Received'
            FROM deliveries 
            WHERE payment_status = 'Unpaid' AND (apv_number IS NULL OR apv_number = '')
            ORDER BY received_date ASC
        """, conn)
        
        if not apv_df.empty:
            st.dataframe(apv_df.style.format({"Total Amount": "₱{:,.2f}"}), use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.write("#### 📑 Generate APV Document")
            col1, col2, col3 = st.columns(3)
            
            dr_to_apv = col1.selectbox("Select DR Number to Voucher", apv_df['DR Number'].tolist())
            suggested_apv = generate_voucher_number(c, "apv_number", "APV")
            
            apv_input = col2.text_input(
                "APV Number Sequence", 
                value=suggested_apv, 
                key=f"apv_input_{suggested_apv}"
            )
            
            expense_accounts = c.execute("SELECT account_code, account_name FROM chart_of_accounts WHERE account_type = 'Expense'").fetchall()
            
            if expense_accounts:
                expense_options = [f"[{acc[0]}] {acc[1]}" for acc in expense_accounts]
            else:
                expense_options = ["No Expense Accounts Found"]
                
            selected_expense = col3.selectbox("Accounting Tag (Debit Account)", expense_options)
            
            if selected_expense != "No Expense Accounts Found":
                selected_acc_code = selected_expense.split("]")[0].replace("[", "")
                selected_acc_name = selected_expense.split("]")[1].strip()
            else:
                selected_acc_code = "60200"
                selected_acc_name = "Direct Cost Materials"
            
            st.info(f"""
            💡 **Accounting Entry Preview:**
            * **Debit:** {selected_acc_name} (Code {selected_acc_code})
            * **Credit:** Accounts Payable-Trade (Code 20100)
            """)
            
            if st.button("✅ Generate Accounts Payable Voucher", type="primary"):
                if apv_input.strip():
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    selected_del = apv_df[apv_df['DR Number'] == dr_to_apv].iloc[0]
                    total_amt = float(selected_del['Total Amount'])
                    po_no = selected_del['PO Number']
                    supplier_name = selected_del['Supplier']
                    proj_name = selected_del['Project']
                    
                    po_details = c.execute("SELECT activity, Description FROM requests WHERE pono = ?", (po_no,)).fetchall()
                    po_desc_string = ""
                    
                    if po_details:
                        desc_parts = []
                        for act, part in po_details:
                            item_desc = " - ".join([str(x) for x in [act, part] if x])
                            if item_desc:
                                if len(item_desc) > 30:
                                    item_desc = item_desc[:25] + "..."
                                desc_parts.append(item_desc)
                        if desc_parts:
                            po_desc_string = " - " + " | ".join(desc_parts)
                    
                    debit_desc = f"APV setup for {dr_to_apv} ({supplier_name}){po_desc_string}"
                    credit_desc = f"APV liability accrued for {dr_to_apv}{po_desc_string}"
                    
                    c.execute("""
                        UPDATE deliveries 
                        SET apv_number = ?, apv_date = ? 
                        WHERE dr_number = ?
                    """, (apv_input.strip(), current_time, dr_to_apv))
                    
                    c.execute("""
                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                        VALUES (?, ?, ?, ?, ?, 0.0, ?, ?, ?)
                    """, (current_time, apv_input.strip(), selected_acc_code, selected_acc_name, total_amt, dr_to_apv, debit_desc, proj_name))
                    
                    c.execute("""
                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                        VALUES (?, ?, '20100', 'Accounts Payable-Trade', 0.0, ?, ?, ?, ?)
                    """, (current_time, apv_input.strip(), total_amt, dr_to_apv, credit_desc, proj_name))
                    
                    conn.commit()
                    st.success(f"🎉 Voucher {apv_input.strip()} recorded successfully for DR #{dr_to_apv}!")
                    st.rerun()
                else:
                    st.error("⚠️ Please enter a valid APV Number.")
        else:
            st.success("🎉 All received deliveries have been vouchered with an APV!")

        st.markdown("---")
        st.subheader("🖨️ Generated Accounts Payable Vouchers (Ready for Printing)")
        
        generated_apvs = c.execute("""
            SELECT apv_number, apv_date, dr_number, pono, supplier, project_name, total_amount 
            FROM deliveries 
            WHERE apv_number IS NOT NULL AND apv_number != ''
            ORDER BY apv_date DESC
        """).fetchall()
        
        if generated_apvs and HAS_REPORTLAB:
            for idx, apv in enumerate(generated_apvs):
                apv_no, apv_date, dr_no, po_no, supplier, proj, total_amt = apv
                col_info, col_btn = st.columns([3, 1])
                col_info.write(f"📄 **APV:** {apv_no} | **Supplier:** {supplier} | **Project:** {proj} | **Amount:** ₱{total_amt:,.2f}")
                
                pdf_bytes = create_apv_pdf(apv_no, apv_date, dr_no, po_no, supplier, proj, total_amt, conn)
                col_btn.download_button(
                    label=f"🖨️ Print APV",
                    data=pdf_bytes,
                    file_name=f"APV_{apv_no}.pdf",
                    mime="application/pdf",
                    key=f"print_apv_{apv_no}_{idx}"
                )
        else:
            st.info("No generated APVs available for printing yet.")

    # --- TAB 2: CHECK VOUCHER / PAYMENT (CV) ---
    with tab_payment:
        st.write("### 💳 Outstanding Payables with AP Aging Summary")
        
        pay_df = pd.read_sql_query("""
            SELECT id, apv_number AS 'APV Number', pono AS 'PO Number', dr_number AS 'DR Number', 
                   supplier AS 'Supplier', total_amount AS 'Total Amount', apv_date AS 'APV Date',
                   project_name AS 'Project'
            FROM deliveries 
            WHERE payment_status = 'Unpaid' AND apv_number IS NOT NULL AND apv_number != ''
            ORDER BY apv_date ASC
        """, conn)

        try:
            terms_lookup = dict(c.execute("SELECT supplier_name, terms_days FROM suppliers").fetchall())
        except Exception:
            terms_lookup = {}

        today = datetime.now().date()

        def compute_aging(row):
            sup = row['Supplier']
            terms = terms_lookup.get(sup, 30)
            try:
                apv_dt = pd.to_datetime(row['APV Date']).date()
            except Exception:
                apv_dt = today
            
            due_dt = apv_dt + timedelta(days=terms)
            days_overdue = (today - due_dt).days
            
            if days_overdue <= 0:
                status = f"🟢 Current ({abs(days_overdue)}d left)"
                bucket = "Current"
            elif 1 <= days_overdue <= 15:
                status = f"🟡 Overdue ({days_overdue}d)"
                bucket = "1-15 Days"
            elif 16 <= days_overdue <= 30:
                status = f"🟠 Overdue ({days_overdue}d)"
                bucket = "16-30 Days"
            else:
                status = f"🔴 Overdue ({days_overdue}d)"
                bucket = "30+ Days"
                
            return pd.Series([due_dt.strftime('%Y-%m-%d'), days_overdue, status, bucket])

        if not pay_df.empty:
            pay_df[['Due Date', 'Days Overdue', 'Aging Status', 'Aging Bucket']] = pay_df.apply(compute_aging, axis=1)

            m_curr = pay_df[pay_df['Aging Bucket'] == 'Current']['Total Amount'].sum()
            m_1_15 = pay_df[pay_df['Aging Bucket'] == '1-15 Days']['Total Amount'].sum()
            m_16_30 = pay_df[pay_df['Aging Bucket'] == '16-30 Days']['Total Amount'].sum()
            m_30_plus = pay_df[pay_df['Aging Bucket'] == '30+ Days']['Total Amount'].sum()

            ac1, ac2, ac3, ac4 = st.columns(4)
            ac1.metric("🟢 Current (Not Due)", f"₱{m_curr:,.2f}")
            ac2.metric("🟡 1-15 Days Overdue", f"₱{m_1_15:,.2f}")
            ac3.metric("🟠 16-30 Days Overdue", f"₱{m_16_30:,.2f}")
            ac4.metric("🔴 30+ Days Overdue", f"₱{m_30_plus:,.2f}")

            st.markdown("---")
            st.dataframe(
                pay_df[['APV Number', 'PO Number', 'Supplier', 'Project', 'Total Amount', 'APV Date', 'Due Date', 'Aging Status']]
                .style.format({"Total Amount": "₱{:,.2f}"}), 
                use_container_width=True, 
                hide_index=True
            )

            st.markdown("---")
            st.write("#### 💸 Process Payment & Generate Check Voucher")
            
            col1, col2, col3 = st.columns(3)
            
            apv_options = pay_df.apply(lambda r: f"{r['APV Number']} - {r['Supplier']} (₱{r['Total Amount']:,.2f}) [{r['Aging Status']}]", axis=1).tolist()
            selected_apv_str = col1.selectbox("Select APV Number to Pay", apv_options)
            apv_to_pay = selected_apv_str.split(" - ")[0]
            
            pay_method = col2.selectbox("Payment Method", ["Check", "Cash"])
            
            bank_accounts = [
                ("10310", "Cash in Bank MBTC"),
                ("10320", "Cash in Bank CHINA"),
                ("10330", "Cash in Bank BDO"),
                ("10340", "Cash in Bank Landbank"),
                ("10100", "Cash on Hand")
            ]
            
            bank_choice = st.selectbox("Select Funding Cash/Bank Account", [f"[{b[0]}] {b[1]}" for b in bank_accounts])
            selected_bank_code = bank_choice.split("]")[0].replace("[", "")
            selected_bank_name = bank_choice.split("]")[1].strip()
            
            prefix = "CV" if pay_method == "Check" else "CAV"
            suggested_cv = generate_voucher_number(c, "cv_number", prefix)
            
            cv_input = col3.text_input(
                "Voucher Number Sequence", 
                value=suggested_cv, 
                key=f"cv_input_{prefix}_{suggested_cv}"
            )
            
            st.info(f"""
            💡 **Accounting Entry Preview:**
            * **Debit:** Accounts Payable-Trade (Code 20100)
            * **Credit:** {selected_bank_name} (Code {selected_bank_code})
            """)
            
            if st.button("✅ Process Payment & Issue Voucher", type="primary"):
                if cv_input.strip():
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    selected_pay = pay_df[pay_df['APV Number'] == apv_to_pay].iloc[0]
                    pay_amt = float(selected_pay['Total Amount'])
                    po_no = selected_pay['PO Number']
                    supplier_name = selected_pay['Supplier']
                    proj_name = selected_pay['Project']
                    
                    po_details = c.execute("SELECT activity, Description FROM requests WHERE pono = ?", (po_no,)).fetchall()
                    po_desc_string = ""
                    
                    if po_details:
                        desc_parts = []
                        for act, part in po_details:
                            item_desc = " - ".join([str(x) for x in [act, part] if x])
                            if item_desc:
                                if len(item_desc) > 30:
                                    item_desc = item_desc[:25] + "..."
                                desc_parts.append(item_desc)
                        if desc_parts:
                            po_desc_string = " - " + " | ".join(desc_parts)
                    
                    cv_debit_desc = f"Settlement of APV #{apv_to_pay} ({supplier_name}){po_desc_string}"
                    cv_credit_desc = f"Payment release via {pay_method}{po_desc_string}"
                    
                    c.execute("""
                        UPDATE deliveries 
                        SET payment_status = 'Paid', cv_number = ?, cv_date = ?, payment_method = ?
                        WHERE apv_number = ?
                    """, (cv_input.strip(), current_time, pay_method, apv_to_pay))
                    
                    c.execute("UPDATE requests SET payment_status = 'Paid' WHERE pono = ?", (po_no,))
                    
                    c.execute("""
                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                        VALUES (?, ?, '20100', 'Accounts Payable-Trade', ?, 0.0, ?, ?, ?)
                    """, (current_time, cv_input.strip(), pay_amt, apv_to_pay, cv_debit_desc, proj_name))
                    
                    c.execute("""
                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                        VALUES (?, ?, ?, ?, 0.0, ?, ?, ?, ?)
                    """, (current_time, cv_input.strip(), selected_bank_code, selected_bank_name, pay_amt, apv_to_pay, cv_credit_desc, proj_name))
                    
                    conn.commit()
                    st.success(f"🎉 Voucher {cv_input.strip()} completed! Payment cleared for APV #{apv_to_pay}.")
                    st.rerun()
                else:
                    st.error("⚠️ Please enter a valid Check Voucher Number.")
        else:
            st.success("🎉 No outstanding vouchered payables waiting for payment!")

        # --- PETTY CASH LIQUIDATION EXPANDER ---
        st.markdown("---")
        with st.expander("🧾 Process Petty Cash Liquidation / Direct Expense Reimbursement"):
            # Auto-increment PCV number directly from journal_entries
            pcv_row = c.execute("SELECT MAX(voucher_no) FROM journal_entries WHERE voucher_no LIKE 'PCV-%'").fetchone()
            if pcv_row and pcv_row[0]:
                try:
                    last_num = int(pcv_row[0].split('-')[-1])
                    suggested_pcv = f"PCV-{(last_num + 1):05d}"
                except ValueError:
                    suggested_pcv = "PCV-00001"
            else:
                suggested_pcv = "PCV-00001"

            with st.form("petty_cash_form", clear_on_submit=True):
                pc_col1, pc_col2, pc_col3, pc_col4 = st.columns(4)
                
                pc_v_num_input = pc_col1.text_input(
                    "Voucher Number", 
                    value=suggested_pcv, 
                    key=f"pcv_num_{suggested_pcv}"
                )
                payee_name = pc_col2.text_input("Payee / Custodian Name")
                or_number = pc_col3.text_input("OR / Receipt Ref Number")
                
                projects_query = c.execute("SELECT DISTINCT project_name FROM deliveries WHERE project_name IS NOT NULL AND project_name != ''").fetchall()
                project_options = [p[0] for p in projects_query] if projects_query else ["General Head Office"]
                pc_project = pc_col4.selectbox("Project Site Tagging", project_options)
                
                pc_col5, pc_col6 = st.columns(2)
                pc_amount = pc_col5.number_input("Liquidation Amount (₱)", min_value=0.0, step=100.0, format="%.2f")
                
                exp_accounts = c.execute("SELECT account_code, account_name FROM chart_of_accounts WHERE account_type = 'Expense'").fetchall()
                exp_opts = [f"[{acc[0]}] {acc[1]}" for acc in exp_accounts] if exp_accounts else ["60200 - Direct Cost Materials"]
                pc_expense_account = pc_col6.selectbox("Expense Category (Debit)", exp_opts)
                
                pc_desc = st.text_area("Particulars / Purpose of Expense", height=70)
                
                submit_pc = st.form_submit_button("⚡ Post Petty Cash Liquidation", type="primary")
                if submit_pc:
                    if payee_name.strip() and pc_amount > 0 and pc_v_num_input.strip():
                        cur_dt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        e_code = pc_expense_account.split("]")[0].replace("[", "")
                        e_name = pc_expense_account.split("]")[1].strip()
                        
                        desc_full = f"Petty Cash: {pc_desc.strip()} (Payee: {payee_name}, OR: {or_number}, Site: {pc_project})"
                        
                        # Debit Expense
                        c.execute("""
                            INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                            VALUES (?, ?, ?, ?, ?, 0.0, ?, ?, ?)
                        """, (cur_dt, pc_v_num_input.strip(), e_code, e_name, pc_amount, or_number, desc_full, pc_project))
                        
                        # Credit Cash on Hand
                        c.execute("""
                            INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                            VALUES (?, ?, '10100', 'Cash on Hand', 0.0, ?, ?, ?, ?)
                        """, (cur_dt, pc_v_num_input.strip(), pc_amount, or_number, desc_full, pc_project))
                        
                        conn.commit()
                        st.success(f"🎉 Petty Cash Voucher {pc_v_num_input.strip()} posted successfully for ₱{pc_amount:,.2f}!")
                        st.rerun()
                    else:
                        st.error("⚠️ Payee Name, Voucher Number, and a valid Amount greater than 0 are required.")

        # --- TAB 2: UPDATE CHEQUE DATE & NUMBER EXPANDER ---
        st.markdown("---")
        with st.expander("✏️ Update Cheque Date / Cheque Number for Issued Vouchers"):
            issued_cv_rows = c.execute("""
                SELECT cv_number, supplier, total_amount, cheque_no, cheque_date 
                FROM deliveries 
                WHERE cv_number IS NOT NULL AND cv_number != ''
                ORDER BY cv_date DESC
            """).fetchall()
            
            if issued_cv_rows:
                cv_list = [f"{r[0]} - {r[1]} (₱{r[2]:,.2f})" for r in issued_cv_rows]
                selected_cv_str = st.selectbox("Select Voucher to Update", cv_list)
                target_cv_no = selected_cv_str.split(" - ")[0]
                
                # Retrieve current details
                cur_row = [r for r in issued_cv_rows if r[0] == target_cv_no][0]
                existing_cnum = cur_row[3] if cur_row[3] else ""
                existing_cdate = cur_row[4] if cur_row[4] else ""
                
                col_u1, col_u2 = st.columns(2)
                updated_cnum = col_u1.text_input("Cheque Number", value=existing_cnum, key=f"cnum_{target_cv_no}")
                
                # Checkbox allowing accounting to toggle whether the cheque is dated yet
                has_date = col_u2.checkbox("Set Exact Cheque Date", value=bool(existing_cdate))
                
                if has_date:
                    try:
                        default_dt = datetime.strptime(existing_cdate, "%Y-%m-%d").date()
                    except Exception:
                        default_dt = datetime.now().date()
                    updated_cdate_input = col_u2.date_input("Cheque Date", value=default_dt)
                    final_cdate_str = updated_cdate_input.strftime("%Y-%m-%d")
                else:
                    final_cdate_str = ""

                if st.button("💾 Save Cheque Details", type="primary"):
                    c.execute("""
                        UPDATE deliveries 
                        SET cheque_no = ?, cheque_date = ? 
                        WHERE cv_number = ?
                    """, (updated_cnum.strip(), final_cdate_str, target_cv_no))
                    conn.commit()
                    st.success(f"🎉 Cheque details updated for {target_cv_no}!")
                    st.rerun()
            else:
                st.info("No issued vouchers available to update.")

        #============================================================
        # --- TAB 2: ISSUED VOUCHERS LIST ---
        st.markdown("---")
        st.subheader("🖨️ Issued Check / Payment Vouchers (Ready for Printing)")
        
        issued_cvs = c.execute("""
            SELECT cv_number, cv_date, apv_number, supplier, payment_method, total_amount, cheque_no, cheque_date 
            FROM deliveries 
            WHERE cv_number IS NOT NULL AND cv_number != ''
            ORDER BY cv_date DESC
        """).fetchall()
        
        if issued_cvs and HAS_REPORTLAB:
            for idx, cv in enumerate(issued_cvs):
                cv_no, cv_date, apv_no, supplier, pay_method, total_amt, c_num, c_date = cv
                
                st.write(f"💳 **Voucher:** {cv_no} ({pay_method}) | **Supplier:** {supplier} | **Amount:** ₱{total_amt:,.2f}")
                
                col_btn1, col_btn2 = st.columns(2)
                
                # Button 1: Full Payment Voucher Sheet
                voucher_pdf = create_cv_pdf(cv_no, cv_date, apv_no, supplier, pay_method, total_amt, conn=conn)
                col_btn1.download_button(
                    label="📄 Print Payment Voucher PDF",
                    data=voucher_pdf,
                    file_name=f"Voucher_{cv_no}.pdf",
                    mime="application/pdf",
                    key=f"print_pv_{cv_no}_{idx}"
                )
                
                # Button 2: A4 Cheque Printing
                cheque_pdf = create_cheque_pdf(supplier, total_amt, c_date)
                col_btn2.download_button(
                    label="🎟️ Print Cheque (A4)",
                    data=cheque_pdf,
                    file_name=f"Cheque_{cv_no}.pdf",
                    mime="application/pdf",
                    key=f"print_chk_{cv_no}_{idx}"
                )
                st.markdown("---")
        else:
            st.info("No issued check or payment vouchers available for printing yet.")
            #========================================================================
            
    # --- TAB 3: GENERAL LEDGER ---
    with tab_gl:
        st.write("### 📖 Real-Time General Ledger Journal Entries")
        
        gl_df = pd.read_sql_query("""
            SELECT 
                j.id AS 'Entry ID', 
                j.entry_date AS 'Date', 
                j.voucher_no AS 'Voucher No', 
                j.account_code AS 'Account Code', 
                j.account_name AS 'Account Name', 
                j.debit AS 'Debit', 
                j.credit AS 'Credit', 
                j.ref_no AS 'Ref Doc', 
                j.description AS 'Description',
                COALESCE(NULLIF(j.project_name, ''), d.project_name, '') AS 'Project Name',
                COALESCE(d.supplier, '') AS 'Supplier'
            FROM journal_entries j
            LEFT JOIN deliveries d ON (j.ref_no = d.dr_number OR j.ref_no = d.apv_number OR j.ref_no = d.cv_number)
            ORDER BY j.id DESC
        """, conn)
        
        suppliers_df = pd.read_sql_query("SELECT DISTINCT supplier FROM deliveries WHERE supplier IS NOT NULL AND supplier != '' ORDER BY supplier ASC", conn)
        supplier_list = suppliers_df['supplier'].tolist() if not suppliers_df.empty else []

        if not gl_df.empty:
            st.markdown("---")
            st.subheader("🔍 Filter & Subsummary")
            
            col_f1, col_f2, col_f3 = st.columns(3)
            
            all_accounts = ["All Account Titles"] + sorted(gl_df['Account Name'].dropna().unique().tolist())
            selected_account = col_f1.selectbox("Filter by Account Title", all_accounts, key="gl_filter_acc")
            
            all_suppliers = ["All Suppliers"] + sorted(supplier_list)
            selected_supplier = col_f2.selectbox("Filter by Supplier", all_suppliers, key="gl_filter_sup")
            
            project_list = sorted([str(p) for p in gl_df['Project Name'].dropna().unique().tolist() if str(p).strip() != ''])
            all_projects = ["All Projects"] + project_list
            selected_project = col_f3.selectbox("Filter by Project", all_projects, key="gl_filter_proj")
            
            filtered_df = gl_df.copy()
            
            if selected_account != "All Account Titles":
                filtered_df = filtered_df[filtered_df['Account Name'] == selected_account]
                
            if selected_supplier != "All Suppliers":
                filtered_df = filtered_df[
                    (filtered_df['Supplier'] == selected_supplier) | 
                    (filtered_df['Description'].str.contains(selected_supplier, case=False, na=False))
                ]
                
            if selected_project != "All Projects":
                filtered_df = filtered_df[filtered_df['Project Name'] == selected_project]

            sub_debit = filtered_df["Debit"].sum()
            sub_credit = filtered_df["Credit"].sum()
            sub_net = sub_debit - sub_credit

            m1, m2, m3 = st.columns(3)
            m1.metric("Filtered Total Debits", f"₱{sub_debit:,.2f}")
            m2.metric("Filtered Total Credits", f"₱{sub_credit:,.2f}")
            m3.metric("Net Activity (Debit - Credit)", f"₱{sub_net:,.2f}")
            
            st.markdown("---")
            
            display_df = filtered_df.drop(columns=['Supplier'])
            st.dataframe(
                display_df.style.format({"Debit": "₱{:,.2f}", "Credit": "₱{:,.2f}"}), 
                use_container_width=True, 
                hide_index=True
            )

            csv_gl = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Filtered General Ledger as CSV",
                data=csv_gl,
                file_name=f"general_ledger_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No journal entries posted yet. Generate an APV or CV to trigger automated entries.")

    # --- TAB 4: FINANCIAL STATEMENTS ---
    with tab_fs:
        st.write("### 📈 Financial Statements & Performance Reports")
        
        fs_tab1, fs_tab2 = st.tabs(["Income Statement", "Balance Sheet"])

        with fs_tab1:
            st.subheader("Income Statement (Profit & Loss)")
            col1, col2 = st.columns(2)
            start_d = col1.date_input("Start Date", pd.to_datetime("2026-01-01"))
            end_d = col2.date_input("End Date", pd.to_datetime("2026-12-31"))

            df_is = get_income_statement(conn, start_d, end_d)
            
            rev_df = df_is[df_is['account_type'] == 'Revenue']
            exp_df = df_is[df_is['account_type'] == 'Expense']
            
            total_rev = rev_df['amount'].sum() if not rev_df.empty else 0.0
            total_exp = exp_df['amount'].sum() if not exp_df.empty else 0.0
            net_income = total_rev - total_exp

            st.markdown("**Revenues**")
            st.dataframe(rev_df[['account_code', 'account_name', 'amount']].rename(
                columns={'account_code': 'Code', 'account_name': 'Account', 'amount': 'Amount (₱)'}
            ), use_container_width=True, hide_index=True)
            st.metric("Total Revenue", f"₱{total_rev:,.2f}")

            st.markdown("**Expenses & Costs**")
            st.dataframe(exp_df[['account_code', 'account_name', 'amount']].rename(
                columns={'account_code': 'Code', 'account_name': 'Account', 'amount': 'Amount (₱)'}
            ), use_container_width=True, hide_index=True)
            st.metric("Total Expenses", f"₱{total_exp:,.2f}")
            
            st.divider()
            st.metric("NET INCOME / (LOSS)", f"₱{net_income:,.2f}")

        with fs_tab2:
            st.subheader("Balance Sheet")
            as_of = st.date_input("As of Date", pd.to_datetime("2026-12-31"))

            df_bs = get_balance_sheet(conn, as_of)
            
            df_is_till_date = get_income_statement(conn, "1900-01-01", as_of)
            rev_until = df_is_till_date[df_is_till_date['account_type'] == 'Revenue']['amount'].sum() if not df_is_till_date.empty else 0.0
            exp_until = df_is_till_date[df_is_till_date['account_type'] == 'Expense']['amount'].sum() if not df_is_till_date.empty else 0.0
            current_net_income = rev_until - exp_until

            assets = df_bs[df_bs['account_type'] == 'Asset']
            liabilities = df_bs[df_bs['account_type'] == 'Liability']
            equity = df_bs[df_bs['account_type'] == 'Equity']

            tot_assets = assets['amount'].sum() if not assets.empty else 0.0
            tot_liab = liabilities['amount'].sum() if not liabilities.empty else 0.0
            tot_equity = (equity['amount'].sum() if not equity.empty else 0.0) + current_net_income

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Assets**")
                st.dataframe(assets[['account_code', 'account_name', 'amount']].rename(
                    columns={'account_code': 'Code', 'account_name': 'Account', 'amount': 'Amount (₱)'}
                ), use_container_width=True, hide_index=True)
                st.metric("Total Assets", f"₱{tot_assets:,.2f}")

            with col_b:
                st.markdown("**Liabilities**")
                st.dataframe(liabilities[['account_code', 'account_name', 'amount']].rename(
                    columns={'account_code': 'Code', 'account_name': 'Account', 'amount': 'Amount (₱)'}
                ), use_container_width=True, hide_index=True)
                st.metric("Total Liabilities", f"₱{tot_liab:,.2f}")
                
                st.markdown("**Equity**")
                st.dataframe(equity[['account_code', 'account_name', 'amount']].rename(
                    columns={'account_code': 'Code', 'account_name': 'Account', 'amount': 'Amount (₱)'}
                ), use_container_width=True, hide_index=True)
                st.write(f"Current Period Net Profit: **₱{current_net_income:,.2f}**")
                st.metric("Total Equity", f"₱{tot_equity:,.2f}")

            st.divider()
            balanced = abs(tot_assets - (tot_liab + tot_equity)) < 0.01
            if balanced:
                st.success(f"Balance Check Passed: Total Assets (₱{tot_assets:,.2f}) = Liabilities + Equity (₱{tot_liab + tot_equity:,.2f})")
            else:
                st.error(f"⚠️ Unbalanced! Assets: ₱{tot_assets:,.2f} | Liabilities + Equity: ₱{tot_liab + tot_equity:,.2f}")

# --- ROLE 6: ADMIN VIEW ALL ---
elif role == "Admin View All":
    st.subheader("🛡️ Admin Dashboard & Analytics")

    tab_settings, tab_reports, tab_payables = st.tabs(["⚙️ Master Database & Settings", "📊 Project Approved Reports", "💸 Accounts Payable"])

    with tab_settings:
        st.write("### ⚙️ Admin Settings & Configuration")
        
        with st.expander("👥 Manage System Users"):
            st.write("#### 👤 Add, Edit, or Remove Users")
            users_df = pd.read_sql_query("SELECT id, username, password, role1, role2, role3, role4, role5, role6, status, can_add_act, can_add_item FROM users", conn)
            
            role_options = ["", "Requisitor", "Purchaser", "Approver", "Office Manager", "Accounting", "Admin View All"]
            yes_no_options = ["Yes", "No"]
            
            edited_users = st.data_editor(
                users_df,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": None, 
                    "username": st.column_config.TextColumn("Username", required=True),
                    "password": st.column_config.TextColumn("Password", required=True),
                    "role1": st.column_config.SelectboxColumn("Role 1", options=role_options),
                    "role2": st.column_config.SelectboxColumn("Role 2", options=role_options),
                    "role3": st.column_config.SelectboxColumn("Role 3", options=role_options),
                    "role4": st.column_config.SelectboxColumn("Role 4", options=role_options),
                    "role5": st.column_config.SelectboxColumn("Role 5", options=role_options),
                    "role6": st.column_config.SelectboxColumn("Role 6", options=role_options),
                    "status": st.column_config.SelectboxColumn("Status", options=["Active", "Inactive"], default="Active"),
                    "can_add_act": st.column_config.SelectboxColumn("Can Add Act?", options=yes_no_options, default="No"),
                    "can_add_item": st.column_config.SelectboxColumn("Can Add Item?", options=yes_no_options, default="No")
                }
            )
            
            if st.button("💾 Save User Changes", type="primary"):
                c.execute("DELETE FROM users")
                for _, row in edited_users.iterrows():
                    username_val = str(row['username']).strip() if pd.notnull(row['username']) else ""
                    if username_val:
                        r1 = str(row.get('role1', '')) if pd.notnull(row.get('role1')) else ''
                        r2 = str(row.get('role2', '')) if pd.notnull(row.get('role2')) else ''
                        r3 = str(row.get('role3', '')) if pd.notnull(row.get('role3')) else ''
                        r4 = str(row.get('role4', '')) if pd.notnull(row.get('role4')) else ''
                        r5 = str(row.get('role5', '')) if pd.notnull(row.get('role5')) else ''
                        r6 = str(row.get('role6', '')) if pd.notnull(row.get('role6')) else ''
                        status = str(row.get('status', 'Active')) if pd.notnull(row.get('status')) else 'Active'
                        can_add_act = str(row.get('can_add_act', 'No')) if pd.notnull(row.get('can_add_act')) else 'No'
                        can_add_item = str(row.get('can_add_item', 'No')) if pd.notnull(row.get('can_add_item')) else 'No'
                        pwd = str(row.get('password', '1234')) if pd.notnull(row.get('password')) else '1234'
                        
                        c.execute("""
                            INSERT INTO users (username, password, role1, role2, role3, role4, role5, role6, status, can_add_act, can_add_item)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            username_val, pwd, 
                            r1, r2, r3, r4, r5, r6, status, can_add_act, can_add_item
                        ))
                conn.commit()
                st.success("User database updated successfully!")
                st.rerun()

        with st.expander("➕ Add New Project"):
            new_proj = st.text_input("Project Name")
            if st.button("Save Project"):
                if new_proj.strip():
                    c.execute("INSERT OR IGNORE INTO projects (project_name) VALUES (?)", (new_proj.strip(),))
                    conn.commit()
                    st.success(f"Project '{new_proj}' added!")
                    st.rerun()

        with st.expander("🏗️ Manage Project Activities"):
            st.write("#### 📝 Edit & Manage Project Activities")
            projects_list = [p[0] for p in c.execute("SELECT project_name FROM projects").fetchall()]
            if not projects_list:
                projects_list = ["No projects available"]
            sel_proj_act = st.selectbox("Select Project for Activity", projects_list, key="sel_proj_editable")
            
            if sel_proj_act and sel_proj_act != "No projects available":
                proj_row = c.execute("SELECT id FROM projects WHERE project_name = ?", (sel_proj_act,)).fetchone()
                if proj_row:
                    project_id = proj_row[0]
                    
                    st.markdown("---")
                    st.write(f"#### 📋 Editable Activity List for: *{sel_proj_act}*")
                    
                    acts_df = pd.read_sql_query("""
                        SELECT 
                            id,
                            activity_name AS 'Activity Name', 
                            qty AS 'Qty',
                            unit AS 'Unit',
                            contract_amount AS 'Contract Amount'
                        FROM activities 
                        WHERE project_id = ? 
                        ORDER BY id ASC
                    """, conn, params=(project_id,))
                    
                    if not acts_df.empty:
                        edited_acts_df = st.data_editor(
                            acts_df,
                            use_container_width=True,
                            hide_index=True,
                            num_rows="dynamic",
                            column_config={
                                "id": None,
                                "Qty": st.column_config.NumberColumn("Qty", min_value=0.0, step=0.01, format="%.2f"),
                                "Contract Amount": st.column_config.NumberColumn("Contract Amount", min_value=0.0, step=100.0, format="₱%.2f")
                            }
                        )
                        
                        col_save, col_metric = st.columns([1, 2])
                        if col_save.button("💾 Save Table Changes", type="primary"):
                            for _, row in edited_acts_df.iterrows():
                                act_id = row['id']
                                act_name = str(row['Activity Name']).strip() if pd.notnull(row['Activity Name']) else ""
                                act_qty = float(row['Qty']) if pd.notnull(row['Qty']) else 1.0
                                act_unit = str(row['Unit']).strip() if pd.notnull(row['Unit']) else "lot"
                                act_amt = float(row['Contract Amount']) if pd.notnull(row['Contract Amount']) else 0.0
                                
                                if pd.notnull(act_id):
                                    c.execute("""
                                        UPDATE activities 
                                        SET activity_name = ?, qty = ?, unit = ?, contract_amount = ?
                                        WHERE id = ?
                                    """, (act_name, act_qty, act_unit, act_amt, act_id))
                                elif act_name:
                                    c.execute("""
                                        INSERT INTO activities (project_id, activity_name, qty, unit, contract_amount)
                                        VALUES (?, ?, ?, ?, ?)
                                    """, (project_id, act_name, act_qty, act_unit, act_amt))
                            
                            original_ids = acts_df['id'].dropna().tolist()
                            current_ids = edited_acts_df['id'].dropna().tolist()
                            deleted_ids = [old_id for old_id in original_ids if old_id not in current_ids]
                            for d_id in deleted_ids:
                                c.execute("DELETE FROM activities WHERE id = ?", (d_id,))
                            
                            conn.commit()
                            st.success("Changes successfully saved to database!")
                            st.rerun()
                            
                        acts_df['Implementing Amount'] = acts_df['Contract Amount'] * 0.42
                        total_contract = acts_df['Contract Amount'].sum()
                        total_implementing = acts_df['Implementing Amount'].sum()
                        col_metric.markdown(f"**Total Contract:** ₱{total_contract:,.2f} | **Total Implementing (42%):** ₱{total_implementing:,.2f}")
                    else:
                        st.info("No activities registered yet for this project.")
                    
                    st.markdown("---")
                    st.write("#### ➕ Add New Activity")
                    ac1, ac2, ac3, ac4 = st.columns([3, 1, 1, 2])
                    new_act = ac1.text_input("Activity Name / Description", key="new_act_name")
                    new_qty = ac2.number_input("Qty", min_value=0.0, value=1.0, step=1.0, key="new_act_qty")
                    new_unit = ac3.text_input("Unit", value="lot", key="new_act_unit")
                    new_amt = ac4.number_input("Contract Amount", min_value=0.0, step=100.0, key="new_act_amt")
                    
                    if st.button("➕ Add Activity", type="primary", key="btn_add_activity"):
                        if new_act.strip():
                            c.execute("""
                                INSERT INTO activities (project_id, activity_name, qty, unit, contract_amount)
                                VALUES (?, ?, ?, ?, ?)
                            """, (project_id, new_act.strip(), new_qty, new_unit.strip(), new_amt))
                            conn.commit()
                            st.success(f"Activity '{new_act}' added to project '{sel_proj_act}'!")
                            st.rerun()
                        else:
                            st.warning("Please enter an activity name.")

        with st.expander("📦 Manage Materials Master List"):
            st.write("#### 📝 Edit & Manage Materials")
            mats_df = pd.read_sql_query("SELECT item_no, description, unit, category FROM materials", conn)
            edited_mats = st.data_editor(
                mats_df,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "item_no": st.column_config.TextColumn("Item No.", required=True),
                    "description": st.column_config.TextColumn("Description", required=True),
                    "unit": st.column_config.TextColumn("Unit", default="PCS"),
                    "category": st.column_config.SelectboxColumn("Category", options=["Direct Materials", "Equipment & Rental", "Tools & Consumables", "Fuel & Lubricants", "Subcontract & Services"], default="Direct Materials")
                }
            )
            if st.button("💾 Save Materials List", type="primary"):
                c.execute("DELETE FROM materials")
                for _, r in edited_mats.iterrows():
                    item_no = str(r['item_no']).strip() if pd.notnull(r['item_no']) else ""
                    desc = str(r['description']).strip() if pd.notnull(r['description']) else ""
                    unit = str(r['unit']).strip() if pd.notnull(r['unit']) else "PCS"
                    cat = str(r['category']).strip() if pd.notnull(r['category']) else "Direct Materials"
                    if item_no and desc:
                        c.execute("INSERT OR REPLACE INTO materials (item_no, description, unit, category) VALUES (?, ?, ?, ?)", (item_no, desc, unit, cat))
                conn.commit()
                st.success("Materials list updated!")
                st.rerun()

        with st.expander("🏬 Manage Suppliers Master List"):
            st.write("#### 📝 Edit & Manage Suppliers")
            sups_df = pd.read_sql_query("SELECT id, supplier_name, location, contact_person, contact_number, tin_number, vat_type, terms_days FROM suppliers", conn)
            edited_sups = st.data_editor(
                sups_df,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                column_config={"id": None}
            )
            if st.button("💾 Save Suppliers List", type="primary"):
                c.execute("DELETE FROM suppliers")
                for _, r in edited_sups.iterrows():
                    s_name = str(r['supplier_name']).strip() if pd.notnull(r['supplier_name']) else ""
                    if s_name:
                        c.execute("""
                            INSERT INTO suppliers (supplier_name, location, contact_person, contact_number, tin_number, vat_type, terms_days)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            s_name,
                            str(r.get('location', '') or ''),
                            str(r.get('contact_person', '') or ''),
                            str(r.get('contact_number', '') or ''),
                            str(r.get('tin_number', '') or ''),
                            str(r.get('vat_type', '') or 'VAT Registered'),
                            int(r.get('terms_days', 0) or 0)
                        ))
                conn.commit()
                st.success("Suppliers list updated!")
                st.rerun()

        with st.expander("✍️ Manage Signatories"):
            sigs_df = pd.read_sql_query("SELECT id, name, role, signature_path FROM signatories", conn)
            edited_sigs = st.data_editor(sigs_df, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"id": None})
            if st.button("💾 Save Signatories"):
                c.execute("DELETE FROM signatories")
                for _, r in edited_sigs.iterrows():
                    if pd.notnull(r['name']) and str(r['name']).strip():
                        c.execute("INSERT INTO signatories (name, role, signature_path) VALUES (?, ?, ?)",
                                  (str(r['name']).strip(), str(r['role']).strip(), str(r['signature_path']).strip()))
                conn.commit()
                st.success("Signatories updated!")
                st.rerun()

    with tab_reports:
        st.write("### 📊 Comprehensive Project Reports")
        all_reqs = pd.read_sql_query("""
            SELECT id, timestamp, project_name, activity, item_no, description, category, qty, unit, price, amount, requester_name, supplier, pono, status, received_status, payment_status
            FROM requests ORDER BY id DESC
        """, conn)
        st.dataframe(all_reqs, use_container_width=True, hide_index=True)
        
        csv_reqs = all_reqs.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export All Request Records (CSV)",
            data=csv_reqs,
            file_name=f"all_requests_report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    with tab_payables:
        st.write("### 💸 Master Accounts Payable Overview")
        del_ap = pd.read_sql_query("""
            SELECT id, pono, dr_number, supplier, project_name, total_amount, received_date, apv_number, cv_number, payment_status, payment_method
            FROM deliveries ORDER BY id DESC
        """, conn)
        st.dataframe(del_ap.style.format({"total_amount": "₱{:,.2f}"}), use_container_width=True, hide_index=True)
        
        csv_ap = del_ap.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Accounts Payable Report (CSV)",
            data=csv_ap,
            file_name=f"accounts_payable_report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
