import streamlit as st
import requests
import json
import datetime
import re

APP_VERSION = "Chatbot Free"
DEFAULT_MODEL_NAME = "Meta Llama 3 8B Instruct"
DEFAULT_SYSTEM_PROMPT = "Anda adalah asisten AI yang serbaguna dan ramah. Selalu odgovori dalam Bahasa Indonesia kecuali diminta lain."

AVAILABLE_MODELS = {
    "Meta Llama 3 8B Instruct": {"id": "meta-llama/llama-3-8b-instruct", "vision": False, "max_tokens": 8192, "free": True},
    "DeepSeek Chat V3 0324 (free)": {"id": "deepseek/deepseek-chat-v3-0324:free", "vision": False, "max_tokens": 163840, "free": True}
}

PREDEFINED_PERSONAS = {
    "Asisten Umum (Default)": DEFAULT_SYSTEM_PROMPT,
    "Penulis Kreatif": "Anda adalah seorang penulis cerita dan puisi yang imajinatif...",
    "Pakar Sejarah": "Anda adalah seorang sejarawan dengan pengetahuan luas...",
    "Penerjemah Ahli": "Anda adalah penerjemah bahasa profesional...",
    "Guru Matematika": "Anda adalah seorang guru matematika yang sabar..."
}

TXT_PATTERN_FULL_TS = re.compile(r"\[(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\]\s*(User|Assistant|System|Bot):\s*([\s\S]*)", re.IGNORECASE)
TXT_PATTERN_TIME_ONLY_TS = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]\s*(User|Assistant|System|Bot):\s*([\s\S]*)", re.IGNORECASE)
MD_BLOCK_PATTERN_FULL_TS = re.compile(r"\*(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\*\s*-\s*\*\*(User|Assistant|System|Bot)\*\*:\s*\n?([\s\S]*)", re.IGNORECASE)
MD_BLOCK_PATTERN_TIME_ONLY_TS = re.compile(r"\*(\d{2}:\d{2}:\d{2})\*\s*-\s*\*\*(User|Assistant|System|Bot)\*\*:\s*\n?([\s\S]*)", re.IGNORECASE)

if not AVAILABLE_MODELS: st.error("Kritis: Tidak ada model."); st.stop()
if DEFAULT_MODEL_NAME not in AVAILABLE_MODELS:
    DEFAULT_MODEL_NAME = list(AVAILABLE_MODELS.keys())[0] if AVAILABLE_MODELS else None
    if not DEFAULT_MODEL_NAME: st.error("Kritis: Tidak ada model default."); st.stop()

MAX_HISTORY_MESSAGES_TO_SEND = 10

try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
except (FileNotFoundError, KeyError):
    st.error("CRITICAL ERROR: `OPENROUTER_API_KEY` tidak ditemukan di Streamlit Secrets.")
    st.markdown("Pastikan sudah ditambahkan di Settings -> Secrets di Streamlit Cloud.")
    st.stop()

def update_system_prompt_from_persona_callback():
    selected_persona_key = st.session_state.get("persona_selector_key_v119", "Asisten Umum (Default)")
    st.session_state.selected_persona_name = selected_persona_key
    st.session_state.system_prompt = PREDEFINED_PERSONAS.get(selected_persona_key, DEFAULT_SYSTEM_PROMPT)

def handle_rename_chat_submit(chat_id_to_rename, input_key):
    new_name = st.session_state[input_key]
    if new_name and new_name.strip():
        if chat_id_to_rename in st.session_state.all_chats:
            st.session_state.all_chats[chat_id_to_rename]['title'] = new_name.strip()
            st.session_state.all_chats[chat_id_to_rename]['title_is_fixed'] = True
            st.toast(f"Chat diubah nama menjadi '{new_name.strip()}'", icon="✏️")
        else:
            st.warning("Gagal rename: Chat ID tidak ditemukan.")
    else:
        st.warning("Nama chat tidak boleh kosong.")
    st.session_state.renaming_chat_id = None

def get_current_chat_messages():
    if st.session_state.current_chat_id and st.session_state.current_chat_id in st.session_state.all_chats:
        return st.session_state.all_chats[st.session_state.current_chat_id]["messages"]
    return []

