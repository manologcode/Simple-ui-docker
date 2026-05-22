from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import docker
import uvicorn
import os
import json
import re
import time
from collections import defaultdict, deque

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

@app.get("/apidocs.json")
async def api_docs():
    try:
        with open("apidocs.json", "r", encoding="utf-8") as file:
            api_docs_content = json.load(file)
            return JSONResponse(content=api_docs_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="API docs not found")

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
  current_container = get_current_container_name()
  
  dockers_not_in_items = [
    docker for docker in dockers
    if not any(item['name'] == docker['name'] for item in items)
    and docker['name'] != current_container  # Excluir el propio servicio
  ]

  return {"dockers" : dockers_not_in_items, 'items': items, 'title': title}

@app.get("/list")
def list():
  response=[]
  for item in db_tinydb.get_all_services():
    item['status'] = status(item['name'])
    item['group'] = get_container_group(item['name'])
    response.append(item)
  result ={'data': response, 'title': title}
  return result

@app.get("/list_groups")
def list_groups():
  """Returns containers grouped by ui.group label, with dependency order"""
  all_containers = client.containers.list(all=True)
  groups_dict = defaultdict(list)
  ungrouped = []
  
  # Separar contenedores por grupo
  for container in all_containers:
    container_data = get_container_info(container)
    group = get_container_group_by_labels(container)
    
    if group:
      groups_dict[group].append(container_data)
    else:
      ungrouped.append(container_data)
  
  # Ordenar cada grupo por dependencias
  result = {}
  for group_name, containers in groups_dict.items():
    ordered = build_start_order(containers, all_containers)
    result[group_name] = ordered
  
  # Añadir contenedores sin grupo
  if ungrouped:
    result['ungrouped'] = ungrouped
  
  return {'groups': result, 'title': title}

@app.get("/toggle/{docker_name}")
def toggle(docker_name):
  container = get_container(docker_name)
  if container:
    group = get_container_group_by_labels(container)
    if group:
      # Si pertenece a un grupo, toggle el grupo completo
      if container.status == "running":
        stop_group_containers(group)
        response = "exited"
      else:
        start_group_containers(group)
        response = "running"
    else:
      # Si no pertenece a grupo, toggle individual
      if container.status == "running":
        container.stop()
        response = "exited"
      else:
        container.start()
        response = "running"
  else:
    response = "error"
  return response

@app.get("/stop/{docker_name}")
def stop(docker_name):
  container = get_container(docker_name)
  if container:
    group = get_container_group_by_labels(container)
    if group:
      stop_group_containers(group)
      response = "exited"
    else:
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
    group = get_container_group_by_labels(container)
    if group:
      start_group_containers(group)
      response = "running"
    else:
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


# ===== GROUP MANAGEMENT FUNCTIONS =====

def get_container_group_by_labels(container):
  """Obtiene el label ui.group de un contenedor, retorna None si no existe"""
  try:
    labels = container.labels
    return labels.get('ui.group') if labels else None
  except:
    return None

def get_container_group(container_name):
  """Obtiene el grupo de un contenedor por nombre"""
  container = get_container(container_name)
  if container:
    return get_container_group_by_labels(container)
  return None

def get_container_info(container):
  """Retorna info del contenedor: nombre, puerto, estado, grupo"""
  data_str = json.dumps(container.attrs, indent=4)
  port = find_host_ports(data_str)
  return {
    'name': container.name,
    'port': port,
    'status': container.status,
    'group': get_container_group_by_labels(container)
  }

def get_depends_on(container, all_containers_list):
  """Extrae las dependencias de un contenedor desde el label com.docker.compose.depends_on"""
  try:
    labels = container.labels
    if not labels:
      return []
    depends_on_str = labels.get('com.docker.compose.depends_on', '')
    if not depends_on_str:
      return []
    # Format: "service1:service_started,service2:service_started"
    deps = []
    for dep in depends_on_str.split(','):
      if ':' in dep:
        service_name = dep.split(':')[0].strip()
        deps.append(service_name)
    return deps
  except:
    return []

