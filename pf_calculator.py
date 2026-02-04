import streamlit as st
import pandas as pd
from fpdf import FPDF
from io import BytesIO

# --- Page Configuration ---
st.set_page_config(page_title="PF Ledger (Clean)", layout="wide")

st.title("💰 Provident Fund Ledger (Truncation Mode)")
st.markdown("""
**Clean Calculator:**
* All values start at **0**.
* **Interest:** Uses Truncation logic (e.g., 2202.549 -> 2202.54).
* **Lowest Balance:** Includes Deposits & PFLR made before the 15th.
""")

# --- Sidebar: Configuration ---
st.sidebar.header("Configuration")
start_year = st.sidebar.number_input("Financial Year Start", value=2024, step=1)
opening_balance_input = st.sidebar.number_input("Opening Balance (April 1st)", min_value=0.0, value=0.0, step=100.0, format="%.2f")
rate_input = st.sidebar.number_input("Interest Rate (%)", min_value=0.0, value=7.1, step=0.1, format="%.2f")

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
# Initialize Session State with ZEROS (No pre-filled data)
if 'input_data' not in st.session_state:
    data = {
        "Month": months_list,
        "Dep_Before_15": [0.0] * 12,
        "PFLR_Before_15": [0.0] * 12,
        "PFLR_After_15": [0.0] * 12,
        "Dep_After_15": [0.0] * 12,
        "Withdrawal": [0.0] * 12,
        "Rate": [rate_input] * 12
    }
    st.session_state.input_data = pd.DataFrame(data)
else:
    # Update Month labels if Year changes
    st.session_state.input_data["Month"] = months_list

# Button to Reset Manually (Optional convenience)
if st.sidebar.button("Reset All Values to 0"):
    data = {
        "Month": months_list,
        "Dep_Before_15": [0.0] * 12,
        "PFLR_Before_15": [0.0] * 12,
        "PFLR_After_15": [0.0] * 12,
        "Dep_After_15": [0.0] * 12,
        "Withdrawal": [0.0] * 12,
        "Rate": [rate_input] * 12
    }
    st.session_state.input_data = pd.DataFrame(data)
    st.rerun()

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

        # Lowest Balance
        effective_deposit_for_interest = dep_before + pflr_before
        lowest_bal_calc = current_bal + effective_deposit_for_interest - withdrawal
        lowest_bal = max(0, lowest_bal_calc)

        # --- LOGIC: Interest Truncation ---
        raw_interest = (lowest_bal * rate) / 1200
        # Truncate to 2 decimal places (No Rounding Up)
        interest = int(raw_interest * 100) / 100.0

        # Closing Balance
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
    "Interest": "₹ {:.2f}", 
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
        pdf.cell(col_widths[9], 10, f"{row['Interest']:.2f}", 1) 
        pdf.cell(col_widths[10], 10, f"{row['Closing Balance']:.2f}", 1)
        pdf.ln()

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, f"Total Interest: {tot_int:,.2f}", 0, 1)
    pdf.cell(0, 10, f"Final Balance: {final_bal:,.2f}", 0, 1)
    
    return pdf.output(dest='S').encode('latin-1')

pdf_data = to_pdf(result_df, final_balance_with_interest, total_yearly_interest, start_year)
st.download_button("📄 Download PDF", pdf_data, 'PF_Statement.pdf', 'application/pdf')
