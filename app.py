import streamlit as st
import pandas as pd
import numpy as np
import io
import time
import re

# --- 페이지 및 내부 고정 설정 ---
st.set_page_config(layout="wide", page_title="매칭 관리 시스템")
FIXED_MULT = 2  # 채용인원 배수
FIXED_PLUS = 1  # 추가 상수
W_BONUS = 50.0  # 1지망, 2지망 공통 가산점

# --- 데이터 정제 함수 ---
def clean_job_summary(text):
    if not text: return ""
    patterns = re.findall(r'([가-힣\w\s/]+?\s*\d+\s*명)', str(text))
    if patterns: return ", ".join([p.strip() for p in patterns])
    return str(text)[:30]

# --- 점수 계산 엔진 (평균 70점 이상 유도형) ---
def calculate_scores(app, comp):
    app_text = f"{app.get('experience_keywords', '')} {app.get('tool_keywords', '')} {app.get('essay_full_text', '')}".lower()
    
    # 1. 지망 가산점 (1지망, 2지망 동일하게 50점 부여)
    p1 = str(app.get('preferred_company_1', '')).strip()
    p2_3 = str(app.get('preferred_company_2_3', '')).strip()
    c_name = str(comp.get('company_name', '')).strip()
    
    pref_b = 50
#    if p1 == c_name or p2_3 == c_name:
#        pref_b = W_BONUS
    
    # 2. 역량 항목 점수
    major_s = 10.0 if str(app.get('major', '')).strip() in str(comp.get('recruitment_job_groups', '')).strip() else 5.0
    req_list = [k.strip().lower() for k in str(comp.get('required_keywords_raw', '')).split(',') if k.strip()]
    req_match = sum(1 for k in req_list if k in app_text)
    req_s = req_match * 5.0
    
    exp_count = float(app.get('experience_count', 0))
    exp_s = exp_count * 3.0 + float(app.get('job_training_count', 0)) * 2.0
    doc_s = float(app.get('document_completeness_score', 0)) * 0.8
    
    total = major_s + req_s + exp_s + doc_s + pref_b
    
    # 전체 평균 70점 이상 보정
    if total < 65: total += (70 - total) * 0.5 + 10
    
    return {
        "job_fit_score": major_s, "required_match_score": req_s,
        "experience_match_score": exp_s, "document_score": round(doc_s, 2), "preference_bonus_score": pref_b,
        "final_evaluation_score": round(total, 1), 
        "score_reason_summary": f"점수 {total:.1f} (가점 {pref_b} 포함)"
    }

# --- 1. 사이드바 메뉴 ---
st.sidebar.title("🛠️ 운영 메뉴")
menu = st.sidebar.radio("페이지 이동", [
    "1. 지원자 평가 점수표", 
    "2. 개인별 상세 리포트", 
    "3. 기업별 매칭 결과",
    "4. 2지망 매칭 현황 (구제자)",
    "5. 종합 매칭 현황판"
])

# --- 2. 데이터 업로드 ---
st.title("🤝 매칭 및 배치 관리 시스템")
with st.expander("📂 데이터 업로드", expanded=True):
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        app_file = st.file_uploader("지원자 데이터", type="csv")
        comp_file = st.file_uploader("기업 데이터", type="csv")
    with col_u2:
        history_file = st.file_uploader("기존 결과 불러오기", type="csv")

if app_file and comp_file:
    if 'apps_df' not in st.session_state:
        apps = pd.read_csv(app_file).fillna('')
        apps.columns = [c.strip() for c in apps.columns]
        apps['preferred_company_1'] = apps['preferred_company_1'].astype(str).str.strip()
        apps['preferred_company_2_3'] = apps['preferred_company_2_3'].astype(str).str.strip()
        st.session_state['apps_df'] = apps
    if 'comps_df' not in st.session_state:
        comps = pd.read_csv(comp_file).fillna('')
        comps.columns = [c.strip() for c in comps.columns]
        comps['company_name'] = comps['company_name'].astype(str).str.strip()
        comps['capacity'] = (comps['recruitment_headcount_total'].astype(float) * FIXED_MULT + FIXED_PLUS).astype(int)
        st.session_state['comps_df'] = comps

apps_df = st.session_state.get('apps_df')
comps_df = st.session_state.get('comps_df')

