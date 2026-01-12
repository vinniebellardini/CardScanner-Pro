import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import pandas as pd
import json
import re
import time
import os
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. Configure Page
st.set_page_config(page_title="The Dig", page_icon="⛏️", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;900&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .logo-container { display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 2rem; text-align: center; }
    .logo-img { max-width: 180px; border-radius: 20px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5); margin-bottom: 0.5rem; }
    .main-title { font-family: 'Inter', sans-serif; font-weight: 900; font-size: 2.5rem; background: linear-gradient(to bottom, #F8FAFC, #94A3B8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 2px 10px rgba(0,0,0,0.3); margin-top: 0px; }

    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #1E293B; border-radius: 10px; color: #94A3B8; padding: 10px 20px; border: 1px solid #334155; }
    .stTabs [aria-selected="true"] { background-color: #3B82F6; color: white; border-color: #3B82F6; }

    [data-testid="stExpander"] { background-color: #1E293B; border-radius: 15px; border: 1px solid #334155; }
    [data-testid="stFileUploader"] { background-color: #1E293B; border: 2px dashed #475569; border-radius: 15px; padding: 2rem; text-align: center; }
    [data-testid="stFileUploader"] section > button { background-color: #3B82F6; color: white; border: none; border-radius: 8px; font-weight: 600; }
    [data-testid="stSidebar"] { background-color: #0F172A; border-right: 1px solid #334155; }
    [data-testid="stMetricValue"] { font-size: 2rem; font-weight: 900; color: #10B981; }

    .slab-container { background-color: #1E293B; border-radius: 15px; padding: 1rem; margin-top: 1rem; border: 1px solid #334155; border-left: 5px solid #3B82F6; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
    .slab-header { font-size: 1.1rem; font-weight: 900; color: #F8FAFC; }
    .slab-detail { color: #94A3B8; font-size: 0.9rem; }
    .slab-price { font-size: 1.4rem; font-weight: 900; color: #10B981; text-align: right; }
    
    .toast-box { padding: 10px; border-radius: 8px; background-color: #14532d; color: #bbf7d0; font-weight: bold; border: 1px solid #22c55e; margin-bottom: 10px; text-align: center;}
</style>
""", unsafe_allow_html=True)

# 2. Google Sheets Connection
def connect_to_sheets():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        # Load credentials from Streamlit Secrets
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        # Open the Sheet named "Card Inventory"
        sheet = client.open("Card Inventory").sheet1
        return sheet, None
    except Exception as e:
        return None, str(e)

# 3. Helper Functions
def get_price_range(value_str):
    if not isinstance(value_str, str): return 0.0, 0.0
    numbers = re.findall(r"[\d,\.]+", value_str)
    if not numbers: return 0.0, 0.0
    clean_nums = [float(n.replace(",", "")) for n in numbers if n.replace(",", "").replace(".", "").isdigit()]
    if not clean_nums: return 0.0, 0.0
    if len(clean_nums) == 1: return clean_nums[0], clean_nums[0]
    else: return min(clean_nums), max(clean_nums)

def save_to_google_sheets(data_dict):
    sheet, err = connect_to_sheets()
    if sheet:
        try:
            # Check if headers exist, if not add them
            if not sheet.row_values(1):
                headers = ['Player', 'Year', 'Set', 'Team', 'Card_Number', 'Variation', 'Condition_Notes', 'Estimated_Raw_Value', 'Archive_Location', 'Search_Source']
                sheet.append_row(headers)
            
            # Create row data
            row = [
                data_dict.get('Player', ''),
                data_dict.get('Year', ''),
                data_dict.get('Set', ''),
                data_dict.get('Team', ''),
                data_dict.get('Card_Number', ''),
                data_dict.get('Variation', ''),
                data_dict.get('Condition_Notes', ''),
                data_dict.get('Estimated_Raw_Value', ''),
                data_dict.get('Archive_Location', ''),
                "Google Grounding" # Mark that we used live search
            ]
            sheet.append_row(row)
            return True
        except Exception as e:
            return False
    return False

# 4. Initialize State
if 'inventory' not in st.session_state:
    st.session_state.inventory = []

# 5. Sidebar
with st.sidebar:
    st.title("💎 Collection Stats")
    
    # Check Cloud Connection
    sheet_conn, conn_err = connect_to_sheets()
    if sheet_conn:
        st.success("🟢 Cloud Connected")
    else:
        st.error(f"🔴 Cloud Error: {conn_err}")

    total_low, total_high = 0.0, 0.0
    for item in st.session_state.inventory:
        val_str = str(item.get('Estimated_Raw_Value', '0'))
        low, high = get_price_range(val_str)
        total_low += low
        total_high += high
    
    st.metric(label="Total Value (Est.)", value=f"${total_low:,.0f} - ${total_high:,.0f}")
    st.caption(f"{len(st.session_state.inventory)} items scanned in this session.")
    
    st.divider()
    st.info("ℹ️ Items are automatically saved to your 'Card Inventory' Google Sheet.")

# 6. SPLIT LAYOUT
col_action, col_data = st.columns([1, 1.2], gap="large")

# --- LEFT COLUMN: ACTION ZONE ---
with col_action:
    # Logo
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
    with st.expander("⚙️ Session Settings", expanded=True):
        archive_location = st.text_input("📦 Archive Box / Location", value="Box 1")
        series_hint = st.text_input("🔍 Series Hint (Optional)", placeholder="e.g. '1986 Fleer'")

    # Upload Tabs
    st.markdown("### 📸 Scan Tools")
    tab_single, tab_batch = st.tabs(["💎 Single Item", "🚀 Batch Dig"])

    # --- TAB 1: SINGLE ---
    with tab_single:
        col_f, col_b = st.columns(2)
        with col_f: s_front = st.file_uploader("Front (Req)", type=['jpg','png','jpeg'], key="sf")
        with col_b: s_back = st.file_uploader("Back (Opt)", type=['jpg','png','jpeg'], key="sb")
        
        if st.button("🔍 Analyze Single", type="primary", use_container_width=True):
            if not s_front: st.warning("Need Front Image")
            else:
                status = st.empty()
                status.write("Analyzing & Searching Market...")
                try:
                    # NEW GEMINI API CLIENT SETUP
                    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
                    
                    ctx = f"HINT: {series_hint}" if series_hint else ""
                    prompt_text = f"""Identify item. Search the web for current market sales/sold listings to determine value. 
                    JSON: 'Player','Team','Year','Set','Card_Number','Variation','Condition_Notes','Estimated_Raw_Value' ($ Range). {ctx}"""
                    
                    inputs = [prompt_text, Image.open(s_front)]
                    if s_back: inputs.append(Image.open(s_back))
                    
                    # Call new API WITH SEARCH GROUNDING
                    response = client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=inputs,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            tools=[types.Tool(google_search=types.GoogleSearch())] # <--- THE MAGIC SEARCH TOOL
                        )
                    )
                    
                    new = json.loads(response.text)
                    new['Archive_Location'] = archive_location
                    
                    # SAVE TO CLOUD & SESSION
                    cloud_success = save_to_google_sheets(new)
                    st.session_state.inventory.append(new)
                    
                    st.markdown(f"""
                    <div class="slab-container">
                        <div class="slab-header">✅ {new.get('Player')}</div>
                        <div class="slab-detail">{new.get('Year')} {new.get('Set')} #{new.get('Card_Number')}</div>
                        <div class="slab-price">{new.get('Estimated_Raw_Value')}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if cloud_success: st.toast("☁️ Saved to Google Sheets!", icon="✅")
                    else: st.toast("⚠️ Saved locally only (Check Sheet connection)", icon="⚠️")
                    
                except Exception as e: st.error(f"Error: {e}")

    # --- TAB 2: BATCH ---
    with tab_batch:
        st.info("Order: Front, Back, Front, Back...")
        b_files = st.file_uploader("Upload Batch", type=['jpg','png','jpeg'], accept_multiple_files=True, key="bf")
        
        if st.button("🚀 Run Batch", type="primary", use_container_width=True):
            if not b_files: st.warning("No files")
            else:
                sorted_files = sorted(b_files, key=lambda x: x.name)
                if len(sorted_files) % 2 != 0: st.error("Uneven batch! Need pairs.")
                else:
                    prog = st.progress(0)
                    stat = st.empty()
                    total = len(sorted_files)//2
                    
                    # Initialize API Client once
                    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
                    
                    for i in range(0, len(sorted_files), 2):
                        stat.markdown(f"**Card {(i//2)+1}/{total}**")
                        try:
                            ctx = f"HINT: {series_hint}" if series_hint else ""
                            prompt_text = f"""Identify item using Front (Img1) & Back (Img2). Search the web for current market sales to determine value.
                            JSON keys: 'Player','Team','Year','Set','Card_Number','Variation','Condition_Notes','Estimated_Raw_Value'. {ctx}"""
                            
                            inputs = [prompt_text, Image.open(sorted_files[i]), Image.open(sorted_files[i+1])]
                            
                            # BATCH CALL WITH SEARCH GROUNDING
                            response = client.models.generate_content(
                                model="gemini-1.5-flash",
                                contents=inputs,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                    tools=[types.Tool(google_search=types.GoogleSearch())] # <--- THE MAGIC SEARCH TOOL
                                )
                            )
                            
                            new = json.loads(response.text)
                            new['Archive_Location'] = archive_location
                            
                            # SAVE TO CLOUD & SESSION
                            cloud_success = save_to_google_sheets(new)
                            st.session_state.inventory.append(new)
                            
                            if cloud_success: st.toast(f"Item {(i//2)+1} Saved to Cloud", icon="☁️")
                            
                        except Exception as e: st.error(f"Error: {e}")
                        prog.progress(((i//2)+1)/total)
                        time.sleep(4)
                    
                    st.success("Batch Done! All items saved to Google Sheets.")
                    time.sleep(1)
                    st.rerun()

# --- RIGHT COLUMN: DATA ZONE ---
with col_data:
    st.markdown("### 📋 Live Inventory")
    if len(st.session_state.inventory) > 0:
        df = pd.DataFrame(st.session_state.inventory)
        cols = ['Player', 'Year', 'Set', 'Card_Number', 'Variation', 'Estimated_Raw_Value', 'Archive_Location', 'Condition_Notes']
        visible_cols = [c for c in cols if c in df.columns]
        st.dataframe(df[visible_cols], use_container_width=True, height=600, hide_index=True)
    else:
        st.info("Waiting for scans... Your list will appear here.")
