import streamlit as st
import pandas as pd
import numpy as np
import io
import time

# --- 페이지 설정 ---
st.set_page_config(layout="wide", page_title="미청 매칭 & 평가 시스템")

# --- 1. 사이드바: 운영자 메뉴 및 가중치 설정 ---
st.sidebar.title("🛠️ 운영 관리 메뉴")
menu = st.sidebar.radio("페이지 이동", ["1. 지원자 평가 점수표", "2. 개인별 상세 리포트", "3. 기업별 매칭 결과"])

st.sidebar.divider()
st.sidebar.header("⚖️ 매칭 가중치 설정")

# 가중치 입력값들
w_first = st.sidebar.number_input("1순위 지망 가산점", value=50)
w_second = st.sidebar.number_input("2순위 지망 가산점", value=20)
w_req = st.sidebar.slider("필수 키워드 가중치 (개당)", 0, 20, 10)
w_pref = st.sidebar.slider("우대 키워드 가중치 (개당)", 0, 20, 5)
w_major = st.sidebar.slider("전공 적합도 가중치", 0, 20, 10)
w_exp = st.sidebar.slider("경력 점수 가중치 (건당)", 0, 10, 3)
w_train = st.sidebar.slider("교육 점수 가중치 (건당)", 0, 10, 2)
w_portfolio = st.sidebar.number_input("포트폴리오 가산점", value=15)
w_doc = st.sidebar.slider("문서 성실도 가중치 (계수)", 0.0, 2.0, 1.0)

st.sidebar.divider()
st.sidebar.header("📏 면접 배치 규칙")
mult = st.sidebar.number_input("채용인원 배수 (N)", value=2)
plus = st.sidebar.number_input("추가 상수 (M)", value=1)

# --- 2. 데이터 업로드 섹션 ---
st.title("🎯 매칭 및 배치 통합 관리 시스템")
with st.expander("📂 데이터 파일 업로드 (CSV)", expanded=True):
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        app_file = st.file_uploader("지원자 데이터 업로드", type="csv")
    with col_u2:
        comp_file = st.file_uploader("기업 데이터 업로드", type="csv")

# --- 3. 핵심 엔진: 세부 점수 계산 함수 ---
def calculate_scores(app, comp):
    # 텍스트 데이터 전처리 (소문자화 및 공백 제거)
    app_text = f"{app['experience_keywords']} {app['tool_keywords']} {app['essay_full_text']}".lower()
    
    # 1. 전공/직무 적합도
    major_s = w_major if str(app['major']).strip() in str(comp['recruitment_job_groups']).strip() else 0
    
    # 2. 필수/우대 키워드 매칭
    req_list = [k.strip().lower() for k in str(comp['required_keywords_raw']).split(',') if k.strip()]
    req_match = sum(1 for k in req_list if k in app_text)
    req_s = req_match * w_req
    
    pref_list = [k.strip().lower() for k in str(comp['preferred_keywords_raw']).split(',') if k.strip()]
    pref_match = sum(1 for k in pref_list if k in app_text)
    pref_s = pref_match * w_pref
    
    # 3. 활동 점수
    exp_s = app['experience_count'] * w_exp
    train_s = app['job_training_count'] * w_train
    
    # 4. 문서 및 포트폴리오
    port_s = w_portfolio if app['has_portfolio'] else 0
    doc_s = app['document_completeness_score'] * w_doc
    
    # 5. 지망 가산점
    pref_b = 0
    if app['preferred_company_1'] == comp['company_name']:
        pref_b = w_first
    elif app['preferred_company_2_3'] == comp['company_name']:
        pref_b = w_second

    total = major_s + req_s + pref_s + exp_s + train_s + port_s + doc_s + pref_b
    
    # 산출 근거 텍스트
    reason = f"필수키워드 {req_match}개 일치(+{req_s}), 활동 {app['experience_count'] + app['job_training_count']}건 반영, 문서성실도 {doc_s:.1f}점"
    if pref_b > 0: reason += f", {('1지망' if pref_b==w_first else '2지망')} 가중치 포함"
    
    return {
        "job_fit_score": major_s, "required_match_score": req_s, "preferred_match_score": pref_s,
        "major_match_score": major_s, "training_match_score": train_s, "experience_match_score": exp_s,
        "portfolio_score": port_s, "document_score": round(doc_s, 2), "preference_bonus_score": pref_b,
        "final_evaluation_score": round(total, 2), "score_reason_summary": reason
    }

