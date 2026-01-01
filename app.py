import streamlit as st
import google.generativeai as genai
from PIL import Image

# 1. Configure the page to look like an app
st.set_page_config(page_title="CardScanner Pro", page_icon="🎴")

# 2. Add a title and simple styling
st.title("🎴 CardScanner Pro")
st.write("Upload your card photos to get an AI valuation and details.")

# 3. Handle the API Key securely
# This looks for the key in Streamlit's "Secrets"
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except KeyError:
    st.error("API Key not found. Please set GOOGLE_API_KEY in Streamlit Secrets.")
    st.stop()

# 4. Create the "Scanner" interface (Two columns for Front/Back)
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

# 5. The "Analyze" Logic
if st.button("Analyze & Save", type="primary"):
    if not front_image:
        st.warning("Please upload at least the front of the card!")
    else:
        with st.spinner("AI is analyzing your card..."):
            try:
                # Prepare the model
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Load images
                img_front = Image.open(front_image)
                inputs = ["Identify this sports card. Provide: Year, Set, Player, Card Number, and an estimated raw value range based on recent market data. Return the data as a clean summary.", img_front]
                
                if back_image:
                    img_back = Image.open(back_image)
                    inputs.append(img_back)

                # Get response
                response = model.generate_content(inputs)
                
                # Display Result
                st.success("Analysis Complete!")
                st.markdown("### Card Details")
                st.write(response.text)
                
            except Exception as e:
                st.error(f"An error occurred: {e}")

# 6. Inventory Placeholder (Visual only for now)
st.markdown("---")
st.subheader("Your Inventory")
st.info("Inventory saving features require a database connection (advanced).")