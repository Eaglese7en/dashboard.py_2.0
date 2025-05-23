import streamlit as st
from streamlit_lottie import st_lottie
import pandas as pd
import sqlite3
import requests
from datetime import date

# -----------------------------------------------------------------------------
# Configuração da página e estilo rápido
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Dashboard Oficina", page_icon="🚗", layout="wide")

st.markdown(
    """
    <style>
        h1, h2, h3 {color:#0A66C2;}
        /* deixa as tabelas roláveis se ficarem grandes */
        .dataframe-container {max-height:500px; overflow:auto;}
        [data-testid="stSidebar"] > div:first-child {padding-top: 1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

DB_PATH = "client_data.db"

# -----------------------------------------------------------------------------
# Banco de dados
# -----------------------------------------------------------------------------

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                email TEXT,
                telefone TEXT
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS carros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER,
                modelo TEXT,
                placa TEXT,
                FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS orcamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER,
                descricao TEXT,
                valor REAL,
                FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER,
                status_atual TEXT,
                data_atualizacao DATE,
                FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS entregas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER,
                data_entrega DATE,
                FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        )""")
        conn.commit()

# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------

def carregar_lottie(url: str):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def selecionar_cliente(conn):
    """Devolve (id, nome). Se não houver clientes, mostra aviso e retorna (None, "")."""
    clientes = pd.read_sql_query("SELECT id, nome, telefone FROM clientes", conn)
    if clientes.empty:
        st.warning("Nenhum cliente cadastrado. Adicione clientes primeiro.")
        return None, ""

    opcoes = {
        f"{row.nome} — {row.telefone or 'sem telefone'}": row.id for row in clientes.itertuples()
    }
    label = st.selectbox("Selecione o cliente", opcoes.keys())
    return opcoes[label], label.split(" — ")[0]

# -----------------------------------------------------------------------------
# Páginas
# -----------------------------------------------------------------------------

def pagina_inicio():
    st.header("🚗 Dashboard da Oficina")
    st.markdown("Gerencie clientes, veículos, orçamentos e entregas em um só lugar.")
    lottie_json = carregar_lottie("https://lottie.host/01c2f244-7ed7-49cf-8c3f-6b89353626c7/CLfXsS5rvf.json")
    if lottie_json:
        st_lottie(lottie_json, height=250)


