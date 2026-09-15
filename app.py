import re
import time
import streamlit as st
from duckduckgo_search import DDGS

st.set_page_config(page_title="Radar Fiscal ICMS", page_icon="⚖️", layout="centered")

st.title("⚖️ Consulta Fiscal de ICMS por Item")
st.caption("Verificador de isenção, alíquotas e fundamentação legal por NCM e UF.")

# Entradas do Usuário
with st.form("form_consulta"):
    ncm = st.text_input("1. Código NCM (ex: 3006.40.20 ou 9018.90.99)", placeholder="Apenas números ou formatado").strip()
    descricao = st.text_input("2. Descrição Comercial (ex: Pinça OPMS / Cimento Ósseo)", placeholder="Nome do item").strip()
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
        r"(?:Convênio\s+ICMS\s+n?º?\s*\d+/\d+)",
        r"(?:Art(?:igo|\.)?\s*\d+º?[A-Z]?(?:\s+do\s+Anexo\s+[I|V|X]+)?)",
        r"(?:Decreto\s+n?º?\s*[\d\.]+)",
        r"(?:RICMS[^\.\,\;]+)",
        r"(?:Isento[^\.\;]+)"
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
        
        # Consultas simplificadas para evitar bloqueio e ampliar alcance
        queries = [
            f'RICMS {uf} ICMS NCM {ncm_formatado} isenção',
            f'RICMS {uf} ICMS NCM {ncm_limpo} isenção',
            f'site:confaz.fazenda.gov.br NCM {ncm_formatado} ICMS',
            f'NCM {ncm_formatado} {descricao} ICMS {uf} "Anexo I"'
        ]
        
        if anvisa:
            queries.append(f'ANVISA {anvisa} ICMS {uf} {ncm_limpo}')

        st.info(f"Buscando enquadramento para NCM **{ncm_formatado}** na UF **{uf}**...")
        
        resultados = []
        vistos = set()

        with st.spinner("Varrendo regulamentos estaduais e convênios CONFAZ..."):
            try:
                with DDGS() as ddgs:
                    for q in queries:
                        try:
                            # Tenta buscar textos sem restrição rígida
                            busca = ddgs.text(q, max_results=4)
                            if busca:
                                for r in busca:
                                    url = r.get("href") or r.get("link") or ""
                                    if url and url not in vistos:
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
                        except Exception as e:
                            pass
                        time.sleep(1)
            except Exception as main_err:
                st.error("Ocorreu uma instabilidade na busca de dados na nuvem. Tente novamente em instantes.")

        if not resultados:
            st.warning(f"Nenhum resultado direto retornado para a busca rápida do NCM {ncm_formatado}. Tente remover os pontos do NCM ou resumir a descrição.")
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
        st.caption("⚠️ **Lembrete de Especialista:** Para aplicação de isenção de ICMS (Art. 111 do CTN), confirme se a descrição do produto na nota fiscal corresponde à cobertura do texto legal localizado.")
