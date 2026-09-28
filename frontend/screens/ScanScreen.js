// screens/ScanScreen.js
import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ActivityIndicator,
  SafeAreaView,
  StatusBar,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { API_BASE } from '../config';
import ResultCard from '../components/ResultCard';

export default function ScanScreen({ onBack }) {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState(false);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('Position the card barcode within the frame');
  const [result, setResult] = useState(null);
  const [errorDetail, setErrorDetail] = useState(null);
  const [torch, setTorch] = useState(false);

  if (!permission) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <ActivityIndicator size="small" color="#18181B" />
        <Text style={styles.loadingText}>Checking permissions...</Text>
      </SafeAreaView>
    );
  }

  if (!permission.granted) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <View style={styles.permissionCard}>
          <Text style={styles.permissionTitle}>Camera Access</Text>
          <Text style={styles.permissionDesc}>
            Camera permission is required to scan QR codes on identity cards.
          </Text>
          <TouchableOpacity style={styles.primaryBtn} onPress={requestPermission} activeOpacity={0.8}>
            <Text style={styles.primaryBtnText}>Allow camera access</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.backLink} onPress={onBack}>
            <Text style={styles.backLinkText}>Return to home</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const handleBarcodeScanned = async (scanResult) => {
    if (scanned || loading) return;
    setScanned(true);
    setLoading(true);
    setErrorDetail(null);
    setStatusMsg('Code detected, reading details...');

    const payload = scanResult?.data || scanResult?.raw || '';

    try {
      const res = await fetch(`${API_BASE}/api/v1/extract/qr-payload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_payload: payload }),
      });

      const json = await res.json();

      if (res.ok) {
        setResult(json);
        setStatusMsg('Extracted successfully');
      } else {
        setErrorDetail(json.detail || 'Could not parse this barcode.');
        setStatusMsg('');
      }
    } catch (err) {
      setErrorDetail(`Connection error: ${err.message}. Please verify the server is running.`);
      setStatusMsg('');
    } finally {
      setLoading(false);
    }
  };

  const resetScan = () => {
    setResult(null);
    setErrorDetail(null);
    setScanned(false);
    setStatusMsg('Position the card barcode within the frame');
  };

  // If extraction succeeded, show ResultCard
  if (result) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.topNav}>
          <TouchableOpacity style={styles.navActionBtn} onPress={onBack}>
            <Text style={styles.navActionText}>&larr; Home</Text>
          </TouchableOpacity>
          <Text style={styles.navTitle}>Result</Text>
          <TouchableOpacity style={styles.navActionBtn} onPress={resetScan}>
            <Text style={styles.navActionText}>Rescan</Text>
          </TouchableOpacity>
        </View>
        <ResultCard data={result} onReset={resetScan} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.scannerContainer}>
      <StatusBar barStyle="light-content" backgroundColor="#000000" />

      {/* Top Header */}
      <View style={styles.scannerHeader}>
        <TouchableOpacity style={styles.scannerHeaderBtn} onPress={onBack}>
          <Text style={styles.scannerHeaderBtnText}>&larr; Back</Text>
        </TouchableOpacity>
        <Text style={styles.scannerHeaderTitle}>Scan Code</Text>
        <TouchableOpacity
          style={[styles.torchBtn, torch && styles.torchBtnActive]}
          onPress={() => setTorch(!torch)}>
          <Text style={styles.torchText}>{torch ? 'Light on' : 'Light off'}</Text>
        </TouchableOpacity>
      </View>

      {/* Camera Viewport */}
      <View style={styles.cameraWrapper}>
        <CameraView
          style={styles.camera}
          facing="back"
          enableTorch={torch}
          barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
          onBarcodeScanned={scanned ? undefined : handleBarcodeScanned}>
          {/* Viewfinder Overlay */}
          <View style={styles.overlay}>
            <View style={styles.viewfinderFrame}>
              <View style={[styles.corner, styles.topLeft]} />
              <View style={[styles.corner, styles.topRight]} />
              <View style={[styles.corner, styles.bottomLeft]} />
              <View style={[styles.corner, styles.bottomRight]} />

              {loading && (
                <View style={styles.loaderOverlay}>
                  <ActivityIndicator size="small" color="#FFFFFF" />
                  <Text style={styles.loaderText}>Processing...</Text>
                </View>
              )}
            </View>
          </View>
        </CameraView>
      </View>

      {/* Bottom Status & Hints */}
      <View style={styles.bottomSection}>
        <View style={styles.hintContainer}>
          <Text style={styles.hintText}>{statusMsg}</Text>
        </View>

        {errorDetail && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{errorDetail}</Text>
            <TouchableOpacity style={styles.retryBtn} onPress={resetScan}>
              <Text style={styles.retryBtnText}>Try again</Text>
            </TouchableOpacity>
          </View>
        )}

        <Text style={styles.subtext}>
          Supports Aadhaar and Driving Licence barcodes
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FBFBFC',
  },
  scannerContainer: {
    flex: 1,
    backgroundColor: '#000000',
  },
  centerContainer: {
    flex: 1,
    backgroundColor: '#FBFBFC',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  loadingText: {
    marginTop: 14,
    color: '#6E6E73',
    fontSize: 14,
  },
  permissionCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#EBEBED',
    width: '100%',
  },
  permissionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1C1C1E',
    marginBottom: 8,
  },
  permissionDesc: {
    fontSize: 14,
    color: '#6E6E73',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 20,
  },
  primaryBtn: {
    backgroundColor: '#18181B',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 10,
    width: '100%',
    alignItems: 'center',
  },
  primaryBtnText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 14,
  },
  backLink: {
    marginTop: 16,
  },
  backLinkText: {
    color: '#6E6E73',
    fontSize: 13,
  },
  topNav: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#EBEBED',
  },
  navActionBtn: {
    paddingVertical: 4,
  },
  navActionText: {
    color: '#1C1C1E',
    fontWeight: '500',
    fontSize: 15,
  },
  navTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#1C1C1E',
  },
  scannerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    backgroundColor: '#000000',
  },
  scannerHeaderBtn: {
    paddingVertical: 4,
  },
  scannerHeaderBtnText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '500',
  },
  scannerHeaderTitle: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '600',
  },
  torchBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: '#27272A',
  },
  torchBtnActive: {
    backgroundColor: '#3F3F46',
  },
  torchText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '500',
  },
  cameraWrapper: {
    flex: 1,
    backgroundColor: '#000000',
    overflow: 'hidden',
  },
  camera: {
    flex: 1,
  },
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.4)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  viewfinderFrame: {
    width: 240,
    height: 240,
    borderRadius: 16,
    position: 'relative',
    justifyContent: 'center',
    alignItems: 'center',
  },
  corner: {
    position: 'absolute',
    width: 24,
    height: 24,
    borderColor: '#FFFFFF',
  },
  topLeft: {
    top: 0,
    left: 0,
    borderTopWidth: 3,
    borderLeftWidth: 3,
    borderTopLeftRadius: 12,
  },
  topRight: {
    top: 0,
    right: 0,
    borderTopWidth: 3,
    borderRightWidth: 3,
    borderTopRightRadius: 12,
  },
  bottomLeft: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 3,
    borderLeftWidth: 3,
    borderBottomLeftRadius: 12,
  },
  bottomRight: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 3,
    borderRightWidth: 3,
    borderBottomRightRadius: 12,
  },
  loaderOverlay: {
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 12,
    alignItems: 'center',
  },
  loaderText: {
    color: '#FFFFFF',
    marginTop: 8,
    fontSize: 13,
    fontWeight: '500',
  },
  bottomSection: {
    backgroundColor: '#000000',
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 28,
    alignItems: 'center',
  },
  hintContainer: {
    paddingVertical: 6,
    alignItems: 'center',
  },
  hintText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#A1A1AA',
    textAlign: 'center',
  },
  errorBox: {
    backgroundColor: '#27272A',
    borderRadius: 12,
    padding: 12,
    marginTop: 10,
    width: '100%',
    alignItems: 'center',
  },
  errorText: {
    color: '#F87171',
    fontSize: 13,
    textAlign: 'center',
    marginBottom: 8,
  },
  retryBtn: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 6,
    backgroundColor: '#3F3F46',
  },
  retryBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '500',
  },
  subtext: {
    fontSize: 12,
    color: '#71717A',
    textAlign: 'center',
    marginTop: 10,
  },
});
