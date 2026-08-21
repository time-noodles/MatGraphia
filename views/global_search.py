import streamlit as st
import database as db
import pandas as pd
from ui.helpers import log_errors

TITLE="検索とタグ"
ORDER=8

# キーワードによる絞り込みフィルタ
def filter_by_keywords(rows,keywords,fields):
    if not keywords:return rows
    res=[]
    for row in rows:
        match=True
        for kw in keywords:
            kw_match=False
            for field in fields:
                val=str(row.get(field) or "").lower()
                if kw.lower() in val:
                    kw_match=True
                    break
            if not kw_match:
                match=False
                break
        if match:res.append(row)
    return res

# 特定のタグを持つエンティティを取得
def fetch_entities_by_tag(tag_name:str):
    conn=db.get_connection()
    cursor=conn.cursor()
    cursor.execute("""
        SELECT et.entity_type,et.entity_id FROM entity_tags et
        JOIN tags t ON et.tag_id=t.tag_id
        WHERE t.tag_name=?
    """,(tag_name,))
    rows=cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# 画面描画
@log_errors("検索とタグ")
def render():
    st.header("検索とタグ管理")
    st.markdown("スペース区切りの複数キーワードによるAND検索や、ハッシュタグによる絞り込み検索が行えます。")
    conn=db.get_connection()
    cursor=conn.cursor()
    cursor.execute("SELECT tag_name FROM tags")
    all_tags=[r[0] for r in cursor.fetchall()]
    conn.close()
    tab_search,tab_tags=st.tabs(["キーワードAND検索","ハッシュタグ絞り込み"])
    with tab_search:
        search_q=st.text_input("検索キーワードを入力 (スペース区切りでAND検索)",placeholder="例: NaCrS2 焼成")
        if search_q:
            kws=search_q.split()
            lits=db.fetch_all_literatures()
            evts=db.fetch_all_events()
            smps=db.fetch_all_samples()
            msrs=db.fetch_all_measurements()
            mats=db.fetch_all_materials()
            tsks=db.fetch_all_tasks()
            f_lits=filter_by_keywords(lits,kws,["title","authors","venue","doi","remarks"])
            f_evts=filter_by_keywords(evts,kws,["project_id","target_material","event_type","motivation","remarks"])
            f_smps=filter_by_keywords(smps,kws,["human_id","form","location","remarks"])
            f_msrs=filter_by_keywords(msrs,kws,["measurement_type","operator","remarks"])
            f_mats=filter_by_keywords(mats,kws,["name","remarks"])
            f_tsks=filter_by_keywords(tsks,kws,["title","remarks"])
            if f_lits:
                st.markdown(f"**文献 ({len(f_lits)}件)**")
                for lit in f_lits[:10]:
                    col_txt,col_act=st.columns([4,1])
                    with col_txt:
                        st.caption(f"📖 **{lit['title']}** ({lit.get('authors','')}) - DOI: {lit.get('doi','(なし)')}")
                    with col_act:
                        if st.button("🔗 イベントの派生元に指定",key=f"link_lit_{lit['literature_id']}"):
                            st.session_state["evt_search_q"]=lit["title"]
                            st.session_state["nav_menu"]="イベントの登録"
                            st.rerun()
                if len(f_lits)>10:st.dataframe(pd.DataFrame(f_lits)[["literature_id","title","authors","doi"]],hide_index=True)
            if f_evts:
                st.markdown(f"**イベント ({len(f_evts)}件)**")
                for evt in f_evts[:10]:
                    col_txt,col_act=st.columns([4,1])
                    with col_txt:
                        st.caption(f"⚡ **[{evt['event_type']}]** {evt['target_material']} (Proj: {evt['project_id']})")
                    with col_act:
                        if st.button("🔗 イベントの参照元に指定",key=f"link_evt_{evt['event_id']}"):
                            st.session_state["evt_search_q"]=evt["target_material"]
                            st.session_state["nav_menu"]="イベントの登録"
                            st.rerun()
                if len(f_evts)>10:st.dataframe(pd.DataFrame(f_evts)[["event_id","project_id","target_material","event_type"]],hide_index=True)
            if f_smps:
                st.markdown(f"**サンプル ({len(f_smps)}件)**")
                for smp in f_smps[:10]:
                    col_txt,col_act=st.columns([4,1])
                    with col_txt:
                        st.caption(f"🧪 **{smp['human_id']}** ({smp['form']}) - 保管: {smp.get('location','(未指定)')}")
                    with col_act:
                        if st.button("🔗 サンプルの元データに指定",key=f"link_smp_{smp['sample_id']}"):
                            st.session_state["evt_search_q"]=smp["human_id"]
                            st.session_state["nav_menu"]="イベントの登録"
                            st.rerun()
                if len(f_smps)>10:st.dataframe(pd.DataFrame(f_smps)[["sample_id","human_id","form","location"]],hide_index=True)
            if f_msrs:
                st.markdown(f"**測定 ({len(f_msrs)}件)**")
                st.dataframe(pd.DataFrame(f_msrs)[["measurement_id","measurement_type","operator"]],hide_index=True)
            if f_mats:
                st.markdown(f"**物質 ({len(f_mats)}件)**")
                st.dataframe(pd.DataFrame(f_mats)[["material_id","name","cif_file_path"]],hide_index=True)
            if f_tsks:
                st.markdown(f"**タスク ({len(f_tsks)}件)**")
                st.dataframe(pd.DataFrame(f_tsks)[["task_id","title","status"]],hide_index=True)
            if not any([f_lits,f_evts,f_smps,f_msrs,f_mats,f_tsks]):st.info("一致するデータは見つかりませんでした。")
    with tab_tags:
        if not all_tags:
            st.info("登録されているハッシュタグはありません（備考欄等に #タグ名 と入力すると自動抽出されます）。")
            return
        st.markdown("**登録済みハッシュタグ一覧**")
        selected_tag=st.selectbox("タグを選択してください",all_tags)
        if selected_tag:
            results=fetch_entities_by_tag(selected_tag)
            if results:
                st.markdown(f"**タグ #{selected_tag} が付いている要素 ({len(results)}件)**")
                st.dataframe(pd.DataFrame(results),hide_index=True)
            else:
                st.info("該当する要素はありません。")
