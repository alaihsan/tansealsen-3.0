from my_app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class School(db.Model):
    __tablename__ = 'schools'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    address = db.Column(db.String(255), nullable=True)
    logo = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    users = db.relationship('User', backref='school', lazy=True)
    classrooms = db.relationship('Classroom', backref='school', lazy=True)
    students = db.relationship('Student', backref='school', lazy=True)
    rules = db.relationship('ViolationRule', backref='school', lazy=True)
    categories = db.relationship('ViolationCategory', backref='school', lazy=True)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=True)
    
    role = db.Column(db.String(20), default='school_admin', nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=True)
    
    def set_password(self, password):
        self.password = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password, password)
        
    @property
    def is_super_admin(self):
        return self.role == 'super_admin'

class Classroom(db.Model):
    __tablename__ = 'classrooms'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    students = db.relationship('Student', backref='classroom', lazy=True)

class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    nis = db.Column(db.String(20), nullable=False)
    
    classroom_id = db.Column(db.Integer, db.ForeignKey('classrooms.id'), index=True)
    rombel = db.Column(db.String(50)) 
    poin = db.Column(db.Integer, default=100)
    
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False, index=True)
    violations = db.relationship('Violation', backref='student', lazy=True)

class ViolationRule(db.Model):
    __tablename__ = 'violation_rules'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)

    # relationship: rule -> ayats
    ayats = db.relationship('Ayat', backref='rule', lazy=True, cascade='all, delete-orphan')

class ViolationCategory(db.Model):
    __tablename__ = 'violation_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)

class Violation(db.Model):
    __tablename__ = 'violations'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(2000), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False, index=True)

    pasal = db.Column(db.String(255), nullable=True)
    kategori_pelanggaran = db.Column(db.String(50), nullable=True, index=True)
    di_input_oleh = db.Column(db.String(100), nullable=True)
    
    photos = db.relationship('ViolationPhoto', backref='violation', lazy=True, cascade="all, delete-orphan")

    # --- KOLOM BARU UNTUK REMISI ---
    is_remitted = db.Column(db.Boolean, default=False) # Status Remisi
    remission_reason = db.Column(db.String(255), nullable=True) # Alasan Remisi
    remission_date = db.Column(db.DateTime, nullable=True) # Kapan diremisi

    @property
    def tanggal_kejadian(self):
        if self.date_posted:
            if self.date_posted.hour == 0 and self.date_posted.minute == 0:
                return self.date_posted.strftime('%d/%m/%Y')
            return self.date_posted.strftime('%d/%m/%Y %H:%M')
        return "-"

    @property
    def tanggal_dicatat(self):
        return self.date_posted

# Association table between violations and ayats (many-to-many)
violation_ayats = db.Table(
    'violation_ayats',
    db.Column('violation_id', db.Integer, db.ForeignKey('violations.id'), primary_key=True),
    db.Column('ayat_id', db.Integer, db.ForeignKey('ayats.id'), primary_key=True)
)

# Ayat model (sub-clause under a ViolationRule/Pasal)
class Ayat(db.Model):
    __tablename__ = 'ayats'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), nullable=True)
    description = db.Column(db.String(1000), nullable=False)
    rule_id = db.Column(db.Integer, db.ForeignKey('violation_rules.id'), nullable=False, index=True)

    def __repr__(self):
        return f"<Ayat {self.number or self.id}: {self.description[:30]}...>"

# Link Violation -> Ayat via many-to-many
Violation.ayats = db.relationship('Ayat', secondary=violation_ayats, backref=db.backref('violations', lazy='dynamic'))

class ViolationPhoto(db.Model):
    __tablename__ = 'violation_photos'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    violation_id = db.Column(db.Integer, db.ForeignKey('violations.id'), nullable=False)