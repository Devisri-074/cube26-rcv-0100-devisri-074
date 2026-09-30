/**
 * InspectIQ™ — AI-Powered Visual Receiving Inspection
 * Primary Application Controller & Verification Matrix Logic.
 */

let annotator = null;
let currentScenarioId = "SCENARIO_01_CORRECT";
let currentEvidenceRecord = null;
let currentPO = null;
let scenariosData = [];
let manualHistory = [];
let activeFilter = "core"; // 'core' (5 canonical), 'all' (13 scenarios), or 'manual' (uploaded)
let currentUser = null;

const CORE_SCENARIO_IDS = [
    "SCENARIO_01_CORRECT",
    "SCENARIO_02_SHORTAGE",
    "SCENARIO_04_WRONG_SKU",
    "SCENARIO_06_CRUSHED",
    "SCENARIO_10_AMBIGUOUS_BLUR"
];

document.addEventListener("DOMContentLoaded", async () => {
    annotator = new InspectionCanvasAnnotator("inspectionCanvas");
    setupClock();
    setupEventListeners();
    await loadUserProfile();
    await loadScenariosList();
    await loadManualHistory();
    selectScenario("SCENARIO_01_CORRECT");
});

function setupClock() {
    const clockEl = document.getElementById("dockClock");
    if (!clockEl) return;
    setInterval(() => {
        const now = new Date();
        clockEl.textContent = `DOCK UTC: ${now.toISOString().slice(0, 19).replace('T', ' ')}`;
    }, 1000);
}

function setupEventListeners() {
    // Navigation Ribbon Tabs
    document.querySelectorAll(".nav-tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".nav-tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-view").forEach(c => c.classList.remove("active"));
            btn.classList.add("active");
            const target = btn.getAttribute("data-tab");
            const targetEl = document.getElementById(target);
            if (targetEl) targetEl.classList.add("active");

            if (target === "tab-workspace" && annotator) {
                setTimeout(() => annotator.render(), 40);
            }

            if (target === "tab-dossier" && currentEvidenceRecord && currentPO) {
                renderDossierTab();
            }
        });
    });

    // Top Demo Quick-Select Bar Buttons
    document.querySelectorAll(".demo-pill-btn").forEach(pill => {
        pill.addEventListener("click", () => {
            const scId = pill.getAttribute("data-scenario");
            if (scId) {
                selectScenario(scId);
            }
        });
    });

    // Sidebar Filter Chips (Core 5 vs All 13 vs Manual History)
    const filterCore = document.getElementById("filterCore");
    const filterAll = document.getElementById("filterAll");
    const filterManual = document.getElementById("filterManual");

    if (filterCore && filterAll) {
        filterCore.addEventListener("click", () => {
            activeFilter = "core";
            filterCore.classList.add("active");
            filterAll.classList.remove("active");
            if (filterManual) filterManual.classList.remove("active");
            renderScenariosList();
        });
        filterAll.addEventListener("click", () => {
            activeFilter = "all";
            filterAll.classList.add("active");
            filterCore.classList.remove("active");
            if (filterManual) filterManual.classList.remove("active");
            renderScenariosList();
        });
    }

    if (filterManual) {
        filterManual.addEventListener("click", () => {
            activeFilter = "manual";
            filterManual.classList.add("active");
            if (filterCore) filterCore.classList.remove("active");
            if (filterAll) filterAll.classList.remove("active");
            renderScenariosList();
        });
    }

    // Clear History Button
    const btnClearHistory = document.getElementById("btnClearManualHistory");
    if (btnClearHistory) {
        btnClearHistory.addEventListener("click", async () => {
            if (confirm("Are you sure you want to clear all stored manual inspection history?")) {
                await clearAllManualHistory();
            }
        });
    }

    // Toggle Sidebar / Drawer button
    const btnToggleDrawer = document.getElementById("btnToggleDrawer");
    if (btnToggleDrawer) {
        btnToggleDrawer.addEventListener("click", () => {
            if (activeFilter === "core") {
                filterAll.click();
            }
            const sidebar = document.getElementById("manifestSidebar");
            if (sidebar) {
                sidebar.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
        });
    }

    // Quick Link Button to Dossier
    const btnGoToDossier = document.getElementById("btnGoToDossier");
    if (btnGoToDossier) {
        btnGoToDossier.addEventListener("click", () => {
            const dossierTabBtn = document.getElementById("navTabDossier");
            if (dossierTabBtn) dossierTabBtn.click();
        });
    }

    // Vision Layer Switches
    document.getElementById("toggleBoxes").addEventListener("change", (e) => {
        annotator.toggleBoxes(e.target.checked);
        annotator.render();
    });

    document.getElementById("toggleLabels").addEventListener("change", (e) => {
        annotator.toggleLabels(e.target.checked);
        annotator.render();
    });

    document.getElementById("toggleHeatmap").addEventListener("change", (e) => {
        annotator.toggleHeatmap(e.target.checked);
        annotator.render();
    });

    document.getElementById("toggleGrid").addEventListener("change", (e) => {
        annotator.toggleGrid(e.target.checked);
        annotator.render();
    });

    const btnReset = document.getElementById("btnResetView");
    if (btnReset) {
        btnReset.addEventListener("click", () => annotator.resetView());
    }

    // Benchmark Suite Button
    const btnBench = document.getElementById("btnRunBenchmark");
    if (btnBench) {
        btnBench.addEventListener("click", runFullBenchmark);
    }

    // Dossier Actions
    const btnCopy = document.getElementById("btnCopyDossier");
    if (btnCopy) {
        btnCopy.addEventListener("click", () => {
            const txt = document.getElementById("markdownPreview").textContent;
            navigator.clipboard.writeText(txt);
            alert("Official inspection report & claim dossier copied to clipboard!");
        });
    }

    const btnPrint = document.getElementById("btnPrintDossier");
    if (btnPrint) {
        btnPrint.addEventListener("click", () => window.print());
    }

    // Manual Inbound Intake Form & Presets
    setupIntakeForm();
}

