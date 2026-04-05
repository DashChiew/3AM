from datetime import datetime, date
from flask_login import UserMixin
from app import db, bcrypt
import hashlib


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id             = db.Column(db.Integer, primary_key=True)
    username       = db.Column(db.String(80), unique=True, nullable=False)
    email          = db.Column(db.String(120), unique=True, nullable=False)
    password_hash  = db.Column(db.String(255), nullable=False)
    is_anonymous_mode = db.Column(db.Boolean, default=False)
    is_admin       = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    last_active    = db.Column(db.DateTime, default=datetime.utcnow)
    checkin_streak = db.Column(db.Integer, default=0)
    last_checkin   = db.Column(db.Date, nullable=True)

    # Relationships — one user has many moods, posts, etc.
    moods    = db.relationship("Mood", backref="user", lazy=True)
    posts    = db.relationship("Post", backref="user", lazy=True)

    def set_password(self, password):
        """Hash the password before saving — never store plain text."""
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        """Check if entered password matches the stored hash."""
        return bcrypt.check_password_hash(self.password_hash, password)


class Mood(db.Model):
    __tablename__ = "moods"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mood_score = db.Column(db.Integer, nullable=False)   # 1 to 10
    mood_emoji = db.Column(db.String(10), nullable=True)
    note       = db.Column(db.Text, nullable=True)
    logged_at  = db.Column(db.DateTime, default=datetime.utcnow)


class Post(db.Model):
    __tablename__ = "posts"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content      = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    is_flagged   = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    comments     = db.relationship("Comment", backref="post", lazy=True)


class Comment(db.Model):
    __tablename__ = "comments"

    id           = db.Column(db.Integer, primary_key=True)
    post_id      = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content      = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    author       = db.relationship("User", foreign_keys=[user_id])


class Helpline(db.Model):
    __tablename__ = "helplines"

    id      = db.Column(db.Integer, primary_key=True)
    name    = db.Column(db.String(200), nullable=False)
    phone   = db.Column(db.String(50), nullable=False)
    type    = db.Column(db.String(100), nullable=False)
    is_24hr = db.Column(db.Boolean, default=True)
    country = db.Column(db.String(100), default="Malaysia")


class ChatRoom(db.Model):
    __tablename__ = "chat_rooms"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    topic       = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(300), nullable=True)
    is_active   = db.Column(db.Boolean, default=True)


class CrisisAlert(db.Model):
    __tablename__ = "crisis_alerts"

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    trigger_keyword = db.Column(db.String(100), nullable=False)
    context         = db.Column(db.Text, nullable=True)
    detected_at     = db.Column(db.DateTime, default=datetime.utcnow)
    resolved        = db.Column(db.Boolean, default=False)
    user            = db.relationship("User", foreign_keys=[user_id])


class Conversation(db.Model):
    __tablename__ = "conversations"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    sender     = db.Column(db.String(10), nullable=False)  # 'user' or 'bot'
    session_id = db.Column(db.String(64), nullable=False)
    timestamp  = db.Column(db.DateTime, default=datetime.utcnow)


class ConvSummary(db.Model):
    __tablename__ = "conv_summaries"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    summary_text = db.Column(db.Text, nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)


class Announcement(db.Model):
    __tablename__ = "announcements"

    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    author     = db.relationship("User", foreign_keys=[author_id])
    reactions  = db.relationship("AnnouncementReaction", backref="announcement", lazy=True, cascade="all, delete-orphan")


class AnnouncementReaction(db.Model):
    __tablename__ = "announcement_reactions"

    id = db.Column(db.Integer, primary_key=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey("announcements.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    emoji = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('announcement_id', 'user_id', 'emoji', name='_uc_ann_user_emoji'),)


class PasswordReset(db.Model):
    __tablename__ = "password_resets"

    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(120), nullable=False)
    code       = db.Column(db.String(6), nullable=False)
    expiry     = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id           = db.Column(db.Integer, primary_key=True)
    room_id      = db.Column(db.Integer, db.ForeignKey("chat_rooms.id"), nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message      = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    timestamp    = db.Column(db.DateTime, default=datetime.utcnow)
    user      = db.relationship("User", foreign_keys=[user_id])


class Feedback(db.Model):
    __tablename__ = "feedbacks"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user       = db.relationship("User", foreign_keys=[user_id])