import os
import shutil
from pathlib import Path

# ドキュメントルート直下のdataフォルダを基準とする
BASE_DIR = Path("data")
RAW_DIR = BASE_DIR / "Raw"
PROCESSED_DIR = BASE_DIR / "Processed"
LITERATURE_DIR = BASE_DIR / "Literature"
MATERIAL_DIR = BASE_DIR / "Material"

def init_directories():
    """各種ディレクトリの初期化"""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    LITERATURE_DIR.mkdir(parents=True, exist_ok=True)
    MATERIAL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Info] Directories initialized at {BASE_DIR.absolute()}")

def get_raw_dir(measurement_id: str) -> Path:
    """ID単位のRawディレクトリ取得・生成"""
    target = RAW_DIR / measurement_id
    target.mkdir(parents=True, exist_ok=True)
    return target

def get_processed_dir(measurement_id: str) -> Path:
    """ID単位のProcessedディレクトリ取得・生成"""
    target = PROCESSED_DIR / measurement_id
    target.mkdir(parents=True, exist_ok=True)
    return target

def save_raw_file(measurement_id: str, file_name: str, file_content: bytes) -> str:
    """Rawデータを保存（measurement_id 単位でフォルダー分け）"""
    target_dir = get_raw_dir(measurement_id)
    file_path = target_dir / file_name
    with open(file_path, "wb") as f: f.write(file_content)
    return str(file_path.relative_to(BASE_DIR))

def save_literature_file(literature_id: str, file_name: str, file_content: bytes) -> str:
    """文献ファイルを保存"""
    target_dir = LITERATURE_DIR / literature_id
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / file_name
    with open(file_path, "wb") as f: f.write(file_content)
    return str(file_path.relative_to(BASE_DIR))

def save_material_file(material_id: str, file_name: str, file_content: bytes) -> str:
    """物質関連ファイル（CIFなど）を保存"""
    target_dir = MATERIAL_DIR / material_id
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / file_name
    with open(file_path, "wb") as f: f.write(file_content)
    return str(file_path.relative_to(BASE_DIR))

def save_processed_file(measurement_id: str, file_name: str, file_content: bytes) -> str:
    """Processedデータを保存"""
    target_dir = get_processed_dir(measurement_id)
    file_path = target_dir / file_name
    with open(file_path, "wb") as f: f.write(file_content)
    return str(file_path.relative_to(BASE_DIR))
