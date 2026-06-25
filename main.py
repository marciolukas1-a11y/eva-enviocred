"""
EVA — Servidor de Atendimento em Tempo Real
Envio CRED + SuperSim Multiplik
Versao 4.2 — 24h/7d | Correções de fluxo: abordagem, privacidade, tom
Atualizado: 25/06/2026
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
import random
import tempfile
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)
CORS(app)

EVOLUTION_API_URL  = os.environ.get("EVOLUTION_API_URL", "https://evolution-api-production-08787.up.railway.app")
EVOLUTION_API_KEY  = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "enviocred2")
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

EVA_VOICE_ID = "4NRXT5DGqWzIcL6iVqtF"

GELADEIRA = ["vera", "sandra", "breno"]

CONTATOS_VIP = {
    "5511000000000": "Crefisa",
}

def eh_contato_vip(numero):
    for num_vip, nome_vip in CONTATOS_VIP.items():
        if numero.endswith(num_vip[-8:]):
            return nome_vip
    return None

MARCIO_NUMBERS = ['5583999628152', '558399628152', '5583991144899', '558391144899']

TABELA_OFICIAL = [
    {"nc": 1, "v": 50},  {"nc": 2, "v": 80},  {"nc": 3, "v": 100},
    {"nc": 4, "v": 150}, {"nc": 5, "v": 200}, {"nc": 6, "v": 300},
    {"nc": 7, "v": 400}, {"nc": 8, "v": 500},
]

def calcular_operacao(nome, valor, taxa=20, prazo=30, num_contrato=1):
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
            f"Oi {primeiro_nome}! 😊 Analisei aqui com cuidado, mas infelizmente não consegui liberar o crédito desta vez.\n\n"
            f"Não desanima! Quando sua situação financeira mudar, pode voltar que a gente tenta de novo. 💙\n"
            f"Obrigada pela confiança na Envio CRED! 🙏"
        )
    elif requer_aprovacao:
        status = "AGUARDA_MARCIO"
        script = (
            f"Oi {primeiro_nome}! 😊 Já fiz a análise aqui e as condições estão certas!\n\n"
            f"Valor acima de R$100 — vou confirmar com o responsável e já te retorno! ⏳💙"
        )
    else:
        status = "APROVADA"
        script = (
            f"Oi {primeiro_nome}! 🎉 Tudo certo por aqui!\n\n"
            f"Consigo liberar *R${valor:.2f}* pra você.\n"
            f"O valor a devolver será de *R${total:.2f}* no dia *{vencimento}*.\n\n"
            f"Para finalizar, faz o PIX:\n"
            f"🏦 Banco: Inter\n"
            f"🔑 Chave: *83991144899* (telefone)\n\n"
            f"Me manda o comprovante aqui! 😊💙\n\n*Envio CRED* 💙"
        )

    return {
        "nome": nome, "valor": valor, "taxa": taxa, "total": total,
        "lucro": lucro, "margem": margem, "prazo": prazo,
        "vencimento": vencimento, "erros": erros, "avisos": avisos,
        "status": status, "bloqueado": bloqueado,
        "requer_aprovacao": requer_aprovacao, "script": script,
    }

SUPERSIM_LINK = "susim.co/7+peoHFiNQsn8C1qFl0tCA=="

DASHBOARD_DATA = {"leads": [], "transacoes": [], "socios_arvore": []}

def registrar_no_dashboard(tipo, dados):
    tz = pytz.timezone("America/Sao_Paulo")
    dados["data_registro"] = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
    dados["tipo"] = tipo
    if tipo == "lead":
        existente = next((l for l in DASHBOARD_DATA["leads"] if l.get("telefone") == dados.get("telefone")), None)
        if existente:
            existente.update(dados)
        else:
            DASHBOARD_DATA["leads"].append(dados)
    elif tipo == "transacao":
        DASHBOARD_DATA["transacoes"].append(dados)
    elif tipo == "socio_arvore":
        DASHBOARD_DATA["socios_arvore"].append(dados)
    print(f"[DASHBOARD] {tipo} registrado: {dados.get('nome','?')} | {dados.get('data_registro')}")

conversas = {}

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

def gerar_audio(texto):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{EVA_VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.3, "use_speaker_boost": True}
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        if r.status_code == 200:
            return r.content
        print(f"[EVA] ElevenLabs erro: {r.status_code} {r.text[:200]}")
        return None
    except Exception as e:
        print(f"[EVA] Erro ElevenLabs: {e}")
        return None

def enviar_audio(numero, audio_bytes):
    import base64
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    url = f"{EVOLUTION_API_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {
        "number": numero, "mediatype": "audio", "mimetype": "audio/mpeg",
        "media": audio_b64, "fileName": "eva_audio.mp3"
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[EVA] Erro ao enviar áudio: {e}")
        return False

def extrair_dados_lead(historico):
    import re
    nome, valor, num_contrato = None, None, 1
    for msg in historico:
        texto = msg.get("content", "").lower()
        match_valor = re.search(r'r\$\s*(\d+[\.,]?\d*)|(\d+[\.,]?\d*)\s*reais|quero\s+(\d+)', texto)
        if match_valor:
            v = match_valor.group(1) or match_valor.group(2) or match_valor.group(3)
            if v:
                try:
                    valor = float(v.replace(",", "."))
                except:
                    pass
        if msg.get("role") == "user" and len(texto.split()) <= 5 and not any(c.isdigit() for c in texto):
            candidato = msg["content"].strip()
            if len(candidato) > 3:
                nome = candidato
    return nome, valor, num_contrato

def gerar_resposta(mensagem_cliente, numero_cliente, historico):
    calc_result = None
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
            calc_result = calcular_operacao(nome=nome_lead or "Cliente", valor=valor_lead, taxa=20, prazo=30, num_contrato=nc)
            print(f"[CALC] {nome_lead} | R${valor_lead} | status={calc_result['status']}")
            if calc_result["status"] == "APROVADA":
                registrar_no_dashboard("transacao", {"nome": nome_lead or "Cliente", "produto": "Crédito Pessoal", "valor": valor_lead, "taxa": 20, "total": calc_result["total"], "status": "aprovado"})
                registrar_no_dashboard("lead", {"nome": nome_lead or "Cliente", "telefone": numero_cliente, "produto": "Crédito Pessoal", "valor": valor_lead, "status": "aprovado"})
            elif calc_result["status"] == "AGUARDA_MARCIO":
                registrar_no_dashboard("lead", {"nome": nome_lead or "Cliente", "telefone": numero_cliente, "produto": "Crédito Pessoal", "valor": valor_lead, "status": "aguarda_marcio"})

    calc_inject = ""
    if calc_result:
        if calc_result["status"] == "APROVADA":
            calc_inject = f"\n\n🧮 CALCULADORA — ✅ APROVADA\nValor: R${calc_result['valor']:.2f} | Total: R${calc_result['total']:.2f} | Venc: {calc_result['vencimento']}\nScript:\n---\n{calc_result['script']}\n---\nEnvie o script acima agora."
        elif calc_result["status"] == "AGUARDA_MARCIO":
            calc_inject = f"\n\n🧮 CALCULADORA — ⚠️ AGUARDA MÁRCIO (valor > R$100)\nValor: R${calc_result['valor']:.2f} | Total: R${calc_result['total']:.2f}\nScript:\n---\n{calc_result['script']}\n---\nEnvie e aguarde Márcio liberar."
        elif calc_result["status"] == "BLOQUEADA":
            erros_str = " | ".join(calc_result["erros"])
            calc_inject = f"\n\n🧮 CALCULADORA — ❌ BLOQUEADA\nMotivo: {erros_str}\nNÃO avance. Use o script de recusa gentil e encaminhe ao Super Sim."

    system_prompt = f"""Você é Simone, atendente da Envio CRED. Atende 24 horas por dia, 7 dias por semana.

