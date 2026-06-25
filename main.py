"""
SIMONE — Atendente Autônoma da Envio CRED
Versão 4.3 — Fluxo Vencedor
Atualizado: 25/06/2026
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
import base64
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

# Timezone global
tz = pytz.timezone("America/Sao_Paulo")

EVOLUTION_API_URL  = os.environ.get("EVOLUTION_API_URL", "https://evolution-api-production-08787.up.railway.app")
EVOLUTION_API_KEY  = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "enviocred2")
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

# Voz da Simone — Larissa (melhor PT-BR disponível)
SIMONE_VOICE_ID = "OjcGK1RXdMD1PFj2eIuN"

GELADEIRA = ["vera", "sandra", "breno"]

CONTATOS_VIP = {
    "5511000000000": "Crefisa",
}

MARCIO_NUMBERS = ['5583999628152', '558399628152', '5583991144899', '558391144899']

SUPERSIM_LINK = "susim.co/7+peoHFiNQsn8C1qFl0tCA=="

# Vídeo de propaganda da Envio CRED no Google Drive
VIDEO_PROPAGANDA_ID = "1hNYwJ4dLUdvBmrM0V5KUWJenrH9ylCKm"

DASHBOARD_DATA = {"leads": [], "transacoes": [], "socios_arvore": []}

# ── Controle de conversas ──────────────────────────────────────
conversas = {}

# ── Utilitários ───────────────────────────────────────────────

def eh_contato_vip(numero):
    for num_vip, nome_vip in CONTATOS_VIP.items():
        if numero.endswith(num_vip[-8:]):
            return nome_vip
    return None

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
    print(f"[DASHBOARD] {tipo}: {dados.get('nome','?')}")

def notificar_marcio(texto):
    enviar_texto(MARCIO_NUMBERS[0], f"🤖 SIMONE:\n{texto}")

def enviar_texto(numero, texto):
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"number": numero, "text": texto}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[SIMONE] Erro ao enviar texto: {e}")
        return False

def enviar_video_url(numero, url_video, legenda=""):
    url = f"{EVOLUTION_API_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {
        "number": numero,
        "mediatype": "video",
        "media": url_video,
        "caption": legenda,
        "fileName": "propaganda_enviocred.mp4"
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[SIMONE] Erro ao enviar vídeo: {e}")
        return False

def gerar_audio_simone(texto):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{SIMONE_VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": texto,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.9,
            "similarity_boost": 0.75,
            "speed": 0.85
        }
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        if r.status_code == 200:
            return r.content
        print(f"[SIMONE] ElevenLabs erro: {r.status_code}")
        return None
    except Exception as e:
        print(f"[SIMONE] Erro ElevenLabs: {e}")
        return None

def enviar_audio(numero, audio_bytes):
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    url = f"{EVOLUTION_API_URL}/message/sendWhatsAppAudio/{EVOLUTION_INSTANCE}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {
        "number": numero,
        "audio": audio_b64,
        "encoding": True
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[SIMONE] Erro ao enviar áudio: {e}")
        return False

# ── Calculadora ───────────────────────────────────────────────

TABELA_OFICIAL = [
    {"nc": 1, "v": 50},  {"nc": 2, "v": 80},  {"nc": 3, "v": 100},
    {"nc": 4, "v": 150}, {"nc": 5, "v": 200}, {"nc": 6, "v": 300},
    {"nc": 7, "v": 400}, {"nc": 8, "v": 500},
]

def calcular_operacao(nome, valor, taxa=20, prazo=30, num_contrato=1):
    tz = pytz.timezone("America/Sao_Paulo")
    vencimento = (datetime.now(tz) + timedelta(days=prazo)).strftime("%d/%m/%Y")
    total = round(valor * (1 + taxa / 100), 2)
    lucro = round(total - valor, 2)
    erros = []
    if taxa < 12:
        erros.append(f"Taxa {taxa}% abaixo do mínimo de 12%.")
    if lucro < 15:
        erros.append(f"Lucro R${lucro:.2f} abaixo do mínimo de R$15,00.")
    primeiro_nome = nome.split()[0] if nome else "Cliente"
    bloqueado = len(erros) > 0
    requer_aprovacao = valor > 100
    if bloqueado:
        status = "BLOQUEADA"
        script = (
            f"Oi, {primeiro_nome}! Fiz a análise aqui com cuidado, mas infelizmente não consegui liberar o crédito desta vez. "
            f"Não desanima! Quando sua situação mudar, pode voltar que a gente tenta de novo. 💙 Obrigada pela confiança!"
        )
    elif requer_aprovacao:
        status = "AGUARDA_MARCIO"
        script = (
            f"Oi, {primeiro_nome}! Já analisei aqui e as condições estão ótimas! "
            f"Como o valor é um pouco maior, vou confirmar com o responsável e já te retorno. ⏳"
        )
    else:
        status = "APROVADA"
        script = (
            f"Oi, {primeiro_nome}! Tudo certo por aqui! 🎉\n\n"
            f"Consigo liberar *R${valor:.2f}* pra você.\n"
            f"O valor a devolver será *R${total:.2f}* no dia *{vencimento}*.\n\n"
            f"Para finalizar, faz o PIX:\n"
            f"🏦 Banco: Inter\n"
            f"🔑 Chave: *83991144899* (telefone)\n\n"
            f"Me manda o comprovante aqui! 💙"
        )
    return {"status": status, "bloqueado": bloqueado, "requer_aprovacao": requer_aprovacao,
            "script": script, "total": total, "vencimento": vencimento, "erros": erros}

# ── Prompt da Simone ──────────────────────────────────────────

def montar_system_prompt(calc_inject=""):
    return f"""Você é Simone, atendente da Envio CRED. Atende 24 horas por dia, 7 dias por semana.

