from flask import Flask, render_template, request, jsonify, session
import anthropic
import os
import json
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
import re

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

def match_food_with_ai(food_input, available_foods):
    """Claude APIを使って食品名をマッチング"""
    if not CLAUDE_API_KEY:
        raise Exception('Claude APIキーが設定されていません')
    
    # 利用可能な食品名のリスト（最初の500件のみ）
    food_list = [f['食品名'] for f in available_foods[:500]]
    
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY, max_retries=2)
    
    prompt = f"""以下の食品入力に対して、データベースから最も適切な食品名を選んでください。

入力された食品: {food_input}

利用可能な食品（一部）:
{chr(10).join(food_list[:100])}

指示:
1. 入力された食品名に最も近い食品名をデータベースから1つ選んでください
2. 完全一致がない場合は、最も類似した食品を選んでください
3. 調理方法（生、ゆで、焼きなど）も考慮してください
4. JSONフォーマットで回答してください

回答フォーマット:
{{"matched_food": "データベース内の正確な食品名"}}

重要: JSON以外のテキストは含めないでください。"""
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = message.content[0].text.strip()
    
    # JSONをパース
    try:
        # マークダウンのコードブロックを削除
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        result = json.loads(response_text)
        matched_food = result.get('matched_food', '')
        
        # データベースに存在するか確認
        for food in available_foods:
            if food['食品名'] == matched_food:
                return matched_food
        
        # 完全一致がない場合は部分一致を試す
        for food in available_foods:
            if matched_food in food['食品名'] or food['食品名'] in matched_food:
                return food['食品名']
        
        return None
    except:
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
        
        # AIで食品名をマッチング
        matched_items = []
        total_nutrients = {key: 0.0 for key in DAILY_TARGETS.keys()}
        
        for item in parsed_items:
            matched_food_name = match_food_with_ai(item['food_name'], FOOD_DATABASE)
            
            if not matched_food_name:
                return jsonify({'error': f'食品「{item["food_name"]}」が見つかりませんでした'}), 400
            
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

if __name__ == '__main__':
    # データベース初期化
    init_db()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