IDENTIDADE:
- Nome: Simone | Empresa: Envio CRED — correspondente de crédito
- Tom: simpático, humano, caloroso — NUNCA robótico

🚨 REGRAS QUE NUNCA PODEM SER VIOLADAS:
1. NUNCA repita dados sensíveis do cliente (CPF, RG) — apenas confirme: "CPF recebido ✅"
2. NUNCA faça mais de UMA pergunta por mensagem — siga a ordem, uma de cada vez
3. NUNCA use o mesmo emoji duas vezes na mesma mensagem — varie sempre
4. NUNCA diga "não posso prosseguir" ou "não consigo atender" — sempre redirecione com positividade
5. NUNCA repita informações que o cliente já deu — avance direto pro próximo dado
6. NUNCA aprove ou negue crédito sem resultado da Calculadora
7. NUNCA gere ou informe PIX — só use o PIX fixo quando Calculadora APROVAR
8. NUNCA revele comissões ou estratégias internas

📋 FLUXO OBRIGATÓRIO — UMA PERGUNTA POR VEZ:

PASSO 1 — PRIMEIRA ABORDAGEM (cliente chegou do nada ou perguntou "quem é?"):
→ "Oi! Aqui é a Simone, da Envio CRED 😊 Vi que você assistiu nosso vídeo sobre crédito rápido! Posso te ajudar a conseguir o seu empréstimo hoje?"

