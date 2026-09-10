class HandoverError(Exception):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class InputError(HandoverError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 2)


class MediaError(HandoverError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 3)


class TranscriptionError(HandoverError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 4)


class CheckpointError(HandoverError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 5)


class OutputError(HandoverError):
    def __init__(self, message: str) -> None:
        super().__init__(message, 5)
