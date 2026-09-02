import { registerRootComponent } from 'expo';
import { Platform, View } from 'react-native';
import { useCallback, useState } from 'react';
import App from './App';
import SecurityTrustBar from './components/SecurityTrustBar';
import WebIntro from './components/WebIntro';
import { installWebBranding } from './src/webBranding';

if (Platform.OS === 'web') installWebBranding();

function RootApp() {
  const [intro, setIntro] = useState(Platform.OS === 'web');
  const finishIntro = useCallback(() => setIntro(false), []);
  if (Platform.OS !== 'web') return <App />;
  return <View style={{ flex: 1, minHeight: 0, backgroundColor: '#07111C' }}>
    <View style={{ flex: 1, minHeight: 0 }}><App /></View>
    <SecurityTrustBar />
    {intro ? <WebIntro onComplete={finishIntro} /> : null}
  </View>;
}

registerRootComponent(RootApp);
