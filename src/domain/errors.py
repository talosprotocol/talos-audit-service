class DomainError(Exception):
    """Base class for domain exceptions."""
    pass

class ValidationError(DomainError):
    """Raised when domain validation fails."""
    pass

class NotFoundError(DomainError):
    """Raised when a resource is not found."""
    pass

class ConflictError(DomainError):
    """Raised when there is a conflict (e.g., duplicate ID)."""
    pass
