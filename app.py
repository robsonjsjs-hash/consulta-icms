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

def expandir_categorias(desc):
    desc_lower = desc.lower()
    termos = [desc]
    if any(k in desc_lower for k in ["opms", "pinca", "pinça", "cirurgic", "medico", "médico"]):
        termos.extend(["medico-hospitalar", "instrumental cirurgico", "ortese e protese"])
    elif any(k in desc_lower for k in ["cimento", "implante", "protese", "prótese"]):
        termos.extend(["material de osteossintese", "implante ortopedico"])
    return termos

def extrair_fundamento_legal(texto):
    padroes = [
        r"(?:Convênio\s+ICMS\s+n?º?\s*\d+/\d+)",
        r"(?:Art(?:igo|\.)?\s*\d+º?[A-Z]?(?:\s+do\s+Anexo\s+[I|V|X]+)?)",
        r"(?:Decreto\s+n?º?\s*[\d\.]+)",
        r"(?:RICMS[^\.\,\;]+)",
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
        categorias = expandir_categorias(descricao)
        
        queries = [
            f'RICMS {uf} "Anexo I" "isenção" "{ncm_limpo}"',
            f'site:confaz.fazenda.gov.br "Convênio ICMS" "{ncm_limpo}" "isenção"',
            f'"{ncm_limpo}" "{categorias[0]}" ICMS {uf} "Artigo" "Isento"'
        ]
        if anvisa:
            queries.append(f'ANVISA "{anvisa}" "{ncm_limpo}" ICMS {uf} isenção')

        st.info(f"Buscando enquadramento para NCM **{ncm_limpo}** na UF **{uf}**...")
        
        resultados = []
        vistos = set()

        with st.spinner("Varrendo regulamentos estaduais e convênios CONFAZ..."):
            with DDGS() as ddgs:
                for q in queries:
                    try:
                        for r in ddgs.text(q, max_results=3):
                            url = r.get("href") or r.get("link") or ""
                            if url and url not in vistos:
                                vistos.add(url)
                                tit = r.get("title", "")
                                body = r.get("body", "")
                                fundamentos = extrair_fundamento_legal(f"{tit} {body}")
                                resultados.append({"titulo": tit, "url": url, "trecho": body, "fundamentos": fundamentos})
                    except Exception:
                        pass
                    time.sleep(1)

        if not resultados:
            st.warning("Nenhuma norma explícita de isenção encontrada com os termos informados. Verifique se o NCM e a UF estão corretos.")
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
