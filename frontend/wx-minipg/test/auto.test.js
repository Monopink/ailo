const automator = require('miniprogram-automator');

describe('MiniProgram Auto Test', () => {
  let miniProgram;
  let page;

  beforeAll(async () => {
    // Connect to running miniprogram devtools
    miniProgram = await automator.connect({
      wsEndpoint: 'ws://localhost:15244',
    });

    // Get current page
    page = await miniProgram.currentPage();
  }, 30000);

  afterAll(async () => {
    await miniProgram.close();
  });

  it('should load square page', async () => {
    expect(page.path).toBe('pages/square/square');
  });

  it('should have filter bar', async () => {
    const filterBar = await page.$('.filter-bar');
    expect(filterBar).toBeTruthy();
  });

  it('should have refresh button', async () => {
    const refreshBtn = await page.$('.refresh-btn');
    expect(refreshBtn).toBeTruthy();
  });

  it('should navigate to login page', async () => {
    // Try to click a filter that requires login
    const filterBtn = await page.$('.filter-btn[data-filter="dating"]');
    if (filterBtn) {
      await filterBtn.tap();
      await miniProgram.waitFor(1000);

      const currentPage = await miniProgram.currentPage();
      expect(currentPage.path).toBe('pages/login/login');
    }
  });
});
