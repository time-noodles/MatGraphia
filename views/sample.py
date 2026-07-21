import streamlit as st
import database as db
import plugin_manager as pm
from ui.forms import render_dynamic_form
from ui.helpers import build_event_label,log_errors
from ui.validators import is_duplicate_sample

TITLE="サンプルの登録"
ORDER=4

# 画面描画
@log_errors("サンプルの登録")
def render():
    st.header("サンプルの登録")
    from schemas import Sample
    SAMPLE_FORM_SCHEMAS=pm.get_sample_schemas()
    events=db.fetch_all_events()
    samples=db.fetch_all_samples()
    if not events:
        st.warning("先にイベント（合成・加工など）を登録してください。")
        return
    evt_options={build_event_label(e):e["event_id"] for e in events}
    sample_type_options=list(SAMPLE_FORM_SCHEMAS.keys()) if SAMPLE_FORM_SCHEMAS else ["Single Crystal","Powder"]
    with st.form("sample_form"):
        source_event_key=st.selectbox("生成元のイベント",list(evt_options.keys()))
        source_event_id=evt_options[source_event_key]
        human_id=st.text_input("人間用識別バッチ名 (例: 01-Powder)",value="01-Test")
        form_type=st.selectbox("形状",sample_type_options)
        location=st.text_input("物理的な保管場所",value="デシケーターA")
        remarks=st.text_area("備考")
        schema=SAMPLE_FORM_SCHEMAS.get(form_type,{})
        parameters=render_dynamic_form(schema,key_prefix="sample")
        submitted=st.form_submit_button("サンプルを登録する")
        if submitted:
            new_smp_dict={"source_event_id":source_event_id,"human_id":human_id,"form":form_type}
            if is_duplicate_sample(new_smp_dict,samples):
                st.error("【重複エラー】 同じ生成元イベントに対し、同名・同形状のサンプルが既に登録されています。")
                return
            try:
                smp=Sample(
                    source_event_id=source_event_id,
                    human_id=human_id,
                    form=form_type,
                    parameters=parameters,
                    location=location,
                    remarks=remarks
                )
                db.insert_sample(smp)
                st.success(f"サンプルを登録しました！ (ID: {smp.sample_id})")
            except Exception as e:
                st.error(f"登録時にエラーが発生しました: {e}")
