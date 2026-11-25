const grid = document.querySelector("#grid");
const stage = document.querySelector("#stage");
const months = document.querySelector("#months");
const yearsNav = document.querySelector("#years");
const summary = document.querySelector("#summary");
const tooltip = document.querySelector("#tooltip");
const ship = document.querySelector("#ship");
const playButton = document.querySelector("#play");
const resetButton = document.querySelector("#reset");

const DAY_MS = 86_400_000;
const STEP = 14;
const LEVEL = {
  NONE: 0,
  FIRST_QUARTILE: 1,
  SECOND_QUARTILE: 2,
  THIRD_QUARTILE: 3,
  FOURTH_QUARTILE: 4,
};

let data;
let selectedYear;
let cells = new Map();
let path = [];
let frame = 0;
let timer = null;

function utcDate(year, month, day) {
  return new Date(Date.UTC(year, month, day));
}

function iso(date) {
  return date.toISOString().slice(0, 10);
}

function showTooltip(cell) {
  const count = Number(cell.dataset.count);
  const date = new Date(cell.dataset.date + "T00:00:00Z");
  const readable = new Intl.DateTimeFormat("en-US", {
    year: "numeric", month: "short", day: "numeric", timeZone: "UTC",
  }).format(date);
  tooltip.textContent = `${count} contribution${count === 1 ? "" : "s"} on ${readable}`;
  tooltip.hidden = false;
  const rect = cell.getBoundingClientRect();
  const left = Math.min(
    Math.max(8, rect.left + rect.width / 2 - tooltip.offsetWidth / 2),
    window.innerWidth - tooltip.offsetWidth - 8,
  );
  const above = rect.top - tooltip.offsetHeight - 10;
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${above >= 8 ? above : rect.bottom + 10}px`;
}

function hideTooltip() {
  tooltip.hidden = true;
}

function stopGame() {
  if (timer !== null) clearInterval(timer);
  timer = null;
  playButton.textContent = "Play";
  playButton.setAttribute("aria-label", "Play contribution game");
}

function resetGame() {
  frame = 0;
  grid.querySelectorAll(".eaten").forEach((cell) => cell.classList.remove("eaten"));
  ship.classList.remove("visible");
}

function tick() {
  if (frame >= path.length) resetGame();
  const step = path[frame++];
  if (!step) {
    ship.classList.remove("visible");
    return;
  }
  const { col, row, direction } = step;
  const cell = cells.get(`${col}:${row}`);
  if (cell && Number(cell.dataset.count) > 0) cell.classList.add("eaten");
  ship.classList.add("visible");
  ship.style.transform = `translate(${col * STEP - 6}px, ${row * STEP - 4}px) scaleX(${direction})`;
}

function startGame() {
  if (timer !== null) return;
  timer = window.setInterval(tick, 45);
  playButton.textContent = "Pause";
  playButton.setAttribute("aria-label", "Pause contribution game");
}

function makePath(weekCount) {
  const result = Array(14).fill(null);
  for (let row = 0; row < 7; row++) {
    const direction = row % 2 === 0 ? 1 : -1;
    const columns = Array.from({ length: weekCount }, (_, col) => col);
    if (direction < 0) columns.reverse();
    for (const col of columns) result.push({ col, row, direction });
  }
  result.push(...Array(18).fill(null));
  return result;
}

function renderYears(years) {
  yearsNav.replaceChildren();
  for (const year of years) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = year;
    button.setAttribute("aria-current", String(Number(year) === selectedYear));
    button.addEventListener("click", () => renderCalendar(Number(year)));
    yearsNav.append(button);
  }
}

function renderCalendar(year) {
  const wasPlaying = timer !== null;
  stopGame();
  hideTooltip();
  selectedYear = year;
  const yearData = data.years[String(year)];
  const dayData = new Map(yearData.days.map((day) => [day.date, day]));
  const first = utcDate(year, 0, 1);
  first.setUTCDate(first.getUTCDate() - first.getUTCDay());
  const last = utcDate(year, 11, 31);
  last.setUTCDate(last.getUTCDate() + 6 - last.getUTCDay());
  const numberOfDays = Math.round((last - first) / DAY_MS) + 1;
  const weekCount = numberOfDays / 7;
  const width = weekCount * STEP - 3;
  const currentDate = iso(new Date());

  grid.style.setProperty("--weeks", weekCount);
  grid.style.setProperty("--grid-width", `${width}px`);
  stage.style.setProperty("--grid-width", `${width}px`);
  months.style.setProperty("--grid-width", `${width}px`);
  summary.textContent = `${yearData.total.toLocaleString("en-US")} contributions in ${year}`;
  grid.replaceChildren();
  months.replaceChildren();
  cells = new Map();

  for (let month = 0; month < 12; month++) {
    const monthStart = utcDate(year, month, 1);
    const column = Math.floor((monthStart - first) / DAY_MS / 7);
    const label = document.createElement("span");
    label.textContent = new Intl.DateTimeFormat("en-US", { month: "short", timeZone: "UTC" }).format(monthStart);
    label.style.left = `${column * STEP}px`;
    months.append(label);
  }

  for (let dayIndex = 0; dayIndex < numberOfDays; dayIndex++) {
    const date = new Date(first.getTime() + dayIndex * DAY_MS);
    const dateString = iso(date);
    const col = Math.floor(dayIndex / 7);
    const row = dayIndex % 7;
    if (date.getUTCFullYear() !== year || dateString > currentDate) {
      const blank = document.createElement("span");
      blank.className = "blank";
      grid.append(blank);
      continue;
    }
    const info = dayData.get(dateString) || { count: 0, level: "NONE" };
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = "cell";
    cell.dataset.level = LEVEL[info.level] ?? 0;
    cell.dataset.count = info.count;
    cell.dataset.date = dateString;
    cell.setAttribute("aria-label", `${info.count} contribution${info.count === 1 ? "" : "s"} on ${dateString}`);
    cell.addEventListener("mouseenter", () => showTooltip(cell));
    cell.addEventListener("mouseleave", hideTooltip);
    cell.addEventListener("focus", () => showTooltip(cell));
    cell.addEventListener("blur", hideTooltip);
    cell.addEventListener("click", () => showTooltip(cell));
    grid.append(cell);
    cells.set(`${col}:${row}`, cell);
  }

  path = makePath(weekCount);
  resetGame();
  renderYears(Object.keys(data.years).sort((a, b) => Number(b) - Number(a)));
  if (wasPlaying) startGame();
}

playButton.addEventListener("click", () => {
  if (timer === null) startGame();
  else stopGame();
});
resetButton.addEventListener("click", resetGame);

fetch("./contributions.json", { cache: "no-store" })
  .then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then((payload) => {
    data = payload;
    const years = Object.keys(data.years).map(Number).sort((a, b) => b - a);
    if (!years.length) throw new Error("No contribution years");
    renderCalendar(years[0]);
    if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) startGame();
  })
  .catch(() => {
    summary.textContent = "Contributions unavailable";
    grid.className = "error";
    grid.textContent = "The contribution data could not be loaded.";
    playButton.disabled = true;
    resetButton.disabled = true;
  });
