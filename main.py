import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mongoengine import MongoEngine
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- AYARLAR ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'TorontoCarRental_Secret_2026'
app.config['MONGODB_SETTINGS'] = {
    'host': os.environ.get('MONGO_URI') or 'mongodb+srv://Torontocarental:inan.1907@cluster0.oht1igm.mongodb.net/CarRentalDB?retryWrites=true&w=majority',
    'connectTimeoutMS': 30000,
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
    # Kanada Adres Formatı
    address = db.StringField()
    city = db.StringField()
    province = db.StringField()
    zip_code = db.StringField()
    # Güvenlik Belgeleri
    drivers_license_img = db.ImageField()
    passport_img = db.ImageField()
    is_admin = db.BooleanField(default=False)

class Car(db.Document):
    car_id = db.StringField(unique=True) # Plaka veya Stok No
    brand = db.StringField(required=True)
    model = db.StringField(required=True)
    category = db.StringField(choices=['SUV', 'Sedan', 'Luxury', 'Economy', 'Sport'], default='Sedan')
    price = db.IntField(required=True) # Günlük Fiyat (CAD)
    transmission = db.StringField(choices=['Automatic', 'Manual'], default='Automatic')
    fuel_type = db.StringField(choices=['Gasoline', 'Electric', 'Hybrid', 'Diesel'], default='Gasoline')
    image = db.ImageField()
    features = db.ListField(db.StringField()) # GPS, Isıtmalı Koltuk vb.
    is_available = db.BooleanField(default=True)

class Booking(db.Document):
    user = db.ReferenceField(User)
    car = db.ReferenceField(Car)
    from_date = db.DateTimeField(required=True)
    to_date = db.DateTimeField(required=True)
    days = db.IntField()
    base_price = db.IntField()
    tax_amount = db.FloatField() # %13 HST
    total_price = db.FloatField()
    status = db.StringField(default="Pending", choices=['Pending', 'Confirmed', 'Cancelled', 'Completed'])
    created_at = db.DateTimeField(default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.objects(pk=user_id).first()

# --- ROUTES ---

@app.route('/')
def index():
    # Vitrin için ilk 4 müsait araç
    cars = Car.objects(is_available=True)[:4]
    return render_template('index.html', cars=cars)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        if User.objects(email=email).first():
            flash('This email is already registered.', 'danger')
            return redirect(url_for('register'))
        
        user = User(
            email=email,
            password=generate_password_hash(request.form.get('password')),
            name=request.form.get('name'),
            phone=request.form.get('phone')
        )
        user.save()
        flash('Account created successfully. Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Backdoor for Admin (Geliştirme Amaçlı)
        if email == 'admin' and password == '12345':
            u = User.objects(email='admin@toronto.ca').first()
            if not u:
                u = User(email='admin@toronto.ca', password=generate_password_hash('12345'), name='Admin', is_admin=True).save()
            login_user(u)
            return redirect(url_for('admin'))

        user = User.objects(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('admin' if user.is_admin else 'dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- ANA FONKSİYONLAR ---

@app.route('/fleet')
def display_cars():
    cars = Car.objects(is_available=True)
    return render_template('display_cars.html', cars=cars)

@app.route('/car/<car_id>', methods=['GET', 'POST'])
def car_detail(car_id):
    car = Car.objects(pk=car_id).first()
    if not car: return "Car not found", 404

    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Please login to book a car.', 'warning')
            return redirect(url_for('login'))
            
        pickup = datetime.strptime(request.form.get('pickup'), '%Y-%m-%d')
        dropoff = datetime.strptime(request.form.get('dropoff'), '%Y-%m-%d')
        
        delta = (dropoff - pickup).days
        if delta < 1:
            flash('Rental period must be at least 1 day.', 'danger')
            return redirect(url_for('car_detail', car_id=car_id))
            
        base_price = car.price * delta
        tax = base_price * 0.13 # Ontario HST Tax
        total = base_price + tax
        
        booking = Booking(
            user=current_user,
            car=car,
            from_date=pickup,
            to_date=dropoff,
            days=delta,
            base_price=base_price,
            tax_amount=tax,
            total_price=total
        )
        booking.save()
        flash('Reservation request sent! Wait for admin confirmation.', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('car_detail.html', car=car)

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        # Kullanıcı Profil Güncelleme & Dosya Yükleme
        current_user.phone = request.form.get('phone')
        current_user.address = request.form.get('address')
        current_user.city = request.form.get('city')
        current_user.zip_code = request.form.get('zip_code')
        
        if 'license_img' in request.files:
            f = request.files['license_img']
            if f.filename: current_user.drivers_license_img.replace(f, content_type=f.content_type)
            
        if 'passport_img' in request.files:
            f = request.files['passport_img']
            if f.filename: current_user.passport_img.replace(f, content_type=f.content_type)
            
        current_user.save()
        flash('Profile and documents updated.', 'success')

    bookings = Booking.objects(user=current_user).order_by('-created_at')
    return render_template('dashboard.html', bookings=bookings)

# --- ADMIN PANELİ ---
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin: return redirect(url_for('index'))
    
    # Araç Ekleme
    if request.method == 'POST' and 'add_car' in request.form:
        car = Car(
            car_id=request.form.get('car_id'),
            brand=request.form.get('brand'),
            model=request.form.get('model'),
            price=int(request.form.get('price')),
            category=request.form.get('category'),
            transmission=request.form.get('transmission'),
            features=request.form.get('features').split(',') if request.form.get('features') else []
        )
        if 'image' in request.files:
            f = request.files['image']
            if f.filename: car.image.put(f, content_type=f.content_type)
        car.save()
        flash('New car added to fleet.', 'success')

    cars = Car.objects.all()
    bookings = Booking.objects.all().order_by('-created_at')
    return render_template('admin.html', cars=cars, bookings=bookings)

@app.route('/admin/booking/<action>/<booking_id>')
@login_required
def manage_booking(action, booking_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    
    booking = Booking.objects(pk=booking_id).first()
    if booking:
        if action == 'confirm':
            booking.status = 'Confirmed'
            # Opsiyonel: Aracı o tarihler için meşgul işaretle
        elif action == 'cancel':
            booking.status = 'Cancelled'
        elif action == 'complete':
            booking.status = 'Completed'
        booking.save()
        flash(f'Booking {action}ed.', 'success')
    return redirect(url_for('admin'))

# --- RESİM SERVİSİ ---
@app.route('/img/car/<car_id>')
def car_image(car_id):
    car = Car.objects(pk=car_id).first()
    if car and car.image:
        return car.image.read(), 200, {'Content-Type': car.image.content_type}
    return "", 404

if __name__ == '__main__':
    app.run(debug=True)
