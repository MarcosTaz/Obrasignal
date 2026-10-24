/** Public contact identities must be deliberately configured after mailbox ownership
 * AND inbound delivery have been verified. No guessed support/legal emails.
 * These Expo constants are compiled into the public client: never put secrets here.
 */
const address=(value)=>{
  const v=String(value||'').trim().toLowerCase();
  return /^[a-z0-9._%+-]+@obrasignal\.com$/.test(v)?v:null;
};
export const PUBLIC_CONTACTS=Object.freeze({
  support:address(process.env.EXPO_PUBLIC_OBRASIGNAL_SUPPORT_EMAIL),
  privacy:address(process.env.EXPO_PUBLIC_OBRASIGNAL_PRIVACY_EMAIL),
  legal:address(process.env.EXPO_PUBLIC_OBRASIGNAL_LEGAL_EMAIL),
});
export function getContact(role) {return PUBLIC_CONTACTS[role]||null;}
export function contactLink(role,subject='ObraSignal enquiry') {
  const mail=getContact(role);
  return mail?'mailto:'+mail+'?subject='+encodeURIComponent(subject):null;
}
export const CONTACT_UNVERIFIED_MESSAGE='Institutional email contact is being verified. No address is shown until its mailbox is confirmed.';
