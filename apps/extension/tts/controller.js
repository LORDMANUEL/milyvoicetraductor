const SUCCESS_REASONS = new Set(['END', 'end']);

function notifyDrop(job, reason) {
  try {
    job?.lifecycle?.onDrop?.({
      requestId: job.requestId,
      utteranceId: job.utteranceId,
      speakerId: job.speakerId || null,
      reason
    });
  } catch (_) {
    // Diagnostics hooks must never break queue control.
  }
}

export class TtsQueueController {
  constructor({ maxPending = 3, maxAgeMs = 4000, now = () => Date.now() } = {}) {
    if (!Number.isInteger(maxPending) || maxPending < 1) {
      throw new RangeError('maxPending must be a positive integer');
    }
    if (!Number.isFinite(maxAgeMs) || maxAgeMs <= 0) {
      throw new RangeError('maxAgeMs must be positive');
    }
    if (typeof now !== 'function') {
      throw new TypeError('now must be a function');
    }
    this.maxPending = maxPending;
    this.maxAgeMs = maxAgeMs;
    this.now = now;
    this.pending = [];
    this.active = null;
    this.droppedCount = 0;
    this.health = 'healthy';
    this.lastErrorReason = 'NONE';
  }

  enqueue(job) {
    if (!job || typeof job !== 'object') throw new TypeError('job is required');
    if (!String(job.text || '').trim()) throw new TypeError('job text is required');
    const createdAt = Number.isFinite(job.createdAt) ? Number(job.createdAt) : this.now();
    const queued = { ...job, createdAt };

    if (this.pending.length >= this.maxPending) {
      const dropped = this.pending.shift();
      this._drop(dropped, 'QUEUE_OVERFLOW');
    }
    this.pending.push(queued);
    return queued;
  }

  takeNext() {
    if (this.active) return this.active;
    const current = this.now();
    while (this.pending.length) {
      const candidate = this.pending.shift();
      if (current - candidate.createdAt > this.maxAgeMs) {
        this._drop(candidate, 'STALE');
        continue;
      }
      this.active = candidate;
      return candidate;
    }
    return null;
  }

  finish(reason = 'END') {
    const finished = this.active;
    this.active = null;
    if (SUCCESS_REASONS.has(String(reason))) {
      this.health = 'healthy';
      this.lastErrorReason = 'NONE';
    } else if (finished) {
      this.markDegraded(String(reason || 'RUNTIME_ERROR').toUpperCase());
    }
    return finished;
  }

  markDegraded(reason) {
    this.health = 'degraded';
    this.lastErrorReason = String(reason || 'RUNTIME_ERROR').toUpperCase();
  }

  reset(_reason = 'CANCELLED') {
    const cleared = {
      active: this.active,
      pending: [...this.pending]
    };
    this.active = null;
    this.pending.length = 0;
    this.health = 'healthy';
    this.lastErrorReason = 'NONE';
    return cleared;
  }

  snapshot() {
    return {
      active: Boolean(this.active),
      pendingCount: this.pending.length,
      droppedCount: this.droppedCount,
      health: this.health,
      lastErrorReason: this.lastErrorReason
    };
  }

  _drop(job, reason) {
    if (!job) return;
    this.droppedCount += 1;
    this.markDegraded(reason);
    notifyDrop(job, reason);
  }
}
