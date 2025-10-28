import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  ScrollView,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import SignatureCanvas from 'react-native-signature-canvas';
import { supabase, getCurrentUser, signOut } from '../lib/supabase';

const { width } = Dimensions.get('window');

export default function SignatureScreen({ route, navigation }) {
  const { contractMd5 } = route.params;
  const signatureRef = useRef();

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [contractData, setContractData] = useState(null);
  const [signatureData, setSignatureData] = useState(null);
  const [hasSignature, setHasSignature] = useState(false);

  useEffect(() => {
    loadContractData();
  }, [contractMd5]);

  const loadContractData = async () => {
    try {
      setIsLoading(true);

      const user = await getCurrentUser();
      if (!user) {
        navigation.replace('Login');
        return;
      }

      // Fetch contract data from the view
      const { data, error } = await supabase
        .from('new_authenticated_list_contract')
        .select('*')
        .eq('uid', user.id)
        .eq('contract_num_detail_md5', contractMd5)
        .single();

      if (error) {
        throw error;
      }

      if (!data) {
        Alert.alert('Error', 'Contract not found');
        navigation.replace('NoContract');
        return;
      }

      setContractData(data);
    } catch (error) {
      console.error('Error loading contract:', error);
      Alert.alert('Error', 'Failed to load contract data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignature = (signature) => {
    setSignatureData(signature);
    setHasSignature(true);
  };

  const handleClear = () => {
    signatureRef.current?.clearSignature();
    setSignatureData(null);
    setHasSignature(false);
  };

  const handleSave = async () => {
    if (!hasSignature) {
      Alert.alert('Error', 'Please provide your signature');
      return;
    }

    try {
      setIsSaving(true);

      const user = await getCurrentUser();
      if (!user) {
        navigation.replace('Login');
        return;
      }

      // Save signature to contract_signatures table
      const { error } = await supabase
        .from('contract_signatures')
        .insert({
          uid: user.id,
          contract_num_detail: contractData.contract_num_detail,
          signature_svg: signatureData,
          signature_png: signatureData, // In production, convert SVG to PNG
          signed_pdf: null, // In production, generate signed PDF
          signer_name: contractData.name,
        });

      if (error) {
        throw error;
      }

      Alert.alert(
        'Success',
        'Your signature has been saved successfully!',
        [
          {
            text: 'OK',
            onPress: () => {
              handleSignOut();
            },
          },
        ]
      );
    } catch (error) {
      console.error('Error saving signature:', error);
      Alert.alert('Error', 'Failed to save signature. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleSignOut = async () => {
    try {
      await signOut();
      navigation.replace('Login');
    } catch (error) {
      console.error('Sign out error:', error);
    }
  };

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#2563EB" />
        <Text style={styles.loadingText}>Loading contract...</Text>
      </View>
    );
  }

  if (!contractData) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>Contract not found</Text>
          <TouchableOpacity style={styles.button} onPress={handleSignOut}>
            <Text style={styles.buttonText}>Sign Out</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Contract Signature</Text>
          <TouchableOpacity onPress={handleSignOut}>
            <Text style={styles.signOutLink}>Sign Out</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Contract Information</Text>

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Name:</Text>
            <Text style={styles.infoValue}>{contractData.name}</Text>
          </View>

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>NIP:</Text>
            <Text style={styles.infoValue}>{contractData.nip}</Text>
          </View>

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Position:</Text>
            <Text style={styles.infoValue}>{contractData.job_position}</Text>
          </View>

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Location:</Text>
            <Text style={styles.infoValue}>{contractData.location}</Text>
          </View>

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Contract Number:</Text>
            <Text style={styles.infoValue}>{contractData.contract_num_detail}</Text>
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Your Signature</Text>
          <Text style={styles.instructions}>
            Please sign below to acknowledge and accept the contract terms
          </Text>

          <View style={styles.signatureContainer}>
            <SignatureCanvas
              ref={signatureRef}
              onOK={handleSignature}
              onEmpty={() => {
                setHasSignature(false);
                setSignatureData(null);
              }}
              descriptionText=""
              clearText="Clear"
              confirmText="Save"
              webStyle={`
                .m-signature-pad {
                  box-shadow: none;
                  border: 2px solid #D1D5DB;
                  border-radius: 8px;
                }
                .m-signature-pad--body {
                  border: none;
                }
                .m-signature-pad--footer {
                  display: none;
                }
              `}
              style={styles.signature}
            />
          </View>

          <View style={styles.buttonContainer}>
            <TouchableOpacity
              style={[styles.button, styles.clearButton]}
              onPress={handleClear}
              disabled={isSaving}
            >
              <Text style={styles.clearButtonText}>Clear</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.button,
                styles.saveButton,
                (!hasSignature || isSaving) && styles.buttonDisabled,
              ]}
              onPress={handleSave}
              disabled={!hasSignature || isSaving}
            >
              {isSaving ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.buttonText}>Submit Signature</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#6B7280',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  errorText: {
    fontSize: 18,
    color: '#DC2626',
    marginBottom: 24,
  },
  scrollContent: {
    padding: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#111827',
  },
  signOutLink: {
    fontSize: 16,
    color: '#2563EB',
    fontWeight: '500',
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 16,
  },
  instructions: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 16,
  },
  infoRow: {
    flexDirection: 'row',
    marginBottom: 12,
  },
  infoLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#6B7280',
    width: 120,
  },
  infoValue: {
    fontSize: 14,
    color: '#111827',
    flex: 1,
  },
  signatureContainer: {
    height: 250,
    marginBottom: 16,
    borderWidth: 2,
    borderColor: '#D1D5DB',
    borderRadius: 8,
    overflow: 'hidden',
  },
  signature: {
    flex: 1,
  },
  buttonContainer: {
    flexDirection: 'row',
    gap: 12,
  },
  button: {
    flex: 1,
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
  },
  clearButton: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#D1D5DB',
  },
  clearButtonText: {
    color: '#374151',
    fontSize: 16,
    fontWeight: '600',
  },
  saveButton: {
    backgroundColor: '#2563EB',
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
});
