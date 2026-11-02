/* ==========================================================================
   DKA DIGITAL — GATE SCANNER CONTROLLER (PAGE 6)
   ========================================================================== */

const el = (id) => document.getElementById(id);
const start = el("start-scanner");
const stop = el("stop-scanner");
const status = el("scanner-status");
const scanCountKey = "dkaGateScans";
let scanner;
let active = false;
let starting = false;
let fileScanInProgress = false;
let captured = false;
let resetTimer;
let scans = Number.parseInt(sessionStorage.getItem(scanCountKey), 10) || 0;

if (el("session-scan-count")) {
  el("session-scan-count").textContent = scans;
}

function getHtml5QrcodeConstructor() {
  if (typeof window.Html5Qrcode !== "undefined") return window.Html5Qrcode;
  if (typeof Html5Qrcode !== "undefined") return Html5Qrcode;
  if (window.__Html5QrcodeLibrary__ && window.__Html5QrcodeLibrary__.Html5Qrcode) {
    return window.__Html5QrcodeLibrary__.Html5Qrcode;
  }
  return null;
}

function updateClock() {
  const clockEl = el("gate-clock");
  if (clockEl) {
    clockEl.textContent = new Intl.DateTimeFormat("en-NG", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Africa/Lagos",
    }).format(new Date()) + " WAT";
  }
}

function countScan() {
  scans += 1;
  sessionStorage.setItem(scanCountKey, String(scans));
  if (el("session-scan-count")) {
    el("session-scan-count").textContent = scans;
  }
}

function showResult(data) {
  const resBox = el("scan-result");
  const title = el("scan-result-title");
  const details = el("scan-result-details");
  const message = el("scan-result-message");

  const now = new Intl.DateTimeFormat("en-NG", {
    timeStyle: "short",
    timeZone: "Africa/Lagos",
  }).format(new Date());

  if (data.result === "VALID") {
    resBox.className = "scanner-result-box result-valid text-start";
    title.innerHTML = `✓ <span style="color: #15803D; font-size: 13.5px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">BOARDING APPROVED</span>`;
    details.textContent = data.passenger_name || "Approved Passenger";
    message.innerHTML = `
      <div style="font-size: 14px; font-weight: 600; color: #111827; margin-top: 6px;">
        ${data.flight_number || 'FLIGHT'} &nbsp;·&nbsp; Seat ${data.seat_number || '—'} &nbsp;·&nbsp; Gate ${data.gate || 'A1'}
      </div>
      <div style="font-size: 12.5px; color: #4B5563; margin-top: 4px;">
        ${data.message || 'Passenger verified successfully.'}
      </div>
      <div style="font-size: 12px; color: #15803D; margin-top: 6px; font-weight: 500;">
        Verified at ${now} WAT · Ready for aircraft boarding
      </div>
    `;
  } else if (data.result === "ALREADY_USED") {
    resBox.className = "scanner-result-box result-used text-start";
    title.innerHTML = `⚠️ <span style="color: #B45309; font-size: 13.5px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">ALREADY SCANNED (DUPLICATE)</span>`;
    details.textContent = data.passenger_name ? `${data.passenger_name} · Seat ${data.seat_number || '—'}` : "Already Scanned";
    message.innerHTML = `
      <div style="font-size: 14px; font-weight: 600; color: #92400E; margin-top: 6px;">
        ${data.flight_number ? 'Flight ' + data.flight_number + ' · ' : ''}Seat ${data.seat_number || '—'}
      </div>
      <div style="font-size: 13px; color: #78350F; margin-top: 4px;">
        ${data.message || 'This boarding pass was already scanned today.'}
      </div>
      <div style="font-size: 12px; color: #B45309; margin-top: 6px; font-weight: 600;">
        ⛔ DO NOT ALLOW RE-ENTRY. Alert gate supervisor if duplicate passenger presented.
      </div>
    `;
  } else if (data.result === "EXPIRED") {
    resBox.className = "scanner-result-box result-expired text-start";
    title.innerHTML = `🕒 <span style="color: #1D4ED8; font-size: 13.5px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">PASS EXPIRED (PAST FLIGHT)</span>`;
    details.textContent = data.passenger_name ? `${data.passenger_name} (${data.flight_number || ''})` : "Expired Boarding Pass";
    message.innerHTML = `
      <div style="font-size: 13.5px; color: #1E3A8A; margin-top: 6px; font-weight: 500;">
        ${data.message || 'This pass is for a flight that has already taken place.'}
      </div>
      <div style="font-size: 12px; color: #3B82F6; margin-top: 6px;">
        Direct passenger to the airport customer service / ticketing counter.
      </div>
    `;
  } else if (data.reason_type === "FUTURE_FLIGHT_DATE") {
    resBox.className = "scanner-result-box result-used text-start";
    title.innerHTML = `📅 <span style="color: #D97706; font-size: 13.5px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">TOO EARLY — FUTURE FLIGHT</span>`;
    details.textContent = data.passenger_name ? `${data.passenger_name} · Flight ${data.flight_number || ''}` : "Future Flight Pass";
    message.innerHTML = `
      <div style="font-size: 13.5px; color: #92400E; margin-top: 6px; font-weight: 500;">
        ${data.message || 'This pass is for an upcoming flight on a future date.'}
      </div>
      <div style="font-size: 12px; color: #B45309; margin-top: 6px; font-weight: 600;">
        ⛔ Passenger cannot board today. Please advise passenger to return on their scheduled departure date.
      </div>
    `;
  } else if (data.reason_type === "FLIGHT_CANCELLED") {
    resBox.className = "scanner-result-box result-invalid text-start";
    title.innerHTML = `✕ <span style="color: #B91C1C; font-size: 13.5px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">FLIGHT CANCELLED</span>`;
    details.textContent = data.passenger_name ? `${data.passenger_name} (${data.flight_number || ''})` : "Flight Cancelled";
    message.innerHTML = `
      <div style="font-size: 13.5px; color: #7F1D1D; margin-top: 6px;">
        ${data.message || 'This flight has been cancelled.'}
      </div>
      <div style="font-size: 12px; color: #DC2626; margin-top: 6px;">
        Direct passenger to the airline desk for rescheduling.
      </div>
    `;
  } else {
    resBox.className = "scanner-result-box result-invalid text-start";
    title.innerHTML = `✕ <span style="color: #B91C1C; font-size: 13.5px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">BOARDING DENIED (INVALID)</span>`;
    details.textContent = data.passenger_name ? `${data.passenger_name} · Invalid` : "Invalid Boarding Code";
    message.innerHTML = `
      <div style="font-size: 13.5px; color: #7F1D1D; margin-top: 6px;">
        ${data.message || 'This QR code is not recognized as a valid boarding pass.'}
      </div>
      <div style="font-size: 12px; color: #DC2626; margin-top: 6px;">
        Verify physical ID and direct passenger to the terminal service desk.
      </div>
    `;
  }
}

