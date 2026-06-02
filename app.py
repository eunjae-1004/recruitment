import streamlit as st
import pandas as pd
import numpy as np
import io
import time
import re

# --- 페이지 설정 ---
st.set_page_config(layout="wide", page_title="미청 매칭 및 평가 시스템")

# --- 데이터 정제 함수: 직무명과 인원만 추출 ---
def clean_job_summary(text):
    if not text: return "정보없음"
    # '직무명 N명' 또는 '직무명(N)' 패턴 추출
    patterns = re.findall(r'([가-힣\w\s/]+?\s*\d+\s*명)', str(text))
    if patterns:
        return ", ".join([p.strip() for p in patterns])
    return str(text)[:20] + "..."

# --- 1. 사이드바: 메뉴 및 가중치 설정 ---
st.sidebar.title("🛠️ 운영 관리 메뉴")
menu = st.sidebar.radio("페이지 이동", [
    "1. 지원자 평가 점수표", 
    "2. 개인별 상세 리포트", 
    "3. 기업별 매칭 결과",
    "4. 2지망 매칭 현황 (구제자)",
    "5. 종합 매칭 현황판 (이미지 형식)"
])

st.sidebar.divider()
st.sidebar.header("⚖️ 매칭 가중치 설정")
w_first = st.sidebar.number_input("1순위 지망 가산점", value=50)
w_second = st.sidebar.number_input("2순위 지망 가산점", value=20)
w_req = st.sidebar.slider("필수 키워드 가중치 (개당)", 0, 20, 10)
w_pref = st.sidebar.slider("우대 키워드 가중치 (개당)", 0, 20, 5)
w_major = st.sidebar.slider("전공 적합도 가중치", 0, 20, 10)
w_exp = st.sidebar.slider("경력 점수 가중치 (건당)", 0, 10, 3)
w_doc = st.sidebar.slider("문서 성실도 가중치", 0.0, 2.0, 1.0)
mult = st.sidebar.number_input("채용인원 배수 (N)", value=2)
plus = st.sidebar.number_input("추가 상수 (M)", value=1)

# --- 2. 점수 계산 엔진 ---
def calculate_scores(app, comp):
    # 텍스트 데이터 통합
    app_text = f"{app.get('experience_keywords', '')} {app.get('tool_keywords', '')} {app.get('essay_full_text', '')}".lower()
    
    # 세부 항목 계산
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
    
    p1 = str(app.get('preferred_company_1', '')).strip()
    p2_3 = str(app.get('preferred_company_2_3', '')).strip()
    c_name = str(comp.get('company_name', '')).strip()
    
    pref_b = w_first if p1 == c_name else (w_second if p2_3 == c_name else 0)
    
    total = major_s + req_s + pref_s + exp_s + port_s + doc_s + pref_b
    reason = f"필수 {req_match}개(+{req_s}), 활동 {int(app.get('experience_count', 0))}건 반영, 문서성실도 {doc_s:.1f}점"
    
    return {
        "job_fit_score": major_s, "required_match_score": req_s, "preferred_match_score": pref_s,
        "experience_match_score": exp_s, "document_score": round(doc_s, 2), "preference_bonus_score": pref_b,
        "final_evaluation_score": round(total, 2), "score_reason_summary": reason
    }

# --- 3. 데이터 로딩 및 배치 실행 ---
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

    if st.button("🚀 전체 배치 실행"):
        with st.spinner("점수 계산 및 자동 배치 중..."):
            # 1. 모든 지원자-기업 조합 점수 계산
            score_matrix = []
            for _, app in apps_df.iterrows():
                for _, comp in comps_df.iterrows():
                    res = calculate_scores(app, comp)
                    score_matrix.append({
                        "applicant_id": app['applicant_id'], "applicant_name": app['applicant_name'],
                        "company_id": comp['company_id'], "company_name": comp['company_name'].strip(),
                        "score": res['final_evaluation_score'], "pref_level": 1 if str(app['preferred_company_1']).strip() == str(comp['company_name']).strip() else (2 if str(app.get('preferred_company_2_3', '')).strip() == str(comp['company_name']).strip() else 0)
                    })
            score_df = pd.DataFrame(score_matrix)
            st.session_state['score_df'] = score_df
            
            # 2. 배치 알고리즘 (Pass 1: 1순위 / Pass 2: 2순위)
            assigned = {}
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
            
            # 3. 통합 결과 데이터프레임 생성
            final_rows = []
            for _, app in apps_df.iterrows():
                aid = app['applicant_id']
                t_cid = assigned.get(aid, None)
                cname = comps_df[comps_df['company_id'] == t_cid]['company_name'].values[0] if t_cid else "미배정"
                p1_name = str(app['preferred_company_1']).strip()
                s_info = score_df[(score_df['applicant_id'] == aid) & (score_df['company_name'] == p1_name)]
                eval_data = calculate_scores(app, comps_df[comps_df['company_name']==(cname if cname != "미배정" else p1_name)].iloc[0])
                
                final_rows.append({
                    "applicant_id": aid, "applicant_name": app['applicant_name'], "field": app.get('application_field', '기타'),
                    "preferred_company_1": p1_name, "preferred_company_2_3": str(app.get('preferred_company_2_3', '')).strip(),
                    "assigned_company": cname, **eval_data
                })
            st.session_state['summary'] = pd.DataFrame(final_rows)
            st.success("배치가 완료되었습니다!")

