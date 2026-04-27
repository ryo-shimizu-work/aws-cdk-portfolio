# 04_incident_bot

CloudWatch Alarm → EventBridge → Lambda → Bedrock でエラーログを自動要約し、対応提案を Slack に通知するインシデント対応ボット。

## 構成サービス

CloudWatch (Alarm / Logs Insights), EventBridge, Lambda, Amazon Bedrock (Nova Lite), Slack (Incoming Webhook)

## アーキテクチャ

![Architecture](./image/04_incident_bot.png)

## CDK スタック構成

| スタック | 責務 |
| --- | --- |
| IamStack | Lambda 実行ロール（CloudWatch Logs / Bedrock / Slack 通知に必要な権限） |
| MonitoringStack | CloudWatch Logs メトリクスフィルター + Alarm + EventBridge ルール |
| ComputeStack | Lambda（Logs Insights クエリ → Bedrock 要約 → Slack 通知） |

## 処理フロー

1. アプリケーションログに ERROR が出力される
2. CloudWatch メトリクスフィルターが検知 → Alarm 発火
3. EventBridge ルールが Lambda を起動
4. Lambda が Logs Insights でエラーログを取得
5. Bedrock (Nova Lite) がエラー内容を要約し、対応提案を生成
6. Slack Incoming Webhook で通知

## デプロイ

```bash
cd cdk
cp .env.example .env
# .env に SLACK_WEBHOOK_URL を設定
npm install
npx cdk deploy --all --profile <PROFILE>
```

## 削除

```bash
cd cdk
npx cdk destroy --all --profile <PROFILE>
```
