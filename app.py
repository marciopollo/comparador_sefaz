import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Comparador de Notas Fiscais", layout="centered")
st.title("📄 Comparador de Notas Fiscais - SEFAZ x Cliente")

# === Funções auxiliares ===
def limpar_texto(txt):
    if pd.isna(txt): return ""
    return re.sub(r'\D', '', str(txt)).strip()

def limpar_num(txt):
    try:
        return int(re.sub(r'\D', '', str(txt)))
    except:
        return None

def pad_cnpj(cnpj):
    cnpj = limpar_texto(cnpj)
    return cnpj.zfill(14) if cnpj else ""

def pad_numero(numero):
    numero = limpar_texto(numero)
    return numero.lstrip('0')

# === Etapa 1: Upload dos arquivos ===
with st.form("upload_form"):
    st.subheader("1️⃣ Enviar arquivos CSV")
    arquivo_sefaz = st.file_uploader("📁 Selecione o arquivo Sefaz", type=["csv"])
    arquivo_cliente = st.file_uploader("📁 Selecione o arquivo Cliente", type=["csv"])
    submitted = st.form_submit_button("Avançar ➡️")

if submitted and arquivo_sefaz and arquivo_cliente:
    try:
        sefaz = pd.read_csv(arquivo_sefaz, sep=";", encoding="utf-8-sig", engine="python", dtype=str, index_col=False)
        cliente = pd.read_csv(arquivo_cliente, sep=";", encoding="utf-8-sig", engine="python", dtype=str, index_col=False)

        sefaz.columns = sefaz.columns.str.strip()
        cliente.columns = cliente.columns.str.strip()

        st.session_state["sefaz"] = sefaz
        st.session_state["cliente"] = cliente
        st.session_state["etapa"] = "mapear"

        st.success("✅ Arquivos carregados com sucesso!")

    except Exception as e:
        st.error(f"Erro ao ler os arquivos: {e}")

# === Etapa 2: Mapeamento das colunas ===
if st.session_state.get("etapa") == "mapear":
    st.subheader("2️⃣ Mapear colunas")
    sefaz = st.session_state["sefaz"]
    cliente = st.session_state["cliente"]

    colunas_sefaz = [""] + sefaz.columns.tolist()
    colunas_cliente = [""] + cliente.columns.tolist()

    st.markdown("### 📄 Mapeamento SEFAZ")
    col_chave_sefaz = st.selectbox("Coluna da CHAVE_NFE (opcional)", colunas_sefaz)
    col_numero_sefaz = st.selectbox("Coluna do número da nota", colunas_sefaz)
    col_cnpj_sefaz = st.selectbox("Coluna do CNPJ do emitente", colunas_sefaz)
    col_razao_sefaz = st.selectbox("Coluna da Razão Social", colunas_sefaz)

    st.markdown("### 🧾 Mapeamento CLIENTE")
    col_chave_cliente = st.selectbox("Coluna da CHAVE_NFE (opcional)", colunas_cliente)
    col_numero_cliente = st.selectbox("Coluna do número da nota", colunas_cliente)
    col_cnpj_cliente = st.selectbox("Coluna do CNPJ do fornecedor", colunas_cliente)

    if st.button("Comparar 🔍"):
        st.session_state["mapa"] = {
            "sefaz": {
                "chave": col_chave_sefaz,
                "numero": col_numero_sefaz,
                "cnpj": col_cnpj_sefaz,
                "razao": col_razao_sefaz
            },
            "cliente": {
                "chave": col_chave_cliente,
                "numero": col_numero_cliente,
                "cnpj": col_cnpj_cliente
            }
        }
        st.session_state["etapa"] = "comparar"

# === Etapa 3: Comparar usando for ===
if st.session_state.get("etapa") == "comparar":
    st.subheader("3️⃣ Resultado da Comparação")

    sefaz = st.session_state["sefaz"]
    cliente = st.session_state["cliente"]
    mapa = st.session_state["mapa"]

    chaves_cliente = set()

    # Preferência pela CHAVE_NFE se existir
    if mapa["cliente"]["chave"] and mapa["sefaz"]["chave"]:
        chaves_cliente = set(cliente[mapa["cliente"]["chave"]].dropna().map(limpar_texto))
        faltantes = []
        for _, row in sefaz.iterrows():
            chave = limpar_texto(row[mapa["sefaz"]["chave"]])
            if chave not in chaves_cliente:
                faltantes.append({
                    "CHAVE_NFE": chave,
                    "RAZAO_SOCIAL": row[mapa["sefaz"]["razao"]]
                })

    else:
        # Comparar por NUMERO + CNPJ com padding correto
        cliente_chaves = set(
            cliente.dropna(subset=[mapa["cliente"]["numero"], mapa["cliente"]["cnpj"]])
            .apply(lambda r: f"{pad_numero(r[mapa['cliente']['numero']])}-{pad_cnpj(r[mapa['cliente']['cnpj']])}", axis=1)
        )

        faltantes = []
        for _, row in sefaz.iterrows():
            chave = f"{pad_numero(row[mapa['sefaz']['numero']])}-{pad_cnpj(row[mapa['sefaz']['cnpj']])}"
            if chave not in cliente_chaves:
                faltantes.append({
                    "NUMERO": pad_numero(row[mapa["sefaz"]["numero"]]),
                    "CNPJ": pad_cnpj(row[mapa["sefaz"]["cnpj"]]),
                    "RAZAO_SOCIAL": row[mapa["sefaz"]["razao"]]
                })

    resultado_df = pd.DataFrame(faltantes)
    st.success(f"✅ Foram encontradas {len(resultado_df)} notas da SEFAZ que não estão no cliente.")
    st.dataframe(resultado_df)

    # Exportar como Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        resultado_df.to_excel(writer, sheet_name="Notas Faltantes", index=False)
        workbook = writer.book
        worksheet = writer.sheets["Notas Faltantes"]
        for col_num, value in enumerate(resultado_df.columns.values):
            worksheet.write(0, col_num, value)

    st.download_button(
        label="📥 Baixar Excel com notas faltantes",
        data=output.getvalue(),
        file_name="notas_faltantes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
