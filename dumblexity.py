import streamlit as st
from google import genai
from google.genai import types
import traceback
import urllib.request
import os
import json
import glob

# --- Constants & Setup ---
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

st.set_page_config(page_title="Dumblexity", page_icon="🤖", layout="wide")
st.title("🤖 Dumblexity - AI Assistant")

# --- Helper Functions ---
def get_final_url_urllib(initial_url):
    try:
        req = urllib.request.Request(initial_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            return response.geturl()
    except Exception as e:
        return initial_url

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

def save_session(session_name):
    if not session_name:
        st.sidebar.error("Session name cannot be empty.")
        return
    safe_name = "".join([c for c in session_name if c.isalnum() or c in (' ', '-', '_')]).strip()
    file_path = os.path.join(SESSION_DIR, f"{safe_name}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
        st.sidebar.success(f"Session '{safe_name}' saved!")
    except Exception as e:
        st.sidebar.error(f"Failed to save session: {e}")

def load_session(session_name):
    file_path = os.path.join(SESSION_DIR, f"{session_name}.json")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            st.session_state.messages = json.load(f)
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Failed to load session: {e}")

def delete_session(session_name):
    file_path = os.path.join(SESSION_DIR, f"{session_name}.json")
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            st.sidebar.success(f"Session '{session_name}' deleted!")
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Failed to delete session: {e}")

# --- Session State Initialization ---
if "genai_client" not in st.session_state:
    st.session_state.genai_client = genai.Client()

if "messages" not in st.session_state:
    st.session_state.messages = []

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
    
    # [NEW] Model Selection
    selected_model = st.selectbox(
        "Choose Model:",
        ["gemini-2.5-flash", "gemini-2.5-pro"],
        index=0,
        help="Flash is faster and cheaper, Pro is more capable for complex tasks."
    )
    
    st.divider()
    
    st.header("🗂️ Session Management")
    if st.button("🧹 Clear Current Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    save_name = st.text_input("Save as:", placeholder="Enter session name...")
    if st.button("💾 Save Session", use_container_width=True):
        save_session(save_name)

    st.divider()

    existing_sessions = get_all_sessions()
    if existing_sessions:
        selected_session = st.selectbox("Select a session:", existing_sessions)
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

    with st.chat_message("assistant"):
        try:
            total_grounding_chunks = []
            
            # [CHANGED] Use the selected model from sidebar
            chat_session = st.session_state.genai_client.chats.create(
                model=selected_model,
                config=generate_config,
                history=sdk_history
            )
            
            response_stream = chat_session.send_message_stream(prompt)
            full_response_text = st.write_stream(genai_stream_wrapper(response_stream, total_grounding_chunks))

            citation_text = ""
            if total_grounding_chunks:
                unique_chunks = {}
                for chunk in total_grounding_chunks:
                    if chunk.web and chunk.web.uri:
                         unique_chunks[chunk.web.uri] = chunk

                if unique_chunks:
                    citation_text += "\n\n#### Citations\n"
                    for i, chunk in enumerate(unique_chunks.values()):
                        title = chunk.web.title or "Untitled"
                        uri = get_final_url_urllib(chunk.web.uri)
                        citation_text += f"{i+1}. [{title}]({uri})\n"
                    st.markdown(citation_text)

            final_content = full_response_text + citation_text
            st.session_state.messages.append({"role": "assistant", "content": final_content})

        except Exception as e:
            st.error(f"An error occurred: {e}")
            traceback.print_exc()