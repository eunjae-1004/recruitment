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
    "5. 종합 매칭 현황판 (상세 지표)"
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
    # 텍스트 데이터가 없을 경우 빈 문자열 처리
    exp_key = str(app.get('experience_keywords', ''))
    tool_key = str(app.get('tool_keywords', ''))
    essay = str(app.get('essay_full_text', ''))
    app_text = f"{exp_key} {tool_key} {essay}".lower()
    
    major_s = w_major if str(app.get('major', '')).strip() in str(comp.get('recruitment_job_groups', '')).strip() else 0
    
    req_list = [k.strip().lower() for k in str(comp.get('required_keywords_raw', '')).split(',') if k.strip()]
    req_match = sum(1 for k in req_list if k in app_text)
    req_s = req_match * w_req
    
    pref_list = [k.strip().lower() for k in str(comp.get('preferred_keywords_raw', '')).split(',') if k.strip()]
    pref_match = sum(1 for k in pref_list if k in app_text)
    pref_s = pref_match * w_pref
    
    exp_count = float(app.get('experience_count', 0))
    train_count = float(app.get('job_training_count', 0))
    exp_s = exp_count * w_exp + train_count * 2
    
    port_s = 15 if app.get('has_portfolio', False) else 0
    doc_s = float(app.get('document_completeness_score', 0)) * w_doc
    
    # 지망 가산점 (안전한 키 접근)
    p1 = str(app.get('preferred_company_1', '')).strip()
    p2_3 = str(app.get('preferred_company_2_3', '')).strip()
    c_name = str(comp.get('company_name', '')).strip()
    
    pref_b = 0
    if p1 == c_name: pref_b = w_first
    elif p2_3 == c_name: pref_b = w_second
    
    total = major_s + req_s + pref_s + exp_s + port_s + doc_s + pref_b
    reason = f"필수 {req_match}개(+{req_s}), 경력 {int(exp_count)}건 반영, 문서성실도 {doc_s:.1f}점"
    
    return {
        "job_fit_score": major_s, "required_match_score": req_s, "preferred_match_score": pref_s,
        "experience_match_score": exp_s, "document_score": round(doc_s, 2), "preference_bonus_score": pref_b,
        "final_evaluation_score": round(total, 2), "score_reason_summary": reason
    }

# --- 데이터 업로드 및 배치 로직 ---
st.title("🎯 매칭 및 배치 통합 관리 시스템")
with st.expander("📂 데이터 파일 업로드 (CSV)", expanded=True):
    c1, c2 = st.columns(2)
    with c1: app_file = st.file_uploader("지원자 데이터 업로드", type="csv")
    with c2: comp_file = st.file_uploader("기업 데이터 업로드", type="csv")

if app_file and comp_file:
    # 컬럼명 앞뒤 공백 자동 제거하여 로드
    apps_df = pd.read_csv(app_file).fillna('')
    apps_df.columns = [c.strip() for c in apps_df.columns]
    comps_df = pd.read_csv(comp_file).fillna('')
    comps_df.columns = [c.strip() for c in comps_df.columns]
    
    # 필수 기업명 공백 제거
    apps_df['preferred_company_1'] = apps_df['preferred_company_1'].astype(str).str.strip()
    if 'preferred_company_2_3' in apps_df.columns:
        apps_df['preferred_company_2_3'] = apps_df['preferred_company_2_3'].astype(str).str.strip()
    comps_df['company_name'] = comps_df['company_name'].astype(str).str.strip()
    comps_df['capacity'] = (comps_df['recruitment_headcount_total'].astype(float) * mult + plus).astype(int)

    if st.button("🚀 배치 알고리즘 실행"):
        with st.spinner("계산 및 배치 중..."):
            score_matrix = []
            for _, app in apps_df.iterrows():
                for _, comp in comps_df.iterrows():
                    res = calculate_scores(app, comp)
                    score_matrix.append({
                        "applicant_id": app['applicant_id'], "applicant_name": app['applicant_name'],
                        "company_id": comp['company_id'], "company_name": comp['company_name'],
                        "score": res['final_evaluation_score'], 
                        "pref_level": 1 if app['preferred_company_1'] == comp['company_name'] else (2 if app.get('preferred_company_2_3', '') == comp['company_name'] else 0)
                    })
            score_df = pd.DataFrame(score_matrix)
            assigned = {}
            for cid in comps_df['company_id']:
                cap = comps_df[comps_df['company_id'] == cid]['capacity'].values[0]
                p1 = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 1)].sort_values('score', ascending=False)
                for aid in p1.head(cap)['applicant_id']: assigned[aid] = cid
            unassigned = set(apps_df['applicant_id']) - set(assigned.keys())
            for cid in comps_df['company_id']:
                rem = comps_df[comps_df['company_id'] == cid]['capacity'].values[0] - sum(1 for v in assigned.values() if v == cid)
                if rem > 0:
                    p2 = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 2) & (score_df['applicant_id'].isin(unassigned))].sort_values('score', ascending=False)
                    for aid in p2.head(rem)['applicant_id']: assigned[aid] = cid

            final_summary = []
            for _, app in apps_df.iterrows():
                aid = app['applicant_id']
                t_cid = assigned.get(aid, None)
                if t_cid:
                    c_row = comps_df[comps_df['company_id'] == t_cid].iloc[0]
                    assigned_cname = c_row['company_name']
                else:
                    assigned_cname = "미배정"
                    c1_q = comps_df[comps_df['company_name'] == app['preferred_company_1']]
                    c_row = c1_q.iloc[0] if not c1_q.empty else comps_df.iloc[0]
                
                eval_data = calculate_scores(app, c_row)
                final_summary.append({
                    "applicant_id": aid, 
                    "applicant_name": app['applicant_name'],
                    "preferred_company_1": app['preferred_company_1'], 
                    "preferred_company_2_3": app.get('preferred_company_2_3', '정보없음'),
                    "assigned_company": assigned_cname, 
                    **eval_data
                })
            st.session_state['summary'] = pd.DataFrame(final_summary)
            st.session_state['comps'] = comps_df
            st.success("배치 완료!")

