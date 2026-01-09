import json
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

import gspread
import pymysql
from pymysql.cursors import DictCursor

CONFIG_PATH = os.getenv("FORMS_CONFIG_PATH", "forms_config.json")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT", "service_account.json")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "survey_db"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
    "autocommit": False,
}


class SyncError(RuntimeError):
    pass


def load_config(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_config(path: str, entries: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=2)


def get_gspread_client() -> gspread.client.Client:
    return gspread.service_account(filename=SERVICE_ACCOUNT_FILE)


def get_db_connection() -> pymysql.connections.Connection:
    return pymysql.connect(**DB_CONFIG)


def normalize_date(date_text: str) -> str:
    try:
        parsed = datetime.strptime(date_text, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d")
    except ValueError as exc:
        raise SyncError(f"date 형식이 올바르지 않습니다: {date_text}") from exc


def ensure_survey(cursor: DictCursor, entry: Dict[str, Any]) -> int:
    date_value = normalize_date(entry["date"])
    insert_sql = (
        "INSERT INTO survey_info "
        "(client_name, course_name, manager, date, category, survey_name) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)"
    )
    cursor.execute(
        insert_sql,
        (
            entry["client"],
            entry["course"],
            entry["manager"],
            date_value,
            entry["category"],
            entry["survey_name"],
        ),
    )
    return int(cursor.lastrowid)


def ensure_question(cursor: DictCursor, question_text: str, category: str) -> int:
    insert_sql = (
        "INSERT INTO question_bank (category, question_text) "
        "VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)"
    )
    cursor.execute(insert_sql, (category, question_text))
    return int(cursor.lastrowid)


def ensure_synced_column(worksheet: gspread.Worksheet, headers: List[str]) -> int:
    if "Synced" in headers:
        return headers.index("Synced") + 1
    synced_col_index = len(headers) + 1
    worksheet.update_cell(1, synced_col_index, "Synced")
    headers.append("Synced")
    return synced_col_index


def fetch_sheet_rows(worksheet: gspread.Worksheet) -> Tuple[List[str], List[List[str]]]:
    values = worksheet.get_all_values()
    if not values:
        return [], []
    headers = values[0]
    rows = values[1:]
    return headers, rows


def sync_sheet(entry: Dict[str, Any]) -> Dict[str, Any]:
    client = get_gspread_client()
    sheet = client.open_by_url(entry["sheet_url"])
    worksheet = sheet.sheet1

    headers, rows = fetch_sheet_rows(worksheet)
    if not headers:
        return {"survey_name": entry["survey_name"], "status": "empty"}

    synced_col_index = ensure_synced_column(worksheet, headers)
    question_headers = [h for h in headers if h and h != "Synced"]

    with get_db_connection() as connection:
        cursor = connection.cursor()
        survey_id = ensure_survey(cursor, entry)

        question_ids: Dict[str, int] = {}
        for question_text in question_headers:
            question_ids[question_text] = ensure_question(
                cursor, question_text, entry["category"]
            )

        inserted = 0
        for row_offset, row in enumerate(rows, start=2):
            synced_value = row[synced_col_index - 1] if len(row) >= synced_col_index else ""
            if synced_value.strip().lower() == "yes":
                continue

            respondent_id = f"{survey_id}_{row_offset}"
            for col_index, question_text in enumerate(question_headers, start=1):
                answer_value = row[col_index - 1] if len(row) >= col_index else ""
                question_id = question_ids[question_text]
                cursor.execute(
                    "INSERT IGNORE INTO responses "
                    "(survey_id, respondent_id, question_id, answer_value) "
                    "VALUES (%s, %s, %s, %s)",
                    (survey_id, respondent_id, question_id, answer_value),
                )
                inserted += cursor.rowcount

            worksheet.update_cell(row_offset, synced_col_index, "Yes")

        connection.commit()

    return {
        "survey_name": entry["survey_name"],
        "survey_id": survey_id,
        "inserted": inserted,
    }


def run_sync() -> Dict[str, Any]:
    entries = load_config(CONFIG_PATH)
    if not entries:
        return {"status": "no-config", "message": "등록된 설문이 없습니다."}

    results = []
    for entry in entries:
        results.append(sync_sheet(entry))

    return {"status": "ok", "results": results}


if __name__ == "__main__":
    outcome = run_sync()
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
