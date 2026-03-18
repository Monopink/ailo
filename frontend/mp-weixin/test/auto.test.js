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

  it('should load square entry page', async () => {
    expect(page.path).toBe('pages/square-entry/square-entry');
  });

  it('should render entry cards', async () => {
    const cards = await page.$$('.square-entry-card');
    expect(cards.length).toBeGreaterThan(0);
  });

  it('should navigate after tapping a card', async () => {
    const card = await page.$('.square-entry-card');
    if (card) {
      await card.tap();
      await miniProgram.waitFor(1000);

      const currentPage = await miniProgram.currentPage();
      const allowed = ['pages/square/square', 'pages/login/login'];
      expect(allowed.includes(currentPage.path)).toBeTruthy();
    }
  });
});