def update_chat_title_from_prompt(chat_id, user_prompt_content):
    if chat_id in st.session_state.all_chats and \
       not st.session_state.all_chats[chat_id].get("title_is_fixed", False):
        words = user_prompt_content.split()
        title = " ".join(words[:5])
        if len(words) > 5: title += "..."
        current_chat_info = st.session_state.all_chats[chat_id]
        is_default_or_placeholder_title = current_chat_info['title'].startswith("Chat Baru") or \
                                           current_chat_info['title'].startswith("Upload:") or \
                                           current_chat_info['title'] == "Chat Awal"
        if not title.strip():
            if is_default_or_placeholder_title :
                title = f"Chat ({current_chat_info['created_at'].strftime('%H:%M:%S')})"
            else:
                return
        st.session_state.all_chats[chat_id]['title'] = title

def append_message_to_current_chat(role, content_text, timestamp=None):
    chat_id = st.session_state.current_chat_id
    if chat_id and chat_id in st.session_state.all_chats:
        messages = st.session_state.all_chats[chat_id]["messages"]
        current_time = timestamp or datetime.datetime.now()
        messages.append({
            "role": role, "content_text": content_text, "timestamp": current_time
        })
        if role == "user":
            update_chat_title_from_prompt(chat_id, content_text)

def get_bot_response_stream(messages_for_api, selected_model_id, temperature):
    payload = { "model": selected_model_id, "messages": messages_for_api, "stream": True, "temperature": temperature }
    headers = { "Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": st.session_state.get("http_referer", "http://localhost:8501"), "X-Title": f"Ai Chatbot ({st.session_state.get('app_version', APP_VERSION)})" }
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    response_obj = None
    try:
        response_obj = requests.post(API_URL, headers=headers, json=payload, stream=True, timeout=180)
        response_obj.raise_for_status()
        for line in response_obj.iter_lines():
            if st.session_state.get("stop_generating", False): yield "🛑 Generasi dihentikan pengguna."; break
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    json_str = decoded_line[len("data: "):]
                    if json_str.strip() == "[DONE]": break
                    try:
                        data = json.loads(json_str)
                        if data.get("choices") and data["choices"]:
                            delta = data["choices"][0].get("delta", {})
                            chunk = delta.get("content")
                            if chunk: yield chunk
                    except json.JSONDecodeError: pass
    except requests.exceptions.HTTPError as http_err:
        error_detail = ""
        if response_obj and response_obj.text:
            try: error_json = response_obj.json(); error_detail = f" API: {error_json.get('error', {}).get('message', response_obj.text[:100])}"
            except json.JSONDecodeError: error_detail = f" Detail: {response_obj.text[:100]}"
        yield f"🛑 HTTP error {response_obj.status_code if response_obj else ''}: {http_err}.{error_detail}"
    except Exception as e: yield f"🛑 Kesalahan: {str(e)[:100]}"

def format_timestamp_display(ts_obj):
    if isinstance(ts_obj, str):
        try: ts_obj = datetime.datetime.fromisoformat(ts_obj)
        except ValueError: return ts_obj
    if isinstance(ts_obj, datetime.datetime): return ts_obj.strftime("%H:%M:%S")
    return "N/A"

def format_timestamp_export(ts_obj):
    if isinstance(ts_obj, str):
        try: ts_obj = datetime.datetime.fromisoformat(ts_obj)
        except ValueError: return ts_obj
    if isinstance(ts_obj, datetime.datetime): return ts_obj.strftime("%Y-%m-%d %H:%M:%S")
    return "N/A"

def prepare_messages_for_api(chat_messages_list, system_prompt):
    messages = [{"role": "system", "content": system_prompt}]
    relevant_history = chat_messages_list[-(MAX_HISTORY_MESSAGES_TO_SEND):]
    for msg in relevant_history: messages.append({"role": msg["role"], "content": str(msg.get("content_text",""))})
    return messages

def handle_automation_command(command_input, current_model_info, chat_messages_list):
    parts = command_input.strip().split(" ", 1)
    command = parts[0].lower()
    if command == "!help" or command == "!bantuan":
        return """**Perintah:**\n- `!help`/`!bantuan`: Bantuan.\n- `!info_model`: Info model.\n- `!waktu`: Waktu.\n- `!summarize_chat`: Rangkum chat."""
    elif command == "!info_model":
        model_id_val = current_model_info.get('id', 'N/A')
        max_tokens_val = current_model_info.get('max_tokens', 'N/A')
        return f"**Info Model:**\n- Nama: {st.session_state.selected_model_name}\n- ID: `{model_id_val}`\n- Max Tokens: {max_tokens_val}"
    elif command == "!waktu":
        return f"Waktu server: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    elif command == "!summarize_chat":
        if not chat_messages_list: return "Riwayat chat kosong."
        conversation_text = "\n".join([f"{msg['role']}: {msg['content_text']}" for msg in chat_messages_list if msg.get('content_text') and not str(msg.get('content_text', '')).startswith("🛑")])
        if not conversation_text.strip(): return "Tidak ada konten chat untuk dirangkum."
        st.info(f"Merangkum {len(chat_messages_list)} pesan...")
        summary_prompt = [{"role": "system", "content": "Summarize this conversation concisely:"}, {"role": "user", "content": conversation_text}]
        st.session_state.pending_llm_automation = {"messages": summary_prompt, "model_id": current_model_info.get("id", AVAILABLE_MODELS[DEFAULT_MODEL_NAME]["id"]), "is_summary_for_current_chat": True}
        return None
    return f"Perintah '{command}' tidak dikenal. Ketik `!help`."

