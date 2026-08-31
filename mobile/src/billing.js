import { Platform } from 'react-native';
import Purchases from 'react-native-purchases';

export const BILLING_ENTITLEMENT = 'pro';
export const BILLING_PRODUCT = 'obrasignal_pro_monthly';
export const BILLING_PLATFORM_SUPPORTED = Platform.OS === 'android' || Platform.OS === 'ios' || Platform.OS === 'web';
export const BILLING_RESTORE_SUPPORTED = Platform.OS === 'android' || Platform.OS === 'ios';

let configuredUserId = null;

function publicKey() {
  if (Platform.OS === 'web') return process.env.EXPO_PUBLIC_REVENUECAT_WEB_KEY;
  if (Platform.OS === 'ios') return process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY;
  return process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_KEY;
}

export function billingConfigurationAvailable() {
  return BILLING_PLATFORM_SUPPORTED && Boolean(publicKey());
}

export async function configureBilling(appUserId) {
  if (!billingConfigurationAvailable() || !appUserId) return { configured: false, customerInfo: null };
  const key = publicKey();
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
  if (!billingConfigurationAvailable()) return null;
  const offerings = await Purchases.getOfferings();
  return offerings?.current || null;
}

export async function purchasePro() {
  if (!billingConfigurationAvailable()) throw new Error('billing_not_configured');
  const offering = await getCurrentOffering();
  const pkg = offering?.availablePackages?.find(p =>
    p?.product?.identifier === BILLING_PRODUCT || p?.packageType === 'MONTHLY'
  ) || offering?.availablePackages?.[0];
  if (!pkg) throw new Error('subscription_not_configured');
  const result = await Purchases.purchasePackage(pkg);
  return result?.customerInfo || null;
}

export async function restoreBilling() {
  if (!BILLING_RESTORE_SUPPORTED) throw new Error('restore_not_supported_on_web');
  return Purchases.restorePurchases();
}

export async function refreshBilling() {
  if (!billingConfigurationAvailable()) return null;
  return Purchases.getCustomerInfo();
}
