# HWST AC Web V10

Versi V10 fokus pada perbaikan visualisasi simulasi sesuai revisi:

- Grafik tren ditempatkan langsung di bawah visualisasi sistem.
- Legend grafik diperjelas: titik 1, 2, 2', 3, 4 memakai keterangan posisi lengkap; zona coil memakai nama komponen lengkap.
- Kondensor diperbaiki dengan pipa/coil internal yang terlihat dan port masuk-keluar yang jelas.
- Kapiler diperbaiki agar tersambung penuh dengan pipa dari kondensor dan menuju evaporator.
- Layout visualisasi dipadatkan untuk mengurangi area kosong.

Backend tetap mengikuti model MATLAB terbaru: CoolProp, Auto-U, Shah TP, mixed tank, compressor nominal calibration, dan capillary/pressure feedback.

## Jalankan backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Jalankan frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Buka http://localhost:5173

## Catatan Revisi NTU

Versi revisi ini menambahkan `calculation_method`:

- `1` = Segmented UA–ΔT lama.
- `2` = NTU–Effectiveness berbasis zona refrigeran, default aktif.

Detail perubahan ada di `README_NTU_REVISION.md`.
