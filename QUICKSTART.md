# FER3ON-AI-V2 Quick Start

This guide helps you start the project quickly and safely.

## 1. Prerequisites
- Python 3.10 or 3.11
- Windows environment recommended
- Virtual environment created under .venv

## 2. Setup
Run the installer once:

```bat
install.bat
```

Or with PowerShell:

```powershell
./install.ps1
```

## 3. Start the project
### Fast start
```bat
run_fast.bat
```

### Full start (cleanup + checks + runtime)
```bat
run_full.bat
```

### Python entrypoint
```bash
python tools/full_start.py
```

## 4. Run checks
```bash
python tools/run_project_checks.py
```

## 5. Health check
```bash
python tools/system_health_check.py
```

## 6. Useful folders
- runtime/logs — runtime logs
- runtime/state — runtime state
- docs/ — operational documentation
- archive/legacy_docs — archived historical docs

## 7. Notes
- Review config.env before live trading.
- Keep automation gated until health checks are green.
- Use the cleanup script whenever you want to remove temporary artifacts.
