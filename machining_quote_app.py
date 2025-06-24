# ────────────────────────────────────────────────────────────────
# 0) IMPORTS  +  MATERIAL DATA
# ────────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path
from io import BytesIO
from fpdf import FPDF

base_dir = Path(__file__).parent
MATS = pd.read_csv(base_dir / "data" / "materials.csv")
mat_ids = MATS["Material-ID"].tolist()

# ────────────────────────────────────────────────────────────────
# 1) PAGE CONFIG + TITLE
# ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="🛠️ Machining Quote Calculator", layout="wide")
st.markdown(
    "<h1 style='text-align:center;'>🛠️ Machining Quote Calculator</h1>",
    unsafe_allow_html=True,
)

# ────────────────────────────────────────────────────────────────
# 2) SIDEBAR – ALL INPUTS
# ────────────────────────────────────────────────────────────────
with st.sidebar:
    # ── Material
    st.subheader("Material")
    sel_mat = st.selectbox("Choose material", mat_ids, index=mat_ids.index("AL6061"))
    mat_row = MATS[MATS["Material-ID"] == sel_mat].iloc[0]
    rho_default = float(mat_row["rho_kg_mm3"])

    # ── Raw block
    st.header("Raw Block Dimensions (mm)")
    L = st.number_input("Length (X)", value=200, min_value=1)
    W = st.number_input("Width  (Y)", value=150, min_value=1)
    H = st.number_input("Height (Z)", value=40, min_value=1)

    V_raw = L * W * H
    raw_mass_sidebar = V_raw * rho_default

    st.markdown("### Block & Volume")
    st.write(f"Raw block volume: `{V_raw:,.0f} mm³`")
    st.write(f"Raw material weight: `{raw_mass_sidebar:.2f} kg`")

    st.divider()

    # ── Final part & costs
    st.header("Final Part & Costs")
    V_final = st.number_input("Final part volume (mm³)", value=0)
    machine_rate = st.number_input("Machine rate ($/hr)", value=60)
    tool_cost = st.number_input("Tool wear cost per part ($)", value=1.0)
    mat_density = st.number_input("Material density (kg/mm³)", value=rho_default, format="%e")
    mat_price = st.number_input("Material cost ($/kg)", value=0.0)
    overhead_pct = st.number_input("Overhead (%)", value=15.0)

    # ── Setup
    st.header("Setup")
    setup_time_min = st.number_input("Setup time (min)", value=60)
    setup_labor_rate = st.number_input("Labor rate ($/hr)", value=40.0)

# ────────────────────────────────────────────────────────────────
# 3) BLOCK / CHIP VOLUMES
# ────────────────────────────────────────────────────────────────
V_raw = L * W * H
V_chip = max(V_raw - V_final, 0)

# ────────────────────────────────────────────────────────────────
# 4) DEFAULT OPERATIONS TABLE
# ────────────────────────────────────────────────────────────────
def default_operations() -> pd.DataFrame:
    return pd.DataFrame({
        "Operation":      ["Rough 3X", "Semi-rough 5X", "Finish"],
        "Tool Ø (mm)":    [12, 8, 6],
        "Teeth":          [3, 2, 2],
        "RPM":            [12000, 16000, 18000],
        "f_z (mm)":       [0.06, 0.04, 0.03],
        "Feed (mm/min)":  [0, 0, 0],       # manual girdi
        "a_p (mm)":       [8, 6, 0.5],
        "a_e (mm)":       [4, 2, 0.2],     # manual girdi
        "ae % (of Ø)":    [50, 50, 10],    # % girdi
        "Volume Share":   [0.70, 0.25, 0.05],
    })

if "op_df" not in st.session_state:
    st.session_state.op_df = default_operations()

# ── Giriş modları
ae_mode = st.radio(
    "aₑ input mode",
    ["Use % of tool Ø", "Manual aₑ (mm)"],
    horizontal=True,
)

feed_mode = st.radio(
    "Feedrate input mode",
    ["Calculate from RPM × fₓ × teeth", "Manual column 'Feed (mm/min)'"],
    horizontal=True,
)

# ── Tablo editörü
data_editor_kwargs = dict(
    data=st.session_state.op_df,
    num_rows="dynamic",
    use_container_width=True,
    key="ops_editor",
)
if hasattr(st, "experimental_rerun"):
    data_editor_kwargs["on_change"] = st.experimental_rerun

op_df_edit = st.data_editor(**data_editor_kwargs)
st.session_state.op_df = op_df_edit

# Eski sürümde otomatik yenileme yoksa isteğe bağlı "Recalculate" düğmesi
if not hasattr(st, "experimental_rerun"):
    if st.button("🔄 Recalculate"):
        st.experimental_rerun()

