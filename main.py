import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mongoengine import MongoEngine
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)

# --- AYARLAR ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'TorontoCarRental_Secret_2026'
app.config['MONGODB_SETTINGS'] = {
    'host': os.environ.get('MONGO_URI') or 'mongodb+srv://Torontocarental:inan.1907@cluster0.oht1igm.mongodb.net/CarRentalDB?retryWrites=true&w=majority',
    'connectTimeoutMS': 30000,
}

# --- GOOGLE OAUTH AYARLARI ---
app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')

db = MongoEngine(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},
)

# --- MODELLER ---
class User(UserMixin, db.Document):
    email = db.StringField(unique=True, required=True)
    password = db.StringField() # Google girişinde boş olabilir
    name = db.StringField(required=True)
    phone = db.StringField()
    address = db.StringField()
    city = db.StringField()
    province = db.StringField()
    zip_code = db.StringField()
    drivers_license_img = db.ImageField()
    passport_img = db.ImageField()
    is_admin = db.BooleanField(default=False)
    auth_type = db.StringField(default='email') # email veya google

class Car(db.Document):
    car_id = db.StringField(unique=True)
    brand = db.StringField(required=True)
    model = db.StringField(required=True)
    category = db.StringField(choices=['SUV', 'Sedan', 'Luxury', 'Economy', 'Sport'], default='Sedan')
    price = db.IntField(required=True)
    transmission = db.StringField(choices=['Automatic', 'Manual'], default='Automatic')
    fuel_type = db.StringField(choices=['Gasoline', 'Electric', 'Hybrid', 'Diesel'], default='Gasoline')
    image = db.ImageField()
    features = db.ListField(db.StringField())
    is_available = db.BooleanField(default=True)

class Booking(db.Document):
    user = db.ReferenceField(User)
    car = db.ReferenceField(Car)
    from_date = db.DateTimeField(required=True)
    to_date = db.DateTimeField(required=True)
    days = db.IntField()
    base_price = db.IntField()
    tax_amount = db.FloatField()
    total_price = db.FloatField()
    status = db.StringField(default="Pending", choices=['Pending', 'Confirmed', 'Cancelled', 'Completed'])
    created_at = db.DateTimeField(default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.objects(pk=user_id).first()

# --- CONTEXT PROCESSOR (WhatsApp için her sayfada geçerli) ---
@app.context_processor
def inject_whatsapp():
    return dict(whatsapp_number="15550123456") # Kendi numaranı buraya yaz

# --- ROUTES ---

@app.route('/', methods=['GET', 'POST'])
def index():
    # 405 HATASI ÇÖZÜMÜ: Ana sayfadan gelen POST isteğini yakala
    if request.method == 'POST':
        # Kullanıcı "Find Car" dediğinde Fleet sayfasına yönlendir
        pickup = request.form.get('pickup')
        return redirect(url_for('display_cars'))
        
    cars = Car.objects(is_available=True).limit(4)
    return render_template('index.html', cars=cars)

# --- GOOGLE LOGIN ROUTES ---
@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/google/callback')
def google_authorize():
    token = google.authorize_access_token()
    user_info = google.get('userinfo').json()
    
    email = user_info['email']
    user = User.objects(email=email).first()
    
    if not user:
        user = User(
            email=email,
            name=user_info['name'],
            auth_type='google',
            password='google_user_no_pass' # Dummy password
        )
        user.save()
    
    login_user(user)
    flash('Logged in via Google successfully!', 'success')
    return redirect(url_for('dashboard'))

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
            phone=request.form.get('phone'),
            auth_type='email'
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
        
        # Admin Backdoor
        if email == 'admin' and password == '12345':
            u = User.objects(email='admin@toronto.ca').first()
            if not u:
                u = User(email='admin@toronto.ca', password=generate_password_hash('12345'), name='Admin', is_admin=True).save()
            login_user(u)
            return redirect(url_for('admin'))

        user = User.objects(email=email).first()
        # Google hesapları şifre ile giremez uyarısı eklenebilir
        if user and user.auth_type == 'email' and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('admin' if user.is_admin else 'dashboard'))
        elif user and user.auth_type == 'google':
             flash('Please use Google Login for this email.', 'warning')
        else:
            flash('Invalid email or password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

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
            
        # 1. Tarih Kontrolleri
        try:
            pickup = datetime.strptime(request.form.get('pickup'), '%Y-%m-%d')
            dropoff = datetime.strptime(request.form.get('dropoff'), '%Y-%m-%d')
        except ValueError:
            flash('Invalid date format.', 'danger')
            return redirect(url_for('car_detail', car_id=car_id))

        delta = (dropoff - pickup).days
        if delta < 1:
            flash('Rental period must be at least 1 day.', 'danger')
            return redirect(url_for('car_detail', car_id=car_id))

        # 2. Belge ve Adres Güncelleme (Rezervasyon sırasında zorunlu)
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        # Eğer kullanıcıda bu bilgiler eksikse ve formdan geliyorsa güncelle
        if phone: current_user.phone = phone
        if address: current_user.address = address
        
        # Dosya Yükleme Kontrolü
        if 'license_img' in request.files:
            f = request.files['license_img']
            if f.filename: 
                current_user.drivers_license_img.replace(f, content_type=f.content_type)
        
        if 'passport_img' in request.files:
            f = request.files['passport_img']
            if f.filename: 
                current_user.passport_img.replace(f, content_type=f.content_type)
        
        current_user.save()

        # Eksik belge kontrolü (Opsiyonel: İstersen burayı açabilirsin)
        # if not current_user.drivers_license_img:
        #     flash('You must upload your Drivers License to book.', 'danger')
        #     return redirect(url_for('car_detail', car_id=car_id))
            
        # 3. Rezervasyonu Oluştur
        base_price = car.price * delta
        tax = base_price * 0.13
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
        flash('Reservation request sent! Documents updated.', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('car_detail.html', car=car)

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    # Dashboard sadece görüntüleme ve ek dosya güncelleme için kalsın
    if request.method == 'POST':
        if 'license_img' in request.files:
            f = request.files['license_img']
            if f.filename: current_user.drivers_license_img.replace(f, content_type=f.content_type)
        current_user.save()
        flash('Profile updated.', 'success')

    bookings = Booking.objects(user=current_user).order_by('-created_at')
    return render_template('dashboard.html', bookings=bookings)

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin: return redirect(url_for('index'))
    
    if request.method == 'POST' and 'add_car' in request.form:
        # Hata Yönetimi Ekleyelim
        try:
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
            flash('New car added to fleet successfully.', 'success')
        except Exception as e:
            flash(f'Error adding car: {str(e)}', 'danger')

    # Tüm arabaları getir (QuerySet'i listeye çevirmeyi deneyelim garanti olsun)
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
        flash(f'Booking {action}ed.', 'success')
    return redirect(url_for('admin'))

@app.route('/img/car/<car_id>')
def car_image(car_id):
    car = Car.objects(pk=car_id).first()
    if car and car.image:
        return car.image.read(), 200, {'Content-Type': car.image.content_type}
    return "", 404

if __name__ == '__main__':
    app.run(debug=True)
