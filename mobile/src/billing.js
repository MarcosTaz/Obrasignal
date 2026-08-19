import { Platform } from 'react-native';
import Purchases from 'react-native-purchases';

export const BILLING_ENTITLEMENT = 'pro';
export const BILLING_PRODUCT = 'obrasignal_pro_monthly';

let configuredUserId = null;

function publicKey() {
  return Platform.OS === 'ios'
    ? process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY
    : process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_KEY;
}

export async function configureBilling(appUserId) {
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
  const offerings = await Purchases.getOfferings();
  return offerings?.current || null;
}

export async function purchasePro() {
  const offering = await getCurrentOffering();
  const pkg = offering?.availablePackages?.find(p =>
    p?.product?.identifier === BILLING_PRODUCT || p?.packageType === 'MONTHLY'
  ) || offering?.availablePackages?.[0];
  if (!pkg) throw new Error('subscription_not_configured');
  const result = await Purchases.purchasePackage(pkg);
  return result?.customerInfo || null;
}

export async function restoreBilling() {
  return Purchases.restorePurchases();
}

export async function refreshBilling() {
  return Purchases.getCustomerInfo();
}
