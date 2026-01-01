import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import re
import time
import os

# 1. Configure Page
st.set_page_config(page_title="Card Miner Pro", page_icon="⛏️", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Russo+One&display=swap');
    
    .title-box {
        font-family: 'Russo One', sans-serif;
        font-size: 38px;
        color: #FFD700; /* Gold Text */
        text-shadow: 2px 2px #000000;
        text-align: center;
        padding: 15px;
        background: linear-gradient(90deg, #2C1810 0%, #8B4513 100%); /* Dirt/Earth Background */
        border-radius: 12px;
        border: 3px solid #FFD700;
        margin-bottom: 10px;
    }
    
    .slab-container {
        border: 4px solid #D9381E;
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
    .slab-detail { font-family: sans-serif; font-size: 16px; margin: 5px 0; font-weight: bold; }
    .slab-price { font-size: 24px; color: #28a745; font-weight: 900; text-align: right; }
    
    /* Highlight the Hint Box */
    .stTextInput input {
        background-color: #2C1810;
        color: #FFD700;
        border: 1px solid #FFD700;
    }
</style>
""", unsafe_allow_html=True)

# 2. Helper: Extract Low and High values
def get_price_range(value_str):
    if not isinstance(value_str, str):
        return 0.0, 0.0
    numbers = re.findall(r"[\d,\.]+", value_str)
    if not numbers:
        return 0.0, 0.0
    clean_nums = [float(n.replace(",", "")) for n in numbers if n.replace(",", "").replace(".", "").isdigit()]
    if not clean_nums:
        return 0.0, 0.0
    
    if len(clean_nums) == 1:
        return clean_nums[0], clean_nums[0]
    else:
        return min(clean_nums), max(clean_nums)

# 3. Initialize State
if 'inventory' not in st.session_state:
    st.session_state.inventory = []

# 4. Sidebar
with st.sidebar:
    st.header("⛏️ The Gold Mine")
    
    # Archive Input
    archive_location = st.text_input("Current Storage Box", value="Box 1")
    
    st.divider()
    
    # CALCULATE TOTAL RANGE
    total_low = 0.0
    total_high = 0.0
    
    for card in st.session_state.inventory:
        val_str = str(card.get('Estimated_Raw_Value', '0'))
        low, high = get_price_range(val_str)
        total_low += low
        total_high += high
    
    # Display Range
    st.metric(label="Collection Value (Est.)", value=f"${total_low:,.0f} - ${total_high:,.0f}")
    st.caption(f"Cards Scanned: {len(st.session_state.inventory)}")
    
    st.divider()
    
    st.subheader("💾 Data Manager")
    
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
            type="primary"
        )

# 5. Main Header
if os.path.exists("logo.png"):
    col_1, col_2, col_3 = st.columns([1,2,1])
    with col_2:
        st.image("logo.png", use_container_width=True)
else:
    # Fallback Text Art if no image file
    st.markdown('<div class="title-box">⛏️ CARD MINER PRO</div>', unsafe_allow_html=True)

st.markdown(f"**Digging into:** `{archive_location}`")

# 6. Secure API Key
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except KeyError:
    st.error("API Key not found. Please set GOOGLE_API_KEY in Streamlit Secrets.")
    st.stop()

# 7. Smart Upload Interface
st.info("💡 **Accuracy Tip:** If scanning a stack of the same set (e.g. 1990 Score), type it in the Hint Box below. This lets you scan **Fronts Only** with high accuracy.")

# --- THE ACCURACY HACK: SERIES HINT ---
series_hint = st.text_input("🔍 Series Hint (Optional)", placeholder="e.g., '1989 Upper Deck' or '2023 Prizm Football'")

front_images = st.file_uploader("📸 Front Images", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)

# SAFETY LOGIC: Back uploader only appears for SINGLE cards
back_image = None
if front_images and len(front_images) == 1:
    with st.expander("Add Back Image (Single Card Only)", expanded=True):
        back_image = st.file_uploader("Upload Back", type=['jpg', 'png', 'jpeg'], key="back")
elif front_images and len(front_images) > 1:
    st.caption("🚫 *Back uploads disabled during bulk scan. Use 'Series Hint' above for accuracy.*")

# 8. Analysis Logic
if st.button("⛏️ START DIGGING", type="primary", use_container_width=True):
    if not front_images:
        st.warning("Please upload at least one card image.")
    else:
        # Create a progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_files = len(front_images)
        
        for i, img_file in enumerate(front_images):
            status_text.text(f"Analyzing card {i+1} of {total_files}...")
            
            try:
                model = genai.GenerativeModel(
                    'gemini-1.5-flash',
                    generation_config={"response_mime_type": "application/json"}
                )
                
                # Dynamic Prompt using the Hint
                context_instruction = ""
                if series_hint:
                    context_instruction = f"IMPORTANT CONTEXT: The user states this card is from the set '{series_hint}'. Use this to strictly verify the Year and Brand."
                
                prompt = f"""
                Identify this sports card. Return a single JSON object with these exact keys:
                'Player', 'Team', 'Year', 'Set', 'Card_Number', 'Variation', 'Condition_Notes', 'Estimated_Raw_Value'
                
                {context_instruction}
                
                For 'Team', list the team name.
                For 'Estimated_Raw_Value', provide a dollar range based on raw sales (e.g. '$10-15').
                """
                
                inputs = [prompt, Image.open(img_file)]
                
                # Attach back image if available
                if len(front_images) == 1 and back_image:
                    inputs.append(Image.open(back_image))

                response = model.generate_content(inputs)
                new_entry = json.loads(response.text)
                
                # Add location
                new_entry['Archive_Location'] = archive_location
                st.session_state.inventory.append(new_entry)
                
                # Show the Slab
                st.markdown(f"""
                <div class="slab-container">
                    <div class="slab-header">✅ {new_entry.get('Player')}</div>
                    <div class="slab-detail">{new_entry.get('Year')} {new_entry.get('Set')} #{new_entry.get('Card_Number')}</div>
                    <div class="slab-detail" style="color: #555;">{new_entry.get('Team')} | {new_entry.get('Variation')}</div>
                    <div class="slab-price">{new_entry.get('Estimated_Raw_Value')}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Update progress
                progress_bar.progress((i + 1) / total_files)
                
                # SAFETY DELAY: 4 seconds for free tier
                if total_files > 1:
                    time.sleep(4)
                
            except Exception as e:
                st.error(f"Error on file {img_file.name}: {e}")
        
        st.success("Batch Processing Complete!")
        time.sleep(1)
        st.rerun()

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
