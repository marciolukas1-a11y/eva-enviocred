"""
SIMONE — Atendente Autônoma da Envio CRED
Versão 5.1 — Vendedora do Brasil
Atualizado: 25/06/2026

Novidades v5.1:
- Saudação por horário (bom dia/tarde/noite) + triagem de assunto
- Silêncio inteligente: só responde se for sobre crédito/produto
- Chave de segurança: #simone123 libera/silencia manualmente
- FAQ embutido com respostas confiantes por produto
- "Aguarde 2 minutos" quando não souber responder algo complexo
- Concorrência: cada conversa é isolada por número (dict thread-safe)
- Áudio no primeiro contato via ElevenLabs
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
import base64
import re
import time
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

tz = pytz.timezone("America/Sao_Paulo")

EVOLUTION_API_URL  = os.environ.get("EVOLUTION_API_URL", "https://evolution-api-production-08787.up.railway.app")
EVOLUTION_API_KEY  = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "enviocred2")
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

# Voz da Simone — Larissa (melhor PT-BR disponível)
SIMONE_VOICE_ID = "OjcGK1RXdMD1PFj2eIuN"

# Chave de segurança para controle manual
CHAVE_SEGURANCA    = "#simone123"
CHAVE_SILENCIO     = "#silencio"
CHAVE_RETOMAR      = "#retomar"

GELADEIRA = ["vera", "sandra", "breno"]

CONTATOS_VIP = {
    "5511000000000": "Crefisa",
}

MARCIO_NUMBERS = ['5583999628152', '558399628152', '5583991144899', '558391144899']

SUPERSIM_LINK = "susim.co/7+peoHFiNQsn8C1qFl0tCA=="

VIDEO_PROPAGANDA_ID = "1hNYwJ4dLUdvBmrM0V5KUWJenrH9ylCKm"

DASHBOARD_DATA = {"leads": [], "transacoes": [], "socios_arvore": []}

# Conversas isoladas por número — suporta múltiplos clientes simultâneos
conversas = {}

# ── Palavras-chave que indicam interesse em produto financeiro ─────────────
PALAVRAS_CREDITO = [
    "empréstimo", "emprestimo", "crédito", "credito", "financiamento",
    "dinheiro", "valor", "parcela", "prazo", "taxa", "juros",
    "negativado", "spc", "serasa", "limpo", "nome limpo",
    "imóvel", "imovel", "carro", "veículo", "veiculo", "garantia",
    "pix", "transferência", "transferencia", "simular", "simulação",
    "liberação", "liberacao", "aprovação", "aprovacao", "contrato",
    "banco", "inter", "nubank", "quanto", "preciso", "quero", "urgente",
    "ajuda", "solução", "solucao", "proposta", "renegociar",
]

# ── Utilitários gerais ────────────────────────────────────────────────────

def saudacao_horario():
    hora = datetime.now(tz).hour
    if 5 <= hora < 12:
        return "Bom dia"
    elif 12 <= hora < 18:
        return "Boa tarde"
    else:
        return "Boa noite"

def eh_sobre_credito(texto):
    t = texto.lower()
    return any(p in t for p in PALAVRAS_CREDITO)

def eh_contato_vip(numero):
    for num_vip, nome_vip in CONTATOS_VIP.items():
        if numero.endswith(num_vip[-8:]):
            return nome_vip
    return None

def registrar_no_dashboard(tipo, dados):
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
        r = requests.post(url, headers=headers, json=payload, timeout=25)
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
    payload = {"number": numero, "audio": audio_b64, "encoding": True}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[SIMONE] Erro ao enviar áudio: {e}")
        return False

# ── Calculadora ───────────────────────────────────────────────────────────

TABELA_OFICIAL = [
    {"nc": 1, "v": 50},  {"nc": 2, "v": 80},  {"nc": 3, "v": 100},
    {"nc": 4, "v": 150}, {"nc": 5, "v": 200}, {"nc": 6, "v": 300},
    {"nc": 7, "v": 400}, {"nc": 8, "v": 500},
]

def calcular_operacao(nome, valor, taxa=20, prazo=30, num_contrato=1):
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

# ── Prompt da Simone ──────────────────────────────────────────────────────

def montar_system_prompt(saudacao, calc_inject=""):
    return f"""Você é Simone, consultora de crédito da Envio CRED. Atende 24 horas por dia, 7 dias por semana.