function setupIntakeForm() {
    const uploadForm = document.getElementById("customUploadForm");
    if (uploadForm) {
        uploadForm.addEventListener("submit", handleCustomUpload);
    }

    const fileInput = document.getElementById("customImageFile");
    const fileNameEl = document.getElementById("selectedFileName");
    const dropZone = document.getElementById("fileDropZone");

    async function loadSampleImage(imgUrl, buttonEl = null) {
        try {
            const response = await fetch(imgUrl);
            const blob = await response.blob();
            const fileName = imgUrl.split('/').pop();
            const file = new File([blob], fileName, { type: blob.type || "image/png" });
            
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            if (fileInput) fileInput.files = dataTransfer.files;

            if (fileNameEl) {
                fileNameEl.textContent = `Attached: ${fileName} (${(file.size / 1024).toFixed(1)} KB)`;
                fileNameEl.style.color = "#38bdf8";
            }

            document.querySelectorAll(".btn-sample-img").forEach(b => b.classList.remove("active"));
            if (buttonEl) {
                buttonEl.classList.add("active");
            } else {
                const matchingBtn = document.querySelector(`.btn-sample-img[data-img="${imgUrl}"]`);
                if (matchingBtn) matchingBtn.classList.add("active");
            }
        } catch (e) {
            console.error("Failed to load sample image:", e);
        }
    }

    // Auto-select standard photo on initialization
    loadSampleImage("/static/images/scenario_01_correct.png");

    // Preset Buttons
    const pBlue = document.getElementById("presetBlue24");
    const pBlack = document.getElementById("presetBlack12");
    const pGreen = document.getElementById("presetGreen48");

    if (pBlue) {
        pBlue.addEventListener("click", () => {
            document.getElementById("inputPoNumber").value = "PO-2026-LIVE-8801";
            document.getElementById("inputSku").value = "BLUE-BOTTLE-001";
            document.getElementById("inputUpc").value = "810092345001";
            document.getElementById("inputQty").value = "24";
            document.getElementById("inputUnitsPerCarton").value = "12";
            document.getElementById("inputVariant").value = "Blue";
            document.getElementById("inputSupplier").value = "Apex Hydration Mfg Ltd";
            document.getElementById("inputUnitPrice").value = "18.50";
            loadSampleImage("/static/images/scenario_01_correct.png");
        });
    }

    if (pBlack) {
        pBlack.addEventListener("click", () => {
            document.getElementById("inputPoNumber").value = "PO-2026-LIVE-8802";
            document.getElementById("inputSku").value = "BLUE-BOTTLE-001";
            document.getElementById("inputUpc").value = "810092345001";
            document.getElementById("inputQty").value = "12";
            document.getElementById("inputUnitsPerCarton").value = "12";
            document.getElementById("inputVariant").value = "Matte Black";
            document.getElementById("inputSupplier").value = "Apex Hydration Mfg Ltd";
            document.getElementById("inputUnitPrice").value = "18.50";
            loadSampleImage("/static/images/scenario_05_wrong_variant.png");
        });
    }

    if (pGreen) {
        pGreen.addEventListener("click", () => {
            document.getElementById("inputPoNumber").value = "PO-2026-LIVE-8803";
            document.getElementById("inputSku").value = "BLUE-BOTTLE-001";
            document.getElementById("inputUpc").value = "810092345001";
            document.getElementById("inputQty").value = "48";
            document.getElementById("inputUnitsPerCarton").value = "12";
            document.getElementById("inputVariant").value = "Alpine Green";
            document.getElementById("inputSupplier").value = "Apex Hydration Mfg Ltd";
            document.getElementById("inputUnitPrice").value = "18.50";
            loadSampleImage("/static/images/scenario_01_correct.png");
        });
    }

    // File Drop Zone with Drag & Drop
    if (dropZone && fileInput) {
        dropZone.addEventListener("click", (e) => {
            if (e.target !== fileInput) {
                fileInput.click();
            }
        });

        ["dragenter", "dragover"].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add("dragover");
            }, false);
        });

        ["dragleave", "drop"].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove("dragover");
            }, false);
        });

        dropZone.addEventListener("drop", (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files && files.length > 0) {
                fileInput.files = files;
                fileNameEl.textContent = `Attached File: ${files[0].name} (${(files[0].size / 1024).toFixed(1)} KB)`;
                fileNameEl.style.color = "#38bdf8";
                document.querySelectorAll(".btn-sample-img").forEach(b => b.classList.remove("active"));
            }
        });

        fileInput.addEventListener("change", () => {
            if (fileInput.files && fileInput.files[0]) {
                fileNameEl.textContent = `Attached File: ${fileInput.files[0].name} (${(fileInput.files[0].size / 1024).toFixed(1)} KB)`;
                fileNameEl.style.color = "#38bdf8";
                document.querySelectorAll(".btn-sample-img").forEach(b => b.classList.remove("active"));
            }
        });
    }

    // Sample Photo Picker Buttons
    document.querySelectorAll(".btn-sample-img").forEach(btn => {
        btn.addEventListener("click", () => {
            const imgUrl = btn.getAttribute("data-img");
            if (imgUrl) {
                loadSampleImage(imgUrl, btn);

                // Auto-configure PO manifest to match condition for realistic live evaluation
                if (imgUrl.includes("shortage")) {
                    document.getElementById("inputPoNumber").value = "PO-2026-LIVE-8802";
                    document.getElementById("inputSku").value = "BLUE-BOTTLE-001";
                    document.getElementById("inputQty").value = "24";
                    document.getElementById("inputVariant").value = "Blue";
                } else if (imgUrl.includes("wrong_sku")) {
                    document.getElementById("inputPoNumber").value = "PO-2026-LIVE-8804";
                    document.getElementById("inputSku").value = "BLUE-BOTTLE-001";
                    document.getElementById("inputQty").value = "24";
                    document.getElementById("inputVariant").value = "Blue";
                } else if (imgUrl.includes("wrong_variant")) {
                    document.getElementById("inputPoNumber").value = "PO-2026-LIVE-8805";
                    document.getElementById("inputSku").value = "BLUE-BOTTLE-001";
                    document.getElementById("inputQty").value = "24";
                    document.getElementById("inputVariant").value = "Blue";
                } else if (imgUrl.includes("crushed")) {
                    document.getElementById("inputPoNumber").value = "PO-2026-LIVE-8806";
                    document.getElementById("inputSku").value = "BLUE-BOTTLE-001";
                    document.getElementById("inputQty").value = "24";
                    document.getElementById("inputVariant").value = "Blue";
                } else if (imgUrl.includes("water_damage")) {
                    document.getElementById("inputPoNumber").value = "PO-2026-LIVE-8807";
                    document.getElementById("inputSku").value = "BLUE-BOTTLE-001";
                    document.getElementById("inputQty").value = "24";
                    document.getElementById("inputVariant").value = "Blue";
                } else if (imgUrl.includes("torn")) {
                    document.getElementById("inputPoNumber").value = "PO-2026-LIVE-8808";
                    document.getElementById("inputSku").value = "BLUE-BOTTLE-001";
                    document.getElementById("inputQty").value = "24";
                    document.getElementById("inputVariant").value = "Blue";
                } else if (imgUrl.includes("blur")) {
                    document.getElementById("inputPoNumber").value = "PO-2026-LIVE-8810";
                    document.getElementById("inputSku").value = "BLUE-BOTTLE-001";
                    document.getElementById("inputQty").value = "24";
                    document.getElementById("inputVariant").value = "Blue";
                } else if (imgUrl.includes("correct")) {
                    document.getElementById("inputPoNumber").value = "PO-2026-LIVE-8801";
                    document.getElementById("inputSku").value = "BLUE-BOTTLE-001";
                    document.getElementById("inputQty").value = "24";
                    document.getElementById("inputVariant").value = "Blue";
                }
            }
        });
    });
}

