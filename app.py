from flask import Flask, render_template, request, redirect, url_for, flash, make_response, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, date
from sqlalchemy import func
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pg_management.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'supersecretkey'
db = SQLAlchemy(app)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(10), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    students = db.relationship('Student', backref='room', lazy=True)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    rent_status = db.Column(db.String(20), nullable=False)
    mode_of_payment = db.Column(db.String(20), nullable=False)
    monthly_rent = db.Column(db.Integer, nullable=False)
    security_deposit = db.Column(db.Integer, nullable=False)
    join_date = db.Column(db.Date, nullable=False)
    left_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class RentPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # Format: YYYY-MM
    paid = db.Column(db.Boolean, default=False)
    paid_date = db.Column(db.Date, nullable=True)
    student = db.relationship('Student', backref='rent_payments')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

@app.context_processor
def inject_user():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        return {'current_user': user}
    return {'current_user': None}

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next') or url_for('home')
            return redirect(next_page)
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))
            
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))
            
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
            
        user = User(username=username, email=email, is_admin=False)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/rooms')
@login_required
def list_rooms():
    rooms = Room.query.all()
    return render_template('rooms.html', rooms=rooms)

@app.route('/rooms/add', methods=['GET', 'POST'])
@login_required
def add_room():
    if request.method == 'POST':
        number = request.form['number']
        capacity = request.form['capacity']
        if Room.query.filter_by(number=number).first():
            flash('Room number already exists!')
            return redirect(url_for('add_room'))
        room = Room(number=number, capacity=capacity)
        db.session.add(room)
        db.session.commit()
        flash('Room added successfully!')
        return redirect(url_for('list_rooms'))
    return render_template('add_room.html')

@app.route('/rooms/edit/<int:room_id>', methods=['GET', 'POST'])
@login_required
def edit_room(room_id):
    room = Room.query.get_or_404(room_id)
    if request.method == 'POST':
        room.number = request.form['number']
        room.capacity = request.form['capacity']
        db.session.commit()
        flash('Room updated successfully!')
        return redirect(url_for('list_rooms'))
    return render_template('edit_room.html', room=room)

@app.route('/rooms/delete/<int:room_id>', methods=['POST'])
@login_required
def delete_room(room_id):
    room = Room.query.get_or_404(room_id)
    if room.students:
        flash('Cannot delete a room with students assigned!')
        return redirect(url_for('list_rooms'))
    db.session.delete(room)
    db.session.commit()
    flash('Room deleted successfully!')
    return redirect(url_for('list_rooms'))

@app.route('/rooms/vacant')
@login_required
def vacant_rooms():
    rooms = Room.query.all()
    vacant = []
    for room in rooms:
        active_students = Student.query.filter_by(room_id=room.id, is_active=True).count()
        if active_students < room.capacity:
            vacant.append({'room': room, 'vacant': room.capacity - active_students})
    return render_template('vacant_rooms.html', vacant_rooms=vacant)

@app.route('/students')
def list_students():
    students = Student.query.all()
    return render_template('students.html', students=students)

