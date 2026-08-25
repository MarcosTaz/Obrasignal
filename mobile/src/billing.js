import { Platform } from 'react-native';
import Purchases from 'react-native-purchases';

const {
  BILLING_ENTITLEMENT,
  BILLING_PRODUCT,
  isCanonicalBillingProduct,
  selectProPackage,
} = require('./billingContracts');

export { BILLING_ENTITLEMENT, BILLING_PRODUCT, isCanonicalBillingProduct, selectProPackage };
export const BILLING_SUPPORTED = Platform.OS === 'android' || Platform.OS === 'ios';

let configuredUserId = null;

function publicKey() {
  return Platform.OS === 'ios'
    ? process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY
    : process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_KEY;
}

export async function configureBilling(appUserId) {
  if (!BILLING_SUPPORTED) return { configured: false, customerInfo: null };
  const key = publicKey();
  if (!key || !appUserId) return { configured: false, customerInfo: null };
  const userId = String(appUserId);
  if (!configuredUserId) {
    await Purchases.configure({ apiKey: key, appUserID: userId });
    configuredUserId = userId;
  } else if (configuredUserId !== userId) {
    await Purchases.logIn(userId);
    configuredUserId = userId;
  }
  const customerInfo = await Purchases.getCustomerInfo();
  return { configured: true, customerInfo };
}

export function hasProEntitlement(customerInfo) {
  return Boolean(customerInfo?.entitlements?.active?.[BILLING_ENTITLEMENT]);
}

export function activeEntitlement(customerInfo) {
  return customerInfo?.entitlements?.active?.[BILLING_ENTITLEMENT] || null;
}

export async function getCurrentOffering() {
  if (!BILLING_SUPPORTED) return null;
  const offerings = await Purchases.getOfferings();
  return offerings?.current || null;
}

export async function purchasePro() {
  if (!BILLING_SUPPORTED) throw new Error('billing_not_available_on_web');
  const offering = await getCurrentOffering();
  const pkg = selectProPackage(offering);
  if (!pkg) throw new Error('canonical_subscription_not_configured');
  const result = await Purchases.purchasePackage(pkg);
  return result?.customerInfo || null;
}

export async function restoreBilling() {
  if (!BILLING_SUPPORTED) throw new Error('billing_not_available_on_web');
  return Purchases.restorePurchases();
}

export async function refreshBilling() {
  if (!BILLING_SUPPORTED) return null;
  return Purchases.getCustomerInfo();
}
