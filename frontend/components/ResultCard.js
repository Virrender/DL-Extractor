// components/ResultCard.js
import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  Image,
  TouchableOpacity,
  ScrollView,
  Share,
} from 'react-native';

export default function ResultCard({ data, onReset }) {
  const [copied, setCopied] = useState(false);

  if (!data) return null;

  const docType = data.document_type || 'unknown';
  const source = data.extraction_source || 'ocr';
  const result = data.result || {};
  const status = result.status || 'success';
  const front = result.front || {};
  const back = result.back || {};
  const photoB64 = data.photo_base64 || result.photo_base64;
  const warnings = data.warnings || result.warnings || [];

  // Title formatting
  const isDL = docType === 'driving_licence';
  const isAadhaar = docType === 'aadhaar_card';
  const docTitle = isDL ? 'Driving Licence' : isAadhaar ? 'Aadhaar Card' : 'Identity Document';

  // Subdued source tag
  const sourceLabel =
    source === 'qr'
      ? 'Barcode verified'
      : source === 'ocr+qr'
      ? 'Optical OCR'
      : 'Optical OCR';

  // Helper to get field value
  const getVal = (field) => {
    if (!field) return null;
    if (typeof field === 'string') return field;
    return field.value || null;
  };

  // Extract structured fields
  const fields = [];

  // Cardholder Name
  const name = getVal(front.name);
  if (name) fields.push({ label: 'Full name', value: name });

  // ID / Aadhaar Number
  const idNo = getVal(front.id_number) || getVal(front.aadhaar_number);
  if (idNo) {
    fields.push({
      label: isDL ? 'Licence number' : 'Aadhaar number',
      value: idNo,
      highlight: true,
    });
  }

  // DOB
  const dob = getVal(front.dob);
  if (dob) fields.push({ label: 'Date of birth', value: dob });

  // Gender
  const gender = getVal(front.gender);
  if (gender) fields.push({ label: 'Gender', value: gender });

  // Relative Name
  const relativeName = getVal(front.father_or_husband_name);
  if (relativeName) fields.push({ label: 'Relative / Guardian', value: relativeName });

  // Blood Group
  const bloodGroup = getVal(front.blood_group);
  if (bloodGroup) fields.push({ label: 'Blood group', value: bloodGroup });

  // Issue & Expiry Dates
  const issueDate = getVal(front.issue_date);
  if (issueDate) fields.push({ label: 'Issue date', value: issueDate });

  const expiryDate = getVal(front.expiry_date);
  if (expiryDate) fields.push({ label: 'Expiry date', value: expiryDate });

  // Address & PIN
  const address = getVal(back.address);
  if (address) fields.push({ label: 'Address', value: address, fullWidth: true });

  const pin = getVal(back.pin_code);
  if (pin) fields.push({ label: 'Postal code', value: pin });

  const handleShare = async () => {
    try {
      const summaryLines = [
        `${docTitle} Details:`,
        ...fields.map((f) => `${f.label}: ${f.value}`),
      ];
      await Share.share({
        message: summaryLines.join('\n'),
      });
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.log(e);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
      {/* Primary Summary Card */}
      <View style={styles.summaryCard}>
        <View style={styles.summaryHeader}>
          <Text style={styles.docTypeLabel}>{docTitle.toUpperCase()}</Text>
          <View style={styles.tagsRow}>
            <View style={[styles.statusBadge, status === 'success' ? styles.statusSuccess : styles.statusPartial]}>
              <Text style={[styles.statusBadgeText, status === 'success' ? styles.statusSuccessText : styles.statusPartialText]}>
                {status === 'success' ? 'Verified' : 'Partial'}
              </Text>
            </View>
            <View style={styles.sourceBadge}>
              <Text style={styles.sourceBadgeText}>{sourceLabel}</Text>
            </View>
          </View>
        </View>

        <View style={styles.profileRow}>
          {photoB64 ? (
            <Image
              source={{ uri: `data:image/jpeg;base64,${photoB64}` }}
              style={styles.photo}
            />
          ) : (
            <View style={styles.placeholderPhoto}>
              <Text style={styles.placeholderText}>No photo</Text>
            </View>
          )}

          <View style={styles.profileDetails}>
            <Text style={styles.cardName}>{name || 'Cardholder'}</Text>
            <Text style={styles.cardId}>{idNo || '—'}</Text>
          </View>
        </View>
      </View>

      {/* Structured Details Card */}
      <View style={styles.detailsCard}>
        <Text style={styles.sectionHeading}>Document Information</Text>

        <View style={styles.fieldsList}>
          {fields.map((f, idx) => (
            <View
              key={idx}
              style={[
                styles.fieldRow,
                idx === fields.length - 1 && styles.fieldRowLast,
              ]}>
              <Text style={styles.fieldLabel}>{f.label}</Text>
              <Text style={styles.fieldValue} selectable={true}>
                {f.value}
              </Text>
            </View>
          ))}
        </View>
      </View>

      {/* Warnings / Advisory (subdued) */}
      {warnings && warnings.length > 0 && (
        <View style={styles.noticeCard}>
          <Text style={styles.noticeHeading}>Notes</Text>
          {warnings.map((w, idx) => (
            <Text key={idx} style={styles.noticeText}>
              &bull; {w}
            </Text>
          ))}
        </View>
      )}

      {/* Action Buttons */}
      <View style={styles.actionsContainer}>
        <TouchableOpacity style={styles.primaryActionBtn} onPress={handleShare} activeOpacity={0.8}>
          <Text style={styles.primaryActionText}>{copied ? 'Copied to clipboard' : 'Share details'}</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.secondaryActionBtn} onPress={onReset} activeOpacity={0.8}>
          <Text style={styles.secondaryActionText}>Scan another document</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 40,
    backgroundColor: '#F0F4F8',
  },
  summaryCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 20,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  summaryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  docTypeLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#64748B',
    letterSpacing: 0.8,
  },
  tagsRow: {
    flexDirection: 'row',
    gap: 6,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  statusSuccess: {
    backgroundColor: '#F0FDF4',
  },
  statusPartial: {
    backgroundColor: '#FEF3C7',
  },
  statusBadgeText: {
    fontSize: 11,
    fontWeight: '500',
  },
  statusSuccessText: {
    color: '#166534',
  },
  statusPartialText: {
    color: '#92400E',
  },
  sourceBadge: {
    backgroundColor: '#F1F5F9',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  sourceBadgeText: {
    fontSize: 11,
    fontWeight: '500',
    color: '#64748B',
  },
  profileRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  photo: {
    width: 68,
    height: 86,
    borderRadius: 10,
    backgroundColor: '#F1F5F9',
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  placeholderPhoto: {
    width: 68,
    height: 86,
    borderRadius: 10,
    backgroundColor: '#F1F5F9',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  placeholderText: {
    fontSize: 11,
    color: '#94A3B8',
  },
  profileDetails: {
    flex: 1,
    marginLeft: 16,
  },
  cardName: {
    fontSize: 20,
    fontWeight: '700',
    color: '#0F172A',
    letterSpacing: -0.3,
    marginBottom: 4,
  },
  cardId: {
    fontSize: 14,
    color: '#64748B',
    letterSpacing: 0.2,
  },
  detailsCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 20,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  sectionHeading: {
    fontSize: 12,
    fontWeight: '600',
    color: '#64748B',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    marginBottom: 14,
  },
  fieldsList: {
    flexDirection: 'column',
  },
  fieldRow: {
    paddingVertical: 11,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
  },
  fieldRowLast: {
    borderBottomWidth: 0,
    paddingBottom: 0,
  },
  fieldLabel: {
    fontSize: 12,
    fontWeight: '500',
    color: '#64748B',
    marginBottom: 3,
  },
  fieldValue: {
    fontSize: 15,
    fontWeight: '500',
    color: '#0F172A',
    lineHeight: 20,
  },
  noticeCard: {
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    padding: 14,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  noticeHeading: {
    fontSize: 12,
    fontWeight: '600',
    color: '#64748B',
    marginBottom: 4,
  },
  noticeText: {
    fontSize: 12,
    color: '#64748B',
    lineHeight: 18,
  },
  actionsContainer: {
    marginTop: 8,
    gap: 10,
  },
  primaryActionBtn: {
    backgroundColor: '#0F172A',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryActionText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
  secondaryActionBtn: {
    backgroundColor: '#F1F5F9',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryActionText: {
    color: '#0F172A',
    fontSize: 15,
    fontWeight: '500',
  },
});
