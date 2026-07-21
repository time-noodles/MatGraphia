import uuid
from datetime import datetime,date
from typing import Optional,Dict,Any,List
from pydantic import BaseModel,Field

# システム内部で使用する一意なUUIDを生成する
def generate_uuid()->str:
    return str(uuid.uuid4())

# 文献情報
class Literature(BaseModel):
    literature_id:str=Field(default_factory=generate_uuid)
    literature_type:str
    title:Optional[str]=None
    authors:Optional[str]=None
    venue:Optional[str]=None
    publication_year:Optional[int]=None
    volume:Optional[str]=None
    parameters:Dict[str,Any]=Field(default_factory=dict)
    doi:str
    pdf_file_path:Optional[str]=None
    remarks:str
    created_at:datetime=Field(default_factory=datetime.now)
    updated_at:Optional[datetime]=None

# 実験・操作イベント
class Event(BaseModel):
    event_id:str=Field(default_factory=generate_uuid)
    project_id:str
    target_material:str
    event_type:str
    input_sample_ids:List[str]=Field(default_factory=list)
    reference_event_ids:List[str]=Field(default_factory=list)
    reference_literature_ids:List[str]=Field(default_factory=list)
    motivation:Optional[str]=None
    parameters:Dict[str,Any]=Field(default_factory=dict)
    remarks:Optional[str]=None
    created_at:datetime=Field(default_factory=datetime.now)
    updated_at:Optional[datetime]=None

# 測定試料の状態
class Sample(BaseModel):
    sample_id:str=Field(default_factory=generate_uuid)
    source_event_id:str
    human_id:str
    form:str
    parameters:Dict[str,Any]=Field(default_factory=dict)
    location:Optional[str]=None
    remarks:Optional[str]=None
    created_at:datetime=Field(default_factory=datetime.now)
    updated_at:Optional[datetime]=None

# 測定データ
class Measurement(BaseModel):
    measurement_id:str=Field(default_factory=generate_uuid)
    sample_id:str
    measurement_type:str
    conditions:Dict[str,Any]=Field(default_factory=dict)
    raw_data_path:Optional[str]=None
    processed_data_path:Optional[str]=None
    extracted_features:Dict[str,Any]=Field(default_factory=dict)
    operator:Optional[str]=None
    measured_at:date=Field(default_factory=date.today)
    remarks:Optional[str]=None
    created_at:datetime=Field(default_factory=datetime.now)
    updated_at:Optional[datetime]=None

# 比較解析・グラフ
class ComparisonFigure(BaseModel):
    figure_id:str=Field(default_factory=generate_uuid)
    title:str
    measurement_ids:List[str]=Field(default_factory=list)
    plot_script_path:Optional[str]=None
    output_image_path:Optional[str]=None
    remarks:Optional[str]=None
    created_at:datetime=Field(default_factory=datetime.now)
    updated_at:Optional[datetime]=None

# 物質メタデータ
class Material(BaseModel):
    material_id:str=Field(default_factory=generate_uuid)
    name:str
    properties:Dict[str,Any]=Field(default_factory=dict)
    reference_literature_id:Optional[str]=None
    impurity_material_ids:List[str]=Field(default_factory=list)
    polymorph_material_ids:List[str]=Field(default_factory=list)
    cif_file_path:Optional[str]=None
    remarks:Optional[str]=None
    created_at:datetime=Field(default_factory=datetime.now)
    updated_at:Optional[datetime]=None

# タスク管理
class Task(BaseModel):
    task_id:str=Field(default_factory=generate_uuid)
    title:str
    status:str="Todo"
    related_entity_type:Optional[str]=None
    related_entity_id:Optional[str]=None
    due_date:Optional[str]=None
    remarks:Optional[str]=None
    created_at:datetime=Field(default_factory=datetime.now)
    updated_at:Optional[datetime]=None
