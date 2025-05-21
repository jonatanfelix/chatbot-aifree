import streamlit as st
import requests
import json
import datetime
import re
import pytz # Untuk penanganan zona waktu GMT+7
import base64 # Untuk memainkan suara notifikasi
import os # Untuk mengecek path file suara

# -- Konfigurasi Awal & Variabel Global --
APP_VERSION = "Chatbot AI"

DEFAULT_MODEL_NAME = "Meta Llama 3 8B Instruct"
DEFAULT_SYSTEM_PROMPT = "Anda adalah asisten AI yang serbaguna dan ramah. Selalu odgovori dalam Bahasa Indonesia kecuali diminta lain."
TARGET_TIMEZONE_STR = "Asia/Bangkok" # GMT+7
TARGET_TZ = pytz.timezone(TARGET_TIMEZONE_STR)
DEFAULT_MAX_HISTORY_LENGTH = 10
SOUND_NOTIFICATION_FILE = "assets/notification.mp3" # Path ke file suara Anda

AVAILABLE_MODELS = {
    "Meta Llama 3 8B Instruct": {"id": "meta-llama/llama-3-8b-instruct", "vision": False, "max_tokens": 8192, "free": True},
    "DeepSeek Chat V3 0324 (free)": {"id": "deepseek/deepseek-chat-v3-0324:free", "vision": False, "max_tokens": 163840, "free": True}
}

PREDEFINED_PERSONAS = {
    "Asisten Umum (Default)": DEFAULT_SYSTEM_PROMPT,
    "Penulis Kreatif": "Anda adalah seorang penulis cerita dan puisi yang imajinatif. Hasilkan teks yang puitis, mendalam, dan membangkitkan emosi. Gunakan gaya bahasa yang kaya.",
    "Pakar Sejarah": "Anda adalah seorang sejarawan dengan pengetahuan luas. Jawab pertanyaan tentang sejarah dengan detail, akurat, dan sertakan konteks yang relevan. Bersikaplah objektif.",
    "Penerjemah Ahli": "Anda adalah penerjemah bahasa profesional. Terjemahkan teks antar bahasa dengan akurat, mempertahankan nuansa dan makna asli. Sebutkan bahasa sumber dan target jika tidak jelas.",
    "Guru Matematika": "Anda adalah seorang guru matematika yang sabar. Jelaskan konsep matematika yang sulit dengan cara yang mudah dimengerti. Berikan contoh dan langkah-langkah penyelesaian."
}

# Pra-kompilasi Regex
TXT_PATTERN_FULL_TS = re.compile(r"\[(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\]\s*(User|Assistant|System|Bot):\s*([\s\S]*)", re.IGNORECASE)
TXT_PATTERN_TIME_ONLY_TS = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]\s*(User|Assistant|System|Bot):\s*([\s\S]*)", re.IGNORECASE)
MD_BLOCK_PATTERN_FULL_TS = re.compile(r"\*(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\*\s*-\s*\*\*(User|Assistant|System|Bot)\*\*:\s*\n?([\s\S]*)", re.IGNORECASE)
MD_BLOCK_PATTERN_TIME_ONLY_TS = re.compile(r"\*(\d{2}:\d{2}:\d{2})\*\s*-\s*\*\*(User|Assistant|System|Bot)\*\*:\s*\n?([\s\S]*)", re.IGNORECASE)

if not AVAILABLE_MODELS: st.error("Kritis: Tidak ada model."); st.stop()
if DEFAULT_MODEL_NAME not in AVAILABLE_MODELS:
    DEFAULT_MODEL_NAME = list(AVAILABLE_MODELS.keys())[0] if AVAILABLE_MODELS else None
    if not DEFAULT_MODEL_NAME: st.error("Kritis: Tidak ada model default."); st.stop()

try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
except (FileNotFoundError, KeyError):
    st.error("CRITICAL ERROR: `OPENROUTER_API_KEY` tidak ditemukan di Streamlit Secrets.")
    st.markdown("Pastikan sudah ditambahkan di Settings -> Secrets di Streamlit Cloud.")
    st.stop()

# --- Fungsi Notifikasi Suara ---
def play_notification_sound(sound_file_path=SOUND_NOTIFICATION_FILE):
    if not st.session_state.get("play_sound_once", False): # Hanya mainkan sekali per trigger
        return
    
    # Reset flag agar bisa diputar lagi nanti
    st.session_state.play_sound_once = False

    if os.path.exists(sound_file_path):
        try:
            with open(sound_file_path, "rb") as f:
                data = f.read()
                b64 = base64.b64encode(data).decode()
                # Tentukan tipe MIME berdasarkan ekstensi file
                mime_type = "audio/mp3"
                if sound_file_path.lower().endswith(".wav"):
                    mime_type = "audio/wav"
                elif sound_file_path.lower().endswith(".ogg"):
                    mime_type = "audio/ogg"
                
                html_audio = f"""
                    <audio autoplay>
                        <source src="data:{mime_type};base64,{b64}" type="{mime_type}">
                        Browser Anda tidak mendukung elemen audio.
                    </audio>
                    <script>
                        // Script kecil untuk memastikan autoplay dicoba setelah elemen dimuat
                        var audio = document.querySelector("audio");
                        if (audio) {{
                            audio.play().catch(function(error) {{
                                console.log("Autoplay dicegah oleh browser: ", error);
                                // Mungkin perlu interaksi pengguna untuk mengaktifkan suara
                            }});
                        }}
                    </script>
                    """
                st.components.v1.html(html_audio, height=0, width=0)
        except FileNotFoundError:
            st.warning(f"File suara notifikasi '{sound_file_path}' tidak ditemukan.", icon="🔊")
        except Exception as e:
            st.warning(f"Tidak dapat memainkan suara notifikasi: {e}", icon="🔊")
    else:
        st.warning(f"File suara notifikasi '{sound_file_path}' tidak ada.", icon="🔊")


