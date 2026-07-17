// profile.js
async function getProfile() {
    const res = await fetch('/api/profile');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
}

function formatDateToRussian(dateStr) {
    if (!dateStr) return "—";
    return new Date(dateStr)
        .toLocaleDateString("ru-RU", { day: "numeric", month: "long" })
        .replace(" ", "\u00A0");
}

async function buildProfile() {
    const data = await getProfile();

    // Навбар
    document.querySelector(".user-ip").textContent = data.ip;
    document.querySelector(".user-name").textContent = data.username;

    const statusEl = document.querySelector(".user-status");
    const statusMap = {
        active: ["АКТИВЕН", "--status-active"],
        restricted: ["ОГРАНИЧЕН", "--status-restricted"],
        inactive: ["НЕАКТИВЕН", "--status-blocked"]
    };

    const [text, colorVar] = statusMap[data.status] || ["Не определено", "--status-blocked"];
    statusEl.textContent = text;
    statusEl.style.color = getComputedStyle(document.documentElement)
        .getPropertyValue(colorVar);

    // Баланс
    document.querySelector(".balance__amount").textContent = `${data.balance} ₽`;
    document.querySelector(".balance__next").textContent =
        "Следующее списание:\u00A0" + formatDateToRussian(data.next_payment);

    // Тариф
    const tariffHeader = document.querySelector(".tariff-card .card__header");
    tariffHeader.textContent = `Тариф: "${data.tariff?.name || 'Не назначен'}"`;

    const tariffTrack = document.querySelector(".tariff-card .carousel__track");
    tariffTrack.innerHTML = `
        <div class="carousel__item">Скорость: ${data.speed || 0} Мбит/с</div>
        <div class="carousel__item">Устройств: ${data.devices.length}</div>
        <div class="carousel__item">Ежемесячно: ${data.monthly_fee || 0} ₽</div>
    `;

    // Устройства
    const devicesOption = document.getElementById("devices-option");
    if (devicesOption) {
        devicesOption.classList.add("hidden");
    }

    const devicesTrack = document.getElementById("devices-track");
    devicesTrack.innerHTML = "";

    data.devices.forEach(dev => {
        const statusText = dev.status === "active" ? "Активно" : "Неактивно";
        const statusClass = dev.status === "active" ? "status-active" : "status-inactive";

        devicesTrack.innerHTML += `
            <div class="carousel__item device__item" onclick="openDeviceModal('${dev.ip}')">
                <span class="device__ip">${dev.ip}</span>
                <span class="device__name">${dev.name}</span>
                <span class="device__status ${statusClass}">${statusText}</span>
            </div>
        `;
    });
}

window.onload = buildProfile;

// ==================== МОДАЛКИ ====================
function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.add("show");
        openModalBG();
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.remove("show");
        closeModalBG();
    }
}

function openModalBG() {
    const bg = document.getElementById("modal-bg");
    if (bg) {
        bg.classList.add("show");
    }
}

function closeModalBG() {
    const opened = document.querySelectorAll(".modal-content.show").length;
    const bg = document.getElementById("modal-bg");

    if (!opened && bg) {
        bg.classList.remove("show");
    }
}

async function copyOnClick(el) {
    try {
        await navigator.clipboard.writeText(el.value);
    } catch (_) {}
}

async function openDeviceModal(targetip) {
    openModal("editDeviceModal");

    try {
        const res = await fetch("/api/getDevice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ip: targetip })
        });

        if (!res.ok) {
            throw new Error((await res.json()).error);
        }

        const d = await res.json();

        document.getElementById("deviceEditName").value = d.name;
        document.getElementById("ipEdit").value = d.ip;
        document.getElementById("publickeyEdit").value = d.public_key;
        document.getElementById("statusEdit").checked = d.status === "active";
    } catch (e) {
        console.error(e);
        alert("Ошибка загрузки устройства: " + e.message);
        closeModal("editDeviceModal");
    }
}

async function addDevice() {
    closeModal("addDeviceModal");
    openModal("keysModal");

    const name = document.getElementById("deviceName").value.trim();

    try {
        const res = await fetch("/api/addDevice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name || "Новое устройство" })
        });

        if (!res.ok) {
            throw new Error((await res.json()).error);
        }

        const d = await res.json();

        document.getElementById("privateKey").value = d.private_key;
        document.getElementById("publicKey").value = d.public_key;
    } catch (e) {
        console.error(e);
        alert("Ошибка создания: " + e.message);
        closeModal("keysModal");
    }
}

async function deleteDevice() {
    const ip = document.getElementById("ipEdit").value;

    if (!confirm("Удалить устройство " + ip + "?")) {
        return;
    }

    try {
        const res = await fetch("/api/deleteDevice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ip })
        });

        if (!res.ok) {
            throw new Error((await res.json()).error);
        }

        location.reload();
    } catch (e) {
        alert("Ошибка: " + e.message);
    }
}

async function editDevice() {
    const ip = document.getElementById("ipEdit").value;
    const name = document.getElementById("deviceEditName").value;
    const active = document.getElementById("statusEdit").checked;

    try {
        const res = await fetch("/api/editDevice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ip, name, status: active })
        });

        if (!res.ok) {
            throw new Error((await res.json()).error);
        }

        location.reload();
    } catch (e) {
        alert("Ошибка: " + e.message);
    }
}