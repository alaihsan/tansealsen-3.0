import os

class Config:
    # Direktori dasar aplikasi
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    SECRET_KEY = 'kunci_rahasia_yang_sangat_sulit_ditebak_ini_harus_panjang'
    
    # --- KONFIGURASI MYSQL ---
    # Sesuaikan dengan setting MySQL Workbench Anda
    DB_USERNAME = 'root'         # Default XAMPP/MySQL biasanya 'root'
    DB_PASSWORD = 'passwd'             # Default XAMPP biasanya kosong, sesuaikan jika ada password
    DB_HOST = 'localhost'        # Server lokal
    DB_NAME = 'tanse_db'         # Nama database yang baru saja Anda buat
    
    # Connection String untuk MySQL
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Opsi tambahan agar koneksi stabil
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
    }
    
    # Konfigurasi Upload
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    PER_PAGE = 20