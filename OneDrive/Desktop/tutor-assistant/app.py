import streamlit as st
import pdfplumber
from google import genai
import tempfile
import time

# Create the Gemini client using the key from secrets (never hard-code it here!)
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

MODEL_NAME = "gemini-3.1-flash-lite"

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
                prompt = f"Summarize the following study notes in clear bullet points:\n\n{extracted_text}"
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt,
                )

            st.subheader("AI Summary")
            st.write(response.text)

st.header("Step 2: Upload a Video")
video_file = st.file_uploader("Upload your video recording here", type=["mp4", "mov"])

if video_file is not None:
    st.success(f"Received file: {video_file.name}")
    st.video(video_file)

    if st.button("🎬 Transcribe & Summarize this Video"):
        with st.spinner("Uploading video to Gemini... this can take a minute for larger files."):
            # Gemini needs the video saved as an actual file on disk first,
            # so we write it to a temporary file.
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                tmp.write(video_file.getvalue())
                tmp_path = tmp.name

            uploaded_video = client.files.upload(file=tmp_path)

            # Gemini needs a little time to finish processing the video
            # before we can ask questions about it.
            while uploaded_video.state.name == "PROCESSING":
                time.sleep(3)
                uploaded_video = client.files.get(name=uploaded_video.name)

        if uploaded_video.state.name == "FAILED":
            st.error("Sorry, Gemini couldn't process this video. Try a shorter clip.")
        else:
            with st.spinner("Watching and summarizing the video..."):
                prompt = (
                    "Watch this video and provide: "
                    "1) A full transcript of what is said, "
                    "2) A short bullet-point summary of the key points."
                )
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[uploaded_video, prompt],
                )

            st.subheader("Video Transcript & Summary")
            st.write(response.text)