def parse_json_history(json_string_content):
    try:
        raw_history = json.loads(json_string_content)
        processed_history = []
        if not isinstance(raw_history, list): st.error("Format JSON tidak valid: harus list."); return None
        for item_raw in raw_history:
            if isinstance(item_raw, dict) and 'role' in item_raw and item_raw.get('content_text') is not None and 'timestamp' in item_raw:
                role, ts_data = item_raw["role"], item_raw.get('timestamp')
                if role not in ["user", "assistant", "system"]: st.warning(f"Role tidak valid '{role}' dilewati."); continue
                ts_obj = datetime.datetime.now() 
                if isinstance(ts_data, str):
                    try: ts_obj = datetime.datetime.fromisoformat(ts_data)
                    except ValueError: 
                        try: ts_obj = datetime.datetime.strptime(ts_data, "%Y-%m-%d %H:%M:%S")
                        except ValueError: st.warning(f"Timestamp JSON '{ts_data}' tidak dikenal, pakai waktu sekarang.")
                elif isinstance(ts_data, (int, float)): ts_obj = datetime.datetime.fromtimestamp(ts_data)
                else: st.warning(f"Tipe timestamp JSON '{type(ts_data)}' tidak dikenal, pakai waktu sekarang.")
                processed_history.append({"role": role, "content_text": str(item_raw["content_text"]), "timestamp": ts_obj})
            else: st.warning(f"Item JSON tidak valid: {str(item_raw)[:100]}")
        return processed_history
    except Exception as e: st.error(f"Error proses JSON: {e}"); return None

def parse_txt_history(txt_string_content):
    processed_history, today_date = [], datetime.date.today()
    for msg_str in txt_string_content.strip().split("\n\n"):
        if not msg_str.strip(): continue
        match, ts_obj, role_str, content = TXT_PATTERN_FULL_TS.match(msg_str.strip()), None, None, None
        if match:
            ts_str_val, role_str, content = match.groups()
            try: ts_obj = datetime.datetime.strptime(ts_str_val, "%Y-%m-%d %H:%M:%S")
            except ValueError: st.warning(f"Timestamp TXT (full) '{ts_str_val}' tidak valid."); continue
        else:
            match_time = TXT_PATTERN_TIME_ONLY_TS.match(msg_str.strip())
            if match_time:
                time_str, role_str, content = match_time.groups()
                try: ts_obj = datetime.datetime.combine(today_date, datetime.datetime.strptime(time_str, "%H:%M:%S").time()); st.info(f"Timestamp TXT ({time_str}) pakai tanggal hari ini.")
                except ValueError: st.warning(f"Waktu TXT '{time_str}' tidak valid."); continue
            else: st.warning(f"Format TXT tidak dikenali: {msg_str[:100]}"); continue
        processed_history.append({"role": "user" if role_str.lower() == "user" else "assistant", "content_text": content.strip(), "timestamp": ts_obj})
    return processed_history

def parse_md_history(md_string_content):
    processed_history, today_date = [], datetime.date.today()
    for msg_block in md_string_content.strip().split("\n---\n"):
        if not msg_block.strip(): continue
        match, ts_obj, role_str, content = MD_BLOCK_PATTERN_FULL_TS.match(msg_block.strip()), None, None, None
        if match:
            ts_str_val, role_str, content = match.groups()
            try: ts_obj = datetime.datetime.strptime(ts_str_val, "%Y-%m-%d %H:%M:%S")
            except ValueError: st.warning(f"Timestamp MD (full) '{ts_str_val}' tidak valid."); continue
        else:
            match_time = MD_BLOCK_PATTERN_TIME_ONLY_TS.match(msg_block.strip())
            if match_time:
                time_str, role_str, content = match_time.groups()
                try: ts_obj = datetime.datetime.combine(today_date, datetime.datetime.strptime(time_str, "%H:%M:%S").time()); st.info(f"Timestamp MD ({time_str}) pakai tanggal hari ini.")
                except ValueError: st.warning(f"Waktu MD '{time_str}' tidak valid."); continue
            else: st.warning(f"Format MD tidak dikenali: {msg_block[:100]}"); continue
        processed_history.append({"role": "user" if role_str.lower() == "user" else "assistant", "content_text": content.strip(), "timestamp": ts_obj})
    return processed_history

