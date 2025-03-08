from tinydb import TinyDB, Query

db = TinyDB('data.json')

def add_service(service):
    return db.insert(service)

def delete_service(name):
    Service = Query()
    return db.remove(Service.name == name)

def get_all_services():
    return db.all()