async function verify(code) {
  const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
  const token = csrfInput ? csrfInput.value : "";
  const response = await fetch("/gate/verify/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": token },
    body: JSON.stringify({ code }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Verification request failed.");
  showResult(data);
}

async function handleScanSuccess(code) {
  if (captured) return;
  captured = true;
  countScan();
  await stopCamera(false);
  if (stop) stop.disabled = true;
  if (start) start.disabled = false;
  status.textContent = "Verifying boarding pass...";

  try {
    await verify(code);
    status.textContent = "Verification complete.";
  } catch (error) {
    el("scan-result-title").textContent = "VERIFICATION ERROR";
    el("scan-result-details").textContent = "Please alert a supervisor.";
    el("scan-result-message").textContent = error.message;
    el("scan-result").className = "scanner-result-box result-invalid text-start";
  }

  resetTimer = window.setTimeout(startCamera, 3500);
}

async function startCamera() {
  if (active || starting || fileScanInProgress) return;
  starting = true;
  if (start) start.disabled = true;
  status.textContent = "Starting camera...";
  captured = false;

  const QrConstructor = getHtml5QrcodeConstructor();
  if (!QrConstructor) {
    starting = false;
    active = false;
    if (start) start.disabled = false;
    if (stop) stop.disabled = true;
    status.textContent = "Scanner library is loading. Please try again in a few seconds or use 'Scan Image'.";
    return;
  }

  if (!scanner) scanner = new QrConstructor("qr-reader");
  const config = { fps: 10, qrbox: { width: 250, height: 250 } };
  const onSuccess = (text) => handleScanSuccess(text);
  const onFailure = () => {};
  try {
    const cameras = await QrConstructor.getCameras().catch(() => []);
    const rearCamera = cameras.find((item) => /back|rear|environment/i.test(item.label));
    const candidates = [
      ...(rearCamera ? [rearCamera.id] : []),
      ...cameras.filter((item) => !rearCamera || item.id !== rearCamera.id).map((item) => item.id),
      { facingMode: "environment" },
      { facingMode: "user" },
    ];
    let lastError;
    for (const camera of candidates) {
      try {
        await scanner.start(camera, config, onSuccess, onFailure);
        active = true;
        if (stop) stop.disabled = false;
        status.textContent = "Camera active. Scan a boarding pass QR code.";
        return;
      } catch (error) {
        lastError = error;
        // Some browsers leave a partially initialized scanner after a failed start.
        try { await scanner.clear(); } catch (clearError) {}
        scanner = new QrConstructor("qr-reader");
      }
    }
    const isSecure = window.isSecureContext || location.hostname === "localhost" || location.hostname === "127.0.0.1";
    if (!isSecure) {
      status.innerHTML = `<span style="color:#DC2626;">Camera requires HTTPS or localhost.</span> Use 'Scan Image / PDF' to upload boarding pass.`;
    } else {
      status.textContent = "Could not start camera: " + (lastError?.message || "Permission denied or no webcam available.");
    }
  } finally {
    starting = false;
    if (!active) {
      if (start) start.disabled = false;
      if (stop) stop.disabled = true;
    }
  }
}

async function stopCamera(showStatus = true) {
  if (scanner && active) {
    try { await scanner.stop(); } catch (error) {}
    try { await scanner.clear(); } catch (error) {}
  }
  active = false;
  if (start) start.disabled = false;
  if (stop) stop.disabled = true;
  if (showStatus && status) status.textContent = "Camera stopped.";
}

async function scanUploadedFile(file, QrConstructor) {
  const tempId = `qr-file-scan-${Date.now()}`;
  const container = document.createElement("div");
  container.id = tempId;
  container.style.display = "none";
  document.body.appendChild(container);
  const fileScanner = new QrConstructor(tempId);
  try {
    return await fileScanner.scanFile(file, true);
  } finally {
    try { await fileScanner.clear(); } catch (error) {}
    container.remove();
  }
}

async function extractQrFromPdf(file) {
  if (typeof window.pdfjsLib === "undefined") {
    throw new Error("PDF processing engine is not loaded. Please reload the page.");
  }
  const arrayBuffer = await file.arrayBuffer();
  const pdfDoc = await window.pdfjsLib.getDocument({ data: arrayBuffer }).promise;
  const numPages = Math.min(pdfDoc.numPages, 3);

  for (let pageNum = 1; pageNum <= numPages; pageNum++) {
    status.textContent = `Reading PDF page ${pageNum} of ${numPages}...`;
    const page = await pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: 2.2 });
    const canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext("2d");
    await page.render({ canvasContext: ctx, viewport: viewport }).promise;

    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    if (blob) {
      try {
        const pageFile = new File([blob], `boarding-pass-page-${pageNum}.png`, { type: "image/png" });
        const decoded = await scanUploadedFile(pageFile, getHtml5QrcodeConstructor());
        if (decoded) return decoded;
      } catch (scanErr) {
        // Continue searching next page if not on this page
      }
    }
  }
  throw new Error("Could not find a valid boarding pass QR code inside the PDF file.");
}

