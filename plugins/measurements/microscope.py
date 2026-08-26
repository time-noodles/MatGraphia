"""
顕微鏡写真 (Microscope: 光学 / AFM / TEM / SEM) 測定プラグイン
画像ファイル (.png, .jpg, .tif, .bmp) のアップロード、倍率・スケールバー情報の保持・プレビュー
"""
import os
import io
import streamlit as st
from typing import Tuple, Dict, Any, List

SCHEMA = {
    "type": "Microscope",
    "name": "顕微鏡写真 (Microscope: 光学/AFM/TEM/SEM)",
    "description": "光学顕微鏡、AFM、TEM、SEM等の構造画像データの登録・管理",
    "fields": [
        {
            "name": "microscope_type",
            "label": "顕微鏡タイプ",
            "type": "select",
            "options": ["光学顕微鏡 (Optical)", "SEM (走査電子顕微鏡)", "TEM (透過電子顕微鏡)", "AFM (原子間力顕微鏡)", "その他"],
            "default": "光学顕微鏡 (Optical)",
            "required": True,
        },
        {
            "name": "magnification",
            "label": "倍率 (例: 1000x, 50k)",
            "type": "text",
            "default": "1000x",
            "required": False,
        },
        {
            "name": "scale_bar_um",
            "label": "スケールバー長 (μm)",
            "type": "number",
            "default": 10.0,
            "required": False,
        },
        {
            "name": "observation_area",
            "label": "観察領域 / 測定部位 (例: 表面, 劈開面, 結晶端)",
            "type": "text",
            "default": "表面",
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
        info_msgs.append(f"🖼️ 顕微鏡画像ファイル ({filename}) を読み込みました。")
        if "sem" in filename.lower():
            initial_data["microscope_type"] = "SEM (走査電子顕微鏡)"
        elif "afm" in filename.lower():
            initial_data["microscope_type"] = "AFM (原子間力顕微鏡)"
        elif "tem" in filename.lower():
            initial_data["microscope_type"] = "TEM (透過電子顕微鏡)"
    else:
        warn_msgs.append(f"注意: 画像形式 (.png, .jpg, .tif, .bmp) 以外のファイルが指定されています: {filename}")
        
    return initial_data, info_msgs, warn_msgs
