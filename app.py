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
    return str(text)[:30] + "..." # 길이를 조금 더 허용

# --- 점수 계산 엔진 ---
def calculate_scores(app, comp, weights):
    app_text = f"{app.get('experience_keywords', '')} {app.get('tool_keywords', '')} {app.get('essay_full_text', '')}".lower()
    major_s = weights['w_major'] if str(app.get('major', '')).strip() in str(comp.get('recruitment_job_groups', '')).strip() else 0
    req_list = [k.strip().lower() for k in str(comp.get('required_keywords_raw', '')).split(',') if k.strip()]
    req_match = sum(1 for k in req_list if k in app_text)
    req_s = req_match * weights['w_req']
    pref_list = [k.strip().lower() for k in str(comp.get('preferred_keywords_raw', '')).split(',') if k.strip()]
    pref_match = sum(1 for k in pref_list if k in app_text)
    pref_s = pref_match * weights['w_pref']
    exp_count = float(app.get('experience_count', 0))
    train_count = float(app.get('job_training_count', 0))
    exp_s = exp_count * weights['w_exp'] + train_count * 2
    port_s = 15 if app.get('has_portfolio', False) else 0
    doc_s = float(app.get('document_completeness_score', 0)) * weights['w_doc']
    p1 = str(app.get('preferred_company_1', '')).strip()
    p2_3 = str(app.get('preferred_company_2_3', '')).strip()
    c_name = str(comp.get('company_name', '')).strip()
    pref_b = weights['w_first'] if p1 == c_name else (weights['w_second'] if p2_3 == c_name else 0)
    total = major_s + req_s + pref_s + exp_s + port_s + doc_s + pref_b
    reason = f"필수 {req_match}개(+{req_s}), 활동 {int(exp_count)}건 반영, 문서성실도 {doc_s:.1f}점"
    return {
        "job_fit_score": major_s, "required_match_score": req_s, "preferred_match_score": pref_s,
        "experience_match_score": exp_s, "document_score": round(doc_s, 2), "preference_bonus_score": pref_b,
        "final_evaluation_score": round(total, 2), "score_reason_summary": reason
    }

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
weights = {
    'w_first': st.sidebar.number_input("1순위 지망 가산점", value=50),
    'w_second': st.sidebar.number_input("2순위 지망 가산점", value=20),
    'w_req': st.sidebar.slider("필수 키워드 가중치", 0, 20, 10),
    'w_pref': st.sidebar.slider("우대 키워드 가중치", 0, 20, 5),
    'w_major': st.sidebar.slider("전공 적합도 가중치", 0, 20, 10),
    'w_exp': st.sidebar.slider("경력 점수 가중치", 0, 10, 3),
    'w_doc': st.sidebar.slider("문서 성실도 가중치", 0.0, 2.0, 1.0),
}
mult = st.sidebar.number_input("채용인원 배수 (N)", value=2)
plus = st.sidebar.number_input("추가 상수 (M)", value=1)

# --- 2. 데이터 업로드 및 초기화 ---
st.title("🎯 매칭 및 배치 통합 관리 시스템")
with st.expander("📂 데이터 파일 업로드 (이어서 작업하기 지원)", expanded=True):
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        st.markdown("### 📋 1. 원본 데이터 업로드")
        app_file = st.file_uploader("지원자 데이터 (CSV)", type="csv")
        comp_file = st.file_uploader("기업 데이터 (CSV)", type="csv")
    with col_u2:
        st.markdown("### 📥 2. 작업 복구 (선택사항)")
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

# [알고리즘 실행]
if apps_df is not None and comps_df is not None:
    if st.button("🚀 신규 배치 알고리즘 실행"):
        with st.spinner("점수 계산 및 배치 중..."):
            score_matrix = []
            for _, app in apps_df.iterrows():
                for _, comp in comps_df.iterrows():
                    res = calculate_scores(app, comp, weights)
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
                eval_data = calculate_scores(app, comp_row, weights)
                final_rows.append({
                    "applicant_id": aid, "applicant_name": app['applicant_name'], "field": app.get('application_field', '기타'),
                    "preferred_company_1": app['preferred_company_1'], "preferred_company_2_3": app['preferred_company_2_3'],
                    "assigned_company": assigned_cname, **eval_data
                })
            st.session_state['summary'] = pd.DataFrame(final_rows)
            st.success("배치 알고리즘 실행 완료!")

