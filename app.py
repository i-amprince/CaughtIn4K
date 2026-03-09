import os
# Put this BEFORE any other imports
os.environ["TRUST_REMOTE_CODE"] = "1" 
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# Import our custom machine learning modules
from run_model import run_inferencer_batch
from training import train_local_item_model

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key-for-dev' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False) 

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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
    all_users = User.query.all() if current_user.role == 'System Administrator' else []
    return render_template('dashboard.html', user=current_user, all_users=all_users, results=None, summary=None)

@app.route('/start_training', methods=['POST'])
@login_required
def start_training():
    if current_user.role != 'Manufacturing Engineer':
        flash('Permission Denied.', 'error')
        return redirect(url_for('dashboard'))

    dataset_path = request.form.get('dataset_path')
    item_name = request.form.get('item_name', '').strip().lower()

    if not item_name or not os.path.exists(dataset_path):
        flash('Error: Invalid path or item name.', 'error')
        return redirect(url_for('dashboard'))

    BASE_OUTPUT_DIR = os.path.join(app.root_path, 'inspection_model_outputs')
    try:
        flash(f"Training started for '{item_name}'. Please wait...", 'success')
        final_path = train_local_item_model(dataset_path, item_name, BASE_OUTPUT_DIR)
        flash(f"✅ Training completed! Model ready at: {final_path}", 'success')
    except Exception as e:
        flash(f'❌ Training Error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/run_inspection', methods=['POST'])
@login_required
def run_inspection():
    if current_user.role != 'Quality Operator':
        flash('Permission Denied.', 'error')
        return redirect(url_for('dashboard'))

    item_name = request.form.get('item_name', '').strip().lower()
    test_folder = request.form.get('test_folder')
    
    # Path matches the structure created by training.py's ExportMode
    MODEL_PATH = os.path.join(
        app.root_path, 'inspection_model_outputs', item_name, 'weights', 'torch', 'model.pt'
    )
    
    if not os.path.exists(MODEL_PATH):
        flash(f'Model not found for item "{item_name}". Please train it first.', 'error')
        return redirect(url_for('dashboard'))
    
    OUTPUT_DIR = os.path.join(app.root_path, 'static', 'results')
    
    try:
        results_data, summary = run_inferencer_batch(MODEL_PATH, test_folder, OUTPUT_DIR)
        flash(f'Inspection Complete!', 'success')
        return render_template('dashboard.html', user=current_user, results=results_data, summary=summary)
    except Exception as e:
        flash(f'Inference Error: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/create_user', methods=['POST'])
@login_required
def create_user():
    if current_user.role != 'System Administrator':
        flash('Permission Denied.', 'error')
        return redirect(url_for('dashboard'))

    new_user = User(
        username=request.form.get('username'),
        password=request.form.get('password'),
        role=request.form.get('role')
    )
    db.session.add(new_user)
    db.session.commit()
    flash('User created successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

def create_initial_users():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password='123', role='System Administrator'))
            db.session.add(User(username='inspector', password='123', role='Quality Operator'))
            db.session.add(User(username='engineer', password='123', role='Manufacturing Engineer'))
            db.session.commit()
            
    os.makedirs(os.path.join(app.root_path, 'static', 'results'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'inspection_model_outputs'), exist_ok=True)

if __name__ == '__main__':
    create_initial_users()
    app.run(debug=True)