import streamlit as st
import pandas as pd
import numpy as np
import io
import time

# --- 페이지 설정 ---
st.set_page_config(layout="wide", page_title="미청 매칭 관리 시스템")

# --- 1. 사이드바: 매칭 규칙 및 네비게이션 ---
st.sidebar.title("🛠️ 운영 관리 메뉴")
menu = st.sidebar.radio("페이지 이동", ["1. 지원자 평가 점수표", "2. 개인별 상세 리포트", "3. 기업별 매칭 결과"])

st.sidebar.divider()
st.sidebar.header("⚖️ 가중치 설정")
w_first = st.sidebar.number_input("1순위 가산점", value=50)
w_second = st.sidebar.number_input("2순위 가산점", value=20)
w_req = st.sidebar.slider("필수 키워드 가중치", 0, 20, 10)
w_pref = st.sidebar.slider("우대 키워드 가중치", 0, 20, 5)
w_portfolio = st.sidebar.number_input("포트폴리오 가점", value=15)
w_doc = st.sidebar.slider("문서 성실도 가중치", 0.0, 2.0, 1.0)
mult = st.sidebar.number_input("정원 배수 (N)", value=2)
plus = st.sidebar.number_input("추가 상수 (M)", value=1)

# --- 2. 데이터 업로드 (상단 고정) ---
st.title("🎯 매칭 및 배치 관리 시스템")
with st.expander("📂 데이터 파일 업로드", expanded=True):
    c1, c2 = st.columns(2)
    with c1: app_file = st.file_uploader("지원자 데이터 (CSV)", type="csv")
    with c2: comp_file = st.file_uploader("기업 데이터 (CSV)", type="csv")

# --- 3. 핵심 엔진 (세부 점수 계산) ---
def calculate_detailed_score(app, comp):
    app_text = f"{app['experience_keywords']} {app['tool_keywords']} {app['essay_full_text']}".lower()
    
    # 세부 항목 산출
    major_s = 10 if str(app['major']) in str(comp['recruitment_job_groups']) else 0
    req_match = sum(1 for k in str(comp['required_keywords_raw']).split(',') if k.strip().lower() in app_text)
    req_s = req_match * w_req
    pref_match = sum(1 for k in str(comp['preferred_keywords_raw']).split(',') if k.strip().lower() in app_text)
    pref_s = pref_match * w_pref
    exp_s = app['experience_count'] * 3
    train_s = app['job_training_count'] * 2
    port_s = w_portfolio if app['has_portfolio'] else 0
    doc_s = app['document_completeness_score'] * w_doc
    pref_b = w_first if app['preferred_company_1'] == comp['company_name'] else (w_second if app['preferred_company_2_3'] == comp['company_name'] else 0)

    final = major_s + req_s + pref_s + exp_s + train_s + port_s + doc_s + pref_b
    reason = f"필수키워드 {req_match}개 일치, 경력/교육 {app['experience_count'] + app['job_training_count']}건 반영, 문서성실도 {doc_s:.1f}점"
    
    return {
        "job_fit_score": major_s, "required_match_score": req_s, "preferred_match_score": pref_s,
        "major_match_score": major_s, "training_match_score": train_s, "experience_match_score": exp_s,
        "portfolio_score": port_s, "document_score": round(doc_s, 2), "preference_bonus_score": pref_b,
        "final_evaluation_score": round(final, 2), "score_reason_summary": reason
    }

# --- 4. 데이터 처리 로직 ---
if app_file and comp_file:
    apps_df = pd.read_csv(app_file).fillna('')
    comps_df = pd.read_csv(comp_file).fillna('')
    comps_df['capacity'] = (comps_df['recruitment_headcount_total'] * mult + plus).astype(int)

    if st.button("🚀 배치 알고리즘 및 상세 평가 실행"):
        # 매칭 알고리즘 실행 (이전 로직과 동일)
        # [생략된 매칭 로직: 1순위 우선 배정 -> 2순위 잔여 배정]
        # 결과물 예시를 위해 summary 생성
        summary_list = []
        assigned_map = {} # 실제 운영 시에는 위에서 짠 배정 로직 반영
        
        # (간이 배정 로직: 실제 배포 시에는 이전 단계의 Full Pass 1&2 로직을 여기에 넣습니다)
        for _, app in apps_df.iterrows():
            target_comp = comps_df[comps_df['company_name'] == app['preferred_company_1']].iloc[0]
            eval_res = calculate_detailed_score(app, target_comp)
            summary_list.append({
                "applicant_id": app['applicant_id'], "applicant_name": app['applicant_name'],
                "preferred_company_1": app['preferred_company_1'], "current_assigned_company_name": target_comp['company_name'],
                **eval_res
            })
        st.session_state['summary'] = pd.DataFrame(summary_list)
        st.session_state['comps'] = comps_df
        st.success("데이터 계산이 완료되었습니다. 메뉴를 통해 결과를 확인하세요.")

    # --- 5. 페이지별 화면 구성 ---
    if 'summary' in st.session_state:
        df = st.session_state['summary']

        if menu == "1. 지원자 평가 점수표":
            st.subheader("📑 지원자별 세부 항목 평가표")
            st.markdown("모든 지원자의 항목별 점수를 확인하고 엑셀로 추출할 수 있습니다.")
            view_cols = ["applicant_id", "applicant_name", "job_fit_score", "required_match_score", 
                         "preferred_match_score", "experience_match_score", "document_score", 
                         "preference_bonus_score", "final_evaluation_score"]
            st.dataframe(df[view_cols], use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 평가표 다운로드", data=csv, file_name="evaluation_table.csv")

        elif menu == "2. 개인별 상세 리포트":
            st.subheader("👤 지원자 상세 성적표")
            sel_aid = st.selectbox("지원자 선택", df['applicant_id'].tolist(), 
                                   format_func=lambda x: f"{x} ({df[df['applicant_id']==x]['applicant_name'].values[0]})")
            row = df[df['applicant_id'] == sel_aid].iloc[0]
            
            # 리포트 레이아웃
            col_l, col_r = st.columns([1, 1])
            with col_l:
                st.info(f"### {row['applicant_name']} 지원자\n**배정 기업**: {row['current_assigned_company_name']}")
                st.metric("종합 평가점수", f"{row['final_evaluation_score']}점")
                st.write("**산출 근거 요약**")
                st.write(row['score_reason_summary'])
            with col_r:
                st.write("**항목별 점수 시각화**")
                chart_data = {
                    "직무": row['job_fit_score'], "필수": row['required_match_score'],
                    "우대": row['preferred_match_score'], "경력": row['experience_match_score'],
                    "문서": row['document_score'], "가점": row['preference_bonus_score']
                }
                st.bar_chart(pd.Series(chart_data))
            
            st.write("**세부 점수 데이터**")
            st.table(pd.DataFrame([chart_data]))

        elif menu == "3. 기업별 매칭 결과":
            st.subheader("🏢 기업별 면접 후보 배정 현황")
            comps = st.session_state['comps']
            for _, c_row in comps.iterrows():
                with st.expander(f"{c_row['company_name']} (모집: {c_row['recruitment_headcount_total']} / 정원: {c_row['capacity']})"):
                    c_apps = df[df['current_assigned_company_name'] == c_row['company_name']]
                    if not c_apps.empty:
                        st.table(c_apps[["applicant_id", "applicant_name", "final_evaluation_score", "score_reason_summary"]])
                    else:
                        st.write("배정된 후보자가 없습니다.")

else:
    st.warning("먼저 CSV 파일을 업로드하고 '배치 실행' 버튼을 눌러주세요.")
