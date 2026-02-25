/* ═══════════════════════════════════════════════════════════
   AP Lead Gen Dashboard — Frontend Logic
   ═══════════════════════════════════════════════════════════ */

let currentPage = 1;
let searchTimeout = null;

// ─── Init ──────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    loadStats();
    loadJobs(1);
    loadSources();
    loadConfig();
    loadSchedulerStatus();
    // Refresh stats every 30s
    setInterval(loadStats, 30000);
    setInterval(pollScrapeStatus, 5000);
});


// ─── Stats ─────────────────────────────────────────────────

async function loadStats() {
    try {
        const res = await fetch("/api/stats");
        const data = await res.json();

        animateCounter("statTotalJobs", data.total_jobs || 0);
        animateCounter("statCompanies", data.unique_companies || 0);
        animateCounter("statToday", data.today_count || 0);
        animateCounter("statSources", Object.keys(data.sources || {}).length);

        // Update sources breakdown
        renderSourcesBreakdown(data.sources || {});
    } catch (e) {
        console.error("Failed to load stats:", e);
    }
}

function animateCounter(elementId, target) {
    const el = document.getElementById(elementId);
    const current = parseInt(el.textContent) || 0;
    if (current === target) return;

    const duration = 600;
    const start = performance.now();

    function step(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        el.textContent = Math.round(current + (target - current) * eased).toLocaleString();
        if (progress < 1) requestAnimationFrame(step);
    }

    requestAnimationFrame(step);
}

function renderSourcesBreakdown(sources) {
    const container = document.getElementById("sourcesBreakdown");
    const total = Object.values(sources).reduce((a, b) => a + b, 0) || 1;

    if (Object.keys(sources).length === 0) {
        container.innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div><h3>No data yet</h3><p>Run a scrape to see source breakdown</p></div>`;
        return;
    }

    container.innerHTML = Object.entries(sources)
        .sort((a, b) => b[1] - a[1])
        .map(([source, count]) => `
            <div class="source-item">
                <div class="bar-wrap">
                    <div class="bar-label">
                        <span>${escapeHtml(source)}</span>
                        <span>${count}</span>
                    </div>
                    <div class="bar">
                        <div class="bar-fill" style="width: ${(count / total * 100).toFixed(1)}%"></div>
                    </div>
                </div>
            </div>
        `).join("");
}


// ─── Jobs Table ────────────────────────────────────────────

async function loadJobs(page = 1) {
    currentPage = page;
    const search = document.getElementById("searchInput").value;
    const source = document.getElementById("sourceFilter").value;

    const params = new URLSearchParams({ page, per_page: 25, search, source });

    try {
        const res = await fetch(`/api/jobs?${params}`);
        const data = await res.json();
        renderJobs(data);
    } catch (e) {
        console.error("Failed to load jobs:", e);
    }
}

function renderJobs(data) {
    const tbody = document.getElementById("jobsTableBody");
    const info = document.getElementById("paginationInfo");
    const jobCount = document.getElementById("jobCount");

    if (!data.jobs || data.jobs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><div class="empty-icon">📭</div><h3>No jobs found</h3><p>Run a scrape to populate data</p></div></td></tr>`;
        info.textContent = "0 results";
        jobCount.textContent = "";
        return;
    }

    jobCount.textContent = `${data.total.toLocaleString()} total`;

    tbody.innerHTML = data.jobs.map(job => {
        const sourceClass = getSourceClass(job.source);
        const date = job.seen_at ? new Date(job.seen_at).toLocaleDateString() : "—";
        return `
            <tr>
                <td class="company">${escapeHtml(job.company || "—")}</td>
                <td>${escapeHtml(job.title || "—")}</td>
                <td><span class="source-badge ${sourceClass}">${escapeHtml(job.source || "—")}</span></td>
                <td>${date}</td>
                <td>${job.url ? `<a href="${escapeHtml(job.url)}" target="_blank">View ↗</a>` : "—"}</td>
            </tr>
        `;
    }).join("");

    const start = (data.page - 1) * data.per_page + 1;
    const end = Math.min(data.page * data.per_page, data.total);
    info.textContent = `${start}–${end} of ${data.total.toLocaleString()}`;

    renderPagination(data.page, data.pages);
}

