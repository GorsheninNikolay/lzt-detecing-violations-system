@echo off
setlocal
cd /d "%~dp0"
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 (
  py -3.12 -m venv ".venv"
) else (
  py -3.11 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
  if errorlevel 1 goto :failed
  py -3.11 -m venv ".venv"
)
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install ultralytics==8.4.163 Pillow==11.3.0 numpy==2.3.5
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -c "import torch; assert torch.cuda.is_available(), 'CUDA unavailable'; assert (torch.ones(16,device='cuda')*3).sum().item()==48; print(torch.cuda.get_device_name(0))"
if errorlevel 1 goto :failed
echo Setup complete.
exit /b 0
:failed
echo Setup failed. See the error above. Install Python x64 3.11 or 3.12 and a CUDA 12.8-compatible NVIDIA driver.
exit /b 1
