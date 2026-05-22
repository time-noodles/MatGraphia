# MatGraphia - 物質(Material)メタデータの登録ページ
import os
import re
import importlib.util
import streamlit as st
import database as db
import file_manager as fm
import plugin_manager as pm
from ui.forms import render_dynamic_form
from ui.helpers import _normalize_cif_fraction_tokens,build_literature_label


def _sync_obsidian(force=False):
    if not force and db.get_setting("obsidian_auto_sync")=="False":
        return
    path=os.path.join(os.getcwd(),"obsidian_vault")
    try:
        from obsidian_exporter import ObsidianExporter
        ObsidianExporter(db).export_to_directory(path)
    except Exception as e:
        st.warning(f"Obsidian 同期に失敗しました: {e}")


def _load_measurement_plugin(measurement_type):
    filename=f"{str(measurement_type).lower()}.py"
    plugin_path=os.path.join(os.path.dirname(os.path.dirname(__file__)),"plugins","measurements",filename)
    if not os.path.exists(plugin_path):
        return None
    spec=importlib.util.spec_from_file_location(f"measurement_plugin_{measurement_type}",plugin_path)
    if not spec or not spec.loader:
        return None
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_material_plugin(plugin_name):
    filename=f"{str(plugin_name).lower()}.py"
    plugin_path=os.path.join(os.path.dirname(os.path.dirname(__file__)),"plugins","materials",filename)
    if not os.path.exists(plugin_path):
        return None
    spec=importlib.util.spec_from_file_location(f"material_plugin_{plugin_name}",plugin_path)
    if not spec or not spec.loader:
        return None
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_structure_preview(cif_bytes,cif_name):
    """結晶構造プレビュー (Dashサーバー起動)"""
    plugin=_load_material_plugin("structure_preview")
    if not plugin or not hasattr(plugin,"build_structure_preview"):
        return None,None,"結晶構造プレビュープラグインを読み込めませんでした。"
    try:
        return plugin.build_structure_preview(cif_bytes,cif_name)
    except Exception as e:
        return None,None,f"結晶構造プレビュープラグイン実行に失敗しました: {e}"


@st.cache_data(show_spinner=False)
def _cached_xrd_preview(cif_bytes,cif_name,conditions,material_name):
    xrd_plugin=_load_measurement_plugin("XRD")
    if not xrd_plugin or not hasattr(xrd_plugin,"simulate_xrd_for_cif_bytes"):
        return None,"XRDプラグインが読み込めないため、CIFプレビューは利用できません。",None,None

    sim_result,sim_err=xrd_plugin.simulate_xrd_for_cif_bytes(
        cif_bytes=cif_bytes,
        cif_name=cif_name,
        conditions=conditions,
        material_name=material_name,
    )

    png_bytes=None
    plot_err=None
    if sim_result and hasattr(xrd_plugin,"render_simulated_xrd_plot_png"):
        png_bytes,plot_err=xrd_plugin.render_simulated_xrd_plot_png(sim_result)

    return sim_result,sim_err,png_bytes,plot_err