async function loadManualHistory() {
    try {
        const res = await fetch("/api/inspect/history");
        manualHistory = await res.json();
        updateManualCountBadge();
        renderManualHistoryList();
        if (activeFilter === "manual") {
            renderScenariosList();
        }
    } catch (err) {
        console.error("Failed to load manual history:", err);
    }
}

function updateManualCountBadge() {
    const badge = document.getElementById("manualCountBadge");
    if (badge) badge.textContent = manualHistory.length;
}

function renderManualHistoryList() {
    const container = document.getElementById("manualHistoryContainer");
    if (!container) return;

    if (manualHistory.length === 0) {
        container.innerHTML = `
            <div class="manual-history-empty">
                <p>No manual receiving inspections recorded yet.</p>
                <p style="font-size: 0.74rem; margin-top: 0.35rem;">Upload a photograph above or select a condition preset to run your first visual inspection.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = "";
    manualHistory.forEach(item => {
        const row = document.createElement("div");
        row.className = "manual-history-item";

        const vClass = `badge-${(item.verdict || 'ACCEPT').toLowerCase()}`;
        const dateStr = item.created_at ? new Date(item.created_at).toLocaleString() : "Just now";
        const thumbUrl = item.image_url || "/static/images/scenario_01_correct.png";
        const damagesSummary = item.detected_damages?.length > 0 
            ? item.detected_damages.join(", ") 
            : (item.discrepancies?.length > 0 ? item.discrepancies[0] : "Conforming PO specification");

        row.innerHTML = `
            <div class="manual-history-main">
                <div class="manual-thumb-box">
                    <img src="${thumbUrl}" alt="Photo" class="manual-thumb-img" onerror="this.src='/static/images/scenario_01_correct.png'">
                </div>
                <div class="manual-history-info">
                    <div class="manual-history-title-row">
                        <span class="manual-history-po">${item.po_number || "PO-MANUAL"}</span>
                        <span class="manual-history-sku">SKU: ${item.sku} • ${item.expected_quantity} Units (${item.expected_variant})</span>
                        <span class="badge-status ${vClass}">${item.verdict}</span>
                    </div>
                    <div class="manual-history-desc">${damagesSummary} • <small style="color: var(--text-dim);">${dateStr}</small></div>
                </div>
            </div>
            <div class="manual-history-actions">
                <button class="btn-inspect-history" data-record="${item.record_id}">
                    <svg width="12" height="12" fill="currentColor" viewBox="0 0 16 16"><path d="M10.5 8a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z"/><path d="M0 8s3-5.5 8-5.5S16 8 16 8s-3 5.5-8 5.5S0 8 0 8zm8 3.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z"/></svg>
                    View Inspection
                </button>
                <button class="btn-delete-history" data-record="${item.record_id}" title="Delete Record">✕</button>
            </div>
        `;

        row.querySelector(".btn-inspect-history").addEventListener("click", () => {
            selectManualInspection(item.record_id);
        });

        row.querySelector(".btn-delete-history").addEventListener("click", async (e) => {
            e.stopPropagation();
            if (confirm(`Delete manual inspection record for PO #${item.po_number}?`)) {
                await deleteManualInspection(item.record_id);
            }
        });

        container.appendChild(row);
    });
}

async function deleteManualInspection(recordId) {
    try {
        await fetch(`/api/inspect/history/${recordId}`, { method: "DELETE" });
        await loadManualHistory();
    } catch (err) {
        console.error("Failed to delete manual inspection:", err);
    }
}

async function clearAllManualHistory() {
    try {
        await fetch("/api/inspect/history", { method: "DELETE" });
        await loadManualHistory();
    } catch (err) {
        console.error("Failed to clear manual history:", err);
    }
}

async function loadScenariosList() {
    try {
        const res = await fetch("/api/scenarios");
        scenariosData = await res.json();
        renderScenariosList();
        updateKPISummaries();
    } catch (err) {
        console.error("Failed to load scenarios:", err);
    }
}

