"""
Raman測定 (Raman Spectroscopy) プラグイン
参照: Raman (test.ipynb)

CSVファイルからの Raman Shift [cm^-1] vs Intensity データ自動読み込み、pybeads バックグラウンド除去、symple_plot 描画
"""
import os
import io
import re
import numpy as np
import pandas as pd
import streamlit as st
from typing import Tuple, Dict, Any, List

SCHEMA = {
    "type": "Raman",
    "name": "Raman測定 (ラマン分光)",
    "description": "ラマンシフト [cm⁻¹] vs 強度 [a.u.] プロファイルデータの読み込みと解析",
    "fields": [
        {
            "name": "laser_wavelength_nm",
            "label": "レーザー波長 (nm)",
            "type": "number",
            "default": 532.0,
            "required": True,
        },
        {
            "name": "laser_power_mw",
            "label": "レーザー出力 (mW)",
            "type": "number",
            "default": 1.0,
            "required": False,
        },
        {
            "name": "exposure_time_sec",
            "label": "露光時間 (秒)",
            "type": "number",
            "default": 10.0,
            "required": False,
        },
        {
            "name": "accumulations",
            "label": "積算回数",
            "type": "number",
            "default": 3,
            "required": False,
        },
        {
            "name": "range_min_cm1",
            "label": "測定範囲 Min (cm⁻¹)",
            "type": "number",
            "default": 100.0,
            "required": False,
        },
        {
            "name": "range_max_cm1",
            "label": "測定範囲 Max (cm⁻¹)",
            "type": "number",
            "default": 1000.0,
            "required": False,
        },
    ]
}

def parse_raman_data(file_bytes: bytes) -> Tuple[np.ndarray, np.ndarray, str]:
    """
    Raman CSV/TXT データパース
    Col 0: Raman Shift [cm^-1], Col 1: Intensity
    """
    try:
        for sep in [",", r"\s+", "\t"]:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=sep, header=None, comment="#", engine="python")
                if df.shape[1] >= 2:
                    col0 = pd.to_numeric(df.iloc[:, 0], errors="coerce")
                    col1 = pd.to_numeric(df.iloc[:, 1], errors="coerce")
                    mask = col0.notna() & col1.notna()
                    if mask.sum() > 0:
                        shift = col0[mask].values.astype(float)
                        intensity = col1[mask].values.astype(float)
                        return shift, intensity, None
            except Exception:
                continue
        return None, None, "Ramanデータの2列（Shift, Intensity）をパースできませんでした。"
    except Exception as e:
        return None, None, f"ファイル読み込みエラー: {e}"


def remove_raman_background(signal: np.ndarray, fc: float = 0.1) -> np.ndarray:
    """
    Raman/test.ipynb と同等の pybeads によるベースライン除去
    """
    try:
        import pybeads
        def sigmoid(x):
            return 1 / (1 + np.exp(-x))
        d = 1
        r = 6
        amp = 0.001
        lam0, lam1, lam2 = 0.5 * amp, 5 * amp, 4 * amp
        Nit = 15
        pen = 'L1_v2'
        xscale_l, xscale_r = 10, 10
        dx = 0.5
        y_l = signal[0] * sigmoid(1 / xscale_l * np.arange(-5 * xscale_l, 5 * xscale_l, dx))
        y_r = signal[-1] * sigmoid(-1 / xscale_r * np.arange(-5 * xscale_r, 5 * xscale_r, dx))
        y_ext = np.hstack([y_l, signal, y_r])
        len_l, len_o = len(y_l), len(signal)
        sig_est, bg_est, cost = pybeads.beads(y_ext, d, fc, r, Nit, lam0, lam1, lam2, pen, conv=None)
        return sig_est[len_l:len_l + len_o]
    except Exception:
        # pybeadsが利用できない場合の簡易線形背景除去ポリフィル
        bg = np.linspace(signal[0], signal[-1], len(signal))
        return np.maximum(0, signal - bg)


def prefill_from_upload(filename: str, file_bytes: bytes) -> Tuple[Dict[str, Any], List[str], List[str]]:
    initial_data = {}
    info_msgs = []
    warn_msgs = []
    
    shift, intensity, err = parse_raman_data(file_bytes)
    if shift is not None and intensity is not None:
        info_msgs.append(f"📈 Ramanデータを正常に抽出しました ({len(shift)} データポイント)")
        initial_data["range_min_cm1"] = float(np.nanmin(shift))
        initial_data["range_max_cm1"] = float(np.nanmax(shift))
    elif err:
        warn_msgs.append(err)
        
    return initial_data, info_msgs, warn_msgs
