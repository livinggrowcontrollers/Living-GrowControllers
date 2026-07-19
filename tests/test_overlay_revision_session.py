import unittest

from dashboard_gui.overlays.infrastructure.contracts import SyncState
from dashboard_gui.overlays.infrastructure.revision_session import RevisionSession


class RevisionSessionTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.session = RevisionSession(clock=lambda: self.now)

    def test_opening_snapshot_is_confirmed_without_pending(self):
        self.session.mark_confirmed_snapshot(7)
        self.assertFalse(self.session.is_pending(7))
        self.assertEqual(self.session.status(7), SyncState.CONFIRMED)

    def test_pending_retry_and_confirmation(self):
        self.session.mark_confirmed_snapshot(7)
        self.session.mark_sent(8)
        self.assertTrue(self.session.is_pending(7))
        self.assertEqual(self.session.status(7), SyncState.RETRY)
        self.now += 3.1
        self.assertTrue(self.session.should_retry())
        self.session.register_retry()
        self.assertEqual(self.session.retry_count, 1)
        self.assertEqual(self.session.status(8), SyncState.CONFIRMED)
        self.assertEqual(self.session.retry_count, 0)

    def test_user_interaction_stays_dirty_without_pending_revision(self):
        self.session.mark_confirmed_snapshot(3)
        self.assertEqual(self.session.status(3, user_active=True), SyncState.DIRTY)


if __name__ == "__main__":
    unittest.main()
