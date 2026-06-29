from __future__ import annotations

from typing import Any


def default_config() -> dict[str, Any]:
    """Default input simulasi.

    Nilai awal mengikuti struktur defaultConfig pada file MATLAB HWST AC.
    Beberapa parameter U manual lama tetap disimpan sebagai fallback internal,
    tetapi UI utama lebih fokus pada parameter fisik/desain.
    """
    return {
        # AC & Refrigeran
        "property_source": 2,
        "calculation_method": 2,
        "ac_capacity_pk": 2.0,
        "cooling_capacity_per_PK_kW": 2.637,
        "T_amb_C": 32.0,
        "refrigerant": "R32",
        "pressure_drop_model": 2,
        "pressure_drop_feedback": 1,
        "pressure_drop_roughness_mm": 0.0015,
        "dsh_superheat_margin_C": 1.0,
        # Kompresor
        "compressor_power_kW": 1.45,
        "P_suction_psig": 120.0,
        "P_discharge_psig": 360.0,
        "suction_superheat_nominal_K": 5.0,
        "liquid_subcool_nominal_K": 3.0,
        "T_comp_out_C": 78.0,
        "compressor_mdot_factor": 1.0,
        "compressor_power_factor": 1.0,
        "compressor_cycle_coupled": 1,
        # Faktor kalibrasi U (default 1.0 = tidak mengubah hasil Auto-U)
        "U_cal_factor_hwst": 1.0,
        "U_cal_factor_cond": 1.0,
        "U_cal_factor_evap": 1.0,
        # HWST & Tangki
        "tank_volume_L": 70.0,
        "T_tank_initial_C": 27.0,
        "T_setpoint_C": 50.0,
        "hwst_tube_D_o_mm": 9.52,
        "hwst_tube_D_i_mm": 8.30,
        "hwst_coil_length_m": 6.0,
        "k_tube_hwst_W_mK": 16.0,
        "h_water_hwst_W_m2K": 550.0,
        "Rf_hwst_m2K_W": 0.0,
        "UA_loss_W_K": 0.0,
        "dt_s": 60.0,
        "max_time_h": 6.0,
        # Kondensor
        "cond_tube_D_o_mm": 9.52,
        "cond_tube_D_i_mm": 8.30,
        "cond_fin_length_mm": 700.0,
        "cond_fin_height_mm": 460.0,
        "cond_fin_thickness_mm": 0.12,
        "cond_fin_pitch_mm": 1.6,
        "cond_tube_holes_per_row": 16.0,
        "cond_tube_rows": 2.0,
        "cond_tube_row_pitch_mm": 21.0,
        "cond_return_bend_factor": 1.05,
        "cond_fin_efficiency": 0.75,
        "k_tube_cond_W_mK": 385.0,
        "h_air_cond_W_m2K": 55.0,  # fallback internal jika Auto h_udara dimatikan/gagal
        "Rf_cond_m2K_W": 0.0,
        "cond_airflow_m3_s": 0.58,
        # Auto h_udara coil ber-fin: h mengikuti airflow dan geometri face coil.
        # Disembunyikan dari input utama; default tetap bisa ditelusuri di report/Excel.
        "air_side_htc_auto": 1,
        "air_side_htc_velocity_exponent": 0.65,
        "air_side_htc_ref_velocity_m_s": 1.5,
        "h_air_cond_base_W_m2K": 45.0,
        "h_air_evap_base_W_m2K": 40.0,
        "h_air_cond_min_W_m2K": 25.0,
        "h_air_cond_max_W_m2K": 140.0,
        "h_air_evap_min_W_m2K": 20.0,
        "h_air_evap_max_W_m2K": 120.0,
        "cond_refrigerant_circuits": 2.0,
        "T_cond_air_in_C": 32.0,
        # Ekspansi / Kapiler
        "capillary_mode": 2,
        "capillary_D_i_mm": 1.30,
        "capillary_length_m": 1.50,
        "capillary_coil_factor": 0.95,
        "capillary_D_min_mm": 0.60,
        "capillary_D_max_mm": 2.40,
        "capillary_L_min_m": 0.30,
        "capillary_L_max_m": 5.00,
        "capillary_target_tolerance_pct": 2.0,
        "capillary_diagnostic_mode": 1,
        "capillary_feedback": 1,
        # Evaporator
        "evap_tube_D_o_mm": 9.52,
        "evap_tube_D_i_mm": 8.30,
        "evap_fin_length_mm": 820.0,
        "evap_fin_height_mm": 250.0,
        "evap_fin_thickness_mm": 0.12,
        "evap_fin_pitch_mm": 1.5,
        "evap_tube_holes_per_row": 12.0,
        "evap_tube_rows": 2.0,
        "evap_tube_row_pitch_mm": 19.0,
        "evap_return_bend_factor": 1.05,
        "evap_fin_efficiency": 0.78,
        "k_tube_evap_W_mK": 385.0,
        "h_air_evap_W_m2K": 45.0,
        "Rf_evap_m2K_W": 0.0,
        "evap_airflow_m3_s": 0.25,
        "evap_refrigerant_circuits": 4.0,
        "T_evap_air_in_C": 27.0,
        "evaporator_air_model": 2,
        "RH_evap_air_in_percent": 60.0,
        "P_atm_kPa": 101.325,
        "evap_ADP_offset_K": 2.0,
        "SHR_manual": 0.70,
        # Variasi Volume
        "volume_var1_L": 60.0,
        "volume_var2_L": 70.0,
        "volume_var3_L": 80.0,
    }


