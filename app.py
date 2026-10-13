# -------------------------------------------------------------------------------------------
# /IMPORTACIONES/////////////////////////////////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from optimizador import optimizador # Función de optimización.
from mapa import renderizar_mapa_rutas # Función que renderiza el mapa.
# -------------------------------------------------------------------------------------------
# /Tabla de datos de ejemplo.////////////////////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
df_ejemplo = pd.DataFrame({
    'Parada': [
        "A Coruña", "Carballo", "Ferrol", "Foz", "Lalín", "Lugo", "Melide", 
        "Monforte de Lemos", "Narón", "Ourense", "Pontevedra", "Redondela", 
        "Ribadeo", "Ribeira", "Santiago de Compostela", "Verín", "Vigo", 
        "Vilagarcía de Arousa", "Vilalba", "Xinzo de Limia"
    ],
    'Pasajeros': [326, 58, 231, 40, 77, 158, 23, 58, 18, 233, 211, 113, 98, 50, 367, 32, 412, 87, 29, 22]
})
# Convertimos el DataFrame a CSV en memoria.
csv_ejemplo = df_ejemplo.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
def main():
    # -------------------------------------------------------------------------------------------
    # /Ajustes estéticos con CSS.////////////////////////////////////////////////////////////////
    # -------------------------------------------------------------------------------------------
    st.markdown("""
        <style>
        /* Forzar a que todas las columnas de un st.columns tengan la misma altura */
        [data-testid="stColumn"] {
            display: flex;
            flex-direction: column;
        }
        
        /* Forzar a que el contenedor con borde ocupe el 100% del alto disponible */
        [data-testid="stColumn"] > div {
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        [data-testid="stColumn"] > div > div {
            height: 100%;
        }
        </style>
    """, unsafe_allow_html=True)
    # -------------------------------------------------------------------------------------------
    # /Configuración de la página.///////////////////////////////////////////////////////////////
    # -------------------------------------------------------------------------------------------
    st.set_page_config(
        page_title="Optimizador de Rutas",
        page_icon="assets/mapa_galicia.png",
        layout="wide"
    )  
    st.title("Optimizador de rutas de autobuses")
    # -------------------------------------------------------------------------------------------
    # /Carga de parámetros fijos.////////////////////////////////////////////////////////////////
    # -------------------------------------------------------------------------------------------
    plazas = 55 # Asumimos que cada bus tiene 55 plazas.
    epsilon = 3 # Variable de holgura para asegurar que hay buses disponibles de sobra.
    incremento_epsilon = 2 # Incremento de la variable de holgura hasta que haya los buses suficientes.
    delta = 10 # Coste simbólico de emplear un nuevo bus.
    gamma = 1 # Coste de realizar paradas para evitar paradas innecesarias.
    plazas_midi = 35 # Asumimos que cada midibus tiene 35 plazas.
    coef_midi = 1 # Asumimos que utilizar midibus conlleva la misma distancia y tiempo que un bus estándar.
    plazas_mini = 20 # Asumimos que cada minibus tiene 20 plazas.
    coef_mini = 1 # Asumimos que utilizar minibus conlleva la misma distancia y tiempo que un bus estándar.
    coste_total_optimización = 0
    total_buses_estandar = 0
    total_midibuses = 0
    total_minibuses = 0
    # -------------------------------------------------------------------------------------------
    # /INTERFAZ DE USUARIO///////////////////////////////////////////////////////////////////////
    # -------------------------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------
    # /Selector de nivel de precisión/tiempo de cálculo./////////////////////////////////////////
    # -------------------------------------------------------------------------------------------
    modo_opt = st.sidebar.selectbox(
        "Tiempo de ejecución",
        options=["Rápido (3s por iteración)", "Optimizado (15s por iteración)", "Exhaustivo (60s por iteración)"],
        index=1,  # Por defecto selecciona Optimizado
        help="Determina cuánto tiempo dedicará el solucionador a explorar rutas más eficientes. " \
        "Para pruebas se recomienda la opción rápida u optimizada, para una ejecución definitiva se recomienda " \
        "la opción exhaustiva ya que puede que encuentre alguna solución ligeramente mejor."
    )
    # Mapeo del modo elegido a los segundos reales
    tiempos_map = {
        "Rápido (3s por iteración)": 3,
        "Optimizado (15s por iteración)": 15,
        "Exhaustivo (60s por iteración)": 60
    }
    tiempo_limite_seg = tiempos_map[modo_opt]
    # -------------------------------------------------------------------------------------------
    # /Selección del parámetro a optimizar.//////////////////////////////////////////////////////
    # -------------------------------------------------------------------------------------------
    st.sidebar.subheader("Métrica a optimizar:")
    with st.sidebar.form("formulario_configuracion"):
        metrica_escogida = st.radio("Selecciona en base a qué métrica desesas optimizar las rutas.", ["Distancia", "Tiempo"])
        boton_ejecucion = st.form_submit_button("Calcular rutas")
    if metrica_escogida == "Distancia":
        df_prueba = pd.read_csv("data/matriz_distancias.csv") # Archivo con la red de distancias.
        unidad = "Km"
    else:
        df_prueba = pd.read_csv("data/matriz_tiempos.csv") # Archivo con la red de tiempos.
        unidad = "min"
    nodo_destino = "Viveiro"
    # -------------------------------------------------------------------------------------------
    # /Lectura de la demanda de pasajeros.///////////////////////////////////////////////////////
    # -------------------------------------------------------------------------------------------
    st.sidebar.subheader("Demanda de Pasajeros")
    # Lista de paradas extraídas de la matriz fija.
    paradas_unicas = sorted(
        [p for p in df_prueba["origen"].unique() if p != nodo_destino]
    )
    # Selector de método de carga
    # Inicializar el DataFrame.
    if "df_demanda" not in st.session_state:
        st.session_state.df_demanda = pd.DataFrame(
            {"Parada": paradas_unicas, "Pasajeros": [0] * len(paradas_unicas)}
        )
    metodo_carga = st.sidebar.radio(
        "Selecciona el método para introducir la demanda:",
        ["Manualmente", "Cargar archivo"],
    )
    if metodo_carga == "Cargar archivo":
        archivo_subido = st.sidebar.file_uploader(
            "Sube el archivo de pasajeros.", 
            type=["xlsx", "xls", "csv", "txt", "dat"],
        )
        with st.sidebar.popover("Instrucciones de formato"):
            st.markdown("""
            **Formatos permitidos:** `.xlsx`, `.xls`, `.csv`, `.txt`, `.dat`
            ---
            **Requisitos de estructura:**
            * **Excel (`.xlsx`, `.xls`):** debe contener una hoja con exactamente dos columnas con las cabeceras Parada (nombre de la parada) y Pasajeros (número entero no negativo).
            * **Texto/Datos (`.csv`, `.txt`, `.dat`):** debe ser de texto plano estructurado en dos columnas con las cabeceras Parada y Pasajeros en la primera línea. Los valores deben estar separados mediante comas, tabuladores o puntos y comas.
            ---""")
            st.write("""**Importante:** la lista de paradas debe coincidir con las paradas del programa.
            Si lo deseas, puedes descargar este archivo de ejemplo y modificar el número de pasajeros a tu gusto.
            """)
            st.download_button(
                        label="Descargar (CSV)",
                        data=csv_ejemplo,
                        file_name="ejemplo_demanda_pasajeros.csv",
                        mime="text/csv"
                    )
        if archivo_subido is not None:
            nombre_archivo = archivo_subido.name.lower()
            try:
                if nombre_archivo.endswith(('.xlsx', '.xls')):
                    df_cargado = pd.read_excel(archivo_subido)
                elif nombre_archivo.endswith(('.csv', '.txt', '.dat')):
                    # sep=None con engine='python' autodetecta si usa comas, tabuladores, punto y coma, etc.
                    # encoding='utf-8-sig' elimina automáticamente el carácter invisible \ufeff
                    df_cargado = pd.read_csv(archivo_subido, sep=None, engine='python', encoding='utf-8-sig')
                df_cargado.columns = df_cargado.columns.str.strip()
                # Al leer el Archivo, actualizamos directamente el estado global.
                st.session_state.df_demanda = df_cargado
            except Exception as e:
                st.sidebar.error(f"Error al leer el archivo: {e}")
    df_variables = st.sidebar.data_editor(
        st.session_state.df_demanda, 
        num_rows="fixed", 
        hide_index=True,
        key="editor_demanda"
    )
    # Actualizar el estado con las ediciones manuales si el usuario modifica celdas
    st.session_state.df_demanda = df_variables
    # -------------------------------------------------------------------------------------------
    # /LLAMADA AL OPTIMIZADOR////////////////////////////////////////////////////////////////////
    # -------------------------------------------------------------------------------------------
    # Botón para ejecutar la optimización.
    if boton_ejecucion:
        # Convertimos la demanda seleccionada en la interfaz al diccionario {parada: pasajeros}
        df_variables_filtrado = df_variables[df_variables['Pasajeros'] > 0]
        demanda_dict = dict(zip(df_variables_filtrado['Parada'], df_variables_filtrado['Pasajeros']))
        with st.spinner(f"""Calculando la ruta óptima con respecto {"a la distancia" if metrica_escogida == "Distancia" else "al tiempo"}..."""):
            resultado = optimizador(
                df = df_prueba, 
                paradas = demanda_dict, 
                plazas = plazas, 
                epsilon = epsilon,
                incremento_epsilon = incremento_epsilon, 
                delta = delta,
                gamma = gamma,
                nodo_destino = nodo_destino,
                tiempo_limite_seg = tiempo_limite_seg
            )
        st.session_state["resultado"] = resultado
        st.rerun()
    if "resultado" not in st.session_state:
        # -------------------------------------------------------------------------------------------
        # /PANTALLA DE BIENVENIDA////////////////////////////////////////////////////////////////////
        # -------------------------------------------------------------------------------------------
        st.info("**Bienvenido al Optimizador de Rutas de Autobuses en Galicia**")
        with st.container(border=True):
            st.write("""Este proyecto simula un evento multitudinario en Viveiro que ofrece
             lineas de buses especiales para dicho evento. Estas lineas tienen 20 paradas alrededor
              de toda Galicia para recoger gente. El reto es el siguiente: no limitar de ninguna manera
               el numero de personas que pueden solicitar cada parada y una vez obtenidos esos datos, optimizar
                las rutas para poder llevar a todos los pasajeros a destino utilizando el mínimo de recursos posibles. """)
        col_welcome_1, col_welcome_2 = st.columns(2)
        with col_welcome_1:
            with st.container(border=True):
                st.markdown("### ¿Cómo empezar?")
                st.markdown(
                    "1. Configura el **tiempo de ejecución** y la **métrica** a optimizar en la barra lateral.\n"
                    "2. Introduce o sube la **demanda de pasajeros** para cada parada de la red.\n"
                    "3. Haz clic en el botón **'Calcular rutas'** para generar la solución óptima."
                )
        with col_welcome_2:
            with st.container(border=True):
                st.markdown("### ¿Qué encontrarás aquí?")
                st.markdown(
                    "* **Asignación inteligente** de flotas.\n"
                    "* **Rutas detalladas** con toda la información de cuantos pasajeros se recogen en cada parada, distancia/tiempo invertidos etc.\n"
                    "* **Mapa interactivo** detallado por ruta o en vista general para una visualización clara e intuitiva.\n"
                    "* **Información adicional**, número de buses utilizados, distancia total etc."
                )
    else:
        # -------------------------------------------------------------------------------------------
        # /PRESENTACIÓN DE RESULTADOS////////////////////////////////////////////////////////////////
        # -------------------------------------------------------------------------------------------
        res = st.session_state["resultado"]
        if res["estado"] == "Optimal":
            # -------------------------------------------------------------------------------------------
            # /Tabla con las rutas.//////////////////////////////////////////////////////////////////////
            # -------------------------------------------------------------------------------------------
            costes = res.get("costes", {})
            todas_las_rutas = {} # Vamos guardando cada ruta para luego visualizarla.
            info_rutas = {} # Tipo de bus y pasajeros asociados a cada ruta.
            # Bloque de Autobuses Directos llenos.
            filas_tabla = []
            id = 0 # Índices de los buses
            buses_directos = res.get("buses_directos", {})
            for parada, n in buses_directos.items():
                if n > 0:
                    total_buses_estandar += n
                    coste_n_buses = n*costes[parada, nodo_destino]
                    coste_total_optimización += coste_n_buses
                    id += 1
                    filas_tabla.append({
                        "Índice" : id,
                        "Origen": parada,
                        "Número de buses": n,
                        f"Pasajeros totales ({plazas} por bus)": n*plazas,
                        f"{metrica_escogida} por bus ({unidad})": costes[parada, nodo_destino]
                    })
                    nombre_clave = f"Ruta #{id}"
                    trazado_ruta = [parada, nodo_destino]
                    todas_las_rutas[nombre_clave] = trazado_ruta
                    info_rutas[nombre_clave] = {
                        "tipo": "Estándar",
                        "pasajeros": int(n * plazas),
                        "coste": costes[parada, nodo_destino],
                        "recorrido": " ➔ ".join(trazado_ruta)
                    }
            # Bloque de Autobuses indirectos.
            filas_tabla_2 = []
            filas_tabla_3 = []
            rutas_buses = res.get("rutas_buses", {})
            recogida_pasajeros = res.get("recogida_pasajeros", {})
            buses_unicos = {k for (k, i, j) in rutas_buses.keys()}
            buses_con_paradas = []
            buses_directos_parciales = []
            for bus in buses_unicos:
                arcos_bus = [(i, j) for (k, i, j), var in rutas_buses.items() if k == bus and var > 0.5]
                if len(arcos_bus) == 1: # Buses directos parcialmente llenos.
                    buses_directos_parciales.append(bus)
                elif len(arcos_bus) > 1: # Buses con paradas.
                    buses_con_paradas.append((bus,arcos_bus))
            for bus in buses_directos_parciales:
                for (k,i,j) , var in rutas_buses.items():
                    if k == bus and var > 0.5:
                        id += 1
                        pasajeros = recogida_pasajeros[k,i]
                        if pasajeros > plazas_midi:
                            tipo_bus = "Estándar"
                            coef = 1
                            total_buses_estandar += 1
                        elif pasajeros > plazas_mini:
                            tipo_bus = "Midibus"
                            coef = coef_midi
                            total_midibuses += 1
                        else:
                            tipo_bus = "Minibus"
                            coef = coef_mini
                            total_minibuses += 1
                        coste_n_buses = costes[i,j]*coef
                        coste_total_optimización += coste_n_buses
                        filas_tabla_2.append({
                        "Índice" : id,
                        "Origen" : i,
                        "Tipo de bus" : tipo_bus,
                        "Pasajeros" : pasajeros,
                        f"{metrica_escogida} ({unidad})" : coste_n_buses,
                        })
                        nombre_clave = f"Ruta #{id}"
                        trazado_ruta = [i, j]
                        todas_las_rutas[nombre_clave] = trazado_ruta
                        info_rutas[nombre_clave] = {
                            "tipo": tipo_bus,
                            "pasajeros": int(pasajeros),
                            "coste": coste_n_buses,
                            "recorrido": " ➔ ".join(trazado_ruta)
                        }
            for bus, arcos_bus in buses_con_paradas:
                # Identificar orígenes y destinos.
                origenes = {i for (i, j) in arcos_bus}
                destinos = {j for (i, j) in arcos_bus}
                # El inicio es el nodo de origen que no es destino de ningún otro tramo del mismo bus.
                inicio = list(origenes - destinos)[0]
                # Mapear la ruta para este bus.
                siguiente_nodo = {i: j for (i, j) in arcos_bus}
                ruta_ordenada = [inicio]
                nodo_actual = inicio
                while nodo_actual in siguiente_nodo:
                    nodo_actual = siguiente_nodo[nodo_actual]
                    ruta_ordenada.append(nodo_actual)
                # Información ruta.
                filas_bus = []
                pasajeros_totales = sum(
                    recogida_pasajeros.get((bus, nodo), 0) for nodo in ruta_ordenada
                )
                if pasajeros_totales > plazas_midi:
                    tipo_bus = "Estándar"
                    coef = 1
                    total_buses_estandar += 1
                elif pasajeros_totales > plazas_mini:
                    tipo_bus = "Midibus"
                    coef = coef_midi
                    total_midibuses += 1
                else:
                    tipo_bus = "Minibus"
                    coef = coef_mini
                    total_minibuses += 1
                # Origen.
                origen_inicial = ruta_ordenada[0]
                filas_bus.append({
                    " ": "Inicio de la ruta",
                    "Parada": origen_inicial,
                    "Pasajeros recogidos": recogida_pasajeros[bus,origen_inicial],
                    f"{metrica_escogida} tramo ({unidad})": 0
                })
                # Resto de paradas.
                for i in range(1, len(ruta_ordenada)):
                    coste_tramo = (costes[ruta_ordenada[i-1], ruta_ordenada[i]])*coef
                    pasajeros_parada = recogida_pasajeros.get((bus,ruta_ordenada[i]),0)
                    filas_bus.append({
                        " ": f"Parada Nº{i}",
                        "Parada": ruta_ordenada[i],
                        "Pasajeros recogidos": pasajeros_parada,
                        f"{metrica_escogida} tramo ({unidad})": coste_tramo
                    })  
                # Convertir a DataFrame.
                df_desglose = pd.DataFrame(filas_bus)
                # Titulo.
                titulo_expander = []
                id += 1
                if pasajeros_totales > plazas_midi:
                    tipo_bus = "Estándar"
                elif pasajeros_totales > plazas_mini:
                    tipo_bus = "Midibus"
                else:
                    tipo_bus = "Minibus"
                coste_total = df_desglose[f"{metrica_escogida} tramo ({unidad})"].sum()
                coste_total_optimización += coste_total
                titulo_expander.append({
                    "Índice" : id,
                    "Tipo de bus" : tipo_bus,
                    "Pasajeros totales" : pasajeros_totales,
                    f"{metrica_escogida} total ({unidad})": coste_total
                })
                df_titulo = pd.DataFrame(titulo_expander)
                filas_tabla_3.append({
                "titulo": df_titulo,
                "desglose": df_desglose
                })
                nombre_clave = f"Ruta #{id}"
                todas_las_rutas[nombre_clave] = ruta_ordenada
                info_rutas[nombre_clave] = {
                    "tipo": tipo_bus,
                    "pasajeros": int(pasajeros_totales),
                    "coste": coste_total,
                    "recorrido": " ➔ ".join(ruta_ordenada)
                }
            # Impresión de las tablas.
            if filas_tabla:
                df_tabla = pd.DataFrame(filas_tabla)
                st.subheader(f"Buses estándar llenos directos a {nodo_destino}")
                st.dataframe(df_tabla, 
                    column_config = {"Índice":st.column_config.Column("Índice", width=10),
                        "Origen":st.column_config.Column("Origen", width="medium"),
                        "Número de buses":st.column_config.Column("Número de buses", width="medium"),
                        "Pasajeros totales":st.column_config.Column("Pasajeros totales", width="medium"),
                        f"{metrica_escogida} total ({unidad})":st.column_config.Column(f"{metrica_escogida} total ({unidad})", width="medium")}, 
                    use_container_width=True, hide_index=True)
            if filas_tabla_2:
                df_tabla_2 = pd.DataFrame(filas_tabla_2)
                st.subheader(f"Buses parcialmente llenos directos a {nodo_destino}")
                st.dataframe(df_tabla_2,
                    column_config = {"Índice":st.column_config.Column("Índice", width=10),
                        "Origen":st.column_config.Column("Origen", width="medium"),
                        "Tipo de bus":st.column_config.Column("Tipo de bus", width="medium"),
                        "Pasajeros":st.column_config.Column("Pasajeros ", width="medium"),
                        f"{metrica_escogida} ({unidad})":st.column_config.Column(f"{metrica_escogida} ({unidad})", width="medium")},
                    use_container_width=True, hide_index=True)
            if filas_tabla_3:
                st.subheader(f"Buses con paradas intermedias")
                for bus in filas_tabla_3:
                    st.dataframe(bus["titulo"],
                        column_config = {"Índice":st.column_config.Column("Índice", width=10),
                            "Origen":st.column_config.Column("Origen", width="medium"),
                            "Tipo de bus":st.column_config.Column("Tipo de bus", width="medium"),
                            "Pasajeros totales":st.column_config.Column("Pasajeros totales", width="medium"),
                            f"{metrica_escogida} total ({unidad})":st.column_config.Column(f"{metrica_escogida} total ({unidad})", width="medium")},
                        use_container_width=True, hide_index=True)
                    with st.expander("Detalles de la ruta"):
                        st.dataframe(bus["desglose"], use_container_width=True, hide_index=True)
            # -------------------------------------------------------------------------------------------
            # /Información adicional.////////////////////////////////////////////////////////////////////
            # -------------------------------------------------------------------------------------------
            st.divider()
            # Métricas Globales
            col1, col2, col3 = st.columns([2,1,1])
            with col1:
                with st.container(border=True):
                    st.markdown("**Buses utilizados por tipos:**")
                    st.write(f"""**Estándar:** {total_buses_estandar} |
                        **Midibus:** {total_midibuses} |
                        **Minibus:** {total_minibuses}"""
                    )
                    st.markdown(f"""Plazas de cada tipo de bus: 
                        Estándar: {plazas} | 
                        Midibus: {plazas_midi} | 
                        Minibus: {plazas_mini}"""
                    )
            with col2:
                with st.container(border=True):
                    st.markdown("**Buses totales:**")
                    st.subheader(total_buses_estandar + total_midibuses + total_minibuses)
            with col3:
                with st.container(border=True):
                    st.markdown(f"**{metrica_escogida} total:**")
                    st.subheader(f" {coste_total_optimización:.2f} {unidad}")
            # -------------------------------------------------------------------------------------------
            # /VISUALIZACIÓN DE MAPA DE RUTAS////////////////////////////////////////////////////////////
            # -------------------------------------------------------------------------------------------
            st.divider()
            st.subheader("Mapa interactivo de rutas")
            if todas_las_rutas:
                ALTURA_MAPA = 500
                col_selector, col_mapa = st.columns([1, 7])
                with col_selector:
                    # Ajustes estéticos con CSS
                    st.markdown(
                        f"""
                        <style>
                        div[role="radiogroup"] {{
                            display: flex !important;
                            flex-direction: column !important;
                            flex-wrap: nowrap !important;
                        }}
                        [data-testid="stRadio"] > div {{
                            max-height: {ALTURA_MAPA - 40}px !important;
                            overflow-y: auto !important;
                            padding-right: 5px;
                        }}
                        </style>
                        """,
                        unsafe_allow_html=True
                    )
                    with st.container(border=True):
                        opciones_selector = ["Todas"] + list(todas_las_rutas.keys())
                        bus_seleccionado = st.radio(
                            "Selecciona una ruta para aislarla en el mapa:",
                            options=opciones_selector,
                            label_visibility="collapsed"
                        )
                with col_mapa:
                    mapa_obj = renderizar_mapa_rutas(
                        diccionario_rutas=todas_las_rutas,
                        nodo_destino=nodo_destino,
                        bus_seleccionado=bus_seleccionado
                    )
                    st_folium(mapa_obj, width="100%", height=ALTURA_MAPA, returned_objects=[])
                # Cartel informativo
                if bus_seleccionado == "Todas":
                    st.info("Mostrando todas las rutas optimizadas.")
                elif bus_seleccionado in info_rutas:
                    detalles = info_rutas[bus_seleccionado]
                    st.info(
                        f"**{bus_seleccionado}** | "
                        f"{detalles['recorrido']} | "
                        f"**Tipo de bus:** {detalles['tipo']} | "
                        f"**Pasajeros:** {detalles['pasajeros']} | "
                        f"**{metrica_escogida} ruta:** {detalles['coste']:.2f} {unidad}"
                    )
            else:
                st.info("No hay rutas registradas para mostrar en el mapa.")
            # -------------------------------------------------------------------------------------------
            # /Información adicional.////////////////////////////////////////////////////////////////////
            # -------------------------------------------------------------------------------------------
            st.divider()
            # Sección Técnica Expansible
            with st.expander("Información adicional del modelo"):
                st.write(f"**Estado del Solver:** {res['estado']}")
                st.write(f"**Número de restricciones totales del problema:** {res.get('num_restricciones', '-')}")
                st.write(f"**Número de variables de decisión totales del problema:** {res.get('num_variables_decision', '-')}")
                st.write(f"**Valor de la función objetivo:** {res.get('fun_objetivo', 0):.2f}")
                st.write(
                    f"**Número de combinaciones posibles de rutas para cada bus:** "
                    f"{res.get('num_rutas_posibles', 0):.2e} "
                    f"<small style='opacity: 0.6;'>(Notación científica)</small>",
                    unsafe_allow_html=True
                )
                with st.container(border=True):
                    st.write("**Reducción de variables del tipo x[bus,ciudad origen, ciudad destino]:**")
                    st.write(f"""Número de combinaciones posibles: {res.get('num_posibles_x', '-')} | 
                        Número de variables finalmente creadas: {res.get('num_variables_x', '-')}""")
                    st.write(f"Se ha reducido un **{res.get('reduccion_x', 0):.1f}%** este tipo de variables.")
        else:
            st.error(f"El solver finalizó con estado: **{res['estado']}**")
            st.markdown("Posibles motivos")
            st.markdown("""
            * **Tiempo de cálculo insuficiente:** Al solver no le ha dado tiempo a encontrar una solución factible. Prueba a aumentar el tiempo de ejecución.
            * **Datos de entrada incoherentes:** Revisa que las cifras de pasajeros no contengan valores negativos ni decimales, y verifica que la estructura de la tabla sea correcta.
            """)
            # Botón de descarga
            st.write("Si tienes dudas sobre cómo debe ser el formato del archivo, puedes descargar la plantilla de ejemplo.")
            st.download_button(
                label="Descargar (CSV)",
                data=csv_ejemplo,
                file_name="ejemplo_demanda_pasajeros.csv",
                mime="text/csv"
            )
            st.caption("Si tras revisar estos puntos el problema persiste, puedes contactar con el desarrollador a través de [GitHub](https://github.com/pedro-portela-fernandez).")
# -------------------------------------------------------------------------------------------
# /BLOQUE GLOBAL DE CAPTURA DE ERRORES///////////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("⚠ Se ha producido un error durante la ejecución de la aplicación.")
        st.markdown("Revisa no haber puesto ningún valor negativo o decimal, así como que el formato de la tabla sea el adecuado.")
        st.write("Si tienes dudas sobre cómo debe ser el archivo, puedes descargar esta plantilla de ejemplo:")
        st.download_button(
            label="Descargar (CSV)",
            data=csv_ejemplo,
            file_name="ejemplo_demanda_pasajeros.csv",
            mime="text/csv"
        )
        st.caption("Si tras esto no se soluciona, puedes ponerte en contacto con el desarrollador del proyecto a través de [GitHub](https://github.com/pedro-portela-fernandez).")
        st.divider()
        # Mensaje de error automático
        st.subheader("Detalles del error del sistema:")
        st.exception(e)