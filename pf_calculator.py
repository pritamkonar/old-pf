import streamlit as st
import pandas as pd
from fpdf import FPDF
from io import BytesIO

# --- Page Configuration ---
st.set_page_config(page_title="PF Ledger (1997-98 Style)", layout="wide")

st.title("💰 Provident Fund Ledger (1997-98 Reference Mode)")
st.markdown("""
**Logic Match for "old PF LEDGER - Copy.pdf":**
* **Lowest Balance:** Includes Deposits & P.F.L.R made before the 15th.
* **Interest:** calculated to **2 Decimal Places** (e.g., 1896.51).
* **Withdrawal:** Deducted from Lowest Balance immediately.
""")

# --- Sidebar: Configuration ---
st.sidebar.header("Configuration")
# Defaults set to match your PDF example
start_year = st.sidebar.number_input("Financial Year Start", value=1997, step=1)
opening_balance_input = st.sidebar.number_input("Opening Balance (April 1st)", min_value=0.0, value=187001.40, step=100.0, format="%.2f")
rate_input = st.sidebar.number_input("Interest Rate (%)", min_value=0.0, value=12.0, step=0.1, format="%.2f")

# --- Helper: Generate Financial Year Months ---
def get_fy_months(start_year):
    m_names = ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"]
    fy_months = []
    for i, m in enumerate(m_names):
        y = start_year if i < 9 else start_year + 1
        fy_months.append(f"{m} '{str(y)[-2:]}")
    return fy_months

months_list = get_fy_months(start_year)

# --- Main Data Entry ---
if 'input_data' not in st.session_state:
    # Initialize with 0.0
    dep_before = [0.0] * 12
    pflr_before = [0.0] * 12
    dep_after = [0.0] * 12
    withdrawal = [0.0] * 12
    
    # --- PRE-FILLING DATA TO MATCH YOUR PDF EXAMPLE ---
    # April to August: Dep 2400/2750 + PFLR 250
    dep_before[0] = 2400.0; pflr_before[0] = 250.0 # April
    for i in range(1, 5): # May, June, July, Aug
        dep_before[i] = 2750.0; pflr_before[i] = 250.0
    
    # September: Shows "250+250" and deposit 2750. 
    # Based on calc, 3000 goes to LB, 3000 goes to Closing (Arrear likely)
    dep_before[5] = 2750.0; pflr_before[5] = 250.0 # Sept (<15th)
    dep_after[5] = 2750.0; # Sept (>15th - Arrear/Extra)
    
    # Oct: 250 PFLR only? The PDF shows Closing same as Opening.
    # Actually Oct shows Opening 207651, Lowest 207651. 
    # This means NO deposit/PFLR added to Lowest Balance?
    # Or PFLR was >15th? Let's assume PFLR > 15th for Oct based on visual.
    # But for now, let's keep standard 250 PFLR < 15th for consistency unless user changes.
    # Wait, Oct lowest = Opening. So inputs must be 0 or >15th.
    
    # Nov, Dec: Standard
    dep_before[7] = 2750.0; pflr_before[7] = 250.0 # Nov
    dep_before[8] = 2750.0; pflr_before[8] = 250.0 # Dec
    
    # Jan: 2350 Dep, 250 PFLR, 28166 Withdrawal
    dep_before[9] = 2350.0; pflr_before[9] = 250.0; withdrawal[9] = 28166.0 # Jan
    
    # Feb, Mar: 2350 + 250
    dep_before[10] = 2350.0; pflr_before[10] = 250.0 # Feb
    dep_before[11] = 2350.0; pflr_before[11] = 250.0 # Mar

    data = {
        "Month": months_list,
        "Dep_Before_15": dep_before,
        "PFLR_Before_15": pflr_before,
        "PFLR_After_15": [0.0] * 12, # Not explicitly used in reference, but good to have
        "Dep_After_15": dep_after,
        "Withdrawal": withdrawal,
        "Rate": [rate_input] * 12
    }
    st.session_state.input_data = pd.DataFrame(data)
else:
    st.session_state.input_data["Month"] = months_list
    # Note: Rate updates only on new session or manual change, 
    # to preserve row-specific overrides if any.

edited_df = st.data_editor(
    st.session_state.input_data,
    column_config={
        "Month": st.column_config.TextColumn("Month", disabled=True),
        "Dep_Before_15": st.column_config.NumberColumn("Deposit (<15th)", format="₹ %.2f"),
        "PFLR_Before_15": st.column_config.NumberColumn("PFLR (<15th)", format="₹ %.2f"),
        "PFLR_After_15": st.column_config.NumberColumn("PFLR (>15th)", format="₹ %.2f"),
        "Dep_After_15": st.column_config.NumberColumn("Deposit (>15th)", format="₹ %.2f"),
        "Withdrawal": st.column_config.NumberColumn("Withdrawal", format="₹ %.2f"),
        "Rate": st.column_config.NumberColumn("Rate %", format="%.2f")
    },
    hide_index=True,
    use_container_width=True,
    num_rows="fixed"
)

