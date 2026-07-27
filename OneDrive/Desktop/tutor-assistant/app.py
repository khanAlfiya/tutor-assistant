import streamlit as st
import pdfplumber
from google import genai
import tempfile
import time
import json

# ------------------ PAGE SETUP ------------------
st.set_page_config(
    page_title="My Tutor Assistant",
    page_icon="📚",
    layout="wide",
)

@st.cache_resource
def get_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

client = get_client()
MODEL_NAME = "gemini-3.1-flash-lite"

# ------------------ QUIZ HELPER ------------------
def generate_quiz(source_content, source_label):
    """Ask Gemini for 5 MCQs in JSON format based on the given content."""
    quiz_prompt = (
        "Create exactly 5 multiple-choice questions based on this material. "
        "Reply with ONLY valid JSON (no markdown, no extra text), in this exact format: "
        '[{"question": "...", "options": ["A", "B", "C", "D"], "answer": "A"}, ...] '
        "The 'answer' field must exactly match one of the options."
    )
    if isinstance(source_content, str):
        contents = f"{quiz_prompt}\n\nMaterial:\n{source_content}"
    else:
        contents = [source_content, quiz_prompt]

    response = client.models.generate_content(model=MODEL_NAME, contents=contents)

    # Gemini sometimes wraps JSON in ```json fences even when told not to — strip those out
    raw = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def show_quiz(quiz_key):
    """Render an already-generated quiz stored in session_state, with a Check Answers button."""
    quiz = st.session_state[quiz_key]
    user_answers = {}

    for i, q in enumerate(quiz):
        st.markdown(f"**{i + 1}. {q['question']}**")
        user_answers[i] = st.radio(
            f"q{i}", q["options"], key=f"{quiz_key}_q{i}", label_visibility="collapsed"
        )
        st.markdown("")

    if st.button("✅ Check Answers", key=f"{quiz_key}_check"):
        score = sum(1 for i, q in enumerate(quiz) if user_answers[i] == q["answer"])
        st.success(f"You scored {score} / {len(quiz)}")
        for i, q in enumerate(quiz):
            if user_answers[i] != q["answer"]:
                st.markdown(f"❌ Q{i + 1}: Correct answer was **{q['answer']}**")


with st.sidebar:
    st.title("📚 Tutor Assistant")
    st.caption("Your AI-powered study companion")
    st.markdown("---")
    st.markdown("**How it works:**")
    st.markdown(
        "1. Upload a PDF or a video\n"
        "2. Get an instant AI summary\n"
        "3. Chat with it to ask follow-up questions"
    )
    st.markdown("---")
    st.caption("Built with Streamlit + Gemini")

# ------------------ HEADER ------------------
st.markdown("## 👋 Welcome back!")
st.write("Upload your study material below and let AI do the heavy lifting.")
st.markdown("")

# ------------------ TABS ------------------
tab1, tab2 = st.tabs(["📄  PDF Notes", "🎬  Video Lecture"])

