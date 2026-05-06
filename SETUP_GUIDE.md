# Aura2 Complete Setup Guide

**For Stakeholders:** This guide enables any developer to set up Aura2 from scratch in under 30 minutes.

**For Developers:** Comprehensive installation instructions with tested commands, common issues, and solutions.

---

## Prerequisites

### Required Software

| Software    | Minimum Version | Check Command      | Download                          |
| ----------- | --------------- | ------------------ | --------------------------------- |
| **Python**  | 3.11+           | `python --version` | https://www.python.org/downloads/ |
| **Node.js** | 20+             | `node --version`   | https://nodejs.org/               |
| **npm**     | 10+             | `npm --version`    | (included with Node.js)           |
| **Git**     | 2.40+           | `git --version`    | https://git-scm.com/              |

**Optional but Recommended:**

- **VSCode** - https://code.visualstudio.com/
- **GitHub CLI** - https://cli.github.com/ (for GitHub integration)
- **Vercel CLI** - `npm install -g vercel` (for deployment)

---

### Required API Tokens

#### 1. Figma Personal Access Token (Required)

**For Stakeholders:** Allows Aura2 to read your Figma designs.

**For Developers:**

1. Go to https://www.figma.com/developers/api#access-tokens
2. Click "Get personal access token"
3. Copy the token (starts with `figd_`)
4. Save as `FIGMA_TOKEN` in `.env`

**Scope:** Read-only access to Figma files

---

#### 2. LiteLLM API Key (Required - Claude Access)

**For Stakeholders:** This provides access to Claude AI for code generation.

**For Developers:**

- **Base URL:** ``
- **Provider:** Contact your LiteLLM provider for API key
- **Models Used:**
  - `claude-opus-4-6` - Code generation (primary)
  - `claude-sonnet-3.5` - Design extraction, verification
  - `claude-haiku-3` - Simple validation tasks

**Cost:** ~$262/month for 20 projects (based on token usage)

---

#### 3. GitHub Personal Access Token (Optional)

**For Stakeholders:** Enables automatic code deployment to GitHub.

**For Developers:**

1. Go to https://github.com/settings/tokens
2. Generate new token (classic)
3. Scopes required:
   - ✅ `repo` (full repository access)
   - ✅ `workflow` (if using GitHub Actions)
4. Copy token
5. Save as `GITHUB_PERSONAL_ACCESS_TOKEN` in `.env`

**When to use:** Auto-create GitHub repos for generated projects

---

#### 4. Vercel API Token (Optional)

**For Stakeholders:** Enables automatic website deployment.

**For Developers:**

1. Go to https://vercel.com/account/tokens
2. Create token
3. Copy token
4. Save as `VERCEL_TOKEN` in `.env`

**When to use:** Auto-deploy generated projects to live URLs

---

## Installation Steps

### Step 1: Clone Repository

```bash
git clone https://github.com/poojabisht10/Aura-agent.git
cd Aura-agent
```

**Expected Output:**

```
Cloning into 'Aura-agent'...
remote: Enumerating objects: 450, done.
remote: Counting objects: 100% (450/450), done.
...
Resolving deltas: 100% (240/240), done.
```

**Verify:**

```bash
ls -la
```

You should see: `backend/`, `frontend/`, `figma-plugin/`, `requirements.txt`, etc.

---

### Step 2: Backend Setup (Python)

#### 2.1 Create Virtual Environment

**Windows:**

```bash
python -m venv .venv
```

**Linux/Mac:**

```bash
python3 -m venv .venv
```

**Expected Output:**

```
Creating virtual environment...
```

**Verify:**

```bash
ls .venv
# Should show: Scripts/ (Windows) or bin/ (Linux/Mac)
```

---

#### 2.2 Activate Virtual Environment

**Windows (Command Prompt):**

```bash
.venv\Scripts\activate
```

**Windows (PowerShell):**

```powershell
.venv\Scripts\Activate.ps1
```

**Linux/Mac:**

```bash
source .venv/bin/activate
```

**Expected Output:**

```
(.venv) PS C:\...\Aura-agent>
```

(Note the `(.venv)` prefix indicating activation)

**Troubleshooting:**

- ❌ **PowerShell:** "cannot be loaded because running scripts is disabled"
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

---

#### 2.3 Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Expected Duration:** 2-5 minutes