def generate_chat_id():
    return f"chat_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

def create_new_chat(switch_to_it=True, initial_messages=None, title_prefix="Chat Baru", title_is_fixed=False):
    chat_id = generate_chat_id()
    default_title = f"{title_prefix} ({datetime.datetime.now().strftime('%H:%M:%S')})"
    st.session_state.all_chats[chat_id] = {
        "messages": initial_messages if initial_messages is not None else [],
        "created_at": datetime.datetime.now(),
        "title": default_title,
        "title_is_fixed": title_is_fixed
    }
    if switch_to_it:
        st.session_state.current_chat_id = chat_id
    if initial_messages is None and not st.session_state.all_chats[chat_id]["messages"]:
         sapaan = f"Halo! Sesi '{st.session_state.all_chats[chat_id]['title']}' dimulai."
         st.session_state.all_chats[chat_id]["messages"].append({
             "role": "assistant", "content_text": sapaan, "timestamp": datetime.datetime.now()
         })
    elif initial_messages and st.session_state.all_chats[chat_id]["messages"]:
        first_msg = st.session_state.all_chats[chat_id]["messages"][0]
        if first_msg.get("role") == "user" and not st.session_state.all_chats[chat_id].get("title_is_fixed", False) :
            update_chat_title_from_prompt(chat_id, first_msg.get("content_text", ""))
    return chat_id

def switch_chat(chat_id):
    if chat_id in st.session_state.all_chats:
        st.session_state.current_chat_id = chat_id
    else:
        st.error("Chat ID tidak ditemukan. Beralih ke chat terbaru atau buat baru.");
        if st.session_state.all_chats:
            st.session_state.current_chat_id = max(st.session_state.all_chats.keys(), key=lambda k: st.session_state.all_chats[k]['created_at'])
        else: create_new_chat()

if "app_version" not in st.session_state: st.session_state.app_version = APP_VERSION
if "all_chats" not in st.session_state: st.session_state.all_chats = {}
if "current_chat_id" not in st.session_state: st.session_state.current_chat_id = None
if "renaming_chat_id" not in st.session_state: st.session_state.renaming_chat_id = None
if "selected_model_name" not in st.session_state: st.session_state.selected_model_name = DEFAULT_MODEL_NAME
if st.session_state.selected_model_name not in AVAILABLE_MODELS: st.session_state.selected_model_name = DEFAULT_MODEL_NAME
if "system_prompt" not in st.session_state: st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT
if "selected_persona_name" not in st.session_state: st.session_state.selected_persona_name = "Asisten Umum (Default)"
if "persona_selector_key_v119" not in st.session_state: st.session_state.persona_selector_key_v119 = st.session_state.selected_persona_name
if "temperature" not in st.session_state: st.session_state.temperature = 0.7
if "generating" not in st.session_state: st.session_state.generating = False
if "stop_generating" not in st.session_state: st.session_state.stop_generating = False
if "generation_cancelled_by_user" not in st.session_state: st.session_state.generation_cancelled_by_user = False
if "http_referer" not in st.session_state: st.session_state.http_referer = "http://localhost:8501"
if "regenerate_request" not in st.session_state: st.session_state.regenerate_request = False
if "pending_llm_automation" not in st.session_state: st.session_state.pending_llm_automation = None
if not st.session_state.current_chat_id or st.session_state.current_chat_id not in st.session_state.all_chats:
    if st.session_state.all_chats:
        st.session_state.current_chat_id = max(st.session_state.all_chats.keys(), key=lambda k: st.session_state.all_chats[k]['created_at'])
    else: create_new_chat(title_prefix="Chat Awal")

active_chat_title = "Chatbot"
if st.session_state.current_chat_id and st.session_state.current_chat_id in st.session_state.all_chats:
    active_chat_title = st.session_state.all_chats[st.session_state.current_chat_id].get('title', 'Chat Aktif')
st.set_page_config(page_title=f"AI Chatbot ({active_chat_title})", layout="wide", initial_sidebar_state="expanded")

