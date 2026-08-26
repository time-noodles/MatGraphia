import streamlit as st
import uuid
import sys
import platform
from datetime import datetime
import database as db
import logger_config as lc
from ui.helpers import log_errors

TITLE="💬 開発フィードバック"
ORDER=9


# 画面描画
@log_errors("開発フィードバック")
def render():
    st.header("開発フィードバック ＆ システムログ")
    st.markdown("アプリ使用中に気づいた改善要望や不具合報告の投稿、および自動収集されたターミナルエラーログの確認が行えます。")
    t1,t2,t3,t4=st.tabs(["新規投稿","ログ一覧・管理","フィードバックの共有・集約","自動エラーログ (システム)"])
    with t1:
        st.subheader("新規フィードバックの投稿")
        if st.session_state.get("feedback_success_msg"):
            st.success(st.session_state["feedback_success_msg"])
            if st.button("➕ 続けて新しいフィードバックを投稿する",key="btn_post_another_feedback"):
                del st.session_state["feedback_success_msg"]
                st.rerun()
        else:
            with st.form("feedback_input_form",clear_on_submit=True):
                log_type=st.selectbox("種類",["Feedback","Bug"])
                title=st.text_input("件名 (簡単な概要)")
                content=st.text_area("詳細内容 (具体的な手順や要望)")
                attach_env=st.checkbox("システム環境情報（OS / Pythonバージョン）を添付する",value=True)
                submitted=st.form_submit_button("送信する",type="primary")
                if submitted:
                    if not title or not content:
                        st.error("件名と詳細内容を入力してください。")
                    else:
                        final_content=content
                        if attach_env:
                            env_info=f"\n\n--- システム環境情報 ---\nOS: {platform.system()} {platform.release()}\nPython: {sys.version.split()[0]}"
                            final_content+=env_info
                        log_id=str(uuid.uuid4())
                        db.insert_developer_log(log_id,log_type,title,final_content,"開発フィードバック")
                        st.session_state["feedback_success_msg"]="🎉 フィードバックを正常に登録・送信しました！「ログ一覧・管理」タブで内容を確認できます。"
                        st.rerun()

    with t2:
        st.subheader("システムログ ＆ フィードバック一覧")
        logs=db.fetch_all_developer_logs()
        if not logs:
            st.info("現在記録されているログはありません。")
        else:
            open_logs=[l for l in logs if l.get("status")=="Open"]
            in_prog_logs=[l for l in logs if l.get("status")=="In Progress"]
            resolved_logs=[l for l in logs if l.get("status")=="Resolved"]
            
            def _render_log_item(l):
                lid=l["log_id"]
                label=f"[{l['log_type']}] {l['title']} (日時: {l['created_at']})"
                with st.expander(label):
                    st.write(f"**発生場所**: {l['page_name']} &nbsp;|&nbsp; **ステータス**: `{l.get('status','Open')}`")
                    st.markdown("**【フィードバック・エラー内容】**")
                    st.code(l["content"])
                    
                    st.markdown("---")
                    st.markdown("### 📝 改善計画 ＆ 検証エビデンス")
                    plan_val=l.get("action_plan") or ""
                    notes_val=l.get("verification_notes") or ""
                    
                    with st.form(key=f"form_plan_{lid}"):
                        new_plan=st.text_area("📝 改善計画 (Action Plan)",value=plan_val,placeholder="どのように設計・修正するかの具体的な手順",height=100)
                        new_notes=st.text_area("✅ 検証メモ・テスト結果 (Verification Notes)",value=notes_val,placeholder="修正後の動作確認手順およびテスト結果エビデンス",height=80)
                        save_plan=st.form_submit_button("💾 計画・検証メモを保存",type="primary")
                        if save_plan:
                            db.update_developer_log_plan(lid,new_plan,new_notes)
                            st.success("改善計画・検証メモを保存しました。")
                            st.rerun()
                            
                    st.markdown("---")
                    c1,c2,c3,c4=st.columns(4)
                    with c1:
                        if st.button("⚪ 未対応にする",key=f"to_open_{lid}"):
                            db.update_developer_log_status(lid,"Open")
                            st.rerun()
                    with c2:
                        if st.button("🔵 対応中にする",key=f"to_prog_{lid}"):
                            db.update_developer_log_status(lid,"In Progress")
                            st.rerun()
                    with c3:
                        if st.button("🟢 解決済みにする",key=f"to_res_{lid}"):
                            db.update_developer_log_status(lid,"Resolved")
                            st.rerun()
                    with c4:
                        if st.button("🗑️ 削除する",key=f"to_del_{lid}"):
                            db.delete_developer_log(lid)
                            st.rerun()

            sub_t1,sub_t2,sub_t3=st.tabs([f"⚪ 未対応 ({len(open_logs)})",f"🔵 計画中・対応中 ({len(in_prog_logs)})",f"🟢 解決済み ({len(resolved_logs)})"])
            with sub_t1:
                if not open_logs:st.caption("未対応の項目はありません。")
                for l in open_logs:_render_log_item(l)
            with sub_t2:
                if not in_prog_logs:st.caption("現在計画中・対応中の項目はありません。")
                for l in in_prog_logs:_render_log_item(l)
            with sub_t3:
                if resolved_logs:
                    if st.button("🧹 解決済みログを一括削除する",key="btn_clear_resolved_logs"):
                        db.clear_resolved_developer_logs()
                        st.success("解決済みのログを一括削除しました。")
                        st.rerun()
                if not resolved_logs:st.caption("解決済みの項目はありません。")
                for l in resolved_logs:_render_log_item(l)
    with t3:
        st.subheader("他ユーザーとのフィードバック集約")
        st.info("【データ保護】出力・読み込みされるファイルには改善要望・エラーログのみが含まれます。CIFファイル、合成条件、測定結果などの実験データは一切含まれません。")
        col_exp,col_imp=st.columns(2)
        with col_exp:
            st.markdown("### フィードバックの書き出し")
            st.caption("自分の環境に登録されている改善要望・ログをJSON形式でダウンロードし、開発者や管理者に共有できます。")
            json_data=db.export_developer_logs_json()
            st.download_button(
                label="フィードバックJSONをダウンロード",
                data=json_data,
                file_name=f"MatGraphia_Feedback_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                type="primary"
            )
        with col_imp:
            st.markdown("### 他ユーザーからの集約")
            st.caption("他メンバーから受け取ったフィードバックJSONをアップロードし、この環境のログ一覧に集約します。")
            uploaded_file=st.file_uploader("フィードバックJSONファイルを選択",type=["json"])
            if uploaded_file is not None:
                if st.button("インポートを実行"):
                    try:
                        content=uploaded_file.read().decode("utf-8")
                        count=db.import_developer_logs_json(content)
                        st.success(f"{count} 件のフィードバックを新しくインポートしました！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"インポートに失敗しました: {e}")
    with t4:
        st.subheader("自動キャプチャ・コンソールエラーログ (data/system_errors.log)")
        st.caption("ターミナル（標準エラー出力）や未処理例外でキャプチャされた直近のエラーログです。手動でログをコピペする必要はありません。")
        sys_logs=lc.read_system_error_logs()
        st.code(sys_logs,language="text")
        col_dl,col_clear=st.columns(2)
        with col_dl:
            st.download_button(
                label="エラーログファイルをダウンロード",
                data=sys_logs,
                file_name=f"system_errors_{datetime.now().strftime('%Y%m%d_%H%M')}.log",
                mime="text/plain"
            )
        with col_clear:
            if st.button("エラーログをクリアする"):
                lc.clear_system_error_logs()
                st.success("エラーログをクリアしました。")
                st.rerun()
