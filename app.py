import streamlit as st
import pandas as pd
import numpy as np
import io
import time

# --- 페이지 설정 ---
st.set_page_config(layout="wide", page_title="미청 매칭 관리 시스템")

# --- 1. 사이드바: 메뉴 ---
st.sidebar.title("🛠️ 운영 관리 메뉴")
menu = st.sidebar.radio("페이지 이동", [
    "1. 지원자 평가 점수표", 
    "2. 개인별 상세 리포트", 
    "3. 기업별 매칭 결과",
    "4. 2지망 매칭 현황 (구제자)",
    "5. 종합 매칭 현황판 (이미지 형식)"
])

# 가중치 설정 (기존과 동일)
st.sidebar.divider()
st.sidebar.header("⚖️ 가중치 설정")
w_first = st.sidebar.number_input("1순위 가산점", value=50)
w_second = st.sidebar.number_input("2순위 가산점", value=20)
w_req = st.sidebar.slider("필수 키워드 가중치", 0, 20, 10)
w_pref = st.sidebar.slider("우대 키워드 가중치", 0, 20, 5)
w_major = st.sidebar.slider("전공 적합도 가중치", 0, 20, 10)
w_exp = st.sidebar.slider("경력 점수 가중치", 0, 10, 3)
w_doc = st.sidebar.slider("문서 성실도 가중치", 0.0, 2.0, 1.0)
mult = st.sidebar.number_input("채용인원 배수 (N)", value=2)
plus = st.sidebar.number_input("추가 상수 (M)", value=1)

# --- 데이터 업로드 및 엔진 로직 ---
def calculate_scores(app, comp):
    app_text = f"{app['experience_keywords']} {app['tool_keywords']} {app['essay_full_text']}".lower()
    major_s = w_major if str(app['major']).strip() in str(comp['recruitment_job_groups']).strip() else 0
    req_match = sum(1 for k in [x.strip().lower() for x in str(comp['required_keywords_raw']).split(',') if x.strip()] if k in app_text)
    req_s = req_match * w_req
    pref_match = sum(1 for k in [x.strip().lower() for x in str(comp['preferred_keywords_raw']).split(',') if x.strip()] if k in app_text)
    pref_s = pref_match * w_pref
    exp_s = app['experience_count'] * w_exp + app['job_training_count'] * 2
    port_s = 15 if app['has_portfolio'] else 0
    doc_s = app['document_completeness_score'] * w_doc
    pref_b = w_first if app['preferred_company_1'] == comp['company_name'] else (w_second if app['preferred_company_2_3'] == comp['company_name'] else 0)
    total = major_s + req_s + pref_s + exp_s + port_s + doc_s + pref_b
    return {"final_evaluation_score": round(total, 2), "score_reason_summary": f"매칭점수 {total:.1f}"}

if app_file := st.file_uploader("지원자 데이터 업로드", type="csv"):
    if comp_file := st.file_uploader("기업 데이터 업로드", type="csv"):
        apps_df = pd.read_csv(app_file).fillna('')
        comps_df = pd.read_csv(comp_file).fillna('')
        apps_df['preferred_company_1'] = apps_df['preferred_company_1'].str.strip()
        apps_df['preferred_company_2_3'] = apps_df['preferred_company_2_3'].str.strip()
        comps_df['company_name'] = comps_df['company_name'].str.strip()
        comps_df['capacity'] = (comps_df['recruitment_headcount_total'] * mult + plus).astype(int)

        if st.button("🚀 배치 알고리즘 실행"):
            with st.spinner("계산 중..."):
                # [매칭 로직은 이전과 동일하게 수행하여 st.session_state['summary']에 저장]
                # (중략된 로직은 위쪽 코드와 동일하게 구현됨)
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
                for cid in comps_df['company_id']:
                    cap = comps_df[comps_df['company_id'] == cid]['capacity'].values[0]
                    p1_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 1)].sort_values('score', ascending=False)
                    for aid in p1_pool.head(cap)['applicant_id']: assigned[aid] = cid
                unassigned = set(apps_df['applicant_id']) - set(assigned.keys())
                for cid in comps_df['company_id']:
                    rem = comps_df[comps_df['company_id'] == cid]['capacity'].values[0] - sum(1 for v in assigned.values() if v == cid)
                    if rem > 0:
                        p2_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 2) & (score_df['applicant_id'].isin(unassigned))].sort_values('score', ascending=False)
                        for aid in p2_pool.head(rem)['applicant_id']: assigned[aid] = cid

                final_res = []
                for _, app in apps_df.iterrows():
                    aid = app['applicant_id']
                    target_cid = assigned.get(aid, None)
                    cname = comps_df[comps_df['company_id'] == target_cid]['company_name'].values[0] if target_cid else "미배정"
                    final_res.append({
                        "applicant_id": aid, "applicant_name": app['applicant_name'],
                        "preferred_company_1": app['preferred_company_1'], "assigned_company": cname
                    })
                st.session_state['summary'] = pd.DataFrame(final_res)
                st.session_state['comps'] = comps_df
                st.success("배치 완료!")

