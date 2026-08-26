import streamlit as st
import database as db
import pandas as pd
from datetime import date,datetime
from schemas import Task
from ui.helpers import log_errors,build_literature_label

TITLE="📋 タスク ＆ カレンダー管理"
ORDER=8


# 画面描画
@log_errors("タスクリスト")
def render():
    st.header("📋 タスク ＆ カレンダー管理")
    st.markdown("実験予定やToDo、サブタスク（小タスク）をインタラクティブに管理します。")

    tasks=db.fetch_all_tasks()
    samples=db.fetch_all_samples()
    events=db.fetch_all_events()
    materials=db.fetch_all_materials()
    literatures=db.fetch_all_literatures()

    # 選択肢の構築
    sample_opts={"(なし)":None}
    for s in samples:sample_opts[f"Sample: {s['human_id']} ({s['form']})"]=s["sample_id"]
    event_opts={"(なし)":None}
    for e in events:event_opts[f"Event: {e['event_type']} on {e['target_material']} ({e['event_id'][:4]})"]=e["event_id"]
    mat_opts={"(なし)":None}
    for m in materials:mat_opts[f"Material: {m['name']} ({m['material_id'][:4]})"]=m["material_id"]
    lit_opts={"(なし)":None}
    for l in literatures:lit_opts[f"Literature: {build_literature_label(l)}"]=l["literature_id"]

    # 親タスクの選択肢 (メインタスクのみ)
    main_tasks=[t for t in tasks if not t.get("parent_task_id")]
    parent_task_opts={"(なし - 親タスクとして作成)":None}
    for mt in main_tasks:
        parent_task_opts[f"📌 {mt['title']} (ID: {mt['task_id'][:4]})"]=mt["task_id"]

    # 全体進捗バー
    if tasks:
        done_cnt=sum(1 for t in tasks if t.get("status")=="Done")
        progress_val=done_cnt/len(tasks)
        st.write("**全体進捗状況**")
        st.progress(progress_val,text=f"達成率: {done_cnt}/{len(tasks)} 件 ({int(progress_val*100)}%)")
        st.write("")

    # 新規タスク・小タスクの追加フォーム（常時表示）
    with st.expander("➕ 新規タスク / 小タスク（サブタスク）の追加",expanded=True):
        with st.form("new_task_form"):
            col_p,col_t=st.columns([1,1])
            with col_p:
                parent_sel=st.selectbox("親タスク（小タスクとして作成する場合選択）",list(parent_task_opts.keys()))
                parent_id=parent_task_opts[parent_sel]
            with col_t:
                title=st.text_input("タスク名 (必須)",placeholder="例: サンプルの秤量・カプセル封入")
            
            col_d,col_s=st.columns([1,1])
            with col_d:
                due_date=st.date_input("予定日 / 期限",value=date.today())
            with col_s:
                initial_status=st.selectbox("初期ステータス",["Todo","In Progress","Done"])

            rel_type=st.selectbox("関連データ種別 (任意)",["なし","Sample","Event","Material","Literature"])
            if rel_type=="Sample":rel_id=st.selectbox("関連サンプル",list(sample_opts.keys()))
            elif rel_type=="Event":rel_id=st.selectbox("関連イベント",list(event_opts.keys()))
            elif rel_type=="Material":rel_id=st.selectbox("関連物質",list(mat_opts.keys()))
            elif rel_type=="Literature":rel_id=st.selectbox("関連文献",list(lit_opts.keys()))
            else:rel_id="(なし)"

            remarks=st.text_area("備考 / メモ",placeholder="#優先度高 などのタグも可")
            
            submitted=st.form_submit_button("✨ タスクを追加する",type="primary")
            if submitted:
                if not title:
                    st.error("【必須エラー】 タスク名は必須です。")
                    return
                try:
                    target_rel_id=None
                    if rel_type=="Sample":target_rel_id=sample_opts[rel_id]
                    elif rel_type=="Event":target_rel_id=event_opts[rel_id]
                    elif rel_type=="Material":target_rel_id=mat_opts[rel_id]
                    elif rel_type=="Literature":target_rel_id=lit_opts[rel_id]

                    tsk=Task(
                        parent_task_id=parent_id,
                        title=title,
                        status=initial_status,
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
        st.info("現在登録されているタスクはありません。")
        return

    st.write("---")

    # タブ表示（ツリー表示 / カレンダー・日付表示）
    tab_tree,tab_cal=st.tabs(["📂 タスクツリー (メイン＆小タスク)","📅 カレンダー / アジェンダビュー"])

    # --- TAB 1: タスクツリー表示 ---
    with tab_tree:
        active_tasks=[t for t in tasks if t.get("status")!="Done"]
        completed_tasks=[t for t in tasks if t.get("status")=="Done"]

        # メインタスクと小タスクのグループ化
        sub_tasks_map={}
        for t in tasks:
            pid=t.get("parent_task_id")
            if pid:
                sub_tasks_map.setdefault(pid,[]).append(t)

        def _render_task_card(t,is_subtask=False):
            t_id=t["task_id"]
            is_done=t["status"]=="Done"
            
            indent="&nbsp;&nbsp;&nbsp;&nbsp;↳ 🔹 " if is_subtask else "📌 "
            col_chk,col_info,col_st,col_act=st.columns([0.6,4,1.8,1])
            
            with col_chk:
                chk=st.checkbox("",value=is_done,key=f"chk_done_{t_id}")
                if chk!=is_done:
                    t["status"]="Done" if chk else "Todo"
                    db.update_task(Task(**t))
                    if chk:
                        st.balloons()
                        st.toast(f"🎉 タスク「{t['title']}」を完了しました！")
                    st.rerun()
            
            with col_info:
                title_fmt=f"~~{t['title']}~~" if is_done else f"**{t['title']}**"
                st.markdown(f"{indent}{title_fmt}",unsafe_allow_html=True)
                sub_info=[]
                if t.get("due_date"):sub_info.append(f"📅 {t['due_date']}")
                if t.get("related_entity_type"):sub_info.append(f"🔗 {t['related_entity_type']}")
                if t.get("remarks"):sub_info.append(f"💬 {t['remarks']}")
                if sub_info:
                    st.caption(" | ".join(sub_info))
            
            with col_st:
                curr_st=t["status"]
                new_st=st.selectbox(
                    "ステータス",
                    ["Todo","In Progress","Done"],
                    index=["Todo","In Progress","Done"].index(curr_st),
                    key=f"sel_st_{t_id}",
                    label_visibility="collapsed"
                )
                if new_st!=curr_st:
                    t["status"]=new_st
                    db.update_task(Task(**t))
                    if new_st=="Done":
                        st.balloons()
                        st.toast(f"🎉 タスク「{t['title']}」を完了しました！")
                    st.rerun()
            
            with col_act:
                if st.button("🗑️ 削除",key=f"btn_del_tsk_{t_id}"):
                    db.delete_task(t_id)
                    st.success("削除しました。")
                    st.rerun()

        # 未完了タスクの描画（進行中）
        st.subheader(f"⚡ 進行中のタスク ({len(active_tasks)} 件)")
        active_main=[m for m in main_tasks if m.get("status")!="Done" or any(stsk.get("status")!="Done" for stsk in sub_tasks_map.get(m["task_id"],[]))]
        if not active_main:
            st.success("🎉 進行中のタスクはありません！全てのタスクが完了しています。")
        else:
            for mt in active_main:
                with st.container():
                    _render_task_card(mt,is_subtask=False)
                    subs=sub_tasks_map.get(mt["task_id"],[])
                    for stsk in subs:
                        _render_task_card(stsk,is_subtask=True)
                    st.markdown("<hr style='margin:4px 0; border:0.5px dashed #ccc;'/>",unsafe_allow_html=True)

        # 完了済みタスクのアコーディオン（タッチすると消えてここに集約）
        if completed_tasks:
            st.write("")
            with st.expander(f"🎉 完了済みのタスク ({len(completed_tasks)} 件)",expanded=False):
                for ct in completed_tasks:
                    _render_task_card(ct,is_subtask=bool(ct.get("parent_task_id")))

    # --- TAB 2: 1ヶ月マンスリーカレンダー表示 ---
    with tab_cal:
        import calendar
        st.subheader("🗓️ 1ヶ月マンスリーカレンダー (カレンダーアプリ風)")
        
        # 年月の選択
        now_dt=datetime.now()
        col_y,col_m=st.columns(2)
        with col_y:
            sel_year=st.selectbox("年",list(range(now_dt.year-1,now_dt.year+3)),index=1,key="cal_sel_year")
        with col_m:
            sel_month=st.selectbox("月",list(range(1,13)),index=now_dt.month-1,key="cal_sel_month")

        # 日付別のタスクマッピング
        dated_tasks={}
        for t in tasks:
            d_str=t.get("due_date")
            if d_str:
                dated_tasks.setdefault(d_str,[]).append(t)

        st.write("---")
        st.markdown(f"### 📅 {sel_year}年 {sel_month}月 の月間タスク一覧")
        
        # 月間カレンダーグリッドの生成
        month_cal=calendar.monthcalendar(sel_year,sel_month)
        week_days=["月","火","水","木","金","土","日"]
        
        # 曜日ヘッダー
        cols=st.columns(7)
        for i,wd in enumerate(week_days):
            cols[i].markdown(f"**{wd}**")

        # 各週のグリッド描画
        for week in month_cal:
            w_cols=st.columns(7)
            for idx,day in enumerate(week):
                with w_cols[idx]:
                    if day==0:
                        st.write("")
                    else:
                        d_str=f"{sel_year:04d}-{sel_month:02d}-{day:02d}"
                        day_tasks_list=dated_tasks.get(d_str,[])
                        badge=f" 🔴({len(day_tasks_list)})" if day_tasks_list else ""
                        st.markdown(f"**{day}日**{badge}")
                        if day_tasks_list:
                            for dt in day_tasks_list:
                                st.caption(f"・[{dt['status'][:1]}] {dt['title'][:12]}")

        st.write("---")
        st.markdown("**📌 選択月の日別タスク詳細**")
        target_month_str=f"{sel_year:04d}-{sel_month:02d}"
        month_dates=sorted([d for d in dated_tasks.keys() if d.startswith(target_month_str)])
        if not month_dates:
            st.info("選択された月には予定されているタスクがありません。")
        else:
            for d in month_dates:
                with st.expander(f"📅 {d} ({len(dated_tasks[d])} 件)",expanded=True):
                    for t in dated_tasks[d]:
                        rem_str=f"({t['remarks']})" if t.get('remarks') else ""
                        st.write(f"- **[{t['status']}]** {t['title']} {rem_str}")