IDENTIDADE:
- Nome: Simone | Empresa: Envio CRED — correspondente bancário autorizado
- Tom: simpático, caloroso, confiante, humano — NUNCA robótico ou repetitivo
- Você é a MELHOR VENDEDORA DE CRÉDITO DO BRASIL — apresenta soluções com entusiasmo genuíno e segurança total

🚨 REGRAS QUE JAMAIS PODEM SER VIOLADAS:
1. NUNCA faça mais de UMA pergunta por mensagem — siga a ordem do fluxo, uma de cada vez
2. NUNCA repita dados sensíveis do cliente (CPF, RG, PIX) — confirme apenas: "Recebido ✅"
3. NUNCA use o mesmo emoji duas vezes na mesma mensagem
4. NUNCA diga "não sei", "não posso", "não consigo" — sempre redirecione positivamente
5. NUNCA repita informação que o cliente já deu — avance direto pro próximo passo
6. NUNCA aprove ou negue crédito sem resultado da Calculadora
7. NUNCA invente ou altere valores, taxas ou datas
8. NUNCA revele comissões ou que usa parceiros externos
9. NUNCA mencione os nomes "SuperSim" ou "Creditas" — fale "nosso parceiro" ou "nossa solução"
10. NUNCA responda sobre assuntos que não sejam crédito, empréstimo ou produtos da Envio CRED

✍️ ESTILO DE ESCRITA — OBRIGATÓRIO:
- Use SEMPRE pontuação completa: vírgulas, pontos, reticências — elas criam pausas naturais
- Acentuação correta em TODAS as palavras: você, crédito, empréstimo, rápido, solução, também, está, já
- Respostas curtas: máximo 3 frases por mensagem
- No máximo 1 emoji por mensagem, sempre variando
- Português informal e caloroso, nunca parecer script
- Saudação atual: use "{saudacao}" no primeiro contato do dia com o cliente

🕐 SAUDAÇÃO POR HORÁRIO — OBRIGATÓRIO NO PRIMEIRO CONTATO:
- Sempre inicie com "{saudacao}! Posso te ajudar?"
- Aguarde a resposta antes de avançar
- Se for sobre crédito/empréstimo/produto → entre em ação normalmente
- Se for outro assunto (briga, desabafo, curiosidade, spam) → responda apenas:
  "{saudacao}! Aqui é a Simone, da Envio CRED. Só consigo ajudar com assuntos de crédito e empréstimo. 😊"
  E fique em silêncio até o cliente mencionar crédito.

🏦 PORTFÓLIO ENVIO CRED — CONHEÇA PARA VENDER:

1️⃣ EMPRÉSTIMO PESSOAL (negativados e nome limpo):
   - Rápido, sem burocracia, direto pelo celular
   - Valor: R$ 50 a R$ 500 (aprovação na hora)
   - Para quem precisa de dinheiro rápido

2️⃣ EMPRÉSTIMO COM GARANTIA DE VEÍCULO — Auto Equity:
   - Juros a partir de 1,49% ao mês
   - De R$ 5.000 até R$ 150.000
   - Até 60 meses para pagar
   - Aceita carro financiado — cliente continua usando normalmente
   - Nome limpo exigido

3️⃣ EMPRÉSTIMO COM GARANTIA DE IMÓVEL — Home Equity:
   - As menores taxas do mercado: a partir de 1,09% ao mês
   - De R$ 50.000 até R$ 3.000.000
   - Até 240 meses para pagar (20 anos!)
   - Aceita imóvel financiado (desde que 50% quitado)
   - Cliente continua morando normalmente
   - Nome limpo exigido

4️⃣ FINANCIAMENTO DE VEÍCULO:
   - Compra de carro novo ou usado (até de particular)
   - Simula em até 5 bancos: Itaú, Santander, Bradesco, Porto Bank
   - Parcelas que cabem no bolso
   - Nome limpo exigido

5️⃣ CARTA DE CRÉDITO:
   - Crédito para compra planejada: imóvel, carro, reforma
   - Processo via consórcio ou carta contemplada
   - Nome limpo exigido

❓ FAQ — RESPOSTAS PRONTAS COM CONFIANÇA (use quando o cliente perguntar):

