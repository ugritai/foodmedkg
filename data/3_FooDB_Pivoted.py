import json
import pandas as pd

#------ 1 CARGAR ARCHIVOS ------
with open("FooDB.json", "r", encoding="utf-8") as f:
    foodb_data = json.load(f)

with open("FooDB_Simplificada.json", "r", encoding="utf-8") as f:
    mapping_data = json.load(f)

with open("Nutrients.json", "r", encoding="utf-8") as f:
    nutrients_data = json.load(f)

with open("Compounds.json", "r", encoding="utf-8") as f:
    compounds_data = json.load(f)

#------ 3 CREAR DICCIONARIO PARA REFERENCIA A IDS ------
id_to_food_name = {item["FooDB_ID"]: item["Name"] for item in mapping_data}
id_to_nutrient_name = {item["id"]: item["name"] for item in nutrients_data}
id_to_compound_name = {item["id"]: item["name"] for item in compounds_data}

#------ 3 FILTRAR SOLO USDA Y DTU ------
filtered_entries = [e for e in foodb_data if e.get("citation") in ("USDA", "DTU")]
total = len(filtered_entries)
processed = []

#------ 4 CORREGIR NOMBRES Y CONSTITUYENTES VACÍOS ------
for i, entry in enumerate(filtered_entries, start=1):
    print(f"{i}/{total}", end="\r")

    # Corregimos constituyente
    source_type = entry.get("source_type")
    source_id = entry.get("source_id")

    if (not entry.get("orig_source_name")) or entry["orig_source_name"] in (None, "", "FAT"):
        if source_type == "Nutrient" and source_id in id_to_nutrient_name:
            entry["orig_source_name"] = id_to_nutrient_name[source_id]
        elif source_type == "Compound" and source_id in id_to_compound_name:
            entry["orig_source_name"] = id_to_compound_name[source_id]

    # Valores originales
    content_raw = entry.get("standard_content", "0")
    try:
        content = float(content_raw) if content_raw not in (None, "", "NaN") else 0.0
    except ValueError:
        content = 0.0  # Si viene algo raro no rompe

    unit = entry.get("orig_unit")

    # ⚡ Conversión: si >1000 mg/100g => g/100g
    if unit == "mg/100 g" and content > 1000:
        content = content / 1000
        unit = "g/100 g"

    # Renombrar y mostrar solo campos importantes
    processed.append({
        "id": entry.get("id"),
        "FooDB_ID": entry.get("food_id"),
        "food_name": entry.get("orig_food_common_name"),
        "constituent": entry.get("orig_source_name"),
        "constituent_unit": unit,
        "citation": entry.get("citation"),
        "content": content
    })

#------ 5 PIVOTAR TABLA ------
df = pd.DataFrame(processed)

# Concatenamos cantidad + unidad
df["content_unit"] = df["content"].astype(str) + " " + df["constituent_unit"].astype(str)

# Creamos un diccionario para almacenar los constituyentes de cada alimento
def build_constituent_dict(sub_df):
    return dict(zip(sub_df["constituent"], sub_df["content_unit"]))

# Agrupamos la búsqueda por ID y nombre
constituents_df = df.groupby(["FooDB_ID", "food_name"]).apply(build_constituent_dict).reset_index(name="constituents")
extra_info = df.groupby(["FooDB_ID", "food_name"])[["id", "citation"]].first().reset_index()

# Combinamos los dataframes para obtener la tabla final
final_df = pd.merge(constituents_df, extra_info, on=["FooDB_ID", "food_name"])
final_df.to_json("fooDB_Final.json", orient="records", indent=2, force_ascii=False)

#------ 6 CONVERTIMOS CONSTITUYENTES A JSON ------
with open("fooDB_Final.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for food in data:
    if "constituents" in food:
        food["constituents"] = json.dumps(food["constituents"], ensure_ascii=False)

# Guardamos el resultado
with open("FooDB_Final.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nArchivo final pivotado guardado como FooDB_Final.json ({len(data)} registros)")
