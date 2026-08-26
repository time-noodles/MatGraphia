"""
Laue測定 (Laue X-ray Diffraction) プラグイン
ラウエ回折写真 (.png, .jpg, .tif) および プレゼンテーション (.pptx) ファイルのアップロード・解析・保存機能
"""
import os
import io
import streamlit as st
from typing import Tuple, Dict, Any, List

SCHEMA = {
    "type": "Laue",
    "name": "Laue測定 (ラウエX線回折・結晶方位)",
    "description": "単結晶の結晶方位 (hkl)、対称性、ラウエ回折パターン写真 / PPTX の保存・管理",
    "fields": [
        {
            "name": "target_hkl",
            "label": "測定方位 [hkl] (例: [001], [110])",
            "type": "text",
            "default": "[001]",
            "required": True,
        },
        {
            "name": "symmetry",
            "label": "点群・結晶点対称 (例: C4v, D6h)",
            "type": "text",
            "default": "D6h",
            "required": False,
        },
        {
            "name": "exposure_time_min",
            "label": "露光時間 (分)",
            "type": "number",
            "default": 30.0,
            "required": False,
        },
        {
            "name": "voltage_kv",
            "label": "管電圧 (kV)",
            "type": "number",
            "default": 35.0,
            "required": False,
        },
        {
            "name": "current_ma",
            "label": "管電流 (mA)",
            "type": "number",
            "default": 25.0,
            "required": False,
        },
        {
            "name": "file_format_type",
            "label": "添付フォーマット",
            "type": "select",
            "options": ["画像 (Photo/Image)", "PowerPoint (PPTX)", "その他"],
            "default": "画像 (Photo/Image)",
            "required": False,
        },
    ]
}

def prefill_from_upload(filename: str, file_bytes: bytes) -> Tuple[Dict[str, Any], List[str], List[str]]:
    initial_data = {}
    info_msgs = []
    warn_msgs = []
    
    ext = os.path.splitext(filename)[1].lower()
    if ext in [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"]:
        initial_data["file_format_type"] = "画像 (Photo/Image)"
        info_msgs.append(f"📷 ラウエ回折写真 ({filename}) を検出しました。")
    elif ext in [".pptx", ".ppt"]:
        initial_data["file_format_type"] = "PowerPoint (PPTX)"
        info_msgs.append(f"📊 ラウエ解析プレゼンテーション ({filename}) を検出しました。")
    else:
        info_msgs.append(f"📁 ラウエ測定関連ファイル ({filename}) を読み込みました。")
        
    return initial_data, info_msgs, warn_msgs
