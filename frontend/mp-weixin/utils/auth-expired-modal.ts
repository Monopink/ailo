import { promptLoginAndRedirect } from './login-redirect';

let authModalPromise: Promise<void> | null = null;

export const showAuthExpiredModalAndRelogin = async (): Promise<void> => {
  if (authModalPromise !== null) {
    return await authModalPromise;
  }

  authModalPromise = (async () => {
    try {
      await promptLoginAndRedirect({ source: 'session_expired' });
    } finally {
      authModalPromise = null;
    }
  })();

  return await authModalPromise;
};
