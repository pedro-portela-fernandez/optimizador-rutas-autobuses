# Script encargado de construir las matrices de distancias/tiempos reales entre cada par de paradas.
# -------------------------------------------------------------------------------------------
# /IMPORTACIONES/////////////////////////////////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
import json
import urllib.request
import pandas as pd
# -------------------------------------------------------------------------------------------
# /Obtener los datos de distancias y tiempos.////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
def generar_csv_osrm(ruta_json="data/nodos_galicia.json"):
    # Cargar paradas
    with open(ruta_json, "r", encoding="utf-8") as f:
        nodos = json.load(f)

    # Nombres de los nodos en orden.
    nombres = [nodo["nombre"] for nodo in nodos]

    # Consultar OSRM Table API
    coords_str = ";".join([f"{nodo['lon']},{nodo['lat']}" for nodo in nodos])
    url = f"http://router.project-osrm.org/table/v1/driving/{coords_str}?annotations=distance,duration"

    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        if response.status == 200:
            datos = json.loads(response.read().decode('utf-8'))
        else:
            raise Exception(f"Error OSRM: {response.status}")

    duraciones_seg = datos["durations"]
    distancias_m = datos["distances"]

    # Adaptar las matrices de 21x21 a la estructura de 3 columnas (origen, destino, valor)
    filas_distancia = []
    filas_tiempo = []

    num_nodos = len(nombres)
    for i in range(num_nodos):
        for j in range(num_nodos):
            if i != j:  # Omitir trayectos de una ciudad a sí misma
                origen = nombres[i]
                destino = nombres[j]
                
                # Conversión de unidades
                dist_km = round(distancias_m[i][j] / 1000.0, 2)
                tiempo_min = round(duraciones_seg[i][j] / 60.0, 1)

                filas_distancia.append({
                    "origen": origen,
                    "destino": destino,
                    "coste_medio": dist_km
                })
                
                filas_tiempo.append({
                    "origen": origen,
                    "destino": destino,
                    "coste_medio": tiempo_min
                })

    # Guardar los dataframes en CSV
    df_dist = pd.DataFrame(filas_distancia)
    df_tiempo = pd.DataFrame(filas_tiempo)

    df_dist.to_csv("data/matriz_distancias.csv", index=False, encoding="utf-8-sig")
    df_tiempo.to_csv("data/matriz_tiempos.csv", index=False, encoding="utf-8-sig")

    print("¡Archivos 'matriz_distancias.csv' y 'matriz_tiempos.csv' generados con éxito!")

# Ejecutar la generación
generar_csv_osrm()