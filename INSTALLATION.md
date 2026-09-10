# JAN-DRISHTI AI - Installation Guide

## 🚀 Quick Start (Zero Dependencies)

The system works **out of the box** with just Python 3.9+!

```bash
# Clone or download the project
cd SIH_winner

# Run immediately (no installation needed!)
python -m jan_drishti.server --host 127.0.0.1 --port 8000
```

**That's it!** Open http://127.0.0.1:8000 in your browser.

---

## 📦 Installation Options

Choose based on your needs:

### Option 1: Minimal (Current - No Dependencies) ✅

**Uses:** Python standard library only  
**Best for:** Quick demos, basic analysis, minimal setup

```bash
# No installation needed!
python -m jan_drishti.server
```

**Features:**
- ✅ All core functionality
- ✅ CSV/JSON upload
- ✅ Risk analysis
- ✅ Authentication & database
- ✅ Zero setup time

---

### Option 2: Basic (Core Features) 🎯

**Adds:** Better data handling, Excel support, basic ML  
**Best for:** Daily use, Excel files, improved performance

```bash
pip install pandas numpy openpyxl scikit-learn
```

**Added Features:**
- ✅ Excel file upload (.xlsx, .xls)
- ✅ Faster CSV processing
- ✅ Better data validation
- ✅ Enhanced anomaly detection
- ✅ Statistical analysis

---

### Option 3: Enhanced (Production Ready) 🚀

**Adds:** FastAPI, PostgreSQL, caching, monitoring  
**Best for:** Production deployment, multiple users, scalability

```bash
pip install fastapi uvicorn[standard] pandas numpy scikit-learn psycopg2-binary redis
```

**Added Features:**
- ✅ Async web framework (faster)
- ✅ PostgreSQL database (scalable)
- ✅ Redis caching (performance)
- ✅ Auto API documentation
- ✅ Better error handling

---

### Option 4: Full (All Features) 💪

**Adds:** Everything - ML, PDF, NLP, visualization, testing  
**Best for:** Advanced analysis, reporting, development

```bash
pip install -r requirements.txt
```

**Added Features:**
- ✅ PDF upload & report generation
- ✅ Advanced NLP for text analysis
- ✅ Data visualization & charts
- ✅ Background task processing
- ✅ Monitoring & logging
- ✅ Testing framework
- ✅ Development tools

---

## 🔧 Detailed Installation Steps

### Prerequisites

**Required:**
- Python 3.9 or higher
- pip (Python package manager)

**Recommended:**
- Git (for version control)
- Virtual environment

**Check your Python version:**
```bash
python --version
# Should show: Python 3.9.x or higher
```

---

### Step 1: Set Up Virtual Environment (Recommended)

**Windows:**
```bash
# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# You should see (venv) in your prompt
```

**Linux/Mac:**
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# You should see (venv) in your prompt
```

---

### Step 2: Install Packages

**Choose your installation level:**

#### Minimal (No dependencies - skip this!)
```bash
# Already working! No installation needed.
```

#### Basic Installation
```bash
pip install pandas==2.0.3 numpy==1.24.4 openpyxl==3.1.2 scikit-learn==1.3.2
```

#### Production Installation
```bash
pip install fastapi==0.104.1 uvicorn[standard]==0.24.0 pandas==2.0.3 numpy==1.24.4 scikit-learn==1.3.2 psycopg2-binary==2.9.9 redis==5.0.1
```

#### Full Installation
```bash
pip install -r requirements.txt
```

---

### Step 3: Verify Installation

```bash
# Check installed packages
pip list

# Should see packages like:
# pandas, numpy, openpyxl, etc. (depending on what you installed)
```

---

### Step 4: Run the Server

```bash
# Standard library version (always works)
python -m jan_drishti.server --host 127.0.0.1 --port 8000

# With FastAPI (if installed)
# python -m jan_drishti.server_fastapi --host 127.0.0.1 --port 8000
```

---

## 🌍 Environment Variables

Create a `.env` file for configuration:

```bash
# Server Configuration
JAN_DRISHTI_HOST=0.0.0.0
JAN_DRISHTI_PORT=8000
JAN_DRISHTI_MAX_UPLOAD_MB=50

# Database (optional - defaults to SQLite)
DATABASE_URL=postgresql://user:password@localhost/jandrishti

# Redis Cache (optional)
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-secret-key-here-change-in-production

