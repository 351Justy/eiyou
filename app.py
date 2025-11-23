from flask import Flask, render_template, request, jsonify, session
import os
import json
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
import re

# anthropicはオプショナル（AIマッチング機能を使う場合のみ必要）
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("警告: anthropicモジュールが見つかりません。AI検索機能は無効です。")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# 環境変数から設定を取得
CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'admin123')

# 目標摂取量の定義
DAILY_TARGETS = {
    'エネルギー': 2700,
    'たんぱく質': 70,
    '脂質': 62,
    '食物繊維総量': 22,
    'カリウム': 2500,
    'カルシウム': 750,
    'マグネシウム': 370,
    'リン': 1000,
    '鉄': 7.5,
    '亜鉛': 11,
    '銅': 0.9,
    'マンガン': 4,
    'ヨウ素': 130,
    'セレン': 30,
    'クロム': 10,
    'モリブデン': 30,
    'ビタミンA': 600,
    'ビタミンD': 8.5,
    'ビタミンE': 7,
    'ビタミンK': 150,
    'ビタミンB1': 1.4,
    'ビタミンB2': 1.6,
    'ナイアシン': 17,
    'ビタミンB6': 1.4,
    'ビタミンB12': 2.4,
    '葉酸': 240,
    'パントテン酸': 5,
    'ビオチン': 50,
    'ビタミンC': 100,
    '食塩相当量': 1.5
}

