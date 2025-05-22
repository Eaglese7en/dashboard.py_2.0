import streamlit as st
import pandas as pd
import sqlite3
from contextlib import closing
from pathlib import Path
import requests
import smtplib
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

# -------------------------------------------------
# Configurações Gerais
# -------------------------------------------------
st.set_page_config(
    page_title="Oficina Dashboard",
    page_icon="🚗",
    layout="wide",
)

DB_PATH = "workshop.db"
ARQUIVOS_DIR = Path("relatorios")
ARQUIVOS_DIR.mkdir(exist_ok=True)

# -------------------------------------------------
# Utilidades de Conexão
# -------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_connection():
    """Retorna uma conexão SQLite cacheada."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # acesso por nome
    return conn


def ensure_column(cursor, table: str, column: str, ddl: str):
    """Garante que uma coluna exista; se não existir, adiciona."""
    cursor.execute(f"PRAGMA table_info({table})")
    if column not in [row[1] for row in cursor.fetchall()]:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db():
    """Cria as tabelas do banco, caso ainda não existam e adiciona colunas de data."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        # Tabelas
        cur.execute(
            """CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    telefone TEXT
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS carros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id INTEGER,
                    modelo TEXT,
                    ano INTEGER,
                    cor TEXT,
                    status TEXT DEFAULT 'Em revisão',
                    FOREIGN KEY(cliente_id) REFERENCES clientes(id)
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS orcamentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    carro_id INTEGER,
                    servico TEXT,
                    preco_estimado REAL,
                    preco_final REAL,
                    FOREIGN KEY(carro_id) REFERENCES carros(id)
            )"""
        )
        # Colunas de data (adiciona se não existir)
        ensure_column(cur, "clientes", "criado_em", "TEXT DEFAULT (datetime('now','localtime'))")
        ensure_column(cur, "carros", "criado_em", "TEXT DEFAULT (datetime('now','localtime'))")
        ensure_column(cur, "orcamentos", "criado_em", "TEXT DEFAULT (datetime('now','localtime'))")
        conn.commit()

# -------------------------------------------------
# Estilo e Animações opcionais
# -------------------------------------------------

def carregar_lottie(url: str):
    try:
        from streamlit_lottie import st_lottie
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def apply_status_style(df: pd.DataFrame) -> pd.DataFrame.style:
    colors = {
        "Em revisão": "#F7DC6F",
        "Pronto": "#82E0AA",
        "Aguardando peças": "#F5B7B1",
    }
    def highlight(val):
        color = colors.get(val, "#D5DBDB")
        return f"background-color:{color};font-weight:600;"
    return df.style.applymap(highlight, subset=["status"])

# -------------------------------------------------
# Funções Auxiliares
# -------------------------------------------------

def enviar_email(destinatario: str, arquivo: Path, assunto: str):
    """Envia um e‑mail com o arquivo em anexo usando credenciais em st.secrets."""
    if "email" not in st.secrets:
        st.warning("⚠️ Configure suas credenciais em .streamlit/secrets.toml para usar e‑mail.")
        return
    creds = st.secrets["email"]
    msg = MIMEMultipart()
    msg["From"] = creds["user"]
    msg["To"] = destinatario
    msg["Subject"] = assunto
    msg.attach(MIMEText("Relatório diário gerado pela Oficina Dashboard.", "plain"))

    part = MIMEBase("application", "octet-stream")
    with open(arquivo, "rb") as f:
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename={arquivo.name}")
    msg.attach(part)

    try:
        with smtplib.SMTP(creds.get("smtp", "smtp.gmail.com"), int(creds.get("port", 587))) as server:
            server.starttls()
            server.login(creds["user"], creds["password"])
            server.send_message(msg)
        st.success("📧 E‑mail enviado com sucesso!")
    except Exception as e:
        st.error(f"Erro ao enviar e‑mail: {e}")

# -------------------------------------------------
# Páginas
# -------------------------------------------------

def pagina_inicio():
    st.title("Dashboard da Oficina 🚗")
    st.write("Acompanhe clientes, veículos e orçamentos em um único lugar.")
    anim = carregar_lottie("https://assets9.lottiefiles.com/packages/lf20_tutvdkg0.json")
    if anim:
        from streamlit_lottie import st_lottie
        st_lottie(anim, height=250, key="anim")