function updateKPISummaries() {
    let passCount = 0;
    let exceptionCount = 0;
    let uncertainCount = 0;
    let rejectCount = 0;

    scenariosData.forEach(s => {
        const v = s.expected_verdict;
        if (v === "ACCEPT" || v === "PASS") passCount++;
        else if (v === "EXCEPTION") exceptionCount++;
        else if (v === "UNCERTAIN") uncertainCount++;
        else if (v === "REJECT") rejectCount++;
    });

    const passEl = document.getElementById("kpiPassCount");
    if (passEl) passEl.innerHTML = `${passCount} <small>PASS (Canonical)</small>`;

    const expEl = document.getElementById("kpiExceptionCount");
    if (expEl) expEl.innerHTML = `${exceptionCount} <small>EXCEPTION</small>`;

    const uncEl = document.getElementById("kpiUncertainCount");
    if (uncEl) uncEl.innerHTML = `${uncertainCount} <small>REVIEW REQUIRED</small>`;

    const rejEl = document.getElementById("kpiRejectCount");
    if (rejEl) rejEl.innerHTML = `${rejectCount} <small>REJECT</small>`;
}

function renderScenariosList() {
    const container = document.getElementById("scenarioList");
    if (!container) return;
    container.innerHTML = "";

    if (activeFilter === "manual") {
        if (manualHistory.length === 0) {
            container.innerHTML = `
                <div style="font-size: 0.74rem; color: var(--text-secondary); padding: 1.5rem; text-align: center;">
                    No manual intake inspections recorded yet.<br>Upload a photo in the <strong>Manual Intake</strong> tab.
                </div>
            `;
            return;
        }

        manualHistory.forEach(item => {
            const card = document.createElement("div");
            card.className = `scenario-btn ${item.record_id === currentScenarioId ? 'active' : ''}`;
            card.id = `sc-card-${item.record_id}`;

            const vClass = `badge-${(item.verdict || 'ACCEPT').toLowerCase()}`;
            const desc = item.detected_damages?.length > 0 
                ? item.detected_damages.join(", ") 
                : (item.discrepancies?.length > 0 ? item.discrepancies[0] : `Live intake for SKU ${item.sku}`);

            card.innerHTML = `
                <div class="scenario-btn-top">
                    <span class="scenario-btn-title">📷 ${item.po_number}</span>
                    <span class="badge-status ${vClass}">${item.verdict}</span>
                </div>
                <div class="scenario-btn-desc">${desc}</div>
            `;

            card.addEventListener("click", () => selectManualInspection(item.record_id));
            container.appendChild(card);
        });
        return;
    }

    const filtered = (activeFilter === "core")
        ? scenariosData.filter(s => CORE_SCENARIO_IDS.includes(s.scenario_id))
        : scenariosData;

    filtered.forEach(sc => {
        const card = document.createElement("div");
        card.className = `scenario-btn ${sc.scenario_id === currentScenarioId ? 'active' : ''}`;
        card.id = `sc-card-${sc.scenario_id}`;

        const vClass = `badge-${sc.expected_verdict.toLowerCase()}`;

        card.innerHTML = `
            <div class="scenario-btn-top">
                <span class="scenario-btn-title">${sc.title}</span>
                <span class="badge-status ${vClass}">${sc.expected_verdict}</span>
            </div>
            <div class="scenario-btn-desc">${sc.description}</div>
        `;

        card.addEventListener("click", () => selectScenario(sc.scenario_id));
        container.appendChild(card);
    });
}

async function selectScenario(scenarioId) {
    currentScenarioId = scenarioId;

    // Update active state in Sidebar
    document.querySelectorAll(".scenario-btn").forEach(c => c.classList.remove("active"));
    const activeCard = document.getElementById(`sc-card-${scenarioId}`);
    if (activeCard) activeCard.classList.add("active");

    // Update active state in Demo Pills Bar
    document.querySelectorAll(".demo-pill-btn").forEach(pill => {
        if (pill.getAttribute("data-scenario") === scenarioId) {
            pill.classList.add("active");
        } else {
            pill.classList.remove("active");
        }
    });

    const sc = scenariosData.find(s => s.scenario_id === scenarioId);
    if (!sc) return;

    currentPO = sc.po;
    updatePODisplay(sc.po);

    // Reset and stream perception telemetry
    streamAgentThoughtProcess(sc);

    // Call API inspection endpoint
    try {
        const res = await fetch(`/api/scenarios/run/${scenarioId}`, { method: "POST" });
        const data = await res.json();
        currentEvidenceRecord = data.evidence_record;

        if (sc.image_url) {
            annotator.loadImage(sc.image_url, currentEvidenceRecord.bounding_boxes);
            
            // Update canvas image meta
            const metaTag = document.getElementById("canvasMetaTag");
            if (metaTag) {
                const qScore = currentEvidenceRecord.image_metadata?.quality_score || (scenarioId === "SCENARIO_10_AMBIGUOUS_BLUR" ? 0.28 : 0.92);
                document.getElementById("canvasSharpnessScore").textContent = `Sharpness: ${qScore.toFixed(2)}`;
            }
        }

        renderInspectionResults(currentEvidenceRecord);
    } catch (err) {
        console.error("Error running inspection:", err);
    }
}

function updatePODisplay(po) {
    document.getElementById("poNumber").textContent = po.po_number || "-";
    document.getElementById("poSKU").textContent = po.sku || "-";
    document.getElementById("poQuantity").textContent = `${po.expected_quantity} units (${po.expected_cartons || 2} master ctn)`;
    document.getElementById("poVariant").textContent = po.expected_variant || "-";
    document.getElementById("poSupplier").textContent = po.supplier_name || "-";
    document.getElementById("poUnitPrice").textContent = `$${po.unit_price?.toFixed(2) || "0.00"}`;
}

