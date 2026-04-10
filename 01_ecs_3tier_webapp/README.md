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

### v1.1 Route53で作成したドメインでのルーティング
![v1.1](./images/01_ecs_3tier_webapp_v1.1.png)

**ポイント**
 - Aレコードに設定するドメインはサブドメインだけを指定すればよい。（`parameter.ts`に記載）

### v1.2 HTTP通信のSSL化
![v1.2](./images/01_ecs_3tier_webapp_v1.2.png)

**ポイント**
 - ACMはALBのHTTPSリスナーにアタッチする。

### v1.3 イメージ取得元変更
![v1.3](./images/01_ecs_3tier_webapp_v1.3.png)

**ポイント**
 - ECRは3つある。（プライベート／パブリック／PublicGallery）

### v1.4 NAT Gatewayの廃止（アウトバウンド通信の閉域化）
![v1.4](./images/01_ecs_3tier_webapp_v1.4.png)

**ポイント**
 - ECR（プライベートレジストリ）からイメージを取得するには3つのVPCエンドポイントが必要。
 - その他、LogsとSecretsManagerがあるので、計5つのVPCエンドポイントが必要。