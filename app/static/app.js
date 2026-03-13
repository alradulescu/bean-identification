/* ============================================================
   Bean Identification – Coffee Brewing Assistant – app.js
   ============================================================ */

'use strict';

// ----- Global state --------------------------------------------------------
let currentSessionId = null;

// ----- Helpers --------------------------------------------------------------

/**
 * Show/hide Bootstrap spinner inside a button and toggle its disabled state.
 */
function setLoading(btn, spinId, loading) {
  const spin = document.getElementById(spinId);
  if (spin) spin.classList.toggle('d-none', !loading);
  if (btn) btn.disabled = loading;
}

/** Populate a <table> element from a key-value object. */
function populateTable(tableId, data) {
  const table = document.getElementById(tableId);
  if (!table) return;
  table.innerHTML = '';
  Object.entries(data).forEach(([key, val]) => {
    if (val === null || val === undefined || val === '') return;
    const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    const row = table.insertRow();
    row.insertCell().textContent = label;
    const cell = row.insertCell();
    cell.textContent = Array.isArray(val) ? val.join(', ') : String(val);
  });
}

/** Render a recipe dict as HTML. */
function renderRecipe(recipe, containerId) {
  const el = document.getElementById(containerId);
  if (!el || !recipe) return;

  const secs = recipe.total_time_s;
  const mm = Math.floor(secs / 60);
  const ss = String(secs % 60).padStart(2, '0');
  const timeStr = `${mm}:${ss}`;

  let scheduleHtml = '';
  if (recipe.pour_schedule && recipe.pour_schedule.length) {
    scheduleHtml = '<h6 class="mt-3 mb-2">Pour Schedule</h6>';
    recipe.pour_schedule.forEach(step => {
      const start = fmtTime(step.start_s);
      const end = fmtTime(step.end_s);
      scheduleHtml += `
        <div class="pour-step">
          <span class="pour-step-number">Step ${step.step} – ${step.action}</span><br/>
          <span class="text-muted small">${step.notes} &nbsp;|&nbsp; ${start}–${end}</span>
        </div>`;
    });
  }

  let grinderHtml = '';
  if (recipe.grinder_settings && Object.keys(recipe.grinder_settings).length) {
    grinderHtml = '<h6 class="mt-3 mb-2">Grinder Settings</h6>';
    grinderHtml += '<table class="table table-sm table-bordered mb-0"><tbody>';
    Object.entries(recipe.grinder_settings).forEach(([grinder, setting]) => {
      grinderHtml += `<tr><td class="fw-semibold">${grinder}</td><td>${setting}</td></tr>`;
    });
    grinderHtml += '</tbody></table>';
    grinderHtml += '<p class="text-muted small mt-1 mb-0">Settings are approximate V60 pour-over starting points. Adjust to taste.</p>';
  }

  let adjustHtml = '';
  if (recipe.adjustments_made && recipe.adjustments_made.length) {
    adjustHtml = `<div class="alert alert-info mt-3 small">
      <strong>Adjustments applied:</strong> ${recipe.adjustments_made.join('; ')}
    </div>`;
  }

  el.innerHTML = `
    <div class="recipe-card mb-3">
      <div class="row g-3 text-center mb-3">
        <div class="col-6 col-md-3">
          <h6>Coffee</h6>
          <div class="recipe-value">${recipe.coffee_g}<span class="recipe-unit"> g</span></div>
        </div>
        <div class="col-6 col-md-3">
          <h6>Water</h6>
          <div class="recipe-value">${recipe.water_g}<span class="recipe-unit"> g</span></div>
        </div>
        <div class="col-6 col-md-3">
          <h6>Temp</h6>
          <div class="recipe-value">${recipe.water_temp_c}<span class="recipe-unit"> °C</span></div>
        </div>
        <div class="col-6 col-md-3">
          <h6>Target Time</h6>
          <div class="recipe-value">${timeStr}</div>
        </div>
      </div>
      <div class="row g-3 text-center mb-3">
        <div class="col-6 col-md-3">
          <h6>Ratio</h6>
          <div class="recipe-value" style="font-size:1.2rem">${recipe.ratio}</div>
        </div>
        <div class="col-6 col-md-3">
          <h6>Grind</h6>
          <div class="recipe-value" style="font-size:1.2rem">${recipe.grind_label}</div>
        </div>
        <div class="col-6 col-md-3">
          <h6>Grinder Clicks</h6>
          <div class="recipe-value">${recipe.grind_clicks}</div>
        </div>
        <div class="col-6 col-md-3">
          <h6>Bloom</h6>
          <div class="recipe-value" style="font-size:1.2rem">${recipe.bloom_water_g}g / ${recipe.bloom_time_s}s</div>
        </div>
      </div>
      ${recipe.notes ? `<p class="text-muted small mb-0">${recipe.notes}</p>` : ''}
      ${grinderHtml}
      ${scheduleHtml}
    </div>
    ${adjustHtml}`;
}

function fmtTime(secs) {
  const m = Math.floor(secs / 60);
  const s = String(secs % 60).padStart(2, '0');
  return `${m}:${s}`;
}

