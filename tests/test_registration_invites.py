import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from registration_invites import init_invites, issue_invite, consume_invite, revoke_invite

T = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)


class InvitationAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        init_invites(self.db)

    def tearDown(self):
        self.db.close()

    def issue(self, **kwargs):
        return issue_invite(self.db, email="invited@example.org", created_by="admin",
                            now=T, **kwargs)

    def test_single_use_case_insensitive_email(self):
        invite = self.issue()
        self.assertTrue(consume_invite(self.db, email="Invited@Example.org",
                                       code=invite["code"], now=T))
        self.assertFalse(consume_invite(self.db, email="invited@example.org",
                                        code=invite["code"], now=T))

    def test_wrong_email_and_code(self):
        invite = self.issue()
        self.assertFalse(consume_invite(self.db, email="wrong@example.org",
                                        code=invite["code"], now=T))
        self.assertFalse(consume_invite(self.db, email=invite["email"],
                                        code="OS-" + "0" * 48, now=T))
        self.assertTrue(consume_invite(self.db, email=invite["email"],
                                       code=invite["code"], now=T))

    def test_expired_and_rejected_boundary(self):
        invite = self.issue(hours=1)
        self.assertFalse(consume_invite(self.db, email=invite["email"],
                          code=invite["code"], now=T + timedelta(hours=1)))

    def test_revocation(self):
        invite = self.issue()
        self.assertTrue(revoke_invite(self.db, identifier=invite["id"], now=T))
        self.assertFalse(revoke_invite(self.db, identifier=invite["id"], now=T))
        self.assertFalse(consume_invite(self.db, email=invite["email"],
                          code=invite["code"], now=T))

    def test_reissue_revokes_previous(self):
        first = self.issue()
        second = self.issue()
        self.assertFalse(consume_invite(self.db, email=first["email"],
                         code=first["code"], now=T))
        self.assertTrue(consume_invite(self.db, email=second["email"],
                        code=second["code"], now=T))

    def test_unsafe_inputs_fail(self):
        for hours in (0, 169, True):
            with self.assertRaises(ValueError):
                self.issue(hours=hours)
        with self.assertRaises(ValueError):
            issue_invite(self.db, email="invalid", created_by="admin", now=T)
        with self.assertRaises(ValueError):
            issue_invite(self.db, email="a@b.com", created_by="", now=T)

    def test_only_hash_persisted(self):
        invite = self.issue()
        row = self.db.execute("SELECT code_digest FROM obrasignal_registration_invites").fetchone()
        self.assertEqual(len(row[0]), 32)
        dump = "\n".join(self.db.iterdump())
        self.assertNotIn(invite["code"], dump)


if __name__ == "__main__":
    unittest.main()