# --- Fungsi Timestamp GMT+7 ---
def get_gmt7_now():
    return datetime.datetime.now(TARGET_TZ)

def convert_to_gmt7(dt_obj):
    # ... (fungsi sama seperti v1.1.13) ...
    if not isinstance(dt_obj, datetime.datetime):
        try: dt_obj = datetime.datetime.fromisoformat(str(dt_obj).replace("Z", "+00:00"))
        except ValueError:
            try: dt_obj = datetime.datetime.strptime(str(dt_obj), "%Y-%m-%d %H:%M:%S")
            except ValueError: return get_gmt7_now()
    if dt_obj.tzinfo is None: return TARGET_TZ.localize(dt_obj)
    return dt_obj.astimezone(TARGET_TZ)

# --- Callbacks ---
def update_system_prompt_from_persona_callback():
    # ... (fungsi sama seperti v1.1.13) ...
    selected_persona_key = st.session_state.get("persona_selector_key_v119", "Asisten Umum (Default)")
    st.session_state.selected_persona_name = selected_persona_key
    st.session_state.system_prompt = PREDEFINED_PERSONAS.get(selected_persona_key, DEFAULT_SYSTEM_PROMPT)


def handle_rename_chat_submit(chat_id_to_rename, input_key):
    # ... (fungsi sama seperti v1.1.13) ...
    new_name = st.session_state.get(input_key, "").strip()
    if new_name:
        if chat_id_to_rename in st.session_state.all_chats:
            st.session_state.all_chats[chat_id_to_rename]['title'] = new_name
            st.session_state.all_chats[chat_id_to_rename]['title_is_fixed'] = True
            st.toast(f"Chat diubah nama menjadi '{new_name}'", icon="✏️")
        else: st.warning("Gagal rename: Chat ID tidak ditemukan.")
    else: st.warning("Nama chat tidak boleh kosong.")
    st.session_state.renaming_chat_id = None


def toggle_pin_chat(chat_id_to_pin):
    # ... (fungsi sama seperti v1.1.13) ...
    if chat_id_to_pin in st.session_state.all_chats:
        is_currently_pinned = st.session_state.all_chats[chat_id_to_pin].get("is_pinned", False)
        st.session_state.all_chats[chat_id_to_pin]["is_pinned"] = not is_currently_pinned
        if st.session_state.all_chats[chat_id_to_pin]["is_pinned"]:
            st.session_state.all_chats[chat_id_to_pin]["pinned_at"] = get_gmt7_now()
            st.toast(f"Chat '{st.session_state.all_chats[chat_id_to_pin]['title']}' disematkan!", icon="📌")
        else:
            st.toast(f"Sematan '{st.session_state.all_chats[chat_id_to_pin]['title']}' dilepas.", icon="📍")

# --- Fungsi Inti & Helper ---
def get_current_chat_messages():
    # ... (fungsi sama seperti v1.1.13) ...
    if st.session_state.current_chat_id and st.session_state.current_chat_id in st.session_state.all_chats:
        return st.session_state.all_chats[st.session_state.current_chat_id]["messages"]
    return []

def update_chat_title_from_prompt(chat_id, user_prompt_content):
    # ... (fungsi sama seperti v1.1.13) ...
    if chat_id in st.session_state.all_chats and \
       not st.session_state.all_chats[chat_id].get("title_is_fixed", False):
        cleaned_prompt = user_prompt_content.strip()
        if cleaned_prompt.startswith("!"): return 
        words = cleaned_prompt.split()
        if len(words) < 2: 
            current_chat_info = st.session_state.all_chats[chat_id]
            is_placeholder_title = any(current_chat_info['title'].startswith(p) for p in ["Chat Baru", "Upload:", "Chat Awal", "Diskusi"])
            if not is_placeholder_title: return
            st.session_state.all_chats[chat_id]['title'] = f"Diskusi ({current_chat_info['created_at'].astimezone(TARGET_TZ).strftime('%H:%M')})"
            return
        title = " ".join(words[:5])
        if len(words) > 5: title += "..."
        st.session_state.all_chats[chat_id]['title'] = title

def append_message_to_current_chat(role, content_text, timestamp=None, feedback=None):
    # ... (fungsi sama seperti v1.1.13) ...
    chat_id = st.session_state.current_chat_id
    if chat_id and chat_id in st.session_state.all_chats:
        messages = st.session_state.all_chats[chat_id]["messages"]
        current_time = timestamp or get_gmt7_now()
        message_data = {"role": role, "content_text": content_text, "timestamp": current_time}
        if role == "assistant": message_data["feedback"] = feedback 
        messages.append(message_data)
        if role == "user": update_chat_title_from_prompt(chat_id, content_text)


