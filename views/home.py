import streamlit as st
import database as db
from schemas import Task
from ui.helpers import log_errors

TITLE="ホーム (Homepage)"
ORDER=0

# 画面描画
@log_errors("ホーム")
def render():
    st.title("🏠 MatGraphia ダッシュボード")
    st.markdown("実験データ・物質情報・合成プロセスとタスクを一元管理するホーム画面です。")

    def _navigate_to(target_page_title):
        st.session_state["nav_menu"]=target_page_title
        st.rerun()

    # 全データの取得
    literatures=db.fetch_all_literatures()
    events=db.fetch_all_events()
    samples=db.fetch_all_samples()
    measurements=db.fetch_all_measurements()
    materials=db.fetch_all_materials()
    tasks=db.fetch_all_tasks()

    # 仮登録（下書き）データの抽出
    draft_lits=[l for l in literatures if l.get("is_draft")]
    draft_evts=[e for e in events if e.get("is_draft")]
    draft_smps=[s for s in samples if s.get("is_draft")]
    draft_msrs=[m for m in measurements if m.get("is_draft")]
    draft_mats=[m for m in materials if m.get("is_draft")]
    total_drafts=len(draft_lits)+len(draft_evts)+len(draft_smps)+len(draft_msrs)+len(draft_mats)

    # 1. メトリクスサマリー
    col1,col2,col3,col4,col5=st.columns(5)
    col1.metric("📚 文献",len(literatures))
    col2.metric("🧪 物質",len(materials))
    col3.metric("⚗️ イベント",len(events))
    col4.metric("📊 測定データ",len(measurements))
    col5.metric("⚠️ 下書き(仮登録)",total_drafts,delta=f"{total_drafts}件 未完" if total_drafts>0 else "完了",delta_color="inverse" if total_drafts>0 else "normal")

    st.write("---")

    col_left,col_right=st.columns([1,1])

    # 2. 仮登録（下書き）の管理とダイレクト補完遷移
    with col_left:
        st.subheader("📝 仮登録 (下書き) データ")
        if total_drafts==0:
            st.success("🎉 現在、すべてのデータが本登録済みです！")
        else:
            st.warning(f"現在 **{total_drafts}件** の仮登録データがあります。内容を補完して本登録を完了させましょう。")
            
            if draft_lits:
                st.markdown("**文献の仮登録:**")
                for dl in draft_lits:
                    st.caption(f"・ {dl.get('title') or dl.get('doi')} (ID: {dl.get('literature_id')[:6]})")
            if draft_evts:
                st.markdown("**イベントの仮登録:**")
                for de in draft_evts:
                    st.caption(f"・ [{de.get('event_type')}] {de.get('target_material')} (ID: {de.get('event_id')[:6]})")
            if draft_smps:
                st.markdown("**サンプルの仮登録:**")
                for ds in draft_smps:
                    st.caption(f"・ {ds.get('human_id')} ({ds.get('form')})")
            if draft_msrs:
                st.markdown("**測定データの仮登録:**")
                for dm in draft_msrs:
                    st.caption(f"・ [{dm.get('measurement_type')}] {dm.get('operator') or '未設定'}")
            if draft_mats:
                st.markdown("**物質の仮登録:**")
                for dm in draft_mats:
                    st.caption(f"・ {dm.get('name')}")
            
            if st.button("🔍 「データ管理・編集」画面で補完・本登録する",key="btn_nav_draft_mgmt",type="primary"):
                _navigate_to("データ管理・編集")

    # 3. 直近のTodo・タスク（ホームからの直接完了インタラクティブ操作）
    with col_right:
        st.subheader("✅ ToDo / タスク (直接完了可能)")
        todo_tasks=[t for t in tasks if t.get("status")!="Done"]
        if not todo_tasks:
            st.success("🎉 すべてのタスクが完了しています！")
        else:
            for t in todo_tasks[:6]:
                t_id=t["task_id"]
                c_chk,c_txt,c_st=st.columns([0.6,3.5,1.5])
                with c_chk:
                    chk=st.checkbox("",key=f"hm_chk_{t_id}")
                    if chk:
                        t["status"]="Done"
                        db.update_task(Task(**t))
                        st.balloons()
                        st.toast(f"🎉 タスク「{t['title']}」を完了しました！")
                        st.rerun()
                with c_txt:
                    due_info=f" 📅 {t['due_date']}" if t.get("due_date") else ""
                    st.markdown(f"**{t['title']}** {due_info}")
                    if t.get("remarks"):st.caption(f"   {t['remarks']}")
                with c_st:
                    curr_st=t["status"]
                    new_st=st.selectbox(
                        "ステータス",
                        ["Todo","In Progress","Done"],
                        index=["Todo","In Progress","Done"].index(curr_st),
                        key=f"hm_sel_{t_id}",
                        label_visibility="collapsed"
                    )
                    if new_st!=curr_st:
                        t["status"]=new_st
                        db.update_task(Task(**t))
                        if new_st=="Done":
                            st.balloons()
                            st.toast(f"🎉 タスク「{t['title']}」を完了しました！")
                        st.rerun()
            
            if len(todo_tasks)>6:
                st.caption(f"他 {len(todo_tasks)-6} 件のタスクがあります。")
        
        if st.button("📋 「タスクリスト」画面へ移動する",key="btn_nav_tasks"):
            _navigate_to("タスクリスト")

    st.write("---")

    # 4. クイックアクションガイド (ワンクリック自動ダイレクトページ遷移)
    st.subheader("⚡ クイック登録 ＆ 画面ダイレクト遷移")
    qc1,qc2,qc3,qc4,qc5=st.columns(5)
    with qc1:
        st.markdown("**📚 文献**")
        if st.button("文献の登録へ",key="q_nav_lit"):
            _navigate_to("文献の登録")
    with qc2:
        st.markdown("**🧪 物質情報**")
        if st.button("物質の登録へ",key="q_nav_mat"):
            _navigate_to("物質の登録")
    with qc3:
        st.markdown("**⚗️ イベント**")
        if st.button("イベント登録へ",key="q_nav_evt"):
            _navigate_to("イベントの登録")
    with qc4:
        st.markdown("**📌 サンプル**")
        if st.button("サンプルの登録へ",key="q_nav_smp"):
            _navigate_to("サンプルの登録")
    with qc5:
        st.markdown("**📊 測定データ**")
        if st.button("測定の登録へ",key="q_nav_msr"):
            _navigate_to("測定データの登録")
