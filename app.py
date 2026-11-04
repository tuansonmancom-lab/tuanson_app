import sqlite3
import pandas as pd
import streamlit as st
import re
import os
from datetime import datetime
from io import BytesIO
from datetime import datetime, timedelta

#====================================
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

def generate_calendar_pdf(year, month_num, month_name, events_dict):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CalTitle",
        parent=styles["Heading1"],
        fontSize=18,
        alignment=1,
        spaceAfter=15,
    )

    elements.append(
        Paragraph(
            f"Tuanson Construction - Payables & Loan Calendar: {month_name} {year}",
            title_style,
        )
    )

    header_style = ParagraphStyle(
        "HeaderStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.whitesmoke,
        alignment=1,
    )

    cell_body_style = ParagraphStyle(
        "CellBodyStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.black,
    )

    # Build Headers
    headers = [
        Paragraph("Sunday", header_style),
        Paragraph("Monday", header_style),
        Paragraph("Tuesday", header_style),
        Paragraph("Wednesday", header_style),
        Paragraph("Thursday", header_style),
        Paragraph("Friday", header_style),
        Paragraph("Saturday", header_style),
    ]
    table_data = [headers]

    cal = calendar.Calendar(firstweekday=6)
    month_days = cal.monthdayscalendar(year, month_num)

    for week in month_days:
        week_row = []
        for day in week:
            if day == 0:
                week_row.append(Paragraph("", cell_body_style))
            else:
                cell_html = f"<b>{day}</b>"
                if day in events_dict:
                    for ev in events_dict[day]:
                        if ":" in ev:
                            bank_part, amt_part = ev.split(":", 1)
                            short_bank = bank_part.strip()[:10]
                            safe_ev = f"{short_bank}:{amt_part}".replace("₱", "PHP")
                        else:
                            safe_ev = ev[:15].replace("₱", "PHP")

                        cell_html += f"<br/><font color='#c00000'>• {safe_ev}</font>"

                week_row.append(Paragraph(cell_html, cell_body_style))
        table_data.append(week_row)

    col_width = 104
    row_height = 80

    cal_table = Table(
        table_data, colWidths=[col_width] * 7, rowHeights=[30] + [row_height] * 5
    )
    cal_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e78")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#cccccc")),
        ])
    )

    elements.append(cal_table)
    doc.build(elements)
    buffer.seek(0)
    return buffer
#================end Calendar================
import pandas as pd
import streamlit as st


def render_financial_overview(conn, sel_year, sel_month):
  st.markdown("### 📊 Financial Overview")

  # Fetch loans and amortizations from database
  loans_df = pd.read_sql("SELECT * FROM loans_master", conn)
  amort_df = pd.read_sql(
      """
        SELECT a.*, l.bank_name 
        FROM loan_amortization_schedule a
        JOIN loans_master l ON a.loan_id = l.loan_id
    """,
      conn,
  )

  # Calculate Money In (Loan proceeds released in sel_year/sel_month)
  money_in_month = 0.0
  in_entries = 0
  if not loans_df.empty:
    for _, row in loans_df.iterrows():
      try:
        dt = pd.to_datetime(row["date_granted"])
        if dt.year == sel_year and dt.month == sel_month:
          money_in_month += float(row["principal_amount"])
          in_entries += 1
      except Exception:
        pass

  # Calculate Money Out (Amortizations due in sel_year/sel_month)
  money_out_month = 0.0
  out_entries = 0
  out_by_payee = {}
  if not amort_df.empty:
    for _, row in amort_df.iterrows():
      try:
        dt = pd.to_datetime(row["due_date"])
        if dt.year == sel_year and dt.month == sel_month:
          amt = float(row["total_amount_due"])
          money_out_month += amt
          out_entries += 1
          payee = str(row["bank_name"])[:15]
          out_by_payee[payee] = out_by_payee.get(payee, 0.0) + amt
      except Exception:
        pass

  net_month = money_in_month - money_out_month
  running_balance = net_month  # Can be adjusted with total historical cash flow if needed

  # --- TOP METRIC CARDS ---
  col1, col2, col3, col4 = st.columns(4)

  with col1:
    st.metric(
        label="Money in this month",
        value=f"₱{money_in_month:,.2f}",
        delta=f"{in_entries} entry",
    )
  with col2:
    st.metric(
        label="Money out this month",
        value=f"₱{money_out_month:,.2f}",
        delta=f"{out_entries} entries",
        delta_color="inverse",
    )
  with col3:
    st.metric(label="Net this month", value=f"₱{net_month:,.2f}")
  with col4:
    st.metric(
        label="Running balance",
        value=f"₱{running_balance:,.2f}",
        help="All money in minus all money out",
    )

  st.markdown("---")

  # --- BOTTOM SECTION: CHART & BREAKDOWN ---
  col_chart, col_breakdown = st.columns([1.3, 1])

  with col_chart:
    st.markdown("#### Last 6 Months Cash Flow")
    # Build sample / aggregated trend data for the last 6 months
    chart_data = pd.DataFrame({
        "Month": ["May", "Jun", "Jul", "Aug", "Sep", "Oct"],
        "In": [0, 0, 0, 0, 0, money_in_month],
        "Out": [0, 0, 0, 0, 0, money_out_month],
    })
    st.bar_chart(chart_data.set_index("Month"), color=["#198754", "#dc3545"])

  with col_breakdown:
    st.markdown("#### Where money went this month")
    if out_by_payee:
      breakdown_df = pd.DataFrame(
          list(out_by_payee.items()), columns=["Payee", "Amount"]
      )
      breakdown_df["Amount"] = breakdown_df["Amount"].apply(
          lambda x: f"₱{x:,.2f}"
      )
      st.dataframe(breakdown_df, width="stretch", hide_index=True)
    else:
      st.info("No expenses or loan amortizations recorded this month yet.")
#=============Lending and Bank ====================
import calendar
import io
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle


def render_bank_loans_dashboard(conn):
  st.subheader("🏦 Bank & Lending Institutions & Loans Management")

  #==================Overview===================
  # 1. Define selectors at the top level first so variables exist
  col_y, col_m = st.columns(2)
  with col_y:
    sel_year = st.selectbox("Filter Year", [2026, 2027, 2028], index=0, key="dash_year")
  with col_m:
    sel_month = st.selectbox(
        "Filter Month",
        list(range(1, 13)),
        format_func=lambda x: calendar.month_name[x],
        index=10,  # November default
        key="dash_month",
    )

  st.markdown("---")

  # 2. Call your financial overview right below the top filters
  render_financial_overview(conn, sel_year, sel_month)

  st.markdown("---")
  #=============================================
  cursor = conn.cursor()

  # Expanded to 5 sub-tabs including the Weekly Matrix Summary
  sub_tab1, sub_tab2, sub_tab3, sub_tab4, sub_tab5 = st.tabs([
      "📁 Banks Registry",
      "➕ Log New Loan Proceeds",
      "📅 Amortization & Check Tracking",
      "🗓️ Payables Calendar & PDF",
      "📊 Weekly Payables Matrix",  # <--- TAB 5
  ])

  # --- SUB-TAB 1: BANKS REGISTRY ---
  with sub_tab1:
    st.markdown("### Registered Financial Institutions")
    banks_df = pd.read_sql("SELECT * FROM banks_master", conn)

    if not banks_df.empty:
      edited_banks = st.data_editor(
          banks_df, key="banks_editor", width="stretch", num_rows="dynamic"
      )

      if st.button("💾 Save Bank Changes"):
        for idx, row in edited_banks.iterrows():
          cursor.execute(
              """
                        UPDATE banks_master 
                        SET institution_name = ?, branch = ?, account_type = ?, default_account_no = ?, contact_person = ?, contact_number = ?, notes = ?
                        WHERE bank_id = ?
                    """,
              (
                  row["institution_name"],
                  row["branch"],
                  row["account_type"],
                  row["default_account_no"],
                  row["contact_person"],
                  row["contact_number"],
                  row["notes"],
                  int(row["bank_id"]),
              ),
          )
        conn.commit()
        st.success("Bank registry updated successfully!")
        st.rerun()
    else:
      st.info("No banks or lenders registered yet.")

    st.markdown("---")
    st.markdown("### Add New Bank or Lending Partner")
    with st.form("new_bank_form_unified"):
      col1, col2 = st.columns(2)
      with col1:
        inst_name = st.text_input(
            "Institution Name", value="1st Valley Bank, Inc."
        )
        branch = st.text_input("Branch", value="Mandaue Branch")
        acct_type = st.selectbox(
            "Account / Facility Type",
            ["SME Secured Credit Line", "Term Loan", "Checking", "Savings"],
        )
      with col2:
        default_acct = st.text_input(
            "Default Account Number", value="056-05-00024-1"
        )
        contact_person = st.text_input("Contact Person / Loan Officer", value="")
        contact_number = st.text_input("Contact Number", value="")

      notes = st.text_area("Notes / Remarks", value="")

      submitted_bank = st.form_submit_button("Save New Institution")
      if submitted_bank:
        cursor.execute(
            """
                    INSERT INTO banks_master (institution_name, branch, account_type, default_account_no, contact_person, contact_number, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
            (
                inst_name,
                branch,
                acct_type,
                default_acct,
                contact_person,
                contact_number,
                notes,
            ),
        )
        conn.commit()
        st.success(
            f"Successfully registered **{inst_name} - {branch}** to database!"
        )
        st.rerun()

  # --- SUB-TAB 2: LOG NEW LOAN PROCEEDS ---
  # --- SUB-TAB 2: LOG NEW LOAN PROCEEDS ---
  with sub_tab2:
    st.markdown("### Record New Bank Loan Release & Amortization")
    banks_df = pd.read_sql("SELECT * FROM banks_master", conn)

    if banks_df.empty:
      st.warning(
          "Please register at least one bank in the 'Banks Registry' tab first!"
      )
    else:
      with st.form("new_loan_proceeds_form"):
        col1, col2 = st.columns(2)

        with col1:
          selected_bank_id = st.selectbox(
              "Select Lending Institution",
              banks_df["bank_id"],
              format_func=lambda x: f"{banks_df[banks_df['bank_id'] == x]['institution_name'].values[0]} ({banks_df[banks_df['bank_id'] == x]['branch'].values[0]})",
          )
          selected_bank_row = banks_df[banks_df["bank_id"] == selected_bank_id].iloc[0]
          default_acct = selected_bank_row["default_account_no"] or ""

          account_no = st.text_input("Account Number", value=default_acct)
          pn_no = st.text_input(
              "Promissory Note (PN) Number", value="2610-056-000409"
          )
          borrower = st.text_input(
              "Borrower Name", value="TUANSON, RICARDO PERAS"
          )
          principal = st.number_input(
              "Principal Amount Released (₱)", value=2000000.0, step=10000.0
          )

        with col2:
          date_granted = st.text_input("Date Granted", value="10/26/2026")
          maturity_date = st.text_input("Maturity Date", value="10/26/2027")
          term_months = st.number_input(
              "Loan Term (Months)", value=12, step=1, min_value=1
          )
          loan_product = st.text_input(
              "Loan Product Description",
              value="LE4 - SME SECURED - CREDIT LINE",
          )
          interest_rate = st.number_input(
              "Interest Rate (e.g., 0.13 for 13%)", value=0.13, step=0.01
          )

        submitted_loan = st.form_submit_button(
            "💾 Save Loan & Generate Amortization Schedule"
        )

        if submitted_loan:
          cursor.execute(
              """
                        INSERT INTO loans_master (
                            bank_id, bank_name, branch, account_number, promissory_note_no, 
                            borrower_name, principal_amount, date_granted, maturity_date, 
                            loan_term_months, loan_product, interest_rate, loan_status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Current')
                    """,
              (
                  int(selected_bank_id),
                  selected_bank_row["institution_name"],
                  selected_bank_row["branch"],
                  account_no,
                  pn_no,
                  borrower,
                  principal,
                  date_granted,
                  maturity_date,
                  int(term_months),
                  loan_product,
                  interest_rate,
              ),
          )
          loan_id = cursor.lastrowid

          # Actual/360 Day-Count Amortization Generation
          start_dt = pd.to_datetime(date_granted)
          prev_dt = start_dt

          for i in range(1, int(term_months) + 1):
            due_dt = start_dt + pd.DateOffset(months=i)
            due_date_str = due_dt.strftime("%m/%d/%Y")
            
            # Exact days in period
            days_diff = (due_dt - prev_dt).days
            
            # Actual/360 interest formula matching official bank schedule
            interest_due = principal * interest_rate * (days_diff / 360.0)

            prin_due = principal if i == term_months else 0.0
            total_amt = prin_due + interest_due

            cursor.execute(
                """
                            INSERT INTO loan_amortization_schedule (
                                loan_id, installment_no, due_date, principal_balance, 
                                principal_due, interest_due, total_amount_due, 
                                payee, reference, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unpaid')
                        """,
                (
                    loan_id,
                    i,
                    due_date_str,
                    principal,
                    prin_due,
                    interest_due,
                    total_amt,
                    selected_bank_row["institution_name"],
                    f"ACCTNO-{account_no} PN#{pn_no}",
                ),
            )
            prev_dt = due_dt

          conn.commit()
          st.success(
              "Loan proceeds and Actual/360 amortization schedule generated"
              " successfully!"
          )
          st.rerun()

  # --- SUB-TAB 3: AMORTIZATION & CHECK TRACKING ---
  # --- SUB-TAB 3: AMORTIZATION & CHECK TRACKING ---
  with sub_tab3:
    st.markdown(
        "### Amortization Schedule & Check Disbursement Allocation Matrix"
    )
    loans_list = pd.read_sql(
        "SELECT loan_id, bank_name, promissory_note_no, borrower_name FROM loans_master",
        conn,
    )

    if not loans_list.empty:
      selected_loan_choice = st.selectbox(
          "Select Loan Account",
          loans_list["loan_id"],
          format_func=lambda x: f"{loans_list[loans_list['loan_id'] == x]['bank_name'].values[0]} [PN#: {loans_list[loans_list['loan_id'] == x]['promissory_note_no'].values[0]}]",
      )

      # --- ADD THIS DELETE OPTION HERE ---
      with st.expander("⚠️ Danger Zone: Manage / Delete Loan Account"):
        if st.button("🗑️ Delete This Duplicate Loan & Its Schedules", type="primary"):
          cursor.execute(
              "DELETE FROM loan_amortization_schedule WHERE loan_id = ?",
              (int(selected_loan_choice),),
          )
          cursor.execute(
              "DELETE FROM loans_master WHERE loan_id = ?",
              (int(selected_loan_choice),),
          )
          conn.commit()
          st.success("Loan account and its schedules deleted successfully!")
          st.rerun()

      sched_df = pd.read_sql(
          "SELECT * FROM loan_amortization_schedule WHERE loan_id = ?",
          conn,
          params=(int(selected_loan_choice),),
      )

      if not sched_df.empty:
        edited_sched = st.data_editor(
            sched_df[
                [
                    "installment_no",
                    "due_date",
                    "principal_balance",
                    "principal_due",
                    "interest_due",
                    "total_amount_due",
                    "check_no",
                    "voucher_no",
                    "payee",
                    "reference",
                    "status",
                ]
            ],
            key="amort_matrix_editor",
            width="stretch",
            num_rows="fixed",
        )

        if st.button("💾 Save Amortization & Check Updates"):
          for idx, row in edited_sched.iterrows():
            cursor.execute(
                """
                            UPDATE loan_amortization_schedule 
                            SET due_date = ?, principal_due = ?, interest_due = ?, total_amount_due = ?, 
                                check_no = ?, voucher_no = ?, payee = ?, reference = ?, status = ?
                            WHERE loan_id = ? AND installment_no = ?
                        """,
                (
                    row["due_date"],
                    float(row["principal_due"]) if pd.notna(row["principal_due"]) else 0.0,
                    float(row["interest_due"]) if pd.notna(row["interest_due"]) else 0.0,
                    float(row["total_amount_due"]) if pd.notna(row["total_amount_due"]) else 0.0,
                    row["check_no"],
                    row["voucher_no"],
                    row["payee"],
                    row["reference"],
                    row["status"],
                    int(selected_loan_choice),
                    int(row["installment_no"]),
                ),
            )
          conn.commit()
          st.success("Amortization schedule and exact amounts saved successfully!")
          st.rerun()

  # --- SUB-TAB 4: PAYABLES CALENDAR & PDF EXPORT ---
  with sub_tab4:
    st.markdown(
        "### 🗓️ Monthly Payables Calendar & Amortization Schedule View"
    )

    col_y, col_m = st.columns(2)
    with col_y:
      sel_year = st.selectbox("Select Year", [2026, 2027, 2028], index=0)
    with col_m:
      sel_month = st.selectbox(
          "Select Month",
          list(range(1, 13)),
          format_func=lambda x: calendar.month_name[x],
          index=10,
      )

    amort_df = pd.read_sql(
        """
            SELECT l.bank_name, l.promissory_note_no, a.due_date, a.total_amount_due, a.status 
            FROM loan_amortization_schedule a
            JOIN loans_master l ON a.loan_id = l.loan_id
        """,
        conn,
    )

    events_dict = {}
    if not amort_df.empty:
      for idx, row in amort_df.iterrows():
        try:
          dt = pd.to_datetime(row["due_date"])
          if dt.year == sel_year and dt.month == sel_month:
            day_num = dt.day
            bank_raw = str(row["bank_name"]) if pd.notna(row["bank_name"]) else "Bank"
            short_bank = bank_raw[:10]
            amt = row["total_amount_due"]

            if day_num not in events_dict:
              events_dict[day_num] = []
            events_dict[day_num].append(f"{short_bank}: ₱{amt:,.2f}")
        except Exception:
          pass

    st.markdown(
        f"#### {calendar.month_name[sel_month]} {sel_year} Schedule Grid"
    )

    cal = calendar.Calendar(firstweekday=6)
    month_days = cal.monthdayscalendar(sel_year, sel_month)
    days_header = [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]

    calendar_grid_data = []
    for week in month_days:
      week_row = {}
      for i, day in enumerate(week):
        day_name = days_header[i]
        if day == 0:
          week_row[day_name] = ""
        else:
          content = f"<b>{day}</b>"
          if day in events_dict:
            for ev in events_dict[day]:
              content += f"<br><span style='color:red; font-size:11px;'>• {ev}</span>"
          week_row[day_name] = content
      calendar_grid_data.append(week_row)

    cal_df = pd.DataFrame(calendar_grid_data)
    st.markdown(
        cal_df.to_html(escape=False, index=False), unsafe_allow_html=True
    )

    st.markdown("---")

    if st.button("📥 Generate Printable PDF Calendar"):
      pdf_buffer = generate_calendar_pdf(
          sel_year, sel_month, calendar.month_name[sel_month], events_dict
      )
      st.download_button(
          label="⬇️ Download Payables PDF",
          data=pdf_buffer,
          file_name=(
              f"Payables_Calendar_{calendar.month_name[sel_month]}_{sel_year}.pdf"
          ),
          mime="application/pdf",
      )

  # --- SUB-TAB 5: WEEKLY PAYABLES MATRIX SUMMARY ---
  with sub_tab5:
    st.markdown("### 📊 Weekly Payables & Amortization Matrix Summary")

    col_y5, col_m5 = st.columns(2)
    with col_y5:
      sel_year5 = st.selectbox(
          "Matrix Year", [2026, 2027, 2028], index=0, key="mat_year"
      )
    with col_m5:
      sel_month5 = st.selectbox(
          "Matrix Month",
          list(range(1, 13)),
          format_func=lambda x: calendar.month_name[x],
          index=10,
          key="mat_month",
      )

    # 1. Fetch loan amortizations
    amort_matrix_df = pd.read_sql(
        """
            SELECT l.bank_name as payee, a.due_date, a.total_amount_due 
            FROM loan_amortization_schedule a
            JOIN loans_master l ON a.loan_id = l.loan_id
        """,
        conn,
    )

    # 2. Fetch Accounts Payable Vouchers / Check Vouchers if available
    try:
      apv_matrix_df = pd.read_sql(
          """
                SELECT payee_name as payee, voucher_date as due_date, amount as total_amount_due 
                FROM accounts_payable_vouchers
            """,
          conn,
      )
    except Exception:
      try:
        apv_matrix_df = pd.read_sql(
            """
                    SELECT payee, voucher_date as due_date, amount as total_amount_due 
                    FROM check_vouchers
                """,
            conn,
        )
      except Exception:
        apv_matrix_df = pd.DataFrame(
            columns=["payee", "due_date", "total_amount_due"]
        )

    # Combine data sources
    combined_matrix = pd.concat(
        [amort_matrix_df, apv_matrix_df], ignore_index=True
    )

    matrix_rows = []
    if not combined_matrix.empty:
      for _, row in combined_matrix.iterrows():
        try:
          dt = pd.to_datetime(row["due_date"])
          if dt.year == sel_year5 and dt.month == sel_month5:
            matrix_rows.append({
                "payee": str(row["payee"])[:10].upper(),
                "day": dt.day,
                "amount": float(row["total_amount_due"]),
            })
        except Exception:
          pass

    if matrix_rows:
      df_matrix = pd.DataFrame(matrix_rows)
      pivot_matrix = df_matrix.pivot_table(
          index="payee",
          columns="day",
          values="amount",
          aggfunc="sum",
          fill_value=0.0,
      )

      # Ensure all days of the month are represented
      _, total_days = calendar.monthrange(sel_year5, sel_month5)
      for d in range(1, total_days + 1):
        if d not in pivot_matrix.columns:
          pivot_matrix[d] = 0.0

      pivot_matrix = pivot_matrix[
          sorted([c for c in pivot_matrix.columns if isinstance(c, int)])
      ]
      pivot_matrix["TOTAL"] = pivot_matrix.sum(axis=1)

      st.dataframe(
          pivot_matrix.style.format("{:,.2f}"), width="stretch"
      )
    else:
      st.info(
          "No payables or loan amortizations recorded for this month yet."
      )
#==================End of Lending Bank Loan=======
#===================Bank Databae table
def init_banks_database(conn):
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS banks_master (
            bank_id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution_name TEXT NOT NULL,
            branch TEXT,
            account_type TEXT, -- e.g., 'Credit Line', 'Savings', 'Checking'
            default_account_no TEXT,
            contact_person TEXT,
            contact_number TEXT,
            notes TEXT
        )
    """)
  conn.commit()
#======

#================================Loans Database============================
import sqlite3


def init_loans_database(conn):
  cursor = conn.cursor()

  # Loan Master Table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS loans_master (
            loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_name TEXT NOT NULL,
            branch TEXT,
            account_number TEXT NOT NULL,
            promissory_note_no TEXT NOT NULL,
            borrower_name TEXT NOT NULL,
            principal_amount REAL NOT NULL,
            date_granted TEXT NOT NULL,
            maturity_date TEXT NOT NULL,
            loan_term_months INTEGER NOT NULL,
            loan_product TEXT,
            interest_rate REAL NOT NULL,
            loan_status TEXT DEFAULT 'Current'
        )
    """)

  # Amortization Schedule & Payment Link Table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS loan_amortization_schedule (
            installment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id INTEGER,
            installment_no INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            principal_balance REAL NOT NULL,
            principal_due REAL DEFAULT 0,
            interest_due REAL NOT NULL,
            total_amount_due REAL NOT NULL,
            status TEXT DEFAULT 'unpaid',
            check_no TEXT,
            voucher_no TEXT,
            payee TEXT,
            reference TEXT,
            FOREIGN KEY (loan_id) REFERENCES loans_master (loan_id)
        )
    """)
  conn.commit()
#=============================end Loans Database============================
#================
#from apscheduler.schedulers.background import BackgroundScheduler
#from auto_weather_logger import run_auto_logger

# Initialize background scheduler once
@st.cache_resource
def start_weather_cron():
    scheduler = BackgroundScheduler(daemon=True)
    # Runs at 8:00 AM, 12:00 PM, and 5:00 PM daily
    scheduler.add_job(run_auto_logger, 'cron', hour='8,12,17', minute=0)
    scheduler.start()
    return scheduler

#start_weather_cron()

#===============Auto Logs
import sqlite3
import requests
import streamlit as st
from datetime import datetime

# 1. Project Sites & GPS Mapping
SITE_COORDINATES = {
    "Main Office / Yard": (10.3157, 123.8854),
    "Site A - Commercial Bldg": (10.2447, 123.8488),
    "Site B - Residential": (10.2452, 123.7961),
    "Site C - Infrastructure": (10.2800, 123.8800)
}

# 2. Live Internet Helper (Optional 1-Click Pre-fill)
def fetch_live_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json().get("current_weather", {})
            temp = float(data.get("temperature", 31.0))
            wcode = int(data.get("weathercode", 0))

            if wcode == 0: cond = "☀️ Sunny / Fair"
            elif wcode in [1, 2]: cond = "⛅ Partly Cloudy"
            elif wcode in [3, 45, 48]: cond = "☁️ Overcast / Gloomy"
            elif wcode in [51, 53, 55, 61, 63]: cond = "🌦️ Light Rain / Drizzle"
            elif wcode in [65, 80, 81, 82]: cond = "🌧️ Heavy Rain"
            elif wcode in [95, 96, 99]: cond = "⛈️ Thunderstorm / Downpour"
            else: cond = "⛅ Partly Cloudy"

            return temp, cond
    except Exception:
        pass
    return 31.0, "☀️ Sunny / Fair"

