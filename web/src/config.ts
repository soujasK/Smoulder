export const APP_NAME = 'Smoulder';
export const DATA_MODE: 'offline' | 'live' = (import.meta.env.VITE_DATA_MODE as 'offline' | 'live') || 'offline';
export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL as string) || '';
export const SNAPSHOT_URL = '/data/snapshot.json';
export const AQI_ADVISORY_URL = 'https://airquality.cpcb.gov.in/AQI_India/';
export const REPO_URL = 'https://github.com/';
