from flask import Blueprint, render_template, request, jsonify, session, current_app
from flask_login import login_required, current_user
from app.services.emobot import (
    chat_with_emobot, summarise_session, new_session_id, get_last_session_id
)
from app.models import Helpline, Conversation, ConvSummary
from app import limiter, db

emobot_bp = Blueprint("emobot", __name__)


@emobot_bp.route("/emobot")
@login_required
def emobot():
    # Restore the user's last session from the DB so memory persists
    # across page reloads and new browser tabs.
    if "emobot_session" not in session:
        last = get_last_session_id(current_user.id)
        session["emobot_session"] = last if last else new_session_id()

    recent = (
        Conversation.query
        .filter_by(
            user_id=current_user.id,
            session_id=session["emobot_session"]
        )
        .order_by(Conversation.timestamp.asc())
        .limit(50)
        .all()
    )
    helplines = Helpline.query.filter_by(is_24hr=True).all()
    return render_template("emobot.html",
                           recent_messages=recent,
                           helplines=helplines)


@emobot_bp.route("/emobot/chat", methods=["POST"])
@login_required
@limiter.limit("60 per minute")
def emobot_chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "No message"}), 400

    user_message = data["message"].strip()[:1000]
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    session_id = session.get("emobot_session", new_session_id())
    session["emobot_session"] = session_id

    api_key = current_app.config.get("GROQ_API_KEY", "")
    result  = chat_with_emobot(
        user_id=current_user.id,
        username=current_user.username,
        user_message=user_message,
        session_id=session_id,
        api_key=api_key
    )

    helplines_data = []
    if result["trigger_crisis"]:
        helplines = Helpline.query.filter_by(is_24hr=True).all()
        helplines_data = [
            {"name": h.name, "phone": h.phone, "type": h.type}
            for h in helplines
        ]

    return jsonify({
        "reply":             result["reply"],
        "trigger_breathing": result["trigger_breathing"],
        "trigger_crisis":    result["trigger_crisis"],
        "helplines":         helplines_data
    })


@emobot_bp.route("/emobot/end-session", methods=["POST"])
@login_required
def end_session():
    session_id = session.pop("emobot_session", None)
    if session_id:
        api_key = current_app.config.get("GROQ_API_KEY", "")
        summarise_session(current_user.id, session_id, api_key)
    return jsonify({"status": "ok"})


@emobot_bp.route("/emobot/new-session", methods=["POST"])
@login_required
def new_session_route():
    old_session = session.pop("emobot_session", None)
    if old_session:
        api_key = current_app.config.get("GROQ_API_KEY", "")
        summarise_session(current_user.id, old_session, api_key)
    session["emobot_session"] = new_session_id()
    return jsonify({"status": "ok"})


@emobot_bp.route("/emobot/history", methods=["GET"])
@login_required
def emobot_history():
    """Return a list of past sessions with their summaries."""
    # Distinct session IDs ordered by most recent first
    from sqlalchemy import func
    sessions = (
        db.session.query(
            Conversation.session_id,
            func.min(Conversation.timestamp).label("started_at"),
            func.max(Conversation.timestamp).label("last_at"),
            func.count(Conversation.id).label("message_count")
        )
        .filter_by(user_id=current_user.id)
        .group_by(Conversation.session_id)
        .order_by(func.max(Conversation.timestamp).desc())
        .limit(20)
        .all()
    )

    # Fetch all summaries for this user
    all_summaries = (
        ConvSummary.query
        .filter_by(user_id=current_user.id)
        .order_by(ConvSummary.generated_at.desc())
        .all()
    )

    result = []
    for sess in sessions:
        # Find the preview (first user message in the session)
        first_msg = (
            Conversation.query
            .filter_by(user_id=current_user.id,
                       session_id=sess.session_id,
                       sender="user")
            .order_by(Conversation.timestamp.asc())
            .first()
        )
        result.append({
            "session_id":    sess.session_id,
            "started_at":    sess.started_at.isoformat(),
            "last_at":       sess.last_at.isoformat(),
            "message_count": sess.message_count,
            "preview":       first_msg.message[:80] if first_msg else "(empty)"
        })

    return jsonify({
        "sessions": result,
        "summaries": [s.summary_text for s in all_summaries]
    })