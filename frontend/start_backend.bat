@echo off
echo Starting Backend Server...
cd backend
conda activate heart
python api.py
pause
