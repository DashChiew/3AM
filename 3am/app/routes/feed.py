from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
import os
import re
import base64
import requests
import bleach
from groq import Groq
from app import db, limiter
from app.models import Post, Comment, User

feed_bp = Blueprint("feed", __name__)


@feed_bp.route("/feed")
@login_required
def feed():
    # Get all posts, newest first, only non-flagged
    posts = Post.query.filter_by(is_flagged=False)\
                .order_by(Post.created_at.desc()).all()
    return render_template("feed.html", posts=posts)


@feed_bp.route("/feed/post", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def create_post():
    content = bleach.clean(request.form.get("content", "").strip())

    if not content or len(content) < 3:
        flash("Post is too short.", "error")
        return redirect(url_for("feed.feed"))

    if len(content) > 1000:
        flash("Post is too long (max 1000 characters).", "error")
        return redirect(url_for("feed.feed"))

    is_safe, reason = moderate_content(content)
    if not is_safe:
        if reason == "ADDRESS":
            flash("Sharing a home address is dangerous and not allowed here.", "error")
        elif reason == "MALICIOUS_LINK":
            flash("This message contains a malicious or suspicious link and has been blocked.", "error")
        elif reason == "JUDGMENTAL":
            flash("Please keep posts supportive. We do not allow judging personal qualities.", "error")
        return redirect(url_for("feed.feed"))

    post = Post(
        user_id=current_user.id,
        content=content,
        is_anonymous=current_user.is_anonymous_mode
    )
    db.session.add(post)
    db.session.commit()

    name = "Anonymous" if current_user.is_anonymous_mode else current_user.username
    flash(f"Posted as {name} 💜", "success")
    return redirect(url_for("feed.feed"))


def check_malicious_links(content):
    """
    Extracts URLs and queries the VirusTotal API to determine if they are malicious.
    Returns (is_safe: bool, reason: str)
    """
    urls = re.findall(r'(https?://[^\s]+)', content)
    if not urls:
        return True, None
        
    vt_key = os.environ.get("VIRUSTOTAL_API_KEY")
    if not vt_key:
        return True, None # Fail open if API key is not configured
        
    headers = {"x-apikey": vt_key}
    
    for url in urls:
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        try:
            resp = requests.get(f"https://www.virustotal.com/api/v3/urls/{url_id}", headers=headers, timeout=5)
            if resp.status_code == 200:
                stats = resp.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                if stats.get("malicious", 0) > 0 or stats.get("suspicious", 0) > 0:
                    return False, "MALICIOUS_LINK"
        except Exception:
            pass # Fail open on network errors
            
    return True, None


def moderate_content(content):
    """
    Checks VirusTotal for malicious links, then uses Groq AI for rules.
    Returns a tuple (is_safe: bool, reason: str)
    reason can be "ADDRESS", "JUDGMENTAL", "MALICIOUS_LINK" or None
    """
    # 1. Check for malicious links first
    is_safe_links, link_reason = check_malicious_links(content)
    if not is_safe_links:
        return False, link_reason

    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return (True, None)  # Fail open if no key

        client = Groq(api_key=api_key)
        prompt = f"""You are a community moderator for a mental health support app. 
Analyze the following text and determine if it violates our safety rules.
Rules:
1. No sharing home addresses or highly specific physical locations that could compromise real-world safety.
2. No judging someone's personal qualities or character (e.g., "you are lazy", "you're a bad person").

Respond with EXACTLY ONE of these words:
ADDRESS - if it contains a home address or highly specific location.
JUDGMENTAL - if it judges personal qualities.
SAFE - if it is safe and supportive.

Text: "{content}"
"""
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=10
        )
        result = response.choices[0].message.content.strip().upper()
        
        if "ADDRESS" in result:
            return (False, "ADDRESS")
        elif "JUDGMENTAL" in result:
            return (False, "JUDGMENTAL")
            
        return (True, None)
    except:
        return (True, None)  # Fail open on API error


@feed_bp.route("/feed/comment/<int:post_id>", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = bleach.clean(request.form.get("content", "").strip())

    if not content:
        flash("Comment cannot be empty.", "error")
        return redirect(url_for("feed.feed"))

    # AI Moderation: Block addresses, judgmental content, or malware links
    is_safe, reason = moderate_content(content)
    if not is_safe:
        if reason == "ADDRESS":
            flash("Sharing a home address is dangerous and not allowed here.", "error")
        elif reason == "MALICIOUS_LINK":
            flash("This comment contains a malicious or suspicious link and has been blocked.", "error")
        elif reason == "JUDGMENTAL":
            flash("Please keep comments supportive. We do not allow judging or commenting on someone's personal qualities here.", "error")
        return redirect(url_for("feed.feed"))

    c = Comment(
        post_id=post_id,
        user_id=current_user.id,
        content=content,
        is_anonymous=current_user.is_anonymous_mode
    )
    db.session.add(c)
    db.session.commit()
    return redirect(url_for("feed.feed"))
    