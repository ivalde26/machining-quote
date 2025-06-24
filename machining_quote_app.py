import streamlit as st
import pandas as pd
import altair as alt
from io import BytesIO
from fpdf import FPDF
from pathlib import Path

# ————————————————————————————————————
# 0) Dosya & malzeme verisi
# ————————————————————————————————————
base_dir = Path(__file__).parent
MATS = pd.read_csv(base_dir / "data" / "materials.csv")
mat_ids = MATS["Material-ID"].tolist()

# ————————————————————————————————————
# 1) Yan menü – malzeme ve blok girişleri
# ————————————————————————————————————
st.set_page_config(page_title="🛠️ Machining Quote Calculator", layout="wide")
with st.sidebar:
    st.subheader("Material")
    sel_mat = st.selectbox("Choose material", mat_ids, index=mat_ids.index("AL6061"))
    mat_row = MATS[MATS["Material-ID"] == sel_mat].iloc[0]
    rho_default = float(mat_row["rho_kg_mm3"])      # kg / mm³
    Kc_default  = float(mat_row["Kc_N_mm2"])        # şimdilik dokunmuyoruz

    st.header("Raw Block Dimensions (mm)")
    L = st.number_input("Length (X)",  value=0, min_value=1)
    W = st.number_input("Width  (Y)",  value=0, min_value=1)
    H = st.number_input("Height (Z)",  value=0,  min_value=1)

    st.divider()
    st.header("Final Part & Costs")
    V_final      = st.number_input("Final part volume (mm³)", value=0)
    machine_rate = st.number_input("Machine rate ($/hr)",      value=0)
    tool_cost    = st.number_input("Tool wear cost per part ($)", value=0)
    mat_density  = st.number_input("Material density (kg/mm³)", value=rho_default, format="%e")
    mat_price    = st.number_input("Material cost ($/kg)",     value=0)
    overhead_pct = st.number_input("Overhead (%)",             value=0)

# ————————————————————————————————————
# 2) Sayfa başlığı
# ————————————————————————————————————
st.markdown("<h1 style='text-align:center;'>🛠️ Machining Quote Calculator</h1>", unsafe_allow_html=True)

# ————————————————————————————————————
# 3) Blok / hacim hesapları
# ————————————————————————————————————
V_raw  = L * W * H                           # mm³
V_chip = max(V_raw - V_final, 0)             # mm³

# ————————————————————————————————————
# 4) Varsayılan operasyon tablosu
# ————————————————————————————————————
def default_operations():
    return pd.DataFrame(
        {
            "Operation":      ["Rough 3X", "Semi-rough 5X", "Finish"],
            "Tool Ø (mm)":    [0, 0, 0],
            "Teeth":          [3,  3, 3],
            "RPM":            [13000, 13000, 13000],
            "f_z (mm)":       [0.06, 0.04, 0.03],
            "Feed (mm/min)":  [0, 0, 0],            # manuel değer için
            "a_p (mm)":       [8, 6, 0.5],
            "a_e (mm)":       [4, 2, 0.2],
            "Volume Share":   [0.70, 0.25, 0.05],
        }
    )

if "op_df" not in st.session_state:
    st.session_state.op_df = default_operations()

# ————————————————————————————————————
# 5) Kullanıcıya seçenek: otomatik mi manuel mi?
# ————————————————————————————————————
st.subheader("Operation Parameters")

feed_mode = st.radio(
    "Feedrate giriş türü",
    ["Hesapla (RPM × f_z × teeth)", "Manuel (tabloda Feed gir)"],
    horizontal=True,
)

edited_df = st.data_editor(
    st.session_state.op_df,
    num_rows="dynamic",
    use_container_width=True,
    key="ops_editor",
)
st.session_state.op_df = edited_df

