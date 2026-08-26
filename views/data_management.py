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
    st.header("📂 仮登録・データ管理・編集 (Unified Data Management)")
    st.caption("仮登録（下書き保存）および正式登録されたデータの補完、本登録昇格、直感的な数値編集を 1 ページで統合管理できます。")
    st.write("---")

    entity_type = st.selectbox(
        "対象データカテゴリを選択", 
        ["📌 サンプルの下書き・登録データ", "📊 測定データの下書き・登録データ", "⚗️ イベントの下書き・登録データ", "🧪 物質データの下書き・登録データ", "📚 文献データの下書き・登録データ"],
        key="dm_draft_entity_selector"
    )

    if "サンプル" in entity_type:
        all_samples = db.fetch_all_samples()
        if not all_samples:
            st.info("登録されているサンプルデータはありません。")
        else:
            draft_samples = [s for s in all_samples if s.get("is_draft")]
            st.info(f"💡 全サンプル: **{len(all_samples)}** 件 (下書き: **{len(draft_samples)}** 件)")
            
            smp_df = pd.DataFrame([{
                "ID": s.get("sample_id"),
                "Human ID": s.get("human_id"),
                "Form": s.get("form"),
                "保管場所": s.get("location", "-"),
                "下書き": "📝 下書き" if s.get("is_draft") else "✨ 本登録",
                "登録日": str(s.get("created_at"))[:10],
                "備考": s.get("remarks", "-")
            } for s in all_samples])
            st.dataframe(smp_df, hide_index=True)

            st.write("---")
            st.markdown("##### ✏️ 選択サンプルの元UIと同等での直接編集 ＆ 本登録昇格")
            sel_smp_id = st.selectbox("編集するサンプルを選択", [s["sample_id"] for s in all_samples], format_func=lambda x: f"{next((s['human_id'] for s in all_samples if s['sample_id']==x), x)} ({'下書き' if next((s.get('is_draft') for s in all_samples if s['sample_id']==x), False) else '本登録'})", key="sb_edit_smp_main")
            target_s = next(s for s in all_samples if s["sample_id"] == sel_smp_id)

            with st.form(key=f"form_edit_sample_{sel_smp_id}"):
                c1, c2 = st.columns(2)
                with c1:
                    new_hid = st.text_input("人間用識別バッチ名 (例: 01-Powder)", value=target_s.get("human_id", ""), key=f"inp_hid_{sel_smp_id}")
                    new_form = st.selectbox("形状", ["Powder", "Single Crystal", "Thin Film", "Pellet"], index=0, key=f"inp_form_{sel_smp_id}")
                with c2:
                    new_loc = st.text_input("物理的な保管場所 (例: デシケーター Box #A2)", value=target_s.get("location", ""), key=f"inp_loc_{sel_smp_id}")
                    new_rem = st.text_area("備考", value=target_s.get("remarks", ""), key=f"inp_rem_{sel_smp_id}")

                c_b1, c_b2 = st.columns(2)
                with c_b1:
                    btn_save_main = st.form_submit_button("✨ 正式に「本登録」へ昇格・保存する", type="primary")
                with c_b2:
                    btn_save_draft = st.form_submit_button("📝 下書き（仮登録）として更新保存する")

                if btn_save_main or btn_save_draft:
                    target_s["human_id"] = new_hid
                    target_s["form"] = new_form
                    target_s["location"] = new_loc
                    target_s["remarks"] = new_rem
                    target_s["is_draft"] = False if btn_save_main else True
                    db.update_sample(target_s)
                    st.success(f"サンプル 「{new_hid}」 の変更内容を保存しました！")
                    st.rerun()

    elif "測定データ" in entity_type:
        msrs = db.fetch_all_measurements()
        if not msrs:
            st.info("登録されている測定データはありません。")
        else:
            draft_msrs = [m for m in msrs if m.get("is_draft")]
            st.info(f"💡 全測定データ: **{len(msrs)}** 件 (下書き: **{len(draft_msrs)}** 件)")
            
            m_df = pd.DataFrame([{
                "ID": m.get("measurement_id"),
                "Type": m.get("measurement_type"),
                "Sample ID": m.get("sample_id", "")[:8],
                "Operator": m.get("operator", "-"),
                "Measured At": str(m.get("measured_at"))[:10],
                "下書き": "📝 下書き" if m.get("is_draft") else "✨ 本登録",
                "Raw Data": "あり" if m.get("raw_data_path") else "なし"
            } for m in msrs])
            st.dataframe(m_df, hide_index=True)

            st.write("---")
            st.markdown("##### ✏️ 選択測定データの条件数値編集 ＆ 本登録")
            sel_m_id = st.selectbox("編集する測定データを選択", [m["measurement_id"] for m in msrs], format_func=lambda x: f"{next((m['measurement_type'] for m in msrs if m['measurement_id']==x), '')} - {x[:8]} ({'下書き' if next((m.get('is_draft') for m in msrs if m['measurement_id']==x), False) else '本登録'})", key="sb_edit_msr_main")
            target_m = next(m for m in msrs if m["measurement_id"] == sel_m_id)
            conds = json.loads(target_m.get("conditions") or "{}") if isinstance(target_m.get("conditions"), str) else (target_m.get("conditions") or {})

            updated_conds = dict(conds)
            c_op, c_dt = st.columns(2)
            with c_op:
                new_op = st.text_input("測定担当者", value=target_m.get("operator", ""), key=f"num_op_{sel_m_id}")
            with c_dt:
                st.caption(f"測定日: {str(target_m.get('measured_at'))[:10]}")

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

            c_mb1, c_mb2 = st.columns(2)
            with c_mb1:
                btn_m_sub = st.button("✨ 本登録へ昇格・更新保存する", type="primary", key=f"btn_m_sub_{sel_m_id}")
            with c_mb2:
                btn_m_draft = st.button("📝 下書き（仮登録）として更新保存", key=f"btn_m_draft_{sel_m_id}")

            if btn_m_sub or btn_m_draft:
                target_m["operator"] = new_op
                target_m["conditions"] = updated_conds
                target_m["is_draft"] = False if btn_m_sub else True
                db.update_measurement(target_m)
                st.success("測定データの変更内容をデータベースへ保存しました！")
                st.rerun()

    elif "イベント" in entity_type:
        events = db.fetch_all_events()
        if not events:
            st.info("登録されているイベントデータはありません。")
        else:
            draft_evts = [e for e in events if e.get("is_draft")]
            st.info(f"💡 全イベント: **{len(events)}** 件 (下書き: **{len(draft_evts)}** 件)")
            
            st.dataframe(pd.DataFrame([{
                "ID": e.get("event_id"),
                "Project": e.get("project_name") or e.get("project_id"),
                "Target Material": e.get("target_material"),
                "Type": e.get("event_type"),
                "下書き": "📝 下書き" if e.get("is_draft") else "✨ 本登録",
                "登録日": str(e.get("created_at"))[:10]
            } for e in events]), hide_index=True)

            st.write("---")
            sel_evt_id = st.selectbox("編集するイベントを選択", [e["event_id"] for e in events], format_func=lambda x: f"{next((e['target_material'] for e in events if e['event_id']==x), '')} - {next((e['event_type'] for e in events if e['event_id']==x), '')} ({x[:6]})", key="sb_edit_evt_main")
            target_evt = next(e for e in events if e["event_id"] == sel_evt_id)
            params = json.loads(target_evt.get("parameters") or "{}") if isinstance(target_evt.get("parameters"), str) else (target_evt.get("parameters") or {})

            st.markdown(f"##### ✏️ イベント 「{target_evt.get('target_material')} ({target_evt.get('event_type')})」 の数値パラメータ編集")
            c_mat, c_mw = st.columns(2)
            with c_mat:
                new_target_mat = st.text_input("対象物質名", value=target_evt.get("target_material", ""), key=f"inp_mat_name_{sel_evt_id}")
            with c_mw:
                mw_calc = calc_molecular_weight(new_target_mat)
                if mw_calc:
                    st.info(f"⚖️ 分子量 (M.W.): **{mw_calc:.3f} g/mol**")

            updated_params = dict(params)
            num_keys = [k for k, v in params.items() if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).replace("-", "", 1).isdigit())]
            if not num_keys:
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

            c_eb1, c_eb2 = st.columns(2)
            with c_eb1:
                btn_evt_sub = st.button("✨ 本登録へ昇格・更新保存する", type="primary", key=f"btn_evt_sub_{sel_evt_id}")
            with c_eb2:
                btn_evt_draft = st.button("📝 下書き（仮登録）として更新保存", key=f"btn_evt_draft_{sel_evt_id}")

            if btn_evt_sub or btn_evt_draft:
                target_evt["target_material"] = new_target_mat
                target_evt["parameters"] = updated_params
                target_evt["is_draft"] = False if btn_evt_sub else True
                db.update_event(target_evt)
                st.success("イベントの変更内容をデータベースへ保存しました！")
                st.rerun()

    elif "物質データ" in entity_type:
        mats = db.fetch_all_materials()
        if not mats:
            st.info("登録されている物質データはありません。")
        else:
            draft_mats = [m for m in mats if m.get("is_draft")]
            st.info(f"💡 全物質データ: **{len(mats)}** 件 (下書き: **{len(draft_mats)}** 件)")
            st.dataframe(pd.DataFrame([{
                "ID": m.get("material_id"),
                "Name": m.get("name"),
                "下書き": "📝 下書き" if m.get("is_draft") else "✨ 本登録",
                "CIF Path": m.get("cif_file_path", "-"),
                "登録日": str(m.get("created_at"))[:10]
            } for m in mats]), hide_index=True)

            st.write("---")
            sel_mat_id = st.selectbox("編集する物質を選択", [m["material_id"] for m in mats], format_func=lambda x: next((m["name"] for m in mats if m["material_id"]==x), x), key="sb_edit_num_mat")
            target_mat = next(m for m in mats if m["material_id"] == sel_mat_id)
            props = json.loads(target_mat.get("properties") or "{}") if isinstance(target_mat.get("properties"), str) else (target_mat.get("properties") or {})

            st.markdown(f"##### ✏️ 物質 「{target_mat.get('name')}」 の物性数値編集")
            c_tc, c_tn = st.columns(2)
            with c_tc:
                tc_val = st.number_input("超伝導転移温度 Tc (K)", value=float(props.get("Tc (K)", 0.0) or 0.0), key=f"num_tc_{sel_mat_id}")
            with c_tn:
                tn_val = st.number_input("ネール温度 Tn (K)", value=float(props.get("Tn (K)", 0.0) or 0.0), key=f"num_tn_{sel_mat_id}")

            c_matb1, c_matb2 = st.columns(2)
            with c_matb1:
                btn_mat_sub = st.button("✨ 本登録へ昇格・更新保存する", type="primary", key=f"btn_mat_sub_{sel_mat_id}")
            with c_matb2:
                btn_mat_draft = st.button("📝 下書き（仮登録）として更新保存", key=f"btn_mat_draft_{sel_mat_id}")

            if btn_mat_sub or btn_mat_draft:
                props["Tc (K)"] = str(tc_val) if tc_val > 0 else ""
                props["Tn (K)"] = str(tn_val) if tn_val > 0 else ""
                target_mat["properties"] = props
                target_mat["is_draft"] = False if btn_mat_sub else True
                db.update_material(target_mat)
                st.success("物質データの変更内容をデータベースへ保存しました！")
                st.rerun()

    elif "文献データ" in entity_type:
        lits = db.fetch_all_literatures()
        if not lits:
            st.info("登録されている文献データはありません。")
        else:
            draft_lits = [l for l in lits if l.get("is_draft")]
            st.info(f"💡 全文献データ: **{len(lits)}** 件 (下書き: **{len(draft_lits)}** 件)")
            st.dataframe(pd.DataFrame([{
                "ID": l.get("literature_id"),
                "Title": l.get("title"),
                "DOI": l.get("doi"),
                "下書き": "📝 下書き" if l.get("is_draft") else "✨ 本登録",
                "登録日": str(l.get("created_at"))[:10]
            } for l in lits]), hide_index=True)
