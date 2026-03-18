import type { MessageAdapter } from './adapter-types';
import leancloudAdapter from './leancloud';
import { getLogger } from '../logger';
import { isDefined } from '../guards';

const logger = getLogger('MessageProvider');
let currentAdapter: MessageAdapter | null = null;

export function registerMessageAdapter(adapter: MessageAdapter): void {
  currentAdapter = adapter;
  logger.info('Message adapter registered', { name: adapter.constructor.name });
}

export function getMessageAdapter(): MessageAdapter {
  if (!isDefined(currentAdapter)) {
    currentAdapter = leancloudAdapter;
  }
  return currentAdapter;
}
