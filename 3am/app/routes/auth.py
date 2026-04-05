from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_jwt_extended import create_access_token
import bleach
from datetime import datetime, timedelta
import random
import string
from flask_mail import Message
from app import db, limiter, mail
from app.models import User, PasswordReset, Feedback

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    # If already logged in, go to home
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password   = request.form.get("password", "")

        # Find user by username OR email
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if user and user.check_password(password):
            user.last_active = datetime.utcnow()
            # Set anonymous mode based on login preference
            user.is_anonymous_mode = request.form.get("anonymous_mode") == "on"
            db.session.commit()
            login_user(user, remember=True)
            flash(f"Welcome back, {user.username} 🌙", "success")
            return redirect(url_for("main.index"))

        flash("Wrong username or password. Try again.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/api/auth/token", methods=["POST"])
@limiter.limit("10 per minute")
def api_token():
    """Provides a JWT access token for API integration."""
    data = request.get_json() or {}
    identifier = data.get("identifier", "").strip()
    password = data.get("password", "")
    
    if not identifier or not password:
        return jsonify({"msg": "Missing identifier or password"}), 400
        
    user = User.query.filter(
        (User.username == identifier) | (User.email == identifier)
    ).first()
    
    if user and user.check_password(password):
        access_token = create_access_token(identity=str(user.id))
        return jsonify({"access_token": access_token}), 200
        
    return jsonify({"msg": "Bad username or password"}), 401


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        raw_username = request.form.get("username", "").strip()
        raw_email    = request.form.get("email", "").strip().lower()
        
        # Sanitise inputs to prevent stored XSS
        username = bleach.clean(raw_username)
        email    = bleach.clean(raw_email)
        
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        # Basic validation
        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("auth/register.html")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("auth/register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth/register.html")

        if User.query.filter_by(username=username).first():
            flash("That username is already taken.", "error")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("auth/register.html")

        # Create the user
        anon_mode = request.form.get("anonymous_mode") == "on"
        user = User(username=username, email=email, is_anonymous_mode=anon_mode)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"Welcome to 3am, {username}. You are not alone. 💜", "success")
        return redirect(url_for("main.index"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/toggle-anonymous", methods=["POST"])
@login_required
def toggle_anonymous():
    current_user.is_anonymous_mode = not current_user.is_anonymous_mode
    db.session.commit()
    status = "on" if current_user.is_anonymous_mode else "off"
    flash(f"Anonymous mode turned {status}.", "info")
    return redirect(request.referrer or url_for("main.index"))


@auth_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_profile":
            raw_new_username = request.form.get("username", "").strip()
            raw_new_email    = request.form.get("email", "").strip().lower()
            
            new_username = bleach.clean(raw_new_username)
            new_email    = bleach.clean(raw_new_email)

            if not new_username or not new_email:
                flash("Username and email cannot be empty.", "error")
            elif new_username != current_user.username and \
                    User.query.filter_by(username=new_username).first():
                flash("That username is already taken.", "error")
            elif new_email != current_user.email and \
                    User.query.filter_by(email=new_email).first():
                flash("That email is already in use.", "error")
            else:
                current_user.username = new_username
                current_user.email    = new_email
                db.session.commit()
                flash("Profile updated. 💜", "success")

        elif action == "change_password":
            current_pw = request.form.get("current_password", "")
            new_pw     = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")

            if not current_user.check_password(current_pw):
                flash("Current password is incorrect.", "error")
            elif len(new_pw) < 8:
                flash("New password must be at least 8 characters.", "error")
            elif new_pw != confirm_pw:
                flash("New passwords do not match.", "error")
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                flash("Password changed successfully. 🔒", "success")

        elif action == "toggle_anonymous":
            current_user.is_anonymous_mode = not current_user.is_anonymous_mode
            db.session.commit()
            status = "on" if current_user.is_anonymous_mode else "off"
            flash(f"Anonymous mode turned {status}.", "info")

        elif action == "submit_feedback":
            message = request.form.get("message", "").strip()
            if not message:
                flash("Feedback message cannot be empty.", "error")
            else:
                clean_msg = bleach.clean(message)
                new_fb = Feedback(user_id=current_user.id, message=clean_msg)
                db.session.add(new_fb)
                db.session.commit()
                flash("Feedback sent to administrators. Thank you! 💌", "success")

        return redirect(url_for("auth.settings"))

    return render_template("settings.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per hour")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            # Generate 6-digit code
            code = ''.join(random.choices(string.digits, k=6))
            # Set expiry to 10 minutes from now
            expiry = datetime.utcnow() + timedelta(minutes=10)

            # Store in DB
            reset_entry = PasswordReset(email=email, code=code, expiry=expiry)
            db.session.add(reset_entry)
            db.session.commit()

            # Send email
            try:
                msg = Message("Your 3AM Verification Code", recipients=[email])
                msg.body = f"Hello,\n\nYour 6-digit verification code to reset your 3AM password is: {code}\n\nThis code will expire in 10 minutes.\n\nRemember, you are never alone. 🌙"
                mail.send(msg)
                flash("Verification code sent to your email.", "success")
                return redirect(url_for("auth.verify_code", email=email))
            except Exception as e:
                print(f"Error sending email: {e}")
                flash("Error sending email. Please try again later.", "error")
        else:
            # For security, don't tell if email exists
            flash("If that email is registered, a code has been sent.", "info")
            return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/verify-code", methods=["GET", "POST"])
def verify_code():
    email = request.args.get("email")
    if not email:
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        
        reset_entry = PasswordReset.query.filter_by(email=email, code=code).order_by(PasswordReset.created_at.desc()).first()

        if reset_entry and reset_entry.expiry > datetime.utcnow():
            # Code is valid! Store in session that this email is verified
            from flask import session
            session['reset_email'] = email
            return redirect(url_for("auth.reset_password"))
        else:
            flash("Invalid or expired code.", "error")

    return render_template("auth/verify_code.html", email=email)


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    from flask import session
    email = session.get('reset_email')
    if not email:
        flash("Please verify your email first.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            user = User.query.filter_by(email=email).first()
            if user:
                user.set_password(password)
                db.session.commit()
                # Clear session
                session.pop('reset_email', None)
                # Cleanup reset codes for this email
                PasswordReset.query.filter_by(email=email).delete()
                db.session.commit()
                
                flash("Password reset successfully. You can now log in.", "success")
                return redirect(url_for("auth.login"))
            else:
                flash("User not found.", "error")
                return redirect(url_for("auth.forgot_password"))

    return render_template("auth/reset_password.html")