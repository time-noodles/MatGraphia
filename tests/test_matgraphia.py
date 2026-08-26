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
    parent_lib_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    custom_lib_dir = os.path.join(parent_lib_dir, "custom_lib")
    if custom_lib_dir not in sys.path: sys.path.append(custom_lib_dir)
    if parent_lib_dir not in sys.path: sys.path.append(parent_lib_dir)

    from symple_plot import create_symple_plots
    import numpy as np
    
    x = np.linspace(0, 10, 50)
    y = np.sin(x)
    fig, sp = create_symple_plots(nrows=1, ncols=1, figsize=(5, 3), style='paper')
    sp.plot([x], [y], xlabel="X-axis", ylabel="Y-axis", label=["Sin wave"], color=["#1f77b4"])
    sp.ax.set_title("Test Plot")
    assert fig is not None and sp is not None

def test_sem_composition_ratio():
    """SEM EDX at% 組成比 (化学量論比) 計算のテスト"""
    from plugins.measurements.sem import calculate_composition_ratio
    rows = [
        {"element": "Cu", "at_percent": 25.0},
        {"element": "Cr", "at_percent": 25.0},
        {"element": "S", "at_percent": 50.0}
    ]
    # S = 2.0 に固定して計算
    ratio_rows, formula_str, factor, err = calculate_composition_ratio(rows, ["S"], target_constant=2.0)
    assert err is None
    assert formula_str == "Cu1Cr1S2"
    assert round(factor, 4) == 0.04

def test_task_literature_link():
    """タスクへの文献(Literature)紐付けのテスト"""
    db.init_db()
    lit = Literature(
        literature_type="Paper",
        title="テスト文献論文",
        doi="10.1000/test.doi",
        remarks="テスト用"
    )
    db.insert_literature(lit)
    
    task = Task(
        title="[テスト] 論文調査タスク",
        status="Todo",
        related_entity_type="Literature",
        related_entity_id=lit.literature_id,
        due_date=date.today().isoformat()
    )
    db.insert_task(task)
    
    all_tasks = db.fetch_all_tasks()
    fetched = next(t for t in all_tasks if t["task_id"] == task.task_id)
    assert fetched["related_entity_type"] == "Literature"
    assert fetched["related_entity_id"] == lit.literature_id


def test_all_measurement_plugins_discovery():
    """全測定プラグインが自動検出・ロード可能かテスト"""
    import plugin_manager as pm
    schemas = pm.get_measurement_schemas()
    expected_types = [
        "XRD", "SEM", "Microscope", "Raman", "Laue", 
        "Electrochemistry", "PPMS_4probe", "PPMS_6probe", 
        "ShiftCurrent", "MPMS"
    ]
    for et in expected_types:
        assert et in schemas, f"測定プラグイン {et} がロードされていません"


def test_ppms_6probe_hall_calculation():
    """PPMS 6端子 ホール係数 RH および キャリア密度 n の算定検証 (PPMS/hall_2peace.py 準拠)"""
    from plugins.measurements.ppms_6probe import calculate_hall_parameters
    import numpy as np
    field_oe = np.array([-90000, -45000, 0, 45000, 90000])
    vxy_v = np.array([-0.0018, -0.0009, 0.0, 0.0009, 0.0018])
    res = calculate_hall_parameters(field_oe, vxy_v, thickness_cm=0.01, current_a=1e-4)
    assert res["rh"] > 0
    assert res["carrier_type"] == "p型 (正孔伝導)"
    assert res["n"] > 0


def test_mpms_mub_per_fu_conversion():
    """MPMS 磁気モーメント (emu) ➔ μ_B / f.u. 単位換算検証 (MPMS/test.ipynb 準拠)"""
    from plugins.measurements.mpms import convert_emu_to_mub_per_fu
    mub = convert_emu_to_mub_per_fu(moment_emu=0.01, sample_mass_g=0.01201, mol_weight_g_mol=179.662)
    assert mub > 0


def test_raman_background_removal():
    """Raman バックグラウンド除去処理の検証 (Raman/test.ipynb 準拠)"""
    from plugins.measurements.raman import remove_raman_background
    import numpy as np
    x = np.linspace(0, 100, 200)
    sig = np.sin(x/5) + x/10 + 2.0
    sig_clean = remove_raman_background(sig)
    assert len(sig_clean) == len(sig)


