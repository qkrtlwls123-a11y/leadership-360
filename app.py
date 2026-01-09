import json
import os
from typing import Any, Dict, List

from flask import Flask, render_template, request

import sync_survey

CONFIG_PATH = os.getenv("FORMS_CONFIG_PATH", "forms_config.json")

app = Flask(__name__)


def load_config(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_config(path: str, entries: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=2)


def normalize_entry(form: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "client": form.get("client", "").strip(),
        "course": form.get("course", "").strip(),
        "manager": form.get("manager", "").strip(),
        "date": form.get("date", "").strip(),
        "category": form.get("category", "").strip(),
        "survey_name": form.get("survey_name", "").strip(),
        "sheet_url": form.get("sheet_url", "").strip(),
    }


def validate_entry(entry: Dict[str, Any]) -> List[str]:
    missing = [key for key, value in entry.items() if not value]
    return missing


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    message = ""
    sync_result = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "sync":
            sync_result = sync_survey.run_sync()
            message = "동기화 완료" if sync_result.get("status") == "ok" else "동기화 실패"
        if action == "register":
            entry = normalize_entry(request.form)
            missing = validate_entry(entry)
            if missing:
                message = f"필수 값이 누락되었습니다: {', '.join(missing)}"
            else:
                entries = load_config(CONFIG_PATH)
                entries.append(entry)
                save_config(CONFIG_PATH, entries)
                message = "설문이 등록되었습니다."

    entries = load_config(CONFIG_PATH)
    return render_template("index.html", message=message, sync_result=sync_result, entries=entries)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
