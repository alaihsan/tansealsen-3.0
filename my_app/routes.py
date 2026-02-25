import os
import secrets
import json
import zipfile
import io
from datetime import datetime, timedelta
from flask import render_template, url_for, flash, redirect, request, abort, Blueprint, jsonify, current_app, Response, send_file
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from werkzeug.utils import secure_filename
from functools import wraps
import time

from my_app.extensions import db
from my_app.models import User, Student, Violation, Classroom, School, ViolationRule, ViolationCategory, ViolationPhoto, Ayat
from my_app.utils import compress_image
from flask_login import login_user, current_user, logout_user, login_required

main = Blueprint('main', __name__)

# --- DECORATOR KHUSUS ---

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'super_admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def school_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.school_id:
            flash("Anda harus login sebagai Admin Sekolah untuk mengakses halaman ini.", "warning")
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

# --- SUPER ADMIN ROUTES ---

@main.route("/super-admin")
@super_admin_required
def super_dashboard():
    schools = School.query.all()
    total_users = User.query.count()
    return render_template('super_admin/dashboard.html', schools=schools, total_users=total_users)

@main.route("/super-admin/create-school", methods=['GET', 'POST'])
@super_admin_required
def create_school():
    if request.method == 'POST':
        school_name = request.form.get('school_name')
        address = request.form.get('address')
        admin_username = request.form.get('admin_username')
        admin_password = request.form.get('admin_password')
        if School.query.filter_by(name=school_name).first():
            flash('Nama sekolah sudah terdaftar.', 'danger')
            return redirect(url_for('main.create_school'))
        if User.query.filter_by(username=admin_username).first():
            flash('Username admin sudah digunakan.', 'danger')
            return redirect(url_for('main.create_school'))
        new_school = School(name=school_name, address=address)
        db.session.add(new_school)
        db.session.flush()
        new_user = User(username=admin_username, role='school_admin', school_id=new_school.id, full_name="Administrator")
        new_user.set_password(admin_password)
        db.session.add(new_user)
        default_categories = [('Ringan', 5), ('Sedang', 15), ('Berat', 30)]
        for c_name, c_point in default_categories:
            db.session.add(ViolationCategory(name=c_name, points=c_point, school_id=new_school.id))
        default_rules = [('Pasal 1', 'Ketertiban Umum'), ('Pasal 2', 'Kerapihan Seragam')]
        for r_code, r_desc in default_rules:
            db.session.add(ViolationRule(code=r_code, description=r_desc, school_id=new_school.id))
        db.session.commit()
        flash(f'Sekolah "{school_name}" berhasil dibuat!', 'success')
        return redirect(url_for('main.super_dashboard'))
    return render_template('super_admin/create_school.html')

# --- AUTH ROUTES ---

