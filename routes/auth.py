from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, abort
from extensions import db
from models.user import User
from models.institution import Institution
from services.audit_service import log_audit_event

auth_bp = Blueprint("auth", __name__)


def get_current_user():
    """Retrieves the authenticated user from the database based on session."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.query(User).filter_by(id=user_id, is_active=True).first()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to access the AICTE Administrative Portal.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        user = get_current_user()
        if not user:
            session.clear()
            flash("Session expired or user inactive. Please sign in again.", "danger")
            return redirect(url_for("auth.login"))
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("auth.login", next=request.url))
            user = get_current_user()
            if not user or user.role not in allowed_roles:
                flash("Access denied: You do not possess the required permissions for this action.", "danger")
                return render_template("errors/403.html"), 403
            g.current_user = user
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        user = get_current_user()
        if user and user.is_complainant:
            return redirect(url_for("complaints.student_portal"))
        return redirect(url_for("dashboard.index"))

    institutions = db.session.query(Institution).order_by(Institution.id).all()

    if request.method == "POST":
        username_or_email = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        selected_institution_id = request.form.get("selected_institution_id", type=int)

        user = db.session.query(User).filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

        if user and user.is_active and user.check_password(password):
            user.last_login_at = datetime.utcnow()
            if user.is_institution_admin and selected_institution_id:
                user.institution_id = selected_institution_id
            db.session.commit()

            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            session["display_name"] = user.display_name
            session["role"] = user.role
            session["institution_id"] = user.institution_id
            session["active_institution_id"] = user.institution_id

            log_audit_event(
                db.session,
                actor=user,
                action="LOGIN",
                entity_type="Auth",
                entity_id=str(user.id),
                metadata={"ip": request.remote_addr, "role": user.role},
            )
            db.session.commit()

            flash(f"Welcome back, {user.display_name} ({user.role_title()}).", "success")
            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            if user.is_complainant:
                return redirect(url_for("complaints.student_portal"))
            return redirect(url_for("dashboard.index"))
        else:
            flash("Invalid credentials or account deactivated. Please verify your login details.", "danger")

    return render_template("login.html", institutions=institutions)


@auth_bp.route("/switch-institution/<int:institution_id>", methods=["GET", "POST"])
@login_required
def switch_institution(institution_id):
    """Allows institutional reviewers and officers to dynamically switch review scope to any college."""
    user = g.current_user
    if user.is_complainant:
        abort(403)

    if institution_id == 0:
        session["active_institution_id"] = 0
        flash("Review scope switched to: All Colleges (Pan-Campus oversight).", "info")
    else:
        inst = db.session.query(Institution).get(institution_id)
        if inst:
            user.institution_id = inst.id
            session["institution_id"] = inst.id
            session["active_institution_id"] = inst.id
            db.session.commit()
            flash(f"Active review campus switched to: {inst.name} ({inst.code}).", "success")
        else:
            flash("Selected institution not found.", "warning")

    return redirect(request.referrer or url_for("complaints.review_queues"))


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    user = get_current_user()
    if user:
        log_audit_event(
            db.session,
            actor=user,
            action="LOGOUT",
            entity_type="Auth",
            entity_id=str(user.id),
            metadata={"ip": request.remote_addr},
        )
        db.session.commit()

    session.clear()
    flash("You have been signed out securely.", "info")
    return redirect(url_for("auth.login"))
