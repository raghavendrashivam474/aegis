"""Domain-specific exceptions for Aegis."""


class DomainError(Exception):
    """Base class for all Aegis domain exceptions."""


class DuplicateEntityError(DomainError):
    """Raised when an entity with a duplicate ID is added."""


class EntityNotFoundError(DomainError):
    """Raised when a referenced entity cannot be found."""


class InvariantViolationError(DomainError):
    """Raised when an operation would violate domain model integrity."""
