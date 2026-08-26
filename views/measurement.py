import re
import hashlib
import os
import importlib.util
import streamlit as st
import database as db
import file_manager as fm
import plugin_manager as pm
from ui.forms import render_dynamic_form
from ui.helpers import get_sample_ancestry,build_sample_label,log_errors

TITLE="📊 測定データの登録"
ORDER=6


# 測定用プラグインのロード
def _load_measurement_plugin(measurement_type):
    filename=f"{str(measurement_type).lower()}.py"
    plugin_path=os.path.join(os.path.dirname(os.path.dirname(__file__)),"plugins","measurements",filename)
    if not os.path.exists(plugin_path):return None
    spec=importlib.util.spec_from_file_location(f"measurement_plugin_{measurement_type}",plugin_path)
    if not spec or not spec.loader:return None
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# XRDデータアップロード時の即時プレビュー
def _render_xrd_upload_preview(uploaded_bytes,file_name,selected_sample_id,samples,events_dict,materials):
    import io as _io
    import json as _json
    import numpy as np
    plugin=_load_measurement_plugin("XRD")
    if not plugin:return
    exp_tth,exp_int=None,None
    if hasattr(plugin,"_parse_xrd_bytes"):
        exp_tth,exp_int,parse_err=plugin._parse_xrd_bytes(uploaded_bytes)
        if parse_err:
            st.warning(f"XRDデータのパースに失敗: {parse_err}")
            return
    else:
        try:
            import pandas as pd
            for sep in [",",r"\s+","\t"]:
                try:
                    tmp=pd.read_csv(_io.BytesIO(uploaded_bytes),sep=sep,header=None,comment="#",engine="python")
                    if tmp.shape[1]>=2:
                        col0=pd.to_numeric(tmp.iloc[:,0],errors="coerce")
                        col1=pd.to_numeric(tmp.iloc[:,1],errors="coerce")
                        mask=col0.notna()&col1.notna()
                        if mask.sum()>0:
                            exp_tth=col0[mask].values.astype(float)
                            exp_int=col1[mask].values.astype(float)
                            break
                except Exception:
                    continue
        except Exception:
            pass
    if exp_tth is None or len(exp_tth)==0:return
