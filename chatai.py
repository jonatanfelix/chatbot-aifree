import streamlit as st
import requests
import json
import datetime
import re

APP_VERSION = "v1.1.5 - Robust Cancellation Flow"
DEFAULT_MODEL_NAME = "Meta Llama 3 8B Instruct"
DEFAULT_SYSTEM_PROMPT = "Anda adalah asisten AI yang serbaguna dan ramah. Selalu odgovori dalam Bahasa Indonesia kecuali diminta lain."
AVAILABLE_MODELS = {
    "Meta Llama 3 8B Instruct": {"id": "meta-llama/llama-3-8b-instruct", "vision": False, "max_tokens": 8192, "free": True},
    "DeepSeek Chat V3 0324 (free)": {"id": "deepseek/deepseek-chat-v3-0324:free", "vision": False, "max_tokens": 163840, "free": True}
}
if not AVAILABLE_MODELS:
    st.error("Kritis: Tidak ada model yang terdefinisi dalam AVAILABLE_MODELS.")
    st.stop()
if DEFAULT_MODEL_NAME not in AVAILABLE_MODELS:
    DEFAULT_MODEL_NAME = list(AVAILABLE_MODELS.keys())[0] if AVAILABLE_MODELS else None
    if not DEFAULT_MODEL_NAME:
        st.error("Kritis: Tidak ada model default yang bisa diatur.")
        st.stop()
MAX_HISTORY_MESSAGES_TO_SEND = 10
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
except (FileNotFoundError, KeyError):
    st.error("CRITICAL ERROR: File `secrets.toml` atau `OPENROUTER_API_KEY` tidak ditemukan.")
    st.markdown("Pastikan Anda memiliki file `.streamlit/secrets.toml` dengan isi:\n```toml\nOPENROUTER_API_KEY=\"sk-or-v1-your-actual-api-key\"\n```")
    st.stop()
def get_bot_response_stream(messages_for_api, selected_model_id, temperature):
    payload = {
        "model": selected_model_id,
        "messages": messages_for_api,
        "stream": True,
        "temperature": temperature
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": st.session_state.get("http_referer", "http://localhost:8501"),
        "X-Title": f"Ai Chatbot Streamlit ({st.session_state.get('app_version', APP_VERSION)})"
    }
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    response = None
    try:
        response = requests.post(API_URL, headers=headers, json=payload, stream=True, timeout=180)
        response.raise_for_status()
        for line in response.iter_lines():
            if st.session_state.get("stop_generating", False):
                yield "🛑 Generasi dihentikan oleh pengguna."
                break
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    json_str = decoded_line[len("data: "):]
                    if json_str.strip() == "[DONE]": 
                        break
                    try:
                        data = json.loads(json_str)
                        if data.get("choices") and len(data["choices"]) > 0:
                            chunk = data["choices"][0].get("delta", {}).get("content")
                            if chunk:
                                yield chunk
                    except json.JSONDecodeError: pass
    except requests.exceptions.HTTPError as http_err:
        error_detail = ""
        if response is not None and response.text:
            try:
                error_json = response.json()
                error_detail = f" Pesan API: {error_json.get('error', {}).get('message', response.text[:200])}"
            except json.JSONDecodeError: error_detail = f" Detail: {response.text[:200]}"
        error_message = f"⚠️ HTTP error {response.status_code if response else ''}: {http_err}.{error_detail}"
        st.error(error_message); yield f"🛑 {error_message}"
    except requests.exceptions.ConnectionError as conn_err:
        error_message = f"⚠️ Gagal terhubung: {conn_err}."
        st.error(error_message); yield f"🛑 {error_message}"
    except requests.exceptions.Timeout:
        error_message = "⚠️ Permintaan timeout. Coba lagi nanti."
        st.error(error_message); yield f"🛑 {error_message}"
    except Exception as e:
        error_message = f"⚠️ Kesalahan tak terduga: {str(e)[:200]}."
        st.error(error_message); yield f"🛑 {error_message}"
def format_timestamp(ts_obj):
    if isinstance(ts_obj, str):
        try: ts_obj = datetime.datetime.fromisoformat(ts_obj)
        except ValueError: return ts_obj
    if isinstance(ts_obj, datetime.datetime): return ts_obj.strftime("%H:%M:%S")
    return "N/A"
