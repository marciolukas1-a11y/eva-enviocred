"""
WSGI middleware para CORS — versao corrigida (bugfix Luna 27/06/2026)
Substituiu o middleware que causava headers CORS duplicados.
Agora delega 100% para o after_request do Flask (main.py).
"""
from main import app

# O Flask em main.py ja gerencia CORS via @app.after_request
# Este arquivo existe apenas para compatibilidade com o Procfile
# Nao adicionar headers CORS aqui para evitar duplicatas
