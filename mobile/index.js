import { registerRootComponent } from 'expo';
import { Platform } from 'react-native';
import App from './App';
import { installWebBranding } from './src/webBranding';

if (Platform.OS === 'web') installWebBranding();

registerRootComponent(App);
