"""
MatGraphia 仮登録・データ管理・編集ビュー
TITLE: 📂 仮登録・データ管理・編集
ORDER: 8
"""
import os
import json
import pandas as pd
import streamlit as st
import database as db
import file_manager as fm
from schemas import Literature, Material, Event, Sample, Measurement
from ui.helpers import log_errors, build_sample_label, build_event_label, build_literature_label, render_location_badge

TITLE = "📂 仮登録・データ管理・編集"
ORDER = 8

@log_errors("仮登録・データ管理・編集")
def render():
    st.header("📂 仮登録・データ管理・編集 (Data Management & Draft Completion)")
    st.markdown("仮登録（下書き保存）データの抽出・補完・本登録、および全データのリアルタイム数値編集・更新管理を行えます。")

    sub_tab_drafts, sub_tab_realtime_edit = st.tabs([
        "📝 仮登録（下書き）一覧 ＆ 本登録補完", 
        "📊 登録データ一覧 ＆ リアルタイム数値編集"
    ])

    # =========================================================================
    # 小タブ 1: 仮登録（下書き）データ一覧 ＆ 本登録補完
    # =========================================================================
    with sub_tab_drafts:
        st.subheader("📝 仮登録（下書き保存）データの補完 ＆ 本登録昇格")
        st.caption("下書き保存された各データから未入力項目を補完し、1クリックで本登録（正式データ化）に昇格できます。")

        entity_type = st.selectbox(
            "対象データカテゴリを選択", 
            ["サンプルの下書き", "測定データの下書き", "イベントの下書き", "物質データの下書き", "文献データの下書き"],
            key="dm_draft_entity_selector"
        )

        if entity_type == "サンプルの下書き":
            all_samples = db.fetch_all_samples()
            draft_samples = [s for s in all_samples if s.get("is_draft")]
            if not draft_samples:
                st.success("🎉 現在、下書き保存されているサンプルデータはありません。すべて本登録済みです！")
            else:
                st.info(f"💡 仮登録（下書き）サンプル: **{len(draft_samples)}** 件")
                smp_df = pd.DataFrame([{
                    "Human ID": s.get("human_id"),
                    "Form": s.get("form"),
                    "保管場所": s.get("location", "-"),
                    "備考": s.get("remarks", "-"),
                    "登録日": str(s.get("created_at"))[:10],
                    "ID": s.get("sample_id")
                } for s in draft_samples])
                st.dataframe(smp_df, hide_index=True)

                st.write("---")
                st.markdown("##### ✏️ 選択サンプルの情報補完 ＆ 本登録")
                sel_smp_id = st.selectbox("補完・本登録するサンプルを選択", [s["sample_id"] for s in draft_samples], format_func=lambda x: next((s["human_id"] for s in draft_samples if s["sample_id"]==x), x), key="sb_edit_draft_smp")
                target_s = next(s for s in draft_samples if s["sample_id"] == sel_smp_id)

                with st.form(key=f"form_complete_sample_{sel_smp_id}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_hid = st.text_input("人間用識別バッチ名 (例: 01-Powder)", value=target_s.get("human_id", ""), key=f"inp_hid_{sel_smp_id}")
                        new_form = st.selectbox("形状", ["Powder", "Single Crystal", "Thin Film", "Pellet"], index=0, key=f"inp_form_{sel_smp_id}")
                    with c2:
                        new_loc = st.text_input("物理的な保管場所 (例: デシケーター Box #A2)", value=target_s.get("location", ""), key=f"inp_loc_{sel_smp_id}")
                        new_rem = st.text_area("備考", value=target_s.get("remarks", ""), key=f"inp_rem_{sel_smp_id}")

                    if st.form_submit_button("✨ このサンプルを正式に「本登録」する", type="primary"):
                        target_s["human_id"] = new_hid
                        target_s["form"] = new_form
                        target_s["location"] = new_loc
                        target_s["remarks"] = new_rem
                        target_s["is_draft"] = False
                        db.update_sample(target_s)
                        st.success(f"サンプル 「{new_hid}」 を本登録へ昇格しました！")
                        st.rerun()

        elif entity_type == "測定データの下書き":
            all_msrs = db.fetch_all_measurements()
            draft_msrs = [m for m in all_msrs if m.get("is_draft")]
            if not draft_msrs:
                st.success("🎉 現在、下書き保存されている測定データはありません。すべて本登録済みです！")
            else:
                st.info(f"💡 仮登録（下書き）測定データ: **{len(draft_msrs)}** 件")
                m_df = pd.DataFrame([{
                    "Type": m.get("measurement_type"),
                    "Sample ID": m.get("sample_id", "")[:8],
                    "Operator": m.get("operator", "-"),
                    "Measured At": str(m.get("measured_at"))[:10],
                    "Raw Data": "あり" if m.get("raw_data_path") else "なし",
                    "ID": m.get("measurement_id")
                } for m in draft_msrs])
                st.dataframe(m_df, hide_index=True)

                st.write("---")
                st.markdown("##### ✏️ 選択測定データの情報補完 ＆ 本登録")
                sel_m_id = st.selectbox("補完・本登録する測定データを選択", [m["measurement_id"] for m in draft_msrs], format_func=lambda x: f"{next((m['measurement_type'] for m in draft_msrs if m['measurement_id']==x), '')} ({x[:8]})", key="sb_edit_draft_msr")
                target_m = next(m for m in draft_msrs if m["measurement_id"] == sel_m_id)

                with st.form(key=f"form_complete_msr_{sel_m_id}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_op = st.text_input("測定担当者", value=target_m.get("operator", ""), key=f"inp_op_{sel_m_id}")
                        new_rem = st.text_area("備考", value=target_m.get("remarks", ""), key=f"inp_mrem_{sel_m_id}")
                    with c2:
                        st.caption(f"生データファイルパス: `{target_m.get('raw_data_path', 'なし')}`")

                    if st.form_submit_button("✨ この測定データを正式に「本登録」する", type="primary"):
                        target_m["operator"] = new_op
                        target_m["remarks"] = new_rem
                        target_m["is_draft"] = False
                        db.update_measurement(target_m)
                        st.success(f"測定データ ({target_m.get('measurement_type')}) を本登録へ昇格しました！")
                        st.rerun()

        elif entity_type == "イベントの下書き":
            all_evts = db.fetch_all_events()
            draft_evts = [e for e in all_evts if e.get("is_draft")]
            if not draft_evts:
                st.success("🎉 現在、下書き保存されているイベントデータはありません。")
            else:
                st.dataframe(pd.DataFrame([{
                    "Project": e.get("project_name"),
                    "Target Material": e.get("target_material"),
                    "Type": e.get("event_type"),
                    "登録日": str(e.get("created_at"))[:10],
                    "ID": e.get("event_id")
                } for e in draft_evts]), hide_index=True)

        elif entity_type == "物質データの下書き":
            all_mats = db.fetch_all_materials()
            draft_mats = [m for m in all_mats if m.get("is_draft")]
            if not draft_mats:
                st.success("🎉 現在、下書き保存されている物質データはありません。")
            else:
                st.dataframe(pd.DataFrame([{
                    "Name": m.get("name"),
                    "CIF Path": m.get("cif_file_path", "-"),
                    "登録日": str(m.get("created_at"))[:10]
                } for m in draft_mats]), hide_index=True)

        elif entity_type == "文献データの下書き":
            all_lits = db.fetch_all_literatures()
            draft_lits = [l for l in all_lits if l.get("is_draft")]
            if not draft_lits:
                st.success("🎉 現在、下書き保存されている文献データはありません。")
            else:
                st.dataframe(pd.DataFrame([{
                    "Title": l.get("title"),
                    "DOI": l.get("doi"),
                    "Type": l.get("literature_type"),
                    "登録日": str(l.get("created_at"))[:10]
                } for l in draft_lits]), hide_index=True)

    # =========================================================================
    # 小タブ 2: 登録データ一覧 ＆ リアルタイム数値編集
    # =========================================================================
    with sub_tab_realtime_edit:
        st.subheader("📊 登録データ一覧 ＆ リアルタイム数値編集テーブル")
        st.caption("数値を編集・変更すると、即座に算出値・組成比・テーブルおよびプレビューが動的に更新されます。")

        samples = db.fetch_all_samples()
        measurements = db.fetch_all_measurements()

        if samples:
            st.markdown("##### 1. サンプル一覧 ＆ 保管場所・パラメータのリアルタイム編集")
            sample_df = pd.DataFrame([{
                "ID": s["sample_id"],
                "Human ID": s.get("human_id", ""),
                "Form": s.get("form", "Powder"),
                "保管場所 (Location)": s.get("location", ""),
                "備考": s.get("remarks", "")
            } for s in samples])

            edited_df = st.data_editor(
                sample_df,
                key="editor_realtime_samples",
                num_rows="fixed",
                hide_index=True
            )

            if st.button("💾 サンプルの変更内容を即時データベースへ保存", type="primary", key="btn_save_edited_samples"):
                for _, row in edited_df.iterrows():
                    sid = row["ID"]
                    orig_s = next((s for s in samples if s["sample_id"] == sid), None)
                    if orig_s:
                        orig_s["human_id"] = row["Human ID"]
                        orig_s["form"] = row["Form"]
                        orig_s["location"] = row["保管場所 (Location)"]
                        orig_s["remarks"] = row["備考"]
                        db.update_sample(orig_s)
                st.success("サンプルの変更内容をデータベースへ保存しました！")
                st.rerun()

        st.write("---")
        if measurements:
            st.markdown("##### 2. 測定データ（条件パラメータ・数式結果）のリアルタイム編集")
            msr_df = pd.DataFrame([{
                "ID": m["measurement_id"],
                "Type": m.get("measurement_type"),
                "Operator": m.get("operator", ""),
                "Measured At": str(m.get("measured_at"))[:10],
                "Conditions (JSON)": json.dumps(m.get("conditions") or {}, ensure_ascii=False)
            } for m in measurements])

            edited_m_df = st.data_editor(
                msr_df,
                key="editor_realtime_measurements",
                num_rows="fixed",
                hide_index=True
            )

            if st.button("💾 測定データの条件・パラメータ変更を保存", type="primary", key="btn_save_edited_msrs"):
                for _, row in edited_m_df.iterrows():
                    mid = row["ID"]
                    orig_m = next((m for m in measurements if m["measurement_id"] == mid), None)
                    if orig_m:
                        orig_m["operator"] = row["Operator"]
                        try:
                            orig_m["conditions"] = json.loads(row["Conditions (JSON)"])
                        except Exception:
                            pass
                        db.update_measurement(orig_m)
                st.success("測定データの変更内容をデータベースへ保存しました！")
                st.rerun()
