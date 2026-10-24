
import os
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import inspect, text

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY', 'change-this-secret-before-production'
)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///anos_net.db'
).replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

UPLOAD_DIR = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGES = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


# =========================
# MODÈLES DE BASE DE DONNÉES
# =========================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(24), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.String(180), default='Joueur Free Fire')
    ff_id = db.Column(db.String(40), default='')
    rank = db.Column(db.String(40), default='Non classé')
    favorite_mode = db.Column(db.String(40), default='Battle Royale')
    is_admin = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    profile_image = db.Column(db.String(500), default='')


class PublicMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.String(500), nullable=False, default='')
    image_path = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    caption = db.Column(db.String(1000), default='')
    image_path = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')


class PostLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='unique_post_like'),
    )


class PostComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.String(500), nullable=False, default='')
    image_path = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')


class PrivateMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.String(1000), nullable=False, default='')
    image_path = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id])
    recipient = db.relationship('User', foreign_keys=[recipient_id])


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(250), default='')
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner = db.relationship('User')


# =========================
# AUTHENTIFICATION
# =========================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def common_context():
    return {'site_name': 'ANOS NET'}


# =========================
# GESTION DES IMAGES
# =========================

def save_image(file):
    if not file or not file.filename or '.' not in file.filename:
        return ''

    ext = file.filename.rsplit('.', 1)[1].lower()

    if ext not in ALLOWED_IMAGES:
        raise ValueError(
            'Formats acceptés : PNG, JPG, WEBP ou GIF.'
        )

    name = uuid.uuid4().hex + '.' + ext
    name = secure_filename(name)

    file.save(os.path.join(UPLOAD_DIR, name))

    return 'uploads/' + name


# =========================
# ACCUEIL
# =========================

@app.route('/')
def home():
    latest = PublicMessage.query.order_by(
        PublicMessage.created_at.desc()
    ).limit(5).all()

    return render_template(
        'home.html',
        members=User.query.count(),
        teams=Team.query.count(),
        latest=latest
    )


# =========================
# INSCRIPTION
# =========================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if (
            len(username) < 3
            or len(username) > 24
            or not username.replace('_', '').isalnum()
        ):
            flash(
                'Le pseudo doit contenir 3 à 24 lettres, chiffres ou _.',
                'error'
            )

        elif len(password) < 8:
            flash(
                'Le mot de passe doit contenir au moins 8 caractères.',
                'error'
            )

        elif User.query.filter_by(username=username).first():
            flash('Ce pseudo est déjà utilisé.', 'error')

        else:
            user = User(
                username=username,
                password_hash=generate_password_hash(password)
            )

            db.session.add(user)
            db.session.commit()

            login_user(user)
            flash('Compte créé. Bienvenue dans la zone !', 'success')

            return redirect(url_for('profile'))

    return render_template('auth.html', mode='register')


# =========================
# CONNEXION
# =========================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Connexion réussie.', 'success')
            return redirect(url_for('home'))

        flash('Pseudo ou mot de passe incorrect.', 'error')

    return render_template('auth.html', mode='login')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Tu es déconnecté.', 'success')
    return redirect(url_for('home'))


# =========================
# CHAT PUBLIC
# =========================

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if request.method == 'POST':
        body = request.form.get('body', '').strip()

        try:
            image_path = save_image(request.files.get('image'))

            if (body or image_path) and len(body) <= 500:
                message = PublicMessage(
                    user_id=current_user.id,
                    body=body,
                    image_path=image_path
                )
                db.session.add(message)
                db.session.commit()
            else:
                flash(
                    'Ajoute un texte ou une image '
                    '(texte limité à 500 caractères).',
                    'error'
                )

        except ValueError as exc:
            flash(str(exc), 'error')

        return redirect(url_for('chat'))

    messages = PublicMessage.query.order_by(
        PublicMessage.created_at.desc()
    ).limit(100).all()[::-1]

    return render_template('chat.html', messages=messages)


# =========================
# RECHERCHE DES MEMBRES
# =========================

@app.route('/members')
def members():
    q = request.args.get('q', '').strip()[:24]

    if q:
        users = User.query.filter(
            User.username.ilike(f'%{q}%')
        ).order_by(User.username.asc()).limit(100).all()
    else:
        users = User.query.order_by(
            User.joined_at.desc()
        ).limit(100).all()

    return render_template('members.html', users=users, q=q)


