from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# --- CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key-for-dev' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- DATABASE MODEL ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False) 

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
            
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    all_users = []
    # If the logged-in user is an Admin, fetch all users to show them
    if current_user.role == 'System Administrator':
        all_users = User.query.all()
    
    return render_template('dashboard.html', user=current_user, all_users=all_users)

@app.route('/create_user', methods=['POST'])
@login_required
def create_user():
    # Security: Only Admins can create users
    if current_user.role != 'System Administrator':
        flash('Permission Denied.', 'error')
        return redirect(url_for('dashboard'))

    new_username = request.form.get('username')
    new_password = request.form.get('password')
    new_role = request.form.get('role')

    # Check if user already exists
    if User.query.filter_by(username=new_username).first():
        flash('Username already exists!', 'error')
    else:
        new_user = User(username=new_username, password=new_password, role=new_role)
        db.session.add(new_user)
        db.session.commit()
        flash(f'User "{new_username}" created successfully!', 'success')

    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- INITIAL SETUP ---
def create_initial_users():
    """Creates default users if they don't exist"""
    with app.app_context():
        db.create_all()
        # Create a default Admin if one doesn't exist
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password='123', role='System Administrator'))
            db.session.commit()
            print(">>> System Initialized. Default user: 'admin' (pass: 123)")

if __name__ == '__main__':
    create_initial_users()
    app.run(debug=True)