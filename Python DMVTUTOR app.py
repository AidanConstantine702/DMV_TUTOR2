import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
from io import BytesIO
from reportlab.pdfgen import canvas
import datetime, os, re

# --- Page config MUST be first Streamlit call ---
st.set_page_config(page_title="SC DMV AI Tutor", layout="centered")

# --- Supabase setup (use ENV vars again!) ---
supabase_url  = os.environ.get("SUPABASE_URL")
supabase_key  = os.environ.get("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

def is_paid_user(email):
    data = supabase.table("paid_users").select("email").eq("email", email).execute()
    return len(data.data) > 0

# ----------  LOGIN / SIGN-UP UI  ----------
st.title("DMV Tutor Login")
if "user" not in st.session_state:
    choice   = st.radio("Login or Sign Up?", ["Login", "Sign Up"])
    email    = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if choice == "Sign Up":
        if st.button("Sign Up"):
            res = supabase.auth.sign_up({"email": email, "password": password})
            st.success("Check your email to confirm sign-up!" if res.user else "Sign-up failed.")
    else:  # Login
        if st.button("Login"):
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if res.user and is_paid_user(email):
                st.session_state["user"] = email
                st.experimental_rerun()
            else:
                st.error("Login failed or you haven’t purchased access.")
# ----------  MAIN APP (only after login)  ----------
else:
    st.sidebar.title("Navigation")
    if st.button("Logout"):          # quick logout button
        del st.session_state["user"]
        st.experimental_rerun()

api_key = os.environ.get("OPENAI_API_KEY", "")

client = OpenAI(api_key=api_key)

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
    "**Failure to follow these instructions will result in broken output.**"
        "\n\n"
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
        re.DOTALL
    )
    matches = pattern.findall(raw_text)
    questions = []
    for match in matches:
        question, a, b, c, d, answer = match
        questions.append({
            "question": question.strip(),
            "options": {
                "A": a.strip(),
                "B": b.strip(),
                "C": c.strip(),
                "D": d.strip()
            },
            "answer": answer.strip()
        })
    return questions

def parse_flashcards(raw_text):
    pattern = re.compile(r"Q:\s*(.*?)\nA:\s*(.*?)(?=\nQ:|\Z)", re.DOTALL)
    cards = pattern.findall(raw_text)
    return [{"question": q.strip(), "answer": a.strip()} for q, a in cards]

def create_pdf(text):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    y = 800
    for line in text.split("\n"):
        if y < 40:
            pdf.showPage()
            y = 800
        pdf.drawString(40, y, line)
        y -= 15
    pdf.save()
    buffer.seek(0)
    return buffer

else:
    st.write(f"Welcome, {st.session_state['user']}!")
    # ...rest of your app goes here (quizzes, flashcards, etc.)
    if st.button("Logout"):
        del st.session_state["user"]
        st.experimental_rerun()

