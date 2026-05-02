import authService from './auth-service';
import { post, requestValidated } from './api';
import { BUILD_INFO } from './build-info';
import { ACCOUNT_SEGMENT } from './constants/user';
import { STORAGE_KEYS } from './config';
import { normalizeError } from './errors';
import { getLogger } from './logger';
import {
  ClientHealthResponseSchema,
  ClientPreflightProbeResponseSchema,
  type ClientPreflightProbeResponse,
} from './schemas';
import { getDeviceId } from './storage';

const logger = getLogger('RuntimeSegment');

const OFFLINE_PREVIEW_WINDOW_MS = 36 * 60 * 60 * 1000;
const HEALTH_PROBE_TIMEOUT_MS = 900;
const PROBE_TIMEOUT_MS = 1200;
const OBSERVATION_TIMEOUT_MS = 1000;
const RUNTIME_SESSION_TICK_INTERVAL_MS = 30 * 1000;
const MAX_RUNTIME_SESSION_TICK_QUEUE_SIZE = 240;
const _RUNTIME_STATE_SOURCE_VALUES = ['server', 'offline_36h', 'default'] as const;
const _RUNTIME_STATE_LEVEL_VALUES = ['provisional', 'confirmed'] as const;

let runtimeSessionId: string | null = null;
let latestRuntimeObservationId: number | null = null;
let runtimeSessionTickTimer: ReturnType<typeof setInterval> | null = null;
let runtimeSessionTickInFlightPromise: Promise<void> | null = null;
let runtimeSessionTickQueueFlushPromise: Promise<void> | null = null;

export type SegmentType = 0 | 1;
export type UaFetchStatus = 0 | 1 | 2 | 3;
export type RuntimeStateSource = (typeof _RUNTIME_STATE_SOURCE_VALUES)[number];
export type RuntimeStateLevel = (typeof _RUNTIME_STATE_LEVEL_VALUES)[number];
export type RuntimeProbeSource = RuntimeStateSource | 'server_unavailable';

export interface RuntimeSegmentState {
  segmentType: SegmentType;
  stateSource: RuntimeStateSource;
  stateLevel: RuntimeStateLevel;
  issuedAtMs: number;
  expiresAtMs: number | null;
  matchedFeatures: string[];
  uaFetchStatus: UaFetchStatus;
  userAgent: string;
}

export interface RuntimeProbeResult extends RuntimeSegmentState {
  isOnline: boolean;
  probeSource: RuntimeProbeSource;
}

export interface ClientHealthProbeResult {
  isReachable: boolean;
  serverTimeMs: number | null;
}

interface RuntimeProbeOptions {
  forceServerProbe?: boolean;
}

type RendererUserAgentResult = {
  status: UaFetchStatus;
  userAgent: string;
};

export interface InvitationRuntimeContext {
  segment_type: SegmentType;
  runtime_observation_id: number | null;
  client_user_agent: string;
}

interface RuntimeObservationAck {
  accepted?: unknown;
  event_id?: unknown;
}

interface RuntimeSessionTickQueueItem {
  occurredAtMs: number;
  pagePath: string;
  entrySource: string;
  eventPayload: Record<string, unknown>;
}

const normalizeSegmentType = (value: unknown): SegmentType => {
  if (value === 1) {
    return 1;
  }
  return 0;
};

const normalizeUserAgentText = (value: unknown): string => {
  if (typeof value !== 'string') {
    return '';
  }
  return value.trim();
};

const resolveBuildTimeMs = (): number | null => {
  const builtAt = BUILD_INFO.builtAt.trim();
  if (builtAt === '') {
    return null;
  }
  const builtAtMs = Date.parse(builtAt);
  if (Number.isNaN(builtAtMs)) {
    return null;
  }
  return builtAtMs;
};

const resolveOfflinePreviewExpiresAtMs = (): number | null => {
  const builtAtMs = resolveBuildTimeMs();
  if (builtAtMs === null) {
    return null;
  }
  return builtAtMs + OFFLINE_PREVIEW_WINDOW_MS;
};