# データベース初期化
def init_db():
    """データベースを初期化"""
    conn = sqlite3.connect('nutrition.db')
    c = conn.cursor()
    
    # 食事テーブル
    c.execute('''CREATE TABLE IF NOT EXISTS meals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  person_name TEXT NOT NULL,
                  meal_date DATE NOT NULL,
                  meal_time TIME NOT NULL,
                  raw_input TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # 食事項目テーブル
    c.execute('''CREATE TABLE IF NOT EXISTS meal_items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  meal_id INTEGER NOT NULL,
                  food_name TEXT NOT NULL,
                  weight REAL NOT NULL,
                  matched_food_name TEXT NOT NULL,
                  FOREIGN KEY (meal_id) REFERENCES meals (id))''')
    
    # 栄養素データテーブル
    c.execute('''CREATE TABLE IF NOT EXISTS meal_nutrients
                 (meal_id INTEGER PRIMARY KEY,
                  energy REAL,
                  protein REAL,
                  fat REAL,
                  fiber REAL,
                  potassium REAL,
                  calcium REAL,
                  magnesium REAL,
                  phosphorus REAL,
                  iron REAL,
                  zinc REAL,
                  copper REAL,
                  manganese REAL,
                  iodine REAL,
                  selenium REAL,
                  chromium REAL,
                  molybdenum REAL,
                  vitamin_a REAL,
                  vitamin_d REAL,
                  vitamin_e REAL,
                  vitamin_k REAL,
                  vitamin_b1 REAL,
                  vitamin_b2 REAL,
                  niacin REAL,
                  vitamin_b6 REAL,
                  vitamin_b12 REAL,
                  folate REAL,
                  pantothenic_acid REAL,
                  biotin REAL,
                  vitamin_c REAL,
                  salt REAL,
                  FOREIGN KEY (meal_id) REFERENCES meals (id))''')
    
    conn.commit()
    conn.close()

# 食品データベースをロード
def load_food_database():
    """食品データベースをロード"""
    with open('food_database.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# データベースとデータを初期化
init_db()
FOOD_DATABASE = load_food_database()

# パスワード認証デコレーター
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    """パスワード認証"""
    data = request.json
    password = data.get('password', '')
    
    if password == APP_PASSWORD:
        session['authenticated'] = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'パスワードが正しくありません'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    """ログアウト"""
    session.pop('authenticated', None)
    return jsonify({'success': True})

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    """認証状態をチェック"""
    return jsonify({'authenticated': session.get('authenticated', False)})

@app.route('/api/persons', methods=['GET'])
@login_required
def get_persons():
    """データベースに記録されている人物のリストを取得"""
    try:
        conn = sqlite3.connect('nutrition.db')
        c = conn.cursor()
        
        c.execute('''SELECT DISTINCT person_name FROM meals ORDER BY person_name''')
        rows = c.fetchall()
        conn.close()
        
        persons = [row[0] for row in rows]
        
        return jsonify({
            'success': True,
            'persons': persons
        })
        
    except Exception as e:
        return jsonify({'error': f'エラー: {str(e)}'}), 500

def parse_numeric_value(value):
    """栄養素の値を数値に変換"""
    if value is None or value == '' or value == '-':
        return 0.0
    
    # 文字列の場合
    if isinstance(value, str):
        # "Tr" (微量)は0として扱う
        if value.lower() in ['tr', 'trace', '(tr)', '-', '']:
            return 0.0
        
        # 括弧を削除
        value = value.replace('(', '').replace(')', '')
        
        try:
            return float(value)
        except:
            return 0.0
    
    # 数値の場合
    try:
        return float(value)
    except:
        return 0.0

def get_food_suggestions(food_input, available_foods, max_suggestions=5):
    """入力に対して候補を提案"""
    from difflib import SequenceMatcher
    
    input_normalized = normalize_text(food_input)
    suggestions = []
    
    # キーワードを含む食品を探す
    for food in available_foods:
        food_name = food['食品名']
        # キーワードが含まれているか
        if any(kw in food_name for kw in food_input.split()):
            ratio = SequenceMatcher(None, input_normalized, normalize_text(food_name)).ratio()
            suggestions.append((food_name, ratio))
    
    # スコアでソート
    suggestions.sort(key=lambda x: x[1], reverse=True)
    
    return [name for name, score in suggestions[:max_suggestions]]

def normalize_text(text):
    """テキストを正規化（全角・半角統一、空白除去）"""
    import unicodedata
    # 全角を半角に変換
    text = unicodedata.normalize('NFKC', text)
    # 余分な空白を削除
    text = ' '.join(text.split())
    return text.strip()

def fuzzy_match_food(food_input, available_foods, use_ai=False):
    """食品名をあいまい検索でマッチング
    
    レベル1: 完全一致
    レベル2: 正規化後の完全一致
    レベル3: 部分一致（キーワードベース）
    レベル4: 類似度マッチング
    レベル5 (オプション): Claude AIによるマッチング
    """
    
    input_normalized = normalize_text(food_input)
    
    # レベル1: 完全一致
    for food in available_foods:
        if food['食品名'] == food_input:
            return food['食品名']
    
    # レベル2: 正規化後の完全一致
    for food in available_foods:
        if normalize_text(food['食品名']) == input_normalized:
            return food['食品名']
    
    # レベル3: キーワードベースのマッチング
    # 入力からキーワードを抽出
    keywords = [w for w in input_normalized.replace('　', ' ').split() if len(w) > 0]
    
    # キーワードマッピング（一般的な呼び方 → データベースの表記）
    keyword_mappings = {
        # 穀類
        '納豆': '糸引き納豆',
        'ご飯': 'めし　精白米　うるち米',
        '白米': 'めし　精白米　うるち米',
        '玄米': 'めし　玄米',
        'パン': '食パン',
        
        # 卵類（鶏卵を優先）
        '生卵': '鶏卵　全卵　生',
        '卵': '鶏卵　全卵',
        'ゆで卵': '鶏卵　全卵　ゆで',
        '目玉焼き': '鶏卵　全卵　目玉焼き',
        
        # 肉類
        '鶏肉': 'にわとり　若どり',
        '鶏もも': 'にわとり　若どり　もも',
        '鶏もも肉': 'にわとり　若どり　もも',
        '鶏むね': 'にわとり　若どり　むね',
        '鶏むね肉': 'にわとり　若どり　むね',
        'ささみ': 'にわとり　ささみ',
        '豚肉': '豚　大型種肉',
        '豚バラ': '豚　大型種肉　ばら',
        '牛肉': '牛　和牛肉',
        
        # 魚介類
        'さんま': 'さんま　皮つき',
        '鮭': 'しろさけ',
        'さば': 'まさば',
        'まぐろ': 'まぐろ',
        
        # 野菜
        'ほうれん草': 'ほうれんそう',
        'ほうれんそう': 'ほうれんそう　葉',
        'キャベツ': 'キャベツ　結球葉',
        'レタス': 'レタス　土耕栽培　結球葉',
        '大根': 'だいこん　根',
        'にんじん': 'にんじん　根',
        'トマト': 'トマト　果実',
        'きゅうり': 'きゅうり　果実',
        'ブロッコリー': 'ブロッコリー　花序',
        
        # 豆腐・大豆製品
        '豆腐': '木綿豆腐',
        '絹豆腐': '絹ごし豆腐',
        '厚揚げ': '生揚げ',
        
        # 調味料
        '味噌': 'みそ　淡色辛みそ',
        '醤油': 'しょうゆ　濃口',
        'つゆ': 'めんつゆ',
        'みりん': 'みりん　本みりん',
        '砂糖': '砂糖　上白糖',
        '塩': '食塩',
        '酢': '米酢',
        '油': 'サラダ油',
    }
    
    # キーワードマッピングを適用
    expanded_keywords = []
    for kw in keywords:
        expanded_keywords.append(kw)
        if kw in keyword_mappings:
            expanded_keywords.extend(keyword_mappings[kw].split())
    
    # スコアリング: すべてのキーワードを含む食品を探す
    best_match = None
    best_score = 0
    
    for food in available_foods:
        food_name = food['食品名']
        score = 0
        
        # 各キーワードが含まれているかチェック
        for kw in expanded_keywords:
            if kw in food_name:
                score += 1
        
        # より多くのキーワードを含む食品を優先
        if score > best_score:
            best_score = score
            best_match = food_name
    
    # 少なくとも1つのキーワードがマッチした場合
    if best_score > 0:
        return best_match
    
    # レベル4: 類似度マッチング（difflib使用）
    from difflib import SequenceMatcher
    
    best_ratio = 0
    best_match = None
    
    for food in available_foods:
        ratio = SequenceMatcher(None, input_normalized, normalize_text(food['食品名'])).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = food['食品名']
    
    # 類似度が60%以上ならマッチとみなす
    if best_ratio >= 0.6:
        return best_match
    
    # レベル5: Claude AIによるマッチング（オプション）
    if use_ai and CLAUDE_API_KEY:
        try:
            ai_match = match_food_with_ai_fallback(food_input, available_foods)
            if ai_match:
                return ai_match
        except Exception as e:
            print(f"AI検索エラー（続行します）: {e}")
    
    return None

def match_food_with_deepseek(food_input, available_foods):
    """DeepSeek APIを使った高度なマッチング"""
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
    if not DEEPSEEK_API_KEY:
        return None
    
    try:
        import requests
        
        # 候補をいくつか絞り込む
        candidates = []
        for food in available_foods:
            if any(kw in food['食品名'] for kw in food_input.split()):
                candidates.append(food['食品名'])
        
        if not candidates:
            candidates = [f['食品名'] for f in available_foods[:100]]
        
        prompt = f"""入力: {food_input}

以下から最も適切な食品を1つ選んでください:
{chr(10).join(candidates[:50])}

選んだ食品名のみを回答してください（他の説明は不要）。"""
        
        response = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'deepseek-chat',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 100
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            matched = result['choices'][0]['message']['content'].strip()
            
            # マッチした食品がデータベースに存在するか確認
            for food in available_foods:
                if food['食品名'] == matched or matched in food['食品名']:
                    return food['食品名']
        
        return None
    except Exception as e:
        print(f"DeepSeek API検索エラー: {e}")
        return None

def match_food_with_ai_fallback(food_input, available_foods):
    """AIを使った高度なマッチング（フォールバック用）"""
    # まずDeepSeekを試す
    result = match_food_with_deepseek(food_input, available_foods)
    if result:
        return result
    
    # DeepSeekが使えない場合はClaudeを試す
    if not ANTHROPIC_AVAILABLE:
        print("AIモジュールが利用できません")
        return None
    
    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY, max_retries=2)
        
        # 候補をいくつか絞り込む
        candidates = []
        for food in available_foods:
            if any(kw in food['食品名'] for kw in food_input.split()):
                candidates.append(food['食品名'])
        
        if not candidates:
            candidates = [f['食品名'] for f in available_foods[:100]]
        
        prompt = f"""入力: {food_input}

以下から最も適切な食品を1つ選んでください:
{chr(10).join(candidates[:50])}

選んだ食品名のみを回答してください（他の説明は不要）。"""
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        
        matched = message.content[0].text.strip()
        
        # マッチした食品がデータベースに存在するか確認
        for food in available_foods:
            if food['食品名'] == matched or matched in food['食品名']:
                return food['食品名']
        
        return None
    except Exception as e:
        print(f"AI検索エラー: {e}")
        return None

@app.route('/api/calculate', methods=['POST'])
@login_required
def calculate_nutrition():
    """食事の栄養価を計算"""
    try:
        data = request.json
        person_name = data.get('person_name', '').strip()
        meal_date = data.get('meal_date', '')
        meal_time = data.get('meal_time', '')
        food_input = data.get('food_input', '').strip()
        
        if not person_name or not meal_date or not meal_time or not food_input:
            return jsonify({'error': '全ての項目を入力してください'}), 400
        
        # 食品入力をパース（例: 「納豆45g、ご飯160g、生卵60g」）
        items = [item.strip() for item in food_input.split('、') if item.strip()]
        
        parsed_items = []
        for item in items:
            # 重さを抽出（数字 + g）
            match = re.search(r'([^0-9]+)([\d.]+)\s*g', item)
            if match:
                food_name = match.group(1).strip()
                weight = float(match.group(2))
                parsed_items.append({'food_name': food_name, 'weight': weight})
        
        if not parsed_items:
            return jsonify({'error': '食品の形式が正しくありません（例: 納豆45g、ご飯160g）'}), 400
        
        # 食品名をあいまい検索でマッチング（DeepSeek AI使用）
        matched_items = []
        total_nutrients = {key: 0.0 for key in DAILY_TARGETS.keys()}
        
        for item in parsed_items:
            # DeepSeek AIを使用してマッチング
            matched_food_name = fuzzy_match_food(item['food_name'], FOOD_DATABASE, use_ai=True)
            
            if not matched_food_name:
                # 候補を提案
                suggestions = get_food_suggestions(item['food_name'], FOOD_DATABASE)
                suggestion_text = ''
                if suggestions:
                    suggestion_text = f' もしかして: {", ".join(suggestions[:3])}'
                return jsonify({'error': f'食品「{item["food_name"]}」が見つかりませんでした。{suggestion_text}'}), 400
            
            # 食品データを取得
            food_data = None
            for food in FOOD_DATABASE:
                if food['食品名'] == matched_food_name:
                    food_data = food
                    break
            
            if not food_data:
                return jsonify({'error': f'食品データが見つかりません: {matched_food_name}'}), 400
            
            # 栄養素を計算（100gあたりの値を重さで換算）
            weight_factor = item['weight'] / 100.0
            item_nutrients = {}
            
            for jp_name, target_value in DAILY_TARGETS.items():
                raw_value = food_data.get(jp_name, 0)
                numeric_value = parse_numeric_value(raw_value)
                calculated_value = numeric_value * weight_factor
                item_nutrients[jp_name] = calculated_value
                total_nutrients[jp_name] += calculated_value
            
            matched_items.append({
                'input_name': item['food_name'],
                'matched_name': matched_food_name,
                'weight': item['weight'],
                'nutrients': item_nutrients
            })
        
        # データベースに保存
        conn = sqlite3.connect('nutrition.db')
        c = conn.cursor()
        
        # 食事を保存
        c.execute('''INSERT INTO meals (person_name, meal_date, meal_time, raw_input)
                     VALUES (?, ?, ?, ?)''',
                  (person_name, meal_date, meal_time, food_input))
        meal_id = c.lastrowid
        
        # 食事項目を保存
        for item in matched_items:
            c.execute('''INSERT INTO meal_items (meal_id, food_name, weight, matched_food_name)
                         VALUES (?, ?, ?, ?)''',
                      (meal_id, item['input_name'], item['weight'], item['matched_name']))
        
        # 栄養素データを保存
        c.execute('''INSERT INTO meal_nutrients 
                     (meal_id, energy, protein, fat, fiber, potassium, calcium, magnesium, 
                      phosphorus, iron, zinc, copper, manganese, iodine, selenium, chromium, 
                      molybdenum, vitamin_a, vitamin_d, vitamin_e, vitamin_k, vitamin_b1, 
                      vitamin_b2, niacin, vitamin_b6, vitamin_b12, folate, pantothenic_acid, 
                      biotin, vitamin_c, salt)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (meal_id,
                   total_nutrients['エネルギー'],
                   total_nutrients['たんぱく質'],
                   total_nutrients['脂質'],
                   total_nutrients['食物繊維総量'],
                   total_nutrients['カリウム'],
                   total_nutrients['カルシウム'],
                   total_nutrients['マグネシウム'],
                   total_nutrients['リン'],
                   total_nutrients['鉄'],
                   total_nutrients['亜鉛'],
                   total_nutrients['銅'],
                   total_nutrients['マンガン'],
                   total_nutrients['ヨウ素'],
                   total_nutrients['セレン'],
                   total_nutrients['クロム'],
                   total_nutrients['モリブデン'],
                   total_nutrients['ビタミンA'],
                   total_nutrients['ビタミンD'],
                   total_nutrients['ビタミンE'],
                   total_nutrients['ビタミンK'],
                   total_nutrients['ビタミンB1'],
                   total_nutrients['ビタミンB2'],
                   total_nutrients['ナイアシン'],
                   total_nutrients['ビタミンB6'],
                   total_nutrients['ビタミンB12'],
                   total_nutrients['葉酸'],
                   total_nutrients['パントテン酸'],
                   total_nutrients['ビオチン'],
                   total_nutrients['ビタミンC'],
                   total_nutrients['食塩相当量']))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'meal_id': meal_id,
            'matched_items': matched_items,
            'total_nutrients': total_nutrients
        })
        
    except Exception as e:
        return jsonify({'error': f'エラー: {str(e)}'}), 500

