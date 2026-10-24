from pymongo import MongoClient

# Requires the PyMongo package.
# https://api.mongodb.com/python/current

client = MongoClient('mongodb://localhost:27017/')
result = client['ES_Alterada']['ES_Rango'].aggregate([
    {
        '$lookup': {
            'from': 'ES_FooDB', 
            'localField': 'Food', 
            'foreignField': 'Name', 
            'as': 'FooDB'
        }
    }, {
        '$unwind': {
            'path': '$FooDB'
        }
    }, {
        '$addFields': {
            'FooDB_IDs': '$FooDB.FooDB_IDs', 
            'Group_IDs': '$FooDB.group_ids'
        }
    }, {
        '$project': {
            'FooDB': 0
        }
    }, {
        '$out': {
            'db': 'ES_Alterada', 
            'coll': 'ES_Alterada'
        }
    }
])