def pagina_clientes():
    st.header("📇 Clientes")
    with st.form("form_cliente", clear_on_submit=True):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome")
        telefone = col2.text_input("Telefone")
        if st.form_submit_button("Adicionar"):
            if nome:
                with closing(get_connection()) as conn:
                    conn.execute("INSERT INTO clientes (nome, telefone) VALUES (?,?)", (nome, telefone))
                    conn.commit()
                st.toast("Cliente adicionado!", icon="✅")
    clientes = pd.read_sql("SELECT * FROM clientes", get_connection())
    st.dataframe(clientes, use_container_width=True)


def pagina_carros():
    st.header("🚙 Veículos")
    clientes = pd.read_sql("SELECT * FROM clientes", get_connection())
    if clientes.empty:
        st.info("Cadastre um cliente antes.")
        return
    with st.form("form_carro", clear_on_submit=True):
        cliente_nome = st.selectbox("Cliente", clientes["nome"])
        cliente_id = clientes.loc[clientes["nome"] == cliente_nome, "id"].iloc[0]
        col1, col2 = st.columns(2)
        modelo = col1.text_input("Modelo")
        ano = col2.number_input("Ano", 1900, 2100, step=1, value=2023)
        col3, col4 = st.columns(2)
        cor = col3.text_input("Cor")
        status = col4.selectbox("Status", ["Em revisão", "Pronto", "Aguardando peças"])
        if st.form_submit_button("Adicionar"):
            if modelo:
                with closing(get_connection()) as conn:
                    conn.execute("""
                        INSERT INTO carros (cliente_id, modelo, ano, cor, status)
                        VALUES (?,?,?,?,?)
                    """, (cliente_id, modelo, ano, cor, status))
                    conn.commit()
                st.toast("Veículo registrado!", icon="🚗")
    carros = pd.read_sql("""
        SELECT carros.id, clientes.nome AS cliente, modelo, ano, cor, status, criado_em
        FROM carros JOIN clientes ON carros.cliente_id = clientes.id
    """, get_connection())
    st.dataframe(apply_status_style(carros), use_container_width=True)


def pagina_orcamentos():
    st.header("💰 Orçamentos")
    carros = pd.read_sql("SELECT id, modelo FROM carros", get_connection())
    if carros.empty:
        st.info("Nenhum veículo cadastrado.")
        return
    with st.form("form_orc", clear_on_submit=True):
        modelo = st.selectbox("Modelo", carros["modelo"])
        carro_id = carros.loc[carros["modelo"] == modelo, "id"].iloc[0]
        servico = st.text_input("Serviço")
        col1, col2 = st.columns(2)
        preco_estimado = col1.number_input("Preço estimado", min_value=0.0)
        preco_final = col2.number_input("Preço final", min_value=0.0)
        if st.form_submit_button("Registrar orçamento"):
            if servico:
                with closing(get_connection()) as conn:
                    conn.execute("""
                        INSERT INTO orcamentos (carro_id, servico, preco_estimado, preco_final)
                        VALUES (?,?,?,?)
                    """, (carro_id, servico, preco_estimado, preco_final))
                    conn.commit()
                st.toast("Orçamento salvo!", icon="💸")
    orc = pd.read_sql("""
        SELECT orcamentos.id, modelo, servico, preco_estimado, preco_final, orcamentos.criado_em
        FROM orcamentos JOIN carros ON orcamentos.carro_id = carros.id
    """, get_connection())
    st.dataframe(orc, use_container_width=True)


def pagina_status():
    st.header("📊 Status da Oficina")
    carros = pd.read_sql("SELECT * FROM carros", get_connection())
    col1, col2, col3 = st.columns(3)
    col1.metric("Em revisão", len(carros[carros["status"] == "Em revisão"]))
    col2.metric("Prontos", len(carros[carros["status"] == "Pronto"]))
    col3.metric("Aguardando peças", len(carros[carros["status"] == "Aguardando peças"]))
    st.dataframe(apply_status_style(carros), use_container_width=True)


