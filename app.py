# MatGraphia - 軽量エントリーポイント
# 重量ライブラリは各ページ内で遅延インポートされる
import os
import streamlit as st
import database as db
import file_manager as fm

os.environ["NO_PROXY"]="localhost,127.0.0.1"

st.set_page_config(page_title="MatGraphia",layout="wide")

@st.cache_resource
def initialize_system():
    fm.init_directories()
    db.init_db()

initialize_system()


def sync_obsidian(force=False):
    """Obsidian同期 (遅延インポート)"""
    if not force and db.get_setting("obsidian_auto_sync")=="False":
        return
    path=os.path.join(os.getcwd(),"obsidian_vault")
    try:
        from obsidian_exporter import ObsidianExporter
        ObsidianExporter(db).export_to_directory(path)
    except Exception as e:
        st.warning(f"Obsidian 同期に失敗しました: {e}")


def main():
    st.sidebar.title("MatGraphia DB")

    # ページ定義 (各モジュールは遅延読み込み)
    pages={
        "文献の登録":"views.literature",
        "物質情報の登録":"views.material",
        "イベントの登録":"views.event",
        "サンプルの登録":"views.sample",
        "測定データの登録":"views.measurement",
        "データ管理・編集":"views.data_management",
    }

    selection=st.sidebar.radio("メニュー",list(pages.keys()))

    # Obsidian Sync Section
    st.sidebar.write("---")
    st.sidebar.subheader("外部連携 (Obsidian)")
    st.sidebar.info("同期先: `obsidian_vault` フォルダ")

    # 自動同期フラグ
    auto_sync=db.get_setting("obsidian_auto_sync","False")=="True"
    new_auto=st.sidebar.checkbox("自動同期を有効にする",value=auto_sync)
    if new_auto!=auto_sync:
        db.set_setting("obsidian_auto_sync",str(new_auto))

    if st.sidebar.button("今すぐ手動同期"):
        sync_obsidian(force=True)
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

    # 選択されたページを遅延読み込み
    import importlib
    module=importlib.import_module(pages[selection])
    module.render()


if __name__=="__main__":
    main()
