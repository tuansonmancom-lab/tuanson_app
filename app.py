import sqlite3
import pandas as pd
import streamlit as st
import re
import os
from datetime import datetime
from io import BytesIO

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

    # Safely register fonts if files exist; fallback to Helvetica if missing
    if os.path.exists('Roboto-Regular.ttf') and os.path.exists('Roboto-Bold.ttf'):
        pdfmetrics.registerFont(TTFont('Roboto', 'Roboto-Regular.ttf'))
        pdfmetrics.registerFont(TTFont('Roboto-Bold', 'Roboto-Bold.ttf'))
        addMapping('Roboto', 0, 0, 'Roboto')       # Normal
        addMapping('Roboto', 1, 0, 'Roboto-Bold')  # Bold
        DEFAULT_FONT = 'Roboto'
        DEFAULT_BOLD_FONT = 'Roboto-Bold'
    else:
        DEFAULT_FONT = 'Helvetica'
        DEFAULT_BOLD_FONT = 'Helvetica-Bold'

    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


# --- HELPER FUNCTIONS ---
def generate_voucher_number(cursor, column_name, prefix):
    """
    Robustly finds the highest sequence number for a given prefix (e.g., APV, CV, CAV)
    across all relevant tables and columns, ensuring correct sequencing.
    """
    max_num = 0
    queries = [
        f"SELECT {column_name} FROM deliveries WHERE {column_name} IS NOT NULL AND {column_name} LIKE '{prefix}-%'",
        f"SELECT voucher_no FROM journal_entries WHERE voucher_no IS NOT NULL AND voucher_no LIKE '{prefix}-%'"
    ]
    
    for q in queries:
        try:
            cursor.execute(q)
            rows = cursor.fetchall()
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
        pass

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
                FOREIGN KEY(project_id) REFERENCES projects(id))''')

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
                requester_name TEXT,
                rejection_reason TEXT)''')

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