# ================== PDF TAB ==================
with tab1:
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("Upload")
        pdf_file = st.file_uploader("Upload your PDF notes here", type=["pdf"], key="pdf")

        if pdf_file is not None:
            st.success(f"✅ {pdf_file.name}")

            # Only re-extract text if this is a new file (avoids redoing work on every click)
            if st.session_state.get("pdf_name") != pdf_file.name:
                extracted_text = ""
                with pdfplumber.open(pdf_file) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            extracted_text += page_text + "\n"
                st.session_state["pdf_text"] = extracted_text
                st.session_state["pdf_name"] = pdf_file.name
                st.session_state["pdf_chat"] = None  # reset chat for the new file

            extracted_text = st.session_state["pdf_text"]

            with st.expander("📖 View extracted text"):
                st.text_area("Extracted content", extracted_text, height=250, label_visibility="collapsed")

    with col2:
        st.subheader("AI Summary")
        if pdf_file is not None and st.session_state.get("pdf_text", "").strip():
            if st.button("✨ Summarize this PDF", use_container_width=True):
                with st.spinner("Reading your notes..."):
                    prompt = f"Summarize the following study notes in clear bullet points:\n\n{st.session_state['pdf_text']}"
                    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
                st.markdown(response.text)
        else:
            st.info("Upload a PDF on the left to get started.")

    # ---------- CHAT WITH PDF ----------
    if pdf_file is not None and st.session_state.get("pdf_text", "").strip():
        st.markdown("---")
        st.subheader("💬 Chat with this PDF")

        # Create a fresh chat session (with the PDF text as context) if we don't have one yet
        if st.session_state.get("pdf_chat") is None:
            chat = client.chats.create(model=MODEL_NAME)
            chat.send_message(
                f"You are a helpful tutor. Here are some study notes. "
                f"Answer the student's future questions using only this material:\n\n{st.session_state['pdf_text']}"
            )
            st.session_state["pdf_chat"] = chat
            st.session_state["pdf_messages"] = []

        # Show past messages in this chat
        for msg in st.session_state["pdf_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Input box for a new question
        pdf_question = st.chat_input("Ask a question about this PDF...", key="pdf_chat_input")
        if pdf_question:
            st.session_state["pdf_messages"].append({"role": "user", "content": pdf_question})
            with st.chat_message("user"):
                st.markdown(pdf_question)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    reply = st.session_state["pdf_chat"].send_message(pdf_question)
                st.markdown(reply.text)
            st.session_state["pdf_messages"].append({"role": "assistant", "content": reply.text})

    # ---------- QUIZ FROM PDF ----------
    if pdf_file is not None and st.session_state.get("pdf_text", "").strip():
        st.markdown("---")
        st.subheader("📝 Test Yourself")

        if st.button("Generate a Quiz from this PDF"):
            with st.spinner("Writing quiz questions..."):
                st.session_state["pdf_quiz"] = generate_quiz(st.session_state["pdf_text"], "PDF")

        if st.session_state.get("pdf_quiz"):
            show_quiz("pdf_quiz")

# ================== VIDEO TAB ==================
with tab2:
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("Upload")
        video_file = st.file_uploader("Upload your video recording here", type=["mp4", "mov"], key="video")

        if video_file is not None:
            st.success(f"✅ {video_file.name}")
            st.video(video_file)

    with col2:
        st.subheader("Transcript & Summary")
        if video_file is not None:
            if st.button("🎬 Transcribe & Summarize", use_container_width=True):
                with st.spinner("Uploading video to Gemini..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                        tmp.write(video_file.getvalue())
                        tmp_path = tmp.name

                    uploaded_video = client.files.upload(file=tmp_path)
                    while uploaded_video.state.name == "PROCESSING":
                        time.sleep(3)
                        uploaded_video = client.files.get(name=uploaded_video.name)

                if uploaded_video.state.name == "FAILED":
                    st.error("Sorry, Gemini couldn't process this video. Try a shorter clip.")
                else:
                    st.session_state["uploaded_video"] = uploaded_video
                    st.session_state["video_chat"] = None  # reset chat for the new video

                    with st.spinner("Watching and summarizing..."):
                        prompt = (
                            "Watch this video and provide: "
                            "1) A full transcript of what is said, "
                            "2) A short bullet-point summary of the key points."
                        )
                        response = client.models.generate_content(
                            model=MODEL_NAME,
                            contents=[uploaded_video, prompt],
                        )
                    st.markdown(response.text)
        else:
            st.info("Upload a video on the left to get started.")

    # ---------- CHAT WITH VIDEO ----------
    if video_file is not None and st.session_state.get("uploaded_video") is not None:
        st.markdown("---")
        st.subheader("💬 Chat with this Video")

        if st.session_state.get("video_chat") is None:
            chat = client.chats.create(model=MODEL_NAME)
            chat.send_message([
                st.session_state["uploaded_video"],
                "You are a helpful tutor. Answer the student's future questions using only what is said in this video.",
            ])
            st.session_state["video_chat"] = chat
            st.session_state["video_messages"] = []

        for msg in st.session_state["video_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        video_question = st.chat_input("Ask a question about this video...", key="video_chat_input")
        if video_question:
            st.session_state["video_messages"].append({"role": "user", "content": video_question})
            with st.chat_message("user"):
                st.markdown(video_question)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    reply = st.session_state["video_chat"].send_message(video_question)
                st.markdown(reply.text)
            st.session_state["video_messages"].append({"role": "assistant", "content": reply.text})

    # ---------- QUIZ FROM VIDEO ----------
    if video_file is not None and st.session_state.get("uploaded_video") is not None:
        st.markdown("---")
        st.subheader("📝 Test Yourself")

        if st.button("Generate a Quiz from this Video"):
            with st.spinner("Writing quiz questions..."):
                st.session_state["video_quiz"] = generate_quiz(st.session_state["uploaded_video"], "Video")

        if st.session_state.get("video_quiz"):
            show_quiz("video_quiz")