import os
import logger_config as lc
lc.setup_logger()

import streamlit as st
import database as db
import file_manager as fm

os.environ["NO_PROXY"]="localhost,127.0.0.1"
st.set_page_config(page_title="MatGraphia",layout="wide")

# カスタムデザイン & スクロール追従ボタンCSSスタイル ＆ サイドバー改善
st.markdown("""
<style>
/* 登録フォームの仮登録・本登録ボタンの視認性向上 */
div.stButton > button[kind="primary"] {
    border-radius: 8px;
    font-weight: bold;
    transition: all 0.2s ease-in-out;
}
div.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
/* スクロール追従（Sticky Floating）ボタンコンテナサポート */
.sticky-btn-bar {
    position: sticky;
    bottom: 20px;
    z-index: 999;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(8px);
    padding: 12px 20px;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.12);
    border: 1px solid rgba(0,0,0,0.08);
}
/* サイドバーのモダンデザインカスタマイズ */
div[data-testid="stSidebar"] div.stRadio div[role="radiogroup"] label {
    padding: 8px 14px;
    border-radius: 10px;
    font-weight: 500;
    margin-bottom: 3px;
    transition: all 0.2s ease-in-out;
}
div[data-testid="stSidebar"] div.stRadio div[role="radiogroup"] label:hover {
    background-color: #edf2f7;
    transform: translateX(2px);
}
</style>
""", unsafe_allow_html=True)


# システムの初期化
@st.cache_resource
def initialize_system():
    fm.init_directories()
    db.init_db()

initialize_system()

# ビューモジュールのメタデータ抽出
@st.cache_data
def load_views():

    import ast
    import pkgutil
    import views
    pages={}
    for _,name,is_pkg in pkgutil.iter_modules(views.__path__):
        if is_pkg:continue
        file_path=os.path.join(views.__path__[0],f"{name}.py")
        if not os.path.exists(file_path):continue
        try:
            with open(file_path,"r",encoding="utf-8") as f:
                tree=ast.parse(f.read(),filename=file_path)
            title,order=None,None
            for stmt in tree.body:
                if isinstance(stmt,ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target,ast.Name):
                            if target.id=="TITLE" and isinstance(stmt.value,ast.Constant):
                                title=stmt.value.value
                            elif target.id=="ORDER" and isinstance(stmt.value,ast.Constant):
                                order=stmt.value.value
            if title is not None and order is not None:
                pages[title]=(order,f"views.{name}")
        except Exception:
            pass
    sorted_pages=sorted(pages.items(),key=lambda x:x[1][0])
    return {title:path for title,(_,path) in sorted_pages}

# メイン処理
def main():
    st.sidebar.title("🧬 MatGraphia DB")
    st.sidebar.caption("物質科学実験データ ＆ プロセス統括プラットフォーム")
    pages=load_views()
    if not pages:
        st.sidebar.error("ページが読み込めませんでした。")
        return
    page_keys=list(pages.keys())
    nav_target=st.session_state.get("app_nav_target")
    if nav_target:
        matched_key = next((k for k in page_keys if nav_target in k or k in nav_target), None)
        if matched_key:
            st.session_state["nav_menu"] = matched_key
        if "app_nav_target" in st.session_state:
            del st.session_state["app_nav_target"]
    elif "nav_menu" not in st.session_state or st.session_state["nav_menu"] not in page_keys:
        st.session_state["nav_menu"]=page_keys[0]
        
    selection=st.sidebar.radio("📋 ナビゲーションメニュー",page_keys,key="nav_menu")

    st.sidebar.write("---")
    st.sidebar.subheader("外部連携 (Obsidian)")
    st.sidebar.caption("同期先: `obsidian_vault` フォルダ")
    auto_sync=db.get_setting("obsidian_auto_sync","False")=="True"
    new_auto=st.sidebar.checkbox("自動同期を有効にする",value=auto_sync)
    if new_auto!=auto_sync:
        db.set_setting("obsidian_auto_sync",str(new_auto))
        st.toast("Obsidian自動同期の設定を更新しました")
        
    if st.sidebar.button("今すぐ手動同期",type="primary"):
        try:
            path=os.path.join(os.getcwd(),"obsidian_vault")
            from obsidian_exporter import ObsidianExporter
            ObsidianExporter(db).export_to_directory(path)
            st.sidebar.success("✅ `obsidian_vault` への同期が完了しました！")
            st.toast("🎉 Obsidianへの同期が正常に完了しました！")
        except Exception as e:
            st.sidebar.error(f"❌ 同期エラー: {e}")

    # Zipダウンロード（毎画面再描画時の重いexport_all実行を完全に排除）
    if st.sidebar.button("📦 Zip形式でVaultを出力"):
        try:
            from datetime import datetime
            from obsidian_exporter import ObsidianExporter
            with st.sidebar.spinner("Zip形式でVaultを出力中..."):
                zip_data=ObsidianExporter(db).export_all()
            st.sidebar.download_button(
                label="⬇️ 生成されたZipを保存",
                data=zip_data,
                file_name=f"MatGraphia_Obsidian_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                mime="application/zip",
                key="download_obsidian_zip_btn"
            )
        except Exception as e:
            st.sidebar.error(f"Zip出力エラー: {e}")
    import importlib
    module=importlib.import_module(pages[selection])
    module.render()

if __name__=="__main__":
    main()
