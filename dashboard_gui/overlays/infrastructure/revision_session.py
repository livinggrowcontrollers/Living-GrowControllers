import time

from .contracts import SyncState


class RevisionSession:
    """UI-independent target-revision state machine."""

    def __init__(self, retry_delay=3.0, max_retries=5, clock=None):
        self.retry_delay = float(retry_delay)
        self.max_retries = int(max_retries)
        self._clock = clock or time.time
        self.last_sent_revision = 0
        self.last_send_time = 0.0
        self.retry_count = 0

    def mark_sent(self, revision):
        self.last_sent_revision = int(revision)
        self.last_send_time = self._clock()

    def mark_retried(self):
        self.last_send_time = self._clock()

    def mark_confirmed_snapshot(self, revision):
        self.last_sent_revision = 0 if revision is None else int(revision)
        self.last_send_time = 0.0
        self.reset_retry()

    def is_pending(self, server_revision):
        if server_revision is None:
            return False
        return self.last_sent_revision > int(server_revision)

    def should_retry(self):
        return (self._clock() - self.last_send_time) > self.retry_delay

    def retry_allowed(self):
        return self.retry_count < self.max_retries

    def register_retry(self):
        self.retry_count += 1
        self.mark_retried()

    def reset_retry(self):
        self.retry_count = 0

    def status(self, server_revision, user_active=False):
        if server_revision is None:
            return SyncState.ERROR

        if self.is_pending(server_revision):
            return SyncState.RETRY if self.retry_allowed() else SyncState.ERROR

        if user_active:
            return SyncState.DIRTY

        self.reset_retry()
        return SyncState.CONFIRMED

    # Compatibility aliases for screens that still expose legacy counters.
    def get_status(self, server_rev, user_active, last_user_action=0):
        return self.status(server_rev, user_active).value

    def is_synced(self, server_rev, user_active, last_user_action=0):
        return self.status(server_rev, user_active) == SyncState.CONFIRMED

    @property
    def _last_sent_rev(self):
        return self.last_sent_revision

    @_last_sent_rev.setter
    def _last_sent_rev(self, value):
        self.last_sent_revision = int(value)

    @property
    def _last_send_time(self):
        return self.last_send_time

    @_last_send_time.setter
    def _last_send_time(self, value):
        self.last_send_time = float(value)

    @property
    def _retry_count(self):
        return self.retry_count

    @_retry_count.setter
    def _retry_count(self, value):
        self.retry_count = int(value)

    @property
    def _max_retries(self):
        return self.max_retries

    @_max_retries.setter
    def _max_retries(self, value):
        self.max_retries = int(value)
