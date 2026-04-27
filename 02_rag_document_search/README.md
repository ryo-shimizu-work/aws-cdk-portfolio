# 02_rag_document_search

Bedrock Knowledge Base + OpenSearch Serverless による RAG 構成。
S3 上のドキュメントをベクトル化し、自然言語で検索・回答を生成する。

## 構成サービス

Amazon Bedrock (Knowledge Base / Nova Lite / Titan Embed v2), OpenSearch Serverless, S3, Lambda

## アーキテクチャ

![Architecture](./images/02_rag_document_search_v1.0.png)

## CDK スタック構成

デプロイ順に依存関係がある。`cdk deploy --all` で一括デプロイ可能。

```text
DatasourceStack
  └─ IamStack
       └─ OpenSearchStack
            └─ KnowledgeBaseStack
                 └─ ComputeStack
```

| スタック | 責務 |
| --- | --- |
| DatasourceStack | ドキュメント格納用 S3 バケット |
| IamStack | Bedrock Knowledge Base の実行ロール（循環参照回避のため分離） |
| OpenSearchStack | OpenSearch Serverless コレクション + インデックス自動作成（Custom Resource） |
| KnowledgeBaseStack | Bedrock Knowledge Base + S3 データソース（FIXED_SIZE チャンキング: 300 トークン / 20% オーバーラップ） |
| ComputeStack | Retrieve & Generate API を呼び出す Lambda |

### 設計上の注意点

- DataAccessPolicy の `policy` は `cdk.Fn.sub` で組み立てる（`JSON.stringify` は CFn トークンを解決できない）
- IndexCreatorRole は `roleName` を固定する（スタック再作成時に ARN が変わると DataAccessPolicy の Principal と不一致になる）
- OpenSearch Serverless への署名は `requests-aws4auth` を使用（`botocore.SigV4Auth` は AssumedRole セッションで 403 になる）

## デプロイ

```bash
# Lambda Layer セットアップ（初回のみ）
mkdir -p cdk/lambda-layer/python
pip install requests requests-aws4auth -t cdk/lambda-layer/python

# デプロイ
cd cdk
npm install
npm run deploy
```

## ドキュメント投入・Sync

```bash
AWS_PROFILE=<PROFILE> ./scripts/upload_and_sync.sh
```

## 削除

```bash
cd cdk
npm run destroy
```

> ⚠️ OpenSearch Serverless は最小構成でも $350/月。検証後は即削除すること。
