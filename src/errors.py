"""Exception hierarchy for P_123 Conversational Data Analysis Assistant.

Follows the error taxonomy specified in P123_ARCHITECTURE.md section 12.
"""

class AppError(Exception):
    """Base class for all application-specific exceptions."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UploadError(AppError):
    """Raised when an uploaded file is invalid, empty, too large, or unparseable."""
    pass


class NoDatasetError(AppError):
    """Raised when a question is submitted before uploading a dataset."""
    pass


class QuestionError(AppError):
    """Raised when the question is empty or exceeds the length limit."""
    pass


class ConfigError(AppError):
    """Raised when required configuration (e.g., GEMINI_API_KEY) is missing."""
    pass


class PlannerUnavailableError(AppError):
    """Raised when Gemini is unreachable, times out, or quota/rate limit is exhausted."""
    pass


class PlanError(AppError):
    """Raised when the question cannot be turned into a valid, supported QueryPlan."""
    pass


class ExecutionError(AppError):
    """Raised when deterministic Pandas calculation encounters an error."""
    pass


class ChartError(AppError):
    """Raised when chart generation fails (used internally; falls back gracefully)."""
    pass
