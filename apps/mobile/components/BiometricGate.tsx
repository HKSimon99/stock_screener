import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import * as LocalAuthentication from 'expo-local-authentication';

export default function BiometricGate({ children }: { children: React.ReactNode }) {
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [isSupported, setIsSupported] = useState(false);

  useEffect(() => {
    checkDeviceSupport();
  }, []);

  const checkDeviceSupport = async () => {
    const compatible = await LocalAuthentication.hasHardwareAsync();
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    setIsSupported(compatible && enrolled);

    if (compatible && enrolled) {
      authenticate();
    } else {
      // IF biometrics aren't supported or enrolled, fail-open (unlock) for demo purposes
      console.warn('Biometrics not supported or enrolled on this device. Bypassing gate.');
      setIsUnlocked(true);
    }
  };

  const authenticate = async () => {
    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Unlock Consensus',
        fallbackLabel: 'Use Passcode',
        cancelLabel: 'Cancel',
      });

      if (result.success) {
        setIsUnlocked(true);
        setHasError(false);
      } else {
        setHasError(true);
      }
    } catch (e) {
      console.error(e);
      setHasError(true);
    }
  };

  if (isUnlocked) {
    return <>{children}</>;
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Consensus Secure Auth</Text>
      <Text style={styles.subtitle}>
        Verify your identity to access critical market data
      </Text>
      
      {hasError && (
        <Text style={styles.errorText}>Authentication Failed. Please try again.</Text>
      )}

      {isSupported && (
        <TouchableOpacity style={styles.button} onPress={authenticate}>
          <Text style={styles.buttonText}>Unlock App</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a', /* Dark slate */
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '900',
    color: '#fff',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#94a3b8',
    textAlign: 'center',
    marginBottom: 32,
  },
  errorText: {
    color: '#ef4444',
    marginBottom: 16,
    fontWeight: 'bold',
  },
  button: {
    backgroundColor: '#3b82f6',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
