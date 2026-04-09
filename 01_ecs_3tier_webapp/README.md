# 01_ecs_3tier_webapp

ECS 3層 Web アプリ。全構成の基礎。

## 構成サービス

- VPC / Subnet / SG
- ALB
- ECS Fargate
- RDS (Aurora)
- Secrets Manager
- CDK (TypeScript)

## 学べること

- VPC・サブネット・SG の設計
- ALB + ECS Fargate の構成
- RDS マルチAZ・フェイルオーバー
- IAM / Secrets 管理
- 障害時の切り分け（Route53 → ALB → ECS → DB）

## ステータス

- [x] 設計
- [x] 実装
- [x] 検証

## 構成図

> drawioファイルは `images/` に保管。改造のたびにPNGエクスポートして追加する。

### v1.0 ベース構成
![v1.0](./images/01_ecs_3tier_webapp_v1.0.png)

**ポイント**
 - インターネット経由（NAT Gateway）でDocerHubからイメージを取得
 - インターネット経由（NAT Gateway）でSecretsManager／CloudWatchLogsにアクセス

<!-- 改造後に追加
### v1.1 xxxxxxxxx
![v1.1](./images/01_ecs_3tier_webapp_v1.1.png)

### v1.2 xxxxxxxxx
![v1.2](./images/01_ecs_3tier_webapp_v1.2.png)
-->
