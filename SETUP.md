# セットアップガイド

このガイドでは、食品栄養計算システムをRenderにデプロイする手順を説明します。

## 📋 事前準備

### 必要なアカウント
1. **GitHub アカウント** - コードをホストするため
2. **Render アカウント** - アプリをデプロイするため（無料プラン可）
3. **Anthropic アカウント** - Claude API を利用するため

### Claude API キーの取得

1. [Anthropic Console](https://console.anthropic.com/) にアクセス
2. ログイン/サインアップ
3. API Keys セクションで新しいキーを作成
4. キーをコピーして保存（後で使用）

## 🚀 デプロイ手順

### ステップ1: GitHubリポジトリの作成

1. GitHubで新しいリポジトリを作成
   ```
   リポジトリ名: nutrition-calculator（任意）
   公開設定: Public または Private
   ```

2. ローカルでリポジトリを初期化してプッシュ
   ```bash
   cd nutrition-calculator
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/nutrition-calculator.git
   git push -u origin main
   ```

### ステップ2: Renderでのデプロイ

1. [Render Dashboard](https://dashboard.render.com/) にログイン

2. 「New +」ボタンをクリックし、「Web Service」を選択

3. GitHubリポジトリを接続
   - 初回の場合、GitHubアカウントの連携を許可
   - リポジトリ一覧から `nutrition-calculator` を選択

4. サービス設定
   ```
   Name: nutrition-calculator（任意）
   Region: Singapore（推奨）
   Branch: main
   Root Directory: （空欄のまま）
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app --timeout 300 --workers 1 --bind 0.0.0.0:$PORT
   ```

5. プランを選択
   - **Free** プラン（無料）でOK
   - 注意: 15分間アクセスがないとスリープします

6. 環境変数を設定
   「Environment」セクションで以下を追加:
   
   ```
   CLAUDE_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx（あなたのAPIキー）
   APP_PASSWORD=admin123（ログインパスワード、任意の値に変更推奨）
   SECRET_KEY=your-secret-key-12345（セッション暗号化用、ランダムな文字列推奨）
   PYTHON_VERSION=3.11.0
   ```

7. 「Create Web Service」ボタンをクリック

8. デプロイが開始されます（5-10分程度）
   - ログを確認して進捗を追跡
   - "Your service is live 🎉" と表示されたら完了

### ステップ3: アプリケーションへのアクセス

1. RenderのダッシュボードでURLを確認
   ```
   例: https://nutrition-calculator-xxxx.onrender.com
   ```

2. ブラウザでアクセス

3. 設定したパスワード（APP_PASSWORD）でログイン

## ✅ 動作確認

### 1. 食事を記録する

1. 個人名: `テストユーザー`
2. 日付: 今日の日付を選択
3. 時刻: 現在の時刻を入力
4. 食品入力: `納豆45g、ご飯160g、生卵60g`
5. 「栄養価を計算して保存」ボタンをクリック

AIが食品名を照合し、以下のようにマッチングします:
- 納豆 → だいず　［納豆類］　糸引き納豆
- ご飯 → こめ　［水稲めし］　精白米　うるち米
- 生卵 → 鶏卵　全卵　生

### 2. 週間サマリーを確認

1. 個人名: `テストユーザー`
2. 「データ読み込み」ボタンをクリック

過去7日間の平均摂取量と充足率が表示されます。

## 🔧 トラブルシューティング

### デプロイが失敗する場合

1. **ログを確認**
   - Renderのダッシュボードで「Logs」タブを確認
   - エラーメッセージを読む

2. **よくあるエラー**
   - `ModuleNotFoundError`: requirements.txt に必要なパッケージが記載されているか確認
   - `Database is locked`: 複数のワーカーを使用している場合は1に設定
   - `API Key error`: CLAUDE_API_KEY が正しく設定されているか確認

### アプリが遅い場合

- 無料プランはスリープするため、最初のアクセスは30秒程度かかります
- 有料プラン（$7/月〜）では常時稼働します

### 食品名がマッチしない場合

- より具体的な食品名を入力してください
  - 悪い例: 「飯」
  - 良い例: 「ご飯」「白米」「精白米」

## 📝 データベースの永続化について

**重要**: RenderのFreeプランではSQLiteデータベースは永続化されません。
サービスが再起動すると、データが消える可能性があります。

### 解決策

1. **PostgreSQL を使用**（推奨）
   - Renderで無料のPostgreSQLインスタンスを作成
   - app.pyのデータベース接続をPostgreSQLに変更

2. **定期的なバックアップ**
   - 重要なデータは定期的にエクスポート
   - CSVやJSONとして保存

3. **有料プラン**
   - Persistentディスクを使用（$1/月〜）

## 🔐 セキュリティ

### パスワードの変更

本番環境では、必ず強力なパスワードを設定してください:

```
APP_PASSWORD=your-strong-password-here-with-random-characters-123
SECRET_KEY=another-random-string-for-session-encryption-456
```

### API キーの保護

- APIキーは絶対にGitにコミットしないでください
- 環境変数として設定してください
- .gitignore に .env を追加しています

## 💰 コストについて

### Render（無料プラン）
- 750時間/月まで無料
- スリープあり
- 十分な範囲で使用可能

### Claude API
- 使用した分だけ課金
- 食品マッチング1回あたり約$0.001-0.002
- 月100回程度の使用なら $1未満

### 推奨プラン
- 個人使用: 無料プランで十分
- 複数人使用: Render Starter ($7/月) + API費用

## 📞 サポート

問題が発生した場合:
1. README.mdを確認
2. Renderのログを確認
3. GitHubのIssuesで報告

## 🎉 完了!

これで食品栄養計算システムが利用可能になりました!
