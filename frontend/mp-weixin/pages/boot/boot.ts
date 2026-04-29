import { createPageLayoutData, type PageLayoutData } from '../../templates/page-layout';
import { getLogger } from '../../utils/logger';
import authService from '../../utils/auth-service';
import {
  probeRuntimeSegment,
  reportPreflightProbeResult,
  reportRuntimeObservation,
  type RuntimeProbeResult,
} from '../../utils/runtime-segment';

const logger = getLogger('Boot');
const LOADING_INDICATOR_DELAY_MS = 220;
const LOADING_TEXT_DELAY_MS = 1200;

type TimerHandle = ReturnType<typeof setTimeout>;

type RouteOptions = Record<string, string | undefined>;

interface BootPageData {
  pageLayoutData: PageLayoutData;
  routed: boolean;
  showLoadingIndicator: boolean;
  showLoadingText: boolean;
}

interface BootPageCustom {
  _loadingIndicatorTimer: TimerHandle | null;
  _loadingTextTimer: TimerHandle | null;
  _startLoadingFeedback(): void;
  _clearLoadingFeedback(): void;
  _routeOnce(callback: () => void): void;
  _routeUnauthenticated(options: RouteOptions, probe: RuntimeProbeResult): boolean;
  _handleAuthenticatedRoute(app: AppInstance, options: RouteOptions): Promise<void>;
  _warmupMessageService(app: AppInstance): Promise<void>;
}

const toError = (error: unknown): Error => {
  if (error instanceof Error) {
    return error;
  }
  if (typeof error === 'string') {
    return new Error(error);
  }
  try {
    return new Error(JSON.stringify(error));
  } catch {
    return new Error('Unknown error');
  }
};

const normalizeQueryValue = (value: string | undefined): string | null => {
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
};

const buildRouteUrl = (basePath: string, options: RouteOptions): string => {
  const params: string[] = [];

  const inviteCode = normalizeQueryValue(options.inviteCode);
  if (inviteCode !== null) {
    params.push(`inviteCode=${encodeURIComponent(inviteCode)}`);
  }

  const campaignCode = normalizeQueryValue(options.campaignCode);
  if (campaignCode !== null) {
    params.push(`campaignCode=${encodeURIComponent(campaignCode)}`);
  }

  if (params.length === 0) {
    return basePath;
  }
  return `${basePath}?${params.join('&')}`;
};

const resolveAuthenticatedAccountSegment = (): 0 | 1 => {
  const user = authService.getUserInfo();
  if (user?.account_segment === 1) {
    return 1;
  }
  return 0;
};

const reportBootRouteDecision = async (
  probe: RuntimeProbeResult,
  routeTarget: 'square_demo' | 'preview' | 'login' | 'index' | 'setup',
  source: string
): Promise<void> => {
  await reportRuntimeObservation({
    eventName: 'boot_route_decision',
    pagePath: '/pages/boot/boot',
    entrySource: source,
    probe,
    eventPayload: {
      route_target: routeTarget,
      is_online: probe.isOnline,
      probe_source: probe.probeSource,
    },
  });
};

