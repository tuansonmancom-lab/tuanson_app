import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime
from io import BytesIO  # <--- Ensure this line is included

# ReportLab imports (if using ReportLab)
# --- REPORTLAB PDF GENERATION LIBRARIES ---
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle # <--- ParagraphStyle added here
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
    
# --- DATABASE SETUP ---
# --- DATABASE SETUP ---
DB_NAME = "inventory.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("PRAGMA journal_mode = WAL;")
    c.execute("PRAGMA synchronous = NORMAL;")
    c.execute("PRAGMA busy_timeout = 5000;")

    # 1. Projects Master Table
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT UNIQUE)''')
    
    # 2. Activities Master Table (Updated to include qty, unit, and contract_amount)
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
                received_timestamp DATETIME)''')

    # 6. Deliveries / Receiving Master Table (Updated with receipt fields)
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
                file_name TEXT)''')

    # 7. Signatories Master Table (NEW)
    # Ensure signatories table exists with proper structure
    c.execute('''
        CREATE TABLE IF NOT EXISTS signatories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            role TEXT,
            signature_path TEXT
        )
    ''')

    # --- AUTO-MIGRATIONS FOR EXISTING DATABASES ---
    
    # Safe column additions for suppliers table
    for col in ["location", "contact_person", "contact_number", "tin_number", "vat_type"]:
        try:
            c.execute(f"ALTER TABLE suppliers ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    # Safe column addition for materials table category
    try:
        c.execute("ALTER TABLE materials ADD COLUMN category TEXT DEFAULT 'Direct Materials'")
    except sqlite3.OperationalError:
        pass

    # Safe column addition for requests table category
    try:
        c.execute("ALTER TABLE requests ADD COLUMN category TEXT DEFAULT 'Direct Materials'")
    except sqlite3.OperationalError:
        pass

    # Safe column additions for Payables Monitoring
    try:
        c.execute("ALTER TABLE suppliers ADD COLUMN terms_days INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE requests ADD COLUMN payment_status TEXT DEFAULT 'Unpaid'")
    except sqlite3.OperationalError:
        pass

    # Safe column additions for Receiving Items
    try:
        c.execute("ALTER TABLE requests ADD COLUMN received_status TEXT DEFAULT 'Pending'")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE requests ADD COLUMN received_timestamp DATETIME")
    except sqlite3.OperationalError:
        pass

    # Safe column additions for Activities (contract_amount, qty, unit)
    try:
        c.execute("ALTER TABLE activities ADD COLUMN contract_amount REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass

    for col_def in [("qty", "REAL DEFAULT 1.0"), ("unit", "TEXT DEFAULT 'lot'")]:
        try:
            c.execute(f"ALTER TABLE activities ADD COLUMN {col_def[0]} {col_def[1]}")
        except sqlite3.OperationalError:
            pass

    # Safe column additions for Deliveries Receipt Attachments
    try:
        c.execute("ALTER TABLE deliveries ADD COLUMN receipt_image BLOB")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE deliveries ADD COLUMN file_name TEXT")
    except sqlite3.OperationalError:
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

    # Seed initial Signatories if table is empty
    c.execute("SELECT COUNT(*) FROM signatories")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO signatories (name, role, signature_path) VALUES (?, ?, ?)", [
            ('BRAZEL M. DELA CERNA', 'Preparer', ''),
            ('LEIZEL A. CABUNILAS', 'Approver', 'Leizel_signature.png')
        ])

    conn.commit()
    conn.close()

init_db()

# --- PDF GENERATOR FUNCTION ---
def create_po_pdf(pono, date_str, supplier, project, po_items):
    import os
    import sqlite3
    from io import BytesIO
    from datetime import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    # --- DEFAULT SIGNATORIES FALLBACKS ---
    prep_name = "VERGEL W. MANCIA"
    prep_sig_path = "Vergel_signature.png"
    appr_name = "LEIZEL A. CABUNILAS"
    appr_sig_path = "Leizel_signature.png"

    # --- SAFELY FETCH SIGNATORIES VIA INDEPENDENT CONCURRENT CONNECTION ---
    try:
        # Open an independent database context manager to prevent multi-user locking issues
        with sqlite3.connect("inventory.db") as pdf_conn:
            # Apply your safe secret formula optimizations locally
            pdf_conn.execute("PRAGMA journal_mode = WAL;")
            pdf_conn.execute("PRAGMA synchronous = NORMAL;")
            pdf_conn.execute("PRAGMA busy_timeout = 5000;")
            
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
        pass  # Gracefully falls back to defaults if database is temporarily heavily contested

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
    
    # --- STYLES ---
    company_style = ParagraphStyle(
        'CompanyRed',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=20,
        textColor=colors.HexColor("#CC0000") # Official Red Title
    )
    
    po_title_style = ParagraphStyle(
        'POTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=16,
        alignment=1, # Centered
        textColor=colors.black
    )
    
    po_no_style = ParagraphStyle(
        'PONumber',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=16,
        alignment=2, # Right aligned
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
        alignment=1, # Centered headers
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

    # --- 1. HEADER SECTION ---
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

    # --- 2. TITLE AND PO NUMBER ROW ---
    title_table = Table([
        [Paragraph("<b>PURCHASE ORDER</b>", po_title_style), Paragraph(f"P.O. NO. &nbsp;&nbsp;&nbsp;&nbsp; <b>{pono}</b>", po_no_style)]
    ], colWidths=[340, 200])
    title_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    elements.append(title_table)

    elements.append(Spacer(1, 8))

    # --- 3. METADATA SECTION ---
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

    # --- 4. ITEMS TABLE (Wireframe Grid Layout) ---
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

    # --- 5. FOOTER & SIGNATURE SECTION ---
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



# --- APP LAYOUT ---
st.set_page_config(page_title="Tuanson Construction System", layout="wide")
st.title("🏗️ Tuanson Construction - Procurement & Inventory")

role = st.sidebar.selectbox("🔑 Select Your Role (Trial Mode)", 
                            ["Requisitor", "Purchaser", "Approver", "Office Manager", "Admin View All"])

conn = sqlite3.connect(DB_NAME)
c = conn.cursor()

# --- ROLE 1: REQUISITOR ---
# --- ROLE 1: REQUISITOR ---
# --- ROLE 1: REQUISITOR ---
if role == "Requisitor":
    st.subheader("📋 New Material Request Form")
    
    # Initialize a temporary list (cart) in session state if it doesn't exist yet
    if "request_cart" not in st.session_state:
        st.session_state.request_cart = []
    
    # 1. SELECTION CONTROLS (Outside form for real-time dynamic updates)
    col_proj, col_act = st.columns(2)
    
    # Corrected row unpack parsing from your database query schema format
    projects = [r[0] for r in c.execute("SELECT project_name FROM projects").fetchall()]
    selected_project = col_proj.selectbox("Project Name", projects)
    
    act_query = """SELECT a.activity_name FROM activities a 
                   JOIN projects p ON a.project_id = p.id WHERE p.project_name = ?"""
    activities = [r[0] for r in c.execute(act_query, (selected_project,)).fetchall()]
    selected_activity = col_act.selectbox("Activity", activities if activities else ["N/A"])
    
    # Material selection with Category retrieval
    materials = c.execute("SELECT item_no, description, unit, COALESCE(category, 'Direct Materials') FROM materials").fetchall()
    mat_options = {f"[{m[0]}] {m[1]}": (m[0], m[1], m[2], m[3]) for m in materials} if materials else {"No materials": ("00000", "N/A", "PCS", "Direct Materials")}
    
    selected_mat_label = st.selectbox("Select Item", list(mat_options.keys()))
    item_no, description, default_unit, default_category = mat_options[selected_mat_label]
    
    # Fetch suppliers from your master database setup for the custom dropdown
    suppliers = [r[0] for r in c.execute("SELECT supplier_name FROM suppliers").fetchall()]
    supplier_options = ["No Preference"] + suppliers

    # 2. FORM DETAILS & ADD TO LIST
    with st.form("request_form"):
        category_options = ["Direct Materials", "Equipment & Rental", "Tools & Consumables", "Fuel & Lubricants", "Subcontract & Services"]
        cat_index = category_options.index(default_category) if default_category in category_options else 0
        
        col_cat, col_unit = st.columns(2)
        category = col_cat.selectbox("Category (Accounting Tag)", category_options, index=cat_index)
        unit = col_unit.text_input("Unit", value=default_unit)
        
        # 3-column split pattern directly balances Quantity, Price, and Supplier input components
        col1, col2, col3 = st.columns([1, 1, 1.5])
        qty = col1.number_input("Quantity", min_value=1.0, step=1.0)
        price = col2.number_input("Estimated Price (Optional)", min_value=0.0, step=10.0)
        suggested_supplier = col3.selectbox("Suggested Supplier (Optional)", supplier_options, index=0)
        
        email = st.text_input("Requester Email", value="requester@tuanson.com")
        
        add_to_list = st.form_submit_button("➕ Add to Temporary List")
        
        if add_to_list:
            st.session_state.request_cart.append({
                "Project": selected_project,
                "Activity": selected_activity,
                "Item No": item_no,
                "Description": description,
                "Category": category,
                "Qty": qty,
                "Unit": unit,
                "Price": price,
                "supplier": suggested_supplier, # Matches your table column string casing perfectly
                "Email": email
            })
            st.success(f"Added {qty} {unit} of {description} ({category}) to your list!")

    # 3. REVIEW AND BATCH SUBMISSION SECTION
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
        
        # Final Submit Button
        if st.button("🚀 Submit All Requests to Purchasing"):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for item in st.session_state.request_cart:
                amount = item["Qty"] * item["Price"]
                
                # Directly mirrors all database schemas from your table architecture map 
                c.execute("""INSERT INTO requests 
                             (timestamp, project_name, activity, item_no, description, category, qty, unit, price, amount, email_address, status, supplier)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending Purchaser', ?)""",
                          (now, item["Project"], item["Activity"], item["Item No"], item["Description"], 
                           item["Category"], item["Qty"], item["Unit"], item["Price"], amount, item["Email"], item["supplier"]))
            
            conn.commit()
            st.session_state.request_cart = [] 
            st.success("All items successfully submitted to Purchasing!")
            st.rerun()


# --- ROLE 2: PURCHASER ---
# --- ROLE 2: PURCHASER ---
elif role == "Purchaser":
    st.subheader("🛒 Purchaser Dashboard")
    
    # Create tabs to separate Purchasing and Receiving duties
    tab_create_po, tab_receive = st.tabs(["📝 Create Purchase Orders", "📦 Receive Deliveries"])
    
    # =========================================================
    # TAB 1: CREATE PURCHASE ORDERS
    # =========================================================
    with tab_create_po:
        st.write("### 🛒 Batch Create P.O.")
        
        # 1. Fetch pending requests - 🌟 UPDATED: Included 'supplier' in your SQL query strings
        pending_df = pd.read_sql_query(
            "SELECT id, project_name, activity, item_no, description, qty, unit, price AS est_price, supplier FROM requests WHERE status = 'Pending Purchaser'", 
            conn
        )
        
        # Fetch the last used PO number with leading zeros preserved
        last_po_query = "SELECT pono FROM requests WHERE pono IS NOT NULL AND pono != '' ORDER BY id DESC LIMIT 1"
        last_po_result = c.execute(last_po_query).fetchone()
        
        last_po = last_po_result[0] if last_po_result else None
        suggested_po = ""
        
        if last_po and last_po.isdigit():
            suggested_po = str(int(last_po) + 1).zfill(len(last_po))
        
        if pending_df.empty:
            st.info("No pending requests waiting for Purchasing.")
        else:
            # Calculate Last Purchased Price for each item dynamically
            last_prices = []
            default_confirmed_prices = []
            
            for _, row in pending_df.iterrows():
                item_no = row['item_no']
                est = row['est_price'] if pd.notnull(row['est_price']) else 0.0
                
                # Query database for the latest non-zero price for this material
                res = c.execute("""
                    SELECT price FROM requests 
                    WHERE item_no = ? AND price > 0 AND status != 'Pending Purchaser' 
                    ORDER BY id DESC LIMIT 1
                """, (item_no,)).fetchone()
                
                last_paid = res[0] if res else 0.0
                last_prices.append(last_paid)
                
                # Default confirmed price uses last paid price first, else falls back to requisitor's estimated price
                default_price = last_paid if last_paid > 0 else est
                default_confirmed_prices.append(default_price)
                
            pending_df["Last Purchase Price"] = last_prices
            pending_df["Confirmed Price"] = default_confirmed_prices
            
            # 2. GLOBAL P.O. DETAILS
            st.write("#### 📝 1. Set P.O. Details")
            col1, col2 = st.columns(2)
            
            # Fetch master vendor array
            suppliers_master = [s[0] for s in c.execute("SELECT supplier_name FROM suppliers").fetchall()]
            
            # 🌟 NEW SMART ENGINE: Look at the first row's suggested supplier to automatically select the matching dropdown index
            default_vendor_index = 0
            if not pending_df.empty:
                first_row_suggestion = pending_df.iloc[0]["supplier"]
                if first_row_suggestion and first_row_suggestion in suppliers_master:
                    default_vendor_index = suppliers_master.index(first_row_suggestion)
            
            # Your selectbox component now natively pre-fills matching Requisitor requests
            selected_supplier = col1.selectbox(
                "Select Supplier for this Order", 
                suppliers_master, 
                index=default_vendor_index
            )
            
            po_number = col2.text_input("Enter P.O. Number", value=suggested_po)
            
            if last_po:
                col2.caption(f"💡 *Last used P.O. Number was:* **{last_po}**")
            else:
                col2.caption("💡 *No previous P.O. numbers found in the system.*")
                
            st.markdown("---")
            
            # 3. ITEM SELECTION
            st.write("#### 📦 2. Select Items for this P.O.")
            st.info("Check the **'Add to PO'** box and verify the **'Confirmed Price'**. You can enter exact decimals (e.g. 260.35).")
            
            pending_df.insert(0, "Add to PO", False) 
            
            # 🌟 UPDATED: Cleanly format column strings for the user frame display view
            pending_df.rename(columns={"supplier": "Suggested Supplier"}, inplace=True)
            
            edited_df = st.data_editor(
                pending_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Add to PO": st.column_config.CheckboxColumn(
                        "Add to PO",
                        help="Select this item to include it in the current P.O.",
                        default=False,
                    ),
                    "Suggested Supplier": st.column_config.TextColumn(
                        "Suggested Supplier",
                        help="The vendor recommended by the site engineer."
                    ),
                    "Last Purchase Price": st.column_config.NumberColumn(
                        "Last Purchase Price",
                        format="₱%.2f",
                        help="Historical price per unit from previous orders."
                    ),
                    "Confirmed Price": st.column_config.NumberColumn(
                        "Confirmed Price",
                        min_value=0.0,
                        step=0.01,
                        format="₱%.2f",
                        help="Agreed price per unit for this order."
                    ),
                    "est_price": None, # Hide raw estimated cost key
                    "id": None, 
                },
                disabled=["project_name", "activity", "item_no", "description", "qty", "unit", "Suggested Supplier", "Last Purchase Price"] 
            )
            
            # 4. BATCH SUBMISSION
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

    # =========================================================
    # TAB 2: RECEIVE DELIVERIES (WITH DR ATTACHMENT & HISTORY VIEWER)
    # =========================================================
    with tab_receive:
        st.write("### 🚚 Record Supplier Deliveries")
        st.info("Log items that have arrived on-site and upload attached Delivery Receipts (DR), Sales Invoices (SI), or Official Receipts (OR).")
        
        # Display persistent success message across page reloads
        if "receive_success_msg" in st.session_state:
            st.success(st.session_state.pop("receive_success_msg"))

        # Query approved but NOT YET received POs from requests
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
            dr_number = recv_col2.text_input("DR / SI / OR Document Number", help="Enter Delivery Receipt, Sales Invoice, or Official Receipt Number")
            
           


            
            # File Upload Section for DR / SI / OR
            uploaded_file = st.file_uploader(
                "📎 Attach File for DR / SI / OR (Photo or PDF)", 
                type=["png", "jpg", "jpeg", "pdf"],
                help="Supports photo uploads from mobile or desktop file attachment."
            )
            
            if uploaded_file is not None and uploaded_file.type.startswith("image/"):
                st.image(uploaded_file, caption="Preview of attached document", width=250)
            
            if st.button("Confirm Receiving", type="primary"):
                if dr_number.strip():
                    from datetime import datetime
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    po_details = pending_recv_df[pending_recv_df['PO Number'] == po_to_receive].iloc[0]
                    
                    receipt_blob = uploaded_file.getvalue() if uploaded_file else None
                    file_name = uploaded_file.name if uploaded_file else None
                    
                    # 1. Insert into deliveries table
                    c.execute("""INSERT INTO deliveries 
                                 (pono, supplier, project_name, dr_number, total_amount, received_date, receipt_image, file_name) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                              (po_to_receive, po_details['Supplier'], po_details['Project'], dr_number.strip(), 
                               po_details['Total Amount'], current_time, receipt_blob, file_name))
                    
                    # 2. Update requests status
                    c.execute("UPDATE requests SET received_status = 'Received', received_timestamp = ? WHERE pono = ?", 
                              (current_time, po_to_receive))
                    
                    conn.commit()
                    st.session_state["receive_success_msg"] = f"✅ PO #{po_to_receive} received under Doc #{dr_number}! Forwarded to Accounting."
                    st.rerun()
                else:
                    st.warning("⚠️ Please input the DR / SI / OR document number.")
        else:
            st.success("🎉 No pending deliveries! All approved POs have been physically received.")

        # =========================================================
        # HISTORY VIEWER: VIEW RECEIVED DELIVERIES & ATTACHMENTS
        # =========================================================
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
            # Display history table
            st.dataframe(
                history_df[["PO Number", "Supplier", "Project", "DR / SI / OR No.", "Total Amount", "Date Received", "File Name"]].style.format({"Total Amount": "₱{:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )

            st.write("#### 🔍 Select Item to View Attachment")
            
            # Map selectbox choices to record IDs
            options = {
                f"PO #{row['PO Number']} | DR #{row['DR / SI / OR No.']} | {row['Supplier']} ({row['Project']})": row['id']
                for _, row in history_df.iterrows()
            }
            
            selected_label = st.selectbox("Choose a delivery record:", list(options.keys()))
            selected_id = options[selected_label]

            # Fetch image blob for selected record
            selected_record = c.execute("SELECT receipt_image, file_name FROM deliveries WHERE id = ?", (selected_id,)).fetchone()

            if selected_record and selected_record[0]:
                image_blob, fname = selected_record[0], selected_record[1]
                
                if fname and fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                    st.image(image_blob, caption=f"📷 Attached Receipt: {fname}", width=450)
                elif fname and fname.lower().endswith('.pdf'):
                    st.info(f"📄 PDF Document attached: **{fname}**")
                    st.download_button(
                        label="📥 Download PDF Document",
                        data=image_blob,
                        file_name=fname,
                        mime="application/pdf"
                    )
                else:
                    try:
                        st.image(image_blob, caption=f"📷 Attached Receipt: {fname or 'Image'}", width=450)
                    except Exception:
                        st.download_button(
                            label=f"📥 Download Attached File ({fname or 'file'})",
                            data=image_blob,
                            file_name=fname or "receipt_file"
                        )
            else:
                st.warning("⚠️ No image or document file was attached for this receiving record.")
        else:
            st.info("No received deliveries recorded yet.")
            
    # =========================================================
    # 5. APPROVED PURCHASE ORDERS
    # =========================================================
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
    
    # -----------------------------------------
    # 1. PENDING APPROVAL QUEUE
    # -----------------------------------------
    st.subheader("⏳ Pending Approval Queue")
    
    # Query grouped by P.O. Number using 'Pending Approval'
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
                # Fetch items for this specific PO
                po_items_df = pd.read_sql_query(
                    "SELECT item_no, description, qty, unit, price, amount FROM requests WHERE pono = ? AND status = 'Pending Approval'", 
                    conn, params=(pono,)
                )
                
                st.dataframe(po_items_df, use_container_width=True, hide_index=True)
                
                # Show Grand Total
                total_amount = po_items_df["amount"].sum()
                st.markdown(f"### **Grand Total: ₱{total_amount:,.2f}**")
                
                col_app, col_rej, _ = st.columns([1, 1, 3])
                
                # Approve Action
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
                
                # Reject Action
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
    
    # -----------------------------------------
    # 2. APPROVED PURCHASE ORDERS (READY FOR PRINTING)
    # -----------------------------------------
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
    
    # 1. Fetch Projects & Contract Amounts
    projects_df = pd.read_sql_query("""
        SELECT 
            p.id as 'No.', 
            p.project_name as 'Project Name', 
            COALESCE(SUM(a.contract_amount), 0) as 'CONTRACT Amount'
        FROM projects p
        LEFT JOIN activities a ON p.id = a.project_id
        GROUP BY p.id, p.project_name
    """, conn)
    
    # 2. Fetch Running Expenses (Only Approved or Received/Paid items)
    expenses_df = pd.read_sql_query("""
        SELECT 
            project_name, 
            category, 
            SUM(amount) as cost
        FROM requests
        WHERE status IN ('Approved / Ongoing', 'Received', 'Paid')
        GROUP BY project_name, category
    """, conn)
    
    # 3. Pivot expenses into columns grouped by project
    if not expenses_df.empty:
        pivot_exp = expenses_df.pivot_table(index='project_name', columns='category', values='cost', fill_value=0).reset_index()
    else:
        pivot_exp = pd.DataFrame(columns=['project_name']) # Fallback if no expenses exist yet
        
    # Merge projects with their expenses
    merged_df = pd.merge(projects_df, pivot_exp, left_on='Project Name', right_on='project_name', how='left').fillna(0)
    
    # 4. Map your database categories to the specific spreadsheet columns
    merged_df['MATERIALS Amount'] = merged_df.get('Direct Materials', 0.0) + merged_df.get('Tools & Consumables', 0.0)
    merged_df['SUBCON'] = merged_df.get('Subcontract & Services', 0.0)
    merged_df['EQPT Amount'] = merged_df.get('Equipment & Rental', 0.0) + merged_df.get('Fuel & Lubricants', 0.0)
    
    # Static or placeholder columns (can be updated later if you add these to the DB)
    merged_df['Labor Amount'] = 0.0  
    merged_df['ADMIN'] = 0.0
    merged_df['REVISED Amount'] = merged_df['CONTRACT Amount'] 
    
    # Calculate Implementing Budget (Using the 42% logic from your Admin tab)
    merged_df['Implementing Budget Amount'] = merged_df['CONTRACT Amount'] * 0.42 
    merged_df['Implementing Budget %'] = 0.42 
    
    # Calculate Total Expenses
    merged_df['TOTAL Amount'] = (merged_df['MATERIALS Amount'] + merged_df['Labor Amount'] + 
                                 merged_df['ADMIN'] + merged_df['SUBCON'] + merged_df['EQPT Amount'])
    
    # Calculate Percentages safely (avoiding dividing by zero)
    for col, target in [('MATERIALS Amount', 'Mat %'), ('Labor Amount', 'Lab %'), 
                        ('EQPT Amount', 'Eqpt %'), ('TOTAL Amount', 'Total %')]:
        merged_df[target] = (merged_df[col] / merged_df['Implementing Budget Amount']).replace([float('inf'), -float('inf')], 0.0).fillna(0.0)
        
    # 5. Restructure to match the MultiIndex layout exactly
    final_columns = [
        'No.', 'Project Name', 'CONTRACT Amount', 'REVISED Amount',
        'Implementing Budget %', 'Implementing Budget Amount',
        'Mat %', 'MATERIALS Amount', 'Lab %', 'Labor Amount', 'ADMIN', 'SUBCON',
        'Eqpt %', 'EQPT Amount', 'Total %', 'TOTAL Amount'
    ]
    
    # Ensure all columns exist before rendering to prevent errors
    for col in final_columns:
        if col not in merged_df.columns:
            merged_df[col] = 0.0
            
    final_df = merged_df[final_columns]
    
    # 6. Apply the MultiIndex (Double-Header) structure
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
    
    # 7. Format currency and percentages visually
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
    

# --- ROLE 5: ADMIN VIEW ALL ---
# --- ROLE 5: ADMIN VIEW ALL ---
elif role == "Admin View All":
    st.subheader("🛡️ Admin Dashboard & Analytics")

    # Tabs to separate Admin Settings/Master View, Reporting, and Payables
    tab_settings, tab_reports, tab_payables = st.tabs(["⚙️ Master Database & Settings", "📊 Project Approved Reports", "💸 Accounts Payable"])

    # ---------------------------------------------------------
    # TAB 1: MASTER DATABASE & SETTINGS
    # ---------------------------------------------------------
    with tab_settings:
        st.write("### ⚙️ Admin Settings & Configuration")
        
        # Add New Project Expander
        with st.expander("➕ Add New Project"):
            new_proj = st.text_input("Project Name")
            if st.button("Save Project"):
                if new_proj.strip():
                    c.execute("INSERT OR IGNORE INTO projects (project_name) VALUES (?)", (new_proj.strip(),))
                    conn.commit()
                    st.success(f"Project '{new_proj}' added!")
                    st.rerun()

        # --- Manage Project Activities Expander ---
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
                    st.info("💡 You can edit the cells directly in the table below (Activity Name, Qty, Unit, Contract Amount). Click **Save Changes** when done.")
                    
                    # Fetch activities for the editable grid
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
                        # Use st.data_editor for inline editing with corrected number formats
                        edited_acts_df = st.data_editor(
                            acts_df,
                            use_container_width=True,
                            hide_index=True,
                            num_rows="dynamic",
                            column_config={
                                "id": None,
                                "Qty": st.column_config.NumberColumn(
                                    "Qty", 
                                    min_value=0.0, 
                                    step=0.01, 
                                    format="%.2f"
                                ),
                                "Contract Amount": st.column_config.NumberColumn(
                                    "Contract Amount", 
                                    min_value=0.0, 
                                    step=100.0, 
                                    format="₱%.2f"
                                )
                            }
                        )
                        
                        col_save, col_metric = st.columns([1, 2])
                        if col_save.button("💾 Save Table Changes", type="primary"):
                            # 1. Update existing rows
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
                            
                            # 2. Delete removed rows
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
                        st.info("No activities registered yet for this project. Add one below.")
                    
                    st.markdown("---")
                    
                    # --- Expense Summary & Cost Tracking for Selected Project ---
                    st.write(f"#### 📊 Actual Expense Tracking for: *{sel_proj_act}*")
                    
                    expenses_df = pd.read_sql_query("""
                        SELECT 
                            activity AS 'Activity Name',
                            category AS 'Category',
                            SUM(amount) AS 'Total Cost'
                        FROM requests 
                        WHERE project_name = ?
                        GROUP BY activity, category
                    """, conn, params=(sel_proj_act,))
                    
                    if not acts_df.empty:
                        if not expenses_df.empty:
                            expenses_df['Category'] = expenses_df['Category'].str.strip()
                            
                            pivot_expenses = expenses_df.pivot_table(
                                index='Activity Name', 
                                columns='Category', 
                                values='Total Cost', 
                                fill_value=0.0
                            ).reset_index()
                            
                            tracking_df = pd.merge(
                                acts_df[['Activity Name', 'Qty', 'Unit', 'Contract Amount']], 
                                pivot_expenses, 
                                on='Activity Name', 
                                how='left'
                            ).fillna(0.0)
                        else:
                            tracking_df = acts_df[['Activity Name', 'Qty', 'Unit', 'Contract Amount']].copy()
                    
                        for col in ['Direct Materials', 'Materials', 'Labor', 'Equipment & Rental', 'Equipment']:
                            if col not in tracking_df.columns:
                                tracking_df[col] = 0.0
                    
                        tracking_df['Actual Materials Amount'] = tracking_df.get('Direct Materials', 0.0) + tracking_df.get('Materials', 0.0)
                        tracking_df['Labor Amount'] = tracking_df.get('Labor', 0.0)
                        tracking_df['Equipment Amount'] = tracking_df.get('Equipment & Rental', 0.0) + tracking_df.get('Equipment', 0.0)
                        
                        tracking_df['Total Amount'] = (
                            tracking_df['Actual Materials Amount'] + 
                            tracking_df['Labor Amount'] + 
                            tracking_df['Equipment Amount']
                        )
                        
                        display_tracking_df = tracking_df[['Activity Name', 'Qty', 'Unit', 'Contract Amount', 'Actual Materials Amount', 'Labor Amount', 'Equipment Amount', 'Total Amount']]
                        
                        st.dataframe(
                            display_tracking_df.style.format({
                                "Qty": "{:,.2f}",
                                "Contract Amount": "₱{:,.2f}",
                                "Actual Materials Amount": "₱{:,.2f}",
                                "Labor Amount": "₱{:,.2f}",
                                "Equipment Amount": "₱{:,.2f}",
                                "Total Amount": "₱{:,.2f}"
                            }),
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    st.markdown("---")
                    
                    # Quick Add New Activity Form
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

        # --- Manage Signatories & Signatures Expander ---
        with st.expander("✍️ Manage Signatories & Signatures"):
            st.write("#### ✒️ Edit Signatories & Signature Files")
            st.info("Update the official document signatories and their signature file references.")
            
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

        # --- Add New Material Item Expander ---
        with st.expander("📦 Add New Material Item"):
            st.write("#### ➕ Register New Material / Item")
            
            all_items = [r[0] for r in c.execute("SELECT item_no FROM materials").fetchall() if r[0] and r[0].isdigit()]
            if all_items:
                max_item_num = max([int(x) for x in all_items])
                suggested_item_no = str(max_item_num + 1).zfill(5)
            else:
                suggested_item_no = "00001"

            mc1, mc2 = st.columns(2)
            mat_item_no = mc1.text_input("Item Number", value=suggested_item_no)
            mat_desc = mc2.text_input("Description (e.g. PORTLAND CEMENT)")
            
            mc3, mc4 = st.columns(2)
            mat_unit = mc3.text_input("Unit (e.g. BAGS, LENGTH, LOT)")
            category_options = ["Direct Materials", "Equipment & Rental", "Tools & Consumables", "Fuel & Lubricants", "Subcontract & Services"]
            mat_category = mc4.selectbox("Category (Accounting Tag)", category_options)
            
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
                    st.success(f"Item '{mat_desc}' ({mat_category}) saved successfully as #{mat_item_no.strip()}!")
                    st.rerun()
                else:
                    st.warning("⚠️ Please fill in both Item Number and Description.")
            
            st.markdown("---")
            st.write("#### 📋 Registered Materials & Items List")
            materials_df = pd.read_sql_query(
                """SELECT 
                    item_no AS 'Item No', 
                    description AS 'Description', 
                    unit AS 'Unit', 
                    COALESCE(category, 'Direct Materials') AS 'Category'
                   FROM materials
                   ORDER BY item_no ASC""", 
                conn
            )
            st.dataframe(materials_df, use_container_width=True, hide_index=True) 

        # --- Add & Manage Suppliers Expander ---
        with st.expander("🚚 Add & Manage Suppliers"):
            st.write("#### ✏️ Edit or Register Supplier")
            
            suppliers_list = [s[0] for s in c.execute("SELECT supplier_name FROM suppliers ORDER BY supplier_name ASC").fetchall()]
            supplier_edit_options = ["-- Register New Supplier --"] + suppliers_list
            
            selected_supplier_to_edit = st.selectbox("Select Supplier to Edit (or choose to add new)", supplier_edit_options)
            
            edit_name = ""
            edit_loc = ""
            edit_contact_person = ""
            edit_contact_no = ""
            edit_tin = ""
            edit_vat = "VAT Registered"
            edit_terms = 0
            
            if selected_supplier_to_edit != "-- Register New Supplier --":
                sup_data = c.execute("""
                    SELECT supplier_name, location, contact_person, contact_number, tin_number, vat_type, terms_days 
                    FROM suppliers WHERE supplier_name = ?
                """, (selected_supplier_to_edit,)).fetchone()
                
                if sup_data:
                    edit_name = sup_data[0]
                    edit_loc = sup_data[1] if sup_data[1] else ""
                    edit_contact_person = sup_data[2] if sup_data[2] else ""
                    edit_contact_no = sup_data[3] if sup_data[3] else ""
                    edit_tin = sup_data[4] if sup_data[4] else ""
                    edit_vat = sup_data[5] if sup_data[5] in ["VAT Registered", "Non-VAT"] else "VAT Registered"
                    edit_terms = int(sup_data[6]) if sup_data[6] is not None else 0

            sc1, sc2 = st.columns(2)
            sup_name = sc1.text_input("Supplier Name", value=edit_name, help="If editing, keep name exact or type a new name to create.")
            sup_location = sc2.text_input("Location / Address", value=edit_loc)
            
            sc3, sc4 = st.columns(2)
            sup_contact_person = sc3.text_input("Contact Person", value=edit_contact_person)
            sup_contact_number = sc4.text_input("Contact Number", value=edit_contact_no)
            
            sc5, sc6 = st.columns(2)
            sup_tin = sc5.text_input("TIN Number (e.g., 000-000-000-000)", value=edit_tin)
            
            vat_index = 0 if edit_vat == "VAT Registered" else 1
            sup_vat = sc6.selectbox("VAT Status", ["VAT Registered", "Non-VAT"], index=vat_index)
            
            sup_terms = st.number_input("Payment Terms (Days)", min_value=0, value=edit_terms, step=1, help="0 means Cash on Delivery")
            
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
            
            st.markdown("---")
            st.write("#### 📋 Registered Suppliers List")
            suppliers_df = pd.read_sql_query(
                """SELECT 
                    supplier_name AS 'Supplier Name', 
                    location AS 'Location / Address', 
                    contact_person AS 'Contact Person', 
                    contact_number AS 'Contact Number',
                    tin_number AS 'TIN Number',
                    vat_type AS 'VAT Status',
                    terms_days AS 'Terms (Days)'
                   FROM suppliers""", 
                conn
            )
            st.dataframe(suppliers_df, use_container_width=True, hide_index=True)

        # Master Landing Page Data Table
        st.write("### 📊 Complete Master Landing Page")
        master_df = pd.read_sql_query("SELECT * FROM requests ORDER BY id DESC", conn)
        st.dataframe(master_df, use_container_width=True, hide_index=True)

        # --- DANGER ZONE: RESET DATA ---
        st.markdown("---")
        st.write("### 🚨 Danger Zone: Database Management")
        
        with st.expander("🗑️ Reset Test Data (Clear Transactions)"):
            st.warning("⚠️ **WARNING:** This action will permanently delete all transaction history (Requests, P.O.s, and Deliveries). Your master data (Projects, Suppliers, Materials, Activities) will be kept safe.")
            
            confirm_reset = st.radio(
                "Are you sure you want to clear all transactions?", 
                ("No, keep my data", "Yes, delete transactions")
            )
            
            if confirm_reset == "Yes, delete transactions":
                st.error("❗ You have selected to delete all transactions. Click the button below to execute.")
                
                if st.button("🗑️ Confirm and Clear Data", type="primary"):
                    c.execute("DELETE FROM requests")
                    c.execute("DELETE FROM deliveries")
                    
                    try:
                        c.execute("DELETE FROM sqlite_sequence WHERE name='requests'")
                        c.execute("DELETE FROM sqlite_sequence WHERE name='deliveries'")
                    except sqlite3.OperationalError:
                        pass 
                    
                    conn.commit()
                    st.success("✅ All test transactions have been successfully cleared!")
                    st.rerun()

    # ---------------------------------------------------------
    # TAB 2: PROJECT APPROVED REPORTS & SUPPLIER SUMMARY
    # ---------------------------------------------------------
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
            SELECT 
                pono AS 'P.O. Number',
                project_name AS 'Project Name',
                supplier AS 'Supplier',
                item_no AS 'Item No',
                description AS 'Description',
                activity AS 'Activity',
                qty AS 'Qty',
                unit AS 'Unit',
                price AS 'Unit Price',
                amount AS 'Total Amount',
                approved_timestamp AS 'Approved Date'
            FROM requests 
            WHERE status = 'Approved / Ongoing'
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
            total_spent = approved_df["Total Amount"].sum()
            total_qty = approved_df["Qty"].sum()
            total_pos = approved_df["P.O. Number"].nunique()

            m1, m2, m3 = st.columns(3)
            m1.metric("💰 Total Approved Cost", f"₱{total_spent:,.2f}")
            m2.metric("📦 Total Approved Quantity", f"{total_qty:,.0f} units")
            m3.metric("📄 Total Approved P.O.s", f"{total_pos} Orders")

            st.markdown("---")

            st.write("#### 📄 Detailed Approved Items List")
            st.dataframe(
                approved_df.style.format({
                    "Unit Price": "₱{:,.2f}",
                    "Total Amount": "₱{:,.2f}"
                }),
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")

            st.write("#### 📊 Consolidated Material Totals")
            
            aggregated_df = approved_df.groupby(["Item No", "Description", "Unit"]).agg(
                Total_Approved_Qty=('Qty', 'sum'),
                Total_Approved_Amount=('Total Amount', 'sum')
            ).reset_index().rename(columns={
                "Total_Approved_Qty": "Total Approved Quantity",
                "Total_Approved_Amount": "Total Spent (₱)"
            })

            st.dataframe(
                aggregated_df.style.format({
                    "Total Approved Quantity": "{:,.2f}",
                    "Total Spent (₱)": "₱{:,.2f}"
                }),
                use_container_width=True,
                hide_index=True
            )

    # ---------------------------------------------------------
    # TAB 3: ACCOUNTS PAYABLE & DUE DATES
    # ---------------------------------------------------------
    with tab_payables:
        st.write("### 💸 Accounts Payable (A/P) Monitor")
        st.info("This view only shows official deliveries. Due dates are strictly calculated from the actual Receiving Date.")
        
        ap_query = """
            SELECT 
                d.pono AS 'PO Number',
                d.dr_number AS 'DR Number',
                d.supplier AS 'Supplier',
                d.project_name AS 'Project',
                d.total_amount AS 'Total Amount',
                d.received_date AS 'Date Received',
                s.terms_days AS 'Terms (Days)',
                d.payment_status AS 'Status'
            FROM deliveries d
            LEFT JOIN suppliers s ON d.supplier = s.supplier_name
            WHERE d.payment_status = 'Unpaid'
            ORDER BY d.received_date ASC
        """
        ap_df = pd.read_sql_query(ap_query, conn)
        
        if not ap_df.empty:
            ap_df['Date Received'] = pd.to_datetime(ap_df['Date Received'])
            ap_df['Terms (Days)'] = ap_df['Terms (Days)'].fillna(0).astype(int)
            
            ap_df['Due Date'] = ap_df['Date Received'] + pd.to_timedelta(ap_df['Terms (Days)'], unit='D')
            
            ap_df['Date Received'] = ap_df['Date Received'].dt.strftime('%Y-%m-%d')
            ap_df['Due Date'] = ap_df['Due Date'].dt.strftime('%Y-%m-%d')
            
            st.dataframe(
                ap_df.style.format({"Total Amount": "₱{:,.2f}"}), 
                use_container_width=True, 
                hide_index=True
            )
            
            total_unpaid = ap_df['Total Amount'].sum()
            st.error(f"**Total Outstanding Payables:** ₱ {total_unpaid:,.2f}")
            
            st.markdown("---")
            st.write("#### ✅ Mark Delivery as Paid")
            col_pay1, col_pay2 = st.columns([2, 1])
            dr_to_pay = col_pay1.selectbox("Select DR Number to mark as Paid", ap_df['DR Number'].tolist())
            
            if col_pay2.button("Confirm Payment", type="primary"):
                c.execute("UPDATE deliveries SET payment_status = 'Paid' WHERE dr_number = ?", (dr_to_pay,))
                conn.commit()
                st.success(f"DR #{dr_to_pay} marked as paid successfully!")
                st.rerun()
        else:
            st.success("🎉 No outstanding payables!")
