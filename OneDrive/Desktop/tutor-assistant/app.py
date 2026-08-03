import streamlit as st
import pdfplumber
from google import genai
import tempfile
import time
import json
import sqlite3
from datetime import datetime

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

# ------------------ CUSTOM STYLING ------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        font-size: 16px !important;
    }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span,
    [data-testid="stText"],
    [data-testid="stCaptionContainer"],
    [data-testid="stWidgetLabel"] p,
    [data-testid="stFileUploaderFileName"],
    [data-testid="stChatMessageContent"] p,
    .stTextInput input,
    .stTextArea textarea {
        font-size: 1rem !important;
        line-height: 1.55 !important;
    }
    h1, h2, h3, .hero-banner h1 {
        font-family: 'Poppins', sans-serif;
    }

    /* Full-page rich gradient background (animated, no plain white) */
    .stApp {
        background: linear-gradient(160deg, #0F3D2E 0%, #1B5E20 25%, #2E7D32 55%, #66BB6A 85%, #A5D6A7 100%);
        background-size: 200% 200%;
        animation: gradientShift 18s ease infinite;
    }
    @keyframes gradientShift {
        0% { background-position: 0% 0%; }
        50% { background-position: 100% 100%; }
        100% { background-position: 0% 0%; }
    }

    /* Main content area — glass card, with gentle fade-in */
    .block-container {
        background: rgba(255, 255, 255, 0.92);
        border-radius: 20px;
        padding: 2.2rem 2.5rem !important;
        margin-top: 1rem;
        box-shadow: 0 12px 32px rgba(0,0,0,0.18);
        backdrop-filter: blur(6px);
        position: relative;
        z-index: 1;
        animation: fadeInUp 0.6s ease-out;
    }
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(14px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Hero banner */
    .hero-banner {
        background: linear-gradient(135deg, #1B5E20 0%, #43A047 55%, #81C784 100%);
        border-radius: 18px;
        padding: 2.2rem 2.5rem;
        margin-bottom: 1.8rem;
        color: white;
        box-shadow: 0 8px 24px rgba(27, 94, 32, 0.35);
    }
    .hero-banner h1 {
        color: white !important;
        margin: 0;
        font-size: 2.2rem;
    }
    .hero-banner p {
        color: #EAF7EC;
        margin-top: 0.4rem;
        font-size: 1.05rem;
    }

    /* Feature pills row */
    .pill {
        display: inline-block;
        background: rgba(255,255,255,0.22);
        border-radius: 20px;
        padding: 0.3rem 0.9rem;
        margin-right: 0.5rem;
        margin-top: 0.3rem;
        font-size: 0.85rem;
        color: white;
        backdrop-filter: blur(4px);
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        border: none;
        background: linear-gradient(135deg, #2E7D32, #43A047);
        color: white;
        font-weight: 600;
        padding: 0.5rem 1.2rem;
        transition: all 0.15s ease-in-out;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #1B5E20, #2E7D32);
        color: white;
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(46, 125, 50, 0.3);
    }

    /* Tabs */
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        font-size: 1rem;
    }
    .stTabs [aria-selected="true"] {
        color: #2E7D32 !important;
    }

    /* Headers */
    h2, h3 {
        color: #1B5E20;
    }

    /* Bordered containers (summary/chat/quiz cards) get a soft glass look */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #F8FAF8;
        border-radius: 14px !important;
        border: 1px solid #DCEBDC !important;
    }

    /* File type badges (used in History tab) */
    .badge-pdf {
        background: #E3F2FD;
        color: #1565C0;
        padding: 0.15rem 0.6rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-video {
        background: #F3E5F5;
        color: #6A1B9A;
        padding: 0.15rem 0.6rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1B5E20 0%, #2E7D32 100%);
    }
    section[data-testid="stSidebar"] * {
        color: #F1F8F4 !important;
    }
</style>
""", unsafe_allow_html=True)

# ------------------ DATABASE (SQLite) ------------------
def get_db():
    conn = sqlite3.connect("tutor_assistant.db", check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            filename TEXT,
            summary TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            note_text TEXT,
            created_at TEXT
        )
    """)
    return conn


def save_session(file_type, filename, summary):
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (type, filename, summary, created_at) VALUES (?, ?, ?, ?)",
        (file_type, filename, summary, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()
    conn.close()


def get_all_sessions():
    conn = get_db()
    rows = conn.execute("SELECT * FROM sessions ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def add_note(session_id, note_text):
    conn = get_db()
    conn.execute(
        "INSERT INTO notes (session_id, note_text, created_at) VALUES (?, ?, ?)",
        (session_id, note_text, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()
    conn.close()


def get_notes(session_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notes WHERE session_id = ? ORDER BY id DESC", (session_id,)
    ).fetchall()
    conn.close()
    return rows



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
        "3. Chat with it to ask follow-up questions\n"
        "4. Test yourself with an AI-generated quiz"
    )
    st.markdown("---")
    with st.expander("ℹ️ About this project"):
        st.markdown(
            "**My Tutor Assistant** turns your study material into "
            "an interactive learning session.\n\n"
            "**Built with:**\n"
            "- Streamlit (interface)\n"
            "- Google Gemini API (summaries, chat, quizzes)\n"
            "- pdfplumber (PDF text extraction)\n"
            "- SQLite (session history)\n\n"
            "Made as a learning project while studying AI/ML engineering."
        )
    st.caption("Built with Streamlit + Gemini")

# ------------------ HERO BANNER ------------------
st.markdown("""
<div class="hero-banner">
    <h1>📚 My Tutor Assistant</h1>
    <p>Upload your study material and let AI do the heavy lifting.</p>
    <div style="margin-top: 0.8rem;">
        <span class="pill">✨ AI Summaries</span>
        <span class="pill">💬 Ask Questions</span>
        <span class="pill">📝 Auto Quizzes</span>
        <span class="pill">📂 Saved History</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ------------------ TABS ------------------
tab1, tab2, tab3 = st.tabs(["📄  PDF Notes", "🎬  Video Lecture", "📂  History"])

# ================== PDF TAB ==================
with tab1:
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

    st.markdown("---")
    st.subheader("AI Summary")
    if pdf_file is not None and st.session_state.get("pdf_text", "").strip():
        if st.button("✨ Summarize this PDF", use_container_width=True):
            with st.spinner("Reading your notes..."):
                prompt = f"Summarize the following study notes in clear bullet points:\n\n{st.session_state['pdf_text']}"
                response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            st.session_state["pdf_summary"] = response.text
            save_session("PDF", pdf_file.name, response.text)

        if st.session_state.get("pdf_summary"):
            with st.container(border=True):
                st.markdown(st.session_state["pdf_summary"])
    else:
        st.info("Upload a PDF above to get started.")

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
        with st.container(border=True):
            if not st.session_state["pdf_messages"]:
                st.caption("Ask anything about this PDF below 👇")
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
            with st.container(border=True):
                show_quiz("pdf_quiz")

# ================== VIDEO TAB ==================
with tab2:
    st.subheader("Upload")
    video_file = st.file_uploader("Upload your video recording here", type=["mp4", "mov"], key="video")

    if video_file is not None:
        st.success(f"✅ {video_file.name}")
        video_col, _ = st.columns([2, 1])
        with video_col:
            st.video(video_file)

    st.markdown("---")
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
                st.session_state["video_summary"] = response.text
                save_session("Video", video_file.name, response.text)

        if st.session_state.get("video_summary"):
            with st.container(border=True):
                st.markdown(st.session_state["video_summary"])
    else:
        st.info("Upload a video above to get started.")

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

        with st.container(border=True):
            if not st.session_state["video_messages"]:
                st.caption("Ask anything about this video below 👇")
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
            with st.container(border=True):
                show_quiz("video_quiz")

# ================== HISTORY TAB ==================
with tab3:
    st.subheader("📂 Past Sessions")
    sessions = get_all_sessions()

    if not sessions:
        st.info("No sessions yet — summarize a PDF or video to see it appear here.")
    else:
        for s in sessions:
            session_id, file_type, filename, summary, created_at = s
            icon = "📄" if file_type == "PDF" else "🎬"
            badge_class = "badge-pdf" if file_type == "PDF" else "badge-video"
            with st.expander(f"{icon} {filename}  ·  {created_at}"):
                st.markdown(f'<span class="{badge_class}">{file_type}</span>', unsafe_allow_html=True)
                st.markdown("")
                with st.container(border=True):
                    st.markdown("**Summary:**")
                    st.markdown(summary)

                st.markdown("**📝 Your Notes**")
                with st.container(border=True):
                    notes = get_notes(session_id)
                    if not notes:
                        st.caption("No notes yet.")
                    for n in notes:
                        st.markdown(f"- {n[2]}  \n  <sub>{n[3]}</sub>", unsafe_allow_html=True)

                new_note = st.text_input("Add a note...", key=f"note_input_{session_id}")
                if st.button("Save Note", key=f"note_btn_{session_id}"):
                    if new_note.strip():
                        add_note(session_id, new_note.strip())
                        st.rerun()

# ------------------ FOOTER ------------------
st.markdown("---")
st.markdown(
    """
    <div style="text-align:center; padding: 1rem 0; color: #4C6B4E; font-size: 0.9rem;">
        Made with 💚 using Streamlit &amp; Google Gemini &nbsp;·&nbsp; A learning project
    </div>
    """,
    unsafe_allow_html=True,
)