def build_start_order(containers, all_containers_list):
  """Construye el orden topológico de inicio basado en depends_on"""
  # Crear mapa de nombre -> contenedor para lookup rápido
  container_map = {c.name: c for c in all_containers_list}
  
  # Construir grafo de dependencias
  name_list = [c['name'] for c in containers]
  graph = {name: [] for name in name_list}
  in_degree = {name: 0 for name in name_list}
  
  for container in containers:
    c_name = container['name']
    # Obtener el contenedor completo desde all_containers_list
    full_container = container_map.get(c_name)
    if full_container:
      deps = get_depends_on(full_container, all_containers_list)
      # Solo considerar dependencias que están en el grupo
      for dep in deps:
        if dep in name_list:
          graph[dep].append(c_name)
          in_degree[c_name] += 1
  
  # Topological sort using Kahn's algorithm
  queue = deque([name for name in name_list if in_degree[name] == 0])
  sorted_order = []
  
  while queue:
    node = queue.popleft()
    sorted_order.append(node)
    for neighbor in graph[node]:
      in_degree[neighbor] -= 1
      if in_degree[neighbor] == 0:
        queue.append(neighbor)
  
  # Reordenar contenedores según orden topológico
  result = []
  for name in sorted_order:
    for container in containers:
      if container['name'] == name:
        result.append(container)
        break
  
  return result

def start_group_containers(group_name):
  """Arranca todos los contenedores de un grupo en orden de dependencias"""
  all_containers = client.containers.list(all=True)
  group_containers = []
  
  for container in all_containers:
    if get_container_group_by_labels(container) == group_name:
      group_containers.append(get_container_info(container))
  
  if not group_containers:
    return
  
  # Ordenar por dependencias
  ordered = build_start_order(group_containers, all_containers)
  
  # Arrancar en orden
  for container_info in ordered:
    container = get_container(container_info['name'])
    if container and container.status != "running":
      try:
        container.start()
        time.sleep(1)  # Esperar 1s entre arranques
      except:
        pass

def stop_group_containers(group_name):
  """Para todos los contenedores de un grupo en orden inverso de dependencias"""
  all_containers = client.containers.list(all=True)
  group_containers = []
  
  for container in all_containers:
    if get_container_group_by_labels(container) == group_name:
      group_containers.append(get_container_info(container))
  
  if not group_containers:
    return
  
  # Ordenar por dependencias y revertir para parada
  ordered = build_start_order(group_containers, all_containers)
  ordered.reverse()
  
  # Parar en orden inverso
  for container_info in ordered:
    container = get_container(container_info['name'])
    if container and container.status == "running":
      try:
        container.stop()
        time.sleep(0.5)  # Esperar 0.5s entre paradas
      except:
        pass

def get_current_container_name():
  """Obtiene el nombre del contenedor actual del servicio"""
  try:
    # El hostname en Docker es generalmente el ID del contenedor
    # Buscamos un contenedor que tenga este hostname como parte de su ID
    hostname = os.environ.get('HOSTNAME', '')
    
    if not hostname:
      return None
    
    all_containers = client.containers.list(all=True)
    for container in all_containers:
      if container.id.startswith(hostname) or container.name.lower() == hostname.lower():
        return container.name
    
    return None
  except:
    return None

@app.get("/stop-all")
def stop_all():
  """Para todos los contenedores excepto el servicio actual"""
  current_container_name = get_current_container_name()
  
  try:
    all_containers = client.containers.list(all=True)
    stopped_containers = []
    
    for container in all_containers:
      # No parar el contenedor actual
      if current_container_name and container.name == current_container_name:
        continue
      
      # Parar solo los que están corriendo
      if container.status == "running":
        try:
          container.stop()
          stopped_containers.append(container.name)
          time.sleep(0.5)
        except Exception as e:
          pass
    
    return {
      'status': 'success',
      'stopped_containers': stopped_containers,
      'current_container': current_container_name
    }
  except Exception as e:
    return {
      'status': 'error',
      'message': str(e)
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5000, log_level="info")

