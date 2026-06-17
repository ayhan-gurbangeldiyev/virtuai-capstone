"""Custom exceptions for Type Hype backend."""


class AccountBrokenError(Exception):
    """Twitter cookie/token süresi dolmuş veya geçersiz.
    
    Fırlatıldığında middleware hesabı otomatik olarak 'broken' işaretler
    ve frontend'e ACCOUNT_BROKEN kodu döner.
    """
    def __init__(self, platform: str = "twitter", reason: str = "Token süresi dolmuş"):
        self.platform = platform
        self.reason = reason
        super().__init__(f"{platform}: {reason}")
