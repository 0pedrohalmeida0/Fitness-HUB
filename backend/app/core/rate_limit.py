"""
Rate limiter global (slowapi).
Importado por main.py (registra handler) e pelos routers que aplicam limites.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Instância única — key por IP remoto
limiter = Limiter(key_func=get_remote_address)