export const isWithinOfflinePreviewWindow = (): boolean => {
  const expiresAtMs = resolveOfflinePreviewExpiresAtMs();
  if (expiresAtMs === null) {
    return false;
  }
  return Date.now() <= expiresAtMs;
};

const normalizeStateLevel = (value: unknown): RuntimeStateLevel => {
  if (value === 'confirmed') {
    return 'confirmed';
  }
  return 'provisional';
};

const normalizeStateSource = (value: unknown): RuntimeStateSource => {
  if (value === 'server' || value === 'offline_36h' || value === 'default') {
    return value;
  }
  return 'default';
};

const resolveStateLevel = (segmentType: SegmentType): RuntimeStateLevel => {
  if (segmentType === 1) {
    return 'confirmed';
  }
  return 'provisional';
};

const createRuntimeSegmentState = (options: {
  segmentType: SegmentType;
  stateSource: RuntimeStateSource;
  issuedAtMs: number;
  expiresAtMs?: number | null;
  matchedFeatures: string[];
  uaFetchStatus: UaFetchStatus;
  userAgent: string;
}): RuntimeSegmentState => {
  return {
    segmentType: options.segmentType,
    stateSource: options.stateSource,
    stateLevel: resolveStateLevel(options.segmentType),
    issuedAtMs: options.issuedAtMs,
    expiresAtMs: typeof options.expiresAtMs === 'number' ? options.expiresAtMs : null,
    matchedFeatures: options.matchedFeatures,
    uaFetchStatus: options.uaFetchStatus,
    userAgent: options.userAgent,
  };
};

const getNetworkType = async (): Promise<string> => {
  try {
    const result = await new Promise<WechatMiniprogram.GetNetworkTypeSuccessCallbackResult>(
      (resolve, reject) => {
        wx.getNetworkType({
          success: resolve,
          fail: reject,
        });
      }
    );
    return result.networkType;
  } catch {
    return '';
  }
};

const isOnlineNetworkType = (networkType: string): boolean => {
  const normalized = networkType.trim().toLowerCase();
  if (normalized === '' || normalized === 'none' || normalized === 'unknown') {
    return false;
  }
  return true;
};

const getRuntimeSessionId = (): string => {
  if (runtimeSessionId !== null) {
    return runtimeSessionId;
  }
  const randomSuffix = Math.random().toString(36).slice(2, 10);
  runtimeSessionId = `${BUILD_INFO.id}:${Date.now().toString(36)}:${randomSuffix}`;
  return runtimeSessionId;
};

const fetchRendererUserAgent = async (): Promise<RendererUserAgentResult> => {
  const wxRuntime = wx as unknown as {
    getRendererUserAgent?: (options?: {
      success?: (result: unknown) => void;
      fail?: (error: unknown) => void;
    }) => Promise<string> | void;
  };

  if (typeof wxRuntime.getRendererUserAgent !== 'function') {
    return { status: 3, userAgent: '' };
  }
  const getRendererUserAgent = wxRuntime.getRendererUserAgent;

  try {
    let rawUserAgent = '';

    const promiseUserAgent = await getRendererUserAgent();
    if (typeof promiseUserAgent === 'string') {
      rawUserAgent = promiseUserAgent;
    }

    if (rawUserAgent === '') {
      rawUserAgent = await new Promise<string>((resolve, reject) => {
        void getRendererUserAgent({
          success: (result) => {
            if (typeof result === 'string') {
              resolve(result);
              return;
            }
            if (result !== null && typeof result === 'object') {
              const record = result as { userAgent?: unknown };
              const extracted = normalizeUserAgentText(record.userAgent);
              if (extracted !== '') {
                resolve(extracted);
                return;
              }
            }
            resolve('');
          },
          fail: reject,
        });
      });
    }

    const normalized = normalizeUserAgentText(rawUserAgent);
    if (normalized === '') {
      return { status: 2, userAgent: '' };
    }
    return { status: 1, userAgent: normalized };
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.debug('fetch_renderer_user_agent_failed', { error: err.message });
    return { status: 2, userAgent: '' };
  }
};

