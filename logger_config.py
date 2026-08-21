# コンソールおよび未捕捉エラー・Python標準ログの自動保存モジュール
import os
import sys
import logging
import warnings
import traceback
from datetime import datetime

LOG_FILE_PATH="data/system_errors.log"
_LOGGER_INITIALIZED=False

# 無視対象のログ・警告パターン
_IGNORED_PATTERNS=[
    "missing ScriptRunContext",
    "No artists with labels found to put in legend",
    "running in bare mode",
]

# 標準エラー出力を拡張してファイルへ自動書き込みするクラス
class StderrTee:
    def __init__(self,original_stderr):
        self.original_stderr=original_stderr
        self._is_matgraphia_tee=True

    def write(self,message):
        self.original_stderr.write(message)
        if not message or not message.strip():
            return
        # 無視パターンのチェック
        if any(p in message for p in _IGNORED_PATTERNS):
            return
        try:
            os.makedirs(os.path.dirname(LOG_FILE_PATH),exist_ok=True)
            with open(LOG_FILE_PATH,"a",encoding="utf-8") as f:
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                msg_clean=message.strip()
                f.write(f"[{timestamp}] [stderr] {msg_clean}\n")
        except Exception:
            pass

    def flush(self):
        self.original_stderr.flush()

# 未処理例外のカスタムフック
def custom_excepthook(exc_type,exc_value,exc_tb):
    tb_str="".join(traceback.format_exception(exc_type,exc_value,exc_tb))
    try:
        os.makedirs(os.path.dirname(LOG_FILE_PATH),exist_ok=True)
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE_PATH,"a",encoding="utf-8") as f:
            f.write(f"\n========================================\n")
            f.write(f"[{timestamp}] UNCAUGHT EXCEPTION: {exc_type.__name__}: {exc_value}\n")
            f.write(tb_str)
            f.write(f"========================================\n")
    except Exception:
        pass
    sys.__excepthook__(exc_type,exc_value,exc_tb)

# カスタム Logging ハンドラー (エラーのみ記録)
class FileLogHandler(logging.Handler):
    def emit(self,record):
        try:
            msg=self.format(record)
            if any(p in msg for p in _IGNORED_PATTERNS):
                return
            os.makedirs(os.path.dirname(LOG_FILE_PATH),exist_ok=True)
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(LOG_FILE_PATH,"a",encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{record.levelname}] {msg}\n")
        except Exception:
            pass

# ロガーのセットアップ関数
def setup_logger():
    global _LOGGER_INITIALIZED
    # 既存の Tee ラッパーチェック
    curr=sys.stderr
    is_wrapped=False
    while curr is not None:
        if getattr(curr,"_is_matgraphia_tee",False) or isinstance(curr,StderrTee):
            is_wrapped=True
            break
        curr=getattr(curr,"target",None) or getattr(curr,"_stream",None) or getattr(curr,"stream",None)
    if not is_wrapped:
        sys.stderr=StderrTee(sys.stderr)

    if _LOGGER_INITIALIZED:
        return

    os.makedirs(os.path.dirname(LOG_FILE_PATH),exist_ok=True)
    sys.excepthook=custom_excepthook

    root_logger=logging.getLogger()
    if not any(isinstance(h,FileLogHandler) for h in root_logger.handlers):
        handler=FileLogHandler()
        # エラーログファイルには ERROR 以上のみ出力しログ膨張を防止
        handler.setLevel(logging.ERROR)
        root_logger.addHandler(handler)

    # ノイズ警告の抑止設定
    warnings.filterwarnings("ignore",category=UserWarning,module=".*streamlit.*")
    warnings.filterwarnings("ignore",message=".*missing ScriptRunContext.*")
    warnings.filterwarnings("ignore",message=".*No artists with labels found.*")

    noise_loggers=[
        "streamlit",
        "streamlit.runtime.caching.cache_data_api",
        "streamlit.runtime.scriptrunner_utils.script_run_context",
        "streamlit.runtime.scriptrunner.script_runner",
        "werkzeug",
        "urllib3",
    ]
    for name in noise_loggers:
        logging.getLogger(name).setLevel(logging.ERROR)

    _LOGGER_INITIALIZED=True

# エラーログファイルの読み込み
def read_system_error_logs()->str:
    if not os.path.exists(LOG_FILE_PATH):
        return "現在、システムエラーログはありません。"
    try:
        with open(LOG_FILE_PATH,"r",encoding="utf-8") as f:
            lines=f.readlines()
            return "".join(lines[-200:])
    except Exception as e:
        return f"ログ読み込みエラー: {e}"

# エラーログファイルのクリア
def clear_system_error_logs():
    if os.path.exists(LOG_FILE_PATH):
        try:
            with open(LOG_FILE_PATH,"w",encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass
