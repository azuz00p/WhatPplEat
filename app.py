import os
import random
import sqlite3
import hashlib
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort, make_response

app = Flask(__name__)
secret_key = 'vU4zdDK7anhhRdNpEFJApoReVQDPXwRk1vZKcSKQtsWGwZGOP9EpE9DFWXJEJsXRRtB4f957FZztNudPto8wdyg617qOJc7NxzZ9'
app.config['SECRET_KEY'] = secret_key
app.config['RECIPES_FOLDER'] = 'recipes'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['RECIPES_FOLDER'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


def migrate_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(recipes)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'preparation_time' not in columns:
        print("Добавление колонки preparation_time в таблицу recipes...")
        cursor.execute("ALTER TABLE recipes ADD COLUMN preparation_time INTEGER DEFAULT 0")
        conn.commit()
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [column[1] for column in cursor.fetchall()]
    if 'role' not in user_columns:
        print("Добавление колонки role в таблицу users...")
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        conn.commit()
    conn.close()


def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user'
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        preparation_time INTEGER DEFAULT 0,
        is_private INTEGER DEFAULT 0,
        file_path TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        share_token TEXT UNIQUE,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    conn.commit()
    conn.close()
    migrate_db()


init_db()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def check_password(password, hash_val):
    return hash_password(password) == hash_val


users_session = {}


def get_current_user():
    user_id = request.cookies.get('user_id')
    if user_id and user_id in users_session:
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        return user
    return None


def login_user(user):
    user_id = str(user['id'])
    session_token = hashlib.sha256(f"{user_id}{datetime.now().isoformat()}".encode()).hexdigest()
    users_session[user_id] = session_token
    return user_id


def logout_user():
    user_id = request.cookies.get('user_id')
    if user_id and user_id in users_session:
        del users_session[user_id]


def login_required(f):
    def wrapper(*args, **kwargs):
        if not get_current_user():
            flash('Please login to access this page', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


def moderator_required(f):
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or user['role'] not in ['moderator', 'creator']:
            abort(403)
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


def creator_required(f):
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or user['role'] != 'creator':
            abort(403)
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


@app.context_processor
def context_processor():
    lang = request.cookies.get('lang', 'ru')
    theme = request.cookies.get('theme', 'light')
    user = get_current_user()
    return dict(lang=lang, theme=theme, current_user=user)


def get_categories(lang='ru'):
    if lang == 'ru':
        return ['Завтрак', 'Обед', 'Ужин', 'Десерт', 'Напиток', 'Другое']
    else:
        return ['Breakfast', 'Lunch', 'Dinner', 'Dessert', 'Drink', 'Other']


def get_role_name(role, lang='ru'):
    roles = {
        'user': ('⬛ Простой пользователь', '⬛ Regular User'),
        'active': ('🟨 Активный пользователь', '🟨 Active User'),
        'moderator': ('🛑 Модератор', '🛑 Moderator'),
        'creator': ('👨‍💻 Создатель', '👨‍💻 Creator'),
        'banned': ('⛔ Заблокирован', '⛔ Banned')
    }
    return roles.get(role, ('⬛ Простой пользователь', '⬛ Regular User'))[0 if lang == 'ru' else 1]


def get_text(key, lang):
    texts = {
        'ru': {
            'title': 'ЧёЕдят',
            'welcome': 'Добро пожаловать в ЧёЕдят!',
            'login': 'Вход',
            'logout': 'Выход',
            'register': 'Регистрация',
            'new_recipe': 'Новый рецепт',
            'search': 'Поиск',
            'what_ppl_eat': 'ЧёЕдят™',
            'random_recipe': 'Случайный рецепт',
            'public_recipes': 'Публичные рецепты',
            'profile': 'Профиль',
            'share': 'Поделиться',
            'download': 'Скачать',
            'private': 'Приватный',
            'category': 'Категория',
            'username': 'Имя пользователя',
            'password': 'Пароль',
            'title_label': 'Название блюда',
            'ingredients_label': 'Ингредиенты',
            'instructions_label': 'Способ приготовления',
            'private_label': 'Сделать рецепт приватным',
            'publish': 'Опубликовать рецепт',
            'view': 'Просмотр',
            'delete': 'Удалить',
            'copy': 'Копировать',
            'copy_link': 'Копировать ссылку',
            'link_copied': 'Ссылка скопирована!',
            'delete_confirm': 'Удалить этот рецепт?',
            'no_recipes': 'Нет опубликованных рецептов.',
            'no_user_recipes': 'У пользователя нет рецептов.',
            'search_results': 'Результаты поиска',
            'all_categories': 'Все категории',
            'choose_category': 'Выберите категорию',
            'random_category': 'Случайная категория',
            'select_category': '-- Выберите категорию --',
            'recipe_deleted': 'Рецепт успешно удалён!',
            'recipe_published': 'Рецепт опубликован!',
            'registration_success': 'Регистрация успешна! Теперь войдите.',
            'login_success': 'Добро пожаловать!',
            'username_exists': 'Имя пользователя уже существует',
            'invalid_credentials': 'Неверное имя пользователя или пароль',
            'private_recipe': 'Приватный рецепт',
            'share_link': 'Ссылка для доступа',
            'author': 'Автор',
            'import_recipe': 'Импортировать рецепт из файла',
            'choose_file': 'Выберите файл рецепта',
            'import': 'Импортировать',
            'invalid_format': 'Неверный формат файла',
            'fill_form': 'Импортированные данные:',
            'preparation_time': 'Время приготовления',
            'minutes': 'минут',
            'recipes_count': 'Опубликовано рецептов',
            'role': 'Статус',
            'change_role': 'Изменить статус',
            'role_changed': 'Статус успешно изменён!',
            'cant_change_yourself': 'Вы не можете изменить статус самому себе',
            'delete_recipe_confirm': 'Вы уверены, что хотите удалить этот рецепт?',
            'user_search': 'Поиск пользователей',
            'search_users': 'Найти пользователя',
            'users_list': 'Список пользователей',
            'banned_cant_publish': 'Ваш аккаунт заблокирован. Вы не можете публиковать рецепты.',
            'search_by_title': 'Поиск по названию',
            'search_by_author': 'Поиск по автору',
            'enter_title': 'Введите название',
            'enter_author': 'Введите имя автора'
        },
        'en': {
            'title': 'WhatPplEat',
            'welcome': 'Welcome to WhatPplEat!',
            'login': 'Login',
            'logout': 'Logout',
            'register': 'Register',
            'new_recipe': 'New recipe',
            'search': 'Search',
            'what_ppl_eat': 'WhatPplEat™',
            'random_recipe': 'Random recipe',
            'public_recipes': 'Public recipes',
            'profile': 'Profile',
            'share': 'Share',
            'download': 'Download',
            'private': 'Private',
            'category': 'Category',
            'username': 'Username',
            'password': 'Password',
            'title_label': 'Dish name',
            'ingredients_label': 'Ingredients',
            'instructions_label': 'Instructions',
            'private_label': 'Make recipe private',
            'publish': 'Publish recipe',
            'view': 'View',
            'delete': 'Delete',
            'copy': 'Copy',
            'copy_link': 'Copy link',
            'link_copied': 'Link copied!',
            'delete_confirm': 'Delete this recipe?',
            'no_recipes': 'No published recipes.',
            'no_user_recipes': 'User has no recipes.',
            'search_results': 'Search results',
            'all_categories': 'All categories',
            'choose_category': 'Choose category',
            'random_category': 'Random category',
            'select_category': '-- Choose category --',
            'recipe_deleted': 'Recipe deleted successfully!',
            'recipe_published': 'Recipe published!',
            'registration_success': 'Registration successful! Please login.',
            'login_success': 'Welcome back!',
            'username_exists': 'Username already exists',
            'invalid_credentials': 'Invalid username or password',
            'private_recipe': 'Private recipe',
            'share_link': 'Share link',
            'author': 'Author',
            'import_recipe': 'Import recipe from file',
            'choose_file': 'Choose recipe file',
            'import': 'Import',
            'invalid_format': 'Invalid file format',
            'fill_form': 'Imported data:',
            'preparation_time': 'Preparation time',
            'minutes': 'minutes',
            'recipes_count': 'Recipes published',
            'role': 'Status',
            'change_role': 'Change status',
            'role_changed': 'Status changed successfully!',
            'cant_change_yourself': 'You cannot change your own status',
            'delete_recipe_confirm': 'Are you sure you want to delete this recipe?',
            'user_search': 'User Search',
            'search_users': 'Search users',
            'users_list': 'Users list',
            'banned_cant_publish': 'Your account is banned. You cannot publish recipes.',
            'search_by_title': 'Search by title',
            'search_by_author': 'Search by author',
            'enter_title': 'Enter title',
            'enter_author': 'Enter author name'
        }
    }
    return texts[lang].get(key, key)


def parse_recipe_file(file_path, lang):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    title_ru = re.search(r'РЕЦЕПТ:\s*(.+?)(?=\n|$)', content, re.IGNORECASE)
    category_ru = re.search(r'Категория:\s*(.+?)(?=\n|$)', content, re.IGNORECASE)
    time_ru = re.search(r'Время приготовления:\s*(\d+)\s*минут', content, re.IGNORECASE)
    ingredients_ru = re.search(r'ИНГРЕДИЕНТЫ:\s*-{20,}\s*(.+?)(?=ИНСТРУКЦИЯ|\Z)', content, re.IGNORECASE | re.DOTALL)
    instructions_ru = re.search(r'ИНСТРУКЦИЯ ПРИГОТОВЛЕНИЯ:\s*-{30,}\s*(.+?)(?=Экспортировано|\Z)', content,
                                re.IGNORECASE | re.DOTALL)
    title_en = re.search(r'RECIPE:\s*(.+?)(?=\n|$)', content, re.IGNORECASE)
    category_en = re.search(r'Category:\s*(.+?)(?=\n|$)', content, re.IGNORECASE)
    time_en = re.search(r'Preparation time:\s*(\d+)\s*minutes', content, re.IGNORECASE)
    ingredients_en = re.search(r'INGREDIENTS:\s*-{20,}\s*(.+?)(?=COOKING INSTRUCTIONS|\Z)', content,
                               re.IGNORECASE | re.DOTALL)
    instructions_en = re.search(r'COOKING INSTRUCTIONS:\s*-{30,}\s*(.+?)(?=Exported|\Z)', content,
                                re.IGNORECASE | re.DOTALL)
    title = title_ru.group(1).strip() if title_ru else (title_en.group(1).strip() if title_en else None)
    category = category_ru.group(1).strip() if category_ru else (category_en.group(1).strip() if category_en else None)
    preparation_time = time_ru.group(1).strip() if time_ru else (time_en.group(1).strip() if time_en else None)
    ingredients = ingredients_ru.group(1).strip() if ingredients_ru else (
        ingredients_en.group(1).strip() if ingredients_en else None)
    instructions = instructions_ru.group(1).strip() if instructions_ru else (
        instructions_en.group(1).strip() if instructions_en else None)
    if not (title and category and ingredients and instructions):
        return None
    return {
        'title': title,
        'category': category,
        'preparation_time': int(preparation_time) if preparation_time and preparation_time.isdigit() else 30,
        'ingredients': ingredients,
        'instructions': instructions
    }


def format_recipe_content(title, category, preparation_time, ingredients, instructions, lang):
    if lang == 'ru':
        return f"""==================================================
РЕЦЕПТ: {title}
==================================================
Категория: {category}
Время приготовления: {preparation_time} минут

ИНГРЕДИЕНТЫ:
--------------------
{ingredients}

ИНСТРУКЦИЯ ПРИГОТОВЛЕНИЯ:
------------------------------
{instructions}

Экспортировано из ЧёПоесть: https://github.com/azuz00p/WhatTheEat"""
    else:
        return f"""==================================================
RECIPE: {title}
==================================================
Category: {category}
Preparation time: {preparation_time} minutes

INGREDIENTS:
--------------------
{ingredients}

COOKING INSTRUCTIONS:
------------------------------
{instructions}

Exported from WhatTheEat: https://github.com/azuz00p/WhatTheEat"""


@app.route('/')
def index():
    lang = request.cookies.get('lang', 'ru')
    conn = get_db()
    recent_recipes = conn.execute(
        'SELECT recipes.*, users.username as author_name FROM recipes LEFT JOIN users ON recipes.user_id = users.id WHERE recipes.is_private = 0 ORDER BY recipes.id DESC LIMIT 10'
    ).fetchall()
    conn.close()
    return render_template('index.html', recipes=recent_recipes, get_text=get_text, lang=lang,
                           get_categories=get_categories)


@app.route('/register', methods=['GET', 'POST'])
def register():
    lang = request.cookies.get('lang', 'ru')
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db()
        existing = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if existing:
            flash(get_text('username_exists', lang), 'danger')
            conn.close()
            return redirect(url_for('register'))
        password_hash = hash_password(password)
        conn.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                     (username, password_hash, 'user'))
        conn.commit()
        conn.close()
        flash(get_text('registration_success', lang), 'success')
        return redirect(url_for('login'))
    return render_template('register.html', get_text=get_text, lang=lang)


@app.route('/login', methods=['GET', 'POST'])
def login():
    lang = request.cookies.get('lang', 'ru')
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password(password, user['password_hash']):
            user_id = login_user(user)
            resp = make_response(redirect(url_for('index')))
            resp.set_cookie('user_id', user_id)
            flash(get_text('login_success', lang), 'success')
            return resp
        flash(get_text('invalid_credentials', lang), 'danger')
    return render_template('login.html', get_text=get_text, lang=lang)


@app.route('/logout')
def logout():
    logout_user()
    resp = make_response(redirect(url_for('index')))
    resp.set_cookie('user_id', '', expires=0)
    return resp


@app.route('/profile/<int:user_id>')
def profile(user_id):
    lang = request.cookies.get('lang', 'ru')
    current_user_obj = get_current_user()
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        abort(404)
    if current_user_obj and current_user_obj['id'] == user_id:
        recipes = conn.execute('SELECT * FROM recipes WHERE user_id = ? ORDER BY id DESC', (user_id,)).fetchall()
    else:
        recipes = conn.execute('SELECT * FROM recipes WHERE user_id = ? AND is_private = 0 ORDER BY id DESC',
                               (user_id,)).fetchall()
    recipes_count = len(recipes)
    conn.close()
    return render_template('profile.html', profile_user=user, recipes=recipes, recipes_count=recipes_count,
                           get_text=get_text, lang=lang, get_role_name=get_role_name)


@app.route('/users')
@moderator_required
def users_list():
    lang = request.cookies.get('lang', 'ru')
    search = request.args.get('search', '')
    conn = get_db()
    if search:
        users = conn.execute('SELECT * FROM users WHERE username LIKE ? ORDER BY id', (f'%{search}%',)).fetchall()
    else:
        users = conn.execute('SELECT * FROM users ORDER BY id').fetchall()
    conn.close()
    return render_template('users.html', users=users, search=search, get_text=get_text, lang=lang,
                           get_role_name=get_role_name)


@app.route('/change_role/<int:user_id>', methods=['POST'])
@login_required
def change_role(user_id):
    lang = request.cookies.get('lang', 'ru')
    current_user_obj = get_current_user()
    if current_user_obj['id'] == user_id:
        flash(get_text('cant_change_yourself', lang), 'danger')
        return redirect(request.referrer or url_for('index'))
    new_role = request.form.get('role')
    allowed_roles = ['banned', 'user', 'active', 'moderator', 'creator']
    if new_role not in allowed_roles:
        abort(400)
    conn = get_db()
    target_user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not target_user:
        conn.close()
        abort(404)
    if current_user_obj['role'] == 'creator':
        conn.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
        conn.commit()
        flash(get_text('role_changed', lang), 'success')
    elif current_user_obj['role'] == 'moderator':
        if new_role in ['banned', 'user', 'active']:
            conn.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
            conn.commit()
            flash(get_text('role_changed', lang), 'success')
        else:
            flash('У вас нет прав для назначения этого статуса', 'danger')
    else:
        abort(403)
    conn.close()
    return redirect(request.referrer or url_for('index'))


@app.route('/new_recipe', methods=['GET', 'POST'])
@login_required
def new_recipe():
    lang = request.cookies.get('lang', 'ru')
    current_user_obj = get_current_user()
    if current_user_obj['role'] == 'banned':
        flash(get_text('banned_cant_publish', lang), 'danger')
        return redirect(url_for('index'))
    categories = get_categories(lang)
    imported_data = None
    if request.method == 'POST' and 'import_file' in request.files:
        file = request.files['import_file']
        if file and file.filename.endswith('.txt'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            imported_data = parse_recipe_file(filepath, lang)
            os.remove(filepath)
            if not imported_data:
                flash(get_text('invalid_format', lang), 'danger')
            else:
                flash(get_text('fill_form', lang), 'success')
    if request.method == 'POST' and 'publish' in request.form:
        title = request.form.get('title')
        category = request.form.get('category')
        preparation_time = request.form.get('preparation_time', 30)
        is_private = request.form.get('is_private') == 'on'
        ingredients = request.form.get('ingredients')
        instructions = request.form.get('instructions')
        try:
            preparation_time = int(preparation_time)
        except ValueError:
            preparation_time = 30
        full_content = format_recipe_content(title, category, preparation_time, ingredients, instructions, lang)
        filename = f"{datetime.now().timestamp()}_{title.replace(' ', '_')}.txt"
        file_path = os.path.join(app.config['RECIPES_FOLDER'], filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(full_content)
        share_token = None
        if is_private:
            share_token = hashlib.sha256(f"{title}{datetime.now().isoformat()}".encode()).hexdigest()[:32]
        conn = get_db()
        conn.execute('''INSERT INTO recipes (title, category, preparation_time, is_private, file_path, user_id, share_token)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (title, category, preparation_time, int(is_private), file_path, int(current_user_obj['id']),
                      share_token))
        conn.commit()
        conn.close()
        flash(get_text('recipe_published', lang), 'success')
        return redirect(url_for('index'))
    return render_template('new_recipe.html', categories=categories, imported_data=imported_data,
                           get_text=get_text, lang=lang)


@app.route('/recipe/<int:recipe_id>')
def view_recipe(recipe_id):
    lang = request.cookies.get('lang', 'ru')
    conn = get_db()
    recipe = conn.execute(
        'SELECT recipes.*, users.username as author_name FROM recipes LEFT JOIN users ON recipes.user_id = users.id WHERE recipes.id = ?',
        (recipe_id,)).fetchone()
    if not recipe:
        abort(404)
    current_user_obj = get_current_user()
    if recipe['is_private'] and (not current_user_obj or recipe['user_id'] != current_user_obj['id']):
        abort(403)
    with open(recipe['file_path'], 'r', encoding='utf-8') as f:
        content = f.read()
    title_match = re.search(r'(?:РЕЦЕПТ:|RECIPE:)\s*(.+?)(?=\n|$)', content, re.IGNORECASE)
    category_match = re.search(r'(?:Категория:|Category:)\s*(.+?)(?=\n|$)', content, re.IGNORECASE)
    time_match = re.search(r'(?:Время приготовления:|Preparation time:)\s*(\d+)\s*(?:минут|minutes)', content,
                           re.IGNORECASE)
    ingredients_match = re.search(
        r'(?:ИНГРЕДИЕНТЫ:|INGREDIENTS:)\s*-{20,}\s*(.+?)(?=(?:ИНСТРУКЦИЯ|COOKING INSTRUCTIONS)|\Z)', content,
        re.IGNORECASE | re.DOTALL)
    instructions_match = re.search(
        r'(?:ИНСТРУКЦИЯ ПРИГОТОВЛЕНИЯ:|COOKING INSTRUCTIONS:)\s*-{30,}\s*(.+?)(?=(?:Экспортировано|Exported)|\Z)',
        content, re.IGNORECASE | re.DOTALL)
    parsed_recipe = {
        'title': title_match.group(1).strip() if title_match else recipe['title'],
        'category': category_match.group(1).strip() if category_match else recipe['category'],
        'preparation_time': time_match.group(1).strip() if time_match else recipe['preparation_time'],
        'ingredients': ingredients_match.group(1).strip() if ingredients_match else '',
        'instructions': instructions_match.group(1).strip() if instructions_match else ''
    }
    author = conn.execute('SELECT * FROM users WHERE id = ?', (recipe['user_id'],)).fetchone()
    conn.close()
    return render_template('recipe.html', recipe=recipe, parsed=parsed_recipe,
                           author=author, content=content, get_text=get_text, lang=lang, get_role_name=get_role_name)


@app.route('/share/<token>')
def share_recipe(token):
    lang = request.cookies.get('lang', 'ru')
    conn = get_db()
    recipe = conn.execute(
        'SELECT recipes.*, users.username as author_name FROM recipes LEFT JOIN users ON recipes.user_id = users.id WHERE recipes.share_token = ?',
        (token,)).fetchone()
    if not recipe:
        abort(404)
    with open(recipe['file_path'], 'r', encoding='utf-8') as f:
        content = f.read()
    title_match = re.search(r'(?:РЕЦЕПТ:|RECIPE:)\s*(.+?)(?=\n|$)', content, re.IGNORECASE)
    category_match = re.search(r'(?:Категория:|Category:)\s*(.+?)(?=\n|$)', content, re.IGNORECASE)
    time_match = re.search(r'(?:Время приготовления:|Preparation time:)\s*(\d+)\s*(?:минут|minutes)', content,
                           re.IGNORECASE)
    ingredients_match = re.search(
        r'(?:ИНГРЕДИЕНТЫ:|INGREDIENTS:)\s*-{20,}\s*(.+?)(?=(?:ИНСТРУКЦИЯ|COOKING INSTRUCTIONS)|\Z)', content,
        re.IGNORECASE | re.DOTALL)
    instructions_match = re.search(
        r'(?:ИНСТРУКЦИЯ ПРИГОТОВЛЕНИЯ:|COOKING INSTRUCTIONS:)\s*-{30,}\s*(.+?)(?=(?:Экспортировано|Exported)|\Z)',
        content, re.IGNORECASE | re.DOTALL)
    parsed_recipe = {
        'title': title_match.group(1).strip() if title_match else recipe['title'],
        'category': category_match.group(1).strip() if category_match else recipe['category'],
        'preparation_time': time_match.group(1).strip() if time_match else recipe['preparation_time'],
        'ingredients': ingredients_match.group(1).strip() if ingredients_match else '',
        'instructions': instructions_match.group(1).strip() if instructions_match else ''
    }
    author = conn.execute('SELECT * FROM users WHERE id = ?', (recipe['user_id'],)).fetchone()
    conn.close()
    return render_template('recipe.html', recipe=recipe, parsed=parsed_recipe,
                           author=author, content=content, get_text=get_text, lang=lang, get_role_name=get_role_name)


@app.route('/download/<int:recipe_id>')
def download_recipe(recipe_id):
    conn = get_db()
    recipe = conn.execute('SELECT * FROM recipes WHERE id = ?', (recipe_id,)).fetchone()
    conn.close()
    if not recipe:
        abort(404)
    current_user_obj = get_current_user()
    if recipe['is_private'] and (not current_user_obj or recipe['user_id'] != current_user_obj['id']):
        abort(403)
    return send_file(recipe['file_path'], as_attachment=True, download_name=f"{recipe['title']}.txt")


@app.route('/delete_recipe/<int:recipe_id>', methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    lang = request.cookies.get('lang', 'ru')
    current_user_obj = get_current_user()
    conn = get_db()
    recipe = conn.execute('SELECT * FROM recipes WHERE id = ?', (recipe_id,)).fetchone()
    if not recipe:
        conn.close()
        flash('Рецепт не найден', 'danger')
        return redirect(url_for('index'))
    can_delete = False
    if current_user_obj['id'] == recipe['user_id']:
        can_delete = True
    elif current_user_obj['role'] == 'creator':
        can_delete = True
    elif current_user_obj['role'] == 'moderator' and not recipe['is_private']:
        can_delete = True
    if not can_delete:
        conn.close()
        abort(403)
    if os.path.exists(recipe['file_path']):
        os.remove(recipe['file_path'])
    conn.execute('DELETE FROM recipes WHERE id = ?', (recipe_id,))
    conn.commit()
    conn.close()
    flash(get_text('recipe_deleted', lang), 'success')
    referer = request.referrer
    if referer:
        if '/recipe/' in referer:
            return redirect(url_for('index'))
        elif '/profile/' in referer or '/search' in referer or '/users' in referer:
            return redirect(referer)
    return redirect(url_for('index'))


@app.route('/search', methods=['GET'])
def search():
    lang = request.cookies.get('lang', 'ru')
    category = request.args.get('category')
    search_title = request.args.get('search_title', '')
    search_author = request.args.get('search_author', '')
    conn = get_db()
    query = 'SELECT recipes.*, users.username as author_name FROM recipes LEFT JOIN users ON recipes.user_id = users.id WHERE recipes.is_private = 0'
    params = []
    if category and category != get_text('all_categories', lang):
        query += ' AND recipes.category = ?'
        params.append(category)
    if search_title:
        query += ' AND recipes.title LIKE ?'
        params.append(f'%{search_title}%')
    if search_author:
        query += ' AND users.username LIKE ?'
        params.append(f'%{search_author}%')
    recipes = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('search.html', recipes=recipes, get_text=get_text, lang=lang,
                           get_categories=get_categories, search_title=search_title, search_author=search_author)


@app.route('/what_ppl_eat', methods=['GET', 'POST'])
def what_ppl_eat():
    lang = request.cookies.get('lang', 'ru')
    categories = get_categories(lang)
    recipe = None
    content = None
    parsed_recipe = None
    selected_category = None
    if request.method == 'POST':
        category_choice = request.form.get('category')
        if category_choice == 'random':
            selected_category = random.choice(categories)
        else:
            selected_category = category_choice
        conn = get_db()
        recipes = conn.execute(
            'SELECT recipes.*, users.username as author_name FROM recipes LEFT JOIN users ON recipes.user_id = users.id WHERE recipes.is_private = 0 AND recipes.category = ?',
            (selected_category,)).fetchall()
        conn.close()
        if recipes:
            recipe = random.choice(recipes)
            with open(recipe['file_path'], 'r', encoding='utf-8') as f:
                content = f.read()
            title_match = re.search(r'(?:РЕЦЕПТ:|RECIPE:)\s*(.+?)(?=\n|$)', content, re.IGNORECASE)
            category_match = re.search(r'(?:Категория:|Category:)\s*(.+?)(?=\n|$)', content, re.IGNORECASE)
            time_match = re.search(r'(?:Время приготовления:|Preparation time:)\s*(\d+)\s*(?:минут|minutes)', content,
                                   re.IGNORECASE)
            ingredients_match = re.search(
                r'(?:ИНГРЕДИЕНТЫ:|INGREDIENTS:)\s*-{20,}\s*(.+?)(?=(?:ИНСТРУКЦИЯ|COOKING INSTRUCTIONS)|\Z)', content,
                re.IGNORECASE | re.DOTALL)
            instructions_match = re.search(
                r'(?:ИНСТРУКЦИЯ ПРИГОТОВЛЕНИЯ:|COOKING INSTRUCTIONS:)\s*-{30,}\s*(.+?)(?=(?:Экспортировано|Exported)|\Z)',
                content, re.IGNORECASE | re.DOTALL)
            parsed_recipe = {
                'title': title_match.group(1).strip() if title_match else recipe['title'],
                'category': category_match.group(1).strip() if category_match else recipe['category'],
                'preparation_time': time_match.group(1).strip() if time_match else recipe['preparation_time'],
                'ingredients': ingredients_match.group(1).strip() if ingredients_match else '',
                'instructions': instructions_match.group(1).strip() if instructions_match else ''
            }
        else:
            flash(get_text('no_recipes', lang), 'warning')
    return render_template('what_ppl_eat.html', recipe=recipe, parsed=parsed_recipe, content=content,
                           selected_category=selected_category, categories=categories,
                           get_text=get_text, lang=lang)


@app.route('/set_lang')
def set_lang():
    current_lang = request.cookies.get('lang', 'ru')
    new_lang = 'en' if current_lang == 'ru' else 'ru'
    resp = make_response(redirect(request.referrer or url_for('index')))
    resp.set_cookie('lang', new_lang)
    return resp


@app.route('/set_theme')
def set_theme():
    current_theme = request.cookies.get('theme', 'light')
    new_theme = 'dark' if current_theme == 'light' else 'light'
    resp = make_response(redirect(request.referrer or url_for('index')))
    resp.set_cookie('theme', new_theme)
    return resp


if __name__ == '__main__':
    app.run(debug=False)