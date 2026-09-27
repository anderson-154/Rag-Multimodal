# backend/src/domain/exceptions.py
class DomainError(Exception):
    pass


class DocumentNotFoundError(DomainError):
    pass


class JobNotFoundError(DomainError):
    pass


class InvalidJobTransitionError(DomainError):
    pass


class UnsupportedFileTypeError(DomainError):
    pass


class LLMUnavailableError(DomainError):
    pass


class VectorStoreError(DomainError):
    pass


class ParsingError(DomainError):
    pass