st.title("🚀 AI Chatbot NextGen 🚀")
st.caption(f"Versi: {st.session_state.app_version} | Chat Aktif: {active_chat_title}")

with st.sidebar:
    st.header("💬 Sesi Chat")
    if st.button("➕ New Chat", use_container_width=True, key="new_chat_button_main_v119"):
        create_new_chat()
        st.rerun()
    st.markdown("---")
    st.subheader("Recent Chats")
    sorted_chat_ids = sorted(
        st.session_state.all_chats.keys(),
        key=lambda k: st.session_state.all_chats[k]['created_at'],
        reverse=True
    )
    if not sorted_chat_ids:
        st.caption("Belum ada chat.")
        if not st.session_state.current_chat_id: create_new_chat(title_prefix="Chat Awal"); st.rerun()
    for chat_id_key in sorted_chat_ids[:15]:
        if chat_id_key not in st.session_state.all_chats: continue
        chat_info = st.session_state.all_chats[chat_id_key]
        label = chat_info.get('title', chat_id_key)
        is_renaming_this_chat = st.session_state.renaming_chat_id == chat_id_key
        col_switch, col_rename, col_delete = st.columns([0.7, 0.15, 0.15])
        with col_switch:
            if is_renaming_this_chat:
                rename_input_key = f"rename_input_{chat_id_key}"
                st.text_input(
                    "Nama baru:", value=label, key=rename_input_key,
                    on_change=handle_rename_chat_submit, args=(chat_id_key, rename_input_key),
                    label_visibility="collapsed"
                )
            else:
                button_type = "primary" if chat_id_key == st.session_state.current_chat_id else "secondary"
                if st.button(label, key=f"switch_{chat_id_key}", use_container_width=True, type=button_type, help=f"Buka: {label}"):
                    if st.session_state.current_chat_id != chat_id_key:
                        switch_chat(chat_id_key); st.rerun()
        with col_rename:
            if is_renaming_this_chat:
                if st.button("Batal", key=f"cancel_rename_{chat_id_key}", help="Batal ganti nama"):
                    st.session_state.renaming_chat_id = None; st.rerun()
            else:
                if st.button("✏️", key=f"rename_start_{chat_id_key}", help=f"Ganti nama: {label}"):
                    st.session_state.renaming_chat_id = chat_id_key
                    st.session_state[f"rename_input_{chat_id_key}"] = label
                    st.rerun()
        with col_delete:
            if st.button("🗑️", key=f"delete_{chat_id_key}", help=f"Hapus: {label}"):
                title_deleted = st.session_state.all_chats[chat_id_key]['title']
                del st.session_state.all_chats[chat_id_key]
                st.toast(f"Chat '{title_deleted}' dihapus.", icon="🗑️")
                if st.session_state.current_chat_id == chat_id_key:
                    remaining_ids = sorted(st.session_state.all_chats.keys(), key=lambda k: st.session_state.all_chats[k]['created_at'], reverse=True)
                    if remaining_ids: st.session_state.current_chat_id = remaining_ids[0]
                    else: create_new_chat(title_prefix="Chat Awal")
                st.rerun()
    st.markdown("---")
    st.header("🛠️ Pengaturan Global")
    with st.expander("✨ Atur Gaya, Suhu & Model AI", expanded=True):
        model_options = list(AVAILABLE_MODELS.keys())
        if st.session_state.selected_model_name not in model_options: st.session_state.selected_model_name = model_options[0]
        current_model_idx_sb = model_options.index(st.session_state.selected_model_name)
        selected_model_id = AVAILABLE_MODELS[st.session_state.selected_model_name]["id"] 
        st.session_state.selected_model_name = st.selectbox("Pilih Model AI:", options=model_options, key="model_selector_main_ui_v119", index=current_model_idx_sb)
        selected_model_info = AVAILABLE_MODELS[st.session_state.selected_model_name]
        selected_model_id = selected_model_info["id"]
        st.markdown("---")
        st.markdown("#### **Pengaturan Gaya & Kreativitas**")
        persona_options = list(PREDEFINED_PERSONAS.keys())
        if st.session_state.selected_persona_name not in persona_options:
            st.session_state.selected_persona_name = "Asisten Umum (Default)"
        current_persona_idx_sb = persona_options.index(st.session_state.selected_persona_name)
        st.selectbox("Pilih Gaya/Persona Bot:", options=persona_options, 
                     key="persona_selector_key_v119", 
                     index=current_persona_idx_sb, 
                     on_change=update_system_prompt_from_persona_callback, 
                     help="Pilih peran dasar bot.")
        st.session_state.system_prompt = st.text_area("System Prompt:", value=st.session_state.system_prompt, height=150, key="system_prompt_main_ui_v119", help="Instruksi perilaku bot.")
        st.session_state.temperature = st.slider("Suhu Kreativitas:", min_value=0.0, max_value=1.0, value=st.session_state.temperature, step=0.05, help="Rendah = fokus. Tinggi = kreatif.")
        st.caption(f"Model aktif: {st.session_state.selected_model_name}. Hanya input teks.")
    with st.expander("📜 Riwayat Chat Aktif", expanded=False):
        active_chat_display_title = "Belum ada chat aktif"
        if st.session_state.current_chat_id and st.session_state.current_chat_id in st.session_state.all_chats:
             active_chat_display_title = st.session_state.all_chats[st.session_state.current_chat_id]['title']
        st.markdown(f"Operasi untuk chat: **{active_chat_display_title}**")
        current_chat_messages_list = get_current_chat_messages()
        if current_chat_messages_list:
            col_dl1, col_dl2, col_dl3 = st.columns(3)
            json_export_data = [{"role": m["role"], "content_text": m.get("content_text"), "timestamp": m.get("timestamp").isoformat() if isinstance(m.get("timestamp"), datetime.datetime) else str(m.get("timestamp"))} for m in current_chat_messages_list]
            col_dl1.download_button(label="JSON 💾", data=json.dumps(json_export_data, indent=2, ensure_ascii=False), file_name=f"chat_{st.session_state.current_chat_id}_{datetime.datetime.now().strftime('%H%M')}.json", mime="application/json", use_container_width=True, key=f"dl_json_{st.session_state.current_chat_id}")
            txt_export_data = "\n\n".join([f"[{format_timestamp_export(m['timestamp'])}] {m['role'].capitalize()}: {m['content_text']}" for m in current_chat_messages_list])
            col_dl2.download_button(label="TXT 📝", data=txt_export_data, file_name=f"chat_{st.session_state.current_chat_id}_{datetime.datetime.now().strftime('%H%M')}.txt", mime="text/plain", use_container_width=True, key=f"dl_txt_{st.session_state.current_chat_id}")
            md_export_data = "\n---\n".join([f"*{format_timestamp_export(m['timestamp'])}* - **{m['role'].capitalize()}**:\n{m['content_text']}\n" for m in current_chat_messages_list])
            col_dl3.download_button(label="Markdown 📜", data=md_export_data, file_name=f"chat_{st.session_state.current_chat_id}_{datetime.datetime.now().strftime('%H%M')}.md", mime="text/markdown", use_container_width=True, key=f"dl_md_{st.session_state.current_chat_id}")
        else: st.caption("Tidak ada pesan untuk diunduh.")
        uploaded_file = st.file_uploader("Unggah ke Sesi Chat Baru (JSON, TXT, MD)", type=["json", "txt", "md"], key="upload_chat_v119", accept_multiple_files=False)
        if uploaded_file is not None:
            file_content_str, parse_error = "", False
            try: file_content_str = uploaded_file.getvalue().decode("utf-8")
            except Exception as e: st.error(f"Gagal baca file: {e}"); parse_error = True
            if not parse_error and file_content_str:
                file_extension = uploaded_file.name.split(".")[-1].lower()
                parsed_history = None
                if file_extension == "json": parsed_history = parse_json_history(file_content_str)
                elif file_extension == "txt": parsed_history = parse_txt_history(file_content_str)
                elif file_extension == "md": parsed_history = parse_md_history(file_content_str)
                else: st.error(f"Tipe file .{file_extension} tidak didukung."); parse_error = True
                if not parse_error and parsed_history is not None:
                    if isinstance(parsed_history, list) and parsed_history:
                        upload_title_prefix = uploaded_file.name.rsplit('.', 1)[0] if '.' in uploaded_file.name else uploaded_file.name
                        new_chat_id_upload = create_new_chat(switch_to_it=False, initial_messages=parsed_history, title_prefix=f"Upload: {upload_title_prefix[:20]}", title_is_fixed=True)
                        switch_chat(new_chat_id_upload)
                        st.toast(f"Riwayat dari '{uploaded_file.name}' dimuat ke chat baru '{st.session_state.all_chats[new_chat_id_upload]['title']}'!", icon="✅")
                        st.rerun()
                    elif isinstance(parsed_history, list) and not parsed_history: st.warning(f"Tidak ada item valid di file .{file_extension}.")
            elif not parse_error and not file_content_str: st.warning("File unggahan kosong.")
    last_bot_response_content_active = None
    if st.session_state.current_chat_id and st.session_state.current_chat_id in st.session_state.all_chats:
        active_messages = st.session_state.all_chats[st.session_state.current_chat_id]["messages"]
        for msg in reversed(active_messages):
            if msg["role"] == "assistant": last_bot_response_content_active = msg["content_text"]; break
    if last_bot_response_content_active:
        if st.button("Salin Pesan Terakhir Bot (Chat Aktif) 📋", use_container_width=True, key="copy_btn_active_chat_v119"):
            st.text_area("Teks untuk disalin:", last_bot_response_content_active, height=100, key="copy_area_sidebar_active_v119", label_visibility="collapsed")
            st.toast("Teks siap disalin.", icon="📋")
    st.markdown("---")
    st.caption(f"ID Model: `{selected_model_id}`")
    st.markdown(f"<div style='text-align: center; font-size: 0.8em;'>Powered by OpenRouter.ai | {st.session_state.app_version}</div>", unsafe_allow_html=True)
