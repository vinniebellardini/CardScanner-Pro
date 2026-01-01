import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

# 1. Configure Page
st.set_page_config(page_title="CardScanner Pro", page_icon="🎴", layout="wide")

# 2. Initialize Inventory State
if 'inventory' not in st.session_state:
    st.session_state.inventory = []

# 3. Sidebar: Load & Save
with st.sidebar:
    st.header("📁 File Management")
    st.info("To resume a previous session, upload your last Inventory CSV below.")
    
    # LOAD: Resume previous work
    uploaded_file = st.file_uploader("Upload 'inventory.csv' to resume", type=['csv'])
    
    # Logic to load the file into the app's memory
    if uploaded_file is not None:
        # Only load if we haven't already (prevents overwriting new scans)
        if len(st.session_state.inventory) == 0:
            try:
                df_load = pd.read_csv(uploaded_file)
                st.session_state.inventory = df_load.to_dict('records')
                st.success(f"✅ Loaded {len(df_load)} cards from file!")
            except Exception as e:
                st.error("Error loading file. Make sure it is a valid CSV.")

    st.markdown("---")
    
    # SAVE: Download current work
    if len(st.session_state.inventory) > 0:
        st.write("### 💾 Save Progress")
        df_save = pd.DataFrame(st.session_state.inventory)
        csv = df_save.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="Download Updated CSV",
            data=csv,
            file_name="card_inventory.csv",
            mime="text/csv",
            key="download-btn"
        )

# 4. Main App Area
st.title("🎴 CardScanner Pro")
st.markdown("Snap a photo, get the data, and build your list.")

# 5. Secure API Key
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except KeyError:
    st.error("API Key not found. Please set GOOGLE_API_KEY in Streamlit Secrets.")
    st.stop()

# 6. Scanning Interface
col1, col2 = st.columns(2)
with col1:
    st.write("**Front (Required)**")
    front_image = st.file_uploader("Upload Front", type=['jpg', 'png', 'jpeg'], key="front")
    if front_image:
        st.image(front_image, use_container_width=True)

with col2:
    st.write("**Back (Optional)**")
    back_image = st.file_uploader("Upload Back", type=['jpg', 'png', 'jpeg'], key="back")
    if back_image:
        st.image(back_image, use_container_width=True)

# 7. Analysis Logic
if st.button("Analyze & Add to List", type="primary"):
    if not front_image:
        st.warning("Please upload at least the front of the card!")
    else:
        with st.spinner("AI is researching this card..."):
            try:
                # Force JSON format for clean data entry
                model = genai.GenerativeModel(
                    'gemini-1.5-flash',
                    generation_config={"response_mime_type": "application/json"}
                )
                
                # Prompt optimized for spreadsheet columns
                prompt = """
                Identify this sports card. Return a single JSON object with these exact keys:
                'Player', 'Year', 'Set', 'Card_Number', 'Variation', 'Condition_Notes', 'Estimated_Raw_Value'
                If a value is unknown, use 'N/A'.
                """
                
                inputs = [prompt, Image.open(front_image)]
                if back_image:
                    inputs.append(Image.open(back_image))

                response = model.generate_content(inputs)
                
                # Parse and Add
                new_entry = json.loads(response.text)
                st.session_state.inventory.append(new_entry)
                
                st.success(f"✅ Added: {new_entry.get('Player')} ({new_entry.get('Year')})")
                
            except Exception as e:
                st.error(f"Error: {e}")

# 8. Show the Data Table
st.markdown("---")
st.subheader(f"Current Inventory ({len(st.session_state.inventory)} cards)")

if len(st.session_state.inventory) > 0:
    st.dataframe(pd.DataFrame(st.session_state.inventory), use_container_width=True)
else:
    st.info("Inventory is empty. Upload a CSV in the sidebar to resume, or scan a card to start.")
