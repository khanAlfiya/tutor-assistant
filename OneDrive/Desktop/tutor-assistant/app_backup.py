import streamlit as st
import pdfplumber
import google.generativeai as genai

# Load the API key from the secrets file (never hard-code it here!)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# This is the title that shows at the top of your web page
st.title("📚 My Tutor Assistant")
st.write("Welcome! This is the very first version of your project.")

st.header("Step 1: Upload a PDF")
pdf_file = st.file_uploader("Upload your PDF notes here", type=["pdf"])

if pdf_file is not None:
    st.success(f"Received file: {pdf_file.name}")

    # Open the PDF and pull the text out of every page
    extracted_text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                extracted_text += page_text + "\n"

    st.subheader("Extracted PDF Text")
    st.text_area("Here's what we found inside your PDF:", extracted_text, height=300)

    # Only try to summarize if we actually found some text
    if extracted_text.strip():
        if st.button("✨ Summarize this PDF"):
            with st.spinner("Asking Gemini to summarize your notes..."):
                model = genai.GenerativeModel("gemini-3.1-flash-lite")
                prompt = f"Summarize the following study notes in clear bullet points:\n\n{extracted_text}"
                response = model.generate_content(prompt)

            st.subheader("AI Summary")
            st.write(response.text)

st.header("Step 2: Upload a Video")
video_file = st.file_uploader("Upload your video recording here", type=["mp4", "mov"])

if video_file is not None:
    st.success(f"Received file: {video_file.name}")
    st.video(video_file)