if apps_df is not None and comps_df is not None:
    if st.button("🚀 자동 배치 실행"):
        with st.spinner("알고리즘 계산 중..."):
            score_matrix = []
            for _, app in apps_df.iterrows():
                for _, comp in comps_df.iterrows():
                    res = calculate_scores(app, comp)
                    score_matrix.append({
                        "applicant_id": app['applicant_id'], "applicant_name": app['applicant_name'],
                        "company_id": comp['company_id'], "company_name": comp['company_name'],
                        "score": res['final_evaluation_score'], 
                        "pref_level": 1 if app['preferred_company_1'] == comp['company_name'] else (2 if app['preferred_company_2_3'] == comp['company_name'] else 0)
                    })
            score_df = pd.DataFrame(score_matrix)
            st.session_state['score_df'] = score_df
            
            assigned = {}
            # --- 우선순위 배치 로직 ---
            # Pass 1: 해당 기업을 '1지망'으로 쓴 사람들을 먼저 배정
            for cid in comps_df['company_id']:
                cap = comps_df[comps_df['company_id'] == cid]['capacity'].values[0]
                p1_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 1)].sort_values('score', ascending=False)
                for aid in p1_pool.head(cap)['applicant_id']: assigned[aid] = cid
            
            # Pass 2: 자리가 남은 기업에 대해 '2지망' 지원자들을 배정
            unassigned_ids = set(apps_df['applicant_id']) - set(assigned.keys())
            for cid in comps_df['company_id']:
                filled = sum(1 for v in assigned.values() if v == cid)
                rem = comps_df[comps_df['company_id'] == cid]['capacity'].values[0] - filled
                if rem > 0:
                    p2_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 2) & (score_df['applicant_id'].isin(unassigned_ids))].sort_values('score', ascending=False)
                    for aid in p2_pool.head(rem)['applicant_id']: assigned[aid] = cid
            
            st.session_state['assignments'] = assigned
            
            final_rows = []
            for _, app in apps_df.iterrows():
                aid = app['applicant_id']
                t_cid = assigned.get(aid, None)
                cname = comps_df[comps_df['company_id'] == t_cid]['company_name'].values[0] if t_cid else "미배정"
                # 표시용 점수는 배정된 곳 기준, 미배정 시 1지망 기준
                eval_target = cname if cname != "미배정" else app['preferred_company_1']
                target_comp_row = comps_df[comps_df['company_name'] == eval_target]
                eval_data = calculate_scores(app, target_comp_row.iloc[0] if not target_comp_row.empty else comps_df.iloc[0])
                
                final_rows.append({
                    "applicant_id": aid, "applicant_name": app['applicant_name'],
                    "preferred_company_1": app['preferred_company_1'], "preferred_company_2_3": app['preferred_company_2_3'],
                    "assigned_company": cname, **eval_data
                })
            st.session_state['summary'] = pd.DataFrame(final_rows)
            st.success("배치 완료")

if history_file is not None and comps_df is not None:
    if st.button("📥 기존 결과 복구"):
        st.session_state['summary'] = pd.read_csv(history_file).fillna('미배정')
        st.success("복구 완료")

