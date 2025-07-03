from typing import Optional


class AppException(Exception):
    """
    Base application exception class.
    All custom exceptions in the application should inherit from this class.
    """

    def __init__(self, status_code: int, detail: Optional[str] = None):
        """
        Args:
            status_code (int): HTTP status code to be returned.
            detail (Optional[str], optional): Detailed error message. Defaults to None.
        """
        self.status_code = status_code
        self.detail = detail or self.__class__.__name__
        super().__init__(self.detail)


class BotNotFoundError(AppException):
    """
    Raised when a specific bot cannot be found in the database.
    """

    def __init__(self, entity_id: str):
        super().__init__(status_code=404, detail=f"Bot with entity_id '{entity_id}' not found.")


class AuthorizationError(AppException):
    """
    Raised when a user is not authorized to perform an action on a resource.
    """

    def __init__(self, detail: str = "User not authorized for this action."):
        super().__init__(status_code=403, detail=detail)


class LLMAPIError(AppException):
    """
    Raised when there is an error communicating with the LLM API.
    """

    def __init__(self, detail: str = "Error communicating with the LLM API."):
        super().__init__(status_code=503, detail=detail)  # 503 Service Unavailable


class LLMResponseError(AppException):
    """
    Raised when the response from the LLM API fails structural or content validation.
    """

    def __init__(self, detail: str = "LLM response validation failed."):
        super().__init__(status_code=502, detail=detail)  # 502 Bad Gateway


class LLMContentError(AppException):
    """
    Raised when the generated content fails task-specific validation.
    """

    def __init__(self, detail: str = "Generated content validation failed."):
        super().__init__(status_code=500, detail=detail)


class DatabaseError(AppException):
    """
    Raised for database-related errors, wrapping underlying SQLAlchemy exceptions.
    """

    def __init__(self, detail: str = "A database error occurred."):
        super().__init__(status_code=500, detail=detail)


class ValidationError(AppException):
    """
    Raised when input data validation fails.
    """

    def __init__(self, detail: str = "Invalid input data."):
        super().__init__(status_code=422, detail=detail)  # 422 Unprocessable Entity