def prepare_messages_for_api(history, system_prompt):
    messages = [{"role": "system", "content": system_prompt}]
    relevant_history = history[-(MAX_HISTORY_MESSAGES_TO_SEND):]
    for msg in relevant_history:
        messages.append({"role": msg["role"], "content": str(msg.get("content_text",""))})
    return messages
def handle_automation_command(command_input, current_model_info, chat_history_list):
    parts = command_input.strip().split(" ", 1)
    command = parts[0].lower()
    if command == "!help" or command == "!bantuan":
        return """
        **Perintah yang Tersedia:**
        - `!help` atau `!bantuan`: Menampilkan bantuan ini.
        - `!info_model`: Info model AI yang aktif.
        - `!waktu`: Waktu server saat ini.
        - `!summarize_chat`: Merangkum percakapan ini.
        Untuk tugas lain (merangkum teks, menerjemahkan, dll.), ketik permintaan Anda dalam bahasa alami.
        """
    elif command == "!info_model":
        model_display_name = st.session_state.selected_model_name
        return f"**Info Model:**\n- Nama Tampilan: {model_display_name}\n- ID: `{current_model_info['id']}`\n- Max Tokens: {current_model_info.get('max_tokens', 'N/A')}"
    elif command == "!waktu":
        return f"Waktu server: {datetime.datetime.now().strftime('%H:%M:%S, %d %B %Y')}"
    elif command == "!summarize_chat":
        if not chat_history_list: return "Riwayat chat kosong."
        conversation_to_summarize = [ f"{msg['role']}: {msg['content_text']}" for msg in chat_history_list if msg.get('content_text') and not str(msg.get('content_text', '')).startswith("🛑") and msg['role'] in ['user', 'assistant']]
        formatted_history = "\n".join(conversation_to_summarize)
        if not formatted_history.strip(): return "Tidak ada percakapan yang cukup untuk dirangkum."
        st.info(f"Merangkum {len(conversation_to_summarize)} pesan...")
        messages_for_llm_automation = [{"role": "system", "content": "You are an AI specialized in summarizing conversations concisely."}, {"role": "user", "content": f"Summarize the key points of the following conversation:\n\n---\n{formatted_history}\n---"}]
        st.session_state.pending_llm_automation = {"messages": messages_for_llm_automation, "model_id": current_model_info["id"]}
        return None
    return f"Perintah '{command}' tidak dikenali. Ketik `!help`."
PREDEFINED_PERSONAS = {
    "Asisten Umum (Default)": DEFAULT_SYSTEM_PROMPT,
    "Penulis Kreatif": "Anda adalah seorang penulis cerita dan puisi yang imajinatif. Hasilkan teks yang puitis, mendalam, dan membangkitkan emosi. Gunakan gaya bahasa yang kaya.",
    "Pakar Sejarah": "Anda adalah seorang sejarawan dengan pengetahuan luas. Jawab pertanyaan tentang sejarah dengan detail, akurat, dan sertakan konteks yang relevan. Bersikaplah objektif.",
    "Penerjemah Ahli": "Anda adalah penerjemah bahasa profesional. Terjemahkan teks antar bahasa dengan akurat, mempertahankan nuansa dan makna asli. Sebutkan bahasa sumber dan target jika tidak jelas.",
    "Guru Matematika": "Anda adalah seorang guru matematika yang sabar. Jelaskan konsep matematika yang sulit dengan cara yang mudah dimengerti. Berikan contoh dan langkah-langkah penyelesaian."
}
if "app_version" not in st.session_state: st.session_state.app_version = APP_VERSION
if "chat_history" not in st.session_state: st.session_state.chat_history = []
current_selected_model_name_in_state = st.session_state.get("selected_model_name", DEFAULT_MODEL_NAME)
if current_selected_model_name_in_state not in AVAILABLE_MODELS:
    st.session_state.selected_model_name = DEFAULT_MODEL_NAME
else:
    st.session_state.selected_model_name = current_selected_model_name_in_state
if "system_prompt" not in st.session_state: st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT
if "selected_persona_name" not in st.session_state:
    st.session_state.selected_persona_name = "Asisten Umum (Default)"
