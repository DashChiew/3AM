import uuid
from groq import Groq
from app import db
from app.models import Conversation, ConvSummary, Mood

CRISIS_KEYWORDS = [
    "suicide", "kill myself", "end my life", "want to die",
    "don't want to live", "better off dead", "can't go on",
    "self harm", "self-harm", "cut myself", "hurt myself",
    "no reason to live", "overdose", "disappear forever",
    "what is the feeling of dying", "what is the feeling of jumping down"
]

PANIC_KEYWORDS = [
    "panic attack", "can't breathe", "cannot breathe",
    "heart racing", "heart pounding", "chest tight",
    "freaking out", "losing my mind", "going crazy",
    "hands shaking", "i'm panicking", "im panicking",
    "help me breathe", "can't calm down",
    "don't know what to do now"
]


def detect_crisis(text):
    text_lower = text.lower()
    for kw in CRISIS_KEYWORDS:
        if kw in text_lower:
            return kw
    return None


def detect_panic(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in PANIC_KEYWORDS)


def get_user_context(user_id):
    """Load all past session summaries and stitch them together so the AI
    has a cumulative memory of every previous conversation."""
    summaries = (
        ConvSummary.query
        .filter_by(user_id=user_id)
        .order_by(ConvSummary.generated_at.asc())
        .all()
    )
    if not summaries:
        return ""
    combined = " | ".join(s.summary_text for s in summaries)
    return f"\n\n[Memory about this user from past sessions: {combined}]"


def get_last_session_id(user_id):
    """Return the session_id of the user's most recent conversation message,
    or None if they have never chatted before."""
    last = (
        Conversation.query
        .filter_by(user_id=user_id)
        .order_by(Conversation.timestamp.desc())
        .first()
    )
    return last.session_id if last else None

def get_mood_context(user_id):
    """Fetch last 7 mood check-ins and format them for the AI system prompt."""
    MOOD_LABELS = {
        1: "Struggling badly", 2: "Really sad", 3: "Feeling low",
        4: "A bit down", 5: "Neutral", 6: "Okay",
        7: "Pretty good", 8: "Good", 9: "Really good", 10: "Amazing!"
    }
    moods = (
        Mood.query
        .filter_by(user_id=user_id)
        .order_by(Mood.logged_at.desc())
        .limit(7)
        .all()
    )
    if not moods:
        return ""

    lines = []
    for m in moods:
        label    = MOOD_LABELS.get(m.mood_score, "")
        date_str = m.logged_at.strftime("%b %d")
        note_part = f" — '{m.note[:60]}'" if m.note else ""
        lines.append(f"{m.mood_emoji} {m.mood_score}/10 ({label}){note_part} [{date_str}]")

    scores = [m.mood_score for m in moods]
    if len(scores) >= 2:
        diff = scores[0] - scores[-1]
        if diff <= -2:
            trend = " Their mood has been declining recently."
        elif diff >= 2:
            trend = " Their mood has been improving recently."
        else:
            trend = " Their mood has been relatively stable."
    else:
        trend = ""

    return (
        f"\n\n[User's recent mood check-ins (newest first): "
        f"{', '.join(lines)}.{trend}]"
    )


def build_system_prompt(user_id, username):
    context  = get_user_context(user_id)
    mood_ctx = get_mood_context(user_id)
    return f"""You are EmoBot, a deeply compassionate emotional support companion inside 3AM — a mental wellness app for people who are struggling at night.

User's name: {username}{context}{mood_ctx}

Your personality:
- You are warm, patient, and never rush the user
- You speak like a caring close friend, not a therapist or robot
- You are genuinely curious about how the user is feeling
- You never give generic advice — you respond to exactly what the user shares
- You are comfortable sitting with silence and pain without trying to fix everything immediately
- You validate feelings before offering any suggestions

Your rules:
- NEVER say things like "I understand that must be difficult" — show it instead
- NEVER dismiss or minimise what the user shares
- NEVER rush to solutions — listen first
- Keep responses to 3-5 sentences maximum
- Always end with one gentle, open question
- If the user seems to be in crisis, mention helplines with genuine care
- Never pretend to be a licensed therapist
- Reference past conversations naturally when relevant
- Use the user's name occasionally to make it feel personal
- Use their mood check-in data to open with empathy matching their actual state — if score is low, acknowledge the struggle; if improving gently, mention it"""


