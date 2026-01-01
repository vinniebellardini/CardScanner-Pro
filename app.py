import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import re
import time
import os
import base64

# 1. Configure Page
st.set_page_config(page_title="The Dig", page_icon="⛏️", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;900&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .logo-container { display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 2rem; text-align: center; }
    .logo-img { max-width: 200px; border-radius: 20px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5); margin-bottom: 1rem; }
    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: 3rem; background: linear-gradient(to bottom, #F8FAFC, #94A3B8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 2px 10px rgba(0,0,0,0.3); margin-top: 0.5rem; }

    [data-testid="stExpander"] { background-color: #1E293B; border-radius: 15px; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
    [data-testid="stFileUploader"] { background-color: #1E293B; border: 2px dashed #475569; border-radius: 15px; padding: 2rem; text-align: center; }
    [data-testid="stFileUploader"] section > button { background-color: #3B82F6; color: white; border: none; border-radius: 8px; padding: 0.5rem 1rem; font-weight: 600; }
    [data-testid="stSidebar"] { background-color: #0F172A; border-right: 1px solid #334155; }
    [data-testid="stMetricValue"] { font-size: 2rem; font-weight: 900; color: #10B981; }

    .slab-container { background-color: #1E293B; border-radius: 15px; padding: 1.5rem; margin-top: 1.5rem; border: 1px solid #334155; border-left: 5px solid #3B82F6; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2); }
    .slab-header { font-size: 1.25rem; font-weight: 900; color: #F8FAFC; margin-bottom: 0.5rem; }
    .slab-detail { color: #94A3B8; font-size: 0.95rem; margin-bottom: 0.25rem; }
    .slab-price { font-size: 1.5rem; font-weight: 900; color: #10B981; text-align: right; margin-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# 2. Helper Functions
def get_price_range(value_str):
    if not isinstance(value_str, str): return 0.0, 0.0
    numbers = re.findall(r"[\d,\.]+", value_str)
    if not numbers: return 0.0, 0.0
    clean_nums = [float(n.replace(",", "")) for n in numbers if n.replace(",", "").replace(".", "").isdigit()]
    if not clean_nums: return 0.0, 0.0
    if len(clean_nums) == 1: return clean_nums[0], clean_nums[0]
    else: return min(clean_nums), max(clean_nums)

# 3. Initialize State (Safety Net Logic)
if 'inventory' not in st.session_state:
    st.session_state.inventory = []

# 4. Sidebar
with st.sidebar:
    st.title("💎 Stats")
    total_low, total_high = 0.0, 0.0
    for item in st.session_state.inventory:
        val_str = str(item.get('Estimated_Raw_Value', '0'))
        low, high = get_price_range(val_str)
        total_low += low
        total_high += high
    st.metric(label="Total Value (Est.)", value=f"${total_low:,.0f} - ${total_high:,.0f}")
    st.caption(f"{len(st.session_state.inventory)} items scanned.")
    
    st.divider()
    st.subheader("📁 Data")
    uploaded_file = st.file_uploader("Resume Session (CSV)", type=['csv'])
    if uploaded_file is not None and len(st.session_state.inventory) == 0:
        try:
            df_load = pd.read_csv(uploaded_file)
            st.session_state.inventory = df_load.to_dict('records')
            st.success(f"✅ Loaded {len(df_load)} items!")
            st.rerun()
        except Exception as e: st.error("Error loading file.")
    if len(st.session_state.inventory) > 0:
        df_save = pd.DataFrame(st.session_state.inventory)
        csv = df_save.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, "card_inventory.csv", "text/csv", type="primary")

# 5. Main Content & Logo
col1, col2, col3 = st.columns([1,2,1])
with col2:
    if os.path.exists("logo.png"):
        with open("logo.png", "rb") as f:
            data = base64.b64encode(f.read()).decode()
        st.markdown(f"""
            <div class="logo-container">
                <img src="data:image/png;base64,{data}" class="logo-img">
                <div class="main-title">THE DIG</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="main-title" style="text-align: center;">⛏️ THE DIG</div>', unsafe_allow_html=True)

# Settings
with st.expander("⚙️ Scan Settings & Hints", expanded=True):
    col_a, col_b = st.columns(2)
    with col_a:
        archive_location = st.text_input("📦 Archive Location", value="Box 1")
    with col_b:
        series_hint = st.text_input("🔍 Context Hint (Optional)", placeholder="e.g., '1989 Upper Deck'")

# 6. The "Interleaved" Uploader
st.markdown("### 📸 Batch Upload")
st.info("💡 **Instructions:** Take photos in order: **Front, Back, Front, Back...** then upload them all at once.")

# We accept multiple files
uploaded_files = st.file_uploader("Upload Batch (Fronts & Backs)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)

# 7. Analysis Logic (The Sorting Magic)
if st.button("🚀 Process Batch", type="primary", use_container_width=True):
    if not uploaded_files:
        st.warning("Please upload photos.")
    else:
        # STEP 1: SORT FILES BY NAME to ensure 001 comes before 002
        # This guarantees that if you took them in order, they process in order
        sorted_files = sorted(uploaded_files, key=lambda x: x.name)
        
        # Check if we have an even number
        if len(sorted_files) % 2 != 0:
            st.error(f"⚠️ Odd number of photos detected ({len(sorted_files)}). Please ensure every Front has a Back.")
            st.stop()
            
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Calculate how many "Pairs" (Cards) we have
        total_cards = len(sorted_files) // 2
        
        # STEP 2: LOOP THROUGH IN PAIRS
        # We step by 2: (0, 1), (2, 3), (4, 5)...
        for i in range(0, len(sorted_files), 2):
            front_file = sorted_files[i]
            back_file = sorted_files[i+1]
            
            card_num = (i // 2) + 1
            status_text.markdown(f"**Processing Card {card_num} of {total_cards}...**")
            
            try:
                genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
                
                context_instruction = f"IMPORTANT CONTEXT: The user provided this hint: '{series_hint}'. Use this to help identification." if series_hint else ""
                
                # Prompt specifically mentions TWO images
                prompt = f"""
                Identify this sports item (Card OR Memorabilia). You are provided two images: 
                Image 1 is the FRONT. Image 2 is the BACK (or COA).
                Use information from BOTH images to ensure accuracy.
                
                Return a single JSON object with these exact keys:
                'Player', 'Team', 'Year', 'Set', 'Card_Number', 'Variation', 'Condition_Notes', 'Estimated_Raw_Value'
                
                {context_instruction}
                
                RULES:
                1. If it is a CARD: Standard identification.
                2. If it is MEMORABILIA: Map 'Player' to Signer/Subject, 'Set' to Manufacturer/Type.
                
                For 'Estimated_Raw_Value', provide a dollar range (e.g. '$10-15').
                """
                
                # Pass BOTH images in the pair
                inputs = [prompt, Image.open(front_file), Image.open(back_file)]
                
                response = model.generate_content(inputs)
                new_entry = json.loads(response.text)
                new_entry['Archive_Location'] = archive_location
                st.session_state.inventory.append(new_entry)
                
                # Result Slab
                st.markdown(f"""
                <div class="slab-container">
                    <div class="slab-header">✅ {new_entry.get('Player')}</div>
                    <div class="slab-detail">Goal: {new_entry.get('Year')} {new_entry.get('Set')} #{new_entry.get('Card_Number')}</div>
                    <div class="slab-detail">{new_entry.get('Team')} | {new_entry.get('Variation')}</div>
                    <div class="slab-detail" style="font-style: italic;">Notes: {new_entry.get('Condition_Notes')}</div>
                    <div class="slab-price">{new_entry.get('Estimated_Raw_Value')}</div>
                </div>
                """, unsafe_allow_html=True)
                
            except Exception as e: st.error(f"Error on Pair {card_num}: {e}")
            
            progress_bar.progress(card_num / total_cards)
            if total_cards > 1: time.sleep(4)
            
        st.success("Batch Analysis Complete!")
        time.sleep(1)
        st.rerun()

# Inventory Table
st.divider()
st.markdown("### 📋 Session Inventory")
if len(st.session_state.inventory) > 0:
    df = pd.DataFrame(st.session_state.inventory)
    preferred_order = ['Archive_Location', 'Player', 'Year', 'Set', 'Card_Number', 'Variation', 'Estimated_Raw_Value', 'Condition_Notes']
    cols = [c for c in preferred_order if c in df.columns]
    st.dataframe(df[cols], use_container_width=True, hide_index=True)
else:
    st.info("Inventory is empty. Upload Front/Back pairs to start.")