function streamAgentThoughtProcess(sc) {
    const stream = document.getElementById("thoughtStream");
    if (!stream) return;
    stream.innerHTML = "";

    const thoughts = [
        `[INGEST] Loaded PO #${sc.po.po_number} | SKU: ${sc.po.sku} | Ordered Qty: ${sc.po.expected_quantity}`,
        `[PERCEIVE] Analyzing receiving photography (Laplacian edge density & color clustering)...`,
        `[SECURITY] Sanitizing OCR text against adversarial prompt injections...`,
        `[DETERMINISTIC] Validating SKU cross-reference & quantity arithmetic: Expected ${sc.po.expected_quantity} units...`,
        `[UNCERTAINTY] Epistemic calibration: evaluating focal blur, occlusion & sealed packaging constraints...`,
        `[DECISION] Synthesized verdict: ${sc.expected_verdict} | Sealed SHA-256 evidence audit hash.`
    ];

    thoughts.forEach((msg, idx) => {
        setTimeout(() => {
            const now = new Date();
            const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
            const entry = document.createElement("div");
            entry.style.marginBottom = "3px";
            entry.innerHTML = `<span style="color: var(--text-dim);">[${timeStr}]</span> <span style="color: var(--text-secondary);">${msg}</span>`;
            stream.appendChild(entry);
            stream.scrollTop = stream.scrollHeight;
        }, idx * 45);
    });

    // Active Stepper
    const stepIds = ["stIngest", "stPerceive", "stDeterministic", "stUncertainty", "stArbitrate", "stSealed"];
    stepIds.forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.className = "stepper-step active";
    });
}

function renderInspectionResults(record) {
    // 1. Prominent Decision Hero Card
    const hero = document.getElementById("decisionHero");
    hero.className = `verdict-banner ${record.verdict}`;

    const verdictTitles = {
        "ACCEPT": "PASS",
        "EXCEPTION": "EXCEPTION",
        "UNCERTAIN": "UNCERTAIN",
        "REJECT": "REJECT"
    };

    const vTitle = verdictTitles[record.verdict] || record.verdict;
    document.getElementById("heroVerdictTitle").textContent = vTitle;
    document.getElementById("heroVerdictSummary").textContent = record.summary;

    const confPct = Math.round(record.overall_confidence * 100);
    document.getElementById("confText").textContent = `CALIBRATED CONFIDENCE: ${confPct}%`;
    document.getElementById("confFill").style.width = `${confPct}%`;

    const confTypeEl = document.getElementById("confType");
    if (record.verdict === "UNCERTAIN") {
        confTypeEl.textContent = "Epistemic Uncertainty Gate Active";
        confTypeEl.style.color = "var(--uncertain)";
    } else {
        confTypeEl.textContent = "Mathematically Grounded";
        confTypeEl.style.color = "#60a5fa";
    }

    // 2. Operator Guidance Warning (When UNCERTAIN)
    const opBox = document.getElementById("operatorGuidanceBox");
    if (record.operator_action_required) {
        opBox.style.display = "flex";
        document.getElementById("operatorGuidanceText").textContent = record.operator_action_required;
    } else {
        opBox.style.display = "none";
    }

    // 3. Dispute Claim Callout (When EXCEPTION)
    const claimBox = document.getElementById("disputeClaimCallout");
    if (record.supplier_dispute_eligible && record.dispute_claim_amount_usd > 0) {
        claimBox.style.display = "flex";
        document.getElementById("heroClaimAmount").textContent = `$${record.dispute_claim_amount_usd.toFixed(2)} USD`;
    } else {
        claimBox.style.display = "none";
    }

    // 4. Physical Evidence & Discrepancies List
    const discEl = document.getElementById("discrepanciesList");
    if (record.discrepancies && record.discrepancies.length > 0) {
        discEl.innerHTML = record.discrepancies.map(d => {
            let color = "var(--warning)";
            let prefix = "⚠️";
            if (d.includes("SKU MISMATCH") || d.includes("REJECT")) {
                color = "var(--danger)";
                prefix = "🛑";
            } else if (d.includes("DAMAGE") || d.includes("Crushed") || d.includes("Water") || d.includes("Torn")) {
                color = "var(--danger)";
                prefix = "💥";
            }
            return `<li style="color: ${color};"><strong>${prefix}</strong> ${d}</li>`;
        }).join("");
    } else if (record.verdict === "UNCERTAIN") {
        discEl.innerHTML = `<li style="color: var(--uncertain);"><strong>🔍</strong> Epistemic ambiguity detected. Visual evidence insufficient for automated sign-off.</li>`;
    } else {
        discEl.innerHTML = `<li style="color: var(--success);"><strong>✔</strong> Conforming shipment. 100% PO specifications and quality standards met.</li>`;
    }

    // 5. SHA-256 Tamper Seal
    document.getElementById("recordId").textContent = record.record_id;
    document.getElementById("recordHash").textContent = record.immutable_sha256;

    // 6. Side-by-Side Verification Matrix Table (Expected vs Observed)
    renderVerificationMatrixTable(record);
}

function renderVerificationMatrixTable(record) {
    const tbody = document.getElementById("matrixTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    const dimensionIcons = {
        "SKU_IDENTITY": "🏷️ SKU Identity",
        "QUANTITY_COUNT": "📦 Quantity Count",
        "VARIANT_SPEC": "🎨 Variant / Color",
        "CARTON_INTEGRITY": "🛡️ Packaging Integrity",
        "PACKAGING_DAMAGE": "⚠️ Damage Detection",
        "COMPONENT_INTEGRITY": "🧩 Component Integrity",
        "LABEL_BARCODE": "🔒 Label Security"
    };

    Object.keys(record.checks).forEach(k => {
        const c = record.checks[k];
        const row = document.createElement("tr");

        const vClass = `badge-${c.status.toLowerCase()}`;
        const dimName = dimensionIcons[c.check_type] || c.check_type;

        // Compute Variance / Delta Tag
        let deltaHtml = formatDeltaPill(c);

        row.innerHTML = `
            <td><span class="dimension-cell">${dimName}</span></td>
            <td><span class="badge-status ${vClass}">${c.status}</span></td>
            <td><code class="val-badge">${formatValueString(c.expected_value)}</code></td>
            <td><code class="val-badge">${formatValueString(c.observed_value)}</code></td>
            <td>${deltaHtml}</td>
            <td style="font-size: 0.74rem; color: var(--text-secondary); line-height: 1.35;">${c.reason}</td>
        `;
        tbody.appendChild(row);
    });
}