**Expected Output:**

```
Collecting anthropic>=0.40.0
...
Successfully installed anthropic-0.42.0 fastapi-0.109.0 ...
```

**Common Issues:**

##### Issue 1: `error: Microsoft Visual C++ 14.0 or greater is required`

**For Stakeholders:** Some Python packages need C++ compiler.

**For Developers:**
**Solution:**

1. Download Visual Studio Build Tools: https://visualstudio.microsoft.com/downloads/
2. Install "Desktop development with C++"
3. Retry: `pip install -r requirements.txt`

##### Issue 2: `chromadb installation fails`

**Solution:**

```bash
pip install chromadb==0.4.22
pip install -r requirements.txt
```

##### Issue 3: `Timeout or network error`

**Solution:**

```bash
pip install --timeout=120 -r requirements.txt
# Or use a mirror
pip install -i https://pypi.org/simple -r requirements.txt
```

##### Issue 4: `Permission denied` (Linux/Mac)

**Solution:**

```bash
pip install --user -r requirements.txt
# Or use sudo (not recommended)
```

---

#### 2.4 Install Playwright Browsers

**For Stakeholders:** Headless browser for visual verification.

**For Developers:**

```bash
python -m playwright install chromium
```

**Expected Duration:** 1-2 minutes

**Expected Output:**

```
Downloading Chromium 123.0.6296.0...
100% [========================================]
Chromium 123.0.6296.0 downloaded to ...
```

**Common Issues:**

##### Issue 1: `playwright: command not found`

**Solution:**

```bash
python -m playwright install chromium
```

##### Issue 2: `Missing system dependencies` (Linux)

**Solution:**

```bash
python -m playwright install-deps chromium
# Or manually install
sudo apt-get install -y \
  libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
  libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libasound2
```

---

### Step 3: Frontend Setup (Node.js)

#### 3.1 Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

**Expected Duration:** 2-4 minutes

**Expected Output:**

```
added 1234 packages, and audited 1235 packages in 3m
```

**Common Issues:**

##### Issue 1: `ERESOLVE unable to resolve dependency tree`

**Solution:**

```bash
cd frontend
npm install --legacy-peer-deps
cd ..
```

##### Issue 2: `npm ERR! code EACCES` (Permission denied)

**Solution (Linux/Mac):**

```bash
sudo chown -R $USER ~/.npm
npm install
```

##### Issue 3: `Timeout` or slow download

**Solution:**

```bash
npm config set registry https://registry.npmjs.org/
npm install
```

---

#### 3.2 Install Root Dependencies (Playwright)

```bash
# In project root
npm install
```

**Expected Output:**

```
added 3 packages in 5s
```

---

### Step 4: Environment Configuration ⚠️ CRITICAL

#### 4.1 Create `.env` File

**Windows:**

```bash
copy .env.example .env
```

**Linux/Mac:**

```bash
cp .env.example .env
```

**Verify:**

```bash
ls -la | grep .env
```

Should show both `.env` and `.env.example`

---

#### 4.2 Configure Environment Variables

**Open `.env` in your editor:**

```bash
code .env  # VSCode
# OR
nano .env  # Linux/Mac
# OR
notepad .env  # Windows
```

**Required Configuration:**

```env
# Figma API
FIGMA_TOKEN=figd_your_actual_figma_token_here

# LiteLLM (Claude API)
LITELLM_API_KEY=your_actual_litellm_api_key_here
LITELLM_BASE_URL=
LITELLM_PROVIDER=litellm

# Database (use defaults)
DATABASE_URL=sqlite+aiosqlite:///./aura2.db

# Directories (use defaults)
GENERATED_PROJECTS_DIR=./generated_projects
COMPONENT_LIBRARY_DIR=./component_library
```

**Optional Configuration:**

```env
# GitHub Integration (optional)
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_github_token_here
GITHUB_OWNER=your_github_username

# Vercel Deployment (optional)
VERCEL_TOKEN=your_vercel_token_here

# Vision Comparison Settings
ENABLE_VISION_COMPARISON=true
VISION_COMPARISON_CONFIDENCE_THRESHOLD=95
VISION_COMPARISON_MAX_ITERATIONS=10
```

**⚠️ Important:**

- Never commit `.env` to Git (already in `.gitignore`)
- Keep tokens secure
- Don't share API keys