function renderPagination(current, total) {
    const container = document.getElementById("pagination");
    if (total <= 1) { container.innerHTML = ""; return; }

    let html = `<button ${current <= 1 ? "disabled" : ""} onclick="loadJobs(${current - 1})">‹</button>`;

    const range = getPageRange(current, total);
    for (const p of range) {
        if (p === "...") {
            html += `<button disabled>…</button>`;
        } else {
            html += `<button class="${p === current ? 'active' : ''}" onclick="loadJobs(${p})">${p}</button>`;
        }
    }

    html += `<button ${current >= total ? "disabled" : ""} onclick="loadJobs(${current + 1})">›</button>`;
    container.innerHTML = html;
}

function getPageRange(current, total) {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    if (current <= 3) return [1, 2, 3, 4, "...", total];
    if (current >= total - 2) return [1, "...", total - 3, total - 2, total - 1, total];
    return [1, "...", current - 1, current, current + 1, "...", total];
}

function debounceSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => loadJobs(1), 300);
}

function getSourceClass(source) {
    if (!source) return "default";
    const s = source.toLowerCase();
    if (s.includes("indeed")) return "indeed";
    if (s.includes("linkedin")) return "linkedin";
    if (s.includes("zip")) return "ziprecruiter";
    if (s.includes("monster")) return "monster";
    return "default";
}


// ─── Sources Filter ────────────────────────────────────────

async function loadSources() {
    try {
        const res = await fetch("/api/sources");
        const data = await res.json();
        const select = document.getElementById("sourceFilter");
        (data.sources || []).forEach(source => {
            const opt = document.createElement("option");
            opt.value = source;
            opt.textContent = source;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error("Failed to load sources:", e);
    }
}


// ─── Config ────────────────────────────────────────────────

async function loadConfig() {
    try {
        const res = await fetch("/api/config");
        const data = await res.json();

        document.getElementById("configPanel").innerHTML = `
            <div class="config-item">
                <span class="config-label">SerpAPI</span>
                <span class="config-value ${data.serpapi_configured ? 'success' : 'warning'}">
                    ${data.serpapi_configured ? '✅ Active' : '⚠ Not Set'}
                </span>
            </div>
            <div class="config-item">
                <span class="config-label">RapidAPI</span>
                <span class="config-value ${data.rapidapi_configured ? 'success' : 'warning'}">
                    ${data.rapidapi_configured ? '✅ Active' : '⚠ Not Set'}
                </span>
            </div>
            <div class="config-item">
                <span class="config-label">Keywords</span>
                <span class="config-value">${data.keywords ? data.keywords.length : 0}</span>
            </div>
            <div class="config-item">
                <span class="config-label">Locations</span>
                <span class="config-value">${data.locations_count || 0}</span>
            </div>
            ${data.sheet_url ? `
            <div style="margin-top: 12px;">
                <a href="${data.sheet_url}" target="_blank" class="btn btn-secondary" style="width: 100%; justify-content: center;">
                    📊 Open Google Sheet
                </a>
            </div>` : ''}
        `;

        // Set the Sheet link in header
        if (data.sheet_url) {
            document.getElementById("sheetLink").href = data.sheet_url;
        }
    } catch (e) {
        console.error("Failed to load config:", e);
    }
}


// ─── Scrape Trigger ────────────────────────────────────────

async function triggerScrape() {
    const tiers = [];
    if (document.getElementById("tier1").checked) tiers.push(1);
    if (document.getElementById("tier2").checked) tiers.push(2);
    if (document.getElementById("tier3").checked) tiers.push(3);

    if (tiers.length === 0) {
        showToast("Select at least one tier", "error");
        return;
    }

    const dryRun = document.getElementById("dryRun").checked;

    const btnMain = document.getElementById("btnScrapeNow");
    const btnManual = document.getElementById("btnRunManual");
    btnMain.disabled = true;
    btnManual.disabled = true;
    btnMain.innerHTML = '<span class="loading-spinner"></span> Running...';
    btnManual.innerHTML = '<span class="loading-spinner"></span> Running...';

    const logEl = document.getElementById("scrapeLog");
    logEl.style.display = "block";
    logEl.textContent = "Starting scrape...\n";

    try {
        const res = await fetch("/api/scrape", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tier: tiers, dry_run: dryRun }),
        });
        const data = await res.json();

        if (res.ok) {
            showToast("Scrape started! Monitoring progress...", "info");
            logEl.textContent += `Command: ${data.command}\n\nWaiting for output...\n`;
            pollScrapeStatus();
        } else {
            showToast(data.error || "Failed to start scrape", "error");
            resetScrapeButtons();
        }
    } catch (e) {
        showToast("Connection error: " + e.message, "error");
        resetScrapeButtons();
    }
}