# --- 4. 페이지별 출력 로직 (이 블록이 모든 정보를 관리함) ---
if 'summary' in st.session_state:
    df = st.session_state['summary']
    comps = st.session_state['comps_df']

    if menu == "1. 지원자 평가 점수표":
        st.subheader("📑 지원자 세부 평가 및 지망 정보")
        cols = ["applicant_id", "applicant_name", "preferred_company_1", "preferred_company_2_3", "assigned_company", "final_evaluation_score", "job_fit_score", "required_match_score", "experience_match_score", "document_score"]
        st.dataframe(df[cols], use_container_width=True)
        st.download_button("📥 전체 결과 다운로드 (CSV)", df.to_csv(index=False).encode('utf-8-sig'), "matching_summary.csv")

    elif menu == "2. 개인별 상세 리포트":
        st.subheader("👤 개인별 상세 리포트")
        sel_aid = st.selectbox("지원자 선택", df['applicant_id'].tolist(), format_func=lambda x: f"{x} ({df[df['applicant_id']==x]['applicant_name'].values[0]})")
        row = df[df['applicant_id'] == sel_aid].iloc[0]
        c_l, c_r = st.columns(2)
        with c_l:
            st.info(f"### {row['applicant_name']}\n**1지망**: {row['preferred_company_1']}\n**2지망**: {row['preferred_company_2_3']}\n**최종 배정**: {row['assigned_company']}")
            st.metric("종합 점수", f"{row['final_evaluation_score']}점")
            st.success(f"**산출 근거**: {row['score_reason_summary']}")
        with c_r:
            st.bar_chart(pd.Series({"직무": row['job_fit_score'], "필수": row['required_match_score'], "우대": row['preferred_match_score'], "경력": row['experience_match_score'], "문서": row['document_score'], "가점": row['preference_bonus_score']}))

    elif menu == "3. 기업별 매칭 결과":
        st.subheader("🏢 기업별 최종 배정 명단")
        for _, c_row in comps.iterrows():
            with st.expander(f"{c_row['company_name']} (정원: {c_row['capacity']})"):
                c_res = df[df['assigned_company'] == c_row['company_name']]
                if not c_res.empty: st.table(c_res[["applicant_id", "applicant_name", "final_evaluation_score", "score_reason_summary"]])
                else: st.write("배정 인원 없음")

    elif menu == "4. 2지망 매칭 현황 (구제자)":
        st.subheader("🔄 2지망 매칭 현황 (구제자)")
        guje_df = df[(df['assigned_company'] == df['preferred_company_2_3']) & (df['assigned_company'] != df['preferred_company_1']) & (df['assigned_company'] != "미배정")]
        st.dataframe(guje_df[["applicant_id", "applicant_name", "preferred_company_1", "assigned_company", "final_evaluation_score"]], use_container_width=True)

    elif menu == "5. 종합 매칭 현황판 (이미지 형식)":
        st.subheader("📊 종합 매칭 현황판 (상세 지표)")
        
        # 가변 칸수 및 데이터 정렬 로직
        p1_data, p2_data, pf_data = {}, {}, {}
        for c in comps['company_name']:
            c = c.strip()
            p1_data[c] = df[(df['assigned_company'] == c) & (df['preferred_company_1'] == c)]['applicant_id'].tolist()
            p2_data[c] = df[(df['assigned_company'] == c) & (df['preferred_company_1'] != c) & (df['assigned_company'] != "미배정")]['applicant_id'].tolist()
            pf_df = df[(df['preferred_company_1'] == c) & (df['assigned_company'] != c)]
            pf_data[c] = pf_df.sort_values('final_evaluation_score', ascending=False)['applicant_id'].tolist()
        
        max_p1 = max([len(v) for v in p1_data.values()] + [1])
        max_p2 = max([len(v) for v in p2_data.values()] + [1])
        max_pf = max([len(v) for v in pf_data.values()] + [1])

        st.markdown(f"""
        <style>
        .m-table {{ width: 100%; border-collapse: collapse; font-size: 11px; text-align: center; }}
        .m-table th, .m-table td {{ border: 1px solid #ddd; padding: 6px; }}
        .bg-gray {{ background-color: #f2f2f2; font-weight: bold; color: black; }}
        .deficit-red {{ color: red; font-weight: bold; }}
        .red-text {{ color: red; font-weight: bold; cursor: help; }}
        .blue-text {{ color: blue; text-decoration: underline; cursor: help; }}
        .tooltip {{ position: relative; display: inline-block; }}
        .tooltip .tooltiptext {{ visibility: hidden; width: 160px; background-color: #333; color: #fff; text-align: center; border-radius: 6px; padding: 8px; position: absolute; z-index: 100; bottom: 125%; left: 50%; margin-left: -80px; opacity: 0; transition: opacity 0.3s; }}
        .tooltip:hover .tooltiptext {{ visibility: visible; opacity: 1; }}
        </style>
        """, unsafe_allow_html=True)

        html = f"<table class='m-table'><tr class='bg-gray'><th rowspan='2'>연번</th><th rowspan='2'>지원 사업장</th><th rowspan='2'>지원 분야(요약)</th><th rowspan='2'>채용</th><th rowspan='2'>지원</th><th rowspan='2'>배수</th><th rowspan='2'>배정</th><th rowspan='2'>부족</th><th colspan='{max_p1}'>1차 배정</th><th colspan='{max_p2}'>2차 배정</th><th colspan='{max_pf}'>1차 탈락(점수순)</th></tr><tr class='bg-gray'>"
        for _ in range(max_p1 + max_p2 + max_pf): html += "<th></th>"
        html += "</tr>"
        
        for i, (_, row) in enumerate(comps.iterrows(), 1):
            c = row['company_name'].strip()
            p1, p2, pf = p1_data[c], p2_data[c], pf_data[c]
            assigned_total = len(p1) + len(p2)
            deficit = max(0, row['recruitment_headcount_total'] - assigned_total)
            def_style = "class='deficit-red'" if deficit > 0 else ""
            job_text = clean_job_summary(row.get('recruitment_summary', ''))
            
            html += f"<tr><td>{i}</td><td>{c}</td><td>{job_text}</td><td>{row['recruitment_headcount_total']}</td><td>{len(df[df['preferred_company_1'] == c])}</td><td>{row['capacity']}</td><td>{assigned_total}</td><td {def_style}>{deficit}</td>"
            for j in range(max_p1): html += f"<td>{p1[j] if j < len(p1) else ''}</td>"
            for j in range(max_p2): html += f"<td>{p2[j] if j < len(p2) else ''}</td>"
            for j in range(max_pf):
                if j < len(pf):
                    aid = pf[j]
                    cand = df[df['applicant_id'] == aid].iloc[0]
                    dest = cand['assigned_company']
                    tip = f"분야: {cand['field']}<br>점수: {cand['final_evaluation_score']}점"
                    if dest == "미배정": html += f"<td><div class='tooltip red-text'>{aid}<span class='tooltiptext'>{tip}<br>(미배정)</span></div></td>"
                    else: html += f"<td><div class='tooltip blue-text'>{aid}<span class='tooltiptext'>{tip}<br>(배정지: {dest})</span></div></td>"
                else: html += "<td></td>"
            html += "</tr>"
        st.markdown(html + "</table>", unsafe_allow_html=True)

        # 수동 배치 기능
        st.divider()
        st.subheader("🛠️ 미배정 인원 수동 배치")
        unassigned_list = df[df['assigned_company'] == "미배정"]['applicant_id'].tolist()
        if unassigned_list:
            c_m1, c_m2, c_m3 = st.columns([2, 2, 1])
            with c_m1: s_aid = st.selectbox("수동 배치 지원자 번호", unassigned_list)
            with c_m2: s_comp = st.selectbox("배치할 타겟 기업", comps['company_name'].tolist())
            with c_m3:
                if st.button("수동 배정 확정"):
                    new_cid = comps[comps['company_name'] == s_comp]['company_id'].values[0]
                    st.session_state['assignments'][s_aid] = new_cid
                    st.rerun()
else:
    st.info("CSV 파일을 업로드한 후 배치를 실행해 주세요.")
