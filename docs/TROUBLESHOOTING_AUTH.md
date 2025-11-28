# Troubleshooting Authentication Issues

## Common 401 Unauthorized Errors

### 1. Token Expired

**Error:** `401 Unauthorized - Could not validate credentials`

**Cause:** JWT access tokens expire after 30 minutes by default.

**Solution:**
```bash
# Get a new token by logging in again
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "password": "your-password"
  }'
```

**Or use the refresh token:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refreshToken": "your-refresh-token-here"
  }'
```

### 2. JWT Secret Key Mismatch

**Error:** `401 Unauthorized - Could not validate credentials`

**Cause:** The token was signed with a different secret key than what the server is using.

**Solution:**
1. Check your `.env` file has `JWT_SECRET_KEY` set
2. Make sure you're using the same secret key that was used to sign the token
3. If you changed the secret key, you need to log in again to get a new token

### 3. User Not Found in Database

**Error:** `401 Unauthorized - Could not validate credentials`

**Cause:** The user ID in the token doesn't exist in the database (e.g., database was reset).

**Solution:**
1. Check if the user exists in the database
2. If not, register a new user or recreate the test user:
   ```bash
   python scripts/init_db.py
   ```
3. Log in again to get a new token

### 4. User Account Inactive

**Error:** `403 Forbidden - User account is inactive`

**Cause:** The user account is marked as inactive in the database.

**Solution:**
- Check the user's `is_active` field in the database
- Set it to `true` if needed

## Debugging Steps

### 1. Check Token Expiration

Decode your token to see when it expires:

```python
import jwt
token = "your-token-here"
payload = jwt.decode(token, options={"verify_signature": False})
print(f"Expires at: {payload.get('exp')}")
print(f"User ID: {payload.get('sub')}")
```

### 2. Verify JWT Secret Key

Make sure your `.env` file has:
```env
JWT_SECRET_KEY=your-secret-key-change-in-production
```

### 3. Check Server Logs

Look for authentication errors in your server logs:
- Token validation failures
- User lookup failures
- Database connection issues

### 4. Test Authentication Flow

1. **Login:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "password": "test123"}'
   ```

2. **Use the token:**
   ```bash
   curl -X GET http://localhost:8000/api/v1/auth/me \
     -H "Authorization: Bearer YOUR_TOKEN_HERE"
   ```

3. **If that works, try your comparison endpoint**

## Quick Fix

The quickest solution is usually to **get a fresh token**:

```bash
# 1. Login to get a new token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test123"}' \
  | jq -r '.data.token')

# 2. Use the new token
curl -X GET http://localhost:8000/api/v1/comparison/comp_957de8857311/status \
  -H "Authorization: Bearer $TOKEN"
```

## Default Settings

- **Access Token Expiration:** 30 minutes
- **Refresh Token Expiration:** 7 days
- **Algorithm:** HS256
- **Default Secret:** `your-secret-key-change-in-production` (⚠️ change in production!)

## Environment Variables

Make sure these are set in your `.env` file:

```env
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

