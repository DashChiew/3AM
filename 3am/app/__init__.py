import os
if os.getenv("RENDER"):
    import eventlet
    eventlet.monkey_patch()
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from dotenv import load_dotenv

load_dotenv()

db            = SQLAlchemy()
login_manager = LoginManager()
socketio      = SocketIO()
limiter       = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])
bcrypt        = Bcrypt()
jwt           = JWTManager()
mail          = Mail()


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    app.config["SECRET_KEY"]                     = os.getenv("SECRET_KEY", "dev-secret")
    app.config["JWT_SECRET_KEY"]                 = app.config["SECRET_KEY"]
    
    # Establish an absolute path for local SQLite to prevent the database from 
    # resetting if the app is run from a different terminal directory
    base_dir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.abspath(os.path.join(base_dir, "..", "instance"))
    os.makedirs(instance_dir, exist_ok=True)
    db_path = os.path.join(instance_dir, "3am.db").replace("\\", "/")
    default_sqlite_url = f"sqlite:///{db_path}"
    
    # Render provides postgres:// but SQLAlchemy 2.x needs postgresql://
    db_url = os.getenv("DATABASE_URL", "").strip('"').strip("'").strip()
    
    if not db_url:
        for k, v in os.environ.items():
            if "mysql://" in v or "postgres://" in v or "postgresql://" in v:
                db_url = v.strip('"').strip("'").strip()
                break

    if not db_url:
        db_url = default_sqlite_url

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    elif db_url.startswith("mysql://"):
        db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)
        
    print(f"🔥 BOOTING WITH DATABASE URL: {db_url} 🔥", flush=True)
    app.config["SQLALCHEMY_DATABASE_URI"]        = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["OPENAI_API_KEY"]                 = os.getenv("OPENAI_API_KEY", "")
    app.config["GEMINI_API_KEY"]                 = os.getenv("GEMINI_API_KEY", "")
    app.config["GROQ_API_KEY"]                   = os.getenv("GROQ_API_KEY", "")
    app.config["VIRUSTOTAL_API_KEY"]             = os.getenv("VIRUSTOTAL_API_KEY", "")

    # Mail configuration
    app.config["MAIL_SERVER"]       = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"]         = int(os.getenv("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"]      = os.getenv("MAIL_USE_TLS", "True") == "True"
    app.config["MAIL_USERNAME"]     = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"]     = os.getenv("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

    db.init_app(app)
    login_manager.init_app(app)
    async_mode = "eventlet" if os.getenv("RENDER") else "threading"
    socketio.init_app(app, cors_allowed_origins="*", async_mode=async_mode)
    limiter.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)

    login_manager.login_view    = "auth.login"
    login_manager.login_message = "Please log in first."

    from app.routes.auth      import auth_bp
    from app.routes.main      import main_bp
    from app.routes.feed      import feed_bp
    from app.routes.mood      import mood_bp
    from app.routes.helplines import helplines_bp
    from app.routes.emobot    import emobot_bp
    from app.routes.chat          import chat_bp
    from app.routes.admin         import admin_bp
    from app.routes.announcements import announcements_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(feed_bp)
    app.register_blueprint(mood_bp)
    app.register_blueprint(helplines_bp)
    app.register_blueprint(emobot_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(announcements_bp)

    with app.app_context():
        db.create_all()
        _seed_helplines()
        _seed_rooms()

    return app


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))


def _seed_helplines():
    from app.models import Helpline
    if not Helpline.query.first():
        db.session.add_all([
            Helpline(name="Befrienders KL",        phone="03-7627 2929", type="Emotional Support",     is_24hr=True),
            Helpline(name="Talian Kasih",           phone="15999",        type="Crisis & Emergency",    is_24hr=True),
            Helpline(name="Hospital KL Psychiatry", phone="03-2615 5555", type="Psychiatric Emergency", is_24hr=True),
            Helpline(name="MIASA",                  phone="1800-19-8055", type="Mental Health",         is_24hr=False),
            Helpline(name="MERCY Malaysia",         phone="03-9212 5373", type="General Crisis",        is_24hr=True),
        ])
        db.session.commit()


def _seed_rooms():
    from app.models import ChatRoom
    if not ChatRoom.query.first():
        db.session.add_all([
            ChatRoom(name="Can't Sleep",          topic="sleeplessness", description="For those lying awake, mind racing"),
            ChatRoom(name="Having a Panic Attack", topic="panic",        description="Immediate support for panic episodes"),
            ChatRoom(name="Just Need to Talk",    topic="general",       description="No topic — just someone to listen"),
            ChatRoom(name="Feeling Anxious",      topic="anxiety",       description="Share and manage anxiety together"),
            ChatRoom(name="Overwhelmed",          topic="stress",        description="When everything feels like too much"),
        ])
        db.session.commit()