@app.route('/export/students/pdf')
def export_students_pdf():
    # Get current and left students
    current_students = Student.query.filter_by(is_active=True).all()
    left_students = Student.query.filter_by(is_active=False).all()
    
    # Create a file-like buffer to receive PDF data
    buffer = BytesIO()
    
    # Create the PDF object, using the buffer as its "file."
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Add title
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=20,
        alignment=1  # Center alignment
    )
    elements.append(Paragraph("Student Records - PG Management System", title_style))
    
    # Add current students section
    elements.append(Paragraph("Current Students", styles['Heading2']))
    if current_students:
        # Create table data
        data = [
            ["ID", "Name", "Phone", "Room", "Rent Status", "Join Date"]
        ]
        for student in current_students:
            data.append([
                str(student.id),
                student.name,
                student.phone,
                student.room.number if student.room else 'N/A',
                student.rent_status,
                student.join_date.strftime('%Y-%m-%d')
            ])
        
        # Create table
        table = Table(data, colWidths=[0.5*inch, 1.5*inch, 1.2*inch, 0.8*inch, 1.2*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No current students found.", styles['Normal']))
    
    # Add some space between sections
    elements.append(Spacer(1, 0.5*inch))
    
    # Add left students section
    elements.append(Paragraph("Former Students", styles['Heading2']))
    if left_students:
        # Create table data
        data = [
            ["ID", "Name", "Phone", "Room", "Join Date", "Left Date"]
        ]
        for student in left_students:
            data.append([
                str(student.id),
                student.name,
                student.phone,
                student.room.number if student.room else 'N/A',
                student.join_date.strftime('%Y-%m-%d'),
                student.left_date.strftime('%Y-%m-%d') if student.left_date else 'N/A'
            ])
        
        # Create table
        table = Table(data, colWidths=[0.5*inch, 1.5*inch, 1.2*inch, 0.8*inch, 1.2*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No former students found.", styles['Normal']))
    
    # Add generation date
    elements.append(Spacer(1, 0.25*inch))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                            styles['Italic']))
    
    # Build the PDF
    doc.build(elements)
    
    # File response
    buffer.seek(0)
    response = make_response(buffer.getvalue())
    response.mimetype = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=student_records_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return response

@app.route('/students/add', methods=['GET', 'POST'])
def add_student():
    # Only show rooms with available capacity
    rooms = []
    for room in Room.query.all():
        active_students = Student.query.filter_by(room_id=room.id, is_active=True).count()
        if active_students < room.capacity:
            rooms.append(room)
    if request.method == 'POST':
        room_id = int(request.form['room_id'])
        active_students = Student.query.filter_by(room_id=room_id, is_active=True).count()
        room = Room.query.get(room_id)
        if active_students >= room.capacity:
            flash('Selected room is already full!')
            return redirect(url_for('add_student'))
        name = request.form['name']
        phone = request.form['phone']
        rent_status = request.form['rent_status']
        mode_of_payment = request.form['mode_of_payment']
        monthly_rent = request.form['monthly_rent']
        security_deposit = request.form['security_deposit']
        join_date = request.form['join_date']
        student = Student(
            name=name,
            phone=phone,
            room_id=room_id,
            rent_status=rent_status,
            mode_of_payment=mode_of_payment,
            monthly_rent=monthly_rent,
            security_deposit=security_deposit,
            join_date=datetime.strptime(join_date, '%Y-%m-%d'),
            is_active=True
        )
        db.session.add(student)
        db.session.commit()
        flash('Student added successfully!')
        return redirect(url_for('list_students'))
    return render_template('add_student.html', rooms=rooms)

@app.route('/students/edit/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    rooms = Room.query.all()
    if request.method == 'POST':
        student.name = request.form['name']
        student.phone = request.form['phone']
        student.room_id = request.form['room_id']
        student.rent_status = request.form['rent_status']
        student.mode_of_payment = request.form['mode_of_payment']
        student.monthly_rent = request.form['monthly_rent']
        student.security_deposit = request.form['security_deposit']
        student.join_date = datetime.strptime(request.form['join_date'], '%Y-%m-%d')
        left_date = request.form.get('left_date')
        if left_date:
            student.left_date = datetime.strptime(left_date, '%Y-%m-%d')
        else:
            student.left_date = None
        student.is_active = request.form.get('is_active') == 'on'
        db.session.commit()
        flash('Student updated successfully!')
        return redirect(url_for('list_students'))
    return render_template('edit_student.html', student=student, rooms=rooms)

@app.route('/students/delete/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    student.is_active = False
    student.left_date = datetime.now().date()
    db.session.commit()
    flash('Student marked as left (historical data saved).')
    return redirect(url_for('list_students'))

@app.route('/rent', methods=['GET', 'POST'])
@login_required
def rent_management():
    today = date.today()
    current_month = today.strftime('%Y-%m')
    students = Student.query.filter_by(is_active=True).all()
    rent_data = []
    for student in students:
        # Find rent payment for this month
        payment = RentPayment.query.filter_by(student_id=student.id, month=current_month).first()
        if not payment:
            # If not present, create unpaid record
            payment = RentPayment(student_id=student.id, month=current_month, paid=False)
            db.session.add(payment)
            db.session.commit()
        days_overdue = 0
        if not payment.paid:
            # Calculate due date: join day of this month
            join_day = student.join_date.day
            due_date = date(today.year, today.month, min(join_day, 28))
            if today > due_date:
                days_overdue = (today - due_date).days
        rent_data.append({
            'student': student,
            'payment': payment,
            'days_overdue': days_overdue
        })
    if request.method == 'POST':
        pay_id = int(request.form['pay_id'])
        payment = RentPayment.query.get(pay_id)
        payment.paid = True
        payment.paid_date = today
        db.session.commit()
        flash('Rent marked as paid!')
        return redirect(url_for('rent_management'))
    return render_template('rent_management.html', rent_data=rent_data, current_month=current_month)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

def create_admin_user():
    with app.app_context():
        db.create_all()
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin.set_password('adminpassword')  # In production, use a strong password
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
        return admin

if __name__ == '__main__':
    create_admin_user()
    app.run(debug=True)