const resolveObservationState = (probe?: RuntimeProbeResult): RuntimeSegmentState | null => {
  if (probe !== undefined) {
    return {
      segmentType: probe.segmentType,
      stateSource: probe.stateSource,
      stateLevel: probe.stateLevel,
      issuedAtMs: probe.issuedAtMs,
      expiresAtMs: probe.expiresAtMs,
      matchedFeatures: probe.matchedFeatures,
      uaFetchStatus: probe.uaFetchStatus,
      userAgent: probe.userAgent,
    };
  }
  return getRuntimeSegmentState();
};

export const getInvitationRuntimeContext = (): InvitationRuntimeContext => {
  const state = resolveObservationState();
  return {
    segment_type: normalizeSegmentType(state?.segmentType),
    runtime_observation_id: latestRuntimeObservationId,
    client_user_agent: state?.userAgent ?? '',
  };
};

const resolveObservationEventId = (payload: unknown): number | null => {
  if (payload === null || typeof payload !== 'object') {
    return null;
  }
  const record = payload as RuntimeObservationAck;
  if (record.accepted !== true) {
    return null;
  }
  if (typeof record.event_id !== 'number' || !Number.isFinite(record.event_id)) {
    return null;
  }
  if (record.event_id <= 0) {
    return null;
  }
  return Math.floor(record.event_id);
};

const normalizeRuntimeSessionTickQueueItem = (
  value: unknown
): RuntimeSessionTickQueueItem | null => {
  if (typeof value !== 'object' || value === null) {
    return null;
  }
  const record = value as Partial<RuntimeSessionTickQueueItem>;
  if (!Number.isFinite(record.occurredAtMs) || typeof record.occurredAtMs !== 'number') {
    return null;
  }
  if (typeof record.pagePath !== 'string' || record.pagePath.trim() === '') {
    return null;
  }
  if (typeof record.entrySource !== 'string' || record.entrySource.trim() === '') {
    return null;
  }
  const eventPayload = record.eventPayload as unknown;
  if (typeof eventPayload !== 'object' || eventPayload === null || Array.isArray(eventPayload)) {
    return null;
  }
  return {
    occurredAtMs: Math.floor(record.occurredAtMs),
    pagePath: record.pagePath,
    entrySource: record.entrySource,
    eventPayload: eventPayload as Record<string, unknown>,
  };
};

const getRuntimeSessionTickQueue = (): RuntimeSessionTickQueueItem[] => {
  try {
    const raw = wx.getStorageSync<unknown>(STORAGE_KEYS.RUNTIME_SESSION_TICK_QUEUE);
    if (!Array.isArray(raw)) {
      return [];
    }
    return raw
      .map((item) => normalizeRuntimeSessionTickQueueItem(item))
      .filter((item): item is RuntimeSessionTickQueueItem => item !== null)
      .slice(-MAX_RUNTIME_SESSION_TICK_QUEUE_SIZE);
  } catch {
    return [];
  }
};

const setRuntimeSessionTickQueue = (queue: RuntimeSessionTickQueueItem[]): void => {
  try {
    wx.setStorageSync(
      STORAGE_KEYS.RUNTIME_SESSION_TICK_QUEUE,
      queue.slice(-MAX_RUNTIME_SESSION_TICK_QUEUE_SIZE)
    );
  } catch (error: unknown) {
    logger.debug('store_runtime_session_tick_queue_failed', { error });
  }
};

const enqueueRuntimeSessionTick = (item: RuntimeSessionTickQueueItem): void => {
  const queue = getRuntimeSessionTickQueue();
  queue.push(item);
  setRuntimeSessionTickQueue(queue);
};

