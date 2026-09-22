import sqlite3
import pandas as pd
import streamlit as st
import re
import os
from datetime import datetime
from io import BytesIO

# ==============================================================================
# BIR FORM 2307 (JANUARY 2018 ENCS) OFFICIAL TEMPLATE GENERATOR
# ==============================================================================
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_bir_2307_pdf(voucher_data, supplier_data, wht_details):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=18, 
        leftMargin=18, 
        topMargin=18, 
        bottomMargin=18
    )
    story = []
    styles = getSampleStyleSheet()

    # --- Typography Styles ---
    s_lbl = ParagraphStyle('FormLbl', parent=styles['Normal'], fontSize=6, leading=7, fontName='Helvetica-Bold')
    s_val = ParagraphStyle('FormVal', parent=styles['Normal'], fontSize=7.5, leading=9, fontName='Helvetica')
    s_val_right = ParagraphStyle('FormValR', parent=styles['Normal'], alignment=2, fontSize=7.5, leading=9, fontName='Helvetica')
    s_center = ParagraphStyle('CenterTxt', parent=styles['Normal'], alignment=1, fontSize=7, leading=8.5)
    s_th = ParagraphStyle('TH', parent=styles['Normal'], alignment=1, fontSize=6, leading=7, fontName='Helvetica-Bold')

    BG_GREY = colors.HexColor('#E5E5E5')

    # ==========================================================================
    # 1. TOP HEADER & TITLE BLOCK
    # ==========================================================================
    hdr_data = [
        [
            Paragraph("For BIR<br/>Use Only", s_lbl),
            Paragraph("BCS/<br/>Item:", s_lbl),
            Paragraph("<b>Republic of the Philippines</b><br/>Department of Finance<br/>Bureau of Internal Revenue", s_center),
            ""
        ],
        [
            Paragraph("<b>BIR Form No. 2307</b><br/>January 2018 (ENCS)", s_center),
            "",
            Paragraph("<b>Certificate of Creditable Tax Withheld at Source</b>", s_center),
            Paragraph("||||||||||||||||||||||||||<br/>2307 01/18ENCS", s_center)
        ]
    ]
    t_hdr = Table(hdr_data, colWidths=[55, 55, 336, 130])
    t_hdr.setStyle(TableStyle([
        ('SPAN', (2,0), (3,0)),
        ('SPAN', (0,1), (1,1)),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_hdr)
    story.append(Spacer(1, 10))

    # ==========================================================================
    # 2. PERIOD COVERED
    # ==========================================================================
    p_from = wht_details.get('period_from', '')
    p_to = wht_details.get('period_to', '')

    instr_data = [
        [
            Paragraph("Fill in all applicable spaces. Mark all appropriate boxes with an 'X'.", s_lbl),
            Paragraph(f"<b>1</b> For the Period From: <b>{p_from}</b> To: <b>{p_to}</b>", s_lbl)
        ]
    ]
    t_instr = Table(instr_data, colWidths=[240, 336])
    t_instr.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (0,0), BG_GREY),
    ]))
    story.append(t_instr)
    story.append(Spacer(1, 10))

    # ==========================================================================
    # 3. PART I - PAYEE INFORMATION
    # ==========================================================================
    s_tin = supplier_data.get('tin') or '000-000-000-000'
    s_name = supplier_data.get('name') or 'N/A'
    s_addr = supplier_data.get('address') or 'N/A'
    s_zip = supplier_data.get('zip') or ''

    payee_data = [
        [Paragraph("<b>Part I – Payee Information</b>", s_lbl), ""],
        [Paragraph(f"<b>2</b> TIN: {s_tin}", s_val), ""],
        [Paragraph(f"<b>3</b> Payee's Name: {s_name}", s_val), ""],
        [Paragraph(f"4 Registered Address<br/>{s_addr}", s_val),
         Paragraph(f"4A ZIP Code<br/>{s_zip}", s_val)],
        [Paragraph("5 Foreign Address, if applicable", s_val), ""]
    ]
    t_payee = Table(payee_data, colWidths=[460, 116])
    t_payee.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('SPAN', (0,1), (1,1)),
        ('SPAN', (0,2), (1,2)),
        ('SPAN', (0,4), (1,4)),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), BG_GREY),
    ]))
    story.append(t_payee)
    story.append(Spacer(1, 10))

    # ==========================================================================
    # 4. PART II - PAYOR INFORMATION
    # ==========================================================================
    payor_data = [
        [Paragraph("<b>Part II – Payor Information</b>", s_lbl), ""],
        [Paragraph("6 TIN: 908-376-188-000", s_val), ""],
        [Paragraph("7 Payor's Name: TUANSON CONSTRUCTION", s_val), ""],
        [Paragraph("8 Registered Address<br/>162 P. Labuca St., Cansojong, Talisay City, Cebu", s_val),
         Paragraph("8A ZIP Code<br/>6045", s_val)]
    ]
    t_payor = Table(payor_data, colWidths=[460, 116])
    t_payor.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('SPAN', (0,1), (1,1)),
        ('SPAN', (0,2), (1,2)),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), BG_GREY),
    ]))
    story.append(t_payor)
    story.append(Spacer(1, 10))

     # ==========================================================================
    # 5. PART III - DETAILS OF INCOME PAYMENTS & TAXES WITHHELD
    # ==========================================================================
    gross_amt = wht_details.get('gross', 0.0)
    tax_amt = wht_details.get('tax', 0.0)
    m1 = wht_details.get('m1', 0.0)
    m2 = wht_details.get('m2', gross_amt)
    m3 = wht_details.get('m3', 0.0)

    details_data = [
        ["Income Payments Subject to Expanded Withholding Tax","ATC","1st Month","2nd Month","3rd Month","Total","Tax Withheld"],
        [wht_details.get('income_type',''), wht_details.get('atc',''),
         f"{m1:,.2f}" if m1 else "-", f"{m2:,.2f}" if m2 else "-", f"{m3:,.2f}" if m3 else "-",
         f"{gross_amt:,.2f}", f"{tax_amt:,.2f}"],
        ["Total","","","","",f"{gross_amt:,.2f}",f"{tax_amt:,.2f}"]
    ]
    t_details = Table(details_data, colWidths=[170,36,65,65,65,75,100])
    t_details.setStyle(TableStyle([
        ('BOX',(0,0),(-1,-1),1,colors.black),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('BACKGROUND',(0,0),(-1,0),BG_GREY),
        ('ALIGN',(2,1),(-1,-1),'RIGHT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    story.append(t_details)
    story.append(Spacer(1, 20))

    # ==========================================================================
    # 6. PERJURY DECLARATION & SIGNATORIES
    # ==========================================================================
    perjury_text = """We declare under the penalties of perjury that this certificate has been made in good faith,
    verified by us, and to the best of our knowledge and belief, is true and correct, pursuant to the provisions of the
    National Internal Revenue Code, as amended, and the regulations issued under authority thereof. Further, we give
    our consent to the processing of our information as contemplated under the Data Privacy Act of 2012 (R.A. No. 10173)."""
    story.append(Paragraph(perjury_text, ParagraphStyle('Perj', parent=styles['Normal'], fontSize=6, leading=7)))
    story.append(Spacer(1, 20))

    sig_data = [
        ["__________________________", "__________________________"],
        ["MICHELLE F. BAISAC", "Payee's Authorized Representative"],
        ["Accounting Officer / TIN 239-431-789", "(Signature over Printed Name)"]
    ]
    t_sig = Table(sig_data, colWidths=[270,270])
    t_sig.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER')]))
    story.append(t_sig)
    story.append(Spacer(1, 20))

    # Conforme Section
    conforme_data = [
        ["__________________________", "__________________________"],
        ["Conforme", "Payee/Payor’s Authorized Representative/Tax Agent"],
        ["(Signature over Printed Name)", "(Indicate Title/Designation and TIN)"]
    ]
    t_conforme = Table(conforme_data, colWidths=[270,270])
    t_conforme.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER')]))
    story.append(t_conforme)

    # Footer note
    story.append(Spacer(1, 10))
    story.append(Paragraph("*NOTE: The BIR Data Privacy is in the BIR website (www.bir.gov.ph)", ParagraphStyle('FootNote', parent=styles['Normal'], fontSize=5, leading=6)))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue() 
    # ==============================================================================
    # END OF - BIR FORM 2307 (JANUARY 2018 ENCS) OFFICIAL TEMPLATE GENERATOR
    # ==============================================================================
#============================================================================Bank Reconciliation===============================
import streamlit as st
import pandas as pd
from datetime import datetime, date

def render_bank_reconciliation_tab(conn):
    c = conn.cursor()
    st.header("🏦 Bank Reconciliation Statement")
    st.caption("Reconcile General Ledger Cash in Bank balances, clear floating checks, and record official snapshots.")

    # --- 1. FILTER CONTROLS ---
    col_f1, col_f2, col_f3 = st.columns(3)
    
    # Fetch active Cash/Bank accounts
    try:
        bank_accounts = c.execute("""
            SELECT DISTINCT account_code, account_name 
            FROM journal_entries 
            WHERE account_code LIKE '103%' OR account_name LIKE '%Bank%' OR account_name LIKE '%Cash%'
            ORDER BY account_code
        """).fetchall()
    except Exception:
        bank_accounts = []

    account_options = [f"[{acc[0]}] {acc[1]}" for acc in bank_accounts] if bank_accounts else ["[10330] Cash in Bank BDO"]
    selected_account_str = col_f1.selectbox("Select Bank Account", options=account_options)
    selected_acct_code = selected_account_str.split("]")[0].replace("[", "").strip()

    # Date Period Selection
    today = date.today()
    first_day_curr_month = date(today.year, today.month, 1)
    
    date_range = col_f2.date_input(
        "Select Reconciliation Period (From - To)",
        value=(first_day_curr_month, today),
        key="bank_rec_date_range"
    )

    if isinstance(date_range, (tuple, list)):
        if len(date_range) == 2:
            from_date, to_date = date_range
        elif len(date_range) == 1:
            from_date = to_date = date_range[0]
        else:
            from_date = to_date = today
    elif isinstance(date_range, date):
        from_date = to_date = date_range
    else:
        from_date = to_date = today

    to_date_str = to_date.strftime('%Y-%m-%d') if hasattr(to_date, 'strftime') else str(to_date)

    statement_ending_balance = col_f3.number_input(
        "Bank Statement Ending Balance (₱)",
        min_value=0.0,
        value=0.0,
        step=1000.0,
        help="Enter the final balance shown on the bank statement for this period."
    )

    st.markdown("---")

    # --- 2. CALCULATE GL BOOK BALANCE ---
    try:
        gl_balance_row = c.execute("""
            SELECT SUM(debit) - SUM(credit) 
            FROM journal_entries 
            WHERE account_code = ? AND entry_date <= ?
        """, (selected_acct_code, to_date_str)).fetchone()
        gl_book_balance = float(gl_balance_row[0]) if gl_balance_row and gl_balance_row[0] is not None else 0.0
    except Exception:
        gl_book_balance = 0.0

    # --- 3. FETCH UNCLEARED / OUTSTANDING CHECKS ---
    try:
        raw_checks = c.execute("SELECT * FROM floating_checks").fetchall()
        cols = [description[0] for description in c.description]
        raw_df = pd.DataFrame(raw_checks, columns=cols)
    except Exception:
        raw_df = pd.DataFrame()

    if not raw_df.empty:
        status_col = next((col for col in ['status', 'state'] if col in raw_df.columns), None)
        if status_col:
            raw_df = raw_df[
                raw_df[status_col].isna() | 
                raw_df[status_col].isin(['Pending', 'Un-encashed', ''])
            ]

        date_col = next((col for col in ['check_date', 'created_at', 'issue_date'] if col in raw_df.columns), None)
        if date_col:
            raw_df[date_col] = raw_df[date_col].astype(str)
            raw_df = raw_df[
                (raw_df[date_col] <= to_date_str) | 
                (raw_df[date_col].isna()) | 
                (raw_df[date_col] == 'None') | 
                (raw_df[date_col] == '')
            ]

        id_col = 'id' if 'id' in raw_df.columns else raw_df.index
        v_col = next((col for col in ['voucher_no', 'ref_no', 'apv_no'] if col in raw_df.columns), None)
        chk_col = next((col for col in ['check_no', 'check_number'] if col in raw_df.columns), None)
        payee_col = next((col for col in ['payee', 'supplier_name', 'payee_name', 'supplier', 'description'] if col in raw_df.columns), None)
        amt_col = next((col for col in ['amount', 'check_amount', 'debit'] if col in raw_df.columns), None)

        df_checks = pd.DataFrame({
            "ID": raw_df[id_col] if isinstance(id_col, str) else id_col,
            "Voucher No": raw_df[v_col] if v_col else "",
            "Check No": raw_df[chk_col] if chk_col else "",
            "Issue Date": raw_df[date_col] if date_col else "",
            "Payee / Supplier": raw_df[payee_col] if payee_col else "",
            "Amount (₱)": pd.to_numeric(raw_df[amt_col], errors='coerce').fillna(0.0) if amt_col else 0.0,
            "Status": raw_df[status_col] if status_col else "Pending"
        })
    else:
        df_checks = pd.DataFrame(columns=["ID", "Voucher No", "Check No", "Issue Date", "Payee / Supplier", "Amount (₱)", "Status"])

    if not df_checks.empty:
        df_checks["Mark Cleared"] = False
        df_checks["Passbook Clearing Date"] = today

    # --- 4. INTERACTIVE RECONCILIATION TABLE ---
    st.subheader("📋 Outstanding / Floating Checks")
    st.write("Mark checks as **Cleared** and enter the **Passbook Clearing Date** as shown on your bank statement:")

    if not df_checks.empty:
        edited_df = st.data_editor(
            df_checks,
            column_config={
                "ID": None,
                "Mark Cleared": st.column_config.CheckboxColumn("Cleared?", default=False),
                "Passbook Clearing Date": st.column_config.DateColumn(
                    "Passbook Clearing Date",
                    format="YYYY-MM-DD",
                    default=today,
                    help="Select the exact date this check was cleared per passbook/statement"
                ),
                "Amount (₱)": st.column_config.NumberColumn("Amount (₱)", format="₱%,.2f"),
                "Issue Date": st.column_config.TextColumn("Issue Date"),
            },
            disabled=["Voucher No", "Check No", "Issue Date", "Payee / Supplier", "Amount (₱)", "Status"],
            hide_index=True,
            use_container_width=True,
            key="editor_bank_rec"
        )
        
        cleared_rows = edited_df[edited_df["Mark Cleared"] == True]
        total_cleared_amt = float(cleared_rows["Amount (₱)"].sum()) if not cleared_rows.empty else 0.0
        
        remaining_outstanding_rows = edited_df[edited_df["Mark Cleared"] == False]
        total_outstanding_amt = float(remaining_outstanding_rows["Amount (₱)"].sum()) if not remaining_outstanding_rows.empty else 0.0
    else:
        st.info("ℹ️ No pending or outstanding checks found for this account within the selected period.")
        total_cleared_amt = 0.0
        total_outstanding_amt = 0.0
        edited_df = pd.DataFrame()
        cleared_rows = pd.DataFrame()

    # --- 5. RECONCILIATION SUMMARY CARDS ---
    st.markdown("---")
    st.subheader("📊 Reconciliation Summary")

    adjusted_bank_balance = statement_ending_balance - total_outstanding_amt
    out_of_balance_variance = gl_book_balance - adjusted_bank_balance

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("GL Book Balance", f"₱{gl_book_balance:,.2f}")
    m2.metric("Bank Statement Balance", f"₱{statement_ending_balance:,.2f}")
    m3.metric("Less: Outstanding Checks", f"₱{total_outstanding_amt:,.2f}")
    m4.metric("Adjusted Bank Balance", f"₱{adjusted_bank_balance:,.2f}")

    if abs(out_of_balance_variance) < 0.01:
        st.success("✅ **Balanced!** Your GL Book Balance perfectly matches the Adjusted Bank Balance.")
    else:
        st.warning(f"⚠️ **Out of Balance Discrepancy:** ₱{out_of_balance_variance:,.2f}.")

    # --- 6. SAVE RECONCILIATION & COMMIT CHECKS ---
    btn_col1, btn_col2 = st.columns([2, 1])
    
    with btn_col1:
        if st.button("💾 Finalize & Save Bank Reconciliation Snapshot", type="primary"):
            try:
                # Use the existing conn passed to the function, or grab a fresh one if needed
                c_save = conn.cursor()
        
                # 1. Update cleared checks in floating_checks table
                if 'edited_df' in locals() and not edited_df.empty:
                    for _, row in edited_df.iterrows():
                        if row.get("Mark Cleared"):
                            cleared_date = str(row.get("Passbook Clearing Date", date.today()))
                            check_no = str(row.get("Check No", ""))
                            
                            try:
                                c_save.execute("""
                                    UPDATE floating_checks 
                                    SET status = 'Cleared', cleared_at = ? 
                                    WHERE check_no = ?
                                """, (cleared_date, check_no))
                            except Exception:
                                c_save.execute("""
                                    UPDATE floating_checks 
                                    SET status = 'Cleared' 
                                    WHERE check_no = ?
                                """, (check_no,))
        
                # 2. Save snapshot to bank_reconciliations table
                c_save.execute("""
                    INSERT INTO bank_reconciliations (
                        reconciliation_date,
                        account_code,
                        account_name,
                        gl_book_balance,
                        bank_statement_balance,
                        total_outstanding_checks,
                        total_deposits_in_transit,
                        adjusted_bank_balance,
                        variance,
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date.today().strftime("%Y-%m-%d"),
                    selected_acct_code,
                    selected_account_str,
                    float(gl_book_balance),
                    float(statement_ending_balance),
                    float(total_outstanding_amt),
                    0.0,
                    float(adjusted_bank_balance),
                    float(out_of_balance_variance),
                    'Completed'
                ))
        
                conn.commit()
                
                st.success("Reconciliation snapshot saved successfully!")
                st.rerun()
        
            except Exception as e:
                st.error(f"Error committing bank reconciliation: {e}")

    # --- 7. HISTORICAL RECONCILIATIONS TABLE ---
    st.markdown("---")
    with st.expander("📜 View Past Reconciliation Reports", expanded=False):
        try:
            history_rows = c.execute("""
                SELECT reconciliation_date, account_code, account_name, 
                       gl_book_balance, bank_statement_balance, total_outstanding_checks, 
                       adjusted_bank_balance, variance, status, created_at
                FROM bank_reconciliations
                WHERE account_code = ?
                ORDER BY reconciliation_date DESC
            """, (selected_acct_code,)).fetchall()

            if history_rows:
                df_history = pd.DataFrame(history_rows, columns=[
                    "Date", "Account Code", "Account Name", 
                    "GL Balance (₱)", "Statement Balance (₱)", "Outstanding Checks (₱)", 
                    "Adjusted Balance (₱)", "Variance (₱)", "Status", "Recorded At"
                ])
                st.dataframe(df_history, use_container_width=True, hide_index=True)
            else:
                st.info("No saved reconciliations found for this account.")
        except Exception as e:
            st.warning(f"Unable to load reconciliation history: {e}")
#============================================================================end of bank reconciliation========================

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
        return f"{words_str} & {cents:02d}/100."
    return f"{words_str} PESOS"

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

#================================================================
def amount_to_words(amount):
    """Converts numeric amounts to Philippine Currency words matching custom CV PDF format."""
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

    currency = "PESO" if int(amount) == 1 else "PESOS"

    if cents > 0:
        return f"{words_str} {currency} AND {cents:02d}/100."
    else:
        return f"{words_str} {currency}"
#===========================================================
def generate_voucher_number(cursor, col_name, prefix):
    existing_numbers = []
    
    # 1. Scan journal_entries
    try:
        res = cursor.execute("SELECT DISTINCT voucher_no FROM journal_entries WHERE voucher_no LIKE ?", (f"{prefix}-%",)).fetchall()
        existing_numbers.extend([r[0] for r in res if r[0]])
    except Exception:
        pass

    # 2. Scan deliveries
    try:
        res = cursor.execute("SELECT DISTINCT cv_number FROM deliveries WHERE cv_number LIKE ?", (f"{prefix}-%",)).fetchall()
        existing_numbers.extend([r[0] for r in res if r[0]])
    except Exception:
        pass

    # 3. Scan requests
    try:
        res = cursor.execute("SELECT DISTINCT cv_number FROM requests WHERE cv_number LIKE ?", (f"{prefix}-%",)).fetchall()
        existing_numbers.extend([r[0] for r in res if r[0]])
    except Exception:
        pass

    # 4. Scan floating_checks
    try:
        res = cursor.execute("SELECT DISTINCT voucher_no FROM floating_checks WHERE voucher_no LIKE ?", (f"{prefix}-%",)).fetchall()
        existing_numbers.extend([r[0] for r in res if r[0]])
    except Exception:
        pass

    # Extract maximum numeric sequence
    max_num = 0
    for v_no in existing_numbers:
        try:
            num_part = int(str(v_no).split('-')[-1])
            if num_part > max_num:
                max_num = num_part
        except (ValueError, IndexError):
            pass
            
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
#==================================================================
def get_balance_sheet(conn, as_of_date):
    # Format date boundary string safely
    as_of_str = pd.to_datetime(as_of_date).strftime('%Y-%m-%d 23:59:59')
    
    query = f"""
        SELECT 
            j.account_code,
            j.account_name,
            COALESCE(c.account_type, 
                CASE 
                    WHEN j.account_code LIKE '1%' THEN 'Asset'
                    WHEN j.account_code LIKE '2%' THEN 'Liability'
                    WHEN j.account_code LIKE '3%' THEN 'Equity'
                    ELSE 'Other'
                END
            ) AS account_type,
            SUM(
                CASE 
                    WHEN j.account_code LIKE '1%' THEN (j.debit - j.credit)
                    WHEN j.account_code LIKE '2%' THEN (j.credit - j.debit)
                    WHEN j.account_code LIKE '3%' THEN (j.credit - j.debit)
                    ELSE (j.debit - j.credit)
                END
            ) AS amount
        FROM journal_entries j
        LEFT JOIN chart_of_accounts c ON j.account_code = c.account_code
        WHERE (
            c.account_type IN ('Asset', 'Liability', 'Equity') 
            OR j.account_code LIKE '1%' 
            OR j.account_code LIKE '2%' 
            OR j.account_code LIKE '3%'
        )
        AND j.entry_date <= '{as_of_str}'
        GROUP BY j.account_code, j.account_name, account_type
        HAVING amount != 0
    """
    return pd.read_sql_query(query, conn)    
#=====================================================================

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
#=================================Database=============================================
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute("PRAGMA journal_mode = WAL;")
        c.execute("PRAGMA synchronous = NORMAL;")
        c.execute("PRAGMA busy_timeout = 5000;")
    except Exception:
        pass  # Turso/libsql may safely ignore some PRAGMA statements

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
            description TEXT,
            supplier TEXT
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
            supplier TEXT,
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
        ("requests", "supplier", "TEXT"),
        ("suppliers", "terms_days", "INTEGER DEFAULT 0"),
        ("requests", "payment_status", "TEXT DEFAULT 'Unpaid'"),
        ("requests", "received_status", "TEXT DEFAULT 'Pending'"),
        ("requests", "received_timestamp", "DATETIME"),
        ("requests", "requester_name", "TEXT"),
        ("activities", "contract_amount", "REAL DEFAULT 0.0"),
        ("activities", "qty", "REAL DEFAULT 1.0"),
        ("activities", "unit", "TEXT DEFAULT 'lot'"),
        ("deliveries", "supplier", "TEXT"),
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
        ("inventory_ledger", "supplier", "TEXT"),
        ("inventory_ledger", "status", "TEXT DEFAULT 'Completed'"),
        ("journal_entries", "supplier", "TEXT")
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
#===============================database
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
# --- CV PDF GENERATOR FUNCTION ---
def create_cv_pdf(cv_no, cv_date, apv_no, supplier, pay_method, total_amt, conn=None):
    import os
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from io import BytesIO

    # 1. REGISTER ROBOTO FONT FOR NATIVE ₱ RENDERING
    pdf_font = "Helvetica"
    font_candidates = ["Roboto-Regular.ttf", "roboto.ttf", "Roboto.ttf"]
    for font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont("Roboto", font_path))
                pdf_font = "Roboto"
                break
            except Exception:
                pass

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    # Fetch Supplier Location
    sup_location = "Cebu, Philippines"
    if conn:
        try:
            c = conn.cursor()
            row = c.execute("SELECT location FROM suppliers WHERE supplier_name = ?", (supplier,)).fetchone()
            if row and row[0]:
                sup_location = row[0]
        except Exception:
            pass

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName=pdf_font, fontSize=16, leading=20, alignment=1)
    sub_title_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontName=pdf_font, fontSize=9, leading=12, alignment=1)
    body_norm = ParagraphStyle('BodyNorm', parent=styles['Normal'], fontName=pdf_font, fontSize=8, leading=10)

    story.append(Paragraph("<b>Tuanson Construction</b>", title_style))
    story.append(Paragraph("162 P. Labuca St., Cansojong, Talisay City, Cebu", sub_title_style))
    story.append(Paragraph("Tel: - Fax: -", sub_title_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Payment Voucher</b>", title_style))
    story.append(Spacer(1, 10))

    cheque_no_str = "-"
    cheque_date_str = "-"
    po_no_str = "-"
    project_str = "-"

    if conn:
        try:
            c = conn.cursor()
            # If standard APV payment
            if apv_no and apv_no.strip():
                del_row = c.execute("""
                    SELECT cheque_no, cheque_date, pono, project_name 
                    FROM deliveries WHERE apv_number = ? AND supplier = ?
                """, (apv_no, supplier)).fetchone()
                if del_row:
                    cheque_no_str = del_row[0] or "-"
                    cheque_date_str = del_row[1] or "-"
                    po_no_str = del_row[2] or "-"
                    project_str = del_row[3] or "-"
            # If Advance PDC (PO Basis)
            else:
                req_row = c.execute("""
                    SELECT cheque_no, cheque_date, pono, project_name 
                    FROM requests WHERE cv_number = ? AND supplier = ?
                """, (cv_no, supplier)).fetchone()
                if req_row:
                    cheque_no_str = req_row[0] or "-"
                    cheque_date_str = req_row[1] or "-"
                    po_no_str = req_row[2] or "-"
                    project_str = req_row[3] or "-"
        except Exception:
            pass

    supplier_box_html = f"<b>{supplier}</b><br/>{sup_location}"
    meta_box_html = f"<b>NO.:</b> {cv_no}<br/><b>DATE:</b> {cv_date}<br/><b>CHEQUE NO.:</b> {cheque_no_str} / {cheque_date_str}"

    header_table_data = [[Paragraph(supplier_box_html, body_norm), Paragraph(meta_box_html, body_norm)]]
    t_header = Table(header_table_data, colWidths=[340, 200])
    t_header.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), pdf_font),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 10))

    apv_ref = f"APV#{apv_no}" if apv_no else "Advance Downpayment"
    po_ref = f"(PO#{po_no_str})" if po_no_str != "-" else ""
    desc_text = f"Payment for materials / services ({apv_ref}) {po_ref} for {project_str}".strip()

    acct_code = "20100" if apv_no else "10500"
    acct_name = supplier if apv_no else f"Advances to Suppliers - {supplier}"

    part_data = [
        [Paragraph("<b>A/C CODE</b>", body_norm), Paragraph("<b>A/C NAME</b>", body_norm), Paragraph("<b>DESCRIPTION</b>", body_norm), Paragraph("<b>AMOUNT</b>", body_norm)],
        [Paragraph(acct_code, body_norm), Paragraph(acct_name, body_norm), Paragraph(desc_text, body_norm), Paragraph(f"₱{total_amt:,.2f}", body_norm)]
    ]
    t_part = Table(part_data, colWidths=[70, 150, 230, 90])
    t_part.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), pdf_font),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (3,0), (3,-1), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_part)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Journals:</b>", body_norm))
    story.append(Spacer(1, 3))
    
    # Cleaned duplicate account code "10330:" from "Cash in Bank BDO"
    j_data = [
        [Paragraph("<b>Doc No.</b>", body_norm), Paragraph("<b>Date</b>", body_norm), Paragraph("<b>Account #</b>", body_norm), Paragraph("<b>Account Name</b>", body_norm), Paragraph("<b>Debit</b>", body_norm), Paragraph("<b>Credit</b>", body_norm)],
        [Paragraph(cv_no, body_norm), Paragraph(cv_date, body_norm), Paragraph(acct_code, body_norm), Paragraph(acct_name, body_norm), Paragraph(f"{total_amt:,.2f}", body_norm), Paragraph("", body_norm)],
        [Paragraph(cv_no, body_norm), Paragraph(cv_date, body_norm), Paragraph("10330", body_norm), Paragraph("Cash in Bank BDO", body_norm), Paragraph("", body_norm), Paragraph(f"{total_amt:,.2f}", body_norm)],
        [Paragraph("", body_norm), Paragraph("", body_norm), Paragraph("", body_norm), Paragraph("<b>TOTAL</b>", body_norm), Paragraph(f"<b>{total_amt:,.2f}</b>", body_norm), Paragraph(f"<b>{total_amt:,.2f}</b>", body_norm)]
    ]
    t_j = Table(j_data, colWidths=[65, 65, 65, 185, 80, 80])
    t_j.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), pdf_font),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (4,0), (5,-1), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_j)
    story.append(Spacer(1, 10))

    doc_data = [
        [Paragraph("<b>Type</b>", body_norm), Paragraph("<b>Doc. No.</b>", body_norm), Paragraph("<b>Doc. Date</b>", body_norm), Paragraph("<b>Description</b>", body_norm), Paragraph("<b>Orig. Amount</b>", body_norm), Paragraph("<b>Paid Amount</b>", body_norm)],
        [Paragraph("BIL", body_norm), Paragraph(f"PO#{po_no_str}", body_norm), Paragraph(cv_date, body_norm), Paragraph(f"PAYABLE FOR MATERIALS FOR \"{project_str.upper()}\"", body_norm), Paragraph(f"{total_amt:,.2f}", body_norm), Paragraph(f"{total_amt:,.2f}", body_norm)]
    ]
    t_doc = Table(doc_data, colWidths=[40, 75, 65, 200, 80, 80])
    t_doc.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), pdf_font),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (4,0), (5,-1), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_doc)
    story.append(Spacer(1, 10))

    # 2. CONVERT NUMBER TO WORDS USING YOUR HELPER FUNCTION
    try:
        amt_words = amount_to_words(total_amt)
    except Exception:
        amt_words = f"PHILIPPINE PESO {total_amt:,.2f}"

    r_align_style = ParagraphStyle('RAlign', parent=body_norm, alignment=2)

    words_data = [
        [Paragraph(f"<b>AMOUNT IN WORDS:</b><br/>{amt_words.upper()}", body_norm), 
         Paragraph(f"SUB TOTAL: ₱{total_amt:,.2f}<br/>ROUNDING ADJ: 0.00<br/><b>NET TOTAL PHP: ₱{total_amt:,.2f}</b>", r_align_style)]
    ]
    t_words = Table(words_data, colWidths=[360, 180])
    t_words.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), pdf_font),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_words)
    story.append(Spacer(1, 40))

    sig_data = [
        [Paragraph("____________________________________<br/><b>APPROVED BY</b>", ParagraphStyle('C1', parent=body_norm, alignment=1)),
         Paragraph("____________________________________<br/><b>RECEIVED BY</b>", ParagraphStyle('C2', parent=body_norm, alignment=1))]
    ]
    t_sig = Table(sig_data, colWidths=[270, 270])
    t_sig.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), pdf_font),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_sig)

    doc.build(story)
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

    payee_x    = left_margin + (7 * mm)    # Column for Payee
    payee_y    = top_y - (13 * mm)          # Payee Row

    amt_num_x  = left_margin + (127 * mm)   # Column for Numeric Amount
    amt_num_y  = top_y - (13 * mm)          # Same row as Payee

    words_x    = left_margin + (3 * mm)     # Column for Amount in Words
    words_y    = top_y - (22 * mm)          # Words Row

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
                    
#=================================================================================
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

    with tab_receive:
        st.write("### 🚚 Record Supplier Deliveries")
        st.info("Log items that have arrived on-site (full or partial delivery) and upload attached Delivery Receipts (DR), Sales Invoices (SI), or Official Receipts (OR).")

        # Database migration safeguard: ensures received_qty column exists
        try:
            c.execute("ALTER TABLE requests ADD COLUMN received_qty REAL DEFAULT 0.0")
            conn.commit()
        except Exception:
            pass

        if st.button("🔄 Refresh Deliveries", key="btn_refresh_receive_deliveries"):
            st.rerun()
        
        if "receive_success_msg" in st.session_state:
            st.success(st.session_state.pop("receive_success_msg"))

        # Fetch POs that have undelivered remaining quantities
        pending_recv_df = pd.read_sql_query("""
            SELECT 
                pono AS 'PO Number', 
                supplier AS 'Supplier', 
                project_name AS 'Project', 
                SUM(price * (qty - COALESCE(received_qty, 0))) AS 'Unreceived Value', 
                approved_timestamp AS 'Date Approved'
            FROM requests
            WHERE status = 'Approved / Ongoing' 
              AND (received_status IS NULL OR received_status != 'Received')
              AND (qty - COALESCE(received_qty, 0)) > 0
              AND pono IS NOT NULL AND pono != ''
            GROUP BY pono
            ORDER BY approved_timestamp ASC
        """, conn)
        
        if not pending_recv_df.empty:
            st.dataframe(
                pending_recv_df.style.format({"Unreceived Value": "₱{:,.2f}"}), 
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
            
            dr_number = f"{doc_prefix}#{raw_doc_no}" if raw_doc_no else ""
            
            # Fetch line items for the selected PO to handle partial delivery quantities
            po_items = c.execute("""
                SELECT id, item_no, description, qty, COALESCE(received_qty, 0), price, unit 
                FROM requests 
                WHERE pono = ? AND status = 'Approved / Ongoing'
            """, (po_to_receive,)).fetchall()

            st.write("##### 📦 Specify Quantities Delivered Today")
            
            received_inputs = {}
            total_delivery_amount = 0.0

            for req_id, item_no, desc, ordered_qty, prev_rec, price, unit in po_items:
                rem_qty = max(0.0, float(ordered_qty) - float(prev_rec))
                if rem_qty <= 0:
                    continue

                c1, c2, c3 = st.columns([3, 2, 2])
                c1.markdown(f"**{desc}**\n*(Unit: {unit} | Price: ₱{price:,.2f})*")
                c2.caption(f"Ordered: `{ordered_qty:,.0f}` | Prev Rec: `{prev_rec:,.0f}`\n**Remaining: {rem_qty:,.0f}**")
                
                qty_today = c3.number_input(
                    "Qty Received Today",
                    min_value=0.0,
                    max_value=float(rem_qty),
                    value=float(rem_qty),
                    step=1.0,
                    key=f"recv_qty_{po_to_receive}_{req_id}"
                )
                
                item_total = qty_today * float(price)
                total_delivery_amount += item_total
                received_inputs[req_id] = {
                    "desc": desc,
                    "qty_today": qty_today,
                    "prev_rec": prev_rec,
                    "ordered_qty": ordered_qty,
                    "price": price
                }

            st.markdown(f"#### 💵 Delivery Receipt Total Value: **₱{total_delivery_amount:,.2f}**")

            uploaded_file = st.file_uploader(
                "📎 Attach File for DR / SI / OR (Photo or PDF)", 
                type=["png", "jpg", "jpeg", "pdf"],
                key="receipt_file_uploader"
            )
            
            if uploaded_file is not None and uploaded_file.type.startswith("image/"):
                st.image(uploaded_file, caption="Preview of attached document", width=250)
            
            if st.button("Confirm Receiving", type="primary", key="btn_confirm_receiving"):
                if not raw_doc_no.strip():
                    st.warning("⚠️ Please input the document number.")
                elif total_delivery_amount <= 0:
                    st.warning("⚠️ Delivered quantity must be greater than 0.")
                else:
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    po_details = pending_recv_df[pending_recv_df['PO Number'] == po_to_receive].iloc[0]
                    
                    receipt_blob = uploaded_file.getvalue() if uploaded_file else None
                    file_name = uploaded_file.name if uploaded_file else None
                    
                    # 1. Record delivery header with partial delivery total amount for APV
                    c.execute("""INSERT INTO deliveries 
                                 (pono, supplier, project_name, dr_number, total_amount, received_date, receipt_image, file_name) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                              (po_to_receive, po_details['Supplier'], po_details['Project'], dr_number.strip(), 
                               total_delivery_amount, current_time, receipt_blob, file_name))
                    
                    # 2. Update received items and update inventory ledger
                    all_completed = True
                    for req_id, item_info in received_inputs.items():
                        qty_today = item_info["qty_today"]
                        if qty_today > 0:
                            new_total_rec = item_info["prev_rec"] + qty_today
                            c.execute("UPDATE requests SET received_qty = ? WHERE id = ?", (new_total_rec, req_id))
                            
                            prev_bal = get_latest_item_balance(c, item_info["desc"])
                            new_bal = prev_bal + qty_today
                            c.execute("""
                                INSERT INTO inventory_ledger (date, ref_no, item_description, qty_in, qty_out, balance, location, remarks, status)
                                VALUES (?, ?, ?, ?, 0.0, ?, ?, ?, 'Completed')
                            """, (current_time, dr_number.strip(), item_info["desc"], qty_today, new_bal, po_details['Project'], f"Received via {dr_number.strip()} (PO #{po_to_receive})"))
                        
                        if (item_info["prev_rec"] + qty_today) < item_info["ordered_qty"]:
                            all_completed = False

                    # 3. Update overall PO status
                    po_status = 'Received' if all_completed else 'Partially Received'
                    c.execute("UPDATE requests SET received_status = ?, received_timestamp = ? WHERE pono = ?", 
                              (po_status, current_time, po_to_receive))

                    conn.commit()
                    st.session_state["receive_success_msg"] = f"✅ PO #{po_to_receive} delivery ({dr_number}) logged! Amount: ₱{total_delivery_amount:,.2f}. Updated inventory ledger & generated APV record."
                    st.rerun()
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
    st.subheader("⚠️ Rejected Purchase Orders (Action Required)")

    # Fetch rejected POs and include the rejection_reason column
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
                st.error(f"**Rejection Reason:** {reason}") 
                
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
                key=f"purchaser_print_po_{pono}_{idx}"
            )
    elif not approved_pos:
        st.info("No approved purchase orders currently available for printing.")
#=================================================================================
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

#==================================================================================
# --- ROLE 5: ACCOUNTING ---
elif role == "Accounting":

    from datetime import datetime, timedelta

    # Automatic schema migration check for columns across all tables
    for col_def in ["cv_number TEXT", "cv_date TEXT", "payment_method TEXT", "cheque_no TEXT", "cheque_date TEXT"]:
        try:
            c.execute(f"ALTER TABLE deliveries ADD COLUMN {col_def}")
            conn.commit()
        except Exception:
            pass
        try:
            c.execute(f"ALTER TABLE requests ADD COLUMN {col_def}")
            conn.commit()
        except Exception:
            pass

    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN project_name TEXT")
        conn.commit()
    except Exception:
        pass

    try:
        c.execute("ALTER TABLE journal_entries ADD COLUMN ref_no TEXT")
        conn.commit()
    except Exception:
        pass

    st.subheader("🧾 Accounting Dashboard - Payables & Financial Reports")
    
    if st.button("🔄 Refresh Accounting Data", key="btn_refresh_accounting"):
        st.rerun()
    
    tab_coa, tab_apv, tab_payment, tab_gl, tab_fs, tab_br = st.tabs([
        "📊 Chart of Accounts", 
        "📝 Accounts Payable Voucher (APV)", 
        "💸 Check / Payment Voucher (CV)", 
        "📖 General Ledger Entries",
        "📈 Financial Statements",
        "🏦 Bank Reconciliation"  # <--- NEW TAB 6
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
                        except Exception:
                            st.error(f"⚠️ Account Code '{new_acc_code.strip()}' already exists or error occurred.")
                    else:
                        st.warning("⚠️ Please provide both an Account Code and Account Name.")

        #===================================
        df_coa = pd.read_sql_query("""
            SELECT account_code AS 'Account Code', account_name AS 'Account Name', 
                   account_type AS 'Account Type', status AS 'Status'
            FROM chart_of_accounts
            ORDER BY account_code ASC
        """, conn)
        #===================================
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
                    label="🖨️ Print APV",
                    data=pdf_bytes,
                    file_name=f"APV_{apv_no}.pdf",
                    mime="application/pdf",
                    key=f"print_apv_{apv_no}_{idx}"
                )
        else:
            st.info("No generated APVs available for printing yet.")

    # ==========================================================================================
    # --- TAB 2: CHECK VOUCHER / PAYMENT (CV, PCV & FLOATING CHECKS) ---
    #===============================================================
    # --- AUTOMATIC SETTLEMENT OF APVs WITH ADVANCE PDCs ---
    try:
        # Find APVs where the PO was already paid via Advance PDC/Downpayment
        prepaid_apvs = c.execute("""
            SELECT d.apv_number, d.total_amount, d.supplier, d.project_name, d.pono, r.cv_number
            FROM deliveries d
            JOIN requests r ON d.pono = r.pono
            WHERE (d.payment_status = 'Unpaid' OR d.payment_status IS NULL)
              AND d.apv_number IS NOT NULL AND d.apv_number != ''
              AND r.payment_status = 'Paid'
              AND r.cv_number IS NOT NULL AND r.cv_number != ''
        """).fetchall()
    
        for apv_no, amt, supplier, proj, po_no, existing_cv in prepaid_apvs:
            now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 1. Mark delivery APV as Paid (Applied via Advance)
            c.execute("""
                UPDATE deliveries 
                SET payment_status = 'Paid (Applied Advance)', 
                    cv_number = ?, 
                    cv_date = ? 
                WHERE apv_number = ?
            """, (existing_cv, now_ts, apv_no))
    
            # 2. Post Offsetting General Ledger Entry (20100 AP Trade vs 10500 Advances)
            c.execute("""
                INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                VALUES (?, ?, '20100', 'Accounts Payable-Trade', ?, 0.0, ?, ?, ?)
            """, (now_ts, existing_cv, amt, apv_no, f"Applied Advance ({existing_cv}) to APV {apv_no}", proj))
    
            c.execute("""
                INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                VALUES (?, ?, '10500', ?, 0.0, ?, ?, ?, ?)
            """, (now_ts, existing_cv, f"Advances to Suppliers - {supplier}", amt, apv_no, f"Settled Advance for APV {apv_no}", proj))
    
        if prepaid_apvs:
            conn.commit()
    except Exception as e:
        pass
    #===============================================================
    with tab_payment:
        st.write("### 💳 Outstanding Payables & AP Aging Summary")
        
        pay_df = pd.read_sql_query("""
            SELECT id, apv_number AS 'APV Number', pono AS 'PO Number', dr_number AS 'DR Number', 
                   supplier AS 'Supplier', total_amount AS 'Total Amount', apv_date AS 'APV Date',
                   project_name AS 'Project'
            FROM deliveries 
            WHERE (payment_status = 'Unpaid' OR payment_status IS NULL) 
              AND apv_number IS NOT NULL AND apv_number != ''
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
        else:
            st.success("🎉 No outstanding vouchered payables waiting for payment!")
    
        # ====================================================
        st.markdown("---")
        st.write("#### 💸 Process Payment & Generate Voucher")
    
        pay_basis = st.radio(
            "Payment Mode:", 
            ["Standard Payment (APV Basis)", "Advance PDC / Downpayment (PO Basis)", "Petty Cash / Direct Expense Liquidation (Non-PO)"], 
            horizontal=True
        )
    
        selected_apv_no = ""
        selected_po_no = ""
        supplier_name = ""
        total_amt = 0.0
        project_name = ""
        debit_acct_code = ""
        debit_acct_name = ""
        is_selectable = False
        pcv_description = ""
    
        if pay_basis == "Standard Payment (APV Basis)":
            unpaid_apvs = c.execute("""
                SELECT apv_number, supplier, total_amount, project_name, pono 
                FROM deliveries 
                WHERE apv_number IS NOT NULL AND apv_number != '' AND (payment_status = 'Unpaid' OR payment_status IS NULL)
            """).fetchall()
            
            if unpaid_apvs:
                apv_options = [f"{r[0]} - {r[1]} (₱{r[2]:,.2f})" for r in unpaid_apvs]
                selected_apv_str = st.selectbox("Select APV Number to Pay", apv_options)
                selected_apv_no = selected_apv_str.split(" - ")[0]
                
                row = [r for r in unpaid_apvs if r[0] == selected_apv_no][0]
                supplier_name, total_amt, project_name, selected_po_no = row[1], float(row[2]), row[3], row[4]
                debit_acct_code = "20100"
                debit_acct_name = "Accounts Payable-Trade"
                is_selectable = True
            else:
                st.info("No pending APVs available for payment.")
    
        elif pay_basis == "Advance PDC / Downpayment (PO Basis)":
            unpaid_pos = c.execute("""
                SELECT pono, supplier, SUM(amount) AS total_amount, project_name 
                FROM requests 
                WHERE pono IS NOT NULL AND pono != '' 
                  AND LOWER(COALESCE(status, '')) LIKE '%approved%'
                  AND (payment_status IS NULL OR payment_status = '' OR LOWER(payment_status) = 'unpaid')
                GROUP BY pono, supplier, project_name
            """).fetchall()
            
            if unpaid_pos:
                po_options = [f"{r[0]} - {r[1]} (₱{float(r[2] or 0):,.2f})" for r in unpaid_pos]
                selected_po_str = st.selectbox("Select Approved PO Number for Advance PDC", po_options)
                selected_po_no = selected_po_str.split(" - ")[0]
                
                row = [r for r in unpaid_pos if r[0] == selected_po_no][0]
                supplier_name, total_amt, project_name = row[1], float(row[2] or 0), row[3]
                debit_acct_code = "10500"
                debit_acct_name = f"Advances to Suppliers - {supplier_name}"
                is_selectable = True
            else:
                st.info("No open Approved POs available for advance check issuance.")
    
        else:
            # --- PETTY CASH / DIRECT LIQUIDATION ---
            st.info("ℹ️ Direct liquidation for non-PO expenses (fuel, office supplies, representations, small repairs).")
            col_pc1, col_pc2, col_pc3 = st.columns(3)
            
            supplier_name = col_pc1.text_input("Payee / Claiming Employee", value="", placeholder="e.g., Juan Dela Cruz")
            total_amt = col_pc2.number_input("Total Expense Amount (₱)", min_value=0.0, value=0.0, step=100.0)
            
            projects_db = c.execute("SELECT project_name FROM projects").fetchall() if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'").fetchone() else []
            project_list = ["General / Head Office"] + [p[0] for p in projects_db if p[0]]
            project_name = col_pc3.selectbox("Charge to Project", project_list)
            
            col_pc4, col_pc5 = st.columns(2)
            pcv_description = col_pc4.text_input("Particulars / Purpose", placeholder="e.g., Gas allowance for site inspection")
            
            exp_accs = c.execute("SELECT account_code, account_name FROM chart_of_accounts WHERE account_type = 'Expense'").fetchall()
            exp_options = [f"[{acc[0]}] {acc[1]}" for acc in exp_accs] if exp_accs else ["[60200] Direct Expenses"]
            
            selected_exp = col_pc5.selectbox("Accounting Expense Tag", exp_options)
            debit_acct_code = selected_exp.split("]")[0].replace("[", "")
            debit_acct_name = selected_exp.split("]")[1].strip()
            
            if supplier_name.strip() and total_amt > 0 and pcv_description.strip():
                is_selectable = True
            else:
                st.warning("⚠️ Please fill in Payee Name, Amount, and Particulars to process Petty Cash.")
    
        if is_selectable:
            col1, col2, col3 = st.columns(3)
            
            if pay_basis == "Petty Cash / Direct Expense Liquidation (Non-PO)":
                pay_method = col1.selectbox("Payment Method", ["Cash", "Check"])
                prefix = "PCV"
            else:
                pay_method = col1.selectbox("Payment Method", ["Check", "Cash"])
                prefix = "CV" if pay_method == "Check" else "CAV"
            
            bank_accounts = [
                ("10100", "Petty Cash Fund / Cash on Hand"),
                ("10310", "Cash in Bank MBTC"),
                ("10320", "Cash in Bank CHINA"),
                ("10330", "Cash in Bank BDO"),
                ("10340", "Cash in Bank Landbank")
            ]
            bank_choice = col2.selectbox("Funding Cash/Bank Account", [f"[{b[0]}] {b[1]}" for b in bank_accounts])
            selected_bank_code = bank_choice.split("]")[0].replace("[", "")
            selected_bank_name = bank_choice.split("]")[1].strip()
            
            suggested_cv = generate_voucher_number(c, "cv_number", prefix)
            cv_input = col3.text_input("Voucher Number Sequence", value=suggested_cv, key=f"cv_inp_{prefix}_{suggested_cv}")
    
            # --- Dynamic Date & Floating Check Toggle ---
            if pay_basis == "Advance PDC / Downpayment (PO Basis)":
                date_label = "📆 PDC Maturity / Cheque Date"
            elif pay_basis == "Petty Cash / Direct Expense Liquidation (Non-PO)":
                date_label = "📅 Liquidation / Expense Date"
            else:
                date_label = "📅 Cheque / Disbursement Date"
    
            col_d1, col_d2 = st.columns(2)
            cheque_no_input = col_d1.text_input("Cheque/OR Ref Number (Optional)", value="")
            
            with col_d2:
                cheque_date_input = st.date_input(
                    date_label, 
                    value=datetime.now().date(),
                    key=f"chk_date_{pay_basis.replace(' ', '_')}"
                )
                is_floating_check = st.checkbox("🎟️ Print Blank Date on Cheque (Open Date / Floating Check)", value=False)
    
            # Preview GL Account Routing based on Floating Check status
            credit_preview_code = "20200" if (is_floating_check and pay_method == "Check") else selected_bank_code
            credit_preview_name = "Checks Payable / PDC Issued" if (is_floating_check and pay_method == "Check") else selected_bank_name
    
            st.info(f"""
            💡 **Accounting Entry Preview:**
            * **Debit:** {debit_acct_name} (Code {debit_acct_code}) — ₱{total_amt:,.2f}
            * **Credit:** {credit_preview_name} (Code {credit_preview_code}) — ₱{total_amt:,.2f}
            """)
    
            if st.button("✅ Process Payment & Issue Voucher", type="primary"):
                try:
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    c_date_str = "" if is_floating_check else cheque_date_input.strftime('%Y-%m-%d')
    
                    po_val = selected_po_no.split(" - ")[0].strip() if selected_po_no else ""
                    apv_val = selected_apv_no.split(" - ")[0].strip() if selected_apv_no else ""
    
                    if pay_basis == "Standard Payment (APV Basis)":
                        cv_debit_desc = f"Payment for APV {apv_val} ({supplier_name})"
                        cv_credit_desc = f"Disbursement for APV {apv_val} via {'Floating Check' if is_floating_check else pay_method}"
                        ref_doc = apv_val
                    elif pay_basis == "Advance PDC / Downpayment (PO Basis)":
                        cv_debit_desc = f"Advance PDC for PO {po_val} ({supplier_name})"
                        cv_credit_desc = f"Disbursement for PO {po_val} via {'Floating Check' if is_floating_check else pay_method}"
                        ref_doc = po_val
                    else:
                        cv_debit_desc = f"PCV Expense: {pcv_description} ({supplier_name})"
                        cv_credit_desc = f"Petty cash release: {pcv_description}"
                        ref_doc = cv_input.strip()
    
                    # Update Source Documents if applicable
                    if pay_basis == "Standard Payment (APV Basis)" and apv_val:
                        c.execute("""
                            UPDATE deliveries 
                            SET payment_status = 'Paid', cv_number = ?, cv_date = ?, payment_method = ?, cheque_no = ?, cheque_date = ?
                            WHERE apv_number = ?
                        """, (cv_input.strip(), current_time, pay_method, cheque_no_input.strip(), c_date_str, apv_val))
                        if po_val:
                            c.execute("UPDATE requests SET payment_status = 'Paid' WHERE pono = ?", (po_val,))
                            
                    elif pay_basis == "Advance PDC / Downpayment (PO Basis)" and po_val:
                        c.execute("""
                            UPDATE requests 
                            SET payment_status = 'Paid', cv_number = ?, cv_date = ?, payment_method = ?, cheque_no = ?, cheque_date = ?
                            WHERE pono = ?
                        """, (cv_input.strip(), current_time, pay_method, cheque_no_input.strip(), c_date_str, po_val))
    
                    # Insert General Ledger Entries
                    c.execute("""
                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                        VALUES (?, ?, ?, ?, ?, 0.0, ?, ?, ?)
                    """, (current_time, cv_input.strip(), debit_acct_code, debit_acct_name, total_amt, ref_doc, cv_debit_desc, project_name))
    
                    c.execute("""
                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                        VALUES (?, ?, ?, ?, 0.0, ?, ?, ?, ?)
                    """, (current_time, cv_input.strip(), credit_preview_code, credit_preview_name, total_amt, ref_doc, cv_credit_desc, project_name))
    
                    # If Open-Dated Floating Check, insert record into Turso floating_checks table
                    if is_floating_check and pay_method == "Check":
                        c.execute("""
                            INSERT INTO floating_checks 
                            (voucher_no, supplier_name, check_no, amount, voucher_date, check_date, status, bank_account_code, project_name, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, 'Floating', ?, ?, ?)
                        """, (cv_input.strip(), supplier_name, cheque_no_input.strip(), total_amt, current_time, c_date_str, selected_bank_code, project_name, current_time))
    
                    conn.commit()
                    st.success(f"🎉 Voucher {cv_input.strip()} recorded successfully!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Database Error: {e}")
    
        # ====================================================
        # --- FLOATING CHECKS & PDC REGISTER ---
        st.markdown("---")
        st.subheader("📑 Floating & Post-Dated Check Register")
    
        floating_df = pd.read_sql_query("""
            SELECT id, voucher_no AS 'Voucher', supplier_name AS 'Payee', check_no AS 'Check No.', 
                   amount AS 'Amount', voucher_date AS 'Voucher Date', status AS 'Status', 
                   bank_account_code AS 'Bank Code', project_name AS 'Project'
            FROM floating_checks
            WHERE status = 'Floating'
            ORDER BY id DESC
        """, conn)
    
        if not floating_df.empty:
            st.warning(f"⚠️ You have {len(floating_df)} floating / open-dated check(s) pending bank encashment.")
            st.dataframe(
                floating_df.style.format({"Amount": "₱{:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )
    
            with st.expander("✅ Clear / Release Floating Check"):
                fc_options = [f"{r['Voucher']} - {r['Payee']} (₱{r['Amount']:,.2f})" for _, r in floating_df.iterrows()]
                sel_fc_str = st.selectbox("Select Floating Check to Clear", fc_options)
                sel_fc_voucher = sel_fc_str.split(" - ")[0]
                fc_row = floating_df[floating_df['Voucher'] == sel_fc_voucher].iloc[0]
    
                col_fc1, col_fc2 = st.columns(2)
                actual_check_no = col_fc1.text_input("Final Check No.", value=str(fc_row['Check No.'] or ''))
                actual_clear_date = col_fc2.date_input("Encashment / Clearance Date", value=datetime.now().date())
    
                if st.button("🏦 Mark Check as Cleared (Deduct from Bank in GL)", type="primary"):
                    try:
                        now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        clear_dt_str = actual_clear_date.strftime('%Y-%m-%d')
    
                        # Lookup Bank Account Name
                        bank_names = {"10100": "Petty Cash Fund", "10310": "Cash in Bank MBTC", "10320": "Cash in Bank CHINA", "10330": "Cash in Bank BDO", "10340": "Cash in Bank Landbank"}
                        target_bank_name = bank_names.get(fc_row['Bank Code'], "Cash in Bank")
    
                        # Step 2 Posting: Debit 20200 Checks Payable, Credit 103xx Cash in Bank
                        c.execute("""
                            INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                            VALUES (?, ?, '20200', 'Checks Payable / PDC Issued', ?, 0.0, ?, ?, ?)
                        """, (now_ts, fc_row['Voucher'], fc_row['Amount'], fc_row['Voucher'], f"Cleared floating check {fc_row['Voucher']}", fc_row['Project']))
    
                        c.execute("""
                            INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                            VALUES (?, ?, ?, ?, 0.0, ?, ?, ?, ?)
                        """, (now_ts, fc_row['Voucher'], fc_row['Bank Code'], target_bank_name, fc_row['Amount'], fc_row['Voucher'], f"Bank encashment for check {actual_check_no}", fc_row['Project']))
    
                        # Update floating_checks status
                        c.execute("""
                            UPDATE floating_checks 
                            SET status = 'Cleared', check_no = ?, check_date = ? 
                            WHERE id = ?
                        """, (actual_check_no.strip(), clear_dt_str, int(fc_row['id'])))
    
                        # Update deliveries or requests cheque_date for PDF printing
                        c.execute("UPDATE deliveries SET cheque_no = ?, cheque_date = ? WHERE cv_number = ?", (actual_check_no.strip(), clear_dt_str, fc_row['Voucher']))
                        c.execute("UPDATE requests SET cheque_no = ?, cheque_date = ? WHERE cv_number = ?", (actual_check_no.strip(), clear_dt_str, fc_row['Voucher']))
    
                        conn.commit()
                        st.success(f"🎉 Check {fc_row['Voucher']} successfully cleared and debited from {target_bank_name} in GL!")
                        st.rerun()
    
                    except Exception as e:
                        st.error(f"❌ Error clearing check: {e}")
        else:
            st.success("🎉 No floating or un-encashed open checks pending.")
    
        # ====================================================
        st.markdown("---")
        st.subheader("🖨️ Issued Check / Payment Vouchers (Ready for Printing)")
        
        del_cvs = []
        try:
            del_cvs = c.execute("""
                SELECT cv_number, cv_date, apv_number, supplier, payment_method, total_amount, cheque_no, cheque_date 
                FROM deliveries 
                WHERE cv_number IS NOT NULL AND cv_number != ''
            """).fetchall()
        except Exception:
            del_cvs = []
    
        req_cvs = []
        try:
            req_cvs = c.execute("""
                SELECT cv_number, cv_date, '' AS apv_number, supplier, payment_method, SUM(amount) AS total_amount, cheque_no, cheque_date 
                FROM requests 
                WHERE cv_number IS NOT NULL AND cv_number != ''
                GROUP BY cv_number, cv_date, supplier, payment_method, cheque_no, cheque_date
            """).fetchall()
        except Exception:
            req_cvs = []
    
        # Non-PO Petty Cash Liquidation Vouchers from journal_entries
        pcv_entries = []
        try:
            pcv_entries = c.execute("""
                SELECT DISTINCT voucher_no, entry_date, ref_no, description, 'Cash', debit, '', entry_date
                FROM journal_entries
                WHERE (voucher_no LIKE 'PCV-%' OR voucher_no LIKE 'CAV-%') AND debit > 0
            """).fetchall()
        except Exception:
            pcv_entries = []
    
        seen_cvs = set()
        issued_cvs = []
        for record in (del_cvs + req_cvs + pcv_entries):
            cv_no = record[0]
            if cv_no and cv_no not in seen_cvs:
                seen_cvs.add(cv_no)
                issued_cvs.append(record)
    
        issued_cvs.sort(key=lambda x: str(x[1] or ''), reverse=True)
        # =============================================================
        if issued_cvs and HAS_REPORTLAB:
            for idx, cv in enumerate(issued_cvs):
                cv_no, cv_date, apv_no, supplier, pay_method, total_amt, c_num, c_date = cv
                
                # Fetch existing purchase discount for this voucher if previously saved
                existing_disc_row = c.execute("SELECT credit FROM journal_entries WHERE voucher_no = ? AND account_code = '50200'", (cv_no,)).fetchone()
                init_discount_amt = float(existing_disc_row[0]) if existing_disc_row and existing_disc_row[0] else 0.0

                st.write(f"💳 **Voucher:** {cv_no} ({pay_method}) | **Supplier/Payee:** {supplier} | **Amount:** ₱{total_amt:,.2f}")
                
                col_btn1, col_btn2 = st.columns(2)
                
                voucher_pdf = create_cv_pdf(cv_no, cv_date, apv_no, supplier, pay_method, total_amt, conn=conn)
                col_btn1.download_button(
                    label="📄 Print Payment Voucher PDF",
                    data=voucher_pdf,
                    file_name=f"Voucher_{cv_no}.pdf",
                    mime="application/pdf",
                    key=f"print_pv_{cv_no}_{idx}"
                )
                
                cheque_pdf = create_cheque_pdf(supplier, total_amt - init_discount_amt, c_date)
                col_btn2.download_button(
                    label="🎟️ Print Cheque (A4)",
                    data=cheque_pdf,
                    file_name=f"Cheque_{cv_no}.pdf",
                    mime="application/pdf",
                    key=f"print_chk_{cv_no}_{idx}"
                )

                #===============================inline editor===================
                # --- ✏️ FULL INLINE EDIT TOOL (Amount, Discount, Check No, Check Date & 2307 WHT) ---
                with st.expander(f"⚙️ Options / Edit Details for {cv_no}"):
                    col_e1, col_e2, col_e3 = st.columns(3)
                    
                    new_voucher_amt = col_e1.number_input(
                        "Gross Payable Amount (₱)", 
                        min_value=0.01, 
                        value=float(total_amt), 
                        step=100.0, 
                        key=f"edit_amt_val_{cv_no}_{idx}"
                    )
                
                    discount_amt = col_e2.number_input(
                        "Discount / Rebate (₱)", 
                        min_value=0.0, 
                        value=float(init_discount_amt), 
                        step=50.0, 
                        key=f"edit_disc_val_{cv_no}_{idx}"
                    )
                    
                    new_check_no = col_e3.text_input(
                        "Cheque / Ref Number", 
                        value=str(c_num or ''), 
                        key=f"edit_chk_no_{cv_no}_{idx}"
                    )
                
                    col_e4, col_e5 = st.columns(2)
                
                    # Safely parse current check date for date picker default
                    try:
                        init_date = pd.to_datetime(c_date).date() if c_date else datetime.now().date()
                    except Exception:
                        init_date = datetime.now().date()
                
                    new_check_date = col_e4.date_input(
                        "Cheque Date", 
                        value=init_date, 
                        key=f"edit_chk_dt_{cv_no}_{idx}"
                    )
                    
                    is_blank_dt = col_e5.checkbox(
                        "🎟️ Keep Cheque Date Blank (Open Date / Floating)", 
                        value=(not bool(c_date)), 
                        key=f"blank_dt_{cv_no}_{idx}"
                    )
                
                    st.markdown("---")
                    
                    # --- BIR FORM 2307 WITHHOLDING TAX OPTIONS ---
                    col_w1, col_w2 = st.columns(2)
                    wht_option = col_w1.selectbox(
                        "Withholding Tax (BIR Form 2307)",
                        options=["0% (None)", "1% (Goods - WI158)", "2% (Services - WI160)"],
                        key=f"edit_wht_opt_{cv_no}_{idx}"
                    )
                
                    # Map selection to rates and ATCs
                    if "1%" in wht_option:
                        wht_rate = 0.01
                        atc_code = "WI158"
                        income_type = "PURCHASE OF GOODS"
                    elif "2%" in wht_option:
                        wht_rate = 0.02
                        atc_code = "WI160"
                        income_type = "PURCHASE OF SERVICES"
                    else:
                        wht_rate = 0.0
                        atc_code = ""
                        income_type = ""
                
                    computed_tax_withheld = new_voucher_amt * wht_rate
                    
                    # Net Disbursement accounts for Gross minus Discount minus Tax Withheld (Check amount)
                    net_disbursement = max(0.0, new_voucher_amt - discount_amt - computed_tax_withheld)
                    
                    col_w2.metric("Computed Tax Withheld (2307)", f"₱{computed_tax_withheld:,.2f}")
                
                    if discount_amt > 0 or computed_tax_withheld > 0:
                        st.info(f"💡 **Summary:** Gross: ₱{new_voucher_amt:,.2f} | Less Discount: ₱{discount_amt:,.2f} | Less 2307 Tax: ₱{computed_tax_withheld:,.2f} | **Net Check Disbursement: ₱{net_disbursement:,.2f}**")
                
                    st.markdown("")
                    
                    # Action Buttons layout inside expander
                    b_col1, b_col2 = st.columns([1, 1])
                
                    with b_col1:
                        save_clicked = st.button("💾 Save All Changes", key=f"btn_save_all_{cv_no}_{idx}", type="primary")
                
                    with b_col2:
                        if computed_tax_withheld > 0:
                            if st.button("📄 Generate BIR 2307 PDF", key=f"btn_gen_2307_{cv_no}_{idx}"):
                                # Call your PDF generator buffer helper here
                                # Fetch supplier details from Turso database before generating PDF
                                supp_row = conn.execute(
                                    "SELECT tin_number, location FROM suppliers WHERE supplier_name = ?", 
                                    (supplier_name,)
                                ).fetchone()
                                
                                if supp_row:
                                    supplier_tin = supp_row[0] if supp_row[0] else "000-000-000-000"
                                    supplier_address = supp_row[1] if supp_row[1] else "N/A"
                                else:
                                    supplier_tin = "000-000-000-000"
                                    supplier_address = "N/A"
                                
                                # Generate 2307 PDF
                                pdf_buffer = generate_bir_2307_pdf(
                                    voucher_data={"cv_no": cv_no},
                                    supplier_data={"name": supplier_name, "tin": supplier_tin, "address": supplier_address},
                                    wht_details={"income_type": income_type, "atc": atc_code, "gross": new_voucher_amt, "tax": computed_tax_withheld}
                                )   
                                st.download_button(
                                    label=f"📥 Download 2307 for {cv_no}",
                                    data=pdf_buffer,
                                    file_name=f"BIR_Form_2307_{cv_no}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_2307_{cv_no}_{idx}"
                                )
                
                    if save_clicked:
                        try:
                            formatted_chk_date = "" if is_blank_dt else new_check_date.strftime('%Y-%m-%d')
                            
                            # 1. Update Debit side (Clears full Gross Payable)
                            c.execute("UPDATE journal_entries SET debit = ? WHERE voucher_no = ? AND debit > 0", (new_voucher_amt, cv_no))
                            
                            # 2. Update Credit side for Cash / Bank / PDC Issued (Net Check Amount)
                            c.execute("UPDATE journal_entries SET credit = ? WHERE voucher_no = ? AND credit > 0 AND account_code NOT IN ('50200', '20400')", (net_disbursement, cv_no))
                            
                            # 3. Manage 50200 Purchase Discounts account
                            has_disc_entry = c.execute("SELECT COUNT(*) FROM journal_entries WHERE voucher_no = ? AND account_code = '50200'", (cv_no,)).fetchone()[0] > 0
                
                            if discount_amt > 0:
                                if has_disc_entry:
                                    c.execute("UPDATE journal_entries SET credit = ? WHERE voucher_no = ? AND account_code = '50200'", (discount_amt, cv_no))
                                else:
                                    existing_ref = c.execute("SELECT ref_no, project_name FROM journal_entries WHERE voucher_no = ? LIMIT 1", (cv_no,)).fetchone()
                                    ref_val = existing_ref[0] if existing_ref else cv_no
                                    proj_val = existing_ref[1] if existing_ref else ""
                                    now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                                    c.execute("""
                                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                                        VALUES (?, ?, '50200', 'Purchase Discounts', 0.0, ?, ?, ?, ?)
                                    """, (now_ts, cv_no, discount_amt, ref_val, f"Purchase discount applied for {cv_no}", proj_val))
                            else:
                                if has_disc_entry:
                                    c.execute("DELETE FROM journal_entries WHERE voucher_no = ? AND account_code = '50200'", (cv_no,))
                
                            # 4. Manage Withholding Tax Payable account (e.g., Code 20400) if 2307 is applied
                            has_wht_entry = c.execute("SELECT COUNT(*) FROM journal_entries WHERE voucher_no = ? AND account_code = '20400'", (cv_no,)).fetchone()[0] > 0
                
                            if computed_tax_withheld > 0:
                                if has_wht_entry:
                                    c.execute("UPDATE journal_entries SET credit = ? WHERE voucher_no = ? AND account_code = '20400'", (computed_tax_withheld, cv_no))
                                else:
                                    existing_ref = c.execute("SELECT ref_no, project_name FROM journal_entries WHERE voucher_no = ? LIMIT 1", (cv_no,)).fetchone()
                                    ref_val = existing_ref[0] if existing_ref else cv_no
                                    proj_val = existing_ref[1] if existing_ref else ""
                                    now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                                    c.execute("""
                                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                                        VALUES (?, ?, '20400', 'Withholding Tax Payable - Expanded', 0.0, ?, ?, ?, ?)
                                    """, (now_ts, cv_no, computed_tax_withheld, ref_val, f"EWT {atc_code} withheld for {cv_no}", proj_val))
                            else:
                                if has_wht_entry:
                                    c.execute("DELETE FROM journal_entries WHERE voucher_no = ? AND account_code = '20400'", (cv_no,))
                
                            # 5. Update Deliveries table (Gross APV amount preserved)
                            c.execute("""
                                UPDATE deliveries 
                                SET total_amount = ?, cheque_no = ?, cheque_date = ? 
                                WHERE cv_number = ?
                            """, (new_voucher_amt, new_check_no.strip(), formatted_chk_date, cv_no))
                            
                            # 6. Update Requests table
                            c.execute("""
                                UPDATE requests 
                                SET amount = ?, cheque_no = ?, cheque_date = ? 
                                WHERE cv_number = ?
                            """, (new_voucher_amt, new_check_no.strip(), formatted_chk_date, cv_no))
                            
                            # 7. Update Floating Checks register (Check issued for Net Amount after discount & WHT)
                            c.execute("""
                                UPDATE floating_checks 
                                SET amount = ?, check_no = ?, check_date = ? 
                                WHERE voucher_no = ?
                            """, (net_disbursement, new_check_no.strip(), formatted_chk_date, cv_no))
                            
                            conn.commit()
                            st.success(f"🎉 Updated {cv_no}! Gross: ₱{new_voucher_amt:,.2f}, Discount: ₱{discount_amt:,.2f}, 2307 Tax: ₱{computed_tax_withheld:,.2f}, Net Check: ₱{net_disbursement:,.2f}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error updating voucher details: {e}")
                #===============================end of inline editor============

                st.markdown("---")
        # =============================================================
        else:
            st.info("No issued check or payment vouchers available for printing yet.")
    
        # --- ADMIN / VOUCHER RESET TOOL ---
        if role in ["Accounting", "Admin View All"]:
            st.markdown("---")
            with st.expander("🗑️ Admin Tool: Delete / Reset Payment Voucher Record"):
                st.warning("⚠️ Deleting a voucher will revert the corresponding APV/PO status back to 'Unpaid' and remove its journal entries.")
                
                cv_set = set()
                
                try:
                    res1 = c.execute("SELECT DISTINCT voucher_no FROM journal_entries WHERE voucher_no LIKE 'CV-%' OR voucher_no LIKE 'CAV-%' OR voucher_no LIKE 'PCV-%'").fetchall()
                    cv_set.update([r[0] for r in res1 if r[0]])
                except Exception:
                    pass
    
                try:
                    res2 = c.execute("SELECT DISTINCT cv_number FROM deliveries WHERE cv_number IS NOT NULL AND cv_number != ''").fetchall()
                    cv_set.update([r[0] for r in res2 if r[0]])
                except Exception:
                    pass
    
                try:
                    res3 = c.execute("SELECT DISTINCT cv_number FROM requests WHERE cv_number IS NOT NULL AND cv_number != ''").fetchall()
                    cv_set.update([r[0] for r in res3 if r[0]])
                except Exception:
                    pass
    
                cv_options = sorted(list(cv_set))
                
                if cv_options:
                    selected_del_cv = st.selectbox("Select Voucher Number to Delete/Reset:", cv_options)
                    
                    if st.button(f"🔥 Reset & Delete Voucher {selected_del_cv}", type="primary"):
                        try:
                            c.execute("UPDATE deliveries SET payment_status = 'Unpaid', cv_number = NULL, cv_date = NULL, payment_method = NULL, cheque_no = NULL, cheque_date = NULL WHERE cv_number = ?", (selected_del_cv,))
                        except Exception:
                            pass
                        
                        try:
                            c.execute("UPDATE requests SET payment_status = 'Unpaid', cv_number = NULL, cv_date = NULL, payment_method = NULL, cheque_no = NULL, cheque_date = NULL WHERE cv_number = ?", (selected_del_cv,))
                        except Exception:
                            pass
                        
                        try:
                            c.execute("DELETE FROM journal_entries WHERE voucher_no = ?", (selected_del_cv,))
                        except Exception:
                            pass
    
                        try:
                            c.execute("DELETE FROM floating_checks WHERE voucher_no = ?", (selected_del_cv,))
                        except Exception:
                            pass
                        
                        conn.commit()
                        st.success(f"🎉 Voucher {selected_del_cv} has been deleted and its linked APV/PO status reset to Unpaid!")
                        st.rerun()
                else:
                    st.info("No recorded payment vouchers found to delete.")
    #==============================================================================================            
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
        #==============================================================================================
        # --- TAB 4: SUBTAB 1 (BALANCE SHEET) ---
        with fs_tab2:
            st.subheader("Balance Sheet")
            as_of = st.date_input("As of Date", pd.to_datetime("2026-12-31"))
        
            df_bs = get_balance_sheet(conn, as_of)
            
            df_is_till_date = get_income_statement(conn, "1900-01-01", as_of)
            
            rev_until = df_is_till_date[df_is_till_date['account_type'] == 'Revenue']['amount'].sum() if not df_is_till_date.empty and 'account_type' in df_is_till_date.columns else 0.0
            exp_until = df_is_till_date[df_is_till_date['account_type'] == 'Expense']['amount'].sum() if not df_is_till_date.empty and 'account_type' in df_is_till_date.columns else 0.0
            current_net_income = rev_until - exp_until
        
            assets = df_bs[df_bs['account_type'] == 'Asset'] if not df_bs.empty else pd.DataFrame()
            liabilities = df_bs[df_bs['account_type'] == 'Liability'] if not df_bs.empty else pd.DataFrame()
            equity = df_bs[df_bs['account_type'] == 'Equity'] if not df_bs.empty else pd.DataFrame()
        
            tot_assets = assets['amount'].sum() if not assets.empty else 0.0
            tot_liab = liabilities['amount'].sum() if not liabilities.empty else 0.0
            tot_equity = (equity['amount'].sum() if not equity.empty else 0.0) + current_net_income
        
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Assets**")
                if not assets.empty:
                    st.dataframe(
                        assets[['account_code', 'account_name', 'amount']]
                        .rename(columns={'account_code': 'Code', 'account_name': 'Account', 'amount': 'Amount (₱)'})
                        .style.format({"Amount (₱)": "₱{:,.2f}"}), 
                        use_container_width=True, 
                        hide_index=True
                    )
                else:
                    st.info("No asset entries found.")
                st.metric("Total Assets", f"₱{tot_assets:,.2f}")
        
            with col_b:
                st.markdown("**Liabilities**")
                if not liabilities.empty:
                    st.dataframe(
                        liabilities[['account_code', 'account_name', 'amount']]
                        .rename(columns={'account_code': 'Code', 'account_name': 'Account', 'amount': 'Amount (₱)'})
                        .style.format({"Amount (₱)": "₱{:,.2f}"}), 
                        use_container_width=True, 
                        hide_index=True
                    )
                else:
                    st.info("No liability entries found.")
                st.metric("Total Liabilities", f"₱{tot_liab:,.2f}")
                
                st.markdown("**Equity**")
                if not equity.empty:
                    st.dataframe(
                        equity[['account_code', 'account_name', 'amount']]
                        .rename(columns={'account_code': 'Code', 'account_name': 'Account', 'amount': 'Amount (₱)'})
                        .style.format({"Amount (₱)": "₱{:,.2f}"}), 
                        use_container_width=True, 
                        hide_index=True
                    )
                
                st.write(f"Current Period Net Profit: **₱{current_net_income:,.2f}**")
                st.metric("Total Equity", f"₱{tot_equity:,.2f}")
        
            st.divider()
            tot_liab_equity = tot_liab + tot_equity
            balanced = abs(tot_assets - tot_liab_equity) < 0.01
            
            if balanced:
                st.success(f"✅ Balance Check Passed: Total Assets (₱{tot_assets:,.2f}) = Liabilities + Equity (₱{tot_liab_equity:,.2f})")
            else:
                st.error(f"⚠️ Unbalanced! Assets: ₱{tot_assets:,.2f} | Liabilities + Equity: ₱{tot_liab_equity:,.2f}")


        #===================================================================
        # --- TAB 5: BANK RECONCILIATION ---
        with tab_br:
            render_bank_reconciliation_tab(conn)
            
#==================================================================================
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
    #================================================================
    st.markdown("---")
    with st.expander("🚨 ADMIN TOOL: Complete Operational Reset"):
        st.error("⚠️ **WARNING:** This will permanently delete all requests, deliveries, inventory transactions, and journal entries!")
        
        confirm_wipe = st.checkbox("I understand this will reset all operational data back to zero.")
        
        if confirm_wipe:
            if st.button("🔥 WIPE ALL OPERATIONAL DATA & RESET IDs", type="primary"):
                try:
                    # Clear operational transaction tables
                    c.execute("DELETE FROM journal_entries")
                    c.execute("DELETE FROM deliveries")
                    c.execute("DELETE FROM inventory_ledger")
                    c.execute("DELETE FROM requests")
                    
                    # Reset SQLite auto-increment counters back to 1
                    c.execute("""
                        DELETE FROM sqlite_sequence 
                        WHERE name IN ('journal_entries', 'deliveries', 'inventory_ledger', 'requests')
                    """)
                    
                    conn.commit()
                    st.success("🎉 All operational tables cleared and ID sequences reset to 1!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error during database reset: {e}")
    #================================================================


