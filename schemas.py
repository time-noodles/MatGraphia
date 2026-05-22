import uuid
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

def generate_uuid() -> str:
    """システム内部で使用する一意なUUID(Primary Key)を生成する"""
    return str(uuid.uuid4())

# ----------------------------------------------------
# 1. literatures (先行研究・内部文献)
# ----------------------------------------------------
class Literature(BaseModel):
    literature_id: str = Field(default_factory=generate_uuid)
    literature_type: str
    title: Optional[str] = None
    authors: Optional[str] = None
    venue: Optional[str] = None
    publication_year: Optional[int] = None
    volume: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    doi: str               # 必須項目
    pdf_file_path: Optional[str] = None
    remarks: str           # 必須項目
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

# ----------------------------------------------------
# 2. events (実験・操作イベント)
# ----------------------------------------------------
class Event(BaseModel):
    event_id: str = Field(default_factory=generate_uuid)
    project_id: str
    target_material: str
    event_type: str
    input_sample_id: Optional[str] = None
    reference_event_id: Optional[str] = None
    reference_literature_id: Optional[str] = None
    input_sample_ids: List[str] = Field(default_factory=list)
    reference_event_ids: List[str] = Field(default_factory=list)
    reference_literature_ids: List[str] = Field(default_factory=list)
    motivation: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    remarks: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

# ----------------------------------------------------
# 3. samples (測定試料の状態)
# ----------------------------------------------------
class Sample(BaseModel):
    sample_id: str = Field(default_factory=generate_uuid)
    source_event_id: str
    human_id: str
    form: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    location: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

# ----------------------------------------------------
# 4. measurements (測定データ)
# ----------------------------------------------------
class Measurement(BaseModel):
    measurement_id: str = Field(default_factory=generate_uuid)
    sample_id: str
    measurement_type: str
    conditions: Dict[str, Any] = Field(default_factory=dict)
    raw_data_path: Optional[str] = None
    processed_data_path: Optional[str] = None
    extracted_features: Dict[str, Any] = Field(default_factory=dict)
    operator: Optional[str] = None
    measured_at: date = Field(default_factory=date.today)
    remarks: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

# ----------------------------------------------------
# 5. comparison_figures (比較解析・グラフ)
# ----------------------------------------------------
class ComparisonFigure(BaseModel):
    figure_id: str = Field(default_factory=generate_uuid)
    title: str
    measurement_ids: List[str] = Field(default_factory=list)
    plot_script_path: Optional[str] = None
    output_image_path: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

# ----------------------------------------------------
# 6. materials (物質メタデータ・先行研究特性)
# ----------------------------------------------------
class Material(BaseModel):
    material_id: str = Field(default_factory=generate_uuid)
    name: str              # 物質名 (例: CuCrS2)
    properties: Dict[str, Any] = Field(default_factory=dict) # Tc, Neel, etc.
    reference_literature_id: Optional[str] = None
    impurity_material_ids: List[str] = Field(default_factory=list)
    polymorph_material_ids: List[str] = Field(default_factory=list)
    cif_file_path: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

# ※以前ハードコードされていた各種SCHEMA群は、全て plugin_manager.py 経由で各 `plugins` ディレクトリから動的に読み込むように移行しました
