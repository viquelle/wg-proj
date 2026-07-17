const state = {
    activeTab: "users",
    users: [],
    devices: [],
    payments: [],
    meta: {
        roles: [],
        user_statuses: [],
        device_statuses: []
    },
    modalStack: [],
    selectedUserId: null,
    selectedDeviceId: null,
    confirmAction: null
};

const el = {
    refreshBtn: document.getElementById("refresh-btn"),
    addBtn: document.getElementById("add-btn"),
    tabs: document.querySelectorAll(".tab"),

    usersPanel: document.getElementById("users-panel"),
    devicesPanel: document.getElementById("devices-panel"),
    paymentsPanel: document.getElementById("payments-panel"),

    usersList: document.getElementById("users-list"),
    devicesList: document.getElementById("devices-list"),
    paymentsList: document.getElementById("payments-list"),

    statUsers: document.getElementById("stat-users"),
    statDevices: document.getElementById("stat-devices"),
    statSpeed: document.getElementById("stat-speed"),

    modalOverlay: document.getElementById("modal-overlay"),
    modalRoot: document.getElementById("modal-root"),

    userModal: document.getElementById("user-modal"),
    userRole: document.getElementById("user-role"),

    userCreateModal: document.getElementById("user-create-modal"),
    createUserBtn: document.getElementById("create-user-btn"),
    createUserName: document.getElementById("create-user-name"),
    createUserRole: document.getElementById("create-user-role"),
    createUserBalance: document.getElementById("create-user-balance"),
    createUserFee: document.getElementById("create-user-fee"),
    createUserSpeed: document.getElementById("create-user-speed"),


    deviceModal: document.getElementById("device-modal"),
    deviceCreateModal: document.getElementById("device-create-modal"),
    paymentHistoryModal: document.getElementById("payment-history-modal"),
    paymentModal: document.getElementById("payment-modal"),
    confirmModal: document.getElementById("confirm-modal")
};

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatDate(value) {
    if (!value) return "—";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);

    return date.toLocaleDateString("ru-RU");
}

function formatMoney(value) {
    const num = Number(value || 0);
    return `${num} ₽`;
}

function getStatusDotClass(status) {
    if (status === "active") return "status-active";
    if (status === "restricted") return "status-restricted";
    return "status-inactive";
}