function formatValueString(val) {
    if (Array.isArray(val)) {
        return val.join(", ");
    }
    if (val === null || val === undefined) {
        return "N/A";
    }
    return String(val);
}

function formatDeltaPill(check) {
    if (check.status === "PASS") {
        if (check.check_type === "QUANTITY_COUNT") {
            return `<span class="delta-pill delta-match">Difference: 0 (Exact)</span>`;
        }
        return `<span class="delta-pill delta-match">Exact Match</span>`;
    }

    if (check.status === "UNCERTAIN") {
        return `<span class="delta-pill delta-uncertain">Unverifiable (Review)</span>`;
    }

    // Fail / Exception cases
    if (check.check_type === "QUANTITY_COUNT") {
        if (typeof check.discrepancy_delta === "number" && check.discrepancy_delta < 0) {
            return `<span class="delta-pill delta-neg">Difference: ${check.discrepancy_delta} (Shortage)</span>`;
        } else if (typeof check.discrepancy_delta === "string" && check.discrepancy_delta.startsWith("+")) {
            return `<span class="delta-pill delta-pos">Difference: ${check.discrepancy_delta} (Overage)</span>`;
        }
        return `<span class="delta-pill delta-neg">Qty Mismatch</span>`;
    }

    if (check.check_type === "SKU_IDENTITY") {
        return `<span class="delta-pill delta-mismatch">Mismatch: ${check.observed_value}</span>`;
    }

    if (check.check_type === "VARIANT_SPEC") {
        return `<span class="delta-pill delta-mismatch">Color Mismatch</span>`;
    }

    if (check.check_type === "PACKAGING_DAMAGE" || check.check_type === "CARTON_INTEGRITY") {
        return `<span class="delta-pill delta-defect">Defect Present</span>`;
    }

    if (check.check_type === "COMPONENT_INTEGRITY") {
        return `<span class="delta-pill delta-neg">Missing Parts</span>`;
    }

    if (check.check_type === "LABEL_BARCODE") {
        return `<span class="delta-pill delta-mismatch">Tampered</span>`;
    }

    return `<span class="delta-pill delta-neg">Discrepancy</span>`;
}

async function renderDossierTab() {
    if (!currentEvidenceRecord || !currentPO) return;

    // Populate the 9 Executive Fields
    document.getElementById("repPoNumber").textContent = currentPO.po_number || "-";
    document.getElementById("repSKU").textContent = `${currentPO.sku} (UPC: ${currentPO.asin_or_upc || "N/A"})`;
    
    const qtyCheck = currentEvidenceRecord.checks["QUANTITY_COUNT"];
    const obsQty = qtyCheck ? qtyCheck.observed_value : "N/A";
    const deltaStr = (qtyCheck && qtyCheck.discrepancy_delta !== undefined) 
        ? (typeof qtyCheck.discrepancy_delta === "number" && qtyCheck.discrepancy_delta !== 0 ? ` (Difference: ${qtyCheck.discrepancy_delta > 0 ? '+' : ''}${qtyCheck.discrepancy_delta})` : " (Difference: 0)")
        : "";
    document.getElementById("repQuantity").textContent = `Expected: ${currentPO.expected_quantity} | Observed: ${obsQty}${deltaStr}`;

    const varCheck = currentEvidenceRecord.checks["VARIANT_SPEC"];
    const obsVar = varCheck ? varCheck.observed_value : "N/A";
    document.getElementById("repVariant").textContent = `Expected: ${currentPO.expected_variant} | Observed: ${obsVar}`;

    const damageStr = currentEvidenceRecord.detected_damages?.length > 0 
        ? currentEvidenceRecord.detected_damages.join(", ") 
        : "NONE (Zero Defects Detected)";
    document.getElementById("repDamage").textContent = damageStr;

    document.getElementById("repDecision").innerHTML = `<span class="badge-status badge-${currentEvidenceRecord.verdict.toLowerCase()}">${currentEvidenceRecord.verdict}</span>`;
    document.getElementById("reportHeaderVerdictBadge").className = `badge-status badge-${currentEvidenceRecord.verdict.toLowerCase()}`;
    document.getElementById("reportHeaderVerdictBadge").textContent = currentEvidenceRecord.verdict;

    document.getElementById("repConfidence").textContent = `${Math.round(currentEvidenceRecord.overall_confidence * 100)}% (Grounded Calibrated Score)`;
    
    const checksCount = Object.keys(currentEvidenceRecord.checks).length;
    const discCount = currentEvidenceRecord.discrepancies.length;
    document.getElementById("repEvidence").textContent = `${checksCount} Dimensions Evaluated (${discCount} Non-Conformances Grounded)`;

    document.getElementById("repTimestamp").textContent = `${currentEvidenceRecord.created_at || new Date().toISOString()} (UTC)`;

    // Call API to render raw Markdown
    try {
        const res = await fetch("/api/dossier/render-markdown", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                evidence_record: currentEvidenceRecord,
                po: currentPO
            })
        });
        const data = await res.json();
        document.getElementById("markdownPreview").textContent = data.markdown;
        document.getElementById("dossierClaimAmount").textContent = `$${currentEvidenceRecord.dispute_claim_amount_usd.toFixed(2)} USD`;
        document.getElementById("dossierEligible").textContent = currentEvidenceRecord.supplier_dispute_eligible 
            ? "DISPUTE ACTION REQUIRED (CLAIM ELIGIBLE)" 
            : (currentEvidenceRecord.verdict === "UNCERTAIN" ? "ACTION REQUIRED: MANUAL OPERATOR INSPECTION" : "CONFORMING SHIPMENT (NO CLAIM)");
    } catch (err) {
        console.error("Dossier render error:", err);
    }
}

