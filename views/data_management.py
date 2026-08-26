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
from ui.helpers import log_errors, build_sample_label, build_event_label, build_literature_label, render_location_badge, get_atomic_weight, calc_molecular_weight

TITLE = "📂 仮登録・データ管理・編集"
ORDER = 8

@log_errors("仮登録・データ管理・編集")
def render():
    st.header("📂 仮登録・データ管理・編集 (Data Management & Live Numerical Editor)")
    st.markdown("仮登録（下書き保存）データの補完・本登録昇格、および各種実験パラメータ・測定数値の直感的なインタラクティブ数値編集を行えます。")

    sub_tab_drafts, sub_tab_realtime_edit = st.tabs([
        "📝 仮登録（下書き）一覧 ＆ 本登録補完", 
        "📊 登録データ一覧 ＆ インタラクティブ数値パラメータ編集"
    ])

    # =========================================================================
    # 小タブ 1: 仮登録（下書き）データ一覧 ＆ 本登録補完
    # =========================================================================
    with sub_tab_drafts:
        st.subheader("📝 仮登録（下書き保存）データの補完 ＆ 本登録昇格")
        st.caption("下書き保存されたデータから未入力項目を補完し、1クリックで本登録（正式データ化）に昇格できます。")

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
    # 小タブ 2: 登録データ一覧 ＆ インタラクティブ数値パラメータ編集
    # =========================================================================
    with sub_tab_realtime_edit:
        st.subheader("📊 登録データの数値パラメータ・直接インタラクティブ編集")
        st.caption("JSONを展開し、温度・時間・重量・電流・磁場・組成比等の数値を直接入力・変更できます。変更は即座に自動再計算されます。")

        target_category = st.radio(
            "編集カテゴリを選択", 
            ["⚗️ 合成・加工イベントの数値パラメータ", "📊 測定データの実験条件・数値結果", "🧪 物質の物性パラメータ (Tc/Tn)", "📌 サンプル保管場所・備考"],
            horizontal=True,
            key="dm_num_category"
        )

        if target_category == "⚗️ 合成・加工イベントの数値パラメータ":
            events = db.fetch_all_events()
            if not events:
                st.info("登録されているイベントデータがありません。")
            else:
                sel_evt_id = st.selectbox("編集するイベントを選択", [e["event_id"] for e in events], format_func=lambda x: f"{next((e['target_material'] for e in events if e['event_id']==x), '')} - {next((e['event_type'] for e in events if e['event_id']==x), '')} ({x[:6]})", key="sb_edit_num_evt")
                target_evt = next(e for e in events if e["event_id"] == sel_evt_id)
                params = json.loads(target_evt.get("parameters") or "{}") if isinstance(target_evt.get("parameters"), str) else (target_evt.get("parameters") or {})

                st.write("---")
                st.markdown(f"##### ✏️ イベント 「{target_evt.get('target_material')} ({target_evt.get('event_type')})」 の数値編集")
                
                c_mat, c_mw = st.columns(2)
                with c_mat:
                    new_target_mat = st.text_input("対象物質名", value=target_evt.get("target_material", ""), key=f"inp_mat_name_{sel_evt_id}")
                with c_mw:
                    mw_calc = calc_molecular_weight(new_target_mat)
                    if mw_calc:
                        st.info(f"⚖️ 再算定された分子量 (M.W.): **{mw_calc:.3f} g/mol**")

                st.markdown("**実験数値パラメータ (`st.number_input` 直接編集):**")
                num_keys = [k for k, v in params.items() if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).replace("-", "", 1).isdigit())]
                
                updated_params = dict(params)
                if not num_keys:
                    st.caption("このイベントには直接抽出できる数値キーがありません。以下で一般的なパラメータを設定できます。")
                    p_temp = st.number_input("焼結/加熱温度 (°C)", min_value=0.0, max_value=3000.0, value=800.0, step=10.0, key=f"num_p_temp_{sel_evt_id}")
                    p_time = st.number_input("保持時間 (hours)", min_value=0.0, max_value=500.0, value=12.0, step=1.0, key=f"num_p_time_{sel_evt_id}")
                    updated_params["temperature_c"] = float(p_temp)
                    updated_params["duration_hours"] = float(p_time)
                else:
                    cols = st.columns(min(len(num_keys), 3))
                    for idx, k in enumerate(num_keys):
                        curr_val = float(params[k]) if params[k] is not None else 0.0
                        with cols[idx % 3]:
                            new_val = st.number_input(f"{k}", value=curr_val, key=f"num_k_{k}_{sel_evt_id}")
                            updated_params[k] = new_val

                # 即時自動保存＆DB反映ロジック
                if new_target_mat != target_evt.get("target_material") or updated_params != params:
                    target_evt["target_material"] = new_target_mat
                    target_evt["parameters"] = updated_params
                    db.update_event(target_evt)
                    st.toast("⚡ 編集結果を即座にデータベースへ自動保存しました！")

        elif target_category == "📊 測定データの実験条件・数値結果":
            msrs = db.fetch_all_measurements()
            if not msrs:
                st.info("登録されている測定データがありません。")
            else:
                sel_m_id = st.selectbox("編集する測定データを選択", [m["measurement_id"] for m in msrs], format_func=lambda x: f"{next((m['measurement_type'] for m in msrs if m['measurement_id']==x), '')} - {x[:8]}", key="sb_edit_num_msr")
                target_m = next(m for m in msrs if m["measurement_id"] == sel_m_id)
                conds = json.loads(target_m.get("conditions") or "{}") if isinstance(target_m.get("conditions"), str) else (target_m.get("conditions") or {})

                st.write("---")
                st.markdown(f"##### ✏️ 測定データ 「{target_m.get('measurement_type')}」 の条件数値編集")
                
                updated_conds = dict(conds)
                c_op, c_dt = st.columns(2)
                with c_op:
                    new_op = st.text_input("測定担当者", value=target_m.get("operator", ""), key=f"num_op_{sel_m_id}")
                with c_dt:
                    st.caption(f"測定日: {str(target_m.get('measured_at'))[:10]}")

                st.markdown("**数値条件パラメータ (数値変更時に即時DB保存):**")
                m_type = target_m.get("measurement_type")
                if m_type == "Hall":
                    c_i, c_b, c_d = st.columns(3)
                    with c_i: new_i = st.number_input("励起電流 I (mA)", value=float(conds.get("current_mA", 10.0)), key=f"hall_i_{sel_m_id}")
                    with c_b: new_b = st.number_input("印加磁場 B (Tesla)", value=float(conds.get("magnetic_field_T", 1.0)), key=f"hall_b_{sel_m_id}")
                    with c_d: new_d = st.number_input("試料膜厚 d (μm)", value=float(conds.get("thickness_um", 100.0)), key=f"hall_d_{sel_m_id}")
                    updated_conds["current_mA"] = new_i
                    updated_conds["magnetic_field_T"] = new_b
                    updated_conds["thickness_um"] = new_d
                else:
                    num_cond_keys = [k for k, v in conds.items() if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).replace("-", "", 1).isdigit())]
                    if not num_cond_keys:
                        new_temp = st.number_input("測定温度 (K)", value=float(conds.get("temperature_k", 300.0)), key=f"gen_temp_{sel_m_id}")
                        updated_conds["temperature_k"] = new_temp
                    else:
                        cols = st.columns(min(len(num_cond_keys), 3))
                        for idx, k in enumerate(num_cond_keys):
                            curr_v = float(conds[k]) if conds[k] is not None else 0.0
                            with cols[idx % 3]:
                                updated_conds[k] = st.number_input(f"{k}", value=curr_v, key=f"m_num_{k}_{sel_m_id}")

                if new_op != target_m.get("operator") or updated_conds != conds:
                    target_m["operator"] = new_op
                    target_m["conditions"] = updated_conds
                    db.update_measurement(target_m)
                    st.toast("⚡ 測定データの条件変更を即座に自動保存しました！")

        elif target_category == "🧪 物質の物性パラメータ (Tc/Tn)":
            mats = db.fetch_all_materials()
            if not mats:
                st.info("登録されている物質データがありません。")
            else:
                sel_mat_id = st.selectbox("編集する物質を選択", [m["material_id"] for m in mats], format_func=lambda x: next((m["name"] for m in mats if m["material_id"]==x), x), key="sb_edit_num_mat")
                target_mat = next(m for m in mats if m["material_id"] == sel_mat_id)
                props = json.loads(target_mat.get("properties") or "{}") if isinstance(target_mat.get("properties"), str) else (target_mat.get("properties") or {})

                st.write("---")
                st.markdown(f"##### ✏️ 物質 「{target_mat.get('name')}」 の物性数値編集")
                
                c_tc, c_tn = st.columns(2)
                with c_tc:
                    tc_val = st.number_input("超伝導転移温度 Tc (K)", value=float(props.get("Tc (K)", 0.0) or 0.0), key=f"num_tc_{sel_mat_id}")
                with c_tn:
                    tn_val = st.number_input("ネール温度 Tn (K)", value=float(props.get("Tn (K)", 0.0) or 0.0), key=f"num_tn_{sel_mat_id}")

                new_tc_str = str(tc_val) if tc_val > 0 else ""
                new_tn_str = str(tn_val) if tn_val > 0 else ""
                if new_tc_str != str(props.get("Tc (K)", "")) or new_tn_str != str(props.get("Tn (K)", "")):
                    props["Tc (K)"] = new_tc_str
                    props["Tn (K)"] = new_tn_str
                    target_mat["properties"] = props
                    db.update_material(target_mat)
                    st.toast("⚡ 物質の物性値を即座に自動更新しました！")

        elif target_category == "📌 サンプル保管場所・備考":
            samples = db.fetch_all_samples()
            if not samples:
                st.info("登録されているサンプルデータはありません。")
            else:
                sample_df = pd.DataFrame([{
                    "ID": s["sample_id"],
                    "Human ID": s.get("human_id", ""),
                    "Form": s.get("form", "Powder"),
                    "保管場所 (Location)": s.get("location", ""),
                    "備考": s.get("remarks", "")
                } for s in samples])

                edited_df = st.data_editor(
                    sample_df,
                    key="editor_realtime_samples_full",
                    num_rows="fixed",
                    hide_index=True
                )

                # テーブルセルの変更を即時検知＆自動DB保存
                has_changed = False
                for _, row in edited_df.iterrows():
                    sid = row["ID"]
                    orig_s = next((s for s in samples if s["sample_id"] == sid), None)
                    if orig_s:
                        if (row["Human ID"] != orig_s.get("human_id") or
                            row["Form"] != orig_s.get("form") or
                            row["保管場所 (Location)"] != orig_s.get("location") or
                            row["備考"] != orig_s.get("remarks")):
                            orig_s["human_id"] = row["Human ID"]
                            orig_s["form"] = row["Form"]
                            orig_s["location"] = row["保管場所 (Location)"]
                            orig_s["remarks"] = row["備考"]
                            db.update_sample(orig_s)
                            has_changed = True
                if has_changed:
                    st.toast("⚡ サンプルの変更内容を即座に自動保存しました！")

