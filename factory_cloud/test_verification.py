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
    def request(self):
        return ExecutionRequest(
            app_id="obrasignal",
            mode="repository_safe_execution",
            task="safe task",
            source="MarcosTaz/Obrasignal",
            canonical_head="expected-head",
            resume_at="safe task",
        )

    def test_matching_head_allows_delegate(self):
        verifier = GitHubHeadVerifier(opener=lambda request, timeout: FakeResponse({"commit": {"sha": "expected-head"}}))
        delegate = RecordingAdapter()
        result = VerifiedDispatchAdapter(delegate, "MarcosTaz/Obrasignal", "main", "expected-head", verifier).execute(self.request())
        self.assertEqual(delegate.calls, 1)
        self.assertEqual(result.status, "WAIT")
        self.assertIsNotNone(result.last_verified)

    def test_mismatching_head_stays_wait(self):
        verifier = GitHubHeadVerifier(opener=lambda request, timeout: FakeResponse({"commit": {"sha": "new-head"}}))
        delegate = RecordingAdapter()
        result = VerifiedDispatchAdapter(delegate, "MarcosTaz/Obrasignal", "main", "expected-head", verifier).execute(self.request())
        self.assertEqual(delegate.calls, 0)
        self.assertEqual(result.status, "WAIT")
        self.assertIn("canonical_head_changed", result.blockers)
        self.assertEqual(result.evidence["observed_head"], "new-head")

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
