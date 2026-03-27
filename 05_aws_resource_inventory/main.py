#!/usr/bin/env python3
"""AWSアカウント内のリソース一覧をMarkdown/JSON/Excelで出力するツール。"""

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import boto3

from services import SERVICE_DEFINITIONS
from pricing import CostEstimator
from resource_warnings import check_warnings
from excel_output import output_excel

# ページネーション対応のトークンキーマッピング
_PAGINATION_TOKENS = {
    "NextToken": "NextToken",
    "NextMarker": "Marker",
    "nextToken": "nextToken",
    "position": "position",
}


def get_all_regions(session):
    return [r["RegionName"] for r in session.client("ec2").describe_regions()["Regions"]]


def _paginate_items(client, svc_def):
    func_name = svc_def["func"]
    kwargs = dict(svc_def.get("func_kwargs", {}))
    key = svc_def["key"]
    all_items = []

    while True:
        resp = getattr(client, func_name)(**kwargs)
        items = key(resp) if callable(key) else resp.get(key, [])
        all_items.extend(items)

        next_token = None
        for resp_key, req_key in _PAGINATION_TOKENS.items():
            if resp.get(resp_key):
                next_token = (req_key, resp[resp_key])
                break

        if not next_token:
            break
        kwargs[next_token[0]] = next_token[1]

    return all_items


def _retry(func, max_retries=3, base_delay=1):
    """Exponential backoffでリトライ。Throttling/Rate系エラーのみ対象。"""
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            is_retryable = error_code in ("Throttling", "TooManyRequestsException", "RequestLimitExceeded") \
                or "Rate exceeded" in str(e) \
                or "Throttl" in str(e)
            if not is_retryable or attempt == max_retries:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)


# post_filter: 取得後に追加API呼び出しでフィルタ/エンリッチするハンドラ
def _post_filter_kms(client, items):
    """KMS: describe_keyでKeyManagerを取得し、CUSTOMERキーのみに絞る。"""
    filtered = []
    for item in items:
        try:
            desc = client.describe_key(KeyId=item["KeyId"])["KeyMetadata"]
            if desc.get("KeyManager") == "CUSTOMER" and desc.get("KeyState") != "PendingDeletion":
                item["_KeyManager"] = desc["KeyManager"]
                item["_Description"] = desc.get("Description", "")
                filtered.append(item)
        except Exception:
            pass
    return filtered


_POST_FILTERS = {
    "kms_customer_keys": _post_filter_kms,
}


def _fetch_single_region(session, svc_name, svc_def, region, account_id):
    arn_def = svc_def.get("arn")
    client = session.client(svc_def["client"], region_name=region)
    is_global = svc_def.get("is_global", False)

    try:
        items = _retry(lambda: _paginate_items(client, svc_def))
    except Exception as e:
        return [], [], str(e)

    # post_filter: 追加APIで絞り込み/エンリッチ
    post_filter_name = svc_def.get("post_filter")
    if post_filter_name and post_filter_name in _POST_FILTERS:
        try:
            items = _POST_FILTERS[post_filter_name](client, items)
        except Exception as e:
            return [], [], f"post_filter error: {e}"

    rows = []
    raw_items = []
    for item in items:
        row = {}
        if not is_global:
            row["Region"] = region
        for col_name, col_def in svc_def["columns"].items():
            if callable(col_def):
                row[col_name] = col_def(item)
            else:
                row[col_name] = item.get(col_def, "")
        if arn_def:
            if callable(arn_def):
                row["ARN"] = arn_def(region, account_id, item)
            else:
                row["ARN"] = item.get(arn_def, "") if isinstance(item, dict) else ""
        rows.append(row)
        raw_items.append(item)

    return rows, raw_items, None


class ProgressTracker:
    """スレッドセーフな進捗トラッカー。"""
    def __init__(self, total):
        self.total = total
        self.done = 0
        self.lock = threading.Lock()

    def increment(self, svc_name):
        with self.lock:
            self.done += 1
            print(f"  [{self.done}/{self.total}] {svc_name} done", file=sys.stderr)