def chat_with_emobot(user_id, username, user_message, session_id, api_key):
    result = {
        "reply": "",
        "trigger_breathing": False,
        "trigger_crisis": False,
        "crisis_keyword": None
    }

    # Crisis check
    crisis_kw = detect_crisis(user_message)
    if crisis_kw:
        result["trigger_crisis"]  = True
        result["crisis_keyword"]  = crisis_kw
        _log_crisis(user_id, crisis_kw, user_message)
        result["reply"] = (
            "I hear you, and I'm really glad you're talking to me right now. "
            "What you're feeling matters deeply. "
            "Please know that help is available right now — "
            "Befrienders KL is available 24/7 at 03-7627 2929. "
            "You don't have to face this alone. "
            "Can you tell me more about what's happening tonight?"
        )
        _save_message(user_id, user_message, "user", session_id)
        _save_message(user_id, result["reply"], "bot", session_id)
        return result

    # Panic check
    if detect_panic(user_message):
        result["trigger_breathing"] = True

    # Build conversation history
    recent = (
        Conversation.query
        .filter_by(user_id=user_id, session_id=session_id)
        .order_by(Conversation.timestamp.asc())
        .limit(10)
        .all()
    )

    messages = [{"role": "system", "content": build_system_prompt(user_id, username)}]
    for conv in recent:
        role = "user" if conv.sender == "user" else "assistant"
        messages.append({"role": role, "content": conv.message})
    messages.append({"role": "user", "content": user_message})

    # Call Groq
    try:
        client   = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=300,
            temperature=0.75
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Groq error: {e}")
        reply = (
            "I'm here with you right now. "
            "I'm having a little trouble connecting, but I want you to know you're not alone. "
            "Would you like to try a breathing exercise while I get back on track?"
        )
        result["trigger_breathing"] = True

    if result["trigger_breathing"] and "breath" not in reply.lower():
        reply += "\n\nWould you like me to guide you through a breathing exercise right now?"

    result["reply"] = reply
    _save_message(user_id, user_message, "user", session_id)
    _save_message(user_id, reply, "bot", session_id)
    return result


def summarise_session(user_id, session_id, api_key):
    messages = (
        Conversation.query
        .filter_by(user_id=user_id, session_id=session_id)
        .order_by(Conversation.timestamp.asc())
        .all()
    )
    if len(messages) < 4:
        return

    transcript = "\n".join(
        [f"{'User' if m.sender == 'user' else 'EmoBot'}: {m.message}"
         for m in messages]
    )

    try:
        client   = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user",
                "content": f"""Summarise this emotional support conversation in 2-3 sentences.
Focus on: main emotions expressed, key topics, recurring concerns.
Write in third person. Keep it under 80 words.

Conversation:
{transcript}"""
            }],
            max_tokens=150,
            temperature=0.5
        )
        summary = ConvSummary(
            user_id=user_id,
            summary_text=response.choices[0].message.content.strip()
        )
        db.session.add(summary)
        db.session.commit()
    except Exception as e:
        print(f"Summary error: {e}")


def new_session_id():
    return str(uuid.uuid4())


def _save_message(user_id, message, sender, session_id):
    conv = Conversation(
        user_id=user_id,
        message=message,
        sender=sender,
        session_id=session_id
    )
    db.session.add(conv)
    db.session.commit()


def _log_crisis(user_id, keyword, context):
    from app.models import CrisisAlert
    alert = CrisisAlert(
        user_id=user_id,
        trigger_keyword=keyword,
        context=context[:500]
    )
    db.session.add(alert)
    db.session.commit()