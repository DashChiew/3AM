from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from flask_socketio import join_room, leave_room, emit
import bleach
from datetime import datetime
from app import db, socketio
from app.models import ChatRoom, ChatMessage, CrisisAlert
from app.services.emobot import detect_crisis
from app.routes.feed import moderate_content

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat")
@login_required
def chat_lobby():
    rooms = ChatRoom.query.filter_by(is_active=True).all()
    return render_template("chat_lobby.html", rooms=rooms)


@chat_bp.route("/chat/<int:room_id>")
@login_required
def chat_room(room_id):
    room = ChatRoom.query.get_or_404(room_id)
    history = (
        ChatMessage.query
        .filter_by(room_id=room_id)
        .order_by(ChatMessage.timestamp.asc())
        .limit(50)
        .all()
    )
    return render_template("chat_room.html", room=room, history=history)


# ── SocketIO events ───────────────────────────────────────────────────────────

@socketio.on("join")
def handle_join(data):
    room_id = str(data.get("room_id", ""))
    join_room(room_id)
    display = "Someone" if current_user.is_anonymous_mode else current_user.username
    emit("status", {
        "msg": f"{display} joined the room 🌙",
        "timestamp": datetime.utcnow().strftime("%H:%M")
    }, to=room_id)


@socketio.on("leave")
def handle_leave(data):
    room_id = str(data.get("room_id", ""))
    leave_room(room_id)
    display = "Someone" if current_user.is_anonymous_mode else current_user.username
    emit("status", {
        "msg": f"{display} left the room.",
        "timestamp": datetime.utcnow().strftime("%H:%M")
    }, to=room_id)


@socketio.on("chat_message")
def handle_message(data):
    room_id = str(data.get("room_id", ""))
    message = bleach.clean(data.get("message", "").strip()[:500])

    if not message:
        return

    # User moderation check
    is_safe, reason = moderate_content(message)
    if not is_safe:
        if reason == "ADDRESS":
            alert_msg = "❌ Message blocked. Sharing a home address is dangerous and not allowed here."
        elif reason == "MALICIOUS_LINK":
            alert_msg = "❌ Message blocked. It contains a malicious or suspicious link."
        else:
            alert_msg = "❌ Message blocked. Please keep the chat supportive and do not judge personal qualities."
            
        emit("status", {
            "msg": alert_msg,
            "timestamp": datetime.utcnow().strftime("%H:%M")
        }, to=request.sid) # Only send back to the user who sent it
        return

    display = "Anonymous" if current_user.is_anonymous_mode else current_user.username

    # Crisis check
    crisis_kw = detect_crisis(message)
    if crisis_kw:
        alert = CrisisAlert(
            user_id=current_user.id,
            trigger_keyword=crisis_kw,
            context=f"[Chat Room {room_id}] {message[:300]}"
        )
        db.session.add(alert)

    # Save message
    msg_obj = ChatMessage(
        room_id=int(room_id),
        user_id=current_user.id,
        message=message,
        is_anonymous=current_user.is_anonymous_mode
    )
    db.session.add(msg_obj)
    db.session.commit()

    # Broadcast to room
    emit("chat_message", {
        "msg_id":           msg_obj.id,
        "user_id":          current_user.id,
        "sender":           display,
        "message":          message,
        "timestamp":        datetime.utcnow().strftime("%H:%M"),
        "show_crisis_help": bool(crisis_kw)
    }, to=room_id)