
"""
Teste de conexao com fal.ai
Gera uma imagem simples para confirmar que a chave FAL_API_KEY esta funcionando.
"""

import os
import requests

def testar_conexao_fal():
    api_key = os.environ.get("FAL_API_KEY")

    if not api_key:
        return "ERRO: variavel FAL_API_KEY nao encontrada no ambiente."

    url = "https://fal.run/fal-ai/flux/schnell"
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": "uma lua dourada e prateada sobre um fundo roxo escuro, estilo minimalista",
        "image_size": "square"
    }

    try:
        resposta = requests.post(url, headers=headers, json=payload, timeout=30)
        if resposta.status_code == 200:
            dados = resposta.json()
            imagem_url = dados.get("images", [{}])[0].get("url", "URL nao encontrada")
            return f"SUCESSO! Imagem gerada: {imagem_url}"
        else:
            return f"ERRO {resposta.status_code}: {resposta.text}"
    except Exception as e:
        return f"ERRO de conexao: {str(e)}"


if __name__ == "__main__":
    resultado = testar_conexao_fal()
    print(resultado)
