import sqlite3
import pandas as pd
import uuid
import datetime

DB_FILE = "leadership_360.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """DB 테이블 생성 (최초 1회 실행)"""
    conn = get_connection()
    c = conn.cursor()
    
    # 1. 기업 (고객사)
    c.execute('''CREATE TABLE IF NOT EXISTS corporates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 2. 프로젝트 (연도/차수)
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        corporate_id INTEGER,
        name TEXT NOT NULL,
        year INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (corporate_id) REFERENCES corporates(id)
    )''')
    
    # 3. 리더 (피평가자)
    c.execute('''CREATE TABLE IF NOT EXISTS leaders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        name TEXT NOT NULL,
        leader_code TEXT,
        position TEXT,
        department TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )''')
    
    # 4. 평가자 (링크 토큰 보유)
    c.execute('''CREATE TABLE IF NOT EXISTS evaluators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        name TEXT NOT NULL,
        evaluator_code TEXT,
        email TEXT NOT NULL,
        access_token TEXT UNIQUE,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )''')
    
    # 5. 할당 (Assignment)
    c.execute('''CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        evaluator_id INTEGER,
        leader_id INTEGER,
        relation TEXT,
        project_group TEXT,
        status TEXT DEFAULT 'PENDING',
        FOREIGN KEY (evaluator_id) REFERENCES evaluators(id),
        FOREIGN KEY (leader_id) REFERENCES leaders(id)
    )''')
    
    # 6. 응답 결과
    c.execute('''CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER,
        q1_score INTEGER,
        q2_score INTEGER,
        comment TEXT,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (assignment_id) REFERENCES assignments(id)
    )''')
    
    conn.commit()
    conn.close()

# --- 관리자용: 데이터 업로드 처리 함수 ---

def get_or_create_project(corp_name, project_name, year):
    """기업명, 프로젝트명, 연도를 받아 ID를 반환 (없으면 생성)"""
    conn = get_connection()
    c = conn.cursor()
    
    try:
        # 1. 기업 확인/생성
        c.execute("SELECT id FROM corporates WHERE name = ?", (corp_name,))
        row = c.fetchone()
        if row:
            corp_id = row['id']
        else:
            c.execute("INSERT INTO corporates (name) VALUES (?)", (corp_name,))
            corp_id = c.lastrowid
            
        # 2. 프로젝트 확인/생성
        c.execute("SELECT id FROM projects WHERE corporate_id = ? AND name = ? AND year = ?", (corp_id, project_name, year))
        row = c.fetchone()
        if row:
            proj_id = row['id']
        else:
            c.execute("INSERT INTO projects (corporate_id, name, year) VALUES (?, ?, ?)", (corp_id, project_name, year))
            proj_id = c.lastrowid
            
        conn.commit()
        return proj_id
    finally:
        conn.close()

def process_bulk_upload(project_id, df):
    """엑셀 데이터를 DB에 일괄 등록"""
    conn = get_connection()
    c = conn.cursor()
    
    cnt_created = 0
    cnt_skipped = 0
    
    # 관계명 매핑 (한글 -> 코드)
    RELATION_MAP = {'상사': 'BOSS', '동료': 'PEER', '부하': 'SUB', '본인': 'SELF'}

    try:
        for _, row in df.iterrows():
            # 필수값 체크
            if pd.isna(row.get('evaluator_email')) or pd.isna(row.get('leader_name')):
                continue

            # 1. 평가자(Evaluator) 등록
            # 프로젝트 내에서 이메일로 중복 체크
            c.execute("SELECT id FROM evaluators WHERE project_id=? AND email=?", (project_id, row['evaluator_email']))
            ev_row = c.fetchone()
            
            if ev_row:
                ev_id = ev_row['id']
            else:
                # 난수 토큰 생성 (접속 링크용)
                token = uuid.uuid4().hex[:16]
                c.execute("""
                    INSERT INTO evaluators (project_id, name, evaluator_code, email, access_token)
                    VALUES (?, ?, ?, ?, ?)
                """, (project_id, row['evaluator_name'], str(row.get('evaluator_code','')), row['evaluator_email'], token))
                ev_id = c.lastrowid

            # 2. 리더(Leader) 등록
            # 이름+코드 조합으로 중복 체크
            leader_code = str(row.get('leader_code', ''))
            c.execute("SELECT id FROM leaders WHERE project_id=? AND name=? AND leader_code=?", (project_id, row['leader_name'], leader_code))
            ld_row = c.fetchone()
            
            if ld_row:
                ld_id = ld_row['id']
            else:
                c.execute("""
                    INSERT INTO leaders (project_id, name, leader_code, department, position)
                    VALUES (?, ?, ?, ?, ?)
                """, (project_id, row['leader_name'], leader_code, row.get('project_group'), row.get('leader_position', '')))
                ld_id = c.lastrowid

            # 3. 할당(Assignment) 등록
            c.execute("SELECT id FROM assignments WHERE evaluator_id=? AND leader_id=?", (ev_id, ld_id))
            if not c.fetchone():
                rel_code = RELATION_MAP.get(row.get('relation'), row.get('relation'))
                c.execute("""
                    INSERT INTO assignments (project_id, evaluator_id, leader_id, relation, project_group)
                    VALUES (?, ?, ?, ?, ?)
                """, (project_id, ev_id, ld_id, rel_code, row.get('project_group')))
                cnt_created += 1
            else:
                cnt_skipped += 1
        
        conn.commit()
        return True, f"처리 완료: 신규 {cnt_created}건, 중복 {cnt_skipped}건"
    except Exception as e:
        return False, f"오류 발생: {str(e)}"
    finally:
        conn.close()

# --- 응답자용: 조회 및 저장 함수 ---

def get_evaluator_by_token(token):
    conn = get_connection()
    query = """
        SELECT E.id, E.name, P.name as project_name, C.name as corp_name, E.project_id
        FROM evaluators E
        JOIN projects P ON E.project_id = P.id
        JOIN corporates C ON P.corporate_id = C.id
        WHERE E.access_token = ?
    """
    df = pd.read_sql(query, conn, params=(token,))
    conn.close()
    return df.iloc[0] if not df.empty else None

def get_my_assignments(evaluator_id):
    conn = get_connection()
    query = """
        SELECT A.id, L.name as leader_name, L.position, L.department, A.relation, A.status
        FROM assignments A
        JOIN leaders L ON A.leader_id = L.id
        WHERE A.evaluator_id = ?
    """
    df = pd.read_sql(query, conn, params=(evaluator_id,))
    conn.close()
    return df

def save_response(assignment_id, q1, q2, comment):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO responses (assignment_id, q1_score, q2_score, comment) VALUES (?, ?, ?, ?)", 
              (assignment_id, q1, q2, comment))
    c.execute("UPDATE assignments SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP WHERE id = ?", (assignment_id,))
    conn.commit()
    conn.close()
    return True