# [기존 결과 복구]
if history_file is not None and comps_df is not None:
    if st.button("📥 기존 결과 복구하기"):
        hist_df = pd.read_csv(history_file).fillna('미배정')
        new_assigned = {}
        for _, row in hist_df.iterrows():
            aid = row['applicant_id']
            cname = str(row['assigned_company']).strip()
            if cname != "미배정":
                cid_list = comps_df[comps_df['company_name'] == cname]['company_id'].values
                if len(cid_list) > 0: new_assigned[aid] = cid_list[0]
        st.session_state['assignments'] = new_assigned
        st.session_state['summary'] = hist_df
        st.success("이전 작업 내용을 복구했습니다. 페이지를 이동하여 확인하세요.")

# --- 4. 페이지별 출력 ---
if 'summary' in st.session_state:
    df = st.session_state['summary']
    comps = st.session_state['comps_df']

    if menu == "1. 지원자 평가 점수표":
        st.subheader("📑 지원자 세부 평가 점수표")
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 전체 결과 CSV 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "applicant_matching_scores.csv")

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
            st.bar_chart(pd.Series({"직무": row.get('job_fit_score', 0), "필수": row.get('required_match_score', 0), "경력": row.get('experience_match_score', 0), "문서": row.get('document_score', 0), "가점": row.get('preference_bonus_score', 0)}))

    elif menu == "3. 기업별 매칭 결과":
        st.subheader("🏢 기업별 매칭 결과")
        for _, c_row in comps.iterrows():
            with st.expander(f"{c_row['company_name']} (정원: {c_row['capacity']})"):
                c_res = df[df['assigned_company'] == c_row['company_name']]
                if not c_res.empty:
                    st.table(c_res[["applicant_id", "applicant_name", "final_evaluation_score", "score_reason_summary"]])
                else: st.write("배정 인원 없음")

    elif menu == "4. 2지망 매칭 현황 (구제자)":
        st.subheader("🔄 2지망 매칭 현황 (구제자)")
        guje_df = df[(df['assigned_company'] == df['preferred_company_2_3']) & (df['assigned_company'] != df['preferred_company_1']) & (df['assigned_company'] != "미배정")]
        st.dataframe(guje_df, use_container_width=True)
        st.download_button("📥 구제자 명단 다운로드", guje_df.to_csv(index=False).encode('utf-8-sig'), "guje_list.csv")

    elif menu == "5. 종합 매칭 현황판 (이미지 형식)":
        st.subheader("📊 종합 매칭 현황판 (이미지 형식)")
        
        # 데이터 집계
        p1_data, p2_data, pf_data = {}, {}, {}
        for c_name in comps['company_name']:
            p1_data[c_name] = df[(df['assigned_company'] == c_name) & (df['preferred_company_1'] == c_name)]['applicant_id'].tolist()
            p2_data[c_name] = df[(df['assigned_company'] == c_name) & (df['preferred_company_1'] != c_name) & (df['assigned_company'] != "미배정")]['applicant_id'].tolist()
            pf_df = df[(df['preferred_company_1'] == c_name) & (df['assigned_company'] != c_name)]
            pf_data[c_name] = pf_df.sort_values('final_evaluation_score', ascending=False)['applicant_id'].tolist()
        
        max_p1, max_p2, max_pf = max([len(v) for v in p1_data.values()] + [1]), max([len(v) for v in p2_data.values()] + [1]), max([len(v) for v in pf_data.values()] + [1])

        # CSS 고도화: 폰트 2배(22px), 열폭 조정(지원분야 3배), 색상 변경(연두색)
        st.markdown(f"""
        <style>
        .m-table {{ width: 100%; border-collapse: collapse; font-size: 22px; text-align: center; table-layout: fixed; }}
        .m-table th, .m-table td {{ border: 1px solid #ddd; padding: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .bg-gray {{ background-color: #f2f2f2; font-weight: bold; color: black; }}
        .deficit-red {{ color: #FF0000; font-weight: bold; }}
        .red-text {{ color: #FF0000; font-weight: bold; cursor: help; }}
        .green-text {{ color: #32CD32; font-weight: bold; cursor: help; text-decoration: underline; }}
        .tooltip {{ position: relative; display: inline-block; }}
        .tooltip .tooltiptext {{ visibility: hidden; width: 220px; background-color: black; color: #fff; text-align: center; border-radius: 6px; padding: 8px; position: absolute; z-index: 100; bottom: 125%; left: 50%; margin-left: -110px; opacity: 0; transition: opacity 0.3s; font-size: 16px; }}
        .tooltip:hover .tooltiptext {{ visibility: visible; opacity: 1; }}
        
        /* 열폭 조정 섹션 */
        .col-id {{ width: 60px; }}
        .col-comp {{ width: 200px; }}  /* 사업장 폭 기준 */
        .col-job {{ width: 600px; }}   /* 분야 폭을 사업장의 3배로 설정 */
        .col-num {{ width: 80px; }}
        .col-app-id {{ width: 100px; }}
        </style>
        """, unsafe_allow_html=True)

        # 테이블 헤더 생성
        html = f"<table class='m-table'>"
        html += f"""
        <tr class='bg-gray'>
            <th rowspan='2' class='col-id'>연번</th>
            <th rowspan='2' class='col-comp'>지원 사업장</th>
            <th rowspan='2' class='col-job'>지원 분야(요약)</th>
            <th rowspan='2' class='col-num'>채용</th>
            <th rowspan='2' class='col-num'>지원</th>
            <th rowspan='2' class='col-num'>배수</th>
            <th rowspan='2' class='col-num'>배정</th>
            <th rowspan='2' class='col-num'>부족</th>
            <th colspan='{max_p1}'>1차 배정</th>
            <th colspan='{max_p2}'>2차 배정</th>
            <th colspan='{max_pf}'>1차 탈락(점수순)</th>
        </tr>
        <tr class='bg-gray'>
        """
        for _ in range(max_p1 + max_p2 + max_pf): html += "<th class='col-app-id'></th>"
        html += "</tr>"
        
        # 테이블 바디 생성
        for i, (_, row) in enumerate(comps.iterrows(), 1):
            c = row['company_name']
            p1, p2, pf = p1_data[c], p2_data[c], pf_data[c]
            assigned_total = len(p1) + len(p2)
            deficit = max(0, row['recruitment_headcount_total'] - assigned_total)
            job_text = clean_job_summary(row.get('recruitment_summary', ''))
            
            html += f"<tr>"
            html += f"<td>{i}</td>"
            html += f"<td class='col-comp'>{c}</td>"
            html += f"<td class='col-job' title='{row.get('recruitment_summary', '')}'>{job_text}</td>"
            html += f"<td>{row['recruitment_headcount_total']}</td>"
            html += f"<td>{len(df[df['preferred_company_1'] == c])}</td>"
            html += f"<td>{row['capacity']}</td>"
            html += f"<td>{assigned_total}</td>"
            html += f"<td class='{'deficit-red' if deficit > 0 else ''}'>{deficit}</td>"
            
            # 1차 배정 칸
            for j in range(max_p1): html += f"<td>{p1[j] if j < len(p1) else ''}</td>"
            # 2차 배정 칸
            for j in range(max_p2): html += f"<td>{p2[j] if j < len(p2) else ''}</td>"
            # 탈락자 칸 (스타일 적용)
            for j in range(max_pf):
                if j < len(pf):
                    aid = pf[j]
                    cand = df[df['applicant_id'] == aid].iloc[0]
                    tip = f"분야: {cand.get('field','기타')}<br>점수: {cand['final_evaluation_score']}점"
                    if cand['assigned_company'] == "미배정": 
                        html += f"<td><div class='tooltip red-text'>{aid}<span class='tooltiptext'>{tip}<br>(미배정)</span></div></td>"
                    else: 
                        html += f"<td><div class='tooltip green-text'>{aid}<span class='tooltiptext'>{tip}<br>(배정지: {cand['assigned_company']})</span></div></td>"
                else: html += "<td></td>"
            html += "</tr>"
        
        html += "</table>"
        st.markdown(html, unsafe_allow_html=True)
        
        # 수동 배치 기능
        st.divider()
        st.subheader("🛠️ 미배정 인원 수동 배치 및 조정")
        unassigned_list = df[df['assigned_company'] == "미배정"]['applicant_id'].tolist()
        c_m1, c_m2, c_m3 = st.columns([2, 2, 1])
        with c_m1: s_aid = st.selectbox("수동 배치 지원자 번호", ["선택"] + unassigned_list)
        with c_m2: s_comp = st.selectbox("배치할 타겟 기업", ["선택"] + comps['company_name'].tolist())
        with c_m3:
            if st.button("수동 배정 확정"):
                if s_aid != "선택" and s_comp != "선택":
                    target_cid = comps[comps['company_name'] == s_comp]['company_id'].values[0]
                    st.session_state['assignments'][s_aid] = target_cid
                    st.session_state['summary'].loc[st.session_state['summary']['applicant_id'] == s_aid, 'assigned_company'] = s_comp
                    st.success(f"{s_aid}번 지원자를 {s_comp}에 수동 배정했습니다.")
                    time.sleep(1)
                    st.rerun()

        st.download_button("💾 전체 작업 결과 파일 다운로드 (작업 저장용)", df.to_csv(index=False).encode('utf-8-sig'), "final_matching_results.csv")
else:
    st.info("지원자/기업 CSV 파일을 업로드하거나 기존 작업 결과를 불러와주세요.")
