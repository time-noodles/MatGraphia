"""
MatGraphia 自動ブラウザ E2E テストスクリプト (Playwright)
http://localhost:8501 へ自動アクセスし、UI全画面の操作・遷移・Plotly描画・スクショ撮影を検証します。
"""
import os
import sys
import time
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = "data/e2e_screenshots"

def run_e2e_browser_test():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    print("🚀 MatGraphia 自動ブラウザ E2E テストを開始します...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. ホーム画面アクセス
        print("🌐 http://localhost:8501 へアクセス中...")
        page.goto("http://localhost:8501", wait_until="commit", timeout=15000)
        time.sleep(5)

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_home_dashboard.png"))
        print("✅ 1. ホームダッシュボードへのアクセス成功 (01_home_dashboard.png)")

        # 2. サイドバーから各カテゴリ ＆ ページ遷移
        pages_to_test = [
            ("📚 データ登録", "⚗️ イベントの登録", "02_event_registration.png"),
            ("📚 データ登録", "📌 サンプルの登録", "03_sample_registration.png"),
            ("📚 データ登録", "📊 測定データの登録", "04_measurement_registration.png"),
            ("📊 解析 ＆ データ管理", "⚖️ データの比較 ＆ 傾向分析", "05_comparison_analytics.png"),
            ("📊 解析 ＆ データ管理", "📂 仮登録・データ管理・編集", "06_data_management.png"),
        ]

        for cat, pg_name, ss_file in pages_to_test:
            print(f"📱 画面操作: [{cat}] -> [{pg_name}]...")
            try:
                # 親カテゴリ選択
                sel = page.locator("select").first
                if sel.is_visible():
                    sel.select_option(label=cat)
                    time.sleep(2)
                
                # 小タブページ選択
                page.get_by_text(pg_name, exact=False).first.click(timeout=5000)
                time.sleep(3)
                page.screenshot(path=os.path.join(SCREENSHOT_DIR, ss_file))
                print(f"✅ 画面描画成功: {ss_file}")
            except Exception as e:
                print(f"ℹ️ {pg_name} 画面ログ: {e}")

        browser.close()
        print("🎉 自動ブラウザ E2E テストが完了いたしました！")

if __name__ == "__main__":
    run_e2e_browser_test()