def render():
    st.header("物質（Material）メタデータの登録")
    st.markdown("物質固有の物性値（Tc, Neel点等）や先行研究情報を登録します。")

    # 遅延インポート
    import pandas as pd
    from schemas import Material

    literatures=db.fetch_all_literatures()
    materials=db.fetch_all_materials()

    # リッチラベル付き文献選択肢 (要件6)
    lit_options={"選択なし (None)":None}
    for l in literatures:
        lit_options[build_literature_label(l)]=l["literature_id"]

    with st.container():
        name=st.text_input("物質名 (必須 / 例: CuCrS2)",value="")

        mat_options={}
        for m in materials:
            mat_options[f"{m['name']} #{m['material_id'][:4]}"]=m["material_id"]

        st.write("---")
        st.markdown("**【物性値・先行研究情報】**")
        prop_df_init=pd.DataFrame([{"Property":"Tc (K)","Value":""},{"Property":"Tn (K)","Value":""}])
        edited_prop_df=st.data_editor(prop_df_init,num_rows="dynamic",hide_index=True,key="mat_prop_editor")

        st.markdown("**【関連物質リンク（オプション）】**")
        selected_impurities=st.multiselect("不純物として関連づける物質（オプション）",list(mat_options.keys()),key="mat_impurity_links")
        selected_polymorphs=st.multiselect("多型として関連づける物質（オプション）",list(mat_options.keys()),key="mat_polymorph_links")

        ref_lit=st.selectbox("参照文献",list(lit_options.keys()))
        remarks=st.text_area("備考")

        uploaded_cif=st.file_uploader("CIFファイル(任意)のアップロード",type=["cif","txt"])

        cif_bytes_raw=uploaded_cif.getvalue() if uploaded_cif is not None else None
        cif_bytes=_normalize_cif_fraction_tokens(cif_bytes_raw) if cif_bytes_raw is not None else None

        if uploaded_cif is not None:
            st.write("---")
            st.markdown("**【CIFから結晶構造描画 (crystal_toolkit 3D)】**")
            if not cif_bytes:
                st.warning("CIFデータが空です。")
            else:
                if cif_bytes_raw is not None and cif_bytes!=cif_bytes_raw:
                    st.caption("CIFの分数表記を正規化して解析しています。")
                # session_stateでキャッシュ
                import hashlib
                cif_hash=hashlib.md5(cif_bytes).hexdigest()
                cache_key=f"struct_preview_{cif_hash}"
                if cache_key not in st.session_state:
                    with st.spinner("crystal_toolkit で結晶構造を描画中..."):
                        graph_obj,graph_payload,graph_err=_run_structure_preview(cif_bytes,uploaded_cif.name)
                    st.session_state[cache_key]=(graph_obj,graph_payload,graph_err)
                else:
                    graph_obj,graph_payload,graph_err=st.session_state[cache_key]

                if graph_err:
                    st.warning(graph_err)
                elif graph_payload:
                    st.success("結晶構造の描画を生成しました。")
                    # 3Dインタラクティブモデル (iframe)
                    dash_port=graph_payload.get("dash_port")
                    if dash_port:
                        st.components.v1.iframe(f"http://127.0.0.1:{dash_port}",height=640,scrolling=True)
                    else:
                        st.warning("3Dビューアの起動に失敗しました。")

                    st.markdown("**Summary**")
                    summary=dict(graph_payload["summary"])
                    atom_counts=summary.pop("atom_counts",{})
                    st.dataframe(pd.DataFrame([summary]),hide_index=True,use_container_width=True)
                    if isinstance(atom_counts,dict) and atom_counts:
                        counts_df=pd.DataFrame(
                            [{"element":k,"count_in_unit_cell":v} for k,v in sorted(atom_counts.items())]
                        )
                        st.markdown("**Atom Counts in Unit Cell**")
                        st.dataframe(counts_df,hide_index=True,use_container_width=True)

                    with st.expander("StructureGraph raw output"):
                        st.text(str(graph_obj))

        xrd_plugin=_load_measurement_plugin("XRD")
        if uploaded_cif is not None and xrd_plugin and hasattr(xrd_plugin,"simulate_xrd_for_cif_bytes"):
            st.write("---")
            st.markdown("**【CIFからXRDシミュレーション（登録前プレビュー）】**")
            c1,c2,c3=st.columns(3)
            with c1:
                mat_xrd_mode=st.selectbox(
                    "シミュレーション種別",
                    ["Powder","TMDC c-axis Oriented"],
                    key="mat_xrd_mode_preview",
                )
            with c2:
                mat_xrd_target=st.selectbox(
                    "X-ray Target",
                    ["CuKa","MoKa","CoKa","FeKa"],
                    key="mat_xrd_target_preview",
                )
            with c3:
                mat_xrd_peak_width=st.number_input(
                    "Peak width (FWHM)",
                    min_value=0.01,max_value=5.0,value=0.15,step=0.01,
                    key="mat_xrd_peak_width_preview",
                )

            c4,c5=st.columns(2)
            with c4:
                mat_xrd_tth_min=st.number_input(
                    "2theta min",
                    min_value=0.0,max_value=180.0,value=5.0,step=0.5,
                    key="mat_xrd_tth_min_preview",
                )
            with c5:
                mat_xrd_tth_max=st.number_input(
                    "2theta max",
                    min_value=0.0,max_value=180.0,value=90.0,step=0.5,
                    key="mat_xrd_tth_max_preview",
                )

            preview_conditions={
                "simulation_mode":mat_xrd_mode,
                "target":mat_xrd_target,
                "two_theta_min":float(mat_xrd_tth_min),
                "two_theta_max":float(mat_xrd_tth_max),
                "profile_step":0.02,
                "peak_width":float(mat_xrd_peak_width),
            }
            try:
                with st.spinner("XRDパターンを生成中..."):
                    sim_result,sim_err,png_bytes,plot_err=_cached_xrd_preview(
                        cif_bytes=cif_bytes,
                        cif_name=uploaded_cif.name,
                        conditions=preview_conditions,
                        material_name=name or "Unknown",
                    )

                if sim_result:
                    if png_bytes:
                        st.image(
                            png_bytes,
                            caption=f"XRD simulated pattern ({sim_result.get('mode')})",
                            use_container_width=True,
                        )
                    if plot_err:
                        st.warning(plot_err)

                    profile_df=pd.DataFrame(
                        {
                            "two_theta":sim_result["profile"]["two_theta"],
                            "intensity":sim_result["profile"]["intensity"],
                        }
                    )
                    profile_csv=profile_df.to_csv(index=False).encode("utf-8")
                    csv_name=f"simulated_xrd_{str(sim_result.get('mode') or 'powder').replace(' ','_')}.csv"
                    st.download_button(
                        label="XRDパターンをCSV保存",
                        data=profile_csv,
                        file_name=csv_name,
                        mime="text/csv",
                        key="btn_download_mat_xrd_csv",
                    )

                    st.info(
                        f"プレビュー生成完了: mode={sim_result.get('mode')} / target={sim_result.get('target')} / peaks={sim_result.get('peak_count')}"
                    )
                elif sim_err:
                    st.warning(sim_err)
            except Exception as e:
                st.error(f"XRDプレビューの生成に失敗しました: {e}")
        elif uploaded_cif is not None and not xrd_plugin:
            st.warning("XRDプラグインが読み込めないため、CIFプレビューは利用できません。")

        if st.button("物質情報を登録する"):
            if not name:
                st.error("物質名は必須です。")
                return
            properties={row["Property"]:row["Value"] for _,row in edited_prop_df.iterrows() if row["Property"]}
            impurity_ids=[mat_options[k] for k in selected_impurities if mat_options.get(k)]
            polymorph_ids=[mat_options[k] for k in selected_polymorphs if mat_options.get(k)]
            try:
                mat=Material(
                    name=name,
                    properties=properties,
                    reference_literature_id=lit_options[ref_lit],
                    impurity_material_ids=impurity_ids,
                    polymorph_material_ids=polymorph_ids,
                    remarks=remarks
                )

                if uploaded_cif:
                    cif_path=fm.save_material_file(mat.material_id,uploaded_cif.name,cif_bytes if cif_bytes is not None else uploaded_cif.getvalue())
                    mat.cif_file_path=cif_path

                    # CIFがある場合、Powderモードで全ピークのXRDシミュレーションを事前実行・保存
                    xrd_pl=_load_measurement_plugin("XRD")
                    if xrd_pl and hasattr(xrd_pl,"simulate_xrd_for_cif_bytes"):
                        try:
                            # Powderモードで全ピーク(hkl指数含む)を保存
                            powder_conditions={
                                "simulation_mode":"Powder",
                                "target":"CuKa",
                                "two_theta_min":5.0,
                                "two_theta_max":90.0,
                                "profile_step":0.02,
                                "peak_width":0.15,
                            }
                            sim_res,sim_e=xrd_pl.simulate_xrd_for_cif_bytes(
                                cif_bytes=cif_bytes if cif_bytes is not None else uploaded_cif.getvalue(),
                                cif_name=uploaded_cif.name,
                                conditions=powder_conditions,
                                material_name=name or "Unknown",
                            )
                            if sim_res:
                                mat.properties["xrd_simulation"]=sim_res
                                st.info(f"XRDシミュレーションを事前計算・保存しました（Powder / peaks={sim_res.get('peak_count')}）。")
                            elif sim_e:
                                st.warning(f"XRDシミュレーションの事前計算をスキップしました: {sim_e}")
                        except Exception as ex:
                            st.warning(f"XRDシミュレーション事前計算に失敗しました: {ex}")

                db.insert_material(mat)
                _sync_obsidian()
                st.success(f"物質情報を登録しました！ (ID: {mat.material_id})")
                if mat.cif_file_path:
                    st.info(f"CIFを保存しました: `{mat.cif_file_path}`")
            except Exception as e:
                st.error(f"登録時にエラーが発生しました: {e}")