---

### Step 5: Initialize Data Directories

**For Stakeholders:** Creates folders for generated projects and component library.

**For Developers:**

```bash
# Create required directories
mkdir -p data generated_projects component_library/chroma

# Initialize projects database
echo "[]" > data/projects.json
```

**Windows (if mkdir -p fails):**

```powershell
New-Item -ItemType Directory -Force -Path data
New-Item -ItemType Directory -Force -Path generated_projects
New-Item -ItemType Directory -Force -Path component_library\chroma
echo "[]" > data\projects.json
```

**Verify:**

```bash
ls -la data/projects.json
# Should show: -rw-r--r-- ... 2 ... projects.json
```

---

### Step 6: MCP Server Configuration (Optional)

**For Stakeholders:** Model Context Protocol servers enable Claude Code integration.

**For Developers:**

#### 6.1 Verify `.mcp.json` Configuration

File `.mcp.json` should contain:

```json
{
  "mcpServers": {
    "shadcn": {
      "command": "cmd",
      "args": ["/c", "npx", "shadcn@latest", "mcp"]
    },
    "drawio": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "drawio-mcp-server"]
    }
  }
}
```

**Linux/Mac:** Change `cmd` to `sh` and `/c` to `-c`

#### 6.2 Enable MCP Servers (Claude Code CLI)

File `.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": ["Bash(*)", "WebFetch(*)", "WebSearch"]
  },
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": ["shadcn", "drawio"]
}
```

**Optional:** Add GitHub and Vercel MCPs later if needed.

---

### Step 7: Verify Installation

#### 7.1 Test Backend

**Activate venv (if not already active):**

```bash
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

**Start backend:**

```bash
python -m uvicorn backend.main:app --reload
```

**Expected Output:**

```
INFO:     Will watch for changes in these directories: [...]
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Test in Browser:**

1. Open: http://127.0.0.1:8000/docs
2. You should see **FastAPI Swagger UI** with 22 endpoints

**API Endpoints to verify:**

- `GET /api/health` - Health check
- `POST /api/projects/create` - Create project from Figma
- `GET /api/projects` - List projects

**Test Health Endpoint:**

```bash
# In new terminal
curl http://127.0.0.1:8000/api/health
```

**Expected:**

```json
{ "status": "healthy", "version": "2.0.0" }
```

**Stop backend:**
Press `Ctrl+C`

---

#### 7.2 Test Frontend

**In new terminal:**

```bash
cd frontend
npm run dev
```

**Expected Output:**

```
VITE v5.0.8  ready in 324 ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
➜  press h + enter to show help
```

**Test in Browser:**

1. Open: http://localhost:5173
2. You should see **Aura2 Dashboard**

**Expected UI:**

- Project list (empty initially)
- "Create Project" button
- Component library tab
- Dev servers status

**Stop frontend:**
Press `Ctrl+C`

---

#### 7.3 Test ChromaDB (Component Store)

```bash
python -c "from backend.rag.component_store import ComponentStore; store = ComponentStore(); print('✓ ChromaDB initialized')"
```

**Expected Output:**

```
✓ ChromaDB initialized
```

**Common Issues:**

##### Issue 1: `chromadb.errors.NoIndexException`

**Solution:**

```bash
mkdir -p component_library/chroma
python -c "from backend.rag.component_store import ComponentStore; ComponentStore()"
```

##### Issue 2: `ModuleNotFoundError: No module named 'chromadb'`

**Solution:**

```bash
source .venv/bin/activate  # Activate venv!
pip install chromadb
```

---

#### 7.4 Test Playwright

```bash
python -m playwright show-browser chromium
```

**Expected:**

- Chromium browser window opens
- Blank page displays

**Common Issues:**

##### Issue 1: `Browser closed` or crash

**Solution:**

```bash
python -m playwright install chromium
python -m playwright install-deps  # Linux only
```

---

### Step 8: Run Tests

**For Stakeholders:** Automated tests verify everything works correctly.

**For Developers:**

```bash
# Activate venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate  # Windows

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_rag_store.py -v

# Run with coverage
pytest tests/ --cov=backend --cov-report=html
```

**Expected Output:**

