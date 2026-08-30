import React from 'react';
import { View } from 'react-native';
import AppBase from './AppBase';
import AccountPrivacyControls from './components/AccountPrivacyControls';

function App(){
  return <View style={{flex:1}}><AppBase/><AccountPrivacyControls/></View>;
}

export default App;
