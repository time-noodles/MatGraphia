import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from schemas import Literature, Event, Sample, Measurement, ComparisonFigure, Material

DB_PATH = "data/matgraphia.db"


def _has_column(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table_name})")
    cols = cursor.fetchall()
    return any(col[1] == column_name for col in cols)


def _ensure_column(cursor: sqlite3.Cursor, table_name: str, column_name: str, column_type: str):
    if not _has_column(cursor, table_name, column_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

def get_connection() -> sqlite3.Connection:
    """SQLiteの接続を取得（結果を辞書として扱えるよう設定）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """初期化：SQLiteのテーブル(v6.4 DAGモデル)を生成する"""
    import os
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. literatures
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
        created_at DATETIME
    )
    """)
    
    # 2. events
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        event_id TEXT PRIMARY KEY,
        project_id TEXT,
        target_material TEXT,
        event_type TEXT,
        input_sample_id TEXT,
        reference_event_id TEXT,
        reference_literature_id TEXT,
        input_sample_ids TEXT,
        reference_event_ids TEXT,
        reference_literature_ids TEXT,
        motivation TEXT,
        parameters TEXT,  -- JSON string
        remarks TEXT,
        created_at DATETIME,
        FOREIGN KEY(input_sample_id) REFERENCES samples(sample_id),
        FOREIGN KEY(reference_event_id) REFERENCES events(event_id),
        FOREIGN KEY(reference_literature_id) REFERENCES literatures(literature_id)
    )
    """)

    # 既存DB向けの後方互換マイグレーション
    _ensure_column(cursor, "literatures", "venue", "TEXT")
    _ensure_column(cursor, "literatures", "publication_year", "INTEGER")
    _ensure_column(cursor, "literatures", "volume", "TEXT")
    _ensure_column(cursor, "literatures", "parameters", "TEXT")
    _ensure_column(cursor, "events", "input_sample_ids", "TEXT")
    _ensure_column(cursor, "events", "reference_event_ids", "TEXT")
    _ensure_column(cursor, "events", "reference_literature_ids", "TEXT")
    
    # 3. samples
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
        FOREIGN KEY(source_event_id) REFERENCES events(event_id)
    )
    """)

    _ensure_column(cursor, "samples", "parameters", "TEXT")
    
    # 4. measurements
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS measurements (
        measurement_id TEXT PRIMARY KEY,
        sample_id TEXT,
        measurement_type TEXT,
        conditions TEXT, -- JSON string
        raw_data_path TEXT,
        processed_data_path TEXT,
        extracted_features TEXT, -- JSON string
        operator TEXT,
        measured_at DATE,
        remarks TEXT,
        created_at DATETIME,
        FOREIGN KEY(sample_id) REFERENCES samples(sample_id)
    )
    """)
    
    # 5. comparison_figures
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS comparison_figures (
        figure_id TEXT PRIMARY KEY,
        title TEXT,
        measurement_ids TEXT, -- JSON string array
        plot_script_path TEXT,
        output_image_path TEXT,
        remarks TEXT,
        created_at DATETIME
    )
    """)
    
    # 6. materials
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS materials (
        material_id TEXT PRIMARY KEY,
        name TEXT,
        properties TEXT, -- JSON string
        reference_literature_id TEXT,
        impurity_material_ids TEXT,
        polymorph_material_ids TEXT,
        cif_file_path TEXT,
        remarks TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(reference_literature_id) REFERENCES literatures(literature_id)
    )
    """)
    
    _ensure_column(cursor, "literatures", "updated_at", "DATETIME")
    _ensure_column(cursor, "events", "updated_at", "DATETIME")
    _ensure_column(cursor, "samples", "updated_at", "DATETIME")
    _ensure_column(cursor, "measurements", "updated_at", "DATETIME")
    _ensure_column(cursor, "comparison_figures", "updated_at", "DATETIME")
    _ensure_column(cursor, "materials", "updated_at", "DATETIME")
    _ensure_column(cursor, "materials", "cif_file_path", "TEXT")
    _ensure_column(cursor, "materials", "impurity_material_ids", "TEXT")
    _ensure_column(cursor, "materials", "polymorph_material_ids", "TEXT")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()
    print("[Info] Database initialization completed.")

def get_setting(key: str, default: Any = None) -> Any:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key: str, value: Any):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

# ----------------------------------------------------
# データ登録機能 (Insert Operations)
# ----------------------------------------------------
def insert_literature(lit: Literature):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO literatures (
            literature_id, literature_type, title, authors, venue, publication_year, volume, parameters, doi, pdf_file_path, remarks, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        lit.literature_id, lit.literature_type, lit.title, lit.authors, lit.venue,
        lit.publication_year, lit.volume, json.dumps(lit.parameters), lit.doi, lit.pdf_file_path, lit.remarks, lit.created_at.isoformat()
    ))
    conn.commit()
    conn.close()

def insert_event(evt: Event):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO events (
            event_id, project_id, target_material, event_type, input_sample_id, 
            reference_event_id, reference_literature_id, input_sample_ids, reference_event_ids, reference_literature_ids,
            motivation, parameters, remarks, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        evt.event_id, evt.project_id, evt.target_material, evt.event_type, evt.input_sample_id,
        evt.reference_event_id, evt.reference_literature_id,
        json.dumps(evt.input_sample_ids), json.dumps(evt.reference_event_ids), json.dumps(evt.reference_literature_ids),
        evt.motivation,
        json.dumps(evt.parameters), evt.remarks, evt.created_at.isoformat()
    ))
    conn.commit()
    conn.close()

def insert_sample(smp: Sample):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO samples (
            sample_id, source_event_id, human_id, form, parameters, location, remarks, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        smp.sample_id, smp.source_event_id, smp.human_id, smp.form, json.dumps(smp.parameters), smp.location,
        smp.remarks, smp.created_at.isoformat()
    ))
    conn.commit()
    conn.close()

def insert_measurement(msr: Measurement):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO measurements (
            measurement_id, sample_id, measurement_type, conditions, raw_data_path,
            processed_data_path, extracted_features, operator, measured_at, remarks, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        msr.measurement_id, msr.sample_id, msr.measurement_type, json.dumps(msr.conditions),
        msr.raw_data_path, msr.processed_data_path, json.dumps(msr.extracted_features),
        msr.operator, msr.measured_at.isoformat(), msr.remarks, msr.created_at.isoformat()
    ))
    conn.commit()
    conn.close()

def insert_material(mat: Material):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO materials (
            material_id, name, properties, reference_literature_id, impurity_material_ids, polymorph_material_ids,
            cif_file_path, remarks, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        mat.material_id, mat.name, json.dumps(mat.properties),
        mat.reference_literature_id, json.dumps(mat.impurity_material_ids), json.dumps(mat.polymorph_material_ids),
        mat.cif_file_path, mat.remarks, mat.created_at.isoformat()
    ))
    conn.commit()
    conn.close()

# ----------------------------------------------------
# データ更新機能 (Update Operations)
# ----------------------------------------------------
def update_literature(lit: Literature):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE literatures SET
            literature_type = ?, title = ?, authors = ?, venue = ?, publication_year = ?, volume = ?, parameters = ?,
            doi = ?, pdf_file_path = ?, remarks = ?, updated_at = ?
        WHERE literature_id = ?
    """, (
        lit.literature_type, lit.title, lit.authors, lit.venue, lit.publication_year, lit.volume, json.dumps(lit.parameters),
        lit.doi, lit.pdf_file_path, lit.remarks, now, lit.literature_id
    ))
    conn.commit()
    conn.close()

