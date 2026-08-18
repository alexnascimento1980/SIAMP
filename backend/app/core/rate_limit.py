from slowapi import Limiter
from slowapi.util import get_remote_address

# Limiter compartilhado pela aplicação. Por padrão, limita por IP de origem.
# Usado principalmente para mitigar força bruta em /auth/login.
limiter = Limiter(key_func=get_remote_address)