INPUT_GROUPS = [
    {
        "id": "ac",
        "title": "AC & Refrigeran",
        "fields": [
            ["refrigerant", "Refrigeran", "-", "Pilihan: R32, R410A, R22, R134a"],
            ["ac_capacity_pk", "Kapasitas AC", "PK", "Kapasitas nominal unit AC"],
            ["cooling_capacity_per_PK_kW", "Cooling capacity per PK", "kW/PK", "Total Q nominal = PK × kW/PK"],
            ["T_amb_C", "Suhu lingkungan", "°C", "Untuk kondisi lingkungan simulasi"],
            ["dsh_superheat_margin_C", "Margin superheat DSH murni", "°C", "Batas window HWST tetap sebagai desuperheater"],
        ],
    },
    {
        "id": "kompresor",
        "title": "Kompresor",
        "fields": [
            ["compressor_power_kW", "Daya kompresor nominal", "kW", "Data nameplate unit"],
            ["P_suction_psig", "P_suction / tekanan masuk kompresor", "psig", "Tekanan keluar evaporator / masuk kompresor"],
            ["P_discharge_psig", "P_discharge / tekanan keluar kompresor", "psig", "Tekanan keluar kompresor sebelum HWST/kondensor"],
            ["suction_superheat_nominal_K", "Superheat nominal suction", "K", "Acuan kondisi nominal kompresor"],
            ["liquid_subcool_nominal_K", "Subcool nominal liquid", "K", "Acuan kondisi nominal kompresor"],
            ["T_comp_out_C", "Suhu keluar kompresor", "°C", "Perkiraan temperatur discharge"],
        ],
    },
    {
        "id": "tank",
        "title": "HWST & Tangki",
        "fields": [
            ["tank_volume_L", "Volume tangki utama", "L", "Volume air HWST"],
            ["T_tank_initial_C", "Suhu awal air", "°C", "Kondisi awal mixed/lumped tank"],
            ["T_setpoint_C", "Set point air panas", "°C", "Target suhu air tangki"],
            ["hwst_tube_D_o_mm", "Diameter luar coil HWST", "mm", "Untuk area perpindahan panas"],
            ["hwst_tube_D_i_mm", "Diameter dalam coil HWST", "mm", "Untuk Auto-U dan pressure drop"],
            ["hwst_coil_length_m", "Panjang coil HWST", "m", "Panjang pipa di tangki"],
            ["k_tube_hwst_W_mK", "Konduktivitas pipa HWST", "W/m.K", "Input nilai K tube; SS316 sekitar 16 W/m.K"],
            ["dt_s", "Time step", "s", "Interval perhitungan"],
            ["max_time_h", "Batas waktu maksimum", "jam", "Stop jika target gagal"],
        ],
    },
    {
        "id": "kondensor",
        "title": "Kondensor",
        "fields": [
            ["cond_tube_D_o_mm", "Diameter luar tube", "mm", "Area dan Auto-U"],
            ["cond_tube_D_i_mm", "Diameter dalam tube", "mm", "Auto-U dan pressure drop"],
            ["cond_fin_length_mm", "Fin length / tube lurus", "mm", "Lebar coil"],
            ["cond_fin_height_mm", "Tinggi fin", "mm", "Tinggi muka coil"],
            ["cond_fin_thickness_mm", "Tebal fin", "mm", "Umumnya 0,10–0,15 mm"],
            ["cond_fin_pitch_mm", "Fin pitch", "mm", "Jarak antar fin"],
            ["cond_tube_holes_per_row", "Jumlah tube hole / row", "-", "Jumlah lubang tube per row"],
            ["cond_tube_rows", "Jumlah row tube", "-", "Jumlah row kedalaman coil"],
            ["cond_tube_row_pitch_mm", "Jarak antar row tube", "mm", "Jarak antar row"],
            ["cond_return_bend_factor", "Faktor return bend", "-", "Memasukkan efek belokan"],
            ["cond_refrigerant_circuits", "Jumlah sirkuit refrigeran", "jalur", "Jumlah jalur paralel refrigeran; pressure drop dihitung per sirkuit"],
            ["cond_fin_efficiency", "Efisiensi fin", "-", "0–1"],
            ["k_tube_cond_W_mK", "Konduktivitas tube kondensor", "W/m.K", "Tembaga sekitar 385"],
            ["cond_airflow_m3_s", "Debit udara kondensor", "m³/s", "Dari v_air x A_face"],
            ["T_cond_air_in_C", "Suhu udara masuk kondensor", "°C", "Outdoor air"],
        ],
    },
    {
        "id": "ekspansi",
        "title": "Ekspansi / Kapiler",
        "fields": [
            ["capillary_mode", "Metode iterasi kapiler", "-", "Pilih metode agar input yang muncul sesuai kebutuhan"],
            ["capillary_D_i_mm", "Diameter dalam kapiler", "mm", "Diameter aliran refrigeran pada kapiler"],
            ["capillary_length_m", "Panjang kapiler", "m", "Panjang kapiler aktual atau acuan iterasi"],
        ],
    },
    {
        "id": "evaporator",
        "title": "Evaporator",
        "fields": [
            ["evap_tube_D_o_mm", "Diameter luar tube", "mm", "Area dan Auto-U"],
            ["evap_tube_D_i_mm", "Diameter dalam tube", "mm", "Auto-U dan pressure drop"],
            ["evap_fin_length_mm", "Fin length / tube lurus", "mm", "Lebar coil"],
            ["evap_fin_height_mm", "Tinggi fin", "mm", "Tinggi muka coil"],
            ["evap_fin_thickness_mm", "Tebal fin", "mm", "Umumnya 0,10–0,15 mm"],
            ["evap_fin_pitch_mm", "Fin pitch", "mm", "Jarak antar fin"],
            ["evap_tube_holes_per_row", "Jumlah tube hole / row", "-", "Jumlah lubang tube per row"],
            ["evap_tube_rows", "Jumlah row tube", "-", "Jumlah row kedalaman coil"],
            ["evap_tube_row_pitch_mm", "Jarak antar row tube", "mm", "Jarak antar row"],
            ["evap_return_bend_factor", "Faktor return bend", "-", "Memasukkan efek belokan"],
            ["evap_refrigerant_circuits", "Jumlah sirkuit refrigeran", "jalur", "Jumlah jalur paralel refrigeran; pressure drop dihitung per sirkuit"],
            ["evap_fin_efficiency", "Efisiensi fin", "-", "0–1"],
            ["k_tube_evap_W_mK", "Konduktivitas tube evaporator", "W/m.K", "Tembaga sekitar 385"],
            ["evap_airflow_m3_s", "Debit udara evaporator", "m³/s", "Dari v_air x A_outlet"],
            ["T_evap_air_in_C", "Suhu udara masuk evaporator", "°C", "Return air indoor"],
            ["evaporator_air_model", "Model udara evaporator", "1/2", "1=SHR manual, 2=psikrometrik RH"],
            ["RH_evap_air_in_percent", "RH udara masuk evaporator", "%", "Untuk psikrometrik; contoh 60%"],
            ["evap_ADP_offset_K", "Offset ADP terhadap T evaporasi", "K", "Estimasi coil ADP = T_evap + offset"],
            ["SHR_manual", "SHR manual evaporator", "0–1", "Fallback jika model udara=1"],
        ],
    },
]


def default_inputs_response() -> dict[str, Any]:
    return {"config": default_config(), "groups": INPUT_GROUPS}