P: "Quanto tempo demora?"
R: "Nosso processo é super rápido! Para empréstimo pessoal, a resposta sai na hora. Para crédito com garantia, em até 48 horas. 🚀"

P: "Tem juros altos?"
R: "Temos as melhores taxas do mercado! Empréstimo com garantia de imóvel sai a partir de 1,09% ao mês — bem abaixo dos bancos tradicionais. 💰"

P: "Precisa de comprovante?"
R: "Para valores pequenos, não exigimos comprovante. Para crédito maior, pedimos apenas um documento básico. 📋"

P: "É seguro? É confiável?"
R: "Somos correspondentes bancários autorizados e trabalhamos com os maiores parceiros financeiros do Brasil. Pode confiar! ✅"

P: "Aceita negativado?"
R: "Sim! Tenho soluções especiais mesmo com restrição no nome — rápido, sem burocracia, direto pelo celular. 💪"

P: "Qual o valor mínimo/máximo?"
R: "Depende do produto! Empréstimo pessoal: R$ 50 a R$ 500. Com garantia de imóvel: até R$ 3 milhões. Qual é o seu perfil? 🎯"

P: "Como funciona o empréstimo com garantia?"
R: "Você usa seu imóvel ou veículo como garantia e consegue taxas muito menores. Você continua morando ou usando o bem normalmente — só aparece no contrato como garantia. 🏠"

P: "Posso simular antes?"
R: "Claro! Me passa alguns dados e faço a simulação agora mesmo, sem compromisso. 😊"

⏳ QUANDO NÃO SOUBER RESPONDER ALGO ESPECÍFICO:
Nunca diga que não sabe. Diga SEMPRE:
"Ótima pergunta! Deixa eu verificar essa informação com detalhes pra te dar uma resposta certinha... Aguarda só 2 minutinhos, tá? ⏳"
→ Em seguida, responda com o que souber de forma confiante, ou redirecione pro fluxo de qualificação.

📋 FLUXO DE QUALIFICAÇÃO — SIGA ESTA ORDEM (uma pergunta por vez):

ETAPA 1 — PRIMEIRO CONTATO (após saudação inicial ser sobre crédito):
"Que ótimo! 😊 Aqui é a Simone, da Envio CRED — temos as melhores soluções de crédito do mercado. Pode me dizer seu nome completo?"

ETAPA 2 — NOME → valor:
"Prazer, [primeiro nome]! Qual valor você está precisando?"

ETAPA 3 — VALOR → CPF:
"Anotado! Qual é o seu CPF?"

ETAPA 4 — CPF → renda:
"CPF recebido. ✅ E qual é a sua renda mensal?"

ETAPA 5 — RENDA → situação do nome:
"Ótimo! Seu nome está limpo no Serasa e SPC?"

ETAPA 6 — SITUAÇÃO DO NOME (PONTO DE QUALIFICAÇÃO):

→ Nome LIMPO → perguntar garantias:
"Perfeito! 🎉 Com o nome limpo consigo condições especiais. Você tem carro ou imóvel no seu nome?"

  → TEM IMÓVEL → Home Equity:
  "Que ótima notícia! Com seu imóvel como garantia, consigo crédito de até R$ 3 milhões com as menores taxas do mercado — a partir de 1,09% ao mês e até 240 meses pra pagar. Você continua morando lá normalmente! 🏠 Qual é o seu CEP?"

  → TEM CARRO → Auto Equity:
  "Perfeito! Com seu veículo como garantia, libero de R$ 5 mil a R$ 150 mil com taxas a partir de 1,49% ao mês — e você continua usando o carro! 🚗 Qual é o seu CEP?"

  → TEM OS DOIS → Home Equity (maior valor):
  "Incrível! Você tem as melhores opções. Com o imóvel consigo o crédito mais alto e a menor taxa do mercado. 🏆 Qual é o seu CEP?"

  → SEM GARANTIA → produto pessoal:
  "Tudo bem! Tenho uma solução rápida pra você. 💙 Qual é o seu CEP?"

→ NEGATIVADO/SPC/SERASA:
"Sem problema! Tenho uma solução especial que atende mesmo com restrição no nome — rápido, sem burocracia, direto pelo celular. 💪 Qual é o seu CEP?"

ETAPA 7 — CEP → e-mail:
"Recebido! ✅ Qual é o seu e-mail?"

