/**
 * Country Code Utilities
 * Provides country calling codes and phone number validation rules
 */

export interface CountryCodeInfo {
  code: string; // E.g., '+86'
  name: string; // E.g., '中国大陆'
  nameEn: string; // E.g., 'China Mainland'
  phoneLength: number; // Expected phone number length (without country code)
  flag?: string; // Optional emoji flag
}

/**
 * Supported country codes
 * Currently only China Mainland is supported
 */
export const COUNTRY_CODES: CountryCodeInfo[] = [
  {
    code: '+86',
    name: '中国大陆',
    nameEn: 'China Mainland',
    phoneLength: 11,
    flag: '🇨🇳',
  },
];

/**
 * Default country code (China Mainland)
 */
export const DEFAULT_COUNTRY_CODE = '+86';

/**
 * Get country info by country code
 */
export function getCountryByCode(code: string): CountryCodeInfo | undefined {
  return COUNTRY_CODES.find((country) => country.code === code);
}

/**
 * Get default country info
 */
export function getDefaultCountry(): CountryCodeInfo {
  return COUNTRY_CODES[0];
}

/**
 * Format phone number with country code
 */
export function formatPhoneWithCountryCode(countryCode: string, phone: string): string {
  return `${countryCode}${phone}`;
}

/**
 * Validate phone number length for a given country code
 */
export function validatePhoneLength(countryCode: string, phone: string): boolean {
  const country = getCountryByCode(countryCode);
  if (country === undefined) {
    return false;
  }
  return phone.length === country.phoneLength;
}
