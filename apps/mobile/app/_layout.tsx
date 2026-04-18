import { ClerkProvider, ClerkLoaded } from '@clerk/clerk-expo';
import { Slot } from 'expo-router';
import { tokenCache } from '../lib/tokenCache';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { queryClient, asyncStoragePersister } from '../lib/queryClient';
import { configureApiClient } from '@consensus/api-client';

const publishableKey = process.env.EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY!;

if (!publishableKey) {
  throw new Error('Missing EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY in .env');
}

// Configure shared API client for mobile
configureApiClient({
  baseUrl: process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1',
});

export default function RootLayout() {
  return (
    <ClerkProvider publishableKey={publishableKey} tokenCache={tokenCache}>
      <PersistQueryClientProvider client={queryClient} persistOptions={{ persister: asyncStoragePersister }}>
        <ClerkLoaded>
          <Slot />
        </ClerkLoaded>
      </PersistQueryClientProvider>
    </ClerkProvider>
  );
}
