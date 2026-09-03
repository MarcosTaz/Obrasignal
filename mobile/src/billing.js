import { Linking, Platform } from 'react-native';
import Purchases from 'react-native-purchases';

export const BILLING_ENTITLEMENT = 'pro';
export const BILLING_PRODUCT = 'obrasignal_pro_monthly';
export const BILLING_SUPPORTED = Platform.OS === 'android' || Platform.OS === 'ios';
export const WEB_BILLING_SUPPORTED = Platform.OS === 'web';

let configuredUserId = null;

function publicKey() {
  return Platform.OS === 'ios'
    ? process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY
    : process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_KEY;
}

function webPurchaseBaseUrl() {
  const raw = String(process.env.EXPO_PUBLIC_REVENUECAT_WEB_PURCHASE_URL || '').trim();
  if (!raw) return null;
  let parsed;
  try { parsed = new URL(raw); } catch (_) { return null; }
  if (parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.hash || parsed.search) return null;
  return parsed.toString().replace(/\/$/, '');
}

export function webPurchaseConfigured() {
  return Boolean(webPurchaseBaseUrl());
}

export function webPurchaseUrl(appUserId, email = null) {
  const base = webPurchaseBaseUrl();
  const userId = String(appUserId || '').trim();
  if (!base) throw new Error('web_billing_not_configured');
  if (!userId) throw new Error('web_billing_user_required');
  const url = new URL(`${base}/${encodeURIComponent(userId)}`);
  if (email) url.searchParams.set('email', String(email));
  return url.toString();
}

export async function openWebPurchase(appUserId, email = null) {
  if (!WEB_BILLING_SUPPORTED) throw new Error('web_billing_only_available_on_web');
  const url = webPurchaseUrl(appUserId, email);
  const supported = await Linking.canOpenURL(url);
  if (!supported) throw new Error('web_billing_link_unavailable');
  await Linking.openURL(url);
  return true;
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
  const pkg = offering?.availablePackages?.find(p =>
    p?.product?.identifier === BILLING_PRODUCT || p?.packageType === 'MONTHLY'
  ) || offering?.availablePackages?.[0];
  if (!pkg) throw new Error('subscription_not_configured');
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
