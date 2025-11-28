# Windows Setup Guide

Quick setup guide for running AI Audit Backend on Windows.

## Quick Start

### 1. Initial Setup (One Time)

Run the setup script to create virtual environment and install dependencies:

```cmd
setup.bat
```

This will:
- Create a virtual environment (`venv`)
- Install all dependencies
- Create necessary directories
- Initialize the database
- Create a test user (test@example.com / test123)

### 2. Configure Environment Variables

Create a `.env` file in the project root with your API keys:

```env
# Database
DB_URL=sqlite:///var/audit.db

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# AI Platform API Keys
OPENAI_API_KEY=sk-your-key-here
GEMINI_API_KEY=your-key-here
GROQ_API_KEY=your-key-here
```

### 3. Run the Server

Double-click `run.bat` or run in command prompt:

```cmd
run.bat
```

The server will start at:
- **API Server:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs
- **Alternative Docs:** http://localhost:8000/redoc

## Available Scripts

### `setup.bat`
Initial setup script that:
- Creates virtual environment
- Installs dependencies
- Initializes database
- Creates test user

### `run.bat`
Runs the FastAPI server with auto-reload.

## Manual Setup (Alternative)

If you prefer to set up manually:

```cmd
# 1. Create virtual environment
python -m venv venv

# 2. Activate virtual environment
venv\Scripts\activate.bat

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize database
python scripts/init_db.py

# 5. Run server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Troubleshooting

### Virtual Environment Not Found
- Run `setup.bat` first to create the virtual environment

### Module Not Found Errors
- Make sure virtual environment is activated
- Run `pip install -r requirements.txt` again

### Database Errors
- Run `python scripts/init_db.py` to initialize/refresh database

### Port Already in Use
- Change the port in `run.bat`: `--port 8001` (or another port)
- Or stop the process using port 8000

### API Key Errors
- Check your `.env` file exists and has correct API keys
- Make sure `.env` file is in the project root directory

## Default Test User

After running `setup.bat`, you can use:

- **Email:** test@example.com
- **Password:** test123

## File Structure

```
AI-audit/
├── run.bat              # Run server script
├── setup.bat            # Setup script
├── .env                 # Environment variables (create this)
├── requirements.txt     # Python dependencies
├── app/                 # Application code
├── scripts/             # Utility scripts
│   └── init_db.py      # Database initialization
└── var/                 # Data directory
    └── audit.db        # SQLite database
```

## Notes

- The server runs with `--reload` flag for auto-reload on code changes
- Database is stored in `var/audit.db`
- Logs will appear in the console
- Press `Ctrl+C` to stop the server

