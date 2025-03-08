const urlBase = `${window.location.protocol}//${window.location.hostname}`;
async function initializeApp() {

  drawButtons();
  document.getElementById('edit-button').addEventListener('click', toggleEditButton);
  document.addEventListener('click', handleMenuToggle);
}

async function drawButtons() {
  const services = await fetchServicesGet('/list');
  document.getElementById('title').textContent = services.title;
  document.getElementById('button-container').innerHTML = services.data.map((service, index) => 
    createButtonHTML(index, service.port, service.name, service.status)).join('');
}

function toggleEditButton() {
  const editButton = document.getElementById('edit-button');
  if (editButton.textContent.trim() === 'Editar Servicios') {
    editButton.textContent = 'Cerrar Edición';
    drawButtonsEdit();
  } else {
    editButton.textContent = 'Editar Servicios';
    drawButtons();
  }
}

async function drawButtonsEdit() {
  const data = await fetchServicesGet('/list_news');
  console.log(data)
  document.getElementById('title').textContent = data.title;
  document.getElementById('button-container').innerHTML = [...data.items.map((item, i) => 
    createButtonEditHTML(i, item.port, item.name, "item")), 
    ...data.dockers.map((docker, i) => 
    createButtonEditHTML(i + data.items.length, docker.port, docker.name, "docker"))].join('');
}

function createButtonHTML(id, port, name, status) {
  const isRunning = status === "running";
  return `
    <div class="button-container ${isRunning ? 'btn-active' : 'btn-unactive'}">
      ${isRunning ? `<a href="${urlBase}:${port}" class="service-button" target="_blank" id="item-${id}">${name}</a>` : 
      `<div class="service-button" id="item-${id}">${name}</div>`}
      <span class="menu-toggle">⋮</span>
      <div class="menu">
        <div class="menu-item" onclick="toggleItem(${id})">${isRunning ? 'Parar servicio' : 'Arrancar servicio'}</div>
      </div>
    </div>`;
}

function createButtonEditHTML(id, port, name, type) {
  const isDocker = type === "docker";
  return `
    <div class="button-container ${isDocker ? 'btn-unselec' : 'btn-selec'}" id="container-${id}">
      <div data-port="${port}" class="service-button" id="item-${id}" target="_blank">${name}</div>
      <span class="menu-toggle">${isDocker ? '+' : '-'}</span>
      <div class="menu">
        <div class="menu-item" onclick="${isDocker ? `addItem(${id})` : `delItem(${id})`}">${isDocker ? 'Añadir servicio' : 'Quitar servicio'}</div>
      </div>
    </div>`;
}

async function addItem(id) {
  const element = document.getElementById(`item-${id}`);
  const container = document.getElementById(`container-${id}`);
  const port=element.dataset.port
  const data = { port: port, name: element.textContent };
  const response = await fetchServicesPost("/add_item", data);
  if (response.ok) {
    container.classList.remove("btn-unselec");
    container.classList.add("btn-selec");
  }
}

async function delItem(id) {
  const element = document.getElementById(`item-${id}`);
  const container = document.getElementById(`container-${id}`);
  const port=element.dataset.port
  const data = { port: port, name: element.textContent };
  const response = await fetchServicesPost("/del_item", data);
  if (response.ok) {
    container.classList.remove("btn-selec");
    container.classList.add("btn-unselec");
  }
}0

async function toggleItem(id) {
  const element = document.getElementById(`item-${id}`);
  await fetchServicesGet(`/toggle/${element.textContent}`);
  drawButtons();
}

async function fetchServicesGet(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Network response was not ok');
    return await response.json();
  } catch (error) {
    console.error('Error fetching services:', error);
    return [];
  }
}

async function fetchServicesPost(url, data) {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response;
  } catch (error) {
    console.error('Error:', error);
    return { ok: false };
  }
}

function handleMenuToggle(event) {
  if (event.target.classList.contains('menu-toggle')) {
    let menu = event.target.nextElementSibling;
    if (menu) menu.classList.toggle('show');
  } else {
    document.querySelectorAll('.menu').forEach(menu => menu.classList.remove('show'));
  }
}

initializeApp();