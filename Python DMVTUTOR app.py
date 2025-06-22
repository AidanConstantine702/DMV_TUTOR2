"""SC DMV Tutor – no‑login version
Paste Part 1, Part 2, then Part 3 into a single `app.py`.
"""

import streamlit as st
from openai import OpenAI
from io import BytesIO
from reportlab.pdfgen import canvas
import datetime, os, re

# ------------------------------------------------------------
# PAGE CONFIG (must be first Streamlit call)
# ------------------------------------------------------------
st.set_page_config(page_title="SC DMV AI Tutor", layout="centered")

# ------------------------------------------------------------
# OPENAI client (env var)
# ------------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY)

# ------------------------------------------------------------
# SYSTEM PROMPT & helpers (unchanged)
# ------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a certified South Carolina DMV Permit Test Tutor specializing in helping teenagers "
    "prepare for their written learner’s permit exam.\n\n"
    "Your job is to clearly explain driving laws, road signs, traffic rules, and safety principles "
    "using only the information found in:\n"
    "- The South Carolina Driver’s Manual (2024 edition), and\n"
    "- The official SC DMV Practice Test: https://practice.dmv-test-pro.com/south-carolina/sc-permit-practice-test-19/\n\n"
    "Key instructions:\n"
    "- ONLY use facts found in the manual or practice test.\n"
    "- DO NOT make up laws, facts, or explanations.\n"
    "- Use language appropriate for 15- to 17-year-olds.\n"
    "- When creating a quiz, strictly follow this format:\n"
    "Question 1: [question text]\nA. [option A]\nB. [option B]\nC. [option C]\nD. [option D]\nAnswer: [A/B/C/D]\n\n"
    "- When creating flashcards, strictly follow this format:\nQ: [question]\nA: [answer]\n"
    "- Return exactly 10 Q/A flashcards and nothing else. No numbering, no MCQ, no explanations, no commentary.\n"
    "- Start each question with 'Question [number]:'.\n"
    "- Return EXACTLY N questions in the specified format.\n"
    "- DO NOT include explanations, hints, or any extra text.\n"
    "- Make sure all questions are unique and properly numbered.\n\n"
    "**Failure to follow these instructions will result in broken output.**\n\n"
    "Proactive guidance:\n"
    "- After answering the user's question, briefly suggest ONE effective test‑taking or study strategy (e.g. spaced repetition, practice under timed conditions).\n"
    "- Then, recommend a relevant feature of this website (Practice Quiz, Flashcards, Study Plan, or Progress Tracker) and explain in one sentence how using it will help them master the permit test faster.\n"
    "- Keep the tip + recommendation to a total of **two sentences** so it doesn't feel spammy."
)

def query_gpt(messages):
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=messages
    )
    return response.choices[0].message.content

def parse_quiz(raw_text):
    pattern = re.compile(
        r"Question\s+\d+:\s*(.*?)\nA\.\s*(.*?)\nB\.\s*(.*?)\nC\.\s*(.*?)\nD\.\s*(.*?)\nAnswer:\s*([A-D])",
        re.DOTALL,
    )
    matches = pattern.findall(raw_text)
    questions = []
    for match in matches:
        q, a, b, c, d, ans = match
        questions.append({
            "question": q.strip(),
            "options": {"A": a.strip(), "B": b.strip(), "C": c.strip(), "D": d.strip()},
            "answer": ans.strip(),
        })
    return questions

def parse_flashcards(raw_text):
    pattern = re.compile(r"Q:\s*(.*?)\nA:\s*(.*?)(?=\nQ:|\Z)", re.DOTALL)
    return [{"question": q.strip(), "answer": a.strip()} for q, a in pattern.findall(raw_text)]

def create_pdf(text: str):
    buf = BytesIO()
    pdf = canvas.Canvas(buf)
    y = 800
    for line in text.split("\n"):
        if y < 40:
            pdf.showPage(); y = 800
        pdf.drawString(40, y, line)
        y -= 15
    pdf.save(); buf.seek(0)
    return buf

