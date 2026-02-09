from flask import Flask, render_template_string, jsonify, request
import sqlite3, yt_dlp, os, requests

app = Flask(__name__)

# Database Config
IS_VERCEL = "VERCEL" in os.environ
DB_PATH = '/tmp/flinn_music.db' if IS_VERCEL else 'flinn_music.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            title TEXT, artist TEXT, cover TEXT, 
            duration TEXT, yt_id TEXT UNIQUE)''')
        conn.commit()

@app.route('/')
def index():
    init_db()
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/content')
def get_content():
    with get_db() as conn:
        songs = conn.execute('SELECT * FROM songs ORDER BY id DESC').fetchall()
        return jsonify({"songs": [dict(s) for s in songs]})

@app.route('/api/add', methods=['POST'])
def add_song():
    s = request.json
    try:
        with get_db() as conn:
            # Pastikan field yang wajib ada tidak kosong
            if not s.get('yt_id'): return jsonify({"status": "error"}), 400
            
            conn.execute('INSERT OR IGNORE INTO songs (title, artist, cover, duration, yt_id) VALUES (?,?,?,?,?)',
                         (s.get('title', 'Unknown Title'), 
                          s.get('artist', 'Unknown Artist'), 
                          s.get('cover'), 
                          s.get('duration', '0:00'), 
                          s.get('yt_id')))
            conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Error add_song: {e}")
        return jsonify({"status": "error"}), 500
    
@app.route('/api/delete/<yt_id>', methods=['DELETE'])
def delete_song(yt_id):
    try:
        with get_db() as conn:
            conn.execute('DELETE FROM songs WHERE yt_id = ?', (yt_id,))
            conn.commit()
        return jsonify({"status": "deleted"})
    except:
        return jsonify({"status": "error"}), 500

@app.route('/api/stream/<yt_id>')
def stream(yt_id):
    try:
        # Pake instance yang beda buat jaga-jaga
        piped_api = f"https://pipedapi.lunar.icu/streams/{yt_id}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        res = requests.get(piped_api, headers=headers, timeout=10)
        data = res.json()
        
        # Cari audio stream yang bukan cuma link, tapi ada isinya
        audio_streams = data.get('audioStreams', [])
        
        if audio_streams:
            # Kadang urutan pertama bukan yang terbaik, tapi kita ambil yang ada
            return jsonify({"url": audio_streams[0]['url']})
        
        return jsonify({"error": "Audio tidak ditemukan di server Piped"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Music Hub - Flinn</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Figtree:wght@300;400;600;700;800&display=swap');
    body { background-color: #000; color: white; font-family: 'Figtree', sans-serif; margin: 0; overflow: hidden; cursor: default; }
    .main-content { height: 100vh; overflow-y: auto; padding: 20px 16px 180px 16px; background: linear-gradient(to bottom, #1a1a1a 0%, #000 35%); }
    .player-bar { position: fixed; bottom: 80px; left: 8px; right: 8px; background: #282828; border-radius: 8px; padding: 8px 12px; display: flex; align-items: center; z-index: 100; cursor: pointer; }
    .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; height: 70px; background: rgba(0,0,0,0.95); display: flex; justify-content: space-around; align-items: center; border-top: 1px solid #111; z-index: 101; }
    .nav-item { display: flex; flex-direction: column; align-items: center; color: #b3b3b3; font-size: 10px; gap: 4px; cursor: pointer; }
    .nav-item.active { color: white; }
    .no-scrollbar::-webkit-scrollbar { display: none; }
    
    .menu-card, .cat-card, button, i, .clickable { cursor: pointer; }
    .menu-card { background: rgba(255,255,255,0.1); transition: all 0.2s; }
    .menu-card:hover { background: rgba(255,255,255,0.15); transform: translateY(-1px); }
    .menu-card:active { background: rgba(255,255,255,0.2); transform: scale(0.98); }
    
    .cat-card { transition: transform 0.2s; }
    .cat-card:hover { transform: scale(1.05); }
</style>
</head>
<body>

<div class="app-shell">
    <main class="main-content no-scrollbar">
        <div id="homeView">
            <div class="flex justify-between items-center mb-6 mt-4">
                <h1 class="text-2xl font-bold italic tracking-tight">Halo, Flinn!</h1>
                <div class="flex gap-4 text-xl">
                    <i class="fa-regular fa-bell cursor-pointer hover:text-green-500 transition" onclick="alert('Belum ada notifikasi baru untuk Flinn!')"></i>
                    <i class="fa-solid fa-clock-rotate-left cursor-pointer hover:text-green-500 transition" onclick="changeTab('library', document.querySelectorAll('.nav-item')[2])"></i>
                    <i class="fa-solid fa-gear cursor-pointer hover:text-green-500 transition" onclick="alert('Menu Pengaturan akan segera hadir!')"></i>
                </div>
            </div>

            <div class="flex gap-2 mb-6 overflow-x-auto no-scrollbar">
                <span class="px-4 py-1.5 bg-green-500 text-black rounded-full text-[11px] font-semibold cursor-pointer active:scale-95 transition" onclick="alert('Menampilkan semua Musik')">Music</span>
                <span class="px-4 py-1.5 bg-zinc-800 rounded-full text-[11px] font-semibold cursor-pointer text-zinc-300 active:scale-95 transition" onclick="quickSearch('Podcast Indonesia')">Podcasts</span>
            </div>

            <div class="grid grid-cols-2 gap-2 mb-8">
                <div class="menu-card flex items-center rounded-md overflow-hidden h-14" onclick="changeTab('library', document.querySelectorAll('.nav-item')[2])">
                    <div class="w-14 h-full bg-gradient-to-br from-indigo-700 to-purple-400 flex items-center justify-center shadow-lg">
                        <i class="fa-solid fa-heart text-white text-lg"></i>
                    </div>
                    <span class="ml-3 text-[11px] font-bold">Liked Songs</span>
                </div>

                <div class="menu-card flex items-center rounded-md overflow-hidden h-14" onclick="quickSearch('On Repeat')">
                    <img src="https://images.unsplash.com/photo-1493225255756-d9584f8606e9?w=100" class="w-14 h-full object-cover">
                    <span class="ml-3 text-[11px] font-bold">On Repeat</span>
                </div>

                <div class="menu-card flex items-center rounded-md overflow-hidden h-14" onclick="quickSearch('Daily Mix 1')">
                    <img src="https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=100" class="w-14 h-full object-cover">
                    <span class="ml-3 text-[11px] font-bold">Daily Mix 1</span>
                </div>

                <div class="menu-card flex items-center rounded-md overflow-hidden h-14" onclick="quickSearch('Chill Mix')">
                    <img src="https://images.unsplash.com/photo-1494232410401-ad00d5433cfa?w=200&h=200&fit=crop" class="w-14 h-full object-cover">
                    <span class="ml-3 text-[11px] font-bold">Chill Mix</span>
                </div>

                <div class="menu-card flex items-center rounded-md overflow-hidden h-14" onclick="quickSearch('New Release Music')">
                    <img src="https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=200&h=200&fit=crop" class="w-14 h-full object-cover">
                    <span class="ml-3 text-[11px] font-bold">New Release</span>
                </div>

                <div class="menu-card flex items-center rounded-md overflow-hidden h-14" onclick="quickSearch('Gaming Beats')">
                    <img src="https://images.unsplash.com/photo-1542751371-adc38448a05e?w=100" class="w-14 h-full object-cover">
                    <span class="ml-3 text-[11px] font-bold">Gaming Beat</span>
                </div>
            </div>

            <div class="mb-8">
                <h2 class="text-xl font-bold mb-4">Recommended for you</h2>
                <div class="relative w-full aspect-[16/9] rounded-xl overflow-hidden shadow-2xl cursor-pointer" onclick="quickSearch('Deep Focus Instrument')">
                    <img src="https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?q=80&w=1000&auto=format&fit=crop" class="w-full h-full object-cover">
                    <div class="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent p-5 flex flex-col justify-end">
                        <span class="text-[10px] font-black text-green-400 uppercase tracking-widest mb-1">Focus Mode</span>
                        <h3 class="text-3xl font-black leading-none mb-1">Deep Focus</h3>
                        <p class="text-xs text-zinc-300 opacity-80">Tetap tenang dan produktif dengan instrumen pilihan.</p>
                    </div>
                </div>
            </div>

            <h2 class="text-xl font-bold mb-4">Your Top Categories</h2>
            <div class="flex gap-4 overflow-x-auto no-scrollbar pb-10">
                <div class="cat-card w-32 h-32 flex-shrink-0 bg-pink-600 rounded-lg p-3 relative overflow-hidden" onclick="quickSearch('Pop Music')">
                    <span class="font-bold text-sm">Pop</span>
                    <img src="https://picsum.photos/id/1025/150/150" 
                        class="w-16 h-16 absolute -right-2 -bottom-2 rotate-[25deg] shadow-lg object-cover rounded-md bg-zinc-800">
                </div>

                <div class="cat-card w-32 h-32 flex-shrink-0 bg-orange-600 rounded-lg p-3 relative overflow-hidden" onclick="quickSearch('Rock Music')">
                    <span class="font-bold text-sm">Rock</span>
                    <img src="https://picsum.photos/id/1082/150/150" 
                        class="w-16 h-16 absolute -right-2 -bottom-2 rotate-[25deg] shadow-lg object-cover rounded-md bg-zinc-800">
                </div>

                <div class="cat-card w-32 h-32 flex-shrink-0 bg-blue-700 rounded-lg p-3 relative overflow-hidden" onclick="quickSearch('Hip-Hop Music')">
                    <span class="font-bold text-sm">Hip-Hop</span>
                    <img src="https://picsum.photos/id/1031/150/150" 
                        class="w-16 h-16 absolute -right-2 -bottom-2 rotate-[25deg] shadow-lg object-cover rounded-md bg-zinc-800">
                </div>

                <div class="cat-card w-32 h-32 flex-shrink-0 bg-green-600 rounded-lg p-3 relative overflow-hidden" onclick="quickSearch('Indie Indonesia')">
                    <span class="font-bold text-sm">Indie</span>
                    <img src="https://picsum.photos/id/1075/150/150" 
                        class="w-16 h-16 absolute -right-2 -bottom-2 rotate-[25deg] shadow-lg object-cover rounded-md bg-zinc-800">
                </div>
            </div>
        </div>

        <div id="searchView" class="hidden">
            <h1 class="text-3xl font-bold mb-6">Cari</h1>
            <div class="relative mb-6">
                <input type="text" id="searchInput" autocomplete="off" placeholder="Mau dengerin apa?" 
                    class="w-full p-4 rounded-full bg-zinc-800 text-white font-medium outline-none border border-transparent focus:border-zinc-500">
                <button onclick="doSearch()" class="absolute right-5 top-4 text-zinc-400">
                    <i class="fa-solid fa-magnifying-glass"></i>
                </button>
            </div>
            <div id="searchResult" class="space-y-2"></div>
        </div>

        <div id="libraryView" class="hidden">
            <h1 class="text-2xl font-bold mb-6 mt-4">Koleksi Kamu</h1>
            <div id="libraryList" class="space-y-4"></div>
        </div>
    </main>

    <div class="player-bar" onclick="if(event.target.id !== 'playBtn') toggleNowPlaying()">
        <img id="pCover" src="https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=100" 
             onerror="this.src='https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=100'"
             class="w-10 h-10 rounded shadow-md object-cover">
        <div class="flex-1 ml-3 overflow-hidden">
            <div id="pTitle" class="text-sm font-bold truncate">Pilih Lagu</div>
            <div id="pArtist" class="text-[11px] text-zinc-400 truncate">Flinn Music</div>
        </div>
        <div class="flex items-center gap-4">
             <i class="fa-solid fa-play text-2xl" id="playBtn" onclick="togglePlay(event)"></i>
        </div>
    </div>

    <div id="nowPlayingModal" class="fixed inset-0 bg-zinc-950 z-[200] translate-y-full transition-transform duration-300 flex flex-col p-8 overflow-hidden">
            <div class="flex justify-between items-center mb-6">
                <i class="fa-solid fa-chevron-down text-xl p-2 cursor-pointer" onclick="toggleNowPlaying()"></i>
                <span class="text-[10px] font-bold tracking-widest uppercase opacity-70">Now Playing</span>
                <i class="fa-solid fa-ellipsis-vertical text-xl p-2 cursor-pointer" onclick="showMore()"></i>
            </div>
            
            <div class="flex-1 flex flex-col items-center justify-center">
                <div class="w-full max-w-[320px] aspect-square mb-8 shadow-2xl">
                    <img id="mCover" src="https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=500" 
                         onerror="this.src='https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=500'"
                         class="w-full h-full object-cover rounded-lg shadow-black/50 shadow-2xl">
                </div>

                <div class="w-full flex justify-between items-center mb-6">
                    <div class="overflow-hidden pr-4">
                        <h2 id="mTitle" class="text-xl font-bold truncate">Judul Lagu</h2>
                        <p id="mArtist" class="text-zinc-400 text-sm">Nama Artis</p>
                    </div>
                    <i class="fa-regular fa-heart text-2xl text-zinc-400 cursor-pointer" onclick="toggleLike(this)"></i>
                </div>

                <div id="progCont" class="w-full bg-zinc-800 h-[4px] rounded-full mb-2 cursor-pointer relative">
                    <div id="progBar" class="bg-white h-full w-0 rounded-full relative pointer-events-none">
                        <div class="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-lg"></div>
                    </div>
                </div>
                <div class="w-full flex justify-between text-[10px] text-zinc-500 mb-8 font-medium">
                    <span id="currTime">0:00</span>
                    <span id="totalTime">0:00</span>
                </div>

                <div class="w-full flex justify-between items-center px-2">
                    <i class="fa-solid fa-shuffle text-zinc-600 text-lg cursor-pointer" onclick="toggleShuffle(this)"></i>
                    <i class="fa-solid fa-backward-step text-2xl cursor-pointer" onclick="prevSong()"></i>
                    <i class="fa-solid fa-circle-play text-7xl text-white cursor-pointer" id="mPlayBtn" onclick="togglePlay(event)"></i>
                    <i class="fa-solid fa-forward-step text-2xl cursor-pointer" onclick="nextSong()"></i>
                    <i class="fa-solid fa-repeat text-zinc-600 text-lg cursor-pointer" onclick="toggleRepeat(this)"></i>
                </div>
            </div>
    </div>

    <nav class="bottom-nav">
        <div class="nav-item active" onclick="changeTab('home', this)">
            <i class="fa-solid fa-house text-xl"></i>
            <span>Home</span>
        </div>
        <div class="nav-item" onclick="changeTab('search', this)">
            <i class="fa-solid fa-magnifying-glass text-xl"></i>
            <span>Cari</span>
        </div>
        <div class="nav-item" onclick="changeTab('library', this)">
            <i class="fa-solid fa-book text-xl"></i>
            <span>Library</span>
        </div>
    </nav>
</div>

<script>
    const audio = new Audio();
    let isPlaying = false;
    let isRepeat = false;
    let isShuffle = false;
    let currentPlaylist = [];
    let currentIndex = -1;

    const DEFAULT_COVER = "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=500";

    function quickSearch(keyword) {
        const searchNavItem = document.querySelectorAll('.nav-item')[1];
        changeTab('search', searchNavItem);
        const input = document.getElementById('searchInput');
        input.value = keyword;
        doSearch();
    }

    function toggleNowPlaying() {
        document.getElementById('nowPlayingModal').classList.toggle('translate-y-full');
    }

    function changeTab(tab, el) {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        el.classList.add('active');
        document.getElementById('homeView').classList.add('hidden');
        document.getElementById('searchView').classList.add('hidden');
        document.getElementById('libraryView').classList.add('hidden');
        if(tab === 'home') { document.getElementById('homeView').classList.remove('hidden'); }
        else if(tab === 'search') { document.getElementById('searchView').classList.remove('hidden'); }
        else if(tab === 'library') { document.getElementById('libraryView').classList.remove('hidden'); renderLibrary(); }
    }

    async function renderLibrary() {
        const res = await fetch('/api/content');
        const data = await res.json();
        currentPlaylist = data.songs;
        const libList = document.getElementById('libraryList');
        if(data.songs.length === 0) {
            libList.innerHTML = '<p class="text-zinc-500 text-center py-10 text-sm italic">Library masih kosong nih.</p>';
            return;
        }
        libList.innerHTML = data.songs.map((s, index) => `
            <div class="flex items-center gap-3 p-2 active:bg-zinc-800 rounded-md cursor-pointer transition">
                <img src="${s.cover}" onerror="this.src='${DEFAULT_COVER}'" class="w-12 h-12 rounded object-cover" onclick="playSongByIndex(${index})">
                <div class="flex-1 overflow-hidden" onclick="playSongByIndex(${index})">
                    <div class="text-sm font-bold truncate">${s.title}</div>
                    <div class="text-[11px] text-zinc-400 truncate">${s.artist}</div>
                </div>
                <i class="fa-solid fa-trash text-zinc-600 p-2 hover:text-red-500 transition" onclick="deleteSong('${s.yt_id}')"></i>
            </div>
        `).join('');
    }

    async function playSongByIndex(index) {
        if (index < 0 || index >= currentPlaylist.length) return;
        currentIndex = index;
        const s = currentPlaylist[index];
        playSong(s.yt_id, s.title, s.artist, s.cover);
    }

    async function playSong(id, title, artist, cover) {
        // 1. Update Tampilan Player
        document.getElementById('pTitle').innerText = title;
        document.getElementById('mTitle').innerText = title;
        document.getElementById('pArtist').innerText = artist;
        document.getElementById('mArtist').innerText = artist;
        document.getElementById('pCover').src = cover;
        document.getElementById('mCover').src = cover;
    
        // 2. Efek Loading
        const btn = document.getElementById('playBtn');
        btn.className = "fa-solid fa-spinner animate-spin text-2xl text-green-500";
    
        // Daftar server Piped (kalau satu mati, dia coba yang lain)
        const instances = [
            'https://pipedapi.lunar.icu',
            'https://api.piped.victr.me',
            'https://pipedapi.kavin.rocks'
        ];
        
        let audioUrl = null;
    
        // 3. Cari link audio langsung dari browser (Bypass Vercel)
        for (let base of instances) {
            try {
                console.log("Mencoba ambil audio dari:", base);
                const res = await fetch(`${base}/streams/${id}`);
                const data = await res.json();
                if (data.audioStreams && data.audioStreams.length > 0) {
                    audioUrl = data.audioStreams[0].url;
                    break; 
                }
            } catch (e) {
                console.error("Server " + base + " gagal, mencoba yang lain...");
            }
        }
    
        if (audioUrl) {
            audio.src = audioUrl;
            audio.play().then(() => {
                isPlaying = true;
                updateUI();
            }).catch(e => {
                alert("Klik Play secara manual untuk memutar!");
                updateUI();
            });
        } else {
            alert("Semua server audio sedang sibuk. Coba lagu lain!");
            updateUI();
        }
    }

    function togglePlay(e) {
        if(e) e.stopPropagation();
        if(!audio.src) return;
        isPlaying ? audio.pause() : audio.play();
        isPlaying = !isPlaying;
        updateUI();
    }

    function updateUI() {
        const miniBtn = document.getElementById('playBtn');
        const fullBtn = document.getElementById('mPlayBtn');
        miniBtn.className = isPlaying ? "fa-solid fa-pause text-2xl cursor-pointer" : "fa-solid fa-play text-2xl cursor-pointer";
        fullBtn.className = isPlaying ? "fa-solid fa-circle-pause text-6xl cursor-pointer" : "fa-solid fa-circle-play text-6xl cursor-pointer";
    }

    function nextSong() { 
        if(currentPlaylist.length === 0) return;
        if(isShuffle) {
            playSongByIndex(Math.floor(Math.random() * currentPlaylist.length));
        } else {
            currentIndex < currentPlaylist.length - 1 ? playSongByIndex(currentIndex + 1) : playSongByIndex(0);
        }
    }
    
    function prevSong() { 
        if(currentPlaylist.length === 0) return;
        currentIndex > 0 ? playSongByIndex(currentIndex - 1) : playSongByIndex(currentPlaylist.length - 1); 
    }

    function toggleRepeat(el) { isRepeat = !isRepeat; el.style.color = isRepeat ? '#22c55e' : '#52525b'; }
    function toggleShuffle(el) { isShuffle = !isShuffle; el.style.color = isShuffle ? '#22c55e' : '#52525b'; }
    function toggleLike(el) { el.classList.toggle('fa-regular'); el.classList.toggle('fa-solid'); el.classList.toggle('text-green-500'); }

    function showMore() {
        if(currentIndex === -1) return;
        const s = currentPlaylist[currentIndex];
        alert(`Lagu: ${s.title}\\nArtis: ${s.artist}`);
    }

    audio.ontimeupdate = () => {
        if (!isNaN(audio.duration)) {
            const prog = (audio.currentTime / audio.duration) * 100;
            document.getElementById('progBar').style.width = prog + '%';
            document.getElementById('currTime').innerText = formatTime(audio.currentTime);
            document.getElementById('totalTime').innerText = formatTime(audio.duration);
        }
    };

    function formatTime(sec) {
        if(!sec || isNaN(sec)) return "0:00";
        let m = Math.floor(sec / 60), s = Math.floor(sec % 60);
        return m + ":" + (s < 10 ? "0" + s : s);
    }

    function seek(e) {
        if(!audio.src || isNaN(audio.duration)) return;
        const bar = document.getElementById('progCont');
        const rect = bar.getBoundingClientRect();
        const pos = (e.clientX - rect.left) / rect.width;
        audio.currentTime = pos * audio.duration;
    }

    audio.onended = () => isRepeat ? audio.play() : nextSong();

    async function doSearch() {
        const q = document.getElementById('searchInput').value;
        if (!q) return;
        
        const resultDiv = document.getElementById('searchResult');
        resultDiv.innerHTML = '<div class="flex justify-center py-10"><i class="fa-solid fa-spinner animate-spin text-3xl text-green-500"></i></div>';
        
        try {
            // Kita cari lagu lewat Piped API (Langsung dari browser, bukan lewat Vercel)
            const res = await fetch(`https://pipedapi.lunar.icu/search?q=${encodeURIComponent(q)}&filter=music_videos`);
            const data = await res.json();
            
            if (!data.content || data.content.length === 0) {
                resultDiv.innerHTML = '<p class="text-center text-zinc-500">Lagu gak ketemu, Flinn.</p>';
                return;
            }
    
            resultDiv.innerHTML = data.content.map(s => {
                // Kita bungkus datanya biar formatnya sama kayak database lu
                const songData = {
                    title: s.title.replace(/'/g, ""),
                    artist: s.uploaderName.replace(/'/g, ""),
                    cover: s.thumbnail,
                    yt_id: s.url.split("v=")[1],
                    duration: s.duration >= 0 ? formatTime(s.duration) : "3:00"
                };
    
                return `
                    <div class="flex items-center gap-3 p-2 bg-zinc-900/30 rounded-lg cursor-pointer hover:bg-zinc-800 transition">
                        <img src="${songData.cover}" onerror="this.src='${DEFAULT_COVER}'" class="w-12 h-12 rounded object-cover shadow">
                        <div class="flex-1 overflow-hidden" onclick="playSong('${songData.yt_id}', '${songData.title}', '${songData.artist}', '${songData.cover}')">
                            <div class="text-sm font-bold truncate">${songData.title}</div>
                            <div class="text-[10px] text-zinc-400 truncate">${songData.artist}</div>
                        </div>
                        <i class="fa-solid fa-plus-circle text-xl text-green-500 p-2 hover:scale-110" 
                           onclick='addSong(${JSON.stringify(songData).replace(/'/g, "&apos;")})'></i>
                    </div>
                `;
            }).join('');
        } catch (err) {
            resultDiv.innerHTML = '<p class="text-center text-red-500">Gagal mencari lagu. Server sibuk!</p>';
        }
    }

    async function addSong(s) {
        await fetch('/api/add', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(s) });
        alert('Ditambahkan ke Library!');
    }

    async function deleteSong(id) {
        if(confirm('Hapus lagu dari Library?')) { await fetch('/api/delete/' + id, { method: 'DELETE' }); renderLibrary(); }
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.getElementById('progCont').onclick = seek;
        document.getElementById('searchInput')?.addEventListener('keypress', (e) => e.key === 'Enter' && doSearch());
    });
</script>
</body>
</html>
'''

# Ganti bagian if __name__ == '__main__': ini
if __name__ == '__main__':
    app.run(debug=True)