const getActivePagePath = (): string => {
  const pages = getCurrentPages();
  const currentPage = pages[pages.length - 1] as { route?: unknown } | undefined;
  if (typeof currentPage?.route !== 'string') {
    return '/app';
  }
  const route = currentPage.route.trim();
  if (route === '') {
    return '/app';
  }
  if (route.startsWith('/')) {
    return route;
  }
  return `/${route}`;
};

const isConfirmedLimitedState = (state: RuntimeSegmentState | null): boolean => {
  if (state === null) {
    return false;
  }
  return state.segmentType === 1 && state.stateLevel === 'confirmed';
};

export const ensurePreviewAccess = (pagePath: string): boolean => {
  if (shouldAllowPreviewAccess()) {
    return true;
  }
  void reportRuntimeObservation({
    eventName: 'preview_guard_redirect',
    pagePath,
    entrySource: 'preview_guard',
    eventPayload: {
      route_target: 'boot',
    },
  });
  void wx.reLaunch({
    url: '/pages/boot/boot?source=preview_guard',
  });
  return false;
};

const storeRuntimeSegmentState = (state: RuntimeSegmentState): void => {
  try {
    wx.setStorageSync(STORAGE_KEYS.RUNTIME_SEGMENT_STATE, state);
  } catch (error: unknown) {
    logger.debug('store_runtime_segment_state_failed', { error });
  }
};

export const getRuntimeSegmentState = (): RuntimeSegmentState | null => {
  try {
    const raw = wx.getStorageSync<unknown>(STORAGE_KEYS.RUNTIME_SEGMENT_STATE);
    if (typeof raw !== 'object' || raw === null) {
      return null;
    }
    const record = raw as Partial<RuntimeSegmentState>;
    const segmentType = normalizeSegmentType(record.segmentType);
    const uaFetchStatus = [0, 1, 2, 3].includes(Number(record.uaFetchStatus))
      ? (Number(record.uaFetchStatus) as UaFetchStatus)
      : 0;
    const issuedAtMs = typeof record.issuedAtMs === 'number' ? record.issuedAtMs : 0;
    const expiresAtMs =
      typeof record.expiresAtMs === 'number' && Number.isFinite(record.expiresAtMs)
        ? record.expiresAtMs
        : null;
    return {
      segmentType,
      stateSource: normalizeStateSource(record.stateSource),
      stateLevel: normalizeStateLevel(record.stateLevel),
      issuedAtMs,
      expiresAtMs,
      matchedFeatures: Array.isArray(record.matchedFeatures)
        ? record.matchedFeatures
            .filter((item): item is string => typeof item === 'string')
            .slice(0, 16)
        : [],
      uaFetchStatus,
      userAgent: typeof record.userAgent === 'string' ? record.userAgent : '',
    };
  } catch {
    return null;
  }
};

const getSystemRuntimeInfo = (): { platform: string; osVersion: string } => {
  try {
    const info = wx.getSystemInfoSync();
    return {
      platform: typeof info.platform === 'string' ? info.platform : '',
      osVersion: typeof info.system === 'string' ? info.system : '',
    };
  } catch {
    return { platform: '', osVersion: '' };
  }
};

const preflightProbeSegment = async (
  userAgent: string,
  occurredAtMs: number
): Promise<ClientPreflightProbeResponse | null> => {
  try {
    const deviceId = await getDeviceId();
    return await requestValidated(ClientPreflightProbeResponseSchema, {
      url: '/client/preflight-probe',
      method: 'POST',
      data: {
        client_type: 'mp_weixin',
        device_id: deviceId,
        user_agent: userAgent,
        platform: getSystemRuntimeInfo().platform,
        os_version: getSystemRuntimeInfo().osVersion,
        app_version: BUILD_INFO.appVersion,
        build_id: BUILD_INFO.id,
        build_time: BUILD_INFO.builtAt,
        occurred_at_ms: occurredAtMs,
      },
      auth: true,
      retryAuth: false,
      timeoutMs: PROBE_TIMEOUT_MS,
    });
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.debug('preflight_probe_segment_failed', { error: err.message });
    return null;
  }
};

