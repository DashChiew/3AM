from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Announcement, AnnouncementReaction

announcements_bp = Blueprint("announcements", __name__, url_prefix="/announcements")

@announcements_bp.route("/", methods=["GET", "POST"], strict_slashes=False)
@login_required
def index():
    if request.method == "POST":
        if not getattr(current_user, 'is_admin', False):
            flash("Only administrators can post announcements.", "error")
            return redirect(url_for("announcements.index"))
            
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        
        if not title or not content:
            flash("Title and content are required.", "error")
        else:
            announcement = Announcement(title=title, content=content, author_id=current_user.id)
            db.session.add(announcement)
            db.session.commit()
            flash("Announcement posted successfully.", "success")
            return redirect(url_for("announcements.index"))
            
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    
    # Process reactions
    for ann in announcements:
        ann.reaction_counts = {}
        ann.user_reactions = set()
        for r in ann.reactions:
            ann.reaction_counts[r.emoji] = ann.reaction_counts.get(r.emoji, 0) + 1
            if current_user.is_authenticated and r.user_id == current_user.id:
                ann.user_reactions.add(r.emoji)
                
    return render_template("announcements.html", announcements=announcements)

@announcements_bp.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete(id):
    if not getattr(current_user, 'is_admin', False):
        flash("Only administrators can delete announcements.", "error")
        return redirect(url_for("announcements.index"))
        
    announcement = Announcement.query.get_or_404(id)
    db.session.delete(announcement)
    db.session.commit()
    flash("Announcement deleted.", "success")
    return redirect(url_for("announcements.index"))

@announcements_bp.route("/react/<int:id>", methods=["POST"])
@login_required
def react(id):
    announcement = Announcement.query.get_or_404(id)
    data = request.get_json()
    
    if not data or "emoji" not in data:
        return jsonify({"error": "No emoji provided"}), 400
        
    emoji = data.get("emoji")
    
    existing = AnnouncementReaction.query.filter_by(announcement_id=id, user_id=current_user.id, emoji=emoji).first()
    if existing:
        db.session.delete(existing)
        action = "removed"
    else:
        new_reaction = AnnouncementReaction(announcement_id=id, user_id=current_user.id, emoji=emoji)
        db.session.add(new_reaction)
        action = "added"
        
    db.session.commit()
    
    count = AnnouncementReaction.query.filter_by(announcement_id=id, emoji=emoji).count()
    return jsonify({"action": action, "emoji": emoji, "count": count})
