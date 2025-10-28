# Supabase Configuration Guide

This guide will help you set up the Supabase connection for the mobile-signature-expo application.

## Prerequisites

- A Supabase account (sign up at https://supabase.com)
- A Supabase project created

## Getting Your Supabase Credentials

### Step 1: Access Your Supabase Project

1. Log in to your Supabase dashboard at https://app.supabase.com
2. Select your project (or create a new one)

### Step 2: Find Your API Credentials

1. In your project dashboard, click on the **Settings** icon (gear icon) in the sidebar
2. Navigate to **Project Settings** > **API**
3. You will find two important values:
   - **Project URL**: This is your Supabase URL (e.g., `https://xyzcompany.supabase.co`)
   - **anon public**: This is your anonymous/public API key

### Step 3: Configure Your Environment File

1. Copy the `.env.example` file to create your `.env` file:
   ```bash
   cp .env.example .env
   ```

2. Open the `.env` file in a text editor

3. Replace the placeholder values with your actual credentials:
   ```env
   EXPO_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
   EXPO_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

4. Save the file

## Verification

To verify your Supabase connection is working:

1. Start the development server:
   ```bash
   npm start
   ```

2. Open the app on your device or emulator

3. Try logging in with a test user (make sure you have users created in Supabase Authentication)

## Supabase Client Configuration

The Supabase client is already configured in `src/lib/supabase.js` with:

- **AsyncStorage**: For persistent sessions across app restarts
- **Auto Refresh Token**: Automatically refreshes authentication tokens
- **Persist Session**: Keeps users logged in

## Important Security Notes

- **NEVER** commit your `.env` file to version control
- The `.env` file is already added to `.gitignore` to prevent accidental commits
- Keep your Supabase API keys secure and private
- Use the **anon/public** key (not the service_role key) for client-side applications

## Environment Variables Explained

### EXPO_PUBLIC_SUPABASE_URL
- This is your Supabase project URL
- Format: `https://[project-id].supabase.co`
- Found in: Project Settings > API > Project URL

### EXPO_PUBLIC_SUPABASE_ANON_KEY
- This is your anonymous/public API key
- It's safe to use in client-side applications
- Found in: Project Settings > API > anon public
- This key respects Row Level Security (RLS) policies

## Troubleshooting

### Connection Issues

If you're having trouble connecting to Supabase:

1. Verify your credentials are correct (no extra spaces or quotes)
2. Check that your Supabase project is active and running
3. Ensure you have an active internet connection
4. Check the Expo console for specific error messages

### Authentication Issues

If authentication is not working:

1. Verify you have enabled Email authentication in Supabase:
   - Go to Authentication > Providers
   - Enable Email provider
2. Create a test user in Authentication > Users
3. Check that your RLS policies allow the operations you need

## Next Steps

After configuring Supabase:

1. Set up your database tables and views (see README.md for schema)
2. Configure Row Level Security policies
3. Create test users for development
4. Start building your app features

## Additional Resources

- [Supabase Documentation](https://supabase.com/docs)
- [Supabase JavaScript Client](https://supabase.com/docs/reference/javascript)
- [Expo Environment Variables](https://docs.expo.dev/guides/environment-variables/)