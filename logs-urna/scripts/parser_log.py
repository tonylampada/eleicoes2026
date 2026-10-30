#!/usr/bin/env python3
"""Parser do log da urna (logd.dat dentro de <seção>-log.jez) -> métricas agregadas por seção.

Só lê o texto do log; NÃO guarda linhas brutas, números de título/CPF de mesários ou eleitores,
nem nada que identifique voto. Os modelos de evento têm todos os dígitos trocados por '#'.

Formato observado de cada linha (separador TAB):
    DD/MM/AAAA HH:MM:SS <TAB> nível <TAB> nº de série da urna <TAB> aplicação <TAB> mensagem <TAB> código
O horário é o relógio da própria urna (hora local da seção; ver README).
"""
from __future__ import annotations

import io
import re
import statistics as st
import zipfile
from collections import Counter

PARSER_VERSION = "1.1.0"

# dia da votação e códigos de pleito por turno (nome dos arquivos: o<pleito><uf><mun5><zona4><secao4>-log.jez)
TURNOS = {1: {"dia": "04/10/2026", "pleito": "03220"}, 2: {"dia": "25/10/2026", "pleito": "03221"}}

LIMIARES_S = (5, 10, 20, 30)   # pares de votos consecutivos com intervalo < N segundos
RAJADA_S = (10, 20)            # maior sequência de votos com todos os intervalos < N segundos

M_VOTO = "O voto do eleitor foi computado"
M_PRONTA = "Urna pronta para receber votos"
M_HAB = "Eleitor foi habilitado"
M_AGUARDA = "Aguardando digitação do identificador do eleitor"
M_ID_TIT = "Identificador digitado pelo mesário foi: (Título de eleitor)"
M_ID_CPF = "Identificador digitado pelo mesário foi: (CPF)"
M_BIO = "Tipo de habilitação do eleitor [biométrica]"
M_MANUAL = "Solicitação de dado pessoal do eleitor para habilitação manual"
M_NASC = "Ano de nascimento digitado é igual ao do cadastro"

# contagens fixas (coluna -> (aplicação ou None = qualquer, predicado sobre a mensagem))
CONTAGENS = {
    "n_urna_ligada": ("LOGD", lambda m: m.startswith("Urna ligada em ")),
    "n_desligada_chave": ("INITJE", lambda m: m == "Urna desligada pela chave"),
    "n_votacao_suspensa": ("VOTA", lambda m: m == "Votação suspensa"),
    "n_reinicio_votacao": ("VOTA", lambda m: m == "Mesário confirmou o reinício da votação"),
    "n_urna_pronta": ("VOTA", lambda m: m == M_PRONTA),
    "n_bateria_interna": ("VOTA", lambda m: m == "Urna operando na bateria interna"),
    "n_log_contingencia_validado": ("LOGD", lambda m: m == "Log interno da urna de contingência validado com sucesso"),
    "n_log_me_corrompido": ("LOGD", lambda m: m == "Identificado arquivo de log corrompido na ME"),
    "n_impressora_problema": ("VOTA", lambda m: m.startswith("Impressora sem papel") or m.startswith("Impressora atolada")),
    "n_encerramento_cancelado": ("VOTA", lambda m: m == "Operador cancelou o encerramento da votação"
                                 or m == "Procedimento de encerramento abortado"),
    "n_encerramento_antes_hora": ("VOTA", lambda m: m.startswith("Encerramento só pode ser solicitado após")),
    "n_identificador_invalido": ("VOTA", lambda m: m == "Identificador do eleitor digitado inválido"),
    "n_eleitor_nao_encontrado": ("VOTA", lambda m: m == "Eleitor não encontrado para o identificador informado"),
    "n_eleitor_ja_votou": ("VOTA", lambda m: m == "O eleitor identificado já votou"),
    "n_eleitor_impedido": ("VOTA", lambda m: m.startswith("Eleitor impedido - ")),
    "n_justificativa": ("VOTA", lambda m: m == "Justificativa recebida"),
    "n_eleitor_suspenso": ("VOTA", lambda m: m == "Eleitor foi suspenso pelo mesário"),
    "n_hab_cancelada": ("VOTA", lambda m: m.startswith("Habilitação cancelada")),
    "n_digital_solicitada": ("VOTA", lambda m: m.startswith("Solicita digital. Tentativa")),
    "n_digital_timeout": ("VOTA", lambda m: m.startswith("Timeout de reconhecimento do dedo")),
    "n_digital_nao_corresponde": ("VOTA", lambda m: m.startswith("Digital capturada não corresponde")),
    "n_ano_nasc_diferente": ("VOTA", lambda m: m == "Ano de nascimento digitado é diferente do cadastro"),
    "n_eleitor_corrigiu": ("VOTA", lambda m: m == "Eleitor corrigiu na tela de confirmação de candidato"),
    "n_tecla_indevida": ("VOTA", lambda m: m == "Tecla indevida pressionada"),
    "n_voto_confirmado_presidente": ("VOTA", lambda m: m == "Voto confirmado para [Presidente]"),
}
# mensagens INFO que vão para a tabela longa de eventos (além de todo nível != INFO)
INFO_EVENTOS = (
    "Urna ligada em ", "Urna desligada pela chave", "Votação suspensa", "Apresentada tela do reinício",
    "Mesário confirmou o reinício", "Urna operando na bateria interna", "Log interno da urna de contingência",
    "Copiando conteúdo da pasta logs", "Adicionando informação do log da ME", "Desligando a urna",
    "Eleitor impedido - ", "Eleitor foi suspenso", "Operador cancelou o encerramento", "Mesário indicou reimprimir",
    "Imprimindo relatório de estado da urna", "Operador confirmou que concluiu a manutenção na impressora",
    "Todas as pessoas presentes já votaram? NÃO", "Mudança do estado da chave",
)
RX_DIG = re.compile(r"\d+")


