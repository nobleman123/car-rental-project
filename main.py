# ========================================================
# 1. BÖLÜM: IMPORT VE AYARLAR
# ========================================================
import flask.json
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mongoengine import MongoEngine
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

# JSON Encoder Yaması
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        return str(o)
flask.json.JSONEncoder = CustomJSONEncoder

app = Flask(__name__)

# --- AYARLAR ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'TorontoCarRental_Secret_Key_2026'
# Render ortamında MONGO_URI environment variable'dan alınır, yoksa buradaki kullanılır
app.config['MONGODB_SETTINGS'] = {
    'host': os.environ.get('MONGO_URI') or 'mongodb+srv://Torontocarental:inan.1907@cluster0.oht1igm.mongodb.net/CarRentalDB?retryWrites=true&w=majority',
    'connectTimeoutMS': 30000,
    'socketTimeoutMS': 30000
}

app.json_encoder = CustomJSONEncoder

db = MongoEngine(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ========================================================
# 2. BÖLÜM: VERİTABANI MODELLERİ (Kanada Standartları)
# ========================================================

class User(UserMixin, db.Document):
    email = db.StringField(unique=True, required=True)
    password = db.StringField(required=True)
    name = db.StringField(required=True) # Tam Ad Soyad
    
    # İletişim Bilgileri (Kanada Standardı)
    phone = db.StringField()
    address = db.StringField()
    city = db.StringField()
    province = db.StringField() # Örn: Ontario, Quebec
    zip_code = db.StringField() # Örn: M5V 2T6
    
    # Kimlik ve Ehliyet Dosyaları
    drivers_license_id = db.StringField()
    drivers_license_img = db.ImageField() # Resim olarak sakla
    passport_img = db.ImageField()        # Resim olarak sakla
    
    is_admin = db.BooleanField(default=False)
    
    def get_id(self):
        return str(self.id)

class Car(db.Document):
    car_id = db.StringField(unique=True, required=True) # Plaka
    brand = db.StringField(required=True)
    model = db.StringField(required=True)
    category = db.StringField(choices=['SUV', 'Sedan', 'Luxury', 'Van', 'Sport', 'Economy'], default='Sedan')
    price = db.IntField(required=True) # Günlük Fiyat (CAD)
    image = db.ImageField() 
    
    # Araç Özellikleri
    transmission = db.StringField(choices=['Automatic', 'Manual'], default='Automatic')
    fuel_type = db.StringField(choices=['Gasoline', 'Diesel', 'Electric', 'Hybrid'], default='Gasoline')
    seats = db.IntField(default=5)
    location = db.StringField(default='Toronto Pearson Airport (YYZ)')
    is_available = db.BooleanField(default=True)

class Booking(db.Document):
    user = db.ReferenceField(User)
    car = db.ReferenceField(Car)
    pickup_location = db.StringField()
    dropoff_location = db.StringField()
    from_date = db.DateTimeField(required=True)
    to_date = db.DateTimeField(required=True)
    total_days = db.IntField()
    total_price = db.IntField()
    status = db.StringField(default="Pending") 
    booking_date = db.DateTimeField(default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.objects(pk=user_id).first()

# ========================================================
# 3. BÖLÜM: YÖNLENDİRMELER (ROUTES)
# ========================================================

# --- Resim Gösterme Yardımcısı ---
@app.route('/img/car/<car_id>')
def get_car_image(car_id):
    car = Car.objects(id=car_id).first()
    if car and car.image:
        return car.image.read(), 200, {'Content-Type': car.image.content_type}
    return "", 404

@app.route('/img/user/<user_id>/<doc_type>')
@login_required
def get_user_doc(user_id, doc_type):
    # Sadece admin veya dosyanın sahibi görebilir
    if current_user.id != user_id and not current_user.is_admin:
        return "Access Denied", 403
        
    user = User.objects(pk=user_id).first()
    if user:
        if doc_type == 'license' and user.drivers_license_img:
            return user.drivers_license_img.read(), 200, {'Content-Type': user.drivers_license_img.content_type}
        elif doc_type == 'passport' and user.passport_img:
            return user.passport_img.read(), 200, {'Content-Type': user.passport_img.content_type}
    return "", 404

@app.route('/', methods=['GET', 'POST'])
def index():
    featured_cars = Car.objects(is_available=True).limit(3)
    if request.method == 'POST':
        pickup_loc = request.form.get('location')
        return redirect(url_for('display_cars', location=pickup_loc))
    return render_template('index.html', cars=featured_cars)

@app.route('/cars')
def display_cars():
    location_filter = request.args.get('location')
    category_filter = request.args.get('category')
    query = Car.objects(is_available=True)
    
    if location_filter and location_filter != "All":
        query = query.filter(location=location_filter)
    if category_filter and category_filter != "All":
        query = query.filter(category=category_filter)
        
    return render_template('display_cars.html', cars=query)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        if User.objects(email=email).first():
            flash('This email is already registered.', 'danger')
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password)
        User(email=email, password=hashed_pw, name=name).save()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # --- ACİL DURUM ADMİN GİRİŞİ ---
        if email == 'admin' and password == '12345':
            admin_user = User.objects(email='admin@torontocar.com').first()
            if not admin_user:
                admin_user = User(
                    email='admin@torontocar.com', 
                    password=generate_password_hash('12345'), 
                    name='System Admin', 
                    is_admin=True
                )
                admin_user.save()
            login_user(admin_user)
            return redirect(url_for('admin_dashboard'))
        # ---------------------------------

        user = User.objects(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
            
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

# --- DASHBOARD (HATA DÜZELTİLDİ: methods=['GET', 'POST'] eklendi) ---
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        # Kullanıcı Bilgilerini Güncelleme
        try:
            current_user.phone = request.form.get('phone')
            current_user.address = request.form.get('address')
            current_user.city = request.form.get('city')
            current_user.province = request.form.get('province')
            current_user.zip_code = request.form.get('zip_code')
            current_user.drivers_license_id = request.form.get('drivers_license_id')

            # Dosya Yükleme (Varsa)
            if 'license_image' in request.files:
                file = request.files['license_image']
                if file.filename != '':
                    current_user.drivers_license_img.replace(file, content_type=file.content_type)
            
            if 'passport_image' in request.files:
                file = request.files['passport_image']
                if file.filename != '':
                    current_user.passport_img.replace(file, content_type=file.content_type)
            
            current_user.save()
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'danger')
            
    my_bookings = Booking.objects(user=current_user).order_by('-booking_date')
    return render_template('dashboard.html', bookings=my_bookings, user=current_user)

@app.route('/book/<car_id>', methods=['GET', 'POST'])
@login_required
def add_booking(car_id):
    try:
        car = Car.objects.get(id=car_id)
    except:
        flash('Car not found.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        pickup_str = request.form.get('pickup_date')
        dropoff_str = request.form.get('dropoff_date')
        
        try:
            pickup = datetime.strptime(pickup_str, '%Y-%m-%d')
            dropoff = datetime.strptime(dropoff_str, '%Y-%m-%d')
            days = (dropoff - pickup).days
            if days < 1: days = 1
            
            total_price = days * car.price
            
            Booking(
                user=current_user,
                car=car,
                pickup_location=car.location,
                dropoff_location=car.location,
                from_date=pickup,
                to_date=dropoff,
                total_days=days,
                total_price=total_price
            ).save()
            
            flash(f'Booking Confirmed! Total: ${total_price} CAD', 'success')
            return redirect(url_for('dashboard'))
            
        except ValueError:
            flash('Invalid date format.', 'danger')
            
    return render_template('add_booking.html', car=car)

# --- ADMIN PANELİ ---
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access Denied', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            # Yeni Araç Ekleme
            new_car = Car(
                car_id=request.form.get('car_id'),
                brand=request.form.get('brand'),
                model=request.form.get('model'),
                price=int(request.form.get('price')),
                category=request.form.get('category'),
                location=request.form.get('location'),
                transmission=request.form.get('transmission'),
                fuel_type=request.form.get('fuel_type', 'Gasoline'),
                seats=int(request.form.get('seats', 5))
            )
            
            # Resim Yükleme (Varsa)
            if 'image' in request.files:
                image_file = request.files['image']
                if image_file.filename != '':
                    new_car.image.put(image_file, content_type=image_file.content_type)
            
            new_car.save()
            flash('Car added successfully.', 'success')
        except Exception as e:
            flash(f'Error adding car: {str(e)}', 'danger')

    all_cars = Car.objects.all()
    all_bookings = Booking.objects.all()
    return render_template('admin.html', cars=all_cars, bookings=all_bookings)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
