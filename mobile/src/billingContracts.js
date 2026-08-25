const BILLING_ENTITLEMENT = 'pro';
const BILLING_PRODUCT = 'obrasignal_pro_monthly';

function isCanonicalBillingProduct(identifier) {
  const value = String(identifier || '').trim();
  return value === BILLING_PRODUCT || value.startsWith(`${BILLING_PRODUCT}:`);
}

function selectProPackage(offering) {
  const packages = Array.isArray(offering?.availablePackages) ? offering.availablePackages : [];
  return packages.find((pkg) => isCanonicalBillingProduct(pkg?.product?.identifier)) || null;
}

module.exports = {
  BILLING_ENTITLEMENT,
  BILLING_PRODUCT,
  isCanonicalBillingProduct,
  selectProPackage,
};