// Image preview helper
function setupImagePreview(fileInputId, previewContainerId, previewImgId) {
  const fileInput = document.getElementById(fileInputId);
  if (!fileInput) return;
  fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = e => {
      const container = document.getElementById(previewContainerId);
      const img = document.getElementById(previewImgId);
      if (container && img) {
        img.src = e.target.result;
        container.classList.remove('d-none');
      }
    };
    reader.readAsDataURL(file);
  });
}

// POST multipart/form-data to an endpoint
async function postImage(url, fieldName, file, extraFields = {}) {
  const fd = new FormData();
  fd.append(fieldName, file);
  Object.entries(extraFields).forEach(([k, v]) => fd.append(k, v));
  const resp = await fetch(url, { method: 'POST', body: fd });
  if (!resp.ok) {
    throw new Error(await parseApiError(resp));
  }
  return resp.json();
}

async function parseApiError(resp) {
  const contentType = (resp.headers.get('content-type') || '').toLowerCase();
  if (contentType.includes('application/json')) {
    const err = await resp.json().catch(() => ({}));
    if (err && typeof err.error === 'string' && err.error.trim()) {
      return err.error;
    }
  }

  if (resp.status === 413) {
    return 'Image is too large. Please upload a file smaller than 32 MB.';
  }
  if (resp.status === 415) {
    return 'Unsupported image format. Please use JPG, PNG, or WEBP.';
  }

  const raw = await resp.text().catch(() => '');
  const text = (raw || '').trim();
  if (text) {
    return text.slice(0, 200);
  }

  return `Request failed (HTTP ${resp.status})`;
}

// Switch to a tab by target id
function switchTab(targetId) {
  const btn = document.querySelector(`[data-bs-target="#${targetId}"]`);
  if (btn) btn.click();
}

/** Mark a step progress indicator as done or active. */
function setProgressStep(stepKey, state) {
  // state: 'active' | 'done' | ''
  const el = document.getElementById(`prog-${stepKey}`);
  if (!el) return;
  el.classList.remove('active', 'done');
  if (state) el.classList.add(state);
}

// ----- Step 1: Label --------------------------------------------------------

document.getElementById('btnAnalyseLabel').addEventListener('click', async () => {
  const file = document.getElementById('labelFile').files[0];
  if (!file) {
    alert('Please select a label image first.');
    return;
  }
  const btn = document.getElementById('btnAnalyseLabel');
  setLoading(btn, 'spinLabel', true);
  try {
    const result = await postImage('/api/analyze-label', 'label_image', file);
    currentSessionId = result.session_id;

    populateTable('labelTable', result.coffee_info);
    document.getElementById('labelResult').classList.remove('d-none');
    // Hide the introductory banner once a session is started
    document.getElementById('howItWorks').classList.add('d-none');
    setProgressStep('label', 'done');
    setProgressStep('beans', 'active');
  } catch (e) {
    alert('Error: ' + e.message);
  } finally {
    setLoading(btn, 'spinLabel', false);
  }
});

document.getElementById('btnNextToBeans').addEventListener('click', () => switchTab('step-beans'));

// ----- Step 2: Beans --------------------------------------------------------

document.getElementById('btnAnalyseBeans').addEventListener('click', async () => {
  if (!currentSessionId) {
    document.getElementById('noSessionWarning').classList.remove('d-none');
    return;
  }
  const file = document.getElementById('beansFile').files[0];
  if (!file) {
    alert('Please select a bean image first.');
    return;
  }
  const btn = document.getElementById('btnAnalyseBeans');
  setLoading(btn, 'spinBeans', true);
  try {
    const result = await postImage('/api/analyze-beans', 'bean_image', file, {
      session_id: currentSessionId,
    });
    populateTable('beansTable', result.bean_analysis);
    document.getElementById('beansResult').classList.remove('d-none');
    setProgressStep('beans', 'done');
    setProgressStep('grounds', 'active');
    // Show recipe if available
    if (result.recipe) {
      renderRecipe(result.recipe, 'recipeContent');
      document.getElementById('btnNextToFeedback').classList.remove('d-none');
    }
  } catch (e) {
    alert('Error: ' + e.message);
  } finally {
    setLoading(btn, 'spinBeans', false);
  }
});

document.getElementById('btnNextToGrounds').addEventListener('click', () => switchTab('step-grounds'));
document.getElementById('btnSkipToRecipe').addEventListener('click', async () => {
  // Ensure recipe is shown
  if (currentSessionId) {
    try {
      const resp = await fetch(`/api/recipe/${currentSessionId}`);
      const data = await resp.json();
      if (data.recipe) {
        renderRecipe(data.recipe, 'recipeContent');
        document.getElementById('btnNextToFeedback').classList.remove('d-none');
        setProgressStep('grounds', 'done');
        setProgressStep('recipe', 'active');
      }
    } catch (_) {}
  }
  switchTab('step-recipe');
});

// ----- Step 3: Grounds ------------------------------------------------------

