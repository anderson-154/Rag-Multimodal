# backend/tests/unit/domain/test_job.py
from datetime import UTC, datetime

import pytest

from src.domain.entities.job import Job, JobStatus
from src.domain.exceptions import InvalidJobTransitionError


def _make_job(status: JobStatus = JobStatus.PENDING) -> Job:
    return Job(
        id="job-1",
        document_filename="doc.pdf",
        status=status,
        created_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
    )


class TestJobValidTransitions:
    def test_pending_to_processing_via_start(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        assert job.status == JobStatus.PROCESSING

    def test_pending_to_failed_via_fail(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.fail("boom")
        assert job.status == JobStatus.FAILED
        assert job.error == "boom"

    def test_processing_stay_processing_on_update_progress(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        job.update_progress(50)
        assert job.status == JobStatus.PROCESSING
        assert job.progress == 50

    def test_processing_to_completed(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        job.update_progress(80)
        job.complete()
        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100
        assert job.error is None

    def test_processing_to_failed(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        job.fail("oops")
        assert job.status == JobStatus.FAILED
        assert job.error == "oops"

    def test_complete_clears_previous_error_when_reprocessing_path(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        job.fail("temp")
        job2 = _make_job(JobStatus.PENDING)
        job2.start()
        job2.error = "leftover"
        job2.complete()
        assert job2.error is None

    def test_updated_at_changes_on_transition(self) -> None:
        job = _make_job(JobStatus.PENDING)
        old = job.updated_at
        job.start()
        assert job.updated_at >= old

    def test_update_progress_changes_updated_at(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        old = job.updated_at
        job.update_progress(10)
        assert job.updated_at >= old


class TestJobInvalidTransitions:
    def test_completed_cannot_be_completed_again(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        job.complete()
        with pytest.raises(InvalidJobTransitionError):
            job.complete()

    def test_failed_cannot_be_completed(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.fail("x")
        with pytest.raises(InvalidJobTransitionError):
            job.complete()

    def test_failed_cannot_start(self) -> None:
        job = _make_job(JobStatus.FAILED)
        with pytest.raises(InvalidJobTransitionError):
            job.start()

    def test_failed_cannot_fail_again(self) -> None:
        job = _make_job(JobStatus.FAILED)
        with pytest.raises(InvalidJobTransitionError):
            job.fail("again")

    def test_completed_cannot_fail(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        job.complete()
        with pytest.raises(InvalidJobTransitionError):
            job.fail("x")

    def test_completed_cannot_start(self) -> None:
        job = _make_job(JobStatus.COMPLETED)
        with pytest.raises(InvalidJobTransitionError):
            job.start()

    def test_pending_cannot_complete_directly(self) -> None:
        job = _make_job(JobStatus.PENDING)
        with pytest.raises(InvalidJobTransitionError):
            job.complete()

    def test_update_progress_requires_processing_status(self) -> None:
        job = _make_job(JobStatus.PENDING)
        with pytest.raises(InvalidJobTransitionError):
            job.update_progress(10)

    def test_update_progress_requires_processing_status_when_completed(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        job.complete()
        with pytest.raises(InvalidJobTransitionError):
            job.update_progress(100)


class TestJobProgressValidation:
    def test_update_progress_zero_allowed(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        job.update_progress(0)
        assert job.progress == 0

    def test_update_progress_100_allowed(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        job.update_progress(100)
        assert job.progress == 100

    def test_update_progress_negative_rejected(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        with pytest.raises(ValueError):
            job.update_progress(-1)

    def test_update_progress_over_100_rejected(self) -> None:
        job = _make_job(JobStatus.PENDING)
        job.start()
        with pytest.raises(ValueError):
            job.update_progress(101)
