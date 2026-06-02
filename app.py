import streamlit as st
import pandas as pd
import numpy as np
import io
import time

# --- 페이지 설정 ---
st.set_page_config(layout="wide", page_title="미청 매칭 & 평가 시스템")

# --- 1. 사이드바: 운영 관리 메뉴 ---
st.sidebar.title("🛠️ 운영 관리 메뉴")
menu = st.sidebar.radio("페이지 이동", [
    "1. 지원자 평가 점수표", 
    "2. 개인별 상세 리포트", 
    "3. 기업별 매칭 결과",
    "4. 2지망 매칭 현황 (구제자)"
])

st.sidebar.divider()
st.sidebar.header("⚖️ 가중치 설정")
w_first = st.sidebar.number_input("1순위 지망 가산점", value=50)
w_second = st.sidebar.number_input("2순위 지망 가산점", value=20)
w_req = st.sidebar.slider("필수 키워드 가중치", 0, 20, 10)
w_pref = st.sidebar.slider("우대 키워드 가중치", 0, 20, 5)
w_major = st.sidebar.slider("전공 적합도 가중치", 0, 20, 10)
w_exp = st.sidebar.slider("경력 점수 가중치", 0, 10, 3)
w_doc = st.sidebar.slider("문서 성실도 가중치", 0.0, 2.0, 1.0)

st.sidebar.divider()
st.sidebar.header("📏 면접 배치 규칙")
mult = st.sidebar.number_input("채용인원 배수 (N)", value=2)
plus = st.sidebar.number_input("추가 상수 (M)", value=1)

# --- 2. 데이터 업로드 ---
st.title("🎯 매칭 및 배치 통합 관리 시스템")
with st.expander("📂 데이터 파일 업로드 (CSV)", expanded=True):
    c1, c2 = st.columns(2)
    with c1: app_file = st.file_uploader("지원자 데이터 업로드", type="csv")
    with c2: comp_file = st.file_uploader("기업 데이터 업로드", type="csv")

# --- 3. 핵심 엔진: 점수 계산 함수 ---
def calculate_scores(app, comp):
    app_text = f"{app['experience_keywords']} {app['tool_keywords']} {app['essay_full_text']}".lower()
    major_s = w_major if str(app['major']).strip() in str(comp['recruitment_job_groups']).strip() else 0
    
    req_list = [k.strip().lower() for k in str(comp['required_keywords_raw']).split(',') if k.strip()]
    req_match = sum(1 for k in req_list if k in app_text)
    req_s = req_match * w_req
    
    pref_list = [k.strip().lower() for k in str(comp['preferred_keywords_raw']).split(',') if k.strip()]
    pref_match = sum(1 for k in pref_list if k in app_text)
    pref_s = pref_match * w_pref
    
    exp_s = app['experience_count'] * w_exp + app['job_training_count'] * 2
    port_s = 15 if app['has_portfolio'] else 0
    doc_s = app['document_completeness_score'] * w_doc
    
    pref_b = 0
    if app['preferred_company_1'] == comp['company_name']: pref_b = w_first
    elif app['preferred_company_2_3'] == comp['company_name']: pref_b = w_second

    total = major_s + req_s + pref_s + exp_s + port_s + doc_s + pref_b
    reason = f"필수키워드 {req_match}개 일치(+{req_s}), 활동 {app['experience_count']}건 반영, 문서성실도 {doc_s:.1f}점"
    if pref_b > 0: reason += f", {('1지망' if pref_b==w_first else '2지망')} 가점"
    
    return {
        "job_fit_score": major_s, "required_match_score": req_s, "preferred_match_score": pref_s,
        "experience_match_score": exp_s, "document_score": round(doc_s, 2), 
        "preference_bonus_score": pref_b, "final_evaluation_score": round(total, 2), 
        "score_reason_summary": reason
    }