PASSO 2 — NOME: "Pode me dizer seu nome completo?"

PASSO 3 — VALOR: "Qual valor você precisa, [primeiro nome]?"

PASSO 4 — CPF: "Qual é o seu CPF?"
→ Ao receber: responda apenas "CPF recebido ✅" — JAMAIS repita o número

PASSO 5 — RENDA: "Qual é a sua renda mensal?"

PASSO 6 — RESTRIÇÃO: "Seu nome está limpo ou tem alguma restrição no SPC/Serasa?"

PASSO 7 — ENCAMINHAR:

   A) CPF LIMPO → Calculadora decide (resultado virá abaixo no system prompt)

   B) CPF COM RESTRIÇÃO → Super Sim com tom positivo:
   "Boa notícia, [nome]! 🎉 Tenho um parceiro perfeito pra você que atende mesmo negativado!
   É a Super Sim — processo rápido e sem burocracia, direto pelo celular.
   Acessa aqui e faz seu cadastro: susim.co/7+peoHFiNQsn8C1qFl0tCA==
   Qualquer dúvida é só me chamar! 💙"

📚 DADOS OFICIAIS:
- PIX Envio CRED (só quando Calculadora APROVAR): Banco Inter | Chave 83991144899
- Super Sim: susim.co/7+peoHFiNQsn8C1qFl0tCA==
- Projeto Árvore: https://marciolukas1-a11y.github.io/enviocred-pagamento/contrato-arvore.html

🚫 RECUSA FINAL (só quando Super Sim também negar):
"Oi [nome]! 😊 Fiz tudo que pude aqui e pelo nosso parceiro também, mas no momento não encontramos uma solução.
Não desanima — quando sua situação mudar, pode voltar que a gente tenta de novo. 💙 Conte com a Envio CRED sempre! 🙏"

GELADEIRA — ignorar silenciosamente: Vera, Sandra, Breno

ESTILO: respostas curtas (máx 3 frases), 1 emoji por mensagem no máximo, português informal e caloroso, nunca parecer robótico.

