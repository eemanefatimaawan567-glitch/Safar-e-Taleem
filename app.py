import os
import re
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from modules.petrol_price import get_petrol_price as fetch_live_petrol_price
from modules.commute_engine import recommend_transport, calculate_fuel_cost, calculate_carpool_saving, distance_km, cluster_families
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'safar-e-taleem-dev-key-change-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------------------------------------------------
# DATABASE MODELS
# ---------------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'parent' or 'principal'
    cnic = db.Column(db.String(15), unique=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=True)
    # Location fields for transport matching
    address = db.Column(db.String(200), default='')
    neighborhood = db.Column(db.String(100), default='')
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    children_count = db.Column(db.Integer, default=1)
    school_name = db.Column(db.String(150), default='')


class PetrolPrice(db.Model):
    """Stores petrol price snapshots for history and change detection."""
    id = db.Column(db.Integer, primary_key=True)
    price = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(50), default='shell_pk')
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)



class HybridSchedule(db.Model):
    """Stores hybrid schedule state triggered by principal."""
    id = db.Column(db.Integer, primary_key=True)
    is_active = db.Column(db.Boolean, default=False)
    triggered_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow)
    petrol_price_at_trigger = db.Column(db.Float, nullable=True)
    # Rotation: A=Mon/Wed/Fri physical, B=Tue/Thu physical
    group_a_days = db.Column(db.String(50), default='Mon, Wed, Fri')
    group_b_days = db.Column(db.String(50), default='Tue, Thu, Sat')
    online_days = db.Column(db.String(50), default='Tue, Thu')
    note = db.Column(db.Text, default='')


