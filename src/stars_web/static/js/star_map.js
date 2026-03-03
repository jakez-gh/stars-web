/**
 * Stars! Star Map — interactive canvas renderer.
 *
 * Fetches game state from /api/game-state, renders planets and fleets
 * on an HTML5 canvas with pan, zoom, click-to-select, and hover tooltips.
 */

(function () {
    "use strict";

    // --- Constants ---
    const PLANET_RADIUS = 4;
    const HOMEWORLD_RADIUS = 6;
    const FLEET_SIZE = 5;
    const NAME_OFFSET_Y = -10;
    const CLICK_TOLERANCE = 12;
    const MIN_ZOOM = 0.3;
    const MAX_ZOOM = 5.0;
    const ZOOM_STEP = 1.15;

    // Colors
    const COLOR_OWNED = "#44cc44";
    const COLOR_UNOWNED = "#555";
    const COLOR_HOMEWORLD = "#ffcc00";
    const COLOR_FLEET = "#ff6644";
    const COLOR_STARBASE = "#00ccff";
    const COLOR_NAME = "#aaa";
    const COLOR_NAME_OWNED = "#ccc";
    const COLOR_GRID = "#111";
    const COLOR_SELECTED = "#ffffff";

    // --- State ---
    let gameState = null;
    let prevTurn = null;  // track turn changes for "Turn N loaded" banner
    let selectedPlanet = null;
    let hoveredPlanet = null;
    let selectedFleet = null;
    let hoveredFleet = null;

    // View transform
    let viewX = 0;
    let viewY = 0;
    let zoom = 1.0;

    // Expose state for E2E tests
    Object.defineProperty(window, "_gameState", { get: () => gameState, configurable: true });
    Object.defineProperty(window, "_viewX",     { get: () => viewX,     configurable: true });
    Object.defineProperty(window, "_viewY",     { get: () => viewY,     configurable: true });
    Object.defineProperty(window, "_zoom",      { get: () => zoom,      configurable: true });
    Object.defineProperty(window, "_prevTurn",  { get: () => prevTurn, set: (v) => { prevTurn = v; }, configurable: true });    // Pan state
    let isPanning = false;
    let panStartX = 0;
    let panStartY = 0;
    let panViewStartX = 0;
    let panViewStartY = 0;

    // --- DOM ---
    const canvas = document.getElementById("star-map");
    const ctx = canvas.getContext("2d");
    const container = document.getElementById("map-container");
    const detailPanel = document.getElementById("detail-panel");
    const detailName = document.getElementById("detail-name");
    const detailBody = document.getElementById("detail-body");
    const closeDetail = document.getElementById("close-detail");
    const gameTitle = document.getElementById("game-title");
    const gameInfo = document.getElementById("game-info");
    const showNamesCheck = document.getElementById("show-names");
    const showFleetsCheck = document.getElementById("show-fleets");
    const showUnownedCheck = document.getElementById("show-unowned");
    const submitTurnBtn = document.getElementById("submit-turn-btn");
    const hostLogPanel = document.getElementById("host-log-panel");
    const hostLogTitle = document.getElementById("host-log-title");
    const hostLogBody = document.getElementById("host-log-body");
    const hostLogClose = document.getElementById("host-log-close");

    // Tooltip element
    const tooltip = document.createElement("div");
    tooltip.id = "tooltip";
    document.getElementById("app").appendChild(tooltip);

    // Toast element
    const toast = document.createElement("div");
    toast.id = "toast";
    document.getElementById("app").appendChild(toast);

    function showToast(message, isError = false) {
        toast.textContent = message;
        toast.className = isError ? "error" : "";
        toast.classList.add("visible");
        clearTimeout(toast._timer);
        toast._timer = setTimeout(() => toast.classList.remove("visible"), 2500);
    }

    function showHostLog(status, title, log) {
        hostLogPanel.className = status === "ok" ? "ok" : "error";
        hostLogTitle.textContent = title;
        hostLogBody.textContent = log || "(no output)";
        hostLogPanel.classList.remove("hidden");
    }

    hostLogClose.addEventListener("click", () => {
        hostLogPanel.classList.add("hidden");
    });

    submitTurnBtn.addEventListener("click", async () => {
        const origText = submitTurnBtn.textContent;
        submitTurnBtn.disabled = true;
        submitTurnBtn.textContent = "Submitting…";
        try {
            const resp = await fetch("/game/submit-turn", { method: "POST" });
            const data = await resp.json();
            if (data.status === "ok") {
                showHostLog("ok", "Turn submitted — host run complete", data.log);
                await loadGameState();
            } else {
                showHostLog("error", "Host run failed", data.log);
            }
        } catch (err) {
            showHostLog("error", "Submit failed", err.message);
        }
        submitTurnBtn.textContent = origText;
        // Button re-enabled by loadGameState() toggling has_pending_orders
    });

    // --- Coordinate transforms ---

    function worldToScreen(wx, wy) {
        return {
            x: (wx - viewX) * zoom + canvas.width / 2,
            y: -(wy - viewY) * zoom + canvas.height / 2,
        };
    }

    function screenToWorld(sx, sy) {
        return {
            x: (sx - canvas.width / 2) / zoom + viewX,
            y: -(sy - canvas.height / 2) / zoom + viewY,
        };
    }

    // --- Resize ---

    function resize() {
        const rect = container.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;
        render();
    }

    // --- Rendering ---

    function render() {
        if (!gameState) return;

        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        drawGrid();
        drawPlanets();
        if (showFleetsCheck.checked) drawFleets();
    }

    function drawGrid() {
        // Light grid lines at 100-unit intervals
        ctx.strokeStyle = COLOR_GRID;
        ctx.lineWidth = 1;

        const topLeft = screenToWorld(0, 0);
        const bottomRight = screenToWorld(canvas.width, canvas.height);

        const gridStep = 100;
        const startX = Math.floor(topLeft.x / gridStep) * gridStep;
        // After Y-inversion topLeft.y > bottomRight.y, so clamp both ends
        const minWorldY = Math.min(topLeft.y, bottomRight.y);
        const maxWorldY = Math.max(topLeft.y, bottomRight.y);
        const startY = Math.floor(minWorldY / gridStep) * gridStep;

        ctx.beginPath();
        for (let gx = startX; gx <= bottomRight.x; gx += gridStep) {
            const sx = worldToScreen(gx, 0).x;
            ctx.moveTo(sx, 0);
            ctx.lineTo(sx, canvas.height);
        }
        for (let gy = startY; gy <= maxWorldY; gy += gridStep) {
            const sy = worldToScreen(0, gy).y;
            ctx.moveTo(0, sy);
            ctx.lineTo(canvas.width, sy);
        }
        ctx.stroke();
    }

    function drawPlanets() {
        const showNames = showNamesCheck.checked;
        const showUnowned = showUnownedCheck.checked;

        for (const planet of gameState.planets) {
            if (!showUnowned && planet.owner < 0) continue;

            const { x: sx, y: sy } = worldToScreen(planet.x, planet.y);

            // Skip if off-screen
            if (sx < -50 || sx > canvas.width + 50 || sy < -50 || sy > canvas.height + 50) continue;

            const isSelected = selectedPlanet && selectedPlanet.id === planet.id;
            const isHovered = hoveredPlanet && hoveredPlanet.id === planet.id;

            // Planet dot
            let color = COLOR_UNOWNED;
            let radius = PLANET_RADIUS;

            if (planet.is_homeworld) {
                color = COLOR_HOMEWORLD;
                radius = HOMEWORLD_RADIUS;
            } else if (planet.owner >= 0) {
                color = COLOR_OWNED;
            }

            // Starbase indicator — ring around the planet
            if (planet.has_starbase) {
                ctx.beginPath();
                ctx.arc(sx, sy, radius + 3, 0, Math.PI * 2);
                ctx.strokeStyle = COLOR_STARBASE;
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }

            // Selection ring
            if (isSelected) {
                ctx.beginPath();
                ctx.arc(sx, sy, radius + 6, 0, Math.PI * 2);
                ctx.strokeStyle = COLOR_SELECTED;
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }

            // Planet circle
            ctx.beginPath();
            ctx.arc(sx, sy, radius, 0, Math.PI * 2);
            ctx.fillStyle = color;
            if (isHovered) ctx.fillStyle = lighten(color, 0.3);
            ctx.fill();

            // Planet name
            if (showNames && zoom >= 0.6) {
                ctx.font = isSelected ? "bold 11px sans-serif" : "11px sans-serif";
                ctx.fillStyle = planet.owner >= 0 ? COLOR_NAME_OWNED : COLOR_NAME;
                ctx.textAlign = "center";
                ctx.fillText(planet.name, sx, sy + NAME_OFFSET_Y);
            }
        }
    }

    function drawFleets() {
        for (const fleet of gameState.fleets) {
            const { x: sx, y: sy } = worldToScreen(fleet.x, fleet.y);

            if (sx < -20 || sx > canvas.width + 20 || sy < -20 || sy > canvas.height + 20) continue;

            const isSelected = selectedFleet && selectedFleet.id === fleet.id;
            const isHovered = hoveredFleet && hoveredFleet.id === fleet.id;

            // Selection ring
            if (isSelected) {
                ctx.beginPath();
                ctx.arc(sx, sy, FLEET_SIZE + 5, 0, Math.PI * 2);
                ctx.strokeStyle = COLOR_SELECTED;
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }

            // Fleet triangle
            ctx.beginPath();
            ctx.moveTo(sx, sy - FLEET_SIZE);
            ctx.lineTo(sx - FLEET_SIZE, sy + FLEET_SIZE);
            ctx.lineTo(sx + FLEET_SIZE, sy + FLEET_SIZE);
            ctx.closePath();
            ctx.fillStyle = (isHovered || isSelected) ? lighten(COLOR_FLEET, 0.4) : COLOR_FLEET;
            ctx.fill();
        }
    }

    // --- Interaction ---

    function findPlanetAt(sx, sy) {
        const world = screenToWorld(sx, sy);
        let closest = null;
        let closestDist = Infinity;

        for (const planet of gameState.planets) {
            if (!showUnownedCheck.checked && planet.owner < 0) continue;
            const dx = planet.x - world.x;
            const dy = planet.y - world.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < closestDist) {
                closestDist = dist;
                closest = planet;
            }
        }

        // Check if within click tolerance (in screen pixels)
        if (closest) {
            const screenPos = worldToScreen(closest.x, closest.y);
            const sdx = screenPos.x - sx;
            const sdy = screenPos.y - sy;
            if (Math.sqrt(sdx * sdx + sdy * sdy) <= CLICK_TOLERANCE) {
                return closest;
            }
        }
        return null;
    }

    function findFleetAt(sx, sy) {
        if (!gameState || !showFleetsCheck.checked) return null;
        for (const fleet of gameState.fleets) {
            const { x: fx, y: fy } = worldToScreen(fleet.x, fleet.y);
            const dx = fx - sx;
            const dy = fy - sy;
            if (Math.sqrt(dx * dx + dy * dy) <= CLICK_TOLERANCE) {
                return fleet;
            }
        }
        return null;
    }

    function showDetail(planet) {
        selectedPlanet = planet;
        selectedFleet = null;
        detailName.textContent = planet.name;

        let html = "";

        // Position
        html += `<div class="row"><span class="label">Position</span><span class="value">(${planet.x}, ${planet.y})</span></div>`;

        // Owner
        if (planet.owner >= 0) {
            html += `<div class="row"><span class="label">Owner</span><span class="value">Player ${planet.owner + 1}</span></div>`;
        } else {
            html += `<div class="row"><span class="label">Owner</span><span class="value">Unowned</span></div>`;
        }

        // Flags
        const flags = [];
        if (planet.is_homeworld) flags.push("Homeworld");
        if (planet.has_starbase) flags.push("Starbase");
        if (flags.length > 0) {
            html += `<div class="row"><span class="label">Status</span><span class="value">${flags.join(", ")}</span></div>`;
        }

        // Population
        if (planet.population > 0) {
            html += `<div class="section-title">Population</div>`;
            html += `<div class="row"><span class="label">People</span><span class="value">${planet.population.toLocaleString()}</span></div>`;
        }

        // Installations
        if (planet.mines > 0 || planet.factories > 0 || planet.defenses > 0) {
            html += `<div class="section-title">Installations</div>`;
            html += `<div class="row"><span class="label">Mines</span><span class="value">${planet.mines}</span></div>`;
            html += `<div class="row"><span class="label">Factories</span><span class="value">${planet.factories}</span></div>`;
            html += `<div class="row"><span class="label">Defenses</span><span class="value">${planet.defenses}</span></div>`;
        }

        // Surface minerals
        if (planet.ironium > 0 || planet.boranium > 0 || planet.germanium > 0) {
            html += `<div class="section-title">Surface Minerals</div>`;
            html += mineralBar("Iron", "iron", planet.ironium, 5000);
            html += mineralBar("Bor", "bor", planet.boranium, 5000);
            html += mineralBar("Germ", "germ", planet.germanium, 5000);
        }

        // Mineral concentrations
        if (planet.ironium_conc > 0 || planet.boranium_conc > 0 || planet.germanium_conc > 0) {
            html += `<div class="section-title">Concentrations</div>`;
            html += mineralBar("Iron", "iron conc-bar", planet.ironium_conc, 120);
            html += mineralBar("Bor", "bor conc-bar", planet.boranium_conc, 120);
            html += mineralBar("Germ", "germ conc-bar", planet.germanium_conc, 120);
        }

        // Environment
        if (planet.gravity > 0 || planet.temperature > 0 || planet.radiation > 0) {
            html += `<div class="section-title">Environment</div>`;
            html += `<div class="row"><span class="label">Gravity</span><span class="value">${planet.gravity}</span></div>`;
            html += `<div class="row"><span class="label">Temp</span><span class="value">${planet.temperature}</span></div>`;
            html += `<div class="row"><span class="label">Rad</span><span class="value">${planet.radiation}</span></div>`;
        }

        // Production queue
        if (planet.production_queue && planet.production_queue.length > 0) {
            html += `<div class="section-title">Production Queue</div>`;
            planet.production_queue.forEach((item, i) => {
                const pct = item.complete_percent > 0 ? ` (${item.complete_percent}%)` : "";
                const qty = item.quantity ?? item.count ?? 0;
                const rmBtn =
                    planet.owner >= 0
                        ? ` <button class="q-rm-btn" data-rm-idx="${i}" title="Remove">×</button>`
                        : "";
                html += `<div class="row queue-row"><span class="label">${i + 1}.</span><span class="value">${qty}\u00d7 ${item.name}${pct}${rmBtn}</span></div>`;
            });
        } else if (planet.owner >= 0) {
            html += `<div class="section-title">Production Queue</div>`;
            html += `<div class="row"><span class="label" style="color:#888">Queue is empty</span></div>`;
        }

        // Add to Queue form (owned planets only)
        if (planet.owner >= 0) {
            html += `<div class="section-title">Add to Queue</div>`;
            html += `<div class="queue-form">`;
            html += `<select id="q-item">`;
            [
                { id: 7, name: "Factory" },
                { id: 8, name: "Mine" },
                { id: 9, name: "Defense" },
                { id: 3, name: "Auto Alchemy" },
            ].forEach((item) => {
                html += `<option value="${item.id}">${item.name}</option>`;
            });
            (gameState.designs || []).forEach((d) => {
                html += `<option value="d${d.id}">${d.name} (${d.hull_name})</option>`;
            });
            html += `</select>`;
            html += `<label class="wp-warp-label">Qty <input type="number" id="q-count" value="1" min="1" class="q-count-input"></label>`;
            html += `<button id="q-add-btn" class="wp-add-btn">Add</button>`;
            html += `</div>`;
        }

        detailBody.innerHTML = html;

        // Wire remove-from-queue buttons
        if (planet.owner >= 0) {
            detailBody.querySelectorAll("[data-rm-idx]").forEach((btn) => {
                btn.addEventListener("click", async () => {
                    const idx = parseInt(btn.dataset.rmIdx, 10);
                    const newQueue = (planet.production_queue || [])
                        .filter((_, j) => j !== idx)
                        .map((qi) => ({
                            name: qi.name,
                            quantity: qi.quantity ?? qi.count ?? 1,
                        }));
                    try {
                        const resp = await fetch(`/api/planet/${planet.id}/production`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(newQueue),
                        });
                        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                        planet.production_queue = await resp.json();
                        showDetail(planet);
                        showToast("Removed from queue");
                    } catch (err) {
                        showToast("Error: " + err.message, true);
                    }
                });
            });
        }

        // Wire Add to Queue button
        if (planet.owner >= 0) {
            document.getElementById("q-add-btn").addEventListener("click", async () => {
                const itemSel = document.getElementById("q-item");
                const qty = parseInt(document.getElementById("q-count").value, 10) || 1;
                const name = itemSel.selectedOptions[0].textContent;
                const newQueue = [
                    ...(planet.production_queue || []).map((qi) => ({
                        name: qi.name,
                        quantity: qi.quantity ?? qi.count ?? 1,
                    })),
                    { name, quantity: qty },
                ];
                try {
                    const resp = await fetch(`/api/planet/${planet.id}/production`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(newQueue),
                    });
                    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                    planet.production_queue = await resp.json();
                    showDetail(planet);
                    showToast("Added to queue");
                } catch (err) {
                    showToast("Error: " + err.message, true);
                }
            });
        }

        detailPanel.classList.remove("hidden");
        render();
    }

    function hideDetail() {
        selectedPlanet = null;
        selectedFleet = null;
        detailPanel.classList.add("hidden");
        render();
    }

    function mineralBar(label, cssClass, value, maxVal) {
        const pct = Math.min(100, (value / maxVal) * 100);
        const baseClass = cssClass.split(" ")[0];
        return `
            <div class="mineral-bar-container">
                <span class="mineral-bar-label">${label}</span>
                <div class="mineral-bar-track">
                    <div class="mineral-bar-fill ${baseClass}" style="width:${pct}%"></div>
                </div>
                <span class="mineral-bar-value">${value}</span>
            </div>`;
    }

    function showFleetDetail(fleet) {
        selectedFleet = fleet;
        selectedPlanet = null;
        detailName.textContent = fleet.name;

        let html = "";
        html += `<div class="row"><span class="label">Position</span><span class="value">(${fleet.x}, ${fleet.y})</span></div>`;
        html += `<div class="row"><span class="label">Owner</span><span class="value">Player ${fleet.owner + 1}</span></div>`;
        html += `<div class="row"><span class="label">Ships</span><span class="value">${fleet.ship_count}</span></div>`;

        if (fleet.waypoints && fleet.waypoints.length > 0) {
            html += `<div class="section-title">Waypoints</div>`;
            fleet.waypoints.forEach((wp, i) => {
                const task = wp.task && wp.task !== "None" ? ` — ${wp.task}` : "";
                html += `<div class="row"><span class="label">WP ${i + 1}</span><span class="value">(${wp.x}, ${wp.y}) Warp ${wp.warp}${task}</span></div>`;
            });
        }

        html += `<div class="section-title">Add Waypoint</div>`;
        html += `<div class="wp-form">`;
        html += `<select id="wp-dest"><option value="">— Deep Space —</option></select>`;
        html += `<div class="wp-coords">`;
        html += `<label>X <input type="number" id="wp-x" placeholder="0"></label>`;
        html += `<label>Y <input type="number" id="wp-y" placeholder="0"></label>`;
        html += `</div>`;
        html += `<label class="wp-warp-label">Warp <select id="wp-warp">${[1,2,3,4,5,6,7,8,9].map(w => `<option value="${w}"${w === 5 ? " selected" : ""}>${w}</option>`).join("")}</select></label>`;
        html += `<button id="wp-add-btn" class="wp-add-btn">Add Waypoint</button>`;
        html += `</div>`;

        detailBody.innerHTML = html;

        // Populate planet dropdown
        const dest = document.getElementById("wp-dest");
        const xIn  = document.getElementById("wp-x");
        const yIn  = document.getElementById("wp-y");

        gameState.planets
            .filter(p => p.owner >= 0)
            .sort((a, b) => a.name.localeCompare(b.name))
            .forEach(p => {
                const opt = document.createElement("option");
                opt.value = String(p.id);
                opt.textContent = p.name;
                opt.dataset.x = p.x;
                opt.dataset.y = p.y;
                dest.appendChild(opt);
            });

        dest.addEventListener("change", () => {
            const opt = dest.selectedOptions[0];
            if (opt && opt.dataset.x) {
                xIn.value = opt.dataset.x;
                yIn.value = opt.dataset.y;
            } else {
                xIn.value = "";
                yIn.value = "";
            }
        });

        // Add button — wire to POST /api/fleet/{id}/waypoints
        document.getElementById("wp-add-btn").addEventListener("click", async () => {
            const xVal = parseInt(document.getElementById("wp-x").value, 10);
            const yVal = parseInt(document.getElementById("wp-y").value, 10);
            const warpVal = parseInt(document.getElementById("wp-warp").value, 10);

            if (isNaN(xVal) || isNaN(yVal)) {
                showToast("Enter X and Y coordinates", true);
                return;
            }

            const newWps = [
                ...(fleet.waypoints || []).map((wp) => ({
                    x: wp.x,
                    y: wp.y,
                    warp: wp.warp,
                    task: wp.task,
                })),
                { x: xVal, y: yVal, warp: warpVal, task: "None" },
            ];

            try {
                const resp = await fetch(`/api/fleet/${fleet.id}/waypoints`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ waypoints: newWps }),
                });
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                const data = await resp.json();
                fleet.waypoints = data.waypoints;
                showFleetDetail(fleet);
                showToast("Waypoint added");
            } catch (err) {
                showToast("Error: " + err.message, true);
            }
        });

        detailPanel.classList.remove("hidden");
        render();
    }

    // --- Color utility ---

    function lighten(hex, amount) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        const nr = Math.min(255, Math.round(r + (255 - r) * amount));
        const ng = Math.min(255, Math.round(g + (255 - g) * amount));
        const nb = Math.min(255, Math.round(b + (255 - b) * amount));
        return `#${nr.toString(16).padStart(2, "0")}${ng.toString(16).padStart(2, "0")}${nb.toString(16).padStart(2, "0")}`;
    }

    // --- Event handlers ---

    canvas.addEventListener("mousedown", (e) => {
        isPanning = true;
        panStartX = e.clientX;
        panStartY = e.clientY;
        panViewStartX = viewX;
        panViewStartY = viewY;
        container.classList.add("grabbing");
    });

    canvas.addEventListener("mousemove", (e) => {
        if (isPanning) {
            const dx = e.clientX - panStartX;
            const dy = e.clientY - panStartY;
            viewX = panViewStartX - dx / zoom;
            viewY = panViewStartY - dy / zoom;
            render();
            return;
        }

        // Hover
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const planet = findPlanetAt(mx, my);
        const fleet = findFleetAt(mx, my);

        if (planet !== hoveredPlanet || fleet !== hoveredFleet) {
            hoveredPlanet = planet;
            hoveredFleet = fleet;
            render();
        }

        const hoverLabel = fleet ? fleet.name : (planet ? planet.name : null);
        if (hoverLabel) {
            tooltip.textContent = hoverLabel;
            tooltip.style.display = "block";
            tooltip.style.left = (e.clientX - rect.left + 14) + "px";
            tooltip.style.top = (e.clientY - rect.top - 8) + "px";
            canvas.style.cursor = "pointer";
        } else {
            tooltip.style.display = "none";
            canvas.style.cursor = isPanning ? "grabbing" : "grab";
        }
    });

    canvas.addEventListener("mouseup", (e) => {
        if (isPanning) {
            const dx = Math.abs(e.clientX - panStartX);
            const dy = Math.abs(e.clientY - panStartY);

            // Only count as click if minimal movement
            if (dx < 4 && dy < 4) {
                const rect = canvas.getBoundingClientRect();
                const mx = e.clientX - rect.left;
                const my = e.clientY - rect.top;
                const planet = findPlanetAt(mx, my);
                const fleet = findFleetAt(mx, my);
                if (fleet) {
                    showFleetDetail(fleet);
                } else if (planet) {
                    showDetail(planet);
                } else {
                    hideDetail();
                }
            }

            isPanning = false;
            container.classList.remove("grabbing");
        }
    });

    canvas.addEventListener("mouseleave", () => {
        isPanning = false;
        hoveredPlanet = null;
        hoveredFleet = null;
        tooltip.style.display = "none";
        container.classList.remove("grabbing");
        render();
    });

    canvas.addEventListener("wheel", (e) => {
        e.preventDefault();
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;

        // Zoom toward mouse position
        const worldBefore = screenToWorld(mx, my);

        if (e.deltaY < 0) {
            zoom = Math.min(MAX_ZOOM, zoom * ZOOM_STEP);
        } else {
            zoom = Math.max(MIN_ZOOM, zoom / ZOOM_STEP);
        }

        // Adjust view so the world point under the mouse stays put
        const worldAfter = screenToWorld(mx, my);
        viewX -= worldAfter.x - worldBefore.x;
        viewY -= worldAfter.y - worldBefore.y;

        render();
    }, { passive: false });

    closeDetail.addEventListener("click", hideDetail);

    showNamesCheck.addEventListener("change", render);
    showFleetsCheck.addEventListener("change", render);
    showUnownedCheck.addEventListener("change", render);

    window.addEventListener("resize", resize);

    // --- Init ---

    function centerOnPlanets() {
        if (!gameState || gameState.planets.length === 0) return;

        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;

        for (const p of gameState.planets) {
            if (p.x < minX) minX = p.x;
            if (p.x > maxX) maxX = p.x;
            if (p.y < minY) minY = p.y;
            if (p.y > maxY) maxY = p.y;
        }

        viewX = (minX + maxX) / 2;
        viewY = (minY + maxY) / 2;

        // Fit the map with some padding
        const spanX = maxX - minX + 100;
        const spanY = maxY - minY + 100;
        const zoomX = canvas.width / spanX;
        const zoomY = canvas.height / spanY;
        zoom = Math.min(zoomX, zoomY, MAX_ZOOM);
        zoom = Math.max(zoom, MIN_ZOOM);
    }

    async function loadGameState() {
        try {
            const resp = await fetch("/api/game-state");
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            gameState = await resp.json();

            if (gameState.error) {
                gameTitle.textContent = "Error";
                gameInfo.textContent = gameState.error;
                return;
            }

            gameTitle.textContent = gameState.settings.game_name || "Stars!";
            gameInfo.textContent = `Year ${gameState.year} \u2022 Turn ${gameState.turn} | ${gameState.settings.universe_size} | ${gameState.planets.length} planets | ${gameState.fleets.length} fleets`;
            submitTurnBtn.disabled = !gameState.has_pending_orders;

            if (prevTurn !== null && gameState.turn !== prevTurn) {
                showToast(`Turn ${gameState.turn} loaded successfully`);
            }
            prevTurn = gameState.turn;

            resize();
            centerOnPlanets();
            render();
        } catch (err) {
            gameTitle.textContent = "Connection Error";
            gameInfo.textContent = err.message;
            console.error("Failed to load game state:", err);
        }
    }

    loadGameState();
    window._loadGameState = loadGameState;  // exposed for E2E tests

    // --- Changelog modal ---
    const CHANGELOG_POLL_MS = 5000;
    const SEEN_KEY = "seen_changelog_id";

    async function fetchChangelog() {
        try {
            const resp = await fetch("/api/changelog");
            if (!resp.ok) return;
            const data = await resp.json();
            const lastSeen = localStorage.getItem(SEEN_KEY);
            if (data.id && data.id !== lastSeen) {
                showChangelogModal(data);
                await loadGameState();
            }
        } catch (err) {
            console.warn("Changelog poll error:", err);
        }
    }

    function showChangelogModal(data) {
        const modal = document.getElementById("changelog-modal");
        const title = document.getElementById("changelog-title");
        const list = document.getElementById("changelog-list");
        const btn = document.getElementById("changelog-dismiss");

        title.textContent = data.title || "What\u2019s New";
        list.innerHTML = "";
        (data.items || []).forEach(function (item) {
            const li = document.createElement("li");
            li.textContent = item;
            list.appendChild(li);
        });

        modal.classList.remove("hidden");

        btn.onclick = function () {
            localStorage.setItem(SEEN_KEY, data.id);
            modal.classList.add("hidden");
        };
    }

    fetchChangelog();
    setInterval(fetchChangelog, CHANGELOG_POLL_MS);
})();
