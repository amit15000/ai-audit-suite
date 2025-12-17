# Local Development Setup Guide

This guide walks you through setting up the AI Audit platform for local development using Docker.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11 or higher
- Git

## Step 1: Start Docker Services

Start the local PostgreSQL and MinIO services:

```bash
docker-compose up -d
```

This will start:
- **PostgreSQL** (with pgvector extension) on port `5432`
- **MinIO** (S3-compatible object storage) on ports `9000` (API) and `9001` (Console)

Verify services are running:

```bash
docker-compose ps
```

## Step 2: Configure Environment Variables

Create a `.env` file in the project root:

```env
# Local Docker PostgreSQL Connection
DB_URL=postgresql://audit_user:audit_password@localhost:5432/audit_db

# Storage Configuration (MinIO)
STORAGE_S3_ENDPOINT=http://localhost:9000
STORAGE_S3_BUCKET=w-audit
STORAGE_LOCAL_ROOT=var/object_store

# API Keys (add as needed)
OPENAI_API_KEY=your-openai-api-key-here
# GROQ_API_KEY=your-groq-api-key-here
# GEMINI_API_KEY=your-gemini-api-key-here
```

### Database Connection String Format

For local Docker PostgreSQL:
```
postgresql://[username]:[password]@[host]:[port]/[database]
```

Example:
```
postgresql://audit_user:audit_password@localhost:5432/audit_db
```

## Step 3: Install Python Dependencies

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -U pip
pip install -e .
```

## Step 4: Initialize Database

Create database tables:

```bash
python scripts/init_db.py
```

This will:
- Create all necessary database tables
- Create a test user (email: `test@example.com`, password: `test123`)

## Step 5: Test Database Connection

Verify your database connection:

```bash
python scripts/test_db_connection.py
```

This diagnostic tool will:
- Test DNS resolution (for remote databases)
- Test port connectivity
- Test actual database connection
- Provide troubleshooting tips if issues are found

## Step 6: Start the Application

```bash
uvicorn app.main:app --reload
```

The API will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Step 7: Access MinIO Console (Optional)

The MinIO web console is available at:
- http://localhost:9001
- Username: `minioadmin`
- Password: `minioadmin`

## Troubleshooting

### Database Connection Issues

1. **Check if Docker services are running:**
   ```bash
   docker-compose ps
   ```

2. **Check PostgreSQL logs:**
   ```bash
   docker-compose logs postgres
   ```

3. **Test database connection:**
   ```bash
   python scripts/test_db_connection.py
   ```

4. **Verify environment variables:**
   - Ensure `.env` file exists in project root
   - Check that `DB_URL` is set correctly
   - Make sure there are no extra spaces or quotes

### Port Already in Use

If port 5432 is already in use:

1. **Change Docker Compose port mapping:**
   Edit `docker-compose.yml`:
   ```yaml
   ports:
     - "5433:5432"  # Use 5433 instead of 5432
   ```

2. **Update `.env` file:**
   ```env
   DB_URL=postgresql://audit_user:audit_password@localhost:5433/audit_db
   ```

3. **Restart services:**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Reset Database

To start fresh:

```bash
# Stop and remove containers and volumes
docker-compose down -v

# Start services again
docker-compose up -d

# Reinitialize database
python scripts/init_db.py
```

## Switching Between Local and Supabase

The application prioritizes `DB_URL` over `SUPABASE_DB_URL`. To switch:

**Use Local Docker:**
```env
DB_URL=postgresql://audit_user:audit_password@localhost:5432/audit_db
# Comment out or remove SUPABASE_DB_URL
```

**Use Supabase:**
```env
# Comment out or remove DB_URL
SUPABASE_DB_URL=postgresql://postgres:password@host:5432/postgres
```

## Next Steps

- Read the [API Routes Guide](API_ROUTES_GUIDE.md)
- Check the [Architecture Documentation](architecture.md)
- Review [Troubleshooting Auth](TROUBLESHOOTING_AUTH.md)
