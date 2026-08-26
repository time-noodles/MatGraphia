# Google Drive（rclone）上のリポジトリにおける Git 分離管理運用ルール

本プロジェクトは、ファイル実体を Google Drive（rclone FUSE マウント）上に配置し、Git メタデータ（`.git`）をローカルストレージに分離して管理しています。LLM や自動化スクリプトが Git 操作を行う際は、通常の `git` コマンドではなく以下の仕様に必ず従ってください。

---

## 1. ディレクトリ構造・アーキテクチャ

| 役割 | Ubuntu (Linux) | Windows 11 |
|---|---|---|
| **実ファイル（Working Tree）** | `~/gdrive_storage/Python-Scripts/libs/MatGraphia` | `%USERPROFILE%\gdrive_storage\Python-Scripts\libs\MatGraphia` |
| **Git メタデータ（Git Dir）** | `~/Python-Scripts/MatGraphia-git` | `%USERPROFILE%\Python-Scripts\MatGraphia-git` |
| **専用コマンド** | `matgit`（または明示的フラグ指定） | `matgit`（または明示的フラグ指定） |

---

## 2. LLM / エージェント実行ルール

### 🚨 絶対禁止事項
- `~/gdrive_storage/...` 配下で `git init` や `git clone` を実行しないこと（FUSE 上に `.git` を作らない）。
- 単なる `git status` や `git add` など、`--git-dir` や `--work-tree` を指定しない生 `git` コマンドを実行しないこと。

### 実行コマンド仕様

#### A. Ubuntu (Bash / Zsh) 環境
エイリアス `matgit` を利用するか、明示的パス指定で実行します。

```bash
# 基本操作（エイリアス）
matgit status
matgit add -A
matgit commit -m "feat: [変更内容]"
matgit push origin main

# エイリアス非展開シェル（スクリプト・Subprocess 等）での完全指定形式
git --git-dir=$HOME/Python-Scripts/MatGraphia-git --work-tree=$HOME/gdrive_storage/Python-Scripts/libs/MatGraphia <command>
```

#### B. Windows 11 (PowerShell) 環境
PowerShell 関数 `matgit` を利用するか、環境変数を明示して実行します。

```powershell
# 基本操作
matgit status
matgit add -A
matgit commit -m "feat: [変更内容]"
matgit push origin main

# スクリプト・直接実行形式
git --git-dir="$ENV:USERPROFILE\Python-Scripts\MatGraphia-git" --work-tree="$ENV:USERPROFILE\gdrive_storage\Python-Scripts\libs\MatGraphia" <command>
```

---

## 3. ネットワーク・通信仕様（学内プロキシ対応）

GitHub への通信は、学内ファイアウォール（Port 22 / 直 443 遮断）を回避するため、以下の SSH over Proxy 設定が適用されています。

* **プロキシ**: `proxy.noc.titech.ac.jp:3128`
* **SSH 宛先**: `ssh.github.com:443`
* **中継ツール**: `connect-proxy`

LLM がリモート接続トラブルを検知した場合は、`~/.ssh/config` が以下のように構成されているか確認してください：

```ssh-config
Host github.com
    Hostname ssh.github.com
    Port 443
    User git
    ProxyCommand connect-proxy -H proxy.noc.titech.ac.jp:3128 %h %p
```

---

## 4. 高速化設定（FUSE 遅延対策）

FUSE マウント特有の I/O 遅延（`stat()` コスト）を回避するため、リポジトリ設定には以下のフラグが適用されています。

```bash
# 変更監視デーモンとキャッシュの有効化
matgit config core.fsmonitor true
matgit config core.untrackedCache true
matgit config core.preloadindex true
matgit config core.filemode false
```
