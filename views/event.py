import json
import streamlit as st
import database as db
import plugin_manager as pm
from ui.forms import render_dynamic_form
from ui.helpers import (
    _json_or_raw,get_sample_ancestry,
    build_sample_label,build_literature_label,build_event_label,log_errors
)
from ui.validators import is_duplicate_event

TITLE="イベントの登録"
ORDER=3

# 画面描画
@log_errors("イベントの登録")
def render():
    st.header("イベント（合成・加工など）の登録")
    from schemas import Event
    EVENT_SCHEMAS=pm.get_event_schemas()
    samples=db.fetch_all_samples()
    literatures=db.fetch_all_literatures()
    events=db.fetch_all_events()
    events_dict={e["event_id"]:e for e in events}
    with st.expander("データ絞り込み条件 (検索)"):
        search_q=st.text_input("サンプル名や物質名で絞り込み")
    sample_options={"選択なし (None)":None}
    for s in samples:
        label=build_sample_label(s,events_dict=events_dict,samples_list=samples)
        if search_q and search_q.lower() not in label.lower():continue
        sample_options[label]=s["sample_id"]
    lit_options={"選択なし (None)":None}
    for l in literatures:
        lit_options[build_literature_label(l)]=l["literature_id"]
    evt_options={"選択なし (None)":None}
    for e in events:
        evt_options[build_event_label(e)]=e["event_id"]
    evt_type_options=list(EVENT_SCHEMAS.keys()) if EVENT_SCHEMAS else ["Solid-State","CVT"]
    all_projects=sorted(list(set(e["project_id"] for e in events if e["project_id"])))
    all_materials=sorted(list(set(e["target_material"] for e in events if e["target_material"])))
    mat_sel_state=st.session_state.get("evt_mat_sel","(新規作成)")
    prefill_material=mat_sel_state if mat_sel_state!="(新規作成)" else None
    if prefill_material and st.session_state.get("evt_prefill_material")!=prefill_material:
        template=next((e for e in events if e.get("target_material")==prefill_material),None)
        if template:
            st.session_state["evt_proj_sel"]=template.get("project_id") if template.get("project_id") in all_projects else "(新規作成)"
            st.session_state["evt_project_id_new"]=template.get("project_id") or st.session_state.get("evt_project_id_new","Project-A")
            st.session_state["evt_event_type"]=template.get("event_type") if template.get("event_type") in evt_type_options else evt_type_options[0]
            st.session_state["evt_motivation"]=template.get("motivation") or ""
            st.session_state["evt_remarks"]=template.get("remarks") or ""
            sample_id_to_label={v:k for k,v in sample_options.items() if v}
            lit_id_to_label={v:k for k,v in lit_options.items() if v}
            evt_id_to_label={v:k for k,v in evt_options.items() if v}
            t_sample_ids=_json_or_raw(template.get("input_sample_ids") or "[]")
            t_lit_ids=_json_or_raw(template.get("reference_literature_ids") or "[]")
            t_evt_ids=_json_or_raw(template.get("reference_event_ids") or "[]")
            if not t_sample_ids and template.get("input_sample_id"):
                t_sample_ids=[template.get("input_sample_id")]
            if not t_lit_ids and template.get("reference_literature_id"):
                t_lit_ids=[template.get("reference_literature_id")]
            if not t_evt_ids and template.get("reference_event_id"):
                t_evt_ids=[template.get("reference_event_id")]
            st.session_state["evt_input_samples"]=[sample_id_to_label[sid] for sid in t_sample_ids if sid in sample_id_to_label]
            st.session_state["evt_ref_lits"]=[lit_id_to_label[lid] for lid in t_lit_ids if lid in lit_id_to_label]
            st.session_state["evt_ref_events"]=[evt_id_to_label[eid] for eid in t_evt_ids if eid in evt_id_to_label]
            template_params=_json_or_raw(template.get("parameters") or "{}")
            st.session_state["evt_prefill_params"]=template_params
            st.session_state["evt_form_seed"]=int(st.session_state.get("evt_form_seed",0))+1
        st.session_state["evt_prefill_material"]=prefill_material
    with st.container():
        col_proj,col_mat=st.columns(2)
        with col_proj:
            proj_sel=st.selectbox("プロジェクトID (必須)",["(新規作成)"]+all_projects,key="evt_proj_sel")
            project_id=st.text_input("新規プロジェクト名を入力",value="Project-A",key="evt_project_id_new") if proj_sel=="(新規作成)" else proj_sel
        with col_mat:
            mat_sel=st.selectbox("対象物質 (必須)",["(新規作成)"]+all_materials,key="evt_mat_sel")
            target_material=st.text_input("新規対象物質名を入力",value="Bi2Te3",key="evt_target_material_new") if mat_sel=="(新規作成)" else mat_sel
        event_type=st.selectbox("イベントタイプ",evt_type_options,key="evt_event_type")
        st.write("---")
        st.write("**派生元 (サンプル・イベント・文献は複数選択可 / いずれか1件以上必須)**")
        col1,col2=st.columns(2)
        with col1:
            input_samples=st.multiselect("元サンプル (検索は上部で可能)",list(sample_options.keys()),key="evt_input_samples")
            ref_events=st.multiselect("参照元イベント",list(evt_options.keys()),key="evt_ref_events")
        with col2:
            ref_lits=st.multiselect("ベース文献",list(lit_options.keys()),key="evt_ref_lits")
        motivation=st.text_area("動機 (Motivation) (必須)",placeholder="なぜこの条件で実験を行うのか？",key="evt_motivation")
        schema=EVENT_SCHEMAS.get(event_type,{})
        prefill_params=st.session_state.get("evt_prefill_params",{}) if isinstance(st.session_state.get("evt_prefill_params",{}),dict) else {}
        form_seed=int(st.session_state.get("evt_form_seed",0))
        parameters=render_dynamic_form(schema,key_prefix=f"events_{form_seed}",initial_data=prefill_params)
        remarks=st.text_area("備考",key="evt_remarks")
        if st.button("イベントを登録する"):
            if not project_id or not target_material or not motivation or not event_type:
                st.error("【必須エラー】 プロジェクトID、対象物質、イベントタイプ、動機(Motivation) はすべて必須です。")
                return
            selected_sample_ids=[sample_options[k] for k in input_samples if sample_options.get(k)]
            selected_event_ids=[evt_options[k] for k in ref_events if evt_options.get(k)]
            selected_lit_ids=[lit_options[k] for k in ref_lits if lit_options.get(k)]
            if not selected_sample_ids and not selected_event_ids and not selected_lit_ids:
                st.error("【必須エラー】 派生元となる「元サンプル」「参照元イベント」「ベース文献」のいずれか1つ以上は必ず選択してください。")
                return
            new_evt_dict={
                "project_id":project_id,
                "target_material":target_material,
                "event_type":event_type,
                "input_sample_ids":selected_sample_ids,
                "reference_event_ids":selected_event_ids,
                "reference_literature_ids":selected_lit_ids,
                "parameters":parameters,
            }
            if is_duplicate_event(new_evt_dict,events):
                st.error("【重複エラー】 全く同じ条件（プロジェクト, 物質, 手法, および表パラメータ等）のイベントが既に登録されています！")
                return
            try:
                evt=Event(
                    project_id=project_id,
                    target_material=target_material,
                    event_type=event_type,
                    input_sample_ids=selected_sample_ids,
                    reference_event_ids=selected_event_ids,
                    reference_literature_ids=selected_lit_ids,
                    motivation=motivation,
                    parameters=parameters,
                    remarks=remarks
                )
                db.insert_event(evt)
                st.success(f"イベントを登録しました！ (ID: {evt.event_id})")
            except Exception as e:
                st.error(f"登録時にエラーが発生しました: {e}")