def get_bot_response_stream(messages_for_api, selected_model_id, temperature):
    # ... (fungsi sama seperti v1.1.13) ...
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


def format_timestamp_display(ts_obj_input):
    # ... (fungsi sama seperti v1.1.13) ...
    if not isinstance(ts_obj_input, datetime.datetime):
        try: ts_obj = datetime.datetime.fromisoformat(str(ts_obj_input).replace("Z", "+00:00"))
        except: return str(ts_obj_input)
    else: ts_obj = ts_obj_input
    return convert_to_gmt7(ts_obj).strftime("%H:%M:%S")

def format_timestamp_export(ts_obj_input):
    # ... (fungsi sama seperti v1.1.13) ...
    if not isinstance(ts_obj_input, datetime.datetime):
        try: ts_obj = datetime.datetime.fromisoformat(str(ts_obj_input).replace("Z", "+00:00"))
        except: return str(ts_obj_input)
    else: ts_obj = ts_obj_input
    return convert_to_gmt7(ts_obj).strftime("%Y-%m-%d %H:%M:%S %Z%z")


def prepare_messages_for_api(chat_messages_list, system_prompt):
    # ... (fungsi sama seperti v1.1.13) ...
    messages = [{"role": "system", "content": system_prompt}]
    history_len = st.session_state.get("max_history_length", DEFAULT_MAX_HISTORY_LENGTH)
    relevant_history = chat_messages_list[-history_len:]
    for msg in relevant_history: messages.append({"role": msg["role"], "content": str(msg.get("content_text",""))})
    return messages

def handle_automation_command(command_input, current_model_info, chat_messages_list):
    # ... (fungsi sama seperti v1.1.13) ...
    parts = command_input.strip().split(" ", 1)
    command = parts[0].lower()
    if command == "!help" or command == "!bantuan":
        return """**Perintah:**\n- `!help`/`!bantuan`: Bantuan.\n- `!info_model`: Info model.\n- `!waktu`: Waktu (GMT+7).\n- `!summarize_chat`: Rangkum chat."""
    elif command == "!info_model":
        model_id_val = current_model_info.get('id', 'N/A')
        max_tokens_val = current_model_info.get('max_tokens', 'N/A')
        return f"**Info Model:**\n- Nama: {st.session_state.selected_model_name}\n- ID: `{model_id_val}`\n- Max Tokens: {max_tokens_val}"
    elif command == "!waktu":
        return f"Waktu saat ini (GMT+7): {get_gmt7_now().strftime('%Y-%m-%d %H:%M:%S %Z%z')}"
    elif command == "!summarize_chat":
        if not chat_messages_list: return "Riwayat chat kosong."
        conversation_text = "\n".join([f"{msg['role']}: {msg['content_text']}" for msg in chat_messages_list if msg.get('content_text') and not str(msg.get('content_text', '')).startswith("🛑")])
        if not conversation_text.strip(): return "Tidak ada konten chat untuk dirangkum."
        st.info(f"Merangkum {len(chat_messages_list)} pesan...")
        summary_prompt = [{"role": "system", "content": "Summarize this conversation concisely:"}, {"role": "user", "content": conversation_text}]
        st.session_state.pending_llm_automation = {"messages": summary_prompt, "model_id": current_model_info.get("id", AVAILABLE_MODELS[DEFAULT_MODEL_NAME]["id"]), "is_summary_for_current_chat": True}
        return None
    return f"Perintah '{command}' tidak dikenali. Ketik `!help`."

def parse_timestamp_from_string(ts_str):
    # ... (fungsi sama seperti v1.1.13) ...
    try: dt_obj_iso = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00")); return convert_to_gmt7(dt_obj_iso)
    except ValueError: pass
    formats_to_try = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]
    for fmt in formats_to_try:
        try: dt_obj_naive = datetime.datetime.strptime(ts_str, fmt); return TARGET_TZ.localize(dt_obj_naive)
        except ValueError: continue
    try:
        time_only_obj = datetime.datetime.strptime(ts_str, "%H:%M:%S").time()
        today_gmt7 = get_gmt7_now().date()
        return TARGET_TZ.localize(datetime.datetime.combine(today_gmt7, time_only_obj))
    except ValueError: pass
    st.warning(f"Timestamp '{ts_str}' tidak dapat diparsing, pakai waktu sekarang (GMT+7).")
    return get_gmt7_now()


def parse_json_history(json_string_content):
    # ... (fungsi sama seperti v1.1.13) ...
    try:
        raw_history_data = json.loads(json_string_content)
        if isinstance(raw_history_data, dict) and "all_chats_export" in raw_history_data:
            st.warning("Format file ekspor semua chat belum didukung untuk unggah. Harap unggah file JSON yang berisi list pesan untuk satu sesi chat.")
            return None
        elif isinstance(raw_history_data, list): raw_chat_items = raw_history_data
        else: st.error("Format JSON tidak valid. Harus berupa list pesan."); return None

        processed_history = []
        for item_raw in raw_chat_items:
            if isinstance(item_raw, dict) and 'role' in item_raw and item_raw.get('content_text') is not None and 'timestamp' in item_raw:
                role, ts_data = item_raw["role"], item_raw.get('timestamp')
                if role not in ["user", "assistant", "system"]: st.warning(f"Role '{role}' tidak valid."); continue
                timestamp_obj = None
                if isinstance(ts_data, str): timestamp_obj = parse_timestamp_from_string(ts_data)
                elif isinstance(ts_data, (int, float)): timestamp_obj = datetime.datetime.fromtimestamp(ts_data, tz=pytz.utc).astimezone(TARGET_TZ)
                else: st.warning(f"Tipe timestamp JSON '{type(ts_data)}' tidak dikenal."); timestamp_obj = get_gmt7_now()
                
                processed_history.append({"role": role, "content_text": str(item_raw["content_text"]), "timestamp": timestamp_obj, "feedback": item_raw.get("feedback")})
            else: st.warning(f"Item JSON tidak valid: {str(item_raw)[:100]}")
        return processed_history
    except Exception as e: st.error(f"Error proses JSON: {e}"); return None