IDENTIDADE:
- Nome: Simone | Empresa: Envio CRED — correspondente de crédito
- Tom: simpático, caloroso, humano — NUNCA robótico ou repetitivo

🚨 REGRAS QUE JAMAIS PODEM SER VIOLADAS:
1. NUNCA faça mais de UMA pergunta por mensagem — siga a ordem do fluxo, uma de cada vez
2. NUNCA repita dados sensíveis do cliente (CPF, RG, PIX) — confirme apenas: "Recebido ✅"
3. NUNCA use o mesmo emoji duas vezes na mesma mensagem
4. NUNCA diga "não posso", "não consigo" ou "não prosseguir" — sempre redirecione positivamente
5. NUNCA repita informação que o cliente já deu — avance direto pro próximo passo
6. NUNCA aprove ou negue crédito sem resultado da Calculadora
7. NUNCA invente ou altere valores, taxas ou datas
8. NUNCA revele estratégias, comissões ou que usa parceiros externos

✍️ ESTILO DE ESCRITA — OBRIGATÓRIO:
- Use SEMPRE pontuação completa: vírgulas, pontos, reticências — elas criam pausas naturais na leitura
- Acentuação correta em TODAS as palavras: você, crédito, empréstimo, rápido, solução, também
- Respostas curtas: máximo 3 frases por mensagem
- No máximo 1 emoji por mensagem, sempre variando
- Português informal e caloroso, nunca parecer script

📋 FLUXO OBRIGATÓRIO — SIGA ESTA ORDEM, UMA PERGUNTA POR VEZ:

PASSO 1 — PRIMEIRO CONTATO:
→ O vídeo já foi enviado automaticamente. Aguarde a resposta do cliente.
→ Quando responder qualquer coisa, diga:
"Oi! Que bom que você entrou em contato. 😊 Aqui é a Simone, da Envio CRED! Posso te ajudar a conseguir seu crédito hoje. Pode me dizer seu nome completo?"

PASSO 2 — NOME:
→ Já foi feita no passo 1. Quando receber o nome, avance:
"Prazer, [primeiro nome]! Qual valor você está precisando?"

PASSO 3 — VALOR:
→ Quando receber o valor:
"Anotado! E qual é o seu CPF?"

PASSO 4 — CPF:
→ Quando receber: "CPF recebido. ✅ Qual é a sua renda mensal?"
→ JAMAIS repita o número do CPF

PASSO 5 — RENDA:
→ Quando receber: "Ótimo! Seu nome está limpo ou tem alguma restrição no SPC ou Serasa?"

PASSO 6 — RESTRIÇÃO:
→ Se LIMPO: "Perfeito! Só mais alguns dados rápidos, tá? Qual é o seu CEP?"
→ Se SPC/SERASA: "Sem problema! Tenho uma solução perfeita pra você. 🎯 Qual é o seu CEP?"

