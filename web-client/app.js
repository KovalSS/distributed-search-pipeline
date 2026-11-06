const badgeServer = document.getElementById('badge-server');
const badgeOllama = document.getElementById('badge-ollama');
const badgeIndex = document.getElementById('badge-index');
const noIndexAlert = document.getElementById('no-index-alert');

const tabBtns = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

const searchForm = document.getElementById('search-form');
const queryInput = document.getElementById('query-input');
const modeSelect = document.getElementById('mode-select');
const topInput = document.getElementById('top-input');
const searchBtn = document.getElementById('search-btn');
const statusLine = document.getElementById('status-line');

const expansionSection = document.getElementById('expansion-section');
const expansionChips = document.getElementById('expansion-chips');
const resultsSection = document.getElementById('results-section');
const resultsHeading = document.getElementById('results-heading');
const resultsList = document.getElementById('results-list');

const indexForm = document.getElementById('index-form');
const threadsInput = document.getElementById('threads-input');
const buildIndexBtn = document.getElementById('build-index-btn');
const indexProgress = document.getElementById('index-progress');
const indexProgressText = document.getElementById('index-progress-text');
const indexResultAlert = document.getElementById('index-result-alert');
const benchmarkTbody = document.getElementById('benchmark-tbody');
const noHistoryRow = document.getElementById('no-history-row');

const documentModal = document.getElementById('document-modal');
const modalCloseBtn = document.getElementById('modal-close-btn');
const modalDocId = document.getElementById('modal-doc-id');
const modalCopyBtn = document.getElementById('modal-copy-btn');
const modalCopyStatus = document.getElementById('modal-copy-status');
const modalJsonCode = document.getElementById('modal-json-code');

let currentDocuments = 0;
let websocket = null;
let benchmarkCounter = 0;
let currentModalJson = '';
let currentSearchMode = 'expanded';

function getBaseHttpUrl() {
  if (window.location.protocol === 'http:' || window.location.protocol === 'https:') {
    return `${window.location.protocol}//${window.location.host}`;
  }
  return 'http://localhost:8080';
}

