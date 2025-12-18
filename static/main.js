var form = document.getElementById("snowflakeForm");
var previewEl = document.getElementById("preview");
var snowflakesDiv = document.getElementById("snowflakes");
var modal = document.getElementById("modal");
var currentId = null;
var lastPreviewSeed = null;

var CHARS = {
  classic: ["*", "+", "-", "|", "o", ".", "x"],
  dense: ["#", "@", "%", "&", "$"],
  minimal: [".", "o", "*"],
  mixed: ["*", "+", "-", "|", "o", ".", "x", "#", "@", "%", "&", "$"]
};

function hash(s) {
  var h = 0;
  for (var i = 0; i < s.length; i++) {
    h = ((h << 5) - h) + s.charCodeAt(i);
    h = h & 0xFFFFFFFF;
  }
  return Math.abs(h) || 1;
}

function Rng(seed) { this.s = hash(seed); }
Rng.prototype.next = function() {
  this.s = (this.s * 1103515245 + 12345) & 0x7FFFFFFF;
  return this.s / 0x7FFFFFFF;
};
Rng.prototype.int = function(a, b) { return Math.floor(this.next() * (b - a + 1)) + a; };
Rng.prototype.pick = function(arr) { return arr[Math.floor(this.next() * arr.length)]; };

function generate(size, seed, style) {
  if (size % 2 === 0) size++;
  var rng = new Rng(seed);
  var chars = CHARS[style] || CHARS.classic;
  var c = Math.floor(size / 2);
  var grid = [];
  for (var i = 0; i < size; i++) { grid[i] = []; for (var j = 0; j < size; j++) grid[i][j] = " "; }
  
  var pts = [];
  for (var r = 0; r <= c; r++) {
    if (rng.next() < 0.7) {
      pts.push({x: 0, y: r, ch: rng.pick(chars)});
      if (r > 0 && rng.next() < 0.4) {
        var len = rng.int(1, Math.max(1, Math.floor(r / 2)));
        for (var b = 1; b <= len; b++) if (rng.next() < 0.6) pts.push({x: b, y: r - b, ch: rng.pick(chars)});
      }
    }
  }
  
  for (var rot = 0; rot < 6; rot++) {
    var a = rot * Math.PI / 3, cos = Math.cos(a), sin = Math.sin(a);
    for (var p = 0; p < pts.length; p++) {
      var pt = pts[p];
      var gx = c + Math.round(pt.x * cos - pt.y * sin);
      var gy = c + Math.round(pt.x * sin + pt.y * cos);
      if (gx >= 0 && gx < size && gy >= 0 && gy < size) grid[gy][gx] = pt.ch;
    }
  }
  
  return grid.map(function(row) { return row.join(""); }).join("\n");
}

function makeSeed() { return Date.now() + "-" + Math.random().toString(36).substr(2, 8); }

function load() {
  var xhr = new XMLHttpRequest();
  xhr.open("GET", "/api/snowflakes");
  xhr.onload = function() {
    var flakes = JSON.parse(xhr.responseText);
    snowflakesDiv.innerHTML = flakes.length ? "" : "<p>No snowflakes yet</p>";
    flakes.forEach(function(f) {
      var div = document.createElement("div");
      div.className = "card" + (f.melted ? " melted" : "");
      div.innerHTML = "<pre>" + f.pattern + "</pre><small>#" + f.id + "</small>";
      div.onclick = function() { openModal(f); };
      snowflakesDiv.appendChild(div);
    });
  };
  xhr.send();
}

document.getElementById("previewBtn").onclick = function() {
  var size = parseInt(form.size.value) || 9;
  var seed = form.seed.value || makeSeed();
  previewEl.textContent = generate(size, seed, form.style.value);
  lastPreviewSeed = seed;
};

form.onsubmit = function(e) {
  e.preventDefault();
  if (!lastPreviewSeed) {
    alert("Please preview a snowflake first");
    return;
  }
  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/snowflakes");
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.onload = function() { form.seed.value = ""; previewEl.textContent = ""; lastPreviewSeed = null; load(); };
  xhr.send(JSON.stringify({
    size: parseInt(form.size.value) || 9,
    seed: lastPreviewSeed,
    style: form.style.value
  }));
};

function openModal(f) {
  currentId = f.id;
  document.getElementById("modalPattern").textContent = f.pattern;
  document.getElementById("modalId").textContent = f.id;
  document.getElementById("modalSize").textContent = f.size;
  document.getElementById("modalStatus").textContent = f.melted ? "Melted" : "Frozen";
  document.getElementById("modalCreated").textContent = new Date(f.createdAt * 1000).toLocaleString();
  document.getElementById("meltBtn").disabled = f.melted;
  modal.style.display = "block";
}

document.getElementById("closeBtn").onclick = function() { modal.style.display = "none"; };
modal.onclick = function(e) { if (e.target === modal) modal.style.display = "none"; };

document.getElementById("meltBtn").onclick = function() {
  var xhr = new XMLHttpRequest();
  xhr.open("PATCH", "/api/snowflakes/" + currentId + "/melt");
  xhr.onload = function() { modal.style.display = "none"; load(); };
  xhr.send();
};

document.getElementById("deleteBtn").onclick = function() {
  if (!confirm("Delete?")) return;
  var xhr = new XMLHttpRequest();
  xhr.open("DELETE", "/api/snowflakes/" + currentId);
  xhr.onload = function() { modal.style.display = "none"; load(); };
  xhr.send();
};

load();
