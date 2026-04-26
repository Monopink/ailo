import { initSystemSettingsPage } from '../common/page-core.js';

document.addEventListener('DOMContentLoaded', () => {
  const config = window.qiaoSystemSettingsPageConfig || {};
  initSystemSettingsPage(config);
});