def parse_txt_history(txt_string_content):
    # ... (fungsi sama seperti v1.1.13) ...
    processed_history = []
    for msg_str in txt_string_content.strip().split("\n\n"):
        if not msg_str.strip(): continue
        match_full, match_time_only = TXT_PATTERN_FULL_TS.match(msg_str.strip()), TXT_PATTERN_TIME_ONLY_TS.match(msg_str.strip())
        timestamp_str, role_str, content = None, None, None
        if match_full: timestamp_str, role_str, content = match_full.groups()
        elif match_time_only: timestamp_str, role_str, content = match_time_only.groups()
        else: st.warning(f"Format TXT tidak dikenali: {msg_str[:100]}"); continue
        timestamp_obj = parse_timestamp_from_string(timestamp_str)
        role = "user" if role_str.lower() == "user" else "assistant"
        processed_history.append({"role": role, "content_text": content.strip(), "timestamp": timestamp_obj, "feedback": None}) 
    return processed_history


def parse_md_history(md_string_content):
    # ... (fungsi sama seperti v1.1.13) ...
    processed_history = []
    for msg_block in md_string_content.strip().split("\n---\n"):
        if not msg_block.strip(): continue
        match_full, match_time_only = MD_BLOCK_PATTERN_FULL_TS.match(msg_block.strip()), MD_BLOCK_PATTERN_TIME_ONLY_TS.match(msg_block.strip())
        timestamp_str, role_str, content = None, None, None
        if match_full: timestamp_str, role_str, content = match_full.groups()
        elif match_time_only: timestamp_str, role_str, content = match_time_only.groups()
        else: st.warning(f"Format MD tidak dikenali: {msg_block[:100]}"); continue
        timestamp_obj = parse_timestamp_from_string(timestamp_str)
        role = "user" if role_str.lower() == "user" else "assistant"
        processed_history.append({"role": role, "content_text": content.strip(), "timestamp": timestamp_obj, "feedback": None})
    return processed_history

# --- Fungsi Manajemen Chat ---
def generate_chat_id(): return f"chat_{get_gmt7_now().strftime('%Y%m%d_%H%M%S_%f')}"

def create_new_chat(switch_to_it=True, initial_messages=None, title_prefix="Chat Baru", title_is_fixed=False, uploaded_filename=None, is_pinned=False):
    # ... (fungsi sama seperti v1.1.13) ...
    chat_id = generate_chat_id()
    final_title = f"{title_prefix} ({get_gmt7_now().strftime('%H:%M:%S')})"
    if uploaded_filename:
        base_name = uploaded_filename.rsplit('.', 1)[0] if '.' in uploaded_filename else uploaded_filename
        final_title = f"Upload: {base_name[:25]}"; title_is_fixed = True 
    current_time = get_gmt7_now()
    processed_initial_messages = []
    if initial_messages:
        for msg in initial_messages:
            if msg.get("role") == "assistant" and "feedback" not in msg: msg["feedback"] = None
            processed_initial_messages.append(msg)
    else: # Pesan sapaan default jika chat baru dibuat dari tombol "New Chat"
        sapaan_text = f"Sesi '{final_title}' dimulai. Siap membantu!"
        processed_initial_messages.append({"role": "assistant", "content_text": sapaan_text, "timestamp": current_time, "feedback": None})

    st.session_state.all_chats[chat_id] = {"messages": processed_initial_messages, "created_at": current_time, "title": final_title, "title_is_fixed": title_is_fixed, "is_pinned": is_pinned, "pinned_at": current_time if is_pinned else None}
    if switch_to_it: st.session_state.current_chat_id = chat_id
    
    # Coba set judul dari pesan pertama jika dari upload dan belum fixed (meskipun upload biasanya fixed)
    # atau jika initial_messages diberikan tetapi BUKAN dari upload (jarang terjadi)
    if initial_messages and not title_is_fixed and not uploaded_filename: 
        first_user_msg = next((msg for msg in initial_messages if msg["role"] == "user"), None)
        if first_user_msg: update_chat_title_from_prompt(chat_id, first_user_msg["content_text"])
    return chat_id


def switch_chat(chat_id):
    # ... (fungsi sama seperti v1.1.13) ...
    if chat_id in st.session_state.all_chats: st.session_state.current_chat_id = chat_id
    else:
        st.error("Chat ID tidak ditemukan.");
        if st.session_state.all_chats: st.session_state.current_chat_id = max(st.session_state.all_chats.keys(), key=lambda k: st.session_state.all_chats[k]['created_at'])
        else: create_new_chat(title_prefix="Chat Awal")

