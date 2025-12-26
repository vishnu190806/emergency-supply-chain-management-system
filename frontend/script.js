const API_BASE = "http://localhost:8000/api";

const out = document.getElementById("output");
const sizeLabel = document.getElementById("queueSize");
const statDispatched = document.getElementById("statDispatched");

// ENQUEUE
document.getElementById("reqForm").onsubmit = async (e) => {
  e.preventDefault();

  const expiryInput = document.getElementById("expiry_date").value;

  const payload = {
    id: document.getElementById("id").value,
    supply_type: document.getElementById("supply_type").value,
    quantity: parseInt(document.getElementById("quantity").value, 10),
    timestamp: new Date().toISOString(),
    expiry_date: expiryInput ? new Date(expiryInput).toISOString() : null,
    distance_km: document.getElementById("distance_km").value
      ? parseFloat(document.getElementById("distance_km").value)
      : null,
    destination: document.getElementById("destination").value || null,
  };

  const res = await fetch(`${API_BASE}/requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const text = await res.text();
  out.textContent = text;

  if (res.ok) {
    // reset a few fields
    document.getElementById("id").value = "";
    document.getElementById("quantity").value = "10";
    document.getElementById("expiry_date").value = "";
    document.getElementById("distance_km").value = "";
    document.getElementById("destination").value = "";

    await refreshQueue(); // auto‑update queue
  }
};

// DISPATCH NEXT
document.getElementById("dispatchBtn").onclick = async () => {
  const res = await fetch(`${API_BASE}/dispatch`, { method: "POST" });
  const text = await res.text();
  out.textContent = text;

  if (res.ok && statDispatched) {
    const n = parseInt(statDispatched.textContent || "0", 10) || 0;
    statDispatched.textContent = String(n + 1);
  }

  await refreshQueue(); // keep queue in sync
};

// MANUAL REFRESH
document.getElementById("refreshBtn").onclick = async () => {
  await refreshQueue();
};

// INITIAL LOAD
refreshQueue();

// Fetch and render queue table
async function refreshQueue() {
  try {
    const res = await fetch(`${API_BASE}/queue`);
    if (!res.ok) {
      out.textContent = `Queue fetch failed: ${res.status}`;
      return;
    }

    const data = await res.json();

    if (sizeLabel) {
      sizeLabel.textContent = `${data.size} item${
        data.size === 1 ? "" : "s"
      } in queue`;
    }

    const tbody = document.querySelector("#queueTable tbody");
    tbody.innerHTML = "";

    if (!data.items || data.items.length === 0) {
      const row = document.createElement("tr");
      row.innerHTML =
        '<td colspan="5" class="empty">No requests yet. Enqueue one on the left.</td>';
      tbody.appendChild(row);
      return;
    }

    data.items.forEach((item) => {
      const req = item.request || item.req || item;
      const p = item.priority ?? item.computed_priority ?? 0;

      let cls = "priority-low";
      if (p >= 10) cls = "priority-high";
      else if (p >= 6) cls = "priority-medium";

      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${req.id || ""}</td>
        <td>${req.supply_type || ""}</td>
        <td>${req.destination || ""}</td>
        <td><span class="priority-chip ${cls}">${
        p.toFixed ? p.toFixed(1) : p
      }</span></td>
        <td>${
          req.timestamp ? new Date(req.timestamp).toLocaleString() : ""
        }</td>
      `;
      tbody.appendChild(row);
    });
  } catch (err) {
    out.textContent = `Queue fetch error: ${err}`;
  }
}
