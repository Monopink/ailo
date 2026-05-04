import { initInvitationPolicyCard } from '../common/invitation-policy-card.js';
import { initSystemSettingsPage } from '../common/page-core.js';

document.addEventListener('DOMContentLoaded', () => {
  const config = window.ailoSystemSettingsPageConfig || {};
  initSystemSettingsPage(config);
  initInvitationPolicyCard(config);
});
