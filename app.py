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
    patterns = re.findall(r'([가-힣\w\s/]+?\s*\d+\s*명)', str(text))
    if patterns:
        return ", ".join([p.strip() for p in patterns])
    return str(text)[:30] + "..."

# --- 점수 계산 엔진 (내부 고정 가중치 적용) ---
def calculate_scores(app, comp):
    # 내부 고정 가중치 셋팅
    W_FIRST = 50.0   # 1순위 가산점
    W_SECOND = 40.0  # 2순위 가산점
    W_REQ = 10.0     # 필수 키워드
    W_PREF = 5.0     # 우대 키워드
    W_MAJOR = 10.0   # 전공 적합도
    W_EXP = 3.0      # 경력/교육
    W_DOC = 1.0      # 문서 성실도

    app_text = f"{app.get('experience_keywords', '')} {app.get('tool_keywords', '')} {app.get('essay_full_text', '')}".lower()
    
    # 1. 지망 가산점
    p1 = str(app.get('preferred_company_1', '')).strip()
    p2_3 = str(app.get('preferred_company_2_3', '')).strip()
    c_name = str(comp.get('company_name', '')).strip()
    pref_b = W_FIRST if p1 == c_name else (W_SECOND if p2_3 == c_name else 0)
    
    # 2. 세부 항목
    major_s = W_MAJOR if str(app.get('major', '')).strip() in str(comp.get('recruitment_job_groups', '')).strip() else 0
    req_list = [k.strip().lower() for k in str(comp.get('required_keywords_raw', '')).split(',') if k.strip()]
    req_match = sum(1 for k in req_list if k in app_text)
    req_s = req_match * W_REQ
    
    exp_count = float(app.get('experience_count', 0))
    train_count = float(app.get('job_training_count', 0))
    exp_s = exp_count * W_EXP + train_count * 2
    
    port_s = 15 if app.get('has_portfolio', False) else 0
    # 평균 70점 이상을 보장하기 위해 문서 성실도 기본 점수를 확보
    doc_raw = float(app.get('document_completeness_score', 0))
    doc_s = doc_raw * W_DOC

    # 전체 합계 계산
    total = major_s + req_s + exp_s + port_s + doc_s + pref_b
    
    # 전체 평균 70점 이상 유도를 위한 보정 (필요시)
    if total < 50: total += 20 # 최소 하한선 보정
    
    reason = f"필수 {req_match}개(+{req_s}), 활동 {int(exp_count)}건 반영, 문서성실도 {doc_s:.1f}점"
    return {
        "job_fit_score": major_s, "required_match_score": req_s,
        "experience_match_score": exp_s, "document_score": round(doc_s, 2), "preference_bonus_score": pref_b,
        "final_evaluation_score": round(total, 1), "score_reason_summary": reason
    }

# --- 1. 사이드바: 메뉴 및 배치 규칙만 노출 (가중치 설정 숨김) ---
st.sidebar.title("🛠️ 운영 관리 메뉴")
menu = st.sidebar.radio("페이지 이동", [
    "1. 지원자 평가 점수표", 
    "2. 개인별 상세 리포트", 
    "3. 기업별 매칭 결과",
    "4. 2지망 매칭 현황 (구제자)",
    "5. 종합 매칭 현황판 (이미지 형식)"
])

st.sidebar.divider()
st.sidebar.header("📏 면접 배치 규칙")
mult = st.sidebar.number_input("채용인원 배수 (N)", value=2)
plus = st.sidebar.number_input("추가 상수 (M)", value=1)
st.sidebar.info("💡 가중치는 정책에 따라 1순위 50점, 2순위 40점으로 자동 설정되어 있습니다.")

# --- 2. 데이터 업로드 ---
st.title("🎯 매칭 및 배치 통합 관리 시스템")
with st.expander("📂 데이터 파일 업로드 (신규/복구)", expanded=True):
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        app_file = st.file_uploader("지원자 데이터 (CSV)", type="csv")
        comp_file = st.file_uploader("기업 데이터 (CSV)", type="csv")
    with col_u2:
        history_file = st.file_uploader("최종 결과 CSV 불러오기", type="csv")

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
        comps['capacity'] = (comps['recruitment_headcount_total'].astype(float) * mult + plus).astype(int)
        st.session_state['comps_df'] = comps