# --- PDF GENERATOR FUNCTIONS ---
def create_po_pdf(pono, date_str, supplier, project, po_items):
    if not HAS_REPORTLAB:
        return None

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
        "TUANSON CONSTRUCTION 162 P. Labuca St., Cansojong, Talisay City, Cebu Tel: 032 273-1187"
        "web: [www.tuansoncons.com](https://www.tuansoncons.com), email: ric_tuanson@yahoo.com.ph",
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
        [Paragraph("PURCHASE ORDER", po_title_style), Paragraph(f"P.O. NO.      {pono}", po_no_style)]
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
        Paragraph("*************NF*************", center_cell_style),
        Paragraph("*************NF*************", center_cell_style),
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
    
    prep_element = Paragraph(f"{prep_name}Prepared by:", center_cell_style)
    if prep_sig_path and os.path.exists(prep_sig_path):
        prep_img = Image(prep_sig_path, width=90, height=30)
        prep_element = [prep_img, Paragraph(f"{prep_name}Prepared by:", center_cell_style)]
        
    appr_element = Paragraph(f"{appr_name}Approved by:", center_cell_style)
    if appr_sig_path and os.path.exists(appr_sig_path):
        appr_img = Image(appr_sig_path, width=90, height=30)
        appr_element = [appr_img, Paragraph(f"{appr_name}Approved by:", center_cell_style)]

    footer_data = [
        [
            Paragraph("NOTES:", cell_style),
            "",
            Paragraph("GRAND TOTAL:", right_cell_style),
            Paragraph(f"P {grand_total:,.2f}", right_cell_style)
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
            Paragraph(f"Date Print: {current_time_str}", right_cell_style)
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

def create_apv_pdf(apv_no, apv_date, dr_number, po_number, supplier, project, total_amount, conn=None):
    if not HAS_REPORTLAB:
        return None
        
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    
    title_style = ParagraphStyle('Title', fontName=DEFAULT_BOLD_FONT, fontSize=16, leading=18, alignment=1, textColor=colors.HexColor("#CC0000"))
    subtitle_style = ParagraphStyle('Subtitle', fontName=DEFAULT_FONT, fontSize=8, leading=10, alignment=1)
    normal_style = ParagraphStyle('Normal', fontName=DEFAULT_FONT, fontSize=9, leading=12)
    bold_style = ParagraphStyle('Bold', fontName=DEFAULT_BOLD_FONT, fontSize=9, leading=12)
    
    header_style = ParagraphStyle('HeaderStyle', fontName=DEFAULT_BOLD_FONT, fontSize=9, textColor=colors.white)
    right_align_normal = ParagraphStyle('RightNormal', fontName=DEFAULT_FONT, fontSize=9, alignment=2)
    right_align_bold = ParagraphStyle('RightBold', fontName=DEFAULT_BOLD_FONT, fontSize=9, alignment=2)
    
    elements.append(Paragraph("TUANSON CONSTRUCTION", title_style))
    elements.append(Paragraph("Accounts Payable Voucher (APV)", subtitle_style))
    elements.append(Spacer(1, 15))
    
    meta_data = [
        [Paragraph("APV NO:", bold_style), Paragraph(str(apv_no), normal_style), Paragraph("APV DATE:", bold_style), Paragraph(str(apv_date), normal_style)],
        [Paragraph("SUPPLIER:", bold_style), Paragraph(str(supplier), normal_style), Paragraph("PROJECT:", bold_style), Paragraph(str(project), normal_style)],
        [Paragraph("PO NUMBER:", bold_style), Paragraph(str(po_number), normal_style), Paragraph("DR NUMBER:", bold_style), Paragraph(str(dr_number), normal_style)]
    ]
    meta_table = Table(meta_data, colWidths=[90, 180, 90, 180])
    meta_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    elements.append(meta_table)
    elements.append(Spacer(1, 15))
    
    elements.append(Paragraph("Accounting Entries (General Ledger Distribution)", bold_style))
    elements.append(Spacer(1, 8))
    
    table_data = [
        [Paragraph("Account Code & Name", header_style), 
         Paragraph("Description", header_style), 
         Paragraph("Debit ₱", header_style), 
         Paragraph("Credit ₱", header_style)],
         
        [Paragraph("60200 - Direct Cost Materials", normal_style), 
         Paragraph(f"APV setup for DR #{dr_number} ({supplier})", normal_style), 
         Paragraph(f"₱{total_amount:,.2f}", right_align_normal), 
         Paragraph("-", right_align_normal)],
         
        [Paragraph("20100 - Accounts Payable-Trade", normal_style), 
         Paragraph(f"APV liability accrued for DR #{dr_number}", normal_style), 
         Paragraph("-", right_align_normal), 
         Paragraph(f"₱{total_amount:,.2f}", right_align_normal)],
         
        [Paragraph("TOTAL", bold_style), 
         "", 
         Paragraph(f"₱{total_amount:,.2f}", right_align_bold), 
         Paragraph(f"₱{total_amount:,.2f}", right_align_bold)]
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

def create_cv_pdf(cv_no, cv_date, apv_no, supplier, payment_method, total_amount):
    if not HAS_REPORTLAB:
        return None

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    
    title_style = ParagraphStyle('Title', fontName=DEFAULT_BOLD_FONT, fontSize=16, leading=18, alignment=1, textColor=colors.HexColor("#CC0000"))
    subtitle_style = ParagraphStyle('Subtitle', fontName=DEFAULT_FONT, fontSize=8, leading=10, alignment=1)
    normal_style = ParagraphStyle('Normal', fontName=DEFAULT_FONT, fontSize=9, leading=12)
    bold_style = ParagraphStyle('Bold', fontName=DEFAULT_BOLD_FONT, fontSize=9, leading=12)
    
    header_style = ParagraphStyle('HeaderStyle', fontName=DEFAULT_BOLD_FONT, fontSize=9, textColor=colors.white)
    right_align_normal = ParagraphStyle('RightNormal', fontName=DEFAULT_FONT, fontSize=9, alignment=2)
    right_align_bold = ParagraphStyle('RightBold', fontName=DEFAULT_BOLD_FONT, fontSize=9, alignment=2)
    
    elements.append(Paragraph("TUANSON CONSTRUCTION", title_style))
    elements.append(Paragraph(f"Check / Payment Voucher ({payment_method})", subtitle_style))
    elements.append(Spacer(1, 15))
    
    meta_data = [
        [Paragraph("VOUCHER NO:", bold_style), Paragraph(str(cv_no), normal_style), Paragraph("DATE:", bold_style), Paragraph(str(cv_date), normal_style)],
        [Paragraph("PAYEE / SUPPLIER:", bold_style), Paragraph(str(supplier), normal_style), Paragraph("PAYMENT METHOD:", bold_style), Paragraph(str(payment_method), normal_style)],
        [Paragraph("REF APV NO:", bold_style), Paragraph(str(apv_no), normal_style), "", ""]
    ]
    meta_table = Table(meta_data, colWidths=[90, 180, 90, 180])
    meta_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('SPAN', (1,2), (3,2)), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    elements.append(meta_table)
    elements.append(Spacer(1, 15))
    
    elements.append(Paragraph("Accounting Entries (General Ledger Distribution)", bold_style))
    elements.append(Spacer(1, 8))
    
    table_data = [
        [Paragraph("Account Code & Name", header_style), 
         Paragraph("Description", header_style), 
         Paragraph("Debit (₱)", header_style), 
         Paragraph("Credit (₱)", header_style)],
         
        [Paragraph("20100 - Accounts Payable-Trade", normal_style), 
         Paragraph(f"Payment settlement for APV #{apv_no} to {supplier}", normal_style), 
         Paragraph(f"₱{total_amount:,.2f}", right_align_normal), 
         Paragraph("-", right_align_normal)],
         
        [Paragraph("10100 - Cash in Bank", normal_style), 
         Paragraph(f"Payment issued via {payment_method}", normal_style), 
         Paragraph("-", right_align_normal), 
         Paragraph(f"₱{total_amount:,.2f}", right_align_normal)],
         
        [Paragraph("TOTAL", bold_style), 
         "", 
         Paragraph(f"₱{total_amount:,.2f}", right_align_bold), 
         Paragraph(f"₱{total_amount:,.2f}", right_align_bold)]
    ]
    
    cv_table = Table(table_data, colWidths=[160, 200, 90, 90])
    cv_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c4356')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,-1), (-1,-1), colors.whitesmoke)
    ]))
    
    elements.append(cv_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def create_payment_voucher_pdf(cv_no, cv_date, cheque_no, cheque_date, supplier, supplier_address, project_name, pono, amount, ewt_amount):
    if not HAS_REPORTLAB:
        return None

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

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
    story.append(Paragraph("Payment Voucher", ParagraphStyle('PVTitle', parent=title_style, fontSize=12, textColor=colors.black)))
    story.append(Spacer(1, 10))

    # 2. Vendor & Voucher Meta Data Table
    net_total = amount - ewt_amount
    meta_data = [[Paragraph(supplier, bold_body), Paragraph("NO.:", bold_body), Paragraph(str(cv_no), body_style)]]
    
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
    story.append(Paragraph("Journals:", bold_body))
    story.append(Paragraph("******************************", body_style))
    
    journal_data = [
        [Paragraph("Doc No.", header_style), Paragraph("Date", header_style), Paragraph("Account #", header_style), Paragraph("Account Name", header_style), Paragraph("Debit", header_style), Paragraph("Credit", header_style)],
        [Paragraph(str(cv_no), body_style), Paragraph(str(cv_date), body_style), Paragraph("VEN-M0034", body_style), Paragraph(f"VEN-M0034: {supplier}", body_style), Paragraph(f"₱{amount:,.2f}", body_style), Paragraph("-", body_style)],
        [Paragraph(str(cv_no), body_style), Paragraph(str(cv_date), body_style), Paragraph("100-0004", body_style), Paragraph("100-0004: CIB-BDO1", body_style), Paragraph("-", body_style), Paragraph(f"₱{amount:,.2f}", body_style)],
        [Paragraph("", body_style), Paragraph("", body_style), Paragraph("", body_style), Paragraph("", body_style), Paragraph(f"₱{amount:,.2f}", body_style), Paragraph(f"₱{amount:,.2f}", body_style)],
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
    story.append(Paragraph("PAYMENT DETAILS", bold_body))
    pay_details_data = [
        [Paragraph("Type", header_style), Paragraph("Doc. No.", header_style), Paragraph("Doc. Date", header_style), Paragraph("Description", header_style), Paragraph("Orig. Amount", header_style), Paragraph("Paid Amount", header_style)],
        [Paragraph("BIL", body_style), Paragraph(f"PO#{pono}", body_style), Paragraph(str(cv_date), body_style), Paragraph(f"PAYABLE FOR PURCHASE OF MATERIALS FOR {str(project_name).upper()}", body_style), Paragraph(f"{amount:,.2f}", body_style), Paragraph(f"{amount:,.2f}", body_style)],
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

    # 6. Totals & Notes Section
    totals_data = [
        [
            Paragraph(f"Notes: Less (1%) EWT ₱{ewt_amount:,.2f}", body_style),
            Paragraph("SUB TOTAL", bold_body),
            Paragraph(f"₱{amount:,.2f}", bold_body)
        ],
        [
            Paragraph("", body_style),
            Paragraph("NET TOTAL", bold_body),
            Paragraph(f"₱{net_total:,.2f}", bold_body)
        ]
    ]
    totals_table = Table(totals_data, colWidths=[340, 90, 70])
    totals_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LINEABOVE', (1,1), (-1,1), 0.5, colors.black),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 40))

    # 7. Signatures Section
    sig_data = [
        [Paragraph("Prepared By:", body_style), Paragraph("Checked By:", body_style), Paragraph("Approved By:", body_style), Paragraph("Received By:", body_style)],
        [Spacer(1, 30), Spacer(1, 30), Spacer(1, 30), Spacer(1, 30)], 
        [Paragraph("_________________", body_style), Paragraph("_________________", body_style), Paragraph("_________________", body_style), Paragraph("_________________", body_style)]
    ]
    sig_table = Table(sig_data, colWidths=[135, 135, 135, 135])
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


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
    st.title("🔒 Tuanson Construction - Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_btn = st.form_submit_button("Login")

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

        st.markdown("---")
        st.subheader("⚠️ Rejected Purchase Orders (Action Required)")

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
                    st.error(f"**Rejection Reason:** {reason if reason else 'No specific reason provided.'}") 
                    
                    po_items_df = pd.read_sql_query(
                        "SELECT id, item_no, description, qty, unit, price, amount FROM requests WHERE pono = ? AND status = 'Rejected'", 
                        conn, params=(pono,)
                    )
                    
                    st.write("Update the unit price(s) below:")

                    edited_df = st.data_editor(
                        po_items_df, 
                        disabled=["id", "item_no", "description", "qty", "unit", "amount"],
                        hide_index=True,
                        use_container_width=True,
                        column_config={"id": None},
                        key=f"edit_price_{pono}"
                    )
                    
                    if st.button("💾 Save Prices & Resubmit PO", key=f"resubmit_{pono}", type="primary"):
                        for index, row in edited_df.iterrows():
                            new_price = float(row['price'])
                            new_amount = float(row['qty']) * new_price 
                            row_id = row['id']
                            
                            c.execute("""
                                UPDATE requests
                                SET price = ?, amount = ?, status = 'Pending Approval', rejection_reason = NULL
                                WHERE id = ?
                            """, (new_price, new_amount, row_id))
                        
                        conn.commit()
                        st.success(f"PO #{pono} resubmitted successfully!")
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
            
            sub_col1, sub_col2 = recv_col2.columns([1, 2])
            doc_prefix = sub_col1.selectbox("Type", ["DR", "CSI", "SI", "OR"], key="doc_type_prefix")
            raw_doc_no = sub_col2.text_input("Document No.", placeholder="e.g. 00001", key="doc_num_raw")
            
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
                date AS 'Date & Time',
                ref_no AS 'Ref / Doc No.',
                item_description AS 'Item Description',
                qty_in AS 'Qty In',
                qty_out AS 'Qty Out',
                balance AS 'Running Balance',
                location AS 'Location / Site',
                remarks AS 'Remarks',
                status AS 'Dispatch Status'
            FROM inventory_ledger
            ORDER BY id DESC
        """, conn)

        if not ledger_df.empty:
            st.dataframe(
                ledger_df.style.format({
                    "Qty In": "{:,.2f}",
                    "Qty Out": "{:,.2f}",
                    "Running Balance": "{:,.2f}"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No transactions recorded in the Inventory Ledger yet.")
