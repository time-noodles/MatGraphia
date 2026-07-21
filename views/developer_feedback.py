import streamlit as st
import uuid
import database as db
from ui.helpers import log_errors

TITLE="開発フィードバック"
ORDER=9

# 画面描画
@log_errors("開発フィードバック")
def render():
    st.header("開発フィードバック ＆ システムログ")
    st.markdown("アプリ使用中に気づいた改善要望や、不具合の報告を投稿できます。また、発生した実行時エラーの履歴を確認・管理できます。")
    t1,t2=st.tabs(["新規投稿","ログ一覧・管理"])
    with t1:
        st.subheader("新規フィードバックの投稿")
        log_type=st.selectbox("種類",["Feedback","Bug"])
        title=st.text_input("件名 (簡単な概要)")
        content=st.text_area("詳細内容 (具体的な手順や要望)")
        if st.button("送信する",type="primary"):
            if not title or not content:
                st.error("件名と詳細内容を入力してください。")
            else:
                log_id=str(uuid.uuid4())
                db.insert_developer_log(log_id,log_type,title,content,"開発フィードバック")
                st.success("フィードバックを登録しました！")
                st.rerun()
    with t2:
        st.subheader("システムログ ＆ フィードバック一覧")
        logs=db.fetch_all_developer_logs()
        if not logs:
            st.info("現在記録されているログはありません。")
            return
        open_logs=[l for l in logs if l["status"]=="Open"]
        resolved_logs=[l for l in logs if l["status"]=="Resolved"]
        sub_t1,sub_t2=st.tabs([f"未対応 ({len(open_logs)})",f"解決済み ({len(resolved_logs)})"])
        with sub_t1:
            for l in open_logs:
                color="red" if l["log_type"]=="Error" else "blue"
                label=f"[{l['log_type']}] {l['title']} (日時: {l['created_at']})"
                with st.expander(label):
                    st.write(f"**発生場所**: {l['page_name']}")
                    st.code(l["content"])
                    c1,c2=st.columns(2)
                    with c1:
                        if st.button("解決済みにする",key=f"resolve_{l['log_id']}"):
                            db.update_developer_log_status(l["log_id"],"Resolved")
                            st.rerun()
                    with c2:
                        if st.button("削除する",key=f"del_open_{l['log_id']}"):
                            db.delete_developer_log(l["log_id"])
                            st.rerun()
        with sub_t2:
            for l in resolved_logs:
                label=f"[{l['log_type']}] {l['title']} (日時: {l['created_at']})"
                with st.expander(label):
                    st.write(f"**発生場所**: {l['page_name']}")
                    st.code(l["content"])
                    c1,c2=st.columns(2)
                    with c1:
                        if st.button("未対応に戻す",key=f"reopen_{l['log_id']}"):
                            db.update_developer_log_status(l["log_id"],"Open")
                            st.rerun()
                    with c2:
                        if st.button("削除する",key=f"del_res_{l['log_id']}"):
                            db.delete_developer_log(l["log_id"])
                            st.rerun()
