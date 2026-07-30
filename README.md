# AI GeoLens — GEO診断MVP

AI検索エンジン（ChatGPT・Perplexity・Gemini・DeepSeek）におけるブランド可視性を診断・最適化するGEO（Generative Engine Optimization）SaaSのMVPです。

## 📐 アーキテクチャ

```
geo-mvp/
├── frontend/                # 日語ランディングページ（静的フロントエンド）
│   ├── index.html           # ヒーロー+URL入力→診断→レポート表示の完全ファネル
│   ├── css/style.css        # レスポンシブUI
│   └── js/app.js            # API通信・レポート動的レンダリング
├── backend/                 # Python Flask APIサーバー
│   ├── app.py               # Flask本体 / エンドポイント定義
│   ├── config.py            # 環境設定・マルチAIモデル構成
│   ├── requirements.txt     # Python依存パッケージ
│   ├── .env.example         # API Key設定テンプレート
│   └── engine/              # 診断エンジン
│       ├── __init__.py
│       ├── ai_client.py     # DeepSeek API連携（マルチAI拡張可能）
│       ├── crawler.py       # Webサイトクローラー
│       └── analyzer.py      # 4段階GEO分析パイプライン
└── README.md
```

## 🚀 クイックスタート

### 前提条件
- Python 3.9+

### 手順

```bash
# 1. バックエンド依存パッケージをインストール
cd geo-mvp/backend
pip install -r requirements.txt

# 2. 環境変数を設定
cp .env.example .env
# .envファイルを編集してDeepSeek API Keyを入力:
#   DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
# API Key取得: https://platform.deepseek.com/

# 3. サーバー起動
python app.py

# 4. ブラウザでアクセス
# http://localhost:5000
```

### デモモードについて
`.env` に `DEEPSEEK_API_KEY` が設定されていない場合、自動的にデモモードで起動します。
デモモードでは実際のAI APIを呼び出さず、サンプルデータでレポートを生成します。
フロントエンドから `/api/demo` にアクセスすることでデモレポートを確認できます。

## 🧠 4段階GEO分析パイプライン

| ステージ | 内容 | 手法 |
|---------|------|------|
| Stage 1 | インフラ監査 | 15項目の技術チェック（Schema.org, OG, H1, SSL等） |
| Stage 2 | AI可視性シミュレーション | DeepSeek AIが5次元で評価（引用されやすさ、エンティティ明確性等） |
| Stage 3 | 競合ポジション分析 | AI推定競合3-5社とGEO強度比較 |
| Stage 4 | スコアリング+推奨 | AIVO 4次元スコア + 優先順位付き改善提案 |

### AIVOスコア構成
- AI検索可視性 (25%): AIエンジンから引用される確率
- 基盤完成度 (25%): 技術的インフラのGEO対応レベル
- 競争優勢 (25%): 競合に対する相対ポジション
- 権威信号 (25%): コンテンツ権威性のAI認識度

## 🔌 API エンドポイント

| Method | Path | 説明 |
|--------|------|------|
| GET | `/` | 日本語ランディングページ |
| GET | `/api/health` | ヘルスチェック（モード確認） |
| POST | `/api/analyze` | GEO診断実行（URL + brand_name） |
| GET | `/api/demo` | デモレポート取得 |

### POST /api/analyze リクエスト例
```json
{
  "url": "https://example.com",
  "brand_name": "ExampleBrand"
}
```

### レスポンス例
```json
{
  "analysis_id": "a1b2c3d4e5f6",
  "url": "https://example.com",
  "brand": "ExampleBrand",
  "timestamp": "2026-07-31T00:00:00",
  "overall_score": 62,
  "score_level": "一般",
  "stages": {
    "stage1_infrastructure": { ... },
    "stage2_ai_visibility": { ... },
    "stage3_competitive": { ... },
    "stage4_scoring": {
      "aivo_score": { "total_score": 62, "level": "一般", "dimensions": [...] },
      "recommendations": [ ... ]
    }
  }
}
```

## 🤖 マルチAIモデル拡張

現在は DeepSeek をメインエンジンとして使用しています。
`config.py` と `ai_client.py` に追加のAIモデルを簡単に統合できます：

```python
# config.py — 追加予定
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")       # GPT-4o
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")       # Gemini Pro
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY") # Perplexity
```

将来的には複数AIモデルでクロスチェックし、各エンジンでの可視性を個別に測定する機能を実装予定。

## 🌐 デプロイ

### ローカル開発
```bash
python app.py  # http://localhost:5000
```

### 本番デプロイ候補
- **Vercel + Flask**: フロントエンドをVercel静的ホスティング、APIをServerless Functions
- **Railway / Render**: Flask appをそのままデプロイ、最も簡単
- **Cloud Run**: Docker化してGoogle Cloud Runにデプロイ

## 📊 料金プラン（計画）

| プラン | 価格 | 機能 |
|--------|------|------|
| フリー | €0 | 1URL基本診断 / 月1回 |
| プロ診断 | €49 / レポート | 全25因子分析 + AI可視性シミュレーション |
| サブスク | €99 / 月 | 月10回詳細診断 + 継続モニタリング |
| 代理店 | €299 / 月 | 白ラベル + 多顧客管理 |

## 🎯 次のステップ

- [ ] DeepSeek API Keyを設定してライブモードでテスト
- [ ] ドメイン取得: aigeolens.com
- [ ] Product Hunt ローンチ準備
- [ ] 日本語SEO記事をQiita/Noteに投稿
- [ ] 日本のSEO代理店5社に白ラベル提案
