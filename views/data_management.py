import os
import json
import importlib.util
import streamlit as st
import database as db
import file_manager as fm
import plugin_manager as pm
from ui.forms import render_dynamic_form
from ui.helpers import (
    _json_or_raw,_resolve_data_abs_path,_normalize_cif_fraction_tokens,
    build_event_label,build_sample_label,build_literature_label,build_measurement_label,log_errors
)

TITLE="データ管理・編集"
ORDER=6

# 物質プラグインロード
def _load_material_plugin(plugin_name):
    filename=f"{str(plugin_name).lower()}.py"
    plugin_path=os.path.join(os.path.dirname(os.path.dirname(__file__)),"plugins","materials",filename)
    if not os.path.exists(plugin_path):return None
    spec=importlib.util.spec_from_file_location(f"material_plugin_{plugin_name}",plugin_path)
    if not spec or not spec.loader:return None
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# 測定プラグインロード
def _load_measurement_plugin(measurement_type):
    filename=f"{str(measurement_type).lower()}.py"
    plugin_path=os.path.join(os.path.dirname(os.path.dirname(__file__)),"plugins","measurements",filename)
    if not os.path.exists(plugin_path):return None
    spec=importlib.util.spec_from_file_location(f"measurement_plugin_{measurement_type}",plugin_path)
    if not spec or not spec.loader:return None
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# 構造プレビュー
def _run_structure_preview(cif_bytes,cif_name):
    plugin=_load_material_plugin("structure_preview")
    if not plugin or not hasattr(plugin,"build_structure_preview"):
        return None,None,"結晶構造プレビュープラグインを読み込めませんでした。"
    try:
        return plugin.build_structure_preview(cif_bytes,cif_name)
    except Exception as e:
        return None,None,f"結晶構造プレビュー生成に失敗しました: {e}"

# XRDプレビューキャッシュ
@st.cache_data(show_spinner=False)
def _cached_xrd_preview(cif_bytes,cif_name,conditions,material_name):
    xrd_plugin=_load_measurement_plugin("XRD")
    if not xrd_plugin or not hasattr(xrd_plugin,"simulate_xrd_for_cif_bytes"):
        return None,"XRDプラグインが読み込めません。",None,None
    sim_result,sim_err=xrd_plugin.simulate_xrd_for_cif_bytes(
        cif_bytes=cif_bytes,cif_name=cif_name,
        conditions=conditions,material_name=material_name,
    )
    png_bytes,plot_err=None,None
    if sim_result and hasattr(xrd_plugin,"render_simulated_xrd_plot_png"):
        png_bytes,plot_err=xrd_plugin.render_simulated_xrd_plot_png(sim_result)
    return sim_result,sim_err,png_bytes,plot_err

