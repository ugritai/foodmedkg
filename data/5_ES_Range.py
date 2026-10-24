import json

#------ 1 CARGAR ARCHIVOS ------
with open("ES.json", "r", encoding="utf-8") as f:
    data = json.load(f)

#Si es un solo objeto, lo convertimos en lista
if isinstance(data, dict):
    data = [data]

#------ 2 DEFINIR RANGOS FIJOS ------
# Definimos los límites de cada categoría
RANGE_LIMITS = {
    "Muy negativo": (0.52, 0.76),
    "Negativo": (0.76, 0.90),
    "Neutral": (0.90, 1.1),
    "Positivo": (1.10, 1.51),
    "Muy positivo": (1.51, 1.92),
}

# Opcional: guardar estos rangos como referencia
with open("ES_min_max.json", "w", encoding="utf-8") as f:
    json.dump(RANGE_LIMITS, f, ensure_ascii=False, indent=2)
print("\nArchivo auxiliar guardado como ES_min_max.json")

#------ 3 FUNCIÓN PARA OBTENER EL NIVEL ------
def get_level(value):
    for i, (label, (low, high)) in enumerate(RANGE_LIMITS.items()):
        if low <= value < high or (i == 4 and value <= high):  # incluye el límite superior del último
            return i
    return None  # si el valor está fuera de los rangos

#------ 4 AÑADIMOS CAMPOS CON EL NIVEL ------
for item in data:
    for key in list(item.keys()):
        if key == "Name":
            continue
        try:
            num_value = float(str(item[key]).replace(",", "."))
        except ValueError:
            continue

        level = get_level(num_value)
        if level is not None:
            item[f"{key}_level"] = level

#------ 5 GUARDAR RESULTADOS ------
with open("ES_Rango.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("\nArchivo final guardado como ES_Rango.json")