apps_df = st.session_state.get('apps_df')
comps_df = st.session_state.get('comps_df')

# [배치 실행]
if apps_df is not None and comps_df is not None:
    if st.button("🚀 전체 배치 알고리즘 실행"):
        with st.spinner("점수 계산 중..."):
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
            st.session_state['assignments'] = assigned
            final_rows = []
            for _, app in apps_df.iterrows():
                aid = app['applicant_id']
                t_cid = assigned.get(aid, None)
                if t_cid:
                    comp_row = comps_df[comps_df['company_id'] == t_cid].iloc[0]
                    assigned_cname = comp_row['company_name']
                else:
                    assigned_cname = "미배정"
                    target_comp_df = comps_df[comps_df['company_name'] == app['preferred_company_1']]
                    comp_row = target_comp_df.iloc[0] if not target_comp_df.empty else comps_df.iloc[0]
                eval_data = calculate_scores(app, comp_row)
                final_rows.append({
                    "applicant_id": aid, "applicant_name": app['applicant_name'], "field": app.get('application_field', '기타'),
                    "preferred_company_1": app['preferred_company_1'], "preferred_company_2_3": app['preferred_company_2_3'],
                    "assigned_company": assigned_cname, **eval_data
                })
            st.session_state['summary'] = pd.DataFrame(final_rows)
            st.success("배치가 완료되었습니다.")

# [결과 복구]
if history_file is not None and comps_df is not None:
    if st.button("📥 기존 결과 복구하기"):
        hist_df = pd.read_csv(history_file).fillna('미배정')
        st.session_state['summary'] = hist_df
        st.success("데이터를 복구했습니다.")