# --- 4. 데이터 실행 및 배치 로직 ---
if app_file and comp_file:
    # 데이터 로드 및 전처리
    apps_df = pd.read_csv(app_file).fillna('')
    comps_df = pd.read_csv(comp_file).fillna('')
    
    # 데이터 클리닝 (공백 제거)
    apps_df['preferred_company_1'] = apps_df['preferred_company_1'].str.strip()
    apps_df['preferred_company_2_3'] = apps_df['preferred_company_2_3'].str.strip()
    comps_df['company_name'] = comps_df['company_name'].str.strip()
    comps_df['capacity'] = (comps_df['recruitment_headcount_total'] * mult + plus).astype(int)

    if st.button("🚀 배치 알고리즘 실행 및 평가 리포트 생성"):
        with st.spinner("알고리즘 계산 중..."):
            score_matrix = []
            for _, app in apps_df.iterrows():
                for _, comp in comps_df.iterrows():
                    res = calculate_scores(app, comp)
                    score_matrix.append({
                        "applicant_id": app['applicant_id'],
                        "company_id": comp['company_id'],
                        "company_name": comp['company_name'],
                        "score": res['final_evaluation_score'],
                        "pref_level": 1 if app['preferred_company_1'] == comp['company_name'] else (2 if app['preferred_company_2_3'] == comp['company_name'] else 0)
                    })
            
            score_df = pd.DataFrame(score_matrix)
            assigned = {} # aid -> cid
            
            # Pass 1: 1순위 지원자 우선 배정
            for cid in comps_df['company_id']:
                cap = comps_df[comps_df['company_id'] == cid]['capacity'].values[0]
                p1_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 1)].sort_values('score', ascending=False)
                for aid in p1_pool.head(cap)['applicant_id']:
                    assigned[aid] = cid
            
            # Pass 2: 미배정자 중 2순위 지원자 배정
            unassigned_aids = set(apps_df['applicant_id']) - set(assigned.keys())
            for cid in comps_df['company_id']:
                filled = sum(1 for v in assigned.values() if v == cid)
                rem = comps_df[comps_df['company_id'] == cid]['capacity'].values[0] - filled
                if rem > 0:
                    p2_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 2) & (score_df['applicant_id'].isin(unassigned_aids))].sort_values('score', ascending=False)
                    for aid in p2_pool.head(rem)['applicant_id']:
                        assigned[aid] = cid
            
            # 최종 요약 데이터 생성
            final_summary = []
            for _, app in apps_df.iterrows():
                aid = app['applicant_id']
                target_cid = assigned.get(aid, None)
                
                # 배정된 기업 정보 (없으면 1지망 기준 점수 산출)
                if target_cid:
                    comp_row = comps_df[comps_df['company_id'] == target_cid].iloc[0]
                    assigned_cname = comp_row['company_name']
                else:
                    # 미배정자는 1지망 기업 정보를 찾아봄
                    c1_row = comps_df[comps_df['company_name'] == app['preferred_company_1']]
                    comp_row = c1_row.iloc[0] if not c1_row.empty else comps_df.iloc[0]
                    assigned_cname = "미배정"
                
                eval_data = calculate_scores(app, comp_row)
                final_summary.append({
                    "applicant_id": aid,
                    "applicant_name": app['applicant_name'],
                    "preferred_company_1": app['preferred_company_1'],
                    "assigned_company": assigned_cname,
                    **eval_data
                })
            
            st.session_state['summary'] = pd.DataFrame(final_summary)
            st.session_state['comps'] = comps_df
            st.success("배치 및 평가 리포트 생성이 완료되었습니다!")

    # --- 5. 페이지별 레이아웃 구성 ---
    if 'summary' in st.session_state:
        summary_df = st.session_state['summary']

        # [페이지 1: 전체 점수표]
        if menu == "1. 지원자 평가 점수표":
            st.subheader("📑 지원자 세부 평가 점수 현황")
            st.markdown("모든 지원자의 항목별 점수를 확인하고 엑셀로 내려받을 수 있습니다.")
            
            cols = ["applicant_id", "applicant_name", "assigned_company", "job_fit_score", "required_match_score", 
                    "preferred_match_score", "experience_match_score", "document_score", "final_evaluation_score"]
            st.dataframe(summary_df[cols], use_container_width=True)
            
            csv = summary_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 전체 평가표 다운로드 (CSV)", data=csv, file_name="evaluation_summary.csv")

        # [페이지 2: 개인별 리포트]
        elif menu == "2. 개인별 상세 리포트":
            st.subheader("👤 개인별 심층 평가 리포트")
            
            sel_aid = st.selectbox("지원자를 선택하세요", summary_df['applicant_id'].tolist(),
                                   format_func=lambda x: f"{x} ({summary_df[summary_df['applicant_id']==x]['applicant_name'].values[0]})")
            
            row = summary_df[summary_df['applicant_id'] == sel_aid].iloc[0]
            
            c_left, c_right = st.columns([1, 1])
            with c_left:
                st.info(f"#### {row['applicant_name']} 후보자\n**현재 배정 기업**: {row['assigned_company']}")
                st.metric("종합 평가점수", f"{row['final_evaluation_score']}점")
                st.write("**📝 점수 산출 근거**")
                st.success(row['score_reason_summary'])
            
            with c_right:
                st.write("**📊 항목별 역량 분석**")
                chart_data = {
                    "직무적합": row['job_fit_score'], "필수매칭": row['required_match_score'],
                    "우대매칭": row['preferred_match_score'], "경력점수": row['experience_match_score'],
                    "문서점수": row['document_score'], "지망가점": row['preference_bonus_score']
                }
                st.bar_chart(pd.Series(chart_data))
            
            st.write("**📋 세부 평가 데이터**")
            st.table(pd.DataFrame([chart_data]))

        # [페이지 3: 기업별 매칭 결과]
        elif menu == "3. 기업별 매칭 결과":
            st.subheader("🏢 기업별 면접 후보자 배정 명단")
            comps = st.session_state['comps']
            
            for _, c in comps.iterrows():
                with st.expander(f"📍 {c['company_name']} (모집: {c['recruitment_headcount_total']} / 정원: {c['capacity']})"):
                    # 해당 기업에 배정된 지원자 필터링
                    c_assigned = summary_df[summary_df['assigned_company'] == c['company_name']]
                    if not c_assigned.empty:
                        st.table(c_assigned[["applicant_id", "applicant_name", "final_evaluation_score", "score_reason_summary"]])
                    else:
                        st.write("해당 기업에 배정된 인원이 없습니다.")
else:
    st.info("지원자와 기업 CSV 파일을 업로드한 후 배치를 실행해 주세요.")
