# CLAUDE.md (MatGraphia 開発ガイドライン)

このファイルは、AIアシスタントや開発者がこのプロジェクト（MatGraphia）で作業する際に、環境、実行方法、およびコード規約を素早く理解するためのものです。

---

## 1. 実行・開発コマンド

すべてのコマンドは、仮想環境 `py-antigravity`（Anaconda環境）で実行する必要があります。

* **アプリケーションの起動**
  ```bash
  conda run -n py-antigravity streamlit run app.py
  ```
* **データベースの初期化・再構築 (既存データ破棄)**
  ```bash
  conda run -n py-antigravity python -c "import database;database.init_db()"
  ```
* **テストの実行**
  ```bash
  conda run -n py-antigravity python test_crystal.py
  ```

---

## 2. ディレクトリ構成

* `app.py`: エントリーポイント（views/ を動的にロード）
* `database.py`: データベース操作（SQLiteリレーショナル設計、キャッシュ制御、自動Obsidian同期）
* `schemas.py`: Pydanticデータモデル定義
* `file_manager.py`: 添付ファイルやデータの物理保存管理
* `obsidian_exporter.py`: Obsidian連携（Callout、Canvas、Tasks.mdの自動生成）
* `views/`: 画面UI定義（TITLEとORDERを定義して配置するだけで自動的にメニューに追加される）
* `plugins/`: XRDや構造描画などのカスタム処理プラグイン

---

## 3. コーディング規約 (厳守ルール)

このプロジェクトの開発においては、以下のルールを徹底して守る必要があります。

* **仮想環境の使用**: 必ず `py-antigravity` 環境を使用すること。
* **スペースの排除**: 不必要なスペースは徹底して排除する（`=`の両端、`,`や`+`などの記号のあと等）。
  * 良い例: `a=1` / `func(a,b)` / `x,y=2,3`
  * 悪い例: `a = 1` / `func(a, b)` / `x, y = 2, 3`
* **変数の定義**: 変数はなるべく1行にまとめる。
  * 良い例: `a,b,c=1,2,3`
* **コメントの記述**: インラインコメントは避け、必ずコードの直上などに独立して記述し、プログラムと明確に分離する。
  * 良い例:
    ```python
    # データを取得する
    data=fetch_data()
    ```
  * 悪い例:
    ```python
    data=fetch_data() # データを取得する
    ```
* **文字コード・特殊文字**: Windows互換性を最優先し、コード内およびデータ表現において特殊文字（温度記号 `°C` など）は使用しない。