if st.session_state.get("generation_cancelled_by_user", False) and st.session_state.current_chat_id :
    cancelled_message_text = "🛑 Generasi dihentikan oleh pengguna."
    current_msgs_list = get_current_chat_messages()
    if not current_msgs_list or not (current_msgs_list[-1]["role"] == "assistant" and current_msgs_list[-1]["content_text"] == cancelled_message_text):
        append_message_to_current_chat("assistant", cancelled_message_text)
    st.toast("Generasi telah dibatalkan.", icon="🛑")
    st.session_state.generating = False; st.session_state.stop_generating = False; st.session_state.generation_cancelled_by_user = False
    st.rerun()
current_chat_messages_list_main = get_current_chat_messages()
for i, chat_item in enumerate(current_chat_messages_list_main):
    avatar_icon = "👤" if chat_item['role'] == "user" else "🤖"
    ts_obj = chat_item.get('timestamp', datetime.datetime.now())
    with st.chat_message(chat_item['role'], avatar=avatar_icon):
        if chat_item.get("content_text"):
            st.markdown(chat_item["content_text"])
            code_blocks_matches = re.finditer(r"```(\w*)\n([\s\S]*?)\n```", chat_item["content_text"])
            for block_idx, match in enumerate(code_blocks_matches):
                lang = match.group(1).strip() or "plaintext"
                code = match.group(2).strip()
                unique_suffix = str(ts_obj).replace(' ','_').replace(':','-').replace('.','_')
                exp_key = f"exp_{st.session_state.current_chat_id}_{i}_{block_idx}_{unique_suffix}"
                code_key = f"code_{st.session_state.current_chat_id}_{i}_{block_idx}_{unique_suffix}"
                with st.expander(f"Kode #{block_idx+1} ({lang})", key=exp_key):
                    st.code(code, language=lang, key=code_key)
        is_last_message = (i == len(current_chat_messages_list_main) - 1)
        is_assistant = chat_item['role'] == 'assistant'
        not_error_message = not str(chat_item.get("content_text","")) .startswith("🛑")
        if is_assistant and is_last_message and not st.session_state.generating and not_error_message:
            regen_key = f"regen_btn_{st.session_state.current_chat_id}_{i}_{str(ts_obj).replace(' ','_').replace(':','-').replace('.','_')}"
            if st.button("Regenerate 🔄", key=regen_key, help="Ulang generasi respons ini"):
                st.session_state.regenerate_request = True
                current_messages = get_current_chat_messages()
                if current_messages : current_messages.pop()
                st.rerun()
        st.caption(f"_{format_timestamp_display(ts_obj)}_")
