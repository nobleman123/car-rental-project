import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mongoengine import MongoEngine
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'TorontoPremium2026_Secret'
app.config['MONGODB_SETTINGS'] = {
    'host': os.environ.get('MONGO_URI') or 'mongodb+srv://Torontocarental:inan.1907@cluster0.oht1igm.mongodb.net/CarRentalDB?retryWrites=true&w=majority',
}

db = MongoEngine(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELS ---
class User(UserMixin, db.Document):
    email = db.StringField(unique=True, required=True)
    password = db.StringField(required=True)
    name = db.StringField(required=True)
    phone = db.StringField()
    address = db.StringField()
    drivers_license_img = db.ImageField()
    is_admin = db.BooleanField(default=False)

class Car(db.Document):
    car_id = db.StringField(unique=True, required=True) # Plate or Serial
    brand = db.StringField(required=True)
    model = db.StringField(required=True)
    category = db.StringField(choices=['SUV', 'Luxury', 'Economy', 'Electric', 'Sport', 'Van'], default='Economy')
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
    total_price = db.FloatField()
    status = db.StringField(default="Pending", choices=['Pending', 'Confirmed', 'Cancelled', 'Completed'])
    created_at = db.DateTimeField(default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.objects(pk=user_id).first()

# --- ROUTES ---
@app.route('/')
def index():
    # Hero section için en lüks 3 araç
    featured_cars = Car.objects(is_available=True).limit(3)
    return render_template('index.html', cars=featured_cars)

@app.route('/fleet')
def display_cars():
    category = request.args.get('category')
    if category:
        cars = Car.objects(category=category, is_available=True)
    else:
        cars = Car.objects(is_available=True)
    return render_template('display_cars.html', cars=cars)

@app.route('/car/<id>', methods=['GET', 'POST'])
def car_detail(id):
    car = Car.objects.get_or_404(pk=id)
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash("Please login to book.", "warning")
            return redirect(url_for('login'))
        
        # Rezervasyon Mantığı
        pickup = datetime.strptime(request.form.get('pickup'), '%Y-%m-%d')
        dropoff = datetime.strptime(request.form.get('dropoff'), '%Y-%m-%d')
        days = (dropoff - pickup).days or 1
        
        booking = Booking(
            user=current_user,
            car=car,
            from_date=pickup,
            to_date=dropoff,
            total_price=car.price * days * 1.13 # Tax incl.
        ).save()
        
        flash("Reservation sent! Our team will contact you.", "success")
        return redirect(url_for('dashboard'))
        
    return render_template('car_detail.html', car=car)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Admin Login Check
        if email == "admin" and password == "12345":
            user = User.objects(email="admin@torontocarental.com").first()
            if not user:
                user = User(email="admin@torontocarental.com", password=generate_password_hash("12345"), name="Master Admin", is_admin=True).save()
            login_user(user)
            return redirect(url_for('admin'))

        user = User.objects(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash("Invalid credentials", "danger")
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin: return redirect(url_for('index'))
    
    if request.method == 'POST' and 'add_car' in request.form:
        new_car = Car(
            car_id=request.form.get('car_id'),
            brand=request.form.get('brand'),
            model=request.form.get('model'),
            category=request.form.get('category'),
            price=int(request.form.get('price')),
            transmission=request.form.get('transmission'),
            features=request.form.get('features').split(',')
        )
        if 'image' in request.files:
            img = request.files['image']
            new_car.image.put(img, content_type=img.content_type)
        new_car.save()
        flash("Car added successfully!", "success")

    return render_template('admin.html', cars=Car.objects.all(), bookings=Booking.objects.all())

@app.route('/img/car/<id>')
def car_image(id):
    car = Car.objects.get_or_404(pk=id)
    if car.image:
        return car.image.read(), 200, {'Content-Type': car.image.content_type}
    return "", 404

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    my_bookings = Booking.objects(user=current_user)
    return render_template('dashboard.html', bookings=my_bookings)

if __name__ == '__main__':
    app.run(debug=True)