@app.route('/api/weekly-summary/<person_name>', methods=['GET'])
@login_required
def get_weekly_summary(person_name):
    """過去1週間の平均摂取量と充足率を計算"""
    try:
        conn = sqlite3.connect('nutrition.db')
        c = conn.cursor()
        
        # 過去7日間のデータを取得
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        c.execute('''SELECT m.meal_date, m.meal_time, m.raw_input,
                            n.energy, n.protein, n.fat, n.fiber, n.potassium, n.calcium,
                            n.magnesium, n.phosphorus, n.iron, n.zinc, n.copper, n.manganese,
                            n.iodine, n.selenium, n.chromium, n.molybdenum, n.vitamin_a,
                            n.vitamin_d, n.vitamin_e, n.vitamin_k, n.vitamin_b1, n.vitamin_b2,
                            n.niacin, n.vitamin_b6, n.vitamin_b12, n.folate, n.pantothenic_acid,
                            n.biotin, n.vitamin_c, n.salt
                     FROM meals m
                     JOIN meal_nutrients n ON m.id = n.meal_id
                     WHERE m.person_name = ? AND m.meal_date >= ?
                     ORDER BY m.meal_date DESC, m.meal_time DESC''',
                  (person_name, seven_days_ago))
        
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return jsonify({'error': '過去1週間のデータがありません'}), 404
        
        # 日ごとの合計を計算
        daily_totals = {}
        for row in rows:
            meal_date = row[0]
            if meal_date not in daily_totals:
                daily_totals[meal_date] = {
                    'エネルギー': 0, 'たんぱく質': 0, '脂質': 0, '食物繊維総量': 0,
                    'カリウム': 0, 'カルシウム': 0, 'マグネシウム': 0, 'リン': 0,
                    '鉄': 0, '亜鉛': 0, '銅': 0, 'マンガン': 0, 'ヨウ素': 0,
                    'セレン': 0, 'クロム': 0, 'モリブデン': 0, 'ビタミンA': 0,
                    'ビタミンD': 0, 'ビタミンE': 0, 'ビタミンK': 0, 'ビタミンB1': 0,
                    'ビタミンB2': 0, 'ナイアシン': 0, 'ビタミンB6': 0, 'ビタミンB12': 0,
                    '葉酸': 0, 'パントテン酸': 0, 'ビオチン': 0, 'ビタミンC': 0,
                    '食塩相当量': 0
                }
            
            nutrients_list = ['エネルギー', 'たんぱく質', '脂質', '食物繊維総量',
                            'カリウム', 'カルシウム', 'マグネシウム', 'リン', '鉄',
                            '亜鉛', '銅', 'マンガン', 'ヨウ素', 'セレン', 'クロム',
                            'モリブデン', 'ビタミンA', 'ビタミンD', 'ビタミンE',
                            'ビタミンK', 'ビタミンB1', 'ビタミンB2', 'ナイアシン',
                            'ビタミンB6', 'ビタミンB12', '葉酸', 'パントテン酸',
                            'ビオチン', 'ビタミンC', '食塩相当量']
            
            for i, nutrient in enumerate(nutrients_list):
                daily_totals[meal_date][nutrient] += row[3 + i] or 0
        
        # 1日あたりの平均を計算
        num_days = len(daily_totals)
        average_daily = {}
        fulfillment_rates = {}
        
        for nutrient in DAILY_TARGETS.keys():
            total = sum(day[nutrient] for day in daily_totals.values())
            average = total / num_days if num_days > 0 else 0
            average_daily[nutrient] = round(average, 2)
            
            target = DAILY_TARGETS[nutrient]
            fulfillment = (average / target * 100) if target > 0 else 0
            fulfillment_rates[nutrient] = round(fulfillment, 1)
        
        return jsonify({
            'success': True,
            'person_name': person_name,
            'period_days': num_days,
            'start_date': min(daily_totals.keys()),
            'end_date': max(daily_totals.keys()),
            'average_daily': average_daily,
            'fulfillment_rates': fulfillment_rates,
            'daily_targets': DAILY_TARGETS
        })
        
    except Exception as e:
        return jsonify({'error': f'エラー: {str(e)}'}), 500