user_input = st.chat_input(f"Ketik pesan untuk '{active_chat_title}'...", key=f"chat_input_{st.session_state.current_chat_id}", disabled=st.session_state.generating)
process_input_flag, input_source = False, None
if user_input: process_input_flag, input_source = True, "user"
elif st.session_state.get("regenerate_request", False): process_input_flag, input_source = True, "regenerate"
elif st.session_state.get("pending_llm_automation"): process_input_flag, input_source = True, "automation"
if process_input_flag and not st.session_state.generating and st.session_state.current_chat_id:
    st.session_state.generating = True
    st.session_state.stop_generating = False
    st.session_state.generation_cancelled_by_user = False
    messages_for_llm_call, direct_bot_response_content = None, None
    current_model_id_for_call = AVAILABLE_MODELS[st.session_state.selected_model_name]["id"]
    current_model_info_for_call = AVAILABLE_MODELS[st.session_state.selected_model_name]
    if input_source == "regenerate":
        st.session_state.regenerate_request = False
        active_msgs = get_current_chat_messages()
        if active_msgs and active_msgs[-1]["role"] == "user":
            messages_for_llm_call = prepare_messages_for_api(active_msgs, st.session_state.system_prompt)
        else: st.warning("Regenerasi gagal."); st.session_state.generating = False; st.rerun(); process_input_flag = False
    elif input_source == "user":
        append_message_to_current_chat("user", user_input)
        if user_input.startswith("!"):
            direct_bot_response_content = handle_automation_command(user_input, current_model_info_for_call, get_current_chat_messages()[:-1])
            if st.session_state.get("pending_llm_automation"):
                pending_task = st.session_state.pending_llm_automation
                messages_for_llm_call = pending_task["messages"]
                current_model_id_for_call = pending_task.get("model_id", current_model_id_for_call)
                st.session_state.pending_llm_automation = None
        else: messages_for_llm_call = prepare_messages_for_api(get_current_chat_messages(), st.session_state.system_prompt)
    elif input_source == "automation":
        pending_task = st.session_state.pending_llm_automation
        messages_for_llm_call = pending_task["messages"]
        current_model_id_for_call = pending_task.get("model_id", current_model_id_for_call)
        st.session_state.pending_llm_automation = None
    if direct_bot_response_content:
        append_message_to_current_chat("assistant", direct_bot_response_content)
        st.session_state.generating = False; st.rerun()
    elif messages_for_llm_call and process_input_flag:
        model_name_for_status = st.session_state.selected_model_name
        for name, info in AVAILABLE_MODELS.items():
            if info["id"] == current_model_id_for_call: model_name_for_status = name; break
        with st.chat_message("assistant", avatar="🤖"):
            with st.status(f"🤖 Bot ({model_name_for_status}) mengetik...", expanded=True) as status_indicator:
                cancel_key = f"cancel_btn_{st.session_state.current_chat_id}_{datetime.datetime.now().timestamp()}"
                if st.button("Batalkan Generasi ⏹️", key=cancel_key):
                    st.session_state.stop_generating = True
                    st.session_state.generation_cancelled_by_user = True
                    st.toast("Pembatalan dikirim...", icon="🛑"); st.rerun()
                message_placeholder, full_bot_response = st.empty(), ""
                try:
                    if not st.session_state.generation_cancelled_by_user:
                        for chunk in get_bot_response_stream(messages_for_llm_call, current_model_id_for_call, st.session_state.temperature):
                            if st.session_state.stop_generating: break
                            full_bot_response += chunk; message_placeholder.markdown(full_bot_response + "▌")
                        message_placeholder.markdown(full_bot_response)
                    if st.session_state.generation_cancelled_by_user: status_indicator.update(label="Pembatalan diproses...", state="error", expanded=False)
                    elif st.session_state.stop_generating:
                        if not "🛑 Generasi dihentikan" in full_bot_response: full_bot_response += "\n🛑 Generasi dihentikan."
                        message_placeholder.markdown(full_bot_response); status_indicator.update(label="Generasi dihentikan.", state="error", expanded=False)
                    elif full_bot_response and not full_bot_response.startswith("🛑"): status_indicator.update(label="Respons diterima!", state="complete", expanded=False)
                    elif full_bot_response.startswith("🛑"): status_indicator.update(label="Error dari LLM.", state="error", expanded=False)
                    elif not full_bot_response : full_bot_response = "(Bot tidak memberi respons.)"; message_placeholder.markdown(full_bot_response); status_indicator.update(label="Selesai (output kosong).", state="complete", expanded=False)
                except Exception as e: full_bot_response = f"🛑 Critical stream error: {e}"; message_placeholder.error(full_bot_response); status_indicator.update(label="Streaming Error Kritis!", state="error", expanded=False)
            bot_ts = datetime.datetime.now()
            if full_bot_response or st.session_state.generation_cancelled_by_user: st.caption(f"_{format_timestamp_display(bot_ts)}_")
        if not st.session_state.generation_cancelled_by_user:
            if full_bot_response: append_message_to_current_chat("assistant", full_bot_response, bot_ts)
            st.session_state.generating = False; st.session_state.stop_generating = False; st.rerun()
elif not process_input_flag and st.session_state.generating and not st.session_state.generation_cancelled_by_user:
    st.warning("State anomali. Mereset..."); st.session_state.generating = False; st.session_state.stop_generating = False; st.rerun()
