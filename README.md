# ZeusX Automation

Aplikasi automation menggunakan Python dan Playwright untuk mengotomatisasi pengisian form "Create New Listing" pada website ZeusX.

## Tujuan Project
Proyek ini dibuat untuk mempercepat pembuatan listing di ZeusX dengan membaca data dari file Excel dan mengunggah gambar yang sesuai secara otomatis. Program membaca baris demi baris pada Excel dan secara otomatis mengisi *dropdown*, judul, harga, serta detail lain tanpa menyimpan kredensial.

## Struktur Folder
- `main.py`: Entry point dari aplikasi, berisi alur utama program.
- `config.py`: File konfigurasi (pengaturan DRY_RUN, testing row, dll).
- `automation/`: Modul yang berisi logika interaksi browser, form, unggah gambar, dan validasi.
- `data/`: Folder untuk menyimpan `data.xlsx`.
- `images/`: Folder untuk menyimpan gambar listing. Nama gambar harus sesuai dengan kolom `No` pada Excel (misal: `1.jpg`).
- `logs/`: Tempat menyimpan file log `automation.log` dan screenshot jika terjadi error (`logs/screenshots/`).
- `browser-profile/`: Direktori penyimpanan sesi browser agar Anda tidak perlu login berulang kali.

## Cara Instalasi (Pengguna Windows)

1. **Buat Virtual Environment**
   Buka terminal/Command Prompt di dalam folder project ini, lalu jalankan:
   ```cmd
   python -m venv .venv
   ```

2. **Aktifkan Virtual Environment**
   ```cmd
   .venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```cmd
   pip install -r requirements.txt
   ```

4. **Install Chromium Playwright**
   ```cmd
   playwright install chromium
   ```

## Persiapan Data

1. **Data Excel**
   - Buka folder `data/` dan isi `data.xlsx`.
   - Header yang wajib ada: `No`, `Game`, `Harga`, `Server`, `Spesifikasi`.
   
2. **Data Gambar**
   - Masukkan gambar ke dalam folder `images/`.
   - Nama gambar harus persis dengan angka di kolom `No` pada Excel (contoh: untuk baris dengan `No` 1, nama file adalah `1.jpg`).

## Konfigurasi Penting (`config.py`)

- `DRY_RUN`: 
  - Jika `True`: Program akan membuka browser, mengisi form, dan menyiapkan gambar, namun **TIDAK AKAN** menekan tombol submit (List Items). Sangat disarankan untuk tahap testing.
  - Jika `False`: Program akan benar-benar menekan submit (digunakan jika automation sudah dipastikan berjalan dengan benar).
- `TEST_SINGLE_ROW`:
  - Jika `True`: Hanya akan memproses satu baris data (berdasarkan `TEST_ROW_NO`) untuk mempercepat masa development.
  - Jika `False`: Akan memproses seluruh data di dalam Excel.

## Cara Menjalankan Program

Pastikan virtual environment telah aktif, lalu jalankan:
```cmd
python main.py
```

## Penanganan Error & Login

- **Login**: Program ini **tidak menyimpan kredensial login Anda**. Saat pertama kali dijalankan, jika Anda belum login ke ZeusX, selesaikan login secara manual di browser yang terbuka. Sesi login akan otomatis disimpan di folder `browser-profile/`.
- **Error Handling**: Jika terjadi error pada suatu listing (misalnya internet terputus, atau gambar tidak ditemukan), program tidak akan crash. Program akan mencatat error, mengambil screenshot (disimpan di `logs/screenshots/`), dan melanjutkan ke baris berikutnya.
- **CAPTCHA**: Program tidak diprogram untuk melakukan bypass CAPTCHA. Jika muncul CAPTCHA, selesaikan secara manual di layar browser yang sedang berjalan.