def pagina_entregas():
    st.header("✅ Entregas")
    carros_prontos = pd.read_sql("""
        SELECT carros.id, clientes.nome AS cliente, modelo, ano, cor, carros.criado_em
        FROM carros JOIN clientes ON carros.cliente_id = clientes.id
        WHERE status='Pronto'
    """, get_connection())
    if carros_prontos.empty:
        st.info("Nenhum veículo pronto para entrega.")
        return
    carros_prontos["desc"] = carros_prontos.apply(lambda r: f"{r['cliente']} – {r['modelo']} ({r['cor']})", axis=1)
    selected = st.multiselect("Selecione os veículos entregues", carros_prontos["desc"].tolist())
    if st.button("Remover selecionados") and selected:
        ids = carros_prontos.loc[carros_prontos["desc"].isin(selected), "id"].tolist()
        with closing(get_connection()) as conn:
            for cid in ids:
                conn.execute("DELETE FROM orcamentos WHERE carro_id=?", (cid,))
                conn.execute("DELETE FROM carros WHERE id=?", (cid,))
            conn.execute("""
                DELETE FROM clientes 
                WHERE id NOT IN (SELECT DISTINCT cliente_id FROM carros)
            """)
            conn.commit()
        st.toast(f"Removidos {len(ids)} veículos e clientes relacionados (se aplicável).", icon="🗑️")
        st.experimental_rerun()
    st.dataframe(carros_prontos.drop(columns="desc"), use_container_width=True)


def pagina_exportar():
    st.header("📤 Exportar Dados")
    conn = get_connection()

    # Filtros
    col1, col2 = st.columns(2)
    data_inicial = col1.date_input("Data inicial", pd.Timestamp.now())
    data_final = col2.date_input("Data final", pd.Timestamp.now())
    status_opcoes = ["Em revisão", "Pronto", "Aguardando peças"]
    status_selecionados = st.multiselect("Filtrar status (opcional)", status_opcoes, default=status_opcoes)

    # Query com filtros (SQLite usa date() para extrair parte da data)
    query_carros = """
        SELECT carros.id, clientes.nome AS cliente, modelo, ano, cor, status, carros.criado_em
        FROM carros JOIN clientes ON carros.cliente_id = clientes.id
        WHERE date(carros.criado_em) BETWEEN ? AND ?
    """
    params = (data_inicial, data_final)
    carros = pd.read_sql(query_carros, conn, params=params)
    carros = carros[carros["status"].isin(status_selecionados)] if status_selecionados else carros

    clientes = pd.read_sql("SELECT * FROM clientes WHERE date(criado_em) BETWEEN ? AND ?", conn, params=params)
    orcamentos = pd.read_sql("SELECT * FROM orcamentos WHERE date(criado_em) BETWEEN ? AND ?", conn, params=params)

    # Exibir prévia
    st.subheader("Pré‑visualização")
    with st.expander("Clientes"):
        st.dataframe(clientes, use_container_width=True)
    with st.expander("Carros"):
        st.dataframe(apply_status_style(carros), use_container_width=True)
    with st.expander("Orçamentos"):
        st.dataframe(orcamentos, use_container_width=True)

        # Gerar arquivo
    data_str = f"{data_inicial}_a_{data_final}"
    file_name = ARQUIVOS_DIR / f"relatorio_{data_str}.xlsx"

    if st.button("Gerar arquivo Excel"):
        with pd.ExcelWriter(file_name) as writer:
            clientes.to_excel(writer, sheet_name="Clientes", index=False)
            carros.to_excel(writer, sheet_name="Carros", index=False)
            orcamentos.to_excel(writer, sheet_name="Orçamentos", index=False)
        st.success("Arquivo gerado!")

    # Download e envio por e‑mail
    with open(file_name, "rb") as file:
        st.download_button(
            "📥 Baixar Excel", file, file_name.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    col_dl, col_email = st.columns(2)
    with col_email:
        enviar = st.checkbox("Enviar por e‑mail")
        if enviar:
            email_dest = st.text_input("Destinatário")
            if st.button("Enviar agora") and email_dest:
                enviar_email(email_dest, file_name, f"Relatório Oficina {data_str}")
