import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="Machining Quote Calculator", layout="wide")

st.title("🛠️ Machining Quote Calculator")

# ----------------------------------------
# 1. Sidebar – raw block + cost inputs
# ----------------------------------------
with st.sidebar:
    st.header("Raw Block Dimensions (mm)")
    L = st.number_input("Length (X)", value=200.0, step=10.0)
    W = st.number_input("Width (Y)", value=150.0, step=10.0)
    H = st.number_input("Height (Z)", value=40.0,  step=5.0)

    raw_vol = L * W * H  # mm³
    st.write(f"Raw Volume: **{raw_vol:,.0f} mm³**")

    final_vol = st.number_input("Final Part Volume (mm³)", value=680_000.0, step=50_000.0)
    chip_vol = max(raw_vol - final_vol, 0)
    st.write(f"Chip Volume: **{chip_vol:,.0f} mm³**")

    # ---- Cost inputs ----
    st.divider()
    st.header("Cost Parameters")
    machine_rate = st.number_input("Machine rate ($/hr)", value=75.0, step=5.0)
    tool_cost = st.number_input("Tool wear per part ($)", value=8.0, step=1.0)
    density = st.number_input(
        "Material density (kg/mm³)", value=2.70e-6, format="%.2e", step=1e-7
    )
    mat_price = st.number_input("Material cost ($/kg)", value=5.0, step=0.5)
    overhead_pct = st.number_input("Overhead (%)", value=15.0, step=1.0) / 100

# ----------------------------------------
# 2. Operations table (editable)
# ----------------------------------------
st.subheader("2️⃣ Operations")

_default_ops = pd.DataFrame(
    {
        "Operation": ["Roughing 3X", "Semi‑rough 5X", "Finishing"],
        "Tool Ø (mm)": [12, 8, 6],
        "Teeth (z)": [3, 2, 2],
        "RPM (n)": [12_000, 16_000, 18_000],
        "f_z (mm)": [0.06, 0.04, 0.03],
        "a_p (mm)": [8, 6, 0.5],
        "a_e (mm)": [4, 2, 0.2],
        "Volume share": [0.70, 0.25, 0.05],
    }
)

ops_df = st.data_editor(
    _default_ops,
    num_rows="dynamic",
    hide_index=True,
    use_container_width=True,
    key="ops_editor",
)

# ----------------------------------------
# 3. Calculation helpers
# ----------------------------------------

def calc_row(row, total_chip):
    """Calculate feed, MRR, chip volume and time for one operation row."""
    feed = row["Teeth (z)"] * row["RPM (n)"] * row["f_z (mm)"]  # mm/min
    mrr = feed * row["a_p (mm)"] * row["a_e (mm)"]  # mm³/min
    chip = total_chip * row["Volume share"]
    time_min = chip / mrr if mrr else 0
    return feed, mrr, chip, time_min


result_rows = []
for _, r in ops_df.iterrows():
    feed, mrr, chip, tmin = calc_row(r, chip_vol)
    result_rows.append(
        {
            **r.to_dict(),
            "Feed (mm/min)": feed,
            "MRR (mm³/min)": mrr,
            "Chip vol (mm³)": chip,
            "Time (min)": tmin,
        }
    )

results_df = pd.DataFrame(result_rows)

st.dataframe(
    results_df.style.format(
        {
            "Feed (mm/min)": "{:,.0f}",
            "MRR (mm³/min)": "{:,.0f}",
            "Chip vol (mm³)": "{:,.0f}",
            "Time (min)": "{:.2f}",
        }
    ),
    use_container_width=True,
)

cycle_time = results_df["Time (min)"].sum()
st.metric("⏱️ Total Cutting Time (min)", f"{cycle_time:.1f}")

# ----------------------------------------
# 4. Cost breakdown
# ----------------------------------------
raw_mass = raw_vol * density  # kg
material_cost = raw_mass * mat_price
mach_cost = (cycle_time / 60) * machine_rate
subtotal = material_cost + mach_cost + tool_cost
total_cost = subtotal * (1 + overhead_pct)

st.subheader("3️⃣ Cost Breakdown")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Material ($)", f"{material_cost:,.2f}")
col2.metric("Machine ($)", f"{mach_cost:,.2f}")
col3.metric("Tool ($)", f"{tool_cost:,.2f}")
col4.metric("**Total ($)**", f"{total_cost:,.2f}")

# ----------------------------------------
# 5. Charts
# ----------------------------------------
with st.expander("📊 Cycle Time Chart"):
    chart = (
        alt.Chart(results_df)
        .mark_bar()
        .encode(x=alt.X("Operation", sort=None), y="Time (min)")
        .properties(height=300)
    )
    st.altair_chart(chart, use_container_width=True)

# ----------------------------------------
# 6. Footer / how to run
# ----------------------------------------
with st.expander("ℹ️ Instructions"):
    st.markdown(
        """
        1. **Edit dimensions & volumes** in the sidebar.
        2. **Tweak operation parameters** directly in the table.
        3. Cost inputs live in the sidebar.
        4. Export results via the ••• menu → *Download data* or use *Print to PDF*.

        **Run locally:**
        ```bash
        pip install streamlit pandas altair
        streamlit run machining_quote_app.py
        ```
        """
    )
