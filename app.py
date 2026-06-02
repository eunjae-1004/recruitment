import streamlit as st
import pandas as pd
import numpy as np
import io

# --- 페이지 설정 ---
st.set_page_config(layout="wide", page_title="미청 매칭 관리 시스템")

st.title("🤝 지원자-기업 자동 매칭 및 배치 시스템")
st.markdown("지원자 데이터와 기업 데이터를 업로드하고, 규칙을 설정하여 최적의 면접 후보를 배치하세요.")

# --- 사이드바: 규칙 설정 엔진 ---
st.sidebar.header("⚙️ 매칭 규칙 설정")

with st.sidebar.expander("점수 가중치 설정", expanded=True):
    p1_bonus = st.number_input("1순위 지망 가산점", value=50)
    p2_bonus = st.number_input("2순위 지망 가산점", value=20)
    req_w = st.slider("필수 키워드 매칭 가중치", 0, 50, 10)
    pref_w = st.slider("우대 키워드 매칭 가중치", 0, 50, 5)
    portfolio_b = st.number_input("포트폴리오 가산점", value=15)
    doc_w = st.slider("문서 완성도 가중치", 0.0, 2.0, 1.0)

with st.sidebar.expander("면접 정원 공식", expanded=True):
    mult = st.number_input("채용인원 배수 (N)", value=2)
    plus = st.number_input("추가 상수 (M)", value=1)
    st.caption(f"공식: (채용인원 * {mult}) + {plus}")

# --- 데이터 업로드 섹션 ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("👤 지원자 데이터")
    app_file = st.file_uploader("applicant_recommendation_dataset.csv 업로드", type="csv")
with col2:
    st.subheader("🏢 기업 데이터")
    comp_file = st.file_uploader("company_information_dataset.csv 업로드", type="csv")

# --- 매칭 로직 함수 ---
def run_matching(apps, comps):
    comps['interview_capacity'] = (comps['recruitment_headcount_total'] * mult + plus).astype(int)
    all_scores = []
    for _, comp in comps.iterrows():
        for _, app in apps.iterrows():
            score = 0
            pref_level = 0
            if app['preferred_company_1'] == comp['company_name']:
                score += p1_bonus
                pref_level = 1
            elif app['preferred_company_2_3'] == comp['company_name']:
                score += p2_bonus
                pref_level = 2
            app_keywords = str(app.get('experience_keywords', ''))
            comp_req = str(comp.get('required_keywords_raw', ''))
            match_count = sum(1 for k in str(comp_req).split(',') if k.strip() in app_keywords)
            score += match_count * req_w
            if app.get('has_portfolio') == True: score += portfolio_b
            score += app.get('document_completeness_score', 0) * doc_w
            all_scores.append({
                'company_id': comp['company_id'], 'company_name': comp['company_name'],
                'applicant_id': app['applicant_id'], 'applicant_name': app['applicant_name'],
                'final_score': score, 'pref_level': pref_level
            })
    score_df = pd.DataFrame(all_scores)
    assigned_list = []
    apps_assigned = set()
    for _, comp in comps.iterrows():
        cid = comp['company_id']
        cap = comp['interview_capacity']
        pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 1)].sort_values('final_score', ascending=False)
        top_apps = pool.head(cap)
        assigned_list.append(top_apps)
        apps_assigned.update(top_apps['applicant_id'].tolist())
    current_assigned = pd.concat(assigned_list)
    for _, comp in comps.iterrows():
        cid = comp['company_id']
        cap = comp['interview_capacity']
        already_filled = len(current_assigned[current_assigned['company_id'] == cid])
        rem_cap = cap - already_filled
        if rem_cap > 0:
            pool2 = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 2) & (~score_df['applicant_id'].isin(apps_assigned))].sort_values('final_score', ascending=False)
            top_apps2 = pool2.head(rem_cap)
            assigned_list.append(top_apps2)
            apps_assigned.update(top_apps2['applicant_id'].tolist())
    return pd.concat(assigned_list)

# --- 실행 및 표시 ---
if app_file and comp_file:
    apps_df = pd.read_csv(app_file)
    comps_df = pd.read_csv(comp_file)
    if st.button("🚀 배치 알고리즘 실행"):
        result = run_matching(apps_df, comps_df)
        st.session_state['result'] = result
    if 'result' in st.session_state:
        res = st.session_state['result']
        st.divider()
        st.subheader("📊 배치 요약 통계")
        s1, s2, s3 = st.columns(3)
        s1.metric("총 지원자", len(apps_df))
        s2.metric("면접 배정 인원", len(res))
        s3.metric("배정률", f"{(len(res)/len(apps_df)*100):.1f}%")
        st.subheader("🔍 기업별 상세 배정 명단")
        target_comp = st.selectbox("기업 선택", ["전체보기"] + comps_df['company_name'].tolist())
        display_df = res.copy()
        if target_comp != "전체보기": display_df = display_df[display_df['company_name'] == target_comp]
        st.dataframe(display_df, use_container_width=True)
        csv = res.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 최종 결과 CSV 다운로드", data=csv, file_name="matching_results.csv", mime="text/csv")
