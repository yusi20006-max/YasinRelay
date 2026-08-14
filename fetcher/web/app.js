const STORAGE_KEY = "openfeed_channels";
const CACHE_PREFIX = "openfeed_cache_";

let currentChannel = null;

// ---------- storage helpers ----------

function loadSaved(){
  try{
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  }catch(e){
    return [];
  }
}

function saveSaved(list){
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

function touchChannel(username, title){
  const list = loadSaved().filter(c => c.username !== username);
  list.unshift({ username, title: title || username, lastOpened: Date.now() });
  saveSaved(list.slice(0, 20));
  renderSavedList();
}

function removeChannel(username){
  saveSaved(loadSaved().filter(c => c.username !== username));
  localStorage.removeItem(CACHE_PREFIX + username);
  renderSavedList();
}

function cacheChannel(username, channel){
  try{
    localStorage.setItem(CACHE_PREFIX + username, JSON.stringify({ channel, savedAt: Date.now() }));
  }catch(e){ /* storage full, ignore */ }
}

function readCache(username){
  try{
    const raw = localStorage.getItem(CACHE_PREFIX + username);
    return raw ? JSON.parse(raw) : null;
  }catch(e){
    return null;
  }
}

// ---------- connection status ----------

async function checkStatus(){
  const el = document.getElementById("status");
  const text = document.getElementById("statusText");
  el.className = "status status-checking";
  text.textContent = "در حال بررسی اتصال…";

  try{
    const res = await fetch("/api/status");
    const data = await res.json();
    if(data.connected){
      el.className = "status status-connected";
      text.textContent = "متصل (" + data.ms + " ms)";
    }else{
      el.className = "status status-error";
      text.textContent = "اتصال برقرار نشد";
    }
  }catch(e){
    el.className = "status status-error";
    text.textContent = "سرور در دسترس نیست";
  }
}

// ---------- saved channel chips ----------

function renderSavedList(){
  const wrap = document.getElementById("savedList");
  wrap.innerHTML = "";

  const items = loadSaved();

  items.forEach(c => {
    const chip = document.createElement("div");
    chip.className = "chip" + (c.username === currentChannel ? " active" : "");
    chip.onclick = () => loadChannel(c.username);

    const label = document.createElement("span");
    label.textContent = c.title || c.username;
    chip.appendChild(label);

    const x = document.createElement("span");
    x.className = "x";
    x.textContent = "×";
    x.onclick = (ev) => { ev.stopPropagation(); removeChannel(c.username); };
    chip.appendChild(x);

    wrap.appendChild(chip);
  });
}

// ---------- feed rendering ----------

function timeAgo(dateStr){
  if(!dateStr) return "";
  const d = new Date(dateStr);
  if(isNaN(d.getTime())) return "";
  const diff = (Date.now() - d.getTime()) / 1000;
  if(diff < 60) return "چند لحظه پیش";
  if(diff < 3600) return Math.floor(diff/60) + " دقیقه پیش";
  if(diff < 86400) return Math.floor(diff/3600) + " ساعت پیش";
  if(diff < 2592000) return Math.floor(diff/86400) + " روز پیش";
  return d.toLocaleDateString("fa-IR");
}

function showLoading(){
  document.getElementById("feed").innerHTML = '<div class="loading">در حال دریافت پست‌ها…</div>';
}

function showError(message, retryFn){
  const feed = document.getElementById("feed");
  feed.innerHTML = "";

  const err = document.createElement("div");
  err.className = "error";
  err.textContent = "خطا در دریافت کانال: " + message;
  feed.appendChild(err);

  const btn = document.createElement("button");
  btn.className = "retry-btn";
  btn.textContent = "تلاش دوباره";
  btn.onclick = retryFn;
  feed.appendChild(btn);
}

// ---------- media helpers ----------

// Small transient message at the bottom of the screen. Used instead of
// navigating away when a download fails, since a full-page navigation
// to an error response replaces the whole app shell in standalone PWA
// mode (no address bar, no back button) — it looks like a crash.
let toastTimer = null;
function showToast(text){
  let el = document.getElementById("toast");
  if(!el){
    el = document.createElement("div");
    el.id = "toast";
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 3500);
}

// Fetches the download URL first instead of navigating the page
// straight to it. On success the bytes are handed to the browser as a
// blob download (page never leaves the app); on failure (e.g. the
// source is blocked without a VPN) we show a toast instead of letting
// the error response take over the screen.
async function triggerDownload(url, filename){
  try{
    const res = await fetch(url);
    if(!res.ok){
      const msg = await res.text().catch(() => "");
      throw new Error(msg || ("HTTP " + res.status));
    }
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = filename || "file";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 10000);
  }catch(e){
    showToast("دانلود ناموفق بود — احتمالاً بدون فیلترشکن قابل‌دسترس نیست");
  }
}