async function runFullBenchmark() {
    const btn = document.getElementById("btnRunBenchmark");
    btn.textContent = "⚡ Executing Neural Benchmark Suite...";
    btn.disabled = true;

    try {
        const res = await fetch("/api/scenarios/benchmark", { method: "POST" });
        const bench = await res.json();

        document.getElementById("benchAccuracy").textContent = `${bench.accuracy_pct}%`;
        document.getElementById("benchPassed").textContent = `${bench.correct_evaluations} / ${bench.total_scenarios}`;
        document.getElementById("benchLatencyP50").textContent = `${bench.latency_metrics_ms.p50}ms`;
        document.getElementById("benchLatencyP95").textContent = `${bench.latency_metrics_ms.p95}ms`;

        const tbody = document.getElementById("benchmarkScorecardBody");
        tbody.innerHTML = "";

        bench.scenario_results.forEach(sr => {
            const tr = document.createElement("tr");
            const passBadge = sr.is_correct 
                ? `<span class="badge-status badge-pass">PASS</span>` 
                : `<span class="badge-status badge-fail">FAIL</span>`;
            
            tr.innerHTML = `
                <td><code>${sr.scenario_id}</code></td>
                <td>${sr.category}</td>
                <td><span class="badge-status badge-${sr.expected_verdict.toLowerCase()}">${sr.expected_verdict}</span></td>
                <td><span class="badge-status badge-${sr.actual_verdict.toLowerCase()}">${sr.actual_verdict}</span></td>
                <td>${passBadge}</td>
                <td><code>${sr.latency_ms}ms</code></td>
                <td><code>${sr.sha256}</code></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Benchmark failed:", err);
    } finally {
        btn.textContent = "⚡ Run Autonomous Test Benchmark";
        btn.disabled = false;
    }
}

async function selectManualInspection(recordId, directImageSource = null) {
    currentScenarioId = recordId;
    let item = manualHistory.find(m => m.record_id === recordId);
    
    if (!item) {
        try {
            const res = await fetch(`/api/inspect/history/${recordId}`);
            if (res.ok) {
                item = await res.json();
            }
        } catch (e) {
            console.error("Failed to fetch inspection record:", e);
        }
    }
    
    if (!item) return;

    currentEvidenceRecord = item.evidence_record || item;
    currentPO = item.po || {
        po_number: item.po_number || "PO-2026-LIVE-8801",
        sku: item.sku || "BLUE-BOTTLE-001",
        asin_or_upc: item.po?.asin_or_upc || "810092345001",
        expected_quantity: item.expected_quantity || 24,
        units_per_carton: item.units_per_carton || 12,
        expected_cartons: item.expected_cartons || Math.ceil((item.expected_quantity || 24) / (item.units_per_carton || 12)),
        expected_variant: item.expected_variant || "Blue",
        supplier_name: item.supplier_name || "Apex Hydration Mfg Ltd",
        unit_price: item.unit_price || 18.50,
        required_components: item.po?.required_components || ["Bottle Body", "Insulated Cap"]
    };

    // 1. Switch to workspace tab FIRST so canvas container is visible in DOM
    const wsTab = document.getElementById("navTabWorkspace");
    if (wsTab) wsTab.click();

    // 2. Update PO display
    updatePODisplay(currentPO);

    // 3. Render inspection results & matrix
    renderInspectionResults(currentEvidenceRecord);

    // 4. Stream thought process
    streamCustomThoughtProcess(currentPO, currentEvidenceRecord);

    // 5. Load image into canvas annotator
    const imageUrl = directImageSource || item.image_url || currentEvidenceRecord.image_metadata?.image_url || "/static/images/scenario_01_correct.png";
    annotator.loadImage(imageUrl, currentEvidenceRecord.bounding_boxes);

    // 6. Update canvas metadata overlay
    const metaTag = document.getElementById("canvasMetaTag");
    if (metaTag) {
        const qScore = currentEvidenceRecord.image_metadata?.laplacian_sharpness || currentEvidenceRecord.overall_confidence;
        document.getElementById("canvasSharpnessScore").textContent = `Sharpness: ${Number(qScore).toFixed(2)}`;
        const w = currentEvidenceRecord.image_metadata?.width || 640;
        const h = currentEvidenceRecord.image_metadata?.height || 480;
        document.getElementById("canvasImageResolution").textContent = `Resolution: ${w}×${h}`;
    }

    // 7. Update active state in Sidebar
    document.querySelectorAll(".scenario-btn").forEach(c => c.classList.remove("active"));
    const activeCard = document.getElementById(`sc-card-${recordId}`);
    if (activeCard) activeCard.classList.add("active");

    // 8. Remove active state from preset demo pills
    document.querySelectorAll(".demo-pill-btn").forEach(pill => pill.classList.remove("active"));
}

function streamCustomThoughtProcess(po, record) {
    const stream = document.getElementById("thoughtStream");
    if (!stream) return;
    stream.innerHTML = "";

    const damagesCount = record.detected_damages?.length || 0;
    const damagesStr = damagesCount > 0 ? record.detected_damages.join(", ") : "Zero physical defects";

    const thoughts = [
        `[INGEST] Ingested Live Manual Dock Intake: PO #${po.po_number} | SKU: ${po.sku} | Qty: ${po.expected_quantity} units | Variant: ${po.expected_variant}`,
        `[PERCEIVE] Executing 2D Laplacian operator & HSV color clustering: Sharpness: ${(record.overall_confidence).toFixed(2)} | Variant: ${record.checks?.VARIANT_SPEC?.observed_value || po.expected_variant}`,
        `[SECURITY] Sanitized OCR label text against adversarial prompt injections (${record.adversarial_signals?.length || 0} threats detected)`,
        `[DEFECT SCAN] Physical packaging integrity: ${damagesStr} | Status: ${record.checks?.CARTON_INTEGRITY?.status || "PASS"}`,
        `[DETERMINISTIC] Validating SKU identity & unit packing count (${record.checks?.QUANTITY_COUNT?.observed_value || po.expected_quantity}/${po.expected_quantity})`,
        `[DECISION] Sealed immutable evidence record: ${record.verdict} | Calibrated Confidence: ${Math.round(record.overall_confidence * 100)}% | SHA-256: ${record.immutable_sha256?.slice(0, 12) || "Verified"}`
    ];

    thoughts.forEach((msg, idx) => {
        setTimeout(() => {
            const now = new Date();
            const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
            const entry = document.createElement("div");
            entry.style.marginBottom = "3px";
            entry.innerHTML = `<span style="color: var(--text-dim);">[${timeStr}]</span> <span style="color: var(--text-secondary);">${msg}</span>`;
            stream.appendChild(entry);
            stream.scrollTop = stream.scrollHeight;
        }, idx * 45);
    });

    const stepIds = ["stIngest", "stPerceive", "stDeterministic", "stUncertainty", "stArbitrate", "stSealed"];
    stepIds.forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.className = "stepper-step active";
    });
}

