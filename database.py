import sqlite3
import json
import re
import os
import sys
from datetime import datetime
import streamlit as st
from typing import Dict,List,Any,Optional
from schemas import Literature,Event,Sample,Measurement,ComparisonFigure,Material,Task

DB_PATH="data/matgraphia.db"

# SQLiteの接続を取得
def get_connection()->sqlite3.Connection:
    conn=sqlite3.connect(DB_PATH)
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# データベースの初期化とリレーショナルテーブル生成
def init_db():
    os.makedirs(os.path.dirname(DB_PATH),exist_ok=True)
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS literatures (
        literature_id TEXT PRIMARY KEY,
        literature_type TEXT,
        title TEXT,
        authors TEXT,
        venue TEXT,
        publication_year INTEGER,
        volume TEXT,
        parameters TEXT,
        doi TEXT,
        pdf_file_path TEXT,
        remarks TEXT,
        created_at DATETIME,
        updated_at DATETIME
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        event_id TEXT PRIMARY KEY,
        project_id TEXT,
        target_material TEXT,
        event_type TEXT,
        motivation TEXT,
        parameters TEXT,
        remarks TEXT,
        created_at DATETIME,
        updated_at DATETIME
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS samples (
        sample_id TEXT PRIMARY KEY,
        source_event_id TEXT,
        human_id TEXT,
        form TEXT,
        parameters TEXT,
        location TEXT,
        remarks TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(source_event_id) REFERENCES events(event_id) ON DELETE CASCADE
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS measurements (
        measurement_id TEXT PRIMARY KEY,
        sample_id TEXT,
        measurement_type TEXT,
        conditions TEXT,
        raw_data_path TEXT,
        processed_data_path TEXT,
        extracted_features TEXT,
        operator TEXT,
        measured_at DATE,
        remarks TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(sample_id) REFERENCES samples(sample_id) ON DELETE CASCADE
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS comparison_figures (
        figure_id TEXT PRIMARY KEY,
        title TEXT,
        plot_script_path TEXT,
        output_image_path TEXT,
        remarks TEXT,
        created_at DATETIME,
        updated_at DATETIME
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS materials (
        material_id TEXT PRIMARY KEY,
        name TEXT,
        properties TEXT,
        reference_literature_id TEXT,
        cif_file_path TEXT,
        remarks TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(reference_literature_id) REFERENCES literatures(literature_id) ON DELETE SET NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        title TEXT,
        status TEXT,
        related_entity_type TEXT,
        related_entity_id TEXT,
        due_date TEXT,
        remarks TEXT,
        created_at DATETIME,
        updated_at DATETIME
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS event_inputs (
        event_id TEXT,
        sample_id TEXT,
        PRIMARY KEY(event_id,sample_id),
        FOREIGN KEY(event_id) REFERENCES events(event_id) ON DELETE CASCADE,
        FOREIGN KEY(sample_id) REFERENCES samples(sample_id) ON DELETE CASCADE
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS event_references (
        event_id TEXT,
        ref_event_id TEXT,
        PRIMARY KEY(event_id,ref_event_id),
        FOREIGN KEY(event_id) REFERENCES events(event_id) ON DELETE CASCADE,
        FOREIGN KEY(ref_event_id) REFERENCES events(event_id) ON DELETE CASCADE
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS event_literatures (
        event_id TEXT,
        literature_id TEXT,
        PRIMARY KEY(event_id,literature_id),
        FOREIGN KEY(event_id) REFERENCES events(event_id) ON DELETE CASCADE,
        FOREIGN KEY(literature_id) REFERENCES literatures(literature_id) ON DELETE CASCADE
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS material_relations (
        material_id TEXT,
        related_material_id TEXT,
        relation_type TEXT,
        PRIMARY KEY(material_id,related_material_id,relation_type),
        FOREIGN KEY(material_id) REFERENCES materials(material_id) ON DELETE CASCADE,
        FOREIGN KEY(related_material_id) REFERENCES materials(material_id) ON DELETE CASCADE
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS comparison_measurements (
        figure_id TEXT,
        measurement_id TEXT,
        PRIMARY KEY(figure_id,measurement_id),
        FOREIGN KEY(figure_id) REFERENCES comparison_figures(figure_id) ON DELETE CASCADE,
        FOREIGN KEY(measurement_id) REFERENCES measurements(measurement_id) ON DELETE CASCADE
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tags (
        tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag_name TEXT UNIQUE
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entity_tags (
        entity_type TEXT,
        entity_id TEXT,
        tag_id INTEGER,
        PRIMARY KEY(entity_type,entity_id,tag_id),
        FOREIGN KEY(tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS developer_logs (
        log_id TEXT PRIMARY KEY,
        log_type TEXT NOT NULL,
        title TEXT,
        content TEXT,
        page_name TEXT,
        status TEXT DEFAULT 'Open',
        created_at DATETIME
    )
    """)
    conn.commit()
    conn.close()

# Obsidianとの同期処理
def sync_obsidian(force=False):
    if not force and get_setting("obsidian_auto_sync","False")=="False":return
    path=os.path.join(os.getcwd(),"obsidian_vault")
    try:
        from obsidian_exporter import ObsidianExporter
        ObsidianExporter(sys.modules[__name__]).export_to_directory(path)
    except Exception:
        pass

# 備考などのテキストからハッシュタグを抽出して登録
def extract_and_save_tags(entity_type:str,entity_id:str,text:str,cursor:sqlite3.Cursor):
    cursor.execute("DELETE FROM entity_tags WHERE entity_type=? AND entity_id=?",(entity_type,entity_id))
    if not text:return
    tags=re.findall(r"#([^\s#]+)",text)
    for tag in set(tags):
        cursor.execute("INSERT OR IGNORE INTO tags (tag_name) VALUES (?)",(tag,))
        cursor.execute("SELECT tag_id FROM tags WHERE tag_name=?",(tag,))
        row=cursor.fetchone()
        if row:cursor.execute("INSERT INTO entity_tags (entity_type,entity_id,tag_id) VALUES (?,?,?)",(entity_type,entity_id,row[0]))

# 設定取得
def get_setting(key:str,default:Any=None)->Any:
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key=?",(key,))
    row=cursor.fetchone()
    conn.close()
    return row[0] if row else default

# 設定保存
def set_setting(key:str,value:Any):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",(key,str(value)))
    conn.commit()
    conn.close()

# 文献の挿入
def insert_literature(lit:Literature):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("""
        INSERT INTO literatures (
            literature_id,literature_type,title,authors,venue,publication_year,volume,parameters,doi,pdf_file_path,remarks,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """,(
        lit.literature_id,lit.literature_type,lit.title,lit.authors,lit.venue,
        lit.publication_year,lit.volume,json.dumps(lit.parameters),lit.doi,lit.pdf_file_path,lit.remarks,lit.created_at.isoformat()
    ))
    extract_and_save_tags("Literature",lit.literature_id,lit.remarks,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# イベントの挿入
def insert_event(evt:Event):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("""
        INSERT INTO events (
            event_id,project_id,target_material,event_type,motivation,parameters,remarks,created_at
        ) VALUES (?,?,?,?,?,?,?,?)
    """,(
        evt.event_id,evt.project_id,evt.target_material,evt.event_type,evt.motivation,json.dumps(evt.parameters),evt.remarks,evt.created_at.isoformat()
    ))
    for sid in evt.input_sample_ids:
        cursor.execute("INSERT INTO event_inputs (event_id,sample_id) VALUES (?,?)",(evt.event_id,sid))
    for reid in evt.reference_event_ids:
        cursor.execute("INSERT INTO event_references (event_id,ref_event_id) VALUES (?,?)",(evt.event_id,reid))
    for lid in evt.reference_literature_ids:
        cursor.execute("INSERT INTO event_literatures (event_id,literature_id) VALUES (?,?)",(evt.event_id,lid))
    extract_and_save_tags("Event",evt.event_id,evt.remarks,cursor)
    extract_and_save_tags("Event",evt.event_id,evt.motivation,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# サンプルの挿入
def insert_sample(smp:Sample):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("""
        INSERT INTO samples (
            sample_id,source_event_id,human_id,form,parameters,location,remarks,created_at
        ) VALUES (?,?,?,?,?,?,?,?)
    """,(
        smp.sample_id,smp.source_event_id,smp.human_id,smp.form,json.dumps(smp.parameters),smp.location,smp.remarks,smp.created_at.isoformat()
    ))
    extract_and_save_tags("Sample",smp.sample_id,smp.remarks,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# 測定データの挿入
def insert_measurement(msr:Measurement):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("""
        INSERT INTO measurements (
            measurement_id,sample_id,measurement_type,conditions,raw_data_path,
            processed_data_path,extracted_features,operator,measured_at,remarks,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """,(
        msr.measurement_id,msr.sample_id,msr.measurement_type,json.dumps(msr.conditions),
        msr.raw_data_path,msr.processed_data_path,json.dumps(msr.extracted_features),
        msr.operator,msr.measured_at.isoformat(),msr.remarks,msr.created_at.isoformat()
    ))
    extract_and_save_tags("Measurement",msr.measurement_id,msr.remarks,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# 比較図の挿入
def insert_comparison_figure(fig:ComparisonFigure):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("""
        INSERT INTO comparison_figures (
            figure_id,title,plot_script_path,output_image_path,remarks,created_at
        ) VALUES (?,?,?,?,?,?)
    """,(
        fig.figure_id,fig.title,fig.plot_script_path,fig.output_image_path,fig.remarks,fig.created_at.isoformat()
    ))
    for mid in fig.measurement_ids:
        cursor.execute("INSERT INTO comparison_measurements (figure_id,measurement_id) VALUES (?,?)",(fig.figure_id,mid))
    extract_and_save_tags("ComparisonFigure",fig.figure_id,fig.remarks,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# 物質メタデータの挿入
def insert_material(mat:Material):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("""
        INSERT INTO materials (
            material_id,name,properties,reference_literature_id,cif_file_path,remarks,created_at
        ) VALUES (?,?,?,?,?,?,?)
    """,(
        mat.material_id,mat.name,json.dumps(mat.properties),mat.reference_literature_id,mat.cif_file_path,mat.remarks,mat.created_at.isoformat()
    ))
    for imid in mat.impurity_material_ids:
        cursor.execute("INSERT INTO material_relations (material_id,related_material_id,relation_type) VALUES (?,?,'impurity')",(mat.material_id,imid))
    for pmid in mat.polymorph_material_ids:
        cursor.execute("INSERT INTO material_relations (material_id,related_material_id,relation_type) VALUES (?,?,'polymorph')",(mat.material_id,pmid))
    extract_and_save_tags("Material",mat.material_id,mat.remarks,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# タスクの挿入
def insert_task(tsk:Task):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("""
        INSERT INTO tasks (
            task_id,title,status,related_entity_type,related_entity_id,due_date,remarks,created_at
        ) VALUES (?,?,?,?,?,?,?,?)
    """,(
        tsk.task_id,tsk.title,tsk.status,tsk.related_entity_type,tsk.related_entity_id,tsk.due_date,tsk.remarks,tsk.created_at.isoformat()
    ))
    extract_and_save_tags("Task",tsk.task_id,tsk.remarks,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# 開発フィードバック/エラーログの挿入
def insert_developer_log(log_id:str,log_type:str,title:str,content:str,page_name:str,status:str="Open"):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("""
        INSERT INTO developer_logs (log_id,log_type,title,content,page_name,status,created_at)
        VALUES (?,?,?,?,?,?,?)
    """,(log_id,log_type,title,content,page_name,status,datetime.now().isoformat()))
    conn.commit()
    conn.close()
    sync_obsidian()

# 文献の更新
def update_literature(lit:Literature):
    conn=get_connection()
    cursor=conn.cursor()
    now=datetime.now().isoformat()
    cursor.execute("""
        UPDATE literatures SET
            literature_type=?,title=?,authors=?,venue=?,publication_year=?,volume=?,parameters=?,
            doi=?,pdf_file_path=?,remarks=?,updated_at=?
        WHERE literature_id=?
    """,(
        lit.literature_type,lit.title,lit.authors,lit.venue,lit.publication_year,lit.volume,json.dumps(lit.parameters),
        lit.doi,lit.pdf_file_path,lit.remarks,now,lit.literature_id
    ))
    extract_and_save_tags("Literature",lit.literature_id,lit.remarks,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# イベントの更新
def update_event(evt:Event):
    conn=get_connection()
    cursor=conn.cursor()
    now=datetime.now().isoformat()
    cursor.execute("""
        UPDATE events SET
            project_id=?,target_material=?,event_type=?,motivation=?,parameters=?,remarks=?,updated_at=?
        WHERE event_id=?
    """,(
        evt.project_id,evt.target_material,evt.event_type,evt.motivation,json.dumps(evt.parameters),evt.remarks,now,evt.event_id
    ))
    cursor.execute("DELETE FROM event_inputs WHERE event_id=?",(evt.event_id,))
    for sid in evt.input_sample_ids:
        cursor.execute("INSERT INTO event_inputs (event_id,sample_id) VALUES (?,?)",(evt.event_id,sid))
    cursor.execute("DELETE FROM event_references WHERE event_id=?",(evt.event_id,))
    for reid in evt.reference_event_ids:
        cursor.execute("INSERT INTO event_references (event_id,ref_event_id) VALUES (?,?)",(evt.event_id,reid))
    cursor.execute("DELETE FROM event_literatures WHERE event_id=?",(evt.event_id,))
    for lid in evt.reference_literature_ids:
        cursor.execute("INSERT INTO event_literatures (event_id,literature_id) VALUES (?,?)",(evt.event_id,lid))
    extract_and_save_tags("Event",evt.event_id,evt.remarks,cursor)
    extract_and_save_tags("Event",evt.event_id,evt.motivation,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# サンプルの更新
def update_sample(smp:Sample):
    conn=get_connection()
    cursor=conn.cursor()
    now=datetime.now().isoformat()
    cursor.execute("""
        UPDATE samples SET
            source_event_id=?,human_id=?,form=?,parameters=?,location=?,remarks=?,updated_at=?
        WHERE sample_id=?
    """,(
        smp.source_event_id,smp.human_id,smp.form,json.dumps(smp.parameters),smp.location,smp.remarks,now,smp.sample_id
    ))
    extract_and_save_tags("Sample",smp.sample_id,smp.remarks,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# 測定データの更新
def update_measurement(msr:Measurement):
    conn=get_connection()
    cursor=conn.cursor()
    now=datetime.now().isoformat()
    cursor.execute("""
        UPDATE measurements SET
            sample_id=?,measurement_type=?,conditions=?,raw_data_path=?,
            processed_data_path=?,extracted_features=?,operator=?,
            measured_at=?,remarks=?,updated_at=?
        WHERE measurement_id=?
    """,(
        msr.sample_id,msr.measurement_type,json.dumps(msr.conditions),
        msr.raw_data_path,msr.processed_data_path,json.dumps(msr.extracted_features),
        msr.operator,msr.measured_at.isoformat(),msr.remarks,now,msr.measurement_id
    ))
    extract_and_save_tags("Measurement",msr.measurement_id,msr.remarks,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# 比較図の更新
def update_comparison_figure(fig:ComparisonFigure):
    conn=get_connection()
    cursor=conn.cursor()
    now=datetime.now().isoformat()
    cursor.execute("""
        UPDATE comparison_figures SET
            title=?,plot_script_path=?,output_image_path=?,remarks=?,updated_at=?
        WHERE figure_id=?
    """,(
        fig.title,fig.plot_script_path,fig.output_image_path,fig.remarks,now,fig.figure_id
    ))
    cursor.execute("DELETE FROM comparison_measurements WHERE figure_id=?",(fig.figure_id,))
    for mid in fig.measurement_ids:
        cursor.execute("INSERT INTO comparison_measurements (figure_id,measurement_id) VALUES (?,?)",(fig.figure_id,mid))
    extract_and_save_tags("ComparisonFigure",fig.figure_id,fig.remarks,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# 物質メタデータの更新
def update_material(mat:Material):
    conn=get_connection()
    cursor=conn.cursor()
    now=datetime.now().isoformat()
    cursor.execute("""
        UPDATE materials SET
            name=?,properties=?,reference_literature_id=?,cif_file_path=?,remarks=?,updated_at=?
        WHERE material_id=?
    """,(
        mat.name,json.dumps(mat.properties),mat.reference_literature_id,mat.cif_file_path,mat.remarks,now,mat.material_id
    ))
    cursor.execute("DELETE FROM material_relations WHERE material_id=?",(mat.material_id,))
    for imid in mat.impurity_material_ids:
        cursor.execute("INSERT INTO material_relations (material_id,related_material_id,relation_type) VALUES (?,?,'impurity')",(mat.material_id,imid))
    for pmid in mat.polymorph_material_ids:
        cursor.execute("INSERT INTO material_relations (material_id,related_material_id,relation_type) VALUES (?,?,'polymorph')",(mat.material_id,pmid))
    extract_and_save_tags("Material",mat.material_id,mat.remarks,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# タスクの更新
def update_task(tsk:Task):
    conn=get_connection()
    cursor=conn.cursor()
    now=datetime.now().isoformat()
    cursor.execute("""
        UPDATE tasks SET
            title=?,status=?,related_entity_type=?,related_entity_id=?,due_date=?,remarks=?,updated_at=?
        WHERE task_id=?
    """,(
        tsk.title,tsk.status,tsk.related_entity_type,tsk.related_entity_id,tsk.due_date,tsk.remarks,now,tsk.task_id
    ))
    extract_and_save_tags("Task",tsk.task_id,tsk.remarks,cursor)
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

# 開発フィードバック/エラーログのステータス更新
def update_developer_log_status(log_id:str,status:str):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("UPDATE developer_logs SET status=? WHERE log_id=?",(status,log_id))
    conn.commit()
    conn.close()
    sync_obsidian()

# 削除オペレーション
def delete_literature(lid:str):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("DELETE FROM literatures WHERE literature_id=?",(lid,))
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

def delete_event(eid:str):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("DELETE FROM events WHERE event_id=?",(eid,))
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

def delete_sample(sid:str):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("DELETE FROM samples WHERE sample_id=?",(sid,))
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

def delete_measurement(mid:str):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("DELETE FROM measurements WHERE measurement_id=?",(mid,))
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

def delete_comparison_figure(fid:str):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("DELETE FROM comparison_figures WHERE figure_id=?",(fid,))
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

def delete_material(mid:str):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("DELETE FROM materials WHERE material_id=?",(mid,))
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

def delete_task(tid:str):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE task_id=?",(tid,))
    conn.commit()
    conn.close()
    st.cache_data.clear()
    sync_obsidian()

def delete_developer_log(log_id:str):
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("DELETE FROM developer_logs WHERE log_id=?",(log_id,))
    conn.commit()
    conn.close()
    sync_obsidian()

# データ取得処理（st.cache_dataを適用）
@st.cache_data
def fetch_all_literatures()->List[Dict]:
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("SELECT * FROM literatures ORDER BY COALESCE(updated_at,created_at) DESC")
    rows=cursor.fetchall()
    res=[]
    for row in rows:
        d=dict(row)
        lit_id=d["literature_id"]
        cursor.execute("SELECT t.tag_name FROM tags t JOIN entity_tags et ON t.tag_id=et.tag_id WHERE et.entity_type='Literature' AND et.entity_id=?",(lit_id,))
        d["tags"]=[r[0] for r in cursor.fetchall()]
        res.append(d)
    conn.close()
    return res

@st.cache_data
def fetch_all_events()->List[Dict]:
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("SELECT * FROM events ORDER BY COALESCE(updated_at,created_at) DESC")
    rows=cursor.fetchall()
    res=[]
    for row in rows:
        d=dict(row)
        eid=d["event_id"]
        cursor.execute("SELECT sample_id FROM event_inputs WHERE event_id=?",(eid,))
        d["input_sample_ids"]=[r[0] for r in cursor.fetchall()]
        d["input_sample_id"]=d["input_sample_ids"][0] if d["input_sample_ids"] else None
        cursor.execute("SELECT ref_event_id FROM event_references WHERE event_id=?",(eid,))
        d["reference_event_ids"]=[r[0] for r in cursor.fetchall()]
        d["reference_event_id"]=d["reference_event_ids"][0] if d["reference_event_ids"] else None
        cursor.execute("SELECT literature_id FROM event_literatures WHERE event_id=?",(eid,))
        d["reference_literature_ids"]=[r[0] for r in cursor.fetchall()]
        d["reference_literature_id"]=d["reference_literature_ids"][0] if d["reference_literature_ids"] else None
        cursor.execute("SELECT t.tag_name FROM tags t JOIN entity_tags et ON t.tag_id=et.tag_id WHERE et.entity_type='Event' AND et.entity_id=?",(eid,))
        d["tags"]=[r[0] for r in cursor.fetchall()]
        res.append(d)
    conn.close()
    return res

@st.cache_data
def fetch_all_samples()->List[Dict]:
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("SELECT * FROM samples ORDER BY COALESCE(updated_at,created_at) DESC")
    rows=cursor.fetchall()
    res=[]
    for row in rows:
        d=dict(row)
        sid=d["sample_id"]
        cursor.execute("SELECT t.tag_name FROM tags t JOIN entity_tags et ON t.tag_id=et.tag_id WHERE et.entity_type='Sample' AND et.entity_id=?",(sid,))
        d["tags"]=[r[0] for r in cursor.fetchall()]
        res.append(d)
    conn.close()
    return res

@st.cache_data
def fetch_all_measurements()->List[Dict]:
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("SELECT * FROM measurements ORDER BY COALESCE(updated_at,created_at) DESC")
    rows=cursor.fetchall()
    res=[]
    for row in rows:
        d=dict(row)
        mid=d["measurement_id"]
        cursor.execute("SELECT t.tag_name FROM tags t JOIN entity_tags et ON t.tag_id=et.tag_id WHERE et.entity_type='Measurement' AND et.entity_id=?",(mid,))
        d["tags"]=[r[0] for r in cursor.fetchall()]
        res.append(d)
    conn.close()
    return res

@st.cache_data
def fetch_all_comparison_figures()->List[Dict]:
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("SELECT * FROM comparison_figures ORDER BY COALESCE(updated_at,created_at) DESC")
    rows=cursor.fetchall()
    res=[]
    for row in rows:
        d=dict(row)
        fid=d["figure_id"]
        cursor.execute("SELECT measurement_id FROM comparison_measurements WHERE figure_id=?",(fid,))
        d["measurement_ids"]=[r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT t.tag_name FROM tags t JOIN entity_tags et ON t.tag_id=et.tag_id WHERE et.entity_type='ComparisonFigure' AND et.entity_id=?",(fid,))
        d["tags"]=[r[0] for r in cursor.fetchall()]
        res.append(d)
    conn.close()
    return res

@st.cache_data
def fetch_all_materials()->List[Dict]:
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("SELECT * FROM materials ORDER BY COALESCE(updated_at,created_at) DESC")
    rows=cursor.fetchall()
    res=[]
    for row in rows:
        d=dict(row)
        mid=d["material_id"]
        cursor.execute("SELECT related_material_id FROM material_relations WHERE material_id=? AND relation_type='impurity'",(mid,))
        d["impurity_material_ids"]=[r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT related_material_id FROM material_relations WHERE material_id=? AND relation_type='polymorph'",(mid,))
        d["polymorph_material_ids"]=[r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT t.tag_name FROM tags t JOIN entity_tags et ON t.tag_id=et.tag_id WHERE et.entity_type='Material' AND et.entity_id=?",(mid,))
        d["tags"]=[r[0] for r in cursor.fetchall()]
        res.append(d)
    conn.close()
    return res

@st.cache_data
def fetch_all_tasks()->List[Dict]:
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("SELECT * FROM tasks ORDER BY COALESCE(updated_at,created_at) DESC")
    rows=cursor.fetchall()
    res=[]
    for row in rows:
        d=dict(row)
        tid=d["task_id"]
        cursor.execute("SELECT t.tag_name FROM tags t JOIN entity_tags et ON t.tag_id=et.tag_id WHERE et.entity_type='Task' AND et.entity_id=?",(tid,))
        d["tags"]=[r[0] for r in cursor.fetchall()]
        res.append(d)
    conn.close()
    return res

# 開発フィードバック/エラーログの全件取得
def fetch_all_developer_logs()->List[Dict]:
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("SELECT * FROM developer_logs ORDER BY created_at DESC")
    rows=cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
