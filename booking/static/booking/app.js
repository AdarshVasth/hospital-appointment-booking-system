const content = document.querySelector("#content");
const nav = document.querySelector("#nav");
const notice = document.querySelector("#notice");
const dialog = document.querySelector("#dialog");
const dialogForm = document.querySelector("#dialog-form");
const dialogError = document.querySelector("#dialog-error");
const submit = document.querySelector("#dialog-submit");
const state = { role: null, page: "directory", specialty: "", doctor: null, date: today(), directory: null };
let renderVersion = 0;
let availabilityVersion = 0;
let dialogAction;

function today() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
}

function escapeHtml(value) {
  const chars = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(value ?? "").replace(/[&<>"']/g, char => chars[char]);
}

function dateLabel(date) {
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(date));
}

function errorMessage(data) {
  if (data.detail) return data.detail;
  return Object.values(data).flat().map(item => item.message || item).join(" ") || "The request could not be completed.";
}

async function api(path, method = "GET", body) {
  const csrf = document.cookie.split("; ").find(cookie => cookie.startsWith("csrftoken="))?.slice(10);
  const response = await fetch("/api/" + path, {
    method,
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf || "" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(errorMessage(data));
    error.status = response.status;
    throw error;
  }
  return data;
}

function announce(message, error = false) {
  notice.textContent = message;
  notice.hidden = !message;
  notice.className = error ? "notice error" : "notice";
}

function hero(title, description) {
  return `<section class="hero"><h1>${title}</h1><p>${description}</p></section>`;
}

function renderNav() {
  const tab = (key, label) =>
    `<button class="quiet" data-page="${key}" ${state.page === key ? 'aria-current="page"' : ""}>${label}</button>`;
  if (state.role === "doctor") nav.innerHTML = tab("dashboard", "Appointments") + tab("slots", "Manage slots");
  else if (state.role === "patient") nav.innerHTML = tab("directory", "Find a doctor") + tab("dashboard", "My appointments");
  else if (state.role === "admin") nav.innerHTML = '<a class="button" href="/admin/">Django Admin</a>';
  else nav.innerHTML = '<button class="quiet" data-action="login">Sign in</button><button class="primary" data-action="register">Register</button>';
  if (state.role) nav.insertAdjacentHTML("beforeend", '<button class="quiet" data-action="logout">Sign out</button>');
}

async function render() {
  const version = ++renderVersion;
  ++availabilityVersion;
  renderNav();
  content.setAttribute("aria-busy", "true");
  try {
    if (state.role === "admin") {
      content.innerHTML = hero("Hospital administration", "Manage specialties, doctor accounts, and appointment records.") +
        '<a class="button primary" href="/admin/">Open Django Admin</a>';
    } else if (state.page === "directory") {
      const query = state.specialty ? "?" + new URLSearchParams({ specialty: state.specialty }) : "";
      const data = await api("directory/" + query);
      if (version !== renderVersion) return;
      state.directory = data;
      if (!data.doctors.some(doctor => doctor.id === state.doctor)) state.doctor = data.doctors[0]?.id ?? null;
      renderDirectory();
    } else if (state.page === "dashboard") {
      const data = await api("dashboard/");
      if (version === renderVersion) renderDashboard(data);
    } else {
      const slots = await api("doctor/slots/");
      if (version === renderVersion) renderSlots(slots);
    }
  } catch (error) {
    if (version === renderVersion) content.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  } finally {
    if (version === renderVersion) content.setAttribute("aria-busy", "false");
  }
}

function renderDirectory() {
  const { specialties, doctors } = state.directory;
  content.innerHTML = hero("Find a doctor", "Browse by specialty and choose a time for your consultation.") + `
    <div class="layout">
      <section class="stack" aria-labelledby="directory-title">
        <div class="panel">
          <div class="row spread">
            <h2 id="directory-title">Doctor directory</h2>
            <label>Specialty<select id="specialty"><option value="">All specialties</option>
              ${specialties.map(item => `<option value="${item.id}" ${String(item.id) === state.specialty ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("")}
            </select></label>
          </div>
        </div>
        ${doctors.map(doctor => `
          <article class="card">
            <div class="row spread">
              <div class="profile">
                <span class="avatar" aria-hidden="true">${escapeHtml(doctor.name.replace(/^Dr\.? /i, "").split(" ").slice(0, 2).map(word => word[0]).join(""))}</span>
                <div><h3>${escapeHtml(doctor.name)}</h3><span class="meta">${doctor.experience} years of experience</span></div>
              </div>
              <span class="specialty">${escapeHtml(doctor.specialty.name)}</span>
            </div>
            <p class="muted">${escapeHtml(doctor.bio)}</p>
            <div class="row spread">
              <strong>${Number(doctor.fee).toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 })}</strong>
              <button data-doctor="${doctor.id}" aria-pressed="${state.doctor === doctor.id}">View times</button>
            </div>
          </article>`).join("") || '<p class="card muted">No doctors in this specialty.</p>'}
      </section>
      <section id="calendar" class="panel" aria-labelledby="calendar-title">
        <h2 id="calendar-title">Available appointments</h2>
        <p class="muted" id="selected-doctor"></p>
        <label>Appointment date <input id="date" type="date" min="${today()}" value="${escapeHtml(state.date)}"></label>
        <div id="availability" aria-live="polite"></div>
        <small class="muted">All times are in IST.</small>
      </section>
    </div>`;
  refreshAvailability();
}

async function refreshAvailability() {
  const version = ++availabilityVersion;
  const target = document.querySelector("#availability");
  const doctor = state.directory.doctors.find(item => item.id === state.doctor);
  document.querySelector("#selected-doctor").textContent = doctor?.name || "Choose a doctor to see appointment times.";
  if (!doctor || !state.date) {
    target.textContent = doctor ? "Choose an appointment date." : "";
    return;
  }
  target.textContent = "Checking available times…";
  try {
    const slots = await api("availability/?" + new URLSearchParams({ doctor: doctor.id, date: state.date }));
    if (version !== availabilityVersion) return;
    target.innerHTML = slots.length ? `<div class="row">${slots.map(slot =>
      `<button data-book="${slot.id}" data-time="${slot.start_time.slice(0, 5)}">${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}</button>`).join("")}</div>`
      : '<p class="muted">No available times on this date.</p>';
  } catch (error) {
    if (version === availabilityVersion) target.textContent = error.message;
  }
}

function renderDashboard({ sections, completed }) {
  const doctor = state.role === "doctor";
  const labels = { today: "Today’s appointments", upcoming: "Upcoming appointments", past: "Past and cancelled appointments" };
  content.innerHTML = hero(doctor ? "Doctor dashboard" : "My appointments",
    doctor ? `${completed} completed ${completed === 1 ? "visit" : "visits"}` : "Review upcoming visits and your appointment history.") +
    Object.entries(sections).map(([section, visits]) => `
      <section class="panel">
        <h2>${labels[section]}</h2>
        ${visits.map(visit => `
          <article class="card">
            <div class="row spread">
              <h3>${escapeHtml(doctor ? visit.patient : visit.doctor)}</h3>
              <span class="status ${visit.status}">${escapeHtml(visit.status[0].toUpperCase() + visit.status.slice(1))}</span>
            </div>
            <p class="meta">${dateLabel(visit.date)} · ${visit.start_time.slice(0, 5)}–${visit.end_time.slice(0, 5)} IST
              ${doctor ? "" : " · " + escapeHtml(visit.specialty)}</p>
            <p><strong>Reason</strong> ${escapeHtml(visit.reason)}</p>
            ${visit.notes ? `<p><strong>Visit notes</strong> ${escapeHtml(visit.notes)}</p>` : ""}
            ${visit.can_cancel ? `<button data-cancel="${visit.id}">Cancel appointment</button>` : ""}
            ${visit.can_complete ? `<button data-complete="${visit.id}">Mark completed</button>` : ""}
          </article>`).join("") || '<p class="muted">No appointments to show.</p>'}
      </section>`).join("");
}

function renderSlots(slots) {
  content.innerHTML = hero("Manage availability", "Add consultation times. Patients can book the available slots you publish.") + `
    <section class="panel">
      <div class="row spread"><h2>Your slots</h2><button class="primary" data-action="add-slot">Add slot</button></div>
      ${slots.map(slot => `
        <article class="card row spread">
          <div><h3>${dateLabel(slot.date)}</h3><p class="meta">${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)} IST</p></div>
          ${slot.has_history ? '<span class="specialty">Appointment history</span>' : `
            <div class="row"><button data-edit="${slot.id}" data-date="${slot.date}" data-start="${slot.start_time.slice(0, 5)}" data-end="${slot.end_time.slice(0, 5)}">Edit</button>
            <button data-remove="${slot.id}">Delete</button></div>`}
        </article>`).join("") || '<p class="muted">You haven’t added any slots yet.</p>'}
    </section>`;
}

function showDialog(title, fields, button, action) {
  document.querySelector("#dialog-title").textContent = title;
  document.querySelector("#dialog-fields").innerHTML = fields;
  dialogError.hidden = true;
  submit.textContent = button;
  dialogAction = action;
  dialog.showModal();
}

function setSession(session) {
  state.role = session.role;
  state.page = state.role === "doctor" ? "dashboard" : "directory";
}

function authForm(action) {
  const register = action === "register";
  showDialog(register ? "Create a patient account" : "Sign in", `
    <label>Username<input name="username" required maxlength="150" autocomplete="username"></label>
    <label>Password<input type="password" name="${register ? "password1" : "password"}" required autocomplete="${register ? "new-password" : "current-password"}"></label>
    ${register ? '<label>Confirm password<input type="password" name="password2" required autocomplete="new-password"></label>' : ""}
  `, register ? "Create account" : "Sign in", async data => {
    setSession(await api("auth/" + action + "/", "POST", data));
    await render();
    announce(register ? "Account created. You can now book a consultation." : "Signed in.");
  });
}

function slotForm(fields = {}) {
  showDialog(fields.edit ? "Edit time slot" : "Add time slot", `
    <label>Date<input type="date" name="date" required min="${today()}" value="${fields.date || today()}"></label>
    <label>Start time (IST)<input type="time" name="start_time" required value="${fields.start || ""}"></label>
    <label>End time (IST)<input type="time" name="end_time" required value="${fields.end || ""}"></label>
  `, "Save slot", async data => {
    await api(fields.edit ? `doctor/slots/${fields.edit}/` : "doctor/slots/", fields.edit ? "PUT" : "POST", data);
    await render();
    announce("Slot saved.");
  });
}

document.addEventListener("change", event => {
  if (event.target.id === "specialty") {
    state.specialty = event.target.value;
    render();
  }
  if (event.target.id === "date") {
    state.date = event.target.value;
    refreshAvailability();
  }
});

document.addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button || dialog.contains(button)) return;
  const { page, action, doctor, book, time, cancel, complete, edit, remove } = button.dataset;
  announce("");
  try {
    if (page) {
      state.page = page;
      await render();
    }
    if (action === "login" || action === "register") authForm(action);
    if (action === "logout") {
      setSession(await api("auth/logout/", "POST"));
      await render();
      announce("Signed out.");
    }
    if (doctor) {
      state.doctor = Number(doctor);
      document.querySelectorAll("[data-doctor]").forEach(item =>
        item.setAttribute("aria-pressed", String(item === button)));
      refreshAvailability();
      if (window.matchMedia("(max-width: 740px)").matches) {
        document.querySelector("#calendar").scrollIntoView({ block: "start" });
      }
    }
    if (book && !state.role) authForm("login");
    else if (book) showDialog("Book consultation", `
      <p>${escapeHtml(document.querySelector("#selected-doctor").textContent)} · ${dateLabel(state.date)} · ${time} IST</p>
      <label>Reason for visit<textarea name="reason" maxlength="500" required></textarea></label>`,
      "Confirm booking", async data => {
        await api("appointments/", "POST", { slot: Number(book), ...data });
        state.page = "dashboard";
        await render();
        announce("Appointment booked.");
      });
    if (cancel) showDialog("Cancel appointment", "<p>Cancel this appointment and release its time slot?</p>",
      "Cancel appointment", async () => {
        await api(`appointments/${cancel}/cancel/`, "POST");
        await render();
        announce("Appointment cancelled.");
      });
    if (complete) showDialog("Complete appointment",
      '<label>Visit notes (optional)<textarea name="notes" maxlength="500"></textarea></label>',
      "Mark completed", async data => {
        await api(`appointments/${complete}/complete/`, "POST", data);
        await render();
        announce("Visit marked completed.");
      });
    if (edit || action === "add-slot") slotForm(button.dataset);
    if (remove) showDialog("Delete time slot", "<p>Remove this slot from your availability?</p>",
      "Delete slot", async () => {
        await api(`doctor/slots/${remove}/`, "DELETE");
        await render();
        announce("Slot deleted.");
      });
  } catch (error) {
    announce(error.message, true);
  }
});

document.querySelector("#dismiss").addEventListener("click", () => dialog.close());
dialog.addEventListener("cancel", event => { if (submit.disabled) event.preventDefault(); });
dialogForm.addEventListener("submit", async event => {
  event.preventDefault();
  submit.disabled = true;
  document.querySelector("#dismiss").disabled = true;
  dialogError.hidden = true;
  try {
    await dialogAction(Object.fromEntries(new FormData(dialogForm)));
    dialog.close();
  } catch (error) {
    dialogError.textContent = error.message;
    dialogError.hidden = false;
    if (state.page === "directory" && error.status === 409) refreshAvailability();
  } finally {
    submit.disabled = false;
    document.querySelector("#dismiss").disabled = false;
  }
});

api("session/").then(session => {
  setSession(session);
  return render();
}).catch(error => {
  content.setAttribute("aria-busy", "false");
  announce(error.message, true);
});
