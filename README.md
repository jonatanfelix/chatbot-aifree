# AI Chatbot  

## Deskripsi
AI Chatbot NextGen adalah aplikasi chatbot berbasis web yang dikembangkan menggunakan framework Streamlit. Aplikasi ini menyediakan antarmuka chat yang modern dan interaktif yang terhubung dengan model-model AI terkini melalui OpenRouter API. Dengan fokus pada pengalaman pengguna yang optimal, aplikasi ini dilengkapi dengan berbagai fitur canggih seperti tema yang dapat disesuaikan, pilihan persona AI, dan sistem manajemen percakapan yang lengkap.

### Tujuan Aplikasi
- Menyediakan akses mudah ke model-model AI canggih
- Memfasilitasi interaksi yang natural dengan AI
- Memberikan pengalaman pengguna yang dapat disesuaikan
- Menyimpan dan mengelola riwayat percakapan dengan aman

## Versi
Versi Saat Ini: AI Chatbot NexGen
- Pembaruan terakhir: Mei 2025
- Peningkatan UI/UX
- Penambahan fitur ekspor/impor chat
- Optimalisasi performa streaming

## Fitur Utama dan Fungsi-Fungsi

### Integrasi Model AI
- **Dukungan Multi-Model**
  - Integrasi dengan OpenRouter API untuk akses ke model AI terkini
  - Model default: Meta Llama 3 8B Instruct (optimal untuk tugas umum)
  - Model tambahan: DeepSeek V3
  
- **Kontrol Kreativitas**
  - Pengaturan temperatur (0.0 - 1.0) untuk mengontrol kreativitas respons
  - Temperature rendah (0.0-0.3): Respons lebih konsisten dan faktual
  - Temperature sedang (0.4-0.7): Keseimbangan antara kreativitas dan konsistensi
  - Temperature tinggi (0.8-1.0): Respons lebih kreatif dan bervariasi

### Sistem Persona (get_bot_response_stream)
Fungsi ini mengelola interaksi dengan model AI dan mengatur persona:
- **Persona Bawaan:**
  - Asisten Umum (Default): Cocok untuk percakapan umum dan bantuan sehari-hari
  - Penulis Kreatif: Spesialisasi dalam menulis kreatif dan generasi konten
  - Ahli Sejarah: Memberikan informasi historis dengan konteks yang mendalam
  - Penerjemah Profesional: Membantu dalam terjemahan antar bahasa
  - Guru Matematika: Fokus pada penjelasan konsep matematika
  
- **Kustomisasi Persona**
  - Sistem prompt yang dapat disesuaikan untuk setiap persona
  - Penyimpanan preferensi persona dalam session state
  - Kemampuan untuk membuat persona kustom

### Sistem Tema Visual (get_theme_css_string)
Fungsi ini mengelola tampilan visual aplikasi:
- **Tema Bawaan:**
  - Terang (Streamlit): Tema default yang cerah dan professional
  - Gelap (Kustom): Tema gelap untuk penggunaan malam hari
  - Abu-abu (Kustom): Tema netral yang nyaman dimata
  
- **Fitur Kustomisasi UI:**
  - Penyesuaian warna primer dan sekunder
  - Kustomisasi latar belakang dan teks
  - Pengaturan tampilan widget dan tombol
  - Styling khusus untuk pesan chat

### Manajemen Chat (handle_automation_command)
Fungsi ini mengatur semua aspek percakapan:
- **Streaming Real-time:**
  - Menampilkan respons AI secara progresif
  - Indikator pengetikan yang responsif
  - Penanganan streaming error yang halus
  
- **Pengelolaan Riwayat:**
  - Penyimpanan otomatis setiap percakapan
  - Pembatasan riwayat (10 pesan) untuk optimasi performa
  - Timestamp untuk setiap pesan
  
- **Ekspor/Impor Data:**
  - Format JSON: Untuk backup lengkap dengan metadata
  - Format TXT: Untuk pembacaan mudah
  - Format Markdown: Untuk dokumentasi terformat
  
- **Fitur Tambahan:**
  - Salin cepat respons terakhir
  - Preview pesan sebelum pengiriman
  - Penghapusan riwayat dengan konfirmasi

### Sistem Perintah (handle_automation_command)
Fungsi ini mengatur perintah-perintah khusus dalam chat:

**Perintah Tersedia dan Fungsinya:**
- `!help` atau `!bantuan`
  - Menampilkan daftar perintah yang tersedia
  - Memberikan penjelasan singkat setiap perintah
  - Contoh penggunaan untuk setiap perintah

- `!info_model`
  - Menampilkan informasi detail model AI aktif
  - Menunjukkan parameter-parameter model
  - Menampilkan batasan token dan kemampuan model

