import type { StoredMessage } from '../storage';

type MessageSubscriber = (message: StoredMessage) => void;
type TypingSubscriber = (payload: { conv_id: string; from: string; typing: boolean }) => void;
type ErrorSubscriber = (payload: Error) => void;

class MessageEventBus {
  private messageHandlers = new Set<MessageSubscriber>();
  private typingHandlers = new Set<TypingSubscriber>();
  private errorHandlers = new Set<ErrorSubscriber>();

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

  emitMessage(message: StoredMessage): void {
    this.messageHandlers.forEach((handler) => handler(message));
  }

  emitTyping(payload: { conv_id: string; from: string; typing: boolean }): void {
    this.typingHandlers.forEach((handler) => handler(payload));
  }

  emitError(error: Error): void {
    this.errorHandlers.forEach((handler) => handler(error));
  }
}

export default new MessageEventBus();
