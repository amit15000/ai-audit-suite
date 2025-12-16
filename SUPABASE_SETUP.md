# Supabase Database Configuration

## Environment Variables Required

Based on your Supabase project, add these environment variables to your `.env` file:

### 1. Supabase Database Connection URL

**Variable Name:** `SUPABASE_DB_URL`

**Format:**
```
SUPABASE_DB_URL=postgresql://postgres:[YOUR_DATABASE_PASSWORD]@db.vmlerkejbnjydkmyqlrk.supabase.co:5432/postgres
```

**How to get your database password:**
1. Go to your Supabase project dashboard
2. Navigate to **Settings** → **Database**
3. Look for the **Database password** section
4. Copy the password (or reset it if needed)

**Your Project Reference:** `vmlerkejbnjydkmyqlrk` (extracted from your URL)

### 2. Supabase API Settings (Optional - for future use)

**Variable Names:**
- `SUPABASE_URL` or `SUPABASE_PROJECT_URL`
- `SUPABASE_KEY` or `SUPABASE_ANON_KEY`

**Your Values:**
```
SUPABASE_URL=https://vmlerkejbnjydkmyqlrk.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXE...[your full API key]
```

### 3. JWT Token Settings (Optional - defaults already set)

**Variable Names:**
- `JWT_SECRET_KEY` - Secret key for signing tokens (change in production!)
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` - Access token expiration (default: 30 minutes)
- `JWT_REFRESH_TOKEN_EXPIRE_DAYS` - Refresh token expiration (default: 30 days = 1 month)

## Complete .env File Example

```env
# Database Configuration
SUPABASE_DB_URL=postgresql://postgres:YOUR_PASSWORD_HERE@db.vmlerkejbnjydkmyqlrk.supabase.co:5432/postgres

# Supabase API (Optional)
SUPABASE_URL=https://vmlerkejbnjydkmyqlrk.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXE...

# JWT Settings (Optional)
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# Other settings...
OPENAI_API_KEY=your_openai_key
# etc.
```

## After Setting Up

1. **Initialize the database tables:**
   ```bash
   python scripts/init_db.py
   ```

2. **Restart your server** for the changes to take effect

3. **Test registration/login** - users should now be saved to Supabase PostgreSQL database

## Important Notes

- The database password is different from your Supabase account password
- Make sure your Supabase project allows connections from your server IP
- The connection string format is: `postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres`
- Users will now persist in the Supabase database instead of local SQLite

