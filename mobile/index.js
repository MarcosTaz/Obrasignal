import { registerRootComponent } from 'expo';
import { Platform, View } from 'react-native';
import App from './App';
import SecurityTrustBar from './components/SecurityTrustBar';
import { installWebBranding } from './src/webBranding';

if (Platform.OS === 'web') installWebBranding();

function RootApp() {
  if (Platform.OS !== 'web') return <App />;
  return <View style={{ flex: 1, minHeight: 0, backgroundColor: '#07111C' }}>
    <View style={{ flex: 1, minHeight: 0 }}><App /></View>
    <SecurityTrustBar />
  </View>;
}

registerRootComponent(RootApp);
