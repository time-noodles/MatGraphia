# MatGraphia 動的フォームジェネレーター
# 化学計算(Stoichiometry), Furnace Timer Calculator を含む
import streamlit as st
from datetime import datetime,timedelta


def get_molecular_weight(formula):
    """化学式から分子量を計算する (遅延インポート)"""
    if not formula:
        return 0.0
    try:
        from chempy import Substance
        return float(Substance.from_formula(str(formula).strip()).mass)
    except Exception:
        return 0.0


def render_dynamic_form(schema_def,key_prefix,initial_data=None):
    """プラグインスキーマから動的にフォームを生成する"""
    # pandas は必要な場面でのみインポート
    import pandas as pd

    form_data={}
    initial_data=initial_data or {}
    if "fields" in schema_def and schema_def["fields"]:
        st.write("---")
        st.markdown("**【固有パラメータ】**")
        for field in schema_def["fields"]:
            fname=field["name"]
            flabel=field["label"]
            ftype=field["type"]
            fdefault=initial_data.get(fname,field.get("default"))
            widget_key=f"{key_prefix}_{fname}"

            if ftype=="int":
                form_data[fname]=st.number_input(flabel,value=int(fdefault) if fdefault is not None else 0,step=1,key=widget_key)
            elif ftype=="float":
                form_data[fname]=st.number_input(flabel,value=float(fdefault) if fdefault is not None else 0.0,key=widget_key)
            elif ftype=="select":
                options=field.get("options",[])
                if options:
                    if fdefault in options:
                        default_idx=options.index(fdefault)
                    else:
                        default_idx=0
                    form_data[fname]=st.selectbox(flabel,options,index=default_idx,key=widget_key)
                else:
                    form_data[fname]=st.text_input(flabel,value=str(fdefault) if fdefault is not None else "",key=widget_key)
            elif ftype=="bool":
                form_data[fname]=st.checkbox(flabel,value=bool(fdefault) if fdefault is not None else False,key=widget_key)
            elif ftype=="str":
                form_data[fname]=st.text_input(flabel,value=str(fdefault) if fdefault is not None else "",key=widget_key)
            elif ftype=="text":
                form_data[fname]=st.text_area(flabel,value=str(fdefault) if fdefault is not None else "",height=100,key=widget_key)

    if "tables" in schema_def and schema_def["tables"]:
        st.write("---")
        st.markdown("**【表形式・リストパラメータ】**")
        for table in schema_def["tables"]:
            tname=table["name"]
            st.write(f"**{table['label']}**")

            is_advanced_prep=table.get("is_advanced_prep",False)
            total_mass=1.0
            if is_advanced_prep:
                total_mass=st.number_input(f"目標 Total Mass (g) [{table['label']}]",value=1.0,step=0.1,key=f"{key_prefix}_{tname}_tm")
                st.info("**Tips:** 1行目の mass(g) に実際の秤量値を入れると、それを基準に残りの ideal(g) 値が再計算されます。")
            else:
                st.info("**Tips:** セルを1回クリックして直接文字を打ち込むか、ダブルクリック編集。右下の + アイコンで空行を追加できます。")

            init_data=initial_data.get(tname,table.get("init_data",[]))
            if not init_data:
                empty_row={col["name"]:(0.0 if col.get("type") in ["int","float"] else False if col.get("type")=="bool" else "") for col in table["columns"]}
                init_data.append(empty_row)

            df_init=pd.DataFrame(init_data)
            widget_key=f"{key_prefix}_{tname}"
            edited_df=st.data_editor(
                df_init,
                num_rows="dynamic",
                hide_index=True,
                key=widget_key
            )
            form_data[tname]=edited_df.to_dict(orient="records")

            # Stoichiometry 計算
            if is_advanced_prep:
                _render_stoichiometry(edited_df,total_mass,key_prefix,tname,form_data)

            # Furnace Timer Calculator
            if table.get("is_heating_profile",False):
                _render_furnace_timer(edited_df,key_prefix,tname)

    return form_data


