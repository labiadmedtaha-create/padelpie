from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import dbcompat as sqlite3, hashlib, secrets, os
from pathlib import Path
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename

BASE=Path(__file__).resolve().parent
DATA_DIR=Path(os.getenv('PADELPIE_DATA_DIR', str(BASE.parent/'data')))
DB=Path(os.getenv('PADELPIE_DB', str(DATA_DIR/'padelpie.db')))
DB.parent.mkdir(parents=True,exist_ok=True)
app=Flask(__name__); app.secret_key=os.getenv('PADELPIE_SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_NAME']='padelpie_club_session'
UPLOAD_DIR=Path(os.getenv('PADELPIE_UPLOAD_DIR', str(DATA_DIR/'uploads')))
UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
CITIES=['Casablanca','Rabat','Tanger','Marrakech','Agadir','Fès','Meknès','Oujda','El Jadida','Kénitra']

def db():
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; return con

def hp(p): return hashlib.sha256(p.encode()).hexdigest()

def init_db():
    con=db(); c=con.cursor()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,city TEXT DEFAULT 'Casablanca',photo TEXT DEFAULT '',pies INTEGER DEFAULT 1000,xp INTEGER DEFAULT 0,streak INTEGER DEFAULT 0,matches INTEGER DEFAULT 0,wins INTEGER DEFAULT 0,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS clubs(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,city TEXT NOT NULL,area TEXT NOT NULL,address TEXT NOT NULL,rating REAL DEFAULT 5.0,price_from INTEGER DEFAULT 120,courts INTEGER DEFAULT 1,image TEXT DEFAULT '',description TEXT DEFAULT '',phone TEXT DEFAULT '',hours TEXT DEFAULT '',booking_mode TEXT DEFAULT 'request',booking_url TEXT DEFAULT '',source_note TEXT DEFAULT 'Ajouté par le gérant');
    CREATE TABLE IF NOT EXISTS courts(id INTEGER PRIMARY KEY AUTOINCREMENT,club_id INTEGER NOT NULL,name TEXT NOT NULL,indoor INTEGER DEFAULT 0,type TEXT DEFAULT 'Panoramique');
    CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,club TEXT NOT NULL,court TEXT NOT NULL,booking_time TEXT NOT NULL,price REAL NOT NULL,status TEXT DEFAULT 'confirmed',created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS club_managers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS club_manager_links(manager_id INTEGER NOT NULL,club_id INTEGER NOT NULL,PRIMARY KEY(manager_id,club_id));
    CREATE TABLE IF NOT EXISTS club_availability(id INTEGER PRIMARY KEY AUTOINCREMENT,club_id INTEGER NOT NULL,court_id INTEGER,slot_date TEXT NOT NULL,slot_time TEXT NOT NULL,status TEXT DEFAULT 'blocked',reason TEXT DEFAULT '',UNIQUE(club_id,court_id,slot_date,slot_time));
    ''')
    # Compte gérant de démonstration (non admin)
    demo_email='clubtest@padelpie.ma'
    demo_password='ClubTest123'
    if not c.execute('SELECT 1 FROM club_managers WHERE lower(email)=?', (demo_email,)).fetchone():
        c.execute('INSERT INTO club_managers(name,email,password,created_at) VALUES(?,?,?,?)',
                  ('Club Test Padelpie', demo_email, hp(demo_password), datetime.now().isoformat()))
    con.commit(); con.close()

def manager():
    mid=session.get('manager_id')
    if not mid:return None
    con=db(); r=con.execute('SELECT * FROM club_managers WHERE id=?',(mid,)).fetchone(); con.close(); return r

def mgr_required(fn):
    def wrapper(*a,**kw):
        if not manager(): return redirect(url_for('login'))
        return fn(*a,**kw)
    wrapper.__name__=fn.__name__; return wrapper

@app.route('/')
def index(): return render_template('club_index.html', manager=manager())

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        con=db(); m=con.execute('SELECT * FROM club_managers WHERE lower(email)=?',(email,)).fetchone(); con.close()
        if m and m['password']==hp(password): session.clear(); session['manager_id']=m['id']; return redirect(url_for('dashboard'))
        flash('Email ou mot de passe incorrect.','error')
    return render_template('club_login.html')

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        if len(password)<6: flash('Mot de passe : 6 caractères minimum.','error'); return redirect(url_for('register'))
        con=db()
        try:
            con.execute('INSERT INTO club_managers(name,email,password,created_at) VALUES(?,?,?,?)',(name,email,hp(password),datetime.now().isoformat())); con.commit()
        except sqlite3.IntegrityError: con.close(); flash('Cet email est déjà utilisé.','error'); return redirect(url_for('register'))
        m=con.execute('SELECT id FROM club_managers WHERE email=?',(email,)).fetchone(); con.close(); session.clear(); session['manager_id']=m['id']; flash('Compte gérant créé. Ajoute maintenant ton terrain.','success'); return redirect(url_for('dashboard'))
    return render_template('club_register.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('index'))

@app.route('/dashboard')
@mgr_required
def dashboard():
    m=manager(); con=db(); clubs=con.execute('SELECT * FROM clubs c JOIN club_manager_links l ON l.club_id=c.id WHERE l.manager_id=? ORDER BY c.name',(m['id'],)).fetchall(); bookings=[]
    for c in clubs: bookings += con.execute('SELECT * FROM bookings WHERE club=? ORDER BY booking_time DESC LIMIT 30',(c['name'],)).fetchall()
    con.close(); total_courts=sum(c['courts'] for c in clubs)
    return render_template('club_dashboard.html',manager=m,clubs=clubs,bookings=bookings[:50],total_courts=total_courts)

@app.route('/club/new',methods=['GET','POST'])
@mgr_required
def add_club():
    if request.method=='POST':
        name=request.form.get('name','').strip(); city=request.form.get('city',''); area=request.form.get('area','').strip(); address=request.form.get('address','').strip(); phone=request.form.get('phone','').strip(); hours=request.form.get('hours','').strip(); price=int(request.form.get('price_from',120) or 120); n=int(request.form.get('courts',1) or 1); desc=request.form.get('description','').strip(); indoor=request.form.get('indoor')=='1'
        photo=request.files.get('image'); image_name=''
        if photo and photo.filename:
            ext=Path(photo.filename).suffix.lower()
            if ext in {'.jpg','.jpeg','.png','.webp'}:
                image_name=secure_filename(f'club_{datetime.now().strftime("%Y%m%d%H%M%S%f")}{ext}'); photo.save(UPLOAD_DIR/image_name)
        if not name or not address or n<1: flash('Nom, adresse et au moins 1 terrain sont obligatoires.','error'); return redirect(url_for('add_club'))
        con=db(); cur=con.cursor(); cur.execute('INSERT INTO clubs(name,city,area,address,price_from,courts,description,phone,hours,booking_mode,source_note,image) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(name,city,area,address,price,n,desc,phone,hours,'request','Ajouté par le gérant via Padelpie Clubs',image_name)); cid=cur.lastrowid; mid=manager()['id']; cur.execute('INSERT INTO club_manager_links(manager_id,club_id) VALUES(?,?)',(mid,cid))
        for i in range(1,n+1): cur.execute('INSERT INTO courts(club_id,name,indoor,type) VALUES(?,?,?,?)',(cid,f'Terrain {i}',1 if indoor else 0,'Indoor' if indoor else 'Panoramique'))
        con.commit(); con.close(); flash('Ton terrain a été ajouté au répertoire Padelpie 🎾','success'); return redirect(url_for('manage_club',club_id=cid))
    return render_template('club_form.html',cities=CITIES,club=None)

@app.route('/club/<int:club_id>',methods=['GET','POST'])
@mgr_required
def manage_club(club_id):
    m=manager(); con=db(); club=con.execute('SELECT c.* FROM clubs c JOIN club_manager_links l ON l.club_id=c.id WHERE c.id=? AND l.manager_id=?',(club_id,m['id'])).fetchone()
    if not club: con.close(); flash('Club introuvable.','error'); return redirect(url_for('dashboard'))
    if request.method=='POST':
        con.execute('UPDATE clubs SET name=?,city=?,area=?,address=?,phone=?,hours=?,price_from=?,description=? WHERE id=?',(request.form['name'].strip(),request.form['city'],request.form.get('area','').strip(),request.form['address'].strip(),request.form.get('phone','').strip(),request.form.get('hours','').strip(),int(request.form.get('price_from',120) or 120),request.form.get('description','').strip(),club_id)); con.commit(); club=con.execute('SELECT * FROM clubs WHERE id=?',(club_id,)).fetchone(); flash('Informations du club mises à jour.','success')
    courts=con.execute('SELECT * FROM courts WHERE club_id=? ORDER BY id',(club_id,)).fetchall(); con.close(); return render_template('club_manage.html',manager=m,club=club,courts=courts,cities=CITIES)

@app.route('/club/<int:club_id>/availability',methods=['POST'])
@mgr_required
def block_slot(club_id):
    m=manager(); d=request.form.get('date'); t=request.form.get('time'); court_id=request.form.get('court_id','all'); reason=request.form.get('reason','Indisponible').strip() or 'Indisponible'; con=db(); ok=con.execute('SELECT 1 FROM club_manager_links WHERE manager_id=? AND club_id=?',(m['id'],club_id)).fetchone()
    if not ok: con.close(); flash('Accès refusé.','error'); return redirect(url_for('dashboard'))
    if court_id=='all': courts=con.execute('SELECT id FROM courts WHERE club_id=?',(club_id,)).fetchall(); ids=[r['id'] for r in courts]
    else: ids=[int(court_id)]
    for cid in ids:
        con.execute('DELETE FROM club_availability WHERE club_id=? AND court_id=? AND slot_date=? AND slot_time=?',(club_id,cid,d,t)); con.execute('INSERT INTO club_availability(club_id,court_id,slot_date,slot_time,status,reason) VALUES(?,?,?,?,?,?)',(club_id,cid,d,t,'blocked',reason))
    con.commit(); con.close(); flash('Créneau marqué indisponible.','success'); return redirect(url_for('manage_club',club_id=club_id))

@app.route('/club/<int:club_id>/availability/remove',methods=['POST'])
@mgr_required
def unblock_slot(club_id):
    m=manager(); con=db(); ok=con.execute('SELECT 1 FROM club_manager_links WHERE manager_id=? AND club_id=?',(m['id'],club_id)).fetchone()
    if not ok: con.close(); return redirect(url_for('dashboard'))
    con.execute('DELETE FROM club_availability WHERE club_id=? AND slot_date=? AND slot_time=?',(club_id,request.form['date'],request.form['time'])); con.commit(); con.close(); flash('Créneau remis disponible.','success'); return redirect(url_for('manage_club',club_id=club_id))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

if __name__=='__main__': init_db(); app.run(host='0.0.0.0',port=int(os.getenv('PORT','5001')),debug=False)
