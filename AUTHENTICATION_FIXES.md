# Authentication Fixes - Summary

## Issues Fixed

### 1. ✅ User Accounts Not Being Saved
**Problem:** Users had to create new accounts every time  
**Fix:** 
- Added proper transaction handling with rollback on errors
- Configured support for Supabase PostgreSQL database
- Ensured database commits are properly executed

### 2. ✅ Cookies Not Working for 1 Month
**Problem:** Authentication tokens weren't stored in cookies  
**Fix:**
- Added HTTP-only cookie support for both `access_token` and `refresh_token`
- Cookies are set with 30-day expiration (1 month)
- Cookies are set in login, register, and refresh token endpoints
- Updated authentication dependency to support both Bearer tokens and cookies

### 3. ✅ Token Expiration Updated
**Problem:** Refresh tokens only lasted 7 days  
**Fix:**
- Changed `JWT_REFRESH_TOKEN_EXPIRE_DAYS` from 7 to 30 days (1 month)
- Access tokens still expire in 30 minutes (security best practice)
- Refresh tokens now last 30 days

### 4. ✅ Database Configuration for Supabase
**Problem:** Database was using SQLite, data wasn't persisting properly  
**Fix:**
- Added support for Supabase PostgreSQL connection
- Configured environment variable `SUPABASE_DB_URL`
- Database will use Supabase when configured, otherwise falls back to SQLite

## Environment Variables Required

Add these to your `.env` file:

### Required for Supabase Database:

```env
# Supabase PostgreSQL Connection URL
# Format: postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
SUPABASE_DB_URL=postgresql://postgres:YOUR_DATABASE_PASSWORD@db.vmlerkejbnjydkmyqlrk.supabase.co:5432/postgres
```

**How to get your database password:**
1. Go to Supabase Dashboard → Your Project
2. Settings → Database
3. Copy the database password (or reset if needed)
4. Replace `YOUR_DATABASE_PASSWORD` in the connection string

### Optional (for Supabase API):

```env
# Supabase Project URL
SUPABASE_URL=https://vmlerkejbnjydkmyqlrk.supabase.co

# Supabase Anon/Public Key
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXE...[your full key]
```

### Optional (JWT Settings - defaults are fine):

```env
# Change this in production!
JWT_SECRET_KEY=your-secret-key-change-in-production

# Access token expiration (default: 30 minutes)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Refresh token expiration (default: 30 days = 1 month)
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
```

## Cookie Configuration

Cookies are now set with these attributes:
- **HttpOnly:** `true` (prevents JavaScript access, security)
- **Max Age:** `2592000` seconds (30 days)
- **SameSite:** `lax` (CSRF protection)
- **Secure:** `false` (set to `true` in production with HTTPS)
- **Path:** `/` (available site-wide)

## Authentication Methods Supported

The API now supports authentication via:

1. **Bearer Token** (Authorization header):
   ```
   Authorization: Bearer <token>
   ```

2. **HTTP-Only Cookies** (automatically set on login/register):
   - Cookie: `access_token`
   - Cookie: `refresh_token`

Both methods work interchangeably. The dependency checks Bearer token first, then falls back to cookies.

## Performance Notes

If login/register is still slow, possible causes:

1. **Database Connection:** First connection to Supabase might be slow. Connection pooling is enabled.
2. **Password Hashing:** Bcrypt is intentionally slow (security feature). This is normal.
3. **Network Latency:** If connecting to Supabase from a slow network.

## Next Steps

1. **Add environment variables** to your `.env` file (especially `SUPABASE_DB_URL`)
2. **Initialize database tables:**
   ```bash
   python scripts/init_db.py
   ```
3. **Restart your server** to apply changes
4. **Test registration/login** - users should now persist in Supabase

## Testing

After setup, test:

1. **Register a new user** - should create account in Supabase
2. **Check cookies** - should see `access_token` and `refresh_token` cookies set
3. **Login** - should work with existing account
4. **Refresh token** - should work after 30 minutes when access token expires
5. **User persistence** - create account, restart server, login should still work

## Troubleshooting

### Users still not saving?
- Check `SUPABASE_DB_URL` is set correctly
- Verify database password is correct
- Run `python scripts/init_db.py` to create tables
- Check server logs for database errors

### Cookies not working?
- Check browser developer tools → Application → Cookies
- Ensure frontend is on same domain (or configure CORS properly)
- For production, set `secure=True` in cookie settings (requires HTTPS)

### Slow performance?
- Check Supabase connection from your server location
- Verify database connection pooling is working
- Check server logs for slow queries

