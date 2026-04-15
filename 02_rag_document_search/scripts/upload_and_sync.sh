#!/bin/bash
set -e

PROFILE=${AWS_PROFILE:-default}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SAMPLE_DOCS_DIR="$SCRIPT_DIR/../sample-docs"

echo "=== CloudFormation Outputs から設定を取得 ==="
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name DatasourceStack \
  --query "Stacks[0].Outputs[?OutputKey=='DocumentBucketName'].OutputValue" \
  --output text --profile "$PROFILE")

KB_ID=$(aws cloudformation describe-stacks \
  --stack-name KnowledgeBaseStack \
  --query "Stacks[0].Outputs[?OutputKey=='KnowledgeBaseId'].OutputValue" \
  --output text --profile "$PROFILE")

DS_ID=$(aws cloudformation describe-stacks \
  --stack-name KnowledgeBaseStack \
  --query "Stacks[0].Outputs[?OutputKey=='DataSourceId'].OutputValue" \
  --output text --profile "$PROFILE")

echo "Bucket:        $BUCKET_NAME"
echo "KnowledgeBase: $KB_ID"
echo "DataSource:    $DS_ID"

echo ""
echo "=== S3 にドキュメントをアップロード ==="
aws s3 sync "$SAMPLE_DOCS_DIR" "s3://$BUCKET_NAME/" --profile "$PROFILE"

echo ""
echo "=== Ingestion Job を開始 ==="
JOB_ID=$(aws bedrock-agent start-ingestion-job \
  --knowledge-base-id "$KB_ID" \
  --data-source-id "$DS_ID" \
  --query "ingestionJob.ingestionJobId" \
  --output text --profile "$PROFILE")
echo "Job ID: $JOB_ID"

echo ""
echo "=== 完了を待機中 ==="
while true; do
  STATUS=$(aws bedrock-agent get-ingestion-job \
    --knowledge-base-id "$KB_ID" \
    --data-source-id "$DS_ID" \
    --ingestion-job-id "$JOB_ID" \
    --query "ingestionJob.status" \
    --output text --profile "$PROFILE")
  echo "Status: $STATUS"
  if [ "$STATUS" = "COMPLETE" ]; then
    echo "Sync 完了"
    break
  elif [ "$STATUS" = "FAILED" ]; then
    echo "Sync 失敗"
    exit 1
  fi
  sleep 10
done

FUNCTION_NAME=$(aws cloudformation describe-stacks \
  --stack-name ComputeStack \
  --query "Stacks[0].Outputs[?OutputKey=='RagFunctionName'].OutputValue" \
  --output text --profile "$PROFILE")

OUTPUT_DIR="$SCRIPT_DIR/../output"
OUTPUT_FILE="$OUTPUT_DIR/$(date +%Y%m%d_%H%M%S)_response.json"

echo ""
echo "=== Lambda 実行コマンド ==="
echo "aws lambda invoke \\"
echo "  --function-name $FUNCTION_NAME \\"
echo "  --payload '{\"query\": \"質問テキスト\"}' \\"
echo "  --cli-binary-format raw-in-base64-out \\"
echo "  --profile $PROFILE \\"
echo "  $OUTPUT_FILE && cat $OUTPUT_FILE"