async function apiGetJson(url) {
    const response = await fetch(url, {
        method: "GET",
        headers: {
            "Accept": "application/json"
        }
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
        const message = data?.detail || `HTTP ${response.status}`;
        throw new Error(message);
    }

    return data;
}

async function apiSendJson(url, method, payload) {
    const response = await fetch(url, {
        method,
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        body: JSON.stringify(payload)
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
        const message = data?.detail || `HTTP ${response.status}`;
        throw new Error(message);
    }

    return data;
}

function showPanel(tabName) {
    state.activeTab = tabName;

    el.usersPanel.classList.toggle("active", tabName === "users");
    el.devicesPanel.classList.toggle("active", tabName === "devices");
    el.paymentsPanel.classList.toggle("active", tabName === "payments");

    el.tabs.forEach(tab => {
        tab.classList.toggle("active", tab.dataset.tab === tabName);
    });

    updateAddButtonState();
}

function updateAddButtonState() {
    if (state.activeTab === "users") {
        el.addBtn.classList.remove("btn-disabled");
    } else {
        el.addBtn.classList.add("btn-disabled");
    }
}

function renderModalStack() {
    const allModals = document.querySelectorAll(".modal");
    const stack = state.modalStack;
    const stackSize = stack.length;
    const baseZ = 2;

    allModals.forEach(modal => {
        modal.classList.add("hidden");
        modal.classList.remove("show", "is-top", "is-behind");
        modal.style.zIndex = "";
    });

    el.modalOverlay.classList.remove("show");
    el.modalOverlay.style.zIndex = "";

    if (stackSize === 0) {
        return;
    }

    stack.forEach((modal, index) => {
        const isTop = index === stackSize - 1;
        const z = baseZ + index * 2;

        modal.classList.remove("hidden");
        modal.classList.add("show");
        modal.classList.toggle("is-top", isTop);
        modal.classList.toggle("is-behind", !isTop);
        modal.style.zIndex = String(z);
    });

    const topZ = baseZ + (stackSize - 1) * 2;

    el.modalOverlay.classList.add("show");
    el.modalOverlay.style.zIndex = String(topZ - 1);
}

function openModal(modalElement) {
    if (!modalElement) return;

    state.modalStack = state.modalStack.filter(modal => modal !== modalElement);
    state.modalStack.push(modalElement);

    renderModalStack();
}

function closeTopModal() {
    if (state.modalStack.length === 0) return;

    const closedModal = state.modalStack.pop();

    if (closedModal) {
        closedModal.classList.remove("show", "is-top", "is-behind");
        closedModal.classList.add("hidden");
        closedModal.style.zIndex = "";
    }

    renderModalStack();
}

function updateStats() {
    const usersCount = state.users.length;
    const devicesCount = state.devices.length;
    const totalSpeed = state.users.reduce((sum, user) => sum + Number(user.speed || 0), 0);

    el.statUsers.textContent = String(usersCount);
    el.statDevices.textContent = String(devicesCount);
    el.statSpeed.textContent = String(totalSpeed);
}

function renderUsers() {
    el.usersList.innerHTML = "";

    for (const user of state.users) {
        const card = document.createElement("article");
        card.className = "entity-card";

        card.innerHTML = `
            <div class="entity-main">
                <div class="entity-title">ID ${user.id} · ${escapeHtml(user.username)}</div>
            </div>
            <div class="entity-right">
                <span class="status-dot ${getStatusDotClass(user.status)}"></span>
            </div>
        `;

        card.addEventListener("click", () => {
            openUserModal(user.id);
        });

        el.usersList.appendChild(card);
    }
}

function renderDevices() {
    el.devicesList.innerHTML = "";

    for (const device of state.devices) {
        const card = document.createElement("article");
        card.className = "entity-card";

        card.innerHTML = `
            <div class="entity-main">
                <div class="entity-title">ID ${device.id} · ${escapeHtml(device.name)}</div>
                <div class="entity-sub">${escapeHtml(device.status)} · owner ${device.user_id}</div>
            </div>
        `;

        card.addEventListener("click", () => {
            openDeviceModal(device.id);
        });

        el.devicesList.appendChild(card);
    }
}

function renderPayments() {
    el.paymentsList.innerHTML = "";

    for (const payment of state.payments) {
        const card = document.createElement("article");
        card.className = "entity-card";

        card.innerHTML = `
            <div class="entity-main">
                <div class="entity-title">ID ${payment.id} · ${escapeHtml(payment.desc || "")}</div>
                <div class="entity-sub">${escapeHtml(formatDate(payment.date))} · ${formatMoney(payment.amount)}</div>
            </div>
        `;

        card.addEventListener("click", () => {
            openPaymentModal(payment.id);
        });

        el.paymentsList.appendChild(card);
    }
}

function fillUserRoleSelect(object, selectedRole) {
    const select = object;
    select.innerHTML = "";

    for (const role of state.meta.roles) {
        const option = document.createElement("option");
        option.value = role;
        option.textContent = role;
        option.selected = role === selectedRole;
        select.appendChild(option);
    }
}

function renderUserDevicesStrip(devices) {
    const root = document.getElementById("user-devices-strip");
    root.innerHTML = "";

    for (const device of devices) {
        const item = document.createElement("div");
        item.className = "strip-item";

        item.innerHTML = `
            <div class="strip-main">
                <div class="strip-title">ID ${device.id} · ${escapeHtml(device.name)}</div>
                <div class="strip-sub">${escapeHtml(device.status)}</div>
            </div>
        `;

        item.addEventListener("click", () => {
            openDeviceModal(device.id);
        });

        root.appendChild(item);
    }
}

function renderUserPaymentsStrip(payments) {
    const root = document.getElementById("user-payments-strip");
    root.innerHTML = "";

    for (const payment of payments) {
        const item = document.createElement("div");
        item.className = "strip-item";

        item.innerHTML = `
            <div class="strip-main">
                <div class="strip-title">ID ${payment.id} · ${escapeHtml(payment.desc || "")}</div>
                <div class="strip-sub">${escapeHtml(formatDate(payment.date))} · ${formatMoney(payment.amount)}</div>
            </div>
        `;

        item.addEventListener("click", () => {
            openPaymentModal(payment.id);
        });

        root.appendChild(item);
    }
}

function openUserModal(userId) {
    const user = state.users.find(x => x.id === Number(userId));
    if (!user) return;

    state.selectedUserId = user.id;

    document.getElementById("user-modal-id").textContent = `ID ${user.id}`;

    const statusEl = document.getElementById("user-modal-status");
    statusEl.innerHTML = `
        <span class="status-dot ${getStatusDotClass(user.status)}"></span>
        <span>${escapeHtml(user.status)}</span>
    `;

    document.getElementById("user-name").value = user.username || "";
    document.getElementById("user-created-at").value = user.created_at || "";
    document.getElementById("user-next-payment").value = user.next_payment || "";
    document.getElementById("user-balance").value = user.balance ?? 0;
    document.getElementById("user-monthly-fee").value = user.monthly_fee ?? 0;
    document.getElementById("user-speed").value = user.speed ?? 0;

    fillUserRoleSelect(el.userRole, user.role);
    renderUserDevicesStrip(user.devices || []);

    openModal(el.userModal);
}

function openCreateUserModal() {
    el.createUserName.value = "Устройство";
    fillUserRoleSelect(el.createUserRole, "regular")
    el.createUserBalance.value = "0";
    el.createUserFee.value = "0";
    el.createUserSpeed.value = "0";

    openModal(el.userCreateModal); 
}


function openDeviceModal(deviceId) {
    const device = state.devices.find(x => x.id === Number(deviceId));
    if (!device) return;

    state.selectedDeviceId = device.id;

    document.getElementById("device-modal-id").textContent = `ID ${device.id}`;

    const statusEl = document.getElementById("device-modal-status");
    statusEl.innerHTML = `
        <span class="status-dot ${getStatusDotClass(device.status)}"></span>
        <span>${escapeHtml(device.status)}</span>
    `;

    document.getElementById("device-view-name").value = device.name || "";
    document.getElementById("device-view-owner-id").value = device.user_id ?? "";
    document.getElementById("device-view-ip").value = device.ip || "";
    document.getElementById("device-view-public-key").value = device.public_key || "";

    openModal(el.deviceModal);
}

function openCreateDeviceModal(ownerId) {
    document.getElementById("device-create-name").value = "";
    document.getElementById("device-create-owner-id").value = ownerId ?? "";
    document.getElementById("device-create-ip-suffix").value = "0";
    document.getElementById("device-create-has-own-key").checked = false;
    document.getElementById("device-create-public-key").value = "";

    updateDeviceCreateKeyMode();
    updateDeviceCreateIpPreview();

    openModal(el.deviceCreateModal);
}

function openConfirmModal(text, action) {
    document.getElementById("confirm-text").textContent = text;
    state.confirmAction = action;
    openModal(el.confirmModal);
}

async function deleteDevice() {
    if (state.selectedDeviceId == null) return;

    const deviceId = state.selectedDeviceId;

    try {
        const response = await fetch(`/api/admin/devices/${deviceId}`, {
            method: "DELETE",
            headers: {
                "Accept": "application/json"
            }
        });

        const data = await response.json().catch(() => null);

        if (!response.ok) {
            throw new Error(data?.detail || `HTTP ${response.status}`);
        }

        closeTopModal(); // confirm
        closeTopModal(); // device modal

        state.selectedDeviceId = null;

        await loadBootstrap();
        renderUserDevicesStrip(state.devices)
    } catch (error) {
        alert(`Не удалось удалить устройство: ${error.message}`);
    }
}

function openPaymentHistoryModal(userId) {
    const user = state.users.find(x => x.id === Number(userId));
    if (!user) return;

    document.getElementById("payment-history-user-id").textContent = `Платежи пользователя ID ${user.id}`;
    renderUserPaymentsStrip(user.payments || []);
    openModal(el.paymentHistoryModal);
}

function openPaymentModal(paymentId) {
    const payment = state.payments.find(x => x.id === Number(paymentId));
    if (!payment) return;

    document.getElementById("payment-modal-id").textContent = `ID ${payment.id}`;
    document.getElementById("payment-comment").value = payment.desc || "";
    document.getElementById("payment-date").value = formatDate(payment.date);
    document.getElementById("payment-amount").value = payment.amount ?? 0;

    openModal(el.paymentModal);
}

function updateDeviceCreateKeyMode() {
    const checkbox = document.getElementById("device-create-has-own-key");
    const field = document.getElementById("device-create-public-key-field");

    field.classList.toggle("hidden", !checkbox.checked);
}

function updateDeviceCreateIpPreview() {
    const suffixInput = document.getElementById("device-create-ip-suffix");
    const previewWrap = document.getElementById("device-create-ip-preview-field");
    const previewInput = document.getElementById("device-create-ip-preview");

    const suffix = Number(suffixInput.value || 0);

    if (!suffix || suffix < 1 || suffix > 255) {
        previewWrap.classList.add("hidden");
        previewInput.value = "";
        return;
    }

    previewWrap.classList.remove("hidden");
    previewInput.value = `10.88.88.${suffix}`;
}

async function createUser(data) {
}

async function createDevice() {
    const ownerId = Number(document.getElementById("device-create-owner-id").value || 0);
    const name = document.getElementById("device-create-name").value.trim() || "Устройство";
    const ipSuffix = Number(document.getElementById("device-create-ip-suffix").value || 0);
    const hasOwnKey = document.getElementById("device-create-has-own-key").checked;
    const publicKey = document.getElementById("device-create-public-key").value.trim();

    if (!ownerId) {
        alert("Не удалось определить владельца устройства");
        return;
    }

    if (!Number.isInteger(ipSuffix) || ipSuffix < 0 || ipSuffix > 255) {
        alert("Последнее число IP должно быть от 0 до 255");
        return;
    }

    if (hasOwnKey && !publicKey) {
        alert("Укажи публичный ключ или убери галочку");
        return;
    }

    const payload = {
        name,
        ip_suffix: ipSuffix,
        public_key: hasOwnKey ? publicKey : null
    };

    try {
        await apiSendJson(`/api/admin/users/${ownerId}/devices`, "POST", payload);
        closeTopModal();
        await loadBootstrap();
        renderUserDevicesStrip(state.devices);
        
    } catch (error) {
        alert(`Не удалось создать устройство: ${error.message}`);
    }
}

async function loadBootstrap() {
    const data = await apiGetJson("/api/admin/bootstrap");

    state.meta = data.meta || {
        roles: [],
        user_statuses: [],
        device_statuses: []
    };

    state.users = Array.isArray(data.users) ? data.users : [];
    state.devices = Array.isArray(data.devices) ? data.devices : [];
    state.payments = Array.isArray(data.payments) ? data.payments : [];

    updateStats();
    renderUsers();
    renderDevices();
    renderPayments();
}

el.tabs.forEach(tab => {
    tab.addEventListener("click", () => {
        showPanel(tab.dataset.tab);
    });
});

el.modalOverlay.addEventListener("click", () => {
    closeTopModal();
});

document.querySelectorAll("[data-close-top]").forEach(btn => {
    btn.addEventListener("click", () => {
        closeTopModal();
    });
});

document.getElementById("confirm-no-btn").addEventListener("click", () => {
    state.confirmAction = null;
    closeTopModal();
});

document.getElementById("confirm-yes-btn").addEventListener("click", async () => {
    if (!state.confirmAction) {
        closeTopModal();
        return;
    }

    const action = state.confirmAction;
    state.confirmAction = null;
    await action();
});

document.getElementById("user-payments-history-btn").addEventListener("click", () => {
    if (state.selectedUserId == null) return;
    openPaymentHistoryModal(state.selectedUserId);
});

document.getElementById("user-add-device-btn").addEventListener("click", () => {
    if (state.selectedUserId == null) return;
    openCreateDeviceModal(state.selectedUserId);
});

document.getElementById("device-create-has-own-key").addEventListener("change", () => {
    updateDeviceCreateKeyMode();
});

document.getElementById("device-create-ip-suffix").addEventListener("input", () => {
    updateDeviceCreateIpPreview();
});

document.getElementById("create-device-btn").addEventListener("click", async () => {
    await createDevice();
});

document.getElementById("delete-device-btn").addEventListener("click", () => {
    if (state.selectedDeviceId == null) return;

    openConfirmModal("Удалить устройство?", async () => {
        await deleteDevice();
    });
});

el.refreshBtn.addEventListener("click", async () => {
    try {
        await loadBootstrap();
    } catch (error) {
        alert(`Не удалось обновить данные: ${error.message}`);
    }
});

el.addBtn.addEventListener("click", () => {
    if (el.addBtn.classList.contains("btn-disabled")) return;

    if (state.activeTab === "users") {
        openCreateUserModal();
        return;
    }
});

el.createUserBtn.addEventListener("click", async () => {

    const data = {
        name: el.createUserName.value.trim(),
        role: el.createUserRole.value,
        balance: Number(el.createUserBalance.value || 0),
        monthly_fee: Number(el.createUserFee.value || 0),
        speed: Number(el.createUserSpeed.value || 0)
    };

    console.log(data);

    closeTopModal();

    await loadBootstrap();
    renderUsers();
})

document.addEventListener("DOMContentLoaded", async () => {
    showPanel("users");
    updateAddButtonState();

    try {
        await loadBootstrap();
    } catch (error) {
        alert(`Не удалось загрузить админку: ${error.message}`);
        console.error(error);
    }
});