@app.route('/api/meal-history/<person_name>', methods=['GET'])
@login_required
def get_meal_history(person_name):
    """食事履歴を取得"""
    try:
        conn = sqlite3.connect('nutrition.db')
        c = conn.cursor()
        
        # 過去30日間のデータを取得
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        c.execute('''SELECT m.id, m.meal_date, m.meal_time, m.raw_input, m.created_at
                     FROM meals m
                     WHERE m.person_name = ? AND m.meal_date >= ?
                     ORDER BY m.meal_date DESC, m.meal_time DESC''',
                  (person_name, thirty_days_ago))
        
        rows = c.fetchall()
        conn.close()
        
        meals = []
        for row in rows:
            meals.append({
                'id': row[0],
                'meal_date': row[1],
                'meal_time': row[2],
                'raw_input': row[3],
                'created_at': row[4]
            })
        
        return jsonify({
            'success': True,
            'meals': meals
        })
        
    except Exception as e:
        return jsonify({'error': f'エラー: {str(e)}'}), 500

@app.route('/api/meal/<int:meal_id>', methods=['DELETE'])
@login_required
def delete_meal(meal_id):
    """食事を削除"""
    try:
        conn = sqlite3.connect('nutrition.db')
        c = conn.cursor()
        
        # 関連データを削除
        c.execute('DELETE FROM meal_nutrients WHERE meal_id = ?', (meal_id,))
        c.execute('DELETE FROM meal_items WHERE meal_id = ?', (meal_id,))
        c.execute('DELETE FROM meals WHERE id = ?', (meal_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': '食事を削除しました'
        })
        
    except Exception as e:
        return jsonify({'error': f'エラー: {str(e)}'}), 500