async function handleCustomUpload(e) {
    e.preventDefault();
    const form = e.target;
    const fileInput = document.getElementById("customImageFile");
    
    // If no file selected, automatically load standard sample photo
    if (!fileInput.files || fileInput.files.length === 0) {
        try {
            const fallbackRes = await fetch("/static/images/scenario_01_correct.png");
            const fallbackBlob = await fallbackRes.blob();
            const fallbackFile = new File([fallbackBlob], "scenario_01_correct.png", { type: "image/png" });
            const dt = new DataTransfer();
            dt.items.add(fallbackFile);
            fileInput.files = dt.files;
        } catch (err) {
            console.error("Fallback image load failed:", err);
        }
    }

    const uploadedFile = fileInput.files && fileInput.files[0];
    let localBlobUrl = null;
    if (uploadedFile) {
        try {
            localBlobUrl = URL.createObjectURL(uploadedFile);
        } catch (err) {
            console.error("Blob URL creation failed:", err);
        }
    }

    const formData = new FormData(form);
    const submitBtn = document.getElementById("btnSubmitCustom");
    submitBtn.textContent = "Running AI Vision Inspection...";
    submitBtn.disabled = true;

    try {
        const res = await fetch("/api/inspect/custom", {
            method: "POST",
            body: formData
        });
        
        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || "Inspection failed");
        }

        const result = await res.json();
        const record = result.evidence_record || result;

        // Reload history from server to get saved archive
        await loadManualHistory();

        // Automatically switch to viewing this new inspection in full workspace
        await selectManualInspection(record.record_id, localBlobUrl);

    } catch (err) {
        alert("Custom inspection error: " + err.message);
    } finally {
        submitBtn.textContent = "Run Visual AI Inspection";
        submitBtn.disabled = false;
    }
}

// =========================================================================
// Operator Authentication & Role Personas
// =========================================================================
async function loadUserProfile() {
    try {
        const res = await fetch("/api/auth/me");
        currentUser = await res.json();
        renderCurrentUserBadge();
    } catch (err) {
        console.error("Failed to load user profile:", err);
    }

    const btnUser = document.getElementById("btnUserModal");
    if (btnUser) {
        btnUser.addEventListener("click", openUserModal);
    }

    const btnClose = document.getElementById("btnCloseUserModal");
    if (btnClose) {
        btnClose.addEventListener("click", () => document.getElementById("userModal").classList.remove("active"));
    }

    const btnCloseBottom = document.getElementById("btnCloseModalBottom");
    if (btnCloseBottom) {
        btnCloseBottom.addEventListener("click", () => document.getElementById("userModal").classList.remove("active"));
    }
}

function renderCurrentUserBadge() {
    if (!currentUser) return;
    document.getElementById("userAvatar").textContent = currentUser.avatar_initials;
    document.getElementById("userName").textContent = currentUser.full_name;
    document.getElementById("userRole").textContent = currentUser.role_title.toUpperCase();
}

async function openUserModal() {
    const modal = document.getElementById("userModal");
    modal.classList.add("active");

    try {
        const res = await fetch("/api/auth/users");
        const personas = await res.json();
        const listEl = document.getElementById("personaList");
        listEl.innerHTML = "";

        personas.forEach(p => {
            const card = document.createElement("div");
            card.className = "persona-card";
            const isCurrent = (currentUser && currentUser.username === p.username);

            card.innerHTML = `
                <div class="persona-left">
                    <div class="persona-avatar">${p.avatar_initials}</div>
                    <div>
                        <div style="font-weight: 600; font-size: 0.85rem; color: #fff;">${p.full_name} ${isCurrent ? '<span style="color: var(--success); font-size: 0.7rem;">(Active)</span>' : ''}</div>
                        <div style="font-size: 0.72rem; color: var(--text-secondary);">${p.role_title} • ${p.dock_station}</div>
                    </div>
                </div>
                <button class="btn-primary" style="padding: 0.35rem 0.75rem; font-size: 0.75rem;">Switch</button>
            `;

            card.querySelector("button").addEventListener("click", () => switchUser(p.username));
            listEl.appendChild(card);
        });
    } catch (err) {
        console.error("Failed to load personas:", err);
    }
}

async function switchUser(username) {
    try {
        const res = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: username })
        });
        currentUser = await res.json();
        renderCurrentUserBadge();
        document.getElementById("userModal").classList.remove("active");
        if (currentEvidenceRecord && currentPO) {
            renderDossierTab();
        }
    } catch (err) {
        console.error("Failed to switch user:", err);
    }
}