// Building the download URL/filename here in one place keeps the
// extension guess and the /api/download plumbing in sync.
function downloadNameFor(media, postId){
  const ext = media.type === "video" ? "mp4"
    : media.type === "voice" ? "ogg"
    : media.type === "audio" ? "mp3"
    : "bin";
  const base = media.title || (postId ? postId.replace("/", "_") : "file");
  return base.includes(".") ? base : base + "." + ext;
}

function downloadUrlFor(media, postId){
  if(!media.download) return "";
  const name = downloadNameFor(media, postId);
  return "/api/download?u=" + encodeURIComponent(media.download) + "&name=" + encodeURIComponent(name);
}

function iconFor(type){
  switch(type){
    case "document": return "📄";
    case "audio": return "🎵";
    case "voice": return "🎙️";
    default: return "📎";
  }
}

// A broken/failed image gets a small retry box instead of silently
// vanishing (the old behaviour just called img.remove(), which made it
// look like the post had no photo at all).
function attachImageFallback(img, wrap){
  img.referrerPolicy = "no-referrer";
  img.loading = "lazy";
  img.onerror = () => {
    if(wrap.dataset.failed === "1") return;
    wrap.dataset.failed = "1";
    wrap.innerHTML = "";
    const broken = document.createElement("div");
    broken.className = "media-broken";
    const label = document.createElement("span");
    label.textContent = "🖼️ بارگذاری تصویر ناموفق بود";
    broken.appendChild(label);
    const retry = document.createElement("span");
    retry.className = "retry";
    retry.textContent = "تلاش دوباره";
    retry.onclick = () => {
      wrap.dataset.failed = "";
      wrap.innerHTML = "";
      wrap.appendChild(buildImage(img.src, img.style.aspectRatio));
    };
    broken.appendChild(retry);
    wrap.appendChild(broken);
  };
}

function buildImage(src, ratio){
  const img = document.createElement("img");
  img.src = src;
  if(ratio) img.style.aspectRatio = ratio;
  return img;
}

function renderMedia(media, postId){
  if(media.type === "photo" && media.url){
    const wrap = document.createElement("div");
    wrap.className = "media-photo-wrap";
    const img = buildImage(media.url, media.ratio);
    attachImageFallback(img, wrap);
    wrap.appendChild(img);
    return wrap;
  }

  if(media.type === "video" && media.url){
    const wrap = document.createElement("div");
    wrap.className = "media-video-wrap";
    const img = buildImage(media.url, media.ratio);
    attachImageFallback(img, wrap);
    wrap.appendChild(img);

    const badge = document.createElement("div");
    badge.className = "video-badge";
    const play = document.createElement("div");
    play.className = "video-play";
    play.textContent = "▶";
    badge.appendChild(play);
    wrap.appendChild(badge);

    if(media.duration){
      const dur = document.createElement("div");
      dur.className = "video-duration";
      dur.textContent = media.duration;
      wrap.appendChild(dur);
    }

    if(media.download){
      wrap.style.cursor = "pointer";
      wrap.title = "دانلود ویدیو";
      wrap.onclick = () => triggerDownload(downloadUrlFor(media, postId), downloadNameFor(media, postId));
    }
    return wrap;
  }

  if(media.type === "sticker" && media.url){
    const wrap = document.createElement("div");
    wrap.className = "media-sticker";
    const img = buildImage(media.url, media.ratio);
    attachImageFallback(img, wrap);
    wrap.appendChild(img);
    return wrap;
  }

  if(media.type === "poll"){
    const wrap = document.createElement("div");
    wrap.className = "media-poll";
    const q = document.createElement("div");
    q.className = "media-poll-q";
    q.textContent = "📊 " + (media.title || "نظرسنجی");
    wrap.appendChild(q);
    (media.options || []).forEach(opt => {
      const o = document.createElement("div");
      o.className = "media-poll-opt";
      o.textContent = "▫️ " + opt;
      wrap.appendChild(o);
    });
    return wrap;
  }

  if(["document", "audio", "voice"].includes(media.type)){
    const wrap = document.createElement("div");
    wrap.className = "media-file";

    const icon = document.createElement("div");
    icon.className = "media-file-icon";
    icon.textContent = iconFor(media.type);
    wrap.appendChild(icon);

    const info = document.createElement("div");
    info.className = "media-file-info";
    const title = document.createElement("div");
    title.className = "media-file-title";
    title.textContent = media.title || (media.type === "voice" ? "پیام صوتی" : media.type === "audio" ? "فایل صوتی" : "فایل");
    info.appendChild(title);
    const subtitleParts = [media.subtitle, media.duration].filter(Boolean);
    if(subtitleParts.length){
      const sub = document.createElement("div");
      sub.className = "media-file-subtitle";
      sub.textContent = subtitleParts.join(" · ");
      info.appendChild(sub);
    }
    wrap.appendChild(info);

    if(media.download){
      const btn = document.createElement("a");
      btn.className = "media-download-btn";
      btn.textContent = "⬇";
      btn.href = "#";
      btn.title = "دانلود";
      btn.onclick = (e) => {
        e.preventDefault();
        triggerDownload(downloadUrlFor(media, postId), downloadNameFor(media, postId));
      };
      wrap.appendChild(btn);
    }

    return wrap;
  }

  return null;
}

