from my_app.models import User, School, ViolationRule, Ayat, Classroom, Student, ViolationCategory, Violation
from my_app.extensions import db
from datetime import datetime
import json

def test_home_page(client):
    """Test halaman home."""
    # Tambahkan follow_redirects=True karena sepertinya redirect ke login
    response = client.get('/', follow_redirects=True)
    assert response.status_code == 200

def test_login_logout(client, app):
    """Test alur login berhasil dan logout."""
    # Setup user (tanpa role)
    u = User(username="guru_login")
    u.set_password("123456")
    db.session.add(u)
    db.session.commit()

    # Test Login
    response = client.post('/login', data={
        'username': 'guru_login',
        'password': '123456'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Cek apakah logout muncul (tandanya sudah login)
    assert b"Logout" in response.data or b"guru_login" in response.data

    # Test Logout
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b"Login" in response.data

def test_login_failed(client):
    """Test login gagal."""
    response = client.post('/login', data={
        'username': 'user_ngawur',
        'password': 'password_salah'
    }, follow_redirects=True)
    
    # Cek apakah form login muncul lagi (input username masih ada)
    # Kita tidak cek pesan error spesifik karena teksnya mungkin beda
    assert b'name="username"' in response.data

def test_protected_page(client):
    """Test akses halaman admin tanpa login."""
    # Gunakan halaman /statistics yang pasti ada (dari nama file statistics.html)
    response = client.get('/statistics', follow_redirects=True)
    
    # Harus diredirect ke halaman login
    # Cek keberadaan form login sebagai tanda kita ditendang ke login
    assert b'name="password"' in response.data


# ===== TESTS UNTUK AYAT ROUTES =====

def test_api_get_ayats_by_rule(client, app):
    """Test API endpoint GET /api/rules/<rule_id>/ayats."""
    with app.app_context():
        # Setup user & school
        school = School(name="Test School API", address="Test Address")
        user = User(username="api_test_user", role="school_admin")
        user.set_password("pass123")
        user.school = school
        db.session.add_all([school, user])
        db.session.flush()
        
        # Create rule with ayats
        rule = ViolationRule(code="Pasal X", description="Test Rule", school_id=school.id)
        db.session.add(rule)
        db.session.flush()
        
        ayat1 = Ayat(number="1", description="Ayat Pertama", rule_id=rule.id)
        ayat2 = Ayat(number="2", description="Ayat Kedua", rule_id=rule.id)
        db.session.add_all([ayat1, ayat2])
        db.session.commit()
        
        rule_id = rule.id
    
    # Login
    client.post('/login', data={'username': 'api_test_user', 'password': 'pass123'})
    
    # Test GET /api/rules/<rule_id>/ayats
    response = client.get(f'/api/rules/{rule_id}/ayats')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert len(data) == 2
    assert data[0]['number'] == '1'
    assert data[0]['description'] == 'Ayat Pertama'
    assert data[1]['number'] == '2'
    assert data[1]['description'] == 'Ayat Kedua'


def test_api_get_ayats_empty(client, app):
    """Test API returns empty list saat rule tidak punya ayat."""
    with app.app_context():
        # Setup
        school = School(name="Test School Empty", address="Test Address")
        user = User(username="empty_test_user", role="school_admin")
        user.set_password("pass123")
        user.school = school
        db.session.add_all([school, user])
        db.session.flush()
        
        rule = ViolationRule(code="Pasal Y", description="Empty Rule", school_id=school.id)
        db.session.add(rule)
        db.session.commit()
        
        rule_id = rule.id
    
    # Login
    client.post('/login', data={'username': 'empty_test_user', 'password': 'pass123'})
    
    # Test
    response = client.get(f'/api/rules/{rule_id}/ayats')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert len(data) == 0


def test_settings_add_ayat(client, app):
    """Test POST /settings/ayats untuk menambah ayat."""
    with app.app_context():
        # Setup
        school = School(name="Test School Setttings", address="Test Address")
        user = User(username="settings_user", role="school_admin")
        user.set_password("pass123")
        user.school = school
        db.session.add_all([school, user])
        db.session.flush()
        
        rule = ViolationRule(code="Pasal Z", description="Settings Rule", school_id=school.id)
        db.session.add(rule)
        db.session.commit()
        
        rule_id = rule.id
    
    # Login
    client.post('/login', data={'username': 'settings_user', 'password': 'pass123'})
    
    # Add ayat via POST
    response = client.post('/settings/ayats', data={
        'action': 'add',
        'rule_id': rule_id,
        'number': 'Ayat 1',
        'description': 'Test Ayat Dinamis dengan panjang deskripsi yang cukup untuk testing'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify ayat created
    with app.app_context():
        ayat = Ayat.query.filter_by(rule_id=rule_id, number='Ayat 1').first()
        assert ayat is not None
        assert ayat.description == 'Test Ayat Dinamis dengan panjang deskripsi yang cukup untuk testing'


def test_settings_delete_ayat(client, app):
    """Test POST /settings/ayats untuk menghapus ayat."""
    with app.app_context():
        # Setup
        school = School(name="Test School Delete", address="Test Address")
        user = User(username="delete_user", role="school_admin")
        user.set_password("pass123")
        user.school = school
        db.session.add_all([school, user])
        db.session.flush()
        
        rule = ViolationRule(code="Pasal W", description="Delete Rule", school_id=school.id)
        db.session.add(rule)
        db.session.flush()
        
        ayat = Ayat(number="ToDelete", description="Delete me", rule_id=rule.id)
        db.session.add(ayat)
        db.session.commit()
        
        ayat_id = ayat.id
    
    # Login
    client.post('/login', data={'username': 'delete_user', 'password': 'pass123'})
    
    # Delete ayat
    response = client.post('/settings/ayats', data={
        'action': 'delete',
        'ayat_id': ayat_id
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify deleted
    with app.app_context():
        deleted_ayat = Ayat.query.filter_by(id=ayat_id).first()
        assert deleted_ayat is None


def test_add_violation_with_ayats(client, app):
    """Test membuat violation dengan memilih multiple ayats."""
    with app.app_context():
        # Setup
        school = School(name="Test School Violation", address="Test Address")
        user = User(username="violation_user", role="school_admin")
        user.set_password("pass123")
        user.school = school
        db.session.add_all([school, user])
        db.session.flush()
        
        classroom = Classroom(name="10A", school_id=school.id)
        student = Student(name="Siswa Test", nis="99999", school_id=school.id, classroom_id=classroom.id)
        rule = ViolationRule(code="Pasal V", description="Violation Rule", school_id=school.id)
        category = ViolationCategory(name="Sedang", points=15, school_id=school.id)
        db.session.add_all([classroom, student, rule, category])
        db.session.flush()
        
        ayat1 = Ayat(number="1", description="Bolos", rule_id=rule.id)
        ayat2 = Ayat(number="2", description="Tidak izin", rule_id=rule.id)
        db.session.add_all([ayat1, ayat2])
        db.session.commit()
        
        rule_id = rule.id
        ayat1_id = ayat1.id
        ayat2_id = ayat2.id
    
    # Login
    client.post('/login', data={'username': 'violation_user', 'password': 'pass123'})
    
    # Add violation with ayats
    response = client.post('/add_violation', data={
        'kelas': '10A',
        'nama_murid': 'Siswa Test',
        'deskripsi': 'Siswa bolos tanpa sepengetahuan orang tua',
        'pasal_id': rule_id,
        'ayat_ids': [ayat1_id, ayat2_id],
        'kategori_id': str(category.id),
        'tanggal_kejadian': '25/02/2026',
        'jam_kejadian': '10:00',
        'di_input_oleh': 'Guru BK'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify violation & ayats linked
    with app.app_context():
        violations = Violation.query.filter_by(pasal='Pasal V - Violation Rule').all()
        assert len(violations) > 0
        
        violation = violations[0]
        assert len(violation.ayats) == 2
        assert any(a.number == "1" for a in violation.ayats)
        assert any(a.number == "2" for a in violation.ayats)