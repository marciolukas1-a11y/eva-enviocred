
import requests

def testar_conexao():
    print("Luna testando conexao com eva-server...")
    try:
        response = requests.get("https://eva-server-production-3c09.up.railway.app")
        print("Conexao OK:", response.status_code)
        return True
    except Exception as e:
        print("Erro:", e)
        return False

if __name__ == "__main__":
    testar_conexao()