# ────────────────────────────────────────────────────────────────
# 5) PER-OP CALCULATIONS
# ────────────────────────────────────────────────────────────────
op_results = []
for _, row in st.session_state.op_df.iterrows():
    feed = (row["Teeth"] * row["RPM"] * row["f_z (mm)"]
            if feed_mode.startswith("Calculate") else row["Feed (mm/min)"])

    ae = (row["Tool Ø (mm)"] * row["ae % (of Ø)"] / 100
          if ae_mode.startswith("Use %") else row["a_e (mm)"])

    mrr = feed * row["a_p (mm)"] * ae
    chip_vol = V_chip * row["Volume Share"]
    time_min = chip_vol / mrr / 60 if mrr else 0

    op_results.append({
        "Operation":         row["Operation"],
        "Feed (mm/min)":     feed,
        "aₑ (mm)":           ae,
        "MRR (mm³/min)":     mrr,
        "Chip Volume (mm³)": chip_vol,
        "Time (min)":        time_min,
    })

op_df = pd.DataFrame(op_results)

# ────────────────────────────────────────────────────────────────
# 6) CYCLE TIME TABLE & CHART
# ────────────────────────────────────────────────────────────────
st.subheader("Cycle Time Breakdown")
st.dataframe(op_df, use_container_width=True)

st.altair_chart(
    alt.Chart(op_df).mark_bar().encode(
        x="Operation", y="Time (min)", tooltip=["Time (min)"]
    ).properties(height=300),
    use_container_width=True,
)

mach_time_min  = op_df["Time (min)"].sum()
total_time_min = mach_time_min + setup_time_min

st.subheader("⏱️ Total Production Time")
st.write(f"Machining time : `{mach_time_min:.2f} min`")
st.write(f"Setup time     : `{setup_time_min:.0f} min`")
st.success(f"Total time     : `{total_time_min:.2f} min`")
st.divider()

# ────────────────────────────────────────────────────────────────
# 7) COST SUMMARY
# ────────────────────────────────────────────────────────────────
raw_mass      = V_raw * mat_density
material_cost = raw_mass * mat_price
machine_cost  = (mach_time_min / 60) * machine_rate
setup_cost    = (setup_time_min / 60) * setup_labor_rate

subtotal   = material_cost + machine_cost + tool_cost + setup_cost
overhead   = subtotal * (overhead_pct / 100)
total_cost = subtotal + overhead

cost_df = pd.DataFrame({
    "Cost Component": ["Material", "Machine", "Tool wear",
                       "Setup labor", "Overhead"],
    "Amount ($)":     [material_cost, machine_cost, tool_cost,
                       setup_cost, overhead],
})

st.subheader("Cost Summary")
st.dataframe(cost_df, use_container_width=True)
st.markdown(f"### **Total Cost: ${total_cost:,.2f}**")

# ────────────────────────────────────────────────────────────────
# 8) PDF EXPORT
# ────────────────────────────────────────────────────────────────
def normalize(txt: str) -> str:
    return txt.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Machining Quote",
                  new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(4)

    def add_table(self, df: pd.DataFrame, title: str):
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", size=8)
        col_w = self.w / (len(df.columns) + 1)
        for col in df.columns:
            self.cell(col_w, 6, str(col), border=1, align="C")
        self.ln()
        for _, row in df.iterrows():
            for val in row:
                txt = f"{val:,.3f}" if isinstance(val, (int, float)) else normalize(str(val))
                self.cell(col_w, 6, txt, border=1, align="C")
            self.ln()
        self.ln(4)

def build_pdf() -> bytes:
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=9)

    pdf.cell(0, 8, "Block & Volume", new_x="LMARGIN", new_y="NEXT")
    blk = {
        "L×W×H (mm)": f"{L} × {W} × {H}",
        "Raw Volume (mm³)": f"{V_raw:,.0f}",
        "Final Volume (mm³)": f"{V_final:,.0f}",
        "Chip Volume (mm³)": f"{V_chip:,.0f}",
        "Total Cycle Time (min)": f"{total_time_min:.2f}",
        "Total Cost ($)": f"{total_cost:,.2f}",
    }
    for k, v in blk.items():
        pdf.cell(0, 6, f"{k}: {v}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.add_table(op_df[["Operation", "aₑ (mm)", "Time (min)"]], "Operation Breakdown")
    pdf.add_table(cost_df, "Cost Summary")

    buff = BytesIO()
    pdf.output(buff)
    return buff.getvalue()

if st.button("Generate PDF Quote"):
    st.download_button(
        "Download PDF",
        data=build_pdf(),
        file_name="machining_quote.pdf",
        mime="application/pdf",
    )