- `!waktu`
  - Menampilkan waktu server dalam format lokal
  - Berguna untuk timestamp dan logging

- `!summarize_chat`
  - Menganalisis seluruh percakapan
  - Menghasilkan ringkasan otomatis
  - Menyoroti poin-poin penting diskusi

## Detail Teknis

### Dependensi dan Fungsinya
- **Streamlit**
  - Framework utama untuk UI web
  - Penanganan state dan session
  - Komponen interaktif

- **Requests**
  - Komunikasi dengan OpenRouter API
  - Manajemen response streaming
  - Penanganan error jaringan

- **JSON**
  - Parsing data API
  - Format penyimpanan riwayat
  - Pertukaran data antar komponen

- **Datetime**
  - Pengelolaan timestamp pesan
  - Format waktu yang konsisten
  - Pelacakan durasi sesi

- **Regular Expressions (re)**
  - Parsing format pesan
  - Validasi input
  - Pemrosesan teks khusus

### Konfigurasi Sistem
**Pengaturan Dasar:**
- **API Configuration**
  - OpenRouter API key dalam `.streamlit/secrets.toml`
  - Validasi otomatis konfigurasi saat startup
  - Penanganan error konfigurasi yang user-friendly

- **Batasan Sistem**
  - Maksimum riwayat: 10 pesan (optimasi performa)
  - Rentang temperatur: 0.0 - 1.0 (kontrol respons)
  - Timeout API: 180 detik

### Fitur Keamanan (Security Features)
**Implementasi Keamanan:**
- **Manajemen API Key**
  - Penyimpanan aman dalam Streamlit secrets
  - Enkripsi data sensitif
  - Rotasi key otomatis (opsional)

- **Validasi dan Sanitasi**
  - Pemeriksaan input pengguna
  - Pencegahan injeksi berbahaya
  - Rate limiting untuk permintaan API

- **Error Handling**
  - Penanganan timeout dan disconnect
  - Logging kesalahan terstruktur
  - Feedback pengguna yang informatif

## Komponen UI

### Antarmuka Utama (Main Interface)
**Fitur Antarmuka:**
- **Chat Interface**
  - Gelembung pesan responsif
  - Indikator status pengetikan
  - Avatar pengguna dan bot
  
- **Kode dan Formatting**
  - Syntax highlighting untuk kode
  - Ekspansi blok kode otomatis
  - Dukungan markdown dalam chat
  
- **Informasi Temporal**
  - Timestamp real-time
  - Indikator status pengiriman
  - Penanda pesan baru

### Kontrol Sidebar (Sidebar Controls)
**1. Pengaturan Visual (update_active_theme_callback)**
   - **Manajemen Tema**
     - Selector tema dinamis
     - Preview real-time perubahan
     - Penyimpanan preferensi
   - **Kustomisasi UI**
     - Pengaturan warna komponen
     - Konfigurasi font dan ukuran
     - Penyesuaian layout

**2. Pengaturan Model AI (update_system_prompt_from_persona_callback)**
   - **Konfigurasi Model**
     - Pemilihan model AI yang tersedia
     - Informasi kemampuan model
     - Status penggunaan model
   - **Manajemen Persona**
     - Pemilihan persona predefinisi
     - Editor prompt sistem
     - Preview karakter persona
   - **Parameter Model**
     - Slider temperature dengan preview
     - Batasan token dan respons
     - Pengaturan streaming

**3. Manajemen Chat**
   - **Kontrol Riwayat**
     - Tombol hapus dengan konfirmasi
     - Pencadangan otomatis
     - Pembersihan cache
   - **Fungsi Data**
     - Ekspor multi-format
     - Impor dengan validasi
     - Sinkronisasi data
   - **Utilitas**
     - Salin cepat respons
     - Share percakapan
     - Bookmark penting

## Penanganan Kesalahan
- Manajemen kesalahan koneksi API
- Validasi input
- Validasi unggah file
- Penanganan kesalahan streaming respons

## Fitur Performa
- Streaming pesan yang efisien
- Manajemen riwayat chat yang optimal
- Penanganan tugas latar belakang

## Praktik Terbaik
- Manajemen state sesi
- Desain responsif
- Pesan kesalahan yang bersih
- Antarmuka ramah pengguna

## Persyaratan
- Python 3.x
- Streamlit
- Akses OpenRouter API
- Koneksi internet

## Instruksi Pengaturan
1. Instal dependensi yang diperlukan
2. Konfigurasikan OpenRouter API key di `.streamlit/secrets.toml`
3. Jalankan menggunakan `streamlit run chatai.py`

## Catatan
Aplikasi ini memerlukan OpenRouter API key yang valid untuk berfungsi. Pastikan konfigurasi yang tepat sebelum digunakan.

---
Dibuat dengan ❤️ menggunakan Streamlit dan OpenRouter API
