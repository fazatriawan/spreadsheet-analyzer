# Spreadsheet Deep Analyzer

Analisis formula, dependency graph, dan perbaikan otomatis untuk Google Sheets.

## Mode Deploy

| Mode | Cara jalankan | Cocok untuk |
|------|---------------|-------------|
| **Vercel (Web)** | Deploy ke Vercel | Akses dari browser, tim, mobile |
| **Lokal (Dash)** | `python web_app.py` | Spreadsheet sangat besar, tanpa timeout |
| **CLI** | `python main.py analyze --url "..."` | Otomatisasi & batch |

## Deploy

### Otomatis (disarankan)

Setiap `git push` ke GitHub → Vercel deploy otomatis.

```bash
git add .
git commit -m "update fitur"
git push origin master
```

Repo: [github.com/fazatriawan/spreadsheet-analyzer](https://github.com/fazatriawan/spreadsheet-analyzer)  
Production: [spreadsheet-analyzer-gray.vercel.app](https://spreadsheet-analyzer-gray.vercel.app)

### Manual

```powershell
npx vercel deploy --prod --yes
# atau
.\scripts\deploy.ps1
```

### Deploy ke Vercel (setup awal)

### 1. Push ke GitHub

```bash
git init
git add .
git commit -m "Spreadsheet analyzer with Vercel"
git remote add origin <repo-url>
git push -u origin main
```

### 2. Import di Vercel

1. Buka [vercel.com/new](https://vercel.com/new) → import repository
2. Framework Preset: **Next.js** (otomatis terdeteksi)
3. Tambahkan Environment Variables:

| Variable | Wajib | Keterangan |
|----------|-------|------------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | ✅ | Seluruh isi `service_account.json` sebagai satu baris JSON |
| `ANTHROPIC_API_KEY` | Opsional | Untuk AI report & perbaikan formula |

4. Deploy

### 3. Google Sheets API

- Buat Service Account di Google Cloud Console
- Aktifkan Google Sheets API & Drive API
- Share spreadsheet ke email service account (Editor jika ingin apply fix)
- Paste JSON ke `GOOGLE_SERVICE_ACCOUNT_JSON` di Vercel

### Catatan Vercel

- Analisis berat membutuhkan **Vercel Pro** (timeout hingga 300 detik)
- Cache di `/tmp` bersifat ephemeral (per instance serverless)
- Untuk spreadsheet >25.000 formula, gunakan mode lokal (`web_app.py`)

## Development Lokal (Next.js + API)

```bash
# Terminal 1 — Python API (simulasi Vercel)
pip install -r requirements.txt
vercel dev

# Atau tanpa Vercel CLI:
# Terminal 1: python -m http.server 8000  (tidak cukup — gunakan vercel dev)
```

```bash
# Install & jalankan frontend
npm install
npm run dev
```

Buka http://localhost:3000

## Development Lokal (Dash — legacy)

```bash
pip install -r requirements.txt
python web_app.py
```

Buka http://localhost:8050 atau jalankan `Jalankan Analyzer.bat`

## Kemampuan (Skills)

| Skill | Deskripsi |
|-------|-----------|
| **Health Score** | Skor 0–100 + grade A–F berdasarkan warning, circular ref, kompleksitas |
| **Rekomendasi Otomatis** | Saran prioritas (critical/high/medium/low) tanpa AI |
| **Breakdown per Sheet** | Statistik formula, warning, kompleksitas per sheet |
| **Impact Analysis** | Sel dengan fan-in tertinggi (bottleneck dependency) |
| **Deep Insights** | Detail circular ref, missing ref, orphan cells |
| **AI Explain** | Jelaskan formula individual via Claude |
| **AI Assistant** | Chat kontekstual tentang spreadsheet |
| **AI Audit** | Executive summary singkat (dengan opsi AI Report) |
| **Multi-Bulan Compare** | Perbandingan struktur, nilai drastis, tren chart |
| **Auto Fix** | Perbaikan formula locale Indonesia (; separator) |
| **Export JSON** | Unduh hasil analisis lengkap |

## API Endpoints

| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/api/health` | Status & credential check |
| POST | `/api/sheets/load` | Muat daftar sheet |
| POST | `/api/analyze` | Analisis formula & dependency + skills |
| POST | `/api/compare` | Perbandingan multi-periode |
| POST | `/api/explain` | Jelaskan formula (AI) |
| POST | `/api/chat` | AI assistant |
| POST | `/api/fix` | Perbaiki satu formula (AI) |
| POST | `/api/apply` | Terapkan formula ke sheet |
| POST | `/api/cache/clear` | Hapus cache |

## CLI

```bash
python main.py analyze --url "https://docs.google.com/spreadsheets/d/..."
python main.py compare --links-file links.json
python main.py cache --list
```
