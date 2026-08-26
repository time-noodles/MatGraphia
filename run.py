#!/usr/bin/env python3
"""
MatGraphia Python ワンクリック起動ランナー (run.py)
Windows, Linux, macOS に完全対応。
`./run.py` または `python run.py` で即座に Streamlit アプリを立ち上げます。
"""
import os
import sys
import subprocess

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print("=================================================================")
    print(" 🧬 MatGraphia Python 簡単起動ランナー (Windows / Linux / macOS)")
    print("=================================================================")
    
    python_executable = sys.executable
    
    if sys.platform != "win32":
        default_conda_py = os.path.expanduser("~/miniconda3/envs/py312/bin/python")
        if os.path.exists(default_conda_py):
            python_executable = default_conda_py
    else:
        win_user = os.environ.get("USERNAME", "")
        possible_win_pythons = [
            sys.executable,
            rf"C:\Users\{win_user}\miniconda3\envs\py312\python.exe",
            rf"C:\Users\{win_user}\anaconda3\envs\py312\python.exe",
            rf"C:\Users\{win_user}\miniconda3\python.exe",
            rf"C:\Users\{win_user}\anaconda3\python.exe",
            r"C:\ProgramData\miniconda3\python.exe",
            r"C:\ProgramData\anaconda3\python.exe"
        ]
        for py in possible_win_pythons:
            if py and os.path.exists(py):
                python_executable = py
                break

    cmd = [python_executable, "-m", "streamlit", "run", "app.py", "--server.headless=false", "--server.port=8501"]
    print(f"実行環境 Python: {python_executable}")
    print(f"実行コマンド: {' '.join(cmd)}")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nMatGraphia アプリケーションを終了しました。")

if __name__ == "__main__":
    main()