# =========================
# PROFIL
# =========================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.bio = request.form.get('bio', '')[:180].strip()
        current_user.ff_id = request.form.get('ff_id', '')[:40].strip()
        current_user.rank = request.form.get('rank', 'Non classé')[:40]
        current_user.favorite_mode = request.form.get(
            'favorite_mode', 'Battle Royale'
        )[:40]

        try:
            image_path = save_image(
                request.files.get('profile_image')
            )

            if image_path:
                current_user.profile_image = image_path

        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('profile'))

        db.session.commit()
        flash('Profil mis à jour.', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html')


# =========================
# MESSAGES PRIVÉS
# =========================

@app.route('/dm/<int:user_id>', methods=['GET', 'POST'])
@login_required
def dm(user_id):
    other = db.session.get(User, user_id)

    if not other or other.id == current_user.id:
        abort(404)

    if request.method == 'POST':
        body = request.form.get('body', '').strip()

        try:
            image_path = save_image(request.files.get('image'))

            if (body or image_path) and len(body) <= 1000:
                message = PrivateMessage(
                    sender_id=current_user.id,
                    recipient_id=other.id,
                    body=body,
                    image_path=image_path
                )
                db.session.add(message)
                db.session.commit()
            else:
                flash(
                    'Ajoute un texte ou une image '
                    '(texte limité à 1000 caractères).',
                    'error'
                )

        except ValueError as exc:
            flash(str(exc), 'error')

        return redirect(url_for('dm', user_id=other.id))

    messages = PrivateMessage.query.filter(
        db.or_(
            db.and_(
                PrivateMessage.sender_id == current_user.id,
                PrivateMessage.recipient_id == other.id
            ),
            db.and_(
                PrivateMessage.sender_id == other.id,
                PrivateMessage.recipient_id == current_user.id
            )
        )
    ).order_by(PrivateMessage.created_at.asc()).all()

    return render_template('dm.html', other=other, messages=messages)


@app.route('/inbox')
@login_required
def inbox():
    rows = PrivateMessage.query.filter(
        db.or_(
            PrivateMessage.sender_id == current_user.id,
            PrivateMessage.recipient_id == current_user.id
        )
    ).order_by(PrivateMessage.created_at.desc()).all()

    people = {}

    for msg in rows:
        person = (
            msg.sender
            if msg.sender_id != current_user.id
            else msg.recipient
        )
        people.setdefault(person.id, person)

    return render_template('inbox.html', people=list(people.values()))


# =========================
# FIL D'ACTUALITÉ
# =========================

@app.route('/feed', methods=['GET', 'POST'])
def feed():
    if request.method == 'POST':
        if not current_user.is_authenticated:
            return redirect(url_for('login'))

        action = request.form.get('action', 'post')

        if action == 'comment':
            post_id = request.form.get('post_id', type=int)
            body = request.form.get('body', '').strip()
            post = db.session.get(Post, post_id) if post_id else None

            if post and body and len(body) <= 500:
                db.session.add(
                    PostComment(
                        post_id=post.id,
                        user_id=current_user.id,
                        body=body
                    )
                )
                db.session.commit()
            else:
                flash(
                    'Le commentaire doit contenir entre 1 et 500 caractères.',
                    'error'
                )

            return redirect(url_for('feed'))

        if action == 'like':
            post_id = request.form.get('post_id', type=int)
            post = db.session.get(Post, post_id) if post_id else None

            if post:
                existing = PostLike.query.filter_by(
                    post_id=post.id,
                    user_id=current_user.id
                ).first()

                if existing:
                    db.session.delete(existing)
                else:
                    db.session.add(
                        PostLike(
                            post_id=post.id,
                            user_id=current_user.id
                        )
                    )

                db.session.commit()

            return redirect(url_for('feed'))

        caption = request.form.get('caption', '').strip()[:1000]

        try:
            image_path = save_image(request.files.get('image'))

            if image_path:
                db.session.add(
                    Post(
                        user_id=current_user.id,
                        caption=caption,
                        image_path=image_path
                    )
                )
                db.session.commit()
                flash('Publication ajoutée.', 'success')
            else:
                flash('Choisis une photo à publier.', 'error')

        except ValueError as exc:
            flash(str(exc), 'error')

        return redirect(url_for('feed'))

    posts = Post.query.order_by(
        Post.created_at.desc()
    ).limit(100).all()

    post_data = []

    for post in posts:
        post_data.append({
            'post': post,
            'likes': PostLike.query.filter_by(
                post_id=post.id
            ).count(),
            'liked': bool(
                current_user.is_authenticated
                and PostLike.query.filter_by(
                    post_id=post.id,
                    user_id=current_user.id
                ).first()
            ),
            'comments': PostComment.query.filter_by(
                post_id=post.id
            ).order_by(
                PostComment.created_at.asc()
            ).limit(100).all()
        })

    return render_template('feed.html', posts=post_data)


# =========================
# ÉQUIPES
# =========================

@app.route('/teams', methods=['GET', 'POST'])
def teams():
    if request.method == 'POST':
        if not current_user.is_authenticated:
            return redirect(url_for('login'))

        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if 3 <= len(name) <= 50:
            team = Team(
                name=name,
                description=description[:250],
                owner_id=current_user.id
            )
            db.session.add(team)
            db.session.commit()

            flash('Équipe créée.', 'success')
            return redirect(url_for('teams'))

        flash(
            'Le nom de l’équipe doit contenir au moins 3 caractères.',
            'error'
        )

    all_teams = Team.query.order_by(
        Team.created_at.desc()
    ).all()

    return render_template('teams.html', teams=all_teams)


# =========================
# CLASSEMENT
# =========================

@app.route('/leaderboard')
def leaderboard():
    users = User.query.all()
    scores = []

    for user in users:
        score = (
            PublicMessage.query.filter_by(user_id=user.id).count()
            + PrivateMessage.query.filter_by(sender_id=user.id).count() * 2
            + Team.query.filter_by(owner_id=user.id).count() * 3
        )
        scores.append((user, score))

    scores.sort(key=lambda item: item[1], reverse=True)

    return render_template('leaderboard.html', scores=scores[:50])


# =========================
# ADMINISTRATION
# =========================

@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id', type=int)
        user = db.session.get(User, user_id) if user_id else None

        if action == 'promote' and user:
            user.is_admin = True
            db.session.commit()
            flash(f'{user.username} est maintenant admin.', 'success')

        elif action == 'demote' and user and user.id != current_user.id:
            user.is_admin = False
            db.session.commit()
            flash(f'Rôle admin retiré à {user.username}.', 'success')

        elif action == 'delete_message':
            msg = db.session.get(PublicMessage, user_id)

            if msg:
                db.session.delete(msg)
                db.session.commit()
                flash('Message supprimé.', 'success')

        return redirect(url_for('admin'))

    users = User.query.order_by(User.joined_at.desc()).all()
    messages = PublicMessage.query.order_by(
        PublicMessage.created_at.desc()
    ).limit(30).all()

    return render_template(
        'admin.html',
        users=users,
        messages=messages
    )


# =========================
# ERREURS HTTP
# =========================

@app.errorhandler(403)
def forbidden(_):
    return render_template(
        'error.html',
        code=403,
        message='Accès réservé aux administrateurs.'
    ), 403


@app.errorhandler(404)
def not_found(_):
    return render_template(
        'error.html',
        code=404,
        message='Cette page est introuvable.'
    ), 404


# =========================
# MIGRATION DE LA BASE
# =========================

with app.app_context():
    db.create_all()

    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    additions = {
        'user': {
            'profile_image': "VARCHAR(500) DEFAULT ''"
        },
        'public_message': {
            'image_path': "VARCHAR(500) DEFAULT ''",
            'body': "VARCHAR(500) NOT NULL DEFAULT ''"
        },
        'private_message': {
            'image_path': "VARCHAR(500) DEFAULT ''",
            'body': "VARCHAR(1000) NOT NULL DEFAULT ''"
        }
    }

    for table, columns in additions.items():
        if table not in existing_tables:
            continue

        existing_columns = {
            column['name']
            for column in inspect(db.engine).get_columns(table)
        }

        for column, sql_type in columns.items():
            if column not in existing_columns:
                # Important : "user" est un mot réservé dans PostgreSQL.
                # Les guillemets évitent l'erreur de syntaxe.
                quoted_table = f'"{table}"'

                with db.engine.begin() as connection:
                    connection.execute(
                        text(
                            f'ALTER TABLE {quoted_table} '
                            f'ADD COLUMN {column} {sql_type}'
                        )
                    )

    # Création facultative du premier administrateur via Render.
    admin_name = os.environ.get('ADMIN_USERNAME', '').strip()
    admin_password = os.environ.get('ADMIN_PASSWORD', '')

    if (
        admin_name
        and admin_password
        and not User.query.filter_by(username=admin_name).first()
    ):
        admin_user = User(
            username=admin_name,
            password_hash=generate_password_hash(admin_password),
            is_admin=True
        )
        db.session.add(admin_user)
        db.session.commit()


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=False
    )
