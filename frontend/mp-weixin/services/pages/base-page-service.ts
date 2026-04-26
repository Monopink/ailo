export abstract class BasePageService {
  private requestSeqByKey = new Map<string, number>();
  private disposed = false;

  protected startRequest(requestKey = 'default'): number {
    const current = this.requestSeqByKey.get(requestKey) ?? 0;
    const next = current + 1;
    this.requestSeqByKey.set(requestKey, next);
    return next;
  }

  protected isRequestActive(seq: number, requestKey = 'default'): boolean {
    return !this.disposed && seq === (this.requestSeqByKey.get(requestKey) ?? 0);
  }

  protected get isDisposed(): boolean {
    return this.disposed;
  }

  dispose(): void {
    this.disposed = true;
  }
}
