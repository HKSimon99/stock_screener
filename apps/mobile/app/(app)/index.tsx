import { Redirect } from 'expo-router';

export default function Index() {
  // Redirect to the rankings page when hitting the app root
  return <Redirect href="/(app)/rankings" />;
}
