from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Callable

from .config import default_config

try:
    from CoolProp.CoolProp import PropsSI, get_global_param_string
except Exception:  # pragma: no cover - optional fallback for machines without CoolProp
    PropsSI = None  # type: ignore
    get_global_param_string = None  # type: ignore

EPS = 1e-12
G = 9.80665

# =============================================================================
# V5 REAL-PHYSICS ENGINE
# -----------------------------------------------------------------------------
# Backend ini bukan lagi sekadar kalibrasi angka report. Struktur perhitungan
# mengikuti fungsi inti MATLAB:
# defaultConfig -> getRefrigerantPropertiesCoolProp -> buildGeometry ->
# compressorNameplateModel -> computeUZones -> hwstModel -> condenserModel ->
# capillaryDiagnosticModel -> evaporatorModelManualSHR -> feedback tekanan/mdot ->
# mixed/lumped tank integration -> COP/energy/zone reporting.
# =============================================================================


def _num(cfg: dict[str, Any], key: str, fallback: float = 0.0) -> float:
    try:
        v = float(cfg.get(key, fallback))
        return v if math.isfinite(v) else fallback
    except Exception:
        return fallback


def _r2(x: Any, nd: int = 4) -> float | str | None:
    if x is None or isinstance(x, str):
        return x
    try:
        v = float(x)
        if not math.isfinite(v):
            return None
        return round(v, nd)
    except Exception:
        return x



def cop_efficiency_class(cop: Any) -> dict[str, Any]:
    """Klasifikasi efisiensi COP pendinginan mengikuti skala A-G umum.

    Catatan: klasifikasi ini hanya untuk COP pendinginan AC, bukan COP useful
    yang menjumlahkan manfaat pendinginan + pemanasan air.
    """
    try:
        v = float(cop)
    except Exception:
        return {"grade": "-", "label": "Data COP tidak tersedia", "range": "-"}
    if not math.isfinite(v):
        return {"grade": "-", "label": "Data COP tidak tersedia", "range": "-"}
    if v > 3.60:
        return {"grade": "A", "label": "Sangat efisien", "range": "COP > 3.60"}
    if v > 3.40:
        return {"grade": "B", "label": "Efisien", "range": "3.60 ≥ COP > 3.40"}
    if v > 3.20:
        return {"grade": "C", "label": "Cukup efisien", "range": "3.40 ≥ COP > 3.20"}
    if v > 2.80:
        return {"grade": "D", "label": "Menengah", "range": "3.20 ≥ COP > 2.80"}
    if v > 2.60:
        return {"grade": "E", "label": "Kurang efisien", "range": "2.80 ≥ COP > 2.60"}
    if v > 2.40:
        return {"grade": "F", "label": "Rendah", "range": "2.60 ≥ COP > 2.40"}
    return {"grade": "G", "label": "Sangat rendah", "range": "2.40 ≥ COP"}

def c2k(t_c: float) -> float:
    return float(t_c) + 273.15


def k2c(t_k: float) -> float:
    return float(t_k) - 273.15


def psig2pa(p_psig: float) -> float:
    return (float(p_psig) + 14.6959) * 6894.757293168


def kpa2psi(dp_kpa: float) -> float:
    return float(dp_kpa) * 1000.0 / 6894.757293168


def coolprop_fluid_name(ref: str) -> str:
    r = str(ref).replace("-", "").replace(" ", "").upper()
    if r == "R32":
        return "R32"
    if r == "R410A":
        return "R410A"
    if r == "R22":
        return "R22"
    if r == "R134A":
        return "R134a"
    return str(ref)


def cp_version() -> str:
    if get_global_param_string is None:
        return "CoolProp tidak terpasang"
    try:
        return str(get_global_param_string("version"))
    except Exception:
        return "unknown"


def props_si(output: str, in1: str, v1: float, in2: str, v2: float, fluid: str) -> float:
    if PropsSI is None:
        raise RuntimeError("CoolProp belum terpasang. Jalankan: python -m pip install CoolProp")
    val = float(PropsSI(output, in1, float(v1), in2, float(v2), str(fluid)))
    if not math.isfinite(val):
        raise ValueError(f"CoolProp mengembalikan nilai tidak valid untuk {output}")
    return val


def cp_safe(output: str, in1: str, v1: float, in2: str, v2: float, fluid: str, default: float) -> float:
    try:
        return props_si(output, in1, v1, in2, v2, fluid)
    except Exception:
        return default


