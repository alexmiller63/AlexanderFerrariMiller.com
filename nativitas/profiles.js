(() => {
  'use strict';
  const key = 'nativitas.birthProfiles.v1';
  const listeners = new Set();
  function valid(p) {
    if (!p || typeof p.id !== 'string' || !p.id || typeof p.name !== 'string' || !p.name.trim() || p.name.length > 80) return false;
    if (typeof p.city !== 'string' || p.city.length > 200 || typeof p.unknown !== 'boolean') return false;
    if (typeof p.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(p.date) || p.date < '1900-01-01' || p.date > '2099-12-31') return false;
    const day = new Date(p.date + 'T12:00:00Z');
    if (!Number.isFinite(+day) || day.toISOString().slice(0,10) !== p.date) return false;
    if (typeof p.time !== 'string' || (!p.unknown && !/^([01]\d|2[0-3]):[0-5]\d$/.test(p.time))) return false;
    if (typeof p.zone !== 'string' || typeof p.occurrence !== 'string') return false;
    try { new Intl.DateTimeFormat('en', {timeZone:p.zone}); } catch { return false; }
    return [['latitude',-90,90],['longitude',-180,180],['elevation',-500,10000]].every(([k,min,max]) =>
      typeof p[k] === 'number' && Number.isFinite(p[k]) && p[k] >= min && p[k] <= max);
  }
  function readStore() {
    let raw;
    try { raw = localStorage.getItem(key); }
    catch { throw Error('Device storage is unavailable. Profiles cannot be saved here; you can still use the birth forms.'); }
    if (raw === null) return [];
    let data;
    try { data = JSON.parse(raw); } catch { throw Error('Saved profiles could not be read. Existing data has been left unchanged.'); }
    if (!data || data.version !== 1 || !Array.isArray(data.profiles) || !data.profiles.every(valid) || new Set(data.profiles.map(p=>p.id)).size !== data.profiles.length)
      throw Error('Saved profiles could not be read. Existing data has been left unchanged.');
    return data.profiles;
  }
  function writeStore(profiles) {
    try { localStorage.setItem(key, JSON.stringify({version:1, profiles})); }
    catch { throw Error('The profile could not be saved. Device storage may be full or unavailable.'); }
    listeners.forEach(refresh=>refresh());
  }
  function attach({container, read, apply, validate, isBusy = () => false}) {
    const panel = document.createElement('fieldset');
    panel.className = 'birth-profiles';
    panel.innerHTML = `<legend>Saved profiles</legend>
      <p class="profile-note">Saved only in this browser or Home Screen app on this device. Clearing its website data erases profiles. Profiles do not sync between devices.</p>
      <label>Choose a profile<select class="profile-select"><option value="">Choose a saved profile</option></select></label>
      <label>Profile name<input class="profile-name" maxlength="80" autocomplete="off" placeholder="Name or label"></label>
      <div class="profile-actions"><button type="button" class="profile-new">Save as new</button><button type="button" class="profile-update" disabled>Update selected</button><button type="button" class="profile-delete" disabled>Delete selected</button></div>
      <p class="profile-status" role="status" aria-live="polite"></p>`;
    if (container.firstElementChild?.tagName === 'LEGEND') container.firstElementChild.after(panel);
    else container.prepend(panel);
    const select = panel.querySelector('select'), name = panel.querySelector('input'), status = panel.querySelector('.profile-status');
    const update = panel.querySelector('.profile-update'), remove = panel.querySelector('.profile-delete');
    function refresh() {
      try {
        const previous = select.value, profiles = readStore();
        select.replaceChildren(new Option('Choose a saved profile', ''));
        for (const p of profiles) select.append(new Option(`${p.name} · ${p.date}`, p.id));
        select.value = profiles.some(p=>p.id===previous) ? previous : '';
        update.disabled = remove.disabled = !select.value;
      } catch (error) { status.textContent = error.message; }
    }
    function act(action) {
      if (isBusy()) { status.textContent = 'Wait for the calculation to finish, or cancel it first.'; return; }
      try { action(); } catch (error) { status.textContent = error.message; }
    }
    select.addEventListener('change', () => act(() => {
      const profile = readStore().find(p=>p.id===select.value);
      update.disabled = remove.disabled = !profile;
      if (!profile) return;
      apply(profile);
      name.value = profile.name;
      status.textContent = `Loaded ${profile.name}. Generate a chart or comparison to use these details.`;
    }));
    function save(replace) {
      const profileName = name.value.trim();
      if (!profileName) { name.focus(); throw Error('Enter a profile name.'); }
      validate();
      const profiles = readStore(), index = profiles.findIndex(p=>p.id===select.value);
      if (replace && index < 0) throw Error('Select an existing profile to update.');
      const profile = {...read(), name:profileName, id:replace ? profiles[index].id : crypto.randomUUID()};
      if (!valid(profile)) throw Error('Check the profile name and birth details before saving.');
      if (replace) profiles[index] = profile; else profiles.push(profile);
      writeStore(profiles);
      select.value = profile.id;
      update.disabled = remove.disabled = false;
      status.textContent = `${profile.name} ${replace ? 'updated' : 'saved'} on this device.`;
    }
    panel.querySelector('.profile-new').addEventListener('click', () => act(()=>save(false)));
    update.addEventListener('click', () => act(()=>save(true)));
    remove.addEventListener('click', () => act(() => {
      const profiles = readStore(), profile = profiles.find(p=>p.id===select.value);
      if (!profile) throw Error('Select a profile to delete.');
      if (!window.confirm(`Delete the saved profile “${profile.name}” from this device?`)) return;
      writeStore(profiles.filter(p=>p.id!==profile.id));
      name.value = '';
      status.textContent = `${profile.name} deleted. The current birth details remain in the form.`;
    }));
    listeners.add(refresh);
    refresh();
    return panel;
  }
  window.addEventListener('storage', event => { if (event.key === key || event.key === null) listeners.forEach(refresh=>refresh()); });
  window.NativitasProfiles = {attach};
})();
