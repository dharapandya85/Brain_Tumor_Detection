import os
import secrets
import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing import image
from PIL import Image
import cv2
import uuid
from keras.models import load_model
from flask import Flask,request,render_template,redirect,url_for,session,flash,jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from datetime import timedelta,datetime

app=Flask(__name__)

app.secret_key = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#UPLOAD_FOLDER = 'uploads'
UPLOAD_FOLDER = os.path.join('static','uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
users={}

db = SQLAlchemy(app)
# Define User model for the database
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    age = db.Column(db.Integer)
    name = db.Column(db.String(150))

# Define Prediction model for storing user predictions
class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    result = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('predictions', lazy=True))
# Initialize the database
with app.app_context():
    db.create_all()
model=load_model('BrainTumor10Epochs.h5')
print('Model loaded. Check http://127.0.0.1:5000/')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_className(classNo):
    if classNo==0:
        return "No Brain Tumor"
    elif classNo==1:
        return "Yes Brain Tumor"
def getResult(img):
    try:
        
        image = cv2.imread(img)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)  # Convert BGR to RGB
        image = Image.fromarray(image)
        image=image.resize((64,64))
        image=np.array(image)
        input_img=np.expand_dims(image,axis=0)
        result=model.predict(input_img)
        print("Raw Model Output:", result)
        predicted_class=np.argmax(result,axis=-1)
        
        return predicted_class
    except Exception as e:
        print(f"Error in processing image: {e}")
        raise ValueError("Unable to process the image for prediction.")
@app.route('/',methods=['GET'])
def index():
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        age = request.form.get('age')
        name = request.form.get('name')
        if password!= confirm_password:
            flash("Passwords do not match!")
            return render_template('signup.html')
        


        # Check if username already exists
        if User.query.filter_by(username=username).first():
        
            flash("Username already exists. Please choose another.")
            return render_template('signup.html') 
        
        hashed_password=generate_password_hash(password,method='pbkdf2:sha256')
     # Add new user to the database
        new_user = User(username=username, password=hashed_password, age=age, name=name)
        db.session.add(new_user)
        db.session.commit()
        flash("Signup successful! Please log in.")
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash("Please log in first.")
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    #previous_attempts = Prediction.query.filter_by(user_id=user.id).order_by(Prediction.timestamp.desc()).all()  # Fetch user's predictions
    #recent_activity = previous_attempts[:3]  # Show the 3 most recent activities
    prediction = Prediction.query.filter_by(user_id=user.id).order_by(Prediction.id.desc()).first()
    return render_template('dashboard.html',
                           prediction=prediction)
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password,password):
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials!")
            return render_template('login.html')
    return render_template('login.html')
@app.route('/predict',methods=['POST'])
def predict():
    if 'username' not in session:
        flash('Please log in first')
        return redirect(url_for('login'))
    #user = User.query.filter_by(username=session['username']).first()

    
    if 'file' not in request.files:
        flash("No file selected!")
        return redirect(url_for('dashboard'))
    #user = User.query.filter_by(username=session['username']).first()

    
    #if request.method=='POST':
    f = request.files['file']

    if f.filename == '':
        flash("No selected file")
        return redirect(url_for('dashboard'))
    if f and allowed_file(f.filename):
        #basepath = os.path.dirname(__file__)
        
        #if os.path.exists(file_path):
            #print(f"Image successfully saved at: {file_path}")
        #else:
            #print("File saving failed!")
        #basepath=os.path.dirname(__file__)
        unique_filename = f"{uuid.uuid4()}_{secure_filename(f.filename)}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        f.save(file_path)
        classNo = getResult(file_path)
        result = get_className(classNo[0])

        user = User.query.filter_by(username=session['username']).first()
        
        prediction = Prediction(user_id=user.id, image_path=f'uploads/{unique_filename}', result=result)
       
        db.session.add(prediction)
        db.session.commit()
            
        return render_template('dashboard.html', result=result, prediction_image=f'uploads/{unique_filename}')
            
       
        
    else:
        flash("Invalid file type")
        return redirect(url_for('dashboard'))



@app.route('/logout')
def logout():
    session.pop('username', None)
   
    flash("Logged out successfully.")
    return redirect(url_for('index'))



if __name__=='__main__':
    
    app.run(debug=True)