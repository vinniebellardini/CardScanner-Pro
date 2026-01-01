import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import re

# 1. Configure Page
st.set_page_config(page_title="CardScanner Pro", page_icon="💎", layout="wide")

# --- CUSTOM CSS FOR "SPORTS" VIBE ---
st.markdown("""
<style>
    /* Import a Sports-style Font */
    @import url('https://fonts.googleapis.com/css2?family=Russo+One&display=swap');
    
    /* Main Title Styling */
    .title-box {
        font-family: 'Russo One', sans-serif;
        font-size: 40px;
        color: #FFFFFF;
        text-shadow: 2px 2px #000000;
        text-align: center;
        padding: 20px;
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        border-radius: 10px;
        border: 2px solid #D4AF37;
        margin-bottom: 20px;
    }
    
    /* "Digital Slab" Result Box */
    .slab-container {
        border: 4px solid #D9381E; /* PSA Red Style Border */
        background-color: #f8f9fa;
        color: #000000;
        border-radius: 8px;
        padding: 15px;
        margin-top: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .slab-header {
        font-family: 'Russo One', sans-serif;
        color: #D9381E;
        border-bottom: 2px solid #ccc;
        padding-bottom: 5px;
        margin-bottom: 10px;
        font-size: 20px;
    }
    .slab-detail {
        font-family: sans-serif;
        font-size: 16px;
        margin: 5px 0;
        font-weight: bold;
    }
    .slab-price {
        font-size: 24px;
        color: #28a745; /* Money Green */
        font-weight: 900;
        text-align: right;
    }
</style>
""", unsafe_allow_html=True)

# 2. Helper Function
def parse_value(value_str):
    if not isinstance(value_str, str):
        return 0.0
    numbers = re.findall(r"[\d,\.]+", value_str)
    if not numbers:
        return 0.0
    clean_nums = [float(n.replace(",", "")) for n in numbers if n.replace(",", "").replace(".", "").isdigit()]
    if not clean_nums:
        return 0.0
    return sum(clean_nums) / len(clean_nums)

# 3. Initialize State
if 'inventory' not in st.session_state:
    st.session_state.inventory = []

# 4. Sidebar
with st.sidebar:
    st.markdown("### 🏟️ Collection Stats")
    
    # Archive Input
    archive_location = st.text_input("📦 Storage Box ID", value="Box 1")
    
    st.divider()
    
    # Value Calculator
    total_value = 0.0
    for card in st.session_state.inventory:
        val_str = str(card.get('Estimated_Raw_Value', '0'))
        total_value += parse_value(val_str)
    
    # "Scoreboard" Style Metric
    st.metric(label="💰 Portfolio Value", value=f"${total_value:,.2f}")
    st.caption(f"Cards Scanned: {len(st.session_state.inventory)}")
    
    st.divider()
    
    st.markdown("### 💾 Data Manager")
    
    # Load
    uploaded_file = st.file_uploader("Resume Session (Upload CSV)", type=['csv'])
    if uploaded_file is not None and len(st.session_state.inventory) == 0:
        try:
            df_load = pd.read_csv(uploaded_file)
            st.session_state.inventory = df_load.to_dict('records')
            st.success(f"✅ Loaded {len(df_load)} cards!")
            st.rerun() 
        except Exception as e:
            st.error("Error loading file.")

    # Save
    if len(st.session_state.inventory) > 0:
        df_save = pd.DataFrame(st.session_state.inventory)
        csv = df_save.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name="card_inventory.csv",
            mime="text/csv",
            type="primary" # Makes button stand out
        )

# 5. Main Header (Custom HTML)
st.markdown('<div class="title-box">💎 CARD SCANNER PRO</div>', unsafe_allow_html=True)
st.markdown(f"**Current Archive Box:** `{archive_location}`")

# 6. Secure API Key
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except KeyError:
    st.error("API Key not found. Please set GOOGLE_API_KEY in Streamlit Secrets.")
    st.stop()

# 7. Scan Interface
col1, col2 = st.columns(2)
with col1:
    front_image = st.file_uploader("📸 Front Image (Required)", type=['jpg', 'png', 'jpeg'], key="front")
    if front_image:
        st.image(front_image, use_container_width=True)

with col2:
    back_image = st.file_uploader("📸 Back Image (Optional)", type=['jpg', 'png', 'jpeg'], key="back")
    if back_image:
        st.image(back_image, use_container_width=True)

# 8. Analysis Logic
if st.button("🔍 ANALYZE CARD", type="primary", use_container_width=True):
    if not front_image:
        st.warning("Please upload the front of the card first.")
    else:
        with st.spinner("🧠 AI is grading & valuing..."):
            try:
                model = genai.GenerativeModel(
                    'gemini-1.5-flash',
                    generation_config={"response_mime_type": "application/json"}
                )
                
                prompt = """
                Identify this sports card. Return a single JSON object with these exact keys:
                'Player', 'Team', 'Year', 'Set', 'Card_Number', 'Variation', 'Condition_Notes', 'Estimated_Raw_Value'
                
                For 'Team', list the team name.
                For 'Estimated_Raw_Value', provide a dollar range based on raw sales (e.g. '$10-15').
                """
                
                inputs = [prompt, Image.open(front_image)]
                if back_image:
                    inputs.append(Image.open(back_image))

                response = model.generate_content(inputs)
                new_entry = json.loads(response.text)
                
                # Add location
                new_entry['Archive_Location'] = archive_location
                st.session_state.inventory.append(new_entry)
                
                # --- NEW: VISUAL "SLAB" RESULT ---
                # This creates a pretty box that mimics a grading slab label
                st.markdown(f"""
                <div class="slab-container">
                    <div class="slab-header">✅ IDENTIFIED</div>
                    <div class="slab-detail">{new_entry.get('Year')} {new_entry.get('Set')}</div>
                    <div class="slab-detail" style="font-size: 22px;">{new_entry.get('Player')}</div>
                    <div class="slab-detail">{new_entry.get('Variation')} #{new_entry.get('Card_Number')}</div>
                    <div class="slab-detail" style="color: #555;">Team: {new_entry.get('Team')}</div>
                    <div class="slab-detail" style="color: #555;">Notes: {new_entry.get('Condition_Notes')}</div>
                    <hr>
                    <div class="slab-price">{new_entry.get('Estimated_Raw_Value')}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Update sidebar stats
                # Note: We don't rerun immediately so you can see the "Slab" result above.
                # The sidebar will update on the next action.
                
            except Exception as e:
                st.error(f"Error: {e}")

# 9. Inventory Table
st.divider()
st.subheader("📋 Session Inventory")
if len(st.session_state.inventory) > 0:
    df = pd.DataFrame(st.session_state.inventory)
    preferred_order = ['Archive_Location', 'Player', 'Team', 'Year', 'Set', 'Card_Number', 'Variation', 'Estimated_Raw_Value', 'Condition_Notes']
    cols = [c for c in preferred_order if c in df.columns]
    st.dataframe(df[cols], use_container_width=True)
else:
    st.info("No cards scanned yet.")
