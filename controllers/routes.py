from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from app import app, db
from controllers.models import User, ParkingLot, ParkingSpot, Reservation
from controllers.config import ADMIN_USERNAME, ADMIN_PASSWORD
from typing import Optional, cast
from matplotlib import pyplot as plt
import os
@app.route('/')
def index():
    lots = ParkingLot.query.all()
    return render_template('index.html', lots=lots)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = cast(str, request.form.get('username', ''))
        password = cast(str, request.form.get('password', ''))
        
        # Check for admin login
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            user = User.query.filter_by(username=username, is_admin=True).first()
            if not user:
                # Create admin user if doesn't exist
                user = User()
                user.username = username
                user.email = 'admin@example.com'
                user.address = 'Admin Address'
                user.pin_code = '000000'
                user.is_admin = True
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        
        # Regular user login
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('user_dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = cast(str, request.form.get('username', ''))
        email = cast(str, request.form.get('email', ''))
        password = cast(str, request.form.get('password', ''))
        address = cast(str, request.form.get('address', ''))
        pin_code = cast(str, request.form.get('pin_code', ''))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
            
        user = User()
        user.username = username
        user.email = email
        user.address = address
        user.pin_code = pin_code
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    lots = ParkingLot.query.all()
    users = User.query.filter_by(is_admin=False).all()
    active_reservations = Reservation.query.filter_by(status='active').all()
    
    # Calculate statistics
    total_spots = sum(lot.max_spots for lot in lots)
    occupied_spots = ParkingSpot.query.filter_by(status='O').count()
    available_spots = total_spots - occupied_spots
    
    return render_template('admin/dashboard.html',
                         lots=lots,
                         users=users,
                         active_reservations=active_reservations,
                         total_spots=total_spots,
                         occupied_spots=occupied_spots,
                         available_spots=available_spots)
@app.route('/admin/summary')
def summary():
    cities = ['Lucknow', 'Delhi']
    available = [5, 9]
    occupied = [0, 1]

    # Create grouped bar chart
    x = range(len(cities))
    width = 0.35

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar([p - width/2 for p in x], available, width=width, label='Available Spots', color='lightgreen')
    ax.bar([p + width/2 for p in x], occupied, width=width, label='Occupied Spots', color='khaki')

    ax.set_xticks(x)
    ax.set_xticklabels(cities)
    ax.set_ylabel("Number of Spots")
    ax.set_title("Parking Lots Status")
    ax.legend()

    # Save to static folder
    chart_path = os.path.join('static', 'parking_status.png')
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()

    return render_template("admin/summary.html", chart_url=url_for('static', filename='parking_status.png'))
   

@app.route('/admin/lots', methods=['GET', 'POST'])
@login_required
def manage_lots():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name', '')  # type: str
        address = request.form.get('address', '')  # type: str
        pin_code = request.form.get('pin_code', '')  # type: str
        price = float(request.form.get('price', '0'))  # type: float
        max_spots = int(request.form.get('max_spots', '0'))  # type: int
        
        lot = ParkingLot(prime_location_name=name,
                        address=address,
                        pin_code=pin_code,
                        price_per_hour=price,
                        max_spots=max_spots)  # type: ignore
        db.session.add(lot)
        db.session.commit()
        
        # Create parking spots for the lot
        for i in range(1, max_spots + 1):
            spot = ParkingSpot(lot_id=lot.id, spot_number=i)  # type: ignore
            db.session.add(spot)
        db.session.commit()
        
        flash('Parking lot created successfully', 'success')
        return redirect(url_for('manage_lots'))
    
    lots = ParkingLot.query.all()
    return render_template('admin/manage_lots.html', lots=lots)

@app.route('/admin/lots/<int:lot_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_lot(lot_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    lot = ParkingLot.query.get_or_404(lot_id)
    if request.method == 'POST':
        name = cast(str, request.form.get('name', ''))
        address = cast(str, request.form.get('address', ''))
        pin_code = cast(str, request.form.get('pin_code', ''))
        price = float(cast(str, request.form.get('price', '0')))
        new_max_spots = int(cast(str, request.form.get('max_spots', '0')))
        
        lot.prime_location_name = name
        lot.address = address
        lot.pin_code = pin_code
        lot.price_per_hour = price
        
        if new_max_spots != lot.max_spots:
            # Check if we can reduce spots
            if new_max_spots < lot.max_spots:
                occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
                if occupied_spots > new_max_spots:
                    flash('Cannot reduce spots below number of occupied spots', 'danger')
                    return redirect(url_for('edit_lot', lot_id=lot_id))
                
                # Remove excess spots
                spots_to_delete = ParkingSpot.query.filter(
                    ParkingSpot.lot_id == lot.id,  # type: ignore
                    ParkingSpot.spot_number > new_max_spots  # type: ignore
                )
                spots_to_delete.delete()
            else:
                # Add new spots
                for i in range(lot.max_spots + 1, new_max_spots + 1):
                    spot = ParkingSpot(lot_id=lot.id, spot_number=i)  # type: ignore
                    db.session.add(spot)
            
            lot.max_spots = new_max_spots
        
        db.session.commit()
        flash('Parking lot updated successfully', 'success')
        return redirect(url_for('manage_lots'))
    
    return render_template('admin/edit_lot.html', lot=lot)

@app.route('/admin/lots/<int:lot_id>/delete', methods=['POST'])
@login_required
def delete_lot(lot_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    lot = ParkingLot.query.get_or_404(lot_id)
    
    # Check if any spots are occupied
    occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
    if occupied_spots > 0:
        flash('Cannot delete lot with occupied spots', 'danger')
        return redirect(url_for('manage_lots'))
    
    db.session.delete(lot)  # This will cascade delete spots
    db.session.commit()
    flash('Parking lot deleted successfully', 'success')
    return redirect(url_for('manage_lots'))

@app.route('/admin/users')
@login_required
def view_users():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    users = User.query.filter_by(is_admin=False).all()
    return render_template('admin/view_users.html', users=users)

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    active_reservations = Reservation.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).all()
    
    past_reservations = Reservation.query.filter_by(
        user_id=current_user.id,
        status='completed'
    ).order_by(Reservation.exit_time.desc()).limit(5).all()
    
    return render_template('user/dashboard.html',
                         active_reservations=active_reservations,
                         past_reservations=past_reservations)

@app.route('/user/book-spot', methods=['GET', 'POST'])
@login_required
def book_spot():
    if current_user.is_admin:
        flash('Admins cannot book spots', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        lot_id = int(request.form.get('lot_id', '0'))  # type: int
        vehicle_number = cast(str, request.form.get('vehicle_number', ''))
        
        # Check if vehicle already has an active reservation
        existing_reservation = Reservation.query.filter_by(
            vehicle_number=vehicle_number,
            status='active'
        ).first()
        
        if existing_reservation:
            flash('This vehicle already has an active reservation', 'danger')
            return redirect(url_for('book_spot'))
        
        # Find first available spot in the lot
        spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()
        if not spot:
            flash('No spots available in this lot', 'danger')
            return redirect(url_for('book_spot'))
        
        # Create reservation
        reservation = Reservation(
            spot_id=spot.id,
            user_id=current_user.id,
            vehicle_number=vehicle_number
        )  # type: ignore
        spot.status = 'O'
        
        db.session.add(reservation)
        db.session.commit()
        
        flash('Spot booked successfully', 'success')
        return redirect(url_for('user_dashboard'))
    
    lots = ParkingLot.query.all()
    return render_template('user/book_spot.html', lots=lots)

@app.route('/user/reservations')
@login_required
def my_reservations():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    reservations = Reservation.query.filter_by(user_id=current_user.id)\
        .order_by(Reservation.entry_time.desc()).all()
    return render_template('user/reservations.html', reservations=reservations)

@app.route('/user/release-spot/<int:reservation_id>', methods=['POST'])
@login_required
def release_spot(reservation_id):
    if current_user.is_admin:
        flash('Admins cannot release spots', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    reservation = Reservation.query.get_or_404(reservation_id)
    if reservation.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('user_dashboard'))
    
    if reservation.status != 'active':
        flash('Reservation is not active', 'danger')
        return redirect(url_for('user_dashboard'))
    
    # Calculate cost
    spot = ParkingSpot.query.get(reservation.spot_id)
    lot = ParkingLot.query.get(spot.lot_id)
    
    exit_time = datetime.utcnow()
    duration = (exit_time - reservation.entry_time).total_seconds() / 3600  # hours
    total_cost = duration * lot.price_per_hour
    
    # Update reservation
    reservation.exit_time = exit_time
    reservation.total_cost = round(total_cost, 2)
    reservation.status = 'completed'
    
    # Update spot status
    spot.status = 'A'
    
    db.session.commit()
    flash(f'Spot released. Total cost: ${reservation.total_cost:.2f}', 'success')
    return redirect(url_for('user_dashboard'))

@app.route('/api/parking-stats')
@login_required
def parking_stats():
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    lots = ParkingLot.query.all()
    stats = []
    
    for lot in lots:
        occupied = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
        available = lot.max_spots - occupied
        stats.append({
            'name': lot.prime_location_name,
            'occupied': occupied,
            'available': available
        })
    
    return jsonify(stats)