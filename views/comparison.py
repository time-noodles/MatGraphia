"""
MatGraphia 専用データ比較 ＆ 傾向分析ビュー
TITLE: ⚖️ データの比較 ＆ 傾向分析
ORDER: 7
"""
import os
import re
import pandas as pd
import streamlit as st
import database as db
import file_manager as fm
from ui.helpers import log_errors, build_sample_label, render_location_badge

TITLE = "⚖️ データの比較 ＆ 傾向分析"
ORDER = 7

def _load_measurement_plugin(measurement_type):
    import importlib.util
    filename = f"{str(measurement_type).lower()}.py"
    plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins", "measurements", filename)
    if not os.path.exists(plugin_path): return None
    spec = importlib.util.spec_from_file_location(f"measurement_plugin_{measurement_type}", plugin_path)
    if not spec or not spec.loader: return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@log_errors("データの比較 ＆ 傾向分析")
def render():
    st.header("⚖️ データの比較 ＆ 傾向分析 (Sample & Data Comparison)")
    st.markdown("登録されている複数のサンプル・物質・測定データ（XRD, SEM, MPMS, PPMS, Raman等）を選択し、合成条件・保管場所・物性パラメータの横並びマトリクス比較およびプロット重畳分析を行えます。")

    samples = db.fetch_all_samples()
    measurements = db.fetch_all_measurements()
    events = db.fetch_all_events()
    materials = db.fetch_all_materials()
    events_dict = {e["event_id"]: e for e in events}

    if not samples:
        st.warning("登録されているサンプルが存在しません。先にサンプルおよび測定データを登録してください。")
        return

    sample_options = {}
    for s in samples:
        label = build_sample_label(s, events_dict=events_dict, samples_list=samples)
        sample_options[label] = s["sample_id"]

    tab_sample_comp, tab_msr_overlay, tab_mat_comp = st.tabs([
        "🧪 試料(サンプル)間マトリクス比較", 
        "📈 測定データプロット重畳比較", 
        "🧱 物質(Material)特性比較"
    ])

    # 1. 試料(サンプル)間マトリクス比較
    with tab_sample_comp:
        st.subheader("🧪 選択サンプル基本情報・合成条件・保管場所 マトリクス")
        sample_multiselect = st.multiselect(
            "比較対象のサンプルを複数選択",
            options=list(sample_options.keys()),
            default=list(sample_options.keys())[:3] if len(sample_options) >= 3 else list(sample_options.keys()),
            key="comp_view_ms_samples"
        )
        
        if sample_multiselect:
            sel_sample_ids = [sample_options[lbl] for lbl in sample_multiselect]
            sel_samples = [s for s in samples if s["sample_id"] in sel_sample_ids]
            
            st.markdown("##### 📍 基本情報 ＆ 合成条件 ＆ 保管場所")
            comp_rows = []
            for s in sel_samples:
                s_event = events_dict.get(s.get("source_event_id"), {})
                comp_rows.append({
                    "Sample Human ID": s.get("human_id"),
                    "Form (形態)": s.get("form"),
                    "Target Material (物質)": s_event.get("target_material", "-"),
                    "Event Type (合成イベント)": s_event.get("event_type", "-"),
                    "Storage Location (保管場所)": s.get("location", "未指定"),
                    "登録日": str(s.get("created_at"))[:10]
                })
            st.dataframe(pd.DataFrame(comp_rows), hide_index=True)

            st.write("")
            st.markdown("##### 📍 各サンプルの保管場所ダイレクトリンク:")
            for s in sel_samples:
                c1, c2 = st.columns([1, 4])
                with c1: st.write(f"**{s['human_id']}**")
                with c2: render_location_badge(s.get("location"), key_prefix=f"page_comp_{s['sample_id'][:4]}")

    # 2. 測定データプロット重畳比較
    with tab_msr_overlay:
        st.subheader("📈 測定データプロットの重ね描き・定量比較")
        if not measurements:
            st.info("測定データがまだ登録されていません。")
        else:
            msr_types = sorted(list(set(m["measurement_type"] for m in measurements)))
            selected_type = st.selectbox("比較対象の測定タイプを選択", msr_types, key="comp_view_sb_msr_type")
            
            type_msrs = [m for m in measurements if m["measurement_type"] == selected_type]
            st.write(f"選択タイプの総登録件数: **{len(type_msrs)}** 件")
            
            if selected_type == "XRD":
                sim_list = []
                plugin = _load_measurement_plugin("XRD")
                for m in type_msrs:
                    s_obj = next((s for s in samples if s["sample_id"] == m["sample_id"]), None)
                    s_label = s_obj["human_id"] if s_obj else m["sample_id"][:4]
                    if m.get("raw_data_path") and plugin and hasattr(plugin, "parse_experimental_xrd"):
                        ex_tth, ex_int, _ = plugin.parse_experimental_xrd(m["raw_data_path"], data_base_dir=str(fm.BASE_DIR))
                        if ex_tth is not None and ex_int is not None:
                            sim_list.append({
                                "material_name": f"Sample: {s_label}",
                                "profile": {"two_theta": ex_tth.tolist(), "intensity": ex_int.tolist()},
                                "relation_type": ""
                            })
                if sim_list:
                    from matgraphia_plot import create_multi_trace_chart, render_plotly_with_academic_export
                    traces = []
                    for idx, s in enumerate(sim_list):
                        prof = s.get("profile") or {}
                        if prof.get("two_theta") and prof.get("intensity"):
                            traces.append({
                                "x": prof["two_theta"],
                                "y": prof["intensity"],
                                "name": s.get("material_name", f"Sample {idx+1}")
                            })
                    if traces:
                        fig = create_multi_trace_chart(
                            traces=traces,
                            title=f"XRD Interactive Multi-Sample Overlay ({len(traces)} Samples)",
                            x_title="2θ (degree)",
                            y_title="Intensity (a.u.)",
                            show_legend=True
                        )
                        render_plotly_with_academic_export(fig, key_prefix="xrd_comp_page_plotly", filename_base="XRD_All_Samples_Comparison")
                    
                    if plugin and hasattr(plugin, "build_comparison_csv"):
                        df_csv = plugin.build_comparison_csv(None, sim_list, remove_bg=True)
                        if df_csv is not None:
                            st.download_button(
                                label="⬇️ XRD比較データ CSV をダウンロード",
                                data=df_csv.to_csv(index=False),
                                file_name="XRD_All_Samples_Comparison.csv",
                                mime="text/csv",
                                key="dl_comp_page_xrd_csv"
                            )
            else:
                table_data = []
                for m in type_msrs:
                    s_obj = next((s for s in samples if s["sample_id"] == m["sample_id"]), None)
                    s_label = s_obj["human_id"] if s_obj else m["sample_id"][:4]
                    table_data.append({
                        "Sample": s_label,
                        "Measurement Type": m["measurement_type"],
                        "Measured At": str(m.get("measured_at"))[:10],
                        "Operator": m.get("operator", "-"),
                        "Conditions/Features": str(m.get("conditions") or m.get("extracted_features")),
                        "Raw Data Path": m.get("raw_data_path", "-")
                    })
                st.dataframe(pd.DataFrame(table_data), hide_index=True)

    # 3. 物質(Material)特性比較
    with tab_mat_comp:
        st.subheader("🧱 登録物質 (Material) 特性 ＆ 物性パラメータ比較")
        if not materials:
            st.info("登録されている物質データがありません。")
        else:
            mat_names = [m["name"] for m in materials]
            sel_mats = st.multiselect("比較する物質を選択", mat_names, default=mat_names[:3], key="comp_view_ms_mats")
            if sel_mats:
                mat_rows = []
                for m in materials:
                    if m["name"] in sel_mats:
                        props = m.get("properties") or {}
                        mat_rows.append({
                            "Material Name": m["name"],
                            "CIF File": m.get("cif_file_path", "なし"),
                            "Simulated XRD": "あり" if props.get("xrd_simulation") else "なし",
                            "Remarks": m.get("remarks", "-"),
                            "登録日": str(m.get("created_at"))[:10]
                        })
                st.dataframe(pd.DataFrame(mat_rows), hide_index=True)