if "temperature" not in st.session_state: st.session_state.temperature = 0.7
if "generating" not in st.session_state: st.session_state.generating = False
if "stop_generating" not in st.session_state: st.session_state.stop_generating = False
if "generation_cancelled_by_user" not in st.session_state: st.session_state.generation_cancelled_by_user = False
if "http_referer" not in st.session_state: st.session_state.http_referer = "http://localhost:8501"
if "regenerate_request" not in st.session_state: st.session_state.regenerate_request = False
if "pending_llm_automation" not in st.session_state: st.session_state.pending_llm_automation = None
if "persona_selector_key_v110" not in st.session_state:
    active_persona = st.session_state.get("selected_persona_name", "Asisten Umum (Default)")
    if active_persona not in PREDEFINED_PERSONAS:
        active_persona = "Asisten Umum (Default)"
    st.session_state.persona_selector_key_v110 = active_persona
def update_system_prompt_from_persona_callback():
    selected_persona = st.session_state.persona_selector_key_v110
    st.session_state.selected_persona_name = selected_persona
    st.session_state.system_prompt = PREDEFINED_PERSONAS.get(selected_persona, DEFAULT_SYSTEM_PROMPT)
st.set_page_config(page_title="AI Chatbot NextGen", layout="wide", initial_sidebar_state="expanded")
st.title("🚀 AI Chatbot NextGen 🚀")
st.caption(f"Versi: {st.session_state.app_version}")
with st.sidebar:
    st.header("🛠️ Kontrol & Pengaturan")
    with st.expander("✨ Atur Gaya, Suhu & Model AI", expanded=True):
        model_options = list(AVAILABLE_MODELS.keys())
        if not model_options:
            st.error("Tidak ada model AI yang tersedia. Silakan periksa konfigurasi.")
            st.stop()
        if st.session_state.selected_model_name not in model_options:
            st.session_state.selected_model_name = model_options[0]
        current_model_idx_sb = model_options.index(st.session_state.selected_model_name)
        st.session_state.selected_model_name = st.selectbox(
            "Pilih Model AI (Gratis):", options=model_options,
            key="model_selector_ui_v110", index=current_model_idx_sb
        )
        selected_model_info = AVAILABLE_MODELS[st.session_state.selected_model_name]
        selected_model_id = selected_model_info["id"]
        st.markdown("---")
        st.markdown("#### **Pengaturan Gaya & Kreativitas**")
        persona_options = list(PREDEFINED_PERSONAS.keys())
        try:
            current_persona_idx_sb = persona_options.index(st.session_state.selected_persona_name)
        except ValueError:
             st.session_state.selected_persona_name = "Asisten Umum (Default)"
             current_persona_idx_sb = persona_options.index("Asisten Umum (Default)")
        st.selectbox(
            "Pilih Gaya/Persona Bot:", options=persona_options,
            key="persona_selector_key_v110",
            index=current_persona_idx_sb,
            on_change=update_system_prompt_from_persona_callback,
            help="Pilih peran atau gaya respons dasar untuk bot."
        )
        st.session_state.system_prompt = st.text_area(
            "System Prompt (Instruksi Perilaku Bot):", value=st.session_state.system_prompt,
            height=150, key="system_prompt_ui_v110",
            help="Instruksi detail untuk memandu perilaku, nada, dan fokus bot. Diperbarui otomatis saat memilih persona, namun bisa diubah manual."
        )
        st.session_state.temperature = st.slider(
            "Suhu Kreativitas (Temperature):", min_value=0.0, max_value=1.0,
            value=st.session_state.temperature, step=0.05,
            help="Nilai rendah (mis. 0.1-0.3) = jawaban lebih fokus & konsisten.\nNilai tinggi (mis. 0.7-1.0) = jawaban lebih kreatif & beragam."
        )
        st.caption(f"Model aktif: {st.session_state.selected_model_name}. Hanya input teks.")
    with st.expander("📜 Riwayat Percakapan", expanded=False):
        st.markdown("Riwayat chat disimpan sementara. Gunakan Unduh/Unggah untuk menyimpan permanen.")
        if st.button("Hapus Percakapan 🗑️", use_container_width=True, type="secondary", key="clear_chat_v110"):
            st.session_state.chat_history = [];
            st.session_state.generating = False;
            st.session_state.stop_generating = False
            st.session_state.generation_cancelled_by_user = False
            st.toast("Riwayat percakapan dihapus!", icon="🗑️"); st.rerun()
        if st.session_state.chat_history:
            col_dl1, col_dl2, col_dl3 = st.columns(3)
            history_for_json_download = []
            for item in st.session_state.chat_history:
                dl_item = {"role": item["role"], "content_text": item.get("content_text"), "timestamp": item.get("timestamp")}
                if isinstance(dl_item.get('timestamp'), datetime.datetime): 
                    dl_item['timestamp'] = dl_item['timestamp'].isoformat()
                history_for_json_download.append(dl_item)
            chat_history_json_str = json.dumps(history_for_json_download, indent=2,ensure_ascii=False)
            col_dl1.download_button(label="JSON 💾", data=chat_history_json_str, file_name=f"chat_history_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json", mime="application/json", use_container_width=True, key="download_json_v110")
            txt_history_lines = [f"[{format_timestamp(msg['timestamp'])}] {msg['role'].capitalize()}: {msg['content_text']}" for msg in st.session_state.chat_history]
            chat_history_txt_str = "\n\n".join(txt_history_lines)
            col_dl2.download_button(label="TXT 📝", data=chat_history_txt_str, file_name=f"chat_history_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", mime="text/plain", use_container_width=True, key="download_txt_v110")
            md_history_lines = []
            for msg in st.session_state.chat_history:
                role_prefix = f"**{msg['role'].capitalize()}**"
                timestamp_str = format_timestamp(msg.get('timestamp', ''))
                md_history_lines.append(f"*{timestamp_str}* - {role_prefix}:\n{msg.get('content_text', '')}\n")
            chat_history_md_str = "\n---\n".join(md_history_lines)
            col_dl3.download_button(label="Markdown 📜", data=chat_history_md_str, file_name=f"chat_history_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md", mime="text/markdown", use_container_width=True, key="download_md_v110")
        uploaded_file_history = st.file_uploader("Unggah Riwayat Teks (JSON)", type="json", key="upload_chat_history_v110")
        if uploaded_file_history is not None:
            try:
                new_history_raw = json.load(uploaded_file_history)
                new_history_processed = []
                if isinstance(new_history_raw, list):
                    for item_raw in new_history_raw:
                        if isinstance(item_raw, dict) and 'role' in item_raw and item_raw.get('content_text') is not None:
                            ts_data = item_raw.get('timestamp')
                            if isinstance(ts_data, str):
                                try: timestamp_obj = datetime.datetime.fromisoformat(ts_data)
                                except ValueError: timestamp_obj = datetime.datetime.now()
                            elif isinstance(ts_data, datetime.datetime):
                                timestamp_obj = ts_data
                            else: timestamp_obj = datetime.datetime.now()
                            item_processed = {
                                "role": item_raw["role"],
                                "content_text": item_raw["content_text"],
                                "timestamp": timestamp_obj
                            }
                            new_history_processed.append(item_processed)
                        else: st.warning(f"Item riwayat tidak valid dilewati: {str(item_raw)[:100]}")
                    if new_history_processed:
                        st.session_state.chat_history = new_history_processed
                        st.toast(f"Riwayat percakapan ({len(new_history_processed)} pesan) berhasil dimuat!", icon="✅"); st.rerun()
                    else: st.error("Tidak ada item riwayat yang valid ditemukan dalam file JSON.")
                else: st.error("Format file JSON tidak valid (bukan list).")
            except Exception as e: st.error(f"Terjadi kesalahan saat memuat riwayat: {e}")
    if st.session_state.get("last_bot_response_for_copy"):
        if st.button("Salin Pesan Terakhir Bot 📋", use_container_width=True, key="copy_btn_v110"):
            st.text_area("Teks untuk disalin:", st.session_state.last_bot_response_for_copy, height=100, key="copy_area_sidebar_v110", label_visibility="collapsed")
            st.toast(f"Teks siap disalin dari area di atas.", icon="📋")
    st.markdown("---")
    st.caption(f"ID Model Aktif: `{selected_model_id}`")
    st.markdown(f"<div style='text-align: center; font-size: 0.8em;'>Powered by OpenRouter.ai | {st.session_state.app_version}</div>", unsafe_allow_html=True)
