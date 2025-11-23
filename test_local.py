#!/usr/bin/env python3
"""
ローカルでの動作確認スクリプト
Claude APIキーなしでも基本機能をテストできます
"""

import json
import sqlite3
from datetime import datetime, timedelta

def test_database():
    """データベースの初期化をテスト"""
    print("=" * 50)
    print("データベース初期化テスト")
    print("=" * 50)
    
    conn = sqlite3.connect('test_nutrition.db')
    c = conn.cursor()
    
    # テーブル作成
    c.execute('''CREATE TABLE IF NOT EXISTS meals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  person_name TEXT NOT NULL,
                  meal_date DATE NOT NULL,
                  meal_time TIME NOT NULL,
                  raw_input TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS meal_items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  meal_id INTEGER NOT NULL,
                  food_name TEXT NOT NULL,
                  weight REAL NOT NULL,
                  matched_food_name TEXT NOT NULL,
                  FOREIGN KEY (meal_id) REFERENCES meals (id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS meal_nutrients
                 (meal_id INTEGER PRIMARY KEY,
                  energy REAL,
                  protein REAL,
                  fat REAL,
                  FOREIGN KEY (meal_id) REFERENCES meals (id))''')
    
    conn.commit()
    conn.close()
    print("✓ データベーステーブル作成成功")

def test_food_database():
    """食品データベースの読み込みをテスト"""
    print("\n" + "=" * 50)
    print("食品データベーステスト")
    print("=" * 50)
    
    with open('food_database.json', 'r', encoding='utf-8') as f:
        foods = json.load(f)
    
    print(f"✓ 総食品数: {len(foods)}")
    
    # サンプル食品を表示
    print("\n最初の3食品:")
    for i, food in enumerate(foods[:3], 1):
        print(f"{i}. {food['食品名']}")
        print(f"   エネルギー: {food['エネルギー']}kcal")
        print(f"   たんぱく質: {food['たんぱく質']}g")
    
    # よく使う食品を検索
    print("\n\n「納豆」を含む食品:")
    natto = [f['食品名'] for f in foods if '納豆' in f['食品名']][:5]
    for name in natto:
        print(f"  - {name}")
    
    print("\n「こめ　めし」を含む食品:")
    rice = [f['食品名'] for f in foods if 'こめ' in f['食品名'] and 'めし' in f['食品名']][:5]
    for name in rice:
        print(f"  - {name}")
    
    print("\n「鶏卵」を含む食品:")
    egg = [f['食品名'] for f in foods if '鶏卵' in f['食品名']][:5]
    for name in egg:
        print(f"  - {name}")

def test_sample_data():
    """サンプルデータでの計算をテスト"""
    print("\n" + "=" * 50)
    print("サンプルデータ計算テスト")
    print("=" * 50)
    
    with open('food_database.json', 'r', encoding='utf-8') as f:
        foods = json.load(f)
    
    # 食品を検索する関数
    def find_food(keyword):
        for food in foods:
            if keyword in food['食品名']:
                return food
        return None
    
    # サンプル食事
    sample_meal = [
        ('だいず　［納豆類］　糸引き納豆', 45),
        ('こめ　［水稲めし］　精白米　うるち米', 160),
        ('鶏卵　全卵　生', 60)
    ]
    
    print("\nサンプル食事: 納豆定食")
    total_energy = 0
    total_protein = 0
    total_calcium = 0
    
    for food_name, weight in sample_meal:
        food = find_food(food_name)
        if food:
            energy = float(food['エネルギー']) * (weight / 100)
            protein = float(food['たんぱく質']) * (weight / 100)
            calcium = float(food['カルシウム']) * (weight / 100)
            
            total_energy += energy
            total_protein += protein
            total_calcium += calcium
            
            print(f"\n{food_name} ({weight}g)")
            print(f"  エネルギー: {energy:.1f}kcal")
            print(f"  たんぱく質: {protein:.1f}g")
            print(f"  カルシウム: {calcium:.1f}mg")
    
    print("\n" + "-" * 50)
    print("合計:")
    print(f"  エネルギー: {total_energy:.1f}kcal")
    print(f"  たんぱく質: {total_protein:.1f}g")
    print(f"  カルシウム: {total_calcium:.1f}mg")
    
    # 目標値との比較
    print("\n目標充足率:")
    print(f"  エネルギー: {(total_energy/2700*100):.1f}%")
    print(f"  たんぱく質: {(total_protein/70*100):.1f}%")
    print(f"  カルシウム: {(total_calcium/750*100):.1f}%")

def cleanup():
    """テストファイルのクリーンアップ"""
    import os
    if os.path.exists('test_nutrition.db'):
        os.remove('test_nutrition.db')
        print("\n✓ テストデータベース削除")

if __name__ == '__main__':
    try:
        print("\n食品栄養計算システム - ローカルテスト\n")
        test_database()
        test_food_database()
        test_sample_data()
        print("\n" + "=" * 50)
        print("✅ 全てのテスト成功!")
        print("=" * 50)
    except Exception as e:
        print(f"\n❌ エラー: {e}")
    finally:
        cleanup()
