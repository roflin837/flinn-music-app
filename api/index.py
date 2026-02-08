from flask import Flask, render_template_string, jsonify, request
import sqlite3, yt_dlp, requests, os, json

app = Flask(__name__)

# Flinn, kita simpan di /tmp untuk operasional, tapi kita backup ke folder lokal
DB_NAME = '/tmp/flinn_enterprise.db'
BACKUP_FILE = 'database_backup.json' # File ini aman di GitHub/Vercel (Read-only)

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # Cek apakah DB sudah ada di /tmp, jika belum, coba restore dari backup
    db_exists = os.path.exists(DB_NAME)
    
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, description TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, artist TEXT, 
            cover TEXT, duration TEXT, yt_id TEXT, pid INTEGER,
            is_favorite INTEGER DEFAULT 0,
            FOREIGN KEY(pid) REFERENCES playlists(id) ON DELETE CASCADE)''')
        
        conn.execute("INSERT OR IGNORE INTO playlists (id, name, description) VALUES (1, 'Koleksi Utama', 'Default')")
        conn.execute("INSERT OR IGNORE INTO playlists (id, name, description) VALUES (99, 'Lagu Favorit', 'Liked')")
        conn.commit()

    # Jika baru nyala (DB di /tmp kosong), isi dari backup JSON
    if not db_exists and os.path.exists(BACKUP_FILE):
        restore_data()

def restore_data():
    try:
        with open(BACKUP_FILE, 'r') as f:
            data = json.load(f)
            with get_db() as conn:
                for s in data['songs']:
                    conn.execute('''INSERT OR IGNORE INTO songs (title, artist, cover, duration, yt_id, pid, is_favorite) 
                                 VALUES (?,?,?,?,?,?,?)''', (s['title'], s['artist'], s['cover'], s['duration'], s['yt_id'], s['pid'], s['is_favorite']))
                conn.commit()
    except: pass

# --- UI & LOGIC ---
@app.route('/api/content')
def get_content():
    mode = request.args.get('mode', 'home')
    pid = request.args.get('pid')
    init_db()
    with get_db() as conn:
        if mode == 'liked':
            songs = conn.execute('SELECT * FROM songs WHERE is_favorite = 1').fetchall()
            title = "Lagu Favorit"
        elif mode == 'playlist' and pid:
            songs = conn.execute('SELECT * FROM songs WHERE pid = ?', (pid,)).fetchall()
            res = conn.execute('SELECT name FROM playlists WHERE id = ?', (pid,)).fetchone()
            title = res['name'] if res else "Playlist"
        else:
            songs = conn.execute('SELECT * FROM songs ORDER BY id DESC').fetchall()
            title = "Koleksi Flinn"
        
        return jsonify({"songs": [dict(s) for s in songs], "title": title})

# ... (Route lainnya seperti stream, search, dll tetap sama dengan kode kamu) ...
@app.route('/api/stream/<yt_id>')
def api_stream(yt_id):
    opts = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={yt_id}", download=False)
            return jsonify({"url": info['url']})
        except: return jsonify({"error": "Error"}), 404

@app.route('/api/search_suggestions', methods=['POST'])
def search_suggestions():
    q = request.json.get('q')
    opts = {'default_search': 'ytsearch10', 'quiet': True, 'noplaylist': True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        res = ydl.extract_info(q, download=False)
        output = []
        for info in res.get('entries', []):
            output.append({
                "title": info.get('title'), "artist": info.get('uploader'),
                "cover": info.get('thumbnail'), "duration": str(info.get('duration')),
                "yt_id": info.get('id')
            })
        return jsonify(output)

@app.route('/')
def index():
    init_db()
    return render_template_string(HTML_TEMPLATE)

# HTML TEMPLATE DENGAN PERBAIKAN RESPONSIVE HP
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Flinn-ify Enterprise</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');
        :root { --spotify-green: #1db954; --bg-main: #121212; }
        body { background: #000; color: #fff; font-family: 'Plus Jakarta Sans', sans-serif; margin: 0; overflow: hidden; }

        /* Mobile Adjustments */
        .app-shell { 
            display: grid; 
            grid-template-areas: "sidebar main" "player player";
            grid-template-columns: 280px 1fr;
            grid-template-rows: 1fr 100px;
            height: 100vh;
        }

        @media (max-width: 768px) {
            .app-shell {
                grid-template-areas: "main" "player";
                grid-template-columns: 1fr;
                grid-template-rows: 1fr 140px; /* Player lebih tinggi di HP */
            }
            .sidebar { display: none; }
            .mobile-nav { display: flex !important; }
            .main-content { padding-bottom: 80px; }
            #mainGrid { grid-template-columns: repeat(2, 1fr) !important; gap: 12px; padding: 15px; }
            .search-input { width: 100% !important; }
        }

        .mobile-nav {
            display: none; position: fixed; bottom: 100px; left: 0; right: 0;
            background: linear-gradient(transparent, #000); height: 60px;
            justify-content: space-around; align-items: center; z-index: 100;
        }

        .main-content { grid-area: main; overflow-y: auto; background: linear-gradient(#1e1e1e 0%, #121212 30%); }
        .player-bar { 
            grid-area: player; background: #000; border-top: 1px solid #222; 
            display: flex; align-items: center; justify-content: space-between; padding: 0 15px;
        }
        
        .music-card { background: #181818; padding: 12px; border-radius: 8px; transition: 0.3s; cursor: pointer; }
        .music-card:hover { background: #282828; }
        .music-card img { width: 100%; aspect-ratio: 1; border-radius: 4px; object-fit: cover; }
        
        /* Progress Bar */
        .prog-bg { width: 100%; height: 4px; background: #444; border-radius: 2px; cursor: pointer; }
        .prog-fill { height: 100%; background: #fff; width: 0%; border-radius: 2px; }
    </style>
</head>
<body>

    <div class="app-shell">
        <aside class="sidebar p-4 flex flex-col gap-4 bg-black">
            <div class="bg-zinc-900 rounded-xl p-4">
                <div class="flex items-center gap-4 p-3 text-white font-bold cursor-pointer" onclick="routeTo('home')"><i class="fa-solid fa-house"></i> Home</div>
                <div class="flex items-center gap-4 p-3 text-zinc-400 font-bold cursor-pointer" onclick="routeTo('search')"><i class="fa-solid fa-magnifying-glass"></i> Search</div>
            </div>
            <div class="bg-zinc-900 rounded-xl p-4 flex-1 overflow-y-auto" id="sidebarPlaylists">
                </div>
        </aside>

        <main class="main-content" id="scrollArea">
            <div id="homeView" class="p-4 md:p-8">
                <h1 id="sectionTitle" class="text-2xl md:text-4xl font-extrabold mb-6 mt-4">Koleksi Flinn</h1>
                <div id="mainGrid" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4"></div>
            </div>

            <div id="searchView" class="p-4 md:p-8" style="display:none">
                <input type="text" id="searchInput" placeholder="Cari lagu..." class="w-full bg-zinc-800 p-4 rounded-full outline-none mb-8">
                <div id="searchResultGrid" class="space-y-4"></div>
            </div>
        </main>

        <footer class="player-bar flex-col md:flex-row gap-2 py-2">
            <div class="flex items-center gap-3 w-full md:w-[30%]">
                <img id="trackCover" src="" class="w-12 h-12 rounded bg-zinc-800">
                <div class="overflow-hidden">
                    <div id="trackTitle" class="text-sm font-bold truncate">Pilih Lagu</div>
                    <div id="trackArtist" class="text-xs text-zinc-400 truncate">Flinn Music</div>
                </div>
            </div>

            <div class="flex flex-col items-center w-full md:w-[40%] gap-1">
                <div class="flex items-center gap-6">
                    <i class="fa-solid fa-backward-step cursor-pointer" onclick="playPrev()"></i>
                    <button id="playBtn" class="bg-white text-black w-10 h-10 rounded-full flex items-center justify-center">
                        <i class="fa-solid fa-play"></i>
                    </button>
                    <i class="fa-solid fa-forward-step cursor-pointer" onclick="playNext()"></i>
                </div>
                <div class="flex items-center gap-2 w-full px-4">
                    <span id="timeCurr" class="text-[10px]">0:00</span>
                    <div class="prog-bg" id="progLine"><div id="progFill" class="prog-fill"></div></div>
                    <span id="timeTotal" class="text-[10px]">0:00</span>
                </div>
            </div>

            <div class="hidden md:flex items-center justify-end w-[30%] gap-3">
                <i class="fa-solid fa-volume-high text-xs text-zinc-400"></i>
                <input type="range" id="volRange" min="0" max="1" step="0.1" value="1" class="w-24 accent-white">
            </div>
        </footer>

        <nav class="mobile-nav">
            <div onclick="routeTo('home')" class="flex flex-col items-center gap-1"><i class="fa-solid fa-house"></i><span class="text-[10px]">Home</span></div>
            <div onclick="routeTo('search')" class="flex flex-col items-center gap-1 text-zinc-400"><i class="fa-solid fa-magnifying-glass"></i><span class="text-[10px]">Cari</span></div>
            <div onclick="routeTo('liked')" class="flex flex-col items-center gap-1 text-zinc-400"><i class="fa-solid fa-heart"></i><span class="text-[10px]">Favorit</span></div>
        </nav>
    </div>

    <audio id="audioCore"></audio>

    <script>
        const audio = document.getElementById('audioCore');
        const playBtn = document.getElementById('playBtn');
        let currentQueue = [];
        let activeIdx = -1;

        async function routeTo(dest, pid=null) {
            document.getElementById('homeView').style.display = dest === 'search' ? 'none' : 'block';
            document.getElementById('searchView').style.display = dest === 'search' ? 'block' : 'none';
            if(dest !== 'search') loadContent(dest, pid);
        }

        async function loadContent(mode, pid=null) {
            const res = await fetch(`/api/content?mode=${mode}${pid ? '&pid='+pid : ''}`);
            const data = await res.json();
            currentQueue = data.songs;
            document.getElementById('sectionTitle').innerText = data.title;
            document.getElementById('mainGrid').innerHTML = data.songs.map((s, i) => `
                <div class="music-card" onclick="playAt(${i})">
                    <img src="${s.cover}">
                    <div class="text-sm font-bold truncate mt-2">${s.title}</div>
                    <div class="text-xs text-zinc-500 truncate">${s.artist}</div>
                </div>
            `).join('');
        }

        async function playAt(idx) {
            if(idx < 0 || idx >= currentQueue.length) return;
            activeIdx = idx;
            const song = currentQueue[idx];
            
            document.getElementById('trackTitle').innerText = song.title;
            document.getElementById('trackArtist').innerText = song.artist;
            document.getElementById('trackCover').src = song.cover;
            playBtn.innerHTML = '<i class="fa-solid fa-circle-notch animate-spin"></i>';

            const res = await fetch('/api/stream/' + song.yt_id);
            const data = await res.json();
            audio.src = data.url;
            audio.play();
            playBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
        }

        playBtn.onclick = () => {
            if(!audio.src) return;
            if(audio.paused) { audio.play(); playBtn.innerHTML = '<i class="fa-solid fa-pause"></i>'; }
            else { audio.pause(); playBtn.innerHTML = '<i class="fa-solid fa-play"></i>'; }
        }

        audio.ontimeupdate = () => {
            const p = (audio.currentTime / audio.duration) * 100;
            document.getElementById('progFill').style.width = p + '%';
            document.getElementById('timeCurr').innerText = formatTime(audio.currentTime);
            document.getElementById('timeTotal').innerText = formatTime(audio.duration || 0);
        }

        function formatTime(s) {
            const m = Math.floor(s/60);
            const sec = Math.floor(s%60);
            return `${m}:${sec < 10 ? '0' : ''}${sec}`;
        }

        // Search Logic
        document.getElementById('searchInput').onkeypress = async (e) => {
            if(e.key === 'Enter') {
                const q = e.target.value;
                const res = await fetch('/api/search_suggestions', {
                    method: 'POST', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({q: q})
                });
                const results = await res.json();
                document.getElementById('searchResultGrid').innerHTML = results.map(s => `
                    <div class="flex items-center gap-4 bg-zinc-900 p-2 rounded-lg">
                        <img src="${s.cover}" class="w-12 h-12 rounded">
                        <div class="flex-1 truncate">
                            <div class="text-sm font-bold truncate">${s.title}</div>
                            <div class="text-xs text-zinc-500">${s.artist}</div>
                        </div>
                        <button onclick='saveSong(${JSON.stringify(s).replace(/'/g, "&apos;")})' class="bg-white text-black text-[10px] px-3 py-1 rounded-full font-bold">SIMPAN</button>
                    </div>
                `).join('');
            }
        }

        async function saveSong(song) {
            await fetch('/api/add_to_db', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({...song, pid: 1})
            });
            alert("Tersimpan!");
        }

        loadContent('home');
    </script>
</body>
</html>
'''

# PENYESUAIAN VERCEL NO 4:
# Tidak boleh ada app.run() di sini. 
# Cukup export variabel 'app'.
init_db() 
# app = app (sudah otomatis di Flask)
