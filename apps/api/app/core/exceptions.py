from typing import Any, Optional
from fastapi import HTTPException, status

class LeadNexusException(HTTPException):
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "BAD_REQUEST",
        message: str = "An error occurred.",
        details: Optional[Any] = None
    ):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details

class AuthenticationError(LeadNexusException):
    def __init__(self, message: str = "Invalid email or password.", code: str = "AUTH_INVALID_CREDENTIALS"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=code,
            message=message
        )

class PermissionDeniedError(LeadNexusException):
    def __init__(self, message: str = "You do not have permission to perform this action.", code: str = "PERMISSION_DENIED"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code=code,
            message=message
        )

class TenantAccessDeniedError(LeadNexusException):
    def __init__(self, message: str = "Access to the requested organization or workspace was denied.", code: str = "TENANT_ACCESS_DENIED"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code=code,
            message=message
        )

class NotFoundError(LeadNexusException):
    def __init__(self, message: str = "Resource not found.", code: str = "NOT_FOUND"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code=code,
            message=message
        )

class ConflictError(LeadNexusException):
    def __init__(self, message: str = "A resource with this identifier already exists.", code: str = "CONFLICT"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code=code,
            message=message
        )



class ValidationError(LeadNexusException):
    def __init__(self, message: str = 'Validation failed.', code: str = 'VALIDATION_ERROR', details: Optional[Any] = None):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, code=code, message=message, details=details)

AuthenticationException = AuthenticationError
PermissionDeniedException = PermissionDeniedError
TenantAccessDeniedException = TenantAccessDeniedError
ResourceNotFoundException = NotFoundError
ConflictException = ConflictError
ValidationException = ValidationError