def _render_stoichiometry(edited_df,total_mass,key_prefix,tname,form_data):
    import pandas as pd
    calc_df=edited_df.copy()
    if "item" not in calc_df.columns:return
    mws=[]
    for idx,row in calc_df.iterrows():
        mw_val=0.0
        if "M.W." in calc_df.columns:
            mw_val=pd.to_numeric(row["M.W."],errors="coerce")
        if not mw_val or pd.isna(mw_val) or mw_val<=0:
            mw_val=get_molecular_weight(str(row["item"]))
        mws.append(mw_val)
    calc_df["M.W."]=mws
    ref_idx,ref_mass=None,0.0
    if "mass" in calc_df.columns:
        for idx,row in calc_df.iterrows():
            m=pd.to_numeric(row["mass"],errors="coerce")
            if pd.notnull(m) and m>0:
                ref_idx,ref_mass=idx,m
                break
    if "Composition ratio" not in calc_df.columns:return
    calc_df["Composition ratio"]=pd.to_numeric(calc_df["Composition ratio"],errors="coerce").fillna(0)
    calc_df["Base_Weight"]=calc_df["Composition ratio"]*calc_df["M.W."]
    sum_base_weight=calc_df["Base_Weight"].sum()
    if sum_base_weight<=0:
        st.warning("分子量または組成比の計算が正しく行えません。")
        return
    if ref_idx is not None and ref_mass>0:
        ref_base=calc_df.iloc[ref_idx]["Base_Weight"]
        multiplier=ref_mass/ref_base if ref_base>0 else 0
        calc_df["ideal (g)"]=calc_df["Base_Weight"]*multiplier
    else:
        calc_df["ideal (g)"]=(calc_df["Base_Weight"]/sum_base_weight)*total_mass
    calc_df["ideal S 換算 (g)"]=None
    s_mw=get_molecular_weight("S")
    if s_mw<=0:s_mw=32.06
    for idx,row in calc_df.iterrows():
        item_str=str(row["item"]).upper()
        if any(x in item_str for x in ["SE","TE","S"]):
            moles=row["ideal (g)"]/row["M.W."] if row["M.W."]>0 else 0
            calc_df.at[idx,"ideal S 換算 (g)"]=round(moles*s_mw,4)
    st.markdown("**(自動計算結果) Ideal Mass & S conversion**")
    calc_df["ideal (g)"]=calc_df["ideal (g)"].apply(lambda x:round(x,4) if pd.notnull(x) else x)
    display_cols=["item","Composition ratio","M.W.","ideal (g)","ideal S 換算 (g)","mass"]
    st.dataframe(calc_df[[c for c in display_cols if c in calc_df.columns]],hide_index=True)
    form_data[tname+"_calculated"]=calc_df.to_dict(orient="records")


def _render_furnace_timer(edited_df,key_prefix,tname):
    """Furnace Timer Calculator (最短開始時間・終了時間の逆算機能)"""
    import pandas as pd

    st.markdown("**(オプション) Furnace Timer Calculator (加熱スケジュール確認・調整)**")
    col_d,col_t=st.columns(2)
    tgt_dows=["月 (Mon)","火 (Tue)","水 (Wed)","木 (Thu)","金 (Fri)","土 (Sat)","日 (Sun)"]
    with col_d:
        target_dows_sel=st.multiselect("終了希望曜日 (複数可)",tgt_dows,default=["月 (Mon)"],key=f"{key_prefix}_{tname}_dow")
    with col_t:
        target_times_str=st.text_input("終了希望時間 (複数可 / カンマ区切り 例: 10:00,15:30)",value="10:00",key=f"{key_prefix}_{tname}_time")

    # 文字列から時間のパース
    parsed_times=[]
    for t_str in str(target_times_str).replace(" ","").replace("、",",").split(","):
        if t_str:
            try:
                h,m=map(int,t_str.split(":"))
                parsed_times.append(pd.Timestamp(f"{h:02d}:{m:02d}").time())
            except Exception:
                pass

    total_hours=0.0
    target_checked=False
    for idx,row in edited_df.iterrows():
        h=pd.to_numeric(row.get("Duration (h)"),errors="coerce")
        if pd.isna(h):
            h=0.0
        total_hours+=float(h)

        if row.get("Target End")==True:
            target_checked=True
            break

    if total_hours>0 and target_dows_sel and parsed_times:
        now=datetime.now()
        end_if_start_now=now+timedelta(hours=total_hours)

        valid_options=[]
        for dow in target_dows_sel:
            for p_time in parsed_times:
                target_wd=tgt_dows.index(dow)
                target_dt=now.replace(hour=p_time.hour,minute=p_time.minute,second=0,microsecond=0)

                while target_dt.weekday()!=target_wd or target_dt<now:
                    target_dt+=timedelta(days=1)

                time_to_wait=target_dt-end_if_start_now
                if time_to_wait.total_seconds()<0:
                    target_dt+=timedelta(days=7)
                    time_to_wait=target_dt-end_if_start_now

                valid_options.append({
                    "target_dt":target_dt,
                    "wait_hours":time_to_wait.total_seconds()/3600
                })

        if valid_options:
            best_opt=min(valid_options,key=lambda x: x["wait_hours"])
            best_target_dt=best_opt["target_dt"]
            wait_hours=best_opt["wait_hours"]
            start_dt=best_target_dt-timedelta(hours=total_hours)

            end_str="[Target End]でチェックをつけたポイント" if target_checked else "プロセス全体"
            st.success(
                f"{end_str} が完了するまでの経過時間: **{total_hours:.1f} 時間**\n\n"
                f"もし【今すぐ】開始した場合の終了時刻: **{end_if_start_now.strftime('%m/%d (%a) %H:%M')}**\n\n"
                f"指定された条件 (**{', '.join([d[:1] for d in target_dows_sel])}** の **{target_times_str}**) のうち、最短で合わせられる目標は...\n"
                f"**{start_dt.strftime('%m/%d (%a) %H:%M')}** に開始して、**{best_target_dt.strftime('%m/%d (%a) %H:%M')}** に終了するスケジュールです。(現在から**約 {wait_hours:.1f} 時間後**)"
            )
    elif total_hours>0:
        st.warning("終了希望曜日を選択し、時間は「10:00」や「10:00, 15:30」のようにコロンで正しく入力してください。")
