# -------------------------------------------------------------------------------------------
# /IMPORTACIONES/////////////////////////////////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
import json
import folium
from streamlit_folium import st_folium
# -------------------------------------------------------------------------------------------
# /Carga de los datos de las carreteras//////////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
def cargar_datos_geograficos():
    """Carga los JSONs de carreteras y nodos desde la carpeta data/."""
    try:
        with open("data/geometrias_rutas.json", "r", encoding="utf-8") as f:
            geometrias = json.load(f)
    except Exception:
        geometrias = {}

    try:
        with open("data/nodos_galicia.json", "r", encoding="utf-8") as f:
            datos_paradas = json.load(f)
    except Exception:
        datos_paradas = []

    # Mapeo { "A Coruña": {"coords": [lat, lon], "estacion": "..."} }
    info_paradas = {
        p["nombre"]: {
            "coords": [p["lat"], p["lon"]],
            "estacion": p.get("estacion", p["nombre"])
        }
        for p in datos_paradas
    }

    return geometrias, info_paradas

COLOR_RUTAS = "#0B2A91"
# -------------------------------------------------------------------------------------------
# /RENDERIZADO///////////////////////////////////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
def renderizar_mapa_rutas(diccionario_rutas, nodo_destino="Viveiro", bus_seleccionado="Todas"):
    """
    Genera y dibuja el mapa de Folium.
    - diccionario_rutas: { "Ruta #1 (Midibus)": ["Ferrol", "Narón", "Viveiro"], ... }
    - bus_seleccionado: "Todas" o el nombre concreto de la ruta a aislar.
    """
    geometrias, info_paradas = cargar_datos_geograficos()

    # Definir el encuadre/límites permitidos para Galicia
    limites_galicia = [
        [40.7, -9.3],  # Esquina inferior izquierda (Suroeste)
        [44.8, -6.7]   # Esquina superior derecha (Noreste)
    ]

    # Crear el mapa base de Folium restringido a Galicia
    mapa = folium.Map(
        location=[42.9, -7.85],
        zoom_start=8,
        min_zoom=7,
        max_zoom=15,
        max_bounds=True,
        min_lat=limites_galicia[0][0],
        max_lat=limites_galicia[1][0],
        min_lon=limites_galicia[0][1],
        max_lon=limites_galicia[1][1],
        tiles="OpenStreetMap"
    )

    # Filtrar si el usuario eligió un autobús en concreto
    rutas_a_dibujar = {}
    for idx, (nombre_bus, lista_paradas) in enumerate(diccionario_rutas.items()):
        if bus_seleccionado == "Todas" or bus_seleccionado == nombre_bus:
            rutas_a_dibujar[nombre_bus] = (lista_paradas, COLOR_RUTAS)

    # 1. Dibujar carreteras
    for nombre_bus, (lista_paradas, color) in rutas_a_dibujar.items():
        for i in range(len(lista_paradas) - 1):
            orig = lista_paradas[i]
            dest = lista_paradas[i + 1]
            clave_tramo = f"{orig}->{dest}"

            puntos_carretera = geometrias.get(clave_tramo)
            
            # Si existe la geometría del tramo la dibujamos
            if puntos_carretera:
                folium.PolyLine(
                    locations=puntos_carretera,
                    color=color,
                    weight=5 if bus_seleccionado != "Todas" else 4,
                    opacity=0.9 if bus_seleccionado != "Todas" else 0.75,
                    tooltip=f"<b>{nombre_bus}</b>: {orig} ➔ {dest}"
                ).add_to(mapa)

    # 2. Dibujar paradas / marcadores
    paradas_unicas_en_rutas = set()
    for lista_paradas, _ in rutas_a_dibujar.values():
        paradas_unicas_en_rutas.update(lista_paradas)

    for parada in paradas_unicas_en_rutas:
        if parada in info_paradas:
            coords = info_paradas[parada]["coords"]
            estacion = info_paradas[parada]["estacion"]

            if parada == nodo_destino:
                icon = folium.Icon(color="darkblue", icon="star", prefix="fa")
                popup_txt = f"<b>DESTINO FINAL: {parada}</b><br>{estacion}"
            else:
                icon = folium.Icon(color="blue", icon="bus", prefix="fa")
                popup_txt = f"<b>{parada}</b><br>{estacion}"

            folium.Marker(
                location=coords,
                popup=popup_txt,
                tooltip=parada,
                icon=icon
            ).add_to(mapa)

    return mapa