def reset_all_chats_action():
    # ... (fungsi sama seperti v1.1.13) ...
    st.session_state.all_chats, st.session_state.current_chat_id, st.session_state.renaming_chat_id = {}, None, None
    st.session_state.active_chat_search_query = "" 
    create_new_chat(title_prefix="Chat Awal Baru"); st.toast("Semua riwayat chat telah dihapus!", icon="🗑️")


# --- Inisialisasi Session State Utama ---
# ... (sama seperti v1.1.13, tambahkan play_sound_once)
if "app_version" not in st.session_state: st.session_state.app_version = APP_VERSION
if "all_chats" not in st.session_state: st.session_state.all_chats = {}
if "current_chat_id" not in st.session_state: st.session_state.current_chat_id = None
if "renaming_chat_id" not in st.session_state: st.session_state.renaming_chat_id = None
if "selected_model_name" not in st.session_state: st.session_state.selected_model_name = DEFAULT_MODEL_NAME
if st.session_state.selected_model_name not in AVAILABLE_MODELS: st.session_state.selected_model_name = DEFAULT_MODEL_NAME
if "system_prompt" not in st.session_state: st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT
if "selected_persona_name" not in st.session_state: st.session_state.selected_persona_name = "Asisten Umum (Default)"
if "persona_selector_key_v119" not in st.session_state: st.session_state.persona_selector_key_v119 = st.session_state.selected_persona_name # Kunci untuk selectbox persona
if "temperature" not in st.session_state: st.session_state.temperature = 0.7
if "max_history_length" not in st.session_state: st.session_state.max_history_length = DEFAULT_MAX_HISTORY_LENGTH
if "active_chat_search_query" not in st.session_state: st.session_state.active_chat_search_query = ""
if "play_sound_once" not in st.session_state: st.session_state.play_sound_once = False # Untuk notifikasi suara

if "generating" not in st.session_state: st.session_state.generating = False
if "stop_generating" not in st.session_state: st.session_state.stop_generating = False
if "generation_cancelled_by_user" not in st.session_state: st.session_state.generation_cancelled_by_user = False
if "http_referer" not in st.session_state: st.session_state.http_referer = "http://localhost:8501"
if "regenerate_request" not in st.session_state: st.session_state.regenerate_request = False
if "pending_llm_automation" not in st.session_state: st.session_state.pending_llm_automation = None
if not st.session_state.current_chat_id or st.session_state.current_chat_id not in st.session_state.all_chats:
    if st.session_state.all_chats: 
        sorted_initial_chats = sorted(list(st.session_state.all_chats.items()), key=lambda item: (not item[1].get("is_pinned", False), item[1].get("pinned_at") or item[1]['created_at']), reverse=True)
        if sorted_initial_chats: st.session_state.current_chat_id = sorted_initial_chats[0][0]
        else: create_new_chat(title_prefix="Chat Awal")
    else: create_new_chat(title_prefix="Chat Awal")


# --- UI Streamlit ---
# ... (sama seperti v1.1.13 hingga bagian akhir loop proses input)
active_chat_title = "Chatbot"
if st.session_state.current_chat_id and st.session_state.current_chat_id in st.session_state.all_chats:
    active_chat_title = st.session_state.all_chats[st.session_state.current_chat_id].get('title', 'Chat Aktif')
st.set_page_config(page_title=f"AI Chatbot ({active_chat_title})", layout="wide", initial_sidebar_state="expanded")
st.title("🚀 AI Chatbot NextGen 🚀"); st.caption(f"Versi: {st.session_state.app_version} | Chat: {active_chat_title} (GMT+7)")

