from typing import Protocol


class MeetingProvider(Protocol):
    """Implement and inject an adapter before advertising automatic meeting creation."""

    def create_session(self, title: str, starts_at: str, ends_at: str) -> str: ...


class PlagiarismProvider(Protocol):
    """An external review result must include the real provider and source report."""

    def check_submission(self, submission_id: str, content: str) -> dict: ...
