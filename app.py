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
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
    
# --- DATABASE SETUP (Turso / SQLite Integrated) ---
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
                project_name TEXT UNIQUE)''')
    
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
        ("users", "role6", "TEXT DEFAULT ''")
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
    conn.close()

init_db()

# --- SEQUENCE GENERATOR HELPER FUNCTION ---
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
        with get_db_connection() as pdf_conn:
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
def create_apv_pdf(apv_no, apv_date, dr_no, po_no, supplier, project, total_amount):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=16, leading=18, alignment=1, textColor=colors.HexColor("#CC0000"))
    normal_style = ParagraphStyle('Normal', fontName='Helvetica', fontSize=9, leading=12)
    bold_style = ParagraphStyle('Bold', fontName='Helvetica-Bold', fontSize=9, leading=12)
    
    elements.append(Paragraph("<b>TUANSON CONSTRUCTION</b>", title_style))
    elements.append(Paragraph("<font size=8 align=center>Accounts Payable Voucher (APV)</font>", normal_style))
    elements.append(Spacer(1, 15))
    
    meta_data = [
        [Paragraph("<b>APV NO:</b>", bold_style), Paragraph(str(apv_no), normal_style), Paragraph("<b>APV DATE:</b>", bold_style), Paragraph(str(apv_date), normal_style)],
        [Paragraph("<b>SUPPLIER:</b>", bold_style), Paragraph(str(supplier), normal_style), Paragraph("<b>PROJECT:</b>", bold_style), Paragraph(str(project), normal_style)],
        [Paragraph("<b>PO NUMBER:</b>", bold_style), Paragraph(str(po_no), normal_style), Paragraph("<b>DR NUMBER:</b>", bold_style), Paragraph(str(dr_no), normal_style)],
    ]
    meta_table = Table(meta_data, colWidths=[90, 180, 90, 180])
    meta_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    elements.append(meta_table)
    elements.append(Spacer(1, 15))
    
    table_data = [
        [Paragraph("<b>PARTICULARS / DESCRIPTION</b>", bold_style), Paragraph("<b>AMOUNT</b>", bold_style)],
        [Paragraph(f"Accounts Payable accrual for DR #{dr_no} under PO #{po_no}", normal_style), Paragraph(f"₱{total_amount:,.2f}", normal_style)],
        [Paragraph("<b>TOTAL APV AMOUNT</b>", bold_style), Paragraph(f"<b>₱{total_amount:,.2f}</b>", bold_style)]
    ]
    apv_table = Table(table_data, colWidths=[400, 140])
    apv_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(apv_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# --- CV PDF GENERATOR FUNCTION ---
def create_cv_pdf(cv_no, cv_date, apv_no, supplier, payment_method, total_amount):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=16, leading=18, alignment=1, textColor=colors.HexColor("#CC0000"))
    normal_style = ParagraphStyle('Normal', fontName='Helvetica', fontSize=9, leading=12)
    bold_style = ParagraphStyle('Bold', fontName='Helvetica-Bold', fontSize=9, leading=12)
    
    elements.append(Paragraph("<b>TUANSON CONSTRUCTION</b>", title_style))
    elements.append(Paragraph(f"<font size=8 align=center>Check / Payment Voucher ({payment_method})</font>", normal_style))
    elements.append(Spacer(1, 15))
    
    meta_data = [
        [Paragraph("<b>VOUCHER NO:</b>", bold_style), Paragraph(str(cv_no), normal_style), Paragraph("<b>DATE:</b>", bold_style), Paragraph(str(cv_date), normal_style)],
        [Paragraph("<b>PAYEE / SUPPLIER:</b>", bold_style), Paragraph(str(supplier), normal_style), Paragraph("<b>PAYMENT METHOD:</b>", bold_style), Paragraph(str(payment_method), normal_style)],
        [Paragraph("<b>REF APV NO:</b>", bold_style), Paragraph(str(apv_no), normal_style), "", ""]
    ]
    meta_table = Table(meta_data, colWidths=[90, 180, 90, 180])
    meta_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('SPAN', (1,2), (3,2)), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    elements.append(meta_table)
    elements.append(Spacer(1, 15))
    
    table_data = [
        [Paragraph("<b>PARTICULARS</b>", bold_style), Paragraph("<b>AMOUNT</b>", bold_style)],
        [Paragraph(f"Payment settlement for APV #{apv_no} to {supplier}", normal_style), Paragraph(f"₱{total_amount:,.2f}", normal_style)],
        [Paragraph("<b>TOTAL PAYMENT AMOUNT</b>", bold_style), Paragraph(f"<b>₱{total_amount:,.2f}</b>", bold_style)]
    ]
    cv_table = Table(table_data, colWidths=[400, 140])
    cv_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(cv_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# --- APP LAYOUT & LOGIN SYSTEM ---
st.set_page_config(page_title="Tuanson Construction System", layout="wide")

# Cloud Connection Management Using Factory
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
    
    tab_request, tab_track = st.tabs(["📝 New Material Request", "🔍 Track My Requests"])
    
    with tab_request:
        if "request_cart" not in st.session_state:
            st.session_state.request_cart = []
        
        col_proj, col_act = st.columns(2)
        
        projects = [r[0] for r in c.execute("SELECT project_name FROM projects").fetchall()]
        selected_project = col_proj.selectbox("Project Name", projects)
        
        # --- DYNAMIC ACTIVITY SELECTION WITH ADD OPTION ---
        act_query = """SELECT a.activity_name FROM activities a 
                       JOIN projects p ON a.project_id = p.id WHERE p.project_name = ?"""
        activities = [r[0] for r in c.execute(act_query, (selected_project,)).fetchall()]
        
        activity_options = activities
        if st.session_state.get('can_add_act') == 'Yes':
            activity_options.append("➕ Add New Activity...")
            
        selected_activity_option = col_act.selectbox("Activity", activity_options)
        
        selected_activity = selected_activity_option
        if selected_activity_option == "➕ Add New Activity...":
            new_activity_input = st.text_input("Enter New Activity Name")
            selected_activity = new_activity_input.strip()

        # --- DYNAMIC MATERIAL SELECTION WITH ADD OPTION ---
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

# --- ROLE 2: PURCHASER ---
elif role == "Purchaser":
    st.subheader("🛒 Purchaser Dashboard")
    
    tab_create_po, tab_receive = st.tabs(["📝 Create Purchase Orders", "📦 Receive Deliveries"])
    
    with tab_create_po:
        st.write("### 🛒 Batch Create P.O.")
        
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
            
            default_vendor_index = 0
            if not pending_df.empty:
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

    with tab_receive:
        st.write("### 🚚 Record Supplier Deliveries")
        st.info("Log items that have arrived on-site and upload attached Delivery Receipts (DR), Sales Invoices (SI), or Official Receipts (OR).")
        
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
            po_to_receive = recv_col1.selectbox("Select PO Number", pending_recv_df['PO Number'].tolist())
            dr_number = recv_col2.text_input("DR / SI / OR Document Number")
            
            uploaded_file = st.file_uploader(
                "📎 Attach File for DR / SI / OR (Photo or PDF)", 
                type=["png", "jpg", "jpeg", "pdf"]
            )
            
            if uploaded_file is not None and uploaded_file.type.startswith("image/"):
                st.image(uploaded_file, caption="Preview of attached document", width=250)
            
            if st.button("Confirm Receiving", type="primary"):
                if dr_number.strip():
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
                    
                    conn.commit()
                    st.session_state["receive_success_msg"] = f"✅ PO #{po_to_receive} received under Doc #{dr_number}! Forwarded to Accounting."
                    st.rerun()
                else:
                    st.warning("⚠️ Please input the DR / SI / OR document number.")
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
                f"PO #{row['PO Number']} | DR #{row['DR / SI / OR No.']} | {row['Supplier']} ({row['Project']})": row['id']
                for _, row in history_df.iterrows()
            }
            
            selected_label = st.selectbox("Choose a delivery record:", list(options.keys()))
            selected_id = options[selected_label]

            selected_record = c.execute("SELECT receipt_image, file_name FROM deliveries WHERE id = ?", (selected_id,)).fetchone()

            if selected_record and selected_record[0]:
                image_blob, fname = selected_record[0], selected_record[1]
                if fname and fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                    st.image(image_blob, caption=f"📷 Attached Receipt: {fname}", width=450)
                elif fname and fname.lower().endswith('.pdf'):
                    st.info(f"📄 PDF Document attached: **{fname}**")
                    st.download_button(label="📥 Download PDF Document", data=image_blob, file_name=fname, mime="application/pdf")
                else:
                    try:
                        st.image(image_blob, caption=f"📷 Attached Receipt: {fname or 'Image'}", width=450)
                    except Exception:
                        st.download_button(label=f"📥 Download Attached File ({fname or 'file'})", data=image_blob, file_name=fname or "receipt_file")
            else:
                st.warning("⚠️ No image or document file was attached for this receiving record.")
        else:
            st.info("No received deliveries recorded yet.")
            
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
                
                if col_rej.button("❌ Reject PO", key=f"rej_{pono}"):
                    c.execute("""
                        UPDATE requests 
                        SET status = 'Rejected'
                        WHERE pono = ? AND status = 'Pending Approval'
                    """, (pono,))
                    conn.commit()
                    st.warning(f"PO #{pono} was rejected.")
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
    
    merged_df['MATERIALS Amount'] = merged_df.get('Direct Materials', 0.0) + merged_df.get('Tools & Consumables', 0.0)
    merged_df['SUBCON'] = merged_df.get('Subcontract & Services', 0.0)
    merged_df['EQPT Amount'] = merged_df.get('Equipment & Rental', 0.0) + merged_df.get('Fuel & Lubricants', 0.0)
    
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

# --- ROLE 5: ACCOUNTING ---
elif role == "Accounting":
    st.subheader("🧾 Accounting Dashboard - Payables & Disbursements")
    
    tab_coa, tab_apv, tab_payment, tab_gl = st.tabs([
        "📊 Chart of Accounts", 
        "📝 Accounts Payable Voucher (APV)", 
        "💸 Check / Payment Voucher (CV)", 
        "📖 General Ledger Entries"
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
                        except sqlite3.IntegrityError:
                            st.error(f"⚠️ Account Code '{new_acc_code.strip()}' already exists.")
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
            col1, col2 = st.columns(2)
            
            dr_to_apv = col1.selectbox("Select DR Number to Voucher", apv_df['DR Number'].tolist())
            suggested_apv = generate_voucher_number(c, "apv_number", "APV")
            apv_input = col2.text_input("APV Number Sequence", value=suggested_apv)
            
            st.info("""
            💡 **Accounting Entry Preview:**
            * **Debit:** Construction Materials (Code 13100) / Direct Cost Materials (Code 60200)
            * **Credit:** Accounts Payable-Trade (Code 20100)
            """)
            
            if st.button("✅ Generate Accounts Payable Voucher", type="primary"):
                if apv_input.strip():
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    selected_del = apv_df[apv_df['DR Number'] == dr_to_apv].iloc[0]
                    total_amt = float(selected_del['Total Amount'])
                    
                    c.execute("""
                        UPDATE deliveries 
                        SET apv_number = ?, apv_date = ? 
                        WHERE dr_number = ?
                    """, (apv_input.strip(), current_time, dr_to_apv))
                    
                    # Post Debit/Credit Journal Entry
                    c.execute("""
                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description)
                        VALUES (?, ?, '13100', 'Construction Materials', ?, 0.0, ?, ?)
                    """, (current_time, apv_input.strip(), total_amt, dr_to_apv, f"APV setup for DR #{dr_to_apv} ({selected_del['Supplier']})"))
                    
                    c.execute("""
                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description)
                        VALUES (?, ?, '20100', 'Accounts Payable-Trade', 0.0, ?, ?, ?)
                    """, (current_time, apv_input.strip(), total_amt, dr_to_apv, f"APV liability accrued for DR #{dr_to_apv}"))
                    
                    conn.commit()
                    st.success(f"🎉 Voucher {apv_input.strip()} recorded successfully for DR #{dr_to_apv}!")
                    st.rerun()
                else:
                    st.error("⚠️ Please enter a valid APV Number.")
        else:
            st.success("🎉 All received deliveries have been vouchered with an APV!")

    # --- TAB 1: ACCOUNTS PAYABLE VOUCHER (APV) ---
    with tab_apv:
        # [Keep your existing APV generation form code here...]
        
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
                
                pdf_bytes = create_apv_pdf(apv_no, apv_date, dr_no, po_no, supplier, proj, total_amt)
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
        st.write("### 💳 Outstanding Payables with Approved APV")
        st.info("Process payments for vouchered liabilities via Cash or Check.")
        
        pay_df = pd.read_sql_query("""
            SELECT id, apv_number AS 'APV Number', pono AS 'PO Number', dr_number AS 'DR Number', 
                   supplier AS 'Supplier', total_amount AS 'Total Amount', apv_date AS 'APV Date'
            FROM deliveries 
            WHERE payment_status = 'Unpaid' AND apv_number IS NOT NULL AND apv_number != ''
            ORDER BY apv_date ASC
        """, conn)
        
        if not pay_df.empty:
            st.dataframe(pay_df.style.format({"Total Amount": "₱{:,.2f}"}), use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.write("#### 💸 Process Payment & Generate Check Voucher")
            
            col1, col2, col3 = st.columns(3)
            
            apv_to_pay = col1.selectbox("Select APV Number to Pay", pay_df['APV Number'].tolist())
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
            cv_input = col3.text_input("Voucher Number Sequence", value=suggested_cv)
            
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
                    
                    c.execute("""
                        UPDATE deliveries 
                        SET payment_status = 'Paid', cv_number = ?, cv_date = ?, payment_method = ?
                        WHERE apv_number = ?
                    """, (cv_input.strip(), current_time, pay_method, apv_to_pay))
                    
                    c.execute("UPDATE requests SET payment_status = 'Paid' WHERE pono = ?", (selected_pay['PO Number'],))
                    
                    # Post Debit/Credit Journal Entry
                    c.execute("""
                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description)
                        VALUES (?, ?, '20100', 'Accounts Payable-Trade', ?, 0.0, ?, ?)
                    """, (current_time, cv_input.strip(), pay_amt, apv_to_pay, f"Settlement of APV #{apv_to_pay} ({selected_pay['Supplier']})"))
                    
                    c.execute("""
                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description)
                        VALUES (?, ?, ?, ?, 0.0, ?, ?, ?)
                    """, (current_time, cv_input.strip(), selected_bank_code, selected_bank_name, pay_amt, apv_to_pay, f"Payment release via {pay_method}"))
                    
                    conn.commit()
                    st.success(f"🎉 Voucher {cv_input.strip()} completed! Payment cleared for APV #{apv_to_pay}.")
                    st.rerun()
                else:
                    st.error("⚠️ Please enter a valid Check Voucher Number.")
        else:
            st.success("🎉 No outstanding vouchered payables waiting for payment!")

    # --- TAB 2: CHECK VOUCHER / PAYMENT (CV) ---
    with tab_payment:
        # [Keep your existing Payment Processing form code here...]
        
        st.markdown("---")
        st.subheader("🖨️ Issued Check / Payment Vouchers (Ready for Printing)")
        
        issued_cvs = c.execute("""
            SELECT cv_number, cv_date, apv_number, supplier, payment_method, total_amount 
            FROM deliveries 
            WHERE cv_number IS NOT NULL AND cv_number != ''
            ORDER BY cv_date DESC
        """).fetchall()
        
        if issued_cvs and HAS_REPORTLAB:
            for idx, cv in enumerate(issued_cvs):
                cv_no, cv_date, apv_no, supplier, pay_method, total_amt = cv
                col_info, col_btn = st.columns([3, 1])
                col_info.write(f"💳 **Voucher:** {cv_no} ({pay_method}) | **Supplier:** {supplier} | **Amount:** ₱{total_amt:,.2f}")
                
                pdf_bytes = create_cv_pdf(cv_no, cv_date, apv_no, supplier, pay_method, total_amt)
                col_btn.download_button(
                    label=f"🖨️ Print Voucher",
                    data=pdf_bytes,
                    file_name=f"Voucher_{cv_no}.pdf",
                    mime="application/pdf",
                    key=f"print_cv_{cv_no}_{idx}"
                )
        else:
            st.info("No issued check or payment vouchers available for printing yet.")

    

    # --- TAB 3: GENERAL LEDGER ---
    with tab_gl:
        st.write("### 📖 Real-Time General Ledger Journal Entries")
        gl_df = pd.read_sql_query("""
            SELECT id AS 'Entry ID', entry_date AS 'Date', voucher_no AS 'Voucher No', 
                   account_code AS 'Account Code', account_name AS 'Account Name', 
                   debit AS 'Debit', credit AS 'Credit', ref_no AS 'Ref Doc', description AS 'Description'
            FROM journal_entries
            ORDER BY id DESC
        """, conn)
        
        if not gl_df.empty:
            st.dataframe(gl_df.style.format({"Debit": "₱{:,.2f}", "Credit": "₱{:,.2f}"}), use_container_width=True, hide_index=True)
            
            d_sum = gl_df["Debit"].sum()
            c_sum = gl_df["Credit"].sum()
            st.write(f"**Total Debits:** ₱{d_sum:,.2f} | **Total Credits:** ₱{c_sum:,.2f}")
        else:
            st.info("No journal entries posted yet. Generate an APV or CV to trigger automated entries.")

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
                    if pd.notnull(row['username']) and str(row['username']).strip() != "":
                        
                        r1 = str(row.get('role1', '')) if pd.notnull(row.get('role1')) else ''
                        r2 = str(row.get('role2', '')) if pd.notnull(row.get('role2')) else ''
                        r3 = str(row.get('role3', '')) if pd.notnull(row.get('role3')) else ''
                        r4 = str(row.get('role4', '')) if pd.notnull(row.get('role4')) else ''
                        r5 = str(row.get('role5', '')) if pd.notnull(row.get('role5')) else ''
                        r6 = str(row.get('role6', '')) if pd.notnull(row.get('role6')) else ''
                        status = str(row.get('status', 'Active')) if pd.notnull(row.get('status')) else 'Active'
                        can_add_act = str(row.get('can_add_act', 'No')) if pd.notnull(row.get('can_add_act')) else 'No'
                        can_add_item = str(row.get('can_add_item', 'No')) if pd.notnull(row.get('can_add_item')) else 'No'
                        
                        c.execute("""
                            INSERT INTO users (username, password, role1, role2, role3, role4, role5, role6, status, can_add_act, can_add_item)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            str(row['username']), str(row['password']), 
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
            sel_proj_act = st.selectbox("Select Project for Activity", projects_list, key="sel_proj_editable")
            
            if sel_proj_act:
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
                                act_name = row['Activity Name']
                                act_qty = row['Qty']
                                act_unit = row['Unit']
                                act_amt = row['Contract Amount']
                                
                                if pd.notnull(act_id):
                                    c.execute("""
                                        UPDATE activities 
                                        SET activity_name = ?, qty = ?, unit = ?, contract_amount = ?
                                        WHERE id = ?
                                    """, (act_name, act_qty, act_unit, act_amt, act_id))
                            
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
                    new_amount = ac4.number_input("Contract Amount (₱)", min_value=0.0, step=1000.0, format="%.2f", key="new_act_amt")
                    
                    if st.button("Add New Activity", type="primary", key="btn_add_act"):
                        if new_act.strip():
                            c.execute("""
                                INSERT INTO activities (project_id, activity_name, qty, unit, contract_amount) 
                                VALUES (?, ?, ?, ?, ?)
                            """, (project_id, new_act.strip(), new_qty, new_unit.strip(), new_amount))
                            conn.commit()
                            st.success(f"Activity '{new_act.strip()}' added successfully!")
                            st.rerun()
                        else:
                            st.warning("⚠️ Please provide an activity name.")      

        with st.expander("✍️ Manage Signatories & Signatures"):
            st.write("#### ✒️ Edit Signatories & Signature Files")
            signatories_df = pd.read_sql_query("SELECT id, name, role, signature_path FROM signatories", conn)
            
            edited_sigs_df = st.data_editor(
                signatories_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": None,
                    "name": "Signatory Name",
                    "role": st.column_config.SelectboxColumn("Role", options=["Preparer", "Approver"], required=True),
                    "signature_path": "Signature File Name"
                },
                key="sig_editor"
            )
            
            if st.button("💾 Save Signatories Changes", type="primary", key="save_sigs_btn"):
                for _, row in edited_sigs_df.iterrows():
                    c.execute("""
                        UPDATE signatories 
                        SET name = ?, role = ?, signature_path = ? 
                        WHERE id = ?
                    """, (row['name'], row['role'], row['signature_path'], row['id']))
                conn.commit()
                st.success("Signatories updated successfully!")
                st.rerun()

        with st.expander("📦 Add New Material Item"):
            all_items = [r[0] for r in c.execute("SELECT item_no FROM materials").fetchall() if r[0] and r[0].isdigit()]
            suggested_item_no = str(max([int(x) for x in all_items]) + 1).zfill(5) if all_items else "00001"

            mc1, mc2 = st.columns(2)
            mat_item_no = mc1.text_input("Item Number", value=suggested_item_no)
            mat_desc = mc2.text_input("Description")
            
            mc3, mc4 = st.columns(2)
            mat_unit = mc3.text_input("Unit", value="PCS")
            category_options = ["Direct Materials", "Equipment & Rental", "Tools & Consumables", "Fuel & Lubricants", "Subcontract & Services"]
            mat_category = mc4.selectbox("Category", category_options)
            
            if st.button("Save Material Item", type="primary"):
                if mat_item_no.strip() and mat_desc.strip():
                    c.execute("""
                        INSERT INTO materials (item_no, description, unit, category)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(item_no) DO UPDATE SET
                            description = excluded.description,
                            unit = excluded.unit,
                            category = excluded.category
                    """, (mat_item_no.strip(), mat_desc.strip(), mat_unit.strip(), mat_category))
                    conn.commit()
                    st.success(f"Item '{mat_desc}' saved successfully!")
                    st.rerun()
                else:
                    st.warning("⚠️ Please fill in both Item Number and Description.")

        with st.expander("🚚 Add & Manage Suppliers"):
            suppliers_list = [s[0] for s in c.execute("SELECT supplier_name FROM suppliers ORDER BY supplier_name ASC").fetchall()]
            supplier_edit_options = ["-- Register New Supplier --"] + suppliers_list
            selected_supplier_to_edit = st.selectbox("Select Supplier to Edit", supplier_edit_options)
            
            edit_name, edit_loc, edit_contact_person, edit_contact_no, edit_tin, edit_vat, edit_terms = "", "", "", "", "", "VAT Registered", 0
            
            if selected_supplier_to_edit != "-- Register New Supplier --":
                sup_data = c.execute("SELECT supplier_name, location, contact_person, contact_number, tin_number, vat_type, terms_days FROM suppliers WHERE supplier_name = ?", (selected_supplier_to_edit,)).fetchone()
                if sup_data:
                    edit_name, edit_loc, edit_contact_person, edit_contact_no, edit_tin, edit_vat, edit_terms = sup_data[0], sup_data[1] or "", sup_data[2] or "", sup_data[3] or "", sup_data[4] or "", sup_data[5] or "VAT Registered", int(sup_data[6] or 0)

            sc1, sc2 = st.columns(2)
            sup_name = sc1.text_input("Supplier Name", value=edit_name)
            sup_location = sc2.text_input("Location / Address", value=edit_loc)
            
            sc3, sc4 = st.columns(2)
            sup_contact_person = sc3.text_input("Contact Person", value=edit_contact_person)
            sup_contact_number = sc4.text_input("Contact Number", value=edit_contact_no)
            
            sc5, sc6 = st.columns(2)
            sup_tin = sc5.text_input("TIN Number", value=edit_tin)
            sup_vat = sc6.selectbox("VAT Status", ["VAT Registered", "Non-VAT"], index=0 if edit_vat == "VAT Registered" else 1)
            sup_terms = st.number_input("Payment Terms (Days)", min_value=0, value=edit_terms, step=1)
            
            btn_label = "Update Supplier Details" if selected_supplier_to_edit != "-- Register New Supplier --" else "Save New Supplier"
            
            if st.button(btn_label, type="primary"):
                if sup_name.strip():
                    c.execute("""
                        INSERT INTO suppliers (supplier_name, location, contact_person, contact_number, tin_number, vat_type, terms_days)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(supplier_name) DO UPDATE SET
                            location = excluded.location,
                            contact_person = excluded.contact_person,
                            contact_number = excluded.contact_number,
                            tin_number = excluded.tin_number,
                            vat_type = excluded.vat_type,
                            terms_days = excluded.terms_days
                    """, (sup_name.strip(), sup_location.strip(), sup_contact_person.strip(), sup_contact_number.strip(), sup_tin.strip(), sup_vat, sup_terms))
                    conn.commit()
                    st.success(f"Supplier '{sup_name}' successfully saved/updated!")
                    st.rerun()
                else:
                    st.warning("⚠️ Please enter a Supplier Name.")

        st.write("### 📊 Complete Master Landing Page")
        st.dataframe(pd.read_sql_query("SELECT * FROM requests ORDER BY id DESC", conn), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.write("### 🚨 Danger Zone: Database Management")
        with st.expander("🗑️ Reset Test Data (Clear Transactions)"):
            if st.radio("Are you sure you want to clear all transactions?", ("No, keep my data", "Yes, delete transactions")) == "Yes, delete transactions":
                if st.button("🗑️ Confirm and Clear Data", type="primary"):
                    c.execute("DELETE FROM requests")
                    c.execute("DELETE FROM deliveries")
                    c.execute("DELETE FROM journal_entries")
                    conn.commit()
                    st.success("✅ All test transactions cleared!")
                    st.rerun()

    with tab_reports:
        st.write("### 📈 Approved Items & Summary Reports")
        projects_query = "SELECT DISTINCT project_name FROM requests WHERE status = 'Approved / Ongoing' AND project_name IS NOT NULL AND project_name != ''"
        suppliers_query = "SELECT DISTINCT supplier FROM requests WHERE status = 'Approved / Ongoing' AND supplier IS NOT NULL AND supplier != ''"
        
        available_projects = ["All Projects"] + [p[0] for p in c.execute(projects_query).fetchall()]
        available_suppliers = ["All Suppliers"] + [s[0] for s in c.execute(suppliers_query).fetchall()]

        col_f1, col_f2 = st.columns(2)
        selected_project = col_f1.selectbox("📌 Filter by Project Name:", available_projects)
        selected_supplier = col_f2.selectbox("🚚 Filter by Supplier:", available_suppliers)

        base_query = """
            SELECT pono AS 'P.O. Number', project_name AS 'Project Name', supplier AS 'Supplier',
                   item_no AS 'Item No', description AS 'Description', activity AS 'Activity',
                   qty AS 'Qty', unit AS 'Unit', price AS 'Unit Price', amount AS 'Total Amount',
                   approved_timestamp AS 'Approved Date'
            FROM requests WHERE status = 'Approved / Ongoing'
        """
        params = []
        if selected_project != "All Projects":
            base_query += " AND project_name = ?"
            params.append(selected_project)
        if selected_supplier != "All Suppliers":
            base_query += " AND supplier = ?"
            params.append(selected_supplier)
        base_query += " ORDER BY id DESC"

        approved_df = pd.read_sql_query(base_query, conn, params=params)

        if approved_df.empty:
            st.warning("No approved items found matching the selected filters.")
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("💰 Total Approved Cost", f"₱{approved_df['Total Amount'].sum():,.2f}")
            m2.metric("📦 Total Approved Quantity", f"{approved_df['Qty'].sum():,.0f} units")
            m3.metric("📄 Total Approved P.O.s", f"{approved_df['P.O. Number'].nunique()} Orders")

            st.markdown("---")
            st.dataframe(approved_df.style.format({"Unit Price": "₱{:,.2f}", "Total Amount": "₱{:,.2f}"}), use_container_width=True, hide_index=True)

    with tab_payables:
        st.write("### 💸 Accounts Payable (A/P) Monitor")
        ap_df = pd.read_sql_query("""
            SELECT d.pono AS 'PO Number', d.dr_number AS 'DR Number', d.supplier AS 'Supplier',
                   d.project_name AS 'Project', d.total_amount AS 'Total Amount', d.received_date AS 'Date Received',
                   s.terms_days AS 'Terms (Days)', d.payment_status AS 'Status',
                   d.apv_number AS 'APV No', d.cv_number AS 'CV No'
            FROM deliveries d
            LEFT JOIN suppliers s ON d.supplier = s.supplier_name
            WHERE d.payment_status = 'Unpaid'
            ORDER BY d.received_date ASC
        """, conn)
        
        if not ap_df.empty:
            ap_df['Date Received'] = pd.to_datetime(ap_df['Date Received'])
            ap_df['Terms (Days)'] = ap_df['Terms (Days)'].fillna(0).astype(int)
            ap_df['Due Date'] = (ap_df['Date Received'] + pd.to_timedelta(ap_df['Terms (Days)'], unit='D')).dt.strftime('%Y-%m-%d')
            ap_df['Date Received'] = ap_df['Date Received'].dt.strftime('%Y-%m-%d')
            
            st.dataframe(ap_df.style.format({"Total Amount": "₱{:,.2f}"}), use_container_width=True, hide_index=True)
            st.error(f"**Total Outstanding Payables:** ₱ {ap_df['Total Amount'].sum():,.2f}")
            
            st.markdown("---")
            col_pay1, col_pay2 = st.columns([2, 1])
            dr_to_pay = col_pay1.selectbox("Select DR Number to mark as Paid", ap_df['DR Number'].tolist())
            
            if col_pay2.button("Confirm Direct Settlement", type="primary"):
                c.execute("UPDATE deliveries SET payment_status = 'Paid' WHERE dr_number = ?", (dr_to_pay,))
                conn.commit()
                st.success(f"DR #{dr_to_pay} marked as paid successfully!")
                st.rerun()
        else:
            st.success("🎉 No outstanding payables!")
