from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models import User, Post, Mood, CrisisAlert, Helpline, ChatRoom, Comment, ChatMessage, Feedback

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(f):
    """Decorator to strictly enforce that a user is an admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    """High-level metrics overview for the central Admin dashboard."""
    stats = {
        "users": User.query.count(),
        "posts": Post.query.count(),
        "moods": Mood.query.count(),
        "alerts": CrisisAlert.query.filter_by(resolved=False).count(),
        "unread_feedback": Feedback.query.filter_by(is_read=False).count()
    }
    return render_template("admin/dashboard.html", stats=stats)

@admin_bp.route("/users")
@login_required
@admin_required
def manage_users():
    """Lists all users natively sorted by the newest joining date."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users)

@admin_bp.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    """Secure endpoint that mathematically rejects any attempts to delete an Admin."""
    user = User.query.get_or_404(user_id)
    
    if getattr(user, 'is_admin', False):
        flash("Action denied: Admin accounts cannot be deleted. You must transfer the role first.", "error")
        return redirect(url_for("admin.manage_users"))
        
    db.session.delete(user)
    db.session.commit()
    flash(f"User {user.username} deleted permanently.", "success")
    return redirect(url_for("admin.manage_users"))

@admin_bp.route("/transfer", methods=["POST"])
@login_required
@admin_required
def transfer_admin():
    """The Immutable Role Swap payload. Assigns Admin to a target, removes it from the host."""
    target_username = request.form.get("target_username", "").strip()
    target_user = User.query.filter_by(username=target_username).first()
    
    if not target_user:
        flash("Target user not found.", "error")
        return redirect(url_for("admin.manage_users"))
        
    if target_user.id == current_user.id:
        flash("You are already holding the Admin keys.", "error")
        return redirect(url_for("admin.manage_users"))
        
    # The Hand-Off
    target_user.is_admin = True
    current_user_obj = User.query.get(current_user.id)
    current_user_obj.is_admin = False
    
    db.session.commit()
    flash(f"Admin rights securely transferred to {target_user.username}. You are now a Standard User.", "success")
    # Redirect to home since they immediately lose dashboard access
    return redirect(url_for("main.index"))
    
# ── Infrastructure Management ──

@admin_bp.route("/helplines", methods=["GET", "POST"])
@login_required
@admin_required
def manage_helplines():
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        type = request.form.get("type", "General")
        is_24hr = request.form.get("is_24hr") == 'on'
        h = Helpline(name=name, phone=phone, type=type, is_24hr=is_24hr)
        db.session.add(h)
        db.session.commit()
        flash(f"Helpline '{name}' deployed securely.", "success")
        return redirect(url_for("admin.manage_helplines"))
        
    helplines = Helpline.query.all()
    return render_template("admin/helplines.html", helplines=helplines)

@admin_bp.route("/helplines/delete/<int:id>", methods=["POST"])
@login_required
@admin_required
def delete_helpline(id):
    h = Helpline.query.get_or_404(id)
    db.session.delete(h)
    db.session.commit()
    flash("Helpline safely eradicated.", "success")
    return redirect(url_for("admin.manage_helplines"))

@admin_bp.route("/rooms", methods=["GET", "POST"])
@login_required
@admin_required
def manage_rooms():
    if request.method == "POST":
        name = request.form.get("name")
        topic = request.form.get("topic", "General")
        description = request.form.get("description", "")
        r = ChatRoom(name=name, topic=topic, description=description)
        db.session.add(r)
        db.session.commit()
        flash(f"Night Room '{name}' instantiated successfully.", "success")
        return redirect(url_for("admin.manage_rooms"))
        
    rooms = ChatRoom.query.all()
    return render_template("admin/rooms.html", rooms=rooms)

@admin_bp.route("/rooms/delete/<int:id>", methods=["POST"])
@login_required
@admin_required
def delete_room(id):
    r = ChatRoom.query.get_or_404(id)
    db.session.delete(r)
    db.session.commit()
    flash("Night Room purged.", "success")
    return redirect(url_for("admin.manage_rooms"))
    
# ── Inline God Mode Moderation Hooks ──

@admin_bp.route("/delete_post/<int:id>", methods=["POST"])
@login_required
@admin_required
def delete_post(id):
    p = Post.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    flash("Post permanently deleted.", "success")
    # Using 'HTTP_REFERER' to elegantly drop the admin back to where they were scrolling
    referrer = request.headers.get("Referer") or url_for('feed.feed')
    return redirect(referrer)

@admin_bp.route("/delete_comment/<int:id>", methods=["POST"])
@login_required
@admin_required
def delete_comment(id):
    c = Comment.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash("Comment uniformly scrubbed.", "success")
    referrer = request.headers.get("Referer") or url_for('feed.feed')
    return redirect(referrer)

@admin_bp.route("/delete_chat/<int:id>", methods=["POST"])
@login_required
@admin_required
def delete_chat(id):
    msg = ChatMessage.query.get_or_404(id)
    db.session.delete(msg)
    db.session.commit()
    # Using JSON response for silent async fetch logic in the live web-socket chat layout
    from flask import jsonify
    return jsonify({"status": "erased_by_admin", "id": id})

@admin_bp.route("/feedback", methods=["GET"])
@login_required
@admin_required
def view_feedback():
    feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).all()
    return render_template("admin/feedback.html", feedbacks=feedbacks)

@admin_bp.route("/feedback/read/<int:id>", methods=["POST"])
@login_required
@admin_required
def read_feedback(id):
    fb = Feedback.query.get_or_404(id)
    fb.is_read = True
    db.session.commit()
    flash("Feedback marked as read.", "success")
    return redirect(url_for("admin.view_feedback"))

@admin_bp.route("/feedback/delete/<int:id>", methods=["POST"])
@login_required
@admin_required
def delete_feedback(id):
    fb = Feedback.query.get_or_404(id)
    db.session.delete(fb)
    db.session.commit()
    flash("Feedback deleted.", "success")
    return redirect(url_for("admin.view_feedback"))