```
tests/test_database.py::test_create_project PASSED              [ 5%]
tests/test_mcp_tools.py::test_component_library_tool PASSED     [10%]
tests/test_rag_store.py::test_add_component PASSED              [15%]
...
===================== 20 passed in 12.34s ======================
```

**Common Test Failures:**

##### Test: `test_figma_api_connection`

**Error:** `FigmaAPIError: Invalid token`
**Solution:** Set valid `FIGMA_TOKEN` in `.env`

##### Test: `test_component_store`

**Error:** `chromadb.errors.NoIndexException`
**Solution:**

```bash
mkdir -p component_library/chroma
pytest tests/test_rag_store.py -v
```

---

### Step 9: Figma Plugin Setup (Optional)

**For Stakeholders:** Bypasses Figma API rate limits (2 req/s).

**For Developers:**

#### 9.1 Build Figma Plugin

```bash
cd figma-plugin
npm install
npm run build
```

**Expected Output:**

```
> build
> esbuild src/code.ts --bundle --outfile=dist/code.js

  dist/code.js  152.4kb

✨  Done in 1.23s
```

#### 9.2 Load Plugin in Figma Desktop

1. **Open Figma Desktop** (not browser)
2. **Menu:** Plugins → Development → Import plugin from manifest
3. **Select:** `figma-plugin/manifest.json`
4. **Verify:** Plugin appears as "Aura - Figma to React"

#### 9.3 Configure Backend URL

Edit `figma-plugin/src/code.ts`:

```typescript
// Line ~5
const BACKEND_URL = "http://localhost:8000"; // Or your deployed URL
```

**Rebuild after changes:**

```bash
npm run build
```

#### 9.4 Test Plugin

1. Open any Figma file
2. Right-click → Plugins → Aura - Figma to React
3. Plugin UI should appear
4. Click "Send to Aura2"
5. Check backend logs for upload

---

## Common Setup Issues & Solutions

### Issue 1: `ModuleNotFoundError: No module named 'anthropic'`

**Cause:** Virtual environment not activated

**Solution:**

```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate

# Verify
which python  # Should show path in .venv
```

---

### Issue 2: `chromadb.errors.NoIndexException`

**Cause:** ChromaDB directory doesn't exist

**Solution:**

```bash
mkdir -p component_library/chroma
python -c "from backend.rag.component_store import ComponentStore; ComponentStore()"
```

---

### Issue 3: `FileNotFoundError: [Errno 2] No such file or directory: 'data/projects.json'`

**Cause:** Data directory not initialized

**Solution:**

```bash
mkdir -p data
echo "[]" > data/projects.json
```

---

### Issue 4: `playwright._impl._api_types.Error: Browser closed`

**Cause:** Playwright browsers not installed

**Solution:**

```bash
python -m playwright install chromium
# Linux only:
python -m playwright install-deps
```

---

### Issue 5: Frontend `Module not found: Can't resolve '@/components'`

**Cause:** TypeScript path aliases not configured (rare)

**Solution:**

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

Verify `tsconfig.json` has:

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

---

### Issue 6: `EADDRINUSE: address already in use :::8000`

**Cause:** Backend already running or port in use

**Solution:**

**Windows:**

