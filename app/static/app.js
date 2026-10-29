const $ = (selector) => document.querySelector(selector);

async function apiRequest(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = body && typeof body === "object" ? (body.detail || JSON.stringify(body)) : body;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

function setMessage(target, message, isError = false) {
  target.replaceChildren();
  const node = document.createElement("p");
  node.className = isError ? "error" : "";
  node.textContent = message;
  target.append(node);
}

function setBusy(button, busy, busyText = "Working…") {
  if (busy) {
    button.dataset.originalText = button.textContent;
    button.textContent = busyText;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.originalText || button.textContent;
    button.disabled = false;
  }
}

function addEvidenceCard(container, {title, badge, text, metadata}) {
  const card = document.createElement("article");
  card.className = "evidence";
  const top = document.createElement("div");
  top.className = "evidence-top";
  const heading = document.createElement("div");
  heading.className = "evidence-title";
  heading.textContent = title;
  const tag = document.createElement("span");
  tag.className = "badge";
  tag.textContent = badge;
  top.append(heading, tag);
  const passage = document.createElement("div");
  passage.className = "evidence-text";
  passage.textContent = text;
  const meta = document.createElement("div");
  meta.className = "evidence-meta";
  meta.textContent = metadata;
  card.append(top, passage, meta);
  container.append(card);
}

async function checkHealth() {
  const dot = $("#health-dot");
  try {
    const health = await apiRequest("/health");
    dot.className = "status-dot ok";
    $("#health-title").textContent = "API connected";
    $("#health-detail").textContent = `Service ${health.service} · v${health.version}`;
  } catch (error) {
    dot.className = "status-dot bad";
    $("#health-title").textContent = "API unavailable";
    $("#health-detail").textContent = "Check that the server is running.";
  }
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item === tab));
    document.querySelectorAll(".panel").forEach((panel) => panel.classList.toggle("active", panel.id === `panel-${tab.dataset.panel}`));
  });
});

$("#document-upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type=submit]");
  const target = $("#document-upload-result");
  const file = $("#document-file").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  setBusy(button, true, "Uploading…");
  setMessage(target, "Uploading and extracting text locally…");
  try {
    const body = await apiRequest("/api/v1/documents/upload", {method: "POST", body: form});
    const doc = body.document;
    target.replaceChildren();
    const line = document.createElement("p");
    const strong = document.createElement("strong");
    strong.textContent = "Upload successful";
    line.append(strong, document.createTextNode(` — ${doc.filename}`));
    const id = document.createElement("p");
    id.textContent = `Document ID: ${doc.document_id}`;
    const hint = document.createElement("p");
    hint.textContent = "You can now search for terms in this document.";
    target.append(line, id, hint);
  } catch (error) {
    setMessage(target, error.message, true);
  } finally {
    setBusy(button, false);
  }
});

$("#document-search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type=submit]");
  const target = $("#document-search-results");
  target.replaceChildren();
  setBusy(button, true, "Searching…");
  try {
    const body = await apiRequest("/api/v1/search/evidence", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({query: $("#document-query").value.trim(), top_k: Number($("#document-top-k").value)})
    });
    if (!body.results.length) {
      setMessage(target, "No matching evidence was found in stored documents. This does not prove the topic is absent.");
    } else {
      const summary = document.createElement("p");
      summary.className = "muted";
      summary.textContent = `Found ${body.total_matches} matching passage(s); showing ${body.results.length}.`;
      target.append(summary);
      body.results.forEach((item) => addEvidenceCard(target, {
        title: item.filename, badge: `Page ${item.page_number} · score ${Number(item.score).toFixed(2)}`,
        text: item.text,
        metadata: `Document ID: ${item.document_id} · Chunk ${item.chunk_index} · Matched terms: ${item.matched_terms.join(", ")}`
      }));
    }
  } catch (error) {
    setMessage(target, error.message, true);
  } finally {
    setBusy(button, false);
  }
});

$("#media-upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type=submit]");
  const target = $("#media-upload-result");
  const file = $("#media-file").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  setBusy(button, true, "Uploading…");
  setMessage(target, "Validating and saving media…");
  try {
    const body = await apiRequest("/api/v1/media/upload", {method: "POST", body: form});
    const media = body.media;
    $("#media-id").value = media.media_id;
    target.replaceChildren();
    const success = document.createElement("p");
    success.textContent = `Upload successful: ${media.filename}`;
    const id = document.createElement("p");
    id.textContent = `Media ID: ${media.media_id}`;
    const hint = document.createElement("p");
    hint.textContent = "The Media ID has been copied into the transcription form below.";
    target.append(success, id, hint);
  } catch (error) {
    setMessage(target, error.message, true);
  } finally {
    setBusy(button, false);
  }
});

$("#transcribe-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type=submit]");
  const target = $("#transcribe-result");
  const mediaId = $("#media-id").value.trim();
  const language = $("#language").value;
  if (!mediaId) return;
  setBusy(button, true, "Transcribing…");
  setMessage(target, "Transcription can take time on CPU. Keep this page open.");
  try {
    const params = new URLSearchParams();
    if (language) params.set("language", language);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const body = await apiRequest(`/api/v1/media/${encodeURIComponent(mediaId)}/transcribe${suffix}`, {method: "POST"});
    target.replaceChildren();
    const summary = document.createElement("p");
    summary.textContent = `Transcription saved · Language: ${body.language || "unknown"} · Duration: ${body.duration_seconds ?? "unknown"} seconds · Segments: ${body.segments.length}`;
    const transcript = document.createElement("p");
    transcript.className = "evidence-text";
    transcript.textContent = body.full_text || "No transcript text was returned.";
    target.append(summary, transcript);
  } catch (error) {
    setMessage(target, error.message, true);
  } finally {
    setBusy(button, false);
  }
});

$("#media-search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type=submit]");
  const target = $("#media-search-results");
  target.replaceChildren();
  setBusy(button, true, "Searching…");
  try {
    const body = await apiRequest("/api/v1/search/media-evidence", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({query: $("#media-query").value.trim(), top_k: Number($("#media-top-k").value)})
    });
    if (!body.results.length) {
      setMessage(target, "No matching transcript segments were found. Upload and transcribe media first, and remember that no match does not prove a topic was not discussed.");
    } else {
      const summary = document.createElement("p");
      summary.className = "muted";
      summary.textContent = `Found ${body.total_matches} matching segment(s); showing ${body.results.length}. Verify each timestamp against the original recording.`;
      target.append(summary);
      body.results.forEach((item) => addEvidenceCard(target, {
        title: item.filename,
        badge: `${Number(item.start_seconds).toFixed(1)}s–${Number(item.end_seconds).toFixed(1)}s · score ${Number(item.score).toFixed(2)}`,
        text: item.text,
        metadata: `Media ID: ${item.media_id} · Segment ${item.segment_index} · Matched terms: ${item.matched_terms.join(", ")}`
      }));
    }
  } catch (error) {
    setMessage(target, error.message, true);
  } finally {
    setBusy(button, false);
  }
});

checkHealth();
