# dashboard_gui/overlays/base_revision_system.py
import time

class BaseRevisionSystem:
    """
    Zentrale State-Maschine für:
    - Revision Tracking (rev)
    - Retry Logik
    - Sync Status (Green/Orange/Red)
    """

    def __init__(self):
        self._last_sent_rev = 0
        self._last_send_time = 0
        self._retry_count = 0
        self._max_retries = 5




    # =========================
    # REVISION / RETRY
    # =========================
    def mark_sent(self, rev):
        self._last_sent_rev = rev
        self._last_send_time = time.time()

    def mark_confirmed_snapshot(self, rev):
        """
        Snapshot/RAM data is already the last confirmed device state.
        Opening an overlay must not create a pending/retry state.
        """
        self._last_sent_rev = 0 if rev is None else int(rev)
        self._last_send_time = 0
        self.reset_retry()

    def is_pending(self, server_rev):
        return self._last_sent_rev > server_rev

    def should_retry(self):
        return (time.time() - self._last_send_time) > 3.0

    def retry_allowed(self):
        return self._retry_count < self._max_retries

    def register_retry(self):
        self._retry_count += 1

    def reset_retry(self):
        self._retry_count = 0

    # =========================
    # SYNC STATE (FIXED FOR MULTI-UI)
    # =========================
    def is_synced(self, server_rev, user_active, last_user_action):
        pending = self.is_pending(server_rev)

        return (not pending) and (not user_active)

    def get_status(self, server_rev, user_active, last_user_action):
        # No revision in the snapshot is invalid. Revision 0 itself is valid:
        # fresh devices can legitimately start at 0 and still be confirmed.
        if server_rev is None:
            return "error"

        if self.is_synced(server_rev, user_active, last_user_action):
            self.reset_retry()
            return "green"

        if self.is_pending(server_rev):
            if self.retry_allowed():
                return "retry"
            return "error"

        return "orange"
