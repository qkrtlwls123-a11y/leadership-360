import streamlit as st
import pandas as pd
import database as db

# 1. 앱 설정 & DB 연결
st.set_page_config(page_title="리더십 다면진단 시스템", layout="wide")

# 상단 헤더 숨기기 (깔끔한 UI)
hide_streamlit_style = """
<style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 1rem;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# DB 초기화
db.init_db()

# 2. 토큰 확인 (관리자 vs 응답자 분기)
# Streamlit 버전에 따라 query_params 접근 방식이 다를 수 있음 (최신 버전 기준)
if "token" in st.query_params:
    token = st.query_params["token"]
else:
    token = None

# ==========================================
#  Scenario A: 관리자 모드 (토큰 없음)
# ==========================================
if not token:
    st.sidebar.title("🔧 관리자 시스템")
    menu = st.sidebar.radio("Menu", ["대시보드", "데이터 등록", "데이터 조회"])
    
    if menu == "대시보드":
        st.title("📊 통합 진단 현황")
        
        conn = db.get_connection()
        # 프로젝트별 진행률 통계
        query = """
            SELECT C.name as Corporate, P.name as Project, 
                   COUNT(A.id) as Total,
                   SUM(CASE WHEN A.status='COMPLETED' THEN 1 ELSE 0 END) as Done
            FROM assignments A
            JOIN projects P ON A.project_id = P.id
            JOIN corporates C ON P.corporate_id = C.id
            GROUP BY P.id
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        if not df.empty:
            df['Progress(%)'] = (df['Done'] / df['Total'] * 100).round(1)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # 차트 시각화
            st.bar_chart(df.set_index("Project")['Progress(%)'])
        else:
            st.info("아직 등록된 진단 데이터가 없습니다. [데이터 등록] 메뉴를 이용하세요.")

    elif menu == "데이터 등록":
        st.title("📤 엑셀 일괄 등록")
        st.info("새로운 기업의 진단을 시작하려면 아래 정보를 입력하고 엑셀 파일을 업로드하세요.")
        
        with st.form("upload_form"):
            col1, col2, col3 = st.columns(3)
            corp_input = col1.text_input("기업명 (예: 삼성전자)", placeholder="(주)테크컴퍼니")
            proj_input = col2.text_input("프로젝트명", placeholder="2025 상반기 리더십 진단")
            year_input = col3.number_input("연도", value=2025, step=1)
            
            uploaded_file = st.file_uploader("대상자 명단 파일 (Excel/CSV)", type=['xlsx', 'csv'])
            
            submitted = st.form_submit_button("등록 시작")
            
            if submitted:
                if not corp_input or not proj_input or not uploaded_file:
                    st.error("기업명, 프로젝트명, 파일을 모두 입력해주세요.")
                else:
                    # 파일 읽기
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file)
                    
                    st.write("📋 업로드된 데이터 미리보기 (상위 3건)")
                    st.dataframe(df.head(3))
                    
                    # DB 처리
                    proj_id = db.get_or_create_project(corp_input, proj_input, year_input)
                    success, msg = db.process_bulk_upload(proj_id, df)
                    
                    if success:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)

        st.markdown("""
        ---
        ### 💡 엑셀 파일 작성 가이드
        아래 컬럼명을 엑셀 첫 줄에 포함해야 합니다:
        - `evaluator_name` (필수): 평가자 이름
        - `evaluator_email` (필수): 평가자 이메일
        - `leader_name` (필수): 피평가자(리더) 이름
        - `relation` (필수): 관계 (상사/동료/부하/본인)
        - `leader_code`: 리더 사번 (동명이인 구분용)
        - `evaluator_code`: 평가자 사번
        - `project_group`: 소속 그룹/부서명
        """)

    elif menu == "데이터 조회":
        st.subheader("🗂 테이블 데이터 조회 (디버깅)")
        conn = db.get_connection()
        
        tab_list = ["evaluators", "leaders", "assignments", "responses", "projects", "corporates"]
        selected_tab = st.selectbox("테이블 선택", tab_list)
        
        df = pd.read_sql(f"SELECT * FROM {selected_tab}", conn)
        st.dataframe(df, use_container_width=True)
        
        if selected_tab == "evaluators":
            st.markdown("### 👉 접속 링크 테스트")
            if not df.empty:
                sample_token = df.iloc[0]['access_token']
                st.code(f"http://localhost:8501/?token={sample_token}", language="text")
                st.caption("위 링크를 복사해서 새 창에서 열어보세요.")
        
        conn.close()

# ==========================================
#  Scenario B: 응답자 모드 (토큰 있음)
# ==========================================
else:
    user = db.get_evaluator_by_token(token)
    
    if user is None:
        st.error("⛔ 유효하지 않거나 만료된 링크입니다.")
        st.stop()
    
    # 상단 정보 표시
    st.title(f"{user['corp_name']}")
    st.markdown(f"**{user['project_name']}** | 평가자: {user['name']}님")
    
    tasks = db.get_my_assignments(user['id'])
    
    # 진척률
    completed = len(tasks[tasks['status'] == 'COMPLETED'])
    total = len(tasks)
    if total > 0:
        st.progress(completed / total, text=f"진행률: {completed} / {total} 완료")
    
    st.divider()
    
    if total == 0:
        st.info("평가할 대상이 없습니다.")
    elif completed == total:
        st.success("🎉 모든 평가를 완료하셨습니다. 감사합니다!")
        st.balloons()
    else:
        col1, col2 = st.columns([1, 2])
        
        # 좌측: 리스트
        with col1:
            st.subheader("평가 대상")
            for _, task in tasks.iterrows():
                btn_label = f"{task['leader_name']} ({task['relation']})"
                if task['status'] == 'COMPLETED':
                    st.button(f"✅ {btn_label}", key=task['id'], disabled=True, use_container_width=True)
                else:
                    if st.button(f"👉 {btn_label}", key=task['id'], type="primary", use_container_width=True):
                        st.session_state['current_task'] = task
        
        # 우측: 설문지
        with col2:
            if 'current_task' in st.session_state and st.session_state['current_task']['status'] == 'PENDING':
                task = st.session_state['current_task']
                st.subheader(f"📝 {task['leader_name']}님 평가")
                st.caption(f"관계: {task['relation']} | 부서: {task['department']}")
                
                with st.form(f"survey_{task['id']}"):
                    st.write("**Q1. 전략적 사고 능력**")
                    q1 = st.slider("비전을 명확히 제시합니까?", 1, 5, 3)
                    
                    st.write("**Q2. 의사소통 능력**")
                    q2 = st.slider("팀원의 의견을 경청합니까?", 1, 5, 3)
                    
                    st.write("**Q3. 서술형 피드백**")
                    comment = st.text_area("리더의 강점과 보완할 점을 적어주세요.")
                    
                    if st.form_submit_button("제출하기"):
                        db.save_response(task['id'], q1, q2, comment)
                        st.toast("저장되었습니다!")
                        del st.session_state['current_task']
                        st.rerun()
            elif total > completed:
                st.info("👈 왼쪽 목록에서 평가할 대상을 선택해주세요.")
