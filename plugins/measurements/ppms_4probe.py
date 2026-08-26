"""
PPMS 四端子法 (PPMS 4-probe Transport: R-T, rho-T) プラグイン
参照: PPMS (pT.ipynb)

DAT/CSVファイルからの Temperature [K] vs Resistance R [ohm] / Resistivity rho [ohm cm] データ解析、超伝導 Tc 転移温度抽出
"""
import os
import io
import numpy as np
import pandas as pd
import streamlit as st
from typing import Tuple, Dict, Any, List

SCHEMA = {
    "type": "PPMS_4probe",
    "name": "PPMS 四端子法 (超伝導 R-T, Tc, Hc2)",
    "description": "PPMS 四端子電気抵抗率 (R-T, ρ-T) 測定、超伝導転移温度 (Tc) 解析",
    "fields": [
        {
            "name": "excitation_current_ua",
            "label": "励起電流 (μA)",
            "type": "number",
            "default": 100.0,
            "required": True,
        },
        {
            "name": "magnetic_field_oe",
            "label": "印加磁場 (Oe)",
            "type": "number",
            "default": 0.0,
            "required": False,
        },
        {
            "name": "temp_range_k",
            "label": "測定温度範囲 (K)",
            "type": "text",
            "default": "2.0 ~ 300 K",
            "required": False,
        },
        {
            "name": "tc_onset_k",
            "label": "超伝導転移開始温度 Tc(onset) (K)",
            "type": "number",
            "default": 0.0,
            "required": False,
        },
        {
            "name": "tc_zero_k",
            "label": "ゼロ抵抗温度 Tc(zero) (K)",
            "type": "number",
            "default": 0.0,
            "required": False,
        },
        {
            "name": "rrr_ratio",
            "label": "残留抵抗比 RRR (R_300K / R_Tc)",
            "type": "number",
            "default": 1.0,
            "required": False,
        },
    ]
}

def parse_ppms_4probe_dat(file_bytes: bytes) -> Tuple[np.ndarray, np.ndarray, str]:
    """
    PPMS DAT/CSV 4-probe パース
    Temp [K] vs Resistance R [ohm] / Resistivity rho
    """
    try:
        lines = file_bytes.decode("utf-8", errors="ignore").splitlines()
        header_idx = -1
        for idx, l in enumerate(lines):
            if "[Data]" in l or "Temperature (K)" in l:
                header_idx = idx
                break
                
        if header_idx != -1:
            csv_str = "\n".join(lines[header_idx:])
            df = pd.read_csv(io.StringIO(csv_str), comment="[")
            temp_col = [c for c in df.columns if "Temperature" in c]
            res_col = [c for c in df.columns if "Bridge" in c or "Resistivity" in c or "Resistance" in c or "Ch1" in c]
            if temp_col and res_col:
                t = pd.to_numeric(df[temp_col[0]], errors="coerce")
                r = pd.to_numeric(df[res_col[0]], errors="coerce")
                mask = t.notna() & r.notna()
                return t[mask].values, r[mask].values, None
                
        # フォールバック CSV パース
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
                
        return None, None, "PPMS 4端子データの温度/抵抗列をパースできませんでした。"
    except Exception as e:
        return None, None, f"PPMSファイル読み込みエラー: {e}"


def prefill_from_upload(filename: str, file_bytes: bytes) -> Tuple[Dict[str, Any], List[str], List[str]]:
    initial_data = {}
    info_msgs = []
    warn_msgs = []
    
    t, r, err = parse_ppms_4probe_dat(file_bytes)
    if t is not None and r is not None:
        info_msgs.append(f"❄️ PPMS 4端子データを抽出しました ({float(np.min(t)):.1f}K - {float(np.max(t)):.1f}K, {len(t)} ポイント)")
        initial_data["temp_range_k"] = f"{float(np.min(t)):.1f} ~ {float(np.max(t)):.1f} K"
        # RRR の概算
        if len(r) > 1 and np.min(r) > 0:
            rrr = float(r[0] / r[-1])
            initial_data["rrr_ratio"] = round(rrr, 2)
    elif err:
        warn_msgs.append(err)
        
    return initial_data, info_msgs, warn_msgs