# --- 5. 페이지별 출력 ---
if 'summary' in st.session_state:
    df = st.session_state['summary']
    comps = st.session_state['comps']

    if menu == "5. 종합 매칭 현황판 (이미지 형식)":
        st.subheader("📊 종합 매칭 현황판")
        st.markdown("""
        <style>
        .main-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; }
        .main-table th, .main-table td { border: 1px solid #444; padding: 8px; }
        .header-1 { background-color: #f8f9fa; color: black; }
        .unassigned { color: red; font-weight: bold; cursor: help; position: relative; display: inline-block; }
        .assigned-else { color: #007bff; text-decoration: underline; cursor: help; position: relative; display: inline-block; }
        .tooltip .tooltiptext {
            visibility: hidden; width: 120px; background-color: #555; color: #fff; text-align: center;
            border-radius: 6px; padding: 5px; position: absolute; z-index: 1; bottom: 125%; left: 50%;
            margin-left: -60px; opacity: 0; transition: opacity 0.3s; font-size: 11px;
        }
        .tooltip:hover .tooltiptext { visibility: visible; opacity: 1; }
        </style>
        """, unsafe_allow_html=True)

        html = "<table class='main-table'>"
        html += """
        <tr class='header-1'>
            <th rowspan='2'>연번</th><th rowspan='2'>지원 사업장</th><th rowspan='2'>배치인원</th><th rowspan='2'>지원인원</th>
            <th colspan='5'>1차 배정인원</th><th colspan='5'>2차 배정인원</th><th colspan='5'>1차 지원 탈락인원</th>
        </tr>
        <tr class='header-1'>
            <th>1</th><th>2</th><th>3</th><th>4</th><th>5</th>
            <th>1</th><th>2</th><th>3</th><th>4</th><th>5</th>
            <th>1</th><th>2</th><th>3</th><th>4</th><th>5</th>
        </tr>
        """

        for i, (_, row) in enumerate(comps.iterrows(), 1):
            cname = row['company_name']
            cap = row['capacity']
            
            # 1. 1차 배정 (1지망 && 배정됨)
            p1_assigned = df[(df['assigned_company'] == cname) & (df['preferred_company_1'] == cname)]['applicant_id'].tolist()
            # 2. 2차 배정 (배정됨 && 1지망 아님)
            p2_assigned = df[(df['assigned_company'] == cname) & (df['preferred_company_1'] != cname)]['applicant_id'].tolist()
            # 3. 1차 탈락 (1지망이었으나 배정안됨)
            p1_failed = df[(df['preferred_company_1'] == cname) & (df['assigned_company'] != cname)]['applicant_id'].tolist()
            total_applied = len(df[df['preferred_company_1'] == cname])

            html += f"<tr><td>{i}</td><td>{cname}</td><td>{cap}</td><td>{total_applied}</td>"
            
            # 1차 배정 출력 (최대 5명)
            for j in range(5):
                val = p1_assigned[j] if j < len(p1_assigned) else ""
                html += f"<td>{val}</td>"
            # 2차 배정 출력 (최대 5명)
            for j in range(5):
                val = p2_assigned[j] if j < len(p2_assigned) else ""
                html += f"<td>{val}</td>"
            # 1차 탈락 출력 및 조건부 스타일 (최대 5명)
            for j in range(5):
                if j < len(p1_failed):
                    aid = p1_failed[j]
                    # 최종 배정지 확인
                    final_dest = df[df['applicant_id'] == aid]['assigned_company'].values[0]
                    if final_dest == "미배정":
                        html += f"<td><div class='tooltip unassigned'>{aid}<span class='tooltiptext'>현재 미배정 상태</span></div></td>"
                    else:
                        html += f"<td><div class='tooltip assigned-else'>{aid}<span class='tooltiptext'>배정지: {final_dest}</span></div></td>"
                else:
                    html += "<td></td>"
            html += "</tr>"
        
        html += "</table>"
        st.markdown(html, unsafe_allow_html=True)

    # [기타 메뉴 로직 생략 - 기존과 동일]