# Sidebar (Tata letak tombol feedback disesuaikan di Area Chat Utama)
with st.sidebar:
    st.header("💬 Sesi Chat")
    if st.button("➕ New Chat", use_container_width=True, key="new_chat_button_v1113"): create_new_chat(); st.rerun()
    if st.button("⚠️ Hapus Semua Riwayat Chat", use_container_width=True, type="secondary", help="Menghapus semua sesi chat.", key="reset_all_chats_button_v1113"): reset_all_chats_action(); st.rerun()
    st.markdown("---"); st.subheader("Recent Chats")
    chat_items_for_sort = list(st.session_state.all_chats.items())
    sorted_chat_items = sorted(chat_items_for_sort, key=lambda item: (not item[1].get("is_pinned", False), item[1].get("pinned_at", item[1]['created_at']) if item[1].get("is_pinned", False) else item[1]['created_at']), reverse=True)
    if not sorted_chat_items:
        st.caption("Belum ada chat.")
        if not st.session_state.current_chat_id: create_new_chat(title_prefix="Chat Awal"); st.rerun()
    for chat_id_key, chat_info in sorted_chat_items[:15]:
        if chat_id_key not in st.session_state.all_chats: continue
        label = chat_info.get('title', chat_id_key); is_pinned = chat_info.get("is_pinned", False)
        is_renaming_this_chat = st.session_state.renaming_chat_id == chat_id_key
        col_pin, col_title_or_input, col_actions = st.columns([0.15, 0.7, 0.15])
        with col_pin:
            if not is_renaming_this_chat:
                pin_icon = "📌" if is_pinned else "📍"; pin_help = "Lepas Sematan" if is_pinned else "Sematkan Chat"
                if st.button(pin_icon, key=f"pin_{chat_id_key}", help=pin_help, use_container_width=True): toggle_pin_chat(chat_id_key); st.rerun()
        with col_title_or_input:
            if is_renaming_this_chat:
                rename_input_key = f"rename_input_{chat_id_key}"
                st.text_input("Nama baru:", value=label, key=rename_input_key, on_change=handle_rename_chat_submit, args=(chat_id_key, rename_input_key), label_visibility="collapsed")
            else:
                display_label = f"{'📌 ' if is_pinned else ''}{label}"
                button_type = "primary" if chat_id_key == st.session_state.current_chat_id else "secondary"
                if st.button(display_label, key=f"switch_{chat_id_key}", use_container_width=True, type=button_type, help=f"Buka: {label}"):
                    if st.session_state.current_chat_id != chat_id_key: switch_chat(chat_id_key); st.session_state.active_chat_search_query = ""; st.rerun()
        with col_actions:
            if is_renaming_this_chat:
                if st.button("💾", key=f"save_rename_{chat_id_key}", help="Simpan Nama", use_container_width=True): handle_rename_chat_submit(chat_id_key, f"rename_input_{chat_id_key}"); st.rerun() 
            else:
                if st.button("✏️", key=f"rename_start_{chat_id_key}", help="Ganti Nama", use_container_width=True): st.session_state.renaming_chat_id = chat_id_key; st.rerun()
                # Tombol delete dipindah ke bawah agar tidak terlalu ramai jika rename dan delete digabung
        # Tombol delete di luar kolom rename/save agar selalu terlihat jika tidak sedang rename
        if not is_renaming_this_chat:
             # Buat kolom baru hanya untuk delete jika perlu, atau letakkan di bawah
             # Untuk sederhana, kita letakkan delete di kolom yang sama dengan rename start, tapi pakai if.
             # Ini akan membuat tombol delete hanya muncul jika tidak rename, dan di kolom aksi.
             with col_actions: # Gunakan kolom yang sama tapi hanya jika tidak rename.
                 if st.button("🗑️", key=f"delete_action_sidebar_{chat_id_key}", help="Hapus Chat", use_container_width=True):
                    title_deleted = st.session_state.all_chats[chat_id_key]['title']; del st.session_state.all_chats[chat_id_key]; st.toast(f"Chat '{title_deleted}' dihapus.", icon="🗑️")
                    if st.session_state.current_chat_id == chat_id_key:
                        remaining_ids_sorted = sorted(list(st.session_state.all_chats.items()), key=lambda item: (not item[1].get("is_pinned", False), item[1].get("pinned_at") or item[1]['created_at']), reverse=True)
                        if remaining_ids_sorted: st.session_state.current_chat_id = remaining_ids_sorted[0][0]
                        else: create_new_chat(title_prefix="Chat Awal")
                        st.session_state.active_chat_search_query = ""
                    st.rerun()


    st.markdown("---"); st.header("🛠️ Pengaturan Global")
    with st.expander("✨ Atur Gaya, Suhu & Model AI", expanded=True):
        model_options = list(AVAILABLE_MODELS.keys())
        if st.session_state.selected_model_name not in model_options: st.session_state.selected_model_name = model_options[0]
        current_model_idx_sb = model_options.index(st.session_state.selected_model_name)
        st.session_state.selected_model_name = st.selectbox("Pilih Model AI:", options=model_options, key="model_selector_main_ui_v1113", index=current_model_idx_sb) 
        selected_model_info = AVAILABLE_MODELS[st.session_state.selected_model_name] 
        selected_model_id = selected_model_info["id"]
        st.markdown("---"); st.markdown("#### **Pengaturan Gaya & Kreativitas**")
        persona_options = list(PREDEFINED_PERSONAS.keys())
        if st.session_state.selected_persona_name not in persona_options: st.session_state.selected_persona_name = "Asisten Umum (Default)"
        current_persona_idx_sb = persona_options.index(st.session_state.selected_persona_name)
        st.selectbox("Pilih Gaya/Persona Bot:", options=persona_options, key="persona_selector_key_v119", index=current_persona_idx_sb, on_change=update_system_prompt_from_persona_callback, help="Pilih peran dasar bot.")
        st.session_state.system_prompt = st.text_area("System Prompt:", value=st.session_state.system_prompt, height=150, key="system_prompt_main_ui_v1113", help="Instruksi perilaku bot.") 
        st.session_state.temperature = st.slider("Suhu Kreativitas:", min_value=0.0, max_value=1.0, value=st.session_state.temperature, step=0.05, help="Rendah = fokus. Tinggi = kreatif.")
        st.session_state.max_history_length = st.slider("Riwayat Konteks (Pesan):", min_value=2, max_value=30, value=st.session_state.get("max_history_length", DEFAULT_MAX_HISTORY_LENGTH), step=1, help="Jumlah pesan terakhir dalam konteks LLM.")
        st.caption(f"Model aktif: {st.session_state.selected_model_name}.")
    st.markdown("---"); st.caption(f"ID Model: `{selected_model_id}`")
    st.markdown(f"<div style='text-align: center; font-size: 0.8em;'>Powered by OpenRouter.ai | {st.session_state.app_version}</div>", unsafe_allow_html=True)