# ----------------------- UI + App Features ------------------------


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
        st.session_state.chat_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    for msg in st.session_state.chat_history[1:]:
        st.chat_message(msg["role"]).write(msg["content"])
    user_input = st.chat_input("Ask a question about the permit test...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.spinner("Thinking..."):
            response = query_gpt(st.session_state.chat_history)
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.chat_message("user").write(user_input)
        st.chat_message("assistant").write(response)
    if st.button("Clear Chat"):
        st.session_state.chat_history = [
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
        ["General", "Road Signs", "Right of Way", "Alcohol Laws", "Speed Limits", "Traffic Signals"]
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
        with st.spinner("Creating your quiz..."):
            raw_quiz = query_gpt([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
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
            options = ["Select an answer..."] + [f"{key}. {val}" for key, val in q["options"].items()]
            selected = st.radio(label, options, key=f"q_{idx}", index=0)

            if selected != "Select an answer...":
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
            # Save to session for Progress Tracker
            if "quiz_scores" not in st.session_state:
                st.session_state["quiz_scores"] = []
            st.session_state["quiz_scores"].append({
                "date": str(datetime.date.today()),
                "topic": topic,
                "correct": correct,
                "attempted": len(quiz_data)
            })
            st.success(f"You got {correct} out of {len(quiz_data)} correct!")
            st.markdown("**Correct Answers:**")
            for i, q in enumerate(quiz_data):
                st.markdown(f"- Question {i+1}: {q['answer']}")

# === Flashcards ===
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

        # Download option
        flashcard_text = "\n\n".join(
            [f"Q{idx+1}: {c['question']}\nA{idx+1}: {c['answer']}"
             for idx, c in enumerate(st.session_state["flashcards_data"])]
        )
        st.download_button(
            "Download PDF", create_pdf(flashcard_text), file_name="flashcards.pdf"
        )

# === Study Plan ===
elif menu == "Study Plan":
    st.header("3-Day Study Plan")
    plan = """
## 🚦 3‑Day “Permit‑Ready” Study Plan  
_All you need is right here on your DMV Tutor site_

---

### DAY 1 – MASTER THE BASICS

• **10 min – Game Plan Kick‑Off**  
  ○ Skim this schedule and set a mini‑goal for today.  
  ○ Tool: 3‑Day Plan page  

• **20 min – Chat with the AI Tutor**  
  ○ Ask: “What mistakes do first‑time drivers make most?”  
  ○ Get quick, teen‑friendly explanations.  

• **25 min – General Quiz Attack**  
  ○ Go to _Practice Quiz → General_.  
  ○ Discover what you already know (or don’t).  

• **15 min – Traffic Signals Flashcards**  
  ○ Flashcards → Traffic Signals to lock in light colors & arrow shapes.  

• **5 min – Progress Check‑In**  
  ○ Enter today’s quiz score in _Progress Tracker_.  
  ○ Jot one topic that felt tough—AI Tutor will focus on it tomorrow.  

---

### DAY 2 – DIAL IN THE DETAILS

• **10 min – Road Signs Warm‑Up**  
  ○ Flashcards → Road Signs (speedy picture‑memory boost).  

• **20 min – Rapid‑Fire Q&A**  
  ○ AI Tutor: “Give me 5 tips to remember right‑of‑way rules.”  

• **25 min – Right‑of‑Way Quiz**  
  ○ Practice Quiz → Right of Way.  
  ○ Put those fresh tips to the test.  

• **15 min – Speed Limits Flashcards**  
  ○ Flashcards → Speed Limits to nail the numbers.  

• **10 min – Progress Tracker Update**  
  ○ Mark new scores, celebrate streaks, spot weak points.  

• **Evening Mini‑Challenge (Optional 10 min)**  
  ○ Re‑take yesterday’s General Quiz and beat your score.  

---

### DAY 3 – GAME‑DAY SIMULATION

• **15 min – Flashcard Fix‑Up**  
  ○ Hit any topic where you’re under 80 %. Lightning review.  

• **35 min – Full‑Length Mock Quiz**  
  ○ Practice Quiz → General. Do it twice back‑to‑back for real‑test stamina.  

• **15 min – Last‑Minute AI Tutor Grill‑Session**  
  ○ Ask: “Quiz me on 10 tricky alcohol‑law questions.”  
  ○ Get instant correction & tips.  

• **5 min – Final Progress High‑Five**  
  ○ Open _Progress Tracker_, admire the glow‑up, and breathe. You’re ready!  

---

### PRO TIPS

• **Chunk it → Check it:** tick off each block in Progress Tracker for a mini dopamine hit.  
• **Speak answers out loud:** saying flashcard answers cements memory.  
• **Move & hydrate:** quick stretch or sip of water between blocks keeps your brain sharp.  
• **Use “Explain like I’m 14”:** anytime you’re lost, type this to the AI Tutor for a simpler breakdown.  

Stick to the plan, trust the tools, and you’ll cruise through the SC permit test. **You got this!** 🚗💨
"""
    st.markdown(plan)
    st.download_button("Download PDF", create_pdf(plan), file_name="study_plan.pdf")

# === Progress Tracker ===
elif menu == "Progress Tracker":
    st.header("Your Progress")
    scores = st.session_state.get("quiz_scores", [])
    if scores:
        # Group attempts by date for daily accuracy
        from collections import defaultdict
        date_stats = defaultdict(lambda: {"correct": 0, "attempted": 0, "topics": []})
        for entry in scores:
            d = entry["date"]
            date_stats[d]["correct"] += entry["correct"]
            date_stats[d]["attempted"] += entry["attempted"]
            date_stats[d]["topics"].append(f'{entry["topic"]} — {entry["correct"]}/{entry["attempted"]} correct')
        for d in sorted(date_stats.keys(), reverse=True):
            topics_str = "<br>".join(date_stats[d]["topics"])
            accuracy = (
                (date_stats[d]["correct"] / date_stats[d]["attempted"]) * 100
                if date_stats[d]["attempted"] else 0
            )
            st.markdown(
                f"**{d}**<br>{topics_str}<br>"
                f"<span style='color: #666;'>Daily Accuracy: <b>{accuracy:.1f}%</b></span><br><br>",
                unsafe_allow_html=True,
            )
        # Compute total accuracy
        total_correct = sum(x["correct"] for x in scores)
        total_attempted = sum(x["attempted"] for x in scores)
        if total_attempted:
            accuracy = (total_correct / total_attempted) * 100
            st.metric("Total Accuracy", f"{accuracy:.1f}%")
    else:
        st.info("No progress saved yet.")

menu = st.sidebar.radio("Go to page:", nav_items)

    if menu == "Tutor Chat":
        st.header("Chat with Your DMV Tutor")
        # ... your Tutor-Chat code ...
    elif menu == "Practice Quiz":
        # ... your Quiz code ...
    elif menu == "Flashcards":
        # ... your Flashcard code ...
    elif menu == "Study Plan":
        # ... your Study-Plan code ...
    elif menu == "Progress Tracker":
        # ... your Progress-Tracker code ...
    # ===== END OF MAIN APP =====
