/** Discard responses whose view or confirmed settings are no longer current. */
export class AsyncScope {
  private key = ''
  private revision = 0
  private active = true

  select(key: string) {
    if (key !== this.key) { this.key = key; this.revision++ }
  }

  activate() { this.active = true; this.revision++ }
  dispose() { this.active = false; this.revision++ }

  capture() {
    const revision = this.revision
    return () => this.active && revision === this.revision
  }
}
