# Quick Start Guide

## Run the App Now

1. **Set up environment variables** (if you have Supabase credentials):
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase URL and key
   ```

2. **Start the development server**:
   ```bash
   cd mobile-signature-expo
   npm start
   ```

3. **Open on your device**:
   - Install **Expo Go** app from App Store (iOS) or Play Store (Android)
   - Scan the QR code that appears in the terminal
   - The app will load on your device

## Alternative: Run in Simulator/Emulator

### Android
```bash
npm run android
```
Requires Android Studio and Android SDK

### iOS (Mac only)
```bash
npm run ios
```
Requires Xcode

## Features to Test

1. **Login Screen**: Enter email and password to authenticate
2. **Contract View**: See contract details for authenticated users
3. **Signature**: Draw and submit digital signature
4. **Sign Out**: Clear session and return to login

## Troubleshooting

### "Supabase URL not configured"
- Make sure you created `.env` file from `.env.example`
- Add your actual Supabase credentials

### "Cannot connect to Metro bundler"
- Make sure port 8081 is not in use
- Restart with `npm start -- --clear`

### "Module not found"
- Run `npm install` again
- Clear cache: `npm start -- --clear`

## Database Access

The app connects to:
- **Authentication**: Supabase Auth
- **Contract Data**: `new_authenticated_list_contract` view
- **Signatures**: `contract_signatures` table

Make sure your Supabase instance has these configured properly.

## Next Steps

1. Test the authentication flow
2. Verify contract data loading
3. Test signature capture and submission
4. Build for production using EAS Build
