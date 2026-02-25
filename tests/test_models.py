from my_app.models import User, Student, School, ViolationRule, Ayat, Violation, Classroom, ViolationCategory
from my_app.extensions import db
from datetime import datetime

def test_password_hashing(app):
    """Test keamanan password."""
    # Hapus 'role'
    u = User(username='guru_test')
    u.set_password('rahasia')
    
    assert u.check_password('rahasia') is True
    assert u.check_password('salah') is False
    assert u.password_hash != 'rahasia'

def test_create_student(app):
    """Test pembuatan data siswa."""
    # Hapus 'rombel' karena error (field mungkin tidak ada di DB)
    s = Student(name="Ahmad", nis="998877")
    db.session.add(s)
    db.session.commit()

    saved_student = Student.query.filter_by(nis="998877").first()
    assert saved_student is not None
    assert saved_student.name == "Ahmad"


# ===== TESTS UNTUK AYAT FEATURE =====

def test_create_ayat_model(app):
    """Test pembuatan model Ayat."""
    with app.app_context():
        # Buat school
        school = School(name="Test School", address="Test Address")
        db.session.add(school)
        db.session.flush()
        
        # Buat rule
        rule = ViolationRule(code="Pasal 1", description="Ketertiban", school_id=school.id)
        db.session.add(rule)
        db.session.flush()
        
        # Buat ayat
        ayat = Ayat(number="Ayat 1", description="Hadir tepat waktu", rule_id=rule.id)
        db.session.add(ayat)
        db.session.commit()
        
        # Verify
        saved_ayat = Ayat.query.filter_by(number="Ayat 1").first()
        assert saved_ayat is not None
        assert saved_ayat.description == "Hadir tepat waktu"
        assert saved_ayat.rule_id == rule.id


def test_violation_rule_ayat_relationship(app):
    """Test hubungan antara ViolationRule dan Ayat."""
    with app.app_context():
        school = School(name="Test School 2", address="Test Address 2")
        db.session.add(school)
        db.session.flush()
        
        rule = ViolationRule(code="Pasal 2", description="Kerapihan", school_id=school.id)
        db.session.add(rule)
        db.session.flush()
        
        # Tambah multiple ayats
        ayat1 = Ayat(number="1", description="Menggunakan seragam lengkap", rule_id=rule.id)
        ayat2 = Ayat(number="2", description="Rambut rapi", rule_id=rule.id)
        db.session.add_all([ayat1, ayat2])
        db.session.commit()
        
        # Verify relationship
        rule_fetched = ViolationRule.query.filter_by(code="Pasal 2").first()
        assert len(rule_fetched.ayats) == 2
        assert rule_fetched.ayats[0].description == "Menggunakan seragam lengkap"


def test_violation_ayat_many_to_many(app):
    """Test hubungan many-to-many antara Violation dan Ayat."""
    with app.app_context():
        # Setup data
        school = School(name="Test School 3", address="Test Address 3")
        db.session.add(school)
        db.session.flush()
        
        classroom = Classroom(name="10A", school_id=school.id)
        db.session.add(classroom)
        db.session.flush()
        
        student = Student(name="Budi", nis="12345", school_id=school.id, classroom_id=classroom.id)
        db.session.add(student)
        db.session.flush()
        
        rule = ViolationRule(code="Pasal 3", description="Disiplin", school_id=school.id)
        db.session.add(rule)
        db.session.flush()
        
        ayat1 = Ayat(number="1", description="Tidak bolos", rule_id=rule.id)
        ayat2 = Ayat(number="2", description="Mengikuti upacara", rule_id=rule.id)
        db.session.add_all([ayat1, ayat2])
        db.session.flush()
        
        # Create violation with ayats
        category = ViolationCategory(name="Sedang", points=15, school_id=school.id)
        db.session.add(category)
        db.session.flush()
        
        violation = Violation(
            description="Siswa bolos tanpa keterangan",
            points=15,
            date_posted=datetime.utcnow(),
            student_id=student.id,
            pasal="Pasal 3 - Disiplin",
            kategori_pelanggaran="Sedang",
            di_input_oleh="Guru BK"
        )
        db.session.add(violation)
        db.session.flush()
        
        # Link ayats to violation
        violation.ayats.append(ayat1)
        violation.ayats.append(ayat2)
        db.session.commit()
        
        # Verify
        v = Violation.query.filter_by(id=violation.id).first()
        assert len(v.ayats) == 2
        assert any(a.number == "1" for a in v.ayats)
        assert any(a.number == "2" for a in v.ayats)


def test_ayat_description_length(app):
    """Test bahwa deskripsi Ayat bisa menyimpan hingga 1000 karakter."""
    with app.app_context():
        school = School(name="Test School 4", address="Test Address 4")
        db.session.add(school)
        db.session.flush()
        
        rule = ViolationRule(code="Pasal 4", description="Test", school_id=school.id)
        db.session.add(rule)
        db.session.flush()
        
        # Buat deskripsi panjang (1000 chars)
        long_desc = "a" * 1000
        ayat = Ayat(number="1", description=long_desc, rule_id=rule.id)
        db.session.add(ayat)
        db.session.commit()
        
        # Verify
        saved_ayat = Ayat.query.filter_by(number="1").first()
        assert len(saved_ayat.description) == 1000


def test_ayat_optional_number(app):
    """Test bahwa nomor Ayat bersifat opsional."""
    with app.app_context():
        school = School(name="Test School 5", address="Test Address 5")
        db.session.add(school)
        db.session.flush()
        
        rule = ViolationRule(code="Pasal 5", description="Test", school_id=school.id)
        db.session.add(rule)
        db.session.flush()
        
        # Create ayat tanpa number
        ayat = Ayat(number=None, description="Deskripsi tanpa nomor", rule_id=rule.id)
        db.session.add(ayat)
        db.session.commit()
        
        # Verify
        saved_ayat = Ayat.query.filter_by(description="Deskripsi tanpa nomor").first()
        assert saved_ayat is not None
        assert saved_ayat.number is None