# XRDデータアップロード時の即時プレビュー (任意物質選択・比較 ＆ ミラー指数hkl描画対応)
def _render_xrd_upload_preview(uploaded_bytes,file_name,selected_sample_id,samples,events_dict,materials):
    import io as _io
    import json as _json
    import numpy as np
    import pandas as pd
    plugin=_load_measurement_plugin("XRD")
    if not plugin:return
    exp_tth,exp_int=None,None
    if hasattr(plugin,"_parse_xrd_bytes"):
        exp_tth,exp_int,parse_err=plugin._parse_xrd_bytes(uploaded_bytes)
        if parse_err:
            st.warning(f"XRDデータのパースに失敗: {parse_err}")
            return
    else:
        try:
            for sep in [",",r"\s+","\t"]:
                try:
                    tmp=pd.read_csv(_io.BytesIO(uploaded_bytes),sep=sep,header=None,comment="#",engine="python")
                    if tmp.shape[1]>=2:
                        col0=pd.to_numeric(tmp.iloc[:,0],errors="coerce")
                        col1=pd.to_numeric(tmp.iloc[:,1],errors="coerce")
                        mask=col0.notna()&col1.notna()
                        if mask.sum()>0:
                            exp_tth=col0[mask].values.astype(float)
                            exp_int=col1[mask].values.astype(float)
                            break
                except Exception:
                    continue
        except Exception:
            pass
    if exp_tth is None or len(exp_tth)==0:return
    st.write("---")
    st.markdown("### 📊 XRD プレビュー（実測 vs 物質シミュレーション比較 ＆ ミラー指数 hkl）")
    st.caption("登録物質から自由選択して重ね描き比較および CSV ダウンロードが可能です。")
    c_bg,c_sel=st.columns([1,2])
    with c_bg:
        remove_bg=st.checkbox("バックグラウンド除去 (symple_plot)",value=True,key="xrd_preview_remove_bg")
    
    mat_options_map={f"{m['name']} (ID:{m['material_id'][:4]})":m for m in materials}
    default_selected=[]
    if selected_sample_id and hasattr(plugin,"_find_material_for_sample"):
        main_material=plugin._find_material_for_sample(selected_sample_id,samples,events_dict,materials)
        if main_material:
            m_label=f"{main_material['name']} (ID:{main_material['material_id'][:4]})"
            if m_label in mat_options_map:
                default_selected.append(m_label)

    with c_sel:
        selected_mat_labels=st.multiselect(
            "重ね描き比較する登録物質を選択",
            options=list(mat_options_map.keys()),
            default=default_selected,
            key="xrd_preview_selected_mats"
        )

    sim_results_list=[]
    preview_conds={"simulation_mode":"Powder","target":"CuKa","two_theta_min":float(np.nanmin(exp_tth)),"two_theta_max":float(np.nanmax(exp_tth)),"profile_step":0.02,"peak_width":0.15}
    for label in selected_mat_labels:
        mat=mat_options_map.get(label)
        if not mat:continue
        props=mat.get("properties") or {}
        if isinstance(props,str):
            try:props=_json.loads(props)
            except Exception:props={}
        sim=props.get("xrd_simulation")
        if not sim and mat.get("cif_file_path") and hasattr(plugin,"_simulate_xrd_from_cif_path"):
            cif_abs=os.path.join(str(fm.BASE_DIR),str(mat["cif_file_path"]))
            if os.path.exists(cif_abs):
                sim_res,err=plugin._simulate_xrd_from_cif_path(cif_abs,preview_conds,material_name=mat["name"])
                if sim_res:sim=sim_res
        if sim:
            sim=dict(sim)
            sim["relation_type"]=""
            sim["material_name"]=str(mat.get("name") or "Unknown")
            sim_results_list.append(sim)

    exp_data={"two_theta":exp_tth.tolist(),"intensity":exp_int.tolist()}
    if sim_results_list and hasattr(plugin,"render_comparison_xrd_plot_png"):
        comp_png,comp_err=plugin.render_comparison_xrd_plot_png(
            experimental_data=exp_data,
            sim_results_list=sim_results_list,
            conditions=preview_conds,
            remove_bg=remove_bg,
        )
        if comp_png:
            st.image(comp_png,caption=f"XRD Comparison - Exp. vs {len(sim_results_list)} Materials (with hkl indices)")
            if hasattr(plugin,"build_comparison_csv"):
                df_csv=plugin.build_comparison_csv(exp_data,sim_results_list,remove_bg=remove_bg)
                if df_csv is not None:
                    csv_str=df_csv.to_csv(index=False)
                    st.download_button(
                        label="⬇️ 比較プロファイル CSV をダウンロード",
                        data=csv_str,
                        file_name=f"XRD_Comparison_{file_name}.csv",
                        mime="text/csv",
                        key="dl_xrd_comp_csv"
                    )
            return
        elif comp_err:
            st.warning(f"比較グラフ描画に失敗（実測のみ表示）: {comp_err}")
    try:
        create_symple_plots,remove_background_fn,plt=None,None,None
        try:
            from symple_plot import create_symple_plots as _csp
            import matplotlib.pyplot as _plt
            create_symple_plots,plt=_csp,_plt
            if remove_bg:
                try:
                    from symple_plot import remove_background as _rb
                    remove_background_fn=_rb
                except ImportError:
                    pass
        except Exception:
            try:
                if hasattr(plugin,"_ensure_symple_plot_importable"):
                    plugin._ensure_symple_plot_importable()
                from symple_plot import create_symple_plots as _csp
                import matplotlib.pyplot as _plt
                create_symple_plots,plt=_csp,_plt
                if remove_bg:
                    try:
                        from symple_plot import remove_background as _rb
                        remove_background_fn=_rb
                    except ImportError:
                        pass
            except Exception:
                pass
        if create_symple_plots is None or plt is None:
            import pandas as pd
            exp_int_norm=exp_int-np.nanmin(exp_int)
            ey_max=float(np.nanmax(exp_int_norm))
            if ey_max>0:exp_int_norm=exp_int_norm/ey_max
            chart_df=pd.DataFrame({"2theta":exp_tth,"Intensity":exp_int_norm})
            st.line_chart(chart_df,x="2theta",y="Intensity")
            return
        plot_y=exp_int.copy()
        if remove_bg and remove_background_fn is not None:
            try:
                plot_y=remove_background_fn(plot_y,auto_opt=True)
            except Exception:
                pass
        plot_y=plot_y-np.nanmin(plot_y)
        py_max=float(np.nanmax(plot_y))
        if py_max>0:plot_y=plot_y/py_max
        fig,sp=create_symple_plots(nrows=1,ncols=1,figsize=(8.5,4.0),style="paper")
        sp.plot(
            exp_tth,plot_y,
            col=(0,0,0),
            alab=[r'$\mathrm{2}\theta\ [\mathrm{deg.}]$',"Intensity [a.u.]"],
            cx=[float(np.nanmin(exp_tth)),float(np.nanmax(exp_tth))],
            nony=True,
            lab=f"Exp. ({file_name})",
        )
        sp.ax.legend(frameon=False,loc="upper right",fontsize=10)
        sp.ax.tick_params(axis="y",labelleft=False,left=False)
        fig.tight_layout()
        buf=_io.BytesIO()
        fig.savefig(buf,format="png",dpi=180)
        plt.close(fig)
        st.image(buf.getvalue(),caption=f"XRD Preview - {file_name} (実測のみ)")
    except Exception as e:
        st.warning(f"XRDプレビューの描画に失敗しました: {e}")


