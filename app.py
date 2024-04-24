import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
from authorize import role_required
from models import *
from datetime import datetime as dt

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'university.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'beyond_course_scope'
db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login' # default login route
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    default_route_function = 'volunteer_view_all'
    default_volunteer_route_function = 'volunteer_view'

    if request.method == 'GET':
        # Determine where to redirect user if they are already logged in
        if current_user and current_user.is_authenticated:
            if current_user.role in ['MANAGER', 'ADMIN']:
                return redirect(url_for(default_route_function))
            elif current_user.role == 'STUDENT':
                return redirect(url_for(default_volunteer_route_function, volunteer_id=0))
        else:
            redirect_route = request.args.get('next')
            return render_template('login.html', redirect_route=redirect_route)

    elif request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        redirect_route = request.form.get('redirect_route')

        user = User.query.filter_by(username=username).first()

        # Validate user credentials and redirect them to initial destination
        if user and check_password_hash(user.password, password):
            login_user(user)

            if current_user.role in ['MANAGER', 'ADMIN']:
                return redirect(redirect_route if redirect_route else url_for(default_route_function))
            elif current_user.role == 'STUDENT':
                return redirect(redirect_route if redirect_route else url_for(default_volunteer_route_function, volunteer_id=0))
        else:
            flash(f'Your login information was not correct. Please try again.', 'error')

        return redirect(url_for('login'))

    return redirect(url_for('login'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash(f'You have been logged out.', 'success')
    return redirect(url_for('home'))


@app.route('/volunteer/view')
@login_required
@role_required(['ADMIN', 'MANAGER'])
def volunteer_view_all():
    volunteers = Volunteer.query.outerjoin(Major, Volunteer.major_id == Major.major_id) \
        .add_entity(Major) \
        .order_by(Volunteer.last_name, Volunteer.first_name) \
        .all()
    return render_template('volunteer_view_all.html', volunteers=volunteers)


@app.route('/volunteer/view/<int:volunteer_id>')
@login_required
@role_required(['ADMIN', 'MANAGER', 'STUDENT'])
def volunteer_view(volunteer_id):
    if current_user.role in ['MANAGER', 'ADMIN']:
        volunteer = Volunteer.query.filter_by(volunteer_id=volunteer_id).first()
        majors = Major.query.order_by(Major.major) \
            .all()

        if volunteer:
            return render_template('volunteer_entry.html', volunteer=volunteer, majors=majors, action='read')

        else:
            flash(f'Volunteer attempting to be viewed could not be found!', 'error')
            return redirect(url_for('volunteer_view_all'))

    elif current_user.role == 'STUDENT':
        volunteer = Volunteer.query.filter_by(email=current_user.email).first()
        majors = Major.query.order_by(Major.major) \
            .all()

        if volunteer:
            return render_template('volunteer_entry.html', volunteer=volunteer, majors=majors, action='read')

        else:
            flash(f'Your record could not be located. Please contact advising.', 'error')
            return redirect(url_for('error'))

    # This point should never be reached as all roles are accounted for. Adding defensive programming as a double check.
    else:
        flash(f'Invalid request. Please contact support if this problem persists.', 'error')
        return render_template('error.html')


@app.route('/volunteer/create', methods=['GET', 'POST'])
@login_required
@role_required(['ADMIN', 'MANAGER'])
def volunteer_create():
    if request.method == 'GET':
        majors = Major.query.order_by(Major.major) \
            .order_by(Major.major) \
            .all()
        return render_template('volunteer_entry.html', majors=majors, action='create')
    elif request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        major_id = request.form['major_id']

        birth_date = request.form['birth_date']
        is_honors = True if 'is_honors' in request.form else False

        volunteer = Volunteer(first_name=first_name, last_name=last_name, email=email, major_id=major_id,
                          birth_date=dt.strptime(birth_date, '%Y-%m-%d'), is_honors=is_honors)
        db.session.add(volunteer)
        db.session.commit()
        flash(f'{first_name} {last_name} was successfully added!', 'success')
        return redirect(url_for('volunteer_view_all'))

    # Address issue where unsupported HTTP request method is attempted
    flash(f'Invalid request. Please contact support if this problem persists.', 'error')
    return redirect(url_for('volunteer_view_all'))


@app.route('/volunteer/update/<int:volunteer_id>', methods=['GET', 'POST'])
@login_required
@role_required(['ADMIN', 'MANAGER'])
def volunteer_edit(volunteer_id):
    if request.method == 'GET':
        volunteer = Volunteer.query.filter_by(volunteer_id=volunteer_id).first()
        majors = Major.query.order_by(Major.major) \
            .order_by(Major.major) \
            .all()

        if volunteer:
            return render_template('volunteer_entry.html', volunteer=volunteer, majors=majors, action='update')

        else:
            flash(f'Volunteer attempting to be edited could not be found!', 'error')

    elif request.method == 'POST':
        volunteer = Volunteer.query.filter_by(volunteer_id=volunteer_id).first()

        if volunteer:
            volunteer.first_name = request.form['first_name']
            volunteer.last_name = request.form['last_name']
            volunteer.email = request.form['email']
            volunteer.major_id = request.form['major_id']
            volunteer.birthdate = dt.strptime(request.form['birth_date'], '%Y-%m-%d')
            volunteer.num_credits_completed = request.form['num_credits_completed']
            volunteer.gpa = request.form['gpa']
            volunteer.is_honors = True if 'is_honors' in request.form else False

            db.session.commit()
            flash(f'{volunteer.first_name} {volunteer.last_name} was successfully updated!', 'success')
        else:
            flash(f'Student attempting to be edited could not be found!', 'error')

        return redirect(url_for('volunteer_view_all'))

    # Address issue where unsupported HTTP request method is attempted
    flash(f'Invalid request. Please contact support if this problem persists.', 'error')
    return redirect(url_for('volunteer_view_all'))


@app.route('/volunteer/delete/<int:volunteer_id>')
@login_required
@role_required(['ADMIN'])
def volunteer_delete(volunteer_id):
    volunteer = Volunteer.query.filter_by(volunteer_id=volunteer_id).first()
    print(volunteer_id)
    if volunteer:
        db.session.delete(volunteer)
        db.session.commit()
        flash(f'{volunteer} was successfully deleted!', 'success')
    else:
        flash(f'Delete failed! Volunteer could not be found.', 'error')

    return redirect(url_for('volunteer_view_all'))


@app.route('/error')
def error():
    # Generic error handler to handle various site errors
    # Before routing to this route, ensure flash function is used
    return render_template('error.html')

@app.route('/training')
def training():
    # Generic error handler to handle various site errors
    # Before routing to this route, ensure flash function is used
    return render_template('training.html')


@app.errorhandler(404)
def page_not_found(e):
    flash(f'Sorry! You are trying to access a page that does not exist. Please contact support if this problem persists.', 'error')
    return render_template('404.html'), 404


if __name__ == '__main__':
    app.run(debug=True)