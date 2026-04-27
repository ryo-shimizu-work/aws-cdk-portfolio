# 03_cicd_ecs_pipeline

GitHub Actions + CodePipeline + CodeDeploy による ECS Blue/Green デプロイパイプライン。

## 構成サービス

CodePipeline, CodeBuild, CodeDeploy, ECS Fargate, ECR, ALB, GitHub Actions (OIDC)

## アーキテクチャ

### v1.0 GitHub Actions 直接デプロイ

```text
GitHub（main push）
  └── GitHub Actions
        ├── OIDC 認証（IAM ロール AssumeRole）
        ├── Docker ビルド
        ├── ECR push（:latest）
        └── ECS force-new-deployment
```

### v2.0 Blue/Green デプロイ

![v2.0](./images/03_cicd_ecs_pipeline.png)

```text
GitHub（main push）
  └── GitHub Actions
        ├── OIDC 認証
        ├── Docker ビルド
        └── ECR push（:latest）
              ↓ ECR イメージ変更を EventBridge で検知
        CodePipeline
          ├── Source: ECR（imageDetail.json）
          ├── Build: CodeBuild（appspec.yaml / taskdef.json 動的生成）
          └── Deploy: CodeDeploy Blue/Green
                └── ECS（ALB :80 Blue ↔ Green 切り替え、テスト :8080）
```

## CDK 構成

```text
lib/
├── pipeline-stack.ts          # メインスタック
└── constructs/
    ├── network.ts             # VPC / SG
    ├── ecr.ts                 # ECR リポジトリ
    ├── compute.ts             # ALB / ECS（Blue/Green コントローラー）
    └── pipeline.ts            # CodePipeline / CodeBuild / CodeDeploy
```

## デプロイ

```bash
cd cdk
npm install
npx cdk deploy --profile <PROFILE>
```

CDK Output の ECR URI と IAM ロール ARN を GitHub の Secrets / Variables に登録する。

初回はイメージを手動 push してパイプラインを起動する:

```bash
aws ecr get-login-password --region ap-northeast-1 --profile <PROFILE> \
  | docker login --username AWS --password-stdin <ECR_URI>
docker build -t <ECR_URI>:latest cdk/app
docker push <ECR_URI>:latest
```

以降は `cdk/app/` を変更して `main` に push するだけで自動デプロイされる。

## 削除

Blue/Green デプロイ後はリスナーの向き先が CodeDeploy によって切り替わっているため、`cdk destroy` 前にコンソールでリスナーを Blue TG に戻す必要がある。

```bash
# 1. EC2 コンソール → ロードバランサー → リスナー
#    ポート 80  → デフォルトアクションを Blue TG に変更
#    ポート 8080 → デフォルトアクションを Green TG に変更

# 2. cdk destroy
cd cdk
npx cdk destroy --profile <PROFILE>
```

## GitHub Secrets / Variables

| 名前 | 種別 | 内容 |
| --- | --- | --- |
| `AWS_ROLE_ARN_V2` | Secret | OIDC ロールの ARN（CDK Output 参照） |
| `AWS_REGION` | Variable | `ap-northeast-1` |
| `ECR_REPOSITORY_V2` | Variable | `webapp-v2` |