PASSO 7 — CEP:
→ Quando receber: "Recebido! ✅ Qual é o seu e-mail?"

PASSO 8 — E-MAIL:
→ Quando receber: "Anotado! Qual é a sua chave PIX?"

PASSO 9 — CHAVE PIX:
→ Quando receber: "Recebido! ✅ E em quantas vezes você quer pagar?"

PASSO 10 — PARCELAS:
→ Quando receber TODOS os dados, diga:
"Perfeito, [primeiro nome]! Já tenho tudo que preciso. 🎉 Vou encaminhar sua solicitação agora para análise. Te retorno em instantes com o resultado!"
→ Após essa mensagem, PARE e aguarde — o sistema fará a análise nos bastidores.

PASSO 11 — RESULTADO (sistema vai injetar abaixo):
→ Se APROVADO: use o script da Calculadora exatamente como está
→ Se AGUARDA MÁRCIO: use o script e aguarde liberação
→ Se REPROVADO / SPC: use o script de encaminhamento positivo:
"Boa notícia, [nome]! 🎉 Tenho um parceiro perfeito que atende mesmo com restrição no nome.
É rápido, sem burocracia, direto pelo celular. Já encaminhei sua solicitação — em instantes você recebe o retorno! 💙"

🚫 RECUSA FINAL — só quando tudo falhar:
"Oi, [nome]! Fiz tudo que pude por aqui, mas no momento não encontramos uma solução para o seu perfil.
Não desanima — quando sua situação mudar, pode voltar que a gente tenta de novo. 💙 Conte com a Envio CRED sempre!"

GELADEIRA — ignorar silenciosamente: Vera, Sandra, Breno

