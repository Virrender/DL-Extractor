// screens/HomeScreen.js
import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ScrollView,
  SafeAreaView,
  StatusBar,
} from 'react-native';
import { API_BASE } from '../config';

export default function HomeScreen({ onNavigate }) {
  const [serverOnline, setServerOnline] = useState(null);

  useEffect(() => {
    let isMounted = true;
    const checkServer = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`, { method: 'GET' });
        if (isMounted) setServerOnline(res.ok);
      } catch (err) {
        if (isMounted) setServerOnline(false);
      }
    };
    checkServer();
    const interval = setInterval(checkServer, 8000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" backgroundColor="#F0F4F8" />
      <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
        {/* Connection Status Header */}
        <View style={styles.topBar}>
          <View style={styles.statusPill}>
            <View
              style={[
                styles.statusDot,
                serverOnline === true
                  ? styles.dotOnline
                  : serverOnline === false
                  ? styles.dotOffline
                  : styles.dotChecking,
              ]}
            />
            <Text style={styles.statusText}>
              {serverOnline === true
                ? 'Server connected'
                : serverOnline === false
                ? 'Server offline'
                : 'Connecting...'}
            </Text>
          </View>
        </View>

        {/* Hero Header */}
        <View style={styles.heroSection}>
          <Text style={styles.heroTitle}>Documents</Text>
          <Text style={styles.heroSubtitle}>
            Extract verified details from identity cards with local processing.
          </Text>
        </View>

        {/* Primary Action Cards */}
        <View style={styles.cardsContainer}>
          {/* Action 1: Scan QR */}
          <TouchableOpacity
            style={styles.actionCard}
            activeOpacity={0.7}
            onPress={() => onNavigate('scan')}>
            <View style={styles.actionCardContent}>
              <View style={styles.cardHeaderRow}>
                <Text style={styles.cardTitle}>Scan Barcode</Text>
                <View style={styles.miniTag}>
                  <Text style={styles.miniTagText}>Instant</Text>
                </View>
              </View>
              <Text style={styles.cardDesc}>
                Directly scan the QR code on your Aadhaar or Driving Licence for cryptographic decoding.
              </Text>
              <Text style={styles.cardAction}>Open camera &rarr;</Text>
            </View>
          </TouchableOpacity>

          {/* Action 2: Upload Documents */}
          <TouchableOpacity
            style={styles.actionCard}
            activeOpacity={0.7}
            onPress={() => onNavigate('upload')}>
            <View style={styles.actionCardContent}>
              <View style={styles.cardHeaderRow}>
                <Text style={styles.cardTitle}>Upload Photos</Text>
                <View style={styles.miniTag}>
                  <Text style={styles.miniTagText}>OCR</Text>
                </View>
              </View>
              <Text style={styles.cardDesc}>
                Select front photo and optional back side for automated layout and text extraction.
              </Text>
              <Text style={styles.cardAction}>Choose images &rarr;</Text>
            </View>
          </TouchableOpacity>
        </View>

        {/* Professional Supported Documents Overview */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Supported Documents</Text>
        </View>

        <View style={styles.overviewCard}>
          <View style={styles.overviewRow}>
            <View style={styles.overviewBullet} />
            <View style={styles.overviewTextCol}>
              <Text style={styles.overviewItemTitle}>Driving Licence</Text>
              <Text style={styles.overviewItemDesc}>
                Extracts licence number, holder name, DOB, issue & expiry dates, blood group, address, and PIN code.
              </Text>
            </View>
          </View>

          <View style={styles.overviewDivider} />

          <View style={styles.overviewRow}>
            <View style={styles.overviewBullet} />
            <View style={styles.overviewTextCol}>
              <Text style={styles.overviewItemTitle}>Aadhaar Card</Text>
              <Text style={styles.overviewItemDesc}>
                Extracts demographic data, masked Aadhaar number, guardian name, cardholder portrait, and address.
              </Text>
            </View>
          </View>
        </View>

        {/* Architecture & Pipeline Badge Row */}
        <View style={styles.metricsRow}>
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Engine</Text>
            <Text style={styles.metricValue}>PaddleOCR v3</Text>
          </View>
          <View style={styles.metricDivider} />
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Security</Text>
            <Text style={styles.metricValue}>Local Only</Text>
          </View>
          <View style={styles.metricDivider} />
          <View style={styles.metricItem}>
            <Text style={styles.metricLabel}>Format</Text>
            <Text style={styles.metricValue}>FastAPI JSON</Text>
          </View>
        </View>

        {/* Minimal Footer */}
        <View style={styles.footerSection}>
          <Text style={styles.footerText}>
            Local processing &bull; Data never leaves your network
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#F0F4F8',
  },
  container: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 40,
  },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginBottom: 20,
  },
  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 6,
  },
  dotOnline: {
    backgroundColor: '#16A34A',
  },
  dotOffline: {
    backgroundColor: '#DC2626',
  },
  dotChecking: {
    backgroundColor: '#D97706',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '500',
    color: '#64748B',
  },
  heroSection: {
    marginBottom: 24,
  },
  heroTitle: {
    fontSize: 30,
    fontWeight: '700',
    color: '#0F172A',
    letterSpacing: -0.6,
  },
  heroSubtitle: {
    fontSize: 14,
    color: '#64748B',
    lineHeight: 21,
    marginTop: 6,
  },
  cardsContainer: {
    gap: 12,
    marginBottom: 24,
  },
  actionCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  actionCardContent: {
    flexDirection: 'column',
  },
  cardHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  cardTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#0F172A',
    letterSpacing: -0.3,
  },
  miniTag: {
    backgroundColor: '#E0F2FE',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  miniTagText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#0369A1',
  },
  cardDesc: {
    fontSize: 13,
    color: '#64748B',
    lineHeight: 19,
    marginBottom: 14,
  },
  cardAction: {
    fontSize: 14,
    fontWeight: '600',
    color: '#0F172A',
  },
  sectionHeader: {
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: '#64748B',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  overviewCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 20,
  },
  overviewRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  overviewBullet: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#0284C7',
    marginTop: 6,
    marginRight: 10,
  },
  overviewTextCol: {
    flex: 1,
  },
  overviewItemTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#0F172A',
    marginBottom: 2,
  },
  overviewItemDesc: {
    fontSize: 12,
    color: '#64748B',
    lineHeight: 18,
  },
  overviewDivider: {
    height: 1,
    backgroundColor: '#F1F5F9',
    marginVertical: 12,
  },
  metricsRow: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    paddingVertical: 12,
    paddingHorizontal: 8,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    alignItems: 'center',
    justifyContent: 'space-around',
    marginBottom: 20,
  },
  metricItem: {
    alignItems: 'center',
    flex: 1,
  },
  metricLabel: {
    fontSize: 11,
    color: '#94A3B8',
    fontWeight: '500',
    marginBottom: 2,
  },
  metricValue: {
    fontSize: 12,
    fontWeight: '600',
    color: '#0F172A',
  },
  metricDivider: {
    width: 1,
    height: 20,
    backgroundColor: '#E2E8F0',
  },
  footerSection: {
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    color: '#94A3B8',
    textAlign: 'center',
  },
});
