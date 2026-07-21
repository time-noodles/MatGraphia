import streamlit as st
import database as db
import pandas as pd
from datetime import date
from schemas import Task
from ui.helpers import log_errors

TITLE="タスクリスト"
ORDER=7

# 画面描画
@log_errors("タスクリスト")
def render():
    st.header("タスクリスト")
    st.markdown("実験の予定やToDoタスクを管理します。")
    tasks=db.fetch_all_tasks()
    samples=db.fetch_all_samples()
    events=db.fetch_all_events()
    materials=db.fetch_all_materials()
    sample_opts={"(なし)":None}
    for s in samples:sample_opts[f"Sample: {s['human_id']} ({s['form']})"]=s["sample_id"]
    event_opts={"(なし)":None}
    for e in events:event_opts[f"Event: {e['event_type']} on {e['target_material']} ({e['event_id'][:4]})"]=e["event_id"]
    mat_opts={"(なし)":None}
    for m in materials:mat_opts[f"Material: {m['name']} ({m['material_id'][:4]})"]=m["material_id"]
    with st.expander("新規タスクの追加"):
        with st.form("new_task_form"):
            title=st.text_input("タスク名 (必須)",placeholder="例: XRD測定の実施")
            due_date=st.date_input("期限",value=date.today())
            remarks=st.text_area("備考",placeholder="#重要 などのタグも入力可能")
            rel_type=st.selectbox("関連データ種別",["なし","Sample","Event","Material"])
            if rel_type=="Sample":rel_id=st.selectbox("関連サンプル",list(sample_opts.keys()))
            elif rel_type=="Event":rel_id=st.selectbox("関連イベント",list(event_opts.keys()))
            elif rel_type=="Material":rel_id=st.selectbox("関連物質",list(mat_opts.keys()))
            else:rel_id="(なし)"
            submitted=st.form_submit_button("追加")
            if submitted:
                if not title:
                    st.error("【必須エラー】 タスク名は必須です。")
                    return
                try:
                    target_rel_id=None
                    if rel_type=="Sample":target_rel_id=sample_opts[rel_id]
                    elif rel_type=="Event":target_rel_id=event_opts[rel_id]
                    elif rel_type=="Material":target_rel_id=mat_opts[rel_id]
                    tsk=Task(
                        title=title,
                        status="Todo",
                        related_entity_type=rel_type if rel_type!="なし" else None,
                        related_entity_id=target_rel_id,
                        due_date=due_date.isoformat(),
                        remarks=remarks
                    )
                    db.insert_task(tsk)
                    st.success("タスクを追加しました！")
                    st.rerun()
                except Exception as e:
                    st.error(f"タスク追加時にエラーが発生しました: {e}")
    if not tasks:
        st.info("タスクはありません。")
        return
    st.write("---")
    st.markdown("**タスク一覧**")
    for t in tasks:
        with st.container():
            col_status,col_title,col_due,col_rel,col_action=st.columns([1.5,3,1.5,2,2])
            with col_status:
                new_status=st.selectbox(
                    "ステータス",
                    ["Todo","In Progress","Done"],
                    index=["Todo","In Progress","Done"].index(t["status"]),
                    key=f"status_{t['task_id']}"
                )
                if new_status!=t["status"]:
                    try:
                        t["status"]=new_status
                        db.update_task(Task(**t))
                        st.rerun()
                    except Exception as e:
                        st.error(f"更新エラー: {e}")
            with col_title:
                st.markdown(f"**{t['title']}**")
                if t["remarks"]:st.caption(t["remarks"])
            with col_due:
                st.write(t["due_date"] or "-")
            with col_rel:
                if t["related_entity_type"] and t["related_entity_id"]:
                    st.caption(f"{t['related_entity_type']}: {t['related_entity_id'][:8]}...")
                else:
                    st.write("-")
            with col_action:
                if st.button("削除",key=f"del_task_{t['task_id']}"):
                    try:
                        db.delete_task(t["task_id"])
                        st.success("削除しました。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"削除エラー: {e}")
        st.write("---")