def update_event(evt: Event):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE events SET
            project_id = ?, target_material = ?, event_type = ?, input_sample_id = ?,
            reference_event_id = ?, reference_literature_id = ?, motivation = ?,
            input_sample_ids = ?, reference_event_ids = ?, reference_literature_ids = ?,
            parameters = ?, remarks = ?, updated_at = ?
        WHERE event_id = ?
    """, (
        evt.project_id, evt.target_material, evt.event_type, evt.input_sample_id,
        evt.reference_event_id, evt.reference_literature_id, evt.motivation,
        json.dumps(evt.input_sample_ids), json.dumps(evt.reference_event_ids), json.dumps(evt.reference_literature_ids),
        json.dumps(evt.parameters), evt.remarks, now, evt.event_id
    ))
    conn.commit()
    conn.close()

def update_sample(smp: Sample):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE samples SET
            source_event_id = ?, human_id = ?, form = ?, parameters = ?, location = ?, remarks = ?, updated_at = ?
        WHERE sample_id = ?
    """, (
        smp.source_event_id, smp.human_id, smp.form, json.dumps(smp.parameters), smp.location, smp.remarks, now, smp.sample_id
    ))
    conn.commit()
    conn.close()

def update_measurement(msr: Measurement):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE measurements SET
            sample_id = ?, measurement_type = ?, conditions = ?, raw_data_path = ?,
            processed_data_path = ?, extracted_features = ?, operator = ?,
            measured_at = ?, remarks = ?, updated_at = ?
        WHERE measurement_id = ?
    """, (
        msr.sample_id, msr.measurement_type, json.dumps(msr.conditions),
        msr.raw_data_path, msr.processed_data_path, json.dumps(msr.extracted_features),
        msr.operator, msr.measured_at.isoformat(), msr.remarks, now, msr.measurement_id
    ))
    conn.commit()
    conn.close()

def update_material(mat: Material):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE materials SET
            name = ?, properties = ?, reference_literature_id = ?, impurity_material_ids = ?, polymorph_material_ids = ?,
            cif_file_path = ?, remarks = ?, updated_at = ?
        WHERE material_id = ?
    """, (
        mat.name, json.dumps(mat.properties), mat.reference_literature_id,
        json.dumps(mat.impurity_material_ids), json.dumps(mat.polymorph_material_ids),
        mat.cif_file_path, mat.remarks, now, mat.material_id
    ))
    conn.commit()
    conn.close()