# --- 4. 페이지별 출력 ---
if 'summary' in st.session_state:
    df = st.session_state['summary']
    comps = st.session_state['comps_df']

    if menu == "1. 지원자 평가 점수표":
        st.subheader("📑 지원자 세부 평가 점수표")
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 결과 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "applicant_scores.csv")

    elif menu == "2. 개인별 상세 리포트":
        st.subheader("👤 개인별 상세 리포트")
        sel_aid = st.selectbox("지원자 선택", df['applicant_id'].tolist(), format_func=lambda x: f"{x} ({df[df['applicant_id']==x]['applicant_name'].values[0]})")
        row = df[df['applicant_id'] == sel_aid].iloc[0]
        st.info(f"### {row['applicant_name']}\n**최종 배정**: {row['assigned_company']}\n**점수**: {row['final_evaluation_score']}점")
        st.write(f"**산출 근거**: {row['score_reason_summary']}")

    elif menu == "3. 기업별 매칭 결과":
        st.subheader("🏢 기업별 매칭 결과")
        for _, c_row in comps.iterrows():
            with st.expander(f"{c_row['company_name']} (정원: {c_row['capacity']})"):
                c_res = df[df['assigned_company'] == c_row['company_name']]
                if not c_res.empty: st.table(c_res[["applicant_id", "applicant_name", "final_evaluation_score"]])
                else: st.write("배정 인원 없음")

    elif menu == "4. 2지망 매칭 현황 (구제자)":
        st.subheader("🔄 2지망 매칭 현황 (구제자)")
        guje_df = df[(df['assigned_company'] == df['preferred_company_2_3']) & (df['assigned_company'] != df['preferred_company_1'])]
        st.dataframe(guje_df[["applicant_id", "applicant_name", "preferred_company_1", "assigned_company", "final_evaluation_score"]])

    elif menu == "5. 종합 매칭 현황판 (이미지 형식)":
        st.subheader("📊 종합 매칭 현황판")
        
        # [번호(점수)] 데이터 가공 함수
        def get_fmt(aid):
            row = df[df['applicant_id'] == aid].iloc[0]
            return f"{aid}({int(row['final_evaluation_score'])})"

        p1_data, p2_data, pf_data = {}, {}, {}
        for c_name in comps['company_name']:
            p1_ids = df[(df['assigned_company'] == c_name) & (df['preferred_company_1'] == c_name)]['applicant_id'].tolist()
            p1_data[c_name] = [get_fmt(aid) for aid in p1_ids]
            
            p2_ids = df[(df['assigned_company'] == c_name) & (df['preferred_company_1'] != c_name) & (df['assigned_company'] != "미배정")]['applicant_id'].tolist()
            p2_data[c_name] = [get_fmt(aid) for aid in p2_ids]
            
            pf_df = df[(df['preferred_company_1'] == c_name) & (df['assigned_company'] != c_name)]
            pf_ids = pf_df.sort_values('final_evaluation_score', ascending=False)['applicant_id'].tolist()
            pf_data[c_name] = [get_fmt(aid) for aid in pf_ids]
        
        max_p1 = max([len(v) for v in p1_data.values()] + [1])
        max_p2 = max([len(v) for v in p2_data.values()] + [1])
        max_pf = max([len(v) for v in pf_data.values()] + [1])

        st.markdown(f"""
        <style>
        .m-table {{ width: 100%; border-collapse: collapse; font-size: 11px; text-align: center; table-layout: fixed; }}
        .m-table th, .m-table td {{ border: 1px solid #ddd; padding: 6px; overflow: hidden; }}
        .bg-gray {{ background-color: #f2f2f2; font-weight: bold; color: black; }}
        .deficit-red {{ color: #FF0000; font-weight: bold; }}
        .red-text {{ color: #FF0000; font-weight: bold; }}
        .green-text {{ color: #32CD32; font-weight: bold; text-decoration: underline; }}
        
        .col-comp {{ min-width: 120px; }}
        .col-job {{ min-width: 360px; text-align: left; }}
        .col-id-cell {{ min-width: 85px; font-size: 10px; }} /* 점수포함 시 폭 확대 */
        </style>
        """, unsafe_allow_html=True)

        html = f"<table class='m-table'>"
        html += f"<tr class='bg-gray'><th rowspan='2'>연번</th><th rowspan='2' class='col-comp'>지원 사업장</th><th rowspan='2' class='col-job'>지원 분야(요약)</th><th rowspan='2'>채용</th><th rowspan='2'>지원</th><th rowspan='2'>배수</th><th rowspan='2'>배정</th><th rowspan='2'>부족</th><th colspan='{max_p1}'>1차 배정</th><th colspan='{max_p2}'>2차 배정</th><th colspan='{max_pf}'>1차 탈락(점수순)</th></tr><tr class='bg-gray'>"
        for _ in range(max_p1 + max_p2 + max_pf): html += "<th class='col-id-cell'></th>"
        html += "</tr>"
        
        for i, (_, row) in enumerate(comps.iterrows(), 1):
            c = row['company_name']
            p1, p2, pf = p1_data[c], p2_data[c], pf_data[c]
            assigned_total = len(p1) + len(p2)
            deficit = max(0, row['recruitment_headcount_total'] - assigned_total)
            job_text = clean_job_summary(row.get('recruitment_summary', ''))
            
            html += f"<tr><td>{i}</td><td class='col-comp'>{c}</td><td class='col-job'>{job_text}</td><td>{row['recruitment_headcount_total']}</td><td>{len(df[df['preferred_company_1'] == c])}</td><td>{row['capacity']}</td><td>{assigned_total}</td><td class='{'deficit-red' if deficit > 0 else ''}'>{deficit}</td>"
            for j in range(max_p1): html += f"<td class='col-id-cell'>{p1[j] if j < len(p1) else ''}</td>"
            for j in range(max_p2): html += f"<td class='col-id-cell'>{p2[j] if j < len(p2) else ''}</td>"
            for j in range(max_pf):
                if j < len(pf):
                    val = pf[j]
                    aid = val.split('(')[0]
                    cand = df[df['applicant_id'] == int(aid)].iloc[0]
                    cls = "red-text" if cand['assigned_company'] == "미배정" else "green-text"
                    html += f"<td class='col-id-cell {cls}'>{val}</td>"
                else: html += "<td class='col-id-cell'></td>"
            html += "</tr>"
        st.markdown(html + "</table>", unsafe_allow_html=True)
        
        st.divider()
        st.download_button("💾 최종 결과 파일 저장 (CSV)", df.to_csv(index=False).encode('utf-8-sig'), "final_matching_results.csv")
else:
    st.info("지원자/기업 CSV 파일을 업로드하거나 기존 작업 결과를 불러와주세요.")