# --- Calculation Engine ---
def calculate_ledger(opening_bal, input_df):
    results = []
    current_bal = opening_bal
    total_interest = 0.0

    for index, row in input_df.iterrows():
        month = row['Month']
        dep_before = row['Dep_Before_15']
        dep_after = row['Dep_After_15']
        pflr_before = row['PFLR_Before_15']
        pflr_after = row['PFLR_After_15']
        withdrawal = row['Withdrawal']
        rate = row['Rate']

        # --- LOGIC: Lowest Balance ---
        # The PDF shows: Opening + Dep(<15) + PFLR(<15) - Withdrawal = Lowest Balance
        effective_deposit_for_interest = dep_before + pflr_before
        
        lowest_bal_calc = current_bal + effective_deposit_for_interest - withdrawal
        lowest_bal = max(0, lowest_bal_calc)

        # --- LOGIC: Interest Calculation (2 Decimals) ---
        raw_interest = (lowest_bal * rate) / 1200
        # The PDF values (e.g., 1896.51) match standard rounding to 2 decimals
        interest = round(raw_interest, 2)

        # --- LOGIC: Closing Balance ---
        # Closing = Opening + All Money In - Money Out
        closing_bal = current_bal + dep_before + dep_after + pflr_before + pflr_after - withdrawal

        results.append({
            "Month": month,
            "Opening Balance": current_bal,
            "Dep (<15th)": dep_before,
            "PFLR (<15th)": pflr_before,
            "PFLR (>15th)": pflr_after,
            "Dep (>15th)": dep_after,
            "Withdrawal": withdrawal,
            "Lowest Balance": lowest_bal,
            "Rate (%)": rate,
            "Interest": interest,
            "Closing Balance": closing_bal
        })

        current_bal = closing_bal
        total_interest += interest

    return pd.DataFrame(results), total_interest, current_bal

# Perform Calculation
result_df, total_yearly_interest, final_principal = calculate_ledger(opening_balance_input, edited_df)

# --- Display Results ---
st.subheader("Calculation Result")

st.dataframe(result_df.style.format({
    "Opening Balance": "₹ {:.2f}",
    "Dep (<15th)": "₹ {:.2f}",
    "PFLR (<15th)": "₹ {:.2f}",
    "PFLR (>15th)": "₹ {:.2f}",
    "Dep (>15th)": "₹ {:.2f}",
    "Withdrawal": "₹ {:.2f}",
    "Lowest Balance": "₹ {:.2f}",
    "Interest": "₹ {:.2f}", # <--- 2 Decimals
    "Closing Balance": "₹ {:.2f}"
}), use_container_width=True)

# Summary
final_balance_with_interest = final_principal + total_yearly_interest
col1, col2, col3 = st.columns(3)
col1.metric("Closing Principal", f"₹ {final_principal:,.2f}")
col2.metric("Total Interest", f"₹ {total_yearly_interest:,.2f}")
col3.metric("Final Balance", f"₹ {final_balance_with_interest:,.2f}")

# --- PDF Export ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'PF Ledger Statement', 0, 1, 'C')
        self.ln(5)

def to_pdf(df, final_bal, tot_int, year_label):
    pdf = PDF(orientation='L') 
    pdf.add_page()
    pdf.set_font("Arial", size=7) 
    
    # Title
    pdf.cell(0, 10, f"Financial Year: {year_label}-{year_label+1}", 0, 1, 'L')

    cols = ["Month", "Open", "Dep<15", "PFLR<15", "PFLR>15", "Dep>15", "Withdr", "Lowest", "Rate", "Int", "Close"]
    col_widths = [20, 30, 20, 20, 20, 20, 20, 30, 10, 20, 30] 
    
    pdf.set_font("Arial", 'B', 7)
    for i, col in enumerate(cols):
        pdf.cell(col_widths[i], 10, col, 1, 0, 'C')
    pdf.ln()
    
    pdf.set_font("Arial", size=7)
    for index, row in df.iterrows():
        pdf.cell(col_widths[0], 10, str(row['Month']), 1)
        pdf.cell(col_widths[1], 10, f"{row['Opening Balance']:.2f}", 1)
        pdf.cell(col_widths[2], 10, f"{row['Dep (<15th)']:.2f}", 1)
        pdf.cell(col_widths[3], 10, f"{row['PFLR (<15th)']:.2f}", 1)
        pdf.cell(col_widths[4], 10, f"{row['PFLR (>15th)']:.2f}", 1)
        pdf.cell(col_widths[5], 10, f"{row['Dep (>15th)']:.2f}", 1)
        pdf.cell(col_widths[6], 10, f"{row['Withdrawal']:.2f}", 1)
        pdf.cell(col_widths[7], 10, f"{row['Lowest Balance']:.2f}", 1)
        pdf.cell(col_widths[8], 10, str(row['Rate (%)']), 1)
        pdf.cell(col_widths[9], 10, f"{row['Interest']:.2f}", 1) # 2 Decimals
        pdf.cell(col_widths[10], 10, f"{row['Closing Balance']:.2f}", 1)
        pdf.ln()

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, f"Total Interest: {tot_int:,.2f}", 0, 1)
    pdf.cell(0, 10, f"Final Balance: {final_bal:,.2f}", 0, 1)
    
    return pdf.output(dest='S').encode('latin-1')

pdf_data = to_pdf(result_df, final_balance_with_interest, total_yearly_interest, start_year)
st.download_button("📄 Download PDF (1997 Reference)", pdf_data, 'PF_Statement_1997.pdf', 'application/pdf')
