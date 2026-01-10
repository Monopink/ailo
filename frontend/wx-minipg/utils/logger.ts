/**
 * Logger utility
 * Provides structured logging with different log levels
 */

/* eslint-disable no-console */
import { LOG_LEVEL, LogLevel } from './env';
import { isNonEmptyString } from './guards';

export type LogLevelName = LogLevel | 'INFO' | 'WARN' | 'ERROR';

const LOG_LEVELS: Record<LogLevelName, number> = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3,
  NONE: 4,
};

let currentLogLevel: number = LOG_LEVELS[LOG_LEVEL];

type LogPayload = unknown;

const serializePayload = (payload: LogPayload): string | null => {
  if (payload === undefined) {
    return null;
  }
  if (typeof payload === 'string') {
    return payload;
  }
  try {
    return JSON.stringify(payload);
  } catch {
    return null;
  }
};

export function setLogLevel(level: LogLevelName): void {
  currentLogLevel = LOG_LEVELS[level];
}

function formatLog(level: LogLevelName, tag: string, message: string, data?: LogPayload): string {
  const timestamp = new Date().toISOString();
  const serialized = serializePayload(data);
  const dataStr = isNonEmptyString(serialized) ? ` ${serialized}` : '';
  return `[${timestamp}] [${level}] [${tag}] ${message}${dataStr}`;
}

function log(level: LogLevelName, tag: string, message: string, data?: LogPayload): void {
  const logLevel = LOG_LEVELS[level];

  if (logLevel < currentLogLevel) {
    return;
  }

  const formattedLog = formatLog(level, tag, message, data);

  switch (level) {
    case 'DEBUG':
    case 'INFO':
      console.log(formattedLog);
      break;
    case 'WARN':
      console.warn(formattedLog);
      break;
    case 'ERROR':
      console.error(formattedLog);
      break;
  }
}

export interface Logger {
  debug(message: string, data?: LogPayload): void;
  info(message: string, data?: LogPayload): void;
  warn(message: string, data?: LogPayload): void;
  error(message: string, data?: LogPayload): void;
}

export function getLogger(tag: string): Logger {
  return {
    debug: (message, data) => log('DEBUG', tag, message, data),
    info: (message, data) => log('INFO', tag, message, data),
    warn: (message, data) => log('WARN', tag, message, data),
    error: (message, data) => log('ERROR', tag, message, data),
  };
}

interface DefaultLogger extends Logger {
  getLogger: typeof getLogger;
  setLogLevel: typeof setLogLevel;
}

const defaultLogger: DefaultLogger = {
  debug: (message, data) => log('DEBUG', 'App', message, data),
  info: (message, data) => log('INFO', 'App', message, data),
  warn: (message, data) => log('WARN', 'App', message, data),
  error: (message, data) => log('ERROR', 'App', message, data),
  getLogger,
  setLogLevel,
};

export default defaultLogger;
