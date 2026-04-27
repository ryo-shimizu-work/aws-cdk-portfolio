# 04_incident_bot

インシデント自動要約・対応提案ボット。

## 構成サービス

- CloudWatch Alarm
- EventBridge
- Lambda
- Amazon Bedrock
- Slack

## 学べること

- CloudWatch → EventBridge → Lambda の連携
- Bedrock を使ったテキスト要約・生成
- 運用自動化パターン
- Slack Incoming Webhook の実装

## AWS DevOps Agent との違い

AWS DevOps Agent（2026年3月 GA）は、このボットで自作しようとしている仕組みをAWSがマネージドで提供したもの。

| | 04_incident_bot | AWS DevOps Agent |
| --- | --- | --- |
| 目的 | 学習用の自作ボット | AWSマネージドのSREエージェント |
| インシデント検知 | CloudWatch Alarm を自分で設計 | AWS環境を自律的に監視 |
| AI処理 | Bedrock を自分で呼び出す | AWS側が内部で処理 |
| 対応 | Slackに通知するだけ | 自律的に調査・解決まで行う |
| カスタマイズ性 | 高い（自分でロジックを書く） | 低い（マネージド） |

自作する意義は「中身の仕組みを理解すること」。

## 手順

### CDKデプロイ手順

```bash
cd cdk
npm install
npm run deploy
```

### 動作確認手順

```bash
cd scripts
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 必要に応じて編集
# ドライラン確認
python put_error_logs.py --dry-run
# 実際にログ投入
python put_error_logs.py --profile <YOUR_PROFILE> # .env に AWS_PROFILE=your-profile を書いておけば引数省略可 python put_error_logs.py

```

### venvから離脱する方法

```bash
deactive
```

## ステータス

- [ ] 設計
- [ ] 実装
- [ ] 検証

## 改造アイデア

- [ ] Lambda 内ポーリングを Step Functions に置き換え（Logs Insights クエリの待機をステートマシンで管理）