@main.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'super_admin':
            return redirect(url_for('main.super_dashboard'))
        return redirect(url_for('main.home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):          
            login_user(user)
            if user.role == 'super_admin':
                return redirect(url_for('main.super_dashboard'))
            else:
                return redirect(url_for('main.home'))
        else:
            flash('Login Gagal. Cek username dan password', 'danger')
    return render_template('login.html')

@main.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/favicon.ico')
def favicon():
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
    static_folder = os.path.join(current_app.root_path, 'static')
    if current_user.is_authenticated and current_user.school and current_user.school.logo:
        logo_path = os.path.join(upload_folder, current_user.school.logo)
        if os.path.exists(logo_path):
            return send_from_directory(upload_folder, current_user.school.logo, mimetype='image/vnd.microsoft.icon')
    return send_from_directory(static_folder, 'favicon.svg', mimetype='image/svg+xml')

# --- MAIN ROUTES ---

@main.route("/")
@main.route("/home")
@main.route("/index")
@school_admin_required
def home():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    date_range = request.args.get('date_range', '')
    query = Violation.query.join(Student).filter(Student.school_id == current_user.school_id)
    if search: query = query.filter(Student.name.contains(search))
    if category: query = query.filter(Violation.kategori_pelanggaran == category)
    if date_range:
        today = datetime.utcnow()
        if date_range == 'today': query = query.filter(Violation.date_posted >= today.replace(hour=0, minute=0, second=0))
        elif date_range == 'week': query = query.filter(Violation.date_posted >= today - timedelta(days=7))
        elif date_range == 'month': query = query.filter(Violation.date_posted >= today - timedelta(days=30))
    pelanggaran_pagination = query.options(joinedload(Violation.photos)).order_by(Violation.date_posted.desc()).paginate(page=page, per_page=10, error_out=False)
    total_students = Student.query.filter_by(school_id=current_user.school_id).count()
    total_violations = Violation.query.join(Student).filter(Student.school_id == current_user.school_id).count()
    total_classes = Classroom.query.filter_by(school_id=current_user.school_id).count()
    categories = ViolationCategory.query.filter_by(school_id=current_user.school_id).all()
    return render_template('index.html', 
                           total_students=total_students, total_violations=total_violations, total_classes=total_classes,
                           pelanggaran_pagination=pelanggaran_pagination, search_query=search, category_filter=category,
                           date_range_value=date_range, categories=categories)

@main.route("/classes", methods=['GET', 'POST'])
@school_admin_required
def manage_classes():
    if request.method == 'POST':
        class_name = request.form.get('class_name')
        if class_name:
            existing_class = Classroom.query.filter_by(name=class_name, school_id=current_user.school_id).first()
            if not existing_class:
                new_class = Classroom(name=class_name, school_id=current_user.school_id)
                db.session.add(new_class)
                db.session.commit()
                flash(f'Kelas {class_name} berhasil dibuat!', 'success')
            else:
                flash(f'Kelas {class_name} sudah ada.', 'warning')
        return redirect(url_for('main.manage_classes'))
    classes = Classroom.query.filter_by(school_id=current_user.school_id).order_by(Classroom.name).all()
    return render_template('manajemenkelas.html', classes=classes)

@main.route("/classes/delete/<int:class_id>", methods=['POST'])
@school_admin_required
def delete_class(class_id):
    classroom = Classroom.query.filter_by(id=class_id, school_id=current_user.school_id).first_or_404()
    if classroom.students:
        flash('Tidak bisa menghapus kelas yang masih memiliki murid.', 'danger')
    else:
        db.session.delete(classroom)
        db.session.commit()
        flash('Kelas berhasil dihapus.', 'success')
    return redirect(url_for('main.manage_classes'))

@main.route("/classes/<int:class_id>", methods=['GET', 'POST'])
@school_admin_required
def view_class(class_id):
    classroom = Classroom.query.filter_by(id=class_id, school_id=current_user.school_id).first_or_404()
    all_classes = Classroom.query.filter(Classroom.id != class_id, Classroom.school_id == current_user.school_id).order_by(Classroom.name).all()
    if request.method == 'POST' and 'import_students' in request.form:
        raw_names = request.form.get('student_names')
        if raw_names:
            names_list = raw_names.strip().split('\n')
            count = 0
            for name in names_list:
                clean_name = name.strip()
                if clean_name:
                    dummy_nis = secrets.token_hex(4) 
                    student = Student(name=clean_name, nis=dummy_nis, classroom=classroom, school_id=current_user.school_id)
                    db.session.add(student)
                    count += 1
            db.session.commit()
            flash(f'Berhasil mengimpor {count} murid.', 'success')
            return redirect(url_for('main.view_class', class_id=class_id))
    if request.method == 'POST' and 'mutate_students' in request.form:
        target_class_id = request.form.get('target_class_id')
        selected_student_ids = request.form.getlist('selected_students')
        if target_class_id and selected_student_ids:
            target_class = Classroom.query.filter_by(id=target_class_id, school_id=current_user.school_id).first()
            if target_class:
                for stud_id in selected_student_ids:
                    student = Student.query.filter_by(id=stud_id, school_id=current_user.school_id).first()
                    if student:
                        student.classroom = target_class
                db.session.commit()
                flash('Mutasi berhasil.', 'success')
            else:
                flash('Kelas tujuan tidak valid.', 'danger')
        return redirect(url_for('main.view_class', class_id=class_id))
    return render_template('detailkelas.html', classroom=classroom, all_classes=all_classes)

@main.route("/api/students/<class_name>")
@school_admin_required
def get_students_by_class(class_name):
    classroom = Classroom.query.filter_by(name=class_name, school_id=current_user.school_id).first()
    if classroom:
        students = [student.name for student in classroom.students]
        students.sort()
        return jsonify(students)
    else:
        return jsonify([])


@main.route("/api/rules/<int:rule_id>/ayats")
@school_admin_required
def get_ayats_by_rule(rule_id):
    ayats = Ayat.query.filter_by(rule_id=rule_id).all()
    result = []
    for a in ayats:
        result.append({
            'id': a.id,
            'number': a.number,
            'description': a.description
        })
    return jsonify(result)

@main.route("/student/delete/<int:student_id>", methods=['POST'])
@school_admin_required
def delete_student(student_id):
    student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first_or_404()
    if student.violations:
        flash(f'Gagal menghapus siswa {student.name}. Siswa ini memiliki data pelanggaran.', 'danger')
        return redirect(url_for('main.view_class', class_id=student.classroom_id))
    try:
        db.session.delete(student)
        db.session.commit()
        flash(f'Siswa {student.name} berhasil dihapus.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Terjadi kesalahan: {str(e)}', 'danger')
    return redirect(url_for('main.view_class', class_id=student.classroom_id))

@main.route("/add_violation", methods=['GET', 'POST'])
@school_admin_required
def add_violation():
    classes = Classroom.query.filter_by(school_id=current_user.school_id).order_by(Classroom.name).all()
    rules = ViolationRule.query.filter_by(school_id=current_user.school_id).all()
    categories = ViolationCategory.query.filter_by(school_id=current_user.school_id).all()
    staff_members = User.query.filter_by(school_id=current_user.school_id).all()
    if request.method == 'POST':
        class_name = request.form.get('kelas')
        student_name = request.form.get('nama_murid')
        description = request.form.get('deskripsi')
        pasal_id = request.form.get('pasal_id')
        ayat_ids = request.form.getlist('ayat_ids')
        kategori_id = request.form.get('kategori_id')
        tanggal_str = request.form.get('tanggal_kejadian')
        jam_str = request.form.get('jam_kejadian')
        di_input_oleh = request.form.get('di_input_oleh')
        selected_category = ViolationCategory.query.get(kategori_id)
        points = selected_category.points if selected_category else 0
        kategori_name = selected_category.name if selected_category else "Umum"
        classroom = Classroom.query.filter_by(name=class_name, school_id=current_user.school_id).first()
        student = None
        if classroom:
            student = Student.query.filter_by(name=student_name, classroom_id=classroom.id, school_id=current_user.school_id).first()
        if student:
            try:
                date_obj = datetime.strptime(tanggal_str, '%d/%m/%Y')
                if jam_str:
                    time_obj = datetime.strptime(jam_str, '%H:%M').time()
                    date_posted = datetime.combine(date_obj.date(), time_obj)
                else:
                    date_posted = date_obj 
            except (ValueError, TypeError):
                date_posted = datetime.utcnow()
            # Determine pasal string from selected rule id (if provided)
            pasal = None
            if pasal_id:
                rule = ViolationRule.query.filter_by(id=pasal_id, school_id=current_user.school_id).first()
                if rule:
                    pasal = f"{rule.code} - {rule.description}"

            violation = Violation(
                description=description,
                points=points,
                date_posted=date_posted,
                student_id=student.id,
                pasal=pasal,
                kategori_pelanggaran=kategori_name,
                di_input_oleh=di_input_oleh
            )
            db.session.add(violation)
            db.session.flush()
            # Associate selected ayats (if any)
            if ayat_ids:
                try:
                    ayat_int_ids = [int(a) for a in ayat_ids if a]
                    ayat_objs = Ayat.query.filter(Ayat.id.in_(ayat_int_ids), Ayat.rule_id == pasal_id).all()
                    if ayat_objs:
                        violation.ayats = ayat_objs
                except ValueError:
                    pass
            files = request.files.getlist('bukti_file')
            valid_files = [f for f in files if f.filename != '']
            for file in valid_files[:10]: 
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
                if not os.path.exists(upload_folder): os.makedirs(upload_folder)
                fname = secure_filename(file.filename)
                timestamp = str(int(time.time()))
                unique_suffix = secrets.token_hex(2)
                name_without_ext = os.path.splitext(fname)[0]
                filename = f"{timestamp}_{unique_suffix}_{name_without_ext}.jpg"
                save_path = os.path.join(upload_folder, filename)
                success = compress_image(file, save_path)
                if success:
                    photo = ViolationPhoto(filename=filename, violation_id=violation.id)
                    db.session.add(photo)
            db.session.commit()
            flash('Pelanggaran berhasil dicatat!', 'success')
            return redirect(url_for('main.home'))
        else:
            flash(f'Siswa tidak ditemukan.', 'danger')
    return render_template('add_violation.html', classes=classes, rules=rules, categories=categories, staff_members=staff_members)

@main.route("/student/<int:student_id>")
@school_admin_required
def student_history(student_id):
    student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first_or_404()
    total_points = sum(v.points for v in student.violations if not v.is_remitted)
    return render_template('student_history.html', student=student, total_points=total_points)

@main.route("/violation/delete/<int:violation_id>", methods=['POST'])
@school_admin_required
def delete_violation(violation_id):
    violation = Violation.query.join(Student).filter(
        Violation.id == violation_id,
        Student.school_id == current_user.school_id
    ).first_or_404()
    student_id = violation.student_id
    db.session.delete(violation)
    db.session.commit()
    flash('Data pelanggaran telah dihapus permanen.', 'success')
    return redirect(url_for('main.student_history', student_id=student_id))

@main.route("/violation/remit/<int:violation_id>", methods=['POST'])
@school_admin_required
def remit_violation(violation_id):
    violation = Violation.query.join(Student).filter(
        Violation.id == violation_id,
        Student.school_id == current_user.school_id
    ).first_or_404()
    reason = request.form.get('remission_reason')
    if not reason:
        flash('Keterangan remisi wajib diisi.', 'warning')
        return redirect(url_for('main.student_history', student_id=violation.student_id))
    violation.is_remitted = True
    violation.remission_reason = reason
    violation.remission_date = datetime.utcnow()
    db.session.commit()
    flash('Remisi berhasil.', 'success')
    return redirect(url_for('main.student_history', student_id=violation.student_id))

@main.route("/statistics")
@school_admin_required
def statistics():
    base_query = Violation.query.join(Student).filter(Student.school_id == current_user.school_id)
    category_stats = db.session.query(
        Violation.kategori_pelanggaran, func.count(Violation.id)
    ).join(Student).filter(Student.school_id == current_user.school_id).group_by(Violation.kategori_pelanggaran).all()
    pie_labels = [stat[0] for stat in category_stats]
    pie_data = [stat[1] for stat in category_stats]
    if not pie_data:
        pie_labels = ["Belum ada data"]
        pie_data = [0]
    today = datetime.utcnow().replace(hour=0, minute=0, second=0)
    tomorrow = today + timedelta(days=1)
    top_today = db.session.query(
        Student,
        func.count(Violation.id).label('count'),
        func.sum(Violation.points).label('total_points')
    ).join(Violation).filter(
        Student.school_id == current_user.school_id,
        Violation.date_posted >= today,
        Violation.date_posted < tomorrow
    ).group_by(Student.id).order_by(func.sum(Violation.points).desc()).limit(5).all()
    trend_range = request.args.get('trend_range', '7d')
    end_date = datetime.utcnow()
    days_map = {'30d': 30, '90d': 90, '180d': 180}
    start_date = end_date - timedelta(days=days_map.get(trend_range, 7))
    daily_stats = db.session.query(
        func.date(Violation.date_posted).label('date'),
        func.count(Violation.id).label('count')
    ).join(Student).filter(
        Student.school_id == current_user.school_id,
        Violation.date_posted >= start_date
    ).group_by(func.date(Violation.date_posted)).all()
    stats_dict = {str(stat.date): stat.count for stat in daily_stats}
    trend_labels = []
    trend_data = []
    current = start_date
    while current <= end_date:
        d_str = current.strftime('%Y-%m-%d')
        l_str = current.strftime('%d %b')
        trend_labels.append(l_str)
        trend_data.append(stats_dict.get(d_str, 0))
        current += timedelta(days=1)
    return render_template('statistics.html',
        pie_data=pie_data, pie_labels=pie_labels,
        top_today=top_today, trend_labels=trend_labels, trend_data=trend_data,
        current_range=trend_range, total_violations_today=sum(item.count for item in top_today) if top_today else 0
    )

# --- SETTINGS ROUTES ---

@main.route("/settings")
@school_admin_required
def settings():
    school = current_user.school
    members = User.query.filter_by(school_id=school.id).all()
    rules = ViolationRule.query.filter_by(school_id=school.id).all()
    categories = ViolationCategory.query.filter_by(school_id=school.id).all()
    return render_template('settings.html', school=school, members=members, rules=rules, categories=categories)

@main.route("/settings/update_school", methods=['POST'])
@school_admin_required
def settings_update_school():
    name = request.form.get('name')
    address = request.form.get('address')
    school = current_user.school
    if name: school.name = name
    if address: school.address = address
    if 'logo' in request.files:
        file = request.files['logo']
        if file and file.filename:
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
            if not os.path.exists(upload_folder): os.makedirs(upload_folder)
            fname = secure_filename(file.filename)
            timestamp = str(int(time.time()))
            filename = f"logo_{school.id}_{timestamp}_{fname}"
            file.save(os.path.join(upload_folder, filename))
            school.logo = filename
    db.session.commit()
    flash('Profil sekolah berhasil diperbarui.', 'success')
    return redirect(url_for('main.settings'))

@main.route("/settings/add_member", methods=['POST'])
@school_admin_required
def settings_add_member():
    username = request.form.get('username')
    password = request.form.get('password')
    full_name = request.form.get('full_name')
    if User.query.filter_by(username=username).first():
        flash('Username sudah digunakan.', 'danger')
        return redirect(url_for('main.settings'))
    new_user = User(username=username, full_name=full_name, role='school_admin', school_id=current_user.school_id)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    flash('Anggota berhasil ditambahkan.', 'success')
    return redirect(url_for('main.settings'))

@main.route("/settings/edit_member", methods=['POST'])
@school_admin_required
def settings_edit_member():
    user_id = request.form.get('user_id')
    password = request.form.get('password')
    username = request.form.get('username')
    user = User.query.filter_by(id=user_id, school_id=current_user.school_id).first()
    if user:
        if username and username != user.username:
            if User.query.filter_by(username=username).first():
                flash('Username sudah terpakai.', 'danger')
                return redirect(url_for('main.settings'))
            user.username = username
        if password:
            user.set_password(password)
            flash(f'Password untuk {user.username} berhasil direset.', 'success')
        db.session.commit()
    return redirect(url_for('main.settings'))

@main.route("/settings/delete_member/<int:user_id>", methods=['POST'])
@school_admin_required
def settings_delete_member(user_id):
    if user_id == current_user.id:
        flash('Anda tidak bisa menghapus akun sendiri.', 'warning')
        return redirect(url_for('main.settings'))
    user = User.query.filter_by(id=user_id, school_id=current_user.school_id).first()
    if user:
        db.session.delete(user)
        db.session.commit()
        flash('Anggota berhasil dihapus.', 'success')
    return redirect(url_for('main.settings'))

@main.route("/settings/rules", methods=['POST'])
@school_admin_required
def settings_rules():
    action = request.form.get('action')
    if action == 'add':
        code = request.form.get('code')
        desc = request.form.get('description')
        rule = ViolationRule(code=code, description=desc, school_id=current_user.school_id)
        db.session.add(rule)
    elif action == 'delete':
        rule_id = request.form.get('rule_id')
        rule = ViolationRule.query.filter_by(id=rule_id, school_id=current_user.school_id).first()
        if rule: db.session.delete(rule)
    db.session.commit()
    return redirect(url_for('main.settings'))


@main.route("/settings/ayats", methods=['POST'])
@school_admin_required
def settings_ayats():
    action = request.form.get('action')
    if action == 'add':
        rule_id = request.form.get('rule_id')
        number = request.form.get('number')
        description = request.form.get('description')
        if rule_id and description:
            rule = ViolationRule.query.filter_by(id=rule_id, school_id=current_user.school_id).first()
            if rule:
                db.session.add(Ayat(number=number, description=description, rule_id=rule.id))
    elif action == 'delete':
        ayat_id = request.form.get('ayat_id')
        ayat = Ayat.query.join(ViolationRule).filter(Ayat.id==ayat_id, ViolationRule.school_id==current_user.school_id).first()
        if ayat:
            db.session.delete(ayat)
    db.session.commit()
    # Redirect back to settings but stay on the "aturan" (Pasal) tab
    return redirect(url_for('main.settings', _anchor='tab-aturan'))

@main.route("/settings/categories", methods=['POST'])
@school_admin_required
def settings_categories():
    action = request.form.get('action')
    if action == 'add':
        name = request.form.get('name')
        points = request.form.get('points')
        cat = ViolationCategory(name=name, points=points, school_id=current_user.school_id)
        db.session.add(cat)
    elif action == 'delete':
        cat_id = request.form.get('cat_id')
        cat = ViolationCategory.query.filter_by(id=cat_id, school_id=current_user.school_id).first()
        if cat: db.session.delete(cat)
    db.session.commit()
    return redirect(url_for('main.settings'))

# --- PRINT ROUTES ---

@main.route("/violation/print/<int:violation_id>")
@school_admin_required
def print_violation(violation_id):
    violation = Violation.query.join(Student).filter(
        Violation.id == violation_id,
        Student.school_id == current_user.school_id
    ).first_or_404()
    
    return render_template('print_violation.html', 
                         violation=violation, 
                         student=violation.student, 
                         school=current_user.school)

@main.route("/class/print/<int:class_id>")
@school_admin_required
def print_class_report(class_id):
    classroom = Classroom.query.filter_by(id=class_id, school_id=current_user.school_id).first_or_404()
    
    violations = Violation.query.join(Student).filter(
        Student.classroom_id == class_id,
        Student.school_id == current_user.school_id
    ).order_by(Violation.date_posted.desc()).all()
    
    return render_template('print_class_report.html', 
                         classroom=classroom, 
                         violations=violations, 
                         school=current_user.school)

# --- BACKUP & RESTORE ROUTE (ZIP Format) ---

@main.route("/settings/backup")
@school_admin_required
def backup_data():
    school = current_user.school
    
    # 1. Kumpulkan Data (JSON)
    # a. Data Siswa & Pelanggaran
    students_data = []
    students = Student.query.filter_by(school_id=school.id).all()
    
    for s in students:
        violations_data = []
        for v in s.violations:
            photos_data = []
            for p in v.photos:
                photos_data.append(p.filename)
                
            violations_data.append({
                "date": v.date_posted.isoformat(),
                "description": v.description,
                "points": v.points,
                "pasal": v.pasal,
                "kategori": v.kategori_pelanggaran,
                "reporter": v.di_input_oleh,
                "is_remitted": v.is_remitted,
                "remission_reason": v.remission_reason,
                "ayats": [{"number": a.number, "description": a.description} for a in v.ayats],
                "photos": photos_data
            })
            
        students_data.append({
            "name": s.name,
            "nis": s.nis,
            "classroom": s.classroom.name if s.classroom else None,
            "violations": violations_data
        })

    # b. Data Settings (Anggota, Pasal, Kategori)
    members_data = [{"username": u.username, "full_name": u.full_name} for u in school.users if u.role != 'super_admin']
    # Include ayats for each rule
    rules_data = []
    for r in school.rules:
        rule_entry = {"code": r.code, "description": r.description, "ayats": []}
        for a in r.ayats:
            rule_entry["ayats"].append({"number": a.number, "description": a.description})
        rules_data.append(rule_entry)
    categories_data = [{"name": c.name, "points": c.points} for c in school.categories]
    classrooms_data = [{"name": c.name} for c in school.classrooms]

    backup_json = {
        "school": {
            "name": school.name,
            "address": school.address,
            "logo": school.logo
        },
        "backup_date": datetime.now().isoformat(),
        "settings": {
            "members": members_data,
            "rules": rules_data,
            "categories": categories_data,
            "classrooms": classrooms_data
        },
        "students": students_data
    }
    
    # 2. Buat ZIP File
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # a. Tulis data.json
        zf.writestr('data.json', json.dumps(backup_json, indent=4))
        
        # b. Tulis Foto-foto Bukti
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        
        # Helper to write file if exists
        def add_file_to_zip(filename):
            if not filename: return
            file_path = os.path.join(upload_folder, filename)
            if os.path.exists(file_path):
                zf.write(file_path, arcname=filename) 
        
        # Foto Pelanggaran
        for s in students_data:
            for v in s['violations']:
                for p_name in v['photos']:
                    add_file_to_zip(p_name)
        
        # Logo Sekolah
        add_file_to_zip(school.logo)

    memory_file.seek(0)
    
    # Format Nama File: Backup_NamaSekolah_Tanggal_Waktu_DataPelanggaran.zip
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    clean_school_name = "".join(c for c in school.name if c.isalnum() or c in (' ', '_')).replace(' ', '_')
    filename = f"Backup_{clean_school_name}_{date_str}_DataPelanggaran.zip"
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename
    )

@main.route("/settings/restore", methods=['POST'])
@school_admin_required
def restore_data():
    if 'backup_file' not in request.files:
        flash('Tidak ada file yang diunggah.', 'danger')
        return redirect(url_for('main.settings'))
        
    file = request.files['backup_file']
    
    if file.filename == '':
        flash('Tidak ada file yang dipilih.', 'danger')
        return redirect(url_for('main.settings'))

    if file and file.filename.endswith('.zip'):
        try:
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
            if not os.path.exists(upload_folder): os.makedirs(upload_folder)

            with zipfile.ZipFile(file) as zf:
                # 1. Baca data.json
                if 'data.json' not in zf.namelist():
                    flash('Format backup tidak valid (data.json hilang).', 'danger')
                    return redirect(url_for('main.settings'))
                
                json_data = zf.read('data.json')
                data = json.loads(json_data)
                
                school = current_user.school
                
                # 2. Restore Settings
                if 'school' in data:
                    school.name = data['school'].get('name', school.name)
                    school.address = data['school'].get('address', school.address)
                    logo_name = data['school'].get('logo')
                    if logo_name:
                        school.logo = logo_name
                        # Extract logo file if in zip
                        if logo_name in zf.namelist():
                            with open(os.path.join(upload_folder, logo_name), 'wb') as f:
                                f.write(zf.read(logo_name))

                # Restore Rules (with ayats)
                for r_data in data.get('settings', {}).get('rules', []):
                    rule = ViolationRule.query.filter_by(code=r_data['code'], school_id=school.id).first()
                    if not rule:
                        rule = ViolationRule(code=r_data['code'], description=r_data['description'], school_id=school.id)
                        db.session.add(rule)
                        db.session.flush()
                    # Restore ayats for this rule
                    for a_data in r_data.get('ayats', []):
                        if not Ayat.query.filter_by(rule_id=rule.id, description=a_data['description'], number=a_data.get('number')).first():
                            db.session.add(Ayat(number=a_data.get('number'), description=a_data['description'], rule_id=rule.id))
                
                # Restore Categories
                for c_data in data.get('settings', {}).get('categories', []):
                    if not ViolationCategory.query.filter_by(name=c_data['name'], school_id=school.id).first():
                        db.session.add(ViolationCategory(name=c_data['name'], points=c_data['points'], school_id=school.id))
                
                # Restore Classrooms
                for c_data in data.get('settings', {}).get('classrooms', []):
                    if not Classroom.query.filter_by(name=c_data['name'], school_id=school.id).first():
                        db.session.add(Classroom(name=c_data['name'], school_id=school.id))
                
                # Restore Members (Users) - Password will need reset or default
                for m_data in data.get('settings', {}).get('members', []):
                    if not User.query.filter_by(username=m_data['username']).first():
                        new_user = User(username=m_data['username'], full_name=m_data['full_name'], role='school_admin', school_id=school.id)
                        new_user.set_password('guru123') # Default password for restored users
                        db.session.add(new_user)

                db.session.flush()

                # 3. Restore Siswa & Pelanggaran
                count_students = 0
                count_violations = 0
                
                for s_data in data.get('students', []):
                    # Cari Classroom ID
                    classroom = None
                    if s_data.get('classroom'):
                        classroom = Classroom.query.filter_by(name=s_data['classroom'], school_id=school.id).first()
                    
                    # Cari atau Buat Siswa
                    student = Student.query.filter_by(nis=s_data['nis'], school_id=school.id).first()
                    if not student:
                        student = Student(
                            name=s_data['name'],
                            nis=s_data['nis'],
                            school_id=school.id,
                            classroom_id=classroom.id if classroom else None
                        )
                        db.session.add(student)
                        db.session.flush()
                        count_students += 1
                    
                    # Restore Violations
                    for v_data in s_data.get('violations', []):
                        try: v_date = datetime.fromisoformat(v_data['date'])
                        except ValueError: v_date = datetime.utcnow()

                        # Cek duplikat
                        existing = Violation.query.filter_by(
                            student_id=student.id,
                            date_posted=v_date,
                            description=v_data['description']
                        ).first()
                        
                        if not existing:
                            violation = Violation(
                                student_id=student.id,
                                date_posted=v_date,
                                description=v_data['description'],
                                points=v_data['points'],
                                pasal=v_data['pasal'],
                                kategori_pelanggaran=v_data['kategori'],
                                di_input_oleh=v_data['reporter'],
                                is_remitted=v_data.get('is_remitted', False),
                                remission_reason=v_data.get('remission_reason')
                            )
                            db.session.add(violation)
                            db.session.flush()
                            count_violations += 1
                            
                            # Link ayats back to violation (by matching description)
                            for a_data in v_data.get('ayats', []):
                                ayat = Ayat.query.filter_by(description=a_data['description'], number=a_data.get('number')).first()
                                if ayat:
                                    violation.ayats.append(ayat)
                            # Restore Photos
                            for p_name in v_data.get('photos', []):
                                # Extract file
                                if p_name in zf.namelist():
                                    with open(os.path.join(upload_folder, p_name), 'wb') as f:
                                        f.write(zf.read(p_name))
                                
                                # DB Record
                                if not ViolationPhoto.query.filter_by(violation_id=violation.id, filename=p_name).first():
                                    db.session.add(ViolationPhoto(filename=p_name, violation_id=violation.id))

            db.session.commit()
            flash(f'Restore Berhasil! {count_students} siswa dan {count_violations} pelanggaran dipulihkan.', 'success')
            
        except zipfile.BadZipFile:
            flash('File ZIP rusak atau tidak valid.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Terjadi kesalahan: {str(e)}', 'danger')
            
    else:
        flash('Format file harus .zip', 'danger')
        
    return redirect(url_for('main.settings'))