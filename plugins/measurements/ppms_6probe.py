"""
PPMS 六端子法 (PPMS 6-probe Hall: rhoxy, RH, n, mu) プラグイン
参照: PPMS (hall.ipynb, hall_2peace.py)

磁場 H [Oe/T] vs ホール抵抗/電圧 Vxy データのパース、ホール係数 RH, 搬送波濃度 n, 移動度 mu 算出
"""
import os
import io
import numpy as np
import pandas as pd
import streamlit as st
from typing import Tuple, Dict, Any, List

SCHEMA = {
    "type": "PPMS_6probe",
    "name": r"PPMS 六端子法 (ホール効果 $\rho_{xy}$, $R_\mathrm{H}$, 搬送波濃度 $n$, 移動度 $\mu$)",
    "description": r"ホール効果測定データ ($V_{xy}$ vs $H$) からのホール係数 $R_\mathrm{H}$, キャリア型 (p/n), キャリア密度 $n$, 移動度 $\mu$ 算定",
    "fields": [
        {
            "name": "temp_k",
            "label": r"測定温度 $T$ [K]",
            "type": "number",
            "default": 300.0,
            "required": True,
        },
        {
            "name": "max_magnetic_field_t",
            "label": r"最大磁場 $H$ [T]",
            "type": "number",
            "default": 9.0,
            "required": False,
        },
        {
            "name": "carrier_type",
            "label": "キャリアタイプ (伝導型)",
            "type": "select",
            "options": ["n型 (電子伝導)", "p型 (正孔伝導)", "マルチバンド (複合)"],
            "default": "n型 (電子伝導)",
            "required": False,
        },
        {
            "name": "hall_coefficient_rh_cm3_c",
            "label": r"ホール係数 $R_\mathrm{H}$ [$\mathrm{cm}^3/\mathrm{C}$]",
            "type": "number",
            "default": 0.0,
            "required": False,
        },
        {
            "name": "carrier_density_n_cm3",
            "label": r"搬送波 (キャリア) 密度 $n$ [$\mathrm{cm}^{-3}$]",
            "type": "text",
            "default": "1.0e19",
            "required": False,
        },
        {
            "name": "mobility_mu_cm2_vs",
            "label": r"ホール移動度 $\mu$ [$\mathrm{cm}^2/(\mathrm{V}\cdot\mathrm{s})$]",
            "type": "number",
            "default": 100.0,
            "required": False,
        },
    ]
}

def parse_ppms_6probe_dat(file_bytes: bytes) -> Tuple[np.ndarray, np.ndarray, str]:
    """
    PPMS 六端子 Hall DAT/CSV パース
    Field [Oe/T] vs Hall Voltage / Resistance Vxy
    """
    try:
        lines = file_bytes.decode("utf-8", errors="ignore").splitlines()
        header_idx = -1
        for idx, l in enumerate(lines):
            if "[Data]" in l or "Field (Oe)" in l or "Field (T)" in l:
                header_idx = idx
                break
                
        if header_idx != -1:
            csv_str = "\n".join(lines[header_idx:])
            df = pd.read_csv(io.StringIO(csv_str), comment="[")
            field_col = [c for c in df.columns if "Field" in c]
            vxy_col = [c for c in df.columns if "Ch2" in c or "Hall" in c or "Vxy" in c or "Bridge" in c]
            if field_col and vxy_col:
                h = pd.to_numeric(df[field_col[0]], errors="coerce")
                v = pd.to_numeric(df[vxy_col[0]], errors="coerce")
                mask = h.notna() & v.notna()
                return h[mask].values, v[mask].values, None
                
        for sep in [",", r"\s+", "\t"]:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=sep, header=None, comment="#", engine="python")
                if df.shape[1] >= 2:
                    col0 = pd.to_numeric(df.iloc[:, 0], errors="coerce")
                    col1 = pd.to_numeric(df.iloc[:, 1], errors="coerce")
                    mask = col0.notna() & col1.notna()
                    if mask.sum() > 0:
                        return col0[mask].values, col1[mask].values, None
            except Exception:
                continue
                
        return None, None, "PPMS 6端子データの磁場/Vxy列をパースできませんでした。"
    except Exception as e:
        return None, None, f"PPMS 6端子パースエラー: {e}"


def calculate_hall_parameters(field_oe: np.ndarray, vxy: np.ndarray, thickness_cm: float = 0.01, current_a: float = 1e-4) -> Dict[str, float]:
    """
    hall_2peace.py に準拠した Hall 係数 RH, キャリア密度 n 算定
    RH = (Vxy / I) * (d / B)
    n = 1 / (|RH| * e)
    """
    e_charge = 1.602176634e-19
    field_tesla = field_oe / 10000.0
    
    # 磁場線形一次フィッティングによる斜き dVxy/dB 算出
    if len(field_tesla) > 2 and np.max(field_tesla) != np.min(field_tesla):
        poly = np.polyfit(field_tesla, vxy, 1)
        slope_v_t = poly[0]
        r_h = (slope_v_t / current_a) * thickness_cm  # cm^3 / C
        n_density = 1.0 / (abs(r_h) * e_charge) if abs(r_h) > 0 else 0.0
        return {
            "rh": float(r_h),
            "n": float(n_density),
            "carrier_type": "p型 (正孔伝導)" if r_h > 0 else "n型 (電子伝導)"
        }
    return {"rh": 0.0, "n": 0.0, "carrier_type": "n型 (電子伝導)"}


def prefill_from_upload(filename: str, file_bytes: bytes) -> Tuple[Dict[str, Any], List[str], List[str]]:
    initial_data = {}
    info_msgs = []
    warn_msgs = []
    
    h, v, err = parse_ppms_6probe_dat(file_bytes)
    if h is not None and v is not None:
        info_msgs.append(f"🧲 PPMS 6端子 ホールデータを抽出しました ({len(h)} ポイント)")
        params = calculate_hall_parameters(h, v)
        initial_data["hall_coefficient_rh_cm3_c"] = round(params["rh"], 5)
        initial_data["carrier_density_n_cm3"] = f"{params['n']:.2e}"
        initial_data["carrier_type"] = params["carrier_type"]
    elif err:
        warn_msgs.append(err)
        
    return initial_data, info_msgs, warn_msgs