# --- Area Chat Utama ---
search_col1, search_col2 = st.columns([0.85, 0.15])
with search_col1: st.session_state.active_chat_search_query = st.text_input("Cari di chat ini:", value=st.session_state.get("active_chat_search_query", ""), placeholder="Ketik untuk mencari...", key="search_in_chat_input_v1113", label_visibility="collapsed").strip()
with search_col2:
    if st.button("Bersihkan", key="clear_search_button_v1113", use_container_width=True, help="Bersihkan pencarian"): st.session_state.active_chat_search_query = ""; st.rerun()

if st.session_state.get("generation_cancelled_by_user", False) and st.session_state.current_chat_id :
    cancelled_message_text = "🛑 Generasi dihentikan oleh pengguna."
    current_msgs_list = get_current_chat_messages()
    if not current_msgs_list or not (current_msgs_list[-1]["role"] == "assistant" and current_msgs_list[-1]["content_text"] == cancelled_message_text):
        append_message_to_current_chat("assistant", cancelled_message_text)
    st.toast("Generasi telah dibatalkan.", icon="🛑")
    st.session_state.generating = False; st.session_state.stop_generating = False; st.session_state.generation_cancelled_by_user = False
    st.rerun()

current_chat_messages_list_main_all = get_current_chat_messages()
messages_to_display = current_chat_messages_list_main_all
if st.session_state.active_chat_search_query:
    query = st.session_state.active_chat_search_query.lower()
    messages_to_display = [msg for msg in current_chat_messages_list_main_all if query in msg.get("content_text", "").lower()]
    if not messages_to_display: st.info(f"Tidak ada pesan yang cocok dengan '{st.session_state.active_chat_search_query}'.")

for i, chat_item_display in enumerate(messages_to_display):
    original_message_object, original_message_index = None, -1
    all_current_messages_for_idx_search = get_current_chat_messages() # Ambil list pesan asli untuk pencarian index
    try:
        original_index = next(idx for idx, original_item in enumerate(all_current_messages_for_idx_search) if original_item.get("timestamp") == chat_item_display.get("timestamp") and original_item.get("role") == chat_item_display.get("role") and original_item.get("content_text") == chat_item_display.get("content_text"))
        original_message_object = all_current_messages_for_idx_search[original_index]
    except StopIteration: original_message_index = i; original_message_object = chat_item_display # Fallback

    avatar_icon = "👤" if chat_item_display['role'] == "user" else "🤖"
    ts_obj = chat_item_display.get('timestamp', get_gmt7_now())
    with st.chat_message(chat_item_display['role'], avatar=avatar_icon):
        content_to_display = chat_item_display["content_text"]
        if st.session_state.active_chat_search_query:
            search_term = st.session_state.active_chat_search_query
            try:
                highlighted_content = re.sub(f"({re.escape(search_term)})", r"<mark>\1</mark>", content_to_display, flags=re.IGNORECASE)
                st.markdown(highlighted_content, unsafe_allow_html=True)
            except re.error: st.markdown(content_to_display)
        else: st.markdown(content_to_display)
        code_blocks_matches = re.finditer(r"```(\w*)\n([\s\S]*?)\n```", chat_item_display["content_text"])
        for block_idx, match in enumerate(code_blocks_matches):
            lang, code = (match.group(1).strip() or "plaintext"), match.group(2).strip()
            ts_val_for_key = ts_obj.timestamp() if isinstance(ts_obj, datetime.datetime) else hash(str(ts_obj))
            chat_id_for_key = st.session_state.current_chat_id or "no_active_chat"
            msg_idx_for_key = original_index if original_index != -1 else i
            base_key = f"{chat_id_for_key}_{msg_idx_for_key}_{block_idx}_{ts_val_for_key}"
            exp_key, code_key = f"exp_{base_key}", f"code_{base_key}"
            exp_label = f"Kode #{block_idx+1} ({lang})"
            try:
                with st.expander(exp_label, expanded=False, key=exp_key): st.code(code, language=lang, key=code_key)
            except Exception as e: st.error(f"Error expander: {e} (K: {exp_key})")
        
        if chat_item_display['role'] == 'assistant' and original_index != -1:
            feedback_key_base = f"fb_{st.session_state.current_chat_id}_{original_index}_{ts_obj.timestamp()}"
            current_feedback = original_message_object.get("feedback")
            fb_cols = st.columns([0.1, 0.1, 0.8]) # Sesuaikan rasio kolom
            with fb_cols[0]:
                like_txt = "👍 Liked" if current_feedback == "like" else "👍"
                if st.button(like_txt, key=f"{feedback_key_base}_L", help="Suka", use_container_width=True):
                    original_message_object["feedback"] = None if current_feedback == "like" else "like"; st.rerun()
            with fb_cols[1]:
                dis_txt = "👎 Disliked" if current_feedback == "dislike" else "👎"
                if st.button(dis_txt, key=f"{feedback_key_base}_D", help="Tidak Suka", use_container_width=True):
                    original_message_object["feedback"] = None if current_feedback == "dislike" else "dislike"; st.rerun()
        
        is_truly_last_message_in_chat = (original_index == len(all_current_messages_for_idx_search) - 1) if original_index != -1 else False
        caption_cols_main, regen_cols_main = st.columns([0.85,0.15])
        with caption_cols_main: st.caption(f"_{format_timestamp_display(ts_obj)}_")
        if not st.session_state.active_chat_search_query and is_truly_last_message_in_chat and chat_item_display['role'] == 'assistant' and not st.session_state.generating and not str(chat_item_display.get("content_text","")).startswith("🛑"):
            with regen_cols_main:
                ts_val_for_regen = ts_obj.timestamp() if isinstance(ts_obj, datetime.datetime) else hash(str(ts_obj))
                chat_id_for_regen = st.session_state.current_chat_id or "no_chat_regen"
                regen_key_main = f"regen_main_{chat_id_for_regen}_{original_index}_{ts_val_for_regen}"
                if st.button("🔄", key=regen_key_main, help="Regenerate", use_container_width=True): 
                    st.session_state.regenerate_request = True
                    active_chat_msgs = get_current_chat_messages()
                    if active_chat_msgs : active_chat_msgs.pop()
                    st.rerun()

