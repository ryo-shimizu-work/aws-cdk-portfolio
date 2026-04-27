# 01_ecs_3tier_webapp

ECS Fargate による3層 Web アプリケーション基盤。
v1.0 のベース構成から段階的に機能を追加し、本番運用を意識した構成まで発展させている。

## 構成サービス

VPC, ALB, ECS Fargate, RDS (Aurora Serverless v2), ECR, Secrets Manager, Route53, ACM, CloudWatch Synthetics

## アーキテクチャの変遷

### v1.0 ベース構成

![v1.0](./images/01_ecs_3tier_webapp_v1.0.png)

- NAT Gateway 経由で DockerHub からイメージ取得
- NAT Gateway 経由で Secrets Manager / CloudWatch Logs にアクセス

### v1.1 Route53 ドメインルーティング

![v1.1](./images/01_ecs_3tier_webapp_v1.1.png)

### v1.2 HTTPS 化

![v1.2](./images/01_ecs_3tier_webapp_v1.2.png)

- ACM 証明書を ALB の HTTPS リスナーにアタッチ

### v1.3 ECR からのイメージ取得

![v1.3](./images/01_ecs_3tier_webapp_v1.3.png)

- DockerHub → ECR プライベートリポジトリに変更

### v1.4 アウトバウンド通信の閉域化

![v1.4](./images/01_ecs_3tier_webapp_v1.4.png)

- NAT Gateway を廃止し、VPC エンドポイント（ECR×3 + Logs + Secrets Manager）に置き換え

### v1.5 外形監視

![v1.5](./images/01_ecs_3tier_webapp_v1.5.png)

- CloudWatch Synthetics Canary による外形監視を追加

### v1.6 GitHub Actions CI/CD

![v1.6](./images/01_ecs_3tier_webapp_v1.6.png)

- GitHub Actions から OIDC 認証で ECR にイメージ push

## デプロイ

```bash
cd cdk
npm install
npx cdk deploy --profile <PROFILE>
```

`parameter.ts` のプレースホルダーを環境に合わせて書き換えてからデプロイすること。
