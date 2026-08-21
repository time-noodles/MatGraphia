import pytest
import os
import sys
import sqlite3
from datetime import datetime, date

# プロジェクトルートパスをインポートパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import database as db
from schemas import Literature, Event, Sample, Measurement, Material, Task
from ui.helpers import get_atomic_weight, calc_molecular_weight

@pytest.fixture(autouse=True)
def setup_tmp_db(tmp_path, monkeypatch):
    """Google Drive上のSQLite Bus Errorを防ぐため、pytest実行中のみtmp_pathにDBを作成"""
    tmp_db_file = str(tmp_path / "test_matgraphia.db")
    monkeypatch.setattr(db, "DB_PATH", tmp_db_file)
    db.init_db()

def test_database_init_and_draft_migration():
    """データベース初期化およびis_draft/parent_task_id等のカラム自動マイグレーションのテスト"""
    db.init_db()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # 全テーブルにis_draftカラムが存在することを確認
    for tbl in ["literatures", "events", "samples", "measurements", "materials"]:
        cursor.execute(f"PRAGMA table_info({tbl})")
        cols = [col[1] for col in cursor.fetchall()]
        assert "is_draft" in cols, f"{tbl} に is_draft カラムが存在しません"
        
    # tasksテーブルにparent_task_idカラムが存在することを確認
    cursor.execute("PRAGMA table_info(tasks)")
    task_cols = [col[1] for col in cursor.fetchall()]
    assert "parent_task_id" in task_cols, "tasks に parent_task_id カラムが存在しません"
    conn.close()

def test_element_atomic_weight_calc():
    """元素・化学式の原子量 (M.W.) 自動計算ロジックのテスト"""
    # 1. 単体元素の原子量取得
    w_bi = get_atomic_weight("Bi")
    assert w_bi is not None and round(w_bi, 2) == 208.98
    
    w_te = get_atomic_weight("Te")
    assert w_te is not None and round(w_te, 2) == 127.60
    
    # 2. 化合物の分子量計算
    mw = calc_molecular_weight("Bi2Te3")
    assert mw is not None and round(mw, 2) == 800.76

def test_task_parent_subtask_hierarchy():
    """親タスクと小タスク（サブタスク）の階層構造およびDB挿入・検索のテスト"""
    db.init_db()
    
    # 親タスクの作成
    parent_task = Task(
        title="[テスト] 親実験タスク",
        status="In Progress",
        due_date=date.today().isoformat(),
        remarks="親タスクのテスト"
    )
    db.insert_task(parent_task)
    
    # 小タスク（サブタスク）の作成
    sub_task = Task(
        parent_task_id=parent_task.task_id,
        title="[テスト] 小タスク: 元素秤量",
        status="Todo",
        due_date=date.today().isoformat(),
        remarks="サブタスクのテスト"
    )
    db.insert_task(sub_task)
    
    all_tasks = db.fetch_all_tasks()
    task_ids = [t["task_id"] for t in all_tasks]
    assert parent_task.task_id in task_ids
    assert sub_task.task_id in task_ids
    
    fetched_sub = next(t for t in all_tasks if t["task_id"] == sub_task.task_id)
    assert fetched_sub["parent_task_id"] == parent_task.task_id

def test_draft_registration_flag():
    """仮登録（下書き保存）フラグの検証テスト"""
    db.init_db()
    
    draft_lit = Literature(
        literature_type="Paper",
        doi="-",
        remarks="仮保存の文献",
        is_draft=True
    )
    db.insert_literature(draft_lit)
    
    all_lits = db.fetch_all_literatures()
    fetched_lit = next(l for l in all_lits if l["literature_id"] == draft_lit.literature_id)
    assert fetched_lit["is_draft"] == 1 or fetched_lit["is_draft"] is True

def test_symple_plot_integration():
    """symple_plot ライブラリの統合機能テスト"""
    import sys
    sys.path.append('/home/kotoyumin/gdrive_storage/Python-Scripts/libs/custom_lib')
    sys.path.append('/home/kotoyumin/gdrive_storage/Python-Scripts/libs')
    from symple_plot import create_symple_plots
    import numpy as np
    
    x = np.linspace(0, 10, 50)
    y = np.sin(x)
    fig, sp = create_symple_plots(nrows=1, ncols=1, figsize=(5, 3), style='paper')
    sp.plot([x], [y], xlabel="X-axis", ylabel="Y-axis", label=["Sin wave"], color=["#1f77b4"])
    sp.ax.set_title("Test Plot")
    assert fig is not None and sp is not None
