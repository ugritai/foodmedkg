import json

#------ 1 CARGAR ARCHIVOS ------
with open("ES_Alterada.json", "r", encoding="utf-8") as f:
    es_alterada = json.load(f)

with open("Food_Simplificada.json", "r", encoding="utf-8") as f:
    food_simplificada = json.load(f)

#------ 2 CREAR INDICES PARA LA BÚSQUEDA ------
food_by_id = {item["FooDB_ID"]: item for item in food_simplificada}
food_by_group = {}
for item in food_simplificada:
    gid = int(item["group_id"]["$numberLong"])
    food_by_group.setdefault(gid, []).append(item)
resultado = []

#------ 3 CREAR OBJETOS POR CADA ID ------

for entry in es_alterada:
    # Cogemos los campos importantes
    base_entry = {k: v for k, v in entry.items() if k not in ["_id", "FooDB_IDs", "Group_IDs"]}

    #Si estamos buscando alimentos, se añade su información:
    if entry.get("FooDB_IDs"):
        for fid in entry["FooDB_IDs"]:
            if fid in food_by_id:
                food_data = {k: v for k, v in food_by_id[fid].items() if k != "_id"}
                merged = {**base_entry, **food_data}
                resultado.append(merged)

    #En los grupos, obtener información de cada ID de alimento y añadirlo
    if entry.get("Group_IDs"):
        for gid in entry["Group_IDs"]:
            if gid in food_by_group:
                for food in food_by_group[gid]:
                    food_data = {k: v for k, v in food.items() if k != "_id"}
                    merged = {**base_entry, **food_data}
                    resultado.append(merged)

#------ 4 GUARDAR JSON ------
with open("ES_Final.json", "w", encoding="utf-8") as f:
    json.dump(resultado, f, ensure_ascii=False, indent=2)

print(f"\nArchivo final guardado como ES_Final.json")
