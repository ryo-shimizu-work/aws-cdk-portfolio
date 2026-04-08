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

- [ ] 設計
- [ ] 実装
- [ ] 検証
