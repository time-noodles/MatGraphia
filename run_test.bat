@echo off
chcp 65001 >nul
call conda activate py312
python test_crystal.py > test_crystal_result.txt 2>&1
echo Done. See test_crystal_result.txt
pause