async function pollScrapeStatus() {
    try {
        const res = await fetch("/api/scrape/status");
        const data = await res.json();

        const logEl = document.getElementById("scrapeLog");
        if (data.log_output) {
            logEl.style.display = "block";
            logEl.textContent = data.log_output;
            logEl.scrollTop = logEl.scrollHeight;
        }

        if (data.running) {
            // Update status indicator
            document.getElementById("systemStatus").innerHTML = `
                <span class="loading-spinner"></span>
                <span>Scraping...</span>
            `;
        } else if (data.last_result) {
            document.getElementById("systemStatus").innerHTML = `
                <span class="dot"></span>
                <span>System Online</span>
            `;
            if (data.last_result === "success" && data.last_run) {
                showToast("Scrape completed successfully!", "success");
                loadStats();
                loadJobs(currentPage);
                loadSources();
            }
            resetScrapeButtons();
        }
    } catch (e) {
        // Silently fail — will retry next interval
    }
}

function resetScrapeButtons() {
    const btnMain = document.getElementById("btnScrapeNow");
    const btnManual = document.getElementById("btnRunManual");
    btnMain.disabled = false;
    btnManual.disabled = false;
    btnMain.innerHTML = '🚀 Scrape Now';
    btnManual.innerHTML = '🚀 Run Scrape';
}


// ─── Scheduler ─────────────────────────────────────────────

async function loadSchedulerStatus() {
    try {
        const res = await fetch("/api/scheduler/status");
        const data = await res.json();
        updateSchedulerUI(data);
    } catch (e) {
        document.getElementById("schedulerLabel").textContent = "Not configured";
    }
}

function updateSchedulerUI(data) {
    const label = document.getElementById("schedulerLabel");
    const status = document.getElementById("schedulerStatus");

    if (data.active) {
        label.textContent = `Active — ${data.frequency || 'daily'}`;
        status.style.borderColor = "rgba(16, 185, 129, 0.2)";
        status.style.background = "rgba(16, 185, 129, 0.1)";
        status.style.color = "var(--accent-green)";
    } else if (data.paused) {
        label.textContent = "Paused";
        status.style.borderColor = "rgba(245, 158, 11, 0.2)";
        status.style.background = "rgba(245, 158, 11, 0.1)";
        status.style.color = "var(--accent-amber)";
    } else {
        label.textContent = "Inactive";
        status.style.borderColor = "rgba(100, 116, 139, 0.2)";
        status.style.background = "rgba(100, 116, 139, 0.1)";
        status.style.color = "var(--text-muted)";
    }

    if (data.next_run) {
        label.textContent += ` | Next: ${new Date(data.next_run).toLocaleTimeString()}`;
    }
}

async function saveSchedule() {
    const freq = document.getElementById("scheduleFreq").value;
    const time = document.getElementById("scheduleTime").value;
    const tiers = [];
    if (document.getElementById("schedTier1").checked) tiers.push(1);
    if (document.getElementById("schedTier2").checked) tiers.push(2);
    if (document.getElementById("schedTier3").checked) tiers.push(3);

    try {
        const res = await fetch("/api/scheduler/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ frequency: freq, time: time, tiers: tiers }),
        });
        const data = await res.json();

        if (res.ok) {
            showToast("Schedule saved! " + (data.message || ""), "success");
            updateSchedulerUI(data);
        } else {
            showToast(data.error || "Failed to save schedule", "error");
        }
    } catch (e) {
        showToast("Connection error", "error");
    }
}

async function pauseSchedule() {
    try {
        const res = await fetch("/api/scheduler/pause", { method: "POST" });
        const data = await res.json();
        showToast("Scheduler paused", "info");
        updateSchedulerUI(data);
    } catch (e) {
        showToast("Error pausing scheduler", "error");
    }
}

async function resumeSchedule() {
    try {
        const res = await fetch("/api/scheduler/resume", { method: "POST" });
        const data = await res.json();
        showToast("Scheduler resumed", "success");
        updateSchedulerUI(data);
    } catch (e) {
        showToast("Error resuming scheduler", "error");
    }
}


// ─── Toast Notifications ───────────────────────────────────

function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const icons = { success: "✅", error: "❌", info: "ℹ️" };
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${icons[type] || ""}</span> ${escapeHtml(message)}`;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = "0"; setTimeout(() => toast.remove(), 300); }, 4000);
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
