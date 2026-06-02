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
    "5. 종합 매칭 현황판 (상세 분석 및 수동배치)"
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
mult = st.sidebar.number_input("채용인원 배수 (N)", value=2)
plus = st.sidebar.number_input("추가 상수 (M)", value=1)

# --- 점수 계산 함수 ---
def calculate_scores(app, comp):
    app_text = f"{app.get('experience_keywords', '')} {app.get('tool_keywords', '')} {app.get('essay_full_text', '')}".lower()
    major_s = w_major if str(app.get('major', '')).strip() in str(comp.get('recruitment_job_groups', '')).strip() else 0
    req_list = [k.strip().lower() for k in str(comp.get('required_keywords_raw', '')).split(',') if k.strip()]
    req_match = sum(1 for k in req_list if k in app_text)
    req_s = req_match * w_req
    pref_list = [k.strip().lower() for k in str(comp.get('preferred_keywords_raw', '')).split(',') if k.strip()]
    pref_match = sum(1 for k in pref_list if k in app_text)
    pref_s = pref_match * w_pref
    exp_s = float(app.get('experience_count', 0)) * w_exp + float(app.get('job_training_count', 0)) * 2
    port_s = 15 if app.get('has_portfolio', False) else 0
    doc_s = float(app.get('document_completeness_score', 0)) * w_doc
    p1, p2_3, c_name = str(app.get('preferred_company_1', '')).strip(), str(app.get('preferred_company_2_3', '')).strip(), str(comp.get('company_name', '')).strip()
    pref_b = w_first if p1 == c_name else (w_second if p2_3 == c_name else 0)
    total = major_s + req_s + pref_s + exp_s + port_s + doc_s + pref_b
    return {"final_score": round(total, 2), "reason": f"필수 {req_match}개(+{req_s}), 매칭 {total:.1f}점"}

# --- 2. 데이터 업로드 및 초기화 ---
st.title("🎯 매칭 및 배치 통합 관리 시스템")
with st.expander("📂 데이터 파일 업로드 (CSV)", expanded=True):
    c1, c2 = st.columns(2)
    with c1: app_file = st.file_uploader("지원자 데이터 업로드", type="csv")
    with c2: comp_file = st.file_uploader("기업 데이터 업로드", type="csv")

if app_file and comp_file:
    if 'apps_df' not in st.session_state:
        apps = pd.read_csv(app_file).fillna('')
        apps.columns = [c.strip() for c in apps.columns]
        st.session_state['apps_df'] = apps
    if 'comps_df' not in st.session_state:
        comps = pd.read_csv(comp_file).fillna('')
        comps.columns = [c.strip() for c in comps.columns]
        comps['capacity'] = (comps['recruitment_headcount_total'].astype(float) * mult + plus).astype(int)
        st.session_state['comps_df'] = comps

    apps_df = st.session_state['apps_df']
    comps_df = st.session_state['comps_df']

    # --- 3. 배치 알고리즘 실행 버튼 ---
    if st.button("🚀 배치 알고리즘 실행"):
        with st.spinner("점수 계산 및 자동 배치 중..."):
            score_matrix = []
            for _, app in apps_df.iterrows():
                for _, comp in comps_df.iterrows():
                    res = calculate_scores(app, comp)
                    score_matrix.append({
                        "applicant_id": app['applicant_id'], "applicant_name": app['applicant_name'],
                        "company_id": comp['company_id'], "company_name": comp['company_name'].strip(),
                        "score": res['final_score'], "reason": res['reason'], 
                        "field": app.get('application_field', '기타'),
                        "pref_level": 1 if str(app['preferred_company_1']).strip() == str(comp['company_name']).strip() else (2 if str(app.get('preferred_company_2_3', '')).strip() == str(comp['company_name']).strip() else 0)
                    })
            st.session_state['score_df'] = pd.DataFrame(score_matrix)
            
            assigned = {}
            score_df = st.session_state['score_df']
            for cid in comps_df['company_id']:
                cap = comps_df[comps_df['company_id'] == cid]['capacity'].values[0]
                p1_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 1)].sort_values('score', ascending=False)
                for aid in p1_pool.head(cap)['applicant_id']: assigned[aid] = cid
            unassigned_ids = set(apps_df['applicant_id']) - set(assigned.keys())
            for cid in comps_df['company_id']:
                rem = comps_df[comps_df['company_id'] == cid]['capacity'].values[0] - sum(1 for v in assigned.values() if v == cid)
                if rem > 0:
                    p2_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 2) & (score_df['applicant_id'].isin(unassigned_ids))].sort_values('score', ascending=False)
                    for aid in p2_pool.head(rem)['applicant_id']: assigned[aid] = cid
            st.session_state['assignments'] = assigned
            st.success("자동 배치가 완료되었습니다.")

