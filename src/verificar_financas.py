
import requests
from datetime import datetime

def verificar_pagina_financas():
    url = "https://marciolukas1-a11y.github.io/enviocred-financas/"
    try:
        response = requests.get(url, timeout=10)
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        if response.status_code == 200:
            return f"Pagina de financas esta ONLINE. Verificado em: {agora}"
        else:
            return f"Pagina respondeu com erro {response.status_code}. Verificado em: {agora}"
    except Exception as e:
        return f"Pagina INDISPONIVEL. Erro: {e}"

if __name__ == "__main__":
    resultado = verificar_pagina_financas()
    print(resultado)
