import os
import streamlit as st
import database as db
import file_manager as fm

os.environ["NO_PROXY"]="localhost,127.0.0.1"
st.set_page_config(page_title="MatGraphia",layout="wide")

# システムの初期化
@st.cache_resource
def initialize_system():
    fm.init_directories()
    db.init_db()

initialize_system()

# ビューモジュールの動的ロード
def load_views():
    import importlib
    import pkgutil
    import views
    pages={}
    for _,name,is_pkg in pkgutil.iter_modules(views.__path__):
        if is_pkg:continue
        try:
            mod=importlib.import_module(f"views.{name}")
            if hasattr(mod,"TITLE") and hasattr(mod,"ORDER") and hasattr(mod,"render"):
                pages[mod.TITLE]=(mod.ORDER,f"views.{name}")
        except Exception:
            pass
    sorted_pages=sorted(pages.items(),key=lambda x:x[1][0])
    return {title:path for title,(_,path) in sorted_pages}

# メイン処理
def main():
    st.sidebar.title("MatGraphia DB")
    pages=load_views()
    if not pages:
        st.sidebar.error("ページが読み込めませんでした。")
        return
    selection=st.sidebar.radio("メニュー",list(pages.keys()))
    st.sidebar.write("---")
    st.sidebar.subheader("外部連携 (Obsidian)")
    st.sidebar.info("同期先: `obsidian_vault` フォルダ")
    auto_sync=db.get_setting("obsidian_auto_sync","False")=="True"
    new_auto=st.sidebar.checkbox("自動同期を有効にする",value=auto_sync)
    if new_auto!=auto_sync:db.set_setting("obsidian_auto_sync",str(new_auto))
    if st.sidebar.button("今すぐ手動同期"):
        db.sync_obsidian(force=True)
        st.sidebar.success("同期完了！")
    if st.sidebar.button("Zip形式でダウンロード"):
        try:
            from datetime import datetime
            from obsidian_exporter import ObsidianExporter
            exporter=ObsidianExporter(db)
            zip_data=exporter.export_all()
            st.sidebar.download_button(
                label="Zipをダウンロード",
                data=zip_data,
                file_name=f"MatGraphia_Obsidian_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                mime="application/zip"
            )
        except Exception as e:
            st.sidebar.error(f"エラー: {e}")
    import importlib
    module=importlib.import_module(pages[selection])
    module.render()

if __name__=="__main__":
    main()
