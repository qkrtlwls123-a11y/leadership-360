from datetime import datetime

from config import Config
from database import db
from models import QuestionBank, Response, SurveyInfo
from utils import get_gspread_client, load_json_config, open_sheet, save_json_config


class SyncError(Exception):
    pass


def ensure_synced_column(worksheet, headers):
    if headers and headers[-1].strip().lower() == "synced":
        return headers, len(headers)

    new_headers = headers + ["Synced"]
    if worksheet.row_count < 1:
        worksheet.resize(rows=100)

    worksheet.resize(cols=len(new_headers))
    worksheet.update(range_name="1:1", values=[new_headers])
    return new_headers, len(new_headers)


def get_or_create_question(category, text):
    question = QuestionBank.query.filter_by(question_text=text).first()
    if not question:
        question = QuestionBank(category=category, type="자동생성", question_text=text)
        db.session.add(question)
        db.session.commit()
    return question


def get_or_create_survey_info(config_entry):
    try:
        survey_date = datetime.strptime(config_entry["date"], "%Y-%m-%d").date()
    except ValueError as exc:
        raise SyncError(
            f"Invalid date format for {config_entry.get('survey_name')}"
        ) from exc

    survey = SurveyInfo.query.filter_by(
        client_name=config_entry["client"],
        course_name=config_entry["course"],
        manager=config_entry["manager"],
        date=survey_date,
        category=config_entry["category"],
        survey_name=config_entry["survey_name"],
    ).first()

    if not survey:
        survey = SurveyInfo(
            client_name=config_entry["client"],
            course_name=config_entry["course"],
            manager=config_entry["manager"],
            date=survey_date,
            category=config_entry["category"],
            survey_name=config_entry["survey_name"],
        )
        db.session.add(survey)
        db.session.commit()

    return survey


def sync_single_sheet(client, config_entry):
    try:
        spreadsheet = open_sheet(client, config_entry["sheet_url"])
        worksheet = spreadsheet.sheet1
        all_values = worksheet.get_all_values()
    except Exception as exc:
        return {
            "survey_name": config_entry.get("survey_name"),
            "synced_rows": 0,
            "error": str(exc),
        }

    if not all_values:
        return {"survey_name": config_entry["survey_name"], "synced_rows": 0}

    headers = all_values[0]
    headers, synced_col_idx = ensure_synced_column(worksheet, headers)
    question_headers = headers[:-1]

    survey = get_or_create_survey_info(config_entry)

    question_map = {}
    for q_text in question_headers:
        if q_text:
            q_obj = get_or_create_question(config_entry["category"], q_text)
            question_map[q_text] = q_obj.id

    synced_count = 0

    for row_idx, row_data in enumerate(all_values[1:], start=2):
        row_data = row_data + [""] * (len(headers) - len(row_data))

        synced_flag = row_data[synced_col_idx - 1].strip().lower()
        if synced_flag in ("y", "yes", "true", "1", "synced"):
            continue

        respondent_id = f"{survey.id}_{row_idx}"

        existing = Response.query.filter_by(
            survey_id=survey.id, respondent_id=respondent_id
        ).first()

        if not existing:
            for q_text, answer in zip(question_headers, row_data[: len(question_headers)]):
                if not q_text or not answer.strip():
                    continue

                q_id = question_map.get(q_text)
                if q_id:
                    new_resp = Response(
                        survey_id=survey.id,
                        respondent_id=respondent_id,
                        question_id=q_id,
                        answer_value=answer,
                    )
                    db.session.add(new_resp)

            try:
                db.session.commit()
                synced_count += 1
                worksheet.update_cell(row_idx, synced_col_idx, "Y")
            except Exception:
                db.session.rollback()
        else:
            worksheet.update_cell(row_idx, synced_col_idx, "Y")

    return {"survey_name": config_entry["survey_name"], "synced_rows": synced_count}


def run_sync_all():
    configs = load_json_config(Config.FORMS_CONFIG_PATH)
    if not configs:
        return {"message": "No surveys configured.", "synced": []}

    try:
        client = get_gspread_client()
    except Exception as exc:
        raise SyncError(str(exc)) from exc

    results = []
    for config_entry in configs:
        try:
            res = sync_single_sheet(client, config_entry)
            results.append(res)
        except Exception as exc:
            results.append(
                {
                    "survey_name": config_entry.get("survey_name"),
                    "error": str(exc),
                    "synced_rows": 0,
                }
            )

    return {"message": "Sync completed", "synced": results}


def add_survey_config_entry(form_data):
    required = ["client", "course", "manager", "date", "category", "survey_name", "sheet_url"]
    entry = {k: form_data.get(k, "").strip() for k in required}

    for key, value in entry.items():
        if not value:
            raise SyncError(f"Missing field: {key}")

    try:
        datetime.strptime(entry["date"], "%Y-%m-%d")
    except ValueError as exc:
        raise SyncError("Date must be in YYYY-MM-DD format") from exc

    configs = load_json_config(Config.FORMS_CONFIG_PATH)

    updated = False
    for index, cfg in enumerate(configs):
        if cfg.get("sheet_url") == entry["sheet_url"]:
            configs[index] = entry
            updated = True
            break

    if not updated:
        configs.append(entry)

    save_json_config(Config.FORMS_CONFIG_PATH, configs)
    return updated
