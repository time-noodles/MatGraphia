#!/usr/bin/env bash
# ==============================================================================
# MatGraphia 簡単ワンクリック起動スクリプト (launch.sh)
# ==============================================================================
# ターミナルでの cd や conda activate、streamlit コマンド入力の手数を不要にし、
# ダブルクリックまたは一発実行で仮想環境を自動認識して MatGraphia を起動します。

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "================================================================="
echo " 🧬 MatGraphia 物質科学データ管理システムを起動中..."
echo "================================================================="

# Conda 環境 py312 の自動ロード
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
    conda activate py312 2>/dev/null || true
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
    conda activate py312 2>/dev/null || true
fi

# notify-send 通知
if command -v notify-send &> /dev/null; then
    notify-send "MatGraphia DB" "🧬 MatGraphia アプリケーションを起動しています..." 2>/dev/null || true
fi

# Streamlit 起動
exec python -m streamlit run app.py --server.headless=false --server.port=8501

