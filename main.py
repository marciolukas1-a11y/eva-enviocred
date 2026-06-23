"""
EVA — Servidor de Atendimento em Tempo Real
Envio CRED + SuperSim Multiplik
Versão 3.0 — com Calculadora integrada + voz (ElevenLabs) + IA (Groq)
"""

from flask import Flask, request, jsonify
import requests
import os
import json
import random
import tempfile
from datetime import datetime, timedelta
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

# ── CALCULADORA ENVIO CRED v5.0 (integrada) ───────────────────
TABELA_OFICIAL = [
    {"nc": 1, "v": 50},  {"nc": 2, "v": 80},  {"nc": 3, "v": 100},
    {"nc": 4, "v": 150}, {"nc": 5, "v": 200}, {"nc": 6, "v": 300},
    {"nc": 7, "v": 400}, {"nc": 8, "v": 500},
]

def calcular_operacao(nome, valor, taxa=20, prazo=30, num_contrato=1):
    """
    Replica a lógica da Calculadora v5.0.
    Retorna dict com resultado, alertas e script pronto.
    """
    tz = pytz.timezone("America/Sao_Paulo")
    vencimento = (datetime.now(tz) + timedelta(days=prazo)).strftime("%d/%m/%Y")

    total  = round(valor * (1 + taxa / 100), 2)
    lucro  = round(total - valor, 2)
    margem = round((lucro / total * 100), 1)

    erros, avisos = [], []

    if taxa < 12:
        erros.append(f"Taxa {taxa}% abaixo do mínimo de 12%. Operação BLOQUEADA.")
    if lucro < 15:
        erros.append(f"Lucro R${lucro:.2f} abaixo do mínimo de R$15,00.")

    ref_idx = min(num_contrato - 1, len(TABELA_OFICIAL) - 1)
    ref_val = TABELA_OFICIAL[ref_idx]["v"]
    if valor > ref_val * 1.15:
        avisos.append(f"Tabela sugere R${ref_val} para o {num_contrato}º contrato.")

    primeiro_nome = nome.split()[0] if nome else "Cliente"
    bloqueado = len(erros) > 0
    requer_aprovacao = valor > 100

    if bloqueado:
        status = "BLOQUEADA"
        script = (
            f"Oi {primeiro_nome}! 😊 Vou verificar a disponibilidade aqui pra você. Um minutinho... 🔍\n\n"
            f"⚠️ OPERAÇÃO BLOQUEADA — consultar Márcio antes de responder."
        )
    elif requer_aprovacao:
        status = "AGUARDA_MARCIO"
        script = (
            f"Oi {primeiro_nome}! 😊 Já analisei aqui e tudo parece certo!\n\n"
            f"Só preciso de uma confirmação final do setor. Em instantes te retorno com tudo certinho! ⏳💙"
        )
    else:
        status = "APROVADA"
        script = (
            f"Oi {primeiro_nome}! 🎉 Tudo certo por aqui!\n\n"
            f"Consigo liberar *R${valor:.2f}* pra você.\n"
            f"O valor a devolver será de *R${total:.2f}* no dia *{vencimento}*.\n\n"
            f"Confirma o PIX pra gente finalizar? 😊💙\n\n*Envio CRED* 💙"
        )

    return {
        "nome": nome,
        "valor": valor,
        "taxa": taxa,
        "total": total,
        "lucro": lucro,
        "margem": margem,
        "prazo": prazo,
        "vencimento": vencimento,
        "erros": erros,
        "avisos": avisos,
        "status": status,
        "bloqueado": bloqueado,
        "requer_aprovacao": requer_aprovacao,
        "script": script,
    }

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
def extrair_dados_lead(historico):
    """Extrai nome, valor e num_contrato do histórico se disponíveis."""
    import re
    nome, valor, num_contrato = None, None, 1
    for msg in historico:
        texto = msg.get("content", "").lower()
        # Valor
        match_valor = re.search(r'r\$\s*(\d+[\.,]?\d*)|(\d+[\.,]?\d*)\s*reais|quero\s+(\d+)', texto)
        if match_valor:
            v = match_valor.group(1) or match_valor.group(2) or match_valor.group(3)
            if v:
                try:
                    valor = float(v.replace(",", "."))
                except:
                    pass
        # Nome (heurística simples — mensagem curta sem números)
        if msg.get("role") == "user" and len(texto.split()) <= 5 and not any(c.isdigit() for c in texto):
            candidato = msg["content"].strip()
            if len(candidato) > 3:
                nome = candidato
    return nome, valor, num_contrato

