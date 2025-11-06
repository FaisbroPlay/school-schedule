from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Конфигурация базы данных
if 'DATABASE_URL' in os.environ:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL'].replace('postgres://', 'postgresql://')
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


@app.context_processor
def utility_processor():
    return dict(enumerate=enumerate, range=range)


db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.Integer, nullable=False)
    lesson_number = db.Column(db.Integer, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    teacher = db.Column(db.String(100))
    classroom = db.Column(db.String(20))
    class_group = db.Column(db.String(50), default="all")


# Инициализация базы данных
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()


# Маршруты
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('schedule'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('schedule'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if len(username) < 3:
            flash('Имя пользователя должно содержать минимум 3 символа', 'error')
            return render_template('register.html')

        if len(password) < 4:
            flash('Пароль должен содержать минимум 4 символа', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Пароли не совпадают', 'error')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Имя пользователя уже занято', 'error')
            return render_template('register.html')

        is_first_user = User.query.count() == 0

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            is_admin=is_first_user
        )

        db.session.add(user)
        db.session.commit()

        if is_first_user:
            flash('Регистрация успешна! Вы первый пользователь и стали администратором.', 'success')
        else:
            flash('Регистрация успешна! Теперь вы можете войти.', 'success')

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


@app.route('/schedule')
def schedule():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    day = request.args.get('day', 0, type=int)
    class_group = request.args.get('class', 'all')

    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница']
    lessons = Lesson.query.filter_by(day_of_week=day, class_group=class_group).order_by(Lesson.lesson_number).all()

    return render_template('schedule.html',
                           lessons=lessons,
                           days=days,
                           current_day=day,
                           current_class=class_group)


@app.route('/edit_schedule', methods=['GET', 'POST'])
def edit_schedule():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('У вас нет прав для редактирования расписания', 'error')
        return redirect(url_for('schedule'))

    if request.method == 'POST':
        day = int(request.form['day'])
        class_group = request.form['class_group']

        Lesson.query.filter_by(day_of_week=day, class_group=class_group).delete()

        lesson_count = int(request.form['lesson_count'])

        for i in range(1, lesson_count + 1):
            subject = request.form.get(f'subject_{i}')
            teacher = request.form.get(f'teacher_{i}')
            classroom = request.form.get(f'classroom_{i}')

            if subject:
                lesson = Lesson(
                    day_of_week=day,
                    lesson_number=i,
                    subject=subject,
                    teacher=teacher,
                    classroom=classroom,
                    class_group=class_group
                )
                db.session.add(lesson)

        db.session.commit()
        flash('Расписание успешно обновлено!', 'success')
        return redirect(url_for('schedule'))

    day = request.args.get('day', 0, type=int)
    class_group = request.args.get('class', 'all')

    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница']
    lessons = Lesson.query.filter_by(day_of_week=day, class_group=class_group).order_by(Lesson.lesson_number).all()

    return render_template('edit_schedule.html',
                           lessons=lessons,
                           days=days,
                           current_day=day,
                           current_class=class_group)


@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('У вас нет прав для доступа к этой странице', 'error')
        return redirect(url_for('schedule'))

    users = User.query.all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/toggle_admin/<int:user_id>')
def toggle_admin(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('У вас нет прав для выполнения этого действия', 'error')
        return redirect(url_for('schedule'))

    user = User.query.get_or_404(user_id)

    if user.id == session['user_id']:
        flash('Вы не можете снять права администратора с самого себя', 'error')
        return redirect(url_for('admin_users'))

    user.is_admin = not user.is_admin
    db.session.commit()

    action = "назначен" if user.is_admin else "снят"
    flash(f'Пользователю {user.username} {action} статус администратора', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('У вас нет прав для выполнения этого действия', 'error')
        return redirect(url_for('schedule'))

    user = User.query.get_or_404(user_id)

    if user.id == session['user_id']:
        flash('Вы не можете удалить свой собственный аккаунт', 'error')
        return redirect(url_for('admin_users'))

    db.session.delete(user)
    db.session.commit()

    flash(f'Пользователь {user.username} удален', 'success')
    return redirect(url_for('admin_users'))


@app.route('/api/schedule')
def api_schedule():
    day = request.args.get('day', 0, type=int)
    class_group = request.args.get('class', 'all')

    lessons = Lesson.query.filter_by(day_of_week=day, class_group=class_group).order_by(Lesson.lesson_number).all()

    result = []
    for lesson in lessons:
        result.append({
            'lesson_number': lesson.lesson_number,
            'subject': lesson.subject,
            'teacher': lesson.teacher,
            'classroom': lesson.classroom
        })

    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)