# --- 4. 데이터 배치 로직 ---
if app_file and comp_file:
    apps_df = pd.read_csv(app_file).fillna('')
    comps_df = pd.read_csv(comp_file).fillna('')
    
    apps_df['preferred_company_1'] = apps_df['preferred_company_1'].str.strip()
    apps_df['preferred_company_2_3'] = apps_df['preferred_company_2_3'].str.strip()
    comps_df['company_name'] = comps_df['company_name'].str.strip()
    comps_df['capacity'] = (comps_df['recruitment_headcount_total'] * mult + plus).astype(int)

    if st.button("🚀 배치 알고리즘 실행 및 리포트 생성"):
        with st.spinner("계산 중..."):
            score_matrix = []
            for _, app in apps_df.iterrows():
                for _, comp in comps_df.iterrows():
                    res = calculate_scores(app, comp)
                    score_matrix.append({
                        "applicant_id": app['applicant_id'], "company_id": comp['company_id'],
                        "company_name": comp['company_name'], "score": res['final_evaluation_score'],
                        "pref_level": 1 if app['preferred_company_1'] == comp['company_name'] else (2 if app['preferred_company_2_3'] == comp['company_name'] else 0)
                    })
            score_df = pd.DataFrame(score_matrix)
            
            assigned = {}
            # Pass 1: 1순위 지망자 우선 배치
            for cid in comps_df['company_id']:
                cap = comps_df[comps_df['company_id'] == cid]['capacity'].values[0]
                p1_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 1)].sort_values('score', ascending=False)
                for aid in p1_pool.head(cap)['applicant_id']: assigned[aid] = cid
            
            # Pass 2: 미배정자 중 2순위 지망자 배치
            unassigned = set(apps_df['applicant_id']) - set(assigned.keys())
            for cid in comps_df['company_id']:
                rem = comps_df[comps_df['company_id'] == cid]['capacity'].values[0] - sum(1 for v in assigned.values() if v == cid)
                if rem > 0:
                    p2_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 2) & (score_df['applicant_id'].isin(unassigned))].sort_values('score', ascending=False)
                    for aid in p2_pool.head(rem)['applicant_id']: assigned[aid] = cid

            final_summary = []
            for _, app in apps_df.iterrows():
                aid = app['applicant_id']
                target_cid = assigned.get(aid, None)
                if target_cid:
                    comp_row = comps_df[comps_df['company_id'] == target_cid].iloc[0]
                    assigned_cname = comp_row['company_name']
                else:
                    assigned_cname = "미배정"
                    comp_row = comps_df[comps_df['company_name'] == app['preferred_company_1']].iloc[0] if not comps_df[comps_df['company_name'] == app['preferred_company_1']].empty else comps_df.iloc[0]
                
                eval_data = calculate_scores(app, comp_row)
                final_summary.append({
                    "applicant_id": aid, "applicant_name": app['applicant_name'],
                    "preferred_company_1": app['preferred_company_1'],
                    "preferred_company_2_3": app['preferred_company_2_3'],
                    "assigned_company": assigned_cname,
                    **eval_data
                })
            st.session_state['summary'] = pd.DataFrame(final_summary)
            st.session_state['comps'] = comps_df
            st.success("배치 완료!")

    if 'summary' in st.session_state:
        df = st.session_state['summary']

        # [1페이지: 점수표]
        if menu == "1. 지원자 평가 점수표":
            st.subheader("📑 지원자 세부 평가 및 지망 정보")
            view_cols = ["applicant_id", "applicant_name", "preferred_company_1", "preferred_company_2_3", "assigned_company", "final_evaluation_score", "job_fit_score", "required_match_score", "experience_match_score", "document_score"]
            st.dataframe(df[view_cols], use_container_width=True)

        # [2페이지: 개인 리포트]
        elif menu == "2. 개인별 상세 리포트":
            st.subheader("👤 개인 상세 리포트")
            sel_aid = st.selectbox("지원자 선택", df['applicant_id'].tolist(), format_func=lambda x: f"{x} ({df[df['applicant_id']==x]['applicant_name'].values[0]})")
            row = df[df['applicant_id'] == sel_aid].iloc[0]
            c_l, c_r = st.columns(2)
            with c_l:
                st.info(f"### {row['applicant_name']}\n**1지망**: {row['preferred_company_1']}\n**2지망**: {row['preferred_company_2_3']}\n**최종 배정**: {row['assigned_company']}")
                st.metric("종합 점수", f"{row['final_evaluation_score']}점")
                st.success(f"**산출 근거**: {row['score_reason_summary']}")
            with c_r:
                st.bar_chart(pd.Series({"직무": row['job_fit_score'], "필수": row['required_match_score'], "경력": row['experience_match_score'], "문서": row['document_score'], "가점": row['preference_bonus_score']}))

        # [3페이지: 기업별 결과]
        elif menu == "3. 기업별 매칭 결과":
            st.subheader("🏢 기업별 배정 명단")
            for _, c in st.session_state['comps'].iterrows():
                with st.expander(f"{c['company_name']} (정원: {c['capacity']})"):
                    c_res = df[df['assigned_company'] == c['company_name']]
                    if not c_res.empty:
                        st.table(c_res[["applicant_id", "applicant_name", "preferred_company_1", "final_evaluation_score", "score_reason_summary"]])
                    else: st.write("배정 인원 없음")

        # [4페이지: 2지망 매칭 현황]
        elif menu == "4. 2지망 매칭 현황 (구제자)":
            st.subheader("🔄 2지망 기업 매칭 현황 (1순위 탈락자)")
            st.markdown("1지망 기업에는 정원 초과로 배정되지 못했으나, **2지망 기업에 성공적으로 매칭**된 지원자 명단입니다.")
            
            # 로직: 배정된 기업이 1지망이 아니면서, 2지망과 일치하는 경우 필터링
            second_match_df = df[
                (df['assigned_company'] == df['preferred_company_2_3']) & 
                (df['assigned_company'] != df['preferred_company_1']) &
                (df['assigned_company'] != "미배정")
            ]
            
            if not second_match_df.empty:
                st.info(f"총 **{len(second_match_df)}명**의 지원자가 2지망 기업에 구제되었습니다.")
                
                # 가독성을 위해 컬럼 재구성
                display_cols = [
                    "applicant_id", 
                    "applicant_name", 
                    "preferred_company_1", # 실패한 기업
                    "assigned_company",    # 매칭된 기업 (2지망)
                    "final_evaluation_score", 
                    "score_reason_summary"
                ]
                
                # 컬럼명 변경 (이해하기 쉽게)
                result_view = second_match_df[display_cols].rename(columns={
                    "preferred_company_1": "1지망 (탈락)",
                    "assigned_company": "배정기업 (2지망)",
                    "final_evaluation_score": "매칭점수"
                })
                
                st.dataframe(result_view, use_container_width=True)
                
                # 다운로드 버튼
                csv_2 = result_view.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 2지망 매칭 명단 다운로드", data=csv_2, file_name="second_choice_matches.csv")
            else:
                st.warning("2지망 기업에 매칭된 지원자가 없습니다.")
else:
    st.info("파일 업로드 후 배치를 실행해 주세요.")