if st.session_state.get("generation_cancelled_by_user", False):
    cancelled_message_text = "🛑 Generasi dihentikan oleh pengguna."
    add_cancel_message = True
    if st.session_state.chat_history:
        last_msg = st.session_state.chat_history[-1]
        if last_msg["role"] == "assistant" and last_msg["content_text"] == cancelled_message_text:
            pass
    if add_cancel_message:
        bot_response_data = {"role": "assistant", "content_text": cancelled_message_text, "timestamp": datetime.datetime.now()}
        st.session_state.chat_history.append(bot_response_data)
        st.session_state.last_bot_response_for_copy = cancelled_message_text
    st.toast("Generasi telah dibatalkan.", icon="🛑")
    st.session_state.generating = False
    st.session_state.stop_generating = False
    st.session_state.generation_cancelled_by_user = False
    st.rerun()
if not st.session_state.chat_history:
    initial_greeting = f"Halo! Saya adalah asisten AI (Model: **{st.session_state.selected_model_name}**). Persona: **{st.session_state.selected_persona_name}**. Ketik `!help` untuk perintah."
    st.session_state.chat_history.append({
        "role": "assistant", "content_text": initial_greeting, "timestamp": datetime.datetime.now()
    })
for i, chat_item in enumerate(st.session_state.chat_history):
    avatar_icon = "👤" if chat_item['role'] == "user" else "🤖"
    ts_obj = chat_item.get('timestamp', datetime.datetime.now())
    with st.chat_message(chat_item['role'], avatar=avatar_icon):
        if chat_item.get("content_text"):
            st.markdown(chat_item["content_text"])
            code_blocks_matches = re.finditer(r"```(\w*)\n([\s\S]*?)\n```", chat_item["content_text"])
            code_blocks_parsed = []
            for match in code_blocks_matches:
                language = match.group(1).strip() if match.group(1) else None
                code_content = match.group(2).strip()
                code_blocks_parsed.append({"language": language, "code": code_content})
            if code_blocks_parsed:
                for block_index, block_data in enumerate(code_blocks_parsed):
                    exp_key = f"expander_code_{i}_{block_index}"
                    code_key = f"code_block_{i}_{block_index}"
                    with st.expander(f"Blok Kode #{block_index+1} (Bahasa: {block_data['language'] or 'Tidak terdeteksi'})", expanded=False, key=exp_key):
                        st.code(block_data["code"], language=block_data["language"], key=code_key)
        is_last_message = (i == len(st.session_state.chat_history) - 1)
        is_assistant = chat_item['role'] == 'assistant'
        not_error_message = not str(chat_item.get("content_text","")) .startswith("🛑")
        if is_assistant and is_last_message and not st.session_state.generating and not_error_message:
            regen_key = f"regen_v110_{i}_{str(ts_obj).replace(' ','_')}"
            if st.button("Regenerate 🔄", key=regen_key, help="Minta bot menghasilkan ulang respons ini"):
                st.session_state.regenerate_request = True
                if st.session_state.chat_history:
                    st.session_state.chat_history.pop();
                st.rerun()
        st.caption(f"_{format_timestamp(ts_obj)}_")
