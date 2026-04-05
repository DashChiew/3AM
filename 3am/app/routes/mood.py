from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from app import db
from app.models import Mood, User

mood_bp = Blueprint("mood", __name__)

MOOD_EMOJIS = {
    1: "😭", 2: "😢", 3: "😟", 4: "😔", 5: "😐",
    6: "🙂", 7: "😊", 8: "😄", 9: "🥰", 10: "🤩"
}

BADGE_TIERS = [
    {"req": 3, "id": "bronze", "name": "3-Day Starter", "color": "#d97706", "desc": "3 consecutive check-ins."},
    {"req": 7, "id": "silver", "name": "1-Week Warrior", "color": "#9ca3af", "desc": "7 consecutive check-ins."},
    {"req": 14, "id": "gold", "name": "2-Week Champion", "color": "#fbbf24", "desc": "14 consecutive check-ins."},
    {"req": 30, "id": "diamond", "name": "30-Day Master", "color": "#38bdf8", "desc": "A full month of care!"}
]

def get_badges_status(streak):
    status = []
    for b in BADGE_TIERS:
        b_copy = b.copy()
        b_copy["earned"] = (streak >= b["req"])
        status.append(b_copy)
    return status


@mood_bp.route("/mood")
@login_required
def mood_page():
    # Get last 30 days of mood data for the chart
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    moods = Mood.query.filter(
        Mood.user_id == current_user.id,
        Mood.logged_at >= thirty_days_ago
    ).order_by(Mood.logged_at.asc()).all()

    # Format data for Chart.js
    chart_labels = [m.logged_at.strftime("%b %d") for m in moods]
    chart_data   = [m.mood_score for m in moods]

    # Get last 7 entries to show in the list
    recent_moods = Mood.query.filter_by(user_id=current_user.id)\
                       .order_by(Mood.logged_at.desc()).limit(7).all()

    # Calculate average
    avg = round(sum(chart_data) / len(chart_data), 1) if chart_data else None

    # Calculate badges
    badges_status = get_badges_status(current_user.checkin_streak)

    return render_template("mood.html",
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           recent_moods=recent_moods,
                           mood_emojis=MOOD_EMOJIS,
                           avg=avg,
                           badges_status=badges_status)


@mood_bp.route("/mood/checkin", methods=["POST"])
@login_required
def checkin():
    try:
        score = int(request.form.get("score", 0))
    except ValueError:
        flash("Invalid mood score.", "error")
        return redirect(url_for("mood.mood_page"))

    if not 1 <= score <= 10:
        flash("Score must be between 1 and 10.", "error")
        return redirect(url_for("mood.mood_page"))

    note  = request.form.get("note", "").strip()
    emoji = MOOD_EMOJIS.get(score, "😐")

    # Save mood entry
    mood = Mood(
        user_id=current_user.id,
        mood_score=score,
        mood_emoji=emoji,
        note=note if note else None
    )
    db.session.add(mood)
    db.session.commit()

    # Update streak
    today     = date.today()
    yesterday = today - timedelta(days=1)

    if current_user.last_checkin == today:
        # Already checked in today — just update mood
        flash(f"Mood updated: {emoji} {score}/10", "success")
    elif current_user.last_checkin == yesterday:
        # Consecutive day — increase streak
        current_user.checkin_streak += 1
        current_user.last_checkin    = today
        db.session.commit()
        flash(f"Mood logged: {emoji} {score}/10 — "
              f"{current_user.checkin_streak} night streak!", "success")
              
        # EmoBot Milestone Injection
        if current_user.checkin_streak in [3, 7, 14, 30, 50, 100]:
            from app.services.emobot import get_last_session_id, new_session_id
            from app.models import Conversation
            
            sess_id = get_last_session_id(current_user.id) or new_session_id()
            msg = f"🎉 WOW! I just saw you hit a {current_user.checkin_streak}-day wellness streak! I'm so proud of you for showing up for yourself consistently. Keep it up! 💜"
            bot_msg = Conversation(
                user_id=current_user.id,
                message=msg,
                sender="bot",
                session_id=sess_id
            )
            db.session.add(bot_msg)
            db.session.commit()
            flash(f"EmoBot has a special message for you regarding your streak! 🤖", "info")
            
    else:
        # Streak broken or first check-in
        current_user.checkin_streak = 1
        current_user.last_checkin   = today
        db.session.commit()
        flash(f"Mood logged: {emoji} {score}/10 — streak started!", "success")

    return redirect(url_for("mood.mood_page"))