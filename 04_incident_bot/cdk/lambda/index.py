import json
import os
import urllib.request
import boto3

SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
BEDROCK_MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
LOG_GROUP_NAME = os.environ["LOG_GROUP_NAME"]
LOOKBACK_MINUTES = int(os.environ.get("LOOKBACK_MINUTES", "30"))

logs_client = boto3.client("logs")
bedrock_client = boto3.client("bedrock-runtime")


def handler(event, context):
    """CloudWatch Alarm 状態変化イベントを受け取り、ログ要約を Slack に通知する。"""
    alarm_name = event.get("detail", {}).get("alarmName", "unknown")

    # TODO: CloudWatch Logs からエラーログを取得
    # TODO: Bedrock でログを要約・対応提案を生成
    # TODO: Slack に通知

    return {"statusCode": 200, "body": json.dumps({"alarm": alarm_name})}