user_input = st.chat_input("Ketik pesan atau perintah `!help`...", key="main_chat_input_v110", disabled=st.session_state.generating)
process_input_flag = False
input_source = None
if user_input:
    process_input_flag = True
    input_source = "user"
elif st.session_state.get("regenerate_request", False):
    process_input_flag = True
    input_source = "regenerate"
elif st.session_state.get("pending_llm_automation"):
    process_input_flag = True
    input_source = "automation"
if process_input_flag and not st.session_state.generating:
    st.session_state.generating = True
    st.session_state.stop_generating = False
    st.session_state.generation_cancelled_by_user = False
    messages_for_llm_call = None
    direct_bot_response_content = None
    current_model_id_for_call = selected_model_id
    if input_source == "regenerate":
        st.session_state.regenerate_request = False
        if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
            messages_for_llm_call = prepare_messages_for_api(st.session_state.chat_history, st.session_state.system_prompt)
        else:
            st.warning("Tidak dapat regenerate: Tidak ada pesan pengguna yang sesuai.");
            st.session_state.generating = False; st.rerun()
            process_input_flag = False 
    elif input_source == "user":
        user_message_data = {"role": "user", "timestamp": datetime.datetime.now(), "content_text": user_input}
        st.session_state.chat_history.append(user_message_data)
        if user_input.startswith("!"):
            direct_bot_response_content = handle_automation_command(user_input, selected_model_info, st.session_state.chat_history[:-1])
            if st.session_state.get("pending_llm_automation"):
                pending_task = st.session_state.pending_llm_automation
                messages_for_llm_call = pending_task["messages"]
                current_model_id_for_call = pending_task.get("model_id", selected_model_id)
                st.session_state.pending_llm_automation = None
        else:
            messages_for_llm_call = prepare_messages_for_api(st.session_state.chat_history, st.session_state.system_prompt)
    elif input_source == "automation":
        pending_task = st.session_state.pending_llm_automation
        messages_for_llm_call = pending_task["messages"]
        current_model_id_for_call = pending_task.get("model_id", selected_model_id)
        st.session_state.pending_llm_automation = None
    if direct_bot_response_content:
        bot_response_data = {"role": "assistant", "content_text": direct_bot_response_content, "timestamp": datetime.datetime.now()}
        st.session_state.chat_history.append(bot_response_data)
        st.session_state.last_bot_response_for_copy = direct_bot_response_content
        st.session_state.generating = False
        st.rerun()
    elif messages_for_llm_call and process_input_flag:
        model_name_for_status = st.session_state.selected_model_name
        for name, info in AVAILABLE_MODELS.items():
            if info["id"] == current_model_id_for_call:
                model_name_for_status = name
                break
        with st.chat_message("assistant", avatar="🤖"):
            with st.status(f"🤖 Bot ({model_name_for_status}) sedang mengetik...", expanded=True) as status_indicator:
                cancel_key = f"cancel_gen_btn_{len(st.session_state.chat_history)}_{datetime.datetime.now().timestamp()}"
                if st.button("Batalkan Generasi ⏹️", key=cancel_key):
                    st.session_state.stop_generating = True
                    st.session_state.generation_cancelled_by_user = True 
                    st.toast("Permintaan pembatalan dikirim...", icon="🛑")
                    st.rerun()
                message_placeholder = st.empty()
                full_bot_response = ""
                try:
                    if not st.session_state.generation_cancelled_by_user: 
                        bot_response_generator = get_bot_response_stream(
                            messages_for_llm_call,
                            current_model_id_for_call,
                            st.session_state.temperature
                        )
                        for chunk in bot_response_generator:
                            if st.session_state.stop_generating:
                                break
                            full_bot_response += chunk
                            message_placeholder.markdown(full_bot_response + "▌")
                        message_placeholder.markdown(full_bot_response)
                    if st.session_state.stop_generating:
                        if not "🛑 Generasi dihentikan oleh pengguna." in full_bot_response:
                             full_bot_response += "\n🛑 Generasi dihentikan oleh pengguna."
                        message_placeholder.markdown(full_bot_response)
                        status_indicator.update(label="Generasi dihentikan.", state="error", expanded=False)
                    elif full_bot_response and not full_bot_response.startswith("🛑"):
                        status_indicator.update(label="Respons diterima!", state="complete", expanded=False)
                    elif full_bot_response.startswith("🛑"):
                        status_indicator.update(label="Error dari LLM.", state="error", expanded=False)
                    elif not full_bot_response and not st.session_state.generation_cancelled_by_user :
                        full_bot_response = "(Bot tidak memberikan respons.)"
                        message_placeholder.markdown(full_bot_response)
                        status_indicator.update(label="Selesai (tidak ada output).", state="complete", expanded=False)
                except Exception as e_stream_outer:
                    full_bot_response = f"🛑 Terjadi kesalahan critical saat streaming: {str(e_stream_outer)}"
                    message_placeholder.error(full_bot_response)
                    status_indicator.update(label="Streaming Critical Error!", state="error", expanded=False)
            bot_message_timestamp = datetime.datetime.now()
            if full_bot_response or st.session_state.generation_cancelled_by_user:
                 st.caption(f"_{format_timestamp(bot_message_timestamp)}_")
        if full_bot_response and not st.session_state.generation_cancelled_by_user :
            bot_response_data = {"role": "assistant", "content_text": full_bot_response, "timestamp": bot_message_timestamp}
            st.session_state.chat_history.append(bot_response_data)
            if not full_bot_response.startswith("🛑"):
                st.session_state.last_bot_response_for_copy = full_bot_response
        if not st.session_state.generation_cancelled_by_user:
            st.session_state.generating = False
            st.session_state.stop_generating = False
            st.rerun()
elif not process_input_flag and st.session_state.generating and not st.session_state.generation_cancelled_by_user:
    st.warning("State generating tidak normal terdeteksi. Mereset...")
    st.session_state.generating = False
    st.session_state.stop_generating = False
    st.rerun()