"""
MatGraphia 物質メタデータ登録ビュー
TITLE: 🧪 物質の登録
ORDER: 3
"""
import os
import re
import hashlib
import importlib.util
import pandas as pd
import streamlit as st
import database as db
import file_manager as fm
import plugin_manager as pm
from schemas import Material
from ui.forms import render_dynamic_form
from ui.helpers import _normalize_cif_fraction_tokens, build_literature_label, log_errors

TITLE = "🧪 物質の登録"
ORDER = 3

def _load_measurement_plugin(measurement_type):
    filename = f"{str(measurement_type).lower()}.py"
    plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins", "measurements", filename)
    if not os.path.exists(plugin_path): return None
    spec = importlib.util.spec_from_file_location(f"measurement_plugin_{measurement_type}", plugin_path)
    if not spec or not spec.loader: return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _load_material_plugin(plugin_name):
    filename = f"{str(plugin_name).lower()}.py"
    plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins", "materials", filename)
    if not os.path.exists(plugin_path): return None
    spec = importlib.util.spec_from_file_location(f"material_plugin_{plugin_name}", plugin_path)
    if not spec or not spec.loader: return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _run_structure_preview(cif_bytes, cif_name):
    plugin = _load_material_plugin("structure_preview")
    if not plugin or not hasattr(plugin, "build_structure_preview"):
        return None, None, "結晶構造プレビュープラグインを読み込めませんでした。"
    try:
        return plugin.build_structure_preview(cif_bytes, cif_name)
    except Exception as e:
        return None, None, f"結晶構造プレビュープラグイン実行に失敗しました: {e}"

@st.cache_data(show_spinner=False)
def _cached_xrd_preview(cif_bytes, cif_name, conditions, material_name):
    xrd_plugin = _load_measurement_plugin("XRD")
    if not xrd_plugin or not hasattr(xrd_plugin, "simulate_xrd_for_cif_bytes"):
        return None, "XRDプラグインが読み込めないため、CIFプレビューは利用できません。", None, None
    sim_result, sim_err = xrd_plugin.simulate_xrd_for_cif_bytes(
        cif_bytes=cif_bytes,
        cif_name=cif_name,
        conditions=conditions,
        material_name=material_name,
    )
    png_bytes, plot_err = None, None
    if sim_result and hasattr(xrd_plugin, "render_simulated_xrd_plot_png"):
        png_bytes, plot_err = xrd_plugin.render_simulated_xrd_plot_png(sim_result)
    return sim_result, sim_err, png_bytes, plot_err

