import json
import os

import gspread

from config import Config


def load_json_config(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []


def save_json_config(path: str, data: list):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def get_gspread_client():
    if not os.path.exists(Config.GOOGLE_SERVICE_ACCOUNT):
        raise FileNotFoundError(
            f"Service account file not found: {Config.GOOGLE_SERVICE_ACCOUNT}"
        )
    return gspread.service_account(filename=Config.GOOGLE_SERVICE_ACCOUNT)


def open_sheet(client, url):
    return client.open_by_url(url)
