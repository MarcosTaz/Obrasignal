import json
import unittest

from factory_cloud.adapters import ExecutionRequest, ExecutionResult
from factory_cloud.verification import GitHubHeadVerifier, VerifiedDispatchAdapter


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class RecordingAdapter:
    def __init__(self):
        self.calls = 0

    def execute(self, request):
        self.calls += 1
        return ExecutionResult(status="WAIT", blockers=("app_worker_execution_pending",), resume_at=request.task)


class FactoryCloudSourceVerificationTests(unittest.TestCase):
    def request(self, **changes):
        payload = dict(
            app_id="obrasignal",
            mode="repository_safe_execution",
            task="safe task",
            source="MarcosTaz/Obrasignal",
            canonical_head="expected-head",
            resume_at="safe task",
        )
        payload.update(changes)
        return ExecutionRequest(**payload)

    def test_matching_head_allows_delegate(self):
        verifier = GitHubHeadVerifier(opener=lambda request, timeout: FakeResponse({"commit": {"sha": "expected-head"}}))
        delegate = RecordingAdapter()
        result = VerifiedDispatchAdapter(delegate, "MarcosTaz/Obrasignal", "main", "expected-head", verifier).execute(self.request())
        self.assertEqual(delegate.calls, 1)
        self.assertEqual(result.status, "WAIT")
        self.assertIsNotNone(result.last_verified)

    def test_explicit_execution_source_matching_head_allows_delegate(self):
        verifier = GitHubHeadVerifier(opener=lambda request, timeout: FakeResponse({"commit": {"sha": "execution-head"}}))
        delegate = RecordingAdapter()
        result = VerifiedDispatchAdapter(
            delegate,
            "MarcosTaz/Obrasignal",
            "integration/current-spine",
            "execution-head",
            verifier,
        ).execute(self.request(execution_branch="integration/current-spine", execution_head="execution-head"))
        self.assertEqual(delegate.calls, 1)
        self.assertEqual(result.status, "WAIT")
        self.assertIsNotNone(result.last_verified)

    def test_request_execution_source_mismatch_fails_before_live_verification(self):
        class NeverVerify:
            def verify(self, repository, branch, expected_head):
                raise AssertionError("live verifier must not run for mismatched request authority")

        delegate = RecordingAdapter()
        adapter = VerifiedDispatchAdapter(
            delegate,
            "MarcosTaz/Obrasignal",
            "integration/current-spine",
            "execution-head",
            NeverVerify(),
        )
        for request in (
            self.request(source="MarcosTaz/Other", execution_branch="integration/current-spine", execution_head="execution-head"),
            self.request(execution_branch="other-branch", execution_head="execution-head"),
            self.request(execution_branch="integration/current-spine", execution_head="wrong-head"),
        ):
            result = adapter.execute(request)
            self.assertEqual(result.status, "WAIT")
            self.assertIn("execution_source_request_mismatch", result.blockers)
        self.assertEqual(delegate.calls, 0)

    def test_mismatching_head_stays_wait(self):
        verifier = GitHubHeadVerifier(opener=lambda request, timeout: FakeResponse({"commit": {"sha": "new-head"}}))
        delegate = RecordingAdapter()
        result = VerifiedDispatchAdapter(delegate, "MarcosTaz/Obrasignal", "main", "expected-head", verifier).execute(self.request())
        self.assertEqual(delegate.calls, 0)
        self.assertEqual(result.status, "WAIT")
        self.assertIn("canonical_head_changed", result.blockers)
        self.assertEqual(result.evidence["observed_head"], "new-head")
        self.assertEqual(result.evidence["verification_scope"], "execution_source")

    def test_unavailable_verification_remains_unknown(self):
        def unavailable(request, timeout):
            raise OSError("read unavailable")

        verifier = GitHubHeadVerifier(opener=unavailable)
        delegate = RecordingAdapter()
        result = VerifiedDispatchAdapter(delegate, "MarcosTaz/Obrasignal", "main", "expected-head", verifier).execute(self.request())
        self.assertEqual(delegate.calls, 0)
        self.assertEqual(result.status, "WAIT")
        self.assertEqual(result.evidence["source_verification"], "UNKNOWN")
        self.assertIn("source_verification_unavailable", result.blockers)

    def test_incomplete_source_truth_stays_blocked(self):
        verifier = GitHubHeadVerifier(opener=lambda request, timeout: FakeResponse({}))
        result = verifier.verify("MarcosTaz/Obrasignal", "main", None)
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.blocker, "canonical_source_truth_incomplete")


if __name__ == "__main__":
    unittest.main()
