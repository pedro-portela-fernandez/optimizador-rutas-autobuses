# Generador de las carreteras entre nodos.
# -------------------------------------------------------------------------------------------
# /IMPORTACIONES/////////////////////////////////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
import urllib.request
import json
import time
# -------------------------------------------------------------------------------------------
# /Lectura de coordenadas////////////////////////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
with open('data/nodos_galicia.json', 'r', encoding='utf-8') as f:
    datos_paradas = json.load(f)
# Convertirlo al diccionario
COORDENADAS = {
    parada["nombre"]: [parada["lat"], parada["lon"]] 
    for parada in datos_paradas
}
# -------------------------------------------------------------------------------------------
# /Obtención de las rutas////////////////////////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
def obtener_ruta_osrm(orig_coords, dest_coords):
    """Consulta OSRM mediante urllib.request y devuelve la lista [lat, lon]."""
    url = f"http://router.project-osrm.org/route/v1/driving/{orig_coords[1]},{orig_coords[0]};{dest_coords[1]},{dest_coords[0]}?overview=full&geometries=geojson"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get("code") == "Ok":
                coords = data["routes"][0]["geometry"]["coordinates"]
                # Invertimos de [lon, lat] a [lat, lon] para Folium
                return [[pt[1], pt[0]] for pt in coords]
    except Exception as e:
        print(f"Error consultando OSRM: {e}")
    
    return [orig_coords, dest_coords]

def generar_fichero_geometrias():
    print("Iniciando la descarga de las trazadas por carretera...")
    geometrias = {}
    ciudades = list(COORDENADAS.keys())
    total_combinaciones = len(ciudades) * (len(ciudades) - 1)
    contador = 0

    for orig in ciudades:
        for dest in ciudades:
            if orig != dest:
                contador += 1
                clave = f"{orig}->{dest}"
                print(f"[{contador}/{total_combinaciones}] Descargando carretera: {clave}")
                
                puntos_carretera = obtener_ruta_osrm(COORDENADAS[orig], COORDENADAS[dest])
                geometrias[clave] = puntos_carretera
                
                time.sleep(0.1)  # Pausa para no saturar el servidor

    # Guardamos el resultado en el JSON local
    with open("data/geometrias_rutas.json", "w", encoding="utf-8") as f:
        json.dump(geometrias, f, ensure_ascii=False)
    
    print("\n¡HECHO! Se ha generado 'geometrias_rutas.json' correctamente.")

if __name__ == "__main__":
    generar_fichero_geometrias()