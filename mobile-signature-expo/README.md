# JMax Contract Signature - Mobile App (Expo)

This is a React Native mobile application built with Expo for PKWT contract digital signatures.

## Features

- User authentication with Supabase
- Contract viewing and information display
- Digital signature capture
- Signature submission and storage
- User session management

## Prerequisites

- Node.js (v16 or higher)
- npm or yarn
- Expo Go app installed on your mobile device (for testing)
- Supabase account with configured authentication

## Setup

1. **Install Dependencies**
   ```bash
   npm install
   ```

2. **Configure Environment Variables**

   Copy `.env.example` to `.env` and fill in your Supabase credentials:
   ```bash
   cp .env.example .env
   ```

   Edit `.env`:
   ```
   EXPO_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
   EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
   ```

3. **Start the Development Server**
   ```bash
   npm start
   ```

4. **Run on Device**
   - Scan the QR code with Expo Go app on iOS or Android
   - Or press `a` for Android emulator
   - Or press `i` for iOS simulator

## Database Schema

The app interacts with the following Supabase views and tables:

### Views
- `new_authenticated_list_contract` - Contract information linked to user UIDs
- `new_authenticated_pdf_contract` - Contract PDF data

### Tables
- `contract_signatures` - Stores signature data
  - uid (uuid)
  - contract_num_detail (varchar)
  - signature_svg (text)
  - signature_png (text)
  - signed_pdf (bytea)
  - signed_at (timestamp)
  - signer_name (varchar)

## Project Structure

```
mobile-signature-expo/
├── src/
│   ├── screens/
│   │   ├── LoginScreen.js       # Login/authentication screen
│   │   ├── NoContractScreen.js  # No contract available screen
│   │   └── SignatureScreen.js   # Main signature capture screen
│   ├── navigation/
│   │   └── AppNavigator.js      # React Navigation configuration
│   └── lib/
│       └── supabase.js          # Supabase client configuration
├── App.js                       # Main app component
├── app.json                     # Expo configuration
├── package.json                 # Dependencies
└── README.md                    # This file
```

## Screens

### Login Screen
- Email and password authentication
- Input validation
- Error handling
- Auto-redirect if already authenticated

### No Contract Screen
- Displayed when user has no assigned contract
- Sign out functionality

### Signature Screen
- Contract information display
- Digital signature canvas
- Signature submission
- Clear and save functionality

## Authentication Flow

1. User enters email and password
2. Supabase authenticates the user
3. Check user metadata for `contract_md5`
4. If contract exists, navigate to Signature screen
5. If no contract, navigate to NoContract screen

## Signature Flow

1. Load contract data from `new_authenticated_list_contract` view
2. Display contract information
3. User draws signature on canvas
4. On submit, save to `contract_signatures` table
5. Sign out user after successful submission

## Backend API

The app connects to the FastAPI backend at `http://127.0.0.1:8000` (configurable) and uses Supabase for:
- User authentication
- Contract data retrieval
- Signature storage

## Database Connection

PostgreSQL connection via Supabase:
```
postgresql://neondb_owner:npg_3uDE5TZcNksJ@ep-plain-sky-a11d4k0g-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

## Technologies Used

- **React Native** - Mobile framework
- **Expo** - Development and build tooling
- **React Navigation** - Navigation library
- **Supabase** - Authentication and database
- **AsyncStorage** - Local session storage
- **react-native-signature-canvas** - Signature capture
- **React Native SVG** - Vector graphics support

## Development Notes

- The app uses React Navigation Stack Navigator
- Sessions are persisted using AsyncStorage
- Signature data is currently stored as SVG strings
- PDF generation for signed contracts is pending implementation
- The app is configured for both iOS and Android

## Building for Production

### Android
```bash
eas build --platform android
```

### iOS
```bash
eas build --platform ios
```

Note: Requires Expo Application Services (EAS) account and configuration.

## License

Private - JMax Internal Use Only
