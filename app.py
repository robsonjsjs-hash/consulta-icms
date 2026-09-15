import re
import time
import streamlit as st
from duckduckgo_search import DDGS

st.set_page_config(page_title="Radar Fiscal ICMS", page_icon="⚖️", layout="centered")

st.title("⚖️ Consulta Fiscal de ICMS por Item")
st.caption("Validador de Isenção (Convênio ICMS 01/99 / RICMS) por NCM, Descrição e ANVISA.")

# Dicionário de validação estrita por Descrição e NCM (Regras Oficiais)
# A isenção só se aplica se a NCM E a Descrição baterem com o texto legal
REGRAS_DESCRICAO = [
    {
        "ncm": "30064020",
        "termos_isentos": ["cimento", "cimento osseo", "cimento para recomposicao"],
        "termos_tributados": ["enxerto", "enxerto osseo", "matriz ossea", "substituto osseo"],
        "convenio": "Convênio ICMS 01/99",
        "fundamento_sp": "Artigo 14 do Anexo I do RICMS/SP",
        "item_anexo": "Cimentos para recomposição óssea",
        "obs": "O benefício do Conv. 01/99 é TAXATIVO. O 'Cimento Ósseo' é isento, mas 'Enxertos Ósseos' e substitutos biológicos sob a mesma NCM não constam na norma, sendo TRIBUTADOS INTEGRALMENTE."
    }
]

# Entradas do Usuário
with st.form("form_consulta"):
    ncm = st.text_input("1. Código NCM (ex: 3006.40.20 ou 9018.90.99)", placeholder="Apenas números ou formatado").strip()
    descricao = st.text_input("2. Descrição Comercial do Item (Obrigatório)", placeholder="Ex: Enxerto Ósseo / Cimento Ósseo / Pinça OPMS").strip()
    anvisa = st.text_input("3. Registro ANVISA (Opcional)", placeholder="Número do registro sanitário").strip()
    uf = st.text_input("4. UF de Operação (ex: SP, MG, RJ)", max_chars=2).strip().upper()
    
    submetido = st.form_submit_button("🔍 Consultar Tributação e Base Legal")

def limpar_texto(txt):
    txt_limpo = re.sub(r'[^\w\s]', '', txt.lower())
    return " ".join(txt_limpo.split())

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
        r"(?:RICMS[^\.\,\;\n]+)"
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
        desc_limpa = limpar_texto(descricao)
        
        enquadramento_encontrado = False

        # 1. Análise Estrita: Cruzamento NCM + Descrição Comercial
        for regra in REGRAS_DESCRICAO:
            if regra["ncm"] == ncm_limpo:
                # Checa se a descrição bate com termos TRIBUTADOS (Exclusões da Isenção)
                if any(termo in desc_limpa for termo in regra["termos_tributados"]):
                    enquadramento_encontrado = True
                    st.error(f"❌ **PRODUTO TRIBUTADO INTEGRALMENTE ({uf})**")
                    st.markdown(f"**Item Consultado:** `{descricao}` | **NCM:** `{ncm_formatado}`")
                    st.warning(f"⚠️ **Motivo:** {regra['obs']}")
                    st.markdown(f"**Base Comparativa:** O `{regra['convenio']}` ({regra['fundamento_sp']}) concede isenção **apenas** para *'{regra['item_anexo']}'*.")
                    break
                
                # Checa se a descrição bate com termos ISENTOS
                elif any(termo in desc_limpa for termo in regra["termos_isentos"]):
                    enquadramento_encontrado = True
                    st.success(f"✅ **PRODUTO ISENTO DE ICMS ({uf})**")
                    st.markdown(f"**Base Legal:** `{regra['convenio']}` | `{regra['fundamento_sp']}`")
                    st.markdown(f"**Descrição no Anexo:** *{regra['item_anexo']}*")
                    if anvisa:
                        st.info(f"📋 **ANVISA Informado:** `{anvisa}` — Requisito do Convênio preenchido.")
                    else:
                        st.warning("⚠️ **Atenção:** A isenção exige registro regular na ANVISA para fins hospitalares.")
                    break

        # 2. Se for um NCM/Descrição genérico fora da regra fixa, consulta Web Avançada
        if not enquadramento_encontrado:
            st.info(f"Consultando bases do CONFAZ e RICMS/{uf} para a descrição **'{descricao}'** na NCM **{ncm_formatado}**...")
            
            # Busca rigorosa exigindo o NCM E a Descrição exata do produto
            queries = [
                f'"Convênio ICMS 01/99" "{ncm_formatado}" "{descricao}"',
                f'RICMS {uf} "{ncm_formatado}" "{descricao}" "Anexo I"',
                f'site:confaz.fazenda.gov.br "{ncm_formatado}" "{descricao}"',
                f'site:legisweb.com.br ICMS {uf} "{ncm_formatado}" "{descricao}"'
            ]
            
            resultados = []
            vistos = set()

            DOMINIOS_ACEITOS = [
                ".gov.br", "legisweb.com.br", "normaslegais.com.br", 
                "contabeis.com.br", "jusbrasil.com.br", "itarget.com.br"
            ]

            with st.spinner("Analisando amparo legal..."):
                try:
                    with DDGS() as ddgs:
                        for q in queries:
                            try:
                                busca = ddgs.text(q, region="br-pt", max_results=4)
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
                    st.error("Erro na busca de apoio.")

            if not resultados:
                st.warning(f"⚠️ **Não foi localizada Isenção Explicita para '{descricao}' (NCM {ncm_formatado}).**\n\nPor regra geral do CTN (Art. 111 - interpretação literal), itens que não constam com a descrição exata nos anexos do Convênio 01/99 ou RICMS/{uf} devem ser **TRIBUTADOS INTEGRALMENTE**.")
            else:
                st.success(f"Encontradas {len(resultados)} referências jurídicas para análise:")
                for res in resultados:
                    with st.expander(f"📌 {res['titulo']}", expanded=True):
                        st.write(f"**Link Oficial:** [{res['url']}]({res['url']})")
                        if res['fundamentos']:
                            st.markdown("**Fundamentos Localizados:**")
                            for f in res['fundamentos']:
                                st.markdown(f"- `👉 {f}`")
                        st.write(f"**Trecho da Norma:** {res['trecho']}")

        st.divider()
        st.caption("⚠️ **Análise Fiscal:** A isenção de ICMS é de interpretação estrita (Art. 111 do CTN). Havendo divergência entre a descrição comercial e o texto da lei, prevalece a tributação integral.")
