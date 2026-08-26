"""
電気化学測定 (Electrochemistry) プラグイン
参照: 501-r6244 (test.ipynb)

CV (Cyclic Voltammetry: E [V] vs I [uA]) および PS/GCD (Time [min] vs I [uA]) データの自動抽出と解析
"""
import os
import io
import re
import numpy as np
import pandas as pd
import streamlit as st
from typing import Tuple, Dict, Any, List

SCHEMA = {
    "type": "Electrochemistry",
    "name": "電気化学測定 (CV, GCD, EIS)",
    "description": "サイクリックボルタンメトリー (CV), 充放電 (GCD), 電流時間曲線 (PS) の解析",
    "fields": [
        {
            "name": "electrochemistry_mode",
            "label": "測定モード",
            "type": "select",
            "options": ["CV (Cyclic Voltammetry)", "GCD (Galvanostatic Charge/Discharge)", "PS (Potentiostatic Step)", "EIS (インピーダンス)"],
            "default": "CV (Cyclic Voltammetry)",
            "required": True,
        },
        {
            "name": "scan_rate_mv_s",
            "label": "掃引速度 (mV/s)",
            "type": "number",
            "default": 10.0,
            "required": False,
        },
        {
            "name": "potential_window",
            "label": "電位範囲 (V vs ref)",
            "type": "text",
            "default": "-1.0 ~ +1.0 V",
            "required": False,
        },
        {
            "name": "electrolyte",
            "label": "電解液 (例: 1M H2SO4, 1M KOH)",
            "type": "text",
            "default": "1M H2SO4",
            "required": False,
        },
        {
            "name": "working_electrode",
            "label": "作用電極 (Working Electrode)",
            "type": "text",
            "default": "Glassy Carbon",
            "required": False,
        },
        {
            "name": "reference_electrode",
            "label": "参照電極 (Reference Electrode)",
            "type": "text",
            "default": "Ag/AgCl",
            "required": False,
        },
    ]
}

def parse_electrochemistry_data(file_bytes: bytes) -> Tuple[np.ndarray, np.ndarray, str, str]:
    """
    参照 501-r6244/test.ipynb に基づく CV / PS データの自動パース
    CV: Voltage [V] vs Current [uA]
    PS/GCD: Time [min] vs Current [uA]
    """
    try:
        raw_str = file_bytes.decode("utf-8", errors="ignore")
        data_list = np.array(re.sub(r'\s+', ',', raw_str).split(','))
        
        # 参照コードのヘッダー検出パターン
        match_idx = np.where(data_list == '""')[0]
        if len(match_idx) > 0:
            sta = match_idx[0] + 1 + 4
            df = pd.DataFrame(data_list[sta:-1].reshape(-1, 4)).astype(float)
            cols = [str(c).lower() for c in data_list[sta-4:sta]]
            df.columns = cols
            if "voltage_v" in cols and "current_a" in cols:
                v = df["voltage_v"].values[:-1]
                i_ua = df["current_a"].values[:-1] * 1e6
                return v, i_ua, "Voltage [V]", "Current [uA]"
            elif "time_min" in cols and "current_a" in cols:
                t = df["time_min"].values[:-1]
                i_ua = df["current_a"].values[:-1] * 1e6
                return t, i_ua, "Time [min]", "Current [uA]"
                
        # 通常の CSV フォールバック
        for sep in [",", r"\s+", "\t"]:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=sep, header=None, comment="#", engine="python")
                if df.shape[1] >= 2:
                    col0 = pd.to_numeric(df.iloc[:, 0], errors="coerce")
                    col1 = pd.to_numeric(df.iloc[:, 1], errors="coerce")
                    mask = col0.notna() & col1.notna()
                    if mask.sum() > 0:
                        x_vals = col0[mask].values.astype(float)
                        y_vals = col1[mask].values.astype(float)
                        return x_vals, y_vals, "Potential / Time", "Current"
            except Exception:
                continue
                
        return None, None, "", "電気化学データの列をパースできませんでした。"
    except Exception as e:
        return None, None, "", f"パースエラー: {e}"


def prefill_from_upload(filename: str, file_bytes: bytes) -> Tuple[Dict[str, Any], List[str], List[str]]:
    initial_data = {}
    info_msgs = []
    warn_msgs = []
    
    x, y, x_name, y_name = parse_electrochemistry_data(file_bytes)
    if x is not None and y is not None:
        info_msgs.append(f"⚡ 電気化学データを正常に抽出しました ({x_name} vs {y_name}, {len(x)} ポイント)")
        if "cv" in filename.lower():
            initial_data["electrochemistry_mode"] = "CV (Cyclic Voltammetry)"
        elif "ps" in filename.lower():
            initial_data["electrochemistry_mode"] = "PS (Potentiostatic Step)"
        elif "gcd" in filename.lower():
            initial_data["electrochemistry_mode"] = "GCD (Galvanostatic Charge/Discharge)"
    else:
        warn_msgs.append(y_name)
        
    return initial_data, info_msgs, warn_msgs