# 3. Weather Entry UI Module
def render_manual_weather_entry(conn):
    st.subheader("📝 Daily Site Weather Logging")

    # Session State for Form Pre-filling
    if "form_temp" not in st.session_state:
        st.session_state["form_temp"] = 31.0
    if "form_cond" not in st.session_state:
        st.session_state["form_cond"] = "☀️ Sunny / Fair"

    # Site Selection & Optional Live Fetch
    col_site, col_btn = st.columns([3, 1])
    with col_site:
        selected_site = st.selectbox("Select Project Site", list(SITE_COORDINATES.keys()))
    with col_btn:
        st.write("") # Spacing alignment
        if st.button("🌐 Pre-fill via Internet"):
            lat, lon = SITE_COORDINATES[selected_site]
            t, c = fetch_live_weather(lat, lon)
            st.session_state["form_temp"] = t
            st.session_state["form_cond"] = c
            st.success(f"Fetched: {c} ({t}°C)")

    # Manual Entry Form
    with st.form("manual_weather_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            log_date = st.date_input("Log Date", datetime.now())
        with c2:
            log_time = st.time_input("Time Recorded", datetime.now().time())
        with c3:
            temp_c = st.number_input("Temperature (°C)", value=float(st.session_state["form_temp"]), step=0.5)

        conditions_list = [
            "☀️ Sunny / Fair", "⛅ Partly Cloudy", "☁️ Overcast / Gloomy", 
            "🌦️ Light Rain / Drizzle", "🌧️ Heavy Rain", "⛈️ Thunderstorm / Downpour"
        ]
        
        # Calculate selected index
        cond_idx = conditions_list.index(st.session_state["form_cond"]) if st.session_state["form_cond"] in conditions_list else 0

        c4, c5 = st.columns(2)
        with c4:
            weather_cond = st.selectbox("Weather Condition", conditions_list, index=cond_idx)
        with c5:
            impact = st.selectbox("Site Operations Impact", [
                "🟢 Normal Operations",
                "🟡 Partial Work Suspension (Outdoors Stopped)",
                "🔴 Full Work Suspension (Site Standstill)"
            ])

        c6, c7 = st.columns([1, 3])
        with c6:
            lost_hrs = st.number_input("Hours Lost", min_value=0.0, max_value=24.0, value=0.0, step=0.5)
        with c7:
            remarks = st.text_input("Remarks / Local Notes", placeholder="e.g., ni ulan ug mga 25 minutes")

        submitted = st.form_submit_button("💾 Save Weather Log", type="primary")

        if submitted:
            c = conn.cursor()
            
            # Ensure DB table exists
            c.execute('''
                CREATE TABLE IF NOT EXISTS daily_weather_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_date TEXT NOT NULL,
                    day_of_week TEXT NOT NULL,
                    log_time TEXT NOT NULL,
                    project_site TEXT NOT NULL,
                    weather_condition TEXT NOT NULL,
                    temp_celsius REAL,
                    impact_level TEXT NOT NULL,
                    work_disruption_hrs REAL DEFAULT 0.0,
                    remarks TEXT,
                    logged_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            day_name = log_date.strftime("%A")
            formatted_date = log_date.strftime("%Y-%m-%d")
            formatted_time = log_time.strftime("%I:%M %p")

            c.execute('''
                INSERT INTO daily_weather_logs 
                (log_date, day_of_week, log_time, project_site, weather_condition, temp_celsius, impact_level, work_disruption_hrs, remarks, logged_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (formatted_date, day_name, formatted_time, selected_site, weather_cond, temp_c, impact, lost_hrs, remarks, "Site Engineer"))
            
            conn.commit()
            st.success(f"Successfully recorded weather log for {selected_site}!")

#==============================Weather Report Lab
import io
from datetime import datetime, date
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def clean_pdf_text(text):
    """Strips emoji characters so standard ReportLab fonts render cleanly."""
    if not text:
        return ""
    emojis = ["☀️", "⛅", "☁️", "🌦️", "🌧️", "⛈️", "🌀", "🟢", "🟡", "🔴"]
    cleaned = str(text)
    for e in emojis:
        cleaned = cleaned.replace(e, "")
    return cleaned.strip()

def generate_weather_report_pdf(site_name, start_date_str, end_date_str, df_logs, prepared_by="Site Engineer"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    # Custom Typography Styles
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=14, leading=18, alignment=1)
    subtitle_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=14, alignment=1, textColor=colors.HexColor("#2C3E50"))
    meta_label = ParagraphStyle('MetaLabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10)
    meta_val = ParagraphStyle('MetaVal', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10)
    
    hdr_style = ParagraphStyle('TblHdr', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white, alignment=0)
    body_style = ParagraphStyle('TblBody', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9.5)
    body_center = ParagraphStyle('TblBodyCenter', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9.5, alignment=1)
    body_bold = ParagraphStyle('TblBodyBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9.5)

    # 1. Header Title Block
    story.append(Paragraph("TUANSON CONSTRUCTION", title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("WEEKLY SITE WEATHER & WORK DISRUPTION REPORT", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2C3E50"), spaceAfter=10))

    # 2. Metadata & Metrics Box
    total_entries = len(df_logs)
    total_disruption = df_logs["work_disruption_hrs"].sum() if not df_logs.empty else 0.0
    rainy_days = df_logs[df_logs["weather_condition"].str.contains("Rain|Storm|Typhoon", na=False)]["log_date"].nunique() if not df_logs.empty else 0

    meta_data = [
        [
            Paragraph("Project Site:", meta_label), Paragraph(clean_pdf_text(site_name), meta_val),
            Paragraph("Report Date:", meta_label), Paragraph(date.today().strftime("%B %d, %Y"), meta_val)
        ],
        [
            Paragraph("Week Covered:", meta_label), Paragraph(f"{start_date_str} to {end_date_str}", meta_val),
            Paragraph("Rainy / Storm Days:", meta_label), Paragraph(f"{rainy_days} Day(s)", meta_val)
        ],
        [
            Paragraph("Total Log Entries:", meta_label), Paragraph(str(total_entries), meta_val),
            Paragraph("Total Disruption:", meta_label), Paragraph(f"<b>{total_disruption:.1f} Hours Lost</b>", meta_val)
        ]
    ]

    meta_table = Table(meta_data, colWidths=[80, 190, 100, 170])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8F9FA")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#BDC3C7")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#ECF0F1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # 3. Itemized Logs Table
    table_data = [[
        Paragraph("Date & Day", hdr_style),
        Paragraph("Time", hdr_style),
        Paragraph("Condition", hdr_style),
        Paragraph("Site Impact", hdr_style),
        Paragraph("Lost Hrs", hdr_style),
        Paragraph("Remarks / Disruption Details", hdr_style)
    ]]

    if not df_logs.empty:
        for _, row in df_logs.iterrows():
            date_day_str = f"{row['log_date']}\n({row['day_of_week'][:3]})"
            
            table_data.append([
                Paragraph(date_day_str, body_bold),
                Paragraph(clean_pdf_text(row['log_time']), body_center),
                Paragraph(clean_pdf_text(row['weather_condition']), body_style),
                Paragraph(clean_pdf_text(row['impact_level']), body_style),
                Paragraph(f"{row['work_disruption_hrs']:.1f}", body_center),
                Paragraph(clean_pdf_text(row['remarks']), body_style)
            ])
    else:
        table_data.append([
            Paragraph("No weather logs recorded for this period.", body_style),
            Paragraph("-", body_center), Paragraph("-", body_style),
            Paragraph("-", body_style), Paragraph("0.0", body_center), Paragraph("-", body_style)
        ])

    logs_table = Table(table_data, colWidths=[75, 55, 95, 120, 45, 150])
    logs_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1F4E78")),
        ('ALIGN', (0,0), (-1,0), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#D0D7DE")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F9FBFD")]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(logs_table)
    story.append(Spacer(1, 20))

    # 4. Sign-Off Block
    sig_data = [
        [
            Paragraph("<b>Prepared By:</b>", meta_label),
            Paragraph("<b>Checked By:</b>", meta_label),
            Paragraph("<b>Acknowledged By:</b>", meta_label)
        ],
        [
            Paragraph("<br/><br/>___________________________<br/><b>Site Engineer / Inspector</b>", body_style),
            Paragraph("<br/><br/>___________________________<br/><b>Project Manager</b>", body_style),
            Paragraph("<br/><br/>___________________________<br/><b>Owner / Consultant Rep.</b>", body_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[180, 180, 180])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

#============================Weather logs
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

def render_engineering_weather_tab(conn, c):
    # Auto-create table if it doesn't exist yet
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_weather_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            log_time TEXT NOT NULL,
            project_site TEXT NOT NULL,
            weather_condition TEXT NOT NULL,
            temp_celsius REAL,
            impact_level TEXT NOT NULL,
            work_disruption_hrs REAL DEFAULT 0.0,
            remarks TEXT,
            logged_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    st.header("🏗️ Engineering & Project Site Monitoring")
    
    sub_tab1, sub_tab2 = st.tabs(["📝 Log Daily Weather", "📅 Weekly Weather Summary"])

    # -----------------------------------------------------------------
    # SUB-TAB 1: LOG DAILY WEATHER
    # -----------------------------------------------------------------
    with sub_tab1:
        st.subheader("Record Site Weather Condition")

        with st.form("weather_log_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                selected_date = st.date_input("Date", value=date.today())
                day_name = selected_date.strftime("%A")  # Auto Monday, Tuesday...
                st.text_input("Day of Week", value=day_name, disabled=True)
                
            with col2:
                log_time = st.time_input("Log Time", value=datetime.now().time())
                project_site = st.selectbox("Project Site", [
                    "Main Office / Yard", 
                    "Site A - Commercial Bldg", 
                    "Site B - Residential", 
                    "Site C - Infrastructure"
                ])

            with col3:
                weather_cond = st.selectbox("Weather Condition", [
                    "☀️ Sunny / Fair",
                    "⛅ Partly Cloudy",
                    "☁️ Overcast / Gloomy",
                    "🌦️ Light Rain / Drizzle",
                    "🌧️ Heavy Rain",
                    "⛈️ Thunderstorm / Downpour",
                    "🌀 Typhoon / Tropical Storm"
                ])
                impact = st.selectbox("Site Work Impact", [
                    "🟢 Normal Operations",
                    "🟡 Partial Work Suspension (Outdoors Stopped)",
                    "🔴 Full Work Suspension (Site Standstill)"
                ])

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                disruption_hrs = st.number_input("Work Disruption (Hours)", min_value=0.0, max_value=24.0, step=0.5, value=0.0)
            with col_b:
                temp = st.number_input("Estimated Temp (°C)", min_value=15.0, max_value=50.0, value=31.0, step=0.5)
            with col_c:
                logged_by = st.text_input("Logged By (Engineer/Inspector)", value="Site Engineer")

            remarks = st.text_area("Remarks / Work Affected", placeholder="e.g., Concrete pouring postponed due to heavy rain.")

            submit_btn = st.form_submit_button("💾 Save Weather Log", type="primary")

            if submit_btn:
                time_str = log_time.strftime("%I:%M %p")
                date_str = selected_date.strftime("%Y-%m-%d")

                c.execute('''
                    INSERT INTO daily_weather_logs 
                    (log_date, day_of_week, log_time, project_site, weather_condition, temp_celsius, impact_level, work_disruption_hrs, remarks, logged_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (date_str, day_name, time_str, project_site, weather_cond, temp, impact, disruption_hrs, remarks, logged_by))
                conn.commit()
                st.success(f"Weather logged for {project_site} on {date_str} ({day_name} at {time_str})!")
                st.rerun()

    # -----------------------------------------------------------------
    # SUB-TAB 2: WEEKLY WEATHER SUMMARY & PDF GENERATOR
    # -----------------------------------------------------------------
    with sub_tab2:
        st.subheader("Weekly Site Weather Chart & Disruption Log")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            site_filter = st.selectbox("Filter Project Site", [
                "Main Office / Yard", 
                "Site A - Commercial Bldg", 
                "Site B - Residential", 
                "Site C - Infrastructure"
            ])
        with col_f2:
            ref_date = st.date_input("Select Date in Target Week", value=date.today())
            
        # Calculate Monday to Sunday date range
        start_of_week = ref_date - timedelta(days=ref_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        start_str = start_of_week.strftime("%Y-%m-%d")
        end_str = end_of_week.strftime("%Y-%m-%d")

        st.info(f"📅 **Showing Week:** {start_of_week.strftime('%b %d, %Y')} (Monday) to {end_of_week.strftime('%b %d, %Y')} (Sunday)")

        query = """
            SELECT log_date, day_of_week, log_time, project_site, weather_condition, 
                   impact_level, work_disruption_hrs, remarks, logged_by 
            FROM daily_weather_logs 
            WHERE log_date BETWEEN ? AND ? AND project_site = ?
            ORDER BY log_date ASC, log_time ASC
        """
        df_logs = pd.read_sql_query(query, conn, params=[start_str, end_str, site_filter])

        # Summary Metrics
        total_disruption = df_logs["work_disruption_hrs"].sum() if not df_logs.empty else 0.0
        rainy_days = df_logs[df_logs["weather_condition"].str.contains("Rain|Storm|Typhoon", na=False)]["log_date"].nunique() if not df_logs.empty else 0
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Entries", len(df_logs))
        m2.metric("Rainy/Storm Days", f"{rainy_days} Days")
        m3.metric("Hours Disrupted", f"{total_disruption:.1f} hrs")
        
        # PDF Generation Action
        pdf_bytes = generate_weather_report_pdf(
            site_name=site_filter,
            start_date_str=start_of_week.strftime('%b %d, %Y'),
            end_date_str=end_of_week.strftime('%b %d, %Y'),
            df_logs=df_logs
        )
        
        with m4:
            st.write("") 
            st.download_button(
                label="📄 Download PDF Report",
                data=pdf_bytes,
                file_name=f"Weather_Report_{site_filter.replace(' ', '_')}_{start_str}.pdf",
                mime="application/pdf",
                type="primary",
                width="stretch"
            )

        st.markdown("---")
        
        # FIXED HERE: Removed parentheses () from df_logs.empty
        if not df_logs.empty:
            st.dataframe(
                df_logs.rename(columns={
                    "log_date": "Date",
                    "day_of_week": "Day",
                    "log_time": "Time",
                    "weather_condition": "Condition",
                    "impact_level": "Site Impact",
                    "work_disruption_hrs": "Hours Lost",
                    "remarks": "Remarks / Details",
                    "logged_by": "Inspector"
                })[["Date", "Day", "Time", "Condition", "Site Impact", "Hours Lost", "Remarks / Details", "Inspector"]],
                width="stretch"
            )
        else:
            st.warning(f"No weather logs found for {site_filter} during the week of {start_str} to {end_str}.")

            
#===============================Payoll Staff Setup================
def init_office_payroll_tables(conn):
    c = conn.cursor()
    
    # 1. Office Staff Masterlist
    c.execute("""
        CREATE TABLE IF NOT EXISTS office_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE,
            name TEXT NOT NULL,
            position TEXT,
            monthly_rate REAL DEFAULT 0.0,
            allowance REAL DEFAULT 0.0,
            active_status TEXT DEFAULT 'Active',
            reason_if_resign TEXT,
            date_hired TEXT,
            sss_default REAL DEFAULT 0.0,
            phic_default REAL DEFAULT 0.0,
            hdmf_default REAL DEFAULT 0.0,
            wtax_default REAL DEFAULT 0.0,
            ca_balance REAL DEFAULT 0.0
        )
    """)

    # 2. Cut-off Payroll Records
    c.execute("""
        CREATE TABLE IF NOT EXISTS office_payroll_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_label TEXT, -- e.g. 'SEP 1-15, 2026'
            employee_id TEXT,
            name TEXT,
            position TEXT,
            monthly_rate REAL,
            basic_pay REAL,
            allowance REAL,
            ot_pay REAL DEFAULT 0.0,
            sunday_work REAL DEFAULT 0.0,
            reg_holiday_pay REAL DEFAULT 0.0,
            spec_holiday_pay REAL DEFAULT 0.0,
            paid_leave REAL DEFAULT 0.0,
            tardy REAL DEFAULT 0.0,
            undertime REAL DEFAULT 0.0,
            absent REAL DEFAULT 0.0,
            gross_pay REAL,
            sss_deduction REAL DEFAULT 0.0,
            phic_deduction REAL DEFAULT 0.0,
            hdmf_deduction REAL DEFAULT 0.0,
            wtax_deduction REAL DEFAULT 0.0,
            ca_deduction REAL DEFAULT 0.0,
            ca_remaining_balance REAL DEFAULT 0.0,
            total_deductions REAL,
            net_pay REAL,
            created_at TEXT
        )
    """)
    conn.commit()

#=========================Report Lab=======================
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def draw_single_payslip_on_canvas(p, top_y, data, is_employee_copy=False, page_w=612):
    """Helper function to draw a single 2-up payslip section on a given canvas."""
    # 1. Title Header
    p.setFont("Helvetica-Bold", 12)
    title_text = "PAYSLIP EMPLOYEE'S COPY" if is_employee_copy else "PAYSLIP"
    p.drawCentredString(page_w / 2.0, top_y, title_text)

    # Company Name & Period
    p.setFont("Helvetica-Bold", 10)
    p.drawString(36, top_y - 20, "TUANSON CONSTRUCTION")
    
    p.setFont("Helvetica", 9)
    p.drawString(210, top_y - 20, f"Period: {data.get('period_label', '')}")
    p.drawRightString(page_w - 36, top_y - 20, f"Rate: {data.get('monthly_rate', 0.0):,.2f}")

    p.drawString(36, top_y - 35, f"ID #: {data.get('employee_id', '')}")
    p.drawString(210, top_y - 35, f"Designation: {data.get('position', '')}")

    p.setFont("Helvetica-Bold", 10)
    p.drawString(36, top_y - 50, f"Employee: {data.get('name', '')}")

    # Table Column Headers
    header_y = top_y - 72
    p.line(36, header_y + 12, page_w - 36, header_y + 12)

    p.setFont("Helvetica-Bold", 8)
    p.drawString(36, header_y, "GROSS EARNINGS")
    p.drawRightString(170, header_y, "AMOUNT")

    p.drawString(185, header_y, "DEDUCTIONS")
    p.drawRightString(315, header_y, "AMOUNT")

    p.drawString(330, header_y, "OTHER DEDUCTIONS")
    p.drawRightString(470, header_y, "AMOUNT")
    p.drawRightString(576, header_y, "BALANCE")

    p.line(36, header_y - 4, page_w - 36, header_y - 4)

    # Content Rows
    p.setFont("Helvetica", 8)
    y = header_y - 16
    line_height = 12

    earnings = [
        ("Basic Pay", data.get('basic_pay', 0.0)),
        ("Allowance", data.get('allowance', 0.0)),
        ("Overtime Pay", data.get('ot_pay', 0.0)),
        ("Sunday Work", data.get('sunday_work', 0.0)),
        ("Regular Holiday Pay", data.get('reg_holiday_pay', 0.0)),
        ("Special Holiday Pay", data.get('spec_holiday_pay', 0.0)),
        ("Paid Leave", data.get('paid_leave', 0.0)),
    ]

    deductions = [
        ("SSS Contribution", data.get('sss_deduction', 0.0)),
        ("PHIC Contribution", data.get('phic_deduction', 0.0)),
        ("HDMF Contribution", data.get('hdmf_deduction', 0.0)),
        ("Withholding Tax", data.get('wtax_deduction', 0.0)),
        ("Other Deductions", 0.0),
    ]

    # Draw Earnings
    ey = y
    for label, amt in earnings:
        p.drawString(36, ey, label)
        p.drawRightString(170, ey, f"{amt:,.2f}")
        ey -= line_height

    # Draw LESS header and attendance deductions
    ey -= 2
    p.setFont("Helvetica-Bold", 8)
    p.drawString(36, ey, "LESS:")
    p.setFont("Helvetica", 8)
    ey -= line_height

    less_items = [
        ("Tardy", data.get('tardy', 0.0)),
        ("Undertime", data.get('undertime', 0.0)),
        ("Absent", data.get('absent', 0.0)),
    ]
    for label, amt in less_items:
        p.drawString(46, ey, label)
        p.drawRightString(170, ey, f"{amt:,.2f}")
        ey -= line_height

    p.line(36, ey + 4, 170, ey + 4)
    p.setFont("Helvetica-Bold", 8)
    p.drawString(36, ey - 4, "GROSS PAY")
    p.drawRightString(170, ey - 4, f"{data.get('gross_pay', 0.0):,.2f}")

    # Draw Deductions
    dy = y
    p.setFont("Helvetica", 8)
    for label, amt in deductions:
        p.drawString(185, dy, label)
        p.drawRightString(315, dy, f"{amt:,.2f}")
        dy -= line_height

    dy -= 8
    p.line(185, dy + 4, 315, dy + 4)
    p.setFont("Helvetica-Bold", 8.5)
    p.drawString(185, dy - 4, "NET PAY")
    p.drawRightString(315, dy - 4, f"{data.get('net_pay', 0.0):,.2f}")
    p.line(185, dy - 8, 315, dy - 8)

    # Draw C/A & Other Deductions
    cy = y
    p.setFont("Helvetica", 8)
    p.drawString(330, cy, "C/A - Deduction")
    p.drawRightString(470, cy, f"{data.get('ca_deduction', 0.0):,.2f}")
    p.drawRightString(576, cy, f"{data.get('ca_remaining_balance', 0.0):,.2f}")

    # Signature Box & Total Deductions
    sig_y = top_y - 210
    p.setFont("Helvetica-Bold", 8)
    p.drawString(185, sig_y, f"{data.get('name', '')}")
    p.setFont("Helvetica", 8)
    p.drawString(185, sig_y - 12, "Signature ______________________")

    p.setFont("Helvetica-Bold", 8)
    p.drawString(330, sig_y - 12, "TOTAL DEDUCTIONS")
    p.drawRightString(470, sig_y - 12, f"{data.get('total_deductions', 0.0):,.2f}")
    p.line(330, sig_y - 16, page_w - 36, sig_y - 16)


def generate_office_payslip_pdf(data):
    """Generates a single 1-page (2-up) PDF for one employee."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    page_w, page_h = letter

    # Employer Copy
    draw_single_payslip_on_canvas(p, top_y=750, data=data, is_employee_copy=False, page_w=page_w)

    # Perforated Line
    p.setDash(2, 2)
    p.line(36, 396, page_w - 36, 396)
    p.setDash()

    # Employee Copy
    draw_single_payslip_on_canvas(p, top_y=360, data=data, is_employee_copy=True, page_w=page_w)

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer.getvalue()


def generate_batch_office_payslips_pdf(records_list):
    """Generates a single multi-page PDF containing all payslips for a cut-off period."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    page_w, page_h = letter

    for data in records_list:
        # Employer Copy
        draw_single_payslip_on_canvas(p, top_y=750, data=data, is_employee_copy=False, page_w=page_w)

        # Perforated Line
        p.setDash(2, 2)
        p.line(36, 396, page_w - 36, 396)
        p.setDash()

        # Employee Copy
        draw_single_payslip_on_canvas(p, top_y=360, data=data, is_employee_copy=True, page_w=page_w)

        # Advance to next page for the next employee
        p.showPage()

    p.save()
    buffer.seek(0)
    return buffer.getvalue()

#================================Office Payroll=============================
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

def render_office_payroll_tab(conn):
    c = conn.cursor()
    st.title("💼 Office & Engineering Staff Payroll")

    # Ensure biometric_id column exists in office_staff
    try:
        c.execute("ALTER TABLE office_staff ADD COLUMN biometric_id TEXT")
        conn.commit()
    except:
        pass  # Column already exists

    sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
        "📋 Staff Masterlist", 
        "⏱️ Staff DTR / Attendance", 
        "⚙️ Process Cut-off Payroll", 
        "📄 Generate Payslips"
    ])

    # -----------------------------------------------------------------
    # SUB-TAB 1: STAFF MASTERLIST
    # -----------------------------------------------------------------
    with sub_tab1:
        st.subheader("Manage Office & Engineering Staff")
        
        col_m1, col_m2 = st.columns(2)

        # 1. ADD NEW STAFF FORM
        with col_m1:
            with st.expander("➕ Add New Staff Member"):
                with st.form("add_staff_form"):
                    col_a, col_b = st.columns(2)
                    emp_id = col_a.text_input("Employee ID", placeholder="1 or EMP-001")
                    emp_name = col_b.text_input("Full Name", placeholder="e.g. BRAZEL M. DELA CERNA")
                    
                    position = col_a.text_input("Position / Designation", placeholder="e.g. IT - System Programmer")
                    bio_id = col_b.text_input("Biometric Machine ID", value="", placeholder="e.g. 1")
                    
                    monthly_rate = col_a.number_input("Monthly Rate (₱)", min_value=0.0, step=500.0)
                    allowance = col_b.number_input("Allowance (₱)", min_value=0.0, step=100.0)
                    status = st.selectbox("Active Status", ["Active", "Resigned"])
                    
                    st.markdown("**Default Statutory Deductions (Per Month)**")
                    col_d, col_e, col_f, col_g = st.columns(4)
                    sss = col_d.number_input("SSS", min_value=0.0, value=750.0)
                    phic = col_e.number_input("PHIC", min_value=0.0, value=200.0)
                    hdmf = col_f.number_input("HDMF", min_value=0.0, value=200.0)
                    wtax = col_g.number_input("WTax", min_value=0.0, value=0.0)
                    ca_bal = st.number_input("Current C/A Balance (₱)", min_value=0.0, step=500.0)
                    
                    if st.form_submit_button("Save New Staff"):
                        if not emp_name or not emp_id:
                            st.error("Employee ID and Name are required!")
                        else:
                            c.execute("""
                                INSERT INTO office_staff 
                                (employee_id, name, position, monthly_rate, allowance, active_status, sss_default, phic_default, hdmf_default, wtax_default, ca_balance, biometric_id)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (emp_id, emp_name, position, monthly_rate, allowance, status, sss, phic, hdmf, wtax, ca_bal, bio_id))
                            conn.commit()
                            st.success(f"Added {emp_name} to Staff Masterlist!")
                            st.rerun()

        # 2. EDIT EXISTING STAFF FORM
        with col_m2:
            with st.expander("✏️ Edit Existing Staff Member"):
                all_staff = c.execute("SELECT id, employee_id, name, position, monthly_rate, allowance, active_status, sss_default, phic_default, hdmf_default, wtax_default, ca_balance, biometric_id FROM office_staff").fetchall()
                
                if all_staff:
                    edit_choice = st.selectbox("Select Staff to Edit", [f"ID #{s[0]} | {s[1]} - {s[2]}" for s in all_staff], key="edit_staff_select")
                    selected_db_id = int(edit_choice.split(" | ")[0].replace("ID #", ""))
                    s_data = next(s for s in all_staff if s[0] == selected_db_id)

                    with st.form("edit_staff_form"):
                        col_ea, col_eb = st.columns(2)
                        up_emp_id = col_ea.text_input("Employee ID", value=str(s_data[1]))
                        up_emp_name = col_eb.text_input("Full Name", value=str(s_data[2]))
                        
                        up_position = col_ea.text_input("Position / Designation", value=str(s_data[3]))
                        up_bio_id = col_eb.text_input("Biometric Machine ID", value=str(s_data[12] if s_data[12] else s_data[1]))
                        
                        up_monthly_rate = col_ea.number_input("Monthly Rate (₱)", min_value=0.0, value=float(s_data[4]), step=500.0)
                        up_allowance = col_eb.number_input("Allowance (₱)", min_value=0.0, value=float(s_data[5]), step=100.0)
                        
                        status_list = ["Active", "Resigned"]
                        up_status = st.selectbox("Active Status", status_list, index=status_list.index(s_data[6]) if s_data[6] in status_list else 0)
                        
                        st.markdown("**Default Statutory Deductions (Per Month)**")
                        col_ed, col_ee, col_ef, col_eg = st.columns(4)
                        up_sss = col_ed.number_input("SSS", min_value=0.0, value=float(s_data[7]))
                        up_phic = col_ee.number_input("PHIC", min_value=0.0, value=float(s_data[8]))
                        up_hdmf = col_ef.number_input("HDMF", min_value=0.0, value=float(s_data[9]))
                        up_wtax = col_eg.number_input("WTax", min_value=0.0, value=float(s_data[10]))
                        up_ca_bal = st.number_input("Current C/A Balance (₱)", min_value=0.0, value=float(s_data[11]), step=500.0)
                        
                        if st.form_submit_button("Update Staff Record", type="primary"):
                            c.execute("""
                                UPDATE office_staff 
                                SET employee_id=?, name=?, position=?, monthly_rate=?, allowance=?, active_status=?, sss_default=?, phic_default=?, hdmf_default=?, wtax_default=?, ca_balance=?, biometric_id=?
                                WHERE id=?
                            """, (up_emp_id, up_emp_name, up_position, up_monthly_rate, up_allowance, up_status, up_sss, up_phic, up_hdmf, up_wtax, up_ca_bal, up_bio_id, selected_db_id))
                            conn.commit()
                            st.success(f"Updated record for {up_emp_name}!")
                            st.rerun()
                else:
                    st.info("No staff records available to edit.")

        st.markdown("---")
        staff_df = pd.read_sql_query("SELECT employee_id AS Emp_ID, name AS Name, biometric_id AS Bio_ID, position AS Position, monthly_rate AS Monthly_Rate, allowance AS Allowance, active_status AS Status, sss_default AS SSS, phic_default AS PHIC, hdmf_default AS PagIBIG, wtax_default AS WTax, ca_balance AS CA_Balance FROM office_staff", conn)
        st.dataframe(staff_df, width="stretch")

    # -----------------------------------------------------------------
    # SUB-TAB 2: STAFF DTR / ATTENDANCE SUMMARY
    # -----------------------------------------------------------------
    with sub_tab2:
        st.subheader("⏱️ Office Staff Daily Time Record (DTR)")
        
        tbl_check = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('dtr_biometric_logs', 'biometric_logs')").fetchone()
        
        if not tbl_check:
            st.error("No biometric logs table found in the database.")
            st.stop()
        
        table_name = tbl_check[0]

        cols = [col[1] for col in c.execute(f"PRAGMA table_info({table_name})").fetchall()]
        date_col = "log_date" if "log_date" in cols else ("date" if "date" in cols else cols[0])
        name_col = "emp_name" if "emp_name" in cols else ("worker_name" if "worker_name" in cols else cols[1])
        time_col = "time_in" if "time_in" in cols else cols[2]
        id_col = "emp_id" if "emp_id" in cols else "id"

        staff_members = c.execute("SELECT employee_id, name, biometric_id FROM office_staff WHERE active_status = 'Active'").fetchall()
        
        if not staff_members:
            st.warning("No active office staff found in Masterlist.")
        else:
            col_s1, col_s2, col_s3 = st.columns([2, 1.5, 1.5])
            
            selected_staff_str = col_s1.selectbox(
                "Select Employee", 
                [f"{s[0]} - {s[1]}" for s in staff_members],
                key="dtr_staff_select"
            )
            selected_emp_id = selected_staff_str.split(" - ")[0]
            selected_emp_name = selected_staff_str.split(" - ")[1]

            staff_info = next((s for s in staff_members if s[0] == selected_emp_id), None)
            stored_bio_id = staff_info[2] if staff_info and staff_info[2] else selected_emp_id

            start_date = col_s2.date_input("Cut-off Start Date", value=datetime(2026, 10, 1))
            end_date = col_s3.date_input("Cut-off End Date", value=datetime(2026, 10, 15))

            with st.expander("⚙️ Office Shift Schedule Rules & Late-Refill Policy", expanded=False):
                st.caption("Customize work shift expectations and late-offset policy:")
                sh_c1, sh_c2, sh_c3, sh_c4 = st.columns(4)
                
                time_in_all = sh_c1.time_input("Standard Time In (Mon-Sat)", value=datetime.strptime("08:00:00", "%H:%M:%S").time())
                out_mon_thu = sh_c2.time_input("Time Out (Mon - Thu)", value=datetime.strptime("18:00:00", "%H:%M:%S").time())
                out_fri = sh_c3.time_input("Time Out (Friday)", value=datetime.strptime("17:00:00", "%H:%M:%S").time())
                out_sat = sh_c4.time_input("Time Out (Saturday)", value=datetime.strptime("12:00:00", "%H:%M:%S").time())

                st.markdown("---")
                enable_late_offset = st.checkbox(
                    "🔄 **Enable Late-Refill Offset**: Extra minutes stayed in the afternoon auto-deduct/refill morning late minutes.",
                    value=True
                )

            bio_distinct = c.execute(f"SELECT DISTINCT {id_col}, {name_col} FROM {table_name} WHERE {name_col} IS NOT NULL AND {name_col} != '' ORDER BY {name_col} ASC").fetchall()
            bio_options = ["-- Auto Match --"] + [f"ID: {b[0]} | Name: {b[1]}" for b in bio_distinct]

            override_bio = st.selectbox("💡 Optional: Link Specific Biometric Log Profile", bio_options)

            if st.button("🔍 Generate DTR Report", type="primary"):
                raw_logs = []
                
                if override_bio != "-- Auto Match --":
                    selected_bio_id = override_bio.split(" | ")[0].replace("ID: ", "").strip()
                    selected_bio_name = override_bio.split(" | ")[1].replace("Name: ", "").strip()
                    
                    query = f"""
                        SELECT {date_col}, {time_col} 
                        FROM {table_name} 
                        WHERE ({id_col} = ? OR {name_col} = ?) 
                          AND {date_col} BETWEEN ? AND ?
                        ORDER BY {date_col} ASC, {time_col} ASC
                    """
                    raw_logs = c.execute(query, (selected_bio_id, selected_bio_name, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))).fetchall()
                else:
                    first_name_part = selected_emp_name.split(" ")[0]
                    last_name_part = selected_emp_name.split(" ")[-1]

                    query = f"""
                        SELECT {date_col}, {time_col} 
                        FROM {table_name} 
                        WHERE ({id_col} = ? OR {id_col} = ? OR {name_col} LIKE ? OR {name_col} LIKE ? OR REPLACE({name_col}, ' ', '') LIKE ?) 
                          AND {date_col} BETWEEN ? AND ?
                        ORDER BY {date_col} ASC, {time_col} ASC
                    """
                    raw_logs = c.execute(query, (
                        selected_emp_id, 
                        stored_bio_id, 
                        f"%{first_name_part}%", 
                        f"%{last_name_part}%", 
                        f"%{first_name_part}%",
                        start_date.strftime('%Y-%m-%d'), 
                        end_date.strftime('%Y-%m-%d')
                    )).fetchall()

                daily_punches = {}
                for row in raw_logs:
                    log_date, log_time = row[0], row[1]
                    if log_date not in daily_punches:
                        daily_punches[log_date] = []
                    daily_punches[log_date].append(str(log_time))

                dtr_rows = []
                total_tardy_mins = 0
                total_undertime_mins = 0
                total_absent_days = 0
                total_present_days = 0

                curr_dt = start_date
                while curr_dt <= end_date:
                    date_str = curr_dt.strftime('%Y-%m-%d')
                    day_name = curr_dt.strftime('%A')
                    weekday_num = curr_dt.weekday()
                    is_sunday = (weekday_num == 6)

                    shift_in = time_in_all
                    if weekday_num in [0, 1, 2, 3]:
                        shift_out = out_mon_thu
                    elif weekday_num == 4:
                        shift_out = out_fri
                    elif weekday_num == 5:
                        shift_out = out_sat
                    else:
                        shift_out = None

                    if date_str in daily_punches and daily_punches[date_str]:
                        punches = daily_punches[date_str]
                        first_in = min(punches)
                        last_out = max(punches) if len(punches) > 1 else "-"
                        
                        try:
                            in_dt = datetime.strptime(first_in.split('.')[0], "%H:%M:%S").time()
                        except:
                            in_dt = datetime.strptime(first_in, "%H:%M").time()

                        raw_tardy_mins = 0
                        if in_dt > shift_in:
                            raw_tardy_mins = int((datetime.combine(curr_dt, in_dt) - datetime.combine(curr_dt, shift_in)).total_seconds() / 60)

                        undertime_mins = 0
                        extra_afternoon_mins = 0
                        if last_out != "-" and shift_out is not None:
                            try:
                                out_dt = datetime.strptime(last_out.split('.')[0], "%H:%M:%S").time()
                            except:
                                out_dt = datetime.strptime(last_out, "%H:%M").time()

                            if out_dt < shift_out:
                                undertime_mins = int((datetime.combine(curr_dt, shift_out) - datetime.combine(curr_dt, out_dt)).total_seconds() / 60)
                                total_undertime_mins += undertime_mins
                            elif out_dt > shift_out:
                                extra_afternoon_mins = int((datetime.combine(curr_dt, out_dt) - datetime.combine(curr_dt, shift_out)).total_seconds() / 60)

                        final_tardy_mins = raw_tardy_mins
                        status_note = ""
                        
                        if enable_late_offset and raw_tardy_mins > 0 and extra_afternoon_mins > 0:
                            final_tardy_mins = max(0, raw_tardy_mins - extra_afternoon_mins)
                            offset_used = raw_tardy_mins - final_tardy_mins
                            if final_tardy_mins == 0:
                                status_note = " (Late Refilled)"
                            else:
                                status_note = f" ({offset_used}m Refilled)"

                        total_tardy_mins += final_tardy_mins
                        total_present_days += 1

                        status = "Late" if final_tardy_mins > 0 else "Present"
                        status += status_note

                        dtr_rows.append({
                            "Date": date_str,
                            "Day": day_name,
                            "Time In": first_in,
                            "Time Out": last_out,
                            "Tardy (Mins)": final_tardy_mins,
                            "Undertime (Mins)": undertime_mins,
                            "Status": status
                        })
                    else:
                        if is_sunday:
                            status = "Rest Day (Sunday)"
                        else:
                            status = "ABSENT"
                            total_absent_days += 1

                        dtr_rows.append({
                            "Date": date_str,
                            "Day": day_name,
                            "Time In": "-",
                            "Time Out": "-",
                            "Tardy (Mins)": 0,
                            "Undertime (Mins)": 0,
                            "Status": status
                        })

                    curr_dt += timedelta(days=1)

                st.markdown("---")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Days Present", f"{total_present_days} days")
                m2.metric("Total Tardy", f"{total_tardy_mins} mins")
                m3.metric("Total Undertime", f"{total_undertime_mins} mins")
                m4.metric("Absent Days", f"{total_absent_days} days", delta_color="inverse")

                df_dtr = pd.DataFrame(dtr_rows)
                st.dataframe(df_dtr, width="stretch")

    # -----------------------------------------------------------------
    # SUB-TAB 3: PROCESS PAYROLL (WITH 1-CLICK BIOMETRIC SYNC)
    # -----------------------------------------------------------------
    with sub_tab3:
        st.subheader("Process Semi-Monthly Payroll")
        
        col_p1, col_p2, col_p3 = st.columns([2, 1.5, 1.5])
        period_label = col_p1.text_input("Payroll Period Label", value="OCT 1-15, 2026")
        pay_start_date = col_p2.date_input("Cut-off Start Date", value=datetime(2026, 10, 1), key="pay_start")
        pay_end_date = col_p3.date_input("Cut-off End Date", value=datetime(2026, 10, 15), key="pay_end")
        
        active_staff = c.execute("SELECT employee_id, name, position, monthly_rate, allowance, sss_default, phic_default, hdmf_default, wtax_default, ca_balance, biometric_id FROM office_staff WHERE active_status = 'Active'").fetchall()
        
        if active_staff:
            selected_emp = st.selectbox("Select Staff Member to Compute", [f"{s[0]} - {s[1]} ({s[2]})" for s in active_staff])
            emp_index = [f"{s[0]} - {s[1]} ({s[2]})" for s in active_staff].index(selected_emp)
            curr_emp = active_staff[emp_index]
            
            basic_pay = curr_emp[3] / 2.0  # Monthly Rate / 2
            
            # Rate conversions for deduction estimation
            daily_rate = curr_emp[3] / 26.0
            hourly_rate = daily_rate / 8.0
            minute_rate = hourly_rate / 60.0

            st.info(f"💡 **Monthly Rate**: ₱{curr_emp[3]:,.2f} | **Basic Pay (Half Month)**: ₱{basic_pay:,.2f} | **Daily Rate**: ₱{daily_rate:,.2f} | **Minute Rate**: ₱{minute_rate:,.2f}")

            # Initialize session state for deduction amounts if not set
            sync_key = f"sync_{curr_emp[0]}"
            if sync_key not in st.session_state:
                st.session_state[sync_key] = {"tardy": 0.0, "undertime": 0.0, "absent": 0.0, "synced": False}

            # 1-CLICK BIOMETRIC SYNC BUTTON
            if st.button("⚡ Sync & Auto-Calculate Attendance Deductions from Biometrics", type="secondary"):
                # Fetch raw logs
                tbl_check = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('dtr_biometric_logs', 'biometric_logs')").fetchone()
                if tbl_check:
                    table_name = tbl_check[0]
                    cols = [col[1] for col in c.execute(f"PRAGMA table_info({table_name})").fetchall()]
                    date_col = "log_date" if "log_date" in cols else ("date" if "date" in cols else cols[0])
                    name_col = "emp_name" if "emp_name" in cols else ("worker_name" if "worker_name" in cols else cols[1])
                    time_col = "time_in" if "time_in" in cols else cols[2]
                    id_col = "emp_id" if "emp_id" in cols else "id"

                    first_name_part = curr_emp[1].split(" ")[0]
                    bio_id_target = curr_emp[10] if curr_emp[10] else curr_emp[0]

                    query = f"""
                        SELECT {date_col}, {time_col} 
                        FROM {table_name} 
                        WHERE ({id_col} = ? OR {id_col} = ? OR {name_col} LIKE ? OR REPLACE({name_col}, ' ', '') LIKE ?) 
                          AND {date_col} BETWEEN ? AND ?
                        ORDER BY {date_col} ASC, {time_col} ASC
                    """
                    raw_logs = c.execute(query, (
                        curr_emp[0], bio_id_target, f"%{first_name_part}%", f"%{first_name_part}%",
                        pay_start_date.strftime('%Y-%m-%d'), pay_end_date.strftime('%Y-%m-%d')
                    )).fetchall()

                    daily_punches = {}
                    for row in raw_logs:
                        l_date, l_time = row[0], str(row[1])
                        if l_date not in daily_punches:
                            daily_punches[l_date] = []
                        daily_punches[l_date].append(l_time)

                    calc_tardy_mins = 0
                    calc_undertime_mins = 0
                    calc_absent_days = 0

                    c_dt = pay_start_date
                    while c_dt <= pay_end_date:
                        d_str = c_dt.strftime('%Y-%m-%d')
                        w_num = c_dt.weekday()
                        
                        # Shifts
                        s_in = datetime.strptime("08:00:00", "%H:%M:%S").time()
                        s_out = datetime.strptime("18:00:00" if w_num in [0,1,2,3] else ("17:00:00" if w_num == 4 else "12:00:00"), "%H:%M:%S").time() if w_num != 6 else None

                        if d_str in daily_punches and daily_punches[d_str]:
                            p_list = daily_punches[d_str]
                            f_in = min(p_list)
                            l_out = max(p_list) if len(p_list) > 1 else "-"
                            
                            try:
                                in_t = datetime.strptime(f_in.split('.')[0], "%H:%M:%S").time()
                            except:
                                in_t = datetime.strptime(f_in, "%H:%M").time()

                            r_tardy = 0
                            if in_t > s_in:
                                r_tardy = int((datetime.combine(c_dt, in_t) - datetime.combine(c_dt, s_in)).total_seconds() / 60)

                            r_extra = 0
                            if l_out != "-" and s_out is not None:
                                try:
                                    out_t = datetime.strptime(l_out.split('.')[0], "%H:%M:%S").time()
                                except:
                                    out_t = datetime.strptime(l_out, "%H:%M").time()

                                if out_t < s_out:
                                    calc_undertime_mins += int((datetime.combine(c_dt, s_out) - datetime.combine(c_dt, out_t)).total_seconds() / 60)
                                elif out_t > s_out:
                                    r_extra = int((datetime.combine(c_dt, out_t) - datetime.combine(c_dt, s_out)).total_seconds() / 60)

                            # Refill logic
                            final_t = max(0, r_tardy - r_extra)
                            calc_tardy_mins += final_t
                        else:
                            if w_num != 6:  # Not Sunday
                                calc_absent_days += 1

                        c_dt += timedelta(days=1)

                    # Store calculated Peso equivalent values
                    st.session_state[sync_key] = {
                        "tardy": round(calc_tardy_mins * minute_rate, 2),
                        "undertime": round(calc_undertime_mins * minute_rate, 2),
                        "absent": round(calc_absent_days * daily_rate, 2),
                        "synced": True,
                        "tardy_mins": calc_tardy_mins,
                        "absent_days": calc_absent_days
                    }
                    st.success(f"Synced! Found {calc_tardy_mins} mins tardy and {calc_absent_days} days absent.")

            col_in1, col_in2 = st.columns(2)
            with col_in1:
                st.markdown("### ➕ Additional Earnings")
                allowance_val = st.number_input("Allowance", value=float(curr_emp[4]))
                ot_pay = st.number_input("Overtime Pay", value=0.0)
                sunday_work = st.number_input("Sunday Work", value=0.0)
                reg_holiday = st.number_input("Regular Holiday Pay", value=0.0)
                spec_holiday = st.number_input("Special Holiday Pay", value=0.0)
                paid_leave = st.number_input("Paid Leave", value=0.0)
                
                st.markdown("### ➖ Attendance Deductions (In ₱)")
                default_tardy = st.session_state[sync_key]["tardy"]
                default_undertime = st.session_state[sync_key]["undertime"]
                default_absent = st.session_state[sync_key]["absent"]

                tardy = st.number_input("Tardy Deduction (₱)", value=float(default_tardy), step=50.0)
                undertime = st.number_input("Undertime Deduction (₱)", value=float(default_undertime), step=50.0)
                absent = st.number_input("Absent Deduction (₱)", value=float(default_absent), step=100.0)
                
            with col_in2:
                st.markdown("### 📉 Statutory & C/A Deductions")
                sss_val = st.number_input("SSS Contribution", value=float(curr_emp[5]))
                phic_val = st.number_input("PHIC Contribution", value=float(curr_emp[6]))
                hdmf_val = st.number_input("HDMF Contribution", value=float(curr_emp[7]))
                wtax_val = st.number_input("Withholding Tax", value=float(curr_emp[8]))
                
                st.markdown("---")
                curr_ca_bal = float(curr_emp[9])
                st.caption(f"Current C/A Balance: **₱{curr_ca_bal:,.2f}**")
                ca_deduction = st.number_input("C/A Deduction for this Cut-off", value=min(500.0, curr_ca_bal), max_value=curr_ca_bal)
                remaining_ca = max(0.0, curr_ca_bal - ca_deduction)

            # Calculations
            gross_pay = (basic_pay + allowance_val + ot_pay + sunday_work + reg_holiday + spec_holiday + paid_leave) - (tardy + undertime + absent)
            total_ded = sss_val + phic_val + hdmf_val + wtax_val + ca_deduction
            net_pay = gross_pay - total_ded
            
            st.markdown("---")
            res_col1, res_col2, res_col3 = st.columns(3)
            res_col1.metric("Gross Pay", f"₱{gross_pay:,.2f}")
            res_col2.metric("Total Deductions", f"₱{total_ded:,.2f}")
            res_col3.metric("Net Pay", f"₱{net_pay:,.2f}")
            
            if st.button("💾 Save & Lock Payroll Record", type="primary"):
                c.execute("""
                    INSERT INTO office_payroll_records 
                    (period_label, employee_id, name, position, monthly_rate, basic_pay, allowance, ot_pay, sunday_work, reg_holiday_pay, spec_holiday_pay, paid_leave, tardy, undertime, absent, gross_pay, sss_deduction, phic_deduction, hdmf_deduction, wtax_deduction, ca_deduction, ca_remaining_balance, total_deductions, net_pay, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, DATETIME('now', 'localtime'))
                """, (period_label, curr_emp[0], curr_emp[1], curr_emp[2], curr_emp[3], basic_pay, allowance_val, ot_pay, sunday_work, reg_holiday, spec_holiday, paid_leave, tardy, undertime, absent, gross_pay, sss_val, phic_val, hdmf_val, wtax_val, ca_deduction, remaining_ca, total_ded, net_pay))
                
                c.execute("UPDATE office_staff SET ca_balance = ? WHERE employee_id = ?", (remaining_ca, curr_emp[0]))
                conn.commit()
                st.success(f"Payroll record saved for {curr_emp[1]}!")

    # -----------------------------------------------------------------
    # SUB-TAB 4: GENERATE PAYSLIPS
    # -----------------------------------------------------------------
    # -----------------------------------------------------------------
    # SUB-TAB 4: GENERATE PAYSLIPS (SINGLE & BATCH PRINTING)
    # -----------------------------------------------------------------
    with sub_tab4:
        st.subheader("Print / Download Official Payslips")
        
        mode = st.radio("Select Print Mode", ["📦 Batch PDF (All Employees in Cut-off)", "👤 Single Employee PDF"], horizontal=True)

        def map_rec_to_dict(rec_data):
            return {
                'period_label': rec_data[1],
                'employee_id': rec_data[2],
                'name': rec_data[3],
                'position': rec_data[4],
                'monthly_rate': rec_data[5],
                'basic_pay': rec_data[6],
                'allowance': rec_data[7],
                'ot_pay': rec_data[8],
                'sunday_work': rec_data[9],
                'reg_holiday_pay': rec_data[10],
                'spec_holiday_pay': rec_data[11],
                'paid_leave': rec_data[12],
                'tardy': rec_data[13],
                'undertime': rec_data[14],
                'absent': rec_data[15],
                'gross_pay': rec_data[16],
                'sss_deduction': rec_data[17],
                'phic_deduction': rec_data[18],
                'hdmf_deduction': rec_data[19],
                'wtax_deduction': rec_data[20],
                'ca_deduction': rec_data[21],
                'ca_remaining_balance': rec_data[22],
                'total_deductions': rec_data[23],
                'net_pay': rec_data[24]
            }

        if mode == "📦 Batch PDF (All Employees in Cut-off)":
            periods = c.execute("SELECT DISTINCT period_label FROM office_payroll_records ORDER BY id DESC").fetchall()
            
            if periods:
                period_options = [p[0] for p in periods]
                selected_period = st.selectbox("Select Cut-off Period Label", period_options)
                
                batch_recs = c.execute("SELECT * FROM office_payroll_records WHERE period_label = ? ORDER BY name ASC", (selected_period,)).fetchall()
                st.info(f"Found **{len(batch_recs)}** employee payroll records for **{selected_period}**.")

                if batch_recs:
                    # Map all records to list of dicts
                    batch_data_list = [map_rec_to_dict(r) for r in batch_recs]
                    batch_pdf_bytes = generate_batch_office_payslips_pdf(batch_data_list)
                    
                    st.download_button(
                        label=f"🖨️ Download Batch PDF ({len(batch_recs)} Pages / Personnel)",
                        data=batch_pdf_bytes,
                        file_name=f"Batch_Payslips_{selected_period.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
            else:
                st.info("No processed payroll records found. Process payroll first in Sub-Tab 3.")

        else:
            records = c.execute("SELECT id, period_label, name, net_pay FROM office_payroll_records ORDER BY id DESC").fetchall()
            
            if records:
                selected_rec = st.selectbox("Select Employee Record", [f"ID #{r[0]} | {r[1]} | {r[2]} (Net: ₱{r[3]:,.2f})" for r in records])
                rec_id = int(selected_rec.split(" | ")[0].replace("ID #", ""))
                
                rec_data = c.execute("SELECT * FROM office_payroll_records WHERE id = ?", (rec_id,)).fetchone()
                data_dict = map_rec_to_dict(rec_data)
                
                pdf_bytes = generate_office_payslip_pdf(data_dict)
                st.download_button(
                    label="📄 Download Printable Payslip (1 Page / 2-Up PDF)",
                    data=pdf_bytes,
                    file_name=f"Payslip_{rec_data[3].replace(' ', '_')}_{rec_data[1]}.pdf",
                    mime="application/pdf"
                )
            else:
                st.info("No processed payroll records found. Process payroll first in Sub-Tab 3.")
            
#=========================Helper for Dispatched============
def get_next_mif_number(cursor):
    """Finds the highest MIF-XXXX number in inventory_ledger and returns the next sequential reference."""
    try:
        records = cursor.execute("SELECT ref_no FROM inventory_ledger WHERE ref_no LIKE 'MIF-%'").fetchall()
        numbers = []
        for (ref,) in records:
            if ref and ref.startswith("MIF-"):
                num_part = ref.replace("MIF-", "").strip()
                if num_part.isdigit():
                    numbers.append(int(num_part))
        next_num = (max(numbers) + 1) if numbers else 1
        return f"MIF-{next_num:04d}"
    except Exception:
        return "MIF-0001"


#==========================Motorpool===========Standalone
import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# Check for ReportLab PDF availability
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    import io
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


# Helper function to generate sequential voucher numbers
def generate_voucher_number(cursor, column_name, prefix):
    today_prefix = f"{prefix}-{datetime.now().strftime('%Y%m')}"
    try:
        cursor.execute(f"SELECT {column_name} FROM deliveries WHERE {column_name} LIKE '{today_prefix}%' "
                       f"UNION SELECT voucher_no FROM journal_entries WHERE voucher_no LIKE '{today_prefix}%'")
        records = cursor.fetchall()
    except Exception:
        records = []

    if not records:
        return f"{today_prefix}-001"

    nums = []
    for r in records:
        if r[0]:
            try:
                nums.append(int(r[0].split('-')[-1]))
            except ValueError:
                pass

    next_num = max(nums) + 1 if nums else 1
    return f"{today_prefix}-{next_num:03d}"


def render_full_application(conn):
    c = conn.cursor()

    # ==========================================================================================
    # --- ALL DATABASE TABLES INITIALIZATION ---
    # ==========================================================================================
    c.execute("""
        CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apv_number TEXT,
            pono TEXT,
            dr_number TEXT,
            supplier TEXT,
            total_amount REAL DEFAULT 0.0,
            apv_date TEXT,
            project_name TEXT,
            payment_status TEXT DEFAULT 'Unpaid',
            cv_number TEXT,
            cv_date TEXT,
            payment_method TEXT,
            cheque_no TEXT,
            cheque_date TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pono TEXT,
            supplier TEXT,
            amount REAL DEFAULT 0.0,
            project_name TEXT,
            status TEXT DEFAULT 'Approved',
            payment_status TEXT DEFAULT 'Unpaid',
            cv_number TEXT,
            cv_date TEXT,
            payment_method TEXT,
            cheque_no TEXT,
            cheque_date TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_name TEXT UNIQUE,
            terms_days INTEGER DEFAULT 30,
            requires_advance_pdc TEXT DEFAULT 'No'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS chart_of_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_code TEXT UNIQUE,
            account_name TEXT,
            account_type TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_no TEXT UNIQUE NOT NULL,
            unit_name TEXT NOT NULL,
            unit_type TEXT,
            status TEXT DEFAULT 'Operational',
            assigned_project TEXT,
            starting_odometer REAL DEFAULT 0.0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS fuel_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL,
            plate_no TEXT NOT NULL,
            driver TEXT,
            liters REAL NOT NULL,
            price_per_liter REAL NOT NULL,
            total_cost REAL NOT NULL,
            odometer_reading REAL,
            project_name TEXT,
            remarks TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_date TEXT NOT NULL,
            plate_no TEXT NOT NULL,
            service_type TEXT NOT NULL,
            description TEXT,
            cost REAL NOT NULL,
            mechanic_vendor TEXT,
            odometer_reading REAL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS trip_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_date TEXT NOT NULL,
            plate_no TEXT NOT NULL,
            driver TEXT NOT NULL,
            destination TEXT NOT NULL,
            purpose TEXT,
            start_km REAL,
            end_km REAL,
            status TEXT DEFAULT 'Open'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT,
            voucher_no TEXT,
            account_code TEXT,
            account_name TEXT,
            debit REAL DEFAULT 0.0,
            credit REAL DEFAULT 0.0,
            ref_no TEXT,
            description TEXT,
            project_name TEXT
        )
    """)
    conn.commit()

    # ==========================================================================================
    # --- MAIN NAVIGATION TABS ---
    # ==========================================================================================
    tab_payment, tab_motorpool = st.tabs([
        "💳 Check / Payment Voucher",
        "🚜 Motorpool & Fleet Management"
    ])

    # ==========================================================================================
    # --- TAB 1: CHECK VOUCHER / PAYMENT ---
    # ==========================================================================================
    with tab_payment:
        # --- AUTOMATIC SETTLEMENT OF APVs WITH ADVANCE PDCs ---
        try:
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

                c.execute("""
                    UPDATE deliveries 
                    SET payment_status = 'Paid (Applied Advance)', cv_number = ?, cv_date = ? 
                    WHERE apv_number = ?
                """, (existing_cv, now_ts, apv_no))

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
        except Exception:
            pass

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
                width="stretch", hide_index=True
            )
        else:
            st.success("🎉 No outstanding vouchered payables waiting for payment!")

        st.markdown("---")
        st.write("#### 💸 Process Payment & Generate Voucher")

        pay_basis = st.radio(
            "Payment Mode:", 
            ["Standard Payment (APV Basis)", "Advance PDC / Downpayment (PO Basis)", "Petty Cash / Direct Expense Liquidation (Non-PO)"], 
            horizontal=True
        )

        selected_apv_no, selected_po_no, supplier_name, project_name = "", "", "", ""
        debit_acct_code, debit_acct_name, pcv_description = "", "", ""
        total_amt, is_selectable = 0.0, False

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
                debit_acct_code, debit_acct_name = "20100", "Accounts Payable-Trade"
                is_selectable = True
            else:
                st.info("No pending APVs available for payment.")

        elif pay_basis == "Advance PDC / Downpayment (PO Basis)":
            unpaid_pos = c.execute("""
                SELECT r.pono, r.supplier, SUM(r.amount) AS total_amount, r.project_name 
                FROM requests r
                LEFT JOIN suppliers s ON LOWER(TRIM(r.supplier)) = LOWER(TRIM(s.supplier_name))
                WHERE r.pono IS NOT NULL AND r.pono != '' 
                  AND LOWER(COALESCE(r.status, '')) LIKE '%approved%'
                  AND (r.payment_status IS NULL OR r.payment_status = '' OR LOWER(r.payment_status) = 'unpaid')
                GROUP BY r.pono, r.supplier, r.project_name
            """).fetchall()

            if unpaid_pos:
                po_options = [f"{r[0]} - {r[1]} (₱{float(r[2] or 0):,.2f})" for r in unpaid_pos]
                selected_po_str = st.selectbox("Select Approved PO Number for Advance PDC", po_options)
                selected_po_no = selected_po_str.split(" - ")[0]

                row = [r for r in unpaid_pos if r[0] == selected_po_no][0]
                supplier_name, total_amt, project_name = row[1], float(row[2] or 0), row[3]
                debit_acct_code, debit_acct_name = "10500", f"Advances to Suppliers - {supplier_name}"
                is_selectable = True
            else:
                st.info("No open Approved POs available for Advance PDC.")

        else:
            col_pc1, col_pc2, col_pc3 = st.columns(3)
            supplier_name = col_pc1.text_input("Payee / Claiming Employee", placeholder="e.g., Juan Dela Cruz")
            total_amt = col_pc2.number_input("Total Expense Amount (₱)", min_value=0.0, value=0.0, step=100.0)
            project_name = col_pc3.text_input("Charge to Project", value="General / Head Office")

            col_pc4, col_pc5 = st.columns(2)
            pcv_description = col_pc4.text_input("Particulars / Purpose", placeholder="e.g., Gas allowance for site inspection")

            try:
                exp_accs = c.execute("SELECT account_code, account_name FROM chart_of_accounts WHERE account_type = 'Expense'").fetchall()
            except Exception:
                exp_accs = []
            exp_options = [f"[{acc[0]}] {acc[1]}" for acc in exp_accs] if exp_accs else ["[60200] Direct Cost Materials"]

            selected_exp = col_pc5.selectbox("Accounting Expense Tag", exp_options)
            debit_acct_code = selected_exp.split("]")[0].replace("[", "")
            debit_acct_name = selected_exp.split("]")[1].strip()

            if supplier_name.strip() and total_amt > 0 and pcv_description.strip():
                is_selectable = True
            else:
                st.warning("⚠️ Please fill in Payee Name, Amount, and Particulars to process Petty Cash.")

        if is_selectable:
            col1, col2, col3 = st.columns(3)
            pay_method = col1.selectbox("Payment Method", ["Check", "Cash"])
            prefix = "PCV" if pay_basis.startswith("Petty") else ("CV" if pay_method == "Check" else "CAV")

            bank_accounts = [
                ("10100", "Petty Cash Fund / Cash on Hand"),
                ("10310", "Cash in Bank MBTC"),
                ("10320", "Cash in Bank CHINA"),
                ("10330", "Cash in Bank BDO")
            ]
            bank_choice = col2.selectbox("Funding Cash/Bank Account", [f"[{b[0]}] {b[1]}" for b in bank_accounts])
            selected_bank_code = bank_choice.split("]")[0].replace("[", "")
            selected_bank_name = bank_choice.split("]")[1].strip()

            suggested_cv = generate_voucher_number(c, "cv_number", prefix)
            cv_input = col3.text_input("Voucher Number Sequence", value=suggested_cv)

            col_d1, col_d2 = st.columns(2)
            cheque_no_input = col_d1.text_input("Cheque/OR Ref Number (Optional)", value="")
            cheque_date_input = col_d2.date_input("Disbursement Date", value=datetime.now().date())

            if st.button("✅ Process Payment & Issue Voucher", type="primary"):
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                try:
                    if pay_basis == "Standard Payment (APV Basis)":
                        ref_id = selected_apv_no
                        d_desc = f"Payment for APV {selected_apv_no} ({supplier_name})"
                        c_desc = f"Disbursement for APV {selected_apv_no}"
                        c.execute("UPDATE deliveries SET payment_status = 'Paid', cv_number = ?, cv_date = ? WHERE apv_number = ?", 
                                  (cv_input.strip(), now_str, selected_apv_no))

                    elif pay_basis == "Advance PDC / Downpayment (PO Basis)":
                        ref_id = selected_po_no
                        d_desc = f"Advance PDC for PO {selected_po_no} ({supplier_name})"
                        c_desc = f"PDC issued for PO {selected_po_no}"
                        c.execute("UPDATE requests SET payment_status = 'Paid', cv_number = ?, cv_date = ? WHERE pono = ?", 
                                  (cv_input.strip(), now_str, selected_po_no))

                    else:
                        ref_id = cv_input.strip()
                        d_desc = f"Petty Cash: {pcv_description} ({supplier_name})"
                        c_desc = f"Petty Cash payout to {supplier_name}"

                    c.execute("""
                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                        VALUES (?, ?, ?, ?, ?, 0.0, ?, ?, ?)
                    """, (now_str, cv_input.strip(), debit_acct_code, debit_acct_name, total_amt, ref_id, d_desc, project_name))

                    c.execute("""
                        INSERT INTO journal_entries (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name)
                        VALUES (?, ?, ?, ?, 0.0, ?, ?, ?, ?)
                    """, (now_str, cv_input.strip(), selected_bank_code, selected_bank_name, total_amt, ref_id, c_desc, project_name))

                    conn.commit()
                    st.success(f"🎉 Payment Voucher {cv_input.strip()} recorded successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ Error: {e}")

    # ==========================================================================================
    # --- TAB 2: MOTORPOOL & FLEET MANAGEMENT ---
    # ==========================================================================================
    with tab_motorpool:
        st.header("🚜 Motorpool & Fleet Management")

        mp_tab1, mp_tab2, mp_tab3, mp_tab4 = st.tabs([
            "📋 Fleet Registry", 
            "⛽ Fuel Consumption Log", 
            "🛠️ Repairs & Maintenance", 
            "🎟️ Trip Tickets & Dispatch"
        ])

        vehicles_db = c.execute("SELECT plate_no, unit_name, status FROM vehicles").fetchall()
        vehicle_options = [f"{v[0]} - {v[1]}" for v in vehicles_db] if vehicles_db else []

        # --- FLEET REGISTRY ---
        with mp_tab1:
            st.subheader("Vehicle & Heavy Equipment Inventory")
            with st.expander("➕ Register New Vehicle / Asset"):
                with st.form("add_v_form", clear_on_submit=True):
                    col_v1, col_v2, col_v3 = st.columns(3)
                    p_no = col_v1.text_input("Plate No. / Asset Tag *").strip()
                    u_name = col_v2.text_input("Unit Description *").strip()
                    u_type = col_v3.selectbox("Unit Category", ["Dump Truck", "Transit Mixer", "Pickup", "Backhoe / Excavator", "Generator", "Light Vehicle", "Other"])

                    col_v4, col_v5 = st.columns(2)
                    v_status = col_v4.selectbox("Initial Status", ["Operational", "Under Maintenance", "Standby / Idle", "Decommissioned"])
                    init_odo = col_v5.number_input("Starting Odometer / Hour Meter", min_value=0.0, value=0.0, step=10.0)

                    if st.form_submit_button("Save Unit to Fleet"):
                        if p_no and u_name:
                            try:
                                c.execute("INSERT INTO vehicles (plate_no, unit_name, unit_type, status, starting_odometer) VALUES (?, ?, ?, ?, ?)",
                                          (p_no.upper(), u_name, u_type, v_status, init_odo))
                                conn.commit()
                                st.success(f"✅ Vehicle {p_no.upper()} registered!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"⚠️ Error: {e}")
                        else:
                            st.error("⚠️ Plate No and Unit Description are required.")

            fleet_df = pd.read_sql_query("SELECT id, plate_no AS 'Plate/Tag', unit_name AS 'Unit', unit_type AS 'Type', status AS 'Status', starting_odometer AS 'Start Odo/Hrs' FROM vehicles", conn)
            if not fleet_df.empty:
                st.dataframe(fleet_df, width="stretch", hide_index=True)
            else:
                st.info("No vehicles registered.")

        # --- FUEL CONSUMPTION LOG ---
        with mp_tab2:
            st.subheader("Fuel Dispensing & Refueling Logs")
            if not vehicle_options:
                st.warning("⚠️ Register vehicles in Fleet Registry first.")
            else:
                with st.form("fuel_form", clear_on_submit=True):
                    col_f1, col_f2, col_f3 = st.columns(3)
                    sel_v = col_f1.selectbox("Select Vehicle", vehicle_options)
                    f_date = col_f2.date_input("Refueling Date", value=datetime.now().date())
                    driver = col_f3.text_input("Driver / Operator Name")

                    col_f4, col_f5, col_f6 = st.columns(3)
                    liters = col_f4.number_input("Liters Dispensed", min_value=0.01, value=10.0, step=1.0)
                    price = col_f5.number_input("Price / Liter (₱)", min_value=0.0, value=65.0, step=0.5)
                    odo = col_f6.number_input("Current Odometer / Hour Meter", min_value=0.0, value=0.0, step=10.0)

                    col_f7, col_f8 = st.columns(2)
                    proj = col_f7.text_input("Project Charged To")
                    rem = col_f8.text_input("Remarks / Receipt #")

                    if st.form_submit_button("Log Fuel Expense"):
                        plate = sel_v.split(" - ")[0]
                        tot = round(liters * price, 2)
                        c.execute("INSERT INTO fuel_logs (log_date, plate_no, driver, liters, price_per_liter, total_cost, odometer_reading, project_name, remarks) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                  (f_date.strftime('%Y-%m-%d'), plate, driver, liters, price, tot, odo, proj, rem))
                        conn.commit()
                        st.success(f"⛽ Refueling logged for {plate}!")
                        st.rerun()

            fuel_df = pd.read_sql_query("SELECT log_date AS 'Date', plate_no AS 'Plate/Tag', driver AS 'Driver', liters AS 'Liters', price_per_liter AS 'Price/L', total_cost AS 'Total Cost', odometer_reading AS 'Odometer', project_name AS 'Project', remarks AS 'Remarks' FROM fuel_logs ORDER BY log_date DESC", conn)
            if not fuel_df.empty:
                st.dataframe(fuel_df.style.format({"Total Cost": "₱{:,.2f}", "Price/L": "₱{:,.2f}"}), width="stretch", hide_index=True)
            else:
                st.info("No fuel records found.")

        # --- REPAIRS & MAINTENANCE ---
        with mp_tab3:
            st.subheader("Vehicle Service & Preventive Maintenance Records")
            if not vehicle_options:
                st.warning("⚠️ Register vehicles in Fleet Registry first.")
            else:
                with st.form("maint_form", clear_on_submit=True):
                    col_m1, col_m2, col_m3 = st.columns(3)
                    m_v = col_m1.selectbox("Select Vehicle", vehicle_options, key="m_v_s")
                    m_date = col_m2.date_input("Service Date", value=datetime.now().date())
                    m_type = col_m3.selectbox("Service Type", ["Preventive Maintenance (PMS)", "Engine Repair", "Tire Replacement", "Electrical", "Body Work / Painting", "Other"])

                    col_m4, col_m5, col_m6 = st.columns(3)
                    m_cost = col_m4.number_input("Repair / Parts Cost (₱)", min_value=0.0, value=0.0, step=100.0)
                    m_shop = col_m5.text_input("Mechanic / Service Shop")
                    m_odo = col_m6.number_input("Service Odometer / Hour Meter", min_value=0.0, value=0.0, step=10.0)
                    m_desc = st.text_area("Scope of Work / Parts Replaced")

                    if st.form_submit_button("Record Maintenance Entry"):
                        plate = m_v.split(" - ")[0]
                        c.execute("INSERT INTO maintenance_logs (service_date, plate_no, service_type, description, cost, mechanic_vendor, odometer_reading) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  (m_date.strftime('%Y-%m-%d'), plate, m_type, m_desc, m_cost, m_shop, m_odo))
                        conn.commit()
                        st.success(f"🛠️ Maintenance logged for {plate}!")
                        st.rerun()

            maint_df = pd.read_sql_query("SELECT service_date AS 'Date', plate_no AS 'Plate/Tag', service_type AS 'Type', description AS 'Work Description', cost AS 'Cost', mechanic_vendor AS 'Shop/Vendor', odometer_reading AS 'Odometer' FROM maintenance_logs ORDER BY service_date DESC", conn)
            if not maint_df.empty:
                st.dataframe(maint_df.style.format({"Cost": "₱{:,.2f}"}), width="stretch", hide_index=True)
            else:
                st.info("No maintenance history logged yet.")

        # --- TRIP TICKETS & DISPATCH ---
        # --- TRIP TICKETS & EQUIPMENT UTILIZATION LOG ---
        with mp_tab4:
            st.subheader("Vehicle Dispatch & Equipment Utilization Logs")
            
            # Fetch vehicle plate and type mapping
            vehicles_db = c.execute("SELECT plate_no, unit_name, unit_type FROM vehicles").fetchall()
            
            if not vehicles_db:
                st.warning("⚠️ Register vehicles in Fleet Registry first.")
            else:
                vehicle_dict = {f"{v[0]} - {v[1]}": (v[0], v[2] or "Light Vehicle") for v in vehicles_db}
                vehicle_options = list(vehicle_dict.keys())

                with st.expander("🎫 Issue New Dispatch / Equipment Time Ticket"):
                    # Selected vehicle selector outside form to allow live label updates
                    sel_v_key = st.selectbox("Select Unit / Equipment", vehicle_options, key="t_v_s")
                    selected_plate, unit_category = vehicle_dict[sel_v_key]

                    # Heavy equipment detection keywords
                    heavy_keywords = ["excavator", "backhoe", "generator", "bulldozer", "crane", "grader", "loader"]
                    is_heavy = any(k in unit_category.lower() for k in heavy_keywords)

                    # Dynamic form labels based on unit type
                    lbl_person = "Operator Name" if is_heavy else "Assigned Driver"
                    lbl_loc = "Project Site / Station" if is_heavy else "Destination"
                    lbl_purpose = "Work Activity / Scope" if is_heavy else "Trip Purpose / Load Details"
                    lbl_start = "Start Engine Hours (Hrs)" if is_heavy else "Departure Odometer (KM)"
                    lbl_end = "End Engine Hours (Hrs)" if is_heavy else "Arrival Odometer (KM)"

                    with st.form("trip_form", clear_on_submit=True):
                        col_t1, col_t2 = st.columns(2)
                        t_date = col_t1.date_input("Log / Trip Date", value=datetime.now().date())
                        t_driver = col_t2.text_input(lbl_person)

                        col_t4, col_t5 = st.columns(2)
                        t_dest = col_t4.text_input(lbl_loc, placeholder="e.g., Consolacion Site B" if is_heavy else "e.g., Cansojong to Consolacion")
                        t_purpose = col_t5.text_input(lbl_purpose, placeholder="e.g., Trenching & Site Clearing" if is_heavy else "e.g., Deliver Materials")

                        col_t6, col_t7 = st.columns(2)
                        t_s_km = col_t6.number_input(lbl_start, min_value=0.0, value=0.0, step=1.0)
                        t_e_km = col_t7.number_input(lbl_end, min_value=0.0, value=0.0, step=1.0)

                        if st.form_submit_button("Issue Log Ticket"):
                            c.execute("""
                                INSERT INTO trip_tickets (ticket_date, plate_no, driver, destination, purpose, start_km, end_km, status)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                t_date.strftime('%Y-%m-%d'),
                                selected_plate,
                                t_driver,
                                t_dest,
                                t_purpose,
                                t_s_km,
                                t_e_km if t_e_km > 0 else None,
                                'Completed' if t_e_km > 0 else 'Open'
                            ))
                            conn.commit()
                            st.success(f"✅ Log ticket recorded for {selected_plate}!")
                            st.rerun()

            # Display merged logs table with calculated total utilization
            trips_df = pd.read_sql_query("""
                SELECT 
                    t.id AS 'Ticket #',
                    t.ticket_date AS 'Date',
                    t.plate_no AS 'Plate/Tag',
                    v.unit_type AS 'Type',
                    t.driver AS 'Driver/Operator',
                    t.destination AS 'Site/Destination',
                    t.purpose AS 'Activity/Purpose',
                    t.start_km AS 'Start (KM/Hrs)',
                    t.end_km AS 'End (KM/Hrs)',
                    CASE 
                        WHEN t.end_km IS NOT NULL AND t.end_km >= t.start_km 
                        THEN ROUND(t.end_km - t.start_km, 2)
                        ELSE 0.0 
                    END AS 'Total Run (KM/Hrs)',
                    t.status AS 'Status'
                FROM trip_tickets t
                LEFT JOIN vehicles v ON t.plate_no = v.plate_no
                ORDER BY t.id DESC
            """, conn)

            if not trips_df.empty:
                st.dataframe(trips_df, width="stretch", hide_index=True)
            else:
                st.info("No utilization logs or trip tickets created yet.")


# Standalone runner
#if __name__ == "__main__":
#    st.set_page_config(page_title="Tuanson Construction - Procurement & Motorpool", layout="wide")
#    st.title("🏗️ Tuanson Construction - Procurement & Inventory")
#    db_conn = sqlite3.connect("enterprise_erp.db", check_same_thread=False)
#    render_full_application(db_conn)


#==================================MOTORPOOL============
import streamlit as st
import pandas as pd
from datetime import datetime

def render_motorpool_module(conn):
    c = conn.cursor()

    # --- 1. DATABASE TABLE INITIALIZATION ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_no TEXT UNIQUE NOT NULL,
            unit_name TEXT NOT NULL,
            unit_type TEXT,
            status TEXT DEFAULT 'Operational',
            assigned_project TEXT,
            starting_odometer REAL DEFAULT 0.0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS fuel_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL,
            plate_no TEXT NOT NULL,
            driver TEXT,
            liters REAL NOT NULL,
            price_per_liter REAL NOT NULL,
            total_cost REAL NOT NULL,
            odometer_reading REAL,
            project_name TEXT,
            remarks TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_date TEXT NOT NULL,
            plate_no TEXT NOT NULL,
            service_type TEXT NOT NULL,
            description TEXT,
            cost REAL NOT NULL,
            mechanic_vendor TEXT,
            odometer_reading REAL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS trip_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_date TEXT NOT NULL,
            plate_no TEXT NOT NULL,
            driver TEXT NOT NULL,
            destination TEXT NOT NULL,
            purpose TEXT,
            start_km REAL,
            end_km REAL,
            status TEXT DEFAULT 'Open'
        )
    """)
    conn.commit()

    # --- 2. HEADER & TABS ---
    st.header("🚜 Motorpool & Fleet Management")

    mp_tab1, mp_tab2, mp_tab3, mp_tab4 = st.tabs([
        "📋 Fleet Registry", 
        "⛽ Fuel Consumption Log", 
        "🛠️ Repairs & Maintenance", 
        "🎟️ Trip Tickets & Dispatch"
    ])

    # Dynamic Helper Data
    vehicles_db = c.execute("SELECT plate_no, unit_name, status FROM vehicles").fetchall()
    vehicle_options = [f"{v[0]} - {v[1]}" for v in vehicles_db] if vehicles_db else []

    # ==========================================================================================
    # --- TAB 1: FLEET REGISTRY ---
    # ==========================================================================================
    with mp_tab1:
        st.subheader("Vehicle & Heavy Equipment Inventory")

        with st.expander("➕ Register New Vehicle / Asset"):
            with st.form("add_vehicle_form", clear_on_submit=True):
                col_v1, col_v2, col_v3 = st.columns(3)
                p_no = col_v1.text_input("Plate No. / Asset Tag *", placeholder="e.g., ABC-1234 or DUMP-01").strip()
                u_name = col_v2.text_input("Unit Description *", placeholder="e.g., Isuzu Forward Dump Truck").strip()
                u_type = col_v3.selectbox("Unit Category", ["Dump Truck", "Transit Mixer", "Pickup", "Backhoe / Excavator", "Generator", "Light Vehicle", "Other"])

                col_v4, col_v5 = st.columns(2)
                v_status = col_v4.selectbox("Initial Status", ["Operational", "Under Maintenance", "Standby / Idle", "Decommissioned"])
                init_odo = col_v5.number_input("Starting Odometer / Hour Meter", min_value=0.0, value=0.0, step=10.0)

                btn_add_v = st.form_submit_button("Save Unit to Fleet")

                if btn_add_v:
                    if not p_no or not u_name:
                        st.error("⚠️ Plate Number and Unit Description are required.")
                    else:
                        try:
                            c.execute("""
                                INSERT INTO vehicles (plate_no, unit_name, unit_type, status, starting_odometer)
                                VALUES (?, ?, ?, ?, ?)
                            """, (p_no.upper(), u_name, u_type, v_status, init_odo))
                            conn.commit()
                            st.success(f"✅ Vehicle {p_no.upper()} added to fleet!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Error adding vehicle: {e}")

        fleet_df = pd.read_sql_query("SELECT id, plate_no AS 'Plate/Tag', unit_name AS 'Unit', unit_type AS 'Type', status AS 'Status', starting_odometer AS 'Start Odo/Hrs' FROM vehicles", conn)
        
        if not fleet_df.empty:
            st.dataframe(fleet_df, width="stretch", hide_index=True)
        else:
            st.info("No vehicles currently registered in the motorpool.")

    # ==========================================================================================
    # --- TAB 2: FUEL CONSUMPTION LOG ---
    # ==========================================================================================
    with mp_tab2:
        st.subheader("Fuel Dispensing & Refueling Logs")

        if not vehicle_options:
            st.warning("⚠️️ Please register vehicles in the Fleet Registry tab before logging fuel.")
        else:
            with st.form("log_fuel_form", clear_on_submit=True):
                col_f1, col_f2, col_f3 = st.columns(3)
                selected_v = col_f1.selectbox("Select Vehicle", vehicle_options)
                fuel_date = col_f2.date_input("Refueling Date", value=datetime.now().date())
                driver_name = col_f3.text_input("Driver / Operator Name")

                col_f4, col_f5, col_f6 = st.columns(3)
                liters_val = col_f4.number_input("Liters Dispensed", min_value=0.01, value=10.0, step=1.0)
                price_val = col_f5.number_input("Price / Liter (₱)", min_value=0.0, value=65.0, step=0.5)
                odo_val = col_f6.number_input("Current Odometer / Hour Meter", min_value=0.0, value=0.0, step=10.0)

                col_f7, col_f8 = st.columns(2)
                proj_charge = col_f7.text_input("Project Charged To", placeholder="e.g., Site A - Road Project")
                fuel_remarks = col_f8.text_input("Remarks / Refueling Receipt #")

                btn_log_fuel = st.form_submit_button("Log Fuel Expense")

                if btn_log_fuel:
                    target_plate = selected_v.split(" - ")[0]
                    calc_total = round(liters_val * price_val, 2)

                    try:
                        c.execute("""
                            INSERT INTO fuel_logs (log_date, plate_no, driver, liters, price_per_liter, total_cost, odometer_reading, project_name, remarks)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (fuel_date.strftime('%Y-%m-%d'), target_plate, driver_name, liters_val, price_val, calc_total, odo_val, proj_charge, fuel_remarks))
                        conn.commit()
                        st.success(f"⛽ Logged {liters_val}L (₱{calc_total:,.2f}) for {target_plate}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Error logging fuel: {e}")

        st.markdown("---")
        fuel_df = pd.read_sql_query("""
            SELECT log_date AS 'Date', plate_no AS 'Plate/Tag', driver AS 'Driver', 
                   liters AS 'Liters', price_per_liter AS 'Price/L', total_cost AS 'Total Cost', 
                   odometer_reading AS 'Odometer', project_name AS 'Project', remarks AS 'Remarks'
            FROM fuel_logs ORDER BY log_date DESC
        """, conn)

        if not fuel_df.empty:
            st.dataframe(fuel_df.style.format({"Total Cost": "₱{:,.2f}", "Price/L": "₱{:,.2f}", "Liters": "{:,.2f}"}), width="stretch", hide_index=True)
        else:
            st.info("No fuel records found.")

    # ==========================================================================================
    # --- TAB 3: REPAIRS & MAINTENANCE ---
    # ==========================================================================================
    with mp_tab3:
        st.subheader("Vehicle Service & Preventive Maintenance Records")

        if not vehicle_options:
            st.warning("⚠️ Register vehicles first in the Fleet Registry tab.")
        else:
            with st.form("log_maint_form", clear_on_submit=True):
                col_m1, col_m2, col_m3 = st.columns(3)
                m_v = col_m1.selectbox("Select Vehicle", vehicle_options, key="maint_v_select")
                m_date = col_m2.date_input("Service Date", value=datetime.now().date())
                m_type = col_m3.selectbox("Service Type", ["Preventive Maintenance (PMS)", "Engine Repair", "Tire Replacement", "Electrical", "Body Work / Painting", "Other"])

                col_m4, col_m5, col_m6 = st.columns(3)
                m_cost = col_m4.number_input("Repair / Parts Cost (₱)", min_value=0.0, value=0.0, step=100.0)
                m_vendor = col_m5.text_input("Mechanic / Service Shop Vendor")
                m_odo = col_m6.number_input("Service Odometer / Hour Meter", min_value=0.0, value=0.0, step=10.0)

                m_desc = st.text_area("Scope of Work / Parts Replaced", placeholder="e.g., Changed engine oil, replaced oil filter, adjusted brakes.")

                btn_log_maint = st.form_submit_button("Record Maintenance Entry")

                if btn_log_maint:
                    target_plate = m_v.split(" - ")[0]
                    try:
                        c.execute("""
                            INSERT INTO maintenance_logs (service_date, plate_no, service_type, description, cost, mechanic_vendor, odometer_reading)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (m_date.strftime('%Y-%m-%d'), target_plate, m_type, m_desc, m_cost, m_vendor, m_odo))
                        conn.commit()
                        st.success(f"🛠️ Maintenance record for {target_plate} saved!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Error logging maintenance: {e}")

        st.markdown("---")
        maint_df = pd.read_sql_query("""
            SELECT service_date AS 'Date', plate_no AS 'Plate/Tag', service_type AS 'Type', 
                   description AS 'Work Description', cost AS 'Cost', mechanic_vendor AS 'Shop/Vendor',
                   odometer_reading AS 'Odometer'
            FROM maintenance_logs ORDER BY service_date DESC
        """, conn)

        if not maint_df.empty:
            st.dataframe(maint_df.style.format({"Cost": "₱{:,.2f}"}), width="stretch", hide_index=True)
        else:
            st.info("No maintenance history logged yet.")

    # ==========================================================================================
    # --- TAB 4: TRIP TICKETS & DISPATCH ---
    # ==========================================================================================
    with mp_tab4:
        st.subheader("Vehicle Dispatch & Trip Tickets")

        if not vehicle_options:
            st.warning("⚠️ Register vehicles first in the Fleet Registry tab.")
        else:
            with st.expander("🎫 Issue New Trip Ticket"):
                with st.form("issue_trip_form", clear_on_submit=True):
                    col_t1, col_t2, col_t3 = st.columns(3)
                    t_v = col_t1.selectbox("Select Vehicle", vehicle_options, key="trip_v_select")
                    t_date = col_t2.date_input("Trip Date", value=datetime.now().date())
                    t_driver = col_t3.text_input("Assigned Driver")

                    col_t4, col_t5 = st.columns(2)
                    t_dest = col_t4.text_input("Destination")
                    t_purpose = col_t5.text_input("Trip Purpose / Load Details")

                    col_t6, col_t7 = st.columns(2)
                    t_start_km = col_t6.number_input("Departure Odometer (KM)", min_value=0.0, value=0.0, step=1.0)
                    t_end_km = col_t7.number_input("Arrival Odometer (KM) - Optional", min_value=0.0, value=0.0, step=1.0)

                    btn_issue_ticket = st.form_submit_button("Issue Dispatch Ticket")

                    if btn_issue_ticket:
                        target_plate = t_v.split(" - ")[0]
                        try:
                            c.execute("""
                                INSERT INTO trip_tickets (ticket_date, plate_no, driver, destination, purpose, start_km, end_km, status)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                t_date.strftime('%Y-%m-%d'), target_plate, t_driver, t_dest, t_purpose, 
                                t_start_km, t_end_km if t_end_km > 0 else None,
                                'Completed' if t_end_km > 0 else 'Open'
                            ))
                            conn.commit()
                            st.success(f"🎫 Trip ticket issued for {target_plate}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Error creating trip ticket: {e}")

        st.markdown("---")
        trips_df = pd.read_sql_query("""
            SELECT id AS 'Ticket #', ticket_date AS 'Date', plate_no AS 'Plate/Tag', 
                   driver AS 'Driver', destination AS 'Destination', purpose AS 'Purpose',
                   start_km AS 'Start KM', end_km AS 'End KM', status AS 'Status'
            FROM trip_tickets ORDER BY id DESC
        """, conn)

        if not trips_df.empty:
            st.dataframe(trips_df, width="stretch", hide_index=True)
        else:
            st.info("No trip tickets created yet.")

# Main Execution standard check
#if __name__ == "__main__":
#    import sqlite3
#    conn = sqlite3.connect("enterprise_erp.db", check_same_thread=False)
#    render_motorpool_module(conn)

#==================================end Motorpool=======

# ====================================================
# --- AUTOMATIC DATABASE SCHEMA MIGRATION ---
# ====================================================
def init_motorpool_db(conn):
    c = conn.cursor()
    
    # 1. Create Equipment Master Table if missing
    c.execute("""
        CREATE TABLE IF NOT EXISTS equipment (
            equipment_id TEXT PRIMARY KEY,
            equipment_name TEXT NOT NULL,
            category TEXT,
            current_engine_hours REAL DEFAULT 0,
            current_odometer_km REAL DEFAULT 0,
            status TEXT DEFAULT 'Active',
            project_name TEXT
        )
    """)
    
    # 2. Inspect existing columns in the 'requests' table
    c.execute("PRAGMA table_info(requests)")
    existing_columns = [row[1] for row in c.fetchall()]  # row[1] holds column names
    
    # 3. List of required Motorpool columns and their SQL types
    required_columns = {
        "equipment_id": "TEXT",
        "engine_hours": "REAL",
        "part_number": "TEXT",
        "is_retroactive": "INTEGER DEFAULT 0",
        "motorpool_approver": "TEXT DEFAULT ''"
    }
    
    # 4. Filter and execute ALTER TABLE only for columns that do NOT exist yet
    for col_name, col_type in required_columns.items():
        if col_name not in existing_columns:
            try:
                c.execute(f"ALTER TABLE requests ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                # Catch any unexpected schema error safely
                pass
                
    conn.commit()

# --- CALL THIS DIRECTLY AFTER CONNECTING TO YOUR LOCAL / TURSO DATABASE ---
# init_motorpool_db(conn)

#===========================================================
def sync_table_columns(conn):
    """Ensures existing tables have all required columns by auto-adding missing ones."""
    
    # 1. Check existing columns in the 'users' table
    cursor = conn.execute("PRAGMA table_info(users)")
    existing_user_cols = [row[1] for row in cursor.fetchall()]
    
    # Required columns for 'users' and their data types
    required_user_cols = {
        "email": "TEXT",
        "password": "TEXT",
        "role1": "TEXT",
        "role2": "TEXT",
        "role3": "TEXT",
        "role4": "TEXT",
        "role5": "TEXT",
        "role6": "TEXT",
        "status": "TEXT DEFAULT 'Active'",
        "can_add_act": "INTEGER DEFAULT 0",
        "can_add_item": "INTEGER DEFAULT 0"
    }
    
    # Auto-add any missing column
    for col_name, col_type in required_user_cols.items():
        if col_name not in existing_user_cols:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};")
            
    conn.commit()

#==========================================log out automatic
import streamlit as st
import streamlit.components.v1 as components

def setup_auto_logout(timeout_minutes=5):
    """
    Injects a JavaScript idle timer into Streamlit.
    Resets on mouse move, key press, click, or scroll.
    Triggers auto-logout query parameter when timer expires.
    """
    # 1. Check if auto_logout signal was sent via URL query params
    if st.query_params.get("auto_logout") == "true":
        st.query_params.clear()
        st.session_state.clear()  # Clears user session / logged-in state
        st.warning("⚠️ You were automatically logged out due to 5 minutes of inactivity.")
        st.rerun()

    # 2. Inject JavaScript listener if user is logged in
    timeout_ms = timeout_minutes * 60 * 1000  # Convert minutes to milliseconds
    
    js_code = f"""
    
    """
    components.html(js_code, height=0, width=0)
    #==========================================log out automatic
#=============================Fetch Email add
def get_user_email_by_role(role_name, conn):
    """Fetch the email address of the user assigned to a specific role."""
    try:
        c = conn.cursor()
        row = c.execute("SELECT email FROM users WHERE role = ? AND email IS NOT NULL LIMIT 1", (role_name,)).fetchone()
        if row and row[0]:
            return row[0]
    except Exception as e:
        st.error(f"Error fetching email for role {role_name}: {e}")
    return None
#=======================send email===============================
import smtplib
from email.mime.text import MIMEText

# --- EMAIL NOTIFICATION HELPER ---
def send_notification(to_email, subject, body):
    if "email" not in st.secrets:
        st.error("Email configuration missing! Please add [email] section to Streamlit secrets.")
        return False

    email_cfg = st.secrets["email"]
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = email_cfg["sender_email"]
    msg["To"] = to_email

    try:
        with smtplib.SMTP(email_cfg["smtp_server"], int(email_cfg["port"])) as server:
            server.starttls()
            server.login(email_cfg["sender_email"], email_cfg["sender_password"])
            server.sendmail(email_cfg["sender_email"], to_email, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False
#=======================end send email===============================

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
    
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import Paragraph
    
    styles = getSampleStyleSheet()
    hdr_style = ParagraphStyle(
        'HdrStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=8,
        alignment=1 # Center aligned
    )
    
    # Build table header cells using Paragraphs
    table_data = [
        [
            Paragraph("Income Payments Subject to Expanded Withholding Tax", hdr_style),
            Paragraph("ATC", hdr_style),
            Paragraph("1st Month", hdr_style),
            Paragraph("2nd Month", hdr_style),
            Paragraph("3rd Month", hdr_style),
            Paragraph("Total", hdr_style),
            Paragraph("Tax Withheld", hdr_style)
        ],
        # Row Data
        [
            income_type,
            atc_code,
            "-",
            f"{new_voucher_amt:,.2f}",
            "-",
            f"{new_voucher_amt:,.2f}",
            f"{computed_tax_withheld:,.2f}"
        ]
    ]

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
            width="stretch",
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
                st.dataframe(df_history, width="stretch", hide_index=True)
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


_old_code = '''
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


'''
# --- DATABASE SETUP (Turso / SQLite Integrated) ---
import os
import sqlite3
import streamlit as st

@st.cache_resource
def get_db_connection():
    """
    Dynamically connects to Turso if configured in Streamlit Secrets/Env,
    otherwise falls back automatically to local inventory.db.
    """
    db_url = None
    auth_token = ""

    # 1. Attempt to fetch credentials from Streamlit Secrets or Environment Variables
    try:
        if "TURSO_DATABASE_URL" in st.secrets:
            db_url = st.secrets["TURSO_DATABASE_URL"]
            auth_token = st.secrets.get("TURSO_AUTH_TOKEN", "")
        else:
            db_url = os.getenv("TURSO_DATABASE_URL")
            auth_token = os.getenv("TURSO_AUTH_TOKEN", "")
    except Exception:
        db_url = os.getenv("TURSO_DATABASE_URL")
        auth_token = os.getenv("TURSO_AUTH_TOKEN", "")

    # 2. If valid Turso remote URL exists, connect via libsql
    if db_url and (str(db_url).startswith("libsql://") or str(db_url).startswith("https://") or str(db_url).startswith("wss://")):
        try:
            import libsql_experimental as turso_sqlite
            return turso_sqlite.connect(db_url, auth_token=auth_token)
        except ImportError:
            st.error("Please install `libsql-experimental` to connect to Turso. Run: pip install libsql-experimental")
            st.stop()
        except Exception as e:
            st.error(f"Failed to connect to Turso database: {e}")
            st.stop()

    # 3. Fallback to Local SQLite database (Plug-and-play for local drive E:\Tuanson_App_01)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    local_db_path = os.path.join(BASE_DIR, "inventory.db")

    conn = sqlite3.connect(local_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn
        
#======================================================================================
#                                    DATABASE                                         =
#======================================================================================
# ======================================================================================
#                                    DATABASE
# ======================================================================================
def init_banks_database(conn):
  """Initialize Banks & Lending Institutions Master Table."""
  c = conn.cursor()
  c.execute("""
        CREATE TABLE IF NOT EXISTS banks_master (
            bank_id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution_name TEXT NOT NULL,
            branch TEXT,
            account_type TEXT,
            default_account_no TEXT,
            contact_person TEXT,
            contact_number TEXT,
            notes TEXT
        )
    """)

  c.execute("""
        CREATE TABLE IF NOT EXISTS loans_master (
            loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_id INTEGER,
            bank_name TEXT NOT NULL,
            branch TEXT,
            account_number TEXT NOT NULL,
            promissory_note_no TEXT NOT NULL,
            borrower_name TEXT NOT NULL,
            principal_amount REAL NOT NULL,
            date_granted TEXT NOT NULL,
            maturity_date TEXT NOT NULL,
            loan_term_months INTEGER NOT NULL,
            loan_product TEXT,
            interest_rate REAL NOT NULL,
            loan_status TEXT DEFAULT 'Current',
            FOREIGN KEY(bank_id) REFERENCES banks_master(bank_id)
        )
    """)

  c.execute("""
        CREATE TABLE IF NOT EXISTS loan_amortization_schedule (
            installment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id INTEGER,
            installment_no INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            principal_balance REAL NOT NULL,
            principal_due REAL DEFAULT 0,
            interest_due REAL NOT NULL,
            total_amount_due REAL NOT NULL,
            status TEXT DEFAULT 'unpaid',
            check_no TEXT,
            voucher_no TEXT,
            payee TEXT,
            reference TEXT,
            FOREIGN KEY (loan_id) REFERENCES loans_master (loan_id)
        )
    """)
  conn.commit()


def init_db():
  conn = get_db_connection()
  c = conn.cursor()

  # --- Safe Migration for Advance PDC Column in Suppliers Table ---
  try:
    c.execute(
        "ALTER TABLE suppliers ADD COLUMN requires_advance_pdc TEXT DEFAULT"
        " 'No'"
    )
    conn.commit()
  except Exception:
    # Column already exists
    pass

  try:
    c.execute("PRAGMA journal_mode = WAL;")
    c.execute("PRAGMA synchronous = NORMAL;")
    c.execute("PRAGMA busy_timeout = 5000;")
  except Exception:
    pass  # Turso/libsql may safely ignore some PRAGMA statements

  # 1. Projects Master Table
  c.execute("""CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT UNIQUE
              )""")

  # 2. Activities Master Table
  c.execute("""CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                activity_name TEXT,
                qty REAL DEFAULT 1.0,
                unit TEXT DEFAULT 'lot',
                contract_amount REAL DEFAULT 0.0,
                FOREIGN KEY(project_id) REFERENCES projects(id))""")

  # 3. Materials Master Table
  c.execute("""CREATE TABLE IF NOT EXISTS materials (
                item_no TEXT PRIMARY KEY,
                description TEXT,
                unit TEXT,
                category TEXT DEFAULT 'Direct Materials')""")

  # 4. Suppliers Master Table
  c.execute("""CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_name TEXT UNIQUE,
                location TEXT,
                contact_person TEXT,
                contact_number TEXT,
                tin_number TEXT,
                vat_type TEXT,
                terms_days INTEGER DEFAULT 0)""")

  # 5. Transaction Requests Table
  c.execute("""CREATE TABLE IF NOT EXISTS requests (
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
                requester_name TEXT)""")

  # 6. Deliveries / Receiving Master Table
  c.execute("""CREATE TABLE IF NOT EXISTS deliveries (
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
                payment_method TEXT)""")

  # 7. Signatories Master Table
  c.execute("""
        CREATE TABLE IF NOT EXISTS signatories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            role TEXT,
            signature_path TEXT
        )
    """)

  # 8. Users Master Table
  c.execute("""
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
    """)

  # 9. General Ledger / Journal Entries Table
  c.execute("""
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
    """)

  # 10. Chart of Accounts Table
  c.execute("""
        CREATE TABLE IF NOT EXISTS chart_of_accounts (
            account_code TEXT PRIMARY KEY,
            account_name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            status TEXT DEFAULT 'Active'
        )
    """)

  # 11. Inventory Ledger Table
  c.execute("""
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
    """)

  # --- HRIS / PAYROLL TABLES INITIALIZATION ---
  c.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_name TEXT UNIQUE NOT NULL,
            worker_type TEXT,
            daily_rate REAL NOT NULL,
            sss_no TEXT,
            philhealth_no TEXT,
            pagibig_no TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)

  c.execute("""
        CREATE TABLE IF NOT EXISTS timekeeping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER,
            project_name TEXT,
            activity_name TEXT,
            work_date TEXT,
            days_worked REAL DEFAULT 1.0,
            ot_hours REAL DEFAULT 0.0,
            vale_amount REAL DEFAULT 0.0,
            FOREIGN KEY(worker_id) REFERENCES workers(id)
        )
    """)

  c.execute("""
        CREATE TABLE IF NOT EXISTS payroll_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_period TEXT,
            total_gross REAL,
            total_deductions REAL,
            total_net REAL,
            status TEXT DEFAULT 'Pending Approval'
        )
    """)
  # ========================end of HRIS===================

  # --- AUTO-MIGRATIONS FOR EXISTING DATABASES ---
  for col in [
      "location",
      "contact_person",
      "contact_number",
      "tin_number",
      "vat_type",
  ]:
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
      ("journal_entries", "supplier", "TEXT"),
  ]:
    try:
      c.execute(
          f"ALTER TABLE {col_sql[0]} ADD COLUMN {col_sql[1]} {col_sql[2]}"
      )
    except Exception:
      pass

  # --- SEED INITIAL DATA ---
  c.execute("SELECT COUNT(*) FROM projects")
  if c.fetchone()[0] == 0:
    c.executemany(
        "INSERT INTO projects (project_name) VALUES (?)",
        [("Punta",), ("Suba",), ("Basak",), ("Dumanjug",), ("MOTORPOOL",)],
    )

    c.executemany(
        "INSERT INTO activities (project_id, activity_name, qty, unit,"
        " contract_amount) VALUES (?, ?, ?, ?, ?)",
        [
            (1, "painting", 1.0, "lot", 0.0),
            (2, "FORM WORKS", 1.0, "lot", 0.0),
            (3, "LINTEL BEAM", 1.0, "lot", 0.0),
            (3, "CHB LAYING", 1.0, "lot", 0.0),
            (3, "COLUMN CORRECTION", 1.0, "lot", 0.0),
            (4, "PCCP", 1.0, "lot", 0.0),
            (5, "RENEWAL REGISTRATION", 1.0, "lot", 0.0),
        ],
    )

    c.executemany(
        "INSERT INTO materials (item_no, description, unit, category) VALUES"
        " (?, ?, ?, ?)",
        [
            ("00001", "PORTLAND CEMENT", "BAGS", "Direct Materials"),
            ("00002", "DEF. BARS 12MM X 9M", "LENGTH", "Direct Materials"),
            ("00003", "DEF. BARS 10MM X 6M", "LENGTH", "Direct Materials"),
            ("00004", "STEEL MATTING", "SHEET", "Direct Materials"),
            ("00005", "MCAB - JAR - 8507", "LOT", "Equipment & Rental"),
            ("00006", "SELFLOADER - MEJ - 598", "LOT", "Equipment & Rental"),
        ],
    )

    c.executemany(
        """INSERT INTO suppliers 
            (supplier_name, location, contact_person, contact_number, tin_number, vat_type, terms_days) 
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                "NOEL A. FARIOLEN",
                "Cebu City",
                "Noel Fariolen",
                "0917-000-0001",
                "000-000-000-000",
                "VAT Registered",
                0,
            ),
            (
                "CENTRAL LUMBER CORP.",
                "Mandaue City",
                "Sales Department",
                "0917-000-0002",
                "123-456-789-000",
                "VAT Registered",
                30,
            ),
            (
                "FILMON HARDWARE, INC.",
                "Cebu City",
                "Customer Desk",
                "0917-000-0003",
                "987-654-321-000",
                "VAT Registered",
                15,
            ),
            (
                "DANILO LUMBER SUPPLY",
                "Consolacion",
                "Danilo",
                "0917-000-0004",
                "111-222-333-000",
                "Non-VAT",
                0,
            ),
            (
                "CEBU DIAMOND INDUSTRIAL",
                "Mandaue City",
                "Operations",
                "0917-000-0005",
                "444-555-666-000",
                "VAT Registered",
                30,
            ),
            (
                "GDSM MARKETING",
                "Lapu-Lapu City",
                "Manager",
                "0917-000-0006",
                "777-888-999-000",
                "Non-VAT",
                0,
            ),
        ],
    )

  c.execute("SELECT COUNT(*) FROM signatories")
  if c.fetchone()[0] == 0:
    c.executemany(
        "INSERT INTO signatories (name, role, signature_path) VALUES (?, ?, ?)",
        [
            ("BRAZEL M. DELA CERNA", "Preparer", ""),
            ("LEIZEL A. CABUNILAS", "Approver", "Leizel_signature.png"),
        ],
    )

  c.execute("SELECT COUNT(*) FROM users")
  if c.fetchone()[0] == 0:
    c.executemany(
        """INSERT INTO users 
            (username, password, role1, role2, role3, role4, role5, role6, status) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                "Vergel",
                "1234",
                "Purchaser",
                "",
                "",
                "",
                "",
                "",
                "Active",
            ),
            (
                "Glance",
                "5641",
                "Requisitor",
                "Purchaser",
                "",
                "Office Manager",
                "Admin View All",
                "",
                "Active",
            ),
            (
                "Brazel",
                "12181",
                "Requisitor",
                "Purchaser",
                "Approver",
                "Office Manager",
                "Admin View All",
                "Accounting",
                "Active",
            ),
            (
                "Leizel",
                "5874",
                "",
                "",
                "Approver",
                "Office Manager",
                "",
                "",
                "Active",
            ),
            (
                "AccountingUser",
                "1234",
                "Accounting",
                "",
                "",
                "",
                "",
                "",
                "Active",
            ),
            (
                "Admin",
                "admin",
                "Admin View All",
                "",
                "",
                "",
                "",
                "",
                "Active",
            ),
        ],
    )

  c.execute("SELECT COUNT(*) FROM chart_of_accounts")
  if c.fetchone()[0] == 0:
    c.executemany(
        "INSERT INTO chart_of_accounts (account_code, account_name,"
        " account_type) VALUES (?, ?, ?)",
        [
            ("10100", "Cash on Hand", "Asset"),
            ("10310", "Cash in Bank MBTC", "Asset"),
            ("10320", "Cash in Bank CHINA", "Asset"),
            ("10330", "Cash in Bank BDO", "Asset"),
            ("10340", "Cash in Bank Landbank", "Asset"),
            ("13100", "Construction Materials", "Asset"),
            ("20100", "Accounts Payable-Trade", "Liability"),
            ("60200", "Direct Cost Materials", "Expense"),
        ],
    )

  # Weather Logs Table
  c.execute("""
        CREATE TABLE IF NOT EXISTS daily_weather_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            log_time TEXT NOT NULL,
            project_site TEXT NOT NULL,
            weather_condition TEXT NOT NULL,
            temp_celsius REAL,
            impact_level TEXT NOT NULL,
            work_disruption_hrs REAL DEFAULT 0.0,
            remarks TEXT,
            logged_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

  conn.commit()

  # --- CALL MODULE INITIALIZERS ---
  sync_table_columns(conn)
  init_motorpool_db(conn)
  init_office_payroll_tables(conn)
  init_banks_database(conn)  # <--- Initializes banks_master, loans_master & loan_amortization_schedule
  init_loans_database(conn) 


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

_old_code03 = '''
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
    
    # --- Fetch Item Description from Database ---
    item_desc_str = "N/A"
    if conn:
        try:
            c = conn.cursor()
            po_details = c.execute("SELECT activity, Description FROM requests WHERE pono = ?", (po_number,)).fetchall()
            if po_details:
                desc_parts = []
                for act, part in po_details:
                    item_desc = " - ".join([str(x) for x in [act, part] if x and str(x).strip()])
                    if item_desc:
                        desc_parts.append(item_desc)
                if desc_parts:
                    item_desc_str = " | ".join(desc_parts)
        except Exception:
            item_desc_str = "N/A"

    # Header
    elements.append(Paragraph("**TUANSON CONSTRUCTION**", title_style))
    elements.append(Paragraph("Accounts Payable Voucher (APV)", subtitle_style))
    elements.append(Spacer(1, 15))
    
    # Meta Data Table with Item Description Spanning Across Columns
    meta_data = [
        [Paragraph("**APV NO:**", bold_style), Paragraph(str(apv_no), normal_style), Paragraph("**APV DATE:**", bold_style), Paragraph(str(apv_date), normal_style)],
        [Paragraph("**SUPPLIER:**", bold_style), Paragraph(str(supplier), normal_style), Paragraph("**PROJECT:**", bold_style), Paragraph(str(project), normal_style)],
        [Paragraph("**PO NUMBER:**", bold_style), Paragraph(str(po_number), normal_style), Paragraph("**DR NUMBER:**", bold_style), Paragraph(str(dr_number), normal_style)],
        [Paragraph("**ITEMS:**", bold_style), Paragraph(str(item_desc_str), normal_style), "", ""]
    ]
    meta_table = Table(meta_data, colWidths=[90, 180, 90, 180])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('SPAN', (1, 3), (3, 3))  # Merge item description cell across the remaining columns
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 15))
    
    # Accounting Entries Title
    elements.append(Paragraph("**Accounting Entries (General Ledger Distribution)**", bold_style))
    elements.append(Spacer(1, 8))
    
    # General Ledger Description formatting
    gl_item_suffix = f" ({item_desc_str})" if item_desc_str != "N/A" else ""
    debit_entry_desc = f"APV setup for DR #{dr_number} - {supplier}{gl_item_suffix}"
    credit_entry_desc = f"APV liability accrued for DR #{dr_number}{gl_item_suffix}"

    # Double-Entry Table Data
    table_data = [
        [Paragraph("**Account Code & Name**", header_style), 
         Paragraph("**Description**", header_style), 
         Paragraph("**Debit ₱**", header_style), 
         Paragraph("**Credit ₱**", header_style)],
         
        # Debit Row (Direct Cost Materials)
        [Paragraph("**60200** - Direct Cost Materials", normal_style), 
         Paragraph(debit_entry_desc, normal_style), 
         Paragraph(f"₱{total_amount:,.2f}", right_align_normal), 
         Paragraph("-", right_align_normal)],
         
        # Credit Row (Accounts Payable-Trade)
        [Paragraph("**20100** - Accounts Payable-Trade", normal_style), 
         Paragraph(credit_entry_desc, normal_style), 
         Paragraph("-", right_align_normal), 
         Paragraph(f"₱{total_amount:,.2f}", right_align_normal)],
         
        # Total Row
        [Paragraph("**TOTAL**", bold_style), 
         "", 
         Paragraph(f"**₱{total_amount:,.2f}**", right_align_bold), 
         Paragraph(f"**₱{total_amount:,.2f}**", right_align_bold)]
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
    '''

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
    
    # --- Fetch Item Description from Database ---
    item_desc_str = "N/A"
    if conn:
        try:
            c = conn.cursor()
            po_details = c.execute("SELECT activity, Description FROM requests WHERE pono = ?", (po_number,)).fetchall()
            if po_details:
                desc_parts = []
                for act, part in po_details:
                    item_desc = " - ".join([str(x) for x in [act, part] if x and str(x).strip()])
                    if item_desc:
                        desc_parts.append(item_desc)
                if desc_parts:
                    item_desc_str = " | ".join(desc_parts)
        except Exception:
            item_desc_str = "N/A"

    # Header
    elements.append(Paragraph("TUANSON CONSTRUCTION", title_style))
    elements.append(Paragraph("Accounts Payable Voucher (APV)", subtitle_style))
    elements.append(Spacer(1, 15))
    
    # Meta Data Table with Item Description Spanning Across Columns
    meta_data = [
        [Paragraph("APV NO:", bold_style), Paragraph(str(apv_no), normal_style), Paragraph("APV DATE:", bold_style), Paragraph(str(apv_date), normal_style)],
        [Paragraph("SUPPLIER:", bold_style), Paragraph(str(supplier), normal_style), Paragraph("PROJECT:", bold_style), Paragraph(str(project), normal_style)],
        [Paragraph("PO NUMBER:", bold_style), Paragraph(str(po_number), normal_style), Paragraph("DR NUMBER:", bold_style), Paragraph(str(dr_number), normal_style)],
        [Paragraph("ITEMS:", bold_style), Paragraph(str(item_desc_str), normal_style), "", ""]
    ]
    meta_table = Table(meta_data, colWidths=[90, 180, 90, 180])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('SPAN', (1, 3), (3, 3))  # Merge item description cell across the remaining columns
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 15))
    
    # Accounting Entries Title
    elements.append(Paragraph("Accounting Entries (General Ledger Distribution)", bold_style))
    elements.append(Spacer(1, 8))
    
    # General Ledger Description formatting
    gl_item_suffix = f" ({item_desc_str})" if item_desc_str != "N/A" else ""
    debit_entry_desc = f"APV setup for DR #{dr_number} - {supplier}{gl_item_suffix}"
    credit_entry_desc = f"APV liability accrued for DR #{dr_number}{gl_item_suffix}"

    # Double-Entry Table Data
    table_data = [
        [Paragraph("Account Code & Name", header_style), 
         Paragraph("Description", header_style), 
         Paragraph("Debit ₱", header_style), 
         Paragraph("Credit ₱", header_style)],
         
        # Debit Row (Direct Cost Materials)
        [Paragraph("**60200** - Direct Cost Materials", normal_style), 
         Paragraph(debit_entry_desc, normal_style), 
         Paragraph(f"₱{total_amount:,.2f}", right_align_normal), 
         Paragraph("-", right_align_normal)],
         
        # Credit Row (Accounts Payable-Trade)
        [Paragraph("**20100** - Accounts Payable-Trade", normal_style), 
         Paragraph(credit_entry_desc, normal_style), 
         Paragraph("-", right_align_normal), 
         Paragraph(f"₱{total_amount:,.2f}", right_align_normal)],
         
        # Total Row
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

#==============
# --- CV PDF GENERATOR FUNCTION ---
def create_cv_pdf(cv_no, cv_date, apv_no, supplier, pay_method, total_amt, conn=None, discount=0.0, ewt_amt=0.0, ewt_code=""):
    import os
    import html
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

    # Initial Financial Calculations
    gross_amt = float(total_amt or 0.0)
    disc_amt = float(discount or 0.0)
    tax_amt = float(ewt_amt or 0.0)

    # Fetch Supplier Location & Auto-Detect BIR 2307 / Discount from General Ledger DB
    sup_location = "Cebu, Philippines"
    cheque_no_str = "-"
    cheque_date_str = "-"
    po_no_str = "-"
    project_str = "-"

    if conn:
        try:
            c = conn.cursor()
            
            # Fetch Supplier Location
            row = c.execute("SELECT location FROM suppliers WHERE LOWER(TRIM(supplier_name)) = LOWER(TRIM(?))", (supplier,)).fetchone()
            if row and row[0]:
                sup_location = row[0]

            # -----------------------------------------------------------------
            # AUTO-FETCH SAVED BIR 2307 WITHHOLDING TAX (20400) & DISCOUNT (50200)
            # -----------------------------------------------------------------
            if tax_amt == 0.0:
                wht_row = c.execute("SELECT credit, description FROM journal_entries WHERE voucher_no = ? AND account_code = '20400'", (cv_no,)).fetchone()
                if wht_row and wht_row[0]:
                    tax_amt = float(wht_row[0])
                    wht_desc = str(wht_row[1] or "")
                    if "WI158" in wht_desc:
                        ewt_code = "WI158"
                    elif "WI160" in wht_desc:
                        ewt_code = "WI160"

            if disc_amt == 0.0:
                disc_row = c.execute("SELECT credit FROM journal_entries WHERE voucher_no = ? AND account_code = '50200'", (cv_no,)).fetchone()
                if disc_row and disc_row[0]:
                    disc_amt = float(disc_row[0])

            # Fetch Voucher Metadata (Check details, PO, Project)
            if apv_no and str(apv_no).strip():
                del_row = c.execute("""
                    SELECT cheque_no, cheque_date, pono, project_name 
                    FROM deliveries WHERE apv_number = ? AND LOWER(TRIM(supplier)) = LOWER(TRIM(?))
                """, (apv_no, supplier)).fetchone()
                if del_row:
                    cheque_no_str = del_row[0] or "-"
                    cheque_date_str = del_row[1] or "-"
                    po_no_str = del_row[2] or "-"
                    project_str = del_row[3] or "-"
            else:
                req_row = c.execute("""
                    SELECT cheque_no, cheque_date, pono, project_name 
                    FROM requests WHERE cv_number = ? AND LOWER(TRIM(supplier)) = LOWER(TRIM(?))
                """, (cv_no, supplier)).fetchone()
                if req_row:
                    cheque_no_str = req_row[0] or "-"
                    cheque_date_str = req_row[1] or "-"
                    po_no_str = req_row[2] or "-"
                    project_str = req_row[3] or "-"
        except Exception:
            pass

    # Recalculate Net Disbursement Amount after DB Lookup
    net_disbursement = max(0.0, gross_amt - disc_amt - tax_amt)

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName=pdf_font, fontSize=16, leading=20, alignment=1)
    sub_title_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontName=pdf_font, fontSize=9, leading=12, alignment=1)
    body_norm = ParagraphStyle('BodyNorm', parent=styles['Normal'], fontName=pdf_font, fontSize=8, leading=10)

    story.append(Paragraph("Tuanson Construction", title_style))
    story.append(Paragraph("162 P. Labuca St., Cansojong, Talisay City, Cebu", sub_title_style))
    story.append(Paragraph("Tel: - Fax: -", sub_title_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Payment Voucher", title_style))
    story.append(Spacer(1, 10))

    # Safe HTML escaping to prevent XML parsing errors on dynamic user input (e.g., & symbols)
    supplier_clean = html.escape(str(supplier or ''))
    sup_location_clean = html.escape(str(sup_location or ''))
    cv_no_clean = html.escape(str(cv_no or ''))
    cv_date_clean = html.escape(str(cv_date or ''))
    cheque_no_clean = html.escape(str(cheque_no_str or '-'))
    cheque_date_clean = html.escape(str(cheque_date_str or '-'))
    project_clean = html.escape(str(project_str or '-'))
    po_no_clean = html.escape(str(po_no_str or '-'))


    supplier_box_html = f"<b>{supplier_clean}</b><br/>{sup_location_clean}"

    meta_box_html = (
        f"NO.: {cv_no_clean}<br/>"
        f"DATE: {cv_date_clean}<br/>"
        f"CHEQUE NO.: {cheque_no_clean} / {cheque_date_clean}"
    )

    #==========
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

    apv_ref = f"APV#{html.escape(str(apv_no))}" if apv_no else "Advance Downpayment"
    po_ref = f"(PO#{po_no_clean})" if po_no_clean != "-" else ""
    desc_text = f"Payment for materials / services ({apv_ref}) {po_ref} for {project_clean}".strip()

    acct_code = "20100" if apv_no else "10500"
    acct_name = supplier_clean if apv_no else f"Advances to Suppliers - {supplier_clean}"

    part_data = [
        [Paragraph("A/C CODE", body_norm), Paragraph("A/C NAME", body_norm), Paragraph("DESCRIPTION", body_norm), Paragraph("AMOUNT", body_norm)],
        [Paragraph(acct_code, body_norm), Paragraph(acct_name, body_norm), Paragraph(desc_text, body_norm), Paragraph(f"₱{gross_amt:,.2f}", body_norm)]
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

    story.append(Paragraph("Journals:", body_norm))
    story.append(Spacer(1, 3))

    # --- GENERAL LEDGER DOUBLE ENTRY TABLE WITH BIR 2307 EWT & DISCOUNTS ---
    j_data = [
        [Paragraph("Doc No.", body_norm), Paragraph("Date", body_norm), Paragraph("Account #", body_norm), Paragraph("Account Name", body_norm), Paragraph("Debit", body_norm), Paragraph("Credit", body_norm)],
        # Debit Row (Full Gross Payable)
        [Paragraph(cv_no_clean, body_norm), Paragraph(cv_date_clean, body_norm), Paragraph(acct_code, body_norm), Paragraph(acct_name, body_norm), Paragraph(f"{gross_amt:,.2f}", body_norm), Paragraph("", body_norm)],
    ]

    # Optional Credit Row: Purchase Discounts (50200)
    if disc_amt > 0:
        j_data.append([
            Paragraph(cv_no_clean, body_norm), Paragraph(cv_date_clean, body_norm), Paragraph("50200", body_norm), Paragraph("Purchase Discounts", body_norm), Paragraph("", body_norm), Paragraph(f"{disc_amt:,.2f}", body_norm)
        ])

    # Optional Credit Row: BIR 2307 Withholding Tax Payable (20400)
    if tax_amt > 0:
        atc_label = f" ({html.escape(str(ewt_code))})" if ewt_code else ""
        j_data.append([
            Paragraph(cv_no_clean, body_norm), Paragraph(cv_date_clean, body_norm), Paragraph("20400", body_norm), Paragraph(f"Withholding Tax Payable - Expanded{atc_label}", body_norm), Paragraph("", body_norm), Paragraph(f"{tax_amt:,.2f}", body_norm)
        ])

    # Main Credit Row: Cash / Bank Disbursement
    bank_acct_name = "Cash in Bank BDO"
    bank_acct_code = "10330"
    if pay_method and pay_method.lower() == "cash":
        bank_acct_name = "Petty Cash Fund / Cash on Hand"
        bank_acct_code = "10100"

    j_data.append([
        Paragraph(cv_no_clean, body_norm), Paragraph(cv_date_clean, body_norm), Paragraph(bank_acct_code, body_norm), Paragraph(bank_acct_name, body_norm), Paragraph("", body_norm), Paragraph(f"{net_disbursement:,.2f}", body_norm)
    ])

    # Total Balanced Row
    j_data.append([
        Paragraph("", body_norm), Paragraph("", body_norm), Paragraph("", body_norm), Paragraph("TOTAL", body_norm), Paragraph(f"{gross_amt:,.2f}", body_norm), Paragraph(f"{gross_amt:,.2f}", body_norm)
    ])

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

    # Associated Documents Table
    doc_data = [
        [Paragraph("Type", body_norm), Paragraph("Doc. No.", body_norm), Paragraph("Doc. Date", body_norm), Paragraph("Description", body_norm), Paragraph("Orig. Amount", body_norm), Paragraph("Paid Amount", body_norm)],
        [Paragraph("BIL", body_norm), Paragraph(f"PO#{po_no_clean}", body_norm), Paragraph(cv_date_clean, body_norm), Paragraph(f"PAYABLE FOR MATERIALS FOR \"{project_clean.upper()}\"", body_norm), Paragraph(f"{gross_amt:,.2f}", body_norm), Paragraph(f"{net_disbursement:,.2f}", body_norm)]
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

    # Convert Net Disbursement Amount to Words
    try:
        amt_words = amount_to_words(net_disbursement)
    except Exception:
        amt_words = f"PHILIPPINE PESO {net_disbursement:,.2f}"

    r_align_style = ParagraphStyle('RAlign', parent=body_norm, alignment=2)

    # Summary Breakdown
    summary_lines = [f"SUB TOTAL: ₱{gross_amt:,.2f}"]
    if disc_amt > 0:
        summary_lines.append(f"LESS DISCOUNT: ₱{disc_amt:,.2f}")
    if tax_amt > 0:
        tax_label = f" ({ewt_code})" if ewt_code else ""
        summary_lines.append(f"LESS 2307 EWT{tax_label}: ₱{tax_amt:,.2f}")
    summary_lines.append(f"NET TOTAL PHP: ₱{net_disbursement:,.2f}")

    #===============
    # 1. Join summary lines using HTML line breaks instead of physical line gaps
    summary_html = "<br/>".join(summary_lines)

    # 2. Amount in Words section with clean tags and closed brackets
    words_data = [
        [
            Paragraph(f"<b>AMOUNT IN WORDS:</b><br/>{html.escape(amt_words.upper())}", body_norm),
            Paragraph(summary_html, r_align_style)
        ]
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

    # 3. Signature block with unified single-line string formatting
    sig_data = [
        [
            Paragraph("____________________________________<br/><br/>APPROVED BY", ParagraphStyle('C1', parent=body_norm, alignment=1)),
            Paragraph("____________________________________<br/><br/>RECEIVED BY", ParagraphStyle('C2', parent=body_norm, alignment=1))
        ]
    ]

    t_sig = Table(sig_data, colWidths=[270, 270])
    t_sig.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), pdf_font),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_sig)

    # 4. Build and return the PDF file
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
                      
#================================Login System=======================
import streamlit as st
from datetime import datetime, timedelta

# --- APP LAYOUT & CONFIG ---
st.set_page_config(page_title="Tuanson Construction System", layout="wide")

conn = get_db_connection()
c = conn.cursor()

# --- INITIALIZE SESSION STATE ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.available_roles = []
    st.session_state.can_add_act = "No"
    st.session_state.can_add_item = "No"

# --- RESTORE SESSION ON PAGE REFRESH (WITH 5-MIN INACTIVITY TIMEOUT) ---
query_user = st.query_params.get("user")
last_active_str = st.query_params.get("last_active")

if not st.session_state.logged_in and query_user and last_active_str:
    try:
        last_active_dt = datetime.fromisoformat(last_active_str)
        # Check if last activity was within 5 minutes (300 seconds)
        if datetime.now() - last_active_dt <= timedelta(minutes=5):
            user_data = c.execute(
                "SELECT id, username, password, role1, role2, role3, role4, role5, role6, status, can_add_act, can_add_item FROM users WHERE username=? AND status='Active'",
                (query_user,)
            ).fetchone()
            if user_data:
                st.session_state.logged_in = True
                st.session_state.current_user = user_data[1]
                raw_roles = user_data[3:9]
                st.session_state.available_roles = [r for r in raw_roles if r and str(r).strip() != ""]
                st.session_state.can_add_act = user_data[10]
                st.session_state.can_add_item = user_data[11]
        else:
            # Session expired (> 5 minutes idle)
            st.query_params.clear()
            st.warning("⚠️ Session expired due to 5 minutes of inactivity. Please log in again.")
    except Exception:
        st.query_params.clear()

# --- LOGIN SCREEN (IF NOT LOGGED IN) ---
if not st.session_state.logged_in:
    st.title("🏗️️ Tuanson Construction Enterprise System")
    st.caption("Integrated Procurement, Inventory & Double-Entry Accounting System")
    st.write("---")

    col_login, col_flow = st.columns([1, 1.2], gap="large")

    with col_login:
        st.subheader("🔒 User Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_btn = st.form_submit_button("Login", width="stretch")

            if submit_btn:
                user_data = c.execute(
                    "SELECT id, username, password, role1, role2, role3, role4, role5, role6, status, can_add_act, can_add_item FROM users WHERE username=? AND password=? AND status='Active'",
                    (username, password)
                ).fetchone()
                
                if user_data:
                    st.session_state.logged_in = True
                    st.session_state.current_user = user_data[1] 
                    raw_roles = user_data[3:9]
                    st.session_state.available_roles = [r for r in raw_roles if r and str(r).strip() != ""]
                    st.session_state.can_add_act = user_data[10]
                    st.session_state.can_add_item = user_data[11]

                    # Save URL params to keep session alive across refreshes
                    st.query_params["user"] = user_data[1]
                    st.query_params["last_active"] = datetime.now().isoformat()
                    st.rerun()
                else:
                    st.error("Invalid Username/Password or Account is Inactive.")

    with col_flow:
        st.subheader("🔄 System Workflow Process")
        st.markdown(
            """
            📝 **Requisitor**  
            Creates Purchase Requisition floaters for site material needs.  
            
            ⬇️  
            
            🛒 **Purchaser**  
            Requests supplier quotes and generates Purchase Orders (PO).  
            
            ⬇️  
            
            👔 **Approver / Manager**  
            Reviews budget alignment, approves POs, and authorizes releases.  
            
            ⬇️  
            
            🚚 **Purchaser & Receiving**  
            Logs Delivery Receipts (DR) and updates inventory ledgers.  
            
            ⬇️  
            
            📑 **Accounting**  
            Issues AP Vouchers (APV), 1% EWT deductions, and Payment Vouchers (CV).  
            """,
            unsafe_allow_html=True
        )
        
    st.stop()

# --- MAIN APP (IF LOGGED IN) ---
# Keep activity timestamp updated on every user interaction
st.query_params["user"] = st.session_state.current_user
st.query_params["last_active"] = datetime.now().isoformat()

st.title("🏗️ Tuanson Construction - Procurement & Inventory")

st.sidebar.write(f"👤 **Logged in as:** {st.session_state.current_user}")
st.sidebar.success("Status: Online")

# Logout button: Clears session and URL query parameters
if st.sidebar.button("🚪 Logout",width="stretch"):
    st.query_params.clear()
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")

if not st.session_state.available_roles:
    st.warning("You have no roles assigned. Please contact the Admin.")
    st.stop()

st.write("Welcome back! Your session is active.")
#==============================end Login System=====================

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
                width="stretch",
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
                
                #==========================================Email notification===========================
                

                # --- EMAIL NOTIFICATION TO PURCHASER(S) ---
                try:
                    # 1. Fetch active email addresses for any user assigned as 'Purchaser'
                    purchasers = c.execute("""
                        SELECT DISTINCT email FROM users 
                        WHERE status = 'Active' 
                        AND email IS NOT NULL 
                        AND email != '' 
                        AND (role1 = 'Purchaser' OR role2 = 'Purchaser' OR role3 = 'Purchaser' 
                             OR role4 = 'Purchaser' OR role5 = 'Purchaser' OR role6 = 'Purchaser')
                    """).fetchall()
        
                    requester_name = st.session_state.get('username', 'A Requisitor')
        
                    # 2. Loop through and send email to each Purchaser
                    for row in purchasers:
                        purchaser_email = row[0]
                        send_notification(
                            to_email=purchaser_email,
                            subject="📦 New Purchase Request Submitted",
                            body=f"""New Purchase Request Submitted
                                    Submitted By: {requester_name}
        
                                    New items have been added to the purchasing queue.
        
                                    Please log in to the Construction Management System to process the Purchase Order.
        
                                """
                            )
                except Exception as e:
                    st.warning(f"Submitted successfully, but could not send email alert: {e}")
        
            
        
                st.success("All items successfully submitted to Purchasing!")
                

                #===========================================end of email notication=====================
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
            st.dataframe(history_df, width="stretch", hide_index=True)
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
                st.dataframe(pending_ledger_df.drop(columns=['id']), width="stretch", hide_index=True)
                
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
                width="stretch",
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
                width="stretch", 
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
                width="stretch",
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

    #with tab_ledger:
    #with tab_ledger:
    with tab_ledger:
        st.write("### 🚚 Issue Materials to Site (Qty Out)")
        
        if st.button("🔄 Refresh Ledger Data", key="btn_refresh_inventory_ledger"):
            st.rerun()
        
        # 1. Fetch available items in stock
        items_db = c.execute("SELECT DISTINCT item_description FROM inventory_ledger WHERE item_description IS NOT NULL ORDER BY item_description ASC").fetchall()
        item_list = [i[0] for i in items_db] if items_db else []

        # 2. Fetch project list from database for the Destination dropdown
        try:
            db_projects = [r[0] for r in c.execute("SELECT project_name FROM projects WHERE project_name IS NOT NULL ORDER BY project_name ASC").fetchall() if r[0]]
        except Exception:
            db_projects = []

        # Default fallback list matching your active projects
        default_projects = [
            "LAZADA NEW - WAREHOUSE 2",
            "MOTORPOOL",
            "OFFICE ASSIGN",
            "CONSOLACION-TAYUD-LILOAN RD",
            "PASEO APARTMENT"
        ]

        # Combine database projects with default fallback list without duplicates
        project_options = list(dict.fromkeys(db_projects + default_projects))

        if item_list:
            col1, col2 = st.columns(2)
            
            # SELECT ITEM DROPDOWN
            selected_item = col1.selectbox("Select Item", item_list, key="dispatch_selected_item")
            
            # DYNAMIC STOCK RE-QUERY
            current_stock = get_latest_item_balance(c, selected_item)
            col1.caption(f"📦 Current Stock Available: **{current_stock:,.2f}**")
            
            # AUTO-GENERATED MIF REFERENCE
            next_mif = get_next_mif_number(c)
            mif_ref = col1.text_input("MIF / Dispatch Ref No.", value=next_mif, key="dispatch_mif_ref")
            
            # QUANTITY INPUT
            qty_to_issue = col2.number_input(
                "Qty Out", 
                min_value=0.10, 
                max_value=float(current_stock) if current_stock > 0 else 999999.0, 
                value=0.10, 
                step=1.0, 
                key="dispatch_qty_out"
            )

            # DESTINATION SITE DROPDOWN (Replaced text_input)
            site_location = col2.selectbox("Destination Site / Location", project_options, key="dispatch_site_location")
            
            # REMARKS
            issuance_remarks = st.text_input("Remarks", placeholder="e.g. Dispatched via Flatbed Truck 1", key="dispatch_remarks")
            
            # SUBMIT DISPATCH
            if st.button("🚀 Confirm Material Dispatch", type="primary", key="btn_confirm_dispatch"):
                if current_stock < qty_to_issue:
                    st.error(f"⚠️ Insufficient stock available! Available balance is {current_stock:,.2f}.")
                else:
                    dispatch_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    new_bal = max(0.0, current_stock - qty_to_issue)
                    
                    c.execute("""
                        INSERT INTO inventory_ledger (date, ref_no, item_description, qty_in, qty_out, balance, location, remarks, status)
                        VALUES (?, ?, ?, 0.0, ?, ?, ?, ?, 'Pending')
                    """, (dispatch_time, mif_ref.strip(), selected_item, qty_to_issue, new_bal, site_location.strip(), issuance_remarks.strip()))
                    
                    conn.commit()
                    st.cache_data.clear()
                    st.success(f"✅ Dispatched {qty_to_issue:,.2f} units of {selected_item} to {site_location}! Awaiting site confirmation.")
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
                width="stretch",
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
                    width="stretch",
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
                
                st.dataframe(po_items_df, width="stretch", hide_index=True)
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
    
    st.dataframe(styled_df, width="stretch", hide_index=True)

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
    
    tab_coa, tab_apv, tab_payment, tab_gl, tab_fs, tab_br, tab_brm = st.tabs([
        "📊 Chart of Accounts", 
        "📝 Accounts Payable Voucher (APV)", 
        "💸 Check / Payment Voucher (CV)", 
        "📖 General Ledger Entries",
        "📈 Financial Statements",
        "🏦 Bank Reconciliation",   
        "🏦 Bank Loans"  # <--- NEW TAB 6
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
            st.dataframe(df_coa, width="stretch", hide_index=True)
        else:
            st.info("No accounts found in the Chart of Accounts.")
            
    _old_code02 = '''
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
            st.dataframe(apv_df.style.format({"Total Amount": "₱{:,.2f}"}), width="stretch", hide_index=True)
            
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
                                if len(item_desc) > 40:
                                    item_desc = item_desc[:45] + "..."
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

        '''
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
            # Fetch item descriptions for each PO and insert before 'Project' column
            item_descriptions = []
            for po_no in apv_df['PO Number']:
                po_details = c.execute("SELECT activity, Description FROM requests WHERE pono = ?", (po_no,)).fetchall()
                if po_details:
                    desc_parts = []
                    for act, part in po_details:
                        item_desc = " - ".join([str(x) for x in [act, part] if x and str(x).strip()])
                        if item_desc:
                            desc_parts.append(item_desc)
                    item_descriptions.append(" | ".join(desc_parts) if desc_parts else "N/A")
                else:
                    item_descriptions.append("N/A")
            
            # Add the column and reorder so 'Item Description' is placed right before 'Project'
            apv_df['Item Description'] = item_descriptions
            column_order = ['id', 'PO Number', 'DR Number', 'Supplier', 'Item Description', 'Project', 'Total Amount', 'Date Received']
            apv_df = apv_df[column_order]

            st.dataframe(apv_df.style.format({"Total Amount": "₱{:,.2f}"}), width="stretch", hide_index=True)
            
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
                                if len(item_desc) > 40:
                                    item_desc = item_desc[:45] + "..."
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
                width="stretch", 
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
            # --- FILTERED: Only fetch POs for suppliers flagged with requires_advance_pdc = 'Yes' ---
            unpaid_pos = c.execute("""
                SELECT r.pono, r.supplier, SUM(r.amount) AS total_amount, r.project_name 
                FROM requests r
                JOIN suppliers s ON LOWER(TRIM(r.supplier)) = LOWER(TRIM(s.supplier_name))
                WHERE r.pono IS NOT NULL AND r.pono != '' 
                  AND LOWER(COALESCE(r.status, '')) LIKE '%approved%'
                  AND (r.payment_status IS NULL OR r.payment_status = '' OR LOWER(r.payment_status) = 'unpaid')
                  AND s.requires_advance_pdc = 'Yes'
                GROUP BY r.pono, r.supplier, r.project_name
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
                st.info("No open Approved POs available for suppliers flagged for Advance PDC.")

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
            
            # --- DYNAMIC MULTI-TABLE VOUCHER SEQUENCE GENERATION ---
            cv_seq_list = []
            for tbl, col in [('journal_entries', 'voucher_no'), ('deliveries', 'cv_number'), ('requests', 'cv_number'), ('floating_checks', 'voucher_no')]:
                try:
                    res = c.execute(f"SELECT {col} FROM {tbl} WHERE {col} LIKE ?", (f"{prefix}-%",)).fetchall()
                    for r in res:
                        if r[0]:
                            num_str = ''.join(ch for ch in str(r[0]) if ch.isdigit())
                            if num_str:
                                cv_seq_list.append(int(num_str))
                except Exception:
                    pass

            next_cv_num = max(cv_seq_list) + 1 if cv_seq_list else 1
            suggested_cv = f"{prefix}-{next_cv_num:05d}"

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
                width="stretch",
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
                
                # --- FETCH SAVED FINANCIAL BREAKDOWNS FROM GENERAL LEDGER (50200 & 20400) ---
                existing_disc_row = c.execute("SELECT credit FROM journal_entries WHERE voucher_no = ? AND account_code = '50200'", (cv_no,)).fetchone()
                init_discount_amt = float(existing_disc_row[0]) if existing_disc_row and existing_disc_row[0] else 0.0

                existing_wht_row = c.execute("SELECT credit, description FROM journal_entries WHERE voucher_no = ? AND account_code = '20400'", (cv_no,)).fetchone()
                init_wht_amt = float(existing_wht_row[0]) if existing_wht_row and existing_wht_row[0] else 0.0
                init_wht_desc = str(existing_wht_row[1]) if existing_wht_row and existing_wht_row[1] else ""

                # Determine saved ATC code & default dropdown index for BIR 2307
                init_atc = ""
                default_wht_index = 0
                if "WI158" in init_wht_desc or (init_wht_amt > 0 and abs(init_wht_amt - float(total_amt or 0) * 0.01) < 1.0):
                    init_atc = "WI158"
                    default_wht_index = 1
                elif "WI160" in init_wht_desc or (init_wht_amt > 0 and abs(init_wht_amt - float(total_amt or 0) * 0.02) < 1.0):
                    init_atc = "WI160"
                    default_wht_index = 2

                # Compute net check disbursement
                net_check_amt = max(0.0, float(total_amt or 0.0) - init_discount_amt - init_wht_amt)

                st.write(f"💳 **Voucher:** {cv_no} ({pay_method}) | **Supplier/Payee:** {supplier} | **Amount:** ₱{total_amt:,.2f}")
                
                col_btn1, col_btn2 = st.columns(2)
                
                # Pass discount and ewt (BIR 2307) details directly into create_cv_pdf so GL reflection is included
                #voucher_pdf = create_cv_pdf(cv_no, cv_date, apv_no, supplier, pay_method, total_amt, conn=conn, discount=init_discount_amt, ewt_amt=init_wht_amt, ewt_code=init_atc)
                #col_btn1.download_button(
                #    label="📄 Print Payment Voucher PDF",
                #    data=voucher_pdf,
                #    file_name=f"Voucher_{cv_no}.pdf",
                #    mime="application/pdf",
                #    key=f"print_pv_{cv_no}_{idx}"
                #)
                voucher_pdf = create_cv_pdf(cv_no, cv_date, apv_no, supplier, pay_method, total_amt, conn=conn)
                col_btn1.download_button(
                    label="📄 Print Payment Voucher PDF",
                    data=voucher_pdf,
                    file_name=f"Voucher_{cv_no}.pdf",
                    mime="application/pdf",
                    key=f"print_pv_{cv_no}_{idx}"
                )
                
                cheque_pdf = create_cheque_pdf(supplier, net_check_amt, c_date)
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
                        index=default_wht_index,
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
                    
                    computed_tax_withheld = round(new_voucher_amt * wht_rate, 2)
                    
                    # Net Disbursement accounts for Gross minus Discount minus Tax Withheld (Check amount)
                    net_disbursement = max(0.0, round(new_voucher_amt - discount_amt - computed_tax_withheld, 2))
                    
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
                            try:
                                # 1. Fetch supplier details using flexible TRIM/LOWER matching
                                supp_row = conn.execute(
                                    "SELECT tin_number, location FROM suppliers WHERE LOWER(TRIM(supplier_name)) = LOWER(TRIM(?))", 
                                    (supplier_name,)
                                ).fetchone()
                                
                                supplier_tin = supp_row[0] if (supp_row and supp_row[0]) else "000-000-000-000"
                                supplier_address = supp_row[1] if (supp_row and supp_row[1]) else "N/A"
                                
                                # 2. Compute tax period bounds (current quarter)
                                today = datetime.now()
                                q_start_month = 3 * ((today.month - 1) // 3) + 1
                                period_from = datetime(today.year, q_start_month, 1).strftime('%m/%d/%Y')
                                period_to = today.strftime('%m/%d/%Y')
                
                                # 3. Generate 2307 PDF Buffer directly
                                pdf_buffer = generate_bir_2307_pdf(
                                    voucher_data={
                                        "cv_no": cv_no,
                                        "period_from": period_from,
                                        "period_to": period_to
                                    },
                                    supplier_data={
                                        "payee_name": supplier_name,
                                        "name": supplier_name,
                                        "payee_tin": supplier_tin,
                                        "tin": supplier_tin,
                                        "payee_address": supplier_address,
                                        "address": supplier_address
                                    },
                                    wht_details={
                                        "income_type": income_type, 
                                        "atc": atc_code, 
                                        "gross": new_voucher_amt, 
                                        "tax": computed_tax_withheld
                                    }
                                )
                
                                # 4. Direct 1-Click Download Button
                                st.download_button(
                                    label=f"📄 Download 2307 PDF ({cv_no})",
                                    data=pdf_buffer,
                                    file_name=f"BIR_Form_2307_{cv_no}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_2307_{cv_no}_{idx}",
                                    width="stretch"
                                )
                            except Exception as pdf_err:
                                st.error(f"⚠️ Could not build BIR 2307 PDF: {pdf_err}")
                    
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
                            
                            # 4. Manage Withholding Tax Payable account (Code 20400) if 2307 is applied
                            has_wht_entry = c.execute("SELECT COUNT(*) FROM journal_entries WHERE voucher_no = ? AND account_code = '20400'", (cv_no,)).fetchone()[0] > 0
                            
                            if computed_tax_withheld > 0:
                                if has_wht_entry:
                                    c.execute("UPDATE journal_entries SET credit = ?, description = ? WHERE voucher_no = ? AND account_code = '20400'", (computed_tax_withheld, f"EWT {atc_code} withheld for {cv_no}", cv_no))
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
                            
                            # 7. Update Floating Checks register with full Gross, Tax, Discount & Net Amount
                            c.execute("""
                                UPDATE floating_checks 
                                SET gross_amount = ?,
                                    discount_amount = ?,
                                    wht_rate = ?,
                                    wht_atc = ?,
                                    wht_amount = ?,
                                    amount = ?, 
                                    check_no = ?, 
                                    check_date = ? 
                                WHERE voucher_no = ?
                            """, (
                                new_voucher_amt, 
                                discount_amt, 
                                wht_rate, 
                                atc_code, 
                                computed_tax_withheld, 
                                net_disbursement, 
                                new_check_no.strip(), 
                                formatted_chk_date, 
                                cv_no
                            ))
                            
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
                width="stretch", 
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
            ), width="stretch", hide_index=True)
            st.metric("Total Revenue", f"₱{total_rev:,.2f}")

            st.markdown("**Expenses & Costs**")
            st.dataframe(exp_df[['account_code', 'account_name', 'amount']].rename(
                columns={'account_code': 'Code', 'account_name': 'Account', 'amount': 'Amount (₱)'}
            ), width="stretch", hide_index=True)
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
                        width="stretch", 
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
                        width="stretch", 
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
                        width="stretch", 
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
        with tab_brm:
            conn = get_db_connection()
            render_bank_loans_dashboard(conn)

                  
#==================================================================================
# --- ROLE 6: ADMIN VIEW ALL ---
elif role == "Admin View All":
    st.subheader("🛡️ Admin Dashboard & Analytics")

    tab_settings, tab_reports, tab_payables = st.tabs(["⚙️ Master Database & Settings", "📊 Project Approved Reports", "💸 Accounts Payable"])
    
    with tab_settings:
        st.write("### ⚙️ Admin Settings & Configuration")
        
        with st.expander("👥 Manage System Users"):
            st.write("#### 👤 Add, Edit, or Remove Users")
            users_df = pd.read_sql_query("SELECT id, username, email, password, role1, role2, role3, role4, role5, role6, status, can_add_act, can_add_item FROM users", conn)
            
            role_options = ["", "Requisitor", "Purchaser", "Approver", "Office Manager", "Engineering", "Accounting", "HRIS / Payroll", "Motorpool", "Admin View All"]
            yes_no_options = ["Yes", "No"]
            
            edited_users = st.data_editor(
                users_df,
                num_rows="dynamic",
                width="stretch",
                hide_index=True,
                column_config={
                    "id": None, 
                    "username": st.column_config.TextColumn("Username", required=True),
                    "email": st.column_config.TextColumn("Email Address", help="User's email for workflow alerts"),
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
                        email_val = str(row.get('email', '')).strip() if pd.notnull(row.get('email')) else ''
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
                            INSERT INTO users (username, email, password, role1, role2, role3, role4, role5, role6, status, can_add_act, can_add_item)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            username_val, email_val, pwd, 
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
                            width="stretch",
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
                width="stretch",
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
            
            # 1. Safe DB migration to ensure the column exists
            try:
                c.execute("ALTER TABLE suppliers ADD COLUMN requires_advance_pdc TEXT DEFAULT 'No'")
                conn.commit()
            except Exception:
                pass  # Column already exists
        
            # 2. Query suppliers including the new requires_advance_pdc field
            sups_df = pd.read_sql_query(
                "SELECT id, supplier_name, location, contact_person, contact_number, tin_number, vat_type, terms_days, requires_advance_pdc FROM suppliers", 
                conn
            )
            
            # Fill any null values with 'No'
            if 'requires_advance_pdc' in sups_df.columns:
                sups_df['requires_advance_pdc'] = sups_df['requires_advance_pdc'].fillna('No')
        
            # 3. Data Editor with Selectbox configuration
            edited_sups = st.data_editor(
                sups_df,
                num_rows="dynamic",
                width="stretch",
                hide_index=True,
                column_config={
                    "id": None,
                    "requires_advance_pdc": st.column_config.SelectboxColumn(
                        "Requires Advance PDC?",
                        help="If 'Yes', POs from this supplier can be paid via Advance PDC in Accounting before delivery.",
                        options=["No", "Yes"],
                        required=True,
                        default="No"
                    )
                }
            )
        
            # 4. Save updated suppliers list
            if st.button("💾 Save Suppliers List", type="primary"):
                c.execute("DELETE FROM suppliers")
                for _, r in edited_sups.iterrows():
                    s_name = str(r['supplier_name']).strip() if pd.notnull(r['supplier_name']) else ""
                    if s_name:
                        c.execute("""
                            INSERT INTO suppliers (supplier_name, location, contact_person, contact_number, tin_number, vat_type, terms_days, requires_advance_pdc)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            s_name,
                            str(r.get('location', '') or ''),
                            str(r.get('contact_person', '') or ''),
                            str(r.get('contact_number', '') or ''),
                            str(r.get('tin_number', '') or ''),
                            str(r.get('vat_type', '') or 'VAT Registered'),
                            int(r.get('terms_days', 0) or 0),
                            str(r.get('requires_advance_pdc', 'No') or 'No')
                        ))
                conn.commit()
                st.success("Suppliers list updated!")
                st.rerun()

        with st.expander("✍️ Manage Signatories"):
            sigs_df = pd.read_sql_query("SELECT id, name, role, signature_path FROM signatories", conn)
            edited_sigs = st.data_editor(sigs_df, num_rows="dynamic", width="stretch", hide_index=True, column_config={"id": None})
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
        st.dataframe(all_reqs, width="stretch", hide_index=True)
        
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
        st.dataframe(del_ap.style.format({"total_amount": "₱{:,.2f}"}), width="stretch", hide_index=True)
        
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
                    c.execute("DELETE FROM floating_checks")
                    c.execute("DELETE FROM bank_reconciliations")
                    
                    # Reset SQLite auto-increment counters back to 1
                    c.execute("""
                        DELETE FROM sqlite_sequence 
                        WHERE name IN ('journal_entries', 'deliveries', 'inventory_ledger', 'requests', 'floating_checks', 'bank_reconciliations')
                    """)
                    
                    conn.commit()
                    st.success("🎉 All operational tables cleared and ID sequences reset to 1!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error during database reset: {e}")
    #================================================================
#=================================================================================
### --- ROLE: ENGINEERING (Subcontractor Progress Billings & Rental Licenses) ---
#=================================================================================
elif role == "Engineering":
    st.subheader("👷 Engineering Dashboard - Project Progress Billings")
    st.caption("Verify site accomplishment and generate subcontractor / rental progress billings directly for Accounting.")

    if st.button("🔄 Refresh Engineering Data", key="btn_refresh_engineering"):
        st.rerun()

    tab_eng_billing, tab_eng_history = st.tabs([
        "📝 Subcontractor & Rental Progress Billing", 
        "📜 Billing History & APV Status"
    ])

    # -------------------------------------------------------------------------
    # MODULE 1: PROGRESS BILLING ENTRY
    # -------------------------------------------------------------------------
    with tab_eng_billing:
        st.write("### 📐 Create Progress Billing / APV Requisition")
        st.info("Submit verified physical accomplishment billings for Labor-Only subcontractors or Rental/License agreements.")

        # 1. Project & Activity Selection
        col_proj, col_act = st.columns(2)
        
        # Extract plain string names from database tuples
        projects = [r[0] for r in c.execute("SELECT project_name FROM projects").fetchall()]
        if not projects:
            projects = ["No projects available"]
        selected_project = col_proj.selectbox("Select Project Site", projects, key="eng_proj_select")

        act_query = """
            SELECT a.activity_name 
            FROM activities a 
            JOIN projects p ON a.project_id = p.id 
            WHERE p.project_name = ?
        """
        activities = [r[0] for r in c.execute(act_query, (selected_project,)).fetchall()]
        if not activities:
            activities = ["General Project Works"]
        selected_activity = col_act.selectbox("Project Activity / Scope", activities, key="eng_act_select")

        st.markdown("---")
        st.write("#### 📋 2. Billing & Contractor Details")

        col_b1, col_b2 = st.columns(2)

        # Billing Type Selection
        billing_type = col_b1.selectbox(
            "Billing Type",
            [
                "Subcontractor (Labor Only)", 
                "Project Rental / License (Labor + Materials)"
            ],
            key="eng_billing_type"
        )

        # Contractor / Subcontractor Name Selection
        suppliers = [r[0] for r in c.execute("SELECT supplier_name FROM suppliers").fetchall()]
        if not suppliers:
            suppliers = ["No Contractors Registered"]
        selected_contractor = col_b2.selectbox("Subcontractor / Rental Owner", suppliers, key="eng_contractor_select")

        col_b3, col_b4 = st.columns([1, 2])
        billing_ref_no = col_b3.text_input("Billing / Invoice / Statement No.", placeholder="e.g. PB-001 or INV-2026-05", key="eng_bill_ref")
        billing_date = col_b4.date_input("Billing Date", value=datetime.now().date(), key="eng_bill_date")

        particulars = st.text_area(
            "Accomplishment Particulars / Scope Covered", 
            placeholder="e.g. 1st Progress Billing for CHB Laying & Plastering (50% accomplishment verified on-site)",
            key="eng_particulars"
        )

        st.markdown("---")
        st.write("#### 💵 3. Financial Computations & Withholding Deductions")

        col_c1, col_c2, col_c3 = st.columns(3)

        gross_amount = col_c1.number_input("Gross Accomplishment / Billing Amount (₱)", min_value=0.0, step=1000.0, value=0.0, key="eng_gross_amt")

        # Deductions: Retainage (10%) & EWT (2%)
        apply_retainage = col_c2.checkbox("Apply 10% Contract Retention Withholding", value=(billing_type == "Subcontractor (Labor Only)"), key="eng_apply_ret")
        apply_ewt = col_c3.checkbox("Apply 2% BIR Form 2307 Withholding Tax (WI160)", value=True, key="eng_apply_ewt")

        retainage_amount = round(gross_amount * 0.10, 2) if apply_retainage else 0.0
        ewt_amount = round(gross_amount * 0.02, 2) if apply_ewt else 0.0
        net_payable = max(0.0, round(gross_amount - retainage_amount - ewt_amount, 2))

        # Financial Summary Display Box
        st.info(f"""
        📊 **Billing Summary:**
        * **Gross Accomplishment:** ₱{gross_amount:,.2f}
        * **Less 10% Retention:** -₱{retainage_amount:,.2f}
        * **Less 2% BIR 2307 EWT:** -₱{ewt_amount:,.2f}
        * **NET PAYABLE TO CONTRACTOR:** **₱{net_payable:,.2f}**
        """)

        # Determine Accounting Category & Debit GL Account Code
        if billing_type == "Subcontractor (Labor Only)":
            accounting_category = "Subcontract & Services"
            debit_account_code = "60200" # Direct Subcontract / Labor Expense code
            debit_account_name = "Subcontract & Labor Expense"
        else:
            accounting_category = "Equipment & Rental"
            debit_account_code = "60200" # Equipment Rental Expense code
            debit_account_name = "Equipment & Rental Expense"

        if st.button("🚀 Submit Progress Billing to Accounting", type="primary", key="btn_submit_eng_billing"):
            if gross_amount <= 0:
                st.error("⚠️ Please enter a valid gross billing amount greater than ₱0.00.")
            elif not billing_ref_no.strip():
                st.error("⚠️ Please enter a Billing / Invoice reference number.")
            elif selected_contractor == "No Contractors Registered":
                st.error("⚠️ Please register a contractor in the Suppliers Master list first.")
            else:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                doc_ref = f"{'PB' if billing_type == 'Subcontractor (Labor Only)' else 'RNT'}#{billing_ref_no.strip()}"
                suggested_apv = generate_voucher_number(c, "apv_number", "APV")

                # 1. Record Header Entry in Deliveries Table for Accounting APV Queue
                c.execute("""
                    INSERT INTO deliveries 
                    (pono, supplier, project_name, dr_number, total_amount, received_date, payment_status, apv_number, apv_date) 
                    VALUES (?, ?, ?, ?, ?, ?, 'Unpaid', ?, ?)
                """, (
                    f"ENG-{selected_activity[:10]}", 
                    selected_contractor, 
                    selected_project, 
                    doc_ref, 
                    gross_amount, 
                    current_time, 
                    suggested_apv, 
                    current_time
                ))

                # 2. Record Double-Entry General Ledger Postings
                # Debit: Expense (Gross Amount)
                c.execute("""
                    INSERT INTO journal_entries 
                    (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name, supplier)
                    VALUES (?, ?, ?, ?, ?, 0.0, ?, ?, ?, ?)
                """, (current_time, suggested_apv, debit_account_code, debit_account_name, gross_amount, doc_ref, f"{billing_type}: {particulars}", selected_project, selected_contractor))

                # Credit: Accounts Payable-Trade (Net Payable Amount)
                c.execute("""
                    INSERT INTO journal_entries 
                    (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name, supplier)
                    VALUES (?, ?, '20100', 'Accounts Payable-Trade', 0.0, ?, ?, ?, ?, ?)
                """, (current_time, suggested_apv, net_payable, doc_ref, f"Payable accrued for {doc_ref}", selected_project, selected_contractor))

                # Credit: Withholding Tax Payable (2% EWT) if applicable
                if ewt_amount > 0:
                    c.execute("""
                        INSERT INTO journal_entries 
                        (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name, supplier)
                        VALUES (?, ?, '20400', 'Withholding Tax Payable - Expanded', 0.0, ?, ?, ?, ?, ?)
                    """, (current_time, suggested_apv, ewt_amount, doc_ref, f"2% EWT (WI160) withheld for {selected_contractor}", selected_project, selected_contractor))

                # Credit: Contract Retention Payable (10% Retention) if applicable
                if retainage_amount > 0:
                    c.execute("""
                        INSERT INTO journal_entries 
                        (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name, supplier)
                        VALUES (?, ?, '20500', 'Contract Retention Payable', 0.0, ?, ?, ?, ?, ?)
                    """, (current_time, suggested_apv, retainage_amount, doc_ref, f"10% Retainage withheld for {selected_contractor}", selected_project, selected_contractor))

                conn.commit()
                st.success(f"✅ Progress Billing ({doc_ref}) successfully recorded! Assigned APV #{suggested_apv}. Forwarded to Accounting.")
                st.rerun()

    # -------------------------------------------------------------------------
    # MODULE 2: BILLING HISTORY & APV TRACKING
    # -------------------------------------------------------------------------
    with tab_eng_history:
        st.write("### 📜 Progress Billing History & APV Status")

        history_df = pd.read_sql_query("""
            SELECT 
                d.apv_number AS 'APV No.',
                d.received_date AS 'Date Submitted',
                d.dr_number AS 'Billing Ref',
                d.supplier AS 'Contractor',
                d.project_name AS 'Project',
                d.total_amount AS 'Gross Amount',
                d.payment_status AS 'Payment Status',
                d.cv_number AS 'Payment Voucher No.'
            FROM deliveries d
            WHERE d.dr_number LIKE 'PB#%' OR d.dr_number LIKE 'RNT#%'
            ORDER BY d.id DESC
        """, conn)

        if not history_df.empty:
            st.dataframe(
                history_df.style.format({"Gross Amount": "₱{:,.2f}"}),
                width="stretch",
                hide_index=True
            )

            csv_eng = history_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Engineering Billing History (CSV)",
                data=csv_eng,
                file_name=f"engineering_progress_billings_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No subcontractor or rental progress billings recorded yet.")

#==========================HRIS========================
#=================================================================================
### --- ROLE: HRIS / PAYROLL (Worker Management, Timekeeping & Payroll) ---
#=================================================================================
elif role == "HRIS / Payroll":
    st.subheader("👷 HRIS & Labor Payroll Dashboard")
    st.caption("Manage worker profiles, biometric logs, daily timekeeping, site vale/advances, and batch payroll releases.")

    # 1. Ensure Required HRIS Database Tables Exist
    c.execute("""
    CREATE TABLE IF NOT EXISTS dtr_biometric_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id TEXT,
        emp_name TEXT,
        department TEXT,
        project_site TEXT,
        log_date TEXT,
        time_in TEXT,
        time_out TEXT,
        late_min INTEGER DEFAULT 0,
        early_min INTEGER DEFAULT 0,
        absent_min INTEGER DEFAULT 0,
        total_min INTEGER DEFAULT 0,
        source TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_name TEXT NOT NULL,
        worker_type TEXT,
        daily_rate REAL DEFAULT 0.0,
        sss_no TEXT,
        philhealth_no TEXT,
        pagibig_no TEXT,
        status TEXT DEFAULT 'Active'
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS timekeeping (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER,
        project_name TEXT,
        activity_name TEXT,
        work_date TEXT,
        days_worked REAL DEFAULT 1.0,
        ot_hours REAL DEFAULT 0.0,
        vale_amount REAL DEFAULT 0.0,
        status TEXT DEFAULT 'Pending'
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS payroll_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payroll_period TEXT,
        total_gross REAL,
        total_deductions REAL,
        total_net REAL,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()

    # 2. AUTO-MIGRATE: Add missing 'status' column to existing 'timekeeping' table if created previously
    try:
        c.execute("ALTER TABLE timekeeping ADD COLUMN status TEXT DEFAULT 'Pending'")
        conn.commit()
    except Exception:
        pass  # Column already exists

    if st.button("🔄 Refresh HRIS Data", key="btn_refresh_hris"):
        st.rerun()

    tab_workers, tab_biometrics, tab_timekeeping, tab_payroll, tab_Staff, tab_weather = st.tabs([
        "👤 Worker Profiles", 
        "📠 Biometric Logs (USB & LAN)",
        "⏱️ Daily Timekeeping & Vale", 
        "💵 Payroll Processing & Accounting Release",
        "💼 Office Staff Payroll", 
        "🌤 Site Weather Logs"  # <--- NEW 5th TAB
    ])

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # TAB 1: WORKER PROFILES MASTER
    # -------------------------------------------------------------------------
    with tab_workers:
        # 1. Safely add new columns to database if they don't exist yet
        try:
            c.execute("ALTER TABLE workers ADD COLUMN pay_type TEXT DEFAULT 'Daily Rate'")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE workers ADD COLUMN monthly_rate REAL DEFAULT 0.0")
        except Exception:
            pass
        conn.commit()

        st.write("### 👤 Register / Edit Field & Office Workers")
        
        with st.form("form_add_worker", clear_on_submit=True):
            col_w1, col_w2, col_w3 = st.columns(3)
            worker_name = col_w1.text_input("Worker Full Name *", placeholder="e.g. Juan Dela Cruz")
            worker_type = col_w2.selectbox("Worker Classification", ["Skilled", "Unskilled", "Foreman", "Leadman", "Office Staff"])
            pay_type = col_w3.selectbox("Pay Type *", ["Daily Rate", "Monthly Rate"], index=0)

            col_r1, col_r2 = st.columns([1, 2])
            if pay_type == "Daily Rate":
                daily_rate = col_r1.number_input("Daily Rate (₱) *", min_value=0.0, step=50.0, value=600.0)
                monthly_rate = 0.0
                col_r2.info(f"💡 Standard Field Rate: **₱{daily_rate:,.2f} / day**")
            else:
                monthly_rate = col_r1.number_input("Monthly Salary (₱) *", min_value=0.0, step=500.0, value=25000.0)
                # Calculate estimated daily equivalent for timekeeping (26 days standard)
                daily_rate = monthly_rate / 26.0 if monthly_rate > 0 else 0.0
                col_r2.info(f"💡 Monthly Salary: **₱{monthly_rate:,.2f} / mo** (~₱{daily_rate:,.2f}/day for 26 days)")

            col_w4, col_w5, col_w6 = st.columns(3)
            sss_no = col_w4.text_input("SSS No.", placeholder="00-0000000-0")
            philhealth_no = col_w5.text_input("PhilHealth No.", placeholder="00-000000000-0")
            pagibig_no = col_w6.text_input("Pag-IBIG No.", placeholder="0000-0000-0000")

            btn_save_worker = st.form_submit_button("💾 Register Worker", type="primary")

            if btn_save_worker:
                if not worker_name.strip():
                    st.error("⚠️ Please enter a worker name.")
                elif pay_type == "Daily Rate" and daily_rate <= 0:
                    st.error("⚠️ Daily rate must be greater than ₱0.00.")
                elif pay_type == "Monthly Rate" and monthly_rate <= 0:
                    st.error("⚠️ Monthly salary must be greater than ₱0.00.")
                else:
                    try:
                        c.execute("""
                            INSERT INTO workers (worker_name, worker_type, pay_type, daily_rate, monthly_rate, sss_no, philhealth_no, pagibig_no, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active')
                        """, (worker_name.strip(), worker_type, pay_type, daily_rate, monthly_rate, sss_no.strip(), philhealth_no.strip(), pagibig_no.strip()))
                        conn.commit()
                        st.success(f"✅ Worker '{worker_name}' ({pay_type}) successfully registered!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Error registering worker: {e}")

        st.markdown("---")
        st.write("#### 📋 Registered Workers Masterlist")
        
        workers_df = pd.read_sql_query("""
            SELECT id AS 'ID', 
                   worker_name AS 'Worker Name', 
                   worker_type AS 'Classification',
                   COALESCE(pay_type, 'Daily Rate') AS 'Pay Type',
                   CASE 
                       WHEN pay_type = 'Monthly Rate' THEN '₱' || printf('%,.2f', COALESCE(monthly_rate, 0.0)) || ' / mo'
                       ELSE '₱' || printf('%,.2f', COALESCE(daily_rate, 0.0)) || ' / day'
                   END AS 'Rate Display',
                   sss_no AS 'SSS No.', 
                   philhealth_no AS 'PhilHealth No.', 
                   pagibig_no AS 'Pag-IBIG No.', 
                   status AS 'Status'
            FROM workers ORDER BY id DESC
        """, conn)

        if not workers_df.empty:
            st.dataframe(
                workers_df,
                width="stretch",
                hide_index=True
            )
        else:
            st.info("No workers registered yet.")

    # -------------------------------------------------------------------------
    # TAB 2: BIOMETRIC LOGS (USB EXCEL IMPORT & LAN DIRECT SYNC)
    # -------------------------------------------------------------------------
    with tab_biometrics:
        st.write("### 📠 Biometric Data Sync & Import Center")

        subtab_usb, subtab_lan, subtab_view = st.tabs([
            "📁 Project Sites (USB Excel Import)", 
            "🔌 Sitting Office (LAN Direct Sync)",
            "📋 View Saved Biometric Database Logs"
        ])

        # --- Subtab A: USB File Upload ---
        with subtab_usb:
            st.caption("Import software reports (e.g. `1_StandardReport - Laray.xls`) from field USB flash drives.")

            col_b1, col_b2 = st.columns(2)
            try:
                projects_bio = [r[0] for r in c.execute("SELECT project_name FROM projects").fetchall()]
            except Exception:
                projects_bio = []
            
            if not projects_bio:
                projects_bio = ["Laray Project Site", "General Work Site"]

            selected_bio_project = col_b1.selectbox("Target Project Site:", projects_bio, key="bio_project_select")
            uploaded_bio_file = col_b2.file_uploader("Upload Biometric Excel File (.xls / .xlsx)", type=["xls", "xlsx"], key="bio_file_uploader")

            if uploaded_bio_file:
                try:
                    df_exc = None
                    try:
                        df_exc = pd.read_excel(uploaded_bio_file, sheet_name='Exception Stat.', header=None)
                    except Exception:
                        try:
                            uploaded_bio_file.seek(0)
                            df_exc = pd.read_excel(uploaded_bio_file, sheet_name=0, header=None)
                        except Exception:
                            uploaded_bio_file.seek(0)
                            tables = pd.read_html(uploaded_bio_file)
                            if tables:
                                df_exc = tables[0]

                    if df_exc is not None and not df_exc.empty:
                        data_df = df_exc.iloc[3:].copy()
                        headers = [
                            "emp_id", "emp_name", "department", "log_date", 
                            "time_in", "time_out", "second_in", "second_out", 
                            "late_min", "early_min", "absent_min", "total_min", "note"
                        ]
                        
                        data_df = data_df.iloc[:, :len(headers)]
                        data_df.columns = headers[:data_df.shape[1]]
                        data_df = data_df.dropna(subset=['emp_id', 'log_date'])

                        st.write("🔍 **Preview Parsed Attendance Records:**")
                        preview_cols = [col for col in ["emp_id", "emp_name", "department", "log_date", "time_in", "time_out", "late_min", "early_min", "absent_min"] if col in data_df.columns]
                        st.dataframe(
                            data_df[preview_cols].head(15),
                            width="stretch",
                            hide_index=True
                        )

                        col_save1, col_save2 = st.columns(2)
                        
                        if col_save1.button("💾 Save to Biometric Database", type="primary", key="btn_save_bio_db"):
                            inserted_count = 0
                            for _, row in data_df.iterrows():
                                t_in = str(row['time_in']) if pd.notna(row.get('time_in')) else 'ABSENT'
                                t_out = str(row['time_out']) if pd.notna(row.get('time_out')) else 'ABSENT'
                                late = int(row['late_min']) if pd.notna(row.get('late_min')) and str(row['late_min']).isdigit() else 0
                                early = int(row['early_min']) if pd.notna(row.get('early_min')) and str(row['early_min']).isdigit() else 0
                                absent = int(row['absent_min']) if pd.notna(row.get('absent_min')) and str(row['absent_min']).isdigit() else 0
                                total = int(row['total_min']) if pd.notna(row.get('total_min')) and str(row['total_min']).isdigit() else 0

                                c.execute("""
                                    INSERT INTO dtr_biometric_logs 
                                    (emp_id, emp_name, department, project_site, log_date, time_in, time_out, late_min, early_min, absent_min, total_min, source)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'USB_EXCEL')
                                """, (
                                    str(row.get('emp_id', '')), str(row.get('emp_name', '')), str(row.get('department', '')),
                                    selected_bio_project, str(row.get('log_date', ''))[:10], t_in, t_out,
                                    late, early, absent, total
                                ))
                                inserted_count += 1

                            conn.commit()
                            st.success(f"✅ Imported {inserted_count} attendance records for **{selected_bio_project}**!")
                            st.rerun()
                    else:
                        st.error("⚠️ Could not read attendance rows from this file format.")

                except Exception as e:
                    st.error(f"⚠️ Error reading biometric file: {e}")

        # --- Subtab B: Sitting Office Machine LAN Sync ---
        # --- Subtab B: Sitting Office Machine LAN Sync ---
        with subtab_lan:
            import calendar
            from datetime import datetime, date

            st.caption("Connect live to the sitting office biometric terminal on your office local network.")
            
            # Connection Settings
            col_l1, col_l2, col_l3 = st.columns(3)
            lan_ip = col_l1.text_input("Biometric IP Address", value="192.168.3.254", key="lan_ip_input")
            lan_port = col_l2.number_input("Port", value=4370, key="lan_port_input")
            lan_password = col_l3.text_input("Comm Password", value="1234", type="password", key="lan_pass_input")

            st.markdown("---")
            st.write("📅 **Filter Target Payroll Cutoff Period**")
            
            col_f1, col_f2, col_f3 = st.columns(3)
            
            current_year = datetime.now().year
            current_month = datetime.now().month
            
            selected_year = col_f1.selectbox("Select Year", range(current_year - 2, current_year + 3), index=2, key="lan_year")
            
            months = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
            selected_month_str = col_f2.selectbox("Select Month", months, index=current_month - 1, key="lan_month")
            selected_month = months.index(selected_month_str) + 1
            
            period_option = col_f3.selectbox(
                "Cutoff Period", 
                ["All Machine Logs (No Filter)", "1st - 15th (1st Half)", "16th - End of Month (2nd Half)", "Entire Month"],
                key="lan_period"
            )

            last_day_of_month = calendar.monthrange(selected_year, selected_month)[1]
            
            if period_option == "1st - 15th (1st Half)":
                filter_start = date(selected_year, selected_month, 1)
                filter_end = date(selected_year, selected_month, 15)
            elif period_option == "16th - End of Month (2nd Half)":
                filter_start = date(selected_year, selected_month, 16)
                filter_end = date(selected_year, selected_month, last_day_of_month)
            elif period_option == "Entire Month":
                filter_start = date(selected_year, selected_month, 1)
                filter_end = date(selected_year, selected_month, last_day_of_month)
            else:
                filter_start = None
                filter_end = None

            if filter_start and filter_end:
                st.info(f"🎯 Selected Range: **{filter_start.strftime('%B %d, %Y')}** to **{filter_end.strftime('%B %d, %Y')}**")
            else:
                st.info("🌐 Selected Range: **All Logs Available on Machine**")

            st.markdown("---")
            col_act1, col_act2 = st.columns([2, 2])

            # Button 1: Pull Attendance Logs Over LAN
            if col_act1.button("🔌 Pull Attendance Logs Over LAN", type="primary", key="btn_sync_lan"):
                try:
                    from zk import ZK
                    
                    # Create live status container for visual progress feedback
                    with st.status("📡 Connecting to Biometric Terminal...", expanded=True) as status:
                        comm_key = int(lan_password) if lan_password.isdigit() else 0
                        zk = ZK(lan_ip, port=int(lan_port), timeout=15, password=comm_key, ommit_ping=True)
                        conn_zk = zk.connect()
                        
                        status.write("👤 Fetching employee profile names...")
                        users = conn_zk.get_users()
                        user_map = {str(u.user_id): u.name for u in users}
                        
                        status.write("📥 Pulling raw logs from hardware memory...")
                        attendance = conn_zk.get_attendance()

                        inserted_lan = 0
                        skipped_duplicates = 0
                        skipped_date_filter = 0
                        total_logs = len(attendance)

                        status.write(f"⚙️ Filtering and inserting {total_logs:,} records into database...")
                        
                        # Add progress bar for processing loop
                        progress_bar = st.progress(0)
                        
                        for idx, log in enumerate(attendance):
                            # Update visual progress bar percentage
                            if total_logs > 0:
                                progress_bar.progress((idx + 1) / total_logs)

                            log_date_obj = log.timestamp.date()
                            
                            if filter_start and filter_end:
                                if not (filter_start <= log_date_obj <= filter_end):
                                    skipped_date_filter += 1
                                    continue

                            emp_id_str = str(log.user_id)
                            worker_name = user_map.get(emp_id_str, f"Worker #{emp_id_str}")
                            log_date_str = log.timestamp.strftime("%Y-%m-%d")
                            time_in_str = log.timestamp.strftime("%H:%M:%S")

                            c.execute("""
                                SELECT 1 FROM dtr_biometric_logs 
                                WHERE emp_id = ? AND log_date = ? AND time_in = ? AND source = 'LAN_DIRECT'
                            """, (emp_id_str, log_date_str, time_in_str))
                            
                            if c.fetchone():
                                skipped_duplicates += 1
                                continue

                            c.execute("""
                                INSERT INTO dtr_biometric_logs 
                                (emp_id, emp_name, department, project_site, log_date, time_in, source)
                                VALUES (?, ?, 'Main Office', 'Sitting Office', ?, ?, 'LAN_DIRECT')
                            """, (emp_id_str, worker_name, log_date_str, time_in_str))
                            inserted_lan += 1

                        conn_zk.disconnect()
                        conn.commit()
                        
                        # Clean up progress bar after completion
                        progress_bar.empty()
                        status.update(label="✅ Data sync complete!", state="complete", expanded=False)
                    
                    if inserted_lan > 0:
                        st.success(f"⚡ Successfully imported **{inserted_lan}** new punches! (Skipped: {skipped_duplicates} duplicates, {skipped_date_filter} outside date range)")
                    else:
                        st.warning(f"⚠️ No new logs inserted. ({skipped_duplicates} existing duplicates skipped, {skipped_date_filter} logs skipped by date filter)")
                    
                    st.cache_data.clear()
                    
                except Exception as e:
                    st.error(f"⚠️ Could not connect to machine on network ({e}).")

            # Button 2: Delete Old 'Office Staff' Placeholder Logs
            if col_act2.button("🧹 Clear 'Office Staff' Placeholder Logs", key="btn_clear_office_staff"):
                try:
                    c.execute("DELETE FROM dtr_biometric_logs WHERE emp_name = 'Office Staff'")
                    deleted_count = c.rowcount
                    conn.commit()
                    st.cache_data.clear()
                    st.success(f"🗑️ Successfully removed {deleted_count} 'Office Staff' test logs from database!")
                except Exception as e:
                    st.error(f"⚠️ Could not delete logs: {e}")
        
        # --- Subtab C: View Saved Biometric Database Logs ---
        with subtab_view:
            import pandas as pd

            st.caption("Browse, filter, and manage all historical biometric punch records stored in your database.")

            # Query all saved logs sorted by date and time
            df_logs = pd.read_sql_query("""
                SELECT 
                    id AS [Log ID],
                    emp_id AS [Emp ID],
                    emp_name AS [Worker Name],
                    department AS [Department],
                    project_site AS [Project Site],
                    log_date AS [Date],
                    time_in AS [Time In],
                    source AS [Source]
                FROM dtr_biometric_logs 
                ORDER BY log_date DESC, time_in DESC
            """, conn)

            if df_logs.empty:
                st.warning("⚠️ No biometric logs currently saved in the database. Use **USB Excel Import** or **LAN Direct Sync** to import logs.")
            else:
                st.success(f"📊 Total Saved Database Records: **{len(df_logs):,}** rows")

                # Filters Section
                col_f1, col_f2, col_f3 = st.columns(3)

                # Filter 1: Source (USB vs LAN Direct)
                sources = ["All Sources"] + list(df_logs["Source"].dropna().unique())
                sel_source = col_f1.selectbox("Filter Source", sources, key="view_src_filter")

                # Filter 2: Search Name or ID
                search_query = col_f2.text_input("🔍 Search Worker Name or ID", "", key="view_search_input")

                # Filter 3: Row Limit to keep Streamlit snappy
                display_limit = col_f3.number_input("Max Display Rows", value=1000, step=500, key="view_limit_input")

                # Apply Filters
                filtered_df = df_logs.copy()

                if sel_source != "All Sources":
                    filtered_df = filtered_df[filtered_df["Source"] == sel_source]

                if search_query:
                    search_mask = (
                        filtered_df["Worker Name"].astype(str).str.contains(search_query, case=False, na=False) |
                        filtered_df["Emp ID"].astype(str).str.contains(search_query, case=False, na=False)
                    )
                    filtered_df = filtered_df[search_mask]

                # Render Table
                st.dataframe(
                    filtered_df.head(int(display_limit)),
                    width="stretch",
                    hide_index=True,
                    height=450
                )

                st.markdown("---")
                
                # Database Cleanup Control
                with st.expander("🗑️ Database Management & Log Cleanup Options"):
                    col_del1, col_del2 = st.columns(2)
                    
                    if col_del1.button("🧹 Clear All Saved LAN Logs (`LAN_DIRECT`)", key="btn_clear_all_lan"):
                        c.execute("DELETE FROM dtr_biometric_logs WHERE source = 'LAN_DIRECT'")
                        deleted = c.rowcount
                        conn.commit()
                        st.cache_data.clear()
                        st.success(f"Deleted {deleted:,} LAN logs! Refreshing...")
                        st.rerun()

                    if col_del2.button("⚠️ Clear Entire Biometric Database Table", key="btn_clear_entire_db"):
                        c.execute("DELETE FROM dtr_biometric_logs")
                        deleted = c.rowcount
                        conn.commit()
                        st.cache_data.clear()
                        st.success(f"Cleared all {deleted:,} biometric entries!")
                        st.rerun()
                        
    # -------------------------------------------------------------------------
    # TAB 3: DAILY TIMEKEEPING & VALE ENTRY
    # -------------------------------------------------------------------------
    # TAB 3: DAILY TIMEKEEPING & VALE ENTRY
    # -------------------------------------------------------------------------
    with tab_timekeeping:
        st.write("### ⏱️️ Record Project Timekeeping & Vale Advances")

        # Create subtabs: Automated LAN Sync Engine vs Manual Entry
        subtab_auto, subtab_manual = st.tabs(["⚡ Auto-Process LAN Biometrics", "📝 Manual Entry & Vale"])

        # ---------------------------------------------------------------------
        # SUBTAB 1: AUTOMATED LAN BIOMETRIC PROCESSING
        # ---------------------------------------------------------------------
        # SUBTAB 1: AUTOMATED LAN BIOMETRIC PROCESSING
        # ---------------------------------------------------------------------
        with subtab_auto:
            st.caption("Automatically pair raw LAN biometric punches (First IN / Last OUT) into daily timekeeping entries for both field and office staff.")
            
            col_ap1, col_ap2, col_ap3 = st.columns(3)
            start_date = col_ap1.date_input("Start Date", value=datetime.now().date().replace(day=16 if datetime.now().day > 15 else 1), key="tk_auto_start")
            end_date = col_ap2.date_input("End Date", value=datetime.now().date(), key="tk_auto_end")

            # Fetch project sites from database and prepend standard office locations
            try:
                db_projects = [r[0] for r in c.execute("SELECT project_name FROM projects").fetchall()]
            except Exception:
                db_projects = []

            # Define default office sites and combine with active project sites (removing duplicates)
            office_sites = ["Sitting Office", "Main Office", "Head Office"]
            site_options = office_sites + [p for p in db_projects if p not in office_sites]

            default_proj = col_ap3.selectbox("Default Site / Department", site_options, key="tk_auto_proj")
            
            if st.button("⚡ Batch Process LAN Biometrics", type="primary", key="btn_process_lan_bio"):
                # Dynamically inspect columns in dtr_biometric_logs to prevent schema errors
                try:
                    table_info = c.execute("PRAGMA table_info(dtr_biometric_logs)").fetchall()
                    bio_cols = [r[1] for r in table_info]
                except Exception:
                    bio_cols = []

                if not bio_cols:
                    st.error("⚠️ Table 'dtr_biometric_logs' does not exist or has no columns.")
                else:
                    # Dynamically match column variations safely
                    name_col = next((col for col in ['worker_name', 'employee_name', 'name', 'user_id', 'worker'] if col in bio_cols), bio_cols[1] if len(bio_cols) > 1 else bio_cols[0])
                    date_col = next((col for col in ['date', 'work_date', 'log_date', 'punch_date'] if col in bio_cols), 'date')
                    time_col = next((col for col in ['time_in', 'punch_time', 'time', 'log_time', 'time_out'] if col in bio_cols), 'time_in')

                    # Apply source filter only if the source column exists in schema
                    if 'source' in bio_cols:
                        where_clause = f"WHERE source = 'LAN_DIRECT' AND {date_col} BETWEEN ? AND ?"
                    else:
                        where_clause = f"WHERE {date_col} BETWEEN ? AND ?"

                    query = f"""
                        SELECT 
                            {name_col} AS worker_name,
                            {date_col} AS work_date,
                            MIN({time_col}) AS first_in,
                            MAX({time_col}) AS last_out,
                            COUNT(*) as punch_count
                        FROM dtr_biometric_logs
                        {where_clause}
                        GROUP BY {name_col}, {date_col}
                        ORDER BY {date_col} ASC, {name_col} ASC
                    """

                    raw_bio_df = pd.read_sql_query(query, conn, params=(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

                    if raw_bio_df.empty:
                        st.warning("⚠️ No LAN biometric records found for the selected date range.")
                    else:
                        # Fetch active workers from DB
                        active_workers = pd.read_sql_query("SELECT id, worker_name, COALESCE(pay_type, 'Daily Rate') as pay_type FROM workers WHERE status='Active'", conn)
                        
                        if active_workers.empty:
                            st.error("⚠️ No active registered workers found. Please add workers in Worker Profiles first.")
                        else:
                            def clean_str(s):
                                return "".join(char for char in str(s).upper() if char.isalnum())

                            active_workers['clean_name'] = active_workers['worker_name'].apply(clean_str)

                            inserted_count = 0
                            updated_count = 0
                            skipped_names = set()

                            for _, row in raw_bio_df.iterrows():
                                bio_raw_name = row['worker_name']
                                b_date = str(row['work_date'])
                                t_in = str(row['first_in'])
                                t_out = str(row['last_out'])
                                clean_bio = clean_str(bio_raw_name)

                                # Match registered worker
                                matched_worker = active_workers[active_workers['clean_name'] == clean_bio]
                                if matched_worker.empty:
                                    matched_worker = active_workers[
                                        active_workers['clean_name'].apply(lambda x: clean_bio in x or x in clean_bio if len(clean_bio) > 3 else False)
                                    ]

                                if not matched_worker.empty:
                                    w_id = int(matched_worker.iloc[0]['id'])

                                    # Calculate work shift duration
                                    try:
                                        t1 = datetime.strptime(t_in.split('.')[0], "%H:%M:%S")
                                        t2 = datetime.strptime(t_out.split('.')[0], "%H:%M:%S")
                                        hours = (t2 - t1).total_seconds() / 3600.0
                                    except Exception:
                                        hours = 8.0

                                    if hours <= 0:
                                        hours = 8.0

                                    # Lunch break deduction (1 hr if shift > 5 hrs)
                                    net_hours = max(0.0, hours - 1.0) if hours > 5 else hours

                                    # Calculate days worked and OT
                                    if net_hours >= 7.5:
                                        calc_days = 1.0
                                        calc_ot = round(max(0.0, net_hours - 8.0), 2)
                                    else:
                                        calc_days = round(net_hours / 8.0, 2)
                                        calc_ot = 0.0

                                    # Upsert into timekeeping
                                    existing = c.execute("""
                                        SELECT id FROM timekeeping WHERE worker_id = ? AND work_date = ?
                                    """, (w_id, b_date)).fetchone()

                                    if existing:
                                        c.execute("""
                                            UPDATE timekeeping 
                                            SET days_worked = ?, ot_hours = ?, project_name = ?
                                            WHERE id = ? AND (status = 'Pending' OR status IS NULL)
                                        """, (calc_days, calc_ot, default_proj, existing[0]))
                                        updated_count += 1
                                    else:
                                        c.execute("""
                                            INSERT INTO timekeeping (worker_id, project_name, activity_name, work_date, days_worked, ot_hours, vale_amount, status)
                                            VALUES (?, ?, 'Biometric Clock-In', ?, ?, ?, 0.0, 'Pending')
                                        """, (w_id, default_proj, b_date, calc_days, calc_ot))
                                        inserted_count += 1
                                else:
                                    skipped_names.add(str(bio_raw_name))

                            conn.commit()
                            st.cache_data.clear()
                            st.success(f"🎉 Biometric processing complete! Generated **{inserted_count} new entries** and updated **{updated_count} existing records**.")
                            
                            if skipped_names:
                                st.warning(f"⚠️ Unmatched biometric names (add them to Worker Profiles): **{', '.join(skipped_names)}**")
                            
                            st.rerun()

        # ---------------------------------------------------------------------
        # SUBTAB 2: MANUAL TIMEKEEPING & VALE ENTRY (ORIGINAL FORM)
        # ---------------------------------------------------------------------
        with subtab_manual:
            col_t1, col_t2 = st.columns(2)
            
            # Query workers including their pay type
            workers_data = c.execute("SELECT id, worker_name, daily_rate, COALESCE(pay_type, 'Daily Rate') FROM workers WHERE status='Active'").fetchall()
            worker_list = []
            for r in workers_data:
                w_id, w_name, w_rate, w_ptype = r[0], r[1], r[2], r[3]
                if w_ptype == 'Monthly Rate':
                    worker_list.append(f"{w_id} | {w_name} (Monthly Staff)")
                else:
                    worker_list.append(f"{w_id} | {w_name} (₱{w_rate:,.2f}/day)")

            if not worker_list:
                st.warning("⚠️ No active workers available. Please add workers in Worker Profiles first.")
            else:
                selected_worker_str = col_t1.selectbox("Select Worker", worker_list, key="tk_worker_select")
                worker_id = int(selected_worker_str.split(" | ")[0])

                try:
                    projects = [r[0] for r in c.execute("SELECT project_name FROM projects").fetchall()]
                except Exception:
                    projects = []
                if not projects:
                    projects = ["General Work Site"]
                selected_project = col_t2.selectbox("Project Site Location", projects, key="tk_proj_select")

                col_t3, col_t4 = st.columns(2)
                
                try:
                    act_query = "SELECT a.activity_name FROM activities a JOIN projects p ON a.project_id = p.id WHERE p.project_name = ?"
                    activities = [r[0] for r in c.execute(act_query, (selected_project,)).fetchall()]
                except Exception:
                    activities = []
                if not activities:
                    activities = ["General Operations"]
                selected_activity = col_t3.selectbox("Activity / Scope", activities, key="tk_act_select")
                
                work_date = col_t4.date_input("Work Date", value=datetime.now().date(), key="tk_work_date")

                st.markdown("---")
                st.write("#### 📊 Hours & Cash Advance (Vale)")

                col_m1, col_m2, col_m3 = st.columns(3)
                days_worked = col_m1.number_input("Days Worked", min_value=0.0, max_value=1.5, step=0.5, value=1.0, key="tk_days")
                ot_hours = col_m2.number_input("Overtime Hours", min_value=0.0, max_value=12.0, step=0.5, value=0.0, key="tk_ot")
                vale_amount = col_m3.number_input("Vale / Cash Advance (₱)", min_value=0.0, step=100.0, value=0.0, key="tk_vale")

                if st.button("📝 Record Timekeeping Entry", type="primary", key="btn_save_timekeeping"):
                    c.execute("""
                        INSERT INTO timekeeping (worker_id, project_name, activity_name, work_date, days_worked, ot_hours, vale_amount, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')
                    """, (worker_id, selected_project, selected_activity, work_date.strftime('%Y-%m-%d'), days_worked, ot_hours, vale_amount))
                    conn.commit()
                    worker_display_name = selected_worker_str.split(" | ")[1].split(" (")[0]
                    st.success(f"✅ Recorded timekeeping entry for {worker_display_name}!")
                    st.rerun()

        st.markdown("---")
        st.write("#### 📜 Recent Unprocessed Timekeeping Logs")
        
        tk_df = pd.read_sql_query("""
            SELECT t.id AS 'Log ID', 
                   t.work_date AS 'Date', 
                   w.worker_name AS 'Worker', 
                   COALESCE(w.pay_type, 'Daily Rate') AS 'Pay Type',
                   t.project_name AS 'Project', 
                   t.days_worked AS 'Days Worked', 
                   t.ot_hours AS 'OT Hours', 
                   t.vale_amount AS 'Vale Amount', 
                   t.status AS 'Status'
            FROM timekeeping t
            JOIN workers w ON t.worker_id = w.id
            WHERE t.status = 'Pending' OR t.status IS NULL
            ORDER BY t.id DESC LIMIT 20
        """, conn)

        if not tk_df.empty:
            st.dataframe(
                tk_df.style.format({"Vale Amount": "₱{:,.2f}"}),
                width="stretch",
                hide_index=True
            )
        else:
            st.info("No unbilled/pending timekeeping entries found.")

    # -------------------------------------------------------------------------
    # TAB 4: PAYROLL PROCESSING & ACCOUNTING RELEASE
    # -------------------------------------------------------------------------
    # TAB 4: PAYROLL PROCESSING & ACCOUNTING RELEASE
    # -------------------------------------------------------------------------
    with tab_payroll:
        st.write("### 💵 Payroll Batch Summary & Accounting Release")

        col_p1, col_p2, col_p3 = st.columns(3)
        start_date = col_p1.date_input("Payroll Period Start", value=datetime.now().date().replace(day=16 if datetime.now().day > 15 else 1), key="pr_start")
        end_date = col_p2.date_input("Payroll Period End", value=datetime.now().date(), key="pr_end")
        expected_days = col_p3.number_input("Expected Period Workdays", min_value=1.0, max_value=16.0, value=13.0, step=0.5, help="Standard working days in this cutoff (default: 13 days for a 15-day period). Used to compute monthly staff absences.")

        payroll_period_str = f"{start_date.strftime('%Y/%m/%d')} - {end_date.strftime('%Y/%m/%d')}"

        # Updated query to pull pay_type and monthly_rate safely
        calc_query = """
            SELECT 
                w.id AS worker_id,
                w.worker_name,
                COALESCE(w.pay_type, 'Daily Rate') AS pay_type,
                COALESCE(w.daily_rate, 0.0) AS daily_rate,
                COALESCE(w.monthly_rate, 0.0) AS monthly_rate,
                SUM(t.days_worked) AS total_days,
                SUM(t.ot_hours) AS total_ot,
                SUM(t.vale_amount) AS total_vale
            FROM timekeeping t
            JOIN workers w ON t.worker_id = w.id
            WHERE t.work_date BETWEEN ? AND ? AND (t.status = 'Pending' OR t.status IS NULL)
            GROUP BY w.id, w.worker_name, w.pay_type, w.daily_rate, w.monthly_rate
        """
        raw_payroll = c.execute(calc_query, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))).fetchall()

        if raw_payroll:
            payroll_rows = []
            total_gross = 0.0
            total_deductions = 0.0
            total_net = 0.0

            for r in raw_payroll:
                w_id, name, ptype, d_rate, m_rate, days, ot, vale = r
                days = days or 0.0
                ot = ot or 0.0
                vale = vale or 0.0

                if ptype == 'Monthly Rate':
                    # Semi-Monthly Base Calculation (Monthly Salary / 2)
                    semi_monthly_base = m_rate / 2.0
                    daily_equiv = m_rate / 26.0 if m_rate > 0 else 0.0
                    hourly_equiv = daily_equiv / 8.0

                    # Calculate missing/unworked days deduction
                    lacking_days = max(0.0, float(expected_days) - float(days))
                    absence_deduction = lacking_days * daily_equiv

                    basic_pay = max(0.0, semi_monthly_base - absence_deduction)
                    ot_pay = ot * (hourly_equiv * 1.25)
                    rate_display = f"₱{m_rate:,.2f}/mo"
                else:
                    # Daily Worker Calculation
                    basic_pay = days * d_rate
                    ot_pay = ot * (d_rate / 8.0 * 1.25)
                    rate_display = f"₱{d_rate:,.2f}/day"

                gross_pay = basic_pay + ot_pay
                deductions = min(gross_pay, vale)
                net_pay = gross_pay - deductions

                total_gross += gross_pay
                total_deductions += deductions
                total_net += net_pay

                payroll_rows.append({
                    "Worker Name": name,
                    "Pay Type": ptype,
                    "Base Rate": rate_display,
                    "Days Worked": round(days, 2),
                    "OT Hours": round(ot, 2),
                    "Gross Pay": gross_pay,
                    "Less: Vale": deductions,
                    "Net Pay": net_pay
                })

            summary_df = pd.DataFrame(payroll_rows)

            st.dataframe(
                summary_df.style.format({
                    "Days Worked": "{:.1f}",
                    "OT Hours": "{:.1f}",
                    "Gross Pay": "₱{:,.2f}",
                    "Less: Vale": "₱{:,.2f}",
                    "Net Pay": "₱{:,.2f}"
                }),
                width="stretch",
                hide_index=True
            )

            st.info(f"""
            📊 **Batch Payroll Total:**
            * **Gross Payroll:** ₱{total_gross:,.2f}
            * **Total Deductions / Vale Recovered:** -₱{total_deductions:,.2f}
            * **NET CASH PAYROLL RELEASE:** **₱{total_net:,.2f}**
            """)

            if st.button("🚀 Submit Payroll to Accounting (APV Release)", type="primary", key="btn_submit_payroll"):
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                try:
                    suggested_apv = generate_voucher_number(c, "apv_number", "APV")
                except Exception:
                    suggested_apv = f"APV-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                doc_ref = f"PAYROLL#{start_date.strftime('%m%d')}-{end_date.strftime('%m%d')}"

                c.execute("""
                    INSERT INTO deliveries 
                    (pono, supplier, project_name, dr_number, total_amount, received_date, payment_status, apv_number, apv_date)
                    VALUES (?, 'Direct Labor Payroll', 'Multiple Projects', ?, ?, ?, 'Unpaid', ?, ?)
                """, (
                    f"PAY-{start_date.strftime('%Y%m%d')}", 
                    doc_ref, 
                    total_net, 
                    current_time, 
                    suggested_apv, 
                    current_time
                ))

                c.execute("""
                    INSERT INTO journal_entries 
                    (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name, supplier)
                    VALUES (?, ?, '60100', 'Direct Labor Expense', ?, 0.0, ?, ?, 'Multiple Projects', 'Direct Labor Payroll')
                """, (current_time, suggested_apv, total_gross, doc_ref, f"Labor Payroll for period {payroll_period_str}"))

                c.execute("""
                    INSERT INTO journal_entries 
                    (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name, supplier)
                    VALUES (?, ?, '20100', 'Accounts Payable-Trade', 0.0, ?, ?, ?, 'Multiple Projects', 'Direct Labor Payroll')
                """, (current_time, suggested_apv, total_net, doc_ref, f"Net payroll payable for period {payroll_period_str}"))

                if total_deductions > 0:
                    c.execute("""
                        INSERT INTO journal_entries 
                        (entry_date, voucher_no, account_code, account_name, debit, credit, ref_no, description, project_name, supplier)
                        VALUES (?, ?, '10300', 'Advances to Workers / Vale', 0.0, ?, ?, ?, 'Multiple Projects', 'Direct Labor Payroll')
                    """, (current_time, suggested_apv, total_deductions, doc_ref, f"Vale deductions recovered for period {payroll_period_str}"))

                c.execute("""
                    INSERT INTO payroll_runs (payroll_period, total_gross, total_deductions, total_net, status)
                    VALUES (?, ?, ?, ?, 'Submitted to Accounting')
                """, (payroll_period_str, total_gross, total_deductions, total_net))

                c.execute("""
                    UPDATE timekeeping 
                    SET status = 'Processed'
                    WHERE work_date BETWEEN ? AND ? AND (status = 'Pending' OR status IS NULL)
                """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

                conn.commit()
                st.cache_data.clear()
                st.success(f"✅ Payroll Batch ({doc_ref}) submitted! Created APV #{suggested_apv} for ₱{total_net:,.2f}.")
                st.rerun()
        else:
            st.info("No unbilled timekeeping entries found for the selected date range. Please process LAN biometric logs in Tab 3 first.")
            
    with tab_Staff:
        render_office_payroll_tab(conn)

    with tab_weather:
    # CALL THE WEATHER FUNCTION HERE
        render_engineering_weather_tab(conn, c)
#==========================End HRIS====================

# --- ROLE : MOTORPOOL ---
if role == "Motorpool":
    # CALL MOTORPOOL MODULE HERE
    #render_motorpool_tab(conn)
    
    #import sqlite3
    #conn = sqlite3.connect("enterprise_erp.db", check_same_thread=False)
    #render_motorpool_module(conn)

    # Standalone runner
    #st.set_page_config(page_title="Tuanson Construction - Procurement & Motorpool", layout="wide")
    #st.title("🏗️ Tuanson Construction - Procurement & Inventory")
    #db_conn = sqlite3.connect("enterprise_erp.db", check_same_thread=False)
    #render_full_application(db_conn)
    # Standalone runner
#if __name__ == "__main__":
    #st.set_page_config(page_title="Tuanson Construction - Procurement & Motorpool", layout="wide")
    #st.title("🏗️ Tuanson Construction - Procurement & Inventory")
    #db_conn = sqlite3.connect("enterprise_erp.db", check_same_thread=False)
    #render_full_application(db_conn)

    #st.set_page_config(page_title="Tuanson Construction - Procurement & Motorpool", layout="wide")
    #st.title("🏗️ Tuanson Construction - Procurement & Inventory")
    
    db_conn = sqlite3.connect("enterprise_erp.db", check_same_thread=False)
    render_full_application(db_conn)



