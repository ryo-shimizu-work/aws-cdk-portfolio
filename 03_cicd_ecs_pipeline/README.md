# 03_cicd_ecs_pipeline

CI/CD パイプライン（CodePipeline + ECS）。

## 構成サービス

- CodePipeline
- CodeBuild
- CodeDeploy (Blue/Green)
- ECR
- ECS Fargate
- CDK (TypeScript)

## 学べること

- CodePipeline の各ステージ設計
- CodeBuild でのイメージビルド・プッシュ
- ECS Blue/Green デプロイの仕組み
- IAM 設計（最小権限）
- 失敗時のロールバック戦略

## 01_ecs_3tier_webapp からの引き継ぎ事項

- `01_ecs_3tier_webapp/cdk/lib/constructs/ecr.ts` のプライベート ECR リポジトリを転用する
- GitHub Actions（OIDC 認証）で自動ビルド・ECR push・ECS force-new-deployment を実装する
- 実装後、`01_ecs_3tier_webapp/cdk/lib/constructs/compute.ts` のイメージソースを ECR Public からプライベート ECR に差し替える
- ワークフロートリガーは `main` ブランチへの push + `learning/01_ecs_3tier_webapp/**` パスフィルター

## ステータス

- [ ] 設計
- [ ] 実装
- [ ] 検証