# ... (Sisa logika proses input, LLM call, dll. sama seperti v1.1.12)
# Ganti pemanggilan append_message_to_current_chat untuk menyertakan field feedback saat bot merespons
user_input = st.chat_input(f"Ketik pesan untuk '{active_chat_title}'...", key=f"chat_input_{st.session_state.current_chat_id or 'default_chat_input'}", disabled=st.session_state.generating)
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
        if active_msgs and active_msgs[-1]["role"] == "user": messages_for_llm_call = prepare_messages_for_api(active_msgs, st.session_state.system_prompt)
        elif not active_msgs: messages_for_llm_call = prepare_messages_for_api([], st.session_state.system_prompt)
        else: st.warning("Regenerasi gagal."); st.session_state.generating = False; st.rerun(); process_input_flag = False
    
    elif input_source == "user":
        append_message_to_current_chat("user", user_input)
        st.session_state.active_chat_search_query = "" 
        if user_input.startswith("!"):
            direct_bot_response_content = handle_automation_command(user_input, current_model_info_for_call, get_current_chat_messages()[:-1])
            if st.session_state.get("pending_llm_automation"):
                pending_task = st.session_state.pending_llm_automation
                messages_for_llm_call, current_model_id_for_call = pending_task["messages"], pending_task.get("model_id", current_model_id_for_call)
                st.session_state.pending_llm_automation = None
        else: messages_for_llm_call = prepare_messages_for_api(get_current_chat_messages(), st.session_state.system_prompt)
    
    elif input_source == "automation":
        pending_task = st.session_state.pending_llm_automation
        messages_for_llm_call, current_model_id_for_call = pending_task["messages"], pending_task.get("model_id", current_model_id_for_call)
        st.session_state.pending_llm_automation = None

    if direct_bot_response_content:
        append_message_to_current_chat("assistant", direct_bot_response_content, feedback=None) # Tambah feedback=None
        st.session_state.generating = False; st.rerun()
    
    elif messages_for_llm_call and process_input_flag:
        model_name_for_status = next((name for name, info in AVAILABLE_MODELS.items() if info["id"] == current_model_id_for_call), st.session_state.selected_model_name)
        with st.chat_message("assistant", avatar="🤖"):
            with st.status(f"🤖 Bot ({model_name_for_status}) mengetik...", expanded=True) as status_indicator:
                cancel_key = f"cancel_btn_{st.session_state.current_chat_id or 'no_id'}_{get_gmt7_now().timestamp()}"
                if st.button("Batalkan Generasi ⏹️", key=cancel_key):
                    st.session_state.stop_generating, st.session_state.generation_cancelled_by_user = True, True
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
            bot_ts = get_gmt7_now()
            if full_bot_response or st.session_state.generation_cancelled_by_user: st.caption(f"_{format_timestamp_display(bot_ts)}_")
        
        if not st.session_state.generation_cancelled_by_user:
            if full_bot_response: 
                append_message_to_current_chat("assistant", full_bot_response, bot_ts, feedback=None) # Tambah feedback=None saat buat pesan bot
                if not full_bot_response.startswith("🛑"): 
                    st.session_state.play_sound_once = True # Set flag untuk mainkan suara
            
            st.session_state.generating = False; st.session_state.stop_generating = False
            # Pindahkan pemutaran suara setelah rerun agar komponen HTML dirender di tempat yang benar
            # Untuk ini, kita perlu sedikit trik atau memanggilnya sebelum rerun jika toast tidak mengganggu
            if st.session_state.get("play_sound_once"):
                 play_notification_sound() # Panggil sebelum rerun agar komponen HTML sempat dirender
            st.rerun()


elif not process_input_flag and st.session_state.generating and not st.session_state.generation_cancelled_by_user:
    st.warning("State anomali. Mereset..."); st.session_state.generating = False; st.session_state.stop_generating = False; st.rerun()

# Pemutaran suara yang lebih terkontrol di akhir script jika flag diset
# Ini mungkin cara yang lebih baik daripada memanggilnya sebelum rerun di atas.
if st.session_state.get("play_sound_once_after_rerun", False):
    play_notification_sound(SOUND_NOTIFICATION_FILE)
    st.session_state.play_sound_once_after_rerun = False # Reset flag setelah diputar
