"""
Shift電流測定 (Shift Current Photovoltage/Photocurrent) プラグイン
参照: shift-i (data_processing.ipynb)

光応答電流 I [uA] vs 電圧 V [mV] / 光強度 / 偏光角 測定データの自動抽出と解析
"""
import os
import io
import re
import numpy as np
import pandas as pd
import streamlit as st
from typing import Tuple, Dict, Any, List

SCHEMA = {
    "type": "ShiftCurrent",
    "name": "Shift電流測定 (光応答電流・偏光角依存性)",
    "description": "非線形光電応答・シフト電流 (Photocurrent I [μA] vs Voltage V [mV] / 光強・偏光依存性) 解析",
    "fields": [
        {
            "name": "light_wavelength_nm",
            "label": "励起光波長 (nm)",
            "type": "number",
            "default": 800.0,
            "required": True,
        },
        {
            "name": "light_power_mw",
            "label": "照射光強度 (mW)",
            "type": "number",
            "default": 5.0,
            "required": False,
        },
        {
            "name": "polarization_deg",
            "label": "偏光角 θ (°)",
            "type": "number",
            "default": 0.0,
            "required": False,
        },
        {
            "name": "zero_bias_photocurrent_ua",
            "label": "ゼロバイアス光電流 I_sc (μA)",
            "type": "number",
            "default": 0.0,
            "required": False,
        },
        {
            "name": "responsivity_ua_mw",
            "label": "光応答度 R (μA/mW)",
            "type": "number",
            "default": 0.0,
            "required": False,
        },
    ]
}

def parse_shift_current_data(file_bytes: bytes) -> Tuple[np.ndarray, np.ndarray, str]:
    """
    shift-i/data_processing.ipynb 参照
    V [mV] vs I [uA] データ抽出
    """
    try:
        raw_str = file_bytes.decode("utf-8", errors="ignore")
        # ShiftCurrent txt / csvパース
        for sep in [",", r"\s+", "\t"]:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=sep, header=None, comment="#", engine="python")
                if df.shape[1] >= 2:
                    col0 = pd.to_numeric(df.iloc[:, 0], errors="coerce")
                    col1 = pd.to_numeric(df.iloc[:, 1], errors="coerce")
                    mask = col0.notna() & col1.notna()
                    if mask.sum() > 0:
                        v_mv = col0[mask].values.astype(float)
                        i_ua = col1[mask].values.astype(float)
                        return v_mv, i_ua, None
            except Exception:
                continue
                
        return None, None, "Shift電流データの V, I 列をパースできませんでした。"
    except Exception as e:
        return None, None, f"Shift電流パースエラー: {e}"


def prefill_from_upload(filename: str, file_bytes: bytes) -> Tuple[Dict[str, Any], List[str], List[str]]:
    initial_data = {}
    info_msgs = []
    warn_msgs = []
    
    v, i_ua, err = parse_shift_current_data(file_bytes)
    if v is not None and i_ua is not None:
        info_msgs.append(f"💡 Shift電流データを抽出し増した ({len(v)} ポイント)")
        # ゼロバイアス (V=0近傍) の光電流値を補間算出
        if np.min(v) <= 0 <= np.max(v):
            isc = float(np.interp(0.0, v, i_ua))
            initial_data["zero_bias_photocurrent_ua"] = round(isc, 4)
    elif err:
        warn_msgs.append(err)
        
    return initial_data, info_msgs, warn_msgs