// File input handler: allows scanning any QR photo or PDF document directly
const fileInput = el("qr-file-input");
if (fileInput) {
  fileInput.addEventListener("change", async (event) => {
    if (!event.target.files || event.target.files.length === 0) return;
    const file = event.target.files[0];
    const QrConstructor = getHtml5QrcodeConstructor();
    if (!QrConstructor) {
      alert("Scanner library is still loading. Please wait a moment.");
      return;
    }
    window.clearTimeout(resetTimer);
    fileScanInProgress = true;
    if (active) await stopCamera(false);

    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    status.textContent = isPdf ? "Processing PDF document..." : "Scanning uploaded image...";

    try {
      let decodedText;
      if (isPdf) {
        decodedText = await extractQrFromPdf(file);
      } else {
        decodedText = await scanUploadedFile(file, QrConstructor);
      }
      countScan();
      status.textContent = "Verifying pass...";
      await verify(decodedText);
      status.textContent = "Verification complete.";
    } catch (error) {
      el("scan-result-title").textContent = isPdf ? "PDF SCAN FAILED" : "NO QR DETECTED";
      el("scan-result-details").textContent = isPdf ? "No QR found in PDF" : "Could not read QR code from image.";
      el("scan-result-message").textContent = error.message || "Please ensure the boarding pass QR is clearly visible.";
      el("scan-result").className = "scanner-result-box result-invalid text-start";
      status.textContent = isPdf ? "Failed to decode PDF QR." : "Failed to detect QR in image.";
    }
    fileInput.value = "";
    fileScanInProgress = false;
    if (start) start.disabled = false;
  });
}

updateClock();
window.setInterval(updateClock, 30000);

if (start) start.addEventListener("click", startCamera);
if (stop) {
  stop.addEventListener("click", async () => {
    window.clearTimeout(resetTimer);
    await stopCamera();
  });
}
