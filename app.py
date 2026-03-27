import pandas as pd
import streamlit as st
import gspread
from datetime import datetime
from zoneinfo import ZoneInfo

# ======================================================
# CONFIGURACIÓN
# ======================================================
st.set_page_config(page_title="Registro de ventas 8°A", page_icon="🌭", layout="centered")

# ======================================================
# ACCESO CON CONTRASEÑA
# ======================================================
def mostrar_header():
    st.image("imagenes/Head.png", width="stretch")
 
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "usuario_actual" not in st.session_state:
        st.session_state.usuario_actual = ""

    if "rol_actual" not in st.session_state:
        st.session_state.rol_actual = ""

    if st.session_state.authenticated:
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("imagenes/completo.png", width="stretch")

    st.markdown(
        "<h2 style='color:#FF1F1F; font-weight: bold;'>Registro de ventas</h2>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<h3 style='color:#2F5FBF;'>🔒 Ingreso</h3>",
        unsafe_allow_html=True
    )

    nombre = st.text_input("Nombre vendedor o coordinador")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar", type="primary"):
        if not nombre.strip():
            st.error("Debes ingresar tu nombre.")
        elif password == st.secrets["APP_PASSWORD_VENDEDOR"]:
            st.session_state.authenticated = True
            st.session_state.usuario_actual = nombre.strip()
            st.session_state.rol_actual = "vendedor"
            st.rerun()
        elif password == st.secrets["APP_PASSWORD_COORDINADOR"]:
            st.session_state.authenticated = True
            st.session_state.usuario_actual = nombre.strip()
            st.session_state.rol_actual = "coordinador"
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")

    return False


if not check_password():
    st.stop()

# 👇 Mostrar Header solo después de autenticarse
mostrar_header()

col1, col2 = st.columns([4, 1])

