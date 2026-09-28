// App.js
import React, { useState } from 'react';
import { StyleSheet, View, SafeAreaView, StatusBar } from 'react-native';
import HomeScreen from './screens/HomeScreen';
import ScanScreen from './screens/ScanScreen';
import UploadScreen from './screens/UploadScreen';

export default function App() {
  // Navigation states: 'home' (default landing page), 'scan', 'upload'
  const [currentScreen, setCurrentScreen] = useState('home');

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="dark-content" backgroundColor="#F0F4F8" />
      <View style={styles.content}>
        {currentScreen === 'home' && (
          <HomeScreen onNavigate={(screen) => setCurrentScreen(screen)} />
        )}
        {currentScreen === 'scan' && (
          <ScanScreen onBack={() => setCurrentScreen('home')} />
        )}
        {currentScreen === 'upload' && (
          <UploadScreen onBack={() => setCurrentScreen('home')} />
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F0F4F8',
  },
  content: {
    flex: 1,
  },
});
