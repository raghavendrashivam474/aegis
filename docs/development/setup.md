 Local Environment Setup

## 1. Prerequisites
* **Python:** >= 3.11
* **Git:** >= 2.30
* **Docker:** (Optional for local container topologies)

---

## 2. Environment Initialization

### Step 1: Clone the Repository
```bash
git clone https://github.com/your-org/aegis.git
cd aegis
```

### Step 2: Create a Virtual Environment

#### On Windows (PowerShell)
```Powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### On Linux / macOS
```Terminal
python3 -m venv .venv
source .venv/bin/activate
```

Step 3: Install Core Development Dependencies
```Bash

pip install --upgrade pip
pip install pytest ruff
```

## 3. Verify Local Setup

>Execute the local repository check script:


```Powershell
.\scripts\check.ps1
```

### Or run the individual tools manually:

```Bash
ruff check .
pytest
```