Page<BootPageData, BootPageCustom>({
  data: {
    pageLayoutData: createPageLayoutData({
      screenModel: {
        screenState: 'ready',
        contentVariant: 'data',
        refreshState: 'idle',
      },
      hasFooter: false,
      emptyMessage: '',
    }),
    routed: false,
    showLoadingIndicator: false,
    showLoadingText: false,
  },
  _loadingIndicatorTimer: null,
  _loadingTextTimer: null,

  async onLoad(options: RouteOptions) {
    if (this.data.routed) {
      return;
    }
    this._startLoadingFeedback();

    try {
      const app = getApp<AppInstance>();
      const [isAuthenticated, probe] = await Promise.all([
        authService.initialize(),
        probeRuntimeSegment(),
      ]);

      logger.info('Boot routing', {
        isAuthenticated,
        needsProfileSetup: authService.needsProfileSetup(),
        runtimeSegment: probe.segmentType,
        isOnline: probe.isOnline,
        probeSource: probe.probeSource,
        options,
      });
      void reportPreflightProbeResult({
        probe,
        pagePath: '/pages/boot/boot',
        entrySource: 'cold_start',
      });

      if (!isAuthenticated) {
        const routed = this._routeUnauthenticated(options, probe);
        if (routed) {
          return;
        }
      }

      await this._handleAuthenticatedRoute(app, options);
    } catch (error) {
      const err = toError(error);
      logger.error('Boot routing error', { error: err.message });
      void reportRuntimeObservation({
        eventName: 'boot_route_decision',
        pagePath: '/pages/boot/boot',
        entrySource: 'boot_error',
        eventPayload: {
          route_target: 'login',
          error_message: err.message,
        },
      });
      this._routeOnce(() => {
        void wx.redirectTo({ url: '/pages/login/login' });
      });
    }
  },

  onUnload() {
    this._clearLoadingFeedback();
  },

  _startLoadingFeedback() {
    this._clearLoadingFeedback();

    this._loadingIndicatorTimer = setTimeout(() => {
      if (this.data.routed) {
        return;
      }
      this.setData({ showLoadingIndicator: true });
    }, LOADING_INDICATOR_DELAY_MS);

    this._loadingTextTimer = setTimeout(() => {
      if (this.data.routed) {
        return;
      }
      this.setData({
        showLoadingIndicator: true,
        showLoadingText: true,
      });
    }, LOADING_TEXT_DELAY_MS);
  },

  _clearLoadingFeedback() {
    if (this._loadingIndicatorTimer !== null) {
      clearTimeout(this._loadingIndicatorTimer);
      this._loadingIndicatorTimer = null;
    }
    if (this._loadingTextTimer !== null) {
      clearTimeout(this._loadingTextTimer);
      this._loadingTextTimer = null;
    }
  },

  _routeUnauthenticated(options: RouteOptions, probe: RuntimeProbeResult) {
    if (probe.segmentType === 1) {
      if (probe.isOnline) {
        void reportBootRouteDecision(probe, 'square_demo', 'cold_start');
        this._routeOnce(() => {
          void wx.redirectTo({ url: '/pkg/square-demo/square-demo?source=runtime_segment' });
        });
        return true;
      }

      void reportBootRouteDecision(probe, 'preview', 'cold_start');
      this._routeOnce(() => {
        void wx.redirectTo({ url: '/pkg/preview-index/preview-index?source=runtime_segment' });
      });
      return true;
    }

    void reportBootRouteDecision(probe, 'login', 'cold_start');
    const loginUrl = buildRouteUrl('/pages/login/login', options);
    this._routeOnce(() => {
      void wx.redirectTo({ url: loginUrl });
    });
    return true;
  },

  async _warmupMessageService(app: AppInstance) {
    try {
      await app.getConversationStore().init();
      await app.initMessageService();
    } catch (error) {
      const err = toError(error);
      logger.warn('Boot warmup failed, continue routing', { error: err.message });
    }
  },

  async _handleAuthenticatedRoute(app: AppInstance, options: RouteOptions) {
    const accountSegment = resolveAuthenticatedAccountSegment();

    await this._warmupMessageService(app);

    if (authService.needsProfileSetup()) {
      const setupUrl = buildRouteUrl('/pages/setup/setup', options);
      void reportRuntimeObservation({
        eventName: 'boot_route_decision',
        pagePath: '/pages/boot/boot',
        entrySource: 'cold_start',
        eventPayload: {
          route_target: 'setup',
          account_segment: accountSegment,
        },
      });
      this._routeOnce(() => {
        void wx.redirectTo({ url: setupUrl });
      });
      return;
    }

    void reportRuntimeObservation({
      eventName: 'boot_route_decision',
      pagePath: '/pages/boot/boot',
      entrySource: 'cold_start',
      eventPayload: {
        route_target: 'index',
        account_segment: accountSegment,
      },
    });
    this._routeOnce(() => {
      void wx.switchTab({ url: '/pages/index/index' });
    });
  },

  _routeOnce(callback: () => void) {
    if (this.data.routed) {
      return;
    }

    this._clearLoadingFeedback();
    this.setData({ routed: true });

    if (typeof wx.nextTick === 'function') {
      wx.nextTick(callback);
      return;
    }

    setTimeout(callback, 0);
  },
});
