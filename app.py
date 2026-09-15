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
        r"(?:Convênio\s+ICMS\s+n?º?\s*\d+/\d+)",
        r"(?:Art(?:igo|\.)?\s*\d+º?[A-Z]?(?:\s+do\s+Anexo\s+[I|V|X]+)?)",
        r"(?:Decreto\s+n?º?\s*[\d\.]+)",
        r"(?:RICMS[^\.\,\;]+)",
        r"(?:Isento[^\.\;\n]+)",
        r"(?:Isenção[^\.\;\n]+)"
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
        
        # Consultas focadas em legislação brasileira do estado
        queries = [
            f'site:fazenda.{uf.lower()}.gov.br "{ncm_formatado}" isenção ICMS',
            f'site:confaz.fazenda.gov.br "{ncm_formatado}" isenção ICMS',
            f'RICMS {uf} NCM "{ncm_formatado}" "Anexo I" "isenção"',
            f'RICMS {uf} NCM "{ncm_limpo}" "isenção" "{descricao}"',
            f'site:legisweb.com.br ICMS {uf} NCM "{ncm_formatado}" isenção'
        ]
        
        if anvisa:
            queries.append(f'ANVISA "{anvisa}" ICMS {uf} "{ncm_formatado}" isenção')

        st.info(f"Buscando enquadramento fiscal para NCM **{ncm_formatado}** na UF **{uf}**...")
        
        resultados = []
        vistos = set()

        # Domínios confiáveis aceitos para evitar resultados genéricos de fora do Brasil
        DOMINIOS_ACEITOS = [
            ".gov.br", "legisweb.com.br", "normaslegais.com.br", 
            "contabeis.com.br", "jusbrasil.com.br", "itarget.com.br"
        ]

        with st.spinner("Varrendo regulamentos estaduais da Sefaz e CONFAZ..."):
            try:
                with DDGS() as ddgs:
                    for q in queries:
                        try:
                            # Força a regionalização br-pt (Brasil em Português)
                            busca = ddgs.text(q, region="br-pt", max_results=5)
                            if busca:
                                for r in busca:
                                    url = r.get("href") or r.get("link") or ""
                                    
                                    # Valida se a URL é de uma fonte jurídica/oficial válida
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
                st.error("Ocorreu uma instabilidade na busca de dados. Tente novamente em instantes.")

        if not resultados:
            st.warning(f"Nenhum artigo explícito de isenção localizado para o NCM {ncm_formatado} na UF {uf}. Verifique se o produto é tributado integralmente ou se há redução de base de cálculo em vez de isenção.")
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
