/**
 * Lightweight structured logger. Mirrors the backend's "one line per event,
 * with context" style so frontend logs are easy to correlate with backend
 * logs (e.g. via the `requestId` field, which matches the backend's
 * X-Request-ID).
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';
type LogContext = Record<string, unknown>;

const LEVEL_ORDER: Record<LogLevel, number> = { debug: 0, info: 1, warn: 2, error: 3 };
const minLevel: LogLevel = import.meta.env.DEV ? 'debug' : 'info';

const consoleFns: Record<LogLevel, (...args: unknown[]) => void> = {
  debug: console.debug.bind(console),
  info: console.info.bind(console),
  warn: console.warn.bind(console),
  error: console.error.bind(console),
};

function write(level: LogLevel, message: string, context?: LogContext): void {
  if (LEVEL_ORDER[level] < LEVEL_ORDER[minLevel]) return;
  const timestamp = new Date().toISOString();
  if (context && Object.keys(context).length > 0) {
    consoleFns[level](`[${timestamp}] ${message}`, context);
  } else {
    consoleFns[level](`[${timestamp}] ${message}`);
  }
}

export const logger = {
  debug: (message: string, context?: LogContext) => write('debug', message, context),
  info: (message: string, context?: LogContext) => write('info', message, context),
  warn: (message: string, context?: LogContext) => write('warn', message, context),
  error: (message: string, context?: LogContext) => write('error', message, context),
};