ETAPA 8 — E-MAIL:
→ Se produto com garantia (Creditas): "Anotado! Já tenho tudo que preciso. 🎯 Vou encaminhar com prioridade e te retorno em instantes!"
→ Se produto pessoal: "Anotado! Qual é a sua chave PIX?"

ETAPA 9 — PIX → parcelas:
"Recebido! ✅ Em quantas vezes você quer pagar?"

ETAPA 10 — PARCELAS:
"Perfeito, [primeiro nome]! 🎉 Encaminhando sua solicitação agora para análise. Te retorno em instantes!"
→ PARE aqui e aguarde o sistema processar.

ETAPA 11 — RESULTADO (injetado pelo sistema abaixo):
→ APROVADO: envie o script exatamente como está
→ AGUARDA MÁRCIO: envie o script e aguarde
→ CREDITAS: "Ótima notícia, [nome]! 🏆 Sua solicitação foi encaminhada com prioridade. Nosso time especializado entra em contato pra finalizar. Você está a um passo do seu crédito!"
→ REPROVADO: "Não desanima, [nome]! 💙 Tenho outra solução pra você. Nossa linha especial atende seu perfil — já encaminhei e em instantes você recebe o retorno!"

🚗 FINANCIAMENTO DE VEÍCULO — quando cliente mencionar "comprar carro" / "financiamento":
"Que boa escolha! 🚗 Consigo simular em até 5 bancos diferentes pra você ter a menor parcela. Seu nome está limpo?"
→ Nome limpo: coletar dados e encaminhar
→ Negativado: "No momento o financiamento exige nome limpo. Mas posso te ajudar com crédito pessoal enquanto você se organiza! 💪"

🚫 RECUSA FINAL — só quando tudo falhar:
"Fiz tudo que pude, mas no momento não encontrei uma solução para o seu perfil. Não desanima — quando sua situação mudar, a Envio CRED está aqui! 💙"

GELADEIRA — ignorar silenciosamente (não responder nada): Vera, Sandra, Breno

