from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import dbcompat as sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
import hashlib, secrets, os

BASE = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv('PADELPIE_DATA_DIR', str(BASE.parent / 'data')))
DB = Path(os.getenv('PADELPIE_DB', str(DATA_DIR / 'padelpie.db')))
DB.parent.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.secret_key = os.getenv('PADELPIE_SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_NAME'] = 'padelpie_session'
UPLOAD_DIR = Path(os.getenv('PADELPIE_UPLOAD_DIR', str(DATA_DIR / 'uploads')))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CITIES = ['Casablanca', 'Rabat', 'Tanger', 'Marrakech', 'Agadir', 'Fès', 'Meknès', 'Oujda', 'El Jadida', 'Kénitra']
ADMIN_EMAIL = 'medtahalabiad@gmail.com'
ADMIN_PASSWORD = 'Tahalabiad2'


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()


def init_db():
    con = db(); cur = con.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL, city TEXT DEFAULT 'Casablanca', photo TEXT DEFAULT '',
        pies INTEGER DEFAULT 1000, xp INTEGER DEFAULT 0, streak INTEGER DEFAULT 0,
        matches INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS admins(
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
        name TEXT DEFAULT 'Padelpie Admin', created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS club_managers(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS club_availability(
        id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER NOT NULL, court_id INTEGER,
        slot_date TEXT NOT NULL, slot_time TEXT NOT NULL, status TEXT DEFAULT 'blocked', reason TEXT DEFAULT '',
        UNIQUE(club_id,court_id,slot_date,slot_time)
    );
    CREATE TABLE IF NOT EXISTS challenges(
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL,
        target INTEGER NOT NULL, reward INTEGER NOT NULL, kind TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS user_challenges(
        user_id INTEGER, challenge_id INTEGER, progress INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0, claimed INTEGER DEFAULT 0,
        PRIMARY KEY(user_id, challenge_id)
    );
    CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, amount INTEGER NOT NULL,
        reason TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, club TEXT NOT NULL,
        court TEXT NOT NULL, booking_time TEXT NOT NULL, price REAL NOT NULL,
        status TEXT DEFAULT 'confirmed', created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS clubs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, city TEXT NOT NULL,
        area TEXT NOT NULL, address TEXT NOT NULL, rating REAL DEFAULT 4.7,
        price_from INTEGER DEFAULT 120, courts INTEGER DEFAULT 4, image TEXT DEFAULT '',
        description TEXT DEFAULT '', phone TEXT DEFAULT '', hours TEXT DEFAULT '',
        booking_mode TEXT DEFAULT 'request', booking_url TEXT DEFAULT '', source_note TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS courts(
        id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER NOT NULL, name TEXT NOT NULL,
        indoor INTEGER DEFAULT 0, type TEXT DEFAULT 'Panoramique'
    );
    CREATE TABLE IF NOT EXISTS matches(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, opponent TEXT NOT NULL,
        club TEXT NOT NULL, match_time TEXT NOT NULL, result TEXT DEFAULT 'upcoming'
    );
    CREATE TABLE IF NOT EXISTS open_matches(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, club TEXT NOT NULL,
        match_time TEXT NOT NULL, level TEXT NOT NULL, spots INTEGER DEFAULT 1, note TEXT DEFAULT '',
        status TEXT DEFAULT 'open'
    );
    CREATE TABLE IF NOT EXISTS predictions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, match_name TEXT NOT NULL,
        pick TEXT NOT NULL, stake INTEGER NOT NULL, multiplier REAL NOT NULL,
        status TEXT DEFAULT 'open', payout INTEGER DEFAULT 0, created_at TEXT NOT NULL
    );
    ''')
  # The photo column is already created in the users table above.
# No ALTER TABLE migration is needed here.
    # Final version: no clubs or courts are pre-seeded. Clubs are added by managers.
    if cur.execute('SELECT COUNT(*) FROM admins WHERE email=?', (ADMIN_EMAIL,)).fetchone()[0] == 0:
        cur.execute('INSERT INTO admins(email,password,name,created_at) VALUES(?,?,?,?)',
                    (ADMIN_EMAIL, hash_password(ADMIN_PASSWORD), 'Padelpie Admin', datetime.now().isoformat()))
    # Compte de test joueur (non-admin).
    TEST_EMAIL = 'test@padelpie.ma'
    TEST_PASSWORD = 'PadelpieTest123'
    if cur.execute('SELECT COUNT(*) FROM users WHERE lower(email)=?', (TEST_EMAIL,)).fetchone()[0] == 0:
        cur.execute('''INSERT INTO users(name,email,password,city,pies,xp,streak,matches,wins,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)''',
                    ('Joueur Test', TEST_EMAIL, hash_password(TEST_PASSWORD), 'Casablanca',
                     1000, 0, 0, 0, 0, datetime.now().isoformat()))

    # Remove only legacy demo/seed clubs from previous Padelpie builds.
    legacy_names = [
        'Ocean Padel Club','Padel Garden','Tanger Padel Arena','Atlas Padel Club','Agadir Padel Bay','Fès Padel House',
        'Padel 4','PADEL PRO','DEPOT 4 - INDOOR PADEL CLUB','Club Sahara Padel','Padel Plaza','PimPam Padel Club Rabat',
        'Padel Point Rabat','Urban Padel Marrakech','Padel Square Marrakech','MĀRA Padel Club','GOLDEN PADEL CLUB',
        'TCMT Padel','Padel Hub Tangier','Padel Factory Agadir','Padel Factory Universiapolis','Le Carré Padel'
    ]
    marks=','.join('?' for _ in legacy_names)
    old_ids=[r['id'] for r in cur.execute(f'SELECT id FROM clubs WHERE name IN ({marks})', legacy_names).fetchall()] if legacy_names else []
    if old_ids:
        marks2=','.join('?' for _ in old_ids)
        cur.execute(f'DELETE FROM courts WHERE club_id IN ({marks2})', old_ids)
        cur.execute(f'DELETE FROM club_availability WHERE club_id IN ({marks2})', old_ids)
        cur.execute(f'DELETE FROM clubs WHERE id IN ({marks2})', old_ids)
    cur.execute("DELETE FROM open_matches WHERE club IN ('Ocean Padel Club','Padel Garden','Tanger Padel Arena','Atlas Padel Club','Agadir Padel Bay','Fès Padel House')")

    users = cur.execute('SELECT id FROM users').fetchall()
    challenges = cur.execute('SELECT id FROM challenges').fetchall()
    for u in users:
        for c in challenges:
            cur.execute('INSERT OR IGNORE INTO user_challenges(user_id,challenge_id) VALUES(?,?)', (u['id'], c['id']))
    con.commit(); con.close()


def current_user():
    uid = session.get('uid')
    if not uid: return None
    con = db(); u = con.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone(); con.close()
    return u


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user(): return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def add_pies(user_id, amount, reason):
    con = db()
    con.execute('UPDATE users SET pies=pies+? WHERE id=?', (amount, user_id))
    con.execute('INSERT INTO transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)',
                (user_id, amount, reason, datetime.now().isoformat()))
    con.commit(); con.close()


def add_xp(user_id, amount):
    con = db(); con.execute('UPDATE users SET xp=xp+? WHERE id=?', (amount, user_id)); con.commit(); con.close()


def refresh_challenges(user_id):
    con = db(); u = con.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    rows = con.execute('''SELECT c.*,uc.progress,uc.completed,uc.claimed FROM challenges c
                          JOIN user_challenges uc ON c.id=uc.challenge_id WHERE uc.user_id=?''', (user_id,)).fetchall()
    for r in rows:
        if r['kind'] == 'match': progress = min(u['matches'], r['target'])
        elif r['kind'] == 'win': progress = min(u['wins'], r['target'])
        elif r['kind'] == 'streak': progress = min(u['streak'], r['target'])
        else: progress = r['progress']
        con.execute('UPDATE user_challenges SET progress=?,completed=? WHERE user_id=? AND challenge_id=?',
                    (progress, 1 if progress >= r['target'] else 0, user_id, r['id']))
    con.commit(); con.close()


@app.context_processor
def inject_globals():
    u = current_user()
    return {'current_user': u, 'cities': CITIES}


@app.route('/clubs')
def club_portal():
    return redirect('/clubs/')


@app.route('/')
def index(): return redirect(url_for('home') if current_user() else url_for('login'))


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        if email==ADMIN_EMAIL and password==ADMIN_PASSWORD:
            session.clear(); session['admin']=True; return redirect(url_for('admin_dashboard'))
        con=db(); u=con.execute('SELECT * FROM users WHERE lower(email)=?',(email,)).fetchone(); con.close()
        if u and u['password']==hash_password(password):
            session.clear(); session['uid']=u['id']; return redirect(url_for('home'))
        flash('Email ou mot de passe incorrect.','error')
    return render_template('login.html',cities=CITIES)


@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))


@app.route('/home')
@login_required
def home():
    u=current_user(); refresh_challenges(u['id']); con=db()
    next_match=con.execute("SELECT * FROM matches WHERE user_id=? AND result='upcoming' ORDER BY match_time LIMIT 1",(u['id'],)).fetchone()
    challenges=con.execute('''SELECT c.*,uc.progress,uc.completed,uc.claimed FROM challenges c JOIN user_challenges uc
                              ON c.id=uc.challenge_id WHERE uc.user_id=? ORDER BY c.id''',(u['id'],)).fetchall()
    featured=con.execute('SELECT * FROM clubs ORDER BY rating DESC LIMIT 3').fetchall()
    open_count=con.execute("SELECT COUNT(*) FROM open_matches WHERE status='open'").fetchone()[0]
    con.close(); return render_template('home.html',user=u,next_match=next_match,challenges=challenges,featured=featured,open_count=open_count)


@app.route('/book', methods=['GET','POST'])
@login_required
def book():
    u=current_user()
    if request.method=='POST':
        club_id=int(request.form['club_id']); court_id=int(request.form['court_id']); date=request.form['date']; time=request.form['time']
        con=db(); club=con.execute('SELECT * FROM clubs WHERE id=?',(club_id,)).fetchone(); court=con.execute('SELECT * FROM courts WHERE id=? AND club_id=?',(court_id,club_id)).fetchone()
        if not club or not court: con.close(); flash('Terrain introuvable.', 'error'); return redirect(url_for('book'))
        booking_time=f'{date}T{time}'
        existing=con.execute('SELECT id FROM bookings WHERE club=? AND court=? AND booking_time=? AND status=?',(club['name'],court['name'],booking_time,'confirmed')).fetchone()
        if existing: con.close(); flash('Ce créneau vient d’être réservé. Choisis-en un autre.', 'error'); return redirect(url_for('book',city=club['city'],date=date))
        con.execute('INSERT INTO bookings(user_id,club,court,booking_time,price,created_at) VALUES(?,?,?,?,?,?)',
                    (u['id'],club['name'],court['name'],booking_time,club['price_from'],datetime.now().isoformat()))
        con.commit(); con.close(); flash(f"Réservation confirmée 🎾 · {club['name']} · {court['name']} · {time}", 'success'); return redirect(url_for('book',city=club['city'],date=date))
    city=request.args.get('city',u['city'] if u['city'] in CITIES else 'Casablanca'); date=request.args.get('date',datetime.now().strftime('%Y-%m-%d'))
    con=db(); clubs=con.execute('SELECT * FROM clubs WHERE city=? ORDER BY rating DESC',(city,)).fetchall()
    selected_id=request.args.get('club', type=int) or (clubs[0]['id'] if clubs else None)
    selected=con.execute('SELECT * FROM clubs WHERE id=?',(selected_id,)).fetchone() if selected_id else None
    courts=con.execute('SELECT * FROM courts WHERE club_id=? ORDER BY id',(selected_id,)).fetchall() if selected_id else []
    bookings=con.execute('SELECT * FROM bookings WHERE user_id=? ORDER BY booking_time DESC LIMIT 12',(u['id'],)).fetchall()
    con.close()
    slots=[]
    for hour in range(9,23):
        for minute in (0,30):
            if hour==22 and minute==30: continue
            t=f'{hour:02d}:{minute:02d}'
            booked_courts=set()
            if selected:
                con=db()
                rows=con.execute('SELECT court FROM bookings WHERE club=? AND booking_time=? AND status=?',(selected['name'],f'{date}T{t}','confirmed')).fetchall()
                blocked=con.execute("SELECT court_id FROM club_availability WHERE club_id=? AND slot_date=? AND slot_time=? AND status='blocked'",(selected['id'],date,t)).fetchall()
                con.close()
                booked_courts={r['court'] for r in rows}; blocked_ids={r['court_id'] for r in blocked}
            available=[c for c in courts if c['name'] not in booked_courts and c['id'] not in blocked_ids]
            slots.append({'time':t,'available':len(available),'total':len(courts)})
    return render_template('book.html',user=u,clubs=clubs,selected=selected,courts=courts,slots=slots,bookings=bookings,city=city,date=date)


@app.route('/pies')
@login_required
def pies():
    u=current_user(); con=db(); tx=con.execute('SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 30',(u['id'],)).fetchall(); con.close()
    rewards=[('Réduction réservation','-20% sur une réservation',500,'🏷️'),('Boisson offerte','Chez un partenaire',300,'🥤'),('Pack de balles','Récompense premium',1000,'🎾')]
    return render_template('pies.html',user=u,tx=tx,rewards=rewards)


@app.route('/reward', methods=['POST'])
@login_required
def reward():
    uid=current_user()['id']; cost=int(request.form['cost']); name=request.form['name']; con=db(); u=con.execute('SELECT pies FROM users WHERE id=?',(uid,)).fetchone()
    if u['pies']<cost: con.close(); flash('Pas assez de Pies 🥧','error'); return redirect(url_for('pies'))
    con.execute('UPDATE users SET pies=pies-? WHERE id=?',(cost,uid)); con.execute('INSERT INTO transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)',(uid,-cost,f'Recompense : {name}',datetime.now().isoformat())); con.commit(); con.close()
    flash(f'Récompense débloquée : {name} 🎁','success'); return redirect(url_for('pies'))


@app.route('/play')
@login_required
def play():
    u=current_user(); con=db();
    matches=con.execute('SELECT * FROM matches WHERE user_id=? ORDER BY match_time DESC',(u['id'],)).fetchall()
    predictions=con.execute('SELECT * FROM predictions WHERE user_id=? ORDER BY created_at DESC',(u['id'],)).fetchall()
    ranking=con.execute('SELECT id,name,city,wins,matches,xp,pies FROM users ORDER BY wins DESC,xp DESC LIMIT 10').fetchall()
    open_matches=con.execute("SELECT om.*,u.name AS player FROM open_matches om JOIN users u ON u.id=om.user_id WHERE om.status='open' ORDER BY om.match_time LIMIT 12").fetchall()
    players=con.execute('SELECT id,name,city,matches,wins,xp FROM users WHERE id!=? ORDER BY xp DESC LIMIT 12',(u['id'],)).fetchall(); con.close()
    return render_template('play.html',user=u,matches=matches,predictions=predictions,ranking=ranking,open_matches=open_matches,players=players)


@app.route('/open-match', methods=['POST'])
@login_required
def open_match():
    u=current_user(); con=db(); con.execute('INSERT INTO open_matches(user_id,club,match_time,level,spots,note) VALUES(?,?,?,?,?,?)',(
        u['id'],request.form['club'],request.form['match_time'],request.form['level'],int(request.form.get('spots',1)),request.form.get('note','').strip()))
    con.commit(); con.close(); flash('Ton match ouvert est publié 🎾','success'); return redirect(url_for('play'))


@app.route('/join-match/<int:mid>', methods=['POST'])
@login_required
def join_match(mid):
    uid=current_user()['id']; con=db(); row=con.execute("SELECT * FROM open_matches WHERE id=? AND status='open'",(mid,)).fetchone()
    if not row: con.close(); flash('Ce match n’est plus disponible.','error'); return redirect(url_for('play'))
    if row['user_id']==uid: con.close(); flash('C’est déjà ton match.','error'); return redirect(url_for('play'))
    if row['spots']<=1: con.execute("UPDATE open_matches SET spots=0,status='full' WHERE id=?",(mid,))
    else: con.execute('UPDATE open_matches SET spots=spots-1 WHERE id=?',(mid,))
    con.execute('INSERT INTO matches(user_id,opponent,club,match_time,result) VALUES(?,?,?,?,?)',(uid,row['player'] if 'player' in row.keys() else 'Joueur Padelpie',row['club'],row['match_time'],'upcoming'))
    con.commit(); con.close(); flash('Tu as rejoint le match 🤝','success'); return redirect(url_for('play'))


@app.route('/demo-match', methods=['POST'])
@login_required
def demo_match():
    uid=current_user()['id']; opponent=request.form.get('opponent','Yassine'); club=request.form.get('club','Ocean Padel Club'); result=request.form.get('result','win')
    con=db(); con.execute('INSERT INTO matches(user_id,opponent,club,match_time,result) VALUES(?,?,?,?,?)',(uid,opponent,club,datetime.now().isoformat(),result))
    if result in ('win','loss'): con.execute('UPDATE users SET matches=matches+1,wins=wins+? WHERE id=?',(1 if result=='win' else 0,uid))
    con.commit(); con.close(); add_xp(uid,150 if result=='win' else 100); add_pies(uid,250 if result=='win' else 100,'Match terminé'); refresh_challenges(uid)
    flash('Match enregistré. XP + Pies ajoutés 🥧','success'); return redirect(url_for('play'))


@app.route('/prediction', methods=['POST'])
@login_required
def prediction():
    uid=current_user()['id']; stake=int(request.form['stake']); pick=request.form['pick']
    if stake<=0 or stake>5000: flash('Mise virtuelle entre 1 et 5000 Pies.','error'); return redirect(url_for('play'))
    con=db(); u=con.execute('SELECT pies FROM users WHERE id=?',(uid,)).fetchone()
    if u['pies']<stake: con.close(); flash('Pas assez de Pies.','error'); return redirect(url_for('play'))
    multiplier=1.65 if pick=='Taha' else 2.10
    con.execute('UPDATE users SET pies=pies-? WHERE id=?',(stake,uid)); con.execute('INSERT INTO transactions(user_id,amount,reason,created_at) VALUES(?,?,?,?)',(uid,-stake,'Prédiction virtuelle',datetime.now().isoformat()))
    con.execute('INSERT INTO predictions(user_id,match_name,pick,stake,multiplier,created_at) VALUES(?,?,?,?,?,?)',(uid,'Taha vs Yassine',pick,stake,multiplier,datetime.now().isoformat())); con.commit(); con.close()
    flash('Prédiction enregistrée — Pies virtuelles uniquement.','success'); return redirect(url_for('play'))


@app.route('/profile')
@login_required
def profile():
    u=current_user(); refresh_challenges(u['id']); con=db(); tx=con.execute('SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 10',(u['id'],)).fetchall(); con.close()
    level=max(1,u['xp']//1000+1); level_xp=u['xp']%1000; winrate=round((u['wins']/u['matches'])*100) if u['matches'] else 0
    return render_template('profile.html',user=u,tx=tx,level=level,level_xp=level_xp,winrate=winrate)


@app.route('/challenge/<int:cid>/claim', methods=['POST'])
@login_required
def claim_challenge(cid):
    uid=current_user()['id']; refresh_challenges(uid); con=db(); row=con.execute('''SELECT c.*,uc.completed,uc.claimed FROM challenges c JOIN user_challenges uc ON c.id=uc.challenge_id WHERE c.id=? AND uc.user_id=?''',(cid,uid)).fetchone()
    if row and row['completed'] and not row['claimed']:
        con.execute('UPDATE user_challenges SET claimed=1 WHERE user_id=? AND challenge_id=?',(uid,cid)); con.commit(); con.close(); add_pies(uid,row['reward'],f"Challenge : {row['title']}"); add_xp(uid,300); flash(f"+{row['reward']} Pies 🥧 — {row['title']}",'success')
    else: con.close(); flash('Challenge non disponible.','error')
    return redirect(url_for('home'))


@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'): return redirect(url_for('login'))
    con=db(); clubs=con.execute('SELECT * FROM clubs ORDER BY city,name').fetchall(); users=con.execute('SELECT id,name,email,city,pies,xp,matches,wins,photo FROM users ORDER BY id DESC').fetchall(); managers=con.execute('SELECT id,name,email,created_at FROM club_managers ORDER BY id DESC').fetchall(); bookings=con.execute('SELECT * FROM bookings ORDER BY booking_time DESC LIMIT 50').fetchall(); con.close()
    return render_template('admin.html',clubs=clubs,users=users,managers=managers,bookings=bookings,admin_email=ADMIN_EMAIL)

@app.route('/admin/club/<int:club_id>/delete', methods=['POST'])
def admin_delete_club(club_id):
    if not session.get('admin'): return redirect(url_for('login'))
    con=db(); con.execute('DELETE FROM courts WHERE club_id=?',(club_id,)); con.execute('DELETE FROM club_availability WHERE club_id=?',(club_id,)); con.execute('DELETE FROM clubs WHERE id=?',(club_id,)); con.commit(); con.close(); flash('Club supprimé.','success'); return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.clear(); return redirect(url_for('login'))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route('/profile/photo', methods=['POST'])
@login_required
def profile_photo():
    f=request.files.get('photo'); uid=current_user()['id']
    if not f or not f.filename: flash('Choisis une photo.','error'); return redirect(url_for('profile'))
    ext=Path(f.filename).suffix.lower()
    if ext not in {'.jpg','.jpeg','.png','.webp'}: flash('Format accepté : JPG, PNG ou WEBP.','error'); return redirect(url_for('profile'))
    for old in UPLOAD_DIR.glob(f'user_{uid}.*'):
        try: old.unlink()
        except OSError: pass
    filename=f'user_{uid}{ext}'; f.save(UPLOAD_DIR/filename)
    con=db(); con.execute('UPDATE users SET photo=? WHERE id=?',(filename,uid)); con.commit(); con.close(); flash('Photo de profil mise à jour 📸','success'); return redirect(url_for('profile'))

if __name__ == '__main__':
    init_db(); app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=False)
