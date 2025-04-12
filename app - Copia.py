import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="Comparador de Notas Fiscais", layout="centered")
st.title("📄 Comparador de Notas Fiscais - SEFAZ x Cliente")

# === Etapa 1: Upload ===
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

    st.markdown("### 📄 Mapeamento SEFAZ (obrigatório)")
    colunas_sefaz = [""] + sefaz.columns.tolist()
    col_chave_sefaz = st.selectbox("Coluna da CHAVE_NFE", colunas_sefaz)
    col_numero_sefaz = st.selectbox("Coluna do número da nota", colunas_sefaz)
    col_cnpj_sefaz = st.selectbox("Coluna do CNPJ do emitente", colunas_sefaz)
    col_razao_sefaz = st.selectbox("Coluna da Razão Social", colunas_sefaz)

    st.markdown("### 🧾 Selecione as colunas do CLIENTE para comparar")
    usa_chave = st.radio("Deseja comparar usando a CHAVE_NFE?", ["Sim", "Não"])

    colunas_cliente = [""] + cliente.columns.tolist()

    if usa_chave == "Sim":
        col_chave_cliente = st.selectbox("Coluna da CHAVE_NFE no cliente", colunas_cliente)
        col_numero_cliente = None
        col_cnpj_cliente = None
    else:
        col_chave_cliente = None
        col_numero_cliente = st.selectbox("Coluna do número da nota", colunas_cliente)
        col_cnpj_cliente = st.selectbox("Coluna do CNPJ do fornecedor", colunas_cliente)

    if st.button("Comparar 🔍"):
        if (
            (usa_chave == "Sim" and col_chave_cliente and col_chave_sefaz)
            or (
                usa_chave == "Não"
                and col_numero_cliente and col_cnpj_cliente
                and col_numero_sefaz and col_cnpj_sefaz
            )
        ):
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
                },
                "usa_chave": usa_chave == "Sim"
            }
            st.session_state["etapa"] = "comparar"
        else:
            st.warning("⚠️ Selecione corretamente todas as colunas obrigatórias para continuar.")

# === Etapa 3: Comparação ===
if st.session_state.get("etapa") == "comparar":
    st.subheader("3️⃣ Resultado da Comparação")

    sefaz = st.session_state["sefaz"]
    cliente = st.session_state["cliente"]
    mapa = st.session_state["mapa"]

    def limpar_texto(txt):
        if pd.isna(txt): return ""
        txt = str(txt).strip()
        return re.sub(r'\D', '', txt)

    def limpar_num(txt):
        try:
            return int(re.sub(r'\D', '', str(txt)))
        except:
            return None

    if mapa["usa_chave"]:
        sefaz_chaves = pd.DataFrame()
        sefaz_chaves["CHAVE_NFE"] = sefaz[mapa["sefaz"]["chave"]].apply(limpar_texto)

        cliente_chaves = pd.DataFrame()
        cliente_chaves["CHAVE_NFE"] = cliente[mapa["cliente"]["chave"]].apply(limpar_texto)

        colunas_comparar = ["CHAVE_NFE"]
    else:
        sefaz_chaves = pd.DataFrame()
        sefaz_chaves["NUMERO"] = sefaz[mapa["sefaz"]["numero"]].apply(limpar_num)
        sefaz_chaves["CNPJ"] = sefaz[mapa["sefaz"]["cnpj"]].apply(limpar_texto)

        cliente_chaves = pd.DataFrame()
        cliente_chaves["NUMERO"] = cliente[mapa["cliente"]["numero"]].apply(limpar_num)
        cliente_chaves["CNPJ"] = cliente[mapa["cliente"]["cnpj"]].apply(limpar_texto)

        colunas_comparar = ["NUMERO", "CNPJ"]

    sefaz_chaves = sefaz_chaves.dropna().drop_duplicates()
    cliente_chaves = cliente_chaves.dropna().drop_duplicates()

    faltantes = pd.merge(
        sefaz_chaves,
        cliente_chaves,
        how="left",
        on=colunas_comparar,
        indicator=True
    ).query('_merge == "left_only"').drop(columns=["_merge"])

    col_razao_sefaz = mapa["sefaz"]["razao"]

    # 🔧 Corrigir tipos e aplicar limpeza ANTES do merge com razão social
    if not mapa["usa_chave"]:
        faltantes["NUMERO"] = faltantes["NUMERO"].astype(str).apply(limpar_texto)
        faltantes["CNPJ"] = faltantes["CNPJ"].astype(str).apply(limpar_texto)

        sefaz[mapa["sefaz"]["numero"]] = sefaz[mapa["sefaz"]["numero"]].apply(limpar_texto)
        sefaz[mapa["sefaz"]["cnpj"]] = sefaz[mapa["sefaz"]["cnpj"]].apply(limpar_texto)

    # Merge com razão social
    if mapa["usa_chave"]:
        faltantes_com_razao = pd.merge(
            faltantes,
            sefaz[[mapa["sefaz"]["chave"], col_razao_sefaz]],
            left_on="CHAVE_NFE",
            right_on=mapa["sefaz"]["chave"],
            how="left"
        ).drop(columns=[mapa["sefaz"]["chave"]]).rename(columns={col_razao_sefaz: "RAZAO_SOCIAL"})
    else:
        faltantes_com_razao = pd.merge(
            faltantes,
            sefaz[[mapa["sefaz"]["numero"], mapa["sefaz"]["cnpj"], col_razao_sefaz]],
            left_on=["NUMERO", "CNPJ"],
            right_on=[mapa["sefaz"]["numero"], mapa["sefaz"]["cnpj"]],
            how="left"
        ).drop(columns=[mapa["sefaz"]["numero"], mapa["sefaz"]["cnpj"]]).rename(columns={col_razao_sefaz: "RAZAO_SOCIAL"})

    st.success(f"✅ Foram encontradas **{len(faltantes_com_razao)}** notas da SEFAZ que não estão no cliente.")
    st.dataframe(faltantes_com_razao)

    # Exportar como Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        faltantes_com_razao.to_excel(writer, sheet_name="Notas Faltantes", index=False)
        workbook = writer.book
        worksheet = writer.sheets["Notas Faltantes"]
        for col_num, value in enumerate(faltantes_com_razao.columns.values):
            worksheet.write(0, col_num, value)

    st.download_button(
        label="📥 Baixar Excel com notas faltantes + Razão Social",
        data=output.getvalue(),
        file_name="notas_faltantes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
