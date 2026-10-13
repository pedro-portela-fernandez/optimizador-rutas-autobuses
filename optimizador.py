# -------------------------------------------------------------------------------------------
# /IMPORTACIONES/////////////////////////////////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
import pandas as pd
import math
import pulp
import networkx as nx
# -------------------------------------------------------------------------------------------
# /OPTIMIZADOR///////////////////////////////////////////////////////////////////////////////
# -------------------------------------------------------------------------------------------
def optimizador(df, paradas, plazas, epsilon, incremento_epsilon, delta, gamma, nodo_destino, tiempo_limite_seg):
    # ---------------------------------------------------------------------------------------
    # /Corrección desigualdad triangular//////////////////////////////////////////////////////
    # ---------------------------------------------------------------------------------------
    G = nx.DiGraph()
    for _, row in df.iterrows():
        G.add_edge(row['origen'], row['destino'], weight=row['coste_medio'])
        if row['destino'] != nodo_destino:
            G.add_edge(row['destino'], row['origen'], weight=row['coste_medio'])
    # Calcular los caminos mínimos entre todos los pares de ciudades.
    caminos_minimos = dict(nx.all_pairs_dijkstra_path_length(G))
    # Creamos un diccionario con los costes a partir de los datos corregidos.
    costes = {}
    ciudades = list(G.nodes)
    for orig in ciudades:
        for dest in ciudades:
            if orig != dest and dest in caminos_minimos[orig]:
                costes[orig, dest] = caminos_minimos[orig][dest]
    # ---------------------------------------------------------------------------------------
    # /HEURÍSTICA////////////////////////////////////////////////////////////////////////////
    # ---------------------------------------------------------------------------------------
    buses_por_parada = {parada: 0 for parada in paradas.keys()}
    pasajeros_restantes = {}
    # Los buses que se llenan en su parada van directos.
    for parada, pasajeros in paradas.items():
        if pasajeros >= plazas:
            n = math.floor(pasajeros/plazas)
            buses_por_parada[parada] += n
            pasajeros_restantes[parada] = pasajeros - plazas*n
        else:
            pasajeros_restantes[parada] = pasajeros
    # Cálculo del número de buses necesarios para los pasajeros restantes + un parámetro de holgura.
    np_restantes = sum(pasajeros_restantes.values())
    min_b = math.ceil(np_restantes / plazas)
    epsilon_maximo = len(paradas.keys()) + incremento_epsilon # Nunca harán falta mas buses que esos.
    estado = None
    # Bucle para ajustaar el numero de buses
    while estado != "Optimal" and epsilon <= epsilon_maximo:
        nb = min_b + epsilon 
        buses = [f"Bus_{i}" for i in range(1, nb + 1)] #Lista para los buses restantes
        # ---------------------------------------------------------------------------------------
        # /DEFINIR EL PROBLEMA DE MINIMIZACIÓN con PuLP//////////////////////////////////////////
        # ---------------------------------------------------------------------------------------
        prob = pulp.LpProblem("Modelo_Autobuses", pulp.LpMinimize)
        # ---------------------------------------------------------------------------------------
        # /VARIABLES DE DECISIÓN/////////////////////////////////////////////////////////////////
        # ---------------------------------------------------------------------------------------
        # Función auxiliar para asignar el valor infinito en caso de que se pida un coste no registrado.
        def get_dist(p1, p2):
            return costes.get((p1, p2), float("inf"))
        # Extraemos solo las paradas que tienen al menos 1 pasajero pendiente.
        paradas_con_demanda = [p for p, dem in pasajeros_restantes.items() if dem > 0]
        # x[k,i,j]: variable binaria, 1 si el bus k toma el camino i->j y 0 en otro caso.
        x = {}
        for k in buses:
            # Solo creamos trayectos para paradas que realmente tienen pasajeros
            for i in paradas_con_demanda:
                x[k, i, nodo_destino] = pulp.LpVariable(f"{k}_{i}_{nodo_destino}", cat ="Binary") 
                
                for j in paradas_con_demanda:
                    if i != j:
                        # Heurística para reducir dráticamente el número de variables.
                        coste_al_destino_origen = get_dist(i,nodo_destino)
                        coste_al_destino_futura = get_dist(j,nodo_destino)
                        coste_siguiente_parada = get_dist(i,j)
                        if (
                            coste_al_destino_futura < coste_al_destino_origen 
                            and coste_siguiente_parada < coste_al_destino_origen
                        ):
                            x[k, i, j] = pulp.LpVariable(f"{k}_{i}_{j}", cat =pulp.LpBinary)
        # y[k]: variable binaria, 1 si se utiliza el bus k y 0 en otro caso.
        y = pulp.LpVariable.dicts("Bus_Activo", buses, cat=pulp.LpBinary)
        # p[k, i] = Número de pasajeros que el bus k recoge en la parada i
        p = pulp.LpVariable.dicts(
            "Pasajeros",
            ((k, i) for k in buses for i in paradas_con_demanda),
            lowBound=0,
            cat=pulp.LpInteger
        )
        # ---------------------------------------------------------------------------------------
        # /FUNCIÓN OBJETIVO: minimizar el total de todos los trayectos///////////////////////////
        # ---------------------------------------------------------------------------------------
        prob += (
            pulp.lpSum((get_dist(i,j) + gamma) * x[(k, i, j)] for (k, i, j) in x.keys()) # Suma de todas los costes.
            + pulp.lpSum(delta * y[k] for k in buses), # Suma de un factor delta que representa el coste de usar cada bus para evitar usar buses innecesarios.
            "Minimizar_coste_total_y_buses_usados"
        )
        # ---------------------------------------------------------------------------------------
        # /RESTRICCIONES/////////////////////////////////////////////////////////////////////////
        # ---------------------------------------------------------------------------------------
        # 1. Visita única por parada (máximo una salida por nodo por autobús).
        for k in buses:
            for i in paradas_con_demanda:
                prob += (
                    pulp.lpSum(
                        x[bus, org, dest] for (bus,org,dest) in x.keys() 
                        if bus == k and org == i
                        )
                        <= y[k],
                    f"Max_Una_Salida_bus_{k}_parada_{i}",
                )
        # 2. Conservación de flujo en paradas intermedias.
        for k in buses:
            for parada in paradas_con_demanda:
                entradas = pulp.lpSum(
                    x[bus, org, dest]
                    for (bus,org,dest) in x.keys() 
                    if bus == k and dest == parada
                )
                salidas = pulp.lpSum(
                    x[bus, org, dest]
                    for (bus,org,dest) in x.keys() 
                    if bus == k and org == parada
                )
                # Permite el origen (salidas = entradas + 1).
                prob += (
                    salidas - entradas <= y[k],
                    f"Diferencia_Flujo_bus_{k}_parada_{parada}",
                )
                # Obliga a que si entra, tenga que salir.
                prob += (
                    entradas <= salidas,
                    f"No_Sumidero_bus_{k}_parada_{parada}",
                )
        # 3. Llegada a destino final.
        for k in buses:
            prob += (
                pulp.lpSum(
                    x[bus, org, dest] 
                    for (bus,org,dest) in x.keys()
                    if bus == k and dest == nodo_destino
                    ) 
                == y[k], # Para cada bus se suma todos los trayectos cuyo final es el destino y el total debe ser 0 o 1.
                f"Llegada_Destino_bus_{k}",
            )
        # 4. Cobertura de demanda.
        # 4.1. La suma de todos los pasajeros que cogen todos los buses en la parada i debe ser igual al numero de pasajeros que quedaban.
        for i in paradas_con_demanda:
            demanda = pasajeros_restantes[i]
            prob += (
                pulp.lpSum(p[k, i] for k in buses) == demanda,
                f"Cobertura_Demanda_parada_{i}"
            )
                # 4.2. La suma de los pasajeros que coge un bus en todas las paradas no puede superar el numero de plazas si se usa o 0 si no se usa.
        for k in buses:
            prob += (
                pulp.lpSum(p[k, i] for i in paradas_con_demanda) <= plazas * y[k],
                f"Capacidad_Maxima_bus_{k}"
            )
        # 4.3. Restricción doble.
        for k in buses:
            for i in paradas_con_demanda:
                suma_salida = pulp.lpSum(
                        x[bus, orig, dest] 
                        for (bus, orig, dest) in x.keys() 
                        if bus == k and orig == i
                ) # 1 si el bus k sale en algún momento de la parada i y 0 en caso contrario.
                # 4.3.1. Evitar que un bus recoja pasajeros de una parada por la que no pasa.
                prob += (
                    p[k, i] <= plazas * suma_salida,
                    f"Solo_Recoge_Si_Pasa_bus_{k}_parada_{i}"
                )
                # 4.3.2. Evitar que un bus pase por una parada en la que no recoja pasajeros.
                prob += (
                    p[k, i] >= 1 * suma_salida,
                    f"Solo_Pasa_Si_Recoge_bus_{k}_parada_{i}"
                )
        # 5 por cada parada solo puede pasar un bus para evitar divisiones de pasajeros irrelevantes.
        for i in paradas_con_demanda:
            suma_buses = pulp.lpSum(
                x[bus,orig,dest] for (bus,orig,dest) in x.keys() if orig == i
                )
            prob += (
                suma_buses <= 1,
                f"Por_{i}_solo_pasa_1_bus"
            )

        # ---------------------------------------------------------------------------------------
        # /RESOLUCIÓN////////////////////////////////////////////////////////////////////////////
        # ---------------------------------------------------------------------------------------
        # Solver configurado con máximo 45 segundos y 1% de gap relativo para evitar que se quede congelado.
        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=tiempo_limite_seg, gapRel=0.01)
        solucion = prob.solve(solver)
        estado = pulp.LpStatus[solucion]
        # Si no se ha resuelto, reiteramos con más buses posibles.
        if estado != "Optimal":
            epsilon += incremento_epsilon
    # ---------------------------------------------------------------------------------------
    # /Organizar los resultados de la optimización.//////////////////////////////////////////
    # ---------------------------------------------------------------------------------------
    # ---------------------------------------------------------------------------------------
    # /Información principal.////////////////////////////////////////////////////////////////
    # ---------------------------------------------------------------------------------------
    # Cuanta gente coge cada bus k en cada parada i
    recogida_pasajeros = {}
    for (k, i), var in p.items():
        recogida_pasajeros[k, i] = var.varValue
    # Rutas que realiza cada bus
    rutas_buses = {}
    for (k, i, j), var in x.items():
        rutas_buses[k, i, j] = var.varValue
    # ---------------------------------------------------------------------------------------
    # /Información adicional.////////////////////////////////////////////////////////////////
    # ---------------------------------------------------------------------------------------
    # Número de rutas posibles:
    num_rutas_posibles = sum(math.perm(len(paradas), k) for k in range(1, len(paradas) + 1))
    # Número de variables de decisión x creadas:
    num_posibles_x = (len(paradas)**2)*nb
    num_variables_x = len(x)
    if num_posibles_x > 0:
        reduccion_porcentaje = (1 - (num_variables_x / num_posibles_x)) * 100
    else:
        reduccion_porcentaje = 0
    return {
        'estado': pulp.LpStatus[solucion],
        'num_restricciones': len(prob.constraints),
        'num_variables_decision' : len(prob.variables()),
        'recogida_pasajeros' : recogida_pasajeros,
        'rutas_buses' : rutas_buses,
        'num_rutas_posibles' : num_rutas_posibles,
        'num_posibles_x' : num_posibles_x,
        'reduccion_x' : reduccion_porcentaje,
        'num_variables_x' : num_variables_x,
        'fun_objetivo' : prob.objective.value(),
        'buses_directos': buses_por_parada,
        'costes': costes,
    }