📎 [cliente enviou documento/imagem como comprovante] → "Recebi seu comprovante! ✅" e continue o fluxo.
🎙️ [cliente enviou áudio] → "Oi! Não consigo ouvir áudios aqui, pode me mandar por texto? 😊"{calc_inject}"""

    headers_req = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(historico[-10:])
    messages.append({"role": "user", "content": mensagem_cliente})

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": 300,
        "temperature": 0.7
    }

    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers_req, json=payload, timeout=15)
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[EVA] Erro Groq: {e}")
        return "Oi! 😊 Já estou verificando, te retorno em instantes! 🙏"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "ignored"}), 200

        event = data.get("event", "")
        if event != "messages.upsert":
            return jsonify({"status": "ignored"}), 200

        msg_data = data.get("data", {})
        key = msg_data.get("key", {})

        if key.get("fromMe", False):
            return jsonify({"status": "ignored"}), 200

        remote_jid = key.get("remoteJid", "")
        numero_cliente = remote_jid.replace("@s.whatsapp.net", "").replace("@g.us", "")

        if "@g.us" in remote_jid:
            return jsonify({"status": "ignored"}), 200

        message = msg_data.get("message", {})

        if "reactionMessage" in message or "stickerMessage" in message:
            return jsonify({"status": "ignored"}), 200

        eh_documento = "documentMessage" in message
        eh_imagem = "imageMessage" in message
        eh_audio_cliente = "audioMessage" in message and not key.get("fromMe", False)

        texto_recebido = (
            message.get("conversation") or
            message.get("extendedTextMessage", {}).get("text") or ""
        )

        if eh_documento or eh_imagem:
            tipo = "documento" if eh_documento else "imagem"
            caption = message.get("documentMessage", {}).get("caption") or message.get("imageMessage", {}).get("caption") or ""
            texto_recebido = f"[cliente enviou {tipo} como comprovante] {caption}".strip()

        if eh_audio_cliente:
            texto_recebido = "[cliente enviou áudio]"

        if not texto_recebido.strip():
            return jsonify({"status": "ignored"}), 200

        push_name = msg_data.get("pushName", "") or ""
        nome_lower = push_name.lower()

        print(f"[EVA] De: {push_name} ({numero_cliente}): {texto_recebido}")

        numero_limpo = numero_cliente.replace("+","").replace("-","").replace(" ","")
        if any(numero_limpo.endswith(n[-9:]) or numero_limpo == n for n in MARCIO_NUMBERS):
            return jsonify({"status": "marcio_silencio"}), 200

        nome_vip = eh_contato_vip(numero_cliente)
        if nome_vip:
            msg_vip = f"Mensagem de parceiro/empresa:\nDe: {nome_vip} ({push_name})\nNumero: {numero_cliente}\nMensagem: {texto_recebido}"
            enviar_texto(MARCIO_NUMBERS[0], msg_vip)
            enviar_texto(numero_cliente, "Ola! Sua mensagem foi encaminhada ao responsavel da Envio CRED. Em breve voce recebera um retorno.")
            return jsonify({"status": "vip_encaminhado"}), 200

        for bloqueado in GELADEIRA:
            if bloqueado in nome_lower:
                return jsonify({"status": "geladeira"}), 200

        if numero_cliente not in conversas:
            conversas[numero_cliente] = {"historico": [], "primeiro_contato": True}
            registrar_no_dashboard("lead", {
                "nome": push_name or "Desconhecido",
                "telefone": numero_cliente,
                "produto": "Em qualificação",
                "status": "novo",
                "origem": "WhatsApp (Simone)"
            })

        estado = conversas[numero_cliente]
        historico = estado["historico"]
        primeiro_contato = estado["primeiro_contato"]

        pediu_audio = any(p in texto_recebido.lower() for p in ["áudio", "audio", "voz", "fala", "falar", "grave", "manda um áudio"])

        resposta_texto = gerar_resposta(texto_recebido, numero_cliente, historico)

        historico.append({"role": "user", "content": texto_recebido})
        historico.append({"role": "assistant", "content": resposta_texto})
        if len(historico) > 20:
            conversas[numero_cliente]["historico"] = historico[-20:]

        usar_audio = primeiro_contato or pediu_audio

        if usar_audio and ELEVENLABS_API_KEY:
            audio_bytes = gerar_audio(resposta_texto)
            if audio_bytes:
                sucesso = enviar_audio(numero_cliente, audio_bytes)
                if sucesso:
                    conversas[numero_cliente]["primeiro_contato"] = False
                    return jsonify({"status": "ok", "tipo": "audio"}), 200
            print("[EVA] Falha no áudio, enviando texto como fallback")

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
        "status": "Simone online 24h/7d 🤖",
        "versao": "4.2",
        "agora": now,
        "groq": bool(GROQ_API_KEY),
        "elevenlabs": bool(ELEVENLABS_API_KEY),
        "endpoints": ["/webhook", "/dashboard/dados", "/dashboard/lead", "/dashboard/socio"]
    }), 200

@app.route("/dashboard/dados", methods=["GET"])
def dashboard_dados():
    return jsonify({
        "leads": DASHBOARD_DATA["leads"],
        "transacoes": DASHBOARD_DATA["transacoes"],
        "socios_arvore": DASHBOARD_DATA["socios_arvore"],
        "totais": {
            "leads": len(DASHBOARD_DATA["leads"]),
            "transacoes": len(DASHBOARD_DATA["transacoes"]),
            "socios_arvore": len(DASHBOARD_DATA["socios_arvore"]),
            "receita": sum(t.get("total", 0) - t.get("valor", 0) for t in DASHBOARD_DATA["transacoes"] if t.get("status") == "aprovado")
        }
    }), 200

@app.route("/dashboard/lead", methods=["POST"])
def dashboard_lead():
    dados = request.json or {}
    registrar_no_dashboard("lead", dados)
    return jsonify({"status": "ok"}), 200

@app.route("/dashboard/socio", methods=["POST"])
def dashboard_socio():
    dados = request.json or {}
    registrar_no_dashboard("socio_arvore", dados)
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