def modelo(msg: str) -> str:
    return RX_DIG.sub("#", msg)


def ler_jez(blob: bytes) -> list[tuple[str, str]]:
    """Retorna [(nome, texto)] do logd.dat principal e dos logs arquivados (.jez aninhados)."""
    out = []
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for n in z.namelist():
            b = z.read(n)
            if n.endswith(".dat"):
                out.append((n, b.decode("latin-1")))
            elif n.endswith(".jez"):
                with zipfile.ZipFile(io.BytesIO(b)) as zz:
                    for nn in zz.namelist():
                        if nn.endswith(".dat"):
                            out.append((f"{n}/{nn}", zz.read(nn).decode("latin-1")))
    out.sort(key=lambda x: x[0] != "logd.dat")  # principal primeiro
    return out


def _seg(hms: str) -> int:
    return int(hms[0:2]) * 3600 + int(hms[3:5]) * 60 + int(hms[6:8])


def _hms(s):
    if s is None:
        return None
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def parse_secao(blob: bytes, turno: int) -> tuple[dict, Counter]:
    dia = TURNOS[turno]["dia"]
    outros = {v["dia"] for k, v in TURNOS.items() if k != turno}
    arquivos = ler_jez(blob)
    vistos = set()
    linhas = []  # (seg, ordem, nível, serial, app, msg, arquivo_idx)
    votos_fora = 0
    ordem = 0
    for idx, (_, txt) in enumerate(arquivos):
        for l in txt.splitlines():
            d = l[:10]
            if d != dia:
                if M_VOTO in l and d not in outros:
                    votos_fora += 1
                continue
            if l in vistos:  # mesma linha (inclui código final) em dois arquivos = duplicata
                continue
            vistos.add(l)
            p = l.split("\t")
            if len(p) < 5:
                continue
            ordem += 1
            linhas.append((_seg(p[0][11:19]), ordem, p[1], p[2], p[3], p[4], idx))
    linhas.sort(key=lambda x: (x[0], x[1]))

    c = Counter()
    ev = Counter()
    seriais_linhas, seriais_voto = set(), set()
    votos = []
    votos_arquivados = 0
    pronta = []
    enc = {"inicio": None, "confirmado": None, "bu": None}
    hab_pend = None
    cabine = []
    sess = {"bio": False, "manual": False, "nasc": False, "id": None}
    hab = Counter()
    for seg, _, niv, ser, app, msg, idx in linhas:
        seriais_linhas.add(ser)
        for col, (a, f) in CONTAGENS.items():
            if a == app and f(msg):
                c[col] += 1
        if niv != "INFO" or (app != "GAP" and msg.startswith(INFO_EVENTOS)):
            ev[(app, niv, modelo(msg))] += 1
        if app != "VOTA":
            continue
        if msg == M_VOTO:
            votos.append(seg)
            seriais_voto.add(ser)
            if idx > 0:
                votos_arquivados += 1
            if hab_pend is not None:
                cabine.append(seg - hab_pend)
                hab_pend = None
        elif msg == M_AGUARDA:
            sess = {"bio": False, "manual": False, "nasc": False, "id": None}
        elif msg == M_ID_TIT:
            sess["id"] = "titulo"
        elif msg == M_ID_CPF:
            sess["id"] = "cpf"
        elif msg == M_BIO:
            sess["bio"] = True
        elif msg == M_MANUAL:
            sess["manual"] = True
        elif msg == M_NASC:
            sess["nasc"] = True
        elif msg == M_HAB:
            if sess["bio"]:
                hab["n_hab_biometrica"] += 1
            elif sess["manual"]:
                hab["n_hab_manual"] += 1
            elif sess["nasc"]:
                hab["n_hab_ano_nascimento"] += 1
            else:
                hab["n_hab_outra"] += 1
            if sess["id"] == "titulo":
                hab["n_id_titulo"] += 1
            elif sess["id"] == "cpf":
                hab["n_id_cpf"] += 1
            hab_pend = seg
            sess = {"bio": False, "manual": False, "nasc": False, "id": None}
        elif msg == M_PRONTA:
            pronta.append(seg)
        elif msg == "Inicio do Encerramento":
            enc["inicio"] = seg
        elif msg == "Procedimento de encerramento confirmado":
            enc["confirmado"] = seg
        elif msg.startswith("Imprimindo relatório [BU] via nº [1]"):
            enc["bu"] = seg

    votos.sort()
    n = len(votos)
    intervalos = [b - a for a, b in zip(votos, votos[1:])]
    por_hora = [0] * 24
    for s in votos:
        por_hora[s // 3600] += 1
    int_hora = [[] for _ in range(24)]
    for s, d in zip(votos[1:], intervalos):
        int_hora[s // 3600].append(d)

    def rajada(lim):
        best = cur = 1 if n else 0
        for d in intervalos:
            cur = cur + 1 if d < lim else 1
            best = max(best, cur)
        return best

    dur = (votos[-1] - votos[0]) if n >= 2 else None
    r = {
        "parser_version": PARSER_VERSION,
        "n_arquivos_log": len(arquivos),
        "n_urnas_log": len(seriais_linhas),
        "n_urnas_com_voto": len(seriais_voto),
        "n_linhas_dia": len(linhas),
        "hr_abertura_log": _hms(min(pronta)) if pronta else None,
        "hr_encerramento_log": _hms(enc["confirmado"]),
        "hr_inicio_encerramento_log": _hms(enc["inicio"]),
        "hr_impressao_bu_log": _hms(enc["bu"]),
        "n_votos_log": n,
        "n_votos_logs_arquivados": votos_arquivados,
        "n_votos_fora_do_dia": votos_fora,
        "hr_primeiro_voto": _hms(votos[0]) if n else None,
        "hr_ultimo_voto": _hms(votos[-1]) if n else None,
        "votos_por_hora": por_hora,
        "intervalo_mediano_s": float(st.median(intervalos)) if intervalos else None,
        "intervalo_medio_s": round(st.fmean(intervalos), 3) if intervalos else None,
        "intervalo_min_s": min(intervalos) if intervalos else None,
        "intervalo_p10_s": float(sorted(intervalos)[len(intervalos) // 10]) if intervalos else None,
        "intervalo_mediano_por_hora_s": [float(st.median(x)) if x else None for x in int_hora],
        "velocidade_media_votos_hora": round(n / (dur / 3600), 3) if dur else None,
        "tempo_cabine_mediano_s": float(st.median(cabine)) if cabine else None,
    }
    for lim in LIMIARES_S:
        k = sum(1 for d in intervalos if d < lim)
        r[f"n_pares_lt{lim}s"] = k
        r[f"pct_pares_lt{lim}s"] = round(100 * k / len(intervalos), 4) if intervalos else None
    for lim in RAJADA_S:
        r[f"maior_rajada_lt{lim}s"] = rajada(lim)
    for k in ("n_hab_biometrica", "n_hab_manual", "n_hab_ano_nascimento", "n_hab_outra", "n_id_titulo", "n_id_cpf"):
        r[k] = hab[k]
    r["n_habilitados"] = sum(hab[k] for k in ("n_hab_biometrica", "n_hab_manual", "n_hab_ano_nascimento", "n_hab_outra"))
    for col in CONTAGENS:
        r[col] = c[col]
    r["n_erro"] = sum(v for (a, nv, _), v in ev.items() if nv == "ERRO")
    r["n_alerta"] = sum(v for (a, nv, _), v in ev.items() if nv == "ALERTA")
    return r, ev