function getWebSocketUrl() {
  if (window.location.protocol === 'http:' || window.location.protocol === 'https:') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws/search`;
  }
  return 'ws://localhost:8080/ws/search';
}

tabBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    tabBtns.forEach(b => b.classList.remove('active'));
    tabContents.forEach(c => c.classList.remove('active'));

    btn.classList.add('active');
    const target = document.getElementById(btn.dataset.tab);
    if (target) target.classList.add('active');
  });
});

async function checkSystemHealth() {
  const baseUrl = getBaseHttpUrl();

  try {
    const res = await fetch(`${baseUrl}/api/health`);
    if (res.ok) {
      const data = await res.json();
      badgeServer.textContent = 'Server: Online';
      badgeServer.className = 'status-item online';

      if (data.ollama) {
        badgeOllama.textContent = 'Ollama: Ready';
        badgeOllama.className = 'status-item online';
      } else {
        badgeOllama.textContent = 'Ollama: Offline';
        badgeOllama.className = 'status-item offline';
      }
    } else {
      throw new Error();
    }
  } catch {
    badgeServer.textContent = 'Server: Offline';
    badgeServer.className = 'status-item offline';
    badgeOllama.textContent = 'Ollama: Unknown';
    badgeOllama.className = 'status-item offline';
  }

  try {
    const res = await fetch(`${baseUrl}/api/stats`);
    if (res.ok) {
      const stats = await res.json();
      currentDocuments = stats.documents || 0;

      if (currentDocuments > 0) {
        badgeIndex.textContent = `Index: ${currentDocuments.toLocaleString()} docs`;
        badgeIndex.className = 'status-item online';
        noIndexAlert.hidden = true;
      } else {
        badgeIndex.textContent = 'Index: 0 docs';
        badgeIndex.className = 'status-item offline';
        noIndexAlert.hidden = false;
      }
    }
  } catch {
    badgeIndex.textContent = 'Index: Error';
    badgeIndex.className = 'status-item offline';
  }
}

function resetSearchUi() {
  statusLine.textContent = '';
  statusLine.classList.remove('error');

  expansionSection.hidden = true;
  expansionChips.innerHTML = '';

  resultsSection.hidden = true;
  resultsList.innerHTML = '';
}

function showSearchError(message) {
  statusLine.textContent = message;
  statusLine.classList.add('error');
  searchBtn.disabled = false;
}

function displayExpansion(data) {
  const terms = data.expanded_terms || [];
  if (terms.length === 0) return;

  expansionChips.innerHTML = '';
  terms.forEach(term => {
    const tag = document.createElement('span');
    tag.className = 'expansion-tag';
    tag.textContent = term;
    expansionChips.appendChild(tag);
  });

  expansionSection.hidden = false;
}

function openDocumentModal(docId, rawData) {
  modalDocId.textContent = `ID: ${docId}`;
  currentModalJson = typeof rawData === 'string' ? rawData : JSON.stringify(rawData, null, 2);
  modalJsonCode.textContent = currentModalJson;
  modalCopyStatus.hidden = true;
  documentModal.hidden = false;
}

function closeDocumentModal() {
  documentModal.hidden = true;
  currentModalJson = '';
}

modalCloseBtn.addEventListener('click', closeDocumentModal);

documentModal.addEventListener('click', (e) => {
  if (e.target === documentModal) {
    closeDocumentModal();
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !documentModal.hidden) {
    closeDocumentModal();
  }
});

modalCopyBtn.addEventListener('click', () => {
  if (!currentModalJson) return;
  navigator.clipboard.writeText(currentModalJson).then(() => {
    modalCopyStatus.hidden = false;
    setTimeout(() => {
      modalCopyStatus.hidden = true;
    }, 2000);
  });
});

function displayResults(data) {
  const results = data.results || [];
  const timeMs = data.time_ms || 0;

  resultsHeading.textContent = `Found ${results.length} results (${timeMs} ms):`;
  resultsList.innerHTML = '';

  if (results.length === 0) {
    const emptyMsg = document.createElement('p');
    emptyMsg.className = 'empty-message';
    emptyMsg.textContent = 'No results found for this query.';
    resultsList.appendChild(emptyMsg);
    resultsSection.hidden = false;
    return;
  }

  results.forEach(item => {
    const card = document.createElement('div');
    card.className = 'result-card';

    const info = document.createElement('div');
    info.className = 'result-info';

    const titleText = (item.raw && item.raw.title) || item.snippet || '(No product title)';
    const docIdText = (item.raw && (item.raw.parent_asin || item.raw.asin)) || item.doc_id;

    const title = document.createElement('div');
    title.className = 'result-title';
    title.textContent = titleText;

    const meta = document.createElement('div');
    meta.className = 'result-meta';
    meta.textContent = `ID: ${docIdText} • Score: ${Number(item.score).toFixed(1)}`;

    info.appendChild(title);
    info.appendChild(meta);

    const actions = document.createElement('div');
    actions.className = 'result-actions';

    const viewBtn = document.createElement('button');
    viewBtn.type = 'button';
    viewBtn.className = 'btn-view';
    viewBtn.textContent = 'View JSON';
    viewBtn.addEventListener('click', () => {
      openDocumentModal(docIdText, item.raw || { doc_id: item.doc_id, title: titleText, score: item.score });
    });

    actions.appendChild(viewBtn);

    card.appendChild(info);
    card.appendChild(actions);
    resultsList.appendChild(card);
  });

  resultsSection.hidden = false;
}

function performSearch(query, top, mode = 'expanded') {
  currentSearchMode = mode;
  resetSearchUi();

  if (currentDocuments === 0) {
    showSearchError("Index is empty (0 documents). Go to the \"Indexing & Benchmarks\" tab to build it.");
    return;
  }

  searchBtn.disabled = true;
  statusLine.textContent = 'Connecting...';

  const wsUrl = getWebSocketUrl();

  try {
    websocket = new WebSocket(wsUrl);
  } catch (err) {
    showSearchError('WebSocket initialization failed: ' + err.message);
    return;
  }

  websocket.onopen = () => {
    if (mode === 'keyword') {
      statusLine.textContent = 'Searching index (Keyword mode)...';
    } else {
      statusLine.textContent = 'Expanding query with Ollama...';
    }
    websocket.send(JSON.stringify({ query: query, mode: mode, top: top }));
  };

  websocket.onmessage = (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch {
      showSearchError('Invalid JSON from server.');
      return;
    }

    if (payload.stage === 'error') {
      showSearchError(payload.message || 'Search error');
      websocket.close();
      return;
    }

    if (payload.stage === 'query_expansion') {
      if (currentSearchMode === 'keyword') {
        expansionSection.hidden = true;
        expansionChips.innerHTML = '';
      } else {
        statusLine.textContent = 'Searching index...';
        displayExpansion(payload.data);
      }
    } else if (payload.stage === 'keyword_search') {
      displayResults(payload.data);
    } else if (payload.stage === 'done') {
      statusLine.textContent = '';
      searchBtn.disabled = false;
      websocket.close();
    }
  };

  websocket.onerror = () => {
    showSearchError(`Connection error (${wsUrl}).`);
  };

  websocket.onclose = (event) => {
    searchBtn.disabled = false;
    if (event.code !== 1000 && !statusLine.classList.contains('error')) {
      showSearchError(`Connection closed (${event.code})`);
    }
  };
}

searchForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const query = queryInput.value.trim();
  if (!query) return;

  const top = parseInt(topInput.value, 10) || 5;
  const mode = modeSelect ? modeSelect.value : 'expanded';

  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.close();
  }

  performSearch(query, top, mode);
});

indexForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  const threads = parseInt(threadsInput.value, 10) || 1;
  const baseUrl = getBaseHttpUrl();

  buildIndexBtn.disabled = true;
  indexResultAlert.hidden = true;
  indexProgress.hidden = false;

  const startTime = Date.now();
  const timerInterval = setInterval(() => {
    const elapsedSec = ((Date.now() - startTime) / 1000).toFixed(1);
    indexProgressText.textContent = `Indexing with ${threads} threads... ${elapsedSec} s`;
  }, 100);

  try {
    const response = await fetch(`${baseUrl}/api/index`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ threads: threads })
    });

    clearInterval(timerInterval);
    indexProgress.hidden = true;
    buildIndexBtn.disabled = false;

    if (!response.ok) {
      throw new Error(`HTTP error: ${response.status}`);
    }

    const data = await response.json();
    const timeMs = data.time_ms || 0;
    const timeSec = (timeMs / 1000).toFixed(2);
    const docs = data.documents_indexed || 0;

    indexResultAlert.textContent = `Indexed ${docs.toLocaleString()} documents in ${timeMs} ms (${timeSec} s) using ${threads} threads.`;
    indexResultAlert.hidden = false;

    if (noHistoryRow && noHistoryRow.parentNode) {
      noHistoryRow.remove();
    }

    benchmarkCounter++;
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${benchmarkCounter}</td>
      <td><strong>${threads}</strong></td>
      <td>${docs.toLocaleString()}</td>
      <td>${timeMs}</td>
      <td>${timeSec} s</td>
    `;
    benchmarkTbody.prepend(row);

    checkSystemHealth();
  } catch (err) {
    clearInterval(timerInterval);
    indexProgress.hidden = true;
    buildIndexBtn.disabled = false;
    alert('Index build failed: ' + err.message);
  }
});

checkSystemHealth();
setInterval(checkSystemHealth, 5000);