import re
import time
import streamlit as st
from duckduckgo_search import DDGS

st.set_page_config(page_title="Radar Fiscal ICMS", page_icon="⚖️", layout="centered")

st.title("⚖️ Consulta Fiscal de ICMS por Item")
st.caption("Verificador de isenção, alíquotas e fundamentação legal por NCM e UF.")

# Base interna consolidada (com foco principal no Convênio ICMS 01/99)
REGRAS_FIXAS = {
    "3006.40.20": {
        "status": "ISENTO",
        "convenio": "Convênio ICMS 01/99 (Item/Anexo correspondente)",
        "fundamento_sp": "Artigo 14 do Anexo I do RICMS/SP (Decreto nº 45.490/2000)",
        "descricao_legal": "Cimentos para recomposição óssea, próteses, órteses e implantes médico-hospitalares.",
        "requisito": "Isenção condicionada ao atendimento dos requisitos do Convênio ICMS 01/99 (uso médico/hospitalar e registro sanitário ANVISA)."
    },
    "9018.90.99": {
        "status": "VERIFICAR LISTA DO CONVÊNIO",
        "convenio": "Convênio ICMS 01/99 ou Convênio ICMS 126/10",
        "fundamento_sp": "Artigo 14 ou Artigo 16 do Anexo I do RICMS/SP",
        "descricao_legal": "Instrumentos e aparelhos para medicina e cirurgia.",
        "requisito": "Aplica-se a isenção se a descrição do item constar expressamente na relação anexa ao Convênio ICMS 01/99."
    }
}

# Entradas do Usuário
with st.form("form_consulta"):
    ncm = st.text_input("1. Código NCM (ex: 3006.40.20 ou 9018.90.99)", placeholder="Apenas números ou formatado").strip()
    descricao = st.text_input("2. Descrição Comercial (ex: Cimento Ósseo / Pinça OPMS)", placeholder="Nome do item").strip()
    anvisa = st.text_input("3. Registro ANVISA (Opcional)", placeholder="Número do registro sanitário").strip()
    uf = st.text_input("4. UF de Destino/Operação (ex: SP, MG, RJ)", max_chars=2).strip().upper()
    
    submetido = st.form_submit_button("🔍 Consultar Tributação e Base Legal")

def limpar_ncm(codigo):
    return "".join(filter(str.isdigit, codigo))

def formatar_ncm(codigo):
    digits = limpar_ncm(codigo)
    if len(digits) == 8:
        return f"{digits[:4]}.{digits[4:6]}.{digits[6:]}"
    return codigo

def extrair_fundamento_legal(texto):
    padroes = [
        r"(?:Convênio\s+ICMS\s+n?º?\s*0?1/99)",
        r"(?:Convênio\s+ICMS\s+n?º?\s*\d+/\d+)",
        r"(?:Art(?:igo|\.)?\s*\d+º?[A-Z]?(?:\s+do\s+Anexo\s+[I|V|X]+)?)",
        r"(?:Decreto\s+n?º?\s*[\d\.]+)",
        r"(?:RICMS[^\.\,\;\n]+)",
        r"(?:Isent[o|a][^\.\;\n]+)"
    ]
    encontrados = []
    for p in padroes:
        matches = re.findall(p, texto, re.IGNORECASE)
        for m in matches:
            if m not in encontrados:
                encontrados.append(m.strip())
    return encontrados

if submetido:
    if not ncm or not descricao or not uf:
        st.error("Por favor, preencha NCM, Descrição e UF obrigatoriamente.")
    else:
        ncm_limpo = limpar_ncm(ncm)
        ncm_formatado = formatar_ncm(ncm)
        
        # 1. Checagem direta na regra interna com validação do Convênio 01/99
        if ncm_formatado in REGRAS_FIXAS:
            regra = REGRAS_FIXAS[ncm_formatado]
            st.success(f"✅ Enquadramento Localizado pelo Convênio ICMS 01/99!")
            
            st.markdown(f"### Status: **{regra['status']}**")
            st.markdown(f"**Norma Nacional:** `{regra['convenio']}`")
            if uf == "SP":
                st.markdown(f"**Regulamento Estadual (SP):** `{regra['fundamento_sp']}`")
            st.markdown(f"**Descrição Legal:** {regra['descricao_legal']}")
            st.info(f"📌 **Requisito do Convênio 01/99:** {regra['requisito']}")
            
        else:
            # 2. Busca na Web priorizando a consulta ao Convênio 01/99 e RICMS da UF
            queries = [
                f'"Convênio ICMS 01/99" "{ncm_formatado}" isenção',
                f'"Convênio ICMS 1/99" "{ncm_formatado}"',
                f'RICMS {uf} NCM "{ncm_formatado}" "Anexo I" isenção',
                f'site:confaz.fazenda.gov.br "{ncm_formatado}" "01/99"',
                f'site:legisweb.com.br ICMS {uf} NCM "{ncm_formatado}" isenção'
            ]
            
            st.info(f"Consultando varredura para NCM **{ncm_formatado}** na UF **{uf}** com foco no Convênio ICMS 01/99...")
            
            resultados = []
            vistos = set()

            DOMINIOS_ACEITOS = [
                ".gov.br", "legisweb.com.br", "normaslegais.com.br", 
                "contabeis.com.br", "jusbrasil.com.br", "itarget.com.br"
            ]

            with st.spinner("Buscando na base do CONFAZ e RICMS estaduais..."):
                try:
                    with DDGS() as ddgs:
                        for q in queries:
                            try:
                                busca = ddgs.text(q, region="br-pt", max_results=5)
                                if busca:
                                    for r in busca:
                                        url = r.get("href") or r.get("link") or ""
                                        if url and url not in vistos and any(dom in url.lower() for dom in DOMINIOS_ACEITOS):
                                            vistos.add(url)
                                            tit = r.get("title", "")
                                            body = r.get("body", "")
                                            fundamentos = extrair_fundamento_legal(f"{tit} {body}")
                                            resultados.append({
                                                "titulo": tit,
                                                "url": url,
                                                "trecho": body,
                                                "fundamentos": fundamentos
                                            })
                            except Exception:
                                pass
                            time.sleep(1)
                except Exception:
                    st.error("Instabilidade na consulta externa.")

            if not resultados:
                st.warning(f"Não foram encontradas menções explícitas ao Convênio ICMS 01/99 para o NCM {ncm_formatado}. Confirme se o item se enquadra em outro convênio hospitalar (ex: Convênio 126/10 ou 52/91).")
            else:
                st.success(f"Encontradas {len(resultados)} referências jurídicas e oficiais!")
                
                for res in resultados:
                    with st.expander(f"📌 {res['titulo']}", expanded=True):
                        st.write(f"**Link Oficial:** [{res['url']}]({res['url']})")
                        if res['fundamentos']:
                            st.markdown("**Base Legal Identificada:**")
                            for f in res['fundamentos']:
                                st.markdown(f"- `👉 {f}`")
                        st.write(f"**Trecho da Norma:** {res['trecho']}")

        st.divider()
        st.caption("⚠️ **Lembrete de Especialista:** Para aplicação do Convênio ICMS 01/99 (Art. 111 do CTN), verifique rigorosamente se a descrição do item na Nota Fiscal corresponde exatamente à lista do CONFAZ e se há o Registro ANVISA correspondente.")
