from flask import Flask, render_template, request

from config import Config
from database import db
from services import SyncError, add_survey_config_entry, run_sync_all
from utils import load_json_config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.route("/", methods=["GET", "POST"])
    def index():
        message = None
        error = None
        results = None

        if request.method == "POST":
            try:
                summary = run_sync_all()
                message = summary["message"]
                results = summary.get("synced", [])
            except Exception as exc:
                error = str(exc)

        return render_template("index.html", message=message, error=error, results=results)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        error = None
        success = None

        if request.method == "POST":
            try:
                updated = add_survey_config_entry(request.form)
                success = "설문 정보가 업데이트되었습니다." if updated else "설문 정보가 등록되었습니다."
            except SyncError as exc:
                error = str(exc)
            except Exception as exc:
                error = f"시스템 오류: {str(exc)}"

        return render_template("register.html", error=error, success=success)

    @app.route("/config")
    def config_view():
        data = load_json_config(Config.FORMS_CONFIG_PATH)
        return render_template("config.html", data=data)

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000, debug=True)
