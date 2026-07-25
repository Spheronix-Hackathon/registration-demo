from slowapi import Limiter
from slowapi.util import get_remote_address

# Fix H-02: Global rate limiter instance
limiter = Limiter(key_func=get_remote_address)