# ————————————————————————————————————
# 6) Her işlem için hesaplamalar
# ————————————————————————————————————
op_results = []
for _, row in edited_df.iterrows():
    # Feed belirleme
    if feed_mode.startswith("Hesapla"):
        feed = row["Teeth"] * row["RPM"] * row["f_z (mm)"]
    else:
        feed = row["Feed (mm/min)"]

    mrr       = feed * row["a_p (mm)"] * row["a_e (mm)"]          # mm³ / min
    chip_vol  = V_chip * row["Volume Share"]
    time_min  = chip_vol / mrr / 60 if mrr else 0

    op_results.append(
        {
            "Operation":        row["Operation"],
            "Feed (mm/min)":    feed,
            "MRR (mm³/min)":    mrr,
            "Chip Volume (mm³)": chip_vol,
            "Time (min)":       time_min,
        }
    )

op_df = pd.DataFrame(op_results)

# ————————————————————————————————————
# 7) Zaman tablosu + grafik
# ————————————————————————————————————
st.subheader("Cycle Time Breakdown")
st.dataframe(op_df, use_container_width=True)

chart = (
    alt.Chart(op_df)
    .mark_bar()
    .encode(x="Operation", y="Time (min)", tooltip=["Time (min)"])
    .properties(height=300)
)
st.altair_chart(chart, use_container_width=True)

# ————————————————————————————————————
# 8) Maliyet hesapları
# ————————————————————————————————————
raw_mass       = V_raw * mat_density
material_cost  = raw_mass * mat_price
cut_time_hr    = op_df["Time (min)"].sum() / 60
machine_cost   = cut_time_hr * machine_rate
subtotal       = material_cost + machine_cost + tool_cost
overhead       = subtotal * (overhead_pct / 100)
total_cost     = subtotal + overhead

cost_df = pd.DataFrame(
    {
        "Cost Component": ["Material", "Machine", "Tool wear", "Overhead"],
        "Amount ($)":     [material_cost, machine_cost, tool_cost, overhead],
    }
)

st.subheader("Cost Summary")
st.dataframe(cost_df, use_container_width=True)
st.markdown(f"### **Total Cost: ${total_cost:,.2f}**")

# ————————————————————————————————————
# 9) PDF çıktı
# ————————————————————————————————————
class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Machining Quote", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(4)
        self.set_font("Helvetica", size=9)
        self.cell(0, 6, "Generated by Streamlit app", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(4)

    def add_table(self, dataframe: pd.DataFrame, title: str):
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", size=8)
        col_width = self.w / (len(dataframe.columns) + 1)
        # Header
        for col in dataframe.columns:
            self.cell(col_width, 6, str(col), border=1, align="C")
        self.ln()
        # Rows
        for _, row in dataframe.iterrows():
            for item in row:
                text = (
                    f"{item:,.3f}"
                    if isinstance(item, (int, float))
                    else str(item)
                )
                self.cell(col_width, 6, text, border=1, align="C")
            self.ln()
        self.ln(4)

def build_pdf(block_dims, op_df, cost_summary):
    pdf = PDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Block & Volume", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    for key, val in block_dims.items():
        pdf.cell(0, 6, f"{key}: {val}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.add_table(op_df, "Operation Breakdown")
    pdf.add_table(cost_summary, "Cost Summary")

    buffer = BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()

if st.button("Generate PDF Quote"):
    block_info = {
        "Block L×W×H (mm)": f"{L} × {W} × {H}",
        "Raw Volume (mm³)": f"{V_raw:,.0f}",
        "Final Volume (mm³)": f"{V_final:,.0f}",
        "Chip Volume (mm³)": f"{V_chip:,.0f}",
        "Total Cycle Time (min)": f"{op_df['Time (min)'].sum():.2f}",
        "Total Cost ($)": f"{total_cost:,.2f}",
        # ------------------------------------------------------------------
        def normalize(txt: str) -> str:
    return str(txt).replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")

def add_table(self, dataframe: pd.DataFrame, title: str):
    ...
    for _, row in dataframe.iterrows():
        for item in row:
            text = (
                f"{item:,.3f}" if isinstance(item, (int, float)) else normalize(item)
            )
            self.cell(col_width, 6, text, border=1, align="C")


    }
    pdf_bytes = build_pdf(block_info, op_df, cost_df)
    st.download_button(
        "Download PDF",
        data=pdf_bytes,
        file_name="machining_quote.pdf",
        mime="application/pdf",
    )