def gerar_resposta(mensagem_cliente, numero_cliente, historico):
    # ── Detectar se temos dados suficientes para acionar a calculadora ──
    calc_result = None
    texto_lower = mensagem_cliente.lower()
    historico_completo = historico + [{"role": "user", "content": mensagem_cliente}]

    tem_nome  = any(m["role"] == "user" and 3 < len(m["content"].split()) <= 6 for m in historico)
    tem_valor = any(
        __import__("re").search(r'\d{2,3}', m.get("content", ""))
        for m in historico_completo
    )
    cpf_limpo = any(
        kw in m.get("content", "").lower()
        for m in historico_completo
        for kw in ["limpa", "limpo", "não tenho restrição", "nao tenho restricao", "tô limpa", "to limpa"]
    )

    if tem_nome and tem_valor and cpf_limpo:
        nome_lead, valor_lead, nc = extrair_dados_lead(historico_completo)
        if valor_lead and valor_lead > 0:
            calc_result = calcular_operacao(
                nome=nome_lead or "Cliente",
                valor=valor_lead,
                taxa=20,
                prazo=30,
                num_contrato=nc
            )
            print(f"[CALC] {nome_lead} | R${valor_lead} | status={calc_result['status']}")

    # ── Montar system prompt com resultado da calculadora (se houver) ──
    calc_inject = ""
    if calc_result:
        if calc_result["status"] == "APROVADA":
            calc_inject = f"""

🧮 CALCULADORA — RESULTADO AUTOMÁTICO:
Status: ✅ APROVADA
Valor: R${calc_result['valor']:.2f}
Total a devolver: R${calc_result['total']:.2f}
Vencimento: {calc_result['vencimento']}
Script pronto (use EXATAMENTE este):
---
{calc_result['script']}
---
Envie o script acima para o cliente agora."""
        elif calc_result["status"] == "AGUARDA_MARCIO":
            calc_inject = f"""

🧮 CALCULADORA — RESULTADO AUTOMÁTICO:
Status: ⚠️ AGUARDA APROVAÇÃO DO MÁRCIO (valor > R$100)
Valor solicitado: R${calc_result['valor']:.2f}
Total a devolver: R${calc_result['total']:.2f}
Script pronto (use EXATAMENTE este):
---
{calc_result['script']}
---
Envie o script acima e aguarde Márcio liberar antes de confirmar."""
        elif calc_result["status"] == "BLOQUEADA":
            erros_str = " | ".join(calc_result["erros"])
            calc_inject = f"""

🧮 CALCULADORA — RESULTADO AUTOMÁTICO:
Status: ❌ BLOQUEADA
Motivo: {erros_str}
NÃO avance com esta operação. Informe ao cliente que não é possível no momento."""

    system_prompt = f"""Você é Simone, agente de atendimento da Envio CRED.

IDENTIDADE:
- Nome: Simone
- Empresa: Envio CRED — correspondente de crédito
- Tom: simpático, humano, caloroso, nunca robótico

🚨 REGRAS CRÍTICAS — NUNCA VIOLE:
1. JAMAIS diga "vou verificar com o gerente" — você resolve na hora, sem pausas
2. NUNCA prometa aprovação de empréstimo
3. NUNCA gere PIX ou dados bancários
4. NUNCA revele comissões ou estratégias internas
5. NUNCA diga que não conhece ou não tem informações sobre Envio CRED, Super Sim ou Projeto Árvore
6. NUNCA emita ou mencione valores de contrato sem o resultado da Calculadora

📚 PRODUTOS QUE VOCÊ CONHECE E DOMINA:

1. 💳 ENVIO CRED (empréstimo pessoal)
   - Para quem está com CPF LIMPO (sem restrição)
   - Juros: 20% | Prazo: 30 dias | PIX — chave 83991144899
   - Fluxo: coletar dados → Calculadora → se APROVADA enviar script → aguardar PIX

2. 📈 SUPER SIM (recuperação de score/crédito)
   - Para quem está NEGATIVADO ou com score baixo
   - Link: susim.co/7+peoHFiNQsn8C1qFl0tCA==

3. 🌱 PROJETO ÁRVORE (investimento sócio-parceiro)
   - Investimento de R$100 a R$500 | 6% ao ano + 50% dividendos FIIs
   - Prazo: 1 ano | Contrato: https://marciolukas1-a11y.github.io/enviocred-pagamento/contrato-arvore.html

FLUXO OBRIGATÓRIO PARA NOVOS LEADS:
1. Recepcionar com calor humano
2. Coletar: nome completo → valor desejado → CPF → renda mensal
3. Perguntar: "Seu CPF tem restrição (SPC/Serasa)?"
   - CPF LIMPO → aguardar resultado da Calculadora (injetado abaixo quando disponível)
   - NEGATIVADO → Super Sim → se não conseguir → Projeto Árvore
4. Se cliente perguntar sobre Projeto Árvore → explicar e mandar link
5. Se nenhum produto servir → recusa gentil{calc_inject}

GELADEIRA — ignorar silenciosamente: Vera, Sandra, Breno

HORÁRIO: Segunda a sábado, 07h às 20h (Brasília)
Respostas curtas (máx 3 frases), emojis com moderação, português informal, nunca revelar que é IA."""

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