```bash
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Linux/Mac:**

```bash
lsof -i :8000
kill -9 <PID>
```

**Or use different port:**

```bash
uvicorn backend.main:app --reload --port 8001
```

---

### Issue 7: `Permission denied` executing scripts (Linux/Mac)

**Cause:** Insufficient file permissions

**Solution:**

```bash
chmod +x .venv/bin/activate
chmod +x scripts/*.sh  # If any scripts exist
```

---

### Issue 8: `SSL certificate verify failed` (pip install)

**Cause:** Corporate firewall or network restrictions

**Solution:**

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

---

## Deployment Setup (Optional)

### GitHub Integration

**For Stakeholders:** Automatically creates GitHub repositories for generated projects.

**For Developers:**

#### 1. Install GitHub CLI (Optional but recommended)

```bash
# Windows (winget)
winget install GitHub.cli

# Mac
brew install gh

# Linux
sudo apt install gh
```

#### 2. Authenticate

```bash
gh auth login
```

#### 3. Configure in `.env`

```env
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_OWNER=your_github_username
```

#### 4. Test Integration

1. Generate a project via Aura2 API
2. Check GitHub for new repository
3. Verify commit history

---

### Vercel Deployment

**For Stakeholders:** Automatically deploys generated websites to live URLs.

**For Developers:**

#### 1. Install Vercel CLI

```bash
npm install -g vercel
```

#### 2. Login

```bash
vercel login
```

#### 3. Configure in `.env`

```env
VERCEL_TOKEN=xxxxxxxxxxxxxxxxxxxxxx
VERCEL_ORG_ID=team_xxxxxx  # Optional, for teams
```

#### 4. Test Deployment

1. Generate a project
2. Project auto-deploys to Vercel
3. Access via: `https://project-name.vercel.app`

---

## Verification Checklist

Before using Aura2, verify:

- [ ] Python 3.11+ installed (`python --version`)
- [ ] Node.js 20+ installed (`node --version`)
- [ ] Git installed (`git --version`)
- [ ] Virtual environment created and activated (`.venv` folder exists)
- [ ] All Python dependencies installed (`pip list | grep anthropic`)
- [ ] All frontend dependencies installed (`ls frontend/node_modules`)
- [ ] Playwright browsers installed (`ls ~/.cache/ms-playwright/chromium-*`)
- [ ] `.env` file created with required tokens
- [ ] `.mcp.json` configured (optional)
- [ ] Data directories created (`ls data/ generated_projects/ component_library/`)
- [ ] Backend starts successfully (http://127.0.0.1:8000/docs accessible)
- [ ] Frontend starts successfully (http://localhost:5173 accessible)
- [ ] Tests pass (`pytest tests/ -v`)
- [ ] ChromaDB initializes (`python -c "from backend.rag.component_store import ComponentStore; ComponentStore()"`)

---

## Next Steps

### 1. Test Project Generation

**Via REST API:**

```bash
curl -X POST http://127.0.0.1:8000/api/projects/create \
  -H "Content-Type: application/json" \
  -d '{"figma_url": "https://www.figma.com/file/ABC123/MyDesign"}'
```

**Via Figma Plugin:**

1. Open Figma file
2. Run plugin
3. Click "Send to Aura2"

**Verify:**

```bash
ls generated_projects/
# Should show new project folder
```

---

### 2. Explore Dashboard

1. Open http://localhost:5173
2. View generated projects
3. Check component library
4. Monitor dev servers

---

### 3. Read Technical Documentation

**For deep understanding:**

- See `TECHNICAL_DEEP_DIVE.md`
- Understand conversion pipeline
- Learn how each system works
- Customize configuration

**For troubleshooting:**

- See `PROBLEMS_SUMMARY.md`
- Known issues and workarounds
- Performance optimization tips

---

### 4. Customize Configuration

**Backend config:** `backend/config.py` (Pydantic settings)
**Frontend config:** `frontend/src/config.ts`
**MCP servers:** `.mcp.json`
**Environment:** `.env`

---

## Getting Help

### Community Resources

- **GitHub Issues:** https://github.com/poojabisht10/Aura-agent/issues
- **Discussions:** https://github.com/poojabisht10/Aura-agent/discussions
- **Documentation:** https://github.com/poojabisht10/Aura-agent/wiki

### Support

**For bugs:**

1. Check `PROBLEMS_SUMMARY.md` for known issues
2. Search existing GitHub issues
3. Create new issue with reproduction steps

**For questions:**

1. Check `TECHNICAL_DEEP_DIVE.md`
2. Ask in GitHub Discussions
3. Tag maintainers if urgent

---

## Maintenance

### Update Dependencies

**Python:**

```bash
pip install --upgrade -r requirements.txt
```

**Frontend:**

```bash
cd frontend
npm update
```

**Playwright:**

```bash
python -m playwright install chromium
```

### Clean Up

**Remove generated projects:**

```bash
rm -rf generated_projects/*
```

**Reset ChromaDB:**

```bash
rm -rf component_library/chroma/*
```

**Reset project database:**

```bash
echo "[]" > data/projects.json
```

---

**Setup Guide Version:** 1.0
**Last Updated:** February 13, 2026
**Tested On:** Windows 11, macOS 14, Ubuntu 22.04
**Average Setup Time:** 20-30 minutes

---

**🎉 Congratulations! You've successfully set up Aura2.**

If you encountered any issues not covered in this guide, please report them on GitHub Issues so we can improve this documentation.