# 画面描画
@log_errors("測定データの登録")
def render():
    st.header("測定データ (Measurement) の登録 ＆ 試料間データ比較")
    import pandas as pd
    import json
    from schemas import Measurement
    from ui.helpers import render_location_badge
    MEASUREMENT_SCHEMAS=pm.get_measurement_schemas()
    samples=db.fetch_all_samples()
    measurements=db.fetch_all_measurements()
    events={e["event_id"]:e for e in db.fetch_all_events()}
    materials=db.fetch_all_materials()
    events_dict=events
    recent_operator=measurements[0].get("operator","") if measurements else ""
    if not samples:
        st.warning("先にサンプルを登録してください。")
        return
    sample_options={}
    for s in samples:
        label=build_sample_label(s,events_dict=events_dict,samples_list=samples)
        sample_options[label]=s["sample_id"]

    tab_register, tab_compare = st.tabs(["📝 測定データの登録", "🧪 試料(サンプル)間データ比較"])

    with tab_compare:
        st.subheader("🧪 選択試料 (サンプル) 間でのデータ横並び ＆ プロット重畳比較")
        st.markdown("登録されている複数のサンプルを選択し、合成条件・保管場所・EDX組成比・各種測定データ（XRD, MPMS M-T, PPMS R-T, CV, Raman等）を横並びマトリクス比較およびグラフ重ね描き分析が可能です。")
        
        sample_multiselect = st.multiselect(
            "比較対象のサンプルを複数選択",
            options=list(sample_options.keys()),
            default=list(sample_options.keys())[:2] if len(sample_options) >= 2 else list(sample_options.keys()),
            key="ms_sample_comparison_select"
        )
        
        if sample_multiselect:
            sel_sample_ids = [sample_options[lbl] for lbl in sample_multiselect]
            sel_samples = [s for s in samples if s["sample_id"] in sel_sample_ids]
            
            st.markdown("#### 1. サンプル基本情報 ＆ 保管場所 マトリクス")
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
                with c2: render_location_badge(s.get("location"), key_prefix=f"comp_{s['sample_id'][:4]}")
                
            st.markdown("#### 2. 紐付く測定データの重ね描き・傾向比較")
            sel_msrs = [m for m in measurements if m.get("sample_id") in sel_sample_ids]
            if not sel_msrs:
                st.info("選択されたサンプルにはまだ測定データが登録されていません。")
            else:
                msr_types = sorted(list(set(m["measurement_type"] for m in sel_msrs)))
                selected_comp_type = st.selectbox("比較する測定タイプを選択", msr_types, key="sb_comp_msr_type")
                
                target_msrs = [m for m in sel_msrs if m["measurement_type"] == selected_comp_type]
                st.write(f"選択タイプの登録件数: **{len(target_msrs)}** 件")
                
                if selected_comp_type == "XRD":
                    sim_list = []
                    plugin = _load_measurement_plugin("XRD")
                    for m in target_msrs:
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
                    if sim_list and plugin and hasattr(plugin, "render_comparison_xrd_plot_png"):
                        comp_png, err = plugin.render_comparison_xrd_plot_png(
                            experimental_data=None,
                            sim_results_list=sim_list,
                            conditions={"target": "CuKa"},
                            remove_bg=True
                        )
                        if comp_png:
                            st.image(comp_png, caption=f"Sample-to-Sample XRD Overlay Comparison ({len(sim_list)} Samples)")
                else:
                    table_data = []
                    for m in target_msrs:
                        s_obj = next((s for s in samples if s["sample_id"] == m["sample_id"]), None)
                        s_label = s_obj["human_id"] if s_obj else m["sample_id"][:4]
                        table_data.append({
                            "Sample": s_label,
                            "Measured At": str(m.get("measured_at"))[:10],
                            "Operator": m.get("operator", "-"),
                            "Conditions/Features": str(m.get("conditions") or m.get("extracted_features")),
                            "Raw Path": m.get("raw_data_path", "-")
                        })
                    st.dataframe(pd.DataFrame(table_data), hide_index=True)

    with tab_register:
        st.subheader("1. 生データアップロード ＆ タイプ選択")
        measure_type_options=list(MEASUREMENT_SCHEMAS.keys()) if MEASUREMENT_SCHEMAS else ["XRD","SEM","Hall"]
        measurement_type=st.selectbox("測定タイプ (必須)",measure_type_options,key="measure_type_selector")
        sample_lbl=st.selectbox("対象サンプル (必須)",list(sample_options.keys()),key="measure_sample_selector")
        selected_sample_id=sample_options.get(sample_lbl)
        uploaded_file=st.file_uploader(
            "生データ(Raw Data)のアップロード (必須)",
            type=["csv","txt","dat","tif","jpg","png","pdf","bmp","pptx","ppt"],
            key="measure_upload_file"
        )
        uploaded_bytes=uploaded_file.getvalue() if uploaded_file is not None else None
        if measurement_type=="XRD" and uploaded_file is not None and uploaded_bytes:
            _render_xrd_upload_preview(uploaded_bytes,uploaded_file.name,selected_sample_id,samples,events_dict,materials)




    plugin=_load_measurement_plugin(measurement_type)
    plugin_initial_data,plugin_info_msgs,plugin_warn_msgs={},[],[]
    if uploaded_file is not None and plugin and hasattr(plugin,"prefill_from_upload"):
        try:
            init_data,info_msgs,warn_msgs=plugin.prefill_from_upload(uploaded_file.name,uploaded_bytes)
            plugin_initial_data=init_data if isinstance(init_data,dict) else {}
            plugin_info_msgs=info_msgs if isinstance(info_msgs,list) else []
            plugin_warn_msgs=warn_msgs if isinstance(warn_msgs,list) else []
        except Exception as e:
            plugin_warn_msgs=[f"プラグインによる自動抽出に失敗しました: {e}"]
    for msg in plugin_info_msgs:st.success(msg)
    for msg in plugin_warn_msgs:st.warning(msg)

    if measurement_type=="SEM" and plugin and hasattr(plugin,"calculate_composition_ratio"):
        at_rows=plugin_initial_data.get("at_percent_table") or []
        if at_rows:
            st.write("---")
            st.markdown("### 📊 SEM EDX at% ➔ 組成比（化学量論比）自動計算・変換ツール")
            st.caption("選択した元素の at% の合計を指定定数（例: S=2.0 や 全体=4.0）に規格化して組成比・組成式を計算します。")
            all_elems=[str(r.get("element") or "").strip() for r in at_rows if str(r.get("element") or "").strip()]
            c_elems,c_const=st.columns([2,1])
            with c_elems:
                sel_elems=st.multiselect("規格化の基準とする元素を選択",options=all_elems,default=all_elems,key="sem_calc_ratio_elems")
            with c_const:
                target_const=st.number_input("基準定数 (規格化の目標値)",min_value=0.1,max_value=100.0,value=2.0,step=0.1,key="sem_calc_ratio_const")
            if sel_elems:
                res_rows,formula_str,factor,calc_err=plugin.calculate_composition_ratio(at_rows,sel_elems,target_const)
                if calc_err:
                    st.warning(calc_err)
                elif res_rows:
                    res_df=pd.DataFrame(res_rows)[["element","at_percent","ratio","is_selected"]]
                    res_df.columns=["元素","at%","算出組成比 (Stoichiometry)","基準対象"]
                    st.dataframe(res_df,hide_index=True)
                    st.success(f"🧪 **算定された組成式 (推定):** `{formula_str}` （スケール因子: {factor:.5f}）")

        form_key_prefix="measure"
        if uploaded_file is not None:
            safe_name=re.sub(r"[^A-Za-z0-9_]","_",uploaded_file.name)
            digest=hashlib.md5(uploaded_bytes).hexdigest()[:10]
            form_key_prefix=f"measure_{measurement_type}_{safe_name[:30]}_{digest}"
        conditions=render_dynamic_form(schema,key_prefix=form_key_prefix,initial_data=plugin_initial_data)
        col_ms1,col_ms2=st.columns(2)
        with col_ms1:
            submitted=st.form_submit_button("測定データを登録する (本登録)",type="primary")
        with col_ms2:
            draft_submitted=st.form_submit_button("下書き（仮登録）する")
        if submitted:
            if not sample_lbl or not measurement_type or not measured_at:
                st.error("【必須エラー】 対象サンプル、測定タイプ、測定日は必須項目です。")
                return
            if uploaded_file is None or uploaded_file.size==0:
                st.error("【必須エラー】 生データファイル（0KB以上）のアップロードは必須です。")
                return
            s_id=selected_sample_id
            for m in measurements:
                if (m["sample_id"]==s_id and m["measurement_type"]==measurement_type):
                    try:
                        m_conds=json.loads(m["conditions"])
                        if m_conds==conditions:
                            st.error("【重複エラー】 このサンプルに対して、全く同じ設定条件によるデータが既に登録されています！")
                            return
                    except Exception:
                        pass
            try:
                msr=Measurement(
                    sample_id=s_id,
                    measurement_type=measurement_type,
                    conditions=conditions,
                    operator=operator,
                    measured_at=measured_at,
                    remarks=remarks,
                    is_draft=False
                )
                if uploaded_file is not None:
                    file_bytes=uploaded_bytes
                    for k,v in plugin_initial_data.items():
                        if not conditions.get(k):conditions[k]=v
                    rel_path=fm.save_raw_file(msr.measurement_id,uploaded_file.name,file_bytes)
                    msr.raw_data_path=rel_path
                    msr.conditions=conditions
                if measurement_type=="XRD" and plugin:
                    try:
                        import json as _json
                        exp_data=None
                        if msr.raw_data_path and hasattr(plugin,"parse_experimental_xrd"):
                            ex_tth,ex_int,ex_err=plugin.parse_experimental_xrd(
                                raw_data_path=msr.raw_data_path,
                                data_base_dir=str(fm.BASE_DIR),
                            )
                            if ex_tth is not None and ex_int is not None:
                                exp_data={"two_theta":ex_tth.tolist(),"intensity":ex_int.tolist()}
                            elif ex_err:
                                st.warning(f"実測XRDデータの読込: {ex_err}")
                        sim_results_list=[]
                        main_material=None
                        if hasattr(plugin,"_find_material_for_sample"):
                            main_material=plugin._find_material_for_sample(s_id,samples,events_dict,materials)
                        if main_material:
                            props=main_material.get("properties") or {}
                            if isinstance(props,str):
                                try:
                                    props=_json.loads(props)
                                except Exception:
                                    props={}
                            main_sim=props.get("xrd_simulation")
                            if main_sim:
                                mode=str(conditions.get("simulation_mode") or "Powder")
                                if mode=="TMDC c-axis Oriented" and hasattr(plugin,"_filter_00l_from_saved"):
                                    main_sim=plugin._filter_00l_from_saved(main_sim,conditions)
                                else:
                                    main_sim=dict(main_sim)
                                    main_sim["mode"]=mode
                                main_sim["relation_type"]=""
                                main_sim["material_name"]=str(main_material.get("name") or "Unknown")
                                sim_results_list.append(main_sim)
                                if hasattr(plugin,"collect_related_material_simulations"):
                                    related=plugin.collect_related_material_simulations(
                                        material=main_material,
                                        materials_list=materials,
                                        conditions=conditions,
                                    )
                                    sim_results_list.extend(related)
                        if sim_results_list:
                            msr.extracted_features={"xrd_simulation":sim_results_list[0]}
                        if (exp_data or sim_results_list) and hasattr(plugin,"render_comparison_xrd_plot_png"):
                            comp_png,comp_err=plugin.render_comparison_xrd_plot_png(
                                experimental_data=exp_data,
                                sim_results_list=sim_results_list,
                                conditions=conditions,
                                remove_bg=True,
                            )
                            if comp_png:
                                mode_text=str(conditions.get("simulation_mode") or "Powder")
                                mode_slug=re.sub(r"[^A-Za-z0-9]+","_",mode_text).strip("_").lower() or "powder"
                                img_name=f"xrd_comparison_{mode_slug}.png"
                                plot_rel=fm.save_processed_file(msr.measurement_id,img_name,comp_png)
                                if not isinstance(msr.extracted_features,dict):
                                    msr.extracted_features={}
                                msr.extracted_features["xrd_comparison_plot_path"]=plot_rel
                                st.image(comp_png,caption=f"XRD Comparison ({mode_text})")
                                if sim_results_list:
                                    first_sim=sim_results_list[0]
                                    prof=first_sim.get("profile") or {}
                                    if prof.get("two_theta") and prof.get("intensity"):
                                        profile_df=pd.DataFrame({"two_theta":prof["two_theta"],"intensity":prof["intensity"]})
                                        profile_csv=profile_df.to_csv(index=False).encode("utf-8")
                                        msr.processed_data_path=fm.save_processed_file(msr.measurement_id,"simulated_xrd_profile.csv",profile_csv)
                                n_sim=len(sim_results_list)
                                n_related=max(0,n_sim-1)
                                st.info(f"XRD比較グラフを生成しました（主物質+関連物質{n_related}件）。")
                            elif comp_err:
                                st.warning(comp_err)
                        if (exp_data or sim_results_list) and hasattr(plugin,"build_comparison_csv"):
                            csv_df=plugin.build_comparison_csv(
                                experimental_data=exp_data,
                                sim_results_list=sim_results_list,
                                remove_bg=True,
                            )
                            if csv_df is not None:
                                csv_bytes=csv_df.to_csv(index=False).encode("utf-8")
                                csv_name=f"xrd_comparison_data_{msr.measurement_id[:8]}.csv"
                                fm.save_processed_file(msr.measurement_id,csv_name,csv_bytes)
                                st.download_button(
                                    label="XRD比較データをCSVダウンロード",
                                    data=csv_bytes,
                                    file_name=csv_name,
                                    mime="text/csv",
                                    key=f"btn_dl_xrd_csv_{msr.measurement_id[:8]}",
                                )
                    except Exception as e:
                        st.warning(f"XRD比較グラフの生成に失敗しました: {e}")
                db.insert_measurement(msr)
                st.success(f"測定データを本登録しました！ (ID: {msr.measurement_id})")
                if msr.raw_data_path:
                    st.info(f"生データをRaw保管庫へ安全に保存しました: `{msr.raw_data_path}`")
            except Exception as e:
                st.error(f"登録時にエラーが発生しました: {e}")
        elif draft_submitted:
            try:
                msr=Measurement(
                    sample_id=selected_sample_id or (samples[0]["sample_id"] if samples else ""),
                    measurement_type=measurement_type or "XRD",
                    conditions=conditions or {},
                    operator=operator or "",
                    measured_at=measured_at if measured_at else date.today(),
                    remarks=remarks or "",
                    is_draft=True
                )
                if uploaded_file is not None and uploaded_bytes:
                    rel_path=fm.save_raw_file(msr.measurement_id,uploaded_file.name,uploaded_bytes)
                    msr.raw_data_path=rel_path
                db.insert_measurement(msr)
                st.success(f"測定データを下書き（仮登録）しました！データ管理画面で後から補完・本登録できます。(ID: {msr.measurement_id})")
            except Exception as e:
                st.error(f"下書き登録時にエラーが発生しました: {e}")
