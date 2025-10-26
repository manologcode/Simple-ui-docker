from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import docker
import uvicorn
import os
import json
import re

import db_tinydb as db_tinydb

app = FastAPI()
client = docker.from_env()
app.mount("/static", StaticFiles(directory="static"), name="static")
class SemanticParams(BaseModel):
    name: str
    port: str

title = os.environ.get("TITLE", "Servidor de Datos")

@app.get("/", response_class=HTMLResponse)
async def html_ini():
    try:
        with open(os.path.join("static", "index.html"), "r", encoding="utf-8") as file:
            return HTMLResponse(content=file.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

@app.post("/add_item")
async def add_item(request: SemanticParams):
    response ={'data': db_tinydb.add_service(request.dict()), 'title': title}
    return response
  
@app.post("/del_item/")
async def del_item(request: SemanticParams):
    response ={'data': db_tinydb.delete_service(request.name), 'title': title}
    return response
  
@app.get("/list_news")
def list_news():
  items=db_tinydb.get_all_services()
  dockers=list_dockers()
  dockers_not_in_items = [
    docker for docker in dockers
    if not any(item['name'] == docker['name'] for item in items)
  ]

  return {"dockers" : dockers_not_in_items, 'items': items, 'title': title}

@app.get("/list")
def list():
  response=[]
  for item in db_tinydb.get_all_services():
    item['status'] = status(item['name'])
    response.append(item)
  result ={'data': response, 'title': title}
  return result

@app.get("/toggle/{docker_name}")
def toggle(docker_name):
  container = get_container(docker_name)
  if container:
    if container.status == "running":
      container.stop()
      response = "exited"
    else:
      container.start()
      response = "running"
    # response =  container.status
  else:
    response = "error"
  return response

@app.get("/stop/{docker_name}")
def stop(docker_name):
  container = get_container(docker_name)
  if container:
    if container.status == "running":
      container.stop()
      response = "exited"
  else:
    response = "error"
  return response

@app.get("/start/{docker_name}")
def start(docker_name):
  container = get_container(docker_name)
  if container:
    if container.status == "exited":
      container.start()
      response = "running"
  else:
    response = "error"
  return response

@app.get("/status/{docker_name}")
def status(docker_name):
  container = get_container(docker_name)
  return container.status if container else "error"

def get_container(docker_name):
  try:
    response = client.containers.get(docker_name)
  except:
    response= False
  return response

def list_dockers():
    response = []
    for container in client.containers.list(all=True):
        data_str = json.dumps(container.attrs, indent=4)
        port = find_host_ports(data_str) 
        data = {
            'name': container.name,
            'port': port
        }
        response.append(data)
    return response

def find_host_ports(data_str):

  # Usar una expresión regular para encontrar todos los "HostPort": "valor"
  pattern = r'"HostPort":\s*"([^"]*)"'
  matches = re.findall(pattern, data_str)

  # Filtrar para obtener el primer valor no vacío
  first_non_empty_host_port = None
  for port in matches:
      if port != "":
          first_non_empty_host_port = port
          break
  return first_non_empty_host_port


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5000, log_level="info")