document.getElementById('btnAnalyseGrounds').addEventListener('click', async () => {
  if (!currentSessionId) {
    alert('Please complete Step 1 first.');
    return;
  }
  const file = document.getElementById('groundsFile').files[0];
  if (!file) {
    alert('Please select a grounds image first.');
    return;
  }
  const btn = document.getElementById('btnAnalyseGrounds');
  setLoading(btn, 'spinGrounds', true);
  try {
    const result = await postImage('/api/analyze-grounds', 'grounds_image', file, {
      session_id: currentSessionId,
    });
    populateTable('groundsTable', result.ground_analysis);
    document.getElementById('groundsResult').classList.remove('d-none');
    setProgressStep('grounds', 'done');
    setProgressStep('recipe', 'active');
    if (result.recipe) {
      renderRecipe(result.recipe, 'recipeContent');
      document.getElementById('btnNextToFeedback').classList.remove('d-none');
    }
  } catch (e) {
    alert('Error: ' + e.message);
  } finally {
    setLoading(btn, 'spinGrounds', false);
  }
});

document.getElementById('btnNextToRecipe').addEventListener('click', () => switchTab('step-recipe'));

// ----- Step 4: Recipe (next) ------------------------------------------------

document.getElementById('btnNextToFeedback').addEventListener('click', () => {
  setProgressStep('recipe', 'done');
  setProgressStep('feedback', 'active');
  switchTab('step-feedback');
});

// ----- Step 5: Feedback -----------------------------------------------------

// Range sliders – live badge update
['fbAcidity', 'fbSweetness', 'fbBitterness', 'fbBody', 'fbOverall'].forEach(id => {
  const badgeMap = {
    fbAcidity: 'acidVal', fbSweetness: 'sweetVal',
    fbBitterness: 'bitterVal', fbBody: 'bodyVal', fbOverall: 'overallVal',
  };
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener('input', () => {
      const badge = document.getElementById(badgeMap[id]);
      if (badge) badge.textContent = el.value;
    });
  }
});

document.getElementById('feedbackForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!currentSessionId) {
    document.getElementById('noSessionFeedback').classList.remove('d-none');
    return;
  }
  const btn = e.target.querySelector('[type=submit]');
  setLoading(btn, 'spinFeedback', true);
  try {
    const body = {
      session_id: currentSessionId,
      extraction: document.getElementById('fbExtraction').value,
      acidity: document.getElementById('fbAcidity').value,
      sweetness: document.getElementById('fbSweetness').value,
      bitterness: document.getElementById('fbBitterness').value,
      body: document.getElementById('fbBody').value,
      overall: document.getElementById('fbOverall').value,
      notes: document.getElementById('fbNotes').value,
    };
    const resp = await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const result = await resp.json();
    if (!resp.ok) throw new Error(result.error || `HTTP ${resp.status}`);

    renderRecipe(result.adjusted_recipe, 'adjustedRecipeContent');
    document.getElementById('feedbackResult').classList.remove('d-none');
    setProgressStep('feedback', 'done');
    // Also update recipe tab
    renderRecipe(result.adjusted_recipe, 'recipeContent');
  } catch (err) {
    alert('Error: ' + err.message);
  } finally {
    setLoading(btn, 'spinFeedback', false);
  }
});

// ----- History --------------------------------------------------------------

async function loadHistory() {
  const container = document.getElementById('historyList');
  container.innerHTML = '<p class="text-muted">Loading…</p>';
  try {
    const resp = await fetch('/api/sessions');
    const sessions = await resp.json();
    if (!sessions.length) {
      container.innerHTML = '<p class="text-muted">No brewing sessions yet. Complete Steps 1–2 to create your first session.</p>';
      return;
    }
    container.innerHTML = sessions.map(s => {
      const date = new Date(s.created_at).toLocaleString();
      const origin = s.origin || '—';
      const roast = s.roast_level || '—';
      const recipe = s.recipe ? `${s.recipe.coffee_g}g / ${s.recipe.water_g}g @ ${s.recipe.water_temp_c}°C` : '—';
      return `<div class="history-item">
        <div class="d-flex justify-content-between align-items-center">
          <strong>${origin}</strong>
          <span class="badge bg-secondary">${roast}</span>
        </div>
        <div class="small text-muted">${date}</div>
        <div class="small mt-1">Recipe: ${recipe}</div>
        ${s.masl ? `<div class="small text-muted">MASL: ${s.masl}</div>` : ''}
        ${s.tasting_notes ? `<div class="small text-muted">Notes: ${s.tasting_notes}</div>` : ''}
      </div>`;
    }).join('');
  } catch (_) {
    container.innerHTML = '<p class="text-danger">Failed to load history.</p>';
  }
}

document.getElementById('btnRefreshHistory').addEventListener('click', loadHistory);
// Load history when switching to that tab
document.querySelector('[data-bs-target="#step-history"]').addEventListener('click', loadHistory);

// ----- Image previews -------------------------------------------------------

setupImagePreview('labelFile', 'labelPreview', 'labelImg');
setupImagePreview('beansFile', 'beansPreview', 'beansImg');
setupImagePreview('groundsFile', 'groundsPreview', 'groundsImg');

// ----- Initial progress state -----------------------------------------------
setProgressStep('label', 'active');