@log_errors("物質情報の登録")
def render():
    st.header("物質（Material）メタデータの登録")
    st.markdown("物質固有の物性値（Tc, Neel点等）や先行研究情報を登録します。")

    literatures = db.fetch_all_literatures()
    materials = db.fetch_all_materials()
    lit_options = {"選択なし (None)": None}
    for l in literatures:
        lit_options[build_literature_label(l)] = l["literature_id"]

    mat_options = {}
    for m in materials:
        mat_options[f"{m['name']} #{m['material_id'][:4]}"] = m["material_id"]

    # 変数の初期化
    btn_bot_mat_sub, btn_bot_mat_draft = False, False
    edited_prop_df = None
    selected_impurities, selected_polymorphs = [], []
    ref_lit, remarks = None, ""

    # Top Action Bar (最上部デュアルボタン)
    top_mcol1, top_mcol2 = st.columns(2)
    with top_mcol1:
        btn_top_mat_sub = st.button("✨ 物質情報を登録する (本登録)", type="primary", key="btn_mat_submit_top")
    with top_mcol2:
        btn_top_mat_draft = st.button("📝 下書き（仮登録）保存する", key="btn_mat_draft_top")

    st.write("---")

    active_step = st.session_state.get("active_step_jump", "")

    # 1. 基本情報 ＆ CIFファイル・3D構造プレビュー
    st.subheader("1. 基本情報 ＆ CIFファイル・3D構造プレビュー")
    if "1. 基本情報" in active_step:
        st.info("🎯 **【選択されたステップ: 1. 基本情報 ＆ CIF・3D構造】**")
    name = st.text_input("物質名 (必須 / 例: CuCrS2)", value="", key="draft_mat_name")
    uploaded_cif = st.file_uploader("CIFファイル(任意)のアップロード", type=["cif", "txt"], key="draft_mat_cif")
    cif_bytes_raw = uploaded_cif.getvalue() if uploaded_cif is not None else None
    cif_bytes = _normalize_cif_fraction_tokens(cif_bytes_raw) if cif_bytes_raw is not None else None
    
    if uploaded_cif is not None:
        st.write("---")
        st.markdown("**【CIFから結晶構造描画 (crystal_toolkit 3D)】**")
        if not cif_bytes:
            st.warning("CIFデータが空です。")
        else:
            cif_hash = hashlib.md5(cif_bytes).hexdigest()
            cache_key = f"struct_preview_{cif_hash}"
            if cache_key not in st.session_state:
                with st.spinner("crystal_toolkit で結晶構造を描画中..."):
                    graph_obj, graph_payload, graph_err = _run_structure_preview(cif_bytes, uploaded_cif.name)
                st.session_state[cache_key] = (graph_obj, graph_payload, graph_err)
            else:
                graph_obj, graph_payload, graph_err = st.session_state[cache_key]
            if graph_err:
                st.warning(graph_err)
            elif graph_payload:
                st.success("結晶構造の描画を生成しました。")
                dash_port = graph_payload.get("dash_port")
                if dash_port:
                    st.components.v1.iframe(f"http://127.0.0.1:{dash_port}", height=640, scrolling=True)
                else:
                    st.warning("3Dビューアの起動に失敗しました。")
                st.markdown("**Summary**")
                summary = dict(graph_payload["summary"])
                atom_counts = summary.pop("atom_counts", {})
                st.dataframe(pd.DataFrame([summary]), hide_index=True)
                if isinstance(atom_counts, dict) and atom_counts:
                    counts_df = pd.DataFrame(
                        [{"element": k, "count_in_unit_cell": v} for k, v in sorted(atom_counts.items())]
                    )
                    st.markdown("**Atom Counts in Unit Cell**")
                    st.dataframe(counts_df, hide_index=True)

    xrd_plugin = _load_measurement_plugin("XRD")
    if uploaded_cif is not None and xrd_plugin and hasattr(xrd_plugin, "simulate_xrd_for_cif_bytes"):
        st.write("---")
        st.markdown("**【CIFからXRDシミュレーション（登録前プレビュー）】**")
        c1, c2, c3 = st.columns(3)
        with c1:
            mat_xrd_mode = st.selectbox("シミュレーション種別", ["Powder", "TMDC c-axis Oriented"], key="mat_xrd_mode_preview")
        with c2:
            mat_xrd_target = st.selectbox("X-ray Target", ["CuKa", "MoKa", "CoKa", "FeKa"], key="mat_xrd_target_preview")
        with c3:
            mat_xrd_peak_width = st.number_input("Peak width (FWHM)", min_value=0.01, max_value=5.0, value=0.15, step=0.01, key="mat_xrd_peak_width_preview")
        c4, c5 = st.columns(2)
        with c4:
            mat_xrd_tth_min = st.number_input("2theta min", min_value=0.0, max_value=180.0, value=5.0, step=0.5, key="mat_xrd_tth_min_preview")
        with c5:
            mat_xrd_tth_max = st.number_input("2theta max", min_value=0.0, max_value=180.0, value=90.0, step=0.5, key="mat_xrd_tth_max_preview")
        preview_conditions = {
            "simulation_mode": mat_xrd_mode,
            "target": mat_xrd_target,
            "two_theta_min": float(mat_xrd_tth_min),
            "two_theta_max": float(mat_xrd_tth_max),
            "profile_step": 0.02,
            "peak_width": float(mat_xrd_peak_width),
        }
        try:
            with st.spinner("XRDパターンを生成中..."):
                sim_result, sim_err, png_bytes, plot_err = _cached_xrd_preview(
                    cif_bytes=cif_bytes,
                    cif_name=uploaded_cif.name,
                    conditions=preview_conditions,
                    material_name=name or "Unknown",
                )
            if sim_result:
                if png_bytes:
                    st.image(png_bytes, caption=f"XRD simulated pattern ({sim_result.get('mode')})")
                profile_df = pd.DataFrame({"two_theta": sim_result["profile"]["two_theta"], "intensity": sim_result["profile"]["intensity"]})
                profile_csv = profile_df.to_csv(index=False).encode("utf-8")
                st.download_button(label="XRDパターンをCSV保存", data=profile_csv, file_name="simulated_xrd.csv", mime="text/csv", key="btn_download_mat_xrd_csv")
        except Exception as e:
            st.error(f"XRDプレビューの生成に失敗しました: {e}")
    st.write("---")

    # 2. 物性パラメータ ＆ 不純物相・多形
    st.subheader("2. 物性パラメータ ＆ 不純物相・多形")
    if "2. 物性" in active_step:
        st.info("🎯 **【選択されたステップ: 2. 物性パラメータ ＆ 不純物相・多形】**")
    st.markdown("**【物性値・先行研究情報】**")
    prop_df_init = pd.DataFrame([{"Property": "Tc (K)", "Value": ""}, {"Property": "Tn (K)", "Value": ""}])
    edited_prop_df = st.data_editor(prop_df_init, num_rows="dynamic", hide_index=True, key="mat_prop_editor")
    st.markdown("**【関連物質リンク（オプション）】**")
    selected_impurities = st.multiselect("不純物として関連づける物質（オプション）", list(mat_options.keys()), key="mat_impurity_links")
    selected_polymorphs = st.multiselect("多型として関連づける物質（オプション）", list(mat_options.keys()), key="mat_polymorph_links")
    st.write("---")

    # 3. 関連文献 ＆ 登録実行
    st.subheader("3. 関連文献 ＆ 登録実行")
    if "3. 関連" in active_step:
        st.info("🎯 **【選択されたステップ: 3. 関連文献 ＆ 登録実行】**")
    ref_lit = st.selectbox("参照文献", list(lit_options.keys()), key="draft_mat_reflit")
    remarks = st.text_area("備考", key="draft_mat_remarks")

    # Bottom Action Bar (最下部デュアルボタン)
    st.write("")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        btn_bot_mat_sub = st.button("✨ 物質情報を登録する (本登録)", type="primary", key="btn_mat_submit_bot")
    with col_m2:
        btn_bot_mat_draft = st.button("📝 下書き（仮登録）保存する", key="btn_mat_draft_bot")



    def _execute_material_submit(is_draft_mode: bool):
        if not is_draft_mode and not name:
            st.error("物質名は必須です。")
            return
        properties = {}
        if edited_prop_df is not None and not edited_prop_df.empty:
            for _, row in edited_prop_df.iterrows():
                p_name = str(row.get("Property", "")).strip()
                p_val = str(row.get("Value", "")).strip()
                if p_name and p_val:
                    properties[p_name] = p_val
        impurity_ids = [mat_options[k] for k in selected_impurities if mat_options.get(k)]
        polymorph_ids = [mat_options[k] for k in selected_polymorphs if mat_options.get(k)]
        ref_lit_id = lit_options.get(ref_lit) if isinstance(lit_options, dict) else None
        try:
            mat = Material(
                name=name or ("Draft_Material" if is_draft_mode else "Material"),
                properties=properties,
                reference_literature_id=ref_lit_id,
                impurity_material_ids=impurity_ids,
                polymorph_material_ids=polymorph_ids,
                remarks=remarks or "",
                is_draft=is_draft_mode
            )
            if uploaded_cif and cif_bytes:
                cif_path = fm.save_material_file(mat.material_id, uploaded_cif.name, cif_bytes)
                mat.cif_file_path = cif_path
            db.insert_material(mat)
            if is_draft_mode:
                st.success(f"物質情報を下書き（仮登録）しました！データ管理画面で後から補完・本登録できます。(ID: {mat.material_id})")
            else:
                st.success(f"物質情報を本登録しました！ (ID: {mat.material_id})")
        except Exception as e:
            st.error(f"登録時にエラーが発生しました: {e}")

    if btn_top_mat_sub or btn_bot_mat_sub:
        _execute_material_submit(is_draft_mode=False)
    elif btn_top_mat_draft or btn_bot_mat_draft:
        _execute_material_submit(is_draft_mode=True)
