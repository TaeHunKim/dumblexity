import streamlit as st
import traceback
import asyncio
from st_copy import copy_button
import streamlit_mermaid as stmd
import re
import json

from utils import (
    resolve_all_urls_async,
    save_session,
    load_session,
    delete_session,
    get_all_sessions
)

from ai import (
    genai_stream_wrapper,
    generate_config,
    get_genai_client,
    gen_sdk_history,
    available_models,
    get_function_call_results
)

# --- Constants & Setup ---
st.set_page_config(page_title="Dumblexity", page_icon="🤖", layout="wide")

GLOBAL_THEME_COLOR = "dark"
MERMAID_THEME = "dark"

st.title("🤖 Dumblexity - AI Assistant")


# --- Session State Initialization ---
if "genai_client" not in st.session_state:
    st.session_state.genai_client = get_genai_client()

if "messages" not in st.session_state:
    st.session_state.messages = []

# [NEW] 현재 세션 이름을 추적하기 위한 상태 변수
if "current_session_name" not in st.session_state:
    st.session_state.current_session_name = None

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    selected_model = st.selectbox(
        "Choose Model:",
        available_models,
        index=0,
        help="Flash is faster and cheaper, Pro is more capable for complex tasks."
    )

# [CHANGED] 상호 배타적인 검색 모드 선택
    st.markdown("##### 🔍 Search Mode")
    search_mode = st.radio(
        "Select search mode:",
        ["Google Search", "External Search"],
        index=0,
        label_visibility="collapsed" # "Select search mode:" 레이블 숨기기
    )

    # [NEW] 상태 변수 초기화
    use_google_web_search = False
    use_google_map_search = False
    use_tavily_search = False
    use_extraction = False

    # [NEW] 선택된 모드에 따라 UI 분기
    if search_mode == "Google Search":
        use_google_web_search = st.checkbox("웹 검색 (Web Search)", value=True)
        use_google_map_search = st.checkbox("지도 검색 (Map Search)", value=True)
    
    elif search_mode == "External Search":
        use_tavily_search = st.checkbox("웹 검색 (Tavily Search)", value=True)
        use_extraction = st.checkbox("웹/YT 추출(extraction)", value=True)

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
            gen_sdk_history(role, msg["content"])
        )
    
    st.session_state.messages.append({"role": "user", "content": prompt})

    # [NEW] 사용자 메시지가 추가된 직후에도 자동 저장 (선택 사항이지만, 응답 전 앱이 멈출 경우 대비)
    if st.session_state.current_session_name:
        save_session(st.session_state.current_session_name, silent=True)

    with st.chat_message("assistant"):
        with st.spinner("🤖 Thinking..."):
            try:
                total_grounding_chunks = []
                total_function_calls = []
                
                config_payload = generate_config(
                    google_web_search=use_google_web_search, 
                    google_map_search=use_google_map_search,
                    tavily_search=use_tavily_search,
                    extraction=use_extraction
                )

                chat_session = st.session_state.genai_client.chats.create(
                    model=selected_model,
                    config=config_payload,
                    history=sdk_history
                )
                
                response_stream = chat_session.send_message_stream(prompt)
                full_response_text = st.write_stream(genai_stream_wrapper(response_stream, total_grounding_chunks, total_function_calls))

                # Not yet used for extract_web_page and extract_youtube_transcript as they are called automatically within the model response

                #if total_function_calls:
                #    st.info("🔧 Calling functions...")
                #    function_results = get_function_call_results(total_function_calls)
                #    response_stream2 = chat_session.send_message_stream(function_results)
                #    total_function_calls.clear()
                #    full_response_text += st.write_stream(genai_stream_wrapper(response_stream2, total_grounding_chunks, total_function_calls))

                citation_text = ""
                if total_grounding_chunks:
                    with st.spinner("🔍 Verifying citations..."):
                        unique_web_chunks = {}
                        unique_map_chunks = {}
                        for chunk in total_grounding_chunks:
                            if chunk.web and chunk.web.uri:
                                unique_web_chunks[chunk.web.uri] = chunk.web.title or "Untitled"
                            if chunk.maps and chunk.maps.uri:
                                unique_map_chunks[chunk.maps.uri] = chunk.maps.title or "Untitled"

                        if unique_web_chunks:
                            web_citation_text = "\n\n#### Web Citations\n"
                            
                            urls_to_fetch = list(unique_web_chunks.keys())
                            
                           # --- [FIX START] ---
                            # [CHANGED] asyncio.run()을 사용하여 비동기 함수를 동기식으로 호출
                            # 이것이 동기(Streamlit) 코드와 비동기(httpx) 코드를 연결하는 다리입니다.
                            resolved_urls = asyncio.run(resolve_all_urls_async(urls_to_fetch))
                            # --- [FIX END] ---

                            # [NEW] 병렬로 받아온 결과를 사용하여 Citatation 텍스트 구성
                            for i, initial_uri in enumerate(urls_to_fetch):
                                title = unique_web_chunks[initial_uri]
                                resolved_uri = resolved_urls[i]
                                web_citation_text += f"{i+1}. [{title}]({resolved_uri})\n"
                            
                            st.markdown(web_citation_text)
                            citation_text += web_citation_text
                        if unique_map_chunks:
                            map_citation_text = "\n\n#### Map Citations\n"
                            for i, (uri, title) in enumerate(unique_map_chunks.items()):
                                map_citation_text += f"{i+1}. [{title}]({uri})\n"
                            
                            st.markdown(map_citation_text)
                            citation_text += map_citation_text

                if total_function_calls:
                    with st.spinner("🔍 Verifying citations from function calls..."):
                        unique_web_chunks = {}
                        for func_call in total_function_calls:
                            parts = func_call.parts
                            if parts:
                                for part in parts:
                                    func_response = part.function_response
                                    if func_response:
                                        #print(f"Function response: {func_response}")
                                        response = func_response.response
                                        output = response.get("result", response) if response else None
                                        if isinstance(output, str):
                                            try:
                                                output = json.loads(output)
                                            except json.JSONDecodeError:
                                                pass
                                        if output and 'results' in output:
                                            for res in output['results']:
                                                uri = res.get("url")
                                                title = res.get("title", "Untitled")
                                                if uri:
                                                    unique_web_chunks[uri] = title
                                        elif output and isinstance(output, list) and 'url' in output[0]:
                                            for res in output:
                                                uri = res.get("url")
                                                title = res.get('title', uri)  # Use last part of URL as title if not provided
                                                if uri:
                                                    unique_web_chunks[uri] = title
                        if unique_web_chunks:
                            func_citation_text = "\n\n#### Function Call Citations\n"

                            for i, (uri, title) in enumerate(unique_web_chunks.items()):
                                func_citation_text += f"{i+1}. [{title}]({uri})\n"
                            
                            st.markdown(func_citation_text)
                            citation_text += func_citation_text

                final_content = full_response_text + citation_text

                regex_pattern = r"```mermaid\s*?(.*?)```"
                mermaid_blocks = re.findall(regex_pattern, final_content, re.DOTALL)
                if mermaid_blocks:
                    st.markdown("#### Mermaid Diagrams")    
                    for block in mermaid_blocks:
                        stmd.st_mermaid(block)

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