export const probeClientHealth = async (): Promise<ClientHealthProbeResult> => {
  try {
    const response = await requestValidated(ClientHealthResponseSchema, {
      url: '/client/health',
      method: 'GET',
      auth: false,
      retryAuth: false,
      timeoutMs: HEALTH_PROBE_TIMEOUT_MS,
    });
    return {
      isReachable: true,
      serverTimeMs: response.server_time_ms,
    };
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.debug('client_health_probe_failed', { error: err.message });
    return {
      isReachable: false,
      serverTimeMs: null,
    };
  }
};

export const probeRuntimeSegment = async (
  options: RuntimeProbeOptions = {}
): Promise<RuntimeProbeResult> => {
  const forceServerProbe = options.forceServerProbe === true;
  const occurredAtMs = Date.now();
  const networkType = await getNetworkType();
  const isOnline = isOnlineNetworkType(networkType);
  const rendererResult = await fetchRendererUserAgent();

  if (!isOnline) {
    const isInOfflinePreviewWindow = isWithinOfflinePreviewWindow();
    const state = createRuntimeSegmentState({
      segmentType: isInOfflinePreviewWindow ? 1 : 0,
      stateSource: isInOfflinePreviewWindow ? 'offline_36h' : 'default',
      issuedAtMs: occurredAtMs,
      expiresAtMs: isInOfflinePreviewWindow ? resolveOfflinePreviewExpiresAtMs() : null,
      matchedFeatures: [],
      uaFetchStatus: rendererResult.status,
      userAgent: '',
    });
    storeRuntimeSegmentState(state);
    return {
      ...state,
      isOnline: false,
      probeSource: state.stateSource,
    };
  }

  const remoteDecision = await preflightProbeSegment(rendererResult.userAgent, occurredAtMs);
  if (remoteDecision !== null) {
    const state = createRuntimeSegmentState({
      segmentType: normalizeSegmentType(remoteDecision.segment_type),
      stateSource: 'server',
      issuedAtMs: occurredAtMs,
      matchedFeatures: [],
      uaFetchStatus: rendererResult.status,
      userAgent: rendererResult.userAgent,
    });
    storeRuntimeSegmentState(state);
    return {
      ...state,
      isOnline: true,
      probeSource: 'server',
    };
  }

  if (forceServerProbe) {
    const fallbackState = createRuntimeSegmentState({
      segmentType: 0,
      stateSource: 'default',
      issuedAtMs: occurredAtMs,
      matchedFeatures: [],
      uaFetchStatus: rendererResult.status,
      userAgent: rendererResult.userAgent,
    });
    storeRuntimeSegmentState(fallbackState);
    return {
      ...fallbackState,
      isOnline,
      probeSource: 'server_unavailable',
    };
  }

  const currentState = getRuntimeSegmentState();
  if (currentState !== null) {
    return {
      ...currentState,
      isOnline: true,
      probeSource: 'server_unavailable',
    };
  }

  const fallbackState = createRuntimeSegmentState({
    segmentType: 0,
    stateSource: 'default',
    issuedAtMs: occurredAtMs,
    matchedFeatures: [],
    uaFetchStatus: rendererResult.status,
    userAgent: rendererResult.userAgent,
  });
  storeRuntimeSegmentState(fallbackState);
  return {
    ...fallbackState,
    isOnline: true,
    probeSource: 'server_unavailable',
  };
};

const normalizeSegmentTypeForObservation = (probe?: RuntimeProbeResult): SegmentType => {
  if (probe !== undefined) {
    return probe.segmentType;
  }
  const user = authService.getUserInfo();
  if (user?.account_segment === ACCOUNT_SEGMENT.MEMBER_LIMITED) {
    return 1;
  }
  const state = getRuntimeSegmentState();
  if (isConfirmedLimitedState(state)) {
    return 1;
  }
  return 0;
};