📎 [cliente enviou documento/imagem] → "Recebi seu comprovante! ✅" e continue o fluxo
🎙️ [cliente enviou áudio] → "Oi! Não consigo ouvir áudios aqui, pode me mandar por texto? 😊"{calc_inject}"""

# ── Geração de resposta via Groq ──────────────────────────────

def gerar_resposta(mensagem_cliente, numero_cliente, historico):
    calc_inject = ""

    # Verificar se temos todos os dados para acionar calculadora (CPF limpo)
    historico_completo = historico + [{"role": "user", "content": mensagem_cliente}]
    tem_restricao = any(
        kw in m.get("content", "").lower()
        for m in historico_completo
        for kw in ["spc", "serasa", "negativado", "restrição", "restricao"]
    )
    cpf_limpo = any(
        kw in m.get("content", "").lower()
        for m in historico_completo
        for kw in ["limpa", "limpo", "não tenho", "nao tenho", "tô limpa", "to limpa", "nenhuma"]
    )
    tem_parcelas = any(
        __import__("re").search(r'\b\d+\s*(vez|vezes|parcela|x)\b', m.get("content", "").lower())
        for m in historico_completo
    )

    if cpf_limpo and tem_parcelas:
        import re
        valor_lead = None
        nome_lead = None
        for m in historico_completo:
            match = re.search(r'(\d+[\.,]?\d*)', m.get("content", ""))
            if match and m.get("role") == "user":
                try:
                    v = float(match.group(1).replace(",", "."))
                    if 50 <= v <= 3000:
                        valor_lead = v
                except:
                    pass
            if m.get("role") == "user" and 2 <= len(m["content"].split()) <= 5 and not any(c.isdigit() for c in m["content"]):
                nome_lead = m["content"].strip()

        if valor_lead and nome_lead:
            calc = calcular_operacao(nome=nome_lead, valor=valor_lead)
            if calc["status"] == "APROVADA":
                calc_inject = f"\n\n🧮 CALCULADORA — ✅ APROVADA\nScript:\n---\n{calc['script']}\n---\nEnvie EXATAMENTE este script agora."
                registrar_no_dashboard("transacao", {"nome": nome_lead, "produto": "Crédito Pessoal", "valor": valor_lead, "total": calc["total"], "status": "aprovado"})
                registrar_no_dashboard("lead", {"nome": nome_lead, "telefone": numero_cliente, "produto": "Crédito Pessoal", "valor": valor_lead, "status": "aprovado"})
            elif calc["status"] == "AGUARDA_MARCIO":
                calc_inject = f"\n\n🧮 CALCULADORA — ⚠️ AGUARDA MÁRCIO\nScript:\n---\n{calc['script']}\n---\nEnvie e aguarde Márcio liberar."
                notificar_marcio(f"Lead aguardando aprovação!\nNome: {nome_lead}\nValor: R${valor_lead}\nTelefone: {numero_cliente}")
            elif calc["status"] == "BLOQUEADA":
                calc_inject = f"\n\n🧮 CALCULADORA — ❌ BLOQUEADA\nMotivo: {' | '.join(calc['erros'])}\nNÃO avance com Envio CRED. Encaminhe pro Super Sim positivamente."

    if tem_restricao and tem_parcelas:
        # Notificar Márcio para preencher SuperSim manualmente
        import re
        dados_coletados = {}
        for m in historico_completo:
            if m.get("role") == "user":
                txt = m["content"]
                match_cpf = re.search(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}', txt)
                if match_cpf:
                    dados_coletados["cpf"] = match_cpf.group()
                match_cep = re.search(r'\d{5}-?\d{3}', txt)
                if match_cep:
                    dados_coletados["cep"] = match_cep.group()
                if "@" in txt:
                    dados_coletados["email"] = txt.strip()

        notificar_marcio(
            f"🔥 LEAD COMPLETO — SUPER SIM!\n"
            f"Telefone: {numero_cliente}\n"
            f"CPF: {dados_coletados.get('cpf', 'ver conversa')}\n"
            f"CEP: {dados_coletados.get('cep', 'ver conversa')}\n"
            f"E-mail: {dados_coletados.get('email', 'ver conversa')}\n"
            f"➡️ Preencher no Super Sim agora!"
        )

    system_prompt = montar_system_prompt(calc_inject)

    headers_req = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(historico[-12:])
    messages.append({"role": "user", "content": mensagem_cliente})

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": 300,
        "temperature": 0.65
    }

    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers_req, json=payload, timeout=15)
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[SIMONE] Erro Groq: {e}")
        return "Oi! 😊 Estou verificando aqui, te retorno em instantes!"

# ── Webhook principal ─────────────────────────────────────────

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

        push_name = msg_data.get("pushName", "") or ""
        nome_lower = push_name.lower()

        # Geladeira
        for bloqueado in GELADEIRA:
            if bloqueado in nome_lower:
                return jsonify({"status": "geladeira"}), 200

        # Márcio
        numero_limpo = numero_cliente.replace("+","").replace("-","").replace(" ","")
        if any(numero_limpo.endswith(n[-9:]) or numero_limpo == n for n in MARCIO_NUMBERS):
            return jsonify({"status": "marcio_silencio"}), 200

        # VIP
        nome_vip = eh_contato_vip(numero_cliente)
        if nome_vip:
            msg_vip = f"Parceiro/empresa:\nDe: {nome_vip} ({push_name})\nNúmero: {numero_cliente}\nMsg: {message.get('conversation','')}"
            enviar_texto(MARCIO_NUMBERS[0], msg_vip)
            enviar_texto(numero_cliente, "Olá! Sua mensagem foi encaminhada ao responsável da Envio CRED. Em breve você recebe um retorno!")
            return jsonify({"status": "vip_encaminhado"}), 200

        # Montar texto recebido
        eh_documento = "documentMessage" in message
        eh_imagem = "imageMessage" in message
        eh_audio_cliente = "audioMessage" in message

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

        # Controle de silêncio manual
        if numero_cliente in conversas and conversas[numero_cliente].get("silencio"):
            if texto_recebido.strip().lower() in ["#retomar", "#eva", "#simone"]:
                conversas[numero_cliente]["silencio"] = False
                enviar_texto(numero_cliente, "Olá! Estou de volta. 😊 Como posso te ajudar?")
            return jsonify({"status": "silencio"}), 200

        if texto_recebido.strip().lower() in ["#silencio", "#silêncio"]:
            if numero_cliente in conversas:
                conversas[numero_cliente]["silencio"] = True
            return jsonify({"status": "silencio_ativado"}), 200

        print(f"[SIMONE] De: {push_name} ({numero_cliente}): {texto_recebido[:80]}")

        # Novo lead
        primeiro_contato = numero_cliente not in conversas
        if primeiro_contato:
            conversas[numero_cliente] = {"historico": [], "silencio": False, "video_enviado": False}
            registrar_no_dashboard("lead", {
                "nome": push_name or "Desconhecido",
                "telefone": numero_cliente,
                "produto": "Em qualificação",
                "status": "novo",
                "origem": "WhatsApp (Simone)"
            })

        estado = conversas[numero_cliente]
        historico = estado["historico"]

        # Enviar vídeo no primeiro contato
        if primeiro_contato and not estado.get("video_enviado"):
            video_url = f"https://drive.google.com/uc?export=download&id={VIDEO_PROPAGANDA_ID}"
            enviou = enviar_video_url(numero_cliente, video_url)
            estado["video_enviado"] = True
            print(f"[SIMONE] Vídeo enviado para {numero_cliente}: {enviou}")
            import time
            time.sleep(2)

        # Gerar e enviar resposta
        resposta_texto = gerar_resposta(texto_recebido, numero_cliente, historico)

        historico.append({"role": "user", "content": texto_recebido})
        historico.append({"role": "assistant", "content": resposta_texto})
        if len(historico) > 24:
            conversas[numero_cliente]["historico"] = historico[-24:]

        # Primeiro contato = áudio; demais = texto
        if primeiro_contato and ELEVENLABS_API_KEY:
            audio = gerar_audio_simone(resposta_texto)
            if audio:
                sucesso = enviar_audio(numero_cliente, audio)
                if sucesso:
                    print(f"[SIMONE] Áudio enviado para {numero_cliente}")
                    return jsonify({"status": "ok", "tipo": "audio"}), 200
            print("[SIMONE] Fallback para texto")

        enviar_texto(numero_cliente, resposta_texto)
        print(f"[SIMONE] Texto → {numero_cliente}: {resposta_texto[:80]}...")
        return jsonify({"status": "ok", "tipo": "texto"}), 200

    except Exception as e:
        print(f"[SIMONE] Erro geral: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

# ── Dashboard ─────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def health():
    tz = pytz.timezone("America/Sao_Paulo")
    now = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
    return jsonify({
        "status": "Simone online 24h/7d 🤖",
        "versao": "4.3",
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

# ── Cotações em tempo real (Yahoo Finance) ─────────────────────
_cache_cotacoes = {}
_cache_ts = {}

def buscar_cotacao_yahoo(ticker):
    """Busca cotação real no Yahoo Finance. Ticker BR: KNCR11 → KNCR11.SA"""
    agora = datetime.now(tz).timestamp()
    if ticker in _cache_cotacoes and agora - _cache_ts.get(ticker, 0) < 300:
        return _cache_cotacoes[ticker]
    try:
        symbol = ticker if "." in ticker else (ticker + ".SA" if len(ticker) == 6 and ticker.isalpha() == False else ticker)
        # Tenta com .SA primeiro (B3), depois sem
        for sym in [symbol, ticker]:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            if r.status_code == 200:
                data = r.json()
                meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                preco = meta.get("regularMarketPrice") or meta.get("previousClose")
                if preco:
                    variacao = meta.get("regularMarketChangePercent", 0)
                    resultado = {
                        "ticker": ticker,
                        "symbol": sym,
                        "preco": round(float(preco), 2),
                        "variacao_pct": round(float(variacao), 2),
                        "moeda": meta.get("currency", "BRL"),
                        "mercado": "aberto" if meta.get("marketState") == "REGULAR" else "fechado",
                        "atualizado": datetime.now(tz).strftime("%H:%M:%S")
                    }
                    _cache_cotacoes[ticker] = resultado
                    _cache_ts[ticker] = agora
                    return resultado
    except Exception as e:
        print(f"[COTACAO] Erro {ticker}: {e}")
    return None

@app.route("/cotacoes", methods=["GET"])
def cotacoes():
    """Recebe ?tickers=KNCR11,MXRF11,PETR4 e retorna cotações em tempo real"""
    tickers_param = request.args.get("tickers", "")
    if not tickers_param:
        return jsonify({"erro": "Informe ?tickers=TICKER1,TICKER2"}), 400
    tickers = [t.strip().upper() for t in tickers_param.split(",") if t.strip()]
    resultado = {}
    for ticker in tickers:
        cotacao = buscar_cotacao_yahoo(ticker)
        resultado[ticker] = cotacao if cotacao else {"ticker": ticker, "erro": "não encontrado"}
    return jsonify({
        "cotacoes": resultado,
        "total": len(tickers),
        "gerado_em": datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S")
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
