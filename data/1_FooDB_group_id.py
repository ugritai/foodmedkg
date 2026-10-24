from pymongo import MongoClient

# Requires the PyMongo package.
# https://api.mongodb.com/python/current

client = MongoClient('mongodb://localhost:27017/')
result = client['FooDB']['Food'].aggregate([
    {
        '$group': {
            '_id': {
                'group': '$food_group', 
                'subGroup': '$food_subgroup'
            }
        }
    }, {
        '$setWindowFields': {
            'partitionBy': None, 
            'sortBy': {
                '_id.subGroup': 1
            }, 
            'output': {
                'group_id': {
                    '$documentNumber': {}
                }
            }
        }
    }, {
        '$project': {
            '_id': 0, 
            'group': '$_id.group', 
            'subgroup': '$_id.subGroup', 
            'group_id': '$group_id'
        }
    }, {
        '$out': {
            'db': 'Colecciones_Auxiliares', 
            'coll': 'FooDB_Grupos_ID'
        }
    }
])