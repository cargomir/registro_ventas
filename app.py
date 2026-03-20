from datetime import datetime

import pandas as pd
import streamlit as st
import gspread

# ======================================================
# CONFIGURACIÓN
# ======================================================
st.set_page_config(page_title="Registro de ventas", page_icon="🧾", layout="centered")

SHEET_ID = "11yoIjPuw6v2LxOZ2Hmbg3BxVv-Qzn-jISOxNKTMjO_I"
HOJA_VENTAS = "Ventas"
HOJA_PRECIOS = "Precios"


COLUMNAS_VENTAS = [
    "fecha",
    "hora",
    "nombre_comprador",
    "cantidad_promo_completo_bebida",
    "cantidad_completos_solos",
    "cantidad_bebidas_solas",
    "cantidad_cafes_solos",
    "cantidad_te_solos",
    "total_venta",
]

PRODUCTOS_ESPERADOS = [
    "promocion_completo_bebida",
    "completo_solo",
    "bebida_sola",
    "cafe_solo",
    "te_solo",   
]


# ======================================================
# CONEXIÓN GOOGLE SHEETS
# ======================================================
@st.cache_resource
def conectar_gsheet():
    return gspread.service_account_from_dict(
        dict(st.secrets["gcp_service_account"])
    )


def abrir_spreadsheet():
    client = conectar_gsheet()
    return client.open_by_key(SHEET_ID)


# ======================================================
# FUNCIONES
# ======================================================
@st.cache_data(ttl=300)
def leer_precios():
    try:
        spreadsheet = abrir_spreadsheet()
        ws = spreadsheet.worksheet(HOJA_PRECIOS)

        df_precios = pd.DataFrame(ws.get_all_records())
        df_precios.columns = [c.strip().lower() for c in df_precios.columns]

        if "producto" not in df_precios.columns or "precio" not in df_precios.columns:
            raise ValueError("La hoja 'Precios' debe contener las columnas 'producto' y 'precio'.")

        df_precios["producto"] = df_precios["producto"].astype(str).str.strip().str.lower()
        df_precios["precio"] = pd.to_numeric(df_precios["precio"], errors="coerce")

        if df_precios["precio"].isna().any():
            raise ValueError("Hay precios no numéricos o vacíos en la hoja 'Precios'.")

        precios = dict(zip(df_precios["producto"], df_precios["precio"]))

        faltantes = [p for p in PRODUCTOS_ESPERADOS if p not in precios]
        if faltantes:
            raise ValueError(f"Faltan precios para: {', '.join(faltantes)}")

        return {
            "promocion_completo_bebida": int(precios["promocion_completo_bebida"]),
            "bebida_sola": int(precios["bebida_sola"]),
            "te_solo": int(precios["te_solo"]),
            "cafe_solo": int(precios["cafe_solo"]),
            "completo_solo": int(precios["completo_solo"]),
        }

    except Exception as e:
        raise RuntimeError(f"No fue posible leer la hoja de precios: {e}")


@st.cache_data(ttl=60)
def leer_ventas():
    try:
        spreadsheet = abrir_spreadsheet()
        ws = spreadsheet.worksheet(HOJA_VENTAS)

        df = pd.DataFrame(ws.get_all_records())

        if df.empty:
            return pd.DataFrame(columns=COLUMNAS_VENTAS)

        df.columns = [c.strip() for c in df.columns]

        for col in COLUMNAS_VENTAS:
            if col not in df.columns:
                df[col] = None

        df = df[COLUMNAS_VENTAS]
        df = df.dropna(how="all")
        df = df[df["nombre_comprador"].notna()]
        df = df[df["nombre_comprador"].astype(str).str.strip() != ""]

        return df.reset_index(drop=True)

    except Exception as e:
        st.error(f"No fue posible leer las ventas: {e}")
        return pd.DataFrame(columns=COLUMNAS_VENTAS)


