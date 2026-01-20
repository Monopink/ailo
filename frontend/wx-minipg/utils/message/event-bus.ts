import type { StoredMessage } from '../storage';
import type { ConnectionState } from './adapter-types';
type MessageSubscriber = (message: StoredMessage) => void;
type TypingSubscriber = (payload: {
  conv_id: string;
  from_qiao_id: string;
  typing: boolean;
}) => void;
type ErrorSubscriber = (payload: Error) => void;
type ConnectionSubscriber = (state: ConnectionState) => void;

class MessageEventBus {
  private messageHandlers = new Set<MessageSubscriber>();
  private typingHandlers = new Set<TypingSubscriber>();
  private errorHandlers = new Set<ErrorSubscriber>();
  private connectionHandlers = new Set<ConnectionSubscriber>();

  onMessage(handler: MessageSubscriber): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  onTyping(handler: TypingSubscriber): () => void {
    this.typingHandlers.add(handler);
    return () => this.typingHandlers.delete(handler);
  }

  onError(handler: ErrorSubscriber): () => void {
    this.errorHandlers.add(handler);
    return () => this.errorHandlers.delete(handler);
  }

  onConnection(handler: ConnectionSubscriber): () => void {
    this.connectionHandlers.add(handler);
    return () => this.connectionHandlers.delete(handler);
  }

  emitMessage(message: StoredMessage): void {
    this.messageHandlers.forEach((handler) => handler(message));
  }

  emitTyping(payload: { conv_id: string; from_qiao_id: string; typing: boolean }): void {
    this.typingHandlers.forEach((handler) => handler(payload));
  }

  emitError(error: Error): void {
    this.errorHandlers.forEach((handler) => handler(error));
  }

  emitConnection(state: ConnectionState): void {
    this.connectionHandlers.forEach((handler) => handler(state));
  }
}

export default new MessageEventBus();
