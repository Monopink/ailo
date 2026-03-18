export type RegionCountryCode = 'CN';

export type RegionCountryOption = Readonly<{
  code: RegionCountryCode;
  label: string;
  displayRegion: string;
}>;

export const REGION_COUNTRY_OPTIONS: readonly RegionCountryOption[] = [
  { code: 'CN', label: '中国大陆', displayRegion: '' },
] as const;