export const shouldAllowPreviewAccess = (): boolean => {
  const user = authService.getUserInfo();
  if (user?.account_segment === ACCOUNT_SEGMENT.MEMBER_LIMITED) {
    return true;
  }
  const state = getRuntimeSegmentState();
  return isConfirmedLimitedState(state);
};

export const applyOfflinePreviewFallbackState = (): void => {
  const issuedAtMs = Date.now();
  const state = createRuntimeSegmentState({
    segmentType: 1,
    stateSource: 'offline_36h',
    issuedAtMs,
    expiresAtMs: resolveOfflinePreviewExpiresAtMs(),
    matchedFeatures: [],
    uaFetchStatus: 0,
    userAgent: '',
  });
  storeRuntimeSegmentState(state);
};

export const reportPreflightProbeResult = async (options: {
  probe: RuntimeProbeResult;
  pagePath: string;
  entrySource: string;
}): Promise<number | null> => {
  const { probe, pagePath, entrySource } = options;
  return await reportRuntimeObservation({
    eventName: 'preflight_probe_result',
    pagePath,
    entrySource,
    probe,
    eventPayload: {
      segment_type: probe.segmentType,
      probe_source: probe.probeSource,
      state_source: probe.stateSource,
      state_level: probe.stateLevel,
      is_online: probe.isOnline,
      ua_fetch_status: probe.uaFetchStatus,
      matched_features: probe.matchedFeatures,
    },
  });
};

export const reportRuntimeObservation = async (options: {
  eventName: string;
  pagePath: string;
  entrySource: string;
  eventPayload?: Record<string, unknown>;
  probe?: RuntimeProbeResult;
  requestId?: string;
  occurredAtMs?: number;
}): Promise<number | null> => {
  try {
    const deviceId = await getDeviceId();
    if (deviceId.trim() === '') {
      return null;
    }
    const systemInfo = getSystemRuntimeInfo();
    const networkType = await getNetworkType();
    const state = resolveObservationState(options.probe);
    const segmentType = normalizeSegmentTypeForObservation(options.probe);
    const matchedFeatures = state?.matchedFeatures ?? [];
    const uaFetchStatus = state?.uaFetchStatus ?? 0;
    const userAgent = state?.userAgent ?? '';
    const response = await post(
      '/client/runtime-observations',
      {
        client_type: 'mp_weixin',
        device_id: deviceId,
        session_id: getRuntimeSessionId(),
        user_agent: userAgent,
        platform: systemInfo.platform !== '' ? systemInfo.platform : 'miniprogram',
        os_version: systemInfo.osVersion,
        app_version: BUILD_INFO.appVersion,
        build_id: BUILD_INFO.id,
        build_time: BUILD_INFO.builtAt,
        network_type: networkType,
        segment_type: segmentType,
        matched_features: matchedFeatures,
        ua_fetch_status: uaFetchStatus,
        event_name: options.eventName,
        page_path: options.pagePath,
        entry_source: options.entrySource,
        event_payload: options.eventPayload ?? {},
        request_id: options.requestId ?? '',
        occurred_at_ms: options.occurredAtMs ?? Date.now(),
      },
      {
        auth: true,
        retryAuth: false,
        timeoutMs: OBSERVATION_TIMEOUT_MS,
      }
    );
    const eventId = resolveObservationEventId(response);
    if (eventId !== null) {
      latestRuntimeObservationId = eventId;
    }
    return eventId;
  } catch (error: unknown) {
    const err = normalizeError(error);
    logger.debug('report_runtime_observation_failed', {
      eventName: options.eventName,
      error: err.message,
    });
    return null;
  }
};