@app.route('/api/meal/<int:meal_id>', methods=['GET'])
@login_required
def get_meal(meal_id):
    """食事の詳細を取得"""
    try:
        conn = sqlite3.connect('nutrition.db')
        c = conn.cursor()
        
        c.execute('''SELECT m.id, m.person_name, m.meal_date, m.meal_time, m.raw_input
                     FROM meals m
                     WHERE m.id = ?''', (meal_id,))
        
        row = c.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'error': '食事が見つかりません'}), 404
        
        meal = {
            'id': row[0],
            'person_name': row[1],
            'meal_date': row[2],
            'meal_time': row[3],
            'raw_input': row[4]
        }
        
        conn.close()
        
        return jsonify({
            'success': True,
            'meal': meal
        })
        
    except Exception as e:
        return jsonify({'error': f'エラー: {str(e)}'}), 500

@app.route('/api/meal/<int:meal_id>', methods=['PUT'])
@login_required
def update_meal(meal_id):
    """食事を更新"""
    try:
        data = request.json
        person_name = data.get('person_name', '').strip()
        meal_date = data.get('meal_date', '')
        meal_time = data.get('meal_time', '')
        food_input = data.get('food_input', '').strip()
        
        if not person_name or not meal_date or not meal_time or not food_input:
            return jsonify({'error': '全ての項目を入力してください'}), 400
        
        # 既存の食事を削除
        conn = sqlite3.connect('nutrition.db')
        c = conn.cursor()
        
        c.execute('DELETE FROM meal_nutrients WHERE meal_id = ?', (meal_id,))
        c.execute('DELETE FROM meal_items WHERE meal_id = ?', (meal_id,))
        c.execute('DELETE FROM meals WHERE id = ?', (meal_id,))
        
        conn.commit()
        conn.close()
        
        # 新しい食事として再計算・保存
        # 食品入力をパース
        items = [item.strip() for item in food_input.split('、') if item.strip()]
        
        parsed_items = []
        for item in items:
            match = re.search(r'([^0-9]+)([\d.]+)\s*g', item)
            if match:
                food_name = match.group(1).strip()
                weight = float(match.group(2))
                parsed_items.append({'food_name': food_name, 'weight': weight})
        
        if not parsed_items:
            return jsonify({'error': '食品の形式が正しくありません（例: 納豆45g、ご飯160g）'}), 400
        
        # 食品名をマッチング
        matched_items = []
        total_nutrients = {key: 0.0 for key in DAILY_TARGETS.keys()}
        
        for item in parsed_items:
            matched_food_name = fuzzy_match_food(item['food_name'], FOOD_DATABASE, use_ai=True)
            
            if not matched_food_name:
                suggestions = get_food_suggestions(item['food_name'], FOOD_DATABASE)
                suggestion_text = ''
                if suggestions:
                    suggestion_text = f' もしかして: {", ".join(suggestions[:3])}'
                return jsonify({'error': f'食品「{item["food_name"]}」が見つかりませんでした。{suggestion_text}'}), 400
            
            # 食品データを取得
            food_data = None
            for food in FOOD_DATABASE:
                if food['食品名'] == matched_food_name:
                    food_data = food
                    break
            
            if not food_data:
                return jsonify({'error': f'食品データが見つかりません: {matched_food_name}'}), 400
            
            # 栄養素を計算
            weight_factor = item['weight'] / 100.0
            item_nutrients = {}
            
            for jp_name, target_value in DAILY_TARGETS.items():
                raw_value = food_data.get(jp_name, 0)
                numeric_value = parse_numeric_value(raw_value)
                calculated_value = numeric_value * weight_factor
                item_nutrients[jp_name] = calculated_value
                total_nutrients[jp_name] += calculated_value
            
            matched_items.append({
                'input_name': item['food_name'],
                'matched_name': matched_food_name,
                'weight': item['weight'],
                'nutrients': item_nutrients
            })
        
        # データベースに保存
        conn = sqlite3.connect('nutrition.db')
        c = conn.cursor()
        
        # 食事を保存（同じIDで）
        c.execute('''INSERT INTO meals (id, person_name, meal_date, meal_time, raw_input)
                     VALUES (?, ?, ?, ?, ?)''',
                  (meal_id, person_name, meal_date, meal_time, food_input))
        
        # 食事項目を保存
        for item in matched_items:
            c.execute('''INSERT INTO meal_items (meal_id, food_name, weight, matched_food_name)
                         VALUES (?, ?, ?, ?)''',
                      (meal_id, item['input_name'], item['weight'], item['matched_name']))
        
        # 栄養素データを保存
        c.execute('''INSERT INTO meal_nutrients 
                     (meal_id, energy, protein, fat, fiber, potassium, calcium, magnesium, 
                      phosphorus, iron, zinc, copper, manganese, iodine, selenium, chromium, 
                      molybdenum, vitamin_a, vitamin_d, vitamin_e, vitamin_k, vitamin_b1, 
                      vitamin_b2, niacin, vitamin_b6, vitamin_b12, folate, pantothenic_acid, 
                      biotin, vitamin_c, salt)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (meal_id,
                   total_nutrients['エネルギー'],
                   total_nutrients['たんぱく質'],
                   total_nutrients['脂質'],
                   total_nutrients['食物繊維総量'],
                   total_nutrients['カリウム'],
                   total_nutrients['カルシウム'],
                   total_nutrients['マグネシウム'],
                   total_nutrients['リン'],
                   total_nutrients['鉄'],
                   total_nutrients['亜鉛'],
                   total_nutrients['銅'],
                   total_nutrients['マンガン'],
                   total_nutrients['ヨウ素'],
                   total_nutrients['セレン'],
                   total_nutrients['クロム'],
                   total_nutrients['モリブデン'],
                   total_nutrients['ビタミンA'],
                   total_nutrients['ビタミンD'],
                   total_nutrients['ビタミンE'],
                   total_nutrients['ビタミンK'],
                   total_nutrients['ビタミンB1'],
                   total_nutrients['ビタミンB2'],
                   total_nutrients['ナイアシン'],
                   total_nutrients['ビタミンB6'],
                   total_nutrients['ビタミンB12'],
                   total_nutrients['葉酸'],
                   total_nutrients['パントテン酸'],
                   total_nutrients['ビオチン'],
                   total_nutrients['ビタミンC'],
                   total_nutrients['食塩相当量']))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'meal_id': meal_id,
            'matched_items': matched_items,
            'total_nutrients': total_nutrients
        })
        
    except Exception as e:
        return jsonify({'error': f'エラー: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
