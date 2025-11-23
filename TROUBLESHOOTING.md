# トラブルシューティング - データベース初期化エラー

## エラー: "no such table: meals"

### 原因
アプリケーション起動時にデータベースが初期化されていない。

### 解決方法（v2.1で修正済み）

#### 修正内容
1. `app.py`のデータベース初期化を**モジュールレベル**で実行するように変更
2. `anthropic`モジュールをオプショナルインポートに変更

#### 修正前
```python
# 問題: if __name__ == '__main__'内でのみ初期化
if __name__ == '__main__':
    init_db()  # Gunicorn起動時は実行されない
    app.run(...)
```

#### 修正後
```python
# 解決: モジュール読み込み時に初期化
init_db()  # 常に実行される
FOOD_DATABASE = load_food_database()
```

### 更新方法

#### GitHubから最新版を取得
```bash
git pull origin main
```

#### または、手動で修正

**app.py の約105行目付近を修正:**

修正前:
```python
FOOD_DATABASE = load_food_database()
```

修正後:
```python
# データベースとデータを初期化
init_db()
FOOD_DATABASE = load_food_database()
```

**app.py の最後の部分を修正:**

修正前:
```python
if __name__ == '__main__':
    # データベース初期化
    init_db()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
```

修正後:
```python
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
```

### Renderでの対処

1. GitHubに修正をプッシュ
2. Renderが自動的に再デプロイ
3. ログで「✓ データベース初期化成功!」を確認

### 確認方法

デプロイ後、ブラウザでアクセスして:
1. ログインできるか確認
2. 食事を記録してエラーが出ないか確認
3. 週間サマリーが表示されるか確認

### ローカルでの確認

```bash
cd nutrition-calculator
rm -f nutrition.db  # 既存のDBを削除
python3 app.py      # 起動時にDBが自動作成される
```

起動ログに以下が表示されればOK:
```
 * Running on http://0.0.0.0:5000
```

エラーが出なければ成功です。

## その他のよくあるエラー

### "Template not found: index.html"
**原因**: `templates/`ディレクトリがGitHubにプッシュされていない

**解決方法**:
```bash
git add templates/
git add templates/index.html
git commit -m "Add templates directory"
git push origin main
```

### "ModuleNotFoundError: No module named 'anthropic'"
**原因**: requirements.txtが正しく読み込まれていない

**解決方法**:
1. Renderのログで`pip install -r requirements.txt`が実行されているか確認
2. requirements.txtの内容を確認:
```
Flask==3.0.0
anthropic==0.40.0
gunicorn==21.2.0
```

### データベースが保存されない
**原因**: Renderの無料プランではディスクが永続化されない

**解決方法**:
- これは仕様です
- 重要なデータは定期的にエクスポート推奨
- または、Persistent Disk（有料）を使用

### APIキーエラー
**原因**: 環境変数が設定されていない

**注意**: v2.0以降、CLAUDE_API_KEYは**不要**です！

必要な環境変数:
```
APP_PASSWORD=your_password
SECRET_KEY=your_secret_key
```

## サポート

問題が解決しない場合:
1. Renderのログを確認
2. ブラウザのコンソール（F12）を確認
3. GitHubのIssuesで報告
