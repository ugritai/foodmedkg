from pymongo import MongoClient

# Requires the PyMongo package.
# https://api.mongodb.com/python/current

client = MongoClient('mongodb://localhost:27017/')
result = client['FooDB']['Food'].aggregate([
    {
        '$lookup': {
            'from': 'FooDB_Grupos_ID', 
            'localField': 'food_subgroup', 
            'foreignField': 'subgroup', 
            'as': 'group_info'
        }
    }, {
        '$set': {
            'group_id': {
                '$arrayElemAt': [
                    '$group_info.group_id', 0
                ]
            }
        }
    }, {
        '$project': {
            '_id': 0, 
            'FooDB_ID': '$id', 
            'Name': '$name', 
            'group': '$food_group', 
            'subgroup': '$food_subgroup', 
            'group_id': '$group_id'
        }
    }, {
        '$out': {
            'db': 'Colecciones_Auxiliares', 
            'coll': 'Food_Simplificada'
        }
    }
])