def guardar_venta(
    nombre_comprador,
    cantidad_promo,
    cantidad_bebidas,
    cantidad_te,
    cantidad_cafes,
    cantidad_completos,
    precios,
):
    ahora = datetime.now()
    fecha = ahora.strftime("%Y-%m-%d")
    hora = ahora.strftime("%H:%M:%S")

    total_venta = (
        cantidad_promo * precios["promocion_completo_bebida"]
        + cantidad_bebidas * precios["bebida_sola"]
        + cantidad_te * precios["te_solo"]
        + cantidad_cafes * precios["cafe_solo"]
        + cantidad_completos * precios["completo_solo"]
    )

    nueva_fila = [
        fecha,
        hora,
        nombre_comprador.strip(),
        int(cantidad_promo),
        int(cantidad_completos),
        int(cantidad_bebidas),
        int(cantidad_cafes),
        int(cantidad_te),
        int(total_venta),
    ]

    spreadsheet = abrir_spreadsheet()
    ws = spreadsheet.worksheet(HOJA_VENTAS)
    ws.append_row(nueva_fila, value_input_option="USER_ENTERED")

    leer_ventas.clear()
    return True


# ======================================================
# INTERFAZ
# ======================================================
st.title("🧾 Registro de ventas")

try:
    precios = leer_precios()
except Exception as e:
    st.error(str(e))
    st.stop()

with st.form("formulario_venta", clear_on_submit=True):
    nombre_comprador = st.text_input("Nombre comprador")

    col1, col2 = st.columns(2)

    with col1:
        cantidad_promo = st.number_input(
            "Cantidad promoción completo + bebida",
            min_value=0,
            value=0,
            step=1
        )

    with col2:
        cantidad_completos = st.number_input(
            "Cantidad de completos solos",
            min_value=0,
            value=0,
            step=1
        )

        cantidad_bebidas = st.number_input(
            "Cantidad de bebidas solas",
            min_value=0,
            value=0,
            step=1
        )

        cantidad_cafes = st.number_input(
            "Cantidad de cafés solos",
            min_value=0,
            value=0,
            step=1
        )

        cantidad_te = st.number_input(
            "Cantidad de té solos",
            min_value=0,
            value=0,
            step=1
        )

    total_estimado = (
        int(cantidad_promo) * precios["promocion_completo_bebida"]
        + int(cantidad_bebidas) * precios["bebida_sola"]
        + int(cantidad_te) * precios["te_solo"]
        + int(cantidad_cafes) * precios["cafe_solo"]
        + int(cantidad_completos) * precios["completo_solo"]
    )

    st.markdown("""
    <style>
    div[data-testid="stFormSubmitButton"] > button {
        font-weight: bold;
        font-size: 18px;
    }
    </style>
    """, unsafe_allow_html=True)

    guardar = st.form_submit_button("💾 Guardar venta", type="primary")

    st.markdown(
        f"<h2 style='color:green;'>💰 Total a pagar ({nombre_comprador}): ${total_estimado:,}</h2>".replace(",", "."),
        unsafe_allow_html=True
    )



    if guardar:
        total_items = (
            int(cantidad_promo)
            + int(cantidad_completos)
            + int(cantidad_bebidas)
            + int(cantidad_te)
            + int(cantidad_cafes)
        )

        if not nombre_comprador.strip():
            st.error("Debes ingresar el nombre del comprador.")
        elif total_items == 0:
            st.error("Debes registrar al menos un producto.")
        else:
            try:
                guardar_venta(
                    nombre_comprador=nombre_comprador,
                    cantidad_promo=int(cantidad_promo),
                    cantidad_completos=int(cantidad_completos),
                    cantidad_bebidas=int(cantidad_bebidas),
                    cantidad_te=int(cantidad_te),
                    cantidad_cafes=int(cantidad_cafes),
                    precios=precios,
                )
                st.success("Venta guardada correctamente.")
            except Exception as e:
                st.error(f"No fue posible guardar la venta: {e}")

st.divider()

st.subheader("Últimas ventas registradas")
df_ventas = leer_ventas()

if df_ventas.empty:
    st.info("Aún no hay ventas registradas.")
else:
    st.dataframe(df_ventas.tail(20), use_container_width=True, hide_index=True)

with st.expander("💰 Consultar precios vigentes"):
    df_precios_mostrar = pd.DataFrame({
        "Producto": [
            "Promoción completo + bebida",
            "Bebida sola",
            "Té solo",
            "Café solo",
            "Completo solo"
        ],
        "Precio": [
            precios["promocion_completo_bebida"],
            precios["bebida_sola"],
            precios["te_solo"],
            precios["cafe_solo"],
            precios["completo_solo"],
        ]
    })

    st.dataframe(
        df_precios_mostrar,
        use_container_width=True,
        hide_index=True
    )