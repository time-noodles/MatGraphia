import streamlit as st
import database as db
import plugin_manager as pm
from ui.forms import render_dynamic_form
from ui.helpers import build_event_label,log_errors
from ui.validators import is_duplicate_sample

TITLE="📌 サンプルの登録"
ORDER=5


# 画面描画
@log_errors("サンプルの登録")
def render():
    st.header("サンプルの登録")
    from schemas import Sample
    from ui.helpers import render_location_badge
    SAMPLE_FORM_SCHEMAS=pm.get_sample_schemas()
    events=db.fetch_all_events()
    samples=db.fetch_all_samples()
    if not events:
        st.warning("先にイベント（合成・加工など）を登録してください。")
        return

    # 保管場所絞り込み検索状態の確認
    search_loc_query = st.session_state.get("sample_location_search_query", "")
    if search_loc_query:
        st.info(f"📍 保管場所 「**{search_loc_query}**」 に保管されているサンプルの絞り込み表示中")
        filtered_s = [s for s in samples if search_loc_query.lower() in str(s.get("location") or "").lower()]
        if filtered_s:
            st.dataframe([{
                "Sample Human ID": s["human_id"],
                "Form": s["form"],
                "保管場所": s.get("location", "-"),
                "登録日": str(s.get("created_at"))[:10]
            } for s in filtered_s], hide_index=True)
        else:
            st.caption("該当するサンプルはありません。")
        if st.button("絞り込みを解除", key="btn_clear_loc_filter"):
            st.session_state["sample_location_search_query"] = ""
            st.rerun()
        st.write("---")

    evt_options={build_event_label(e):e["event_id"] for e in events}
    sample_type_options=list(SAMPLE_FORM_SCHEMAS.keys()) if SAMPLE_FORM_SCHEMAS else ["Single Crystal","Powder"]
    with st.container():
        source_event_key=st.selectbox("生成元のイベント",list(evt_options.keys()),key="draft_smp_evt")
        source_event_id=evt_options[source_event_key]
        human_id=st.text_input("人間用識別バッチ名 (例: 01-Powder)",value="01-Test",key="draft_smp_hid")
        form_type=st.selectbox("形状",sample_type_options,key="draft_smp_form")
        
        default_loc = search_loc_query if search_loc_query else "デシケーターA"
        location=st.text_input("物理的な保管場所 (例: デシケーター Box #A2, グローブボックス Shelf #3)",value=default_loc,key="draft_smp_loc")
        if location:
            render_location_badge(location, key_prefix="sample_form_loc")
            
        remarks=st.text_area("備考",key="draft_smp_remarks")
        schema=SAMPLE_FORM_SCHEMAS.get(form_type,{})
        parameters=render_dynamic_form(schema,key_prefix="sample")
        col1,col2=st.columns(2)
        with col1:
            if st.button("サンプルを登録する (本登録)",type="primary"):
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
                        remarks=remarks,
                        is_draft=False
                    )
                    db.insert_sample(smp)
                    st.success(f"サンプルを本登録しました！ (ID: {smp.sample_id})")
                except Exception as e:
                    st.error(f"登録時にエラーが発生しました: {e}")
        with col2:
            if st.button("下書き（仮登録）する"):
                try:
                    smp=Sample(
                        source_event_id=source_event_id,
                        human_id=human_id or "Draft-Sample",
                        form=form_type or "Powder",
                        parameters=parameters or {},
                        location=location or "",
                        remarks=remarks or "",
                        is_draft=True
                    )
                    db.insert_sample(smp)
                    st.success(f"サンプルを下書き（仮登録）しました！データ管理画面で後から補完・本登録できます。(ID: {smp.sample_id})")
                except Exception as e:
                    st.error(f"下書き登録時にエラーが発生しました: {e}")

