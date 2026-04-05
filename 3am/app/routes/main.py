from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import Helpline

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    return redirect(url_for("auth.login"))


@main_bp.route("/home")
@login_required
def index():
    helplines = Helpline.query.filter_by(is_24hr=True).limit(3).all()
    return render_template("home.html", helplines=helplines)


@main_bp.route("/breathing")
@login_required
def breathing():
    return render_template("breathing.html")