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
    "5. 종합 매칭 현황판 (가변 칸수 적용)"
])

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

# --- 점수 계산 함수 ---
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
    pref_b = w_first if app['preferred_company_1'] == comp['company_name'] else (w_second if app['preferred_company_2_3'] == comp['company_name'] else 0)
    total = major_s + req_s + pref_s + exp_s + port_s + doc_s + pref_b
    return {"score": round(total, 2), "reason": f"매칭점수 {total:.1f}"}

# --- 데이터 업로드 및 배치 로직 ---
if app_file := st.file_uploader("지원자 데이터 업로드", type="csv"):
    if comp_file := st.file_uploader("기업 데이터 업로드", type="csv"):
        apps_df = pd.read_csv(app_file).fillna('')
        comps_df = pd.read_csv(comp_file).fillna('')
        apps_df['preferred_company_1'] = apps_df['preferred_company_1'].str.strip()
        apps_df['preferred_company_2_3'] = apps_df['preferred_company_2_3'].str.strip()
        comps_df['company_name'] = comps_df['company_name'].str.strip()
        # 내부 계산용 정원(Capacity)
        comps_df['capacity'] = (comps_df['recruitment_headcount_total'] * mult + plus).astype(int)

        if st.button("🚀 배치 알고리즘 실행"):
            with st.spinner("계산 및 배치 중..."):
                score_matrix = []
                for _, app in apps_df.iterrows():
                    for _, comp in comps_df.iterrows():
                        res = calculate_scores(app, comp)
                        score_matrix.append({
                            "applicant_id": app['applicant_id'], "applicant_name": app['applicant_name'],
                            "company_id": comp['company_id'], "company_name": comp['company_name'],
                            "score": res['score'], "reason": res['reason'],
                            "pref_level": 1 if app['preferred_company_1'] == comp['company_name'] else (2 if app['preferred_company_2_3'] == comp['company_name'] else 0)
                        })
                score_df = pd.DataFrame(score_matrix)
                
                assigned = {}
                # Pass 1: 1순위
                for cid in comps_df['company_id']:
                    cap = comps_df[comps_df['company_id'] == cid]['capacity'].values[0]
                    p1_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 1)].sort_values('score', ascending=False)
                    for aid in p1_pool.head(cap)['applicant_id']: assigned[aid] = cid
                # Pass 2: 2순위 구제
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
                        "preferred_company_1": app['preferred_company_1'].strip(),
                        "preferred_company_2_3": app['preferred_company_2_3'].strip(),
                        "assigned_company": cname
                    })
                st.session_state['summary'] = pd.DataFrame(final_res)
                st.session_state['comps'] = comps_df
                st.success("배치가 완료되었습니다!")

# --- 페이지 출력부 ---
if 'summary' in st.session_state:
    df = st.session_state['summary']
    comps = st.session_state['comps']

    if menu == "5. 종합 매칭 현황판 (가변 칸수 적용)":
        st.subheader("📊 종합 매칭 현황판")
        
        # 가변 칸수 계산을 위해 최대값 산출
        p1_data = {c: df[(df['assigned_company'] == c) & (df['preferred_company_1'] == c)]['applicant_id'].tolist() for c in comps['company_name']}
        p2_data = {c: df[(df['assigned_company'] == c) & (df['preferred_company_1'] != c) & (df['assigned_company'] != "미배정")]['applicant_id'].tolist() for c in comps['company_name']}
        pf_data = {c: df[(df['preferred_company_1'] == c) & (df['assigned_company'] != c)]['applicant_id'].tolist() for c in comps['company_name']}
        
        max_p1 = max([len(v) for v in p1_data.values()] + [1])
        max_p2 = max([len(v) for v in p2_data.values()] + [1])
        max_pf = max([len(v) for v in pf_data.values()] + [1])

        st.markdown(f"""
        <style>
        .m-table {{ width: 100%; border-collapse: collapse; font-size: 11px; text-align: center; }}
        .m-table th, .m-table td {{ border: 1px solid #ddd; padding: 4px; }}
        .bg-gray {{ background-color: #f2f2f2; font-weight: bold; color: black; }}
        .red-text {{ color: red; font-weight: bold; cursor: help; }}
        .blue-text {{ color: blue; text-decoration: underline; cursor: help; }}
        .tooltip {{ position: relative; display: inline-block; }}
        .tooltip .tooltiptext {{ visibility: hidden; width: 140px; background-color: black; color: #fff; text-align: center; border-radius: 6px; padding: 5px; position: absolute; z-index: 1; bottom: 125%; left: 50%; margin-left: -70px; opacity: 0; transition: opacity 0.3s; }}
        .tooltip:hover .tooltiptext {{ visibility: visible; opacity: 1; }}
        </style>
        """, unsafe_allow_html=True)

        html = f"<table class='m-table'>"
        html += f"""
        <tr class='bg-gray'>
            <th rowspan='2'>연번</th><th rowspan='2'>지원 사업장</th><th rowspan='2'>배치인원</th><th rowspan='2'>지원인원</th>
            <th colspan='{max_p1}'>1차 배정인원</th><th colspan='{max_p2}'>2차 배정인원</th><th colspan='{max_pf}'>1차 지원 탈락인원</th>
        </tr>
        <tr class='bg-gray'>
        """
        for _ in range(max_p1): html += "<th></th>"
        for _ in range(max_p2): html += "<th></th>"
        for _ in range(max_pf): html += "<th></th>"
        html += "</tr>"

        for i, (_, row) in enumerate(comps.iterrows(), 1):
            c = row['company_name']
            total_applied = len(df[df['preferred_company_1'] == c])
            
            html += f"<tr><td>{i}</td><td>{c}</td><td>{row['recruitment_headcount_total']}</td><td>{total_applied}</td>"
            
            # 1차 배정인원
            p1_list = p1_data[c]
            for j in range(max_p1):
                html += f"<td>{p1_list[j] if j < len(p1_list) else ''}</td>"
            
            # 2차 배정인원
            p2_list = p2_data[c]
            for j in range(max_p2):
                html += f"<td>{p2_list[j] if j < len(p2_list) else ''}</td>"
            
            # 1차 지원 탈락인원 (로직 및 스타일 적용)
            pf_list = pf_data[c]
            for j in range(max_pf):
                if j < len(pf_list):
                    aid = pf_list[j]
                    dest = df[df['applicant_id'] == aid]['assigned_company'].values[0]
                    if dest == "미배정":
                        html += f"<td><div class='tooltip red-text'>{aid}<span class='tooltiptext'>현재 미배정 상태</span></div></td>"
                    else:
                        html += f"<td><div class='tooltip blue-text'>{aid}<span class='tooltiptext'>배정지: {dest}</span></div></td>"
                else:
                    html += "<td></td>"
            html += "</tr>"
        
        html += "</table>"
        st.markdown(html, unsafe_allow_html=True)

    # --- 나머지 페이지 (기존 유지) ---
    elif menu == "1. 지원자 평가 점수표":
        st.subheader("📑 지원자 세부 평가 및 지망 정보")
        v_cols = ["applicant_id", "applicant_name", "preferred_company_1", "preferred_company_2_3", "assigned_company", "score", "reason"]
        st.dataframe(df.rename(columns={"assigned_company": "최종배정기업"}), use_container_width=True)
    # [2, 3, 4 페이지 생략 - 이전과 동일]