def fetch_resources_parallel(session, svc_name, svc_def, regions, account_id, errors, lock):
    is_global = svc_def.get("is_global", False)
    target_regions = ["us-east-1"] if is_global else regions
    all_rows = []
    all_raw = []

    with ThreadPoolExecutor(max_workers=min(10, len(target_regions))) as executor:
        futures = {
            executor.submit(
                _fetch_single_region, session, svc_name, svc_def, region, account_id
            ): region
            for region in target_regions
        }
        for future in as_completed(futures):
            region = futures[future]
            rows, raw_items, err = future.result()
            if err:
                with lock:
                    errors.append(f"{svc_name} ({region}): {err}")
            else:
                all_rows.extend(rows)
                all_raw.extend(raw_items)

    return all_rows, all_raw


def to_markdown_table(rows):
    if not rows:
        return "_リソースなし_\n"
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines) + "\n"


# --- diff機能 ---

def compute_diff(old_path, new_data):
    """前回出力JSONと比較して差分を返す。"""
    if not old_path or not os.path.exists(old_path):
        return None

    try:
        with open(old_path) as f:
            old_data = json.load(f)
    except Exception:
        return None

    old_svcs = {s["name"]: s for s in old_data.get("services", [])}
    new_svcs = {s["name"]: s for s in new_data.get("services", [])}

    diff = {"added": [], "removed": [], "changed": []}

    for name, new_svc in new_svcs.items():
        old_svc = old_svcs.get(name)
        if not old_svc:
            if new_svc["count"] > 0:
                diff["added"].append({"service": name, "count": new_svc["count"]})
            continue
        old_count = old_svc["count"]
        new_count = new_svc["count"]
        if old_count != new_count:
            diff["changed"].append({
                "service": name,
                "old": old_count,
                "new": new_count,
                "delta": new_count - old_count,
            })

    for name, old_svc in old_svcs.items():
        if name not in new_svcs and old_svc["count"] > 0:
            diff["removed"].append({"service": name, "count": old_svc["count"]})

    if not diff["added"] and not diff["removed"] and not diff["changed"]:
        return None
    return diff


def format_diff_markdown(diff):
    if not diff:
        return ""
    lines = ["## 📊 前回との差分", ""]
    if diff["changed"]:
        lines.append("| Service | 前回 | 今回 | 増減 |")
        lines.append("| --- | --- | --- | --- |")
        for c in diff["changed"]:
            sign = f"+{c['delta']}" if c["delta"] > 0 else str(c["delta"])
            lines.append(f"| {c['service']} | {c['old']} | {c['new']} | {sign} |")
        lines.append("")
    if diff["added"]:
        lines.append(f"**新規サービス:** {', '.join(a['service'] for a in diff['added'])}")
        lines.append("")
    if diff["removed"]:
        lines.append(f"**削除サービス:** {', '.join(r['service'] for r in diff['removed'])}")
        lines.append("")
    return "\n".join(lines)


# --- 出力 ---

def output_json(inventory_data, file=None):
    text = json.dumps(inventory_data, ensure_ascii=False, indent=2, default=str)
    if file:
        with open(file, "w") as f:
            f.write(text)
    else:
        print(text)


def output_markdown(inventory_data, estimate_flag, diff_result=None, file=None):
    meta = inventory_data["metadata"]
    lines = [
        "# AWS Resource Inventory",
        "",
        f"- Account: `{meta['account_id']}`",
        f"- Date: {meta['date']}",
        f"- Regions: {', '.join(meta['regions'])}",
        f"- 実行時間: {meta.get('elapsed', '?')}秒",
    ]
    if estimate_flag:
        lines.append("- **料金概算: 730h/月フル稼働前提。データ転送量は含まない。**")
    lines.append("")

    # diff
    if diff_result:
        lines.append(format_diff_markdown(diff_result))
        lines.append("")

    # 警告サマリ
    total_warnings = sum(len(svc.get("warnings", [])) for svc in inventory_data["services"])
    if total_warnings > 0:
        lines.append(f"## ⚠️ 未使用・要確認リソース ({total_warnings}件)")
        lines.append("")
        all_warnings = []
        for svc in inventory_data["services"]:
            for w in svc.get("warnings", []):
                all_warnings.append({"Service": svc["name"], **w})
        lines.append(to_markdown_table(all_warnings))
        lines.append("")

    for svc in inventory_data["services"]:
        lines.append(f"## {svc['name']} ({svc['count']})")
        lines.append("")
        lines.append(to_markdown_table(svc["resources"]))

        if svc.get("estimates"):
            lines.append("**月額概算:**")
            lines.append("")
            lines.append(to_markdown_table(svc["estimates"]))

        lines.append("")

    if estimate_flag and inventory_data.get("total_monthly_usd") is not None:
        total = inventory_data["total_monthly_usd"]
        lines.append("---")
        lines.append("")
        lines.append(f"## 月額概算合計: ${total:,.2f} USD")
        lines.append("")
        lines.append("> ※ 730h/月フル稼働前提の概算です。データ転送料金・リクエスト課金等は含みません。")
        lines.append("")

    summary = inventory_data["summary"]
    lines.append("---")
    lines.append("")
    lines.append("## 実行サマリ")
    lines.append("")
    lines.append(f"- 対象サービス: {summary['total_services']}")
    lines.append(f"- 取得リソース合計: {summary['total_resources']}")
    lines.append(f"- 対象リージョン数: {summary['total_regions']}")
    lines.append(f"- 警告: {total_warnings}件")
    if summary["errors"]:
        lines.append(f"- **エラー: {len(summary['errors'])}件**")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>エラー詳細</summary>")
        lines.append("")
        for err in summary["errors"]:
            lines.append(f"- `{err}`")
        lines.append("")
        lines.append("</details>")
    else:
        lines.append("- エラー: なし ✅")

    text = "\n".join(lines)
    if file:
        with open(file, "w") as f:
            f.write(text)
    else:
        print(text)


# --- 設定ファイル ---

def load_config(config_path):
    """YAML設定ファイルを読み込んでdictで返す。"""
    import yaml
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def merge_config(args, config):
    """CLI引数と設定ファイルをマージ。CLI引数が優先。"""
    if args.profile is None and config.get("profile"):
        args.profile = config["profile"]
    if args.regions is None and config.get("regions"):
        args.regions = config["regions"]
    if args.services is None and config.get("services"):
        args.services = config["services"]
    if args.exclude_services is None and config.get("exclude_services"):
        args.exclude_services = config["exclude_services"]
    if args.output is None and config.get("output"):
        args.output = config["output"]
    if args.format == "markdown" and config.get("format"):
        args.format = config["format"]
    if not args.estimate and config.get("estimate"):
        args.estimate = True
    if args.workers == 4 and config.get("workers"):
        args.workers = config["workers"]
    if not args.no_cache and config.get("no_cache"):
        args.no_cache = True


def generate_output_path(account_id, fmt):
    """デフォルトの出力ファイル名を生成。"""
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = {"markdown": "md", "json": "json", "excel": "xlsx"}[fmt]
    return f"inventory_{account_id}_{date_str}.{ext}"


def main():
    parser = argparse.ArgumentParser(description="AWS Resource Inventory")
    parser.add_argument("--profile", default=None, help="AWS CLI profile名")
    parser.add_argument("--regions", nargs="*", default=None, help="対象リージョン (省略時: 全リージョン)")
    parser.add_argument("--services", nargs="*", default=None, help="対象サービス名 (省略時: 全サービス)")
    parser.add_argument("--exclude-services", nargs="*", default=None, help="除外するサービス名")
    parser.add_argument("-o", "--output", default=None, help="出力ファイルパス (省略時: 自動生成)")
    parser.add_argument("--format", choices=["markdown", "json", "excel"], default="markdown", help="出力形式 (default: markdown)")
    parser.add_argument("--estimate", action="store_true", help="月額概算(730h稼働前提)を出力")
    parser.add_argument("--workers", type=int, default=4, help="サービス並列数 (default: 4)")
    parser.add_argument("--no-cache", action="store_true", help="Pricing APIキャッシュを使わない")
    parser.add_argument("--config", default=None, help="設定ファイルパス (YAML)")
    parser.add_argument("--diff", default=None, metavar="OLD_JSON", help="前回出力JSONと差分比較")
    parser.add_argument("--list-services", action="store_true", help="指定可能なサービス名一覧を表示")
    parser.add_argument("--auto-output", action="store_true", help="出力ファイル名を自動生成")
    args = parser.parse_args()

    # --list-services
    if args.list_services:
        for name in SERVICE_DEFINITIONS:
            print(name)
        return

    # 設定ファイル
    if args.config:
        config = load_config(args.config)
        merge_config(args, config)

    session = boto3.Session(profile_name=args.profile)
    regions = args.regions or get_all_regions(session)
    account_id = session.client("sts").get_caller_identity()["Account"]

    # 出力ファイル名の自動生成
    if args.auto_output and not args.output:
        args.output = generate_output_path(account_id, args.format)

    if args.format == "excel" and not args.output:
        print("Error: --format excel には -o または --auto-output を指定してください", file=sys.stderr)
        sys.exit(1)

    # サービスフィルタ
    target_services = {}
    excludes = set(args.exclude_services or [])
    for k, v in SERVICE_DEFINITIONS.items():
        if args.services is not None and k not in args.services:
            continue
        if k in excludes:
            continue
        target_services[k] = v

    estimator = CostEstimator(session, use_cache=not args.no_cache) if args.estimate else None

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    start_time = time.time()

    # --- サービス並列取得 ---
    errors = []
    lock = threading.Lock()
    results = {}
    progress = ProgressTracker(len(target_services))

    def _fetch_svc(svc_name, svc_def):
        rows, raw_items = fetch_resources_parallel(
            session, svc_name, svc_def, regions, account_id, errors, lock
        )
        with lock:
            results[svc_name] = (rows, raw_items)
        progress.increment(svc_name)

    print(f"Fetching {len(target_services)} services across {len(regions)} regions ...", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(_fetch_svc, name, defn): name
            for name, defn in target_services.items()
        }
        for future in as_completed(futures):
            future.result()

    elapsed = round(time.time() - start_time, 1)

    # --- 構造化データ組み立て ---
    inventory_data = {
        "metadata": {
            "account_id": account_id,
            "date": now,
            "regions": regions,
            "elapsed": elapsed,
        },
        "services": [],
        "total_monthly_usd": None,
        "summary": {
            "total_services": len(target_services),
            "total_resources": 0,
            "total_regions": len(regions),
            "errors": errors,
        },
    }

    all_estimates = []

    for svc_name in target_services:
        rows, raw_items = results.get(svc_name, ([], []))
        inventory_data["summary"]["total_resources"] += len(rows)

        svc_warnings = check_warnings(svc_name, rows, raw_items)

        svc_entry = {
            "name": svc_name,
            "count": len(rows),
            "resources": rows,
            "estimates": [],
            "warnings": svc_warnings,
        }

        if estimator and rows:
            print(f"Estimating: {svc_name} ...", file=sys.stderr)
            estimates = estimator.estimate(svc_name, rows, raw_items)
            if estimates:
                svc_entry["estimates"] = estimates
                all_estimates.extend(estimates)

        inventory_data["services"].append(svc_entry)

    if args.estimate and all_estimates:
        total = sum(
            float(e["Monthly(USD)"].replace("$", "").replace(",", ""))
            for e in all_estimates
        )
        inventory_data["total_monthly_usd"] = round(total, 2)

    # --- diff ---
    diff_result = compute_diff(args.diff, inventory_data) if args.diff else None

    # --- 出力 ---
    if args.format == "json":
        output_json(inventory_data, args.output)
    elif args.format == "excel":
        output_excel(inventory_data, args.estimate, args.output)
    else:
        output_markdown(inventory_data, args.estimate, diff_result, args.output)

    # diff結果をJSON出力時はstderrに表示
    if diff_result and args.format != "markdown":
        print("\n📊 前回との差分:", file=sys.stderr)
        for c in diff_result.get("changed", []):
            sign = f"+{c['delta']}" if c["delta"] > 0 else str(c["delta"])
            print(f"  {c['service']}: {c['old']} -> {c['new']} ({sign})", file=sys.stderr)
        for a in diff_result.get("added", []):
            print(f"  {a['service']}: +{a['count']} (新規)", file=sys.stderr)
        for r in diff_result.get("removed", []):
            print(f"  {r['service']}: -{r['count']} (削除)", file=sys.stderr)

    if args.output:
        print(f"Output: {args.output}", file=sys.stderr)

    # --- stderrサマリ ---
    s = inventory_data["summary"]
    total_warnings = sum(len(svc.get("warnings", [])) for svc in inventory_data["services"])
    print(f"\n{'='*50}", file=sys.stderr)
    print(f"Done in {elapsed}s: {s['total_resources']} resources from {s['total_services']} services", file=sys.stderr)
    if total_warnings:
        print(f"Warnings: {total_warnings} ⚠️", file=sys.stderr)
    if errors:
        print(f"Errors: {len(errors)}", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
    else:
        print("Errors: none ✅", file=sys.stderr)


if __name__ == "__main__":
    main()