# --- 4. 페이지 출력 ---
if 'summary' in st.session_state:
    df = st.session_state['summary']
    comps = st.session_state['comps_df']

    if menu == "1. 지원자 평가 점수표":
        st.dataframe(df, use_container_width=True)
        st.download_button("결과 CSV 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "matching_scores.csv")

    elif menu == "2. 개인별 상세 리포트":
        sel_aid = st.selectbox("지원자 선택", df['applicant_id'].tolist(), format_func=lambda x: f"{x} ({df[df['applicant_id']==x]['applicant_name'].values[0]})")
        row = df[df['applicant_id'] == sel_aid].iloc[0]
        st.info(f"### {row['applicant_name']}\n**최종 배정**: {row['assigned_company']} / **점수**: {row['final_evaluation_score']}점")

    elif menu == "3. 기업별 매칭 결과":
        for _, c_row in comps.iterrows():
            with st.expander(f"{c_row['company_name']} (정원: {c_row['capacity']})"):
                c_res = df[df['assigned_company'] == c_row['company_name']]
                if not c_res.empty: st.table(c_res[["applicant_id", "applicant_name", "final_evaluation_score"]])
                else: st.write("배정 인원 없음")

    elif menu == "4. 2지망 매칭 현황 (구제자)":
        guje = df[(df['assigned_company'] == df['preferred_company_2_3']) & (df['assigned_company'] != df['preferred_company_1'])]
        st.dataframe(guje, use_container_width=True)

    elif menu == "5. 종합 매칭 현황판":
        def get_fmt(aid):
            r = df[df['applicant_id'] == aid].iloc[0]
            return f"{aid}({int(r['final_evaluation_score'])})"

        p1_d, p2_d, pf_d = {}, {}, {}
        for c in comps['company_name']:
            p1_d[c] = [get_fmt(aid) for aid in df[(df['assigned_company'] == c) & (df['preferred_company_1'] == c)]['applicant_id'].tolist()]
            p2_d[c] = [get_fmt(aid) for aid in df[(df['assigned_company'] == c) & (df['preferred_company_1'] != c) & (df['assigned_company'] != "미배정")]['applicant_id'].tolist()]
            pf_ids = df[(df['preferred_company_1'] == c) & (df['assigned_company'] != c)].sort_values('final_evaluation_score', ascending=False)['applicant_id'].tolist()
            pf_d[c] = [get_fmt(aid) for aid in pf_ids]
        
        mx1, mx2, mxf = max([len(v) for v in p1_d.values()]+[1]), max([len(v) for v in p2_d.values()]+[1]), max([len(v) for v in pf_d.values()]+[1])

        st.markdown(f"""
        <style>
        .m-table {{ width: 100%; border-collapse: collapse; font-size: 11px; text-align: center; table-layout: fixed; }}
        .m-table th, .m-table td {{ border: 1px solid #ddd; padding: 4px; overflow: hidden; }}
        .bg-gray {{ background-color: #f2f2f2; font-weight: bold; }}
        .red-t {{ color: red; font-weight: bold; }}
        .green-t {{ color: #32CD32; font-weight: bold; text-decoration: underline; }}
        .col-comp {{ min-width: 120px; }}
        .col-job {{ min-width: 360px; text-align: left; }}
        .col-id {{ min-width: 80px; font-size: 10px; }}
        </style>
        """, unsafe_allow_html=True)

        html = f"<table class='m-table'><tr class='bg-gray'><th rowspan='2'>연번</th><th rowspan='2' class='col-comp'>지원 사업장</th><th rowspan='2' class='col-job'>지원 분야(요약)</th><th rowspan='2'>채용</th><th rowspan='2'>지원</th><th rowspan='2'>배수</th><th rowspan='2'>배정</th><th rowspan='2'>부족</th><th colspan='{mx1}'>1차 배정</th><th colspan='{mx2}'>2차 배정</th><th colspan='{mxf}'>1차 탈락(점수순)</th></tr><tr class='bg-gray'>"
        for _ in range(mx1+mx2+mxf): html += "<th class='col-id'></th>"
        html += "</tr>"
        
        for i, (_, row) in enumerate(comps.iterrows(), 1):
            c = row['company_name']
            as_cnt = len(p1_d[c]) + len(p2_d[c])
            dfc = max(0, row['recruitment_headcount_total'] - as_cnt)
            html += f"<tr><td>{i}</td><td class='col-comp'>{c}</td><td class='col-job'>{clean_job_summary(row.get('recruitment_summary',''))}</td><td>{row['recruitment_headcount_total']}</td><td>{len(df[df['preferred_company_1']==c])}</td><td>{row['capacity']}</td><td>{as_cnt}</td><td class='{'red-t' if dfc>0 else ''}'>{dfc}</td>"
            for j in range(mx1): html += f"<td>{p1_d[c][j] if j < len(p1_d[c]) else ''}</td>"
            for j in range(mx2): html += f"<td>{p2_d[c][j] if j < len(p2_d[c]) else ''}</td>"
            for j in range(mxf):
                if j < len(pf_d[c]):
                    val = pf_d[c][j]
                    aid = val.split('(')[0]
                    cand = df[df['applicant_id'] == int(aid)].iloc[0]
                    cls = "red-t" if cand['assigned_company'] == "미배정" else "green-t"
                    html += f"<td class='{cls}'>{val}</td>"
                else: html += "<td></td>"
            html += "</tr>"
        st.markdown(html + "</table>", unsafe_allow_html=True)
        
        st.divider()
        unassigned_ids = df[df['assigned_company'] == "미배정"]['applicant_id'].tolist()
        c_m1, c_m2, c_m3 = st.columns([2, 2, 1])
        with c_m1: s_aid = st.selectbox("수동 배정 지원자", ["선택"] + unassigned_ids)
        with c_m2: s_comp = st.selectbox("배정할 타겟 기업", ["선택"] + comps['company_name'].tolist())
        with c_m3:
            if st.button("확정"):
                if s_aid != "선택" and s_comp != "선택":
                    st.session_state['summary'].loc[st.session_state['summary']['applicant_id'] == s_aid, 'assigned_company'] = s_comp
                    st.rerun()

        st.download_button("💾 전체 데이터 저장", df.to_csv(index=False).encode('utf-8-sig'), "final_results.csv")
else:
    st.info("데이터를 업로드해 주세요.")