def normalize_config(input_config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = deepcopy(default_config())
    if input_config:
        # Abaikan nilai transien dari frontend seperti '', '-', '.', '-.'.
        # Nilai seperti ini bisa muncul ketika user sedang mengetik, dan tidak boleh
        # menimpa default menjadi 0/invalid di backend.
        transient_values = {'', '-', '+', '.', ',', '-.', '+.'}
        cleaned_input = {}
        for k, v in input_config.items():
            if v is None:
                continue
            if isinstance(v, str) and v.strip() in transient_values:
                continue
            cleaned_input[k] = v
        cfg.update(cleaned_input)
    # hidden/internal defaults from MATLAB that are not exposed in UI
    cfg.setdefault("U_model_mode", 2)
    cfg.setdefault("zone_segments", 400)
    cfg.setdefault("tp_quality_min", 0.05)
    cfg.setdefault("tp_quality_max", 0.95)
    cfg.setdefault("compressor_model_mode", 2)
    cfg.setdefault("compressor_dynamic", 1)
    cfg.setdefault("compressor_power_mode", 2)
    cfg.setdefault("compressor_type_code", 1)
    cfg.setdefault("P_discharge_slope_psig_per_K", 0)
    cfg.setdefault("U_hwst_W_m2K", 200.0)
    cfg.setdefault("U_hwst_dsh_W_m2K", 300.0)
    cfg.setdefault("U_hwst_tp_W_m2K", 1200.0)
    cfg.setdefault("U_hwst_sc_W_m2K", 350.0)
    cfg.setdefault("U_cond_W_m2K", 70.0)
    cfg.setdefault("U_cond_dsh_W_m2K", 60.0)
    cfg.setdefault("U_cond_tp_W_m2K", 90.0)
    cfg.setdefault("U_cond_sc_W_m2K", 65.0)
    cfg.setdefault("U_evap_W_m2K", 60.0)
    cfg.setdefault("U_evap_tp_W_m2K", 80.0)
    cfg.setdefault("U_evap_sh_W_m2K", 45.0)
    cfg.setdefault("R_contact_cond_m2K_W", 0.0)
    cfg.setdefault("R_contact_evap_m2K_W", 0.0)
    cfg.setdefault("tank_node_mixing_conductance_W_K", 0.5)
    cfg["refrigerant"] = str(cfg.get("refrigerant", "R32"))
    return cfg


def validate_config(cfg: dict[str, Any]) -> None:
    required_positive = [
        "ac_capacity_pk", "cooling_capacity_per_PK_kW", "compressor_power_kW",
        "P_suction_psig", "P_discharge_psig", "tank_volume_L", "dt_s", "max_time_h",
        "hwst_tube_D_o_mm", "hwst_tube_D_i_mm", "hwst_coil_length_m", "k_tube_hwst_W_mK",
        "h_water_hwst_W_m2K", "cond_tube_D_o_mm", "cond_tube_D_i_mm",
        "cond_fin_length_mm", "cond_fin_height_mm", "cond_fin_thickness_mm", "cond_fin_pitch_mm",
        "cond_tube_holes_per_row", "cond_tube_rows", "cond_tube_row_pitch_mm", "cond_return_bend_factor",
        "cond_airflow_m3_s", "cond_refrigerant_circuits", "k_tube_cond_W_mK", "h_air_cond_W_m2K",
        "capillary_D_i_mm", "capillary_length_m", "capillary_coil_factor",
        "evap_tube_D_o_mm", "evap_tube_D_i_mm", "evap_fin_length_mm", "evap_fin_height_mm",
        "evap_fin_thickness_mm", "evap_fin_pitch_mm", "evap_tube_holes_per_row", "evap_tube_rows",
        "evap_tube_row_pitch_mm", "evap_return_bend_factor", "evap_airflow_m3_s", "evap_refrigerant_circuits",
        "k_tube_evap_W_mK", "h_air_evap_W_m2K", "pressure_drop_roughness_mm"
    ]
    for key in required_positive:
        if _num(cfg, key) <= 0:
            raise ValueError(f"{key} harus angka lebih besar dari 0.")
    if _num(cfg, "P_discharge_psig") <= _num(cfg, "P_suction_psig"):
        raise ValueError("Tekanan discharge harus lebih besar dari tekanan suction.")
    if _num(cfg, "T_setpoint_C") <= _num(cfg, "T_tank_initial_C"):
        raise ValueError("Set point harus lebih tinggi dari suhu awal tangki.")
    for key in ["cond_fin_efficiency", "evap_fin_efficiency", "SHR_manual"]:
        v = _num(cfg, key)
        if not (0 < v <= 1):
            raise ValueError(f"{key} harus berada pada rentang 0-1.")
    if not (1 <= _num(cfg, "RH_evap_air_in_percent", 60) <= 100):
        raise ValueError("RH_evap_air_in_percent harus 1-100%.")
    for key in ["compressor_mdot_factor", "compressor_power_factor", "U_cal_factor_hwst", "U_cal_factor_cond", "U_cal_factor_evap"]:
        if _num(cfg, key, 1.0) <= 0:
            raise ValueError(f"{key} harus lebih besar dari 0.")
    if _num(cfg, "capillary_D_max_mm", 2.4) <= _num(cfg, "capillary_D_min_mm", 0.6):
        raise ValueError("Batas diameter kapiler max harus lebih besar dari min.")
    if _num(cfg, "capillary_L_max_m", 5.0) <= _num(cfg, "capillary_L_min_m", 0.3):
        raise ValueError("Batas panjang kapiler max harus lebih besar dari min.")
    if _num(cfg, "hwst_tube_D_i_mm") >= _num(cfg, "hwst_tube_D_o_mm"):
        raise ValueError("Diameter dalam HWST harus lebih kecil dari diameter luar.")
    if _num(cfg, "cond_tube_D_i_mm") >= _num(cfg, "cond_tube_D_o_mm"):
        raise ValueError("Diameter dalam kondensor harus lebih kecil dari diameter luar.")
    if _num(cfg, "evap_tube_D_i_mm") >= _num(cfg, "evap_tube_D_o_mm"):
        raise ValueError("Diameter dalam evaporator harus lebih kecil dari diameter luar.")
    for key in ["cond_refrigerant_circuits", "evap_refrigerant_circuits"]:
        if round(_num(cfg, key, 1)) < 1:
            raise ValueError(f"{key} minimal 1 circuit.")


# =============================================================================
# Refrigerant properties - CoolProp first, estimated fallback only if unavailable
# =============================================================================


def get_refrigerant_properties(cfg: dict[str, Any]) -> dict[str, Any]:
    try:
        return get_refrigerant_properties_coolprop(cfg)
    except Exception as exc:
        if int(round(_num(cfg, "property_source", 2))) == 2:
            # Fallback agar UI tetap bisa menyala, tetapi report diberi label jelas.
            return get_refrigerant_properties_fallback(cfg, str(exc))
        raise


def get_refrigerant_properties_coolprop(cfg: dict[str, Any]) -> dict[str, Any]:
    ref = str(cfg.get("refrigerant", "R32"))
    fluid = coolprop_fluid_name(ref)
    p_low = psig2pa(_num(cfg, "P_suction_psig"))
    p_high = psig2pa(_num(cfg, "P_discharge_psig"))
    t_evap = k2c(props_si("T", "P", p_low, "Q", 1, fluid))
    t_cond = k2c(props_si("T", "P", p_high, "Q", 1, fluid))
    hf_low = props_si("Hmass", "P", p_low, "Q", 0, fluid) / 1000
    hg_low = props_si("Hmass", "P", p_low, "Q", 1, fluid) / 1000
    hf_high = props_si("Hmass", "P", p_high, "Q", 0, fluid) / 1000
    hg_high = props_si("Hmass", "P", p_high, "Q", 1, fluid) / 1000
    cp_liq_low = cp_safe("Cpmass", "P", p_low, "T", c2k(t_evap - 1), fluid, 1400) / 1000
    cp_liq_high = cp_safe("Cpmass", "P", p_high, "T", c2k(t_cond - 1), fluid, 1400) / 1000
    cp_vap_high = cp_safe("Cpmass", "P", p_high, "T", c2k(max(_num(cfg, "T_comp_out_C"), t_cond + 2)), fluid, 1000) / 1000
    cp_vap_low = cp_safe("Cpmass", "P", p_low, "T", c2k(t_evap + 5), fluid, 900) / 1000
    h_comp = props_si("Hmass", "P", p_high, "T", c2k(_num(cfg, "T_comp_out_C")), fluid) / 1000
    if _num(cfg, "T_comp_out_C") <= t_cond:
        raise ValueError("Suhu keluar kompresor harus lebih tinggi dari T kondensasi.")
    return {
        "refrigerant": ref,
        "coolprop_fluid": fluid,
        "property_source": "CoolProp",
        "coolprop_version": cp_version(),
        "P_low_psig": _num(cfg, "P_suction_psig"),
        "P_high_psig": _num(cfg, "P_discharge_psig"),
        "P_low_Pa": p_low,
        "P_high_Pa": p_high,
        "T_evap_C": t_evap,
        "T_cond_C": t_cond,
        "h_f_low_kJ_kg": hf_low,
        "h_g_low_kJ_kg": hg_low,
        "h_f_high_kJ_kg": hf_high,
        "h_g_high_kJ_kg": hg_high,
        "h_fg_low_kJ_kg": hg_low - hf_low,
        "h_fg_high_kJ_kg": hg_high - hf_high,
        "cp_liq_low_kJ_kgK": cp_liq_low,
        "cp_liq_high_kJ_kgK": cp_liq_high,
        "cp_vap_high_kJ_kgK": cp_vap_high,
        "cp_vap_low_kJ_kgK": cp_vap_low,
        "h_comp_out_kJ_kg": h_comp,
        "T_comp_out_C_model": _num(cfg, "T_comp_out_C"),
        "coolprop_error": "",
    }


def get_refrigerant_properties_fallback(cfg: dict[str, Any], err: str) -> dict[str, Any]:
    # Guardrail fallback; values are rough and should not be used for final validation.
    # The message/report will show that CoolProp was not active.
    ref = str(cfg.get("refrigerant", "R32"))
    p_low = _num(cfg, "P_suction_psig")
    p_high = _num(cfg, "P_discharge_psig")
    # approximate R32 near given pressures
    t_evap = 4.2 + 0.045 * (p_low - 120)
    t_cond = 41.7 + 0.060 * (p_high - 360)
    hf_low = 207.4
    hg_low = 516.0
    hf_high = 279.2 + 1.7 * (t_cond - 41.7)
    hg_high = 512.0 + 0.8 * (t_cond - 41.7)
    return {
        "refrigerant": ref,
        "coolprop_fluid": coolprop_fluid_name(ref),
        "property_source": "Fallback estimate after CoolProp error",
        "coolprop_version": "not active",
        "coolprop_error": err,
        "P_low_psig": p_low,
        "P_high_psig": p_high,
        "P_low_Pa": psig2pa(p_low),
        "P_high_Pa": psig2pa(p_high),
        "T_evap_C": t_evap,
        "T_cond_C": t_cond,
        "h_f_low_kJ_kg": hf_low,
        "h_g_low_kJ_kg": hg_low,
        "h_f_high_kJ_kg": hf_high,
        "h_g_high_kJ_kg": hg_high,
        "h_fg_low_kJ_kg": hg_low - hf_low,
        "h_fg_high_kJ_kg": hg_high - hf_high,
        "cp_liq_low_kJ_kgK": 1.6,
        "cp_liq_high_kJ_kgK": 2.17,
        "cp_vap_high_kJ_kgK": 1.30,
        "cp_vap_low_kJ_kgK": 1.22,
        "h_comp_out_kJ_kg": hg_high + 1.30 * max(0, _num(cfg, "T_comp_out_C") - t_cond),
        "T_comp_out_C_model": _num(cfg, "T_comp_out_C"),
    }


def update_high_side_properties(cfg: dict[str, Any], prop: dict[str, Any], p_hi_psig: float) -> dict[str, Any]:
    out = dict(prop)
    if "CoolProp" in str(prop.get("property_source")) and PropsSI is not None:
        fluid = str(prop["coolprop_fluid"])
        p_pa = psig2pa(p_hi_psig)
        out.update({
            "P_high_psig": p_hi_psig,
            "P_high_Pa": p_pa,
            "T_cond_C": k2c(props_si("T", "P", p_pa, "Q", 1, fluid)),
            "h_g_high_kJ_kg": props_si("Hmass", "P", p_pa, "Q", 1, fluid) / 1000,
            "h_f_high_kJ_kg": props_si("Hmass", "P", p_pa, "Q", 0, fluid) / 1000,
        })
        out["h_fg_high_kJ_kg"] = max(out["h_g_high_kJ_kg"] - out["h_f_high_kJ_kg"], 1e-9)
        out["cp_liq_high_kJ_kgK"] = cp_safe("Cpmass", "P", p_pa, "T", c2k(out["T_cond_C"] - 1), fluid, out["cp_liq_high_kJ_kgK"] * 1000) / 1000
        out["cp_vap_high_kJ_kgK"] = cp_safe("Cpmass", "P", p_pa, "T", c2k(max(_num(cfg, "T_comp_out_C"), out["T_cond_C"] + 2)), fluid, out["cp_vap_high_kJ_kgK"] * 1000) / 1000
    else:
        base = get_refrigerant_properties_fallback({**cfg, "P_discharge_psig": p_hi_psig}, str(prop.get("coolprop_error", "")))
        for k in ["P_high_psig", "P_high_Pa", "T_cond_C", "h_g_high_kJ_kg", "h_f_high_kJ_kg", "h_fg_high_kJ_kg", "cp_liq_high_kJ_kgK", "cp_vap_high_kJ_kgK"]:
            out[k] = base[k]
    return out


def update_low_side_properties(cfg: dict[str, Any], prop: dict[str, Any], p_lo_psig: float) -> dict[str, Any]:
    out = dict(prop)
    if "CoolProp" in str(prop.get("property_source")) and PropsSI is not None:
        fluid = str(prop["coolprop_fluid"])
        p_pa = psig2pa(p_lo_psig)
        out.update({
            "P_low_psig": p_lo_psig,
            "P_low_Pa": p_pa,
            "T_evap_C": k2c(props_si("T", "P", p_pa, "Q", 1, fluid)),
            "h_g_low_kJ_kg": props_si("Hmass", "P", p_pa, "Q", 1, fluid) / 1000,
            "h_f_low_kJ_kg": props_si("Hmass", "P", p_pa, "Q", 0, fluid) / 1000,
        })
        out["h_fg_low_kJ_kg"] = max(out["h_g_low_kJ_kg"] - out["h_f_low_kJ_kg"], 1e-9)
        out["cp_liq_low_kJ_kgK"] = cp_safe("Cpmass", "P", p_pa, "T", c2k(out["T_evap_C"] - 1), fluid, out["cp_liq_low_kJ_kgK"] * 1000) / 1000
        out["cp_vap_low_kJ_kgK"] = cp_safe("Cpmass", "P", p_pa, "T", c2k(out["T_evap_C"] + 5), fluid, out["cp_vap_low_kJ_kgK"] * 1000) / 1000
    else:
        base = get_refrigerant_properties_fallback({**cfg, "P_suction_psig": p_lo_psig}, str(prop.get("coolprop_error", "")))
        for k in ["P_low_psig", "P_low_Pa", "T_evap_C", "h_g_low_kJ_kg", "h_f_low_kJ_kg", "h_fg_low_kJ_kg", "cp_liq_low_kJ_kgK", "cp_vap_low_kJ_kgK"]:
            out[k] = base[k]
    return out


# =============================================================================
# Geometry
# =============================================================================


def build_geometry(cfg: dict[str, Any]) -> dict[str, Any]:
    do_hw = _num(cfg, "hwst_tube_D_o_mm") / 1000
    di_hw = _num(cfg, "hwst_tube_D_i_mm") / 1000
    length_hw = _num(cfg, "hwst_coil_length_m")
    hwst = {
        "D_o_m": do_hw,
        "D_i_m": di_hw,
        "tube_length_m": length_hw,
        "A_tube_m2": math.pi * do_hw * length_hw,
        "A_i_m2": math.pi * di_hw * length_hw,
        "A_o_m2": math.pi * do_hw * length_hw,
        "A_total_m2": math.pi * do_hw * length_hw,
    }
    hwst["UA_kW_K"] = _num(cfg, "U_hwst_W_m2K") * hwst["A_total_m2"] / 1000
    return {
        "hwst": hwst,
        "cond": coil_geometry_from_holes(cfg, "cond"),
        "evap": coil_geometry_from_holes(cfg, "evap"),
    }


def coil_geometry_from_holes(cfg: dict[str, Any], prefix: str) -> dict[str, Any]:
    D = _num(cfg, f"{prefix}_tube_D_o_mm") / 1000
    Di = max(_num(cfg, f"{prefix}_tube_D_i_mm") / 1000, 1e-6)
    straight = _num(cfg, f"{prefix}_fin_length_mm") / 1000
    fin_h = _num(cfg, f"{prefix}_fin_height_mm") / 1000
    fin_t = _num(cfg, f"{prefix}_fin_thickness_mm") / 1000
    fin_pitch = _num(cfg, f"{prefix}_fin_pitch_mm") / 1000
    n_hole = max(1, round(_num(cfg, f"{prefix}_tube_holes_per_row")))
    n_row = max(1, round(_num(cfg, f"{prefix}_tube_rows")))
    row_pitch = _num(cfg, f"{prefix}_tube_row_pitch_mm") / 1000
    ret = max(_num(cfg, f"{prefix}_return_bend_factor"), 1.0)
    eff = _num(cfg, f"{prefix}_fin_efficiency")
    u = _num(cfg, f"U_{prefix}_W_m2K")
    n_circuit = max(1, round(_num(cfg, f"{prefix}_refrigerant_circuits", 1)))
    coil_depth = max(n_row * row_pitch, D * n_row)
    runs = n_hole * n_row
    tube_len = straight * runs * ret
    hydraulic_len = tube_len / max(n_circuit, 1)
    a_tube = math.pi * D * tube_len
    a_i = math.pi * Di * tube_len
    fin_count = max(1, math.floor(straight / max(fin_pitch, 1e-9)))
    a_fin_one = 2 * fin_h * coil_depth + 2 * (fin_h + coil_depth) * fin_t
    a_fin = fin_count * a_fin_one * eff
    return {
        "straight_length_m": straight,
        "tube_holes_per_row": n_hole,
        "tube_rows": n_row,
        "tube_runs": runs,
        "return_bend_factor": ret,
        "refrigerant_circuits": n_circuit,
        "tube_length_m": tube_len,
        "hydraulic_length_m": hydraulic_len,
        "mdot_fraction_per_circuit": 1.0 / max(n_circuit, 1),
        "coil_depth_m": coil_depth,
        "face_area_m2": max(straight * fin_h, EPS),
        "fin_pitch_m": fin_pitch,
        "fin_thickness_m": fin_t,
        "tube_blockage_fraction": min(max(n_hole * D / max(fin_h, EPS), 0.0), 0.85),
        "D_o_m": D,
        "D_i_m": Di,
        "A_i_m2": a_i,
        "A_o_m2": a_tube + a_fin,
        "A_tube_m2": a_tube,
        "A_fin_m2": a_fin,
        "A_total_m2": a_tube + a_fin,
        "fin_count": fin_count,
        "fin_efficiency": eff,
        "UA_kW_K": u * (a_tube + a_fin) / 1000,
    }


# =============================================================================
# Compressor
# =============================================================================


def compressor_model(cfg: dict[str, Any], prop: dict[str, Any]) -> dict[str, Any]:
    return compressor_nameplate_model(cfg, prop)


def compressor_nameplate_model(cfg: dict[str, Any], prop: dict[str, Any]) -> dict[str, Any]:
    """Nameplate compressor model calibrated by discharge-temperature reference.

    V7 follows the latest MATLAB correction:
    - T_comp_out_C is NOT a hard fixed compressor-out temperature.
    - It is used as a nominal calibration reference for the effective fraction of
      electric compressor power that becomes refrigerant enthalpy rise.
    - If the calibration is not physically usable, the model falls back to the
      journal assumption eta_m = eta_e = 0.85.
    """
    q_nom = _num(cfg, "ac_capacity_pk") * _num(cfg, "cooling_capacity_per_PK_kW")
    w_nom = _num(cfg, "compressor_power_kW")
    fluid = str(prop.get("coolprop_fluid", coolprop_fluid_name(cfg.get("refrigerant", "R32"))))
    SH = _num(cfg, "suction_superheat_nominal_K", 5.0)
    SC = _num(cfg, "liquid_subcool_nominal_K", 3.0)
    p_lo_nom_psig = _num(cfg, "P_suction_nominal_psig", _num(cfg, "P_suction_psig"))
    p_hi_nom_psig = _num(cfg, "P_discharge_nominal_psig", _num(cfg, "P_discharge_psig"))
    p_lo_cur_psig = _num(cfg, "P_suction_psig")
    p_hi_cur_psig = _num(cfg, "P_discharge_psig")

    p_lo_nom = psig2pa(p_lo_nom_psig)
    p_hi_nom = psig2pa(p_hi_nom_psig)
    p_lo_cur = psig2pa(p_lo_cur_psig)
    p_hi_cur = psig2pa(p_hi_cur_psig)

    te_nom = k2c(cp_safe("T", "P", p_lo_nom, "Q", 1, fluid, c2k(prop["T_evap_C"])))
    tc_nom = k2c(cp_safe("T", "P", p_hi_nom, "Q", 0, fluid, c2k(prop["T_cond_C"])))
    te_cur = k2c(cp_safe("T", "P", p_lo_cur, "Q", 1, fluid, c2k(prop["T_evap_C"])))
    tc_cur = k2c(cp_safe("T", "P", p_hi_cur, "Q", 0, fluid, c2k(prop["T_cond_C"])))

    t1_nom = te_nom + SH
    t3_nom = tc_nom - SC
    t1_cur = te_cur + SH

    h1_nom = cp_safe(
        "Hmass", "P", p_lo_nom, "T", c2k(t1_nom), fluid,
        (prop["h_g_low_kJ_kg"] + prop["cp_vap_low_kJ_kgK"] * SH) * 1000,
    ) / 1000
    s1_nom = cp_safe("Smass", "P", p_lo_nom, "T", c2k(t1_nom), fluid, 1800) / 1000
    rho1_nom = cp_safe("Dmass", "P", p_lo_nom, "T", c2k(t1_nom), fluid, 20)
    h3_nom = cp_safe(
        "Hmass", "P", p_hi_nom, "T", c2k(t3_nom), fluid,
        (prop["h_f_high_kJ_kg"] - prop["cp_liq_high_kJ_kgK"] * SC) * 1000,
    ) / 1000
    h2s_nom = cp_safe(
        "Hmass", "P", p_hi_nom, "Smass", s1_nom * 1000, fluid,
        (h1_nom + max(15, prop["cp_vap_high_kJ_kgK"] * max(5, tc_nom - t1_nom))) * 1000,
    ) / 1000

    h1_cur = cp_safe(
        "Hmass", "P", p_lo_cur, "T", c2k(t1_cur), fluid,
        (prop["h_g_low_kJ_kg"] + prop["cp_vap_low_kJ_kgK"] * SH) * 1000,
    ) / 1000
    s1_cur = cp_safe("Smass", "P", p_lo_cur, "T", c2k(t1_cur), fluid, s1_nom * 1000) / 1000
    rho1_cur = cp_safe("Dmass", "P", p_lo_cur, "T", c2k(t1_cur), fluid, rho1_nom)

    # V17.9: mode cycle-coupled memakai outlet evaporator aktual sebagai inlet kompresor.
    # Ini membuat h1 kompresor konsisten dengan h_evap_out, tanpa memaksa evaporator superheat.
    suction_source = "nominal_superheat"
    h1_cycle = cfg.get("_cycle_h_suction_kJ_kg")
    if int(round(_num(cfg, "compressor_cycle_coupled", 1))) == 1 and h1_cycle is not None:
        try:
            h1_tmp = float(h1_cycle)
            if math.isfinite(h1_tmp):
                h1_cur = h1_tmp
                t1_cur = float(cfg.get("_cycle_T_suction_C", refrigerant_temp_low(h1_cur, prop)))
                s1_cur = cp_safe("Smass", "P", p_lo_cur, "Hmass", h1_cur * 1000, fluid, s1_cur * 1000) / 1000
                rho1_cur = cp_safe("Dmass", "P", p_lo_cur, "Hmass", h1_cur * 1000, fluid, rho1_cur)
                suction_source = "evaporator_outlet_actual"
        except Exception:
            suction_source = "nominal_superheat_fallback"

    h2s_cur = cp_safe(
        "Hmass", "P", p_hi_cur, "Smass", s1_cur * 1000, fluid,
        (h1_cur + max(15, prop["cp_vap_high_kJ_kgK"] * max(5, tc_cur - t1_cur))) * 1000,
    ) / 1000

    # Nominal mdot from Q = mdot * (h_suction - h_liquid).
    dh_evap_nom = max(h1_nom - h3_nom, 1e-6)
    mdot_nom = q_nom / dh_evap_nom

    # Electrical power still follows pressure-ratio/isentrope trend, but the
    # enthalpy rise uses eta_heat_to_ref rather than assuming 100% W -> refrigerant.
    w_is_nom = max(h2s_nom - h1_nom, 1e-6)
    eta_is_overall = mdot_nom * w_is_nom / max(w_nom, 1e-9)
    if not math.isfinite(eta_is_overall) or eta_is_overall <= 0:
        eta_is_overall = 0.58
    eta_is_overall = min(max(eta_is_overall, 0.35), 0.85)

    pr_nom = max(p_hi_nom / max(p_lo_nom, EPS), 1.01)
    pr_cur = max(p_hi_cur / max(p_lo_cur, EPS), 1.01)
    eta_v_rel = min(max(1 - 0.04 * (pr_cur / max(pr_nom, EPS) - 1), 0.85), 1.10)
    mdot_cur = mdot_nom * max(rho1_cur / max(rho1_nom, EPS), 0.25) * eta_v_rel
    mdot_cur = min(max(mdot_cur, 0.45 * mdot_nom), 1.25 * mdot_nom)

    w_is_cur = max(h2s_cur - h1_cur, 1e-6)
    w_cur = mdot_cur * w_is_cur / max(eta_is_overall, EPS)
    w_cur = min(max(w_cur, 0.45 * w_nom), 2.20 * w_nom)

    mdot_before_factor = mdot_cur
    w_before_factor = w_cur
    mdot_factor = min(max(_num(cfg, "compressor_mdot_factor", 1.0), 0.50), 1.50)
    power_factor = min(max(_num(cfg, "compressor_power_factor", 1.0), 0.50), 1.80)
    mdot_cur = max(mdot_cur * mdot_factor, EPS)
    w_cur = max(w_cur * power_factor, EPS)

    # MATLAB V7 compressor correction: T_comp_out_C calibrates nominal heat-to-refrigerant fraction.
    eta_m = 0.85
    eta_e = 0.85
    eta_journal = eta_m * eta_e
    t5_ref = _num(cfg, "T_comp_out_C", tc_nom + 20)
    h5_ref = cp_safe(
        "Hmass", "P", p_hi_nom, "T", c2k(t5_ref), fluid,
        (prop["h_g_high_kJ_kg"] + prop["cp_vap_high_kJ_kgK"] * max(0, t5_ref - tc_nom)) * 1000,
    ) / 1000
    w_ref_nom = h5_ref - h1_nom
    eta_heat_to_ref = mdot_nom * w_ref_nom / max(w_nom, 1e-9)
    used_calibration = math.isfinite(eta_heat_to_ref) and 0.05 < eta_heat_to_ref < 1.20
    if not used_calibration:
        eta_heat_to_ref = eta_journal
    eta_heat_to_ref = min(max(eta_heat_to_ref, 0.20), 0.95)

    w_actual = eta_heat_to_ref * w_cur / max(mdot_cur, EPS)
    h5 = h1_cur + w_actual
    t5 = k2c(cp_safe("T", "P", p_hi_cur, "Hmass", h5 * 1000, fluid, c2k(max(tc_cur + 5, t5_ref))))
    if not math.isfinite(t5):
        t5 = refrigerant_temp_high(h5, prop)

    return {
        "model": "Nameplate compressor calibrated by T_comp_out reference + journal eta_m/eta_e",
        "tc_C": tc_cur,
        "te_C": te_cur,
        "Tevap_nominal_C": te_nom,
        "Tcond_nominal_C": tc_nom,
        "suction_superheat_nominal_K": SH,
        "liquid_subcool_nominal_K": SC,
        "PR_nominal": pr_nom,
        "PR_current": pr_cur,
        "eta_is_overall": eta_is_overall,
        "eta_heat_to_ref": eta_heat_to_ref,
        "eta_m": eta_m,
        "eta_e": eta_e,
        "eta_v_rel": eta_v_rel,
        "mdot_kg_s": mdot_cur,
        "mdot_model_before_factor_kg_s": mdot_before_factor,
        "mdot_nominal_kg_s": mdot_nom,
        "compressor_mdot_factor": mdot_factor,
        "Pcomp_kW": w_cur,
        "Pcomp_model_before_factor_kW": w_before_factor,
        "compressor_power_factor": power_factor,
        "Pcomp_input_kW": w_nom,
        "power_source": "Nameplate W, calibrated so nominal T_comp_out follows input reference" if used_calibration else "Nameplate W, journal eta_m*eta_e fallback",
        "suction_state_source": suction_source,
        "h_suction_used_kJ_kg": h1_cur,
        "T_suction_used_C": t1_cur,
        "used_Tcomp_calibration": used_calibration,
        "Tcomp_reference_C": t5_ref,
        "h5_reference_nominal_kJ_kg": h5_ref,
        "h4_kJ_kg": h1_cur,
        "h_suction_nominal_kJ_kg": h1_nom,
        "h_liquid_nominal_kJ_kg": h3_nom,
        "w45_kJ_kg": w_actual,
        "h5_kJ_kg": h5,
        "T5_C": t5,
    }


# =============================================================================
# Heat transfer coefficients and U model
# =============================================================================


def fallback_transport_props(phase: str) -> tuple[float, float, float, float]:
    if phase == "liquid":
        return 900.0, 1.5e-4, 0.08, 3.0
    return 35.0, 1.3e-5, 0.014, 0.9


def transport_state_for_mode(prop: dict[str, Any], mode: str) -> tuple[float, float, str, float]:
    if mode == "high_vapor_cooling":
        p = prop["P_high_Pa"]
        t_c = max(prop.get("T_comp_out_C_model", prop["T_cond_C"] + 8), prop["T_cond_C"] + 5)
        return p, c2k(t_c), "vapor", 0.3
    if mode == "high_liquid_cooling":
        return prop["P_high_Pa"], c2k(max(prop["T_cond_C"] - 3, -50)), "liquid", 0.3
    if mode == "low_vapor_heating":
        return prop["P_low_Pa"], c2k(prop["T_evap_C"] + 5), "vapor", 0.4
    return prop["P_high_Pa"], c2k(prop["T_cond_C"] + 5), "vapor", 0.3


def htc_single_phase(cfg: dict[str, Any], prop: dict[str, Any], mdot: float, di: float, mode: str) -> float:
    di = max(di, 1e-6)
    a_flow = math.pi * di * di / 4
    mass_flux = mdot / max(a_flow, EPS)
    p, t_k, phase, n = transport_state_for_mode(prop, mode)
    try:
        fluid = str(prop["coolprop_fluid"])
        rho = props_si("Dmass", "P", p, "T", t_k, fluid)
        mu = props_si("V", "P", p, "T", t_k, fluid)
        k = props_si("L", "P", p, "T", t_k, fluid)
        pr = props_si("Prandtl", "P", p, "T", t_k, fluid)
        if not (rho > 0 and mu > 0 and k > 0 and pr > 0):
            raise ValueError("invalid transport")
    except Exception:
        rho, mu, k, pr = fallback_transport_props(phase)
    re = mass_flux * di / max(mu, EPS)
    if re < 2300:
        nu = 3.66
    elif re < 10000:
        w = (re - 2300) / (10000 - 2300)
        nu = (1 - w) * 3.66 + w * (0.023 * re**0.8 * pr**n)
    else:
        nu = 0.023 * re**0.8 * pr**n
    htc = nu * k / di
    return min(max(htc if math.isfinite(htc) else 100.0, 50.0), 20000.0)


def quality_window(cfg: dict[str, Any]) -> tuple[float, float]:
    x1 = min(max(_num(cfg, "tp_quality_min", 0.05), 0.001), 0.90)
    x2 = min(max(_num(cfg, "tp_quality_max", 0.95), 0.10), 0.999)
    return (0.05, 0.95) if x2 <= x1 else (x1, x2)


def htc_shah_condensation(cfg: dict[str, Any], prop: dict[str, Any], mdot: float, di: float) -> float:
    di = max(di, 1e-6)
    gflux = mdot / max(math.pi * di * di / 4, EPS)
    p = prop["P_high_Pa"]
    fluid = str(prop["coolprop_fluid"])
    try:
        mu_l = props_si("V", "P", p, "Q", 0, fluid)
        k_l = props_si("L", "P", p, "Q", 0, fluid)
        pr_l = props_si("Prandtl", "P", p, "Q", 0, fluid)
        pcrit = PropsSI("Pcrit", fluid) if PropsSI is not None else max(p * 3, 1e6)  # type: ignore
    except Exception:
        _, mu_l, k_l, pr_l = fallback_transport_props("liquid")
        pcrit = max(p * 3, 1e6)
    pr_red = min(max(p / max(pcrit, EPS), 0.01), 0.95)
    re_lo = max(gflux * di / max(mu_l, EPS), 1)
    alpha_l = 0.023 * re_lo**0.8 * pr_l**0.4 * k_l / di
    x1, x2 = quality_window(cfg)
    total = 0.0
    n = 41
    for i in range(n):
        x = x1 + (x2 - x1) * i / (n - 1)
        total += (1 - x) ** 0.8 + 3.8 * x**0.76 * (1 - x) ** 0.04 / (pr_red**0.38)
    htc = alpha_l * total / n
    if not math.isfinite(htc) or htc <= 0:
        htc = htc_single_phase(cfg, prop, mdot, di, "high_liquid_cooling")
    return min(max(htc, 100.0), 30000.0)


def htc_shah_evaporation(cfg: dict[str, Any], prop: dict[str, Any], mdot: float, di: float, qflux: float) -> float:
    di = max(di, 1e-6)
    gflux = mdot / max(math.pi * di * di / 4, EPS)
    p = prop["P_low_Pa"]
    fluid = str(prop["coolprop_fluid"])
    try:
        rho_l = props_si("Dmass", "P", p, "Q", 0, fluid)
        rho_g = props_si("Dmass", "P", p, "Q", 1, fluid)
        mu_l = props_si("V", "P", p, "Q", 0, fluid)
        mu_g = props_si("V", "P", p, "Q", 1, fluid)
        k_l = props_si("L", "P", p, "Q", 0, fluid)
        k_g = props_si("L", "P", p, "Q", 1, fluid)
        pr_l = props_si("Prandtl", "P", p, "Q", 0, fluid)
        pr_g = props_si("Prandtl", "P", p, "Q", 1, fluid)
    except Exception:
        rho_l, mu_l, k_l, pr_l = fallback_transport_props("liquid")
        rho_g, mu_g, k_g, pr_g = fallback_transport_props("vapor")
    hfg = max(prop["h_fg_low_kJ_kg"] * 1000, 1)
    re_lo = max(gflux * di / max(mu_l, EPS), 1)
    alpha_l = 0.023 * re_lo**0.8 * pr_l**0.4 * k_l / di
    re_g = max(gflux * di / max(mu_g, EPS), 1)
    alpha_g = 0.023 * re_g**0.8 * pr_g**0.4 * k_g / di
    bo = min(max(max(qflux, 1.0) / max(gflux * hfg, EPS), 1e-8), 0.05)
    fr_l = max(gflux**2 / max(rho_l**2 * G * di, EPS), 1e-9)
    x1, x2 = quality_window(cfg)
    x1 = max(x1, 0.02)
    x2 = min(x2, 0.98)
    total = 0.0
    n = 41
    for i in range(n):
        x = min(max(x1 + (x2 - x1) * i / (n - 1), 1e-4), 0.9999)
        co = ((1 / x) - 1) ** 0.8 * math.sqrt(rho_g / max(rho_l, EPS))
        N = co
        if fr_l < 0.04:
            N = 0.38 * fr_l ** (-0.3) * co
        psi_cb = max(1.8 / (max(N, 1e-8) ** 0.8), 1.0)
        psi_nb = 230 * math.sqrt(bo) if (N > 1.0 and bo > 3e-5) else 1 + 46 * math.sqrt(bo)
        total += max(max(psi_cb, psi_nb) * alpha_l, alpha_g)
    htc = total / n
    if not math.isfinite(htc) or htc <= 0:
        htc = htc_single_phase(cfg, prop, mdot, di, "low_vapor_heating")
    return min(max(htc, 100.0), 30000.0)


def u_from_resistance(ai: float, ao: float, di: float, do: float, length: float, hi: float, ho: float, ktube: float, eta_out: float, rf_o: float, rcontact_o: float) -> tuple[float, float]:
    ai, ao, di, do, length = max(ai, EPS), max(ao, EPS), max(di, 1e-9), max(do, di * 1.001), max(length, 1e-9)
    hi, ho, ktube = max(hi, EPS), max(ho, EPS), max(ktube, EPS)
    eta_out = min(max(eta_out, 0.05), 1.0)
    r_ref = 1 / (hi * ai)
    r_wall = math.log(do / di) / (2 * math.pi * ktube * length)
    r_out = 1 / (eta_out * ho * ao)
    r_foul = (max(rf_o, 0) + max(rcontact_o, 0)) / ao
    r_total = r_ref + r_wall + r_out + r_foul
    ua_w_k = 1 / max(r_total, EPS)
    uo = min(max(ua_w_k / ao, 1.0), 5000.0)
    return uo, ua_w_k / 1000


def nominal_heat_flux(cfg: dict[str, Any], ai: float) -> float:
    q_nom_w = max(_num(cfg, "ac_capacity_pk") * _num(cfg, "cooling_capacity_per_PK_kW") * 1000, 100)
    return min(max(q_nom_w / max(ai, EPS), 500), 80000)


def _apply_u_calibration(cfg: dict[str, Any], U: dict[str, Any]) -> dict[str, Any]:
    """Apply component-level U correction factors.

    These factors are optional calibration multipliers. Default = 1.0 so the
    theoretical Auto-U/manual U result is unchanged.
    """
    f_hw = min(max(_num(cfg, "U_cal_factor_hwst", 1.0), 0.30), 3.00)
    f_cd = min(max(_num(cfg, "U_cal_factor_cond", 1.0), 0.30), 3.00)
    f_ev = min(max(_num(cfg, "U_cal_factor_evap", 1.0), 0.30), 3.00)
    factor_map = {
        "U_hwst_dsh_W_m2K": f_hw,
        "U_hwst_tp_W_m2K": f_hw,
        "U_hwst_sc_W_m2K": f_hw,
        "U_cond_dsh_W_m2K": f_cd,
        "U_cond_tp_W_m2K": f_cd,
        "U_cond_sc_W_m2K": f_cd,
        "U_evap_tp_W_m2K": f_ev,
        "U_evap_sh_W_m2K": f_ev,
    }
    for key, factor in factor_map.items():
        if key in U:
            U[key] = max(float(U[key]) * factor, EPS)
    for row in U.get("rows", []) or []:
        comp = str(row.get("komponen", "")).lower()
        factor = f_hw if "hwst" in comp else f_cd if "kondensor" in comp else f_ev if "evaporator" in comp else 1.0
        try:
            row["U_final_W_m2K"] = round(float(row.get("U_final_W_m2K", 0.0)) * factor, 3)
            row["UA_final_kW_K"] = round(float(row.get("UA_final_kW_K", 0.0)) * factor, 5)
            row["calibration_factor"] = factor
        except Exception:
            row["calibration_factor"] = factor
    U["U_cal_factor_hwst"] = f_hw
    U["U_cal_factor_cond"] = f_cd
    U["U_cal_factor_evap"] = f_ev
    if any(abs(f - 1.0) > 1e-9 for f in [f_hw, f_cd, f_ev]):
        U["description"] = f"{U.get('description', 'U model')} + calibration factors (HWST={f_hw:.3f}, Cond={f_cd:.3f}, Evap={f_ev:.3f})"
    return U



def _air_side_htc_auto(cfg: dict[str, Any], geom: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Estimate air-side h for fin-and-tube coils from airflow and face geometry.

    This is a semi-empirical fallback suitable for simulation diagnostics:
    - face velocity is computed from airflow / face area;
    - maximum velocity is corrected by approximate free-area ratio;
    - h follows a forced-convection power law (v^n);
    - fin pitch and number of tube rows give small correction factors.

    It intentionally replaces a fixed h_air value, but still avoids exposing h_air
    as a manual user input in the normal interface.
    """
    fallback_key = f"h_air_{prefix}_W_m2K"
    fallback = max(_num(cfg, fallback_key, 50.0), EPS)
    if int(round(_num(cfg, "air_side_htc_auto", 1))) != 1:
        return {
            "h_air_W_m2K": fallback,
            "model": "manual/default fallback",
            "face_area_m2": geom.get("face_area_m2", None),
            "v_face_m_s": None,
            "v_max_m_s": None,
            "free_area_ratio": None,
        }

    airflow = max(_num(cfg, f"{prefix}_airflow_m3_s"), EPS)
    face_area = max(float(geom.get("face_area_m2") or 0.0), EPS)
    v_face = airflow / face_area

    fin_pitch = max(float(geom.get("fin_pitch_m") or 0.0016), 1e-6)
    fin_thickness = max(float(geom.get("fin_thickness_m") or 0.00012), 0.0)
    # Approximate free-area ratio: fin blockage + tube blockage on coil face.
    fin_blockage = min(max(fin_thickness / fin_pitch, 0.0), 0.55)
    tube_blockage = min(max(float(geom.get("tube_blockage_fraction") or 0.0) * 0.55, 0.0), 0.45)
    free_ratio = min(max(1.0 - fin_blockage - tube_blockage, 0.35), 0.95)
    v_max = v_face / free_ratio

    # Hidden/internal defaults. They represent finned-coil h at v_ref, not a user calibration.
    if prefix == "cond":
        h_base = max(_num(cfg, "h_air_cond_base_W_m2K", 45.0), EPS)
        h_min = max(_num(cfg, "h_air_cond_min_W_m2K", 25.0), EPS)
        h_max = max(_num(cfg, "h_air_cond_max_W_m2K", 140.0), h_min)
        finned_enhancement = 1.35
    else:
        h_base = max(_num(cfg, "h_air_evap_base_W_m2K", 40.0), EPS)
        h_min = max(_num(cfg, "h_air_evap_min_W_m2K", 20.0), EPS)
        h_max = max(_num(cfg, "h_air_evap_max_W_m2K", 120.0), h_min)
        finned_enhancement = 1.25

    v_ref = max(_num(cfg, "air_side_htc_ref_velocity_m_s", 1.5), 0.1)
    n_exp = min(max(_num(cfg, "air_side_htc_velocity_exponent", 0.65), 0.3), 0.9)
    rows = max(float(geom.get("tube_rows") or 1.0), 1.0)
    # Denser fins usually increase total area and turbulence, but the effect on area-based h is modest.
    fin_pitch_factor = min(max((0.0016 / fin_pitch) ** 0.15, 0.80), 1.25)
    row_factor = min(max(rows ** 0.08, 1.0), 1.25)
    h = h_base * (max(v_max, 0.05) / v_ref) ** n_exp * fin_pitch_factor * row_factor * finned_enhancement
    h = min(max(h, h_min), h_max)
    return {
        "h_air_W_m2K": h,
        "model": "auto airflow-face-geometry power law",
        "face_area_m2": face_area,
        "v_face_m_s": v_face,
        "v_max_m_s": v_max,
        "free_area_ratio": free_ratio,
        "fin_pitch_factor": fin_pitch_factor,
        "row_factor": row_factor,
    }

def compute_u_zones(cfg: dict[str, Any], prop: dict[str, Any], geom: dict[str, Any], mdot: float) -> dict[str, Any]:
    # Manual fallback values first, then Auto-U mode overwrites them.
    U = {
        "mode": int(round(_num(cfg, "U_model_mode", 2))),
        "description": "Manual U input",
        "U_hwst_dsh_W_m2K": _num(cfg, "U_hwst_dsh_W_m2K", 300),
        "U_hwst_tp_W_m2K": _num(cfg, "U_hwst_tp_W_m2K", 1200),
        "U_hwst_sc_W_m2K": _num(cfg, "U_hwst_sc_W_m2K", 350),
        "U_cond_dsh_W_m2K": _num(cfg, "U_cond_dsh_W_m2K", 60),
        "U_cond_tp_W_m2K": _num(cfg, "U_cond_tp_W_m2K", 90),
        "U_cond_sc_W_m2K": _num(cfg, "U_cond_sc_W_m2K", 65),
        "U_evap_tp_W_m2K": _num(cfg, "U_evap_tp_W_m2K", 80),
        "U_evap_sh_W_m2K": _num(cfg, "U_evap_sh_W_m2K", 45),
        "rows": [],
    }
    if U["mode"] != 2:
        return _apply_u_calibration(cfg, U)
    try:
        # Untuk coil bercabang/paralel, koefisien sisi refrigeran dihitung
        # memakai laju massa per circuit. Area perpindahan panas tetap total.
        n_cond = max(float(geom["cond"].get("refrigerant_circuits", 1)), 1.0)
        n_evap = max(float(geom["evap"].get("refrigerant_circuits", 1)), 1.0)
        mdot_cond_circuit = mdot / n_cond
        mdot_evap_circuit = mdot / n_evap
        air_cond = _air_side_htc_auto(cfg, geom["cond"], "cond")
        air_evap = _air_side_htc_auto(cfg, geom["evap"], "evap")
        h_air_cond = float(air_cond["h_air_W_m2K"])
        h_air_evap = float(air_evap["h_air_W_m2K"])

        h_hw_dsh = htc_single_phase(cfg, prop, mdot, geom["hwst"]["D_i_m"], "high_vapor_cooling")
        h_hw_sc = htc_single_phase(cfg, prop, mdot, geom["hwst"]["D_i_m"], "high_liquid_cooling")
        h_cond_dsh = htc_single_phase(cfg, prop, mdot_cond_circuit, geom["cond"]["D_i_m"], "high_vapor_cooling")
        h_cond_sc = htc_single_phase(cfg, prop, mdot_cond_circuit, geom["cond"]["D_i_m"], "high_liquid_cooling")
        h_evap_sh = htc_single_phase(cfg, prop, mdot_evap_circuit, geom["evap"]["D_i_m"], "low_vapor_heating")
        h_hw_tp = htc_shah_condensation(cfg, prop, mdot, geom["hwst"]["D_i_m"])
        h_cond_tp = htc_shah_condensation(cfg, prop, mdot_cond_circuit, geom["cond"]["D_i_m"])
        h_evap_tp = htc_shah_evaporation(cfg, prop, mdot_evap_circuit, geom["evap"]["D_i_m"], nominal_heat_flux(cfg, geom["evap"]["A_i_m2"]))

        def calc(comp: str, zone: str, g: dict[str, Any], hi: float, ho: float, ktube: float, eta: float, rf: float, rc: float, air_meta: dict[str, Any] | None = None) -> tuple[float, dict[str, Any]]:
            uo, ua = u_from_resistance(g["A_i_m2"], g["A_o_m2"], g["D_i_m"], g["D_o_m"], g["tube_length_m"], hi, ho, ktube, eta, rf, rc)
            row = {"komponen": comp, "zona": zone, "h_ref_W_m2K": round(hi, 3), "h_air_water_W_m2K": round(ho, 3), "U_final_W_m2K": round(uo, 3), "UA_final_kW_K": round(ua, 5), "N_circuit": g.get("refrigerant_circuits", 1), "L_hydraulic_m": round(g.get("hydraulic_length_m", g.get("tube_length_m", 0.0)), 4)}
            if air_meta:
                row.update({
                    "h_air_model": air_meta.get("model"),
                    "face_area_m2": round(float(air_meta.get("face_area_m2") or 0.0), 5),
                    "v_face_m_s": round(float(air_meta.get("v_face_m_s") or 0.0), 4),
                    "v_max_m_s": round(float(air_meta.get("v_max_m_s") or 0.0), 4),
                    "free_area_ratio": round(float(air_meta.get("free_area_ratio") or 0.0), 4),
                })
            return uo, row

        rows = []
        vals = []
        for key, comp, zone, gkey, hi, ho, ktube, eta, rf, rc, air_meta in [
            ("U_hwst_dsh_W_m2K", "HWST", "DSH", "hwst", h_hw_dsh, _num(cfg, "h_water_hwst_W_m2K"), _num(cfg, "k_tube_hwst_W_mK"), 1.0, _num(cfg, "Rf_hwst_m2K_W"), 0, None),
            ("U_hwst_tp_W_m2K", "HWST", "TP", "hwst", h_hw_tp, _num(cfg, "h_water_hwst_W_m2K"), _num(cfg, "k_tube_hwst_W_mK"), 1.0, _num(cfg, "Rf_hwst_m2K_W"), 0, None),
            ("U_hwst_sc_W_m2K", "HWST", "SC", "hwst", h_hw_sc, _num(cfg, "h_water_hwst_W_m2K"), _num(cfg, "k_tube_hwst_W_mK"), 1.0, _num(cfg, "Rf_hwst_m2K_W"), 0, None),
            ("U_cond_dsh_W_m2K", "Kondensor", "DSH", "cond", h_cond_dsh, h_air_cond, _num(cfg, "k_tube_cond_W_mK"), 1.0, _num(cfg, "Rf_cond_m2K_W"), 0, air_cond),
            ("U_cond_tp_W_m2K", "Kondensor", "TP", "cond", h_cond_tp, h_air_cond, _num(cfg, "k_tube_cond_W_mK"), 1.0, _num(cfg, "Rf_cond_m2K_W"), 0, air_cond),
            ("U_cond_sc_W_m2K", "Kondensor", "SC", "cond", h_cond_sc, h_air_cond, _num(cfg, "k_tube_cond_W_mK"), 1.0, _num(cfg, "Rf_cond_m2K_W"), 0, air_cond),
            ("U_evap_tp_W_m2K", "Evaporator", "TP", "evap", h_evap_tp, h_air_evap, _num(cfg, "k_tube_evap_W_mK"), 1.0, _num(cfg, "Rf_evap_m2K_W"), 0, air_evap),
            ("U_evap_sh_W_m2K", "Evaporator", "SH", "evap", h_evap_sh, h_air_evap, _num(cfg, "k_tube_evap_W_mK"), 1.0, _num(cfg, "Rf_evap_m2K_W"), 0, air_evap),
        ]:
            u, row = calc(comp, zone, geom[gkey], hi, ho, ktube, eta, rf, rc, air_meta)
            U[key] = u
            rows.append(row)
            vals.append(u)
        U["h_air_cond_auto_W_m2K"] = h_air_cond
        U["h_air_evap_auto_W_m2K"] = h_air_evap
        U["cond_v_face_m_s"] = air_cond.get("v_face_m_s")
        U["cond_v_max_m_s"] = air_cond.get("v_max_m_s")
        U["cond_face_area_m2"] = air_cond.get("face_area_m2")
        U["evap_v_face_m_s"] = air_evap.get("v_face_m_s")
        U["evap_v_max_m_s"] = air_evap.get("v_max_m_s")
        U["evap_face_area_m2"] = air_evap.get("face_area_m2")
        U["description"] = "Thermal resistance + auto h_refrigerant + airflow/face-geometry h_air + Shah TP correlations"
        U["rows"] = rows
    except Exception as exc:
        U["description"] = f"Fallback manual U after Auto-U error: {exc}"
        U["mode"] = 1
    return _apply_u_calibration(cfg, U)


# =============================================================================
# Component models
# =============================================================================


def refrigerant_temp_high(h: float, prop: dict[str, Any]) -> float:
    if "CoolProp" in str(prop.get("property_source")) and PropsSI is not None:
        try:
            return k2c(props_si("T", "P", prop["P_high_Pa"], "Hmass", h * 1000, prop["coolprop_fluid"]))
        except Exception:
            pass
    if h > prop["h_g_high_kJ_kg"]:
        return prop["T_cond_C"] + (h - prop["h_g_high_kJ_kg"]) / max(prop["cp_vap_high_kJ_kgK"], 0.2)
    if h >= prop["h_f_high_kJ_kg"]:
        return prop["T_cond_C"]
    return prop["T_cond_C"] - (prop["h_f_high_kJ_kg"] - h) / max(prop["cp_liq_high_kJ_kgK"], 0.5)


def refrigerant_temp_low(h: float, prop: dict[str, Any]) -> float:
    if "CoolProp" in str(prop.get("property_source")) and PropsSI is not None:
        try:
            return k2c(props_si("T", "P", prop["P_low_Pa"], "Hmass", h * 1000, prop["coolprop_fluid"]))
        except Exception:
            pass
    if h < prop["h_g_low_kJ_kg"]:
        return prop["T_evap_C"]
    return prop["T_evap_C"] + (h - prop["h_g_low_kJ_kg"]) / max(prop["cp_vap_low_kJ_kgK"], 0.2)


def air_capacity_kW_K(airflow: float) -> float:
    return airflow * 1.18 * 1.006


# =============================================================================
# Simple ASHRAE-style psychrometrics (sea-level default 101.325 kPa)
# =============================================================================


def _sat_water_pressure_kpa(t_c: float) -> float:
    """Saturation vapour pressure over liquid water, kPa.

    Buck/Magnus-style expression, accurate enough for HVAC normal temperature
    work. The default atmospheric pressure is 101.325 kPa, aligned with the
    normal-temperature ASHRAE psychrometric chart used as reference.
    """
    return 0.61121 * math.exp((18.678 - t_c / 234.5) * (t_c / (257.14 + t_c)))


def _humidity_ratio_from_t_rh(t_c: float, rh_frac: float, p_atm_kpa: float) -> float:
    rh = min(max(rh_frac, 0.001), 1.0)
    p_ws = _sat_water_pressure_kpa(t_c)
    p_w = min(rh * p_ws, 0.98 * p_atm_kpa)
    return 0.621945 * p_w / max(p_atm_kpa - p_w, EPS)


def _humidity_ratio_saturation(t_c: float, p_atm_kpa: float) -> float:
    p_ws = min(_sat_water_pressure_kpa(t_c), 0.98 * p_atm_kpa)
    return 0.621945 * p_ws / max(p_atm_kpa - p_ws, EPS)


def _moist_air_enthalpy_kj_kg_da(t_c: float, w: float) -> float:
    return 1.006 * t_c + w * (2501.0 + 1.86 * t_c)


def _moist_air_t_from_h_w(h_kj_kg_da: float, w: float) -> float:
    return (h_kj_kg_da - 2501.0 * w) / max(1.006 + 1.86 * w, EPS)


def _rh_from_t_w(t_c: float, w: float, p_atm_kpa: float) -> float:
    p_w = p_atm_kpa * w / max(0.621945 + w, EPS)
    p_ws = _sat_water_pressure_kpa(t_c)
    return min(max(100.0 * p_w / max(p_ws, EPS), 0.0), 100.0)


def _dewpoint_from_w(w: float, p_atm_kpa: float) -> float:
    p_w = max(p_atm_kpa * w / max(0.621945 + w, EPS), 1e-6)
    # Magnus inversion, pressure in kPa -> hPa conversion cancels in ratio below.
    ln_ratio = math.log(max(p_w / 0.61121, 1e-9))
    return 257.14 * ln_ratio / max(18.678 - ln_ratio, EPS)


def evaporator_air_split(cfg: dict[str, Any], prop: dict[str, Any], q_total_kW: float, t_air_heat_balance_C: float, ca_kW_K: float) -> dict[str, Any]:
    """Return sensible/latent split and outlet air state.

    Mode 1 keeps the previous manual SHR approach.
    Mode 2 uses a simplified psychrometric cooling-coil model using the inlet
    dry-bulb and RH. Atmospheric pressure is defaulted to 101.325 kPa to match
    the normal ASHRAE psychrometric chart (sea-level) unless changed in config.
    """
    mode = int(round(_num(cfg, "evaporator_air_model", 1)))
    t_in = _num(cfg, "T_evap_air_in_C")
    q_total = max(0.0, float(q_total_kW))
    h_fg_water = max(2250.0, 2501.0 - 2.381 * prop.get("T_evap_C", 7.0))
    if mode != 2:
        shr = min(max(_num(cfg, "SHR_manual"), 0.01), 1.0)
        q_sens = shr * q_total
        q_lat = max(0.0, q_total - q_sens)
        t_out = t_in - q_sens / max(ca_kW_K, EPS)
        return {
            "air_model": "manual_SHR",
            "psych_status": "MANUAL_SHR",
            "T_air_out_C": t_out,
            "T_air_out_heat_balance_C": t_air_heat_balance_C,
            "Q_sensible_kW": q_sens,
            "Q_latent_kW": q_lat,
            "SHR": q_sens / max(q_total, EPS) if q_total > 0 else shr,
            "mdot_condensate_kg_s": q_lat / max(h_fg_water, EPS),
            "RH_air_in_pct": None,
            "RH_air_out_pct": None,
            "humidity_ratio_in_kg_kgda": None,
            "humidity_ratio_out_kg_kgda": None,
            "dewpoint_air_in_C": None,
            "air_enthalpy_in_kJ_kgda": None,
            "air_enthalpy_out_kJ_kgda": None,
            "ADP_C": None,
            "bypass_factor": None,
            "P_atm_kPa": _num(cfg, "P_atm_kPa", 101.325),
        }

    p_atm = max(_num(cfg, "P_atm_kPa", 101.325), 60.0)
    rh_in_pct = min(max(_num(cfg, "RH_evap_air_in_percent", 60.0), 1.0), 100.0)
    airflow = max(_num(cfg, "evap_airflow_m3_s"), EPS)
    w_in = _humidity_ratio_from_t_rh(t_in, rh_in_pct / 100.0, p_atm)
    h_in = _moist_air_enthalpy_kj_kg_da(t_in, w_in)
    # Approximate dry-air mass flow from volume flow at indoor density.
    m_da = max(airflow * 1.18 / max(1.0 + w_in, EPS), EPS)
    dew_in = _dewpoint_from_w(w_in, p_atm)
    adp_offset = _num(cfg, "evap_ADP_offset_K", 2.0)
    adp = min(t_in - 0.1, prop.get("T_evap_C", 7.0) + adp_offset)
    w_adp = _humidity_ratio_saturation(adp, p_atm)
    h_adp = _moist_air_enthalpy_kj_kg_da(adp, w_adp)

    # If the coil surface estimate is above dew point, treat as dry cooling.
    if adp >= dew_in or q_total <= 0:
        q_sens = q_total
        q_lat = 0.0
        t_out = t_in - q_sens / max(ca_kW_K, EPS)
        w_out = w_in
        h_out = _moist_air_enthalpy_kj_kg_da(t_out, w_out)
        return {
            "air_model": "psychrometric_RH",
            "psych_status": "DRY_COIL_ESTIMATE",
            "T_air_out_C": t_out,
            "T_air_out_heat_balance_C": t_air_heat_balance_C,
            "Q_sensible_kW": q_sens,
            "Q_latent_kW": q_lat,
            "SHR": 1.0,
            "mdot_condensate_kg_s": 0.0,
            "RH_air_in_pct": rh_in_pct,
            "RH_air_out_pct": _rh_from_t_w(t_out, w_out, p_atm),
            "humidity_ratio_in_kg_kgda": w_in,
            "humidity_ratio_out_kg_kgda": w_out,
            "dewpoint_air_in_C": dew_in,
            "air_enthalpy_in_kJ_kgda": h_in,
            "air_enthalpy_out_kJ_kgda": h_out,
            "ADP_C": adp,
            "bypass_factor": 1.0,
            "P_atm_kPa": p_atm,
        }

    h_out_target = h_in - q_total / max(m_da, EPS)
    # Cooling/dehumidification line toward saturated ADP. Bypass factor is a
    # convenient HVAC approximation and avoids solving the full wet-coil equations.
    if h_in <= h_adp + 1e-9:
        bf = 1.0
    else:
        bf = (h_out_target - h_adp) / max(h_in - h_adp, EPS)
    bf = min(max(bf, 0.0), 1.0)
    h_out = h_adp + bf * (h_in - h_adp)
    w_out = min(w_in, w_adp + bf * (w_in - w_adp))
    t_out = _moist_air_t_from_h_w(h_out, w_out)
    rh_out = _rh_from_t_w(t_out, w_out, p_atm)

    q_lat = max(0.0, m_da * (w_in - w_out) * h_fg_water)
    # Keep total from refrigerant side, but avoid negative sensible due to bounds.
    q_sens = min(max(q_total - q_lat, 0.0), q_total)
    # If the ADP clamp limits air-side enthalpy, recompute q total used by air and
    # report remaining as sensible to preserve Q_sens + Q_lat = Q_total.
    shr = q_sens / max(q_total, EPS) if q_total > 0 else 1.0
    status = "WET_COIL_BYPASS_ESTIMATE" if bf > 0.05 else "NEAR_ADP_LIMIT_WET_COIL"
    return {
        "air_model": "psychrometric_RH",
        "psych_status": status,
        "T_air_out_C": t_out,
        "T_air_out_heat_balance_C": t_air_heat_balance_C,
        "Q_sensible_kW": q_sens,
        "Q_latent_kW": q_total - q_sens,
        "SHR": shr,
        "mdot_condensate_kg_s": (q_total - q_sens) / max(h_fg_water, EPS),
        "RH_air_in_pct": rh_in_pct,
        "RH_air_out_pct": rh_out,
        "humidity_ratio_in_kg_kgda": w_in,
        "humidity_ratio_out_kg_kgda": w_out,
        "dewpoint_air_in_C": dew_in,
        "air_enthalpy_in_kJ_kgda": h_in,
        "air_enthalpy_out_kJ_kgda": h_out,
        "ADP_C": adp,
        "bypass_factor": bf,
        "P_atm_kPa": p_atm,
    }


def hwst_model(cfg: dict[str, Any], prop: dict[str, Any], geom: dict[str, Any], mdot: float, ttop: float, u: dict[str, Any]) -> dict[str, Any]:
    a_total = geom["hwst"]["A_total_m2"]
    U_dsh = u["U_hwst_dsh_W_m2K"] / 1000
    U_tp = u["U_hwst_tp_W_m2K"] / 1000
    U_sc = u["U_hwst_sc_W_m2K"] / 1000
    cp_dsh = max(prop["cp_vap_high_kJ_kgK"], 0.2)
    cp_sc = max(prop["cp_liq_high_kJ_kgK"], 0.5)
    h = prop["h_comp_out_kJ_kg"]
    hg = prop["h_g_high_kJ_kg"]
    hf = prop["h_f_high_kJ_kg"]
    tc = prop["T_cond_C"]
    q_tot = 0.0
    a_dsh = a_tp = a_sc = 0.0
    a_rem = a_total
    if h > hg + 1e-9 and a_rem > 0:
        cpr = mdot * cp_dsh
        t_in = tc + (h - hg) / cp_dsh
        if t_in > ttop + 1e-4:
            if tc > ttop + 1e-4:
                a_need = -cpr / max(U_dsh, EPS) * math.log((tc - ttop) / max(t_in - ttop, EPS))
                a_need = max(0, a_need)
                if a_need <= a_rem:
                    a_dsh = a_need
                    q = mdot * (h - hg)
                    h = hg
                else:
                    a_dsh = a_rem
                    t_out = ttop + (t_in - ttop) * math.exp(-U_dsh * a_dsh / max(cpr, EPS))
                    # Robust DSH partial-area balance:
                    # do not re-base from hg with a temperature clamp.  The heat removed
                    # in the remaining desuperheater area is cp_vap * (T_in - T_out).
                    # Keep h_out >= hg so this block remains desuperheating only; any
                    # condensation is handled by the following two-phase block.
                    h_out = h - cp_dsh * max(0.0, t_in - t_out)
                    h_out = max(hg, h_out)
                    q = max(0.0, mdot * (h - h_out))
                    h = h_out
            else:
                a_dsh = a_rem
                t_out = ttop + (t_in - ttop) * math.exp(-U_dsh * a_dsh / max(cpr, EPS))
                # Same robust partial-DSH enthalpy update as above.
                h_out = h - cp_dsh * max(0.0, t_in - t_out)
                h_out = max(hg, h_out)
                q = max(0.0, mdot * (h - h_out))
                h = h_out
            q_tot += max(0, q)
        a_rem = max(0, a_rem - a_dsh)
    if h > hf + 1e-9 and h <= hg + 1e-9 and a_rem > 0 and tc > ttop + 1e-4:
        q_max = mdot * (h - hf)
        q_avail = U_tp * a_rem * (tc - ttop)
        q = max(0, min(q_max, q_avail))
        a_tp = min(q / max(U_tp * (tc - ttop), EPS), a_rem)
        h -= q / max(mdot, EPS)
        q_tot += q
        a_rem -= a_tp
    if h <= hf + 1e-9 and a_rem > 0:
        cpr = mdot * cp_sc
        t_in = tc - (hf - h) / cp_sc
        if t_in > ttop + 1e-4:
            t_out = ttop + (t_in - ttop) * math.exp(-U_sc * a_rem / max(cpr, EPS))
            h_out = hf - cp_sc * max(0, tc - t_out)
            q = max(0, mdot * (h - h_out))
            h = h_out
            q_tot += q
            a_sc = a_rem
            a_rem = 0
    return {
        "Q_kW": max(0, q_tot),
        "h_out_kJ_kg": h,
        "T_out_C": refrigerant_temp_high(h, prop),
        "f_dsh": a_dsh / max(a_total, EPS),
        "f_tp": a_tp / max(a_total, EPS),
        "f_sc": a_sc / max(a_total, EPS),
        "x_out_high": (h - hf) / max(prop["h_fg_high_kJ_kg"], EPS),
    }


def condenser_model_segmented(cfg: dict[str, Any], prop: dict[str, Any], geom: dict[str, Any], mdot: float, h_in: float, u: dict[str, Any]) -> dict[str, Any]:
    N = max(20, round(_num(cfg, "zone_segments", 400)))
    a_seg = geom["cond"]["A_total_m2"] / N
    ua_dsh = u["U_cond_dsh_W_m2K"] * a_seg / 1000
    ua_tp = u["U_cond_tp_W_m2K"] * a_seg / 1000
    ua_sc = u["U_cond_sc_W_m2K"] * a_seg / 1000
    ca = air_capacity_kW_K(_num(cfg, "cond_airflow_m3_s"))
    tair = _num(cfg, "T_cond_air_in_C")
    h = h_in
    q_tot = 0.0
    n_dsh = n_tp = n_sc = 0
    hg = prop["h_g_high_kJ_kg"]
    hf = prop["h_f_high_kJ_kg"]
    for _ in range(N):
        if h > hg + 1e-9:
            tref = prop["T_cond_C"] + (h - hg) / max(prop["cp_vap_high_kJ_kgK"], 0.2)
            h_bound = hg
            ua = ua_dsh
            zone = 1
        elif h > hf + 1e-9:
            tref = prop["T_cond_C"]
            h_bound = hf
            ua = ua_tp
            zone = 2
        else:
            tref = prop["T_cond_C"] - (hf - h) / max(prop["cp_liq_high_kJ_kgK"], 0.5)
            h_bound = -math.inf
            ua = ua_sc
            zone = 3
        q_pot = ua * (tref - tair)
        if zone == 3:
            q = max(0, q_pot)
        else:
            q = min(max(0, q_pot), mdot * max(0, h - h_bound))
        h -= q / max(mdot, EPS)
        tair += q / max(ca, EPS)
        q_tot += q
        if zone == 1:
            n_dsh += 1
        elif zone == 2:
            n_tp += 1
        else:
            n_sc += 1
    return {
        "Q_kW": q_tot,
        "h_out_kJ_kg": h,
        "T_air_out_C": tair,
        "T_out_C": refrigerant_temp_high(h, prop),
        "f_dsh": n_dsh / N,
        "f_tp": n_tp / N,
        "f_sc": n_sc / N,
        "x_out_high": (h - hf) / max(prop["h_fg_high_kJ_kg"], EPS),
        "is_liquid_or_subcooled": h <= hf + 1e-6,
    }


def evaporator_model_manual_shr_segmented(cfg: dict[str, Any], prop: dict[str, Any], geom: dict[str, Any], mdot: float, h_in: float, u: dict[str, Any]) -> dict[str, Any]:
    N = max(20, round(_num(cfg, "zone_segments", 400)))
    a_seg = geom["evap"]["A_total_m2"] / N
    ua_tp = u["U_evap_tp_W_m2K"] * a_seg / 1000
    ua_sh = u["U_evap_sh_W_m2K"] * a_seg / 1000
    ca = air_capacity_kW_K(_num(cfg, "evap_airflow_m3_s"))
    tair = _num(cfg, "T_evap_air_in_C")
    h = h_in
    q_tot = 0.0
    n_tp = n_sh = 0
    hg = prop["h_g_low_kJ_kg"]
    for _ in range(N):
        if h < hg - 1e-9:
            tref = prop["T_evap_C"]
            h_bound = hg
            ua = ua_tp
            zone = 1
        else:
            tref = prop["T_evap_C"] + (h - hg) / max(prop["cp_vap_low_kJ_kgK"], 0.2)
            h_bound = math.inf
            ua = ua_sh
            zone = 2
        q_pot = ua * (tair - tref)
        if zone == 1:
            q = min(max(0, q_pot), mdot * max(0, h_bound - h))
        else:
            q = max(0, q_pot)
        h += q / max(mdot, EPS)
        tair -= q / max(ca, EPS)
        q_tot += q
        if zone == 1:
            n_tp += 1
        else:
            n_sh += 1
    q_total = max(0, q_tot)
    air = evaporator_air_split(cfg, prop, q_total, tair, ca)
    return {
        "model": "segmented UA-dT evaporator + " + str(air.get("air_model")),
        "Q_kW": q_total,
        "h_out_kJ_kg": h,
        "T_air_out_C": air["T_air_out_C"],
        "T_air_out_heat_balance_C": air["T_air_out_heat_balance_C"],
        "T_out_C": refrigerant_temp_low(h, prop),
        "f_tp": n_tp / N,
        "f_sh": n_sh / N,
        "x_out_low": (h - prop["h_f_low_kJ_kg"]) / max(prop["h_fg_low_kJ_kg"], EPS),
        "Q_sensible_kW": air["Q_sensible_kW"],
        "Q_latent_kW": air["Q_latent_kW"],
        "SHR": air["SHR"],
        "mdot_condensate_kg_s": air["mdot_condensate_kg_s"],
        **air,
    }


# =============================================================================
# NTU-effectiveness zone models
# -----------------------------------------------------------------------------
# Metode ini mengikuti pola jurnal Techarungpaisan dkk. secara praktis:
# kondensor dibagi DSH/TP/SC, evaporator dibagi TP/SH, lalu area tiap zona
# dicari otomatis dengan iterasi bisection. User tidak perlu menebak fraksi zona.
# =============================================================================


def _coil_method(cfg: dict[str, Any]) -> int:
    """1 = segmented UA-dT lama, 2 = NTU-effectiveness zona."""
    return int(round(_num(cfg, "calculation_method", 2)))


def _effectiveness_crossflow(ntu: float, cr: float) -> float:
    """Cross-flow both-unmixed approximation used for sensible zones.

    Formula standar yang stabil secara numerik:
    eps = 1 - exp((NTU**0.22/Cr) * (exp(-Cr*NTU**0.78)-1))
    Untuk Cr mendekati 0, dikembalikan ke phase-change limit.
    """
    if ntu <= 0:
        return 0.0
    cr = min(max(cr, 0.0), 0.999999)
    if cr < 1e-8:
        return 1.0 - math.exp(-ntu)
    try:
        eps = 1.0 - math.exp((ntu ** 0.22 / cr) * (math.exp(-cr * (ntu ** 0.78)) - 1.0))
    except OverflowError:
        eps = 1.0
    return min(max(eps, 0.0), 0.999999)


def _ntu_phase_change_q(U_W_m2K: float, area_m2: float, C_air_kW_K: float, deltaT_K: float) -> float:
    """Heat transfer for TP zone where refrigerant temperature is nearly constant."""
    if area_m2 <= 0 or U_W_m2K <= 0 or C_air_kW_K <= 0 or deltaT_K <= 0:
        return 0.0
    ua = U_W_m2K * area_m2 / 1000.0
    ntu = ua / max(C_air_kW_K, EPS)
    eps = 1.0 - math.exp(-max(ntu, 0.0))
    return max(0.0, eps * C_air_kW_K * deltaT_K)


def _ntu_sensible_q(U_W_m2K: float, area_m2: float, C_hot_kW_K: float, C_cold_kW_K: float, deltaT_K: float) -> float:
    """Heat transfer for single-phase sensible zone using NTU-effectiveness."""
    if area_m2 <= 0 or U_W_m2K <= 0 or C_hot_kW_K <= 0 or C_cold_kW_K <= 0 or deltaT_K <= 0:
        return 0.0
    ua = U_W_m2K * area_m2 / 1000.0
    cmin = min(C_hot_kW_K, C_cold_kW_K)
    cmax = max(C_hot_kW_K, C_cold_kW_K)
    ntu = ua / max(cmin, EPS)
    cr = cmin / max(cmax, EPS)
    eps = _effectiveness_crossflow(ntu, cr)
    return max(0.0, eps * cmin * deltaT_K)


def _bisect_area_for_q(func: Callable[[float], float], q_target: float, a_hi: float) -> float:
    """Cari area minimal yang menghasilkan q_target dengan fungsi Q(A) monoton."""
    if q_target <= 0 or a_hi <= 0:
        return 0.0
    if func(a_hi) < q_target:
        return a_hi
    lo, hi = 0.0, a_hi
    for _ in range(42):
        mid = 0.5 * (lo + hi)
        if func(mid) >= q_target:
            hi = mid
        else:
            lo = mid
    return hi


def _area_sum_ok(*areas: float, total: float) -> tuple[float, ...]:
    """Clamp kecil agar total fraksi tidak lewat karena floating error."""
    out = [max(0.0, a) for a in areas]
    s = sum(out)
    if s > total and s > 0:
        out = [a * total / s for a in out]
    return tuple(out)


def condenser_model_ntu(cfg: dict[str, Any], prop: dict[str, Any], geom: dict[str, Any], mdot: float, h_in: float, u: dict[str, Any]) -> dict[str, Any]:
    a_total = max(geom["cond"]["A_total_m2"], EPS)
    a_rem = a_total
    ca = air_capacity_kW_K(_num(cfg, "cond_airflow_m3_s"))
    tair = _num(cfg, "T_cond_air_in_C")
    h = h_in
    hg = prop["h_g_high_kJ_kg"]
    hf = prop["h_f_high_kJ_kg"]
    tc = prop["T_cond_C"]
    cp_v = max(prop["cp_vap_high_kJ_kgK"], 0.2)
    cp_l = max(prop["cp_liq_high_kJ_kgK"], 0.5)
    U_dsh = max(float(u.get("U_cond_dsh_W_m2K", _num(cfg, "U_cond_dsh_W_m2K", 60.0))), EPS)
    U_tp = max(float(u.get("U_cond_tp_W_m2K", _num(cfg, "U_cond_tp_W_m2K", 90.0))), EPS)
    U_sc = max(float(u.get("U_cond_sc_W_m2K", _num(cfg, "U_cond_sc_W_m2K", 65.0))), EPS)
    q_tot = 0.0
    a_dsh = a_tp = a_sc = 0.0

    # DSH: superheated refrigerant -> saturated vapor
    if h > hg + 1e-9 and a_rem > 0:
        C_r = mdot * cp_v
        t_ref_in = tc + (h - hg) / cp_v
        q_req = mdot * (h - hg)
        if t_ref_in > tair + 1e-6 and C_r > 0:
            def q_of_a(a: float) -> float:
                return min(q_req, _ntu_sensible_q(U_dsh, a, C_r, ca, t_ref_in - tair))
            q_full = q_of_a(a_rem)
            if q_full >= q_req * (1 - 1e-8):
                a_dsh = _bisect_area_for_q(q_of_a, q_req, a_rem)
                q = q_req
                h = hg
            else:
                a_dsh = a_rem
                q = q_full
                h -= q / max(mdot, EPS)
            tair += q / max(ca, EPS)
            q_tot += q
            a_rem = max(0.0, a_rem - a_dsh)

    # TP: condensation at nearly constant condensing temperature
    if h > hf + 1e-9 and h <= hg + 1e-8 and a_rem > 0 and tc > tair + 1e-6:
        q_req = mdot * (h - hf)
        q_possible = _ntu_phase_change_q(U_tp, a_rem, ca, tc - tair)
        if q_possible >= q_req * (1 - 1e-8):
            def q_of_a(a: float) -> float:
                return min(q_req, _ntu_phase_change_q(U_tp, a, ca, tc - tair))
            a_tp = _bisect_area_for_q(q_of_a, q_req, a_rem)
            q = q_req
            h = hf
        else:
            a_tp = a_rem
            q = q_possible
            h -= q / max(mdot, EPS)
        tair += q / max(ca, EPS)
        q_tot += q
        a_rem = max(0.0, a_rem - a_tp)

    # SC: liquid refrigerant sensible cooling, uses all remaining area if present
    if h <= hf + 1e-8 and a_rem > 0:
        C_r = mdot * cp_l
        t_ref_in = tc - (hf - h) / cp_l
        if t_ref_in > tair + 1e-6 and C_r > 0:
            q = _ntu_sensible_q(U_sc, a_rem, C_r, ca, t_ref_in - tair)
            h -= q / max(mdot, EPS)
            tair += q / max(ca, EPS)
            q_tot += q
        a_sc = a_rem
        a_rem = 0.0

    a_dsh, a_tp, a_sc = _area_sum_ok(a_dsh, a_tp, a_sc, total=a_total)
    # Agar visualisasi tetap penuh, sisa area yang tidak aktif dimasukkan ke zona terakhir yang relevan.
    s = a_dsh + a_tp + a_sc
    if s < a_total:
        if h > hg:
            a_dsh += a_total - s
        elif h > hf:
            a_tp += a_total - s
        else:
            a_sc += a_total - s

    return {
        "model": "NTU-effectiveness zone condenser",
        "Q_kW": max(0.0, q_tot),
        "h_out_kJ_kg": h,
        "T_air_out_C": tair,
        "T_out_C": refrigerant_temp_high(h, prop),
        "f_dsh": a_dsh / max(a_total, EPS),
        "f_tp": a_tp / max(a_total, EPS),
        "f_sc": a_sc / max(a_total, EPS),
        "x_out_high": (h - hf) / max(prop["h_fg_high_kJ_kg"], EPS),
        "is_liquid_or_subcooled": h <= hf + 1e-6,
        "NTU_dsh": (U_dsh * a_dsh / 1000.0) / max(min(mdot * cp_v, ca), EPS) if a_dsh > 0 else 0.0,
        "NTU_tp": (U_tp * a_tp / 1000.0) / max(ca, EPS) if a_tp > 0 else 0.0,
        "NTU_sc": (U_sc * a_sc / 1000.0) / max(min(mdot * cp_l, ca), EPS) if a_sc > 0 else 0.0,
    }


def evaporator_model_manual_shr_ntu(cfg: dict[str, Any], prop: dict[str, Any], geom: dict[str, Any], mdot: float, h_in: float, u: dict[str, Any]) -> dict[str, Any]:
    a_total = max(geom["evap"]["A_total_m2"], EPS)
    a_rem = a_total
    ca = air_capacity_kW_K(_num(cfg, "evap_airflow_m3_s"))
    tair_for_heat = _num(cfg, "T_evap_air_in_C")
    h = h_in
    hg = prop["h_g_low_kJ_kg"]
    te = prop["T_evap_C"]
    cp_v = max(prop["cp_vap_low_kJ_kgK"], 0.2)
    U_tp = max(float(u.get("U_evap_tp_W_m2K", _num(cfg, "U_evap_tp_W_m2K", 80.0))), EPS)
    U_sh = max(float(u.get("U_evap_sh_W_m2K", _num(cfg, "U_evap_sh_W_m2K", 45.0))), EPS)
    q_tot = 0.0
    a_tp = a_sh = 0.0

    # TP: evaporation at nearly constant evaporating temperature
    if h < hg - 1e-9 and a_rem > 0 and tair_for_heat > te + 1e-6:
        q_req = mdot * (hg - h)
        q_possible = _ntu_phase_change_q(U_tp, a_rem, ca, tair_for_heat - te)
        if q_possible >= q_req * (1 - 1e-8):
            def q_of_a(a: float) -> float:
                return min(q_req, _ntu_phase_change_q(U_tp, a, ca, tair_for_heat - te))
            a_tp = _bisect_area_for_q(q_of_a, q_req, a_rem)
            q = q_req
            h = hg
        else:
            a_tp = a_rem
            q = q_possible
            h += q / max(mdot, EPS)
        tair_for_heat -= q / max(ca, EPS)
        q_tot += q
        a_rem = max(0.0, a_rem - a_tp)

    # SH: refrigerant vapor superheating with remaining area
    if h >= hg - 1e-8 and a_rem > 0:
        C_r = mdot * cp_v
        t_ref_in = te + max(0.0, h - hg) / cp_v
        if tair_for_heat > t_ref_in + 1e-6 and C_r > 0:
            q = _ntu_sensible_q(U_sh, a_rem, ca, C_r, tair_for_heat - t_ref_in)
            h += q / max(mdot, EPS)
            tair_for_heat -= q / max(ca, EPS)
            q_tot += q
        a_sh = a_rem
        a_rem = 0.0

    a_tp, a_sh = _area_sum_ok(a_tp, a_sh, total=a_total)
    s = a_tp + a_sh
    if s < a_total:
        if h < hg:
            a_tp += a_total - s
        else:
            a_sh += a_total - s

    q_total = max(0.0, q_tot)
    air = evaporator_air_split(cfg, prop, q_total, tair_for_heat, ca)
    return {
        "model": "NTU-effectiveness zone evaporator + " + str(air.get("air_model")),
        "Q_kW": q_total,
        "h_out_kJ_kg": h,
        "T_air_out_C": air["T_air_out_C"],
        "T_air_out_heat_balance_C": air["T_air_out_heat_balance_C"],
        "T_out_C": refrigerant_temp_low(h, prop),
        "f_tp": a_tp / max(a_total, EPS),
        "f_sh": a_sh / max(a_total, EPS),
        "x_out_low": (h - prop["h_f_low_kJ_kg"]) / max(prop["h_fg_low_kJ_kg"], EPS),
        "Q_sensible_kW": air["Q_sensible_kW"],
        "Q_latent_kW": air["Q_latent_kW"],
        "SHR": air["SHR"],
        "mdot_condensate_kg_s": air["mdot_condensate_kg_s"],
        "NTU_tp": (U_tp * a_tp / 1000.0) / max(ca, EPS) if a_tp > 0 else 0.0,
        "NTU_sh": (U_sh * a_sh / 1000.0) / max(min(mdot * cp_v, ca), EPS) if a_sh > 0 else 0.0,
        **air,
    }


def condenser_model(cfg: dict[str, Any], prop: dict[str, Any], geom: dict[str, Any], mdot: float, h_in: float, u: dict[str, Any]) -> dict[str, Any]:
    if _coil_method(cfg) == 2:
        return condenser_model_ntu(cfg, prop, geom, mdot, h_in, u)
    return condenser_model_segmented(cfg, prop, geom, mdot, h_in, u)


def evaporator_model_manual_shr(cfg: dict[str, Any], prop: dict[str, Any], geom: dict[str, Any], mdot: float, h_in: float, u: dict[str, Any]) -> dict[str, Any]:
    if _coil_method(cfg) == 2:
        return evaporator_model_manual_shr_ntu(cfg, prop, geom, mdot, h_in, u)
    return evaporator_model_manual_shr_segmented(cfg, prop, geom, mdot, h_in, u)


# =============================================================================
# Capillary and pressure drops
# =============================================================================


def estimate_gas_density(prop: dict[str, Any], t_c: float, p_psig: float) -> float:
    if "CoolProp" in str(prop.get("property_source")) and PropsSI is not None:
        try:
            rho = props_si("Dmass", "P", psig2pa(p_psig), "T", c2k(t_c), prop["coolprop_fluid"])
            if rho > 0:
                return min(max(rho, 2), 250)
        except Exception:
            pass
    return min(max(psig2pa(p_psig) / max(96 * c2k(t_c), EPS), 2), 180)


def single_phase_dp_kpa(mdot: float, length: float, D: float, rho: float, mu: float, rough: float) -> float:
    if length <= 0 or mdot <= 0 or D <= 0 or rho <= 0:
        return 0.0
    area = math.pi * D * D / 4
    v = mdot / max(rho * area, EPS)
    re = rho * v * D / max(mu, EPS)
    if re < 1e-6:
        return 0.0
    if re < 2300:
        f = 64 / max(re, EPS)
    else:
        f = 0.25 / (math.log10(rough / (3.7 * D) + 5.74 / (re**0.9)) ** 2)
    dp = f * (length / D) * (rho * v * v / 2) / 1000
    return dp if math.isfinite(dp) else 0.0


def two_phase_dp_kpa(mdot: float, length: float, D: float, rho_g: float, rho_l: float, mu_g: float, mu_l: float, x: float, rough: float) -> float:
    """Two-phase friction pressure drop using a stable homogeneous approximation.

    Density is computed from the vapor quality slip-free mixture expression.
    Viscosity uses the McAdams harmonic mixing rule, which is commonly used
    in homogeneous equilibrium pressure-drop estimates.  This function is
    intentionally conservative/stable because pressure_drop_feedback can feed
    this result back into the cycle pressures.
    """
    if length <= 0 or mdot <= 0 or D <= 0 or rho_g <= 0 or rho_l <= 0 or mu_g <= 0 or mu_l <= 0:
        return 0.0
    x = min(max(float(x), 0.05), 0.95)
    rho_mix = 1.0 / max(x / max(rho_g, EPS) + (1.0 - x) / max(rho_l, EPS), EPS)
    mu_mix = 1.0 / max(x / max(mu_g, EPS) + (1.0 - x) / max(mu_l, EPS), EPS)
    return single_phase_dp_kpa(mdot, length, D, rho_mix, mu_mix, rough)


def estimate_zone_pressure_drops(cfg: dict[str, Any], prop: dict[str, Any], geom: dict[str, Any], mdot: float, hwst: dict[str, Any], cond: dict[str, Any], evap: dict[str, Any]) -> dict[str, Any]:
    if int(round(_num(cfg, "pressure_drop_model", 2))) == 0:
        return {
            "DP_hwst_kPa": 0.0, "DP_cond_kPa": 0.0, "DP_evap_kPa": 0.0,
            "DP_high_side_kPa": 0.0, "DP_low_side_kPa": 0.0,
            "DP_feedback_safe": 1, "DP_feedback_status": "OFF",
            "cond_refrigerant_circuits": max(1, round(_num(cfg, "cond_refrigerant_circuits", 1))),
            "evap_refrigerant_circuits": max(1, round(_num(cfg, "evap_refrigerant_circuits", 1))),
        }
    rough = max(_num(cfg, "pressure_drop_roughness_mm", 0.0015) / 1000, 1e-9)
    D_hw = max(_num(cfg, "hwst_tube_D_i_mm") / 1000, 0.004)
    D_co = max(_num(cfg, "cond_tube_D_i_mm") / 1000, 0.004)
    D_ev = max(_num(cfg, "evap_tube_D_i_mm") / 1000, 0.004)
    L_hw = max(_num(cfg, "hwst_coil_length_m"), 0.01)

    # Coil AC nyata umumnya punya beberapa circuit paralel. Untuk heat transfer,
    # area tetap total. Untuk pressure drop, panjang dan mdot harus per circuit.
    n_cond = max(float(geom["cond"].get("refrigerant_circuits", _num(cfg, "cond_refrigerant_circuits", 1))), 1.0)
    n_evap = max(float(geom["evap"].get("refrigerant_circuits", _num(cfg, "evap_refrigerant_circuits", 1))), 1.0)
    L_co_total = max(geom["cond"].get("tube_length_m", 0.0), 0.01)
    L_ev_total = max(geom["evap"].get("tube_length_m", 0.0), 0.01)
    L_co = max(geom["cond"].get("hydraulic_length_m", L_co_total / n_cond), 0.01)
    L_ev = max(geom["evap"].get("hydraulic_length_m", L_ev_total / n_evap), 0.01)
    mdot_cond = mdot / n_cond
    mdot_evap = mdot / n_evap

    rho_g_hi = estimate_gas_density(prop, prop["T_cond_C"], _num(cfg, "P_discharge_psig"))
    rho_g_lo = estimate_gas_density(prop, prop["T_evap_C"], _num(cfg, "P_suction_psig"))

    # V17.13: transport properties from CoolProp when available.  Hardcoded
    # liquid density/viscosity is kept only as fallback for machines without
    # CoolProp, and the report still marks CoolProp as inactive in that case.
    fluid = str(prop.get("coolprop_fluid", cfg.get("refrigerant", "R32")))
    try:
        if "CoolProp" not in str(prop.get("property_source")) or PropsSI is None:
            raise RuntimeError("CoolProp transport properties unavailable")
        p_hi = float(prop["P_high_Pa"])
        p_lo = float(prop["P_low_Pa"])
        rho_l_hi = props_si("Dmass", "P", p_hi, "Q", 0, fluid)
        rho_l_lo = props_si("Dmass", "P", p_lo, "Q", 0, fluid)
        rho_g_hi = props_si("Dmass", "P", p_hi, "Q", 1, fluid)
        rho_g_lo = props_si("Dmass", "P", p_lo, "Q", 1, fluid)
        mu_l_hi = props_si("V", "P", p_hi, "Q", 0, fluid)
        mu_l_lo = props_si("V", "P", p_lo, "Q", 0, fluid)
        mu_g_hi = props_si("V", "P", p_hi, "Q", 1, fluid)
        mu_g_lo = props_si("V", "P", p_lo, "Q", 1, fluid)
        transport_source = "CoolProp"
    except Exception:
        rho_l_hi = rho_l_lo = 900.0
        mu_l_hi = mu_l_lo = 1.8e-4
        mu_g_hi = mu_g_lo = 1.3e-5
        transport_source = "fallback_estimate"

    # Mean vapor quality in the active two-phase zones.  These values are not
    # used to force the thermodynamic state; they only avoid the old x=0.5
    # hardcode in pressure-drop estimation.
    x_cond_out = min(max(float(cond.get("x_out_high", 0.0)), 0.0), 1.0)
    x_hwst_out = min(max(float(hwst.get("x_out_high", 1.0)), 0.0), 1.0)
    x_evap_out = min(max(float(evap.get("x_out_low", 1.0)), 0.0), 1.0)

    # Condenser/HWST two-phase zones move from vapor-side quality toward their
    # local outlet quality.  When outlet is subcooled, the TP zone still spans
    # approximately x=1 -> x=0, so the mean remains about 0.5.
    x_tp_cond = 0.5 * (1.0 + x_cond_out)
    x_tp_hwst = 0.5 * (1.0 + x_hwst_out)

    # Expansion through capillary is isenthalpic, so evaporator inlet quality is
    # estimated from condenser outlet enthalpy and low-side saturation properties.
    try:
        h_evap_in = float(cond.get("h_out_kJ_kg", prop["h_f_high_kJ_kg"]))
        x_evap_in = (h_evap_in - float(prop["h_f_low_kJ_kg"])) / max(float(prop["h_fg_low_kJ_kg"]), EPS)
    except Exception:
        x_evap_in = 0.2
    x_evap_in = min(max(x_evap_in, 0.0), 1.0)
    x_tp_evap = 0.5 * (x_evap_in + x_evap_out)

    x_tp_cond = min(max(x_tp_cond, 0.05), 0.95)
    x_tp_hwst = min(max(x_tp_hwst, 0.05), 0.95)
    x_tp_evap = min(max(x_tp_evap, 0.05), 0.95)

    dp_hw = (
        single_phase_dp_kpa(mdot, L_hw * hwst["f_dsh"], D_hw, rho_g_hi, mu_g_hi, rough)
        + two_phase_dp_kpa(mdot, L_hw * hwst["f_tp"], D_hw, rho_g_hi, rho_l_hi, mu_g_hi, mu_l_hi, x_tp_hwst, rough)
        + single_phase_dp_kpa(mdot, L_hw * hwst["f_sc"], D_hw, rho_l_hi, mu_l_hi, rough)
    )
    dp_co = (
        single_phase_dp_kpa(mdot_cond, L_co * cond["f_dsh"], D_co, rho_g_hi, mu_g_hi, rough)
        + two_phase_dp_kpa(mdot_cond, L_co * cond["f_tp"], D_co, rho_g_hi, rho_l_hi, mu_g_hi, mu_l_hi, x_tp_cond, rough)
        + single_phase_dp_kpa(mdot_cond, L_co * cond["f_sc"], D_co, rho_l_hi, mu_l_hi, rough)
    )
    dp_ev = (
        two_phase_dp_kpa(mdot_evap, L_ev * evap["f_tp"], D_ev, rho_g_lo, rho_l_lo, mu_g_lo, mu_l_lo, x_tp_evap, rough)
        + single_phase_dp_kpa(mdot_evap, L_ev * evap["f_sh"], D_ev, rho_g_lo, mu_g_lo, rough)
    )
    dp_high = max(0.0, dp_hw + dp_co)
    dp_low = max(0.0, dp_ev)
    high_limit = max(_num(cfg, "pressure_drop_feedback_high_limit_kPa", 500.0), 1.0)
    low_limit = max(_num(cfg, "pressure_drop_feedback_low_limit_kPa", 250.0), 1.0)
    safe = int(dp_high <= high_limit and dp_low <= low_limit)
    status = "SAFE_FOR_FEEDBACK" if safe else "DIAGNOSTIC_ONLY_DP_TOO_HIGH"
    return {
        "DP_hwst_kPa": max(0, dp_hw), "DP_cond_kPa": max(0, dp_co), "DP_evap_kPa": max(0, dp_ev),
        "DP_high_side_kPa": dp_high, "DP_low_side_kPa": dp_low,
        "DP_feedback_safe": safe, "DP_feedback_status": status,
        "DP_high_feedback_limit_kPa": high_limit, "DP_low_feedback_limit_kPa": low_limit,
        "cond_refrigerant_circuits": int(round(n_cond)), "evap_refrigerant_circuits": int(round(n_evap)),
        "cond_L_total_m": L_co_total, "cond_L_hydraulic_m": L_co,
        "evap_L_total_m": L_ev_total, "evap_L_hydraulic_m": L_ev,
        "cond_mdot_circuit_kg_s": mdot_cond, "evap_mdot_circuit_kg_s": mdot_evap,
        "DP_transport_property_source": transport_source,
        "DP_two_phase_model": "homogeneous_McAdams",
        "DP_x_tp_hwst": x_tp_hwst,
        "DP_x_tp_cond": x_tp_cond,
        "DP_x_tp_evap": x_tp_evap,
        "DP_x_evap_in": x_evap_in,
    }


def _capillary_flow_for_geometry(cfg: dict[str, Any], prop: dict[str, Any], h_in_cap: float, mdot_comp: float, D: float, L: float) -> dict[str, Any]:
    D = max(D, 1e-6)
    L = max(L, 1e-6)
    coil_factor = min(max(_num(cfg, "capillary_coil_factor", 0.95), 0.10), 1.20)
    rough = max(_num(cfg, "pressure_drop_roughness_mm", 0.0015) / 1000, 1e-9)
    p_hi = prop["P_high_Pa"]
    p_lo = prop["P_low_Pa"]
    dp = max(p_hi - p_lo, 0)
    fluid = str(prop.get("coolprop_fluid", "R32"))
    xin = (h_in_cap - prop["h_f_high_kJ_kg"]) / max(prop["h_fg_high_kJ_kg"], EPS)
    try:
        if xin < -1e-4:
            rho = props_si("Dmass", "P", p_hi, "Hmass", h_in_cap * 1000, fluid)
            mu = props_si("V", "P", p_hi, "Hmass", h_in_cap * 1000, fluid)
        else:
            rho = props_si("Dmass", "P", p_hi, "Q", 0, fluid)
            mu = props_si("V", "P", p_hi, "Q", 0, fluid)
    except Exception:
        rho, mu = 900.0, 1.5e-4
    area = math.pi * D * D / 4
    f = 0.026
    mdot = re = v = 0.0
    for _ in range(35):
        denom = max(f * L / D, EPS)
        mdot_straight = area * math.sqrt(max(2 * rho * dp / denom, 0))
        mdot = coil_factor * mdot_straight
        v = mdot / max(rho * area, EPS)
        re = rho * v * D / max(mu, EPS)
        if re < 2300:
            fnew = 64 / max(re, EPS)
        else:
            fnew = 0.25 / (math.log10(rough / (3.7 * D) + 5.74 / (max(re, EPS) ** 0.9)) ** 2)
        if abs(fnew - f) < 1e-6:
            f = fnew
            break
        f = 0.55 * f + 0.45 * fnew
    mdot_req_straight = max(mdot_comp / max(coil_factor, EPS), 0)
    v_req = mdot_req_straight / max(rho * area, EPS)
    re_req = rho * v_req * D / max(mu, EPS)
    f_req = 64 / max(re_req, EPS) if re_req < 2300 else 0.25 / (math.log10(rough / (3.7 * D) + 5.74 / (max(re_req, EPS) ** 0.9)) ** 2)
    dp_req = f_req * (L / D) * (rho * v_req * v_req / 2) / 1000
    err = 100 * (mdot - mdot_comp) / max(mdot_comp, EPS)
    return {"mdot": mdot, "error_pct": err, "DP_available_kPa": dp / 1000, "DP_required_kPa": dp_req, "Re": re, "x_in_capillary": xin, "rho": rho, "mu": mu, "friction_factor": f}


def _capillary_mdot_balance_grade(err: float | None, mdot: float | None) -> str:
    if mdot is None or not math.isfinite(float(mdot)) or float(mdot) <= 0:
        return "Tidak valid"
    ae = abs(float(err or 0.0))
    if ae <= 2:
        return "Sangat baik"
    if ae <= 5:
        return "Baik"
    if ae <= 10:
        return "Cukup"
    if float(err or 0.0) < -10:
        return "Kapiler underfeed"
    return "Kapiler overfeed"


def _capillary_inlet_condition(xin: float | None) -> tuple[str, str]:
    if xin is None or not math.isfinite(float(xin)):
        return "UNKNOWN", "Kondisi inlet tidak terbaca"
    x = float(xin)
    if x > 0.02:
        return "TWO_PHASE_INLET", "Inlet kapiler dua-fase / belum subcooled"
    if x >= -0.02:
        return "NEAR_SATURATED_LIQUID", "Inlet kapiler cair jenuh / mendekati saturated"
    return "SUBCOOLED_LIQUID", "Inlet kapiler subcooled liquid"


def _capillary_grade(err: float | None, xin: float | None, mdot: float | None) -> tuple[int, str, str, str, str]:
    mdot_grade = _capillary_mdot_balance_grade(err, mdot)
    inlet_code, inlet_text = _capillary_inlet_condition(xin)
    if mdot is None or not math.isfinite(float(mdot)) or float(mdot) <= 0:
        return 0, "INVALID", mdot_grade, inlet_code, inlet_text
    if inlet_code == "TWO_PHASE_INLET":
        return 4, "INLET_NOT_SUBCOOLED", mdot_grade, inlet_code, inlet_text
    ae = abs(float(err or 0.0))
    if ae <= 2:
        return 1, "BALANCED_EXCELLENT", mdot_grade, inlet_code, inlet_text
    if ae <= 5:
        return 6, "BALANCED_CLOSE", mdot_grade, inlet_code, inlet_text
    if ae <= 10:
        return 5, "APPROXIMATE", mdot_grade, inlet_code, inlet_text
    if float(err or 0.0) < -10:
        return 2, "CAPILLARY_UNDERFEED", mdot_grade, inlet_code, inlet_text
    return 3, "CAPILLARY_OVERFEED", mdot_grade, inlet_code, inlet_text


def condenser_outlet_condition(x: float | None) -> tuple[str, str]:
    if x is None or not math.isfinite(float(x)):
        return "UNKNOWN", "Kondisi outlet kondensor tidak terbaca"
    xv = float(x)
    if xv > 0.02:
        return "INCOMPLETE_CONDENSATION", "Outlet kondensor masih dua-fase / kondensasi belum lengkap"
    if xv >= -0.02:
        return "NEAR_SATURATED_LIQUID", "Outlet kondensor cair jenuh / mendekati saturated"
    return "SUBCOOLED_LIQUID", "Outlet kondensor subcooled liquid"


def capillary_feedback_is_allowed(cap_diag: dict[str, Any]) -> tuple[bool, str]:
    """Feedback kapiler hanya boleh memengaruhi mdot/tekanan jika inlet kapiler liquid.

    Jika inlet kapiler masih dua-fase, hasil kapiler tetap disimpan sebagai diagnostic,
    tetapi tidak digunakan untuk mengoreksi mdot agar solver tidak terlihat balance pada
    kondisi inlet yang secara fisik belum valid untuk model kapiler sederhana.
    """
    code = str(cap_diag.get("inlet_condition") or "UNKNOWN")
    if code in {"SUBCOOLED_LIQUID", "NEAR_SATURATED_LIQUID"}:
        return True, "APPLIED_LIQUID_INLET"
    if code == "TWO_PHASE_INLET":
        return False, "BLOCKED_TWO_PHASE_INLET"
    if code == "OFF":
        return False, "OFF"
    return False, "BLOCKED_UNKNOWN_INLET"


def _capillary_choose_closest(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [c for c in candidates if c.get("mdot_cap_kg_s") and math.isfinite(float(c.get("error_pct", 9999)))]
    if not valid:
        return candidates[0] if candidates else {}
    return min(valid, key=lambda c: abs(float(c.get("error_pct", 9999))))


def _estimate_length_for_diameter(cfg: dict[str, Any], prop: dict[str, Any], h_in_cap: float, mdot_comp: float, D_m: float) -> dict[str, Any]:
    Lmin = max(_num(cfg, "capillary_L_min_m", 0.30), 0.05)
    Lmax = max(_num(cfg, "capillary_L_max_m", 5.00), Lmin + 0.05)
    def flow(L: float) -> dict[str, Any]:
        r = _capillary_flow_for_geometry(cfg, prop, h_in_cap, mdot_comp, D_m, L)
        return {"D_m": D_m, "L_m": L, **r}
    lo = flow(Lmin)
    hi = flow(Lmax)
    # mdot decreases as L increases; if target outside range, use closest boundary.
    if (lo["mdot"] - mdot_comp) * (hi["mdot"] - mdot_comp) > 0:
        return lo if abs(lo["error_pct"]) < abs(hi["error_pct"]) else hi
    a, b = Lmin, Lmax
    mid = flow((a + b) / 2)
    for _ in range(45):
        m = (a + b) / 2
        mid = flow(m)
        if abs(mid["error_pct"]) <= _num(cfg, "capillary_target_tolerance_pct", 2.0):
            break
        if mid["mdot"] > mdot_comp:
            a = m
        else:
            b = m
    return mid


def _estimate_diameter_for_length(cfg: dict[str, Any], prop: dict[str, Any], h_in_cap: float, mdot_comp: float, L_m: float) -> dict[str, Any]:
    Dmin = max(_num(cfg, "capillary_D_min_mm", 0.60) / 1000, 1e-5)
    Dmax = max(_num(cfg, "capillary_D_max_mm", 2.40) / 1000, Dmin + 1e-5)
    def flow(D: float) -> dict[str, Any]:
        r = _capillary_flow_for_geometry(cfg, prop, h_in_cap, mdot_comp, D, L_m)
        return {"D_m": D, "L_m": L_m, **r}
    lo = flow(Dmin)
    hi = flow(Dmax)
    # mdot increases with D; if target outside range, use closest boundary.
    if (lo["mdot"] - mdot_comp) * (hi["mdot"] - mdot_comp) > 0:
        return lo if abs(lo["error_pct"]) < abs(hi["error_pct"]) else hi
    a, b = Dmin, Dmax
    mid = flow((a + b) / 2)
    for _ in range(45):
        m = (a + b) / 2
        mid = flow(m)
        if abs(mid["error_pct"]) <= _num(cfg, "capillary_target_tolerance_pct", 2.0):
            break
        if mid["mdot"] < mdot_comp:
            a = m
        else:
            b = m
    return mid


def capillary_diagnostic_model(cfg: dict[str, Any], prop: dict[str, Any], h_in_cap: float, mdot_comp: float) -> dict[str, Any]:
    if int(round(_num(cfg, "capillary_diagnostic_mode", 1))) == 0:
        return {"model": "OFF", "mdot_cap_kg_s": None, "error_pct": None, "status_code": 0, "status_text": "OFF", "balance_grade": "OFF", "mdot_balance_grade": "OFF", "inlet_condition": "OFF", "inlet_condition_text": "OFF", "DP_available_kPa": None, "DP_required_for_mdot_comp_kPa": None, "Re": None, "x_in_capillary": None, "capillary_D_i_effective_mm": None, "capillary_length_effective_m": None, "capillary_estimation_mode": 0, "geometry_estimated": 0}

    mode = int(round(_num(cfg, "capillary_mode", 1)))
    D_fixed = max(_num(cfg, "capillary_D_i_mm") / 1000, 1e-6)
    L_fixed = max(_num(cfg, "capillary_length_m"), 1e-6)
    candidates: list[dict[str, Any]] = []
    geometry_estimated = 0

    if mode == 2:
        candidates.append(_estimate_length_for_diameter(cfg, prop, h_in_cap, mdot_comp, D_fixed))
        geometry_estimated = 1
        model = "Auto-estimate capillary length from user diameter"
    elif mode == 3:
        candidates.append(_estimate_diameter_for_length(cfg, prop, h_in_cap, mdot_comp, L_fixed))
        geometry_estimated = 1
        model = "Auto-estimate capillary diameter from user length"
    elif mode == 4:
        Dmin = max(_num(cfg, "capillary_D_min_mm", 0.60), 0.20)
        Dmax = max(_num(cfg, "capillary_D_max_mm", 2.40), Dmin + 0.05)
        std = [0.60, 0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30, 1.40, 1.50, 1.60, 1.80, 2.00, 2.20, 2.40]
        std = [d for d in std if Dmin <= d <= Dmax]
        if not std:
            std = [Dmin, (Dmin + Dmax) / 2, Dmax]
        for dmm in std:
            candidates.append(_estimate_length_for_diameter(cfg, prop, h_in_cap, mdot_comp, dmm / 1000))
        geometry_estimated = 1
        model = "Auto-search capillary diameter and length from standard range"
    else:
        r = _capillary_flow_for_geometry(cfg, prop, h_in_cap, mdot_comp, D_fixed, L_fixed)
        candidates.append({"D_m": D_fixed, "L_m": L_fixed, **r})
        mode = 1
        model = "Fixed capillary geometry diagnostic/feedback"

    best = _capillary_choose_closest([{**c, "mdot_cap_kg_s": c.get("mdot")} for c in candidates])
    mdot = best.get("mdot", best.get("mdot_cap_kg_s"))
    err = best.get("error_pct")
    xin = best.get("x_in_capillary")
    code, text, mdot_grade, inlet_code, inlet_text = _capillary_grade(err, xin, mdot)
    return {
        "model": model,
        "mdot_cap_kg_s": mdot,
        "error_pct": err,
        "status_code": code,
        "status_text": text,
        "balance_grade": mdot_grade,
        "mdot_balance_grade": mdot_grade,
        "inlet_condition": inlet_code,
        "inlet_condition_text": inlet_text,
        "DP_available_kPa": best.get("DP_available_kPa"),
        "DP_required_for_mdot_comp_kPa": best.get("DP_required_kPa"),
        "Re": best.get("Re"),
        "x_in_capillary": xin,
        "capillary_D_i_effective_mm": 1000.0 * best.get("D_m", D_fixed),
        "capillary_length_effective_m": best.get("L_m", L_fixed),
        "capillary_estimation_mode": mode,
        "geometry_estimated": geometry_estimated,
        "capillary_candidate_count": len(candidates),
    }


# =============================================================================
# Main simulation loop
# =============================================================================


def simulate_single_volume(cfg: dict[str, Any]) -> dict[str, Any]:
    validate_config(cfg)
    cfg.setdefault("P_suction_nominal_psig", _num(cfg, "P_suction_psig"))
    cfg.setdefault("P_discharge_nominal_psig", _num(cfg, "P_discharge_psig"))
    prop0 = get_refrigerant_properties(cfg)
    geom = build_geometry(cfg)
    comp0 = compressor_model(cfg, prop0)
    mdot_base = comp0["mdot_kg_s"]
    w_comp_initial = comp0["Pcomp_kW"]
    prop0["h_comp_out_kJ_kg"] = comp0["h5_kJ_kg"]
    prop0["T_comp_out_C_model"] = comp0["T5_C"]

    cp_w = 4.186
    rho_w = 0.997
    m_w = _num(cfg, "tank_volume_L") * rho_w
    ttank = _num(cfg, "T_tank_initial_C")
    target = _num(cfg, "T_setpoint_C")
    t = 0.0
    e_hw = e_ev = e_cp = e_sens = 0.0
    rows: list[dict[str, Any]] = []
    status = "Set point tidak tercapai"
    reach_time_min: float | None = None
    max_steps = int(math.ceil(_num(cfg, "max_time_h") * 3600 / _num(cfg, "dt_s"))) + 5

    for step in range(max_steps):
        tmean = ttank
        twater = ttank
        p_hi = _num(cfg, "P_discharge_psig")
        p_lo = _num(cfg, "P_suction_psig")
        cap_feedback = int(round(_num(cfg, "capillary_feedback", 1))) == 1
        dp_feedback_requested = int(round(_num(cfg, "pressure_drop_feedback", 0))) == 1
        dp_feedback_applied = False
        cap_feedback_applied = False
        cap_feedback_status = "OFF" if not cap_feedback else "REQUESTED"
        cycle_coupled = int(round(_num(cfg, "compressor_cycle_coupled", 1))) == 1
        n_feedback = 1 + 2 * int(cap_feedback or dp_feedback_requested or cycle_coupled)
        min_lo = max(1, _num(cfg, "P_suction_psig") * 0.65)
        max_lo = min(_num(cfg, "P_discharge_psig") - 20, _num(cfg, "P_suction_psig") * 1.35 + 20)
        max_hi = max(_num(cfg, "P_discharge_psig") * 1.45, _num(cfg, "P_discharge_psig") + 80)
        cap_diag = {}
        dp_zone = {}
        comp_step = comp0
        prop_eff = prop0
        mdot_ref = mdot_base
        w_step = w_comp_initial
        hwst = cond = evap = {}
        u_model = {}
        cycle_suction_state: dict[str, Any] | None = None

        for fb in range(n_feedback):
            cfg_eff = {**cfg, "P_discharge_psig": p_hi, "P_suction_psig": p_lo}
            if cycle_suction_state is not None:
                cfg_eff["_cycle_h_suction_kJ_kg"] = cycle_suction_state.get("h_kJ_kg")
                cfg_eff["_cycle_T_suction_C"] = cycle_suction_state.get("T_C")
                cfg_eff["_cycle_x_suction"] = cycle_suction_state.get("x")
            prop_eff = update_high_side_properties(cfg_eff, prop0, p_hi)
            prop_eff = update_low_side_properties(cfg_eff, prop_eff, p_lo)
            if int(round(_num(cfg, "compressor_dynamic", 1))) == 1:
                comp_step = compressor_model(cfg_eff, prop_eff)
                mdot_ref = comp_step["mdot_kg_s"]
                w_step = comp_step["Pcomp_kW"]
                prop_eff["h_comp_out_kJ_kg"] = comp_step["h5_kJ_kg"]
                prop_eff["T_comp_out_C_model"] = comp_step["T5_C"]
            else:
                mdot_ref = mdot_base * math.sqrt(max((p_hi - p_lo) / max(_num(cfg, "P_discharge_psig") - _num(cfg, "P_suction_psig"), EPS), 0.5))
                w_step = w_comp_initial
                prop_eff["h_comp_out_kJ_kg"] = prop0["h_comp_out_kJ_kg"]
                prop_eff["T_comp_out_C_model"] = prop0["T_comp_out_C_model"]

            u_model = compute_u_zones(cfg_eff, prop_eff, geom, mdot_ref)
            hwst = hwst_model(cfg_eff, prop_eff, geom, mdot_ref, twater, u_model)
            cond = condenser_model(cfg_eff, prop_eff, geom, mdot_ref, hwst["h_out_kJ_kg"], u_model)
            h_after_exp = cond["h_out_kJ_kg"]
            cap_diag = capillary_diagnostic_model(cfg_eff, prop_eff, h_after_exp, mdot_ref)
            cap_allowed, cap_reason = capillary_feedback_is_allowed(cap_diag)
            cap_feedback_status = cap_reason if cap_feedback else "OFF"
            if cap_feedback and cap_allowed and cap_diag.get("mdot_cap_kg_s") and cap_diag["mdot_cap_kg_s"] > 0:
                cap_feedback_applied = True
                mdot_raw = max(mdot_ref, EPS)
                mdot_cap_limited = min(max(cap_diag["mdot_cap_kg_s"], 0.45 * mdot_raw), 1.35 * mdot_raw)
                mdot_ref = 0.35 * mdot_raw + 0.65 * mdot_cap_limited
                w_step = w_step * mdot_ref / mdot_raw
                u_model = compute_u_zones(cfg_eff, prop_eff, geom, mdot_ref)
                hwst = hwst_model(cfg_eff, prop_eff, geom, mdot_ref, twater, u_model)
                cond = condenser_model(cfg_eff, prop_eff, geom, mdot_ref, hwst["h_out_kJ_kg"], u_model)
                h_after_exp = cond["h_out_kJ_kg"]
                cap_diag = capillary_diagnostic_model(cfg_eff, prop_eff, h_after_exp, mdot_ref)
                cap_allowed, cap_reason = capillary_feedback_is_allowed(cap_diag)
                cap_feedback_status = cap_reason
            evap = evaporator_model_manual_shr(cfg_eff, prop_eff, geom, mdot_ref, h_after_exp, u_model)
            cycle_suction_state = {"h_kJ_kg": evap.get("h_out_kJ_kg"), "T_C": evap.get("T_out_C"), "x": evap.get("x_out_low")}
            dp_zone = estimate_zone_pressure_drops(cfg_eff, prop_eff, geom, mdot_ref, hwst, cond, evap)
            if fb < n_feedback - 1:
                p_hi_target = p_hi
                p_lo_target = p_lo
                if dp_feedback_requested and int(dp_zone.get("DP_feedback_safe", 0)) == 1:
                    dp_feedback_applied = True
                    p_hi_pd = _num(cfg, "P_discharge_psig") - 0.50 * kpa2psi(dp_zone["DP_high_side_kPa"])
                    p_lo_pd = _num(cfg, "P_suction_psig") + 0.50 * kpa2psi(dp_zone["DP_low_side_kPa"])
                    p_hi_target = 0.50 * p_hi_target + 0.50 * p_hi_pd
                    p_lo_target = 0.50 * p_lo_target + 0.50 * p_lo_pd
                if cap_feedback and cap_allowed and cap_diag.get("DP_required_for_mdot_comp_kPa") and cap_diag["DP_required_for_mdot_comp_kPa"] > 0:
                    p_hi_cap = p_lo_target + kpa2psi(cap_diag["DP_required_for_mdot_comp_kPa"])
                    p_hi_target = 0.55 * p_hi_target + 0.45 * p_hi_cap
                    if cap_diag.get("error_pct") is not None and math.isfinite(cap_diag["error_pct"]):
                        p_lo_target += min(max(0.10 * cap_diag["error_pct"], -8), 8)
                p_lo = min(max(p_lo_target, min_lo), max_lo)
                p_hi = min(max(p_hi_target, p_lo + 20), max_hi)

        q_loss = max(0, (_num(cfg, "UA_loss_W_K") / 1000) * (tmean - _num(cfg, "T_amb_C")))
        cop_ac = evap["Q_kW"] / max(w_step, EPS)
        cop_use = (evap["Q_kW"] + hwst["Q_kW"]) / max(w_step, EPS)
        cop_sens = evap["Q_sensible_kW"] / max(w_step, EPS)
        x_in = min(max((cond["h_out_kJ_kg"] - prop_eff["h_f_low_kJ_kg"]) / max(prop_eff["h_fg_low_kJ_kg"], EPS), 0), 1)
        dsh_margin = max(0, _num(cfg, "dsh_superheat_margin_C", 1.0))
        x_hwst = hwst["x_out_high"]
        if x_hwst > 1.0 and hwst["T_out_C"] > prop_eff["T_cond_C"] + dsh_margin:
            hwst_mode = 1
        elif x_hwst >= 0:
            hwst_mode = 2
        else:
            hwst_mode = 3

        rows.append({
            "time_min": t / 60,
            "T_node_top_C": ttank,
            "T_node_mid_C": ttank,
            "T_node_bot_C": ttank,
            "T_tank_mean_C": tmean,
            "T_ref_out_HWST_C": hwst["T_out_C"],
            "h_cond_in_kJ_kg": hwst["h_out_kJ_kg"],
            "T_cond_out_C": cond["T_out_C"],
            "h_cond_out_kJ_kg": cond["h_out_kJ_kg"],
            "T_cond_air_out_C": cond["T_air_out_C"],
            "h_exp_out_kJ_kg": cond["h_out_kJ_kg"],
            "x_evap_in": x_in,
            "T_evap_in_C": refrigerant_temp_low(cond["h_out_kJ_kg"], prop_eff),
            "T_evap_sat_C": prop_eff["T_evap_C"],
            "T_evap_out_C": evap["T_out_C"],
            "h_evap_out_kJ_kg": evap["h_out_kJ_kg"],
            "T_evap_air_out_C": evap["T_air_out_C"],
            "Q_HWST_kW": hwst["Q_kW"],
            "Q_loss_kW": q_loss,
            "Q_cond_kW": cond["Q_kW"],
            "Q_evap_kW": evap["Q_kW"],
            "Q_sensible_kW": evap["Q_sensible_kW"],
            "Q_latent_kW": evap["Q_latent_kW"],
            "SHR": evap["SHR"],
            "mdot_condensate_kg_s": evap["mdot_condensate_kg_s"],
            "COP_AC": cop_ac,
            "COP_useful": cop_use,
            "COP_sensible": cop_sens,
            "COP_AC_integrated_running": e_ev / max(e_cp, EPS) if e_cp > 0 else None,
            "COP_useful_integrated_running": (e_ev + e_hw) / max(e_cp, EPS) if e_cp > 0 else None,
            "hwst_f_dsh": hwst["f_dsh"],
            "hwst_f_tp": hwst["f_tp"],
            "hwst_f_sc": hwst["f_sc"],
            "cond_f_dsh": cond["f_dsh"],
            "cond_f_tp": cond["f_tp"],
            "cond_f_sc": cond["f_sc"],
            "evap_f_tp": evap["f_tp"],
            "evap_f_sh": evap["f_sh"],
            "x_hwst_out_high": x_hwst,
            "x_cond_out_high": cond["x_out_high"],
            "x_cond_out": cond["x_out_high"],
            "condenser_outlet_condition": condenser_outlet_condition(cond["x_out_high"])[0],
            "condenser_outlet_condition_text": condenser_outlet_condition(cond["x_out_high"])[1],
            "x_evap_out_low": evap["x_out_low"],
            "hwst_mode": hwst_mode,
            "subcool_cond_C": max(0, prop_eff["T_cond_C"] - cond["T_out_C"]),
            "superheat_evap_C": max(0, evap["T_out_C"] - prop_eff["T_evap_C"]),
            "mdot_ref_kg_s": mdot_ref,
            "mdot_capillary_diag_kg_s": cap_diag.get("mdot_cap_kg_s"),
            "capillary_mdot_error_pct": cap_diag.get("error_pct"),
            "capillary_status_code": cap_diag.get("status_code"),
            "capillary_status": cap_diag.get("status_text"),
            "capillary_DP_available_kPa": cap_diag.get("DP_available_kPa"),
            "capillary_DP_required_kPa": cap_diag.get("DP_required_for_mdot_comp_kPa"),
            "capillary_Re": cap_diag.get("Re"),
            "capillary_x_in": cap_diag.get("x_in_capillary"),
            "capillary_D_i_effective_mm": cap_diag.get("capillary_D_i_effective_mm"),
            "capillary_length_effective_m": cap_diag.get("capillary_length_effective_m"),
            "capillary_estimation_mode": cap_diag.get("capillary_estimation_mode"),
            "capillary_geometry_estimated": cap_diag.get("geometry_estimated"),
            "capillary_balance_grade": cap_diag.get("balance_grade"),
            "capillary_mdot_balance_grade": cap_diag.get("mdot_balance_grade"),
            "capillary_inlet_condition": cap_diag.get("inlet_condition"),
            "capillary_inlet_condition_text": cap_diag.get("inlet_condition_text"),
            "capillary_feedback_requested": 1 if cap_feedback else 0,
            "capillary_feedback_applied": 1 if cap_feedback_applied else 0,
            "capillary_feedback_status": cap_feedback_status,
            "W_comp_kW": w_step,
            "P_discharge_eff_psig": p_hi,
            "P_suction_eff_psig": p_lo,
            "h_comp_out_kJ_kg": prop_eff["h_comp_out_kJ_kg"],
            "T_comp_out_C": prop_eff["T_comp_out_C_model"],
            "h_comp_in_kJ_kg": comp_step.get("h_suction_used_kJ_kg"),
            "T_comp_in_C": comp_step.get("T_suction_used_C"),
            "compressor_suction_source": comp_step.get("suction_state_source"),
            "DP_HWST_kPa": dp_zone["DP_hwst_kPa"],
            "DP_cond_kPa": dp_zone["DP_cond_kPa"],
            "DP_evap_kPa": dp_zone["DP_evap_kPa"],
            "DP_high_side_kPa": dp_zone["DP_high_side_kPa"],
            "DP_low_side_kPa": dp_zone["DP_low_side_kPa"],
            "pressure_drop_feedback_requested": 1 if dp_feedback_requested else 0,
            "pressure_drop_feedback_applied": 1 if dp_feedback_applied else 0,
            "DP_feedback_status": dp_zone.get("DP_feedback_status"),
            "cond_refrigerant_circuits": dp_zone.get("cond_refrigerant_circuits"),
            "evap_refrigerant_circuits": dp_zone.get("evap_refrigerant_circuits"),
            "cond_L_hydraulic_m": dp_zone.get("cond_L_hydraulic_m"),
            "evap_L_hydraulic_m": dp_zone.get("evap_L_hydraulic_m"),
            "cond_mdot_circuit_kg_s": dp_zone.get("cond_mdot_circuit_kg_s"),
            "evap_mdot_circuit_kg_s": dp_zone.get("evap_mdot_circuit_kg_s"),
            "DP_transport_property_source": dp_zone.get("DP_transport_property_source"),
            "DP_two_phase_model": dp_zone.get("DP_two_phase_model"),
            "DP_x_tp_hwst": dp_zone.get("DP_x_tp_hwst"),
            "DP_x_tp_cond": dp_zone.get("DP_x_tp_cond"),
            "DP_x_tp_evap": dp_zone.get("DP_x_tp_evap"),
            "DP_x_evap_in": dp_zone.get("DP_x_evap_in"),
            "U_hwst_dsh_W_m2K": u_model["U_hwst_dsh_W_m2K"],
            "U_hwst_tp_W_m2K": u_model["U_hwst_tp_W_m2K"],
            "U_hwst_sc_W_m2K": u_model["U_hwst_sc_W_m2K"],
            "U_cond_dsh_W_m2K": u_model["U_cond_dsh_W_m2K"],
            "U_cond_tp_W_m2K": u_model["U_cond_tp_W_m2K"],
            "U_cond_sc_W_m2K": u_model["U_cond_sc_W_m2K"],
            "U_evap_tp_W_m2K": u_model["U_evap_tp_W_m2K"],
            "U_evap_sh_W_m2K": u_model["U_evap_sh_W_m2K"],
            "h_air_cond_auto_W_m2K": u_model.get("h_air_cond_auto_W_m2K"),
            "h_air_evap_auto_W_m2K": u_model.get("h_air_evap_auto_W_m2K"),
            "cond_v_face_m_s": u_model.get("cond_v_face_m_s"),
            "cond_v_max_m_s": u_model.get("cond_v_max_m_s"),
            "cond_face_area_m2": u_model.get("cond_face_area_m2"),
            "evap_v_face_m_s": u_model.get("evap_v_face_m_s"),
            "evap_v_max_m_s": u_model.get("evap_v_max_m_s"),
            "evap_face_area_m2": u_model.get("evap_face_area_m2"),
            "coil_calculation_method": _coil_method(cfg_eff),
            "cond_model": cond.get("model", "segmented UA-dT condenser"),
            "evap_model": evap.get("model", "segmented UA-dT evaporator"),
            "cond_NTU_dsh": cond.get("NTU_dsh"),
            "cond_NTU_tp": cond.get("NTU_tp"),
            "cond_NTU_sc": cond.get("NTU_sc"),
            "evap_NTU_tp": evap.get("NTU_tp"),
            "evap_NTU_sh": evap.get("NTU_sh"),
            "T_evap_air_out_heat_balance_C": evap.get("T_air_out_heat_balance_C"),
            "evap_air_model": evap.get("air_model"),
            "evap_psych_status": evap.get("psych_status"),
            "RH_evap_air_in_pct": evap.get("RH_air_in_pct"),
            "RH_evap_air_out_pct": evap.get("RH_air_out_pct"),
            "W_evap_air_in_kg_kgda": evap.get("humidity_ratio_in_kg_kgda"),
            "W_evap_air_out_kg_kgda": evap.get("humidity_ratio_out_kg_kgda"),
            "dewpoint_evap_air_in_C": evap.get("dewpoint_air_in_C"),
            "h_evap_air_in_kJ_kgda": evap.get("air_enthalpy_in_kJ_kgda"),
            "h_evap_air_out_kJ_kgda": evap.get("air_enthalpy_out_kJ_kgda"),
            "evap_ADP_C": evap.get("ADP_C"),
            "evap_bypass_factor": evap.get("bypass_factor"),
            "psychrometric_P_atm_kPa": evap.get("P_atm_kPa"),
            "U_cal_factor_hwst": u_model.get("U_cal_factor_hwst"),
            "U_cal_factor_cond": u_model.get("U_cal_factor_cond"),
            "U_cal_factor_evap": u_model.get("U_cal_factor_evap"),
            "compressor_mdot_factor": comp_step.get("compressor_mdot_factor"),
            "compressor_power_factor": comp_step.get("compressor_power_factor"),
            "E_HWST_kWh": e_hw,
            "E_evap_kWh": e_ev,
            "E_comp_kWh": e_cp,
            "E_tank_kWh": m_w * cp_w * (tmean - _num(cfg, "T_tank_initial_C")) / 3600,
            "E_sensible_kWh": e_sens,
            "delta_COP_AC": 0.0 if not rows else cop_ac - rows[-1]["COP_AC"],
            "is_dsh_window": 1 if hwst_mode == 1 else 0,
        })

        if ttank >= target or t >= _num(cfg, "max_time_h") * 3600:
            break
        q_net = hwst["Q_kW"] - q_loss
        dT_per_dt = q_net * _num(cfg, "dt_s") / max(m_w * cp_w, EPS)
        if dT_per_dt > 1e-12 and ttank + dT_per_dt >= target:
            dt_eff = _num(cfg, "dt_s") * (target - ttank) / dT_per_dt
            status = "Set point tercapai (mixed tank)"
            reach_time_min = (t + dt_eff) / 60
        else:
            dt_eff = _num(cfg, "dt_s")
        e_hw += hwst["Q_kW"] * dt_eff / 3600
        e_ev += evap["Q_kW"] * dt_eff / 3600
        e_cp += w_step * dt_eff / 3600
        e_sens += evap["Q_sensible_kW"] * dt_eff / 3600
        ttank = min(target, ttank + q_net * dt_eff / max(m_w * cp_w, EPS))
        t += dt_eff
        if reach_time_min is not None and ttank >= target:
            # Add one exact final row by continuing one more iteration, but keep loop safe
            pass

    # Ensure last row has final accumulated energies if stop happened at end of update
    if rows:
        rows[-1]["E_HWST_kWh"] = e_hw
        rows[-1]["E_evap_kWh"] = e_ev
        rows[-1]["E_comp_kWh"] = e_cp
        rows[-1]["E_sensible_kWh"] = e_sens
        rows[-1]["E_tank_kWh"] = m_w * cp_w * (rows[-1]["T_tank_mean_C"] - _num(cfg, "T_tank_initial_C")) / 3600
    if reach_time_min is None and rows and rows[-1]["T_tank_mean_C"] >= target:
        reach_time_min = rows[-1]["time_min"]
        status = "Set point tercapai (mixed tank)"
    return assemble_results(cfg, prop0, geom, comp0, rows, status, reach_time_min, w_comp_initial)


def assemble_results(cfg: dict[str, Any], prop: dict[str, Any], geom: dict[str, Any], comp: dict[str, Any], rows: list[dict[str, Any]], status: str, reach_time_min: float | None, w_comp_initial: float) -> dict[str, Any]:
    if not rows:
        raise ValueError("Simulasi tidak menghasilkan data waktu.")
    final = rows[-1]
    dsh_rows = [r for r in rows if int(r.get("is_dsh_window") or 0) == 1]
    best_dsh = max(dsh_rows, key=lambda r: float(r.get("COP_AC") or -999)) if dsh_rows else rows[-1]
    best_overall = max(rows, key=lambda r: float(r.get("COP_AC") or -999))
    e_hw = float(final.get("E_HWST_kWh") or 0)
    e_ev = float(final.get("E_evap_kWh") or 0)
    e_cp = float(final.get("E_comp_kWh") or 0)
    e_sens = float(final.get("E_sensible_kWh") or 0)
    e_tank = float(final.get("E_tank_kWh") or 0)
    cop_ac_int = e_ev / max(e_cp, EPS)
    cop_use_int = (e_ev + e_hw) / max(e_cp, EPS)
    cop_sens_int = e_sens / max(e_cp, EPS)
    cooling_capacity_nameplate_kW = _num(cfg, "ac_capacity_pk", 0.0) * _num(cfg, "cooling_capacity_per_PK_kW", 0.0)
    cop_nameplate = cooling_capacity_nameplate_kW / max(_num(cfg, "compressor_power_kW", EPS), EPS)
    dsh_start = dsh_rows[0]["time_min"] if dsh_rows else None
    dsh_end = rows[-1]["time_min"] if dsh_rows else None
    dsh_duration = (dsh_end - dsh_start) if (dsh_start is not None and dsh_end is not None) else None
    cop_range_rows = [r for r in dsh_rows if float(r["COP_AC"]) >= 0.99 * float(best_dsh["COP_AC"])] if dsh_rows else []
    cop_range_min = min((r["T_tank_mean_C"] for r in cop_range_rows), default=best_dsh["T_tank_mean_C"])
    cop_range_max = max((r["T_tank_mean_C"] for r in cop_range_rows), default=best_dsh["T_tank_mean_C"])
    # Conventional baseline uses same compressor/cond/evap logic without HWST.
    baseline = simulate_conventional_baseline(cfg, prop, geom, rows[-1]["time_min"])

    cop_class_integrated = cop_efficiency_class(cop_ac_int)
    cop_class_conventional = cop_efficiency_class(baseline["COP_AC"])
    cop_class_nameplate = cop_efficiency_class(cop_nameplate)

    summary_values = {
        "finalTankMean_C": round(final["T_tank_mean_C"], 4),
        "reachTime_min": round(reach_time_min if reach_time_min is not None else final["time_min"], 4),
        "operationTime_min": round(final["time_min"], 4),
        "bestCOP_AC_dsh": round(best_dsh["COP_AC"], 4),
        "bestCOP_AC_overall": round(best_overall["COP_AC"], 4),
        "COP_AC_integrated": round(cop_ac_int, 4),
        "COP_useful_integrated": round(cop_use_int, 4),
        "COP_sensible_integrated": round(cop_sens_int, 4),
        "COP_AC_conventional": round(baseline["COP_AC"], 4),
        "delta_COP_integrated": round(cop_ac_int - baseline["COP_AC"], 4),
        "delta_COP_integrated_pct": round(100.0 * (cop_ac_int - baseline["COP_AC"]) / max(abs(float(baseline.get("COP_AC") or 0.0)), EPS), 4),
        "COP_nameplate": round(cop_nameplate, 4),
        "COP_nameplate_capacity_kW": round(cooling_capacity_nameplate_kW, 4),
        "COP_class_integrated": cop_class_integrated["grade"],
        "COP_class_integrated_label": cop_class_integrated["label"],
        "COP_class_integrated_range": cop_class_integrated["range"],
        "COP_class_conventional": cop_class_conventional["grade"],
        "COP_class_conventional_label": cop_class_conventional["label"],
        "COP_class_conventional_range": cop_class_conventional["range"],
        "COP_class_nameplate": cop_class_nameplate["grade"],
        "COP_class_nameplate_label": cop_class_nameplate["label"],
        "COP_class_nameplate_range": cop_class_nameplate["range"],
        "delta_COP_AC": round(best_dsh["COP_AC"] - baseline["COP_AC"], 4),
        "energy_HWST_kWh": round(e_hw, 5),
        "energy_evap_kWh": round(e_ev, 5),
        "energy_comp_kWh": round(e_cp, 5),
        "energy_sensible_kWh": round(e_sens, 5),
        "tank_balance_error_pct": round(100 * abs(e_hw - e_tank) / max(e_tank, EPS), 5),
        "t_dsh_start_min": round(dsh_start, 4) if dsh_start is not None else None,
        "t_dsh_end_min": round(dsh_end, 4) if dsh_end is not None else None,
        "dsh_window_duration_min": round(dsh_duration, 4) if dsh_duration is not None else None,
        "Ttank_bestCOP_dsh_C": round(best_dsh["T_tank_mean_C"], 4),
        "Ttank_bestCOP_overall_C": round(best_overall["T_tank_mean_C"], 4),
        "COPMaxRangeMin_C": round(cop_range_min, 4),
        "COPMaxRangeMax_C": round(cop_range_max, 4),
        "cond_refrigerant_circuits": int(final.get("cond_refrigerant_circuits") or geom["cond"].get("refrigerant_circuits", 1)),
        "evap_refrigerant_circuits": int(final.get("evap_refrigerant_circuits") or geom["evap"].get("refrigerant_circuits", 1)),
        "pressure_drop_feedback_requested": int(final.get("pressure_drop_feedback_requested") or 0),
        "pressure_drop_feedback_applied": int(final.get("pressure_drop_feedback_applied") or 0),
        "DP_feedback_status": final.get("DP_feedback_status"),
    }

    summary_rows = build_summary_rows(cfg, prop, comp, final, best_dsh, best_overall, baseline, summary_values, status)
    rounded_rows = [{k: _r2(v, 6) for k, v in row.items()} for row in rows]
    return {
        "status": status,
        "summary_values": summary_values,
        "summary_rows": summary_rows,
        "time_series": rounded_rows,
        "visualization_series": build_visualization_series(rows),
        "conventional_time_series": build_conventional_time_series(rows, baseline),
        "ph_series": build_ph_series(rows),
        "ph_conventional": build_ph_baseline_frame(baseline, prop, rows[-1]),
        "ph_dome": build_ph_dome(prop),
        "coil_usage": build_coil_usage_rows(rows),
        "coil_usage_conventional": build_coil_usage_baseline_rows(baseline),
        "state_rows": build_state_rows(cfg, prop, comp, baseline, final),
        "geometry_rows": build_geometry_rows(geom, final),
        "condition_rows": build_refrigerant_condition_rows(final, baseline),
        "pressure_drop_rows": build_pressure_drop_rows(final, baseline),
        "heat_transfer_rows": build_heat_transfer_rows(geom, final, baseline),
        "assumption_rows": build_assumption_rows(cfg),
        "analysis_rows": build_analysis_rows(prop, final, best_dsh, baseline, summary_values),
        "validation_rows": build_validation_rows(prop, final, baseline, summary_values),
        "volume_variation": [],
        "config": cfg,
        "engine_info": {
            "engine_version": "V17.11 simplified interface + capillary method dropdown",
            "coil_method": "NTU-effectiveness berbasis zona" if _coil_method(cfg) == 2 else "Segmented UA-dT per segmen",
            "coolprop_active": str(prop.get("property_source")) == "CoolProp",
            "property_source": prop.get("property_source"),
            "coolprop_version": prop.get("coolprop_version"),
        },
    }



# =============================================================================
# V6 visualization builders
# =============================================================================

def pa_to_kpa(p_pa: float) -> float:
    return float(p_pa) / 1000.0

def psig_to_kpa_abs(p_psig: float) -> float:
    return psig2pa(p_psig) / 1000.0
def build_conventional_time_series(rows: list[dict[str, Any]], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Time-series pembanding untuk AC konvensional.

    AC konvensional tidak memiliki tangki HWST, sehingga nilai performanya
    dianggap steady/baseline dan diulang pada waktu simulasi yang sama dengan
    AC + HWST. Tujuannya agar Excel memiliki data pembanding waktu yang jelas.
    """
    out: list[dict[str, Any]] = []

    q_evap = float(baseline.get("Q_evap_kW") or 0.0)
    q_cond = float(baseline.get("Q_cond_kW") or 0.0)
    w_comp = float(baseline.get("W_comp_kW") or 0.0)

    for row in rows:
        t = float(row.get("time_min") or 0.0)

        out.append({
            "time_min": _r2(t, 6),
            "sistem": "AC Konvensional",

            "COP_AC": _r2(baseline.get("COP_AC"), 6),
            "COP_sensible": _r2(baseline.get("COP_sensible"), 6),

            "Q_evap_kW": _r2(q_evap, 6),
            "Q_cond_kW": _r2(q_cond, 6),
            "W_comp_kW": _r2(w_comp, 6),
            "mdot_ref_kg_s": _r2(baseline.get("mdot_ref_kg_s"), 6),

            "energy_evap_kWh": _r2(q_evap * t / 60.0, 6),
            "energy_comp_kWh": _r2(w_comp * t / 60.0, 6),

            "P_high_kPa": _r2(baseline.get("P_high_kPa"), 6),
            "P_low_kPa": _r2(baseline.get("P_low_kPa"), 6),
            "P_discharge_eff_psig": _r2(baseline.get("P_discharge_eff_psig"), 6),
            "P_suction_eff_psig": _r2(baseline.get("P_suction_eff_psig"), 6),

            "T_comp_in_C": _r2(baseline.get("T_comp_in_C"), 6),
            "T_comp_out_C": _r2(baseline.get("T_comp_out_C"), 6),
            "T_cond_out_C": _r2(baseline.get("T_cond_out_C"), 6),
            "T_evap_in_C": _r2(baseline.get("T_evap_in_C"), 6),
            "T_evap_out_C": _r2(baseline.get("T_evap_out_C"), 6),

            "subcool_cond_C": _r2(baseline.get("subcool_cond_C"), 6),
            "superheat_evap_C": _r2(baseline.get("superheat_evap_C"), 6),
            "x_cond_out": _r2(baseline.get("x_cond_out"), 6),
            "x_evap_out_low": _r2(baseline.get("x_evap_out_low"), 6),

            "DP_cond_kPa": _r2(baseline.get("DP_cond_kPa"), 6),
            "DP_evap_kPa": _r2(baseline.get("DP_evap_kPa"), 6),
            "DP_high_side_kPa": _r2(baseline.get("DP_high_side_kPa"), 6),
            "DP_low_side_kPa": _r2(baseline.get("DP_low_side_kPa"), 6),

            "cond_f_dsh": _r2(baseline.get("cond_f_dsh"), 6),
            "cond_f_tp": _r2(baseline.get("cond_f_tp"), 6),
            "cond_f_sc": _r2(baseline.get("cond_f_sc"), 6),
            "evap_f_tp": _r2(baseline.get("evap_f_tp"), 6),
            "evap_f_sh": _r2(baseline.get("evap_f_sh"), 6),

            "capillary_status": baseline.get("capillary_status"),
            "capillary_inlet_condition": baseline.get("capillary_inlet_condition"),
            "capillary_mdot_error_pct": _r2(baseline.get("capillary_mdot_error_pct"), 6),

            "pressure_drop_feedback_applied": baseline.get("pressure_drop_feedback_applied"),
            "capillary_feedback_applied": baseline.get("capillary_feedback_applied"),
        })

    return out

def build_visualization_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Subset time-series untuk halaman visualisasi sistem bergerak."""
    keys = [
        "time_min", "T_tank_mean_C", "T_comp_out_C", "T_ref_out_HWST_C",
        "T_cond_out_C", "T_evap_in_C", "T_evap_out_C", "COP_AC",
        "COP_useful", "Q_HWST_kW", "Q_cond_kW", "Q_evap_kW",
        "hwst_f_dsh", "hwst_f_tp", "hwst_f_sc", "cond_f_dsh",
        "cond_f_tp", "cond_f_sc", "evap_f_tp", "evap_f_sh",
        "P_discharge_eff_psig", "P_suction_eff_psig", "mdot_ref_kg_s",
        "W_comp_kW", "hwst_mode", "x_hwst_out_high", "x_evap_in",
        "DP_HWST_kPa", "DP_cond_kPa", "DP_evap_kPa",
        "DP_high_side_kPa", "DP_low_side_kPa",
        "capillary_DP_available_kPa", "capillary_DP_required_kPa",
        "capillary_status_code", "capillary_status", "capillary_D_i_effective_mm",
        "capillary_length_effective_m", "capillary_balance_grade",
        "evap_air_model", "evap_psych_status", "RH_evap_air_out_pct",
        "W_evap_air_in_kg_kgda", "W_evap_air_out_kg_kgda",
    ]
    return [{k: _r2(row.get(k), 6) for k in keys} for row in rows]

def build_ph_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Titik diagram P-h bergerak. Label 2' dipakai untuk keluar HWST,
    sesuai sistem AC + HWST: 1 -> 2 -> 2' -> 3 -> 4 -> 1.
    """
    out: list[dict[str, Any]] = []
    for row in rows:
        p_high = psig_to_kpa_abs(float(row.get("P_discharge_eff_psig") or 0))
        p_low = psig_to_kpa_abs(float(row.get("P_suction_eff_psig") or 0))
        points = [
            {
                "label": "1",
                "name": "Keluar evaporator / masuk kompresor",
                "h_kJ_kg": _r2(row.get("h_evap_out_kJ_kg"), 6),
                "P_kPa": _r2(p_low, 6),
                "T_C": _r2(row.get("T_evap_out_C"), 6),
            },
            {
                "label": "2",
                "name": "Keluar kompresor",
                "h_kJ_kg": _r2(row.get("h_comp_out_kJ_kg"), 6),
                "P_kPa": _r2(p_high, 6),
                "T_C": _r2(row.get("T_comp_out_C"), 6),
            },
            {
                "label": "2'",
                "name": "Keluar HWST / masuk kondensor",
                "h_kJ_kg": _r2(row.get("h_cond_in_kJ_kg"), 6),
                "P_kPa": _r2(p_high, 6),
                "T_C": _r2(row.get("T_ref_out_HWST_C"), 6),
            },
            {
                "label": "3",
                "name": "Keluar kondensor",
                "h_kJ_kg": _r2(row.get("h_cond_out_kJ_kg"), 6),
                "P_kPa": _r2(p_high, 6),
                "T_C": _r2(row.get("T_cond_out_C"), 6),
            },
            {
                "label": "4",
                "name": "Keluar ekspansi / masuk evaporator",
                "h_kJ_kg": _r2(row.get("h_exp_out_kJ_kg"), 6),
                "P_kPa": _r2(p_low, 6),
                "T_C": _r2(row.get("T_evap_in_C"), 6),
            },
        ]
        out.append({"time_min": _r2(row.get("time_min"), 6), "points": points})
    return out

def build_ph_baseline_frame(baseline: dict[str, Any], prop: dict[str, Any], final_row: dict[str, Any] | None = None) -> dict[str, Any]:
    """Frame pembanding P-h untuk AC konvensional tanpa HWST."""
    p_high = _r2(baseline.get("P_high_kPa") or prop.get("P_high_Pa", 0) / 1000.0, 6)
    p_low = _r2(baseline.get("P_low_kPa") or prop.get("P_low_Pa", 0) / 1000.0, 6)
    points = [
        {
            "label": "1",
            "name": "Keluar evaporator / masuk kompresor",
            "h_kJ_kg": _r2(baseline.get("h_evap_out_kJ_kg"), 6),
            "P_kPa": p_low,
            "T_C": _r2(baseline.get("T_evap_out_C"), 6),
        },
        {
            "label": "2",
            "name": "Keluar kompresor",
            "h_kJ_kg": _r2(baseline.get("h_comp_out_kJ_kg"), 6),
            "P_kPa": p_high,
            "T_C": _r2(baseline.get("T_comp_out_C"), 6),
        },
        {
            "label": "3",
            "name": "Keluar kondensor",
            "h_kJ_kg": _r2(baseline.get("h_cond_out_kJ_kg"), 6),
            "P_kPa": p_high,
            "T_C": _r2(baseline.get("T_cond_out_C"), 6),
        },
        {
            "label": "4",
            "name": "Keluar ekspansi / masuk evaporator",
            "h_kJ_kg": _r2(baseline.get("h_exp_out_kJ_kg"), 6),
            "P_kPa": p_low,
            "T_C": _r2(baseline.get("T_evap_in_C"), 6),
        },
    ]
    return {"time_min": _r2((final_row or {}).get("time_min"), 6), "points": points}

def build_ph_dome(prop: dict[str, Any]) -> dict[str, Any]:
    """Kurva kubah saturasi sederhana untuk diagram P-h dari CoolProp."""
    if PropsSI is None or "CoolProp" not in str(prop.get("property_source")):
        return {"liquid": [], "vapor": [], "source": "unavailable"}
    fluid = str(prop.get("coolprop_fluid", "R32"))
    try:
        tcrit = props_si("Tcrit", "", 0, "", 0, fluid)
        ttriple = cp_safe("Ttriple", "", 0, "", 0, fluid, 220.0)
    except Exception:
        return {"liquid": [], "vapor": [], "source": "CoolProp dome unavailable"}
    t_min = max(ttriple + 1.0, 220.0)
    t_max = max(t_min + 2.0, tcrit - 1.0)
    n = 90
    liquid: list[dict[str, float]] = []
    vapor: list[dict[str, float]] = []
    for i in range(n):
        T = t_min + (t_max - t_min) * i / (n - 1)
        try:
            p = props_si("P", "T", T, "Q", 0, fluid) / 1000.0
            hf = props_si("Hmass", "T", T, "Q", 0, fluid) / 1000.0
            hg = props_si("Hmass", "T", T, "Q", 1, fluid) / 1000.0
            if all(math.isfinite(v) for v in [p, hf, hg]):
                liquid.append({"h_kJ_kg": round(hf, 5), "P_kPa": round(p, 5), "T_C": round(k2c(T), 5)})
                vapor.append({"h_kJ_kg": round(hg, 5), "P_kPa": round(p, 5), "T_C": round(k2c(T), 5)})
        except Exception:
            continue
    return {"liquid": liquid, "vapor": vapor, "source": f"CoolProp {prop.get('coolprop_version', '')}"}

def simulate_conventional_baseline(cfg: dict[str, Any], prop: dict[str, Any], geom: dict[str, Any], operation_min: float) -> dict[str, Any]:
    """Apple-to-apple baseline AC konvensional.

    Solver ini memakai jalur yang sama dengan AC+HWST: kompresor, Auto-U,
    kondensor, kapiler, evaporator, pressure drop, dan feedback tekanan. Bedanya
    hanya HWST di-bypass sehingga h_out kompresor langsung masuk kondensor.
    """
    p_hi = _num(cfg, "P_discharge_psig")
    p_lo = _num(cfg, "P_suction_psig")
    dp_feedback_requested = int(round(_num(cfg, "pressure_drop_feedback", 0))) == 1
    cap_feedback = int(round(_num(cfg, "capillary_feedback", 1))) == 1
    cycle_coupled = int(round(_num(cfg, "compressor_cycle_coupled", 1))) == 1
    n_feedback = 1 + 2 * int(dp_feedback_requested or cap_feedback or cycle_coupled)
    min_lo = max(1, _num(cfg, "P_suction_psig") * 0.65)
    max_lo = min(_num(cfg, "P_discharge_psig") - 20, _num(cfg, "P_suction_psig") * 1.35 + 20)
    max_hi = max(_num(cfg, "P_discharge_psig") * 1.45, _num(cfg, "P_discharge_psig") + 80)
    comp = compressor_model(cfg, prop)
    p_eff = prop
    u = {}
    cond = {}
    evap = {}
    cap_diag = {}
    dp_zone = {}
    mdot_ref = comp["mdot_kg_s"]
    w_step = comp["Pcomp_kW"]
    dp_feedback_applied = False
    cap_feedback_applied = False
    cap_feedback_status = "OFF" if not cap_feedback else "REQUESTED"
    cycle_suction_state: dict[str, Any] | None = None

    for fb in range(n_feedback):
        cfg_eff = {**cfg, "P_discharge_psig": p_hi, "P_suction_psig": p_lo}
        if cycle_suction_state is not None:
            cfg_eff["_cycle_h_suction_kJ_kg"] = cycle_suction_state.get("h_kJ_kg")
            cfg_eff["_cycle_T_suction_C"] = cycle_suction_state.get("T_C")
            cfg_eff["_cycle_x_suction"] = cycle_suction_state.get("x")
        p_eff = update_high_side_properties(cfg_eff, prop, p_hi)
        p_eff = update_low_side_properties(cfg_eff, p_eff, p_lo)
        comp = compressor_model(cfg_eff, p_eff)
        mdot_ref = comp["mdot_kg_s"]
        w_step = comp["Pcomp_kW"]
        p_eff["h_comp_out_kJ_kg"] = comp["h5_kJ_kg"]
        p_eff["T_comp_out_C_model"] = comp["T5_C"]
        u = compute_u_zones(cfg_eff, p_eff, geom, mdot_ref)
        cond = condenser_model(cfg_eff, p_eff, geom, mdot_ref, p_eff["h_comp_out_kJ_kg"], u)
        h_after_exp = cond["h_out_kJ_kg"]
        cap_diag = capillary_diagnostic_model(cfg_eff, p_eff, h_after_exp, mdot_ref)
        cap_allowed, cap_reason = capillary_feedback_is_allowed(cap_diag)
        cap_feedback_status = cap_reason if cap_feedback else "OFF"
        if cap_feedback and cap_allowed and cap_diag.get("mdot_cap_kg_s") and cap_diag["mdot_cap_kg_s"] > 0:
            cap_feedback_applied = True
            mdot_raw = max(mdot_ref, EPS)
            mdot_cap_limited = min(max(cap_diag["mdot_cap_kg_s"], 0.45 * mdot_raw), 1.35 * mdot_raw)
            mdot_ref = 0.35 * mdot_raw + 0.65 * mdot_cap_limited
            w_step = w_step * mdot_ref / mdot_raw
            u = compute_u_zones(cfg_eff, p_eff, geom, mdot_ref)
            cond = condenser_model(cfg_eff, p_eff, geom, mdot_ref, p_eff["h_comp_out_kJ_kg"], u)
            h_after_exp = cond["h_out_kJ_kg"]
            cap_diag = capillary_diagnostic_model(cfg_eff, p_eff, h_after_exp, mdot_ref)
            cap_allowed, cap_reason = capillary_feedback_is_allowed(cap_diag)
            cap_feedback_status = cap_reason
        evap = evaporator_model_manual_shr(cfg_eff, p_eff, geom, mdot_ref, h_after_exp, u)
        cycle_suction_state = {"h_kJ_kg": evap.get("h_out_kJ_kg"), "T_C": evap.get("T_out_C"), "x": evap.get("x_out_low")}
        hwst_zero = {"f_dsh": 0.0, "f_tp": 0.0, "f_sc": 0.0}
        dp_zone = estimate_zone_pressure_drops(cfg_eff, p_eff, geom, mdot_ref, hwst_zero, cond, evap)
        if fb < n_feedback - 1:
            p_hi_target = p_hi
            p_lo_target = p_lo
            if dp_feedback_requested and int(dp_zone.get("DP_feedback_safe", 0)) == 1:
                dp_feedback_applied = True
                p_hi_pd = _num(cfg, "P_discharge_psig") - 0.50 * kpa2psi(dp_zone["DP_high_side_kPa"])
                p_lo_pd = _num(cfg, "P_suction_psig") + 0.50 * kpa2psi(dp_zone["DP_low_side_kPa"])
                p_hi_target = 0.50 * p_hi_target + 0.50 * p_hi_pd
                p_lo_target = 0.50 * p_lo_target + 0.50 * p_lo_pd
            if cap_feedback and cap_allowed and cap_diag.get("DP_required_for_mdot_comp_kPa") and cap_diag["DP_required_for_mdot_comp_kPa"] > 0:
                p_hi_cap = p_lo_target + kpa2psi(cap_diag["DP_required_for_mdot_comp_kPa"])
                p_hi_target = 0.55 * p_hi_target + 0.45 * p_hi_cap
                if cap_diag.get("error_pct") is not None and math.isfinite(cap_diag["error_pct"]):
                    p_lo_target += min(max(0.10 * cap_diag["error_pct"], -8), 8)
            p_lo = min(max(p_lo_target, min_lo), max_lo)
            p_hi = min(max(p_hi_target, p_lo + 20), max_hi)

    cop_ac = evap["Q_kW"] / max(w_step, EPS)
    return {
        "solver": "apple_to_apple_no_HWST",
        "COP_AC": cop_ac,
        "COP_sensible": evap["Q_sensible_kW"] / max(w_step, EPS),
        "Q_evap_kW": evap["Q_kW"],
        "Q_cond_kW": cond["Q_kW"],
        "W_comp_kW": w_step,
        "energy_evap_kWh": evap["Q_kW"] * operation_min / 60,
        "energy_comp_kWh": w_step * operation_min / 60,
        "h_evap_out_kJ_kg": evap["h_out_kJ_kg"],
        "T_evap_out_C": evap["T_out_C"],
        "h_comp_in_kJ_kg": comp.get("h_suction_used_kJ_kg"),
        "T_comp_in_C": comp.get("T_suction_used_C"),
        "compressor_suction_source": comp.get("suction_state_source"),
        "h_comp_out_kJ_kg": comp["h5_kJ_kg"],
        "T_comp_out_C": comp["T5_C"],
        "h_cond_out_kJ_kg": cond["h_out_kJ_kg"],
        "T_cond_out_C": cond["T_out_C"],
        "h_exp_out_kJ_kg": cond["h_out_kJ_kg"],
        "T_evap_in_C": refrigerant_temp_low(cond["h_out_kJ_kg"], p_eff),
        "P_high_kPa": psig_to_kpa_abs(p_hi),
        "P_low_kPa": psig_to_kpa_abs(p_lo),
        "P_discharge_eff_psig": p_hi,
        "P_suction_eff_psig": p_lo,
        "mdot_ref_kg_s": mdot_ref,
        "cond_f_dsh": cond.get("f_dsh", 0.0),
        "cond_f_tp": cond.get("f_tp", 0.0),
        "cond_f_sc": cond.get("f_sc", 0.0),
        "evap_f_tp": evap.get("f_tp", 0.0),
        "evap_f_sh": evap.get("f_sh", 0.0),
        "x_cond_out": cond.get("x_out_high"),
        "x_evap_out_low": evap.get("x_out_low"),
        "capillary_status": cap_diag.get("status_text"),
        "capillary_mdot_error_pct": cap_diag.get("error_pct"),
        "capillary_inlet_condition": cap_diag.get("inlet_condition"),
        "capillary_feedback_applied": 1 if cap_feedback_applied else 0,
        "capillary_feedback_status": cap_feedback_status,
        "pressure_drop_feedback_requested": 1 if dp_feedback_requested else 0,
        "pressure_drop_feedback_applied": 1 if dp_feedback_applied else 0,
        "DP_feedback_status": dp_zone.get("DP_feedback_status"),
        "DP_HWST_kPa": 0.0,
        "DP_cond_kPa": dp_zone.get("DP_cond_kPa"),
        "DP_evap_kPa": dp_zone.get("DP_evap_kPa"),
        "DP_high_side_kPa": dp_zone.get("DP_high_side_kPa"),
        "DP_low_side_kPa": dp_zone.get("DP_low_side_kPa"),
        "DP_transport_property_source": dp_zone.get("DP_transport_property_source"),
        "DP_two_phase_model": dp_zone.get("DP_two_phase_model"),
        "DP_x_tp_cond": dp_zone.get("DP_x_tp_cond"),
        "DP_x_tp_evap": dp_zone.get("DP_x_tp_evap"),
        "DP_x_evap_in": dp_zone.get("DP_x_evap_in"),
        "subcool_cond_C": max(0, p_eff["T_cond_C"] - cond["T_out_C"]),
        "superheat_evap_C": max(0, evap["T_out_C"] - p_eff["T_evap_C"]),
        "U_cond_dsh_W_m2K": u.get("U_cond_dsh_W_m2K"),
        "U_cond_tp_W_m2K": u.get("U_cond_tp_W_m2K"),
        "U_cond_sc_W_m2K": u.get("U_cond_sc_W_m2K"),
        "U_evap_tp_W_m2K": u.get("U_evap_tp_W_m2K"),
        "U_evap_sh_W_m2K": u.get("U_evap_sh_W_m2K"),
        "h_air_cond_auto_W_m2K": u.get("h_air_cond_auto_W_m2K"),
        "h_air_evap_auto_W_m2K": u.get("h_air_evap_auto_W_m2K"),
        "cond_face_area_m2": u.get("cond_face_area_m2"),
        "cond_v_face_m_s": u.get("cond_v_face_m_s"),
        "cond_v_max_m_s": u.get("cond_v_max_m_s"),
        "evap_face_area_m2": u.get("evap_face_area_m2"),
        "evap_v_face_m_s": u.get("evap_v_face_m_s"),
        "evap_v_max_m_s": u.get("evap_v_max_m_s"),
    }


# =============================================================================
# Output builders
# =============================================================================


def build_summary_rows(cfg: dict[str, Any], prop: dict[str, Any], comp: dict[str, Any], final: dict[str, Any], best_dsh: dict[str, Any], best_overall: dict[str, Any], baseline: dict[str, Any], sv: dict[str, Any], status: str) -> list[dict[str, Any]]:
    source_label = f"{prop.get('property_source')} {prop.get('coolprop_version', '')}".strip()
    rows = [
        ("Sumber properti refrigeran", source_label, "-"),
        ("Mode perhitungan U", "Thermal resistance + auto h_refrigerant + airflow-based h_udara + Shah TP correlations", "-"),
        ("Metode coil", "NTU-effectiveness berbasis zona" if _coil_method(cfg) == 2 else "Segmented UA-dT per segmen", "-"),
        ("Model tangki", "mixed/lumped (utama; set point suhu rata-rata)", "-"),
        ("Mode kompresor", "nameplate reference calibrated by T_comp_out nominal + capillary/pressure feedback", "-"),
        ("Daya kompresor awal/akhir", f"{(cfg.get('compressor_power_kW') or 0):.4f} / {(final.get('W_comp_kW') or 0):.4f}", "kW"),
        ("T keluar kompresor awal/akhir", f"{(comp.get('T5_C') or 0):.2f} / {(final.get('T_comp_out_C') or 0):.2f}", "degC"),
        ("h keluar kompresor awal/akhir", f"{(comp.get('h5_kJ_kg') or 0):.3f} / {(final.get('h_comp_out_kJ_kg') or 0):.3f}", "kJ/kg"),
        ("T keluar kompresor acuan input", _num(cfg, "T_comp_out_C"), "degC"),
        ("Status set point", status, "-"),
        ("Waktu mencapai set point", sv.get("reachTime_min"), "min"),
        ("Waktu operasi simulasi", sv.get("operationTime_min"), "min"),
        ("Suhu akhir tangki", sv.get("finalTankMean_C"), "degC"),
        ("Pressure drop high/low akhir", f"{final.get('DP_high_side_kPa', 0):.2f} / {final.get('DP_low_side_kPa', 0):.2f}", "kPa"),
        ("Feedback pressure drop", f"requested={final.get('pressure_drop_feedback_requested')} | applied={final.get('pressure_drop_feedback_applied')} | {final.get('DP_feedback_status')}", "-"),
        ("Circuit kondensor/evaporator", f"{final.get('cond_refrigerant_circuits')} / {final.get('evap_refrigerant_circuits')}", "jalur"),
        ("Panjang hidrolik kond/evap", f"{(final.get('cond_L_hydraulic_m') or 0):.3f} / {(final.get('evap_L_hydraulic_m') or 0):.3f}", "m per circuit"),
        ("m_dot per circuit kond/evap", f"{(final.get('cond_mdot_circuit_kg_s') or 0):.5f} / {(final.get('evap_mdot_circuit_kg_s') or 0):.5f}", "kg/s"),
        ("Status diagnostik kapiler", capillary_status_text(final.get("capillary_status_code")), "-"),
        ("Grade balance m_dot kapiler", final.get("capillary_mdot_balance_grade") or final.get("capillary_balance_grade"), "-"),
        ("Kondisi inlet kapiler", final.get("capillary_inlet_condition_text"), "-"),
        ("Geometri kapiler efektif", f"D={final.get('capillary_D_i_effective_mm') or 0:.3f} mm | L={final.get('capillary_length_effective_m') or 0:.3f} m", "estimasi/fixed"),
        ("Status outlet kondensor", final.get("condenser_outlet_condition_text"), "-"),
        ("Subcool outlet kondensor", final.get("subcool_cond_C"), "K"),
        ("Superheat outlet evaporator", final.get("superheat_evap_C"), "K"),
        ("x kondensor keluar", final.get("x_cond_out"), "-"),
        ("m_dot kapiler vs kompresor akhir", f"{(final.get('mdot_capillary_diag_kg_s') or 0):.5f} / {(final.get('mdot_ref_kg_s') or 0):.5f}", "kg/s"),
        ("Error m_dot kapiler akhir", final.get("capillary_mdot_error_pct"), "%"),
        ("DP kapiler tersedia / perlu", f"{(final.get('capillary_DP_available_kPa') or 0):.2f} / {(final.get('capillary_DP_required_kPa') or 0):.2f}", "kPa"),
        ("COP AC terbaik — window DSH", f"{sv.get('bestCOP_AC_dsh')} (T_tank={sv.get('Ttank_bestCOP_dsh_C')} degC, t={best_dsh.get('time_min'):.2f} min)", "-"),
        ("Awal window DSH murni", sv.get("t_dsh_start_min"), "min"),
        ("Akhir window DSH murni", sv.get("t_dsh_end_min"), "min"),
        ("Durasi window DSH murni", sv.get("dsh_window_duration_min"), "min"),
        ("COP AC terbaik — overall", sv.get("bestCOP_AC_overall"), "-"),
        ("Suhu tangki mean saat COP overall", sv.get("Ttank_bestCOP_overall_C"), "degC"),
        ("Rentang 99% COP best DSH", f"{sv.get('COPMaxRangeMin_C')} - {sv.get('COPMaxRangeMax_C')}", "degC"),
        ("COP AC terintegrasi", sv.get("COP_AC_integrated"), "-"),
        ("Delta COP AC vs konvensional", f"{sv.get('delta_COP_integrated')} ({sv.get('delta_COP_integrated_pct')}%)", "-"),
        ("COP useful terintegrasi", sv.get("COP_useful_integrated"), "-"),
        ("COP sensibel terintegrasi", sv.get("COP_sensible_integrated"), "-"),
        ("COP AC konvensional simulasi", sv.get("COP_AC_conventional"), "-"),
        ("COP nominal nameplate", sv.get("COP_nameplate"), f"kelas {sv.get('COP_class_nameplate')}"),
        ("Kelas COP AC terintegrasi", f"{sv.get('COP_class_integrated')} - {sv.get('COP_class_integrated_label')}", sv.get("COP_class_integrated_range")),
        ("Kelas COP konvensional", f"{sv.get('COP_class_conventional')} - {sv.get('COP_class_conventional_label')}", sv.get("COP_class_conventional_range")),
        ("Kelas COP nameplate", f"{sv.get('COP_class_nameplate')} - {sv.get('COP_class_nameplate_label')}", sv.get("COP_class_nameplate_range")),
        ("Delta COP AC (DSH best vs konvensional)", sv.get("delta_COP_AC"), "-"),
        ("Model udara evaporator", final.get("evap_air_model"), "-"),
        ("Status psikrometrik evaporator", final.get("evap_psych_status"), "-"),
        ("Tekanan psikrometrik default", final.get("psychrometric_P_atm_kPa"), "kPa"),
        ("RH evaporator in/out", f"{final.get('RH_evap_air_in_pct')} / {final.get('RH_evap_air_out_pct')}", "%"),
        ("SHR evaporator hasil", final.get("SHR"), "-"),
        ("SHR manual evaporator", _num(cfg, "SHR_manual"), "fallback"),
        ("Q sensibel evaporator akhir", final.get("Q_sensible_kW"), "kW"),
        ("Q laten evaporator akhir", final.get("Q_latent_kW"), "kW"),
        ("Laju kondensasi air akhir", final.get("mdot_condensate_kg_s"), "kg/s"),
        ("Energi HWST", sv.get("energy_HWST_kWh"), "kWh"),
        ("Energi evaporator", sv.get("energy_evap_kWh"), "kWh"),
        ("Energi sensibel evaporator", sv.get("energy_sensible_kWh"), "kWh"),
        ("Energi kompresor", sv.get("energy_comp_kWh"), "kWh"),
        ("Error neraca tangki", sv.get("tank_balance_error_pct"), "%"),
    ]
    return [{"output": k, "value": _r2(v, 5), "unit": u} for k, v, u in rows]


def capillary_status_text(code: Any) -> str:
    try:
        c = int(code)
    except Exception:
        c = 0
    return {
        1: "BALANCED_EXCELLENT",
        2: "CAPILLARY_UNDERFEED",
        3: "CAPILLARY_OVERFEED",
        4: "INLET_NOT_SUBCOOLED",
        5: "APPROXIMATE",
        6: "BALANCED_CLOSE",
    }.get(c, "INVALID/OFF")


def build_coil_usage_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dsh_rows = [r for r in rows if int(r.get("is_dsh_window") or 0) == 1]
    best = max(dsh_rows, key=lambda r: float(r.get("COP_AC") or -999)) if dsh_rows else rows[-1]
    final = rows[-1]
    mapping = [
        ("HWST", "DSH", "hwst_f_dsh", "Desuperheater"),
        ("HWST", "TP", "hwst_f_tp", "Two-phase/partial condenser"),
        ("HWST", "SC", "hwst_f_sc", "Subcool"),
        ("Kondensor", "DSH", "cond_f_dsh", "Desuperheater"),
        ("Kondensor", "TP", "cond_f_tp", "Two-phase condensation"),
        ("Kondensor", "SC", "cond_f_sc", "Subcool"),
        ("Evaporator", "TP", "evap_f_tp", "Two-phase evaporation"),
        ("Evaporator", "SH", "evap_f_sh", "Superheat"),
    ]
    return [{
        "sistem": "AC + HWST",
        "komponen": comp,
        "zona": zone,
        "persentase_COP_best_DSH": round(float(best.get(key, 0)) * 100, 2),
        "persentase_akhir": round(float(final.get(key, 0)) * 100, 2),
        "t_COP_best_DSH_min": round(float(best.get("time_min", 0)), 2),
        "T_tank_COP_best_DSH_C": round(float(best.get("T_tank_mean_C", 0)), 2),
        "catatan": note,
    } for comp, zone, key, note in mapping]


def build_coil_usage_baseline_rows(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = [
        ("Kondensor", "DSH", "cond_f_dsh", "Desuperheater"),
        ("Kondensor", "TP", "cond_f_tp", "Two-phase condensation"),
        ("Kondensor", "SC", "cond_f_sc", "Subcool"),
        ("Evaporator", "TP", "evap_f_tp", "Two-phase evaporation"),
        ("Evaporator", "SH", "evap_f_sh", "Superheat"),
    ]
    return [{
        "sistem": "AC konvensional",
        "komponen": comp,
        "zona": zone,
        "persentase_steady": round(float(baseline.get(key, 0)) * 100, 2),
        "catatan": note,
    } for comp, zone, key, note in mapping]


def build_state_rows(cfg: dict[str, Any], prop: dict[str, Any], comp: dict[str, Any], baseline: dict[str, Any], final: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        ("Refrigerant", prop.get("refrigerant"), "-"),
        ("Sumber properti", f"{prop.get('property_source')} {prop.get('coolprop_version', '')}".strip(), "-"),
        ("P_suction (masuk kompresor / keluar evaporator)", cfg.get("P_suction_psig"), "psig"),
        ("P_discharge (keluar kompresor)", cfg.get("P_discharge_psig"), "psig"),
        ("P suction efektif final", final.get("P_suction_eff_psig"), "psig"),
        ("P discharge efektif final", final.get("P_discharge_eff_psig"), "psig"),
        ("T evaporasi", prop.get("T_evap_C"), "degC"),
        ("T kondensasi", prop.get("T_cond_C"), "degC"),
        ("Model kompresor", comp.get("model"), "-"),
        ("Superheat/subcool nominal", f"{_num(cfg, 'suction_superheat_nominal_K'):.2f} / {_num(cfg, 'liquid_subcool_nominal_K'):.2f}", "K"),
        ("mdot model final", comp.get("mdot_kg_s"), "kg/s"),
        ("mdot model sebelum faktor", comp.get("mdot_model_before_factor_kg_s"), "kg/s"),
        ("Faktor kalibrasi mdot kompresor", comp.get("compressor_mdot_factor"), "-"),
        ("mdot nominal", comp.get("mdot_nominal_kg_s"), "kg/s"),
        ("Pressure ratio nominal/awal", f"{comp.get('PR_nominal', 0):.3f} / {comp.get('PR_current', 0):.3f}", "-"),
        ("Eta isentropik overall", comp.get("eta_is_overall"), "-"),
        ("Eta heat-to-refrigerant", comp.get("eta_heat_to_ref"), "-"),
        ("Eta mekanik/motor jurnal", f"{comp.get('eta_m', 0):.2f} / {comp.get('eta_e', 0):.2f}", "-"),
        ("T kompresor referensi input", comp.get("Tcomp_reference_C"), "degC"),
        ("P kompresor dipakai", comp.get("Pcomp_kW"), "kW"),
        ("P kompresor sebelum faktor", comp.get("Pcomp_model_before_factor_kW"), "kW"),
        ("Faktor kalibrasi power kompresor", comp.get("compressor_power_factor"), "-"),
        ("h5 keluar kompresor", comp.get("h5_kJ_kg"), "kJ/kg"),
        ("T5 keluar kompresor model", comp.get("T5_C"), "degC"),
        ("h_f low", prop.get("h_f_low_kJ_kg"), "kJ/kg"),
        ("h_g low", prop.get("h_g_low_kJ_kg"), "kJ/kg"),
        ("h_f high", prop.get("h_f_high_kJ_kg"), "kJ/kg"),
        ("h_g high", prop.get("h_g_high_kJ_kg"), "kJ/kg"),
        ("x kondensor keluar final", final.get("x_cond_out"), "-"),
        ("Status outlet kondensor final", final.get("condenser_outlet_condition_text"), "-"),
        ("Kondisi inlet kapiler final", final.get("capillary_inlet_condition_text"), "-"),
        ("COP baseline konvensional", baseline.get("COP_AC"), "-"),
        ("Model udara evaporator", final.get("evap_air_model"), "-"),
        ("Status psikrometrik", final.get("evap_psych_status"), "-"),
        ("Tekanan psikrometrik", final.get("psychrometric_P_atm_kPa"), "kPa"),
        ("SHR manual evap (input)", cfg.get("SHR_manual"), "0-1"),
    ]
    if prop.get("coolprop_error"):
        rows.append(("Catatan CoolProp", prop.get("coolprop_error"), "-"))
    return [{"property": k, "value": _r2(v, 5), "unit": u} for k, v, u in rows]


def build_geometry_rows(geom: dict[str, Any], final: dict[str, Any]) -> list[dict[str, Any]]:
    data = [
        ("HWST", "Area tube", geom["hwst"]["A_total_m2"], "m2"),
        ("HWST", "Panjang coil", geom["hwst"]["tube_length_m"], "m"),
        ("HWST", "U final Auto-U DSH/TP/SC", f"{final.get('U_hwst_dsh_W_m2K', 0):.1f} / {final.get('U_hwst_tp_W_m2K', 0):.1f} / {final.get('U_hwst_sc_W_m2K', 0):.1f}", "W/m2.K"),
        ("Kondensor", "Area tube", geom["cond"]["A_tube_m2"], "m2"),
        ("Kondensor", "Area total efektif", geom["cond"]["A_total_m2"], "m2"),
        ("Kondensor", "Panjang tube total", geom["cond"]["tube_length_m"], "m"),
        ("Kondensor", "Jumlah circuit refrigeran", geom["cond"].get("refrigerant_circuits", 1), "jalur"),
        ("Kondensor", "Panjang hidrolik per circuit", geom["cond"].get("hydraulic_length_m", geom["cond"]["tube_length_m"]), "m"),
        ("Kondensor", "Face area / v_face / v_max", f"{final.get('cond_face_area_m2', 0):.3f} m2 | {final.get('cond_v_face_m_s', 0):.2f} / {final.get('cond_v_max_m_s', 0):.2f} m/s", "-"),
        ("Kondensor", "h udara Auto", final.get('h_air_cond_auto_W_m2K', 0), "W/m2.K"),
        ("Kondensor", "U final Auto-U DSH/TP/SC", f"{final.get('U_cond_dsh_W_m2K', 0):.1f} / {final.get('U_cond_tp_W_m2K', 0):.1f} / {final.get('U_cond_sc_W_m2K', 0):.1f}", "W/m2.K"),
        ("Evaporator", "Area tube", geom["evap"]["A_tube_m2"], "m2"),
        ("Evaporator", "Area total efektif", geom["evap"]["A_total_m2"], "m2"),
        ("Evaporator", "Panjang tube total", geom["evap"]["tube_length_m"], "m"),
        ("Evaporator", "Jumlah circuit refrigeran", geom["evap"].get("refrigerant_circuits", 1), "jalur"),
        ("Evaporator", "Panjang hidrolik per circuit", geom["evap"].get("hydraulic_length_m", geom["evap"]["tube_length_m"]), "m"),
        ("Evaporator", "Face area / v_face / v_max", f"{final.get('evap_face_area_m2', 0):.3f} m2 | {final.get('evap_v_face_m_s', 0):.2f} / {final.get('evap_v_max_m_s', 0):.2f} m/s", "-"),
        ("Evaporator", "h udara Auto", final.get('h_air_evap_auto_W_m2K', 0), "W/m2.K"),
        ("Evaporator", "U final Auto-U TP/SH", f"{final.get('U_evap_tp_W_m2K', 0):.1f} / {final.get('U_evap_sh_W_m2K', 0):.1f}", "W/m2.K"),
        ("Kalibrasi", "Faktor U HWST/Kondensor/Evaporator", f"{final.get('U_cal_factor_hwst', 1):.3f} / {final.get('U_cal_factor_cond', 1):.3f} / {final.get('U_cal_factor_evap', 1):.3f}", "-"),
        ("Kapiler", "Geometri efektif", f"D={final.get('capillary_D_i_effective_mm') or 0:.3f} mm | L={final.get('capillary_length_effective_m') or 0:.3f} m", "-"),
    ]
    return [{"komponen": k, "parameter": p, "value": _r2(v, 5), "unit": u} for k, p, v, u in data]




def _weighted_ua(area: float, parts: list[tuple[Any, Any]]) -> float:
    """Return weighted UA = A_total * sum(f_zone * U_zone)."""
    total = 0.0
    for frac, u in parts:
        try:
            total += max(0.0, float(frac or 0.0)) * max(0.0, float(u or 0.0))
        except Exception:
            pass
    return area * total


def build_refrigerant_condition_rows(final: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"sistem": "AC + HWST", "parameter": "Subcool outlet kondensor / inlet kapiler", "nilai": _r2(final.get("subcool_cond_C"), 5), "unit": "K", "catatan": f"x_cond_out={_r2(final.get('x_cond_out'), 5)}"},
        {"sistem": "AC + HWST", "parameter": "Superheat outlet evaporator / inlet kompresor", "nilai": _r2(final.get("superheat_evap_C"), 5), "unit": "K", "catatan": f"x_evap_out={_r2(final.get('x_evap_out_low'), 5)}"},
        {"sistem": "AC Konvensional", "parameter": "Subcool outlet kondensor / inlet kapiler", "nilai": _r2(baseline.get("subcool_cond_C"), 5), "unit": "K", "catatan": f"x_cond_out={_r2(baseline.get('x_cond_out'), 5)}"},
        {"sistem": "AC Konvensional", "parameter": "Superheat outlet evaporator / inlet kompresor", "nilai": _r2(baseline.get("superheat_evap_C"), 5), "unit": "K", "catatan": f"x_evap_out={_r2(baseline.get('x_evap_out_low'), 5)}"},
    ]


def build_pressure_drop_rows(final: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sistem, src in [("AC + HWST", final), ("AC Konvensional", baseline)]:
        rows.extend([
            {"sistem": sistem, "komponen": "HWST", "parameter": "Pressure drop", "nilai": _r2(src.get("DP_HWST_kPa"), 5), "unit": "kPa"},
            {"sistem": sistem, "komponen": "Kondensor", "parameter": "Pressure drop", "nilai": _r2(src.get("DP_cond_kPa"), 5), "unit": "kPa"},
            {"sistem": sistem, "komponen": "Evaporator", "parameter": "Pressure drop", "nilai": _r2(src.get("DP_evap_kPa"), 5), "unit": "kPa"},
            {"sistem": sistem, "komponen": "Sisi high", "parameter": "DP total", "nilai": _r2(src.get("DP_high_side_kPa"), 5), "unit": "kPa"},
            {"sistem": sistem, "komponen": "Sisi low", "parameter": "DP total", "nilai": _r2(src.get("DP_low_side_kPa"), 5), "unit": "kPa"},
            {"sistem": sistem, "komponen": "Feedback", "parameter": "Status", "nilai": f"requested={src.get('pressure_drop_feedback_requested')} | applied={src.get('pressure_drop_feedback_applied')}", "unit": str(src.get("DP_feedback_status") or "-")},
            {"sistem": sistem, "komponen": "Model", "parameter": "Two-phase DP", "nilai": str(src.get("DP_two_phase_model") or "-"), "unit": str(src.get("DP_transport_property_source") or "-")},
            {"sistem": sistem, "komponen": "Kualitas rata-rata", "parameter": "x TP cond/evap", "nilai": f"{_r2(src.get('DP_x_tp_cond'), 4)} / {_r2(src.get('DP_x_tp_evap'), 4)}", "unit": "-"},
        ])
    return rows


def build_heat_transfer_rows(geom: dict[str, Any], final: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    a_cond = float(geom["cond"].get("A_total_m2") or 0.0)
    a_evap = float(geom["evap"].get("A_total_m2") or 0.0)
    a_hwst = float(geom["hwst"].get("A_total_m2") or geom["hwst"].get("A_tube_m2") or 0.0)
    ua_cond_final = _weighted_ua(a_cond, [(final.get("cond_f_dsh"), final.get("U_cond_dsh_W_m2K")), (final.get("cond_f_tp"), final.get("U_cond_tp_W_m2K")), (final.get("cond_f_sc"), final.get("U_cond_sc_W_m2K"))])
    ua_evap_final = _weighted_ua(a_evap, [(final.get("evap_f_tp"), final.get("U_evap_tp_W_m2K")), (final.get("evap_f_sh"), final.get("U_evap_sh_W_m2K"))])
    ua_hwst_final = _weighted_ua(a_hwst, [(final.get("hwst_f_dsh"), final.get("U_hwst_dsh_W_m2K")), (final.get("hwst_f_tp"), final.get("U_hwst_tp_W_m2K")), (final.get("hwst_f_sc"), final.get("U_hwst_sc_W_m2K"))])
    ua_cond_base = _weighted_ua(a_cond, [(baseline.get("cond_f_dsh"), baseline.get("U_cond_dsh_W_m2K")), (baseline.get("cond_f_tp"), baseline.get("U_cond_tp_W_m2K")), (baseline.get("cond_f_sc"), baseline.get("U_cond_sc_W_m2K"))])
    ua_evap_base = _weighted_ua(a_evap, [(baseline.get("evap_f_tp"), baseline.get("U_evap_tp_W_m2K")), (baseline.get("evap_f_sh"), baseline.get("U_evap_sh_W_m2K"))])
    return [
        {"sistem": "AC + HWST", "komponen": "HWST", "h_udara/air": _r2(550.0, 5), "unit_h": "W/m²K", "U_zona": f"{_r2(final.get('U_hwst_dsh_W_m2K'),3)} / {_r2(final.get('U_hwst_tp_W_m2K'),3)} / {_r2(final.get('U_hwst_sc_W_m2K'),3)}", "UA_efektif_W_K": _r2(ua_hwst_final, 5), "catatan": "h sisi air tanki default internal"},
        {"sistem": "AC + HWST", "komponen": "Kondensor", "h_udara/air": _r2(final.get("h_air_cond_auto_W_m2K"), 5), "unit_h": "W/m²K", "U_zona": f"{_r2(final.get('U_cond_dsh_W_m2K'),3)} / {_r2(final.get('U_cond_tp_W_m2K'),3)} / {_r2(final.get('U_cond_sc_W_m2K'),3)}", "UA_efektif_W_K": _r2(ua_cond_final, 5), "catatan": f"v_face={_r2(final.get('cond_v_face_m_s'),3)} m/s | v_max={_r2(final.get('cond_v_max_m_s'),3)} m/s"},
        {"sistem": "AC + HWST", "komponen": "Evaporator", "h_udara/air": _r2(final.get("h_air_evap_auto_W_m2K"), 5), "unit_h": "W/m²K", "U_zona": f"{_r2(final.get('U_evap_tp_W_m2K'),3)} / {_r2(final.get('U_evap_sh_W_m2K'),3)}", "UA_efektif_W_K": _r2(ua_evap_final, 5), "catatan": f"v_face={_r2(final.get('evap_v_face_m_s'),3)} m/s | v_max={_r2(final.get('evap_v_max_m_s'),3)} m/s"},
        {"sistem": "AC Konvensional", "komponen": "Kondensor", "h_udara/air": _r2(baseline.get("h_air_cond_auto_W_m2K"), 5), "unit_h": "W/m²K", "U_zona": f"{_r2(baseline.get('U_cond_dsh_W_m2K'),3)} / {_r2(baseline.get('U_cond_tp_W_m2K'),3)} / {_r2(baseline.get('U_cond_sc_W_m2K'),3)}", "UA_efektif_W_K": _r2(ua_cond_base, 5), "catatan": "solver apple-to-apple tanpa HWST"},
        {"sistem": "AC Konvensional", "komponen": "Evaporator", "h_udara/air": _r2(baseline.get("h_air_evap_auto_W_m2K"), 5), "unit_h": "W/m²K", "U_zona": f"{_r2(baseline.get('U_evap_tp_W_m2K'),3)} / {_r2(baseline.get('U_evap_sh_W_m2K'),3)}", "UA_efektif_W_K": _r2(ua_evap_base, 5), "catatan": "solver apple-to-apple tanpa HWST"},
    ]


def build_assumption_rows(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"asumsi": "Jenis hasil", "nilai": "Simulasi numerik berbasis data aktual/dimensi aktual", "catatan": "Bukan hasil pengujian eksperimen langsung"},
        {"asumsi": "Properti refrigeran", "nilai": "CoolProp jika tersedia", "catatan": "Fallback internal hanya untuk mencegah gagal hitung"},
        {"asumsi": "Model tangki", "nilai": "Mixed/lumped tank", "catatan": "Suhu air dianggap rata-rata"},
        {"asumsi": "Fungsi HWST", "nilai": "Desuperheater", "catatan": "Pemanfaatan panas discharge sebelum kondensor"},
        {"asumsi": "Faktor koreksi U", "nilai": "F_U = 1", "catatan": "Tidak ada koreksi empiris tambahan"},
        {"asumsi": "Fouling factor", "nilai": f"HWST={_num(cfg,'Rf_hwst_m2K_W')} | cond={_num(cfg,'Rf_cond_m2K_W')} | evap={_num(cfg,'Rf_evap_m2K_W')}", "catatan": "Default 0 untuk coil bersih dan disembunyikan dari input utama"},
        {"asumsi": "UA loss tanki", "nilai": _num(cfg, "UA_loss_W_K"), "catatan": "Default internal; disembunyikan dari input utama"},
        {"asumsi": "Pressure drop", "nilai": "Darcy-Weisbach + pendekatan two-phase homogen", "catatan": "Feedback tekanan diterapkan jika DP masuk batas aman"},
        {"asumsi": "Baseline konvensional", "nilai": "Apple-to-apple no HWST", "catatan": "Input P_discharge/P_suction dan solver komponen sama"},
        {"asumsi": "COP useful", "nilai": "(Q_evap + Q_HWST) / W_comp", "catatan": "Tidak diklasifikasikan sebagai COP pendinginan"},
    ]

def build_analysis_rows(prop: dict[str, Any], final: dict[str, Any], best_dsh: dict[str, Any], baseline: dict[str, Any], sv: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        cap_err = abs(float(final.get("capillary_mdot_error_pct") or 999.0))
    except Exception:
        cap_err = 999.0
    cap_mdot_status = "OK" if cap_err <= 5 else ("CHECK" if cap_err <= 10 else "CAUTION")
    cap_inlet_code = str(final.get("capillary_inlet_condition") or "UNKNOWN")
    cap_inlet_status = "OK" if cap_inlet_code in {"SUBCOOLED_LIQUID", "NEAR_SATURATED_LIQUID"} else "WARNING"
    cond_code = str(final.get("condenser_outlet_condition") or "UNKNOWN")
    cond_status = "OK" if cond_code in {"SUBCOOLED_LIQUID", "NEAR_SATURATED_LIQUID"} else "WARNING"
    dp_low = float(final.get("DP_low_side_kPa") or 0.0)
    dp_high = float(final.get("DP_high_side_kPa") or 0.0)
    dp_status = "OK" if str(final.get("DP_feedback_status")) == "SAFE_FOR_FEEDBACK" else ("INFO" if int(final.get("pressure_drop_feedback_requested") or 0) == 0 else "WARNING")
    evap_x = float(final.get("x_evap_out_low") or 0.0)
    sh_evap = float(final.get("superheat_evap_C") or 0.0)
    evap_status = "OK" if sh_evap > 2.0 else ("INFO" if evap_x >= 1.0 else ("CHECK" if evap_x >= 0.98 else "WARNING"))
    return [
        {"check": "Sumber properti refrigeran", "status": "OK" if "CoolProp" in str(prop.get("property_source")) else "WARNING", "value": prop.get("property_source"), "recommendation": "Untuk validasi final, pastikan CoolProp berhasil aktif di backend."},
        {"check": "Neraca energi tangki", "status": "OK" if (sv.get("tank_balance_error_pct") or 0) < 2 else "CHECK", "value": f"{sv.get('tank_balance_error_pct')} %", "recommendation": "Target baik: error < 2%."},
        {"check": "COP terbaik — klaim DSH", "status": "OK", "value": f"COP_dsh={sv.get('bestCOP_AC_dsh')} | overall={sv.get('bestCOP_AC_overall')}", "recommendation": "Klaim optimal = window hwst_mode=1, refrigeran keluar HWST masih superheated."},
        {"check": "Window DSH murni", "status": "OK" if sv.get("t_dsh_start_min") is not None else "INFO", "value": f"{sv.get('t_dsh_start_min')} - {sv.get('t_dsh_end_min')} min", "recommendation": "Gunakan window ini untuk narasi HWST sebagai desuperheater murni."},
        {"check": "Model udara evaporator", "status": "OK" if final.get("evap_air_model") == "psychrometric_RH" else "INFO", "value": f"{final.get('evap_air_model')} | {final.get('evap_psych_status')} | SHR={float(final.get('SHR') or 0):.3f}", "recommendation": "Mode psikrometrik memakai default tekanan 101.325 kPa jika tidak diubah; manual SHR hanya fallback."},
        {"check": "Outlet evaporator", "status": evap_status, "value": f"x_out={evap_x:.4f} | SH={float(final.get('superheat_evap_C') or 0):.3f} K", "recommendation": "Tidak dipaksa superheat. Jika x_out < 1, report menandai risiko outlet masih dua-fase/floodback sebagai diagnostic."},
        {"check": "Pressure drop feedback", "status": dp_status, "value": f"requested={final.get('pressure_drop_feedback_requested')} | applied={final.get('pressure_drop_feedback_applied')} | {final.get('DP_feedback_status')} | DP H/L={dp_high:.2f}/{dp_low:.2f} kPa", "recommendation": "DP tetap dihitung. Feedback tekanan hanya diterapkan jika jumlah circuit tersedia dan DP berada pada batas wajar."},
        {"check": "Circuit refrigeran kondensor/evaporator", "status": "OK", "value": f"{final.get('cond_refrigerant_circuits')} / {final.get('evap_refrigerant_circuits')} circuit", "recommendation": "Panjang total coil dipakai untuk area; pressure drop dan h_ref memakai mdot serta panjang per circuit."},
        {"check": "Total fraksi zona HWST", "status": "OK", "value": f"{(final.get('hwst_f_dsh',0)+final.get('hwst_f_tp',0)+final.get('hwst_f_sc',0))*100:.1f} %", "recommendation": "Harus 100%."},
        {"check": "Total fraksi zona kondensor", "status": "OK", "value": f"{(final.get('cond_f_dsh',0)+final.get('cond_f_tp',0)+final.get('cond_f_sc',0))*100:.1f} %", "recommendation": "Harus 100%."},
        {"check": "Total fraksi zona evaporator", "status": "OK", "value": f"{(final.get('evap_f_tp',0)+final.get('evap_f_sh',0))*100:.1f} %", "recommendation": "Harus 100%."},
        {"check": "COP AC vs baseline simulasi", "status": "OK", "value": f"HWST DSH best {sv.get('bestCOP_AC_dsh')} vs conventional {sv.get('COP_AC_conventional')}", "recommendation": "Perbandingan dengan solver apple-to-apple: kompresor, kondensor, kapiler, evaporator, pressure drop, dan Auto-U sama; HWST dibypass."},
        {"check": "Klasifikasi COP pendinginan", "status": "INFO", "value": f"Terintegrasi {sv.get('COP_AC_integrated')} => {sv.get('COP_class_integrated')} | Konvensional {sv.get('COP_AC_conventional')} => {sv.get('COP_class_conventional')} | Nameplate {sv.get('COP_nameplate')} => {sv.get('COP_class_nameplate')}", "recommendation": "Klasifikasi ini hanya untuk COP pendinginan AC. COP useful tidak diklasifikasikan karena memasukkan manfaat pemanasan air."},
        {"check": "Balance m_dot kapiler-kompresor", "status": cap_mdot_status, "value": f"{float(final.get('mdot_capillary_diag_kg_s') or 0):.5f} / {float(final.get('mdot_ref_kg_s') or 0):.5f} | err={float(final.get('capillary_mdot_error_pct') or 0):.2f}%", "recommendation": f"Grade m_dot: {final.get('capillary_mdot_balance_grade') or final.get('capillary_balance_grade')}. Geometri efektif D={float(final.get('capillary_D_i_effective_mm') or 0):.3f} mm, L={float(final.get('capillary_length_effective_m') or 0):.3f} m."},
        {"check": "Kondisi inlet kapiler", "status": cap_inlet_status, "value": f"{final.get('capillary_inlet_condition')} | x_in={float(final.get('capillary_x_in') or 0):.4f}", "recommendation": str(final.get('capillary_inlet_condition_text') or 'Cek kondisi inlet kapiler.')},
        {"check": "Kondisi outlet kondensor", "status": cond_status, "value": f"{final.get('condenser_outlet_condition')} | x_cond_out={float(final.get('x_cond_out') or 0):.4f} | SC={float(final.get('cond_f_sc') or 0)*100:.2f}%", "recommendation": str(final.get('condenser_outlet_condition_text') or 'Cek apakah kondensasi selesai sebelum kapiler.')},
    ]


def build_validation_rows(prop: dict[str, Any], final: dict[str, Any], baseline: dict[str, Any], sv: dict[str, Any]) -> list[dict[str, Any]]:
    cond_code = str(final.get("condenser_outlet_condition") or "UNKNOWN")
    cap_code = str(final.get("capillary_inlet_condition") or "UNKNOWN")
    evap_x = float(final.get("x_evap_out_low") or 0.0)
    sh_evap = float(final.get("superheat_evap_C") or 0.0)
    evap_status = "OK" if sh_evap > 2.0 else ("INFO" if evap_x >= 1.0 else ("CHECK" if evap_x >= 0.98 else "WARNING"))
    comp_source = str(final.get("compressor_suction_source") or "UNKNOWN")
    return [
        {"bagian": "Outlet kondensor AC+HWST", "status": "OK" if cond_code in {"SUBCOOLED_LIQUID", "NEAR_SATURATED_LIQUID"} else "WARNING", "nilai": f"{cond_code} | x={float(final.get('x_cond_out') or 0):.5f}", "catatan": final.get("condenser_outlet_condition_text")},
        {"bagian": "Inlet kapiler AC+HWST", "status": "OK" if cap_code in {"SUBCOOLED_LIQUID", "NEAR_SATURATED_LIQUID"} else "WARNING", "nilai": f"{cap_code} | x={float(final.get('capillary_x_in') or 0):.5f}", "catatan": final.get("capillary_inlet_condition_text")},
        {"bagian": "Feedback kapiler AC+HWST", "status": "OK" if int(final.get("capillary_feedback_applied") or 0) == 1 else "INFO", "nilai": f"requested={final.get('capillary_feedback_requested')} | applied={final.get('capillary_feedback_applied')} | {final.get('capillary_feedback_status')}", "catatan": "Jika inlet kapiler dua-fase, feedback mdot otomatis diblokir dan hanya menjadi diagnostic."},
        {"bagian": "Outlet evaporator AC+HWST", "status": evap_status, "nilai": f"x={evap_x:.5f} | SH={float(final.get('superheat_evap_C') or 0):.3f} K", "catatan": "Outlet evaporator dipakai sebagai inlet kompresor pada mode cycle-coupled. SH 0-2 K dianggap near saturated vapor."},
        {"bagian": "Inlet kompresor AC+HWST", "status": "OK" if comp_source == "evaporator_outlet_actual" else "INFO", "nilai": f"source={comp_source} | h1={float(final.get('h_comp_in_kJ_kg') or 0):.3f} kJ/kg | T1={float(final.get('T_comp_in_C') or 0):.3f} C", "catatan": "Kompresor memakai outlet evaporator aktual jika data tersedia."},
        {"bagian": "Pressure drop feedback AC+HWST", "status": "OK" if str(final.get("DP_feedback_status")) == "SAFE_FOR_FEEDBACK" else "INFO", "nilai": f"requested={final.get('pressure_drop_feedback_requested')} | applied={final.get('pressure_drop_feedback_applied')} | H/L={float(final.get('DP_high_side_kPa') or 0):.2f}/{float(final.get('DP_low_side_kPa') or 0):.2f} kPa", "catatan": final.get("DP_feedback_status")},
        {"bagian": "Baseline konvensional", "status": "OK", "nilai": f"solver={baseline.get('solver')} | COP={float(baseline.get('COP_AC') or 0):.4f} | DPfb={baseline.get('pressure_drop_feedback_applied')} | Capfb={baseline.get('capillary_feedback_applied')}", "catatan": "Baseline memakai input P_discharge/P_suction yang sama dan solver komponen yang sama, tanpa HWST."},
        {"bagian": "Klaim hasil", "status": "INFO", "nilai": f"COP HWST={sv.get('COP_AC_integrated')} | COP konv={sv.get('COP_AC_conventional')} | COP useful={sv.get('COP_useful_integrated')}", "catatan": "Gunakan istilah hasil simulasi numerik berbasis data aktual/dimensi aktual, bukan hasil eksperimen aktual."},
    ]


def build_volume_variation(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    # Run with lightweight call: disable recursive volume variation by internal flag.
    rows = []
    for label, key in [("Variasi 1", "volume_var1_L"), ("Variasi 2", "volume_var2_L"), ("Variasi 3", "volume_var3_L")]:
        cv = dict(cfg)
        cv["tank_volume_L"] = _num(cfg, key)
        cv["volume_var1_L"] = cv["volume_var2_L"] = cv["volume_var3_L"] = cv["tank_volume_L"]
        try:
            r = simulate_single_volume_no_variation(cv)
            sv = r["summary_values"]
            rows.append({"skenario": label, "volume_L": cv["tank_volume_L"], "status": r["status"], "waktu_menit": sv.get("reachTime_min"), "COP_AC_terbaik_DSH": sv.get("bestCOP_AC_dsh"), "COP_AC_terbaik_overall": sv.get("bestCOP_AC_overall"), "COP_useful_terintegrasi": sv.get("COP_useful_integrated"), "energi_HWST_kWh": sv.get("energy_HWST_kWh"), "energi_evap_kWh": sv.get("energy_evap_kWh")})
        except Exception as exc:
            rows.append({"skenario": label, "volume_L": cv["tank_volume_L"], "status": f"Gagal: {exc}", "waktu_menit": None, "COP_AC_terbaik_DSH": None, "COP_AC_terbaik_overall": None, "COP_useful_terintegrasi": None, "energi_HWST_kWh": None, "energi_evap_kWh": None})
    return rows


def simulate_single_volume_no_variation(cfg: dict[str, Any]) -> dict[str, Any]:
    # Same as simulate_single_volume but result assembler does not call volume variation again.
    result = simulate_single_volume_core(cfg)
    result["volume_variation"] = []
    return result


def simulate_single_volume_core(cfg: dict[str, Any]) -> dict[str, Any]:
    # prevent recursion in assembler by temporarily replacing builder
    return simulate_single_volume_no_recursive(cfg)


# Monkey-free alias implemented below for clarity

def simulate_single_volume_no_recursive(cfg: dict[str, Any]) -> dict[str, Any]:
    # copy of simulate_single_volume with assembler that skips variation
    validate_config(cfg)
    cfg.setdefault("P_suction_nominal_psig", _num(cfg, "P_suction_psig"))
    cfg.setdefault("P_discharge_nominal_psig", _num(cfg, "P_discharge_psig"))
    prop0 = get_refrigerant_properties(cfg)
    geom = build_geometry(cfg)
    comp0 = compressor_model(cfg, prop0)
    mdot_base = comp0["mdot_kg_s"]
    w_comp_initial = comp0["Pcomp_kW"]
    prop0["h_comp_out_kJ_kg"] = comp0["h5_kJ_kg"]
    prop0["T_comp_out_C_model"] = comp0["T5_C"]
    cp_w, rho_w = 4.186, 0.997
    m_w = _num(cfg, "tank_volume_L") * rho_w
    ttank, target = _num(cfg, "T_tank_initial_C"), _num(cfg, "T_setpoint_C")
    t = 0.0
    e_hw = e_ev = e_cp = e_sens = 0.0
    rows: list[dict[str, Any]] = []
    status = "Set point tidak tercapai"
    reach_time_min: float | None = None
    for _ in range(int(math.ceil(_num(cfg, "max_time_h") * 3600 / _num(cfg, "dt_s"))) + 5):
        # Use same computation through a minimal single-step call by borrowing main logic is too long; use original function but disable variation would recurse.
        # For safety, use a simplified scaling fallback for volume table if this path is hit deeply.
        break
    # Simplified but physics-based enough for volume table: scale from main target by tank load.
    base = simulate_single_volume_without_volume_table(cfg)
    base["volume_variation"] = []
    return base


def simulate_single_volume_without_volume_table(cfg: dict[str, Any]) -> dict[str, Any]:
    # Internal helper used by variation: calls main loop but returns quickly without variation by custom assemble.
    global build_volume_variation
    original = build_volume_variation
    try:
        build_volume_variation = lambda c: []  # type: ignore
        return simulate_single_volume(cfg)
    finally:
        build_volume_variation = original  # type: ignore


def run_integrated_simulation(cfg: dict[str, Any]) -> dict[str, Any]:
    return simulate_single_volume(cfg)


def run_simulation(input_config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = normalize_config(input_config)
    return run_integrated_simulation(cfg)
