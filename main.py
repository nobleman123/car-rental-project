import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mongoengine import MongoEngine
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- AYARLAR ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'TorontoCarRental_Premium_2026'
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
    address = db.StringField()
    city = db.StringField()
    drivers_license_img = db.ImageField()
    passport_img = db.ImageField()
    is_admin = db.BooleanField(default=False)

class Car(db.Document):
    car_id = db.StringField(unique=True) 
    brand = db.StringField(required=True)
    model = db.StringField(required=True)
    # Temadaki kategorilerle eşleştirdik
    category = db.StringField(choices=['economy', 'suv', 'van', 'luxury', 'electric', 'sport'], default='economy')
    price = db.IntField(required=True) 
    transmission = db.StringField(choices=['Automatic', 'Manual'], default='Automatic')
    fuel_type = db.StringField(choices=['Gasoline', 'Electric', 'Hybrid', 'Diesel'], default='Gasoline')
    image = db.ImageField()
    features = db.ListField(db.StringField()) 
    is_available = db.BooleanField(default=True)

class Booking(db.Document):
    user = db.ReferenceField(User)
    car = db.ReferenceField(Car)
    pickup_location = db.StringField()
    dropoff_location = db.StringField()
    from_date = db.DateTimeField(required=True)
    to_date = db.DateTimeField(required=True)
    days = db.IntField()
    total_price = db.FloatField()
    status = db.StringField(default="Pending", choices=['Pending', 'Confirmed', 'Cancelled', 'Completed'])
    created_at = db.DateTimeField(default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.objects(pk=user_id).first()

# --- ROUTES ---

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Ana sayfadaki formdan gelen verileri alıp Fleet sayfasına filtre olarak atabiliriz
        # Şimdilik direkt filoya yönlendiriyoruz
        return redirect(url_for('display_cars'))
        
    # Vitrin için premium araçlardan 3 tane
    cars = Car.objects(is_available=True).limit(3)
    return render_template('index.html', cars=cars)

@app.route('/fleet')
def display_cars():
    # Kategori filtresi
    category = request.args.get('category')
    if category and category != 'all':
        cars = Car.objects(is_available=True, category=category)
    else:
        cars = Car.objects(is_available=True)
    return render_template('display_cars.html', cars=cars)

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
        flash('Welcome to Toronto Premium Rental. Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Admin Backdoor
        if email == 'admin' and password == '12345':
            u = User.objects(email='admin@toronto.ca').first()
            if not u:
                u = User(email='admin@toronto.ca', password=generate_password_hash('12345'), name='Master Admin', is_admin=True).save()
            login_user(u)
            return redirect(url_for('admin'))

        user = User.objects(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Welcome back, {user.name}', 'success')
            return redirect(url_for('admin' if user.is_admin else 'dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/car/<car_id>', methods=['GET', 'POST'])
def car_detail(car_id):
    car = Car.objects(pk=car_id).first()
    if not car: return "Car not found", 404

    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Please login to finalize booking.', 'warning')
            return redirect(url_for('login'))
            
        try:
            pickup = datetime.strptime(request.form.get('pickup'), '%Y-%m-%d')
            dropoff = datetime.strptime(request.form.get('dropoff'), '%Y-%m-%d')
        except ValueError:
            flash('Invalid dates selected.', 'danger')
            return redirect(url_for('car_detail', car_id=car_id))

        delta = (dropoff - pickup).days
        if delta < 1: delta = 1
            
        # Kullanıcı bilgilerini güncelle (Formdan geliyorsa)
        if request.form.get('phone'): current_user.phone = request.form.get('phone')
        if request.form.get('address'): current_user.address = request.form.get('address')
        
        # Belge yükleme
        if 'license_img' in request.files:
            f = request.files['license_img']
            if f.filename: current_user.drivers_license_img.replace(f, content_type=f.content_type)
        
        current_user.save()

        # Fiyat Hesaplama
        base_price = car.price * delta
        tax = base_price * 0.13
        total = base_price + tax
        
        booking = Booking(
            user=current_user,
            car=car,
            pickup_location=request.form.get('pickup_loc'),
            dropoff_location=request.form.get('dropoff_loc'),
            from_date=pickup,
            to_date=dropoff,
            days=delta,
            total_price=total
        )
        booking.save()
        flash('Reservation request created successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('car_detail.html', car=car)

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    bookings = Booking.objects(user=current_user).order_by('-created_at')
    return render_template('dashboard.html', bookings=bookings)

# --- ADMIN PANELİ (GELİŞMİŞ) ---
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin: return redirect(url_for('index'))
    
    if request.method == 'POST' and 'add_car' in request.form:
        try:
            # Features virgülle ayrılmış string gelir, listeye çeviririz
            feats = [x.strip() for x in request.form.get('features', '').split(',') if x.strip()]
            
            car = Car(
                car_id=request.form.get('car_id'),
                brand=request.form.get('brand'),
                model=request.form.get('model'),
                category=request.form.get('category'),
                price=int(request.form.get('price')),
                transmission=request.form.get('transmission'),
                fuel_type=request.form.get('fuel_type'),
                features=feats
            )
            if 'image' in request.files:
                f = request.files['image']
                if f.filename: car.image.put(f, content_type=f.content_type)
            car.save()
            flash('Vehicle added to fleet.', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')

    cars = Car.objects.all()
    bookings = Booking.objects.all().order_by('-created_at')
    return render_template('admin.html', cars=cars, bookings=bookings)

@app.route('/admin/booking/<action>/<booking_id>')
@login_required
def manage_booking(action, booking_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    booking = Booking.objects(pk=booking_id).first()
    if booking:
        if action == 'confirm': booking.status = 'Confirmed'
        elif action == 'cancel': booking.status = 'Cancelled'
        elif action == 'complete': booking.status = 'Completed'
        booking.save()
        flash(f'Booking {action}.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/delete_car/<car_id>')
@login_required
def delete_car(car_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    Car.objects(pk=car_id).delete()
    flash('Car removed from fleet.', 'warning')
    return redirect(url_for('admin'))

@app.route('/img/car/<car_id>')
def car_image(car_id):
    car = Car.objects(pk=car_id).first()
    if car and car.image:
        return car.image.read(), 200, {'Content-Type': car.image.content_type}
    return "", 404

if __name__ == '__main__':
    app.run(debug=True)