class LocationShare(db.Model):
    """Live commute location for a parent's child. One row per parent account."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=False)
    started_at = db.Column(db.DateTime, nullable=True)
    last_updated = db.Column(db.DateTime, nullable=True)
    is_sos = db.Column(db.Boolean, default=False)
    sos_triggered_at = db.Column(db.DateTime, nullable=True)

# Initialize Database
with app.app_context():
    db.create_all()
    # Seed initial petrol price if table is empty
    if PetrolPrice.query.count() == 0:
        db.session.add(PetrolPrice(price=325.43, source='seed'))
        db.session.commit()


def get_tracked_petrol_price():
    """
    Fetches live petrol price, compares with the last stored DB price,
    saves the new price if changed, and returns full data dict.
    """
    live = fetch_live_petrol_price()
    current = live['price']

    # Get the most recent stored price
    last_record = PetrolPrice.query.order_by(PetrolPrice.checked_at.desc()).first()
    previous = last_record.price if last_record else current

    # Save new price if it changed (or if no record yet)
    if last_record is None or abs(current - last_record.price) > 0.01:
        new_entry = PetrolPrice(price=current, source=live.get('source', 'live'))
        db.session.add(new_entry)
        db.session.commit()

    difference = round(current - previous, 2)
    direction = 'increase' if difference > 0 else ('decrease' if difference < 0 else 'unchanged')
    percentage = round((difference / previous) * 100, 2) if previous else 0

    return {
        'price': current,
        'current_price': current,
        'previous_price': previous,
        'difference': difference,
        'percentage_change': percentage,
        'direction': direction,
        'alert': (direction == 'increase' and percentage >= 2),
        'source': live.get('source', 'Live PSO/Shell Web Source'),
        'checked_at': datetime.now().isoformat()
    }

def get_family_pod_members(user):
    """Returns parent Users in the same commute cluster as `user` (excludes self)."""
    if not user or not user.neighborhood or user.role != 'parent':
        return []

    neighborhood_parents = User.query.filter(
        User.neighborhood == user.neighborhood,
        User.role == 'parent',
    ).all()

    if len(neighborhood_parents) < 2:
        return [u for u in neighborhood_parents if u.id != user.id]

    clusters = cluster_families(neighborhood_parents)
    for c in clusters:
        member_ids = [m.id for m in c['members']]
        if user.id in member_ids:
            return [m for m in c['members'] if m.id != user.id]

    # User is noise / not in any cluster
    return [u for u in neighborhood_parents if u.id != user.id]

def get_pod_coordinator(user):
    """
    Returns the parent User designated as Group Coordinator for `user`'s pod.
    Deterministic: lowest user id in the pod (self + pod-mates) is coordinator,
    so every member of the same pod agrees on who it is. Returns None if the
    user isn't a parent or has no pod-mates.
    """
    if not user or user.role != 'parent':
        return None
    pod_members = get_family_pod_members(user)
    if not pod_members:
        return None
    return min([user] + pod_members, key=lambda u: u.id)

# Helper function for Pakistani CNIC validation (XXXXX-XXXXXXX-X)
def validate_cnic(cnic_str):
    pattern = r"^\d{5}-\d{7}-\d{1}$"
    return bool(re.match(pattern, cnic_str)) if cnic_str else False

# Helper function to get currently logged-in user object
def get_current_user():
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None

# Login-required decorator
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ---------------------------------------------------------
# PUBLIC & AUTH ROUTES
# ---------------------------------------------------------

@app.route('/')
def index():
    petrol = get_tracked_petrol_price()

    # Dynamic metrics from database
    parent_count = User.query.filter_by(role='parent').count()
    all_parents = User.query.filter_by(role='parent').all()
    total_students = sum(u.children_count for u in all_parents) or 0

    # Count real transport groups via DBSCAN
    clusters = cluster_families(all_parents) if all_parents else []
    group_count = len([c for c in clusters if c['cluster_id'] != -1]) or 0

    # Calculate real estimated savings
    total_savings = 0
    for c in clusters:
        if c['cluster_id'] != -1 and len(c['members']) >= 2:
            info = calculate_carpool_saving(len(c['members']), max(c['avg_distance_km'], 1.0) * 2, petrol['price'])
            total_savings += info['monthly_saving']

    return render_template(
        'index.html',
        petrol_price=petrol['price'],
        petrol_direction=petrol['direction'],
        petrol_change=petrol['difference'],
        petrol_percentage=petrol['percentage_change'],
        parent_count=parent_count,
        group_count=group_count,
        total_savings=total_savings,
        total_students=total_students,
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_role'] = user.role
            
            # Redirect based on user role
            if user.role == 'principal':
                return redirect(url_for('principal_dashboard'))
            return redirect(url_for('parent_dashboard'))
        else:
            return render_template('login.html', error="Invalid email or password.")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'parent')
        cnic = request.form.get('cnic')

        # CNIC Validation Check
        if not validate_cnic(cnic):
            return render_template('register.html', error="Invalid CNIC format. Format must be 35201-1234567-1.")

        # Check existing user
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error="Email is already registered.")
        
        if User.query.filter_by(cnic=cnic).first():
            return render_template('register.html', error="CNIC is already registered.")

        # Create user
        new_user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            role=role,
            cnic=cnic,
            is_verified=True,
            address=request.form.get('address', ''),
            neighborhood=request.form.get('neighborhood', ''),
            latitude=request.form.get('latitude') or None,
            longitude=request.form.get('longitude') or None,
            children_count=int(request.form.get('children_count', 1)),
            school_name=request.form.get('school_name', '')
        )
        db.session.add(new_user)
        db.session.commit()

        # Log in user immediately after registration
        session['user_id'] = new_user.id
        session['user_role'] = new_user.role

        if new_user.role == 'principal':
            return redirect(url_for('principal_dashboard'))
        return redirect(url_for('parent_dashboard'))

    return render_template('register.html')

@app.route('/demo-login/<role>')
def demo_login(role):
    """One-click demo login for hackathon judges — no form, no password needed."""
    if role == 'parent':
        user = User.query.filter_by(email='ayesha@demo.com').first()
    elif role == 'principal':
        user = User.query.filter_by(email='principal@demo.com').first()
    else:
        user = None

    if user:
        session['user_id'] = user.id
        session['user_role'] = user.role
        if user.role == 'principal':
            return redirect(url_for('principal_dashboard'))
        return redirect(url_for('parent_dashboard'))

    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------------------------------------------------
# PROTECTED DASHBOARDS
# ---------------------------------------------------------

@app.route('/parent')
@login_required
def parent_dashboard():
    user = get_current_user()
    petrol = get_tracked_petrol_price()

    # Use real GPS distance if user has coordinates, else default
    sample_distance = 2.5  # km default
    sample_group = max(user.children_count, 2) if user and user.children_count else 3

    # Find nearby parents using DBSCAN clustering on same neighborhood
    nearby_parents = []
    nearby_count = 0
    user_cluster_type = 'Individual Transport'

    if user and user.neighborhood:
        # Get all parents in same neighborhood
        neighborhood_parents = User.query.filter(
            User.neighborhood == user.neighborhood,
            User.role == 'parent',
        ).all()

        # Run DBSCAN clustering on neighborhood parents
        if len(neighborhood_parents) >= 2:
            clusters = cluster_families(neighborhood_parents)
            # Find user's cluster
            for c in clusters:
                member_ids = [m.id for m in c['members']]
                if user.id in member_ids:
                    nearby_parents = [m for m in c['members'] if m.id != user.id][:5]
                    user_cluster_type = c['transport_type']
                    # Use real cluster distance if available
                    if c['avg_distance_km'] > 0:
                        sample_distance = max(c['avg_distance_km'], 0.5)
                    break
            else:
                # User not in any cluster (noise) — fallback to neighborhood query
                nearby_parents = [u for u in neighborhood_parents if u.id != user.id][:5]
        else:
            nearby_parents = [u for u in neighborhood_parents if u.id != user.id][:5]

        nearby_count = len(nearby_parents)

    recommendation = recommend_transport(sample_distance, sample_group)
    monthly_fuel = calculate_fuel_cost(sample_distance * 2, petrol['price'])
    carpool_info = calculate_carpool_saving(sample_group, sample_distance * 2, petrol['price'])

    # Group Coordinator: one parent per pod, chosen deterministically so every
    # member of the pod agrees on who it is.
    coordinator = get_pod_coordinator(user)
    is_coordinator = bool(coordinator and coordinator.id == user.id)
    coordinator_name = coordinator.name if coordinator else None

    return render_template(
        'parent.html',
        user=user,
        petrol_price=petrol['price'],
        petrol_direction=petrol['direction'],
        petrol_change=petrol['difference'],
        petrol_percentage=petrol['percentage_change'],
        recommendation=recommendation,
        monthly_fuel=monthly_fuel,
        carpool_saving=carpool_info,
        nearby_count=nearby_count,
        nearby_parents=nearby_parents,
        user_cluster_type=user_cluster_type,
        sample_distance=round(sample_distance, 1),
        is_coordinator=is_coordinator,
        coordinator_name=coordinator_name,
        coordinator_id=coordinator.id if coordinator else None,
    )

@app.route('/principal')
@login_required
def principal_dashboard():
    user = get_current_user()
    petrol = get_tracked_petrol_price()

    # Real stats from database
    all_parents = User.query.filter_by(role='parent').all()
    total_parents = len(all_parents)
    total_students = sum(u.children_count for u in all_parents) or 1

    # Run DBSCAN clustering for transport breakdown
    clusters = cluster_families(all_parents) if all_parents else []
    walking_groups = len([c for c in clusters if 'Walking' in c['transport_type']])
    carpool_groups = len([c for c in clusters if 'Carpool' in c['transport_type'] or 'Shared' in c['transport_type']])
    solo_count = len([c for c in clusters if c['cluster_id'] == -1])

    # Calculate real average monthly cost
    total_costs = []
    for u in all_parents:
        d = 2.5  # default
        if u.latitude and u.longitude and u.school_name:
            # Use user's actual distance estimate
            d = 2.5  # could be refined with school coords
        total_costs.append(calculate_fuel_cost(d * 2, petrol['price']))
    avg_monthly_cost = round(sum(total_costs) / len(total_costs)) if total_costs else 0

    return render_template(
        'principal.html',
        user=user,
        petrol_price=petrol['price'],
        alert=petrol['alert'],
        percentage_change=petrol['percentage_change'],
        direction=petrol['direction'],
        difference=petrol['difference'],
        total_parents=total_parents,
        total_students=total_students,
        avg_monthly_cost=avg_monthly_cost,
        walking_groups=walking_groups,
        carpool_groups=carpool_groups,
        solo_count=solo_count,
        total_groups=len(clusters),
    )


# ---------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------

@app.route('/api/petrol-price', methods=['GET'])
def get_petrol_price():
    petrol = get_tracked_petrol_price()
    return jsonify(petrol)


@app.route('/api/petrol-history', methods=['GET'])
def get_petrol_history():
    """Returns last 10 petrol price snapshots for charting."""
    records = PetrolPrice.query.order_by(PetrolPrice.checked_at.desc()).limit(10).all()
    history = [
        {
            'price': r.price,
            'checked_at': r.checked_at.isoformat() if r.checked_at else '',
            'source': r.source
        }
        for r in reversed(records)
    ]
    return jsonify(history)

@app.route('/api/ask-ammi-abba', methods=['POST'])
def ask_ammi_abba():
    from modules.ai_responses import generate_response

    # Support both JSON and FormData
    if request.content_type and 'multipart' in request.content_type:
        user_query = request.form.get('message', '')
    else:
        data = request.json or {}
        user_query = data.get('message', '')

    if not user_query.strip():
        return jsonify({'text_response': 'Please type or speak your question. I am here to help!'})

    # Get logged-in user context
    user = get_current_user()
    user_context = {}
    db_context = {}

    if user:
        user_context = {
            'name': user.name,
            'neighborhood': user.neighborhood or '',
            'address': user.address or '',
            'children_count': user.children_count or 1,
            'school_name': user.school_name or '',
            'latitude': user.latitude,
            'longitude': user.longitude,
        }

        # Compute real DB context: nearby families, cluster type, distance
        if user.neighborhood and user.role == 'parent':
            neighborhood_parents = User.query.filter(
                User.neighborhood == user.neighborhood,
                User.role == 'parent',
            ).all()

            if len(neighborhood_parents) >= 2:
                clusters = cluster_families(neighborhood_parents)
                for c in clusters:
                    member_ids = [m.id for m in c['members']]
                    if user.id in member_ids:
                        nearby_members = [m for m in c['members'] if m.id != user.id]
                        db_context = {
                            'nearby_count': len(nearby_members),
                            'nearby_names': [m.name for m in nearby_members],
                            'cluster_type': c['transport_type'],
                            'cluster_distance': c['avg_distance_km'] if c['avg_distance_km'] > 0 else 2.5,
                        }
                        break
                else:
                    # User is noise / no cluster
                    others = [u for u in neighborhood_parents if u.id != user.id]
                    db_context = {
                        'nearby_count': len(others),
                        'nearby_names': [u.name for u in others],
                        'cluster_type': 'Individual Transport',
                        'cluster_distance': 2.5,
                    }
            else:
                db_context = {
                    'nearby_count': 0,
                    'nearby_names': [],
                    'cluster_type': 'Individual Transport',
                    'cluster_distance': 2.5,
                }

    # Fetch live petrol data (with DB tracking)
    petrol = get_tracked_petrol_price()

    # Generate response (Qwen AI if key set, else rule-based fallback)
    response_text = generate_response(user_query, petrol, user_context, db_context)

    return jsonify({'text_response': response_text, 'source': 'ai'})


# ---------------------------------------------------------
# FEATURE 2: HYBRID SCHEDULE API
# ---------------------------------------------------------

@app.route('/api/hybrid-status', methods=['GET'])
def get_hybrid_status():
    """Returns current hybrid schedule state."""
    hybrid = HybridSchedule.query.order_by(HybridSchedule.id.desc()).first()
    if not hybrid:
        return jsonify({'active': False, 'message': 'No hybrid schedule configured'})
    return jsonify({
        'active': hybrid.is_active,
        'group_a_days': hybrid.group_a_days,
        'group_b_days': hybrid.group_b_days,
        'online_days': hybrid.online_days,
        'petrol_at_trigger': hybrid.petrol_price_at_trigger,
        'triggered_at': hybrid.triggered_at.isoformat() if hybrid.triggered_at else None,
        'note': hybrid.note,
    })


@app.route('/api/toggle-hybrid', methods=['POST'])
@login_required
def toggle_hybrid():
    """Principal toggles hybrid schedule on/off."""
    user = get_current_user()
    if not user or user.role != 'principal':
        return jsonify({'error': 'Only principals can toggle hybrid schedule'}), 403

    petrol = get_tracked_petrol_price()

    # Toggle: if active, deactivate; if inactive, activate
    existing = HybridSchedule.query.order_by(HybridSchedule.id.desc()).first()
    if existing and existing.is_active:
        existing.is_active = False
        existing.note = 'Deactivated by principal'
        db.session.commit()
        return jsonify({'active': False, 'message': 'Hybrid schedule deactivated'})

    # Activate new hybrid schedule
    new_schedule = HybridSchedule(
        is_active=True,
        triggered_by=user.id,
        petrol_price_at_trigger=petrol['price'],
        group_a_days='Mon, Wed, Fri',
        group_b_days='Tue, Thu, Sat',
        online_days='Tue, Thu',
        note=f'Auto-triggered at petrol price Rs {petrol["price"]}/L',
    )
    db.session.add(new_schedule)
    db.session.commit()

    return jsonify({
        'active': True,
        'message': 'Hybrid schedule activated!',
        'petrol_at_trigger': petrol['price'],
    })


# ---------------------------------------------------------
# FEATURE: LIVE COMMUTE LOCATION (SAFETY)
# ---------------------------------------------------------

STALE_AFTER_SECONDS = 300  # 5 minutes — a marker turns amber/grey after this


@app.route('/api/location/start', methods=['POST'])
@login_required
def location_start():
    """Start sharing live commute location (parent, on behalf of their child)."""
    user = get_current_user()
    data = request.json or {}
    lat = data.get('latitude')
    lon = data.get('longitude')
    if lat is None or lon is None:
        return jsonify({'error': 'latitude and longitude are required'}), 400

    share = LocationShare.query.filter_by(user_id=user.id).first()
    now = datetime.utcnow()
    if not share:
        share = LocationShare(user_id=user.id)
        db.session.add(share)

    share.latitude = lat
    share.longitude = lon
    share.is_active = True
    share.started_at = now
    share.last_updated = now
    share.is_sos = False
    share.sos_triggered_at = None
    db.session.commit()

    return jsonify({'started': True, 'started_at': now.isoformat()})


@app.route('/api/location/ping', methods=['POST'])
@login_required
def location_ping():
    """Periodic location update sent while sharing is active."""
    user = get_current_user()
    data = request.json or {}
    lat = data.get('latitude')
    lon = data.get('longitude')

    share = LocationShare.query.filter_by(user_id=user.id).first()
    if not share or not share.is_active:
        return jsonify({'error': 'Sharing is not active. Call /api/location/start first.'}), 400

    if lat is not None:
        share.latitude = lat
    if lon is not None:
        share.longitude = lon
    share.last_updated = datetime.utcnow()
    db.session.commit()

    return jsonify({'updated': True, 'last_updated': share.last_updated.isoformat()})


@app.route('/api/location/stop', methods=['POST'])
@login_required
def location_stop():
    """Stop sharing (arrived safely / commute finished)."""
    user = get_current_user()
    share = LocationShare.query.filter_by(user_id=user.id).first()
    if share:
        share.is_active = False
        share.is_sos = False
        share.sos_triggered_at = None
        db.session.commit()
    return jsonify({'stopped': True})


@app.route('/api/location/sos', methods=['POST'])
@login_required
def location_sos():
    """Trigger an SOS — instantly visible to pod-mates, route captain, and principal."""
    user = get_current_user()
    share = LocationShare.query.filter_by(user_id=user.id).first()
    if not share or not share.is_active:
        return jsonify({'error': 'Start sharing location before sending an SOS'}), 400

    share.is_sos = True
    share.sos_triggered_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'sos': True})


@app.route('/api/location/sos-clear', methods=['POST'])
@login_required
def location_sos_clear():
    """Clear an SOS (false alarm / resolved)."""
    user = get_current_user()
    share = LocationShare.query.filter_by(user_id=user.id).first()
    if share:
        share.is_sos = False
        share.sos_triggered_at = None
        db.session.commit()
    return jsonify({'cleared': True})


@app.route('/api/location/pod', methods=['GET'])
@login_required
def location_pod():
    """
    Returns live locations for the current user's commute pod:
      - Parent: self + pod-mates in the same walking/carpool cluster
      - Principal: any active SOS anywhere in the school
    """
    user = get_current_user()
    now = datetime.utcnow()
    results = []

    def build_entry(member_user, share, is_me=False, is_coordinator=False):
        if not share or not share.is_active:
            return None
        age = (now - share.last_updated).total_seconds() if share.last_updated else 999999
        return {
            'user_id': member_user.id,
            'name': member_user.name,
            'latitude': share.latitude,
            'longitude': share.longitude,
            'last_updated': share.last_updated.isoformat() if share.last_updated else None,
            'age_seconds': int(age),
            'is_stale': age > STALE_AFTER_SECONDS,
            'is_sos': share.is_sos,
            'is_me': is_me,
            'is_coordinator': is_coordinator,
        }

    if user.role == 'parent':
        pod_members = get_family_pod_members(user)
        all_members = [user] + pod_members
        member_ids = [m.id for m in all_members]
        shares_by_uid = {s.user_id: s for s in LocationShare.query.filter(LocationShare.user_id.in_(member_ids)).all()}
        coordinator = get_pod_coordinator(user)
        coordinator_id = coordinator.id if coordinator else None
        for m in all_members:
            entry = build_entry(m, shares_by_uid.get(m.id), is_me=(m.id == user.id), is_coordinator=(m.id == coordinator_id))
            if entry:
                results.append(entry)

    elif user.role == 'principal':
        for share in LocationShare.query.filter_by(is_active=True).all():
            member = User.query.get(share.user_id)
            if not member:
                continue
            entry = build_entry(member, share)
            if entry:
                results.append(entry)

    return jsonify({'pod': results, 'stale_after_seconds': STALE_AFTER_SECONDS})


# ---------------------------------------------------------
# RUN SERVER
# ---------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, port=5001)