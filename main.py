import json
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mongoengine import MongoEngine
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)

# --- AYARLAR ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'TorontoCarRental_Secret_2026'

# Veritabanı Bağlantısı
# Not: Render'da Environment Variable olarak MONGO_URI eklemeniz önerilir.
app.config['MONGODB_SETTINGS'] = {
    'host': os.environ.get('MONGO_URI') or 'mongodb+srv://Torontocarental:inan.1907@cluster0.oht1igm.mongodb.net/CarRentalDB?retryWrites=true&w=majority',
    'connectTimeoutMS': 30000,
    'socketTimeoutMS': 30000
}

db = MongoEngine(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELLER ---
class User(UserMixin, db.Document):
    email = db.StringField(unique=True, required=True)
    password = db.StringField(required=True)
    name = db.StringField(required=True)
    phone = db.StringField()
    address = db.StringField()
    city = db.StringField()
    province = db.StringField()
    zip_code = db.StringField()
    drivers_license_no = db.StringField()
    drivers_license_img = db.ImageField()
    passport_img = db.ImageField()
    is_admin = db.BooleanField(default=False)

class Car(db.Document):
    car_id = db.StringField(unique=True, required=True)
    brand = db.StringField(required=True)
    model = db.StringField(required=True)
    category = db.StringField(choices=['SUV', 'Sedan', 'Luxury', 'Economy'], default='Sedan')
    price = db.IntField(required=True)
    transmission = db.StringField(choices=['Automatic', 'Manual'], default='Automatic')
    fuel_type = db.StringField(choices=['Gasoline', 'Electric', 'Hybrid'], default='Gasoline')
    location = db.StringField(default='Toronto')
    image = db.ImageField()
    is_available = db.BooleanField(default=True)

class Booking(db.Document):
    user = db.ReferenceField(User)
    car = db.ReferenceField(Car)
    from_date = db.DateTimeField(required=True)
    to_date = db.DateTimeField(required=True)
    total_price = db.IntField()
    status = db.StringField(default="Pending")

@login_manager.user_loader
def load_user(user_id):
    return User.objects(pk=user_id).first()

# --- YÖNLENDİRMELER (ROUTES) ---

@app.route('/')
def index():
    # Müsait olan ilk 3 aracı göster
    cars = Car.objects(is_available=True)[:6]
    return render_template('index.html', cars=cars)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        existing_user = User.objects(email=email).first()
        if existing_user:
            flash('Bu e-posta adresi zaten kayıtlı.', 'danger')
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(request.form.get('password'))
        new_user = User(
            email=email,
            password=hashed_password,
            name=request.form.get('name')
        )
        new_user.save()
        flash('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Acil Admin Girişi (Geliştirme Amaçlı)
        if email == 'admin' and password == '12345':
            u = User.objects(email='admin@toronto.ca').first()
            if not u:
                u = User(email='admin@toronto.ca', password=generate_password_hash('12345'), name='Admin', is_admin=True).save()
            login_user(u)
            return redirect(url_for('admin'))
        
        user = User.objects(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            # Admin ise admin paneline, değilse dashboard'a
            target = url_for('admin') if user.is_admin else url_for('dashboard')
            return redirect(target)
            
        flash('E-posta veya şifre hatalı.', 'danger')
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        current_user.phone = request.form.get('phone')
        current_user.address = request.form.get('address')
        current_user.city = request.form.get('city')
        current_user.province = request.form.get('province')
        current_user.zip_code = request.form.get('zip_code')
        current_user.drivers_license_no = request.form.get('license_no')
        
        if 'license_img' in request.files:
            img = request.files['license_img']
            if img.filename:
                current_user.drivers_license_img.replace(img, content_type=img.content_type)
        
        current_user.save()
        flash('Bilgileriniz başarıyla güncellendi.', 'success')
        
    bookings = Booking.objects(user=current_user)
    return render_template('dashboard.html', bookings=bookings)

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    # Güvenlik kontrolü: Sadece adminler girebilir
    if not current_user.is_admin:
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Yeni Araç Ekleme
        try:
            car = Car(
                car_id=request.form.get('car_id'),
                brand=request.form.get('brand'),
                model=request.form.get('model'),
                price=int(request.form.get('price')),
                category=request.form.get('category'),
                transmission=request.form.get('transmission'),
                fuel_type=request.form.get('fuel_type', 'Gasoline'),
                location=request.form.get('location', 'Toronto')
            )
            if 'image' in request.files:
                img = request.files['image']
                if img.filename:
                    car.image.put(img, content_type=img.content_type)
            car.save()
            flash('Araç sisteme başarıyla eklendi.', 'success')
        except Exception as e:
            flash(f'Hata oluştu: {str(e)}', 'danger')
    
    cars = Car.objects.all()
    bookings = Booking.objects.all()
    return render_template('admin.html', cars=cars, bookings=bookings)

@app.route('/car_image/<car_id>')
def car_image(car_id):
    car = Car.objects(car_id=car_id).first() # id yerine car_id kullanıldı
    if not car:
        car = Car.objects(pk=car_id).first() # fallback olarak primary key dene
        
    if car and car.image:
        return car.image.read(), 200, {'Content-Type': car.image.content_type}
    return "", 404

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Başarıyla çıkış yapıldı.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