# ----------------------------------------------------
# データ削除機能 (Delete Operations)
# ----------------------------------------------------
def delete_literature(lid: str):
    conn = get_connection()
    cursor = conn.cursor()
    # FK参照が残っていると削除できないため、先に参照を解消する
    cursor.execute("UPDATE events SET reference_literature_id = NULL WHERE reference_literature_id = ?", (lid,))
    cursor.execute("UPDATE materials SET reference_literature_id = NULL WHERE reference_literature_id = ?", (lid,))

    # 後方互換: 配列参照(JSON)に残っているIDも除去
    cursor.execute("SELECT event_id, reference_literature_ids FROM events")
    rows = cursor.fetchall()
    for row in rows:
        raw_ids = row[1]
        try:
            ids = json.loads(raw_ids) if raw_ids else []
        except Exception:
            ids = []
        if not isinstance(ids, list):
            ids = []
        new_ids = [x for x in ids if x != lid]
        if new_ids != ids:
            cursor.execute(
                "UPDATE events SET reference_literature_ids = ? WHERE event_id = ?",
                (json.dumps(new_ids), row[0])
            )

    cursor.execute("DELETE FROM literatures WHERE literature_id = ?", (lid,))
    conn.commit()
    conn.close()

def delete_event(eid: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM events WHERE event_id = ?", (eid,))
    conn.commit()
    conn.close()

def delete_sample(sid: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM samples WHERE sample_id = ?", (sid,))
    conn.commit()
    conn.close()

def delete_measurement(mid: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM measurements WHERE measurement_id = ?", (mid,))
    conn.commit()
    conn.close()

def delete_material(mid: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM materials WHERE material_id = ?", (mid,))
    conn.commit()
    conn.close()

# ----------------------------------------------------
# データ取得機能 (Select Operations)
# ----------------------------------------------------
def fetch_all_literatures() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM literatures ORDER BY COALESCE(updated_at, created_at) DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def fetch_all_events() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events ORDER BY COALESCE(updated_at, created_at) DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def fetch_all_samples() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM samples ORDER BY COALESCE(updated_at, created_at) DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def insert_comparison_figure(fig: ComparisonFigure):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO comparison_figures (
            figure_id, title, measurement_ids, plot_script_path, output_image_path, remarks, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        fig.figure_id, fig.title, json.dumps(fig.measurement_ids), fig.plot_script_path,
        fig.output_image_path, fig.remarks, fig.created_at.isoformat()
    ))
    conn.commit()
    conn.close()

def fetch_all_measurements() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM measurements ORDER BY COALESCE(updated_at, created_at) DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def fetch_all_comparison_figures() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM comparison_figures ORDER BY COALESCE(updated_at, created_at) DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def fetch_all_materials() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM materials ORDER BY COALESCE(updated_at, created_at) DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
