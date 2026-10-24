import os
import logging
from flask import Flask, render_template, g, session, send_file
from config import Config
from extensions import db
from models.user import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("aicte-portal")


def create_app(config_class=Config):
    """Application factory for the AICTE Integrated Complaint Monitoring Portal."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)

    with app.app_context():
        try:
            db.create_all()
            from scripts.seed_demo_data import ensure_schema_updated
            ensure_schema_updated()
        except Exception as e:
            logger.warning(f"Database schema initialization notice: {e}")

    # Inject global user into template contexts
    @app.before_request
    def load_authenticated_user():
        g.current_user = None
        user_id = session.get("user_id")
        if user_id:
            try:
                g.current_user = db.session.query(User).filter_by(id=user_id, is_active=True).first()
            except Exception:
                g.current_user = None

    @app.context_processor
    def inject_context():
        user = g.get("current_user")
        all_institutions = []
        active_institution = None
        if user:
            try:
                from models.institution import Institution
                all_institutions = db.session.query(Institution).order_by(Institution.name).all()
                active_id = session.get("active_institution_id", user.institution_id)
                if active_id:
                    active_institution = db.session.query(Institution).filter_by(id=active_id).first()
            except Exception:
                pass
        return {
            "current_user": user,
            "all_institutions": all_institutions,
            "active_institution": active_institution,
        }

    # Register Blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.complaints import complaints_bp
    from routes.overlaps import overlaps_bp
    from routes.institutions import institutions_bp
    from routes.reports import reports_bp
    from routes.settings import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(overlaps_bp)
    app.register_blueprint(institutions_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)

    @app.route("/download-zip")
    def download_zip():
        """Serves the complete project source code archive as a downloadable zip file."""
        from pathlib import Path
        base_dir = Path(__file__).resolve().parent
        zip_candidates = [
            base_dir / "static" / "aicte-complaint-monitoring.zip",
            base_dir / "aicte-complaint-monitoring.zip",
            base_dir.parent / "aicte-complaint-monitoring.zip",
        ]
        zip_path = next((p for p in zip_candidates if p.exists()), None)
        if not zip_path:
            from scripts.package_zip import package
            zip_path = package() or (base_dir / "static" / "aicte-complaint-monitoring.zip")
        return send_file(zip_path, as_attachment=True, download_name="aicte-complaint-monitoring.zip")

    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def internal_server_error(e):
        logger.error(f"Internal server error encountered: {e}")
        return render_template("errors/500.html"), 500

    # CLI commands
    @app.cli.command("init-db")
    def init_db_command():
        """Creates database schema tables."""
        db.create_all()
        logger.info("Database tables successfully created.")

    @app.cli.command("seed-data")
    def seed_data_command():
        """Seeds realistic demonstration institutions, complaints, overlaps, and users."""
        from scripts.seed_demo_data import seed_database
        seed_database()

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=True)
