"""独自例外クラス"""


class DynamoDBError(Exception):
    """DynamoDB 操作失敗時に発生する独自例外"""

    def __init__(self, message: str, original: Exception = None):
        super().__init__(message)
        self.original = original


class BedrockError(Exception):
    """Bedrock API 呼び出し失敗時に発生する独自例外"""

    def __init__(self, message: str, original: Exception = None):
        super().__init__(message)
        self.original = original


class GoogleCalendarError(Exception):
    """Google Calendar API 呼び出し失敗時に発生する独自例外"""

    def __init__(self, message: str, original: Exception = None):
        super().__init__(message)
        self.original = original


class LineServiceError(Exception):
    """LINE API 呼び出し失敗時に発生する独自例外"""

    def __init__(self, message: str, original: Exception = None):
        super().__init__(message)
        self.original = original


class SecretsError(Exception):
    """Secrets Manager 取得失敗時に発生する独自例外"""

    def __init__(self, message: str, original: Exception = None):
        super().__init__(message)
        self.original = original
