"""High-volume synthetic-only security regression for invitation authority."""
import concurrent.futures
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from registration_invites import init_invites, issue_invite, consume_invite, revoke_invite

T=datetime(2026,10,15,20,tzinfo=timezone.utc)

class MassInvitationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.path=os.path.join(self.temp.name,"invites.sqlite")
  with sqlite3.connect(self.path) as c:
   c.execute("PRAGMA journal_mode=WAL")
   init_invites(c)
 def tearDown(self): self.temp.cleanup()
 def connect(self):
  return sqlite3.connect(self.path,timeout=20)
 def test_10000_distinct_issues_and_single_use(self):
  count=10000
  with self.connect() as c:
   items=[issue_invite(c,email=f"synthetic{i}@example.test",created_by="admin",now=T) for i in range(count)]
   self.assertEqual(len({x["code"] for x in items}),count)
   self.assertEqual(c.execute("SELECT count(*) FROM obrasignal_registration_invites").fetchone()[0],count)
   for x in items:
    self.assertTrue(consume_invite(c,email=x["email"],code=x["code"],now=T))
    self.assertFalse(consume_invite(c,email=x["email"],code=x["code"],now=T))
   self.assertEqual(c.execute("SELECT count(*) FROM obrasignal_registration_invites WHERE used_at IS NOT NULL").fetchone()[0],count)
 def test_64_simultaneous_redeemers_one_success(self):
  with self.connect() as c:
   x=issue_invite(c,email="concurrency@example.test",created_by="admin",now=T)
  def attempt(_):
   with self.connect() as c:
    return consume_invite(c,email=x["email"],code=x["code"],now=T)
  with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
   results=list(pool.map(attempt,range(64)))
  self.assertEqual(sum(results),1)
 def test_2000_wrong_email_and_expiry_cases(self):
  with self.connect() as c:
   items=[issue_invite(c,email=f"case{i}@example.test",created_by="admin",hours=1,now=T) for i in range(2000)]
   for i,x in enumerate(items):
    self.assertFalse(consume_invite(c,email=f"case{i+3000}@example.test",code=x["code"],now=T))
    self.assertFalse(consume_invite(c,email=x["email"],code=x["code"],now=T+timedelta(hours=1)))
   self.assertEqual(c.execute("SELECT count(*) FROM obrasignal_registration_invites WHERE used_at IS NOT NULL").fetchone()[0],0)
 def test_1000_revocations(self):
  with self.connect() as c:
   items=[issue_invite(c,email=f"revoke{i}@example.test",created_by="admin",now=T) for i in range(1000)]
   for x in items:
    self.assertTrue(revoke_invite(c,identifier=x["id"],now=T))
    self.assertFalse(consume_invite(c,email=x["email"],code=x["code"],now=T))
 def test_5000_reissues_invalidate_old_codes(self):
  with self.connect() as c:
   for i in range(5000):
    email=f"repeat{i}@example.test"
    old=issue_invite(c,email=email,created_by="admin",now=T)
    new=issue_invite(c,email=email,created_by="admin",now=T)
    self.assertFalse(consume_invite(c,email=email,code=old["code"],now=T))
    self.assertTrue(consume_invite(c,email=email,code=new["code"],now=T))

 def test_128_parallel_invalid_guesses_never_consume(self):
  with self.connect() as c:
   invited=issue_invite(c,email="target@example.test",created_by="admin",now=T)
  def guess(i):
   with self.connect() as c:
    return consume_invite(c,email=invited["email"],code="OS-"+format(i,"048x"),now=T)
  with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
   self.assertEqual(sum(pool.map(guess,range(128))),0)
  with self.connect() as c:
   self.assertTrue(consume_invite(c,email=invited["email"],code=invited["code"],now=T))

 def test_32_redeem_vs_revoke_races_never_both_win(self):
  for i in range(32):
   with self.connect() as c:
    invite=issue_invite(c,email=f"race{i}@example.test",created_by="admin",now=T)
   def consume():
    with self.connect() as c:
     return consume_invite(c,email=invite["email"],code=invite["code"],now=T)
   def revoke():
    with self.connect() as c:
     return revoke_invite(c,identifier=invite["id"],now=T)
   with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    a=pool.submit(consume)
    b=pool.submit(revoke)
    self.assertEqual(int(a.result())+int(b.result()),1)
   with self.connect() as c:
    self.assertFalse(consume_invite(c,email=invite["email"],code=invite["code"],now=T))

if __name__=="__main__": unittest.main()