# 画面描画
@log_errors("データ管理・編集")
def render():
    st.header("データ管理・編集 (Data Explorer)")
    import pandas as pd
    from schemas import Literature,Event,Sample,Measurement,Material
    LITERATURE_SCHEMAS=pm.get_literature_schemas()
    EVENT_SCHEMAS=pm.get_event_schemas()
    SAMPLE_FORM_SCHEMAS=pm.get_sample_schemas()
    MEASUREMENT_SCHEMAS=pm.get_measurement_schemas()
    if st.session_state.get("data_mgmt_msg"):
        st.success(st.session_state.data_mgmt_msg)
        del st.session_state.data_mgmt_msg
    search_query=st.text_input("キーワードで絞り込み (DOI, タイトル, 物質名, 備考など)",key="global_search_mgmt")
    choice=st.radio("表示カテゴリ",["文献","イベント","サンプル","測定","物質"],horizontal=True,key="data_mgmt_main_choice")
    def _get_selected_id(rows,id_col,display_cols=None):
        if not rows:return None
        df=pd.DataFrame(rows)
        if search_query:
            mask=df.astype(str).apply(lambda x:x.str.contains(search_query,case=False,na=False)).any(axis=1)
            df=df[mask]
        if df.empty:
            st.info("キーワードに一致するデータはありません。")
            return None
        if "select" not in df.columns:
            df.insert(0,"select",[False]*len(df))
        df_for_editor=df.copy()
        if display_cols:
            if "select" not in display_cols:
                display_cols=["select"]+display_cols
            actual_cols=list(dict.fromkeys([c for c in display_cols if c in df_for_editor.columns]+[id_col]))
            df_for_editor=df_for_editor[actual_cols]
        column_config={id_col:None} if id_col in df_for_editor.columns else {}
        if "select" in df_for_editor.columns:
            column_config["select"]=st.column_config.CheckboxColumn("選択",default=False)
        edited_df=st.data_editor(
            df_for_editor,
            hide_index=True,
            use_container_width=True,
            disabled=[c for c in df_for_editor.columns if c!="select"],
            column_config=column_config,
            key=f"editor_v2_{choice}_{id_col}"
        )
        selected=edited_df[edited_df["select"]==True]
        if not selected.empty:return selected.iloc[0][id_col]
        return df.iloc[0][id_col]

    if choice=="文献":
        rows=db.fetch_all_literatures()
        if not rows:
            st.info("文献データがまだありません。")
            return
        display_df=pd.DataFrame(rows)
        display_df["ID"]=display_df["literature_id"].str[:4]
        display_df["日付"]=display_df["created_at"].str[:10]
        display_df["備考"]=display_df["remarks"].fillna("-").str[:40]
        cols=["select","ID","title","authors","venue","publication_year","日付","備考"]
        sel_id=_get_selected_id(rows,"literature_id",display_cols=cols)
        if not sel_id:return
        target=next(r for r in rows if r["literature_id"]==sel_id)
        with st.form("form_edit_lit"):
            col1,col2=st.columns(2)
            with col1:
                title=st.text_input("タイトル",value=target["title"] or "")
                authors=st.text_input("著者",value=target["authors"] or "")
            with col2:
                doi=st.text_input("DOI",value=target["doi"])
                venue=st.text_input("発表先",value=target.get("venue") or "")
            col3,col4=st.columns(2)
            with col3:
                pub_year_default=int(target.get("publication_year") or 0)
                publication_year=st.number_input("発行年",min_value=0,max_value=3000,value=pub_year_default,step=1)
            with col4:
                volume=st.text_input("巻 (Volume)",value=target.get("volume") or "")
            remarks=st.text_area("備考",value=target["remarks"] or "")
            uploaded_pdf=st.file_uploader("文献PDFの差し替え・更新",type=["pdf"])
            schema=LITERATURE_SCHEMAS.get(target.get("literature_type"),{})
            existing_params=_json_or_raw(target.get("parameters") or "{}")
            ui_params=render_dynamic_form(schema,key_prefix=f"edit_lit_params_{sel_id}",initial_data=existing_params)
            if st.form_submit_button("文献情報を反映して更新する"):
                try:
                    merged_params={**existing_params,**ui_params}
                    target.update({
                        "title":title,"authors":authors,"doi":doi,"venue":venue,
                        "publication_year":int(publication_year) if publication_year>0 else None,
                        "volume":volume,"parameters":merged_params,"remarks":remarks
                    })
                    if uploaded_pdf:
                        target["pdf_file_path"]=fm.save_literature_file(sel_id,uploaded_pdf.name,uploaded_pdf.getvalue())
                    db.update_literature(Literature(**target))
                    st.session_state.data_mgmt_msg="更新しました。"
                    st.rerun()
                except Exception as e:
                    st.error(f"エラー: {e}")
        col_copy,col_del=st.columns(2)
        with col_copy:
            if st.button("コピーして新規作成",key=f"copy_btn_lit_{sel_id}"):
                try:
                    existing_params=_json_or_raw(target.get("parameters") or "{}")
                    new_lit=Literature(
                        literature_type=target["literature_type"],
                        doi="",
                        remarks=target["remarks"] or "",
                        title=target.get("title"),
                        authors=target.get("authors"),
                        venue=target.get("venue"),
                        publication_year=target.get("publication_year"),
                        volume=target.get("volume"),
                        parameters=existing_params if isinstance(existing_params,dict) else {}
                    )
                    db.insert_literature(new_lit)
                    st.session_state.data_mgmt_msg=f"コピーを作成しました (ID: {new_lit.literature_id})"
                    st.rerun()
                except Exception as e:
                    st.error(f"コピーに失敗しました: {e}")
        with col_del:
            if st.button("この文献を削除する",key=f"del_btn_lit_{sel_id}"):
                st.session_state[f"confirm_del_lit_{sel_id}"]=True
        if st.session_state.get(f"confirm_del_lit_{sel_id}"):
            st.warning(f"本当にこの文献を削除しますか？ (ID: {sel_id})")
            c1,c2=st.columns(2)
            with c1:
                if st.button("はい、削除します",type="primary",key=f"do_del_lit_{sel_id}"):
                    try:
                        db.delete_literature(sel_id)
                        st.session_state.data_mgmt_msg="削除しました。"
                        del st.session_state[f"confirm_del_lit_{sel_id}"]
                        st.rerun()
                    except Exception as e:
                        st.error(f"削除に失敗しました: {e}")
            with c2:
                if st.button("キャンセル",key=f"cancel_del_lit_{sel_id}"):
                    del st.session_state[f"confirm_del_lit_{sel_id}"]
                    st.rerun()

    elif choice=="イベント":
        rows=db.fetch_all_events()
        if not rows:
            st.info("イベントデータがまだありません。")
            return
        lits={l["literature_id"]:l["title"] or l["doi"] for l in db.fetch_all_literatures()}
        smps={s["sample_id"]:s["human_id"] for s in db.fetch_all_samples()}
        display_df=pd.DataFrame(rows)
        display_df["ID"]=display_df["event_id"].str[:4]
        display_df["日付"]=display_df["created_at"].str[:10]
        display_df["参照文献"]=display_df["reference_literature_id"].map(lits).fillna("-")
        display_df["元サンプル"]=display_df["input_sample_id"].map(smps).fillna("-")
        display_df["備考"]=display_df["remarks"].fillna("-").str[:30]
        display_df["動機"]=display_df["motivation"].fillna("-").str[:30]
        cols=["select","ID","event_type","target_material","日付","元サンプル","参照文献","動機","備考"]
        sel_id=_get_selected_id(rows,"event_id",display_cols=cols)
        if not sel_id:return
        literatures=db.fetch_all_literatures()
        samples=db.fetch_all_samples()
        target=next(r for r in rows if r["event_id"]==sel_id)
        lit_options={"(なし)":None}
        for l in literatures:lit_options[build_literature_label(l)]=l["literature_id"]
        smp_options={"(なし)":None}
        for s in samples:smp_options[f"{s['human_id']} ({s['form']})"]=s["sample_id"]
        evt_options={"(なし)":None}
        for e in rows:evt_options[build_event_label(e)]=e["event_id"]
        target_input_sample_ids=target.get("input_sample_ids") or []
        target_reference_literature_ids=target.get("reference_literature_ids") or []
        target_reference_event_ids=target.get("reference_event_ids") or []
        default_smp_keys=[k for k,v in smp_options.items() if v in target_input_sample_ids]
        default_lit_keys=[k for k,v in lit_options.items() if v in target_reference_literature_ids]
        default_evt_keys=[k for k,v in evt_options.items() if v in target_reference_event_ids]
        with st.form("form_edit_evt"):
            col1,col2=st.columns(2)
            with col1:
                proj=st.text_input("プロジェクトID",value=target["project_id"])
                mat=st.text_input("対象物質",value=target["target_material"])
            with col2:
                ref_lits=st.multiselect("参照文献",list(lit_options.keys()),default=default_lit_keys)
                in_smps=st.multiselect("元サンプル",list(smp_options.keys()),default=default_smp_keys)
                ref_evts=st.multiselect("参照イベント",list(evt_options.keys()),default=default_evt_keys)
            motivation=st.text_area("動機",value=target["motivation"] or "")
            remarks=st.text_area("備考",value=target["remarks"] or "")
            schema=EVENT_SCHEMAS.get(target.get("event_type"),{})
            existing_params=_json_or_raw(target.get("parameters") or "{}")
            ui_params=render_dynamic_form(schema,key_prefix=f"edit_evt_params_{sel_id}",initial_data=existing_params)
            if st.form_submit_button("イベント情報を反映して更新する"):
                try:
                    selected_smp_ids=list(dict.fromkeys([smp_options[k] for k in in_smps if smp_options.get(k)]))
                    selected_lit_ids=list(dict.fromkeys([lit_options[k] for k in ref_lits if lit_options.get(k)]))
                    selected_evt_ids=list(dict.fromkeys([evt_options[k] for k in ref_evts if evt_options.get(k)]))
                    merged_params={**existing_params,**ui_params}
                    target.update({
                        "project_id":proj,"target_material":mat,"motivation":motivation,"remarks":remarks,
                        "reference_literature_id":selected_lit_ids[0] if selected_lit_ids else None,
                        "input_sample_id":selected_smp_ids[0] if selected_smp_ids else None,
                        "reference_event_id":selected_evt_ids[0] if selected_evt_ids else None,
                        "input_sample_ids":selected_smp_ids,
                        "reference_literature_ids":selected_lit_ids,
                        "reference_event_ids":selected_evt_ids,
                        "parameters":merged_params
                    })
                    db.update_event(Event(**target))
                    st.session_state.data_mgmt_msg="更新しました。"
                    st.rerun()
                except Exception as e:
                    st.error(f"エラー: {e}")
        col_copy,col_del=st.columns(2)
        with col_copy:
            if st.button("コピーして新規作成",key=f"copy_btn_evt_{sel_id}"):
                try:
                    existing_params=_json_or_raw(target.get("parameters") or "{}")
                    new_evt=Event(
                        project_id=target["project_id"],
                        target_material=target["target_material"],
                        event_type=target["event_type"],
                        input_sample_ids=target_input_sample_ids,
                        reference_event_ids=target_reference_event_ids,
                        reference_literature_ids=target_reference_literature_ids,
                        motivation=target.get("motivation"),
                        parameters=existing_params if isinstance(existing_params,dict) else {},
                        remarks=target.get("remarks")
                    )
                    db.insert_event(new_evt)
                    st.session_state.data_mgmt_msg=f"コピーを作成しました (ID: {new_evt.event_id})"
                    st.rerun()
                except Exception as e:
                    st.error(f"コピーに失敗しました: {e}")
        with col_del:
            if st.button("このイベントを削除する",key=f"del_btn_evt_{sel_id}"):
                st.session_state[f"confirm_del_evt_{sel_id}"]=True
        if st.session_state.get(f"confirm_del_evt_{sel_id}"):
            st.warning("本当にこのイベントを削除しますか？")
            c1,c2=st.columns(2)
            with c1:
                if st.button("はい、削除します",type="primary",key=f"do_del_evt_{sel_id}"):
                    db.delete_event(sel_id)
                    st.session_state.data_mgmt_msg="削除しました。"
                    del st.session_state[f"confirm_del_evt_{sel_id}"]
                    st.rerun()
            with c2:
                if st.button("キャンセル",key=f"cancel_del_evt_{sel_id}"):
                    del st.session_state[f"confirm_del_evt_{sel_id}"]
                    st.rerun()

    elif choice=="サンプル":
        rows=db.fetch_all_samples()
        if not rows:
            st.info("サンプルデータがまだありません。")
            return
        events_raw=db.fetch_all_events()
        events_map={e["event_id"]:f"{e['event_type']} on {e['target_material']}" for e in events_raw}
        df=pd.DataFrame(rows)
        df["select"]=False
        df["ID"]=df["sample_id"].str[:4]
        df["日付"]=df["created_at"].str[:10]
        df["元イベント"]=df["source_event_id"].map(events_map).fillna("-")
        df["備考"]=df["remarks"].fillna("-").str[:30]
        cols=["select","ID","human_id","form","日付","元イベント","location","備考"]
        sel_id=_get_selected_id(df.to_dict("records"),"sample_id",display_cols=cols)
        if not sel_id:return
        target=next(r for r in rows if r["sample_id"]==sel_id)
        with st.form("form_edit_smp"):
            col1,col2=st.columns(2)
            with col1:
                h_id=st.text_input("人間用識別ID",value=target["human_id"])
                form=st.text_input("形状 (Form)",value=target["form"])
            with col2:
                loc=st.text_input("保管場所",value=target["location"] or "")
            remarks=st.text_area("備考",value=target["remarks"] or "")
            schema=SAMPLE_FORM_SCHEMAS.get(target.get("form"),{})
            existing_params=_json_or_raw(target.get("parameters") or "{}")
            ui_params=render_dynamic_form(schema,key_prefix=f"edit_smp_params_{sel_id}",initial_data=existing_params)
            if st.form_submit_button("サンプル情報を反映して更新する"):
                try:
                    merged_params={**existing_params,**ui_params}
                    target.update({
                        "human_id":h_id,"form":form,"parameters":merged_params,"location":loc,"remarks":remarks
                    })
                    db.update_sample(Sample(**target))
                    st.session_state.data_mgmt_msg="更新しました。"
                    st.rerun()
                except Exception as e:
                    st.error(f"エラー: {e}")
        col_copy,col_del=st.columns(2)
        with col_copy:
            if st.button("コピーして新規作成",key=f"copy_btn_smp_{sel_id}"):
                try:
                    existing_params=_json_or_raw(target.get("parameters") or "{}")
                    new_smp=Sample(
                        source_event_id=target["source_event_id"],
                        human_id=f"{target['human_id']}_copy",
                        form=target["form"],
                        parameters=existing_params if isinstance(existing_params,dict) else {},
                        location=target.get("location"),
                        remarks=target.get("remarks")
                    )
                    db.insert_sample(new_smp)
                    st.session_state.data_mgmt_msg=f"コピーを作成しました (ID: {new_smp.sample_id})"
                    st.rerun()
                except Exception as e:
                    st.error(f"コピーに失敗しました: {e}")
        with col_del:
            if st.button("このサンプルを削除する",key=f"del_btn_smp_{sel_id}"):
                st.session_state[f"confirm_del_smp_{sel_id}"]=True
        if st.session_state.get(f"confirm_del_smp_{sel_id}"):
            st.warning("本当にこのサンプルを削除しますか？")
            c1,c2=st.columns(2)
            with c1:
                if st.button("はい、削除します",type="primary",key=f"do_del_smp_{sel_id}"):
                    db.delete_sample(sel_id)
                    st.session_state.data_mgmt_msg="削除しました。"
                    del st.session_state[f"confirm_del_smp_{sel_id}"]
                    st.rerun()
            with c2:
                if st.button("キャンセル",key=f"cancel_del_smp_{sel_id}"):
                    del st.session_state[f"confirm_del_smp_{sel_id}"]
                    st.rerun()

    elif choice=="測定":
        rows=db.fetch_all_measurements()
        if not rows:
            st.info("測定データがまだありません。")
            return
        smps={s["sample_id"]:s["human_id"] for s in db.fetch_all_samples()}
        df=pd.DataFrame(rows)
        df["select"]=False
        df["ID"]=df["measurement_id"].str[:4]
        df["対象サンプル"]=df["sample_id"].map(smps).fillna("-")
        df["日付"]=df["measured_at"].str[:10]
        df["備考"]=df["remarks"].fillna("-").str[:30]
        cols=["select","ID","日付","measurement_type","対象サンプル","operator","備考"]
        sel_id=_get_selected_id(df.to_dict("records"),"measurement_id",display_cols=cols)
        if not sel_id:return
        target=next(r for r in rows if r["measurement_id"]==sel_id)
        st.markdown("**現在の保存データ**")
        st.write(f"Raw: {target.get('raw_data_path') or '-'}")
        st.write(f"Processed: {target.get('processed_data_path') or '-'}")
        extracted_preview=_json_or_raw(target.get("extracted_features") or "{}")
        if not isinstance(extracted_preview,dict):extracted_preview={}
        conditions_preview=_json_or_raw(target.get("conditions") or "{}")
        if not isinstance(conditions_preview,dict):conditions_preview={}
        with st.expander("詳細JSON（Conditions / Extracted Features）"):
            st.markdown("**Conditions**")
            st.json(conditions_preview)
            st.markdown("**Extracted Features**")
            st.json(extracted_preview)
        xrd_sim_preview=extracted_preview.get("xrd_simulation") if isinstance(extracted_preview.get("xrd_simulation"),dict) else None
        if str(target.get("measurement_type") or "").upper()=="XRD":
            if xrd_sim_preview:
                st.info(f"XRD simulation: mode={xrd_sim_preview.get('mode')} / target={xrd_sim_preview.get('target')} / peaks={xrd_sim_preview.get('peak_count')}")
            else:
                st.info("XRD simulation: 未保存")
            plot_rel=extracted_preview.get("xrd_plot_path")
            plot_abs=_resolve_data_abs_path(plot_rel)
            if plot_abs:
                try:
                    with open(plot_abs,"rb") as f:
                        st.image(f.read(),caption="Saved XRD plot",use_container_width=True)
                except Exception:
                    st.warning(f"XRD画像の読込に失敗しました: {plot_rel}")
            processed_abs=_resolve_data_abs_path(target.get("processed_data_path"))
            if processed_abs:
                try:
                    with open(processed_abs,"rb") as f:
                        st.download_button(
                            label="保存済みXRD CSVをダウンロード",
                            data=f.read(),
                            file_name=f"{target.get('measurement_id')[:8]}_xrd_profile.csv",
                            mime="text/csv",
                            key=f"btn_dl_saved_xrd_{sel_id}",
                        )
                except Exception:
                    st.warning("保存済みCSVの読込に失敗しました。")
        with st.form("form_edit_msr"):
            col1,col2=st.columns(2)
            with col1:
                op=st.text_input("測定者",value=target["operator"] or "")
                m_date=st.date_input("測定日",value=pd.to_datetime(target["measured_at"]))
            with col2:
                m_type=st.text_input("測定タイプ",value=target["measurement_type"])
            remarks=st.text_area("備考",value=target["remarks"] or "")
            schema=MEASUREMENT_SCHEMAS.get(target.get("measurement_type"),{})
            existing_conditions=_json_or_raw(target.get("conditions") or "{}")
            ui_conditions=render_dynamic_form(schema,key_prefix=f"edit_msr_cond_{sel_id}",initial_data=existing_conditions)
            if st.form_submit_button("測定情報を反映して更新する"):
                try:
                    merged_conditions={**existing_conditions,**ui_conditions}
                    extracted_features=_json_or_raw(target.get("extracted_features") or "{}")
                    if not isinstance(extracted_features,dict):extracted_features={}
                    target.update({
                        "operator":op,"measured_at":m_date,"measurement_type":m_type,"remarks":remarks,
                        "conditions":merged_conditions,
                        "extracted_features":extracted_features
                    })
                    db.update_measurement(Measurement(**target))
                    st.session_state.data_mgmt_msg="更新しました。"
                    st.rerun()
                except Exception as e:
                    st.error(f"エラー: {e}")
        col_copy,col_del=st.columns(2)
        with col_copy:
            if st.button("コピーして新規作成",key=f"copy_btn_msr_{sel_id}"):
                try:
                    existing_conditions=_json_or_raw(target.get("conditions") or "{}")
                    new_msr=Measurement(
                        sample_id=target["sample_id"],
                        measurement_type=target["measurement_type"],
                        conditions=existing_conditions if isinstance(existing_conditions,dict) else {},
                        operator=target.get("operator"),
                        measured_at=pd.to_datetime(target["measured_at"]).date(),
                        remarks=target.get("remarks")
                    )
                    db.insert_measurement(new_msr)
                    st.session_state.data_mgmt_msg=f"コピーを作成しました (ID: {new_msr.measurement_id})"
                    st.rerun()
                except Exception as e:
                    st.error(f"コピーに失敗しました: {e}")
        with col_del:
            if st.button("この測定を削除する",key=f"del_btn_msr_{sel_id}"):
                st.session_state[f"confirm_del_msr_{sel_id}"]=True
        if st.session_state.get(f"confirm_del_msr_{sel_id}"):
            st.warning("本当にこの測定を削除しますか？")
            c1,c2=st.columns(2)
            with c1:
                if st.button("はい、削除します",type="primary",key=f"do_del_msr_{sel_id}"):
                    db.delete_measurement(sel_id)
                    st.session_state.data_mgmt_msg="削除しました。"
                    del st.session_state[f"confirm_del_msr_{sel_id}"]
                    st.rerun()
            with c2:
                if st.button("キャンセル",key=f"cancel_del_msr_{sel_id}"):
                    del st.session_state[f"confirm_del_msr_{sel_id}"]
                    st.rerun()

    elif choice=="物質":
        rows=db.fetch_all_materials()
        if not rows:
            st.info("物質データがまだありません。")
            return
        lits={l["literature_id"]:l["title"] or l["doi"] for l in db.fetch_all_literatures()}
        mat_name_map={m["material_id"]:m["name"] for m in rows}
        df=pd.DataFrame(rows)
        df["select"]=False
        df["ID"]=df["material_id"].str[:4]
        df["参照文献"]=df["reference_literature_id"].map(lits).fillna("-")
        df["日付"]=df["created_at"].str[:10]
        df["備考"]=df["remarks"].fillna("-").str[:30]
        cols=["select","ID","name","参照文献","日付","備考"]
        sel_id=_get_selected_id(df.to_dict("records"),"material_id",display_cols=cols)
        if not sel_id:return
        literatures=db.fetch_all_literatures()
        all_materials=db.fetch_all_materials()
        target=next(r for r in rows if r["material_id"]==sel_id)
        cif_rel=target.get("cif_file_path")
        cif_abs=_resolve_data_abs_path(cif_rel)
        st.markdown("**現在の保存データ**")
        st.write(f"CIF: {cif_rel or '-'}")
        st.write(f"CIF status: {'OK' if cif_abs else 'missing'}")
        if cif_abs:
            try:
                with open(cif_abs,"rb") as f:cif_bytes_raw=f.read()
                cif_bytes=_normalize_cif_fraction_tokens(cif_bytes_raw)
                cif_name=os.path.basename(cif_abs)
            except Exception as e:
                cif_bytes,cif_name=None,None
                st.warning(f"CIFファイルの読み込みに失敗しました: {e}")
            if cif_bytes:
                st.write("---")
                st.markdown("**【CIFから結晶構造描画 (crystal_toolkit 3D)】**")
                import hashlib
                cif_hash=hashlib.md5(cif_bytes).hexdigest()
                cache_key=f"dm_struct_preview_{cif_hash}"
                if cache_key not in st.session_state:
                    with st.spinner("crystal_toolkit で結晶構造を描画中..."):
                        graph_obj,graph_payload,graph_err=_run_structure_preview(cif_bytes,cif_name)
                    st.session_state[cache_key]=(graph_obj,graph_payload,graph_err)
                else:
                    graph_obj,graph_payload,graph_err=st.session_state[cache_key]
                if graph_err:
                    st.warning(graph_err)
                elif graph_payload:
                    st.success("結晶構造の描画を生成しました。")
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
                    with st.expander("StructureGraph raw output"):st.text(str(graph_obj))
                xrd_plugin=_load_measurement_plugin("XRD")
                if xrd_plugin and hasattr(xrd_plugin,"simulate_xrd_for_cif_bytes"):
                    st.write("---")
                    st.markdown("**【CIFからXRDシミュレーション】**")
                    c1,c2,c3=st.columns(3)
                    with c1:
                        mat_xrd_mode=st.selectbox(
                            "シミュレーション種別",["Powder","TMDC c-axis Oriented"],
                            key=f"dm_mat_xrd_mode_{sel_id}",
                        )
                    with c2:
                        mat_xrd_target=st.selectbox(
                            "X-ray Target",["CuKa","MoKa","CoKa","FeKa"],
                            key=f"dm_mat_xrd_target_{sel_id}",
                        )
                    with c3:
                        mat_xrd_peak_width=st.number_input(
                            "Peak width (FWHM)",min_value=0.01,max_value=5.0,value=0.15,step=0.01,
                            key=f"dm_mat_xrd_pw_{sel_id}",
                        )
                    preview_conditions={
                        "simulation_mode":mat_xrd_mode,
                        "target":mat_xrd_target,
                        "two_theta_min":5.0,
                        "two_theta_max":90.0,
                        "profile_step":0.02,
                        "peak_width":float(mat_xrd_peak_width),
                    }
                    try:
                        with st.spinner("XRDパターンを生成中..."):
                            sim_result,sim_err,png_bytes,plot_err=_cached_xrd_preview(
                                cif_bytes=cif_bytes,cif_name=cif_name,
                                conditions=preview_conditions,
                                material_name=target.get("name") or "Unknown",
                            )
                        if sim_result:
                            if png_bytes:st.image(png_bytes,caption=f"XRD simulated pattern ({sim_result.get('mode')})",use_container_width=True)
                            if plot_err:st.warning(plot_err)
                            st.info(f"mode={sim_result.get('mode')} / target={sim_result.get('target')} / peaks={sim_result.get('peak_count')}")
                        elif sim_err:st.warning(sim_err)
                    except Exception as e:
                        st.error(f"XRDプレビュー生成に失敗しました: {e}")
        curr_impurity_ids_view=target.get("impurity_material_ids") or []
        curr_polymorph_ids_view=target.get("polymorph_material_ids") or []
        impurity_names=[mat_name_map.get(mid,f"(不明:{str(mid)[:4]})") for mid in curr_impurity_ids_view if mid in mat_name_map]
        polymorph_names=[mat_name_map.get(mid,f"(不明:{str(mid)[:4]})") for mid in curr_polymorph_ids_view if mid in mat_name_map]
        st.markdown("**関連物質リンク（現在値）**")
        st.write(f"不純物リンク: {', '.join(impurity_names) if impurity_names else 'なし'}")
        st.write(f"多型リンク: {', '.join(polymorph_names) if polymorph_names else 'なし'}")
        lit_options={"(変更なし/なし)":target["reference_literature_id"]}
        for l in literatures:lit_options[build_literature_label(l)]=l["literature_id"]
        with st.form("form_edit_mat"):
            name=st.text_input("物質名",value=target["name"])
            curr_props=json.loads(target["properties"]) if isinstance(target["properties"],str) else target["properties"]
            prop_list=[{"Property":k,"Value":v} for k,v in curr_props.items()]
            if not prop_list:prop_list=[{"Property":"","Value":""}]
            st.write("物性値 (Properties)")
            edited_prop_df=st.data_editor(pd.DataFrame(prop_list),num_rows="dynamic",hide_index=True,key="edit_mat_prop_editor")
            mat_options={}
            for m in all_materials:
                if m["material_id"]==sel_id:continue
                mat_options[f"{m['name']} #{m['material_id'][:4]}"]=m["material_id"]
            curr_impurity_ids=target.get("impurity_material_ids") or []
            curr_polymorph_ids=target.get("polymorph_material_ids") or []
            default_impurity_keys=[k for k,v in mat_options.items() if v in curr_impurity_ids]
            default_polymorph_keys=[k for k,v in mat_options.items() if v in curr_polymorph_ids]
            st.write("関連物質リンク（オプション）")
            selected_impurities=st.multiselect(
                "不純物として関連づける物質（オプション）",
                list(mat_options.keys()),
                default=default_impurity_keys,
                key=f"edit_mat_impurity_{sel_id}"
            )
            selected_polymorphs=st.multiselect(
                "多型として関連づける物質（オプション）",
                list(mat_options.keys()),
                default=default_polymorph_keys,
                key=f"edit_mat_polymorph_{sel_id}"
            )
            ref_lit=st.selectbox("参照文献",list(lit_options.keys()))
            remarks=st.text_area("備考",value=target["remarks"] or "")
            uploaded_cif=st.file_uploader("CIFファイルの差し替え・更新",type=["cif","txt"])
            if st.form_submit_button("物質情報を反映して更新する"):
                try:
                    new_props={row["Property"]:row["Value"] for _,row in edited_prop_df.iterrows() if row["Property"]}
                    impurity_ids=[mat_options[k] for k in selected_impurities if mat_options.get(k)]
                    polymorph_ids=[mat_options[k] for k in selected_polymorphs if mat_options.get(k)]
                    target.update({
                        "name":name,"remarks":remarks,"reference_literature_id":lit_options[ref_lit],
                        "properties":new_props,
                        "impurity_material_ids":impurity_ids,
                        "polymorph_material_ids":polymorph_ids
                    })
                    if uploaded_cif:
                        updated_cif=_normalize_cif_fraction_tokens(uploaded_cif.getvalue())
                        target["cif_file_path"]=fm.save_material_file(sel_id,uploaded_cif.name,updated_cif)
                    db.update_material(Material(**target))
                    st.session_state.data_mgmt_msg="更新しました。"
                    st.rerun()
                except Exception as e:
                    st.error(f"エラー: {e}")
        col_copy,col_del=st.columns(2)
        with col_copy:
            if st.button("コピーして新規作成",key=f"copy_btn_mat_{sel_id}"):
                try:
                    curr_props=json.loads(target["properties"]) if isinstance(target["properties"],str) else target["properties"]
                    new_mat=Material(
                        name=f"{target['name']}_copy",
                        properties=curr_props if isinstance(curr_props,dict) else {},
                        reference_literature_id=target.get("reference_literature_id"),
                        impurity_material_ids=curr_impurity_ids_view,
                        polymorph_material_ids=curr_polymorph_ids_view,
                        remarks=target.get("remarks")
                    )
                    db.insert_material(new_mat)
                    st.session_state.data_mgmt_msg=f"コピーを作成しました (ID: {new_mat.material_id})"
                    st.rerun()
                except Exception as e:
                    st.error(f"コピーに失敗しました: {e}")
        with col_del:
            if st.button("この物質を削除する",key=f"del_btn_mat_{sel_id}"):
                st.session_state[f"confirm_del_mat_{sel_id}"]=True
        if st.session_state.get(f"confirm_del_mat_{sel_id}"):
            st.warning("本当にこの物質を削除しますか？")
            c1,c2=st.columns(2)
            with c1:
                if st.button("はい、削除します",type="primary",key=f"do_del_mat_{sel_id}"):
                    db.delete_material(sel_id)
                    st.session_state.data_mgmt_msg="削除しました。"
                    del st.session_state[f"confirm_del_mat_{sel_id}"]
                    st.rerun()
            with c2:
                if st.button("キャンセル",key=f"cancel_del_mat_{sel_id}"):
                    del st.session_state[f"confirm_del_mat_{sel_id}"]
                    st.rerun()
