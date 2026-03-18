export abstract class BasePageService {
  private requestSeq = 0;
  private disposed = false;

  protected startRequest(): number {
    this.requestSeq += 1;
    return this.requestSeq;
  }

  protected isRequestActive(seq: number): boolean {
    return !this.disposed && seq === this.requestSeq;
  }

  protected get isDisposed(): boolean {
    return this.disposed;
  }

  dispose(): void {
    this.disposed = true;
    this.requestSeq += 1;
  }
}
