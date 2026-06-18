"""
EVA — Servidor de Atendimento em Tempo Real
Envio CRED + SuperSim Multiplik
Versão 2.0 — com voz (ElevenLabs) + IA (Groq)
"""

from flask import Flask, request, jsonify
import requests
import os
import json
import random
import tempfile
from datetime import datetime
import pytz

app = Flask(__name__)

# ── Configurações ──────────────────────────────────────────────
EVOLUTION_API_URL  = os.environ.get("EVOLUTION_API_URL", "https://evolution-api-production-08787.up.railway.app")
EVOLUTION_API_KEY  = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "enviocred2")
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

# Voz da Eva — Carolina (brasileira, confiante, conversacional)
EVA_VOICE_ID = "4NRXT5DGqWzIcL6iVqtF"

# Geladeira — contatos bloqueados
GELADEIRA = ["vera", "sandra", "breno"]

# Link SuperSim
SUPERSIM_LINK = "susim.co/7+peoHFiNQsn8C1qFl0tCA=="

# Memória de conversas {numero: {"historico": [], "primeiro_contato": bool}}
conversas = {}

# ── Horário de funcionamento ───────────────────────────────────
def dentro_do_horario():
    tz = pytz.timezone("America/Sao_Paulo")
    now = datetime.now(tz)
    if now.weekday() == 6:  # Domingo
        return False
    if now.hour < 7 or now.hour >= 20:
        return False
    return True

MENSAGEM_FORA_HORARIO = (
    "Oi! 😊 Nosso atendimento funciona de segunda a sábado, das 7h às 20h. "
    "Deixa sua mensagem aqui e te respondemos assim que abrir! 🙏 — Envio CRED"
)

# ── Enviar TEXTO via Evolution API ────────────────────────────
def enviar_texto(numero, texto):
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"number": numero, "text": texto}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[EVA] Erro ao enviar texto: {e}")
        return False

# ── Gerar áudio via ElevenLabs ────────────────────────────────
def gerar_audio(texto):
    """Gera áudio MP3 com a voz da Carolina e retorna bytes."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{EVA_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.3,
            "use_speaker_boost": True
        }
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        if r.status_code == 200:
            return r.content  # bytes do MP3
        else:
            print(f"[EVA] ElevenLabs erro: {r.status_code} {r.text[:200]}")
            return None
    except Exception as e:
        print(f"[EVA] Erro ElevenLabs: {e}")
        return None

# ── Enviar ÁUDIO via Evolution API ────────────────────────────
def enviar_audio(numero, audio_bytes):
    """Envia áudio via base64 para o WhatsApp."""
    import base64
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    url = f"{EVOLUTION_API_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {
        "number": numero,
        "mediatype": "audio",
        "mimetype": "audio/mpeg",
        "media": audio_b64,
        "fileName": "eva_audio.mp3"
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[EVA] Erro ao enviar áudio: {e}")
        return False

# ── Gerar resposta via Groq ────────────────────────────────────
def gerar_resposta(mensagem_cliente, numero_cliente, historico):
    system_prompt = """Você é Simone, agente de atendimento da Envio CRED.

IDENTIDADE:
- Nome: Simone
- Empresa: Envio CRED — correspondente de crédito
- Tom: simpático, humano, caloroso, nunca robótico

REGRAS ABSOLUTAS — NUNCA VIOLE:
- NUNCA prometa aprovação de empréstimo
- NUNCA informe taxa ou valor sem dizer "vou verificar"
- NUNCA gere PIX ou dados bancários
- NUNCA revele comissões ou estratégias internas
- Se valor > R$100, sempre diga: "vou verificar com o gerente"

FLUXO DE ATENDIMENTO:
1. Recepcionar com calor humano
2. Perguntar: nome completo, valor desejado, se tem renda, se consegue comprovar
3. Se perfil OK → "Vou verificar, já te retorno! 🔍"
4. Se Envio CRED não puder ajudar → avaliar SuperSim:
   - Tem renda (formal ou informal)?
   - Consegue comprovar?
   - Valor compatível (até 30% da renda)?
   - Se sim → "Temos uma opção especial! Acesse: susim.co/7+peoHFiNQsn8C1qFl0tCA=="
5. Se nenhum serve → recusa gentil e orientação

GELADEIRA — se cliente mencionar esses nomes, ignorar silenciosamente:
- Vera, Sandra, Breno

HORÁRIO: Segunda a sábado, 07h às 20h (Brasília)