# ------------------------------------------------------------
# UI HEADER + SIDEBAR NAV  (no login gate)
# ------------------------------------------------------------
st.title("SC DMV Permit Test Tutor")

nav_items = [
    "Tutor Chat",
    "Practice Quiz",
    "Flashcards",
    "Study Plan",
    "Progress Tracker",
]
menu = st.sidebar.radio("Navigation", nav_items)
# ------------------------------------------------------------
# MAIN APP UI (continued)
# ------------------------------------------------------------

st.title("SC DMV Permit Test Tutor")

nav_items = [
    "Tutor Chat",
    "Practice Quiz",
    "Flashcards",
    "Study Plan",
    "Progress Tracker",
]
menu = st.sidebar.radio("Navigation", nav_items)

# === Tutor Chat ===
if menu == "Tutor Chat":
    st.header("Chat with Your DMV Tutor")
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    for msg in st.session_state["chat_history"][1:]:
        st.chat_message(msg["role"]).write(msg["content"])

    user_input = st.chat_input("Ask a question about the permit test…")
    if user_input:
        st.session_state["chat_history"].append({"role": "user", "content": user_input})
        with st.spinner("Thinking…"):
            response = query_gpt(st.session_state["chat_history"])
        st.session_state["chat_history"].append({"role": "assistant", "content": response})
        st.chat_message("user").write(user_input)
        st.chat_message("assistant").write(response)

    if st.button("Clear Chat"):
        st.session_state["chat_history"] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        st.rerun()

# === Practice Quiz ===
elif menu == "Practice Quiz":
    st.header("Practice Quiz")
    st.info("For each question, select your answer. No answer is selected by default. You must answer every question to submit the quiz.")

    num = st.slider("Number of Questions", 5, 10, 5)
    topic = st.selectbox(
        "Quiz Topic",
        ["General", "Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"],
    )

    if st.button("Generate Quiz"):
        prompt = (
            f"Generate exactly {num} multiple-choice questions for the topic '{topic}' from the South Carolina DMV permit test. "
            "Each must follow this format:\n"
            "Question 1: [question]\n"
            "A. [option A]\n"
            "B. [option B]\n"
            "C. [option C]\n"
            "D. [option D]\n"
            "Answer: [correct option letter]\n\n"
            "Return ONLY the questions — no explanations, no commentary, no extra text. "
            "Number all questions correctly and provide the correct answer for each."
        )
        with st.spinner("Creating your quiz…"):
            raw_quiz = query_gpt([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ])
            st.session_state["quiz_data"] = parse_quiz(raw_quiz)
            st.session_state["quiz_answers"] = {}
            st.session_state["quiz_submitted"] = False

    if "quiz_data" in st.session_state:
        st.subheader("Take the Quiz")
        quiz_data = st.session_state["quiz_data"]
        all_answered = True

        for idx, q in enumerate(quiz_data):
            label = f"{idx + 1}. {q['question']}"
            options = ["Select an answer…"] + [f"{key}. {val}" for key, val in q["options"].items()]
            selected = st.radio(label, options, key=f"q_{idx}", index=0)

            if selected != "Select an answer…":
                st.session_state["quiz_answers"][idx] = selected[0]
            else:
                st.session_state["quiz_answers"][idx] = None
                all_answered = False

        if st.button("Submit Quiz", disabled=not all_answered):
            st.session_state["quiz_submitted"] = True
            correct = sum(
                1 for idx, q in enumerate(quiz_data)
                if st.session_state["quiz_answers"].get(idx) == q["answer"]
            )
            st.success(f"You got {correct} out of {len(quiz_data)} correct!")
            st.markdown("**Correct Answers:**")
            for i, q in enumerate(quiz_data):
                st.markdown(f"- Question {i + 1}: {q['answer']}")
    elif menu == "Flashcards":
        st.header("Flashcards")
        topic = st.selectbox(
            "Flashcard Topic",
            ["General", "Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"]
        )

        if st.button("Generate Flashcards"):
            prompt = (
                f"Generate 10 flashcards for the topic '{topic}' using a Q&A format only from the SC pe...