function render(channel){
  const feed = document.getElementById("feed");
  feed.innerHTML = "";

  const header = document.createElement("div");
  header.className = "channel-header";

  if(channel.avatar){
    const img = document.createElement("img");
    img.className = "avatar";
    img.referrerPolicy = "no-referrer";
    img.loading = "lazy";
    img.src = channel.avatar;
    img.alt = "";
    img.onerror = () => img.remove();
    header.appendChild(img);
  }

  const meta = document.createElement("div");
  meta.className = "channel-meta";
  meta.innerHTML = `<h3>${channel.title || currentChannel}</h3><div class="sub">${channel.subscribers || ""}</div>`;
  header.appendChild(meta);

  const refreshBtn = document.createElement("button");
  refreshBtn.className = "refresh-btn";
  refreshBtn.textContent = "بروزرسانی";
  refreshBtn.onclick = () => loadChannel(currentChannel, { force: true });
  header.appendChild(refreshBtn);

  feed.appendChild(header);

  (channel.posts || []).forEach(post => {
    const card = document.createElement("div");
    card.className = "post";

    const mediaItems = post.media || [];
    if(mediaItems.length){
      const grid = document.createElement("div");
      grid.className = "media-grid";
      mediaItems.forEach(m => {
        const el = renderMedia(m, post.id);
        if(el) grid.appendChild(el);
      });
      if(grid.childElementCount) card.appendChild(grid);
    }

    if(post.text){
      const text = document.createElement("p");
      text.innerHTML = post.text;
      card.appendChild(text);

      const isLong = text.textContent.length > 280;
      if(isLong){
        text.classList.add("clamp");
        const more = document.createElement("span");
        more.className = "show-more";
        more.textContent = "بیشتر ببین";
        let expanded = false;
        more.onclick = () => {
          expanded = !expanded;
          text.classList.toggle("clamp", !expanded);
          more.textContent = expanded ? "کمتر ببین" : "بیشتر ببین";
        };
        card.appendChild(more);
      }
    }

    const metaRow = document.createElement("div");
    metaRow.className = "meta";
    metaRow.innerHTML = `<span>${timeAgo(post.date)}</span><span>${post.views || ""}</span>`;
    card.appendChild(metaRow);

    feed.appendChild(card);
  });

  if(!(channel.posts || []).length){
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "پستی برای نمایش پیدا نشد";
    feed.appendChild(empty);
  }
}

// ---------- load flow ----------

function openFromInput(){
  const name = document.getElementById("channel").value.trim();
  if(name === "") return;
  loadChannel(name);
}

async function loadChannel(name, opts){
  opts = opts || {};
  currentChannel = name;
  document.getElementById("channel").value = name;
  renderSavedList();

  const cached = !opts.force ? readCache(name) : null;
  if(cached){
    render(cached.channel);
  }else{
    showLoading();
  }

  try{
    const res = await fetch("/api/channel/" + encodeURIComponent(name));
    if(!res.ok) throw new Error("HTTP " + res.status);
    const channel = await res.json();

    render(channel);
    cacheChannel(name, channel);
    touchChannel(name, channel.title);

  }catch(e){
    if(cached){
      // keep showing the cached version; just let status badge reflect the problem
      checkStatus();
      return;
    }
    showError(e.message, () => loadChannel(name, opts));
  }
}

// ---------- pull to refresh ----------

(function setupPullToRefresh(){
  const feed = document.getElementById("feed");
  const hint = document.getElementById("pullHint");
  let startY = null;

  feed.addEventListener("touchstart", e => {
    if(window.scrollY === 0){
      startY = e.touches[0].clientY;
    }else{
      startY = null;
    }
  }, { passive: true });

  feed.addEventListener("touchmove", e => {
    if(startY === null) return;
    const dy = e.touches[0].clientY - startY;
    hint.classList.toggle("show", dy > 60);
  }, { passive: true });

  feed.addEventListener("touchend", e => {
    if(hint.classList.contains("show") && currentChannel){
      loadChannel(currentChannel, { force: true });
    }
    hint.classList.remove("show");
    startY = null;
  });
})();

// ---------- init ----------

document.getElementById("channel").addEventListener("keydown", e => {
  if(e.key === "Enter") openFromInput();
});

checkStatus();
renderSavedList();

const last = loadSaved()[0];
if(last) loadChannel(last.username);

if("serviceWorker" in navigator){
  navigator.serviceWorker.register("sw.js");
}
