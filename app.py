import streamlit as st
import pandas as pd
import numpy as np

# --- 페이지 설정 ---
st.set_page_config(layout="wide", page_title="미청 매칭 및 평가 시스템")

st.title("🎯 지원자 개인별 상세 평가 및 배치 시스템")

# --- 1. 가중치 설정 (사이드바) ---
st.sidebar.header("⚖️ 점수 가중치 설정")
w = {
    "first_choice": st.sidebar.number_input("1순위 가산점", value=50),
    "second_choice": st.sidebar.number_input("2순위 가산점", value=20),
    "required": st.sidebar.slider("필수요건 가중치", 0, 20, 10),
    "preferred": st.sidebar.slider("우대요건 가중치", 0, 20, 5),
    "portfolio": st.sidebar.number_input("포트폴리오 가점", value=15),
    "doc": st.sidebar.slider("문서 완성도 가중치", 0.0, 2.0, 1.0)
}

# --- 2. 데이터 업로드 ---
col1, col2 = st.columns(2)
with col1:
    app_file = st.file_uploader("지원자 데이터 업로드 (CSV)", type="csv")
with col2:
    comp_file = st.file_uploader("기업 데이터 업로드 (CSV)", type="csv")

# --- 3. 핵심 계산 엔진 (상세 점수 포함) ---
def get_detailed_evaluation(app, comp, rules):
    """지원자 1명과 기업 1개 사이의 세부 점수 산출"""
    
    # 세부 항목 계산
    req_match = sum(1 for k in str(comp['required_keywords_raw']).split(',') if k.strip() in str(app['experience_keywords']))
    pref_match = sum(1 for k in str(comp['preferred_keywords_raw']).split(',') if k.strip() in str(app['experience_keywords']))
    
    scores = {
        "job_fit_score": 10 if str(app['major']) in str(comp['recruitment_job_groups']) else 0,
        "required_match_score": req_match * rules['required'],
        "preferred_match_score": pref_match * rules['preferred'],
        "portfolio_score": rules['portfolio'] if app['has_portfolio'] else 0,
        "document_score": app['document_completeness_score'] * rules['doc'],
        "preference_bonus_score": rules['first_choice'] if app['preferred_company_1'] == comp['company_name'] 
                                   else (rules['second_choice'] if app['preferred_company_2_3'] == comp['company_name'] else 0)
    }
    
    final_score = sum(scores.values())
    
    # 산출 근거 생성
    reason = f"[{comp['company_name']} 기준] "
    if scores['preference_bonus_score'] > 0: reason += f"지망 가산점 적용, "
    reason += f"필수 키워드 {req_match}개 일치, "
    if app['has_portfolio']: reason += "포트폴리오 가점 부여. "
    
    return scores, final_score, reason

# --- 4. 메인 로직 및 UI ---
if app_file and comp_file:
    apps_df = pd.read_csv(app_file)
    comps_df = pd.read_csv(comp_file)

    # 전체 평가 요약 데이터 생성 (배치 전 미리 계산)
    if st.button("📊 개인별 평가점수 및 배치 실행"):
        all_evals = []
        # 각 지원자별로 지망 기업들에 대한 점수 미리 계산
        for _, app in apps_df.iterrows():
            # 1지망 기업 찾기
            c1 = comps_df[comps_df['company_name'] == app['preferred_company_1']]
            if not c1.empty:
                comp = c1.iloc[0]
                det_scores, final, reason = get_detailed_evaluation(app, comp, w)
                eval_row = {
                    "applicant_id": app['applicant_id'],
                    "applicant_name": app['applicant_name'],
                    "target_company_name": comp['company_name'],
                    "final_evaluation_score": final,
                    "score_reason_summary": reason,
                    **det_scores
                }
                all_evals.append(eval_row)
        
        st.session_state['eval_summary'] = pd.DataFrame(all_evals)
        st.success("평가 및 배치가 완료되었습니다.")

    # --- 5. 상세 결과 화면 ---
    if 'eval_summary' in st.session_state:
        st.divider()
        st.subheader("👤 지원자별 상세 평가 리포트")
        
        selected_app_id = st.selectbox("지원자 선택", st.session_state['eval_summary']['applicant_id'].unique())
        
        if selected_app_id:
            row = st.session_state['eval_summary'][st.session_state['eval_summary']['applicant_id'] == selected_app_id].iloc[0]
            
            # 리포트 카드 UI
            with st.container():
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.metric("종합 평가점수", f"{row['final_evaluation_score']:.1f}점")
                    st.write(f"**대상 기업**: {row['target_company_name']}")
                with c2:
                    st.info(f"**점수 산출 근거**: {row['score_reason_summary']}")
                
                # 세부 점수 표
                st.write("### 세부 항목별 점수")
                score_data = {
                    "항목": ["직무 적합도", "필수 매칭", "우대 매칭", "포트폴리오", "문서 완성도", "지망 가산점"],
                    "점수": [row['job_fit_score'], row['required_match_score'], row['preferred_match_score'], 
                           row['portfolio_score'], row['document_score'], row['preference_bonus_score']]
                }
                st.table(pd.DataFrame(score_data))

        # 전체 테이블 다운로드
        st.divider()
        st.subheader("📥 전체 평가 요약 데이터 (CSV)")
        csv_data = st.session_state['eval_summary'].to_csv(index=False).encode('utf-8-sig')
        st.download_button("평가 데이터 다운로드", data=csv_data, file_name="applicant_evaluation_summary.csv")
