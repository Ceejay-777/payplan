class NombaBankLookupError(Exception):
    """Raised when Nomba's bank-account lookup returns a definitive rejection
    or a malformed response. Distinct from NombaConnectionError (which signals
    that we couldn't reach Nomba at all) so callers can decide whether the
    failure is retryable.
    """
