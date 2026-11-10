const $ = (id) => document.getElementById(id);

let pollTimer = null;

const SEED_TEMPLATES = {
  experience: () => `
    <div class="seed-card" data-kind="experience">
      <div class="seed-card-head"><span>Position</span><button type="button" class="icon-x" data-remove aria-label="Remove">&times;</button></div>
      <div class="row-2">
        <div><label>Company</label><input data-field="company" placeholder="Siemens" /></div>
        <div><label>Title</label><input data-field="title" placeholder="Controls engineer" /></div>
      </div>
      <div class="row-3">
        <div><label>Start</label><input data-field="start" placeholder="2014" /></div>
        <div><label>End</label><input data-field="end" placeholder="2019" /></div>
        <div><label>Location</label><input data-field="location" placeholder="Detroit, MI" /></div>
      </div>
      <label>Highlights (one per line)</label>
      <textarea data-field="bullets" placeholder="Commissioned 12 robot cells"></textarea>
    </div>`,
  education: () => `
    <div class="seed-card" data-kind="education">
      <div class="seed-card-head"><span>School</span><button type="button" class="icon-x" data-remove aria-label="Remove">&times;</button></div>
      <div class="row-2">
        <div><label>School</label><input data-field="school" placeholder="Georgia Institute of Technology" /></div>
        <div><label>Degree</label><input data-field="degree" placeholder="BSc" /></div>
      </div>
      <div class="row-3">
        <div><label>Field</label><input data-field="field" placeholder="Electrical Engineering" /></div>
        <div><label>Start</label><input data-field="start" placeholder="2010" /></div>
        <div><label>End</label><input data-field="end" placeholder="2014" /></div>
      </div>
      <label>Details (one per line)</label>
      <textarea data-field="details" placeholder="Controls concentration"></textarea>
    </div>`,
  licenses: () => `
    <div class="seed-card" data-kind="licenses">
      <div class="seed-card-head"><span>License</span><button type="button" class="icon-x" data-remove aria-label="Remove">&times;</button></div>
      <div class="row-3">
        <div><label>Name</label><input data-field="name" placeholder="Professional Engineer (PE)" /></div>
        <div><label>Issuer</label><input data-field="issuer" placeholder="NCEES / state board" /></div>
        <div><label>Year</label><input data-field="year" placeholder="2018" /></div>
      </div>
    </div>`,
  certifications: () => `
    <div class="seed-card" data-kind="certifications">
      <div class="seed-card-head"><span>Certification</span><button type="button" class="icon-x" data-remove aria-label="Remove">&times;</button></div>
      <div class="row-3">
        <div><label>Name</label><input data-field="name" placeholder="PMP" /></div>
        <div><label>Issuer</label><input data-field="issuer" placeholder="PMI" /></div>
        <div><label>Year</label><input data-field="year" placeholder="2020" /></div>
      </div>
    </div>`,
  skills: () => `
    <div class="seed-card" data-kind="skills">
      <div class="seed-card-head"><span>Skill</span><button type="button" class="icon-x" data-remove aria-label="Remove">&times;</button></div>
      <input data-field="skill" placeholder="Safety PLCs" />
    </div>`,
  languages: () => `
    <div class="seed-card" data-kind="languages">
      <div class="seed-card-head"><span>Language</span><button type="button" class="icon-x" data-remove aria-label="Remove">&times;</button></div>
      <div class="row-2">
        <div><label>Language</label><input data-field="name" placeholder="English" /></div>
        <div><label>Level</label><input data-field="level" placeholder="Native / Professional" /></div>
      </div>
    </div>`,
  projects: () => `
    <div class="seed-card" data-kind="projects">
      <div class="seed-card-head"><span>Project</span><button type="button" class="icon-x" data-remove aria-label="Remove">&times;</button></div>
      <label>Name</label>
      <input data-field="name" placeholder="Cell safety retrofit" />
      <label>Description</label>
      <textarea data-field="description" placeholder="Documented a lockout design used on 12 cells."></textarea>
      <label>Skills (comma-separated)</label>
      <input data-field="skills" placeholder="PLC, lockout, FANUC" />
    </div>`,
};

