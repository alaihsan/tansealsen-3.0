import sys
import os

# Add the parent directory to sys.path if running directly
# This allows 'from my_app...' imports to work even if run as 'python app.py'
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.append(parent_dir)

from flask import Flask
from my_app.config import Config
from my_app.extensions import db, migrate
from my_app.models import User, School, Student, Classroom, Violation, ViolationRule, ViolationCategory, Ayat, ViolationPhoto  # Import models agar terdeteksi
from my_app.routes import main
from flask_login import LoginManager

app = Flask(__name__)
app.config.from_object(Config)

# Inisialisasi Extensions
db.init_app(app)
migrate.init_app(app, db) # Inisialisasi Flask-Migrate

# Login Manager Setup
login_manager = LoginManager()
login_manager.login_view = 'main.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app.register_blueprint(main)

if __name__ == "__main__":
    app.run(debug=True)