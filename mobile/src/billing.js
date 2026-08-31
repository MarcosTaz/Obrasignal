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

function productForPackage(pkg) {
  return pkg?.product || pkg?.webBillingProduct || pkg?.storeProduct || null;
}

function productIdentifier(pkg) {
  const product = productForPackage(pkg);
  return product?.identifier || product?.productIdentifier || product?.productId || product?.id || null;
}

function productionWebPurchaseLink() {
  if (Platform.OS !== 'web') return '';
  const raw = String(process.env.EXPO_PUBLIC_REVENUECAT_PURCHASE_LINK || '').trim();
  if (!raw) return '';
  try {
    const url = new URL(raw);
    if (url.protocol !== 'https:' || url.hostname !== 'pay.rev.cat') return '';
    if (url.pathname.toLowerCase().includes('/sandbox/')) return '';
    const cleanPath = url.pathname.replace(/\/+$/, '');
    if (!cleanPath || cleanPath === '/') return '';
    return `${url.origin}${cleanPath}`;
  } catch (_) {
    return '';
  }
}

export function billingConfigurationAvailable() {
  return BILLING_PLATFORM_SUPPORTED && Boolean(publicKey());
}

export function webPurchaseLinkConfigurationAvailable() {
  return Boolean(productionWebPurchaseLink());
}

export function webPurchaseUrl(appUserId) {
  const base = productionWebPurchaseLink();
  if (!base || !appUserId) return null;
  // RevenueCat Web Purchase Links identify a signed-in customer by appending
  // the URL-encoded App User ID as a path segment. We deliberately do not put
  // email or other personal data into the checkout URL.
  return `${base}/${encodeURIComponent(String(appUserId))}`;
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

export function proPackage(offering) {
  return offering?.availablePackages?.find(pkg => productIdentifier(pkg) === BILLING_PRODUCT) || null;
}

export function packagePriceString(pkg) {
  const product = productForPackage(pkg);
  return product?.priceString || product?.price?.formatted || product?.price?.formattedPrice || product?.currentPrice?.formatted || product?.currentPrice?.formattedPrice || null;
}

export async function getCurrentOffering() {
  if (!billingConfigurationAvailable()) return null;
  const offerings = await Purchases.getOfferings();
  return offerings?.current || null;
}

export async function purchasePro() {
  if (!billingConfigurationAvailable()) throw new Error('billing_not_configured');
  const offering = await getCurrentOffering();
  const pkg = proPackage(offering);
  if (!pkg) throw new Error('subscription_product_not_configured');
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
