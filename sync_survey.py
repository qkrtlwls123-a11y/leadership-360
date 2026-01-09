import gspread
import pymysql
import json
import re
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'service_account.json')
FORMS_CONFIG_FILE = os.path.join(BASE_DIR, 'forms_config.json')

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "Zmfflr19!@"),
    "database": os.getenv("DB_NAME", "test"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

# --- [2] 웹 서버 연동용 클래스 및 함수 (이게 없어서 오류가 났던 것) ---
class SyncError(Exception):
    """동기화 중 발생하는 사용자 정의 에러"""
    pass

def load_config():
    """설정 파일 읽기"""
    if not os.path.exists(FORMS_CONFIG_FILE):
        return []
    with open(FORMS_CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def add_survey_config(new_config):
    """새로운 설문 설정을 JSON에 추가"""
    configs = load_config()
    configs.append(new_config)
    with open(FORMS_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(configs, f, ensure_ascii=False, indent=4)

# --- [3] 핵심 로직 ---
def get_db_connection():
    return pymysql.connect(**DB_CONFIG)

def get_or_create_question_id(cursor, question_text):
    sql = "SELECT id FROM question_bank WHERE question_text = %s"
    cursor.execute(sql, (question_text,))
    result = cursor.fetchone()
    if result:
        return result['id']
    else:
        sql = "INSERT INTO question_bank (category, type, question_text, keyword) VALUES ('미분류', '자동생성', %s, 'auto')"
        cursor.execute(sql, (question_text,))
        return cursor.lastrowid

def sync_sheet(survey_info, gc, conn):
    # 구글 시트 연결
    try:
        sh = gc.open_by_url(survey_info['sheet_url'])
        worksheet = sh.sheet1
    except Exception as e:
        return f"실패: 시트 접근 불가 ({str(e)})"

    all_values = worksheet.get_all_values()
    if not all_values: return "데이터 없음"

    headers = all_values[0]
    data_rows = all_values[1:]

    # 헤더에 SyncStatus 없으면 추가
    if 'SyncStatus' not in headers:
        headers.append('SyncStatus')
        worksheet.update(values=[headers], range_name="1:1")
        sync_col_idx = len(headers)
    else:
        sync_col_idx = headers.index('SyncStatus') + 1

    new_count = 0
    cells_to_update = [] 

    with conn.cursor() as cursor:
        # 설문 정보 등록
        sql_survey = """
            INSERT INTO survey_info (client_name, course_name, manager, date, category, survey_name)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)
        """
        cursor.execute(sql_survey, (
            survey_info['client'], survey_info['course'], survey_info['manager'], 
            survey_info['date'], survey_info['category'], survey_info['survey_name']
        ))
        survey_id = cursor.lastrowid

        # 질문 매핑
        question_map = {}
        for idx, text in enumerate(headers):
            if text in ['타임스탬프', 'timestamp', 'SyncStatus'] or not text.strip(): continue
            question_map[idx] = get_or_create_question_id(cursor, text)

        # 데이터 저장
        for row_idx, row in enumerate(data_rows):
            excel_row_num = row_idx + 2
            # 이미 처리된 행인지 확인
            if len(row) >= sync_col_idx and row[sync_col_idx - 1] == 'Y':
                continue

            respondent_id = f"S{survey_id}_R{excel_row_num}"
            
            for col_idx, answer in enumerate(row):
                if col_idx in question_map and col_idx != (sync_col_idx - 1):
                    q_id = question_map[col_idx]
                    sql_resp = "INSERT INTO responses (survey_id, respondent_id, question_id, answer_value) VALUES (%s, %s, %s, %s)"
                    cursor.execute(sql_resp, (survey_id, respondent_id, q_id, answer))
            
            # 업데이트할 셀 목록에 추가 (메모리)
            cells_to_update.append(gspread.Cell(excel_row_num, sync_col_idx, 'Y'))
            new_count += 1

        conn.commit()

    # 구글 시트에 한 번에 반영 (Batch Update)
    if cells_to_update:
        try:
            worksheet.update_cells(cells_to_update)
        except Exception as e:
            print(f"경고: 시트 업데이트 실패 ({e})")

    return f"성공 ({new_count}건)"

def run_sync():
    if not os.path.exists(SERVICE_ACCOUNT_FILE): raise SyncError("service_account.json 없음")
    if not os.path.exists(FORMS_CONFIG_FILE): return "설정 파일 없음 (설문이 등록되지 않음)"

    configs = load_config()
    if not configs: return "등록된 설문이 없습니다."

    try:
        client = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
    except Exception as e:
        raise SyncError(f"구글 인증 실패: {e}")

    results = []
    try:
        conn = get_db_connection()
        for survey in configs:
            res = sync_sheet(survey, client, conn)
            results.append(f"[{survey['survey_name']}] {res}")
        conn.close()
    except Exception as e:
        raise SyncError(f"DB 오류: {e}")

    return "\n".join(results)

if __name__ == "__main__":
    print(run_sync())
