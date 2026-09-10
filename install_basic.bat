@echo off
REM JAN-DRISHTI AI - Basic Installation Script (Windows)
REM Installs core packages for enhanced functionality

echo ========================================
echo JAN-DRISHTI AI - Basic Installation
echo ========================================
echo.

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python 3.9+ first.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python found! Checking version...
python --version
echo.

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment!
    pause
    exit /b 1
)
echo Virtual environment created!
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
echo.

REM Install basic packages
echo Installing core packages...
echo This may take a few minutes...
echo.

pip install pandas==2.0.3
if errorlevel 1 goto :error

pip install numpy==1.24.4
if errorlevel 1 goto :error

pip install openpyxl==3.1.2
if errorlevel 1 goto :error

pip install scikit-learn==1.3.2
if errorlevel 1 goto :error

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Installed packages:
pip list | findstr "pandas numpy openpyxl scikit"
echo.
echo New features available:
echo   - Excel file upload (.xlsx, .xls)
echo   - Faster data processing
echo   - Enhanced ML algorithms
echo   - Better statistical analysis
echo.
echo To run the server:
echo   venv\Scripts\activate
echo   python -m jan_drishti.server
echo.
echo Press any key to start the server now...
pause >nul

REM Start server
echo Starting JAN-DRISHTI AI server...
python -m jan_drishti.server --host 127.0.0.1 --port 8000

goto :end

:error
echo.
echo ========================================
echo ERROR: Installation failed!
echo ========================================
echo.
echo Please check your internet connection and try again.
echo Or install manually:
echo   pip install pandas numpy openpyxl scikit-learn
echo.
pause
exit /b 1

:end