function listEl(kind) {
  return $(`${kind}List`);
}

function addSeedCard(kind) {
  const host = listEl(kind);
  const tpl = SEED_TEMPLATES[kind];
  if (!host || !tpl) return;
  const wrap = document.createElement('div');
  wrap.innerHTML = tpl().trim();
  const card = wrap.firstElementChild;
  card.querySelector('[data-remove]').onclick = () => card.remove();
  host.appendChild(card);
}

function fieldValue(card, name) {
  const el = card.querySelector(`[data-field="${name}"]`);
  return el ? String(el.value || '').trim() : '';
}

function lines(text) {
  return String(text || '')
    .split(/\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function collectProfileSeed() {
  const seed = {};
  const location = $('location').value.trim();
  const headline = $('headline').value.trim();
  const about = $('about').value.trim();
  if (location) seed.location = location;
  if (headline) seed.headline = headline;
  if (about) seed.about = about;

  const experience = [];
  listEl('experience').querySelectorAll('.seed-card').forEach((card) => {
    const entry = {
      company: fieldValue(card, 'company'),
      title: fieldValue(card, 'title'),
      start: fieldValue(card, 'start'),
      end: fieldValue(card, 'end'),
      location: fieldValue(card, 'location'),
      bullets: lines(fieldValue(card, 'bullets')),
    };
    if (Object.values(entry).some((v) => (Array.isArray(v) ? v.length : v))) {
      experience.push(Object.fromEntries(Object.entries(entry).filter(([, v]) => (Array.isArray(v) ? v.length : v))));
    }
  });
  if (experience.length) seed.experience = experience;

  const education = [];
  listEl('education').querySelectorAll('.seed-card').forEach((card) => {
    const entry = {
      school: fieldValue(card, 'school'),
      degree: fieldValue(card, 'degree'),
      field: fieldValue(card, 'field'),
      start: fieldValue(card, 'start'),
      end: fieldValue(card, 'end'),
      details: lines(fieldValue(card, 'details')),
    };
    if (Object.values(entry).some((v) => (Array.isArray(v) ? v.length : v))) {
      education.push(Object.fromEntries(Object.entries(entry).filter(([, v]) => (Array.isArray(v) ? v.length : v))));
    }
  });
  if (education.length) seed.education = education;

  const licenses = [];
  listEl('licenses').querySelectorAll('.seed-card').forEach((card) => {
    const entry = {
      name: fieldValue(card, 'name'),
      issuer: fieldValue(card, 'issuer'),
      year: fieldValue(card, 'year'),
    };
    if (Object.values(entry).some(Boolean)) {
      licenses.push(Object.fromEntries(Object.entries(entry).filter(([, v]) => v)));
    }
  });
  if (licenses.length) seed.licenses = licenses;

  const certifications = [];
  listEl('certifications').querySelectorAll('.seed-card').forEach((card) => {
    const entry = {
      name: fieldValue(card, 'name'),
      issuer: fieldValue(card, 'issuer'),
      year: fieldValue(card, 'year'),
    };
    if (Object.values(entry).some(Boolean)) {
      certifications.push(Object.fromEntries(Object.entries(entry).filter(([, v]) => v)));
    }
  });
  if (certifications.length) seed.certifications = certifications;

  const skills = [];
  listEl('skills').querySelectorAll('.seed-card').forEach((card) => {
    const skill = fieldValue(card, 'skill');
    if (skill) skills.push(skill);
  });
  if (skills.length) seed.skills = skills;

  const languages = [];
  listEl('languages').querySelectorAll('.seed-card').forEach((card) => {
    const entry = {
      name: fieldValue(card, 'name'),
      level: fieldValue(card, 'level'),
    };
    if (Object.values(entry).some(Boolean)) {
      languages.push(Object.fromEntries(Object.entries(entry).filter(([, v]) => v)));
    }
  });
  if (languages.length) seed.languages = languages;

  const projects = [];
  listEl('projects').querySelectorAll('.seed-card').forEach((card) => {
    const skillsText = fieldValue(card, 'skills');
    const entry = {
      name: fieldValue(card, 'name'),
      description: fieldValue(card, 'description'),
      skills: skillsText.split(/[,;]+/).map((s) => s.trim()).filter(Boolean),
    };
    if (Object.values(entry).some((v) => (Array.isArray(v) ? v.length : v))) {
      projects.push(Object.fromEntries(Object.entries(entry).filter(([, v]) => (Array.isArray(v) ? v.length : v))));
    }
  });
  if (projects.length) seed.projects = projects;

  return seed;
}

async function api(path, opts = {}) {
  const res = await chrome.runtime.sendMessage({
    type: 'api',
    path,
    method: opts.method || 'GET',
    body: opts.body,
  });
  if (!res) {
    return { status: 0, data: { ok: false, error: 'Extension worker did not answer. Reload the extension.' } };
  }
  return res;
}

function setBridgeUi(st) {
  const connected = !!st.connected;
  const waiting = !!st.waitingForBridge && !connected;
  $('dot').className = 'dot ' + (connected ? 'ok' : waiting ? 'wait' : 'bad');
  if (connected) {
    $('status').textContent = 'Browser session ready';
  } else if (waiting) {
    $('status').textContent = 'Waiting for bridge…';
  } else {
    $('status').textContent = st.error || 'Not connected';
  }
  const bits = [];
  if (st.current) bits.push(`Running ${st.current.provider}`);
  bits.push(`${st.jobsDone || 0} bridge jobs`);
  if (!connected) {
    bits.push('Run jt bridge serve, then reload this panel');
  }
  $('detail').textContent = bits.join(' · ');
}

async function refreshBridge() {
  try {
    const st = await chrome.runtime.sendMessage({ type: 'getState' });
    setBridgeUi(st || {});
  } catch (_) {
    setBridgeUi({ connected: false, error: 'Extension worker asleep — click Build to wake it.' });
  }
}

async function refreshStatus() {
  await chrome.runtime.sendMessage({ type: 'reconnect' }).catch(() => {});
  await refreshBridge();
  try {
    const { data } = await api('/api/status');
    if (data.error && !data.engine) {
      $('detail').textContent = data.error;
      return;
    }
    if (data.engine) $('engine').value = data.engine;
    if (data.browser) $('browser').value = data.browser;
    if (data.suggest_seed_mode) {
      $('useProvided').checked = data.suggest_seed_mode === 'provided';
    }
    if (data.auth_required) {
      $('detail').textContent = 'Bridge up, but token missing — wait a second or reload the extension.';
    }
  } catch (e) {
    $('detail').textContent = String(e.message || e);
  }
}

async function savePrefs() {
  const { data } = await api('/api/prefs', {
    method: 'POST',
    body: JSON.stringify({
      engine: $('engine').value,
      browser: $('browser').value,
      suggest_seed_mode: $('useProvided').checked ? 'provided' : 'last_company',
    }),
  });
  if (!data.ok) {
    $('jobStatus').className = 'hint bad';
    $('jobStatus').textContent = data.error || 'Could not save settings';
    return;
  }
  await chrome.storage.local.set({ preferredBrowser: $('browser').value });
  $('jobStatus').className = 'hint ok';
  $('jobStatus').textContent = 'Settings saved.';
}

function setBusy(busy) {
  $('build').disabled = busy;
  $('savePrefs').disabled = busy;
}

async function pollJob(id) {
  clearInterval(pollTimer);
  const tick = async () => {
    const { data } = await api(`/api/jobs/${id}`);
    const job = data.job;
    if (!job) {
      $('jobStatus').className = 'hint bad';
      $('jobStatus').textContent = data.error || 'Job lost';
      setBusy(false);
      clearInterval(pollTimer);
      return;
    }
    if (job.status === 'queued' || job.status === 'running') {
      $('jobStatus').className = 'hint';
      $('jobStatus').textContent = `Building… (${job.status})`;
      return;
    }
    clearInterval(pollTimer);
    setBusy(false);
    if (job.status === 'done') {
      const paths = job.paths || {};
      $('jobStatus').className = 'hint ok';
      $('jobStatus').textContent =
        `Done: ${job.label || 'teaching profile'}\n` +
        (paths.profile ? `profile: ${paths.profile}\n` : '') +
        (paths.docx ? `resume: ${paths.docx}` : '');
      refreshBridge();
      return;
    }
    $('jobStatus').className = 'hint bad';
    $('jobStatus').textContent = job.error || `Failed (${job.code || job.status})`;
  };
  await tick();
  pollTimer = setInterval(tick, 1500);
}

async function build() {
  const name = $('name').value.trim();
  const company = $('company').value.trim();
  if (!name || !company) {
    $('jobStatus').className = 'hint bad';
    $('jobStatus').textContent = 'Add a name and a real last company.';
    return;
  }
  setBusy(true);
  $('jobStatus').className = 'hint';
  $('jobStatus').textContent = 'Connecting…';
  try {
    await chrome.runtime.sendMessage({ type: 'reconnect' }).catch(() => {});
    const seedMode = $('useProvided').checked ? 'provided' : 'last_company';
    const pref = await api('/api/prefs', {
      method: 'POST',
      body: JSON.stringify({
        engine: $('engine').value,
        browser: $('browser').value,
        suggest_seed_mode: seedMode,
      }),
    });
    if (!pref.data.ok) {
      throw new Error(pref.data.error || 'Could not save settings (is jt bridge serve running?)');
    }
    const provider = $('browser').value === 'claude' ? 'claude' : 'gpt';
    const needsBrowser = ['browser', 'claude', 'gpt', 'auto'].includes($('engine').value);
    if (needsBrowser) {
      $('jobStatus').textContent = 'Opening AI tab…';
      const opened = await chrome.runtime.sendMessage({
        type: 'ensureAiTab',
        provider,
        focus: true,
      });
      if (opened && opened.ok === false) {
        throw new Error(opened.error || 'Could not open AI tab');
      }
    }
    $('jobStatus').textContent = 'Starting build…';
    const body = {
      name,
      last_company: company,
      title: $('title').value.trim(),
      notes: $('notes').value.trim(),
      jd: $('jd').value.trim(),
      seed_mode: seedMode,
    };
    if (seedMode === 'provided') {
      const profileSeed = collectProfileSeed();
      if (Object.keys(profileSeed).length) body.profile_seed = profileSeed;
    }
    const { data } = await api('/api/suggest', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    if (!data.ok || !data.id) {
      throw new Error(data.error || 'Suggest failed to start');
    }
    await pollJob(data.id);
  } catch (e) {
    setBusy(false);
    $('jobStatus').className = 'hint bad';
    $('jobStatus').textContent = String(e.message || e);
  }
}

$('savePrefs').onclick = () => savePrefs().catch((e) => {
  $('jobStatus').className = 'hint bad';
  $('jobStatus').textContent = String(e.message || e);
});
$('build').onclick = () => build();
$('openDashboard').onclick = () => {
  chrome.tabs.create({ url: 'http://localhost:8501', active: true });
};
document.querySelectorAll('[data-add]').forEach((btn) => {
  btn.onclick = () => addSeedCard(btn.getAttribute('data-add'));
});

(async () => {
  await refreshStatus();
  setInterval(refreshBridge, 2000);
})();