with col1:
    st.markdown(
        f"""
        <div style="font-size:14px;">
            <strong style="color:#2F5FBF;">Usuario:</strong> {st.session_state.usuario_actual}
            &nbsp;&nbsp;|&nbsp;&nbsp;
            <strong style="color:#2F5FBF;">Rol:</strong> {st.session_state.rol_actual.title()}
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    if st.button("🔒 Cerrar sesión", type="primary"):
        st.session_state.authenticated = False
        st.session_state.usuario_actual = ""
        st.session_state.rol_actual = ""
        st.rerun()

SHEET_ID = "11yoIjPuw6v2LxOZ2Hmbg3BxVv-Qzn-jISOxNKTMjO_I"
HOJA_VENTAS = "Ventas"
HOJA_PRECIOS = "Precios"

COLUMNAS_VENTAS = [
    "numero_pedido",
    "fecha",
    "hora",
    "vendedor",
    "nombre_comprador",
    "cantidad_promo_completo_bebida",
    "cantidad_completos_solos",
    "cantidad_bebidas_solas",
    "cantidad_cafes_solos",
    "cantidad_te_solos",
    "total_venta",
    "forma_pago",
    #"observaciones",
    "estado_pedido",
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

def obtener_siguiente_numero_pedido(df_ventas):
    if df_ventas.empty or "numero_pedido" not in df_ventas.columns:
        return 1

    numeros = pd.to_numeric(df_ventas["numero_pedido"], errors="coerce").dropna()

    if numeros.empty:
        return 1

    return int(numeros.max()) + 1

def guardar_venta(
    vendedor,
    nombre_comprador,
    cantidad_promo,
    cantidad_bebidas,
    cantidad_te,
    cantidad_cafes,
    cantidad_completos,
    precios,
    forma_pago,
):
    ahora = datetime.now(ZoneInfo("America/Santiago"))
    fecha = ahora.strftime("%Y-%m-%d")
    hora = ahora.strftime("%H:%M:%S")

    df_actual = leer_ventas()
    numero_pedido = obtener_siguiente_numero_pedido(df_actual)

    total_venta = (
        cantidad_promo * precios["promocion_completo_bebida"]
        + cantidad_bebidas * precios["bebida_sola"]
        + cantidad_te * precios["te_solo"]
        + cantidad_cafes * precios["cafe_solo"]
        + cantidad_completos * precios["completo_solo"]
    )

    nueva_fila = [
        numero_pedido,
        fecha,
        hora,
        vendedor.strip(),
        nombre_comprador.strip(),
        int(cantidad_promo),
        int(cantidad_completos),
        int(cantidad_bebidas),
        int(cantidad_cafes),
        int(cantidad_te),
        int(total_venta),
        forma_pago,
        "Pendiente",
    ]

    spreadsheet = abrir_spreadsheet()
    ws = spreadsheet.worksheet(HOJA_VENTAS)
    ws.append_row(nueva_fila, value_input_option="USER_ENTERED")

    leer_ventas.clear()
    return numero_pedido

def marcar_pedido_entregado(numero_pedido):
    spreadsheet = abrir_spreadsheet()
    ws = spreadsheet.worksheet(HOJA_VENTAS)

    datos = ws.get_all_values()
    encabezados = datos[0]

    try:
        col_numero = encabezados.index("numero_pedido") + 1
        col_estado = encabezados.index("estado_pedido") + 1
    except ValueError:
        raise ValueError("La hoja Ventas debe contener las columnas 'numero_pedido' y 'estado_pedido'.")

    for i, fila in enumerate(datos[1:], start=2):
        if str(fila[col_numero - 1]).strip() == str(numero_pedido).strip():
            ws.update_cell(i, col_estado, "Entregado")
            leer_ventas.clear()
            return True

    raise ValueError(f"No se encontró el pedido {numero_pedido}.")

def construir_compra(fila):
    partes = []

    promo = pd.to_numeric(pd.Series([fila.get("cantidad_promo_completo_bebida", 0)]), errors="coerce").fillna(0).iloc[0]
    completos = pd.to_numeric(pd.Series([fila.get("cantidad_completos_solos", 0)]), errors="coerce").fillna(0).iloc[0]
    bebidas = pd.to_numeric(pd.Series([fila.get("cantidad_bebidas_solas", 0)]), errors="coerce").fillna(0).iloc[0]
    cafes = pd.to_numeric(pd.Series([fila.get("cantidad_cafes_solos", 0)]), errors="coerce").fillna(0).iloc[0]
    tes = pd.to_numeric(pd.Series([fila.get("cantidad_te_solos", 0)]), errors="coerce").fillna(0).iloc[0]

    if int(promo) > 0:
        partes.append(f"{int(promo)} Promos")

    if int(completos) > 0:
        partes.append(f"{int(completos)} Completos")

    if int(bebidas) > 0:
        partes.append(f"{int(bebidas)} Bebidas")

    if int(cafes) > 0:
        partes.append(f"{int(cafes)} Cafés")

    if int(tes) > 0:
        partes.append(f"{int(tes)} Tés (solos)")

    return ", ".join(partes) if partes else "Sin productos"

def vista_coordinador():
    st.markdown("## 📋 Pedidos pendientes")

    df = leer_ventas()

    if df.empty:
        st.info("No hay pedidos.")
        return

    if "estado_pedido" not in df.columns:
        df["estado_pedido"] = "Pendiente"

    pendientes = df[
        df["estado_pedido"].fillna("").astype(str).str.strip() != "Entregado"
    ].copy()

    if pendientes.empty:
        st.success("No hay pedidos pendientes.")
        return

    # Limpiar tipos
    pendientes["numero_pedido"] = pd.to_numeric(
        pendientes["numero_pedido"], errors="coerce"
    )
    pendientes = pendientes.dropna(subset=["numero_pedido"]).copy()
    pendientes["numero_pedido"] = pendientes["numero_pedido"].astype(int)

    # Construir resumen
    pendientes["compra"] = pendientes.apply(construir_compra, axis=1)

    # Dataframe a mostrar
    df_mostrar = pendientes[[
        "numero_pedido",
        "hora",
        "nombre_comprador",
        "compra"
    ]].rename(columns={
        "numero_pedido": "Pedido",
        "hora": "Hora",
        "nombre_comprador": "Comprador/a",
        "compra": "Compra"
    })

    # 👇 columna interactiva
    df_mostrar["Entregar"] = False

    st.markdown("""
    <style>
    /* Oculta menú de columnas en data editor */
    div[data-testid="stDataEditor"] button {
        visibility: hidden;
    }
    </style>
    """, unsafe_allow_html=True)

    edited_df = st.data_editor(
        df_mostrar,
        width="stretch",
        hide_index=True,
        column_config={
            "Entregar": st.column_config.CheckboxColumn(
                "✅ Entregado",
                help="Marcar pedido como entregado"
            )
        },
        disabled=["Pedido", "Hora", "Comprador/a", "Compra"]
    )

    # Detectar cambios
    pedidos_a_entregar = edited_df[edited_df["Entregar"] == True]

    if not pedidos_a_entregar.empty:
        for _, fila in pedidos_a_entregar.iterrows():
            numero = int(fila["Pedido"])
            try:
                marcar_pedido_entregado(numero)
            except Exception as e:
                st.error(f"No fue posible actualizar el pedido {numero}: {e}")

        st.success("Pedidos actualizados correctamente")
        st.rerun()
            
# ======================================================
# INTERFAZ
# ======================================================
try:
    precios = leer_precios()
except Exception as e:
    st.error(str(e))
    st.stop()

if "nombre_comprador" not in st.session_state:
    st.session_state.nombre_comprador = ""

if "cantidad_promo" not in st.session_state:
    st.session_state.cantidad_promo = 0

if "cantidad_completos" not in st.session_state:
    st.session_state.cantidad_completos = 0

if "cantidad_bebidas" not in st.session_state:
    st.session_state.cantidad_bebidas = 0

if "cantidad_cafes" not in st.session_state:
    st.session_state.cantidad_cafes = 0

if "cantidad_te" not in st.session_state:
    st.session_state.cantidad_te = 0

if "forma_pago" not in st.session_state:
    st.session_state.forma_pago = "Seleccione una opción"

if "limpiar_formulario" not in st.session_state:
    st.session_state.limpiar_formulario = False

if "mensaje_confirmacion" not in st.session_state:
    st.session_state.mensaje_confirmacion = ""

if st.session_state.limpiar_formulario:
    st.session_state.nombre_comprador = ""
    st.session_state.cantidad_promo = 0
    st.session_state.cantidad_completos = 0
    st.session_state.cantidad_bebidas = 0
    st.session_state.cantidad_cafes = 0
    st.session_state.cantidad_te = 0
    st.session_state.forma_pago = "Seleccione una opción"
    st.session_state.limpiar_formulario = False

df_ventas = leer_ventas()

st.markdown("""
<style>
button[data-baseweb="tab"] {
    font-size: 16px;
    font-weight: 600;
    padding: 10px 18px;
    border-radius: 8px 8px 0 0;
    background-color: #f0f2f6;
    margin-right: 6px;
    transition: all 0.2s ease-in-out;
}

button[data-baseweb="tab"]:hover {
    background-color: #e0e0e0;
}

button[data-baseweb="tab"][aria-selected="true"] {
    background-color: #FF1F1F;
    color: white;
    border-bottom: 3px solid #FF1F1F;
}
</style>
""", unsafe_allow_html=True)

if st.session_state.rol_actual == "vendedor":
    tab1, tab2, tab3, tab4 = st.tabs([
        "🧾 Registro",
        "🌭 Ventas",
        "📊 Resumen",
        "💲 Precios"
    ])

    # ======================================================
    # TAB 1: REGISTRO VENTA
    # ======================================================
    with tab1:
        st.markdown(
            "<h2 style='color:#FF1F1F;'>🧾 Ingreso ventas</h2>",
            unsafe_allow_html=True
        )
        
        with st.form("formulario_venta", clear_on_submit=False):
            nombre_comprador = st.text_input("NOMBRE COMPRADOR", key="nombre_comprador")

            col1, col2 = st.columns(2)

            with col1:
                cantidad_promo = st.number_input(
                    "Cantidad promo completo + bebestible",
                    min_value=0,
                    step=1,
                    key="cantidad_promo"
                )

            with col2:
                cantidad_completos = st.number_input(
                    "Cantidad de completos solos",
                    min_value=0,
                    step=1,
                    key="cantidad_completos"
                )

                cantidad_bebidas = st.number_input(
                    "Cantidad de bebidas solas",
                    min_value=0,
                    step=1,
                    key="cantidad_bebidas"
                )

                cantidad_cafes = st.number_input(
                    "Cantidad de café(s) solos",
                    min_value=0,
                    step=1,
                    key="cantidad_cafes"
                )

                cantidad_te = st.number_input(
                    "Cantidad de té(s) solos",
                    min_value=0,
                    step=1,
                    key="cantidad_te"
                )
            
            # observaciones = st.text_area("📝 Observaciones del pedido (opcional)", placeholder="Ej: Un completo sin mayo, café sin azúcar...")
            
            forma_pago = st.selectbox(
                "FORMA DE PAGO",
                options=["Seleccione una opción", "Efectivo", "Transferencia"],
                key="forma_pago"
            )

            total_estimado = (
                int(cantidad_promo) * precios["promocion_completo_bebida"]
                + int(cantidad_bebidas) * precios["bebida_sola"]
                + int(cantidad_te) * precios["te_solo"]
                + int(cantidad_cafes) * precios["cafe_solo"]
                + int(cantidad_completos) * precios["completo_solo"]
            )

            guardar = st.form_submit_button("💾 Guardar venta", type="primary")

            nombre_mostrar = nombre_comprador if nombre_comprador else st.session_state.get("ultimo_nombre", "")
            total_mostrar = total_estimado if nombre_comprador else st.session_state.get("ultimo_total", 0)

            st.markdown(
                f"<h2 style='color:#2F5FBF;'>Total a pagar ({nombre_mostrar}): ${total_mostrar:,}</h2>".replace(",", "."),
                unsafe_allow_html=True
            )

            mensaje_formulario = st.empty()
            if st.session_state.mensaje_confirmacion:
                mensaje_formulario.success(st.session_state.mensaje_confirmacion)
                st.session_state.mensaje_confirmacion = ""

            if guardar:
                total_items = (
                    int(cantidad_promo)
                    + int(cantidad_completos)
                    + int(cantidad_bebidas)
                    + int(cantidad_te)
                    + int(cantidad_cafes)
                )

                if not nombre_comprador.strip():
                    mensaje_formulario.error("Debes ingresar el nombre del comprador.")
                elif total_items == 0:
                    mensaje_formulario.error("Debes registrar al menos un producto.")
                elif forma_pago == "Seleccione una opción":
                    mensaje_formulario.error("Debes seleccionar una forma de pago.")
                else:
                    try:
                        numero_pedido = guardar_venta(
                            vendedor=st.session_state.usuario_actual,
                            nombre_comprador=nombre_comprador,
                            cantidad_promo=int(cantidad_promo),
                            cantidad_completos=int(cantidad_completos),
                            cantidad_bebidas=int(cantidad_bebidas),
                            cantidad_te=int(cantidad_te),
                            cantidad_cafes=int(cantidad_cafes),
                            precios=precios,
                            forma_pago=forma_pago,
                        )

                        st.session_state.mensaje_confirmacion = f"Pedido #{numero_pedido} guardado correctamente"

                        st.session_state.ultimo_nombre = nombre_comprador
                        st.session_state.ultimo_total = total_estimado

                        st.session_state.limpiar_formulario = True
                        st.rerun()

                    except Exception as e:
                        st.error(f"No fue posible guardar la venta: {e}")

    # ======================================================
    # TAB 2: ÚLTIMAS VENTAS
    # ======================================================
    with tab2:
        st.markdown(
            "<h2 style='color:#FF1F1F;'>🌭 Últimas ventas</h2>",
            unsafe_allow_html=True
        )

        if df_ventas.empty:
            st.info("Aún no hay ventas registradas.")
        else:
            df_ventas["datetime_orden"] = pd.to_datetime(
                df_ventas["fecha"].astype(str) + " " + df_ventas["hora"].astype(str),
                errors="coerce"
            )

            df_ventas_mostrar = (
                df_ventas
                .sort_values("datetime_orden", ascending=False)
                .drop(columns=["datetime_orden"])
                .head(20)
            )

            # Renombrar columnas
            df_ventas_mostrar = df_ventas_mostrar.rename(columns={
                "numero_pedido": "Número pedido",
                "fecha": "Fecha",
                "hora": "Hora",
                "vendedor": "Vendedor/a",
                "nombre_comprador": "Comprador/a",
                "cantidad_promo_completo_bebida": "Promos",
                "cantidad_completos_solos": "Completos (solos)",
                "cantidad_bebidas_solas": "Bebidas (solas)",
                "cantidad_cafes_solos": "Cafés (solos)",
                "cantidad_te_solos": "Tés (solos)",
                "total_venta": "Total ($)",
                "forma_pago": "Forma de pago",
                #"observaciones": "Observaciones",
                "estado_pedido": "Estado pedido",
            })

            st.dataframe(
            df_ventas_mostrar,
            width="stretch",
            hide_index=True,
            column_config={
                "Fecha": None,
                "Hora": None,
                "Vendedor/a": None,
            }
            )

    # ======================================================
    # TAB 3: RESUMEN VENTAS
    # ======================================================
    with tab3:
        st.markdown(
            "<h2 style='color:#FF1F1F;'>📊 Ventas totales</h2>",
            unsafe_allow_html=True
        )
        if df_ventas.empty:
            st.info("Aún no hay ventas registradas.")
        else:
            resumen = pd.DataFrame({
                "Producto": [
                    "Promoción completo + bebida",
                    "Completo solo",
                    "Bebida sola",
                    "Café solo",
                    "Té solo"
                ],
                "Cantidad vendida": [
                    pd.to_numeric(df_ventas["cantidad_promo_completo_bebida"], errors="coerce").fillna(0).sum(),
                    pd.to_numeric(df_ventas["cantidad_completos_solos"], errors="coerce").fillna(0).sum(),
                    pd.to_numeric(df_ventas["cantidad_bebidas_solas"], errors="coerce").fillna(0).sum(),
                    pd.to_numeric(df_ventas["cantidad_cafes_solos"], errors="coerce").fillna(0).sum(),
                    pd.to_numeric(df_ventas["cantidad_te_solos"], errors="coerce").fillna(0).sum(),
                ],
                "Total vendido": [
                    pd.to_numeric(df_ventas["cantidad_promo_completo_bebida"], errors="coerce").fillna(0).sum() * precios["promocion_completo_bebida"],
                    pd.to_numeric(df_ventas["cantidad_completos_solos"], errors="coerce").fillna(0).sum() * precios["completo_solo"],
                    pd.to_numeric(df_ventas["cantidad_bebidas_solas"], errors="coerce").fillna(0).sum() * precios["bebida_sola"],
                    pd.to_numeric(df_ventas["cantidad_cafes_solos"], errors="coerce").fillna(0).sum() * precios["cafe_solo"],
                    pd.to_numeric(df_ventas["cantidad_te_solos"], errors="coerce").fillna(0).sum() * precios["te_solo"],
                ]
            })

            # Totales por forma de pago
            total_efectivo = df_ventas.loc[
                df_ventas["forma_pago"] == "Efectivo", "total_venta"
            ].sum()

            total_transferencia = df_ventas.loc[
                df_ventas["forma_pago"] == "Transferencia", "total_venta"
            ].sum()

            # Total general
            total_general = resumen["Total vendido"].sum()

            st.dataframe(
                resumen.style.format({
                    "Cantidad vendida": "{:.0f}",
                    "Total vendido": lambda x: f"${x:,.0f}".replace(",", ".")
                }),
                width="stretch",
                hide_index=True
            )

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "💵 Total efectivo",
                f"${total_efectivo:,.0f}".replace(",", ".")
            )

            col2.metric(
                "🏦 Total transferencias",
                f"${total_transferencia:,.0f}".replace(",", ".")
            )

            col3.metric(
                "💰 Total general de ventas",
                f"${total_general:,.0f}".replace(",", ".")
            )

    # ======================================================
    # TAB 4: CONSULTAR PRECIOS
    # ======================================================
    with tab4:
        st.markdown(
            "<h2 style='color:#FF1F1F;'>💲Consultar precios</h2>",
            unsafe_allow_html=True
        )

        df_precios_mostrar = pd.DataFrame({
            "Producto": [
                "Promoción completo + bebida",
                "Completo solo",
                "Bebida sola",
                "Café solo",
                "Té solo",
            ],
            "Precio": [
                precios["promocion_completo_bebida"],
                precios["completo_solo"],
                precios["bebida_sola"],
                precios["cafe_solo"],
                precios["te_solo"],            
            ]
        })

        st.dataframe(
            df_precios_mostrar.style.format({
                "Precio": lambda x: f"${x:,.0f}".replace(",", ".")
            }),
            width="stretch",
            hide_index=True
        )

elif st.session_state.rol_actual == "coordinador":
    vista_coordinador()