# Logging
LOG_LEVEL=INFO
SENTRY_DSN=your-sentry-dsn-here
```

---

## 📊 Feature Comparison

| Feature | Minimal | Basic | Enhanced | Full |
|---------|---------|-------|----------|------|
| CSV Upload | ✅ | ✅ | ✅ | ✅ |
| JSON Upload | ✅ | ✅ | ✅ | ✅ |
| Excel Upload | ❌ | ✅ | ✅ | ✅ |
| PDF Upload | ❌ | ❌ | ❌ | ✅ |
| Risk Analysis | ✅ | ✅ | ✅ | ✅ |
| ML Enhancement | ❌ | ✅ | ✅ | ✅ |
| Fast Processing | ⚡ | ⚡⚡ | ⚡⚡⚡ | ⚡⚡⚡ |
| PostgreSQL | ❌ | ❌ | ✅ | ✅ |
| Caching | ❌ | ❌ | ✅ | ✅ |
| PDF Reports | ❌ | ❌ | ❌ | ✅ |
| Charts/Graphs | ❌ | ❌ | ❌ | ✅ |
| Background Jobs | ❌ | ❌ | ✅ | ✅ |
| Monitoring | ❌ | ❌ | ✅ | ✅ |
| Testing Suite | ❌ | ❌ | ❌ | ✅ |
| Setup Time | 0 min | 2 min | 5 min | 10 min |
| Disk Space | 0 MB | 200 MB | 500 MB | 1 GB |

---

## 🎓 Use Case Recommendations

### For Hackathon Demo
**Use:** Minimal (no dependencies)
- Instant setup
- Shows core innovation
- Zero installation hassle

### For Pilot Deployment
**Use:** Basic installation
- Excel file support
- Better performance
- Still lightweight

### For District/Department
**Use:** Enhanced installation
- Multiple users
- Faster processing
- Production-ready

### For State/National
**Use:** Full installation
- All features
- Scalable
- Enterprise-grade

---

## 🔍 Troubleshooting

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'pandas'`

**Solution:**
```bash
pip install pandas
```

### Permission Errors (Windows)

**Problem:** `Access Denied` during pip install

**Solution:**
```bash
# Run PowerShell as Administrator, or:
pip install --user packagename
```

### Permission Errors (Linux/Mac)

**Problem:** `Permission denied` during pip install

**Solution:**
```bash
# Use virtual environment (recommended), or:
pip install --user packagename
# Or with sudo (not recommended):
sudo pip install packagename
```

### Conflicting Versions

**Problem:** Package version conflicts

**Solution:**
```bash
# Uninstall all packages
pip freeze > to_uninstall.txt
pip uninstall -r to_uninstall.txt -y

# Reinstall fresh
pip install -r requirements.txt
```

### Database Migration (SQLite to PostgreSQL)

**If using enhanced/full installation:**

```bash
# Install PostgreSQL support
pip install psycopg2-binary sqlalchemy

# Set environment variable
export DATABASE_URL=postgresql://user:pass@localhost/dbname

# Migrate data (create migration script if needed)
python migrate_database.py
```

---

## 🚀 Production Deployment

### Using Gunicorn (Linux/Mac)

```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker jan_drishti.server:app
```

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "-m", "jan_drishti.server"]
```

### Using Systemd Service (Linux)

```ini
[Unit]
Description=JAN-DRISHTI AI Service
After=network.target

[Service]
Type=simple
User=jandrishti
WorkingDirectory=/opt/jandrishti
ExecStart=/opt/jandrishti/venv/bin/python -m jan_drishti.server
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 📝 Development Setup

For contributing or advanced development:

```bash
# Clone repository
git clone https://github.com/your-org/jan-drishti-ai.git
cd jan-drishti-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install development dependencies
pip install -r requirements.txt

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install

# Run tests
pytest

# Run with auto-reload
uvicorn jan_drishti.server:app --reload

# Code formatting
black .

# Type checking
mypy jan_drishti/
```

---

## 🎯 Quick Reference Commands

```bash
# Check Python version
python --version

# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Activate virtual environment (Linux/Mac)
source venv/bin/activate

# Install basic packages
pip install pandas numpy openpyxl scikit-learn

# Install all packages
pip install -r requirements.txt

# Run server (standard)
python -m jan_drishti.server

# Run tests
pytest

# Deactivate virtual environment
deactivate
```

---

## 💡 Tips

1. **Start Minimal** - Use standard library version first to verify it works
2. **Add Gradually** - Install packages as you need features
3. **Use Virtual Env** - Always use virtual environment to avoid conflicts
4. **Pin Versions** - Lock package versions for reproducible deployments
5. **Read Logs** - Check console output for errors and warnings

---

## 📚 Additional Resources

- **Python Downloads:** https://www.python.org/downloads/
- **pip Documentation:** https://pip.pypa.io/
- **Virtual Environments:** https://docs.python.org/3/tutorial/venv.html
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **Pandas Guide:** https://pandas.pydata.org/docs/

---

## 🆘 Getting Help

**Installation Issues:**
1. Check Python version (`python --version`)
2. Try in virtual environment
3. Update pip (`pip install --upgrade pip`)
4. Check firewall/antivirus settings
5. Review error messages carefully

**Still Stuck?**
- Check GitHub Issues
- Review documentation
- Ask in project Discord/Slack
- Contact support team

---

**Built for flexibility - from zero dependencies to full-featured enterprise system! 🚀**

**Last Updated:** Smart India Hackathon 2026  
**Python Version:** 3.9+  
**Platform:** Windows, Linux, macOS