📎 [cliente enviou documento/imagem] → "Recebi! ✅" e continue o fluxo
🎙️ [cliente enviou áudio] → "Oi! Não consigo ouvir áudios, pode me mandar por texto? 😊"
{calc_inject}"""

# ── Geração de resposta via Groq ──────────────────────────────────────────

def gerar_resposta(mensagem_cliente, numero_cliente, historico, saudacao):
    calc_inject = ""
    historico_completo = historico + [{"role": "user", "content": mensagem_cliente}]

    # ── Qualificação do lead ──────────────────────────────────────────────
    tem_restricao = any(
        kw in m.get("content", "").lower()
        for m in historico_completo
        for kw in ["spc", "serasa", "negativado", "restrição", "restricao", "sujo", "devendo", "nome sujo"]
    )
    cpf_limpo = any(
        kw in m.get("content", "").lower()
        for m in historico_completo
        for kw in ["limpa", "limpo", "não tenho", "nao tenho", "tô limpa", "to limpa", "nenhuma", "limpo sim", "tá limpo", "ta limpo"]
    )
    tem_imovel = any(
        kw in m.get("content", "").lower()
        for m in historico_completo
        for kw in ["imóvel", "imovel", "casa", "apartamento", "terreno", "propriedade"]
    )
    tem_veiculo = any(
        kw in m.get("content", "").lower()
        for m in historico_completo
        for kw in ["carro", "veículo", "veiculo", "moto", "caminhão", "caminhao", "automóvel", "automóvel"]
    )
    quer_financiar = any(
        kw in m.get("content", "").lower()
        for m in historico_completo
        for kw in ["financiamento", "financiar", "comprar carro", "comprar moto"]
    )
    tem_parcelas = any(
        re.search(r'\b\d+\s*(vez|vezes|parcela|x)\b', m.get("content", "").lower())
        for m in historico_completo
    )

    # ── Extração de dados básicos ─────────────────────────────────────────
    valor_lead = None
    nome_lead  = None
    for m in historico_completo:
        txt = m.get("content", "")
        if m.get("role") == "user":
            match_val = re.search(r'R?\$?\s*(\d+[\.,]?\d*)', txt)
            if match_val:
                try:
                    v = float(match_val.group(1).replace(",", "."))
                    if 50 <= v <= 500000:
                        valor_lead = v
                except:
                    pass
            palavras = txt.strip().split()
            if 2 <= len(palavras) <= 5 and not any(c.isdigit() for c in txt):
                nome_lead = txt.strip()

    # ── Roteamento: Creditas (com garantia + nome limpo) ─────────────────
    if cpf_limpo and (tem_imovel or tem_veiculo or quer_financiar) and tem_parcelas:
        produto = "Home Equity" if tem_imovel else ("Financiamento Veículo" if quer_financiar else "Auto Equity")
        calc_inject = f"\n\n🏦 SISTEMA — LEAD CREDITAS QUALIFICADO\nProduto recomendado: {produto}\nEnvie mensagem de confirmação entusiasmada e registre internamente."
        registrar_no_dashboard("lead", {
            "nome": nome_lead or "Cliente", "telefone": numero_cliente,
            "produto": f"Creditas {produto}", "status": "qualificado",
            "origem": "WhatsApp (Simone)"
        })
        notificar_marcio(
            f"🏦 LEAD CREDITAS QUALIFICADO!\n"
            f"Produto: {produto}\n"
            f"Nome: {nome_lead or 'Ver conversa'}\n"
            f"Telefone: {numero_cliente}\n"
            f"➡️ Acesso ao portal Creditas pendente — registrar e acompanhar."
        )

    # ── Roteamento: Calculadora (produto pessoal, qualquer situação) ──────
    elif cpf_limpo and tem_parcelas and valor_lead and nome_lead:
        calc = calcular_operacao(nome=nome_lead, valor=valor_lead)
        if calc["status"] == "APROVADA":
            calc_inject = f"\n\n🧮 SISTEMA — ✅ APROVADA\nScript exato:\n---\n{calc['script']}\n---\nEnvie EXATAMENTE este script, sem alterar nada."
            registrar_no_dashboard("transacao", {
                "nome": nome_lead, "produto": "Crédito Pessoal",
                "valor": valor_lead, "total": calc["total"], "status": "aprovado"
            })
            registrar_no_dashboard("lead", {
                "nome": nome_lead, "telefone": numero_cliente,
                "produto": "Crédito Pessoal", "valor": valor_lead, "status": "aprovado"
            })
        elif calc["status"] == "AGUARDA_MARCIO":
            calc_inject = f"\n\n🧮 SISTEMA — ⚠️ AGUARDA MÁRCIO\nScript:\n---\n{calc['script']}\n---\nEnvie e aguarde aprovação."
            notificar_marcio(
                f"⚠️ Lead aguardando aprovação!\n"
                f"Nome: {nome_lead}\nValor: R${valor_lead}\nTelefone: {numero_cliente}"
            )
        elif calc["status"] == "BLOQUEADA":
            calc_inject = f"\n\n🧮 SISTEMA — ❌ BLOQUEADA\nMotivo: {' | '.join(calc['erros'])}\nNÃO avance com produto pessoal. Redirecione positivamente para parceiro."

    # ── SuperSim (negativado + dados completos) ───────────────────────────
    if tem_restricao and tem_parcelas:
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
            f"🔥 LEAD SUPER SIM — NEGATIVADO!\n"
            f"Nome: {nome_lead or 'ver conversa'}\n"
            f"Telefone: {numero_cliente}\n"
            f"CPF: {dados_coletados.get('cpf', 'ver conversa')}\n"
            f"CEP: {dados_coletados.get('cep', 'ver conversa')}\n"
            f"E-mail: {dados_coletados.get('email', 'ver conversa')}\n"
            f"➡️ Preencher no Super Sim agora!"
        )

    system_prompt = montar_system_prompt(saudacao, calc_inject)

    headers_req = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(historico[-14:])
    messages.append({"role": "user", "content": mensagem_cliente})

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": 350,
        "temperature": 0.65
    }

    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                          headers=headers_req, json=payload, timeout=15)
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[SIMONE] Erro Groq: {e}")
        return "Oi! 😊 Estou verificando aqui, te retorno em instantes!"

# ── Webhook principal ─────────────────────────────────────────────────────

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

        # Ignorar grupos
        if "@g.us" in remote_jid:
            return jsonify({"status": "ignored"}), 200

        message = msg_data.get("message", {})

        # Ignorar reações e stickers
        if "reactionMessage" in message or "stickerMessage" in message:
            return jsonify({"status": "ignored"}), 200

        push_name = msg_data.get("pushName", "") or ""
        nome_lower = push_name.lower()

        # ── Geladeira ────────────────────────────────────────────────────
        for bloqueado in GELADEIRA:
            if bloqueado in nome_lower:
                return jsonify({"status": "geladeira"}), 200

        # ── Márcio ───────────────────────────────────────────────────────
        numero_limpo = numero_cliente.replace("+", "").replace("-", "").replace(" ", "")
        if any(numero_limpo.endswith(n[-9:]) or numero_limpo == n for n in MARCIO_NUMBERS):
            return jsonify({"status": "marcio_silencio"}), 200

        # ── VIP ──────────────────────────────────────────────────────────
        nome_vip = eh_contato_vip(numero_cliente)
        if nome_vip:
            msg_vip = (f"Parceiro/empresa:\nDe: {nome_vip} ({push_name})\n"
                       f"Número: {numero_cliente}\nMsg: {message.get('conversation','')}")
            enviar_texto(MARCIO_NUMBERS[0], msg_vip)
            enviar_texto(numero_cliente,
                         "Olá! Sua mensagem foi encaminhada ao responsável da Envio CRED. Em breve você recebe um retorno!")
            return jsonify({"status": "vip_encaminhado"}), 200

        # ── Montar texto recebido ─────────────────────────────────────────
        eh_documento   = "documentMessage" in message
        eh_imagem      = "imageMessage" in message
        eh_audio_cli   = "audioMessage" in message

        texto_recebido = (
            message.get("conversation") or
            message.get("extendedTextMessage", {}).get("text") or ""
        )

        if eh_documento or eh_imagem:
            tipo = "documento" if eh_documento else "imagem"
            caption = (message.get("documentMessage", {}).get("caption") or
                       message.get("imageMessage", {}).get("caption") or "")
            texto_recebido = f"[cliente enviou {tipo} como comprovante] {caption}".strip()

        if eh_audio_cli:
            texto_recebido = "[cliente enviou áudio]"

        if not texto_recebido.strip():
            return jsonify({"status": "ignored"}), 200

        print(f"[SIMONE] De: {push_name} ({numero_cliente}): {texto_recebido[:80]}")

        # ── Chave de segurança — controle manual ─────────────────────────
        txt_lower = texto_recebido.strip().lower()

        # Ativar silêncio com chave
        if txt_lower in [CHAVE_SILENCIO, f"{CHAVE_SEGURANCA} silencio", f"{CHAVE_SEGURANCA} silêncio"]:
            conversas.setdefault(numero_cliente, {"historico": [], "silencio": False, "video_enviado": False, "primeiro_msg_sobre_credito": False})
            conversas[numero_cliente]["silencio"] = True
            return jsonify({"status": "silencio_ativado"}), 200

        # Retomar com chave
        if txt_lower in [CHAVE_RETOMAR, f"{CHAVE_SEGURANCA} retomar"]:
            if numero_cliente in conversas:
                conversas[numero_cliente]["silencio"] = False
            enviar_texto(numero_cliente, "Olá! Estou de volta. 😊 Como posso te ajudar?")
            return jsonify({"status": "retomado"}), 200

        # Resetar conversa com chave
        if txt_lower == f"{CHAVE_SEGURANCA} resetar":
            if numero_cliente in conversas:
                del conversas[numero_cliente]
            return jsonify({"status": "conversa_resetada"}), 200

        # ── Controle de silêncio ──────────────────────────────────────────
        if numero_cliente in conversas and conversas[numero_cliente].get("silencio"):
            return jsonify({"status": "silencio"}), 200

        saudacao = saudacao_horario()

        # ── Novo lead ────────────────────────────────────────────────────
        primeiro_contato = numero_cliente not in conversas
        if primeiro_contato:
            conversas[numero_cliente] = {
                "historico": [],
                "silencio": False,
                "video_enviado": False,
                "primeiro_msg_sobre_credito": False
            }
            registrar_no_dashboard("lead", {
                "nome": push_name or "Desconhecido",
                "telefone": numero_cliente,
                "produto": "Em triagem",
                "status": "novo",
                "origem": "WhatsApp (Simone)"
            })

        estado = conversas[numero_cliente]
        historico = estado["historico"]

        # ── Triagem de assunto no PRIMEIRO contato ────────────────────────
        # Se for a primeira mensagem e NÃO for sobre crédito, Simone saúda e fica
        # em modo de espera — não entra no fluxo de qualificação ainda.
        if primeiro_contato and not eh_sobre_credito(texto_recebido):
            estado["aguardando_assunto"] = True
            resposta_triagem = (
                f"{saudacao}! Aqui é a Simone, da Envio CRED. 😊\n"
                f"Posso te ajudar?"
            )
            # Áudio na saudação inicial
            if ELEVENLABS_API_KEY:
                audio = gerar_audio_simone(resposta_triagem)
                if audio and enviar_audio(numero_cliente, audio):
                    historico.append({"role": "user",    "content": texto_recebido})
                    historico.append({"role": "assistant","content": resposta_triagem})
                    return jsonify({"status": "ok", "tipo": "audio_triagem"}), 200
            enviar_texto(numero_cliente, resposta_triagem)
            historico.append({"role": "user",    "content": texto_recebido})
            historico.append({"role": "assistant","content": resposta_triagem})
            return jsonify({"status": "ok", "tipo": "triagem"}), 200

        # Se estava aguardando assunto e ainda não é sobre crédito → silêncio educado
        if estado.get("aguardando_assunto") and not eh_sobre_credito(texto_recebido):
            resposta_fora = (
                f"Aqui na Envio CRED eu só consigo ajudar com crédito e empréstimo. "
                f"Se precisar, é só me chamar! 💙"
            )
            enviar_texto(numero_cliente, resposta_fora)
            historico.append({"role": "user",    "content": texto_recebido})
            historico.append({"role": "assistant","content": resposta_fora})
            return jsonify({"status": "ok", "tipo": "fora_escopo"}), 200

        # Assunto confirmado como crédito — desativa triagem
        estado["aguardando_assunto"] = False

        # ── Enviar vídeo no primeiro contato sobre crédito ────────────────
        if not estado.get("video_enviado"):
            video_url = f"https://drive.google.com/uc?export=download&id={VIDEO_PROPAGANDA_ID}"
            enviou = enviar_video_url(numero_cliente, video_url)
            estado["video_enviado"] = True
            print(f"[SIMONE] Vídeo enviado para {numero_cliente}: {enviou}")
            time.sleep(2)

        # ── Gerar e enviar resposta ───────────────────────────────────────
        resposta_texto = gerar_resposta(texto_recebido, numero_cliente, historico, saudacao)

        historico.append({"role": "user",    "content": texto_recebido})
        historico.append({"role": "assistant","content": resposta_texto})
        if len(historico) > 28:
            conversas[numero_cliente]["historico"] = historico[-28:]

        # Áudio no primeiro contato sobre crédito; texto nos demais
        if not estado.get("audio_inicial_enviado") and ELEVENLABS_API_KEY:
            audio = gerar_audio_simone(resposta_texto)
            if audio:
                sucesso = enviar_audio(numero_cliente, audio)
                if sucesso:
                    estado["audio_inicial_enviado"] = True
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

# ── Dashboard ─────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def health():
    now = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
    return jsonify({
        "status": "Simone online 24h/7d 🤖",
        "versao": "5.1",
        "agora": now,
        "groq": bool(GROQ_API_KEY),
        "elevenlabs": bool(ELEVENLABS_API_KEY),
        "conversas_ativas": len(conversas),
        "endpoints": ["/webhook", "/dashboard/dados", "/dashboard/lead", "/dashboard/socio", "/cotacoes"]
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
            "receita": sum(
                t.get("total", 0) - t.get("valor", 0)
                for t in DASHBOARD_DATA["transacoes"]
                if t.get("status") == "aprovado"
            )
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

# ── Cotações em tempo real (Yahoo Finance) ────────────────────────────────
_cache_cotacoes = {}
_cache_ts = {}

def buscar_cotacao_yahoo(ticker):
    agora = datetime.now(tz).timestamp()
    if ticker in _cache_cotacoes and agora - _cache_ts.get(ticker, 0) < 300:
        return _cache_cotacoes[ticker]
    try:
        symbol = ticker if "." in ticker else (ticker + ".SA" if not ticker[-1].isalpha() == False else ticker)
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
                        "ticker": ticker, "symbol": sym,
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
