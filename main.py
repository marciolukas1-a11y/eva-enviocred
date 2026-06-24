"""
EVA — Servidor de Atendimento em Tempo Real
Envio CRED + SuperSim Multiplik
Versão 4.0 — 24h/7d | Calculadora obrigatória | Dashboard integrado
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
CORS(app)  # permite chamadas do GitHub Pages e qualquer origem

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

# VIPs — parceiros, fornecedores e empresas externas
# Simone NÃO inicia fluxo de empréstimo com esses números — encaminha direto ao Márcio
CONTATOS_VIP = {
    "5511000000000": "Crefisa",       # substitua pelo número real quando vier o contato
}

def eh_contato_vip(numero):
    """Retorna o nome do VIP se for um contato especial, senão None."""
    for num_vip, nome_vip in CONTATOS_VIP.items():
        if numero.endswith(num_vip[-8:]):   # compara pelos 8 últimos dígitos (ignora DDI)
            return nome_vip
    return None

# Numeros do Marcio
MARCIO_NUMBERS = ['5583999628152', '558399628152', '5583991144899', '558391144899']

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
    # R$100 ou abaixo: APROVADA direto pela calculadora (Márcio não precisa aprovar)
    # Acima de R$100: calculadora aprova, mas avisa Márcio
    requer_aprovacao = valor > 100

    if bloqueado:
        status = "BLOQUEADA"
        script = (
            f"Oi {primeiro_nome}! 😊 Fiz a análise aqui, mas infelizmente não consigo liberar o crédito agora.\n\n"
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

# ── Banco de dados em memória (alimenta o Dashboard) ──────────
DASHBOARD_DATA = {
    "leads": [],
    "transacoes": [],
    "socios_arvore": []
}

def registrar_no_dashboard(tipo, dados):
    """Registra evento no banco de dados do servidor para o Dashboard consultar."""
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
            # Registrar resultado no dashboard
            if calc_result["status"] == "APROVADA":
                registrar_no_dashboard("transacao", {
                    "nome": nome_lead or "Cliente",
                    "produto": "Crédito Pessoal",
                    "valor": valor_lead,
                    "taxa": 20,
                    "total": calc_result["total"],
                    "status": "aprovado"
                })
                registrar_no_dashboard("lead", {
                    "nome": nome_lead or "Cliente",
                    "telefone": numero_cliente,
                    "produto": "Crédito Pessoal",
                    "valor": valor_lead,
                    "status": "aprovado"
                })
            elif calc_result["status"] == "AGUARDA_MARCIO":
                registrar_no_dashboard("lead", {
                    "nome": nome_lead or "Cliente",
                    "telefone": numero_cliente,
                    "produto": "Crédito Pessoal",
                    "valor": valor_lead,
                    "status": "aguarda_marcio"
                })

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
NÃO avance com esta operação. Use o script abaixo para recusar com gentileza:
---
Oi {{primeiro_nome}}! 😊 Analisei aqui com cuidado, mas infelizmente não consegui liberar o crédito desta vez.
Isso pode mudar no futuro! Quando sua situação financeira estiver diferente, pode voltar aqui e a gente tenta de novo. 💙
Qualquer dúvida, tô à disposição. Obrigada pela confiança na Envio CRED! 🙏
---
Se cliente for NEGATIVADO e Super Sim também não aceitar, use este script de encerramento:
---
Oi {{primeiro_nome}}! 😊 Fiz tudo que pude aqui, mas no momento as plataformas parceiras também não conseguiram aprovar.
Não desanima! Assim que seu score melhorar um pouco, as portas se abrem. Se precisar de alguma orientação sobre como limpar o nome, pode me chamar. 💙
Conte com a Envio CRED sempre que precisar! 🌟
---"""

    system_prompt = f"""Você é Simone, agente de atendimento da Envio CRED. Atende 24 horas por dia, 7 dias por semana.

IDENTIDADE:
- Nome: Simone
- Empresa: Envio CRED — correspondente de crédito
- Tom: simpático, humano, caloroso, nunca robótico

🚨 DIRETRIZ ZERO — REGRA MÁXIMA, NUNCA VIOLE:
A CALCULADORA é a única autoridade para aprovar ou negar empréstimos.
Você NUNCA aprova, promete ou sugere crédito sem o resultado da Calculadora.
NUNCA diga "vou verificar com o gerente" — você resolve com a Calculadora, sem pausas.

🚨 REGRAS CRÍTICAS:
1. JAMAIS diga "vou verificar com o gerente" ou qualquer variação
2. NUNCA prometa aprovação sem o carimbo da Calculadora
3. NUNCA gere ou informe PIX — só use o PIX fixo abaixo quando a Calculadora APROVAR
4. NUNCA revele comissões ou estratégias internas
5. NUNCA diga que não conhece Envio CRED, Super Sim ou Projeto Árvore
6. NUNCA emita valores de contrato sem resultado da Calculadora

📋 FLUXO OBRIGATÓRIO — SIGA ESTA ORDEM:
1. Recepcionar com calor humano
2. Coletar: nome completo → valor desejado → CPF → renda mensal → "Seu CPF tem restrição (SPC/Serasa)?"

3. COM BASE NA RESPOSTA:

   A) CPF LIMPO + valor ≤ R$100:
      → Calculadora decide. Se APROVADA: enviar script com PIX e aguardar comprovante.
      → Se BLOQUEADA: NÃO encerre ainda. Mande pro Super Sim com mensagem gentil.

   B) CPF LIMPO + valor > R$100:
      → Calculadora decide. Se APROVADA: avisar que está confirmando com responsável e notificar Márcio.
      → Se BLOQUEADA: NÃO encerre ainda. Mande pro Super Sim com mensagem gentil.

   C) CPF COM RESTRIÇÃO (negativado):
      → Não passa pela Calculadora. Encaminhar direto ao Super Sim com mensagem gentil.

   EM TODOS OS CASOS QUE VÃO PRO SUPER SIM, use este script:
   "Oi [nome]! 😊 No momento não consigo liberar por aqui, mas tenho uma boa notícia!
   Temos um parceiro que pode te ajudar com valores ainda maiores: a *Super Sim*! 🚀
   ✅ Funciona mesmo pra quem está negativado
   ✅ Processo rápido e sem burocracia
   Acessa aqui e faz seu cadastro: susim.co/7+peoHFiNQsn8C1qFl0tCA==
   Qualquer dúvida, é só chamar! 💙"

   SE O CLIENTE VOLTAR DIZENDO QUE A SUPER SIM TAMBÉM NEGOU:
   → Aí sim encerra com script de recusa final gentil abaixo.

4. Se cliente perguntar sobre Projeto Árvore → explicar e mandar link do contrato.

📚 DADOS OFICIAIS:

💳 ENVIO CRED
- PIX (só enviar quando Calculadora APROVAR): Banco Inter | Chave 83991144899 (telefone)

⚡ SUPER SIM
- Link: susim.co/7+peoHFiNQsn8C1qFl0tCA==
- Enviar para quem está negativado

🌱 PROJETO ÁRVORE
- Investimento R$100–R$500 | 6% ao ano + 50% dividendos FIIs | Prazo 1 ano
- Contrato: https://marciolukas1-a11y.github.io/enviocred-pagamento/contrato-arvore.html

🚫 SCRIPT DE RECUSA FINAL (só usar quando Super Sim também negar):
"Oi [nome]! 😊 Me desculpa muito, fiz o possível aqui e pelo nosso parceiro também, mas no momento não conseguimos encontrar uma solução pra você.
Não desanima! Sua situação pode mudar e quando isso acontecer, pode voltar que a gente tenta de novo. 💙
Foi um prazer te atender! Obrigada pela confiança na Envio CRED! 🙏"

GELADEIRA — ignorar silenciosamente: Vera, Sandra, Breno
Respostas curtas (máx 3 frases), emojis com moderação, português informal.

📎 QUANDO CLIENTE ENVIAR DOCUMENTO OU IMAGEM:
- O sistema vai te avisar com: [cliente enviou documento como comprovante] ou [cliente enviou imagem como comprovante]
- Isso significa que o cliente mandou um comprovante de renda, extrato ou holerite
- Responda reconhecendo e continue o fluxo normalmente: "Recebi seu comprovante! ✅ ..."
- Se ainda faltar informações (CPF, valor desejado), continue coletando
- NUNCA diga que não consegue ver ou receber documentos

🎙️ QUANDO CLIENTE ENVIAR ÁUDIO:
- O sistema vai te avisar com: [cliente enviou áudio]
- Responda: "Oi! Não consigo ouvir áudios aqui, mas pode me mandar por texto que respondo na hora! 😊"{calc_inject}"""

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

        # Ignorar reações e figurinhas silenciosamente
        if "reactionMessage" in message or "stickerMessage" in message:
            print(f"[EVA] Reação/figurinha ignorada de {numero_cliente}")
            return jsonify({"status": "ignored"}), 200

        # Detectar documentos e imagens (comprovante de renda, etc.)
        eh_documento = "documentMessage" in message
        eh_imagem = "imageMessage" in message
        eh_audio_cliente = "audioMessage" in message and not key.get("fromMe", False)

        texto_recebido = (
            message.get("conversation") or
            message.get("extendedTextMessage", {}).get("text") or
            ""
        )

        # Se mandou documento ou imagem, tratar como comprovante e continuar o fluxo
        if eh_documento or eh_imagem:
            tipo = "documento" if eh_documento else "imagem"
            caption = message.get("documentMessage", {}).get("caption") or \
                      message.get("imageMessage", {}).get("caption") or ""
            texto_recebido = f"[cliente enviou {tipo} como comprovante] {caption}".strip()
            print(f"[EVA] {tipo.upper()} recebido de {numero_cliente} — tratando como comprovante")

        # Áudio do cliente — avisar que não consegue ouvir
        if eh_audio_cliente:
            texto_recebido = "[cliente enviou áudio]"

        if not texto_recebido.strip():
            return jsonify({"status": "ignored"}), 200

        push_name = msg_data.get("pushName", "") or ""
        nome_lower = push_name.lower()

        print(f"[EVA] De: {push_name} ({numero_cliente}): {texto_recebido}")

        # -- Numero do Marcio -- modo silencio
        numero_limpo = numero_cliente.replace("+","").replace("-","").replace(" ","")
        print("[EVA DEBUG] numero_limpo=" + numero_limpo + " MARCIO_NUMBERS=" + str(MARCIO_NUMBERS))
        print("[EVA DEBUG] sufixos=" + str([n[-9:] for n in MARCIO_NUMBERS]))
        if any(numero_limpo.endswith(n[-9:]) or numero_limpo == n for n in MARCIO_NUMBERS):
            print("[EVA] Mensagem do Marcio. Modo silencio.")
            return jsonify({"status": "marcio_silencio"}), 200

        # ── Contato VIP (parceiro/empresa externa) ───────────
        nome_vip = eh_contato_vip(numero_cliente)
        if nome_vip:
            print(f"[EVA] Contato VIP detectado: {nome_vip} ({numero_cliente}). Encaminhando ao Márcio.")
            msg_vip = "Mensagem de parceiro/empresa:" + chr(10) + "De: " + nome_vip + " (" + push_name + ")" + chr(10) + "Numero: " + numero_cliente + chr(10) + "Mensagem: " + texto_recebido
            enviar_texto(MARCIO_NUMBER, msg_vip)
            enviar_texto(numero_cliente, "Ola! Sua mensagem foi encaminhada ao responsavel da Envio CRED. Em breve voce recebera um retorno.")
            return jsonify({"status": "vip_encaminhado"}), 200

        # ── Geladeira ─────────────────────────────────────────
        for bloqueado in GELADEIRA:
            if bloqueado in nome_lower:
                print(f"[EVA] {push_name} está na geladeira. Ignorando.")
                return jsonify({"status": "geladeira"}), 200

        # ── Histórico e estado do cliente ─────────────────────
        if numero_cliente not in conversas:
            conversas[numero_cliente] = {"historico": [], "primeiro_contato": True}
            # Registrar como novo lead no dashboard
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
        "status": "Simone online 24h/7d 🤖",
        "versao": "4.0",
        "agora": now,
        "groq": bool(GROQ_API_KEY),
        "elevenlabs": bool(ELEVENLABS_API_KEY),
        "endpoints": ["/webhook", "/dashboard/dados", "/dashboard/lead", "/dashboard/socio"]
    }), 200

# ── Endpoints do Dashboard ─────────────────────────────────────
@app.route("/dashboard/dados", methods=["GET"])
def dashboard_dados():
    """Retorna todos os dados para o dashboard."""
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
    """Recebe lead manualmente (ex: do painel web)."""
    dados = request.json or {}
    registrar_no_dashboard("lead", dados)
    return jsonify({"status": "ok"}), 200

@app.route("/dashboard/socio", methods=["POST"])
def dashboard_socio():
    """Registra sócio do Projeto Árvore."""
    dados = request.json or {}
    registrar_no_dashboard("socio_arvore", dados)
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

