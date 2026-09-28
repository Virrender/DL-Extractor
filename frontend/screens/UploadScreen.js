// screens/UploadScreen.js
import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ScrollView,
  Image,
  ActivityIndicator,
  SafeAreaView,
  Alert,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { API_BASE } from '../config';
import ResultCard from '../components/ResultCard';
import { uploadMultipart, CustomFormData } from '../utils/uploader';

export default function UploadScreen({ onBack }) {
  const [frontUri, setFrontUri] = useState(null);
  const [backUri, setBackUri] = useState(null);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [result, setResult] = useState(null);
  const [errorDetail, setErrorDetail] = useState(null);

  // Pick from gallery with permissions check
  const pickFromGallery = async (setter) => {
    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission needed', 'Please grant photos access in your settings to pick documents.');
        return;
      }
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        quality: 0.75,
      });
      if (!res.canceled && res.assets && res.assets.length > 0) {
        setter(res.assets[0].uri);
        setErrorDetail(null);
      }
    } catch (e) {
      Alert.alert('Error picking image', e.message);
    }
  };

  // Capture with camera with permissions check
  const captureFromCamera = async (setter) => {
    try {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission needed', 'Please grant camera access in your settings to capture documents.');
        return;
      }
      const res = await ImagePicker.launchCameraAsync({
        mediaTypes: ['images'],
        quality: 0.75,
      });
      if (!res.canceled && res.assets && res.assets.length > 0) {
        setter(res.assets[0].uri);
        setErrorDetail(null);
      }
    } catch (e) {
      Alert.alert('Error taking photo', e.message);
    }
  };

  const submit = async () => {
    if (!frontUri) {
      setErrorDetail('Front image is required to begin extraction.');
      return;
    }

    setLoading(true);
    setStatusMsg('Processing document...');
    setErrorDetail(null);

    // Build multipart FormData with CustomFormData to format parts correctly
    const formData = new CustomFormData();
    const frontFilename = frontUri.split('/').pop() || 'front.jpg';
    const frontMime = frontFilename.toLowerCase().endsWith('.png') ? 'image/png' : 'image/jpeg';

    formData.append('front_image', {
      uri: frontUri,
      name: frontFilename,
      type: frontMime,
    });

    // Back image is strictly optional: only append if selected
    if (backUri) {
      const backFilename = backUri.split('/').pop() || 'back.jpg';
      const backMime = backFilename.toLowerCase().endsWith('.png') ? 'image/png' : 'image/jpeg';
      formData.append('back_image', {
        uri: backUri,
        name: backFilename,
        type: backMime,
      });
    }

    try {
      const res = await uploadMultipart(`${API_BASE}/api/v1/extract`, formData);

      if (res.ok) {
        setResult(res.data);
        setStatusMsg('Extracted successfully');
      } else {
        const detail = res.data && res.data.detail;
        const msg = detail
          ? (typeof detail === 'string' ? detail : JSON.stringify(detail))
          : 'Extraction failed.';
        setErrorDetail(msg);
        setStatusMsg('');
      }
    } catch (err) {
      setErrorDetail(`Connection error: ${err.message}. Please verify the server is running at ${API_BASE}`);
      setStatusMsg('');
    } finally {
      setLoading(false);
    }
  };

  const resetAll = () => {
    setFrontUri(null);
    setBackUri(null);
    setResult(null);
    setErrorDetail(null);
    setStatusMsg('');
  };

  // Show ResultCard on success
  if (result) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.topNav}>
          <TouchableOpacity style={styles.navActionBtn} onPress={onBack}>
            <Text style={styles.navActionText}>&larr; Home</Text>
          </TouchableOpacity>
          <Text style={styles.navTitle}>Result</Text>
          <TouchableOpacity style={styles.navActionBtn} onPress={resetAll}>
            <Text style={styles.navActionText}>New</Text>
          </TouchableOpacity>
        </View>
        <ResultCard data={result} onReset={resetAll} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.topNav}>
        <TouchableOpacity style={styles.navActionBtn} onPress={onBack}>
          <Text style={styles.navActionText}>&larr; Back</Text>
        </TouchableOpacity>
        <Text style={styles.navTitle}>Upload</Text>
        <View style={{ width: 48 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Intro */}
        <View style={styles.introBox}>
          <Text style={styles.introTitle}>Document Photos</Text>
          <Text style={styles.introSubtitle}>
            Add a clear photo of the front side. The back side is optional.
          </Text>
        </View>

        {/* 1. Front Side Card (Required) */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.sideTitle}>Front side</Text>
            <View style={styles.badgeRequired}>
              <Text style={styles.badgeText}>Required</Text>
            </View>
          </View>
          <Text style={styles.cardHint}>Includes ID number, name, DOB, and portrait.</Text>

          {frontUri ? (
            <View style={styles.previewContainer}>
              <Image source={{ uri: frontUri }} style={styles.previewImage} />
              <TouchableOpacity style={styles.removeBtn} onPress={() => setFrontUri(null)}>
                <Text style={styles.removeBtnText}>Remove photo</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.buttonRow}>
              <TouchableOpacity
                style={styles.actionBtn}
                onPress={() => pickFromGallery(setFrontUri)}>
                <Text style={styles.btnText}>Choose from library</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.actionBtn}
                onPress={() => captureFromCamera(setFrontUri)}>
                <Text style={styles.btnText}>Take photo</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* 2. Back Side Card (Optional) */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.sideTitle}>Back side</Text>
            <View style={styles.badgeOptional}>
              <Text style={styles.badgeText}>Optional</Text>
            </View>
          </View>
          <Text style={styles.cardHint}>Includes residential address and postal code.</Text>

          {backUri ? (
            <View style={styles.previewContainer}>
              <Image source={{ uri: backUri }} style={styles.previewImage} />
              <TouchableOpacity style={styles.removeBtn} onPress={() => setBackUri(null)}>
                <Text style={styles.removeBtnText}>Remove photo</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.buttonRow}>
              <TouchableOpacity
                style={styles.actionBtn}
                onPress={() => pickFromGallery(setBackUri)}>
                <Text style={styles.btnText}>Choose from library</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.actionBtn}
                onPress={() => captureFromCamera(setBackUri)}>
                <Text style={styles.btnText}>Take photo</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Error Callout */}
        {errorDetail && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{errorDetail}</Text>
          </View>
        )}

        {/* Status Callout */}
        {statusMsg !== '' && !errorDetail && (
          <View style={styles.statusBox}>
            <Text style={styles.statusBoxText}>{statusMsg}</Text>
          </View>
        )}

        {/* Submit Primary Button */}
        <TouchableOpacity
          style={[styles.submitBtn, (!frontUri || loading) && styles.submitBtnDisabled]}
          onPress={submit}
          disabled={!frontUri || loading}
          activeOpacity={0.8}>
          {loading ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator size="small" color="#FFFFFF" />
              <Text style={styles.submitBtnText}>  Extracting details...</Text>
            </View>
          ) : (
            <Text style={styles.submitBtnText}>Extract Details</Text>
          )}
        </TouchableOpacity>

        <Text style={styles.privacyNote}>
          Processed locally on your server &bull; Not shared with external services
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F0F4F8',
  },
  topNav: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  navActionBtn: {
    paddingVertical: 4,
  },
  navActionText: {
    color: '#0F172A',
    fontWeight: '500',
    fontSize: 15,
  },
  navTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#0F172A',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 40,
  },
  introBox: {
    marginBottom: 20,
  },
  introTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: '#0F172A',
    letterSpacing: -0.4,
  },
  introSubtitle: {
    fontSize: 14,
    color: '#64748B',
    marginTop: 4,
    lineHeight: 20,
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 18,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  sideTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#0F172A',
  },
  badgeRequired: {
    backgroundColor: '#E0F2FE',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  badgeOptional: {
    backgroundColor: '#F1F5F9',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#0369A1',
  },
  cardHint: {
    fontSize: 13,
    color: '#64748B',
    marginBottom: 16,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 10,
  },
  actionBtn: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#F1F5F9',
  },
  btnText: {
    fontSize: 13,
    fontWeight: '500',
    color: '#0F172A',
  },
  previewContainer: {
    alignItems: 'center',
  },
  previewImage: {
    width: '100%',
    height: 170,
    borderRadius: 12,
    resizeMode: 'cover',
  },
  removeBtn: {
    marginTop: 10,
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  removeBtnText: {
    color: '#DC2626',
    fontSize: 13,
    fontWeight: '500',
  },
  errorBox: {
    backgroundColor: '#FEF2F2',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#FEE2E2',
  },
  errorText: {
    color: '#B91C1C',
    fontSize: 13,
    lineHeight: 18,
  },
  statusBox: {
    backgroundColor: '#F1F5F9',
    borderRadius: 12,
    padding: 12,
    marginBottom: 16,
    alignItems: 'center',
  },
  statusBoxText: {
    color: '#475569',
    fontSize: 13,
  },
  submitBtn: {
    backgroundColor: '#0F172A',
    borderRadius: 12,
    paddingVertical: 15,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 6,
  },
  submitBtnDisabled: {
    backgroundColor: '#CBD5E1',
  },
  submitBtnText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 15,
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  privacyNote: {
    fontSize: 12,
    color: '#94A3B8',
    textAlign: 'center',
    marginTop: 20,
    lineHeight: 16,
  },
});
