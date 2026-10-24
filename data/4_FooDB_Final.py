[
    {
        '$lookup': {
            'from': 'Food_Simplificada', 
            'localField': 'FooDB_ID', 
            'foreignField': 'FooDB_ID', 
            'as': 'food_info'
        }
    }, {
        '$unwind': {
            'path': '$food_info'
        }
    }, {
        '$addFields': {
            'group': '$food_info.group', 
            'subgroup': '$food_info.subgroup', 
            'group_id': '$food_info.group_id'
        }
    }, {
        '$project': {
            'id': '$id', 
            'FooDB_ID': '$FooDB_ID', 
            'food_name': '$food_name', 
            'group': '$group', 
            'subgroup': '$subgroup', 
            'group_id': '$group_id', 
            'constituents': '$constituents', 
            'citation': '$citation'
        }
    }, {
        '$out': {
            'db': 'Colecciones_Finales', 
            'coll': 'FooDB_Alimento_Constituyentes'
        }
    }
]