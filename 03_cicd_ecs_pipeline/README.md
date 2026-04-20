# 03_cicd_ecs_pipeline

CI/CD パイプライン（GitHub Actions + ECS）。

## 構成サービス

### v1.0（実装済み）

- GitHub Actions（OIDC 認証）
- ECR（プライベートリポジトリ）
- ECS Fargate

### v2.0（未着手）

- GitHub Actions（ECR push のみ）
- CodePipeline
- CodeDeploy (Blue/Green)
- ECR
- ECS Fargate

## 学べること

- GitHub Actions OIDC 認証（アクセスキー不要）
- ECR へのイメージビルド・push
- ECS force-new-deployment
- CodePipeline の各ステージ設計（v2.0）
- ECS Blue/Green デプロイの仕組み（v2.0）
- 失敗時のロールバック戦略（v2.0）

## 01_ecs_3tier_webapp からの引き継ぎ事項

- `01_ecs_3tier_webapp/cdk/lib/constructs/ecr.ts` のプライベート ECR リポジトリを転用
- `01_ecs_3tier_webapp/cdk/lib/constructs/compute.ts` のイメージソースを ECR Public からプライベート ECR（`:latest`）に変更
- `01_ecs_3tier_webapp/cdk/lib/constructs/github-actions-role.ts` で OIDC 用 IAM ロールを作成

## 構成図

### v1.0

```text
GitHub（main push）
  │
  └── GitHub Actions
        ├── OIDC 認証（IAM ロール AssumeRole）
        ├── Docker ビルド
        ├── ECR push（:latest）
        └── ECS force-new-deployment
```

### v2.0（予定）

```text
GitHub（main push）
  │
  └── GitHub Actions
        ├── OIDC 認証
        ├── Docker ビルド
        └── ECR push（:latest）
              ↓ イメージ変更を検知
        CodePipeline
              └── CodeDeploy Blue/Green
                    └── ECS（ALB トラフィック切り替え）
```

## ファイル構成

```text
03_cicd_ecs_pipeline/
├── docs/
│   └── design.md          # 設計ドキュメント（v1.0 / v2.0）
└── README.md

# 実装ファイル（01_ecs_3tier_webapp 配下）
01_ecs_3tier_webapp/
├── cdk/lib/constructs/
│   ├── ecr.ts             # プライベート ECR リポジトリ
│   ├── compute.ts         # イメージソースをプライベート ECR に変更
│   └── github-actions-role.ts  # OIDC 用 IAM ロール
└── .github/workflows/
    └── deploy-ecs.yml     # GitHub Actions ワークフロー
```

## デプロイ手順

```bash
# CDK デプロイ（IAMロール・ECSタスク定義の更新）
cd learning/01_ecs_3tier_webapp/cdk
cdk deploy --profile <PROFILE>
```

CDK デプロイ後、`learning/01_ecs_3tier_webapp/**` 配下を変更して `main` に push するだけ。
GitHub Actions が自動で ECR へのイメージ push と ECS の再起動を行う。

## GitHub Secrets / Variables

| 名前 | 種別 | 内容 |
| --- | --- | --- |
| `AWS_ROLE_ARN` | Secret | OIDC ロールの ARN |
| `AWS_REGION` | Variable | `ap-northeast-1` |
| `ECR_REPOSITORY` | Variable | `webapp` |
| `ECS_CLUSTER` | Variable | `dev-cluster` |
| `ECS_SERVICE` | Variable | `dev-service` |

## ステータス

- [x] 設計
- [x] 実装（v1.0）
- [x] 検証（v1.0）
- [ ] 設計（v2.0）
- [ ] 実装（v2.0）
- [ ] 検証（v2.0）
