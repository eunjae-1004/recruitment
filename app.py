import streamlit as st
import pandas as pd
import numpy as np
import io
import time

# --- 페이지 설정 ---
st.set_page_config(layout="wide", page_title="미청 매칭 & 평가 시스템")

# --- 1. 사이드바 지원자가 희망했던 **1순위 지망 기업**과 **2순위 지망 기업** 정보를 추가했습니다. 이를 통해 어떤 기업을 희망했으나 최종적으로 어디에 배정되었는지(또는 미배정되었: 운영자 메뉴 및 가중치 설정 ---
st.sidebar.title("🛠️ 운영 관리 메뉴")
menu = st.sidebar.radio("페이지 이동", ["1. 지원자 평가 점수표", "2. 개인는지) 한눈에 비교할 수 있습니다.

또한, 데이터 누락을 방지하기 위해 2순위 지망 기업 정보별 상세 리포트", "3. 기업별 매칭 결과"])

st.sidebar.divider()
st(`preferred_company_2_3`)도 결과 테이블에 포함되도록 로직을 수정했습니다.

---

### 🚀 수정.sidebar.header("⚖️ 매칭 가중치 설정")

# 가중치 입력값들
w_first = st.sidebar.number_input("1순위 지망 가산점", value=50)
w_second = st.sidebar.number_input("2순위 지망 가산점", value된 최종 통합 코드 (app.py)

이 코드를 복사하여 GitHub의 `app.py`에 업데이트=20)
w_req = st.sidebar.slider("필수 키워드 가중치 (해 주세요.

```python
import streamlit as st
import pandas as pd
import numpy as np
import io
개당)", 0, 20, 10)
w_pref = st.sidebar.sliderimport time

# --- 페이지 설정 ---
st.set_page_config(layout="wide", page_title("우대 키워드 가중치 (개당)", 0, 20, 5)
="미청 매칭 & 평가 시스템")

# --- 1. 사이드바: 운영 관리 메뉴 ---
st.sidebarw_major = st.sidebar.slider("전공 적합도 가중치", 0, 2.title("🛠️ 운영 관리 메뉴")
menu = st.sidebar.radio("페이지 이동", ["1. 지원자 평가 점수표", "2. 개인별 상세 리포트", "3. 기업별 매칭0, 10)
w_exp = st.sidebar.slider("경력 점수 가중치 (건당)", 0, 10, 3)
w_train = st.sidebar.slider 결과"])

st.sidebar.divider()
st.sidebar.header("⚖️ 가중치 설정")
w_first = st.sidebar.number_input("1순위 지망 가산점", value=5("교육 점수 가중치 (건당)", 0, 10, 2)
w_portfolio = st.sidebar.number_input("포트폴리오 가산점", value=15)
w_doc = st.sidebar.slider("문서 성실도 가중치 (계수)", 0.0, 0)
w_second = st.sidebar.number_input("2순위 지망 가산점", value=20)
w_req = st.sidebar.slider("필수 키워드 가중치",2.0, 1.0)

st.sidebar.divider()
st.sidebar.header("📏 면접 배치 규칙")
mult = st.sidebar.number_input("채용인원 배수 (N 0, 20, 10)
w_pref = st.sidebar.slider("우대 키워드 가중치", 0, 20, 5)
w_major = st.sidebar.slider("전공 적합도 가중치", 0, 20, 10))", value=2)
plus = st.sidebar.number_input("추가 상수 (M)", value=1)

# --- 2. 데이터 업로드 섹션 ---
st.title("🎯 매칭 및 배치
w_exp = st.sidebar.slider("경력 점수 가중치", 0, 10 통합 관리 시스템")
with st.expander("📂 데이터 파일 업로드 (CSV)", expanded=True):
    col_u1, col_u2 = st.columns(2)
    with col_u1:, 3)
w_doc = st.sidebar.slider("문서 성실도 가중치", 0.0, 2.0, 1.0)

st.sidebar.divider()
st.sidebar.header
        app_file = st.file_uploader("지원자 데이터 업로드", type="csv")
    with col_u2:
        comp_file = st.file_uploader("기업 데이터 업로드", type="csv")

# --- 3. 핵심 엔진: 세부 점수 계산 함수 ---
def calculate_scores("📏 면접 배치 규칙")
mult = st.sidebar.number_input("채용인원 배수 (N)", value=2)
plus = st.sidebar.number_input("추가 상수 (M)", value=(app, comp):
    app_text = f"{app['experience_keywords']} {app['tool_1)

# --- 2. 데이터 업로드 ---
st.title("🎯 매칭 및 배치 통합 관리 시스템")
with stkeywords']} {app['essay_full_text']}".lower()
    
    major_s = w_.expander("📂 데이터 파일 업로드 (CSV)", expanded=True):
    c1, c2 = stmajor if str(app['major']).strip() in str(comp['recruitment_job_groups']).strip().columns(2)
    with c1: app_file = st.file_uploader("지원자 데이터 else 0
    
    req_list = [k.strip().lower() for k in str(comp['required_keywords_raw']).split(',') if k.strip()]
    req_match = sum(1 for 업로드", type="csv")
    with c2: comp_file = st.file_uploader("기업 데이터 k in req_list if k in app_text)
    req_s = req_match * w_ 업로드", type="csv")

# --- 3. 핵심 엔진: 점수 계산 함수 ---
def calculatereq
    
    pref_list = [k.strip().lower() for k in str(comp['preferred_scores(app, comp):
    app_text = f"{app['experience_keywords']} {app['tool_keywords']} {_keywords_raw']).split(',') if k.strip()]
    pref_match = sum(1 for k inapp['essay_full_text']}".lower()
    major_s = w_major if str(app pref_list if k in app_text)
    pref_s = pref_match * w_pref
['major']).strip() in str(comp['recruitment_job_groups']).strip() else 0
        
    exp_s = app['experience_count'] * w_exp
    train_s = appreq_list = [k.strip().lower() for k in str(comp['required_keywords_raw']).['job_training_count'] * w_train
    
    port_s = w_portfolio if app['has_portfolio'] else 0
    doc_s = app['document_completeness_score'] * w_doc
    split(',') if k.strip()]
    req_match = sum(1 for k in req_list if k
    pref_b = 0
    if app['preferred_company_1'] == comp['company_name']:
        pref_b = w_first
    elif app['preferred_company_2_3'] in app_text)
    req_s = req_match * w_req
    pref_list = [k.strip().lower() for k in str(comp['preferred_keywords_raw']).split(',') if k == comp['company_name']:
        pref_b = w_second

    total = major_s +.strip()]
    pref_match = sum(1 for k in pref_list if k in app_text)
     req_s + pref_s + exp_s + train_s + port_s + doc_s +pref_s = pref_match * w_pref
    exp_s = app['experience_count'] * pref_b
    reason = f"필수키워드 {req_match}개 일치(+{ w_exp + app['job_training_count'] * 2
    port_s = 15 if app['hasreq_s}), 활동 {app['experience_count'] + app['job_training_count']}건 반영,_portfolio'] else 0
    doc_s = app['document_completeness_score'] * w_ 문서성실도 {doc_s:.1f}점"
    if pref_b > 0: reason += f", {doc
    
    pref_b = 0
    if app['preferred_company_1'] == comp['company_name('1지망' if pref_b==w_first else '2지망')} 가중치 포함"']: pref_b = w_first
    elif app['preferred_company_2_3'] == comp['
    
    return {
        "job_fit_score": major_s, "required_match_company_name']: pref_b = w_second

    total = major_s + req_s + pref_s + exp_s + port_s + doc_s + pref_b
    reason = f"score": req_s, "preferred_match_score": pref_s,
        "major_match_score": major필수키워드 {req_match}개 일치(+{req_s}), 활동 {app['experience_count']}건 반영, 문서성실도 {doc_s:.1f}점"
    if pref_b >_s, "training_match_score": train_s, "experience_match_score": exp_s,
        "portfolio_score": port_s, "document_score": round(doc_s,  0: reason += f", {('1지망' if pref_b==w_first else '22), "preference_bonus_score": pref_b,
        "final_evaluation_score": round(total, 2), "score_reason_summary": reason
    }

# --- 4. 데이터 실행 및 배치 로직 ---
if app_file and comp_file:
    apps_df = pd.read지망')} 가점"
    
    return {
        "job_fit_score": major_s_csv(app_file).fillna('')
    comps_df = pd.read_csv(comp_file, "required_match_score": req_s, "preferred_match_score": pref_s,
        "experience_match_score": exp_s, "document_score": round(doc_s, 2), ").fillna('')
    
    apps_df['preferred_company_1'] = apps_df['preferred_preference_bonus_score": pref_b,
        "final_evaluation_score": round(total, 2), "score_company_1'].str.strip()
    apps_df['preferred_company_2_3'] = apps_df['preferred_company_2_3'].str.strip()
    comps_df['company_namereason_summary": reason
    }

# --- 4. 데이터 배치 로직 ---
if app_file'] = comps_df['company_name'].str.strip()
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
                        "company_name": comp['company_ and comp_file:
    apps_df = pd.read_csv(app_file).fillna('')
    comps_df = pd.read_csv(comp_file).fillna('')
    apps_df['preferred_company_1'] = apps_df['preferred_company_1'].str.strip()
    apps_df['name'],
                        "score": res['final_evaluation_score'],
                        "pref_level": 1 if app['preferred_company_1'] == comp['company_name'] else (2 if app['preferred_company_2_3'] == comp['company_name'] else 0)
                    })
            
            score_df = pd.DataFrame(score_matrix)
            assigned = {} 
            
            for cid in comps_df['company_id']:
                cap = comps_df[comps_df['company_idpreferred_company_2_3'] = apps_df['preferred_company_2_3'].str.strip()
    comps_df['company_name'] = comps_df['company_name'].str.strip()
    comps_df['capacity'] = (comps_df['recruitment_headcount_total'] * mult + plus).astype(int)

    if st.button("🚀 배치 알고리즘 실행 및 리포트 생성"):
        '] == cid]['capacity'].values[0]
                p1_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 1)].sort_with st.spinner("계산 중..."):
            # 매칭 스코어 매트릭스 생성
            score_matrix =values('score', ascending=False)
                for aid in p1_pool.head(cap)['applicant_id']:
                    assigned[aid] = cid
            
            unassigned_aids = set(apps_df['applicant_id']) - set(assigned.keys())
            for cid in comps_df['company_id']:
                filled = sum(1 for v in assigned.values() if v == cid)
                rem = comps_df[comps_df['company_id'] == cid]['capacity'].values[0] - filled []
            for _, app in apps_df.iterrows():
                for _, comp in comps_df.iterrows
                if rem > 0:
                    p2_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 2) & (score_df['applicant_id'].isin(unassigned_aids))].sort_values('score', ascending=False)
                    for aid in p2_pool.head(rem)['applicant_id']:
                        assigned[aid():
                    res = calculate_scores(app, comp)
                    score_matrix.append({
                        "] = cid
            
            final_summary = []
            for _, app in apps_df.iterrows():
                aid = app['applicant_id']
                target_cid = assigned.get(aid, None)
                
                if target_cid:
                    comp_row = comps_df[comps_df['company_id'] == target_cid].iloc[0]
                    assigned_cname = comp_row['companyapplicant_id": app['applicant_id'], "company_id": comp['company_id'],
                        "company_name": comp['company_name'], "score": res['final_evaluation_score'],
                        "pref_level": 1 if app['preferred_company_1'] == comp['company_name'] else (2 if app['preferred_company_2_3'] == comp['company_name'] else 0)
                    })
            _name']
                else:
                    c1_row = comps_df[comps_df['company_name'] == app['preferred_company_1']]
                    comp_row = c1_row.iloc[0] if notscore_df = pd.DataFrame(score_matrix)
            
            assigned = {}
            # Pass 1: 1순위 지망자 우선
            for cid in comps_df['company_id']:
                cap = comps_df[comps_df['company_id'] == cid]['capacity'].values[0]
                p1_pool = score_df c1_row.empty else comps_df.iloc[0]
                    assigned_cname = "미[(score_df['company_id'] == cid) & (score_df['pref_level'] == 1)].sort_values('score', ascending=False)
                for aid in p1_pool.head(cap)['applicant_id']: assigned[aid] = cid
            
            # Pass 2: 미배정자 2순위 지망
            unassigned = set(apps_df['applicant_id']) - set(assigned.keys())
            for cid in comps_df['company_id']:
                rem = comps_df[comps_df['company_id'] == cid]['capacity'].values[0] - sum(1 for v in assigned.values() if v ==배정"
                
                eval_data = calculate_scores(app, comp_row)
                final_summary.append({
                    "applicant_id": aid,
                    "applicant_name": app['applicant cid)
                if rem > 0:
                    p2_pool = score_df[(score_df['company_id'] == cid) & (score_df['pref_level'] == 2) & (score_df['applicant_id'].isin(unassigned))].sort_values('score', ascending=False)
                    for aid in p2_pool.head(rem)['applicant_id']: assigned[aid] = cid_name'],
                    "preferred_company_1": app['preferred_company_1'],
                    "preferred_company_2_3": app['preferred_company_2_3'],
                    "assigned_company":

            # 결과 요약 생성
            final_summary = []
            for _, app in apps_df.iterrows():
                aid = app['applicant_id']
                target_cid = assigned.get(aid, None)
                if target_ assigned_cname,
                    **eval_data
                })
            
            st.session_state['summary'] = pd.DataFrame(final_summary)
            st.session_state['comps'] = comps_cid:
                    comp_row = comps_df[comps_df['company_id'] == target_cid].iloc[0]
                    assigned_cname = comp_row['company_name']
                else:
                    assigned_cname = "미df
            st.success("배치 및 평가 리포트 생성이 완료되었습니다!")

    # --- 배정"
                    comp_row = comps_df[comps_df['company_name'] == app['preferred_company_15. 페이지별 레이아웃 구성 ---
    if 'summary' in st.session_state:
        summary_df = st']].iloc[0] if not comps_df[comps_df['company_name'] == app['preferred_company_.session_state['summary']

        if menu == "1. 지원자 평가 점수표":
            st.subheader("1']].empty else comps_df.iloc[0]
                
                eval_data = calculate_scores(app, comp_row)
                final_summary.append({
                    "applicant_id": aid, "applicant_name": app['applicant_name'],
                    "preferred_company_1": app['preferred_company_1'],
📑 지원자 세부 평가 점수 현황")
            st.markdown("지원자의 지망 기업과 실제 배정된 기업, 그리고 항목별 세부 점수를 비교해 보세요.")
            
            # 지망 정보(                    "preferred_company_2_3": app['preferred_company_2_3'], # 2순위 정보 추가
                    "assigned_company": assigned_cname,
                    **eval_data
                })
            1순위, 2순위) 컬럼 추가
            cols = [
                "applicant_id", "applicant_name",st.session_state['summary'] = pd.DataFrame(final_summary)
            st.session_state[' 
                "preferred_company_1", "preferred_company_2_3", # 지망 정보 추가
                "assigned_comps'] = comps_df
            st.success("배치 완료!")

    if 'summary' in st.company", "job_fit_score", "required_match_score", 
                "preferred_match_score", "experience_match_score", "document_score", "final_evaluation_score"
            ]
            
            # 가session_state:
        df = st.session_state['summary']

        # [1페이지: 지망 정보가 추가된 테이블]
        if menu == "1. 지원자 평가 점수표":
            st.subheader("📑 지원자 세부 평가 및 지망 정보 현황")
            # 지망 정보 컬독성을 위해 컬럼명 변경 (선택사항)
            display_df = summary_df[cols].rename(columns럼을 전면에 배치
            view_cols = [
                "applicant_id", "applicant_name",={
                "preferred_company_1": "1지망 기업",
                "preferred_company_2_3": 
                "preferred_company_1", "preferred_company_2_3", # 지망 정보 추가
                "assigned_ "2지망 기업",
                "assigned_company": "최종 배정 기업"
            })
            
            st.dataframe(display_df, use_container_width=True)
            
            csv = summary_company", "final_evaluation_score",
                "job_fit_score", "required_match_score", "experiencedf.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 전체 평가표 다운로드 (CSV)", data=csv, file_name="evaluation_summary_with_preference_match_score", "document_score"
            ]
            st.dataframe(df[view_cols.csv")

        elif menu == "2. 개인별 상세 리포트":
            st.subheader("👤 개인별 심층 평가 리포트")
            sel_aid = st.selectbox("지원자를 선택하세요], use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 결과 다운로드", data=csv, file_name="matching_summary.csv")

        # [2페이지: 개인 리포트]
        elif menu == "2", summary_df['applicant_id'].tolist(),
                                   format_func=lambda x: f"{x} ({summary_df[summary_df['applicant_id']==x]['applicant_name'].values[0]}). 개인별 상세 리포트":
            st.subheader("👤 개인별 평가 리포트")
            ")
            row = summary_df[summary_df['applicant_id'] == sel_aid].iloc[sel_aid = st.selectbox("지원자 선택", df['applicant_id'].tolist())
            row = df[0]
            
            c_left, c_right = st.columns([1, 1])
            with c_left:
                st.info(f"#### {row['applicant_name']} 후보자\n**1지망**: {row['df['applicant_id'] == sel_aid].iloc[0]
            c_l, c_r = st.columns(2)
            with c_l:
                st.info(f"### {row['applicant_name']}\preferred_company_1']}\n\n**현재 배정 기업**: {row['assigned_company']}")
                st.n**1지망**: {row['preferred_company_1']}\n**2지망**: {row['preferred_company_2_3']}\n**최종 배정**: {row['assigned_company']}")
metric("종합 평가점수", f"{row['final_evaluation_score']}점")
                st.write("**📝 점수 산출 근거**")
                st.success(row['score_reason_summary                st.metric("종합 점수", f"{row['final_evaluation_score']}점")
            '])
            
            with c_right:
                st.write("**📊 항목별 역량 분석**")
                chart_data = {
                    "직무적합": row['job_fit_score'], "필수매칭": row['required_match_score'],
                    "우대매칭": row['preferredwith c_r:
                st.bar_chart(pd.Series({
                    "직무": row['job_fit_score'], "필수": row['required_match_score'],
                    "경력": row['experience_match_score_match_score'], "경력점수": row['experience_match_score'],
                    "문서'], "문서": row['document_score'], "가점": row['preference_bonus_score']
                }))
            st점수": row['document_score'], "지망가점": row['preference_bonus_score']
.success(f"**산출 근거**: {row['score_reason_summary']}")

        # [3                }
                st.bar_chart(pd.Series(chart_data))

        elif menu == "3. 기업별 매칭 결과":
            st.subheader("🏢 기업별 면접 후보자 배정 명단페이지: 기업별 결과]
        elif menu == "3. 기업별 매칭 결과":
            st.subheader("🏢 기업")
            comps = st.session_state['comps']
            for _, c in comps.iterrows():
별 배정 명단")
            for _, c in st.session_state['comps'].iterrows():
                with                with st.expander(f"📍 {c['company_name']} (모집: {c['recruitment_headcount_total']} / 정원: {c['capacity']})"):
                    c_assigned st.expander(f"{c['company_name']} (정원: {c['capacity']})"):
                    c_res = df[df['assigned_company'] == c['company_name']]
                    st.table(c_ = summary_df[summary_df['assigned_company'] == c['company_name']]
                    if notres[["applicant_id", "applicant_name", "final_evaluation_score", "score_reason_summary c_assigned.empty:
                        # 기업별 화면에서도 지망 정보를 보여주면 배정의 정당성을 확인하기 좋습니다."]]) if not c_res.empty else st.write("배정 인원 없음")