def pagina_clientes():
    st.subheader("📇 Clientes")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        with st.form("frm_cliente", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            nome = col1.text_input("Nome")
            email = col2.text_input("Email")
            telefone = col3.text_input("Telefone")
            if st.form_submit_button("Adicionar"):
                if nome.strip():
                    cur.execute("INSERT INTO clientes (nome,email,telefone) VALUES (?,?,?)", (nome,email,telefone))
                    conn.commit()
                    st.success("Cliente adicionado!")
                else:
                    st.error("O nome é obrigatório.")

        st.divider()
        clientes = pd.read_sql_query("SELECT * FROM clientes", conn)
        st.dataframe(clientes, use_container_width=True)


def pagina_carros():
    st.subheader("🚙 Veículos")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cliente_id, _ = selecionar_cliente(conn)
        if cliente_id is None:
            return

        with st.form("frm_carro", clear_on_submit=True):
            col1, col2 = st.columns(2)
            modelo = col1.text_input("Modelo")
            placa = col2.text_input("Placa")
            if st.form_submit_button("Registrar"):
                if modelo.strip() and placa.strip():
                    cur.execute("INSERT INTO carros (cliente_id,modelo,placa) VALUES (?,?,?)", (cliente_id,modelo,placa))
                    conn.commit()
                    st.success("Carro registrado!")
                else:
                    st.error("Preencha modelo e placa.")

        st.divider()
        carros = pd.read_sql_query("SELECT id, modelo, placa FROM carros WHERE cliente_id = ?", conn, params=(cliente_id,))
        st.dataframe(carros, use_container_width=True)


def pagina_orcamentos():
    st.subheader("💰 Orçamentos")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cliente_id, _ = selecionar_cliente(conn)
        if cliente_id is None:
            return

        with st.form("frm_orc", clear_on_submit=True):
            descricao = st.text_area("Descrição")
            valor = st.number_input("Valor", min_value=0.0, format="%.2f")
            if st.form_submit_button("Salvar"):
                if descricao.strip():
                    cur.execute("INSERT INTO orcamentos (cliente_id,descricao,valor) VALUES (?,?,?)", (cliente_id,descricao,valor))
                    conn.commit()
                    st.success("Orçamento salvo!")
                else:
                    st.error("Descrição obrigatória.")

        st.divider()
        orcs = pd.read_sql_query("SELECT id, descricao, valor FROM orcamentos WHERE cliente_id = ?", conn, params=(cliente_id,))
        st.dataframe(orcs, use_container_width=True)


def pagina_status():
    st.subheader("📊 Status")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cliente_id, _ = selecionar_cliente(conn)
        if cliente_id is None:
            return

        with st.form("frm_status", clear_on_submit=True):
            status_atual = st.text_input("Status atual")
            data_atualizacao = st.date_input("Data", value=date.today())
            if st.form_submit_button("Atualizar"):
                if status_atual.strip():
                    cur.execute("INSERT INTO status (cliente_id,status_atual,data_atualizacao) VALUES (?,?,?)", (cliente_id,status_atual,data_atualizacao))
                    conn.commit()
                    st.success("Status atualizado!")
                else:
                    st.error("Status obrigatório.")

        st.divider()
        df = pd.read_sql_query("SELECT status_atual, data_atualizacao FROM status WHERE cliente_id=?", conn, params=(cliente_id,))
        st.dataframe(df, use_container_width=True)


def pagina_entregas():
    st.subheader("✅ Entregas")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cliente_id, _ = selecionar_cliente(conn)
        if cliente_id is None:
            return

        with st.form("frm_ent", clear_on_submit=True):
            data_entrega = st.date_input("Data de entrega", value=date.today())
            if st.form_submit_button("Registrar"):
                cur.execute("INSERT INTO entregas (cliente_id,data_entrega) VALUES (?,?)", (cliente_id,data_entrega))
                conn.commit()
                st.success("Entrega registrada!")

        st.divider()
        ent = pd.read_sql_query("SELECT data_entrega FROM entregas WHERE cliente_id=?", conn, params=(cliente_id,))
        st.dataframe(ent, use_container_width=True)


def pagina_exportar():
    st.subheader("📤 Exportar dados")
    with sqlite3.connect(DB_PATH) as conn:
        clientes = pd.read_sql_query("SELECT * FROM clientes", conn)
        carros = pd.read_sql_query("SELECT * FROM carros", conn)
        orcamentos = pd.read_sql_query("SELECT * FROM orcamentos", conn)
        status = pd.read_sql_query("SELECT * FROM status", conn)
        entregas = pd.read_sql_query("SELECT * FROM entregas", conn)

    with pd.ExcelWriter("dados_exportados.xlsx") as writer:
        clientes.to_excel(writer, sheet_name="Clientes", index=False)
        carros.to_excel(writer, sheet_name="Carros", index=False)
        orcamentos.to_excel(writer, sheet_name="Orcamentos", index=False)
        status.to_excel(writer, sheet_name="Status", index=False)
        entregas.to_excel(writer, sheet_name="Entregas", index=False)

    with open("dados_exportados.xlsx", "rb") as f:
        st.download_button("Baixar Excel", f, file_name="dados_exportados.xlsx")

# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
init_db()

menu = st.sidebar.radio("Navegar para:", [
    "Início",
    "Clientes",
    "Veículos",
    "Orçamentos",
    "Status",
    "Entregas",
    "Exportar",
])

if menu == "Início":
    pagina_inicio()
elif menu == "Clientes":
    pagina_clientes()
elif menu == "Veículos":
    pagina_carros()
elif menu == "Orçamentos":
    pagina_orcamentos()
elif menu == "Status":
    pagina_status()
elif menu == "Entregas":
    pagina_entregas()
elif menu == "Exportar":
    pagina_exportar()