IMPORTANTE:
- Respostas curtas e naturais (máx 3 frases por vez)
- Use emojis com moderação
- Português brasileiro informal
- Nunca mencione que é IA ou robô"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(historico[-10:])  # Últimas 10 mensagens
    messages.append({"role": "user", "content": mensagem_cliente})

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": 300,
        "temperature": 0.7
    }

    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=15
        )
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[EVA] Erro Groq: {e}")
        return "Oi! 😊 Já estou verificando, te retorno em instantes! 🙏"

# ── Webhook principal ──────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "ignored"}), 200

        event = data.get("event", "")

        # Só processa mensagens recebidas
        if event != "messages.upsert":
            return jsonify({"status": "ignored"}), 200

        msg_data = data.get("data", {})
        key = msg_data.get("key", {})

        # Ignorar mensagens enviadas por nós
        if key.get("fromMe", False):
            return jsonify({"status": "ignored"}), 200

        remote_jid = key.get("remoteJid", "")
        numero_cliente = remote_jid.replace("@s.whatsapp.net", "").replace("@g.us", "")

        # Ignorar grupos
        if "@g.us" in remote_jid:
            return jsonify({"status": "ignored"}), 200

        # Extrair texto
        message = msg_data.get("message", {})
        texto_recebido = (
            message.get("conversation") or
            message.get("extendedTextMessage", {}).get("text") or
            "[mídia recebida]"
        )

        push_name = msg_data.get("pushName", "") or ""
        nome_lower = push_name.lower()

        print(f"[EVA] De: {push_name} ({numero_cliente}): {texto_recebido}")

        # ── Geladeira ─────────────────────────────────────────
        for bloqueado in GELADEIRA:
            if bloqueado in nome_lower:
                print(f"[EVA] {push_name} está na geladeira. Ignorando.")
                return jsonify({"status": "geladeira"}), 200

        # ── Fora do horário ───────────────────────────────────
        if not dentro_do_horario():
            enviar_texto(numero_cliente, MENSAGEM_FORA_HORARIO)
            return jsonify({"status": "fora_horario"}), 200

        # ── Histórico e estado do cliente ─────────────────────
        if numero_cliente not in conversas:
            conversas[numero_cliente] = {"historico": [], "primeiro_contato": True}

        estado = conversas[numero_cliente]
        historico = estado["historico"]
        primeiro_contato = estado["primeiro_contato"]

        # ── Verificar se cliente pediu áudio ──────────────────
        pediu_audio = any(p in texto_recebido.lower() for p in [
            "áudio", "audio", "voz", "fala", "falar", "grave", "manda um áudio"
        ])

        # ── Gerar resposta via Groq ───────────────────────────
        resposta_texto = gerar_resposta(texto_recebido, numero_cliente, historico)

        # Atualizar histórico
        historico.append({"role": "user", "content": texto_recebido})
        historico.append({"role": "assistant", "content": resposta_texto})
        if len(historico) > 20:
            conversas[numero_cliente]["historico"] = historico[-20:]

        # ── Decidir: áudio ou texto ───────────────────────────
        usar_audio = primeiro_contato or pediu_audio

        if usar_audio and ELEVENLABS_API_KEY:
            audio_bytes = gerar_audio(resposta_texto)
            if audio_bytes:
                sucesso = enviar_audio(numero_cliente, audio_bytes)
                if sucesso:
                    conversas[numero_cliente]["primeiro_contato"] = False
                    print(f"[EVA] Áudio enviado para {numero_cliente}")
                    return jsonify({"status": "ok", "tipo": "audio"}), 200
            # Fallback para texto se áudio falhar
            print("[EVA] Falha no áudio, enviando texto como fallback")

        # Enviar como texto
        enviar_texto(numero_cliente, resposta_texto)
        conversas[numero_cliente]["primeiro_contato"] = False
        print(f"[EVA] Texto enviado para {numero_cliente}: {resposta_texto[:80]}...")

        return jsonify({"status": "ok", "tipo": "texto"}), 200

    except Exception as e:
        print(f"[EVA] Erro geral: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/", methods=["GET"])
def health():
    tz = pytz.timezone("America/Sao_Paulo")
    now = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
    return jsonify({
        "status": "Eva online 🤖",
        "horario_funcionamento": dentro_do_horario(),
        "agora": now,
        "groq": bool(GROQ_API_KEY),
        "elevenlabs": bool(ELEVENLABS_API_KEY)
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