# --- 페이지별 출력 로직 ---
if 'summary' in st.session_state:
    df = st.session_state['summary']
    comps = st.session_state['comps']

    if menu == "1. 지원자 평가 점수표":
        st.subheader("📑 지원자 세부 평가 및 지망 정보")
        v_cols = ["applicant_id", "applicant_name", "preferred_company_1", "preferred_company_2_3", "assigned_company", "final_evaluation_score", "job_fit_score", "required_match_score", "experience_match_score", "document_score"]
        st.dataframe(df[[c for c in v_cols if c in df.columns]], use_container_width=True)

    elif menu == "2. 개인별 상세 리포트":
        st.subheader("👤 개인별 상세 리포트")
        # 지원자 리스트 생성
        aid_list = df['applicant_id'].tolist()
        sel_aid = st.selectbox("지원자 선택", aid_list, format_func=lambda x: f"{x} ({df[df['applicant_id']==x]['applicant_name'].values[0]})")
        
        # 선택된 지원자 데이터 추출
        row = df[df['applicant_id'] == sel_aid].iloc[0]
        
        c_l, c_r = st.columns(2)
        with c_l:
            # 안전하게 데이터 가져오기
            p1 = row.get('preferred_company_1', '정보없음')
            p2 = row.get('preferred_company_2_3', '정보없음')
            a_c = row.get('assigned_company', '미배정')
            name = row.get('applicant_name', '이름없음')
            score = row.get('final_evaluation_score', 0)
            reason = row.get('score_reason_summary', '근거 없음')
            
            st.info(f"### {name}\n**1지망**: {p1}\n**2지망**: {p2}\n**최종 배정**: {a_c}")
            st.metric("종합 점수", f"{score}점")
            st.success(f"**산출 근거**: {reason}")
            
        with c_r:
            st.bar_chart(pd.Series({
                "직무": row.get('job_fit_score', 0), 
                "필수": row.get('required_match_score', 0), 
                "경력": row.get('experience_match_score', 0), 
                "문서": row.get('document_score', 0), 
                "가점": row.get('preference_bonus_score', 0)
            }))

    elif menu == "3. 기업별 매칭 결과":
        st.subheader("🏢 기업별 배정 현황")
        for _, c in comps.iterrows():
            with st.expander(f"{c['company_name']} (정원: {c['capacity']})"):
                c_res = df[df['assigned_company'] == c['company_name']]
                if not c_res.empty: st.table(c_res[["applicant_id", "applicant_name", "final_evaluation_score", "score_reason_summary"]])
                else: st.write("배정 인원 없음")

    elif menu == "4. 2지망 매칭 현황 (구제자)":
        st.subheader("🔄 2지망 매칭 현황")
        # 컬럼 존재 여부 확인 후 필터링
        if 'preferred_company_2_3' in df.columns:
            second_df = df[(df['assigned_company'] == df['preferred_company_2_3']) & (df['assigned_company'] != df['preferred_company_1']) & (df['assigned_company'] != "미배정")]
            st.dataframe(second_df[["applicant_id", "applicant_name", "preferred_company_1", "assigned_company", "final_evaluation_score"]], use_container_width=True)
        else:
            st.error("2지망 기업 정보가 없습니다.")

    elif menu == "5. 종합 매칭 현황판 (상세 지표)":
        st.subheader("📊 종합 매칭 현황판")
        # 가변 칸수 계산을 위해 안전한 필터링
        p1_data = {c: df[(df['assigned_company'] == c) & (df['preferred_company_1'] == c)]['applicant_id'].tolist() for c in comps['company_name']}
        p2_data = {c: df[(df['assigned_company'] == c) & (df.get('preferred_company_2_3', '') == c) & (df['assigned_company'] != df['preferred_company_1'])]['applicant_id'].tolist() for c in comps['company_name']}
        pf_data = {c: df[(df['preferred_company_1'] == c) & (df['assigned_company'] != c)]['applicant_id'].tolist() for c in comps['company_name']}
        
        max_p1 = max([len(v) for v in p1_data.values()] + [1])
        max_p2 = max([len(v) for v in p2_data.values()] + [1])
        max_pf = max([len(v) for v in pf_data.values()] + [1])

        st.markdown(f"<style>.m-table {{ width: 100%; border-collapse: collapse; font-size: 11px; text-align: center; }} .m-table th, .m-table td {{ border: 1px solid #ddd; padding: 6px; }} .bg-gray {{ background-color: #f2f2f2; font-weight: bold; color: black; }} .deficit-red {{ color: red; font-weight: bold; }} .red-text {{ color: red; font-weight: bold; cursor: help; }} .blue-text {{ color: blue; text-decoration: underline; cursor: help; }} .tooltip {{ position: relative; display: inline-block; }} .tooltip .tooltiptext {{ visibility: hidden; width: 140px; background-color: black; color: #fff; text-align: center; border-radius: 6px; padding: 5px; position: absolute; z-index: 1; bottom: 125%; left: 50%; margin-left: -70px; opacity: 0; transition: opacity 0.3s; }} .tooltip:hover .tooltiptext {{ visibility: visible; opacity: 1; }} </style>", unsafe_allow_html=True)
        html = f"<table class='m-table'><tr class='bg-gray'><th rowspan='2'>연번</th><th rowspan='2'>지원 사업장</th><th rowspan='2'>채용인원</th><th rowspan='2'>지원인원</th><th rowspan='2'>배수정원</th><th rowspan='2'>배정인원</th><th rowspan='2'>부족인원</th><th colspan='{max_p1}'>1차 배정</th><th colspan='{max_p2}'>2차 배정</th><th colspan='{max_pf}'>1차 탈락</th></tr><tr class='bg-gray'>"
        for _ in range(max_p1 + max_p2 + max_pf): html += "<th></th>"
        html += "</tr>"
        for i, (_, row) in enumerate(comps.iterrows(), 1):
            c = row['company_name']
            p1, p2, pf = p1_data[c], p2_data[c], pf_data[c]
            assigned_cnt = len(p1) + len(p2)
            deficit = row['recruitment_headcount_total'] - assigned_cnt
            def_style = "class='deficit-red'" if deficit > 0 else ""
            html += f"<tr><td>{i}</td><td>{c}</td><td>{row['recruitment_headcount_total']}</td><td>{len(df[df['preferred_company_1'] == c])}</td><td>{row['capacity']}</td><td>{assigned_cnt}</td><td {def_style}>{deficit}</td>"
            for j in range(max_p1): html += f"<td>{p1[j] if j < len(p1) else ''}</td>"
            for j in range(max_p2): html += f"<td>{p2[j] if j < len(p2) else ''}</td>"
            for j in range(max_pf):
                if j < len(pf):
                    aid = pf[j]
                    target_row = df[df['applicant_id'] == aid]
                    dest = target_row['assigned_company'].values[0] if not target_row.empty else "미배정"
                    if dest == "미배정": html += f"<td><div class='tooltip red-text'>{aid}<span class='tooltiptext'>미배정</span></div></td>"
                    else: html += f"<td><div class='tooltip blue-text'>{aid}<span class='tooltiptext'>배정지: {dest}</span></div></td>"
                else: html += "<td></td>"
            html += "</tr>"
        st.markdown(html + "</table>", unsafe_allow_html=True)
