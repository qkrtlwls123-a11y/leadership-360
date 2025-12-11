import streamlit as st
import pandas as pd
import database as db

# 1. 앱 설정 & DB 연결
st.set_page_config(page_title="리더십 다면진단 시스템", layout="wide")

# 상단 헤더 숨기기 (깔끔한 UI)
hide_streamlit_style = """
<style>
    footer {visibility: hidden;}
    .block-container {padding-top: 2rem;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# DB 초기화
db.init_db()

# 2. 토큰 확인
if "token" in st.query_params:
    token = st.query_params["token"]
else:
    token = None

# ==========================================
#  Scenario A: 관리자 모드 (토큰 없음)
# ==========================================
if not token:
    st.sidebar.title("🔧 관리자 시스템")
    menu = st.sidebar.radio("Menu", ["대시보드", "데이터 등록", "데이터 조회", "결과 관리", "설정"])

    st.title("리더십 360° B2B 진단 플랫폼")
    st.caption("SurveyMonkey 의존 없이, 멀티 테넌트 프로젝트를 한 번에 운영하세요.")

    if menu == "대시보드":
        st.subheader("📊 프로젝트별 실시간 진행률")
        df = db.get_dashboard_progress()

        if not df.empty:
            cols = st.columns(3)
            total_assignments = int(df['total'].sum())
            total_done = int(df['done'].sum())
            progress_pct = round(total_done / total_assignments * 100, 1) if total_assignments else 0
            cols[0].metric("총 배포 건수", f"{total_assignments:,}")
            cols[1].metric("완료", f"{total_done:,}")
            cols[2].metric("평균 진행률", f"{progress_pct}%")

            st.dataframe(
                df.rename(columns={"corporate": "기업", "project_name": "프로젝트", "year": "연도", "total": "배포", "done": "완료", "progress_pct": "진행률(%)"}),
                use_container_width=True,
                hide_index=True,
            )
            st.bar_chart(df.set_index("project_name")["progress_pct"])
        else:
            st.info("데이터가 없습니다. '데이터 등록'이나 '설정' 탭에서 데이터를 생성하세요.")

    elif menu == "데이터 등록":
        tab1, tab2 = st.tabs(["기업/프로젝트 생성", "엑셀 일괄 업로드"])

        with tab1:
            st.markdown("#### 1) 기업 & 프로젝트 생성")
            col1, col2, col3 = st.columns([1.2, 1.2, 0.6])
            with col1:
                corp_input = st.text_input("기업명", placeholder="(주)테크컴퍼니")
                if st.button("기업 추가") and corp_input:
                    db.create_corporate(corp_input)
                    st.success("기업이 등록되었습니다.")
            with col2:
                corp_df = db.list_corporates()
                corp_map = {row['name']: row['id'] for _, row in corp_df.iterrows()} if not corp_df.empty else {}
                corp_selected = st.selectbox("프로젝트 소속 기업", options=list(corp_map.keys())) if corp_map else None
                proj_name = st.text_input("프로젝트명", placeholder="2025 상반기 리더십 진단")
            with col3:
                proj_year = st.number_input("연도", value=2025, step=1)

            if st.button("프로젝트 생성", type="primary"):
                if corp_selected and proj_name:
                    db.create_project(corp_map[corp_selected], proj_name, proj_year)
                    st.success("프로젝트가 생성되었습니다.")
                else:
                    st.warning("기업과 프로젝트명을 모두 입력해주세요.")

            st.divider()
            st.caption("현재 등록된 기업/프로젝트")
            proj_df = db.list_projects()
            if proj_df.empty:
                st.info("등록된 프로젝트가 없습니다.")
            else:
                st.dataframe(
                    proj_df.rename(columns={"corporate_name": "기업", "name": "프로젝트", "year": "연도"})[
                        ["기업", "프로젝트", "연도"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

        with tab2:
            st.markdown("#### 2) 배포용 엑셀 업로드")
            st.write("평가자-피평가자-관계를 한 번에 매핑합니다. 필수 컬럼: **evaluator_name, evaluator_email, leader_name, relation**")
            with st.form("upload_form"):
                col1, col2, col3 = st.columns(3)
                corp_input = col1.text_input("기업명", placeholder="(주)테크컴퍼니")
                proj_input = col2.text_input("프로젝트명", placeholder="2025 상반기 진단")
                year_input = col3.number_input("연도", value=2025, step=1)
                uploaded_file = st.file_uploader("파일 선택", type=['xlsx', 'csv'])

                if st.form_submit_button("등록 시작", type="primary"):
                    if uploaded_file and corp_input and proj_input:
                        if uploaded_file.name.endswith('.csv'):
                            df = pd.read_csv(uploaded_file)
                        else:
                            df = pd.read_excel(uploaded_file)

                        proj_id = db.get_or_create_project(corp_input, proj_input, year_input)
                        success, msg = db.process_bulk_upload(proj_id, df)
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("정보를 모두 입력해주세요.")

    elif menu == "데이터 조회":
        st.subheader("🗂 테이블 조회")
        proj_df = db.list_projects()
        selected_project = None
        if not proj_df.empty:
            project_options = [
                (row['id'], f"{row['corporate_name']} - {row['name']} ({row['year']})") for _, row in proj_df.iterrows()
            ]
            selected_tuple = st.selectbox(
                "프로젝트 선택 (선택 시 assignments/responses 필터링)", options=project_options, format_func=lambda x: x[1]
            )
            selected_project = selected_tuple[0] if selected_tuple else None

        tab = st.selectbox("테이블", ["evaluators", "leaders", "assignments", "responses", "projects"])
        conn = db.get_connection()
        if tab in ["assignments", "responses"] and selected_project:
            if tab == "assignments":
                df = pd.read_sql("SELECT * FROM assignments WHERE project_id = ?", conn, params=(selected_project,))
            else:
                df = pd.read_sql(
                    """SELECT R.* FROM responses R JOIN assignments A ON R.assignment_id=A.id WHERE A.project_id=?""",
                    conn,
                    params=(selected_project,),
                )
        else:
            df = pd.read_sql(f"SELECT * FROM {tab}", conn)
        st.dataframe(df, use_container_width=True)
        conn.close()

    elif menu == "결과 관리":
        st.subheader("📥 프로젝트 결과 집계")
        proj_df = db.list_projects()
        if proj_df.empty:
            st.info("집계할 프로젝트가 없습니다. 먼저 데이터를 업로드하세요.")
        else:
            option = st.selectbox(
                "대상 프로젝트",
                options=[(row['id'], f"{row['corporate_name']} - {row['name']} ({row['year']})") for _, row in proj_df.iterrows()],
                format_func=lambda x: x[1],
            )
            project_id = option[0]

            summary = db.get_assignment_summary(project_id)
            responses = db.get_responses(project_id)

            col1, col2 = st.columns(2)
            if not summary.empty:
                col1.metric("완료 응답", int(summary['completed'].sum()))
                col2.metric("배포", int(summary['total'].sum()))
                st.markdown("**리더별 상태**")
                st.dataframe(summary.rename(columns={"leader_name": "리더", "relation": "관계", "completed": "완료", "total": "총"}), use_container_width=True, hide_index=True)
            else:
                st.info("아직 배포된 과제가 없습니다.")

            st.markdown("**응답 상세**")
            if responses.empty:
                st.info("제출된 응답이 없습니다.")
            else:
                st.dataframe(responses, use_container_width=True, hide_index=True)
                csv = responses.to_csv(index=False).encode('utf-8-sig')
                st.download_button("응답 CSV 다운로드", csv, file_name="responses.csv", mime="text/csv")

    elif menu == "설정":
        st.title("⚙️ 시스템 설정")

        st.warning("⚠️ 데이터 상태가 꼬였을 때만 사용하세요.")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("1. DB 강제 초기화 (Reset)", type="primary"):
                msg = db.reset_database()
                st.toast(msg, icon="🧹")
                st.success(msg)

        with col2:
            if st.button("2. 샘플 데이터 생성하기"):
                msg = db.create_sample_data()
                if "완료" in msg:
                    st.success(msg)
                    st.balloons()
                else:
                    st.warning(msg)

        st.divider()
        st.write("👉 **테스트 링크:**")
        # 실제 Streamlit 배포 주소가 있다면 그걸로 테스트하세요. 로컬용은 아래와 같습니다.
        st.code("https://leadership-360-test.streamlit.app/?token=test1234", language="text")

# ==========================================
#  Scenario B: 응답자 모드 (토큰 있음)
# ==========================================
else:
    user = db.get_evaluator_by_token(token)
    
    # [수정] Pandas Series 에러 방지를 위해 'is None'으로 명확하게 검사
    if user is None:
        st.error("⛔ 유효하지 않은 접속 링크입니다.")
        st.stop()
    
    st.title(f"{user['corp_name']}")
    st.caption(f"프로젝트: {user['project_name']} | 평가자: {user['name']}")
    
    tasks = db.get_my_assignments(user['id'])
    
    # 진척률 표시
    done = len(tasks[tasks['status'] == 'COMPLETED'])
    total = len(tasks)
    if total > 0:
        st.progress(done / total, text=f"진행률: {done}/{total} 완료")
    
    st.divider()
    
    if total == 0:
        st.info("할당된 평가 대상이 없습니다.")
    elif done == total:
        st.success("🎉 모든 평가를 완료했습니다. 감사합니다!")
    else:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("평가 대상")
            for _, task in tasks.iterrows():
                label = f"{task['leader_name']} ({task['relation']})"
                if task['status'] == 'COMPLETED':
                    st.button(f"✅ {label}", key=task['id'], disabled=True, use_container_width=True)
                else:
                    if st.button(f"👉 {label}", key=task['id'], type="secondary", use_container_width=True):
                        st.session_state['task'] = task
        
        with col2:
            if 'task' in st.session_state and st.session_state['task']['status'] == 'PENDING':
                t = st.session_state['task']
                st.subheader(f"📝 {t['leader_name']}님 평가")
                with st.form(f"f_{t['id']}"):
                    q1 = st.slider("Q1. 비전 제시 능력", 1, 5, 3)
                    q2 = st.slider("Q2. 소통 능력", 1, 5, 3)
                    comment = st.text_area("서술형 의견")
                    
                    if st.form_submit_button("제출"):
                        db.save_response(t['id'], q1, q2, comment)
                        st.toast("저장완료!")
                        del st.session_state['task']
                        st.rerun()
            elif total > done:
                st.info("👈 왼쪽에서 평가할 대상을 선택해주세요.")


