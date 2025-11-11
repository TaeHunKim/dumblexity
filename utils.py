import streamlit as st
import os
import json
import glob
import asyncio
import httpx

SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

async def _get_final_url_httpx(initial_url, client):
    try:
        # GET 요청을 보내고 리디렉션을 자동으로 따릅니다.
        response = await client.get(initial_url, headers={'User-Agent': 'Mozilla/5.0'}, follow_redirects=True, timeout=10.0)
        # 최종 URL 반환
        return str(response.url)
    except Exception as e:
        # 오류 발생 시 원본 URL 반환
        return initial_url

# [NEW] 비동기 URL을 가져오는 로직을 래핑할 별도의 async 함수
async def resolve_all_urls_async(urls_to_fetch):
    async with httpx.AsyncClient() as client:
        tasks = [_get_final_url_httpx(uri, client) for uri in urls_to_fetch]
        # [NOTE] gather는 작업 목록을 받아 동시에 실행합니다.
        resolved_urls = await asyncio.gather(*tasks)
        return resolved_urls

def get_all_sessions():
    files = glob.glob(os.path.join(SESSION_DIR, "*.json"))
    return [os.path.splitext(os.path.basename(f))[0] for f in files]

# [CHANGED] 'silent' 매개변수 추가 (자동 저장 시 알림을 띄우지 않기 위함)
def save_session(session_name, silent=False):
    if not session_name:
        if not silent:
            st.sidebar.error("Session name cannot be empty.")
        return
    safe_name = "".join([c for c in session_name if c.isalnum() or c in (' ', '-', '_')]).strip()
    
    # [NEW] 안전한 이름이 비어있는 경우 (예: 특수문자로만 입력)
    if not safe_name:
        if not silent:
            st.sidebar.error("Valid session name is required.")
        return

    file_path = os.path.join(SESSION_DIR, f"{safe_name}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
        
        # [NEW] 현재 세션 이름 업데이트
        st.session_state.current_session_name = safe_name
        
        if not silent:
            st.sidebar.success(f"Session '{safe_name}' saved!")
    except Exception as e:
        if not silent:
            st.sidebar.error(f"Failed to save session: {e}")

def load_session(session_name):
    file_path = os.path.join(SESSION_DIR, f"{session_name}.json")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            st.session_state.messages = json.load(f)
        
        # [NEW] 현재 세션 이름 업데이트
        st.session_state.current_session_name = session_name
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Failed to load session: {e}")

def delete_session(session_name):
    file_path = os.path.join(SESSION_DIR, f"{session_name}.json")
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            
            # [NEW] 만약 현재 세션을 삭제했다면, current_session_name 초기화
            if st.session_state.current_session_name == session_name:
                st.session_state.current_session_name = None
                
            st.sidebar.success(f"Session '{session_name}' deleted!")
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Failed to delete session: {e}")

