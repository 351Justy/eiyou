#!/usr/bin/env python3
"""
食品名マッチングのテストスクリプト
"""

import json
import unicodedata
from difflib import SequenceMatcher

# 食品データベースをロード
with open('food_database.json', 'r', encoding='utf-8') as f:
    FOOD_DATABASE = json.load(f)

def normalize_text(text):
    """テキストを正規化（全角・半角統一、空白除去）"""
    # 全角を半角に変換
    text = unicodedata.normalize('NFKC', text)
    # 余分な空白を削除
    text = ' '.join(text.split())
    return text.strip()

def fuzzy_match_food(food_input, available_foods):
    """食品名をあいまい検索でマッチング"""
    
    input_normalized = normalize_text(food_input)
    
    # レベル1: 完全一致
    for food in available_foods:
        if food['食品名'] == food_input:
            return food['食品名'], "完全一致"
    
    # レベル2: 正規化後の完全一致
    for food in available_foods:
        if normalize_text(food['食品名']) == input_normalized:
            return food['食品名'], "正規化一致"
    
    # レベル3: キーワードベースのマッチング
    keywords = [w for w in input_normalized.replace('　', ' ').split() if len(w) > 0]
    
    # キーワードマッピング
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
    
    expanded_keywords = []
    for kw in keywords:
        expanded_keywords.append(kw)
        if kw in keyword_mappings:
            expanded_keywords.extend(keyword_mappings[kw].split())
    
    best_match = None
    best_score = 0
    
    for food in available_foods:
        food_name = food['食品名']
        score = 0
        
        for kw in expanded_keywords:
            if kw in food_name:
                score += 1
        
        if score > best_score:
            best_score = score
            best_match = food_name
    
    if best_score > 0:
        return best_match, f"キーワードマッチ (スコア: {best_score})"
    
    # レベル4: 類似度マッチング
    best_ratio = 0
    best_match = None
    
    for food in available_foods:
        ratio = SequenceMatcher(None, input_normalized, normalize_text(food['食品名'])).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = food['食品名']
    
    if best_ratio >= 0.6:
        return best_match, f"類似度マッチ ({best_ratio:.2%})"
    
    return None, "マッチなし"

# テストケース
test_cases = [
    # データベースと完全一致
    "鶏卵　全卵　生",
    "だいず　［納豆類］　糸引き納豆",
    "こめ　［水稲めし］　精白米　うるち米",
    
    # 一般的な呼び方
    "納豆",
    "ご飯",
    "白米",
    "生卵",
    "卵",
    "ゆで卵",
    
    # 部分的な名前
    "鶏卵",
    "豆腐",
    "味噌",
    "醤油",
    "つゆ",
    
    # より具体的
    "鶏もも肉",
    "ブロッコリー",
    "ほうれん草",
    "さんま",
]

print("=" * 70)
print("食品名マッチングテスト")
print("=" * 70)

for i, test_input in enumerate(test_cases, 1):
    result, method = fuzzy_match_food(test_input, FOOD_DATABASE)
    if result:
        print(f"\n{i}. 入力: 「{test_input}」")
        print(f"   ✓ マッチ: {result}")
        print(f"   方法: {method}")
    else:
        print(f"\n{i}. 入力: 「{test_input}」")
        print(f"   ✗ マッチなし")

print("\n" + "=" * 70)
print("テスト完了")
print("=" * 70)
