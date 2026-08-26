"""
MPMS 磁気測定 (MPMS SQUID Magnetometer: M-T, M-H, FC/ZFC) プラグイン
参照: MPMS (test.ipynb)

Temperature T [K] vs Magnetization M [emu/g, emu/mol], Field H [Oe] vs M [mu_B/f.u.] データ全自動解析
"""
import os
import io
import scipy.constants
import numpy as np
import pandas as pd
import streamlit as st
from typing import Tuple, Dict, Any, List

SCHEMA = {
    "type": "MPMS",
    "name": "MPMS 磁気測定 (M-T FC/ZFC, M-H 磁化曲線, 磁化率 χ)",
    "description": "SQUID MPMS 磁化率 (M-T FC/ZFC, 居里・外挿分析) および 磁化曲線 (M-H, μ_B/f.u. 単位換算) 解析",
    "fields": [
        {
            "name": "mpms_mode",
            "label": "測定モード",
            "type": "select",
            "options": ["M-T (FC: Field-Cooled)", "M-T (ZFC: Zero-Field-Cooled)", "M-T (FC/ZFC ペア)", "M-H (磁化曲線)"],
            "default": "M-T (FC/ZFC ペア)",
            "required": True,
        },
        {
            "name": "magnetic_field_oe",
            "label": "印加磁場 H (Oe)",
            "type": "number",
            "default": 1000.0,
            "required": False,
        },
        {
            "name": "sample_mass_mg",
            "label": "試料質量 (mg)",
            "type": "number",
            "default": 10.0,
            "required": False,
        },
        {
            "name": "molecular_weight_g_mol",
            "label": "分子量 (g/mol)",
            "type": "number",
            "default": 179.66,
            "required": False,
        },
        {
            "name": "tc_tn_transition_k",
            "label": "磁気転移温度 Tc / TN (K)",
            "type": "number",
            "default": 0.0,
            "required": False,
        },
        {
            "name": "mu_b_per_fu",
            "label": "飽和磁気モーメント (μ_B / f.u.)",
            "type": "number",
            "default": 0.0,
            "required": False,
        },
    ]
}

def parse_mpms_dat(file_bytes: bytes) -> Tuple[np.ndarray, np.ndarray, str, str]:
    """
    MPMS RSO/DAT パース
    Temp [K] / Field [Oe] vs Long Moment [emu]
    """
    try:
        lines = file_bytes.decode("utf-8", errors="ignore").splitlines()
        header_idx = -1
        for idx, l in enumerate(lines):
            if "[Data]" in l or "Temperature (K)" in l or "Field (Oe)" in l:
                header_idx = idx
                break
                
        if header_idx != -1:
            csv_str = "\n".join(lines[header_idx:])
            df = pd.read_csv(io.StringIO(csv_str), comment="[")
            t_col = [c for c in df.columns if "Temperature" in c]
            h_col = [c for c in df.columns if "Field" in c]
            m_col = [c for c in df.columns if "Moment" in c or "Magnetization" in c or "Long" in c]
            
            if "MT" in csv_str.upper() or "FC" in csv_str.upper() or "ZFC" in csv_str.upper():
                if t_col and m_col:
                    t = pd.to_numeric(df[t_col[0]], errors="coerce")
                    m = pd.to_numeric(df[m_col[0]], errors="coerce")
                    mask = t.notna() & m.notna()
                    return t[mask].values, m[mask].values, "Temperature [K]", "Long Moment [emu]"
            elif h_col and m_col:
                h = pd.to_numeric(df[h_col[0]], errors="coerce")
                m = pd.to_numeric(df[m_col[0]], errors="coerce")
                mask = h.notna() & m.notna()
                return h[mask].values, m[mask].values, "Field [Oe]", "Long Moment [emu]"
                
        # フォールバック CSV パース
        for sep in [",", r"\s+", "\t"]:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=sep, header=None, comment="#", engine="python")
                if df.shape[1] >= 2:
                    col0 = pd.to_numeric(df.iloc[:, 0], errors="coerce")
                    col1 = pd.to_numeric(df.iloc[:, 1], errors="coerce")
                    mask = col0.notna() & col1.notna()
                    if mask.sum() > 0:
                        return col0[mask].values, col1[mask].values, "X", "Y"
            except Exception:
                continue
                
        return None, None, "", "MPMS データの列をパースできませんでした。"
    except Exception as e:
        return None, None, "", f"MPMSパースエラー: {e}"


def convert_emu_to_mub_per_fu(moment_emu: float, sample_mass_g: float, mol_weight_g_mol: float) -> float:
    """
    MPMS/test.ipynb に準拠した mu_B / f.u. 単位換算
    NA = 6.02214076e23
    mu_B = 9.27401006573807e-24 J/T = 9.27401006573807e-21 emu
    num_fu = (mass / mol_weight) * NA
    mu_per_fu = moment_emu / (num_fu * mu_B_emu)
    """
    N_A = scipy.constants.N_A
    e = scipy.constants.e
    hbar = scipy.constants.hbar
    m_e = scipy.constants.m_e
    mu_B_SI = (e * hbar) / (2 * m_e)
    mu_B_emu = mu_B_SI * 1e3  # 9.27401e-21 emu
    
    if sample_mass_g > 0 and mol_weight_g_mol > 0:
        num_fu = (sample_mass_g / mol_weight_g_mol) * N_A
        return float(moment_emu / (num_fu * mu_B_emu))
    return 0.0


def prefill_from_upload(filename: str, file_bytes: bytes) -> Tuple[Dict[str, Any], List[str], List[str]]:
    initial_data = {}
    info_msgs = []
    warn_msgs = []
    
    x, y, x_name, y_name = parse_mpms_dat(file_bytes)
    if x is not None and y is not None:
        info_msgs.append(f"🧲 MPMS 磁気測定データを正常に抽出しました ({x_name} vs {y_name}, {len(x)} ポイント)")
        if "zfc" in filename.lower():
            initial_data["mpms_mode"] = "M-T (ZFC: Zero-Field-Cooled)"
        elif "fc" in filename.lower():
            initial_data["mpms_mode"] = "M-T (FC: Field-Cooled)"
        elif "mh" in filename.lower():
            initial_data["mpms_mode"] = "M-H (磁化曲線)"
    else:
        warn_msgs.append(y_name)
        
    return initial_data, info_msgs, warn_msgs
