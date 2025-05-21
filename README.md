# AI Chatbot (chatai.py)

## Deskripsi
`chatai.py` adalah aplikasi chatbot berbasis web yang dibangun menggunakan Streamlit dan terintegrasi dengan model AI melalui OpenRouter API. Aplikasi ini mendukung multi-chat, ekspor/impor riwayat, multi-persona, serta pengaturan model dan kreativitas secara interaktif.

## Fitur Utama
- **Multi-Model AI**: Pilih model AI (misal: Meta Llama 3 8B, DeepSeek Chat V3) secara dinamis.
- **Multi-Chat**: Setiap sesi chat disimpan terpisah, dapat diganti nama, dihapus, dan diatur judul otomatis.
- **Ekspor/Impor Riwayat**: Chat dapat diekspor ke format JSON, TXT, atau Markdown, serta diimpor kembali.
- **Persona Bot**: Pilih persona (asisten umum, penulis kreatif, pakar sejarah, penerjemah, guru matematika) atau atur prompt sistem sendiri.
- **Kontrol Kreativitas**: Slider untuk mengatur temperature (0.0-1.0) yang mempengaruhi kreativitas respons AI.
- **Perintah Otomatis**: Mendukung perintah seperti `!help`, `!info_model`, `!waktu`, `!summarize_chat` untuk bantuan, info model, waktu server, dan ringkasan chat.
- **Streaming Respons**: Respons AI tampil secara real-time, dapat dibatalkan oleh pengguna.
- **Salin Cepat**: Fitur untuk menyalin respons terakhir bot.
- **UI Interaktif**: Sidebar untuk navigasi chat, pengaturan model, persona, dan ekspor/impor.

## Struktur Kode Utama
- **Konfigurasi & Inisialisasi**: Penentuan model, persona, dan session state.
- **Fungsi Helper**: Parsing riwayat, format timestamp, update judul chat, dsb.
- **Manajemen Chat**: Buat chat baru, ganti nama, hapus, switch chat.
- **Streaming & Kontrol**: Fungsi utama untuk streaming respons AI, pembatalan, dan penanganan error.
- **UI Streamlit**: Sidebar (navigasi chat, pengaturan global), area utama (tampilan chat, input, tombol kontrol).

## Alur Utama Penggunaan
1. Pilih atau buat chat baru di sidebar.
2. Pilih model AI, persona, dan atur prompt sistem jika perlu.
3. Mulai percakapan di area utama, gunakan perintah khusus jika dibutuhkan.
4. Ekspor atau impor riwayat chat sesuai kebutuhan.
5. Gunakan tombol "Regenerate" untuk mengulang respons bot, atau "Batalkan" untuk menghentikan streaming.

## Dependensi
- Python 3.x
- Streamlit
- requests
- json
- datetime
- re

## Cara Menjalankan
1. Install dependensi: `pip install streamlit requests`
2. Tambahkan API key OpenRouter di `.streamlit/secrets.toml`:
   ```toml
   OPENROUTER_API_KEY="sk-or-v1-..."
   ```
3. Jalankan aplikasi:
   ```bash
   streamlit run chatai.py
   ```

## Catatan
- Pastikan koneksi internet aktif.
- API key harus valid agar aplikasi dapat berjalan.
- Semua chat disimpan di session state (memori), ekspor jika ingin menyimpan permanen.

---
Dibuat dengan ❤️ oleh tim pengembang AI Chatbot NextGen.
