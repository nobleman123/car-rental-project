# ========================================================
# 1. BÖLÜM: KRİTİK HATA DÜZELTME YAMASI (SİLMEYİN!)
# ========================================================
import flask.json
import json

# Flask 3.x sürümünde kaldırılan JSONEncoder'ı manuel olarak ekliyoruz
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        return str(o)

# Flask modülüne yamayı uyguluyoruz
flask.json.JSONEncoder = CustomJSONEncoder

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mongoengine import MongoEngine
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)

# ========================================================
# 2. BÖLÜM: AYARLAR (Config Dosyası Yerine Buraya Gömdük)
# ========================================================
app.config['SECRET_KEY'] = 'TorontoCarRental_Secure_Key_2026_Ultra_Secret'
# MongoDB Atlas Bağlantısı
app.config['MONGODB_SETTINGS'] = {
    'host': 'mongodb+srv://Torontocarental:inan.1907@cluster0.oht1igm.mongodb.net/CarRentalDB?retryWrites=true&w=majority',
    'connectTimeoutMS': 30000,
    'socketTimeoutMS': 30000
}

# --- KRİTİK YAMA DEVAMI ---
# MongoEngine başlatılmadan ÖNCE, app içine sahte bir json_encoder ekliyoruz.
# Bu satır, "AttributeError: 'Flask' object has no attribute 'json_encoder'" hatasını çözer.
app.json_encoder = CustomJSONEncoder 
# --------------------------

db = MongoEngine(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ========================================================
# 3. BÖLÜM: VERİTABANI MODELLERİ (Kanada Standartları)
# ========================================================

class User(UserMixin, db.Document):
    email = db.StringField(unique=True, required=True)
    password = db.StringField(required=True)
    name = db.StringField(required=True)
    phone = db.StringField()
    drivers_license_id = db.StringField()
    # Dosya yüklemeleri için
    drivers_license_img = db.StringField() 
    passport_img = db.StringField()
    is_admin = db.BooleanField(default=False)
    
    def get_id(self):
        return str(self.id)

class Car(db.Document):
    # Araç Bilgileri
    car_id = db.StringField(unique=True, required=True) # Plaka veya ID
    brand = db.StringField(required=True)
    model = db.StringField(required=True)
    category = db.StringField(choices=['SUV', 'Sedan', 'Luxury', 'Van', 'Sport', 'Economy'], default='Sedan')
    price = db.IntField(required=True)
    image = db.ImageField() # Veritabanında saklanan resim
    
    # Detaylı Özellikler (Filtreleme için)
    transmission = db.StringField(choices=['Automatic', 'Manual'], default='Automatic')
    fuel_type = db.StringField(choices=['Gasoline', 'Diesel', 'Electric', 'Hybrid'], default='Gasoline')
    seats = db.IntField(default=5)
    features = db.ListField(db.StringField()) # Örn: ["Winter Tires", "GPS", "Heated Seats"]
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
    status = db.StringField(default="Pending") # Pending, Confirmed, Completed, Cancelled
    booking_date = db.DateTimeField(default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.objects(pk=user_id).first()

# ========================================================
# 4. BÖLÜM: YÖNLENDİRMELER (ROUTES)
# ========================================================

# --- Resim Görüntüleme Helper ---
@app.route('/car_image/<car_id>')
def car_image(car_id):
    car = Car.objects(id=car_id).first()
    if car and car.image:
        return car.image.read(), 200, {'Content-Type': car.image.content_type}
    return "", 404

@app.route('/', methods=['GET', 'POST'])
def index():
    # Vitrin için ilk 3 uygun aracı getir
    featured_cars = Car.objects(is_available=True).limit(3)
    
    if request.method == 'POST':
        # Ana sayfadaki arama motorundan gelen veriler
        pickup_loc = request.form.get('location')
        return redirect(url_for('display_cars', location=pickup_loc))
        
    return render_template('index.html', cars=featured_cars)

@app.route('/cars')
def display_cars():
    location_filter = request.args.get('location')
    category_filter = request.args.get('category')
    
    # Temel sorgu: Sadece uygun araçlar
    query = Car.objects(is_available=True)
    
    # Filtreleri uygula
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
        
        # ACİL DURUM ADMİN GİRİŞİ (Proje teslimi/test için)
        if email == 'admin' and password == '12345':
            admin_user = User.objects(email='admin@torontocar.com').first()
            if not admin_user:
                # Admin yoksa oluştur
                admin_user = User(
                    email='admin@torontocar.com', 
                    password=generate_password_hash('12345'), 
                    name='System Admin', 
                    is_admin=True
                )
                admin_user.save()
            login_user(admin_user)
            return redirect(url_for('admin_dashboard'))

        user = User.objects(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard')) # Normal kullanıcı Dashboard'a gider
            
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Kullanıcının kendi geçmiş kiralamaları
    my_bookings = Booking.objects(user=current_user).order_by('-booking_date')
    return render_template('dashboard.html', bookings=my_bookings)

@app.route('/book/<car_id>', methods=['GET', 'POST'])
@login_required
def add_booking(car_id):
    car = Car.objects.get_or_404(id=car_id)
    if request.method == 'POST':
        pickup_str = request.form.get('pickup_date')
        dropoff_str = request.form.get('dropoff_date')
        
        try:
            pickup = datetime.strptime(pickup_str, '%Y-%m-%d')
            dropoff = datetime.strptime(dropoff_str, '%Y-%m-%d')
            days = (dropoff - pickup).days
            if days < 1: days = 1
            
            total_price = days * car.price
            
            # Rezervasyonu Kaydet
            Booking(
                user=current_user,
                car=car,
                pickup_location=car.location, # Şimdilik aracın olduğu yerden
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
        # Yeni Araç Ekleme
        try:
            new_car = Car(
                car_id=request.form.get('car_id'),
                brand=request.form.get('brand'),
                model=request.form.get('model'),
                price=int(request.form.get('price')),
                category=request.form.get('category'),
                location=request.form.get('location'),
                transmission=request.form.get('transmission')
            )
            if 'image' in request.files:
                new_car.image.put(request.files['image'], content_type='image/jpeg')
            new_car.save()
            flash('Car added successfully to the fleet.', 'success')
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
    # Debug modunu açıyoruz ki hataları net görelim
    app.run(debug=True)