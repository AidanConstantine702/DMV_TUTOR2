import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
from io import BytesIO
from reportlab.pdfgen import canvas
import datetime
import os
import re

# ------------------------------------------------------------
# PAGE CONFIG  (must be first Streamlit call)
# ------------------------------------------------------------
st.set_page_config(page_title="SC DMV AI Tutor", layout="centered")

# ------------------------------------------------------------
# SUPABASE +  OPENAI SETUP  (reads ENV‑vars)
# ------------------------------------------------------------
SUPABASE_URL  = os.environ.get("SUPABASE_URL")
SUPABASE_KEY  = os.environ.get("SUPABASE_ANON_KEY")
OPENAI_KEY    = os.environ.get("OPENAI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client   : OpenAI = OpenAI(api_key=OPENAI_KEY)

# ------------------------------------------------------------
# HELPER – check if an email exists in paid_users table
# ------------------------------------------------------------
def is_paid_user(email: str) -> bool:
    resp = supabase.table("paid_users").select("email").eq("email", email).execute()
    return len(resp.data) > 0

# ------------------------------------------------------------
# LOGIN / SIGN‑UP  (shown to guests only)
# ------------------------------------------------------------
st.title("DMV Tutor Login")

if "user" not in st.session_state:
    mode      = st.radio("Login or Sign Up?", ["Login", "Sign Up"], horizontal=True)
    email     = st.text_input("Email")
    password  = st.text_input("Password", type="password")

    if mode == "Sign Up":
        if st.button("Sign Up"):
            res = supabase.auth.sign_up({"email": email, "password": password})
            st.success("Check your inbox to confirm!" if res.user else "Sign‑up failed.")
    else:  # LOGIN
        if st.button("Login"):
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if res.user and is_paid_user(email):
                st.session_state["user"] = email
                st.experimental_rerun()
            else:
                st.error("Login failed or you haven’t purchased access.")
else:
    # --------------------------------------------------------
    # BEGIN MAIN APP (everything indented 4 spaces)
    # --------------------------------------------------------
    # ------------------------------------------------------------
    #   MAIN APP (visible only when logged in)
    # ------------------------------------------------------------
    st.sidebar.title("Navigation")
    if st.sidebar.button("Logout"):
        del st.session_state["user"]
        st.experimental_rerun()

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
        "Question 1: [question text]\n"
        "A. [option A]\n"
        "B. [option B]\n"
        "C. [option C]\n"
        "D. [option D]\n"
        "Answer: [A/B/C/D]\n\n"
        "- When creating flashcards, strictly follow this format:\n"
        "Q: [question]\nA: [answer]\n"
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
        return [
            {
                "question": q.strip(),
                "options": {"A": a.strip(), "B": b.strip(), "C": c.strip(), "D": d.strip()},
                "answer": ans.strip(),
            }
            for q, a, b, c, d, ans in matches
        ]

    def parse_flashcards(raw_text):
        pattern = re.compile(r"Q:\s*(.*?)\nA:\s*(.*?)(?=\nQ:|\Z)", re.DOTALL)
        return [{"question": q.strip(), "answer": a.strip()} for q, a in pattern.findall(raw_text)]

    def create_pdf(text):
        buf = BytesIO(); pdf = canvas.Canvas(buf); y = 800
        for line in text.split("\n"):
            if y < 40: pdf.showPage(); y = 800
            pdf.drawString(40, y, line); y -= 15
        pdf.save(); buf.seek(0); return buf

    # ------------------ NAVIGATION ------------------
    st.title("SC DMV Permit Test Tutor")

    nav_items = ["Tutor Chat", "Practice Quiz", "Flashcards", "Study Plan", "Progress Tracker"]
    menu = st.sidebar.radio("Navigation", nav_items)

    # ------------------ TUTOR CHAT ------------------
    if menu == "Tutor Chat":
        st.header("Chat with Your DMV Tutor")
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in st.session_state.chat_history[1:]:
            st.chat_message(msg["role"]).write(msg["content"])
        question = st.chat_input("Ask a question about the permit test…")
        if question:
            st.session_state.chat_history.append({"role": "user", "content": question})
            with st.spinner("Thinking..."):
                answer = query_gpt(st.session_state.chat_history)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
            st.chat_message("user").write(question)
            st.chat_message("assistant").write(answer)
        if st.button("Clear Chat"):
            st.session_state.chat_history = [{"role": "system", "content": SYSTEM_PROMPT}]
            st.rerun()

    # ------------------ PRACTICE QUIZ ------------------
    elif menu == "Practice Quiz":
        st.header("Practice Quiz")
        st.info("For each question, select your answer. All must be answered before submission.")
        num   = st.slider("Number of Questions", 5, 10, 5)
        topic = st.selectbox("Quiz Topic", ["General", "Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"])

        if st.button("Generate Quiz"):
            prompt = (
                f"Generate exactly {num} multiple‑choice questions for '{topic}' from the SC permit test. "
                "Use the specified quiz format and include the correct answer letter after each question."
            )
            with st.spinner("Creating your quiz…"):
                raw = query_gpt([
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ])
            st.session_state.quiz_data   = parse_quiz(raw)
            st.session_state.quiz_ans    = {}
            st.session_state.quiz_done   = False

        if "quiz_data" in st.session_state:
            st.subheader("Take the Quiz")
            all_done = True
            for i, q in enumerate(st.session_state.quiz_data):
                opts = ["Select an answer…"] + [f"{k}. {v}" for k, v in q["options"].items()]
                sel  = st.radio(f"{i+1}. {q['question']}", opts, index=0, key=f"q_{i}")
                st.session_state.quiz_ans[i] = sel[0] if sel != "Select an answer…" else None
                if sel == "Select an answer…": all_done = False

            if st.button("Submit Quiz", disabled=not all_done):
                st.session_state.quiz_done = True
                correct = sum(
                    1 for i, q in enumerate(st.session_state.quiz_data)
                    if st.session_state.quiz_ans.get(i) == q["answer"]
                )
                st.success(f"You got {correct} / {len(st.session_state.quiz_data)} correct!")
                # log score for progress tracker
                scores = st.session_state.setdefault("quiz_scores", [])
                scores.append({"date": str(datetime.date.today()), "topic": topic, "correct": correct, "attempted": len(st.session_state.quiz_data)})
    elif menu == "Flashcards":
        st.header("Flashcards")
        topic = st.selectbox(
            "Flashcard Topic",
            ["General", "Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"]
        )

        if st.button("Generate Flashcards"):
            prompt = (
                f"Generate 10 flashcards for the topic '{topic}' using a Q&A format only from the SC permit test. "
                "Each flashcard should have a clear question and a short, clear answer. "
                "Use exactly this format for each flashcard: Q: [question]\nA: [answer]\n"
                "Return ONLY flashcards, no extra text, no multiple choice, and no explanations."
            )
            with st.spinner("Creating flashcards..."):
                raw_flashcards = query_gpt([
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ])
                flashcards_data = parse_flashcards(raw_flashcards)
                st.session_state["flashcards_data"] = flashcards_data
                st.session_state["flashcard_revealed"] = [False] * len(flashcards_data)

        if "flashcards_data" in st.session_state:
            st.subheader(f"{topic} Flashcards")
            for idx, card in enumerate(st.session_state["flashcards_data"]):
                st.markdown(f"**Q{idx+1}: {card['question']}**")
                if not st.session_state["flashcard_revealed"][idx]:
                    if st.button("Reveal Answer", key=f"reveal_btn_{idx}"):
                        st.session_state["flashcard_revealed"][idx] = True

                if st.session_state["flashcard_revealed"][idx]:
                    st.success(f"**A{idx+1}: {card['answer']}**")
                st.write("---")

            flashcard_text = "\n\n".join([
                f"Q{idx+1}: {c['question']}\nA{idx+1}: {c['answer']}"
                for idx, c in enumerate(st.session_state["flashcards_data"])
            ])
            st.download_button("Download PDF", create_pdf(flashcard_text), file_name="flashcards.pdf")

    elif menu == "Study Plan":
        st.header("3-Day Study Plan")
        plan = """(your existing markdown plan text here)"""
        st.markdown(plan)
        st.download_button("Download PDF", create_pdf(plan), file_name="study_plan.pdf")

    elif menu == "Progress Tracker":
        st.header("Your Progress")
        scores = st.session_state.get("quiz_scores", [])
        if scores:
            from collections import defaultdict
            date_stats = defaultdict(lambda: {"correct": 0, "attempted": 0, "topics": []})
            for entry in scores:
                d = entry["date"]
                date_stats[d]["correct"] += entry["correct"]
                date_stats[d]["attempted"] += entry["attempted"]
                date_stats[d]["topics"].append(f"{entry['topic']} — {entry['correct']}/{entry['attempted']} correct")
            for d in sorted(date_stats.keys(), reverse=True):
                topics_str = "<br>".join(date_stats[d]["topics"])
                accuracy = (date_stats[d]["correct"] / date_stats[d]["attempted"] * 100) if date_stats[d]["attempted"] else 0
                st.markdown(f"**{d}**<br>{topics_str}<br><span style='color:#666'>Daily Accuracy: <b>{accuracy:.1f}%</b></span><br><br>", unsafe_allow_html=True)
            total_correct = sum(x["correct"] for x in scores)
            total_attempted = sum(x["attempted"] for x in scores)
            if total_attempted:
                accuracy = total_correct / total_attempted * 100
                st.metric("Total Accuracy", f"{accuracy:.1f}%")
        else:
            st.info("No progress saved yet.")

# ---------- END MAIN APP BLOCK ----------

