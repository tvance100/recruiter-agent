# TalentMatch — AI Sales Recruiter Agent

An AI-powered web app that reads a candidate's resume, extracts their profile,
and returns ranked sales job matches — built with Flask + Claude.

---

## Project structure

```
recruiter-agent/
├── app.py              ← Flask backend (API routes)
├── requirements.txt    ← Python dependencies
├── Procfile            ← For Render/Railway deployment
├── README.md
└── templates/
    └── index.html      ← Frontend (HTML/CSS/JS)
```

---

## Local development (test on your own machine first)

### 1. Get an Anthropic API key
Sign up at https://console.anthropic.com and create an API key.

### 2. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 3. Set your API key as an environment variable
On Mac/Linux:
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```
On Windows (Command Prompt):
```cmd
set ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 4. Run the app
```bash
python app.py
```
Open http://localhost:5000 in your browser.

---

## Deploy to Render (recommended — free tier available)

1. Push this folder to a GitHub repository
   - Go to https://github.com and create a new repository
   - Upload these files (or use git push from Cursor)

2. Go to https://render.com and sign up for a free account

3. Click "New +" → "Web Service"

4. Connect your GitHub repo

5. Configure the service:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

6. Add your environment variable:
   - Go to "Environment" tab
   - Add key: `ANTHROPIC_API_KEY`
   - Value: your key from https://console.anthropic.com

7. Click "Deploy" — Render will give you a public URL like:
   `https://your-app-name.onrender.com`

---

## Deploy to Replit (easiest option)

1. Go to https://replit.com and sign up
2. Click "Create Repl" → choose "Import from GitHub" or upload files manually
3. In the Replit shell, run: `pip install -r requirements.txt`
4. Go to "Secrets" (lock icon in sidebar) and add:
   - Key: `ANTHROPIC_API_KEY`
   - Value: your key
5. Click "Run" — Replit gives you a public URL instantly

---

## API endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | / | Serves the frontend |
| POST | /api/parse-resume | Accepts a resume file, returns extracted profile JSON |
| POST | /api/match-jobs | Accepts profile JSON, returns all strong matched roles (each may include a `url` to apply) |

---

## Sharing the app

Once deployed, share the public URL with anyone — candidates, colleagues, or clients.
No login required. Each submission is independent.

---

## Costs

The app calls the Anthropic API twice per candidate:
1. Resume parsing (~500 tokens)
2. Job matching (~600 tokens)

At Claude Sonnet pricing this is roughly $0.002–0.004 per candidate.
Monitor usage at https://console.anthropic.com/usage