# --- 4. 메뉴별 통합 데이터 가공 ---
if 'assignments' in st.session_state:
    assigned = st.session_state['assignments']
    comps_df = st.session_state['comps_df']
    apps_df = st.session_state['apps_df']
    score_df = st.session_state['score_df']

    final_rows = []
    for _, app in apps_df.iterrows():
        aid = app['applicant_id']
        t_cid = assigned.get(aid, None)
        cname = comps_df[comps_df['company_id'] == t_cid]['company_name'].values[0] if t_cid else "미배정"
        p1_cname = str(app['preferred_company_1']).strip()
        s_info = score_df[(score_df['applicant_id'] == aid) & (score_df['company_name'] == p1_cname)]
        
        final_rows.append({
            "applicant_id": aid, "applicant_name": app['applicant_name'], "field": app.get('application_field', '기타'),
            "preferred_company_1": p1_cname, "preferred_company_2_3": str(app.get('preferred_company_2_3', '')).strip(),
            "assigned_company": cname, 
            "final_score": s_info['score'].values[0] if not s_info.empty else 0,
            "score_reason_summary": s_info['reason'].values[0] if not s_info.empty else "기본점수"
        })
    df_res = pd.DataFrame(final_rows)

    # --- 5. 페이지별 출력 ---
    if menu == "1. 지원자 평가 점수표":
        st.subheader("📑 지원자 세부 평가 점수표")
        st.dataframe(df_res, use_container_width=True)

    elif menu == "2. 개인별 상세 리포트":
        st.subheader("👤 개인별 상세 리포트")
        sel_aid = st.selectbox("지원자 선택", df_res['applicant_id'].tolist(), format_func=lambda x: f"{x} ({df_res[df_res['applicant_id']==x]['applicant_name'].values[0]})")
        row = df_res[df_res['applicant_id'] == sel_aid].iloc[0]
        st.info(f"### {row['applicant_name']}\n**최종 배정**: {row['assigned_company']}\n**점수**: {row['final_score']}점\n**근거**: {row['score_reason_summary']}")

    elif menu == "3. 기업별 매칭 결과":
        st.subheader("🏢 기업별 배정 현황")
        for _, c in comps_df.iterrows():
            with st.expander(f"{c['company_name']} (정원: {c['capacity']})"):
                c_res = df_res[df_res['assigned_company'] == c['company_name']]
                if not c_res.empty: st.table(c_res[["applicant_id", "applicant_name", "final_score", "score_reason_summary"]])
                else: st.write("배정 인원 없음")

    elif menu == "4. 2지망 매칭 현황 (구제자)":
        st.subheader("🔄 2지망 매칭 현황")
        guje_df = df_res[(df_res['assigned_company'] == df_res['preferred_company_2_3']) & (df_res['assigned_company'] != df_res['preferred_company_1'])]
        st.dataframe(guje_df, use_container_width=True)

    elif menu == "5. 종합 매칭 현황판 (상세 분석 및 수동배치)":
        st.subheader("📊 종합 매칭 현황판")
        p1_data, p2_data, pf_data = {}, {}, {}
        for c in comps_df['company_name']:
            c = c.strip()
            p1_data[c] = df_res[(df_res['assigned_company'] == c) & (df_res['preferred_company_1'] == c)]['applicant_id'].tolist()
            p2_data[c] = df_res[(df_res['assigned_company'] == c) & (df_res['preferred_company_1'] != c) & (df_res['assigned_company'] != "미배정")]['applicant_id'].tolist()
            # 1차 탈락자 점수순 정렬
            pf_df = df_res[(df_res['preferred_company_1'] == c) & (df_res['assigned_company'] != c)]
            pf_data[c] = pf_df.sort_values('final_score', ascending=False)['applicant_id'].tolist()
        
        max_p1, max_p2, max_pf = max([len(v) for v in p1_data.values()] + [1]), max([len(v) for v in p2_data.values()] + [1]), max([len(v) for v in pf_data.values()] + [1])

        st.markdown(f"<style>.m-table {{ width: 100%; border-collapse: collapse; font-size: 11px; text-align: center; }} .m-table th, .m-table td {{ border: 1px solid #ddd; padding: 6px; }} .bg-gray {{ background-color: #f2f2f2; font-weight: bold; color: black; }} .deficit-red {{ color: red; font-weight: bold; }} .red-text {{ color: red; font-weight: bold; cursor: help; }} .blue-text {{ color: blue; text-decoration: underline; cursor: help; }} .tooltip {{ position: relative; display: inline-block; }} .tooltip .tooltiptext {{ visibility: hidden; width: 180px; background-color: #333; color: #fff; text-align: center; border-radius: 6px; padding: 8px; position: absolute; z-index: 99; bottom: 125%; left: 50%; margin-left: -90px; opacity: 0; transition: opacity 0.3s; font-size: 10px; }} .tooltip:hover .tooltiptext {{ visibility: visible; opacity: 1; }} </style>", unsafe_allow_html=True)
        
        # [수정] 지원 분야(요약) 컬럼에 recruitment_summary 값 매핑
        html = f"<table class='m-table'><tr class='bg-gray'><th rowspan='2'>연번</th><th rowspan='2'>지원 사업장</th><th rowspan='2'>지원 분야 (요약)</th><th rowspan='2'>채용</th><th rowspan='2'>지원</th><th rowspan='2'>배수</th><th rowspan='2'>배정</th><th rowspan='2'>부족</th><th colspan='{max_p1}'>1차 배정</th><th colspan='{max_p2}'>2차 배정</th><th colspan='{max_pf}'>1차 탈락 (점수순)</th></tr><tr class='bg-gray'>"
        for _ in range(max_p1 + max_p2 + max_pf): html += "<th></th>"
        html += "</tr>"
        
        for i, (_, row) in enumerate(comps_df.iterrows(), 1):
            c = row['company_name'].strip()
            p1, p2, pf = p1_data[c], p2_data[c], pf_data[c]
            assigned_cnt = len(p1) + len(p2)
            deficit = row['recruitment_headcount_total'] - assigned_cnt
            
            # row.get('recruitment_summary')를 사용하여 출력
            html += f"<tr><td>{i}</td><td>{c}</td><td>{row.get('recruitment_summary', '정보없음')}</td><td>{row['recruitment_headcount_total']}</td><td>{len(df_res[df_res['preferred_company_1'] == c])}</td><td>{row['capacity']}</td><td>{assigned_cnt}</td><td class='{'deficit-red' if deficit > 0 else ''}'>{deficit}</td>"
            for j in range(max_p1): html += f"<td>{p1[j] if j < len(p1) else ''}</td>"
            for j in range(max_p2): html += f"<td>{p2[j] if j < len(p2) else ''}</td>"
            for j in range(max_pf):
                if j < len(pf):
                    aid = pf[j]
                    a_info = df_res[df_res['applicant_id'] == aid].iloc[0]
                    dest, msg = a_info['assigned_company'], f"직무: {a_info['field']}<br>점수: {a_info['final_score']}점"
                    if dest == "미배정": html += f"<td><div class='tooltip red-text'>{aid}<span class='tooltiptext'>{msg}<br>(미배정)</span></div></td>"
                    else: html += f"<td><div class='tooltip blue-text'>{aid}<span class='tooltiptext'>{msg}<br>(배정: {dest})</span></div></td>"
                else: html += "<td></td>"
            html += "</tr>"
        st.markdown(html + "</table>", unsafe_allow_html=True)

        # 수동 배치 기능
        st.divider()
        st.subheader("🛠️ 미배정 인원 수동 배치")
        unassigned_list = df_res[df_res['assigned_company'] == "미배정"]['applicant_id'].tolist()
        if unassigned_list:
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1: s_aid = st.selectbox("수동 배치 지원자 번호", unassigned_list)
            with c2: s_comp = st.selectbox("배치할 타겟 기업", comps_df['company_name'].tolist())
            with c3:
                if st.button("수동 배정 확정"):
                    st.session_state['assignments'][s_aid] = comps_df[comps_df['company_name'] == s_comp]['company_id'].values[0]
                    st.rerun()
else:
    st.info("CSV 파일을 업로드한 후 배치를 실행해 주세요.")
