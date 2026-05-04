import type { LocalConfigOverride } from './config';

export const LOCAL_CONFIG_OVERRIDE: LocalConfigOverride = {
  API_CONFIG: {
    baseUrl: 'http://localhost:8000',
  },
  ASSET_CONFIG: {
    cosBaseUrl: 'https://your-dev-cos-domain.example.com',
    avatarPlaceholderPath: '/assets/avatar-placeholder.webp',
    demoAvatarDirPath: '/demo/avatars',
    loginBackgroundPath: '/login/bg.webp',
  },
};

export default LOCAL_CONFIG_OVERRIDE;
