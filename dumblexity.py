import streamlit as st
from google import genai
from google.genai import types
import traceback
import os
import json
import glob
import asyncio
import httpx
from st_copy import copy_button

# --- Constants & Setup ---
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

st.set_page_config(page_title="Dumblexity", page_icon="🤖", layout="wide")
st.title("🤖 Dumblexity - AI Assistant")

async def get_final_url_httpx(initial_url, client):
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
        tasks = [get_final_url_httpx(uri, client) for uri in urls_to_fetch]
        # [NOTE] gather는 작업 목록을 받아 동시에 실행합니다.
        resolved_urls = await asyncio.gather(*tasks)
        return resolved_urls

def genai_stream_wrapper(response_stream, grounding_chunks_list):
    for chunk in response_stream:
        if chunk.candidates:
            for cand in chunk.candidates:
                if cand.grounding_metadata and cand.grounding_metadata.grounding_chunks:
                    grounding_chunks_list.extend(cand.grounding_metadata.grounding_chunks)
        if chunk.text:
            yield chunk.text

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

# --- Session State Initialization ---
if "genai_client" not in st.session_state:
    st.session_state.genai_client = genai.Client()

if "messages" not in st.session_state:
    st.session_state.messages = []

# [NEW] 현재 세션 이름을 추적하기 위한 상태 변수
if "current_session_name" not in st.session_state:
    st.session_state.current_session_name = None

# --- Configuration ---
grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)
generate_config = types.GenerateContentConfig(
    tools=[grounding_tool],
    system_instruction="You are an AI assistant. You MUST use the Google Search tool for any query that requires up-to-date information or external facts. Always provide citations when you use search results.",
    max_output_tokens=65536,
    temperature=0.2,
    thinking_config=types.ThinkingConfig(thinking_budget=-1)
)

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    selected_model = st.selectbox(
        "Choose Model:",
        ["gemini-2.5-flash", "gemini-2.5-pro"],
        index=0,
        help="Flash is faster and cheaper, Pro is more capable for complex tasks."
    )
    
    st.divider()
    
    st.header("🗂️ Session Management")
    
    # [NEW] 현재 세션 상태 표시
    if st.session_state.current_session_name:
        st.markdown(f"**Current:** `{st.session_state.current_session_name}`")
    else:
        st.markdown("*Unsaved Chat*")

    if st.button("🧹 Clear Current Chat", use_container_width=True):
        st.session_state.messages = []
        # [NEW] 현재 세션 이름 초기화
        st.session_state.current_session_name = None
        st.rerun()

    st.divider()

    save_name = st.text_input("Save as:", 
                              # [CHANGED] 만약 현재 세션 이름이 있다면 기본값으로 제안
                              value=st.session_state.current_session_name or "",
                              placeholder="Enter session name...")
    
    # [CHANGED] silent=False로 명시적 호출 (수동 저장이므로 알림 표시)
    if st.button("💾 Save Session", use_container_width=True):
        save_session(save_name, silent=False)

    st.divider()

    existing_sessions = get_all_sessions()
    if existing_sessions:
        
        # [NEW] 현재 세션이 목록에 있다면 기본값으로 선택
        default_index = None
        if st.session_state.current_session_name in existing_sessions:
            default_index = existing_sessions.index(st.session_state.current_session_name)
        
        selected_session = st.selectbox("Select a session:", 
                                        existing_sessions, 
                                        index=default_index)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📂 Load", use_container_width=True):
                load_session(selected_session)
        with col2:
                if st.button("🗑️ Delete", use_container_width=True):
                    delete_session(selected_session)
    else:
        st.markdown("*No saved sessions found.*")

# --- Display Chat History ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # [NEW] 어시스턴트의 메시지(봇 답변) 아래에만 복사 버튼 추가
        if message["role"] == "assistant":
            copy_button(message["content"],
                        tooltip="Copy this text",
                        copied_label="Copied!",
                        icon="📋")

# --- Chat Input & Response Handling ---
if prompt := st.chat_input("Ask me anything..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    
    sdk_history = []
    for msg in st.session_state.messages:
        role = "user" if msg["role"] == "user" else "model"
        sdk_history.append(
            types.Content(role=role, parts=[types.Part(text=msg["content"])])
        )
    
    st.session_state.messages.append({"role": "user", "content": prompt})

    # [NEW] 사용자 메시지가 추가된 직후에도 자동 저장 (선택 사항이지만, 응답 전 앱이 멈출 경우 대비)
    if st.session_state.current_session_name:
        save_session(st.session_state.current_session_name, silent=True)

    with st.chat_message("assistant"):
        with st.spinner("🤖 Thinking..."):
            try:
                total_grounding_chunks = []
                
                chat_session = st.session_state.genai_client.chats.create(
                    model=selected_model,
                    config=generate_config,
                    history=sdk_history
                )
                
                response_stream = chat_session.send_message_stream(prompt)
                full_response_text = st.write_stream(genai_stream_wrapper(response_stream, total_grounding_chunks))
                citation_text = ""
                with st.spinner("🔍 Verifying citations..."):
                    if total_grounding_chunks:
                        unique_chunks = {}
                        for chunk in total_grounding_chunks:
                            if chunk.web and chunk.web.uri:
                                unique_chunks[chunk.web.uri] = chunk.web.title or "Untitled"

                        if unique_chunks:
                            citation_text += "\n\n#### Citations\n"
                            
                            urls_to_fetch = list(unique_chunks.keys())
                            
                           # --- [FIX START] ---
                            # [CHANGED] asyncio.run()을 사용하여 비동기 함수를 동기식으로 호출
                            # 이것이 동기(Streamlit) 코드와 비동기(httpx) 코드를 연결하는 다리입니다.
                            resolved_urls = asyncio.run(resolve_all_urls_async(urls_to_fetch))
                            # --- [FIX END] ---

                            # [NEW] 병렬로 받아온 결과를 사용하여 Citatation 텍스트 구성
                            for i, initial_uri in enumerate(urls_to_fetch):
                                title = unique_chunks[initial_uri]
                                resolved_uri = resolved_urls[i]
                                citation_text += f"{i+1}. [{title}]({resolved_uri})\n"
                            
                            st.markdown(citation_text)

                final_content = full_response_text + citation_text
                copy_button(final_content,
                            tooltip="Copy this text",
                            copied_label="Copied!",
                            icon="📋")
                st.session_state.messages.append({"role": "assistant", "content": final_content})

                # --- [NEW] 자동 저장 트리거 ---
                # 어시스턴트의 응답이 message에 추가된 후,
                # 현재 세션 이름이 존재한다면 (즉, 로드했거나 한 번이라도 저장했다면)
                # 'silent=True'로 자동 저장합니다.
                if st.session_state.current_session_name:
                    save_session(st.session_state.current_session_name, silent=True)
                # --- [NEW] End Auto-save ---

            except Exception as e:
                st.error(f"An error occurred: {e}")
                traceback.print_exc()