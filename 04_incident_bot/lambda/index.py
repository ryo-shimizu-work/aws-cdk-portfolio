import json
import os
import time
import urllib.request

import boto3

SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
BEDROCK_MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
LOG_GROUP_NAME = os.environ["LOG_GROUP_NAME"]
LOOKBACK_MINUTES = int(os.environ.get("LOOKBACK_MINUTES", "30"))

logs_client = boto3.client("logs")
bedrock_client = boto3.client("bedrock-runtime", region_name="ap-northeast-1")


def handler(event, context):
    alarm_name = event.get("detail", {}).get("alarmName", "unknown")

    logs = _fetch_error_logs()
    if not logs:
        print("[INFO] エラーログなし。通知をスキップします", flush=True)
        return {"statusCode": 200, "body": "no logs"}

    message = _invoke_bedrock(logs)
    _notify_slack(alarm_name, message)

    return {"statusCode": 200, "body": json.dumps({"alarm": alarm_name})}


def _fetch_error_logs() -> str:
    end_time = int(time.time())
    start_time = end_time - LOOKBACK_MINUTES * 60

    response = logs_client.start_query(
        logGroupName=LOG_GROUP_NAME,
        startTime=start_time,
        endTime=end_time,
        queryString="fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20",
    )
    query_id = response["queryId"]

    # クエリ完了までポーリング（最大 30 秒）
    for _ in range(30):
        time.sleep(1)
        result = logs_client.get_query_results(queryId=query_id)
        if result["status"] in ("Complete", "Failed", "Cancelled"):
            break

    if result["status"] != "Complete":
        raise RuntimeError(f"Logs Insights クエリ失敗: {result['status']}")

    lines = []
    for record in result["results"]:
        fields = {f["field"]: f["value"] for f in record}
        lines.append(f"{fields.get('@timestamp', '')} {fields.get('@message', '')}")

    return "\n".join(lines)


def _invoke_bedrock(logs: str) -> str:
    prompt = (
        "以下は AWS アプリケーションのエラーログです。\n"
        "1. エラーの概要を 2〜3 文で要約してください。\n"
        "2. 考えられる原因を箇条書きで挙げてください。\n"
        "3. 推奨する対応手順を箇条書きで挙げてください。\n\n"
        f"```\n{logs}\n```"
    )

    body = {
        "schemaVersion": "messages-v1",
        "messages": [
            {"role": "user", "content": [{"text": prompt}]}
        ],
        "inferenceConfig": {"maxTokens": 512},
    }

    response = bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


def _notify_slack(alarm_name: str, message: str) -> None:
    payload = {
        "text": f":rotating_light: *アラーム検知: {alarm_name}*\n\n{message}"
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        print(f"[INFO] Slack 通知完了: {resp.status}", flush=True)
