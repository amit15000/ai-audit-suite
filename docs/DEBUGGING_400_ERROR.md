# Debugging 400 Bad Request Errors

If you're seeing a `400 Bad Request` error when trying to register a user, follow these steps to diagnose and fix the issue.

## Quick Diagnosis Steps

### 1. Check the Error Response

In your browser's developer tools:
1. Open the **Network** tab
2. Click on the failed `register` request
3. Go to the **Response** tab to see the actual error message

The error response will look like:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format: email"
  }
}
```

### 2. Common Causes and Solutions

#### A. Validation Errors

**Invalid Email Format**
- **Error**: `Invalid email format: email`
- **Solution**: Ensure the email is in valid format (e.g., `user@example.com`)

**Password Too Short**
- **Error**: `Password must be at least 6 characters long`
- **Solution**: Use a password with at least 6 characters

**Missing Required Fields**
- **Error**: `Missing required field: email` or `Missing required field: password`
- **Solution**: Ensure your request includes both `email` and `password` fields

#### B. User Already Exists

**Error**: 
```json
{
  "success": false,
  "error": {
    "code": "USER_ALREADY_EXISTS",
    "message": "A user with this email already exists"
  }
}
```

**Solution**: Use a different email address or delete the existing user from the database.

#### C. Database Connection Issues

If you see database-related errors (usually 500, but can sometimes appear as 400):

1. **Check Docker is running:**
   ```bash
   docker-compose ps
   ```

2. **Start Docker services:**
   ```bash
   docker-compose up -d
   ```

3. **Verify database connection:**
   ```bash
   python scripts/test_db_connection.py
   ```

4. **Check health endpoint:**
   ```bash
   curl http://localhost:8001/health
   ```
   Or visit: http://localhost:8001/health

5. **Initialize database if needed:**
   ```bash
   python scripts/init_db.py
   ```

## Testing the Registration Endpoint

### Using the Test Script

Run the provided test script to diagnose issues:

```bash
python scripts/test_register_endpoint.py
```

This will test:
- Valid registration
- Invalid email format
- Short password
- Missing fields

### Using curl

Test with a valid request:
```bash
curl -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123",
    "name": "Test User"
  }'
```

Test with invalid email:
```bash
curl -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "invalid-email",
    "password": "test123"
  }'
```

### Using the API Docs

1. Visit http://localhost:8001/docs
2. Find the `/api/v1/auth/register` endpoint
3. Click "Try it out"
4. Fill in the form and see the response

## Request Format

The registration endpoint expects:

```json
{
  "email": "user@example.com",    // Required, must be valid email
  "password": "password123",       // Required, minimum 6 characters
  "name": "User Name"              // Optional
}
```

## Environment Setup Checklist

Ensure your environment is properly configured:

- [ ] Docker services are running (`docker-compose ps`)
- [ ] `.env` file exists with `DB_URL` set to local Docker:
  ```env
  DB_URL=postgresql://audit_user:audit_password@localhost:5432/audit_db
  ```
- [ ] Database is initialized (`python scripts/init_db.py`)
- [ ] Server is running on port 8001 (`uvicorn app.main:app --reload --port 8001`)
- [ ] Health check passes (`curl http://localhost:8001/health`)

## Server Logs

Check your server logs for detailed error information. The server should log:
- Validation errors
- Database connection issues
- Any other exceptions

Look for lines like:
```
{"error": "...", "event": "auth.register.error"}
```

## Still Having Issues?

1. **Check server logs** for detailed error messages
2. **Verify your `.env` file** has the correct `DB_URL`
3. **Test database connection** with `python scripts/test_db_connection.py`
4. **Check the health endpoint** at http://localhost:8001/health
5. **Try the test script** `python scripts/test_register_endpoint.py`

If the issue persists, share:
- The error response from the Response tab
- Server logs
- Output of `python scripts/test_db_connection.py`
- Output of `curl http://localhost:8001/health`
