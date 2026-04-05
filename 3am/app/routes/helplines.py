from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Helpline

helplines_bp = Blueprint("helplines", __name__)


@helplines_bp.route("/helplines")
@login_required
def helplines():
    lines = Helpline.query.order_by(Helpline.is_24hr.desc()).all()
    return render_template("helplines.html", helplines=lines)