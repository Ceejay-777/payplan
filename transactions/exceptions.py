class NombaConnectionError(Exception):
    """Raised when we couldn't confirm the outcome — network/timeout, ambiguous."""
    pass

class NombaTransferRejected(Exception):
    """Raised when Nomba gave a definitive rejection — safe to treat as failed."""
    pass