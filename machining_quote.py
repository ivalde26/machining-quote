import streamlit as st
import pandas as pd

# --- Malzeme Yoğunluk Verisi ---
MATERIALS = {
    'Aluminum 5083': 2650,
    'Aluminum 7075': 2810,
    'Steel 1018': 7850,
    'Stainless 304': 8000,
}

st.title("🛠️ Machining Quote Generator")

# Malzeme seçimi
material = st.selectbox("Select Material", list(MATERIALS.keys()))
density = MATERIALS.get(material)

if density:
    st.write(f"**Density:** {density} kg/m³")
else:
    st.error("Density data not available.")

# Kullanıcıdan hacim al
volume_cm3 = st.number_input("Enter Part Volume (cm³):", min_value=0.0, format="%.2f")

# Toplam hacmi göster
st.write(f"**Total Volume:** {volume_cm3:.2f} cm³")

# Ağırlık hesapla
weight_kg = (volume_cm3 / 1_000_000) * density
st.write(f"**Estimated Weight:** {weight_kg:.2f} kg")

# Süre ve saatlik maliyet
time_minutes = st.number_input("Estimated Machining Time (minutes):", min_value=0.0, format="%.2f")
hourly_rate = st.number_input("Hourly Machining Cost (₺):", min_value=0.0, format="%.2f")

# Teklif hesapla
if st.button("Calculate Cost"):
    time_hours = time_minutes / 60
    cost = time_hours * hourly_rate
    st.success(f"Estimated Machining Cost: ₺{cost:.2f}")

# İlerleme kısmı
st.markdown("---")
st.subheader("💡 Feedrate (İlerleme Hızı) Ayarı")

feed_mode = st.radio("Feedrate nasıl girilsin?", ["Hesapla (rpm & fz)", "Manuel gir"])

if feed_mode == "Hesapla (rpm & fz)":
    rpm = st.number_input("Spindle Speed (RPM):", min_value=0.0, format="%.0f")
    fz = st.number_input("Feed per Tooth (mm):", min_value=0.0, format="%.3f")
    flutes = st.number_input("Number of Flutes (Teeth):", min_value=1, step=1)
    feedrate = rpm * fz * flutes
    st.write(f"**Hesaplanan Feedrate:** {feedrate:.2f} mm/min")
else:
    feedrate = st.number_input("Feedrate (mm/min):", min_value=0.0, format="%.2f")
    st.write(f"**Girilen Feedrate:** {feedrate:.2f} mm/min")