const flushRuntimeSessionTickQueueInternal = async (): Promise<void> => {
  const flushOneByOne = async (
    queue: RuntimeSessionTickQueueItem[],
    index: number
  ): Promise<RuntimeSessionTickQueueItem[]> => {
    if (index >= queue.length) {
      return [];
    }
    const item = queue[index];
    const eventId = await reportRuntimeObservation({
      eventName: 'runtime_session_tick',
      pagePath: item.pagePath,
      entrySource: item.entrySource,
      eventPayload: item.eventPayload,
      occurredAtMs: item.occurredAtMs,
    });
    if (eventId === null) {
      return queue.slice(index);
    }
    return await flushOneByOne(queue, index + 1);
  };

  const networkType = await getNetworkType();
  if (!isOnlineNetworkType(networkType)) {
    return;
  }
  const queue = getRuntimeSessionTickQueue();
  if (queue.length === 0) {
    return;
  }
  const remaining = await flushOneByOne(queue, 0);
  setRuntimeSessionTickQueue(remaining);
};

export const flushRuntimeSessionTickQueue = async (): Promise<void> => {
  if (runtimeSessionTickQueueFlushPromise !== null) {
    await runtimeSessionTickQueueFlushPromise;
    return;
  }
  const flushPromise = flushRuntimeSessionTickQueueInternal();
  runtimeSessionTickQueueFlushPromise = flushPromise;
  try {
    await flushPromise;
  } finally {
    if (runtimeSessionTickQueueFlushPromise === flushPromise) {
      runtimeSessionTickQueueFlushPromise = null;
    }
  }
};

const reportRuntimeSessionTickOnceInternal = async (
  trigger: 'app_launch' | 'app_show' | 'interval'
): Promise<void> => {
  const occurredAtMs = Date.now();
  const pagePath = getActivePagePath();
  const entrySource = 'runtime_tick';
  const eventPayload = {
    trigger,
    queue_size_before_flush: getRuntimeSessionTickQueue().length,
  };
  const networkType = await getNetworkType();

  if (!isOnlineNetworkType(networkType)) {
    enqueueRuntimeSessionTick({
      occurredAtMs,
      pagePath,
      entrySource,
      eventPayload,
    });
    return;
  }

  await flushRuntimeSessionTickQueue();
  const eventId = await reportRuntimeObservation({
    eventName: 'runtime_session_tick',
    pagePath,
    entrySource,
    eventPayload,
    occurredAtMs,
  });
  if (eventId === null) {
    enqueueRuntimeSessionTick({
      occurredAtMs,
      pagePath,
      entrySource,
      eventPayload,
    });
  }
};

const reportRuntimeSessionTickOnce = async (
  trigger: 'app_launch' | 'app_show' | 'interval'
): Promise<void> => {
  if (runtimeSessionTickInFlightPromise !== null) {
    await runtimeSessionTickInFlightPromise;
    return;
  }
  const inFlight = reportRuntimeSessionTickOnceInternal(trigger);
  runtimeSessionTickInFlightPromise = inFlight;
  try {
    await inFlight;
  } finally {
    if (runtimeSessionTickInFlightPromise === inFlight) {
      runtimeSessionTickInFlightPromise = null;
    }
  }
};

const reportRuntimeSessionTickIfEligible = async (
  trigger: 'app_launch' | 'app_show' | 'interval'
): Promise<void> => {
  if (!shouldAllowPreviewAccess()) {
    return;
  }
  await reportRuntimeSessionTickOnce(trigger);
};

const reportRuntimeSessionTickLoop = (): void => {
  void reportRuntimeSessionTickIfEligible('interval');
};

const reportRuntimeSessionTickStart = (trigger: 'app_launch' | 'app_show'): void => {
  void reportRuntimeSessionTickIfEligible(trigger);
};

export const startRuntimeSessionTick = (
  trigger: 'app_launch' | 'app_show' = 'app_launch'
): void => {
  if (runtimeSessionTickTimer !== null) {
    return;
  }
  reportRuntimeSessionTickStart(trigger);
  runtimeSessionTickTimer = setInterval(
    reportRuntimeSessionTickLoop,
    RUNTIME_SESSION_TICK_INTERVAL_MS
  );
};

export const stopRuntimeSessionTick = (): void => {
  if (runtimeSessionTickTimer === null) {
    return;
  }
  clearInterval(runtimeSessionTickTimer);
  runtimeSessionTickTimer = null;
};
