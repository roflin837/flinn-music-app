from flask import Flask, render_template_string, jsonify, request
import sqlite3, yt_dlp, requests, os, random

app = Flask(__name__)

# PENYESUAIAN VERCEL: Database harus di folder /tmp agar bisa ditulis
DB_NAME = '/tmp/flinn_enterprise.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # Cek apakah file sudah ada, kalau belum buat tabelnya
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT UNIQUE, 
            description TEXT)''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            title TEXT, 
            artist TEXT, 
            cover TEXT, 
            duration TEXT, 
            yt_id TEXT, 
            pid INTEGER,
            is_favorite INTEGER DEFAULT 0,
            FOREIGN KEY(pid) REFERENCES playlists(id) ON DELETE CASCADE)''')
        
        conn.execute("INSERT OR IGNORE INTO playlists (id, name, description) VALUES (1, 'Koleksi Utama', 'Default Collection')")
        conn.execute("INSERT OR IGNORE INTO playlists (id, name, description) VALUES (99, 'Lagu Favorit', 'User Liked Songs')")
        conn.commit()

class FlinnDownloader:
    YDL_OPTS = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'default_search': 'ytsearch',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    @staticmethod
    def get_info(query):
        opts = FlinnDownloader.YDL_OPTS.copy()
        opts.update({'noplaylist': True, 'default_search': 'ytsearch1'})
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                res = ydl.extract_info(query, download=False)
                if 'entries' in res and len(res['entries']) > 0:
                    return res['entries'][0]
                return res
        except Exception as e:
            return None

    @staticmethod
    def search_multiple(query, limit=15):
        opts = FlinnDownloader.YDL_OPTS.copy()
        opts.update({'default_search': f'ytsearch{limit}'})
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                res = ydl.extract_info(query, download=False)
                return res['entries'] if 'entries' in res else []
        except:
            return []

@app.route('/api/playlists')
def get_playlists():
    with get_db() as conn:
        p = conn.execute('SELECT * FROM playlists WHERE id != 99 ORDER BY id ASC').fetchall()
        return jsonify([dict(x) for x in p])

@app.route('/api/create_playlist', methods=['POST'])
def create_playlist():
    data = request.json
    name = data.get('name', 'Playlist Baru Flinn')
    try:
        with get_db() as conn:
            conn.execute('INSERT INTO playlists (name) VALUES (?)', (name,))
            conn.commit()
        return jsonify({"status": "success"})
    except:
        return jsonify({"status": "error", "message": "Nama sudah ada"}), 400

@app.route('/api/delete_playlist', methods=['POST'])
def delete_playlist():
    data = request.json
    if data['id'] == 1: return jsonify({"error": "Admin cannot delete root"}), 400
    with get_db() as conn:
        conn.execute('DELETE FROM playlists WHERE id = ?', (data['id'],))
        conn.execute('DELETE FROM songs WHERE pid = ?', (data['id'],))
        conn.commit()
    return jsonify({"status": "success"})

@app.route('/api/add_to_db', methods=['POST'])
def add_to_db():
    info = request.json
    pid = info.get('pid', 1) 
    with get_db() as conn:
        exists = conn.execute('SELECT id FROM songs WHERE yt_id = ? AND pid = ?', (info['yt_id'], pid)).fetchone()
        if not exists:
            conn.execute('''INSERT INTO songs (title, artist, cover, duration, yt_id, pid) 
                            VALUES (?,?,?,?,?,?)''',
                         (info['title'], info['artist'], info['cover'], info['duration'], info['yt_id'], pid))
            conn.commit()
    return jsonify({"status": "success"})

@app.route('/api/toggle_favorite', methods=['POST'])
def toggle_favorite():
    data = request.json
    with get_db() as conn:
        conn.execute('UPDATE songs SET is_favorite = 1 - is_favorite WHERE yt_id = ?', (data['yt_id'],))
        conn.commit()
        res = conn.execute('SELECT is_favorite FROM songs WHERE yt_id = ? LIMIT 1', (data['yt_id'],)).fetchone()
    return jsonify({"status": "success", "is_favorite": res['is_favorite'] if res else 0})

@app.route('/api/stream/<yt_id>')
def api_stream(yt_id):
    info = FlinnDownloader.get_info(f"https://www.youtube.com/watch?v={yt_id}")
    if info and 'url' in info:
        return jsonify({"url": info['url']})
    return jsonify({"error": "Streaming Forbidden"}), 403

@app.route('/api/content')
def get_content():
    mode = request.args.get('mode', 'home')
    pid = request.args.get('pid')
    init_db()
    with get_db() as conn:
        if mode == 'liked':
            songs = conn.execute('SELECT * FROM songs WHERE is_favorite = 1').fetchall()
            title = "Lagu yang Disukai"
        elif mode == 'playlist' and pid:
            songs = conn.execute('SELECT * FROM songs WHERE pid = ?', (pid,)).fetchall()
            res = conn.execute('SELECT name FROM playlists WHERE id = ?', (pid,)).fetchone()
            title = res['name'] if res else "Playlist Detail"
        else:
            # KITA HAPUS 'GROUP BY' DAN 'LIMIT' BIAR SEMUA 637+ LAGU MUNCUL
            songs = conn.execute('SELECT * FROM songs ORDER BY id DESC').fetchall()
            title = "Koleksi Flinn"
        
        return jsonify({"songs": [dict(s) for s in songs], "title": title})

@app.route('/api/search_suggestions', methods=['POST'])
def search_suggestions():
    data = request.json
    results = FlinnDownloader.search_multiple(data['q'])
    output = []
    for info in (results or []):
        if not info: continue
        output.append({
            "title": info.get('title'),
            "artist": info.get('uploader', 'Artist YouTube'),
            "cover": info.get('thumbnail'),
            "duration": str(info.get('duration')),
            "yt_id": info.get('id')
        })
    return jsonify(output)

@app.route('/')
def index():
    # Pastikan DB terbuat saat pertama kali buka
    init_db()
    return render_template_string(HTML_TEMPLATE)

# (Ganti HTML_TEMPLATE di sini dengan kode HTML panjang lu tadi)
# Biar pendek gue asumsikan lu tetep pake HTML_TEMPLATE yang sama ya Flinn.
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flinn-ify Enterprise Premium v5</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
        /* --------------------------------------------------------
           CSS GLOBAL STYLING & ANIMATIONS
           -------------------------------------------------------- */
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
        
        :root {
            --bg-base: #000000;
            --bg-surface: #121212;
            --bg-elevated: #1e1e1e;
            --spotify-green: #1db954;
            --text-main: #ffffff;
            --text-sub: #b3b3b3;
            --trans-fast: 0.2s ease;
            --trans-slow: 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }

        body { 
            background: var(--bg-base); 
            color: var(--text-main); 
            font-family: 'Plus Jakarta Sans', sans-serif; 
            overflow: hidden; 
            margin: 0;
            -webkit-user-select: none;
        }

        /* App Shell Layout */
        .app-shell { 
            display: grid; 
            grid-template-areas: "sidebar main" "player player"; 
            grid-template-columns: 320px 1fr; 
            grid-template-rows: 1fr 110px; 
            height: 100vh; 
            padding: 8px; 
            gap: 8px; 
        }

        /* Sidebar Styling */
        .sidebar { grid-area: sidebar; display: flex; flex-direction: column; gap: 8px; }
        .nav-card { background: var(--bg-surface); border-radius: 12px; padding: 16px; }
        .nav-item { 
            display: flex; align-items: center; gap: 20px; padding: 14px; 
            color: var(--text-sub); font-weight: 700; cursor: pointer; transition: var(--trans-fast);
        }
        .nav-item:hover, .nav-item.active { color: #fff; transform: translateX(5px); }
        .nav-item i { font-size: 1.4rem; }

        .library-section { 
            flex: 1; background: var(--bg-surface); border-radius: 12px; 
            display: flex; flex-direction: column; overflow: hidden; 
        }

        /* Main Content Styling */
        .main-content { 
            grid-area: main; 
            background: linear-gradient(to bottom, #1f1f1f 0%, #121212 35%); 
            border-radius: 12px; overflow-y: auto; position: relative; scroll-behavior: smooth;
        }

        /* Search Input */
        .search-container { position: sticky; top: 0; padding: 20px 32px; z-index: 50; background: rgba(18,18,18,0.8); backdrop-filter: blur(10px); }
        .search-input { 
            width: 100%; max-width: 450px; background: #2a2a2a; border-radius: 50px; 
            padding: 14px 54px; outline: none; border: 2px solid transparent; color: white;
            transition: var(--trans-fast);
        }
        .search-input:focus { border-color: #444; background: #333; width: 105%; }

        /* Music Cards */
        .music-card { 
            background: #181818; padding: 18px; border-radius: 10px; 
            transition: var(--trans-slow); cursor: pointer; position: relative;
        }
        .music-card:hover { background: #2a2a2a; transform: translateY(-5px); }
        .music-card img { 
            width: 100%; aspect-ratio: 1; border-radius: 8px; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.6); margin-bottom: 14px;
        }

        /* Player Bar */
        .player-bar { 
            grid-area: player; background: #000; border-top: 1px solid #1a1a1a;
            display: flex; align-items: center; justify-content: space-between; padding: 0 24px; 
        }

        /* Progress Bar Engine */
        .progress-container { flex: 1; height: 5px; background: #333; border-radius: 10px; cursor: pointer; position: relative; }
        .progress-fill { height: 100%; background: #fff; width: 0%; border-radius: 10px; transition: width 0.1s linear; }
        .progress-container:hover .progress-fill { background: var(--spotify-green); }

        /* Custom Modal */
        .modal-overlay { 
            display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); 
            z-index: 1000; align-items: center; justify-content: center; backdrop-filter: blur(5px);
            animation: fadeIn 0.3s ease;
        }
        .modal-content { 
            background: #282828; width: 350px; border-radius: 15px; padding: 24px; 
            box-shadow: 0 25px 50px rgba(0,0,0,0.5); 
        }

        /* Keyframes Animations */
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #444; border-radius: 5px; }
        ::-webkit-scrollbar-thumb:hover { background: #666; }

        .active-green { color: var(--spotify-green) !important; }
        .heart-active { color: var(--spotify-green) !important; animation: beat 0.3s ease; }
        @keyframes beat { 0% { transform: scale(1); } 50% { transform: scale(1.4); } 100% { transform: scale(1); } }

        /* FIX UNTUK HP */
        @media (max-width: 768px) {
            .app-shell {
                grid-template-areas: "main" "player";
                grid-template-columns: 1fr;
                grid-template-rows: 1fr 100px;
                padding: 0;
            }
            .sidebar { display: none; } /* Sidebar ganggu di HP, kita sembunyiin */
            .main-content { border-radius: 0; }
            #mainGrid { 
                grid-template-columns: repeat(2, 1fr) !important; 
                gap: 12px; 
                padding: 10px;
            }
            .player-bar { padding: 0 10px; }
            #trackCover { width: 40px; height: 40px; }
            #trackTitle { font-size: 12px; }
        }
        
    </style>
</head>
<body>

<div id="playlistModal" class="modal-overlay">
    <div class="modal-content">
        <h3 class="text-xl font-bold mb-5 flex items-center gap-2">
            <i class="fa-solid fa-folder-plus text-green-500"></i> Simpan ke Playlist
        </h3>
        <div id="playlistOptions" class="space-y-3 max-h-[300px] overflow-y-auto pr-2">
            </div>
        <div class="mt-6 flex gap-3">
            <button onclick="closeModal()" class="flex-1 py-3 text-sm font-bold text-zinc-400 hover:text-white transition">Batal</button>
            <button onclick="ui_createPlaylist()" class="flex-1 py-3 bg-white text-black rounded-full text-sm font-bold hover:scale-105 transition">Buat Baru</button>
        </div>
    </div>
</div>

<div class="app-shell">
    <aside class="sidebar">
        <div class="nav-card">
            <div class="nav-item active" id="navHome" onclick="routeTo('home')">
                <i class="fa-solid fa-house"></i> <span>Beranda</span>
            </div>
            <div class="nav-item" id="navSearch" onclick="routeTo('search')">
                <i class="fa-solid fa-magnifying-glass"></i> <span>Cari Lagu</span>
            </div>
            <div class="nav-item" id="navLiked" onclick="routeTo('liked')">
                <i class="fa-solid fa-heart text-zinc-500"></i> <span>Lagu Favorit</span>
            </div>
        </div>

        <div class="library-section">
            <div class="p-5 flex justify-between items-center text-zinc-400">
                <div class="flex items-center gap-3 font-extrabold text-sm uppercase tracking-widest">
                    <i class="fa-solid fa-layer-group"></i> Koleksi Flinn
                </div>
                <i class="fa-solid fa-plus cursor-pointer hover:bg-zinc-800 p-2 rounded-full transition" onclick="ui_createPlaylist()"></i>
            </div>
            <div id="sidebarPlaylists" class="px-3 flex-1 overflow-y-auto space-y-1">
                </div>
        </div>
    </aside>

    <main class="main-content" id="mainScroll">
        <div id="homeView" class="px-8 pb-40">
            <h2 id="sectionTitle" class="text-4xl font-black mt-10 mb-8 tracking-tight">Halo, Flinn!</h2>
            <div id="mainGrid" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-6">
                </div>
        </div>

        <div id="searchView" style="display:none;">
            <div class="search-container">
                <div class="relative">
                    <i class="fa-solid fa-magnifying-glass absolute left-5 top-4 text-zinc-400"></i>
                    <input type="text" id="searchInput" placeholder="Cari jutaan lagu di YouTube..." class="search-input">
                </div>
            </div>
            <div id="searchResultGrid" class="px-8 pb-40 space-y-3">
                </div>
        </div>
    </main>

    <footer class="player-bar">
        <div class="flex items-center gap-4 w-[30%] min-w-[200px]">
            <img id="trackCover" src="https://via.placeholder.com/60" class="w-16 h-16 rounded-md shadow-lg">
            <div class="truncate">
                <div id="trackTitle" class="font-bold text-sm truncate text-white">Selamat Datang</div>
                <div id="trackArtist" class="text-[12px] text-zinc-400 truncate">Flinn Enterprise Music</div>
            </div>
            <i id="btnFav" class="fa-solid fa-heart text-zinc-600 cursor-pointer hover:scale-125 transition ml-3" onclick="toggleFavorite()"></i>
        </div>

        <div class="flex flex-col items-center w-[40%] gap-3">
            <div class="flex items-center gap-8">
                <i id="shuffleBtn" onclick="toggleShuffle()" class="fa-solid fa-shuffle text-sm text-zinc-500 cursor-pointer hover:text-white transition"></i>
                <i onclick="playPrev()" class="fa-solid fa-backward-step text-2xl text-zinc-300 hover:text-white cursor-pointer"></i>
                <button id="masterPlayBtn" class="bg-white text-black w-12 h-12 rounded-full flex items-center justify-center hover:scale-110 active:scale-95 transition shadow-white/10 shadow-xl">
                    <i class="fa-solid fa-play text-xl ml-1"></i>
                </button>
                <i onclick="playNext()" class="fa-solid fa-forward-step text-2xl text-zinc-300 hover:text-white cursor-pointer"></i>
                <i id="repeatBtn" onclick="toggleRepeat()" class="fa-solid fa-repeat text-sm text-zinc-500 cursor-pointer hover:text-white transition"></i>
            </div>
            <div class="w-full flex items-center gap-4">
                <span id="timeCurr" class="text-[11px] font-medium text-zinc-500 w-10 text-right">0:00</span>
                <div class="progress-container" id="progLine">
                    <div id="progFill" class="progress-fill"></div>
                </div>
                <span id="timeTotal" class="text-[11px] font-medium text-zinc-500 w-10">0:00</span>
            </div>
        </div>

        <div class="flex items-center justify-end gap-4 w-[30%]">
            <i class="fa-solid fa-volume-high text-zinc-400 text-sm"></i>
            <input type="range" id="volRange" min="0" max="1" step="0.01" value="1" class="w-28 accent-white cursor-pointer">
        </div>
    </footer>
</div>

<audio id="coreAudio"></audio>

<script>
    /**
     * --------------------------------------------------------
     * FLINN-IFY JAVASCRIPT ENGINE
     * --------------------------------------------------------
     */
    const audio = document.getElementById('coreAudio');
    const playBtn = document.getElementById('masterPlayBtn');
    let currentQueue = [];
    let originalQueue = [];
    let activeIndex = -1;
    let isShuffle = false;
    let isRepeat = false;
    let currentSongData = null;

    // --- ROUTING ENGINE ---
    function routeTo(dest, pid = null) {
        document.getElementById('homeView').style.display = (dest === 'search') ? 'none' : 'block';
        document.getElementById('searchView').style.display = (dest === 'search') ? 'block' : 'none';
        
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
        if(dest === 'home') { document.getElementById('navHome').classList.add('active'); loadContent('home'); }
        if(dest === 'search') { document.getElementById('navSearch').classList.add('active'); }
        if(dest === 'liked') { document.getElementById('navLiked').classList.add('active'); loadContent('liked'); }
        if(dest === 'playlist') loadContent('playlist', pid);
    }

    // --- CONTENT LOADER ---
    async function loadContent(mode, pid = null) {
        const res = await fetch(`/api/content?mode=${mode}${pid ? '&pid='+pid : ''}`);
        const data = await res.json();
        originalQueue = [...data.songs];
        currentQueue = isShuffle ? [...data.songs].sort(() => Math.random() - 0.5) : [...data.songs];
        
        document.getElementById('sectionTitle').innerText = data.title;
        document.getElementById('mainGrid').innerHTML = data.songs.map((s, i) => `
            <div class="music-card group" onclick="playFromGrid('${s.yt_id}')" style="animation: slideUp 0.5s ease ${i*0.05}s both">
                <div class="relative overflow-hidden rounded-lg">
                    <img src="${s.cover}">
                    <div class="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition">
                        <i class="fa-solid fa-circle-play text-5xl text-green-500 bg-black rounded-full"></i>
                    </div>
                </div>
                <div class="font-bold text-sm truncate mt-3">${s.title}</div>
                <div class="text-[11px] text-zinc-500 truncate font-semibold">${s.artist}</div>
            </div>`).join('');
    }

    async function refreshSidebar() {
        const r = await fetch('/api/playlists');
        const data = await r.json();
        document.getElementById('sidebarPlaylists').innerHTML = data.map(p => `
            <div class="flex items-center justify-between p-3 hover:bg-zinc-800/50 rounded-lg group cursor-pointer transition" onclick="routeTo('playlist', ${p.id})">
                <div class="flex items-center gap-4 truncate">
                    <div class="w-12 h-12 bg-zinc-800 flex items-center justify-center rounded-md shadow-lg">
                        <i class="fa-solid fa-compact-disc text-zinc-600"></i>
                    </div>
                    <div class="truncate">
                        <div class="text-[13px] font-bold text-white truncate">${p.name}</div>
                        <div class="text-[10px] text-zinc-500 font-bold uppercase tracking-tighter">Playlist • Flinn</div>
                    </div>
                </div>
                <i class="fa-solid fa-trash-can text-xs text-zinc-700 opacity-0 group-hover:opacity-100 hover:text-red-500 transition" onclick="ui_deletePlaylist(event, ${p.id})"></i>
            </div>`).join('');
    }

    // --- SEARCH & PLAYLIST MANAGEMENT ---
    let pendingSong = null;
    document.getElementById('searchInput').oninput = async (e) => {
        const q = e.target.value;
        if(q.length < 2) return;
        const res = await fetch('/api/search_suggestions', { 
            method:'POST', headers:{'Content-Type':'application/json'}, 
            body: JSON.stringify({q: q}) 
        });
        const results = await res.json();
        document.getElementById('searchResultGrid').innerHTML = results.map(item => `
            <div class="flex items-center gap-5 p-3 hover:bg-white/5 rounded-xl group transition">
                <img src="${item.cover}" class="w-14 h-14 rounded shadow-xl">
                <div class="flex-1 truncate">
                    <div class="text-sm font-bold text-white">${item.title}</div>
                    <div class="text-xs text-zinc-500">${item.artist}</div>
                </div>
                <button onclick='openPlaylistModal(${JSON.stringify(item).replace(/'/g, "&apos;")})' 
                        class="bg-white text-black px-5 py-2 rounded-full text-xs font-black opacity-0 group-hover:opacity-100 hover:scale-105 transition">
                    SIMPAN
                </button>
            </div>`).join('');
    };

    async function openPlaylistModal(song) {
        pendingSong = song;
        const res = await fetch('/api/playlists');
        const playlists = await res.json();
        document.getElementById('playlistOptions').innerHTML = playlists.map(p => `
            <div onclick="confirmAdd(${p.id})" class="p-4 bg-zinc-800/50 hover:bg-green-500 hover:text-black rounded-xl cursor-pointer font-bold text-sm transition">
                <i class="fa-solid fa-music mr-2"></i> ${p.name}
            </div>
        `).join('');
        document.getElementById('playlistModal').style.display = 'flex';
    }

    function closeModal() { document.getElementById('playlistModal').style.display = 'none'; }

    async function confirmAdd(pid) {
        if(!pendingSong) return;
        pendingSong.pid = pid;
        await fetch('/api/add_to_db', { 
            method:'POST', headers:{'Content-Type':'application/json'}, 
            body: JSON.stringify(pendingSong) 
        });
        closeModal();
        refreshSidebar();
    }

    // --- AUDIO CORE PLAYER ---
    function playFromGrid(ytId) {
        const idx = currentQueue.findIndex(s => s.yt_id === ytId);
        if(idx !== -1) playQueueAt(idx);
    }

    function playQueueAt(index) {
        if(index < 0 || index >= currentQueue.length) return;
        activeIndex = index;
        const song = currentQueue[index];
        currentSongData = song;
        startStreaming(song);
    }

    async function startStreaming(song) {
        playBtn.innerHTML = '<i class="fa-solid fa-circle-notch animate-spin"></i>';
        const res = await fetch('/api/stream/' + song.yt_id);
        const data = await res.json();
        
        audio.src = data.url;
        audio.play();
        
        document.getElementById('trackTitle').innerText = song.title;
        document.getElementById('trackArtist').innerText = song.artist;
        document.getElementById('trackCover').src = song.cover;
        updateFavIcon(song.is_favorite);
        playBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
    }

    function updateFavIcon(isFav) {
        const icon = document.getElementById('btnFav');
        icon.className = isFav ? 'fa-solid fa-heart heart-active' : 'fa-solid fa-heart text-zinc-600';
    }

    playBtn.onclick = () => {
        if(!audio.src) return;
        if(audio.paused) { audio.play(); playBtn.innerHTML = '<i class="fa-solid fa-pause"></i>'; }
        else { audio.pause(); playBtn.innerHTML = '<i class="fa-solid fa-play ml-1"></i>'; }
    };

    function playNext() { 
        if(isRepeat) { audio.currentTime = 0; audio.play(); }
        else { playQueueAt(activeIndex + 1); }
    }
    function playPrev() { playQueueAt(activeIndex - 1); }
    audio.onended = () => playNext();

    // --- SHUFFLE & REPEAT ---
    function toggleShuffle() {
        isShuffle = !isShuffle;
        document.getElementById('shuffleBtn').classList.toggle('active-green', isShuffle);
        if(isShuffle) currentQueue = [...currentQueue].sort(() => Math.random() - 0.5);
        else currentQueue = [...originalQueue];
    }

    function toggleRepeat() {
        isRepeat = !isRepeat;
        document.getElementById('repeatBtn').classList.toggle('active-green', isRepeat);
    }

    async function toggleFavorite() {
        if(!currentSongData) return;
        const res = await fetch('/api/toggle_favorite', { 
            method:'POST', headers:{'Content-Type':'application/json'}, 
            body: JSON.stringify({yt_id: currentSongData.yt_id}) 
        });
        const data = await res.json();
        currentSongData.is_favorite = data.is_favorite;
        updateFavIcon(data.is_favorite);
        if(document.getElementById('navLiked').classList.contains('active')) loadContent('liked');
    }

    // --- UTILITIES ---
    audio.ontimeupdate = () => {
        if(audio.duration) {
            const perc = (audio.currentTime / audio.duration) * 100;
            document.getElementById('progFill').style.width = perc + '%';
            document.getElementById('timeCurr').innerText = formatTime(audio.currentTime);
            document.getElementById('timeTotal').innerText = formatTime(audio.duration);
        }
    };

    document.getElementById('progLine').onclick = (e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        audio.currentTime = ((e.clientX - rect.left) / rect.width) * audio.duration;
    };

    function formatTime(s) {
        const m = Math.floor(s/60);
        const sec = Math.floor(s%60);
        return `${m}:${sec < 10 ? '0' : ''}${sec}`;
    }

    document.getElementById('volRange').oninput = (e) => audio.volume = e.target.value;

    function ui_createPlaylist() {
        const n = prompt("Beri nama playlist barumu, Flinn:");
        if(n) fetch('/api/create_playlist', { 
            method:'POST', headers:{'Content-Type':'application/json'}, 
            body: JSON.stringify({name:n}) 
        }).then(() => refreshSidebar());
    }

    function ui_deletePlaylist(e, id) {
        e.stopPropagation();
        if(confirm("Hapus playlist ini secara permanen?")) {
            fetch('/api/delete_playlist', { 
                method:'POST', headers:{'Content-Type':'application/json'}, 
                body: JSON.stringify({id:id}) 
            }).then(() => { refreshSidebar(); routeTo('home'); });
        }
    }

    // BOOTSTRAP SYSTEM
    init_db();
    refreshSidebar();
    routeTo('home');
</script>
</body>
</html>
'''

# PENYESUAIAN VERCEL NO 4:
# Tidak boleh ada app.run() di sini. 
# Cukup export variabel 'app'.
init_db() 
# app = app (sudah otomatis di Flask)
