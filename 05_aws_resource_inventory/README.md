# aws_resource_inventory

AWSアカウント内のリソース一覧をMarkdown/JSON/Excelで出力するツール。
未使用リソースの検出・月額概算・前回差分比較にも対応。

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 使い方

```bash
source .venv/bin/activate

# 全リージョン・全サービス（stdout出力）
python main.py --profile my-profile

# ファイル名を自動生成して出力
python main.py --profile my-profile --auto-output

# ファイル出力
python main.py --profile my-profile -o inventory.md

# JSON出力
python main.py --profile my-profile --format json -o inventory.json

# Excel出力（サマリ・警告・概算シート付き）
python main.py --profile my-profile --format excel --estimate -o inventory.xlsx

# リージョン指定
python main.py --profile my-profile --regions ap-northeast-1 us-east-1

# サービス指定
python main.py --profile my-profile --services "EC2 Instances" "S3 Buckets"

# サービス除外
python main.py --profile my-profile --exclude-services "IAM Roles" "IAM Users"

# 月額概算付き
python main.py --profile my-profile --estimate -o inventory.md

# 並列数指定（デフォルト4、最大推奨10程度）
python main.py --profile my-profile --workers 8

# 前回との差分比較
python main.py --profile my-profile --format json -o new.json --diff old.json

# 設定ファイルを使用
python main.py --config config.yaml

# 指定可能なサービス名一覧
python main.py --list-services
```

## オプション一覧

| オプション | 説明 | デフォルト |
| --- | --- | --- |
| `--profile` | AWS CLI profile名 | default |
| `--regions` | 対象リージョン | 全リージョン |
| `--services` | 対象サービス名 | 全サービス |
| `--exclude-services` | 除外サービス名 | なし |
| `-o` / `--output` | 出力ファイルパス | stdout |
| `--auto-output` | ファイル名を自動生成 (`inventory_{account}_{date}.{ext}`) | off |
| `--format` | 出力形式 (`markdown` / `json` / `excel`) | markdown |
| `--estimate` | 月額概算を出力 | off |
| `--workers` | サービス並列数 | 4 |
| `--no-cache` | Pricing APIキャッシュ無効化 | off |
| `--config` | 設定ファイルパス (YAML) | なし |
| `--diff` | 前回出力JSONと差分比較 | なし |
| `--list-services` | 指定可能なサービス名一覧を表示 | - |

## 設定ファイル (`--config`)

YAML形式で頻繁に使うオプションを保存可能。CLI引数が優先。

```yaml
profile: my-profile
regions:
  - ap-northeast-1
exclude_services:
  - IAM Roles
format: markdown
estimate: true
workers: 8
```

`config.yaml.example` を参照。

## 差分比較 (`--diff`)

前回のJSON出力と比較して、サービスごとのリソース増減を表示。

```bash
# 1回目
python main.py --profile my-profile --format json -o baseline.json

# 2回目（差分付き）
python main.py --profile my-profile --format json -o current.json --diff baseline.json
```

Markdown出力時は先頭に差分テーブルが挿入される。

## 未使用リソース検出

以下のリソースを自動検出し、警告セクション / Warningsシートに表示:

| 検出対象 | 条件 |
| --- | --- |
| EC2 Instances | 停止中 (EBS・EIP課金継続) |
| EBS Volumes | 未アタッチ (available状態で課金中) |
| Elastic IPs | 未割当 ($0.005/hr課金中) |
| NAT Gateways | 失敗状態 |
| RDS Instances | 停止中 (7日後に自動起動) |
| ELBv2 | 失敗状態 |
| Security Groups | EC2-Classic (レガシー) |
| RDS Snapshots | 手動スナップショット (保存課金) |

## Excel出力 (`--format excel`)

以下のシート構成で出力:

- **Summary**: アカウント情報・サービス別リソース数・警告数
- **サービスごとのシート**: リソース一覧 + 概算(--estimate時)
- **⚠ Warnings**: 未使用・要確認リソース一覧 (黄色ハイライト)
- **Cost Estimate**: 全サービスの概算合計 (--estimate時)
- **Errors**: エラー一覧 (エラーがある場合)

## 料金概算 (`--estimate`)

Pricing APIを使用して月額概算を出力。

- 前提: リソースが730h/月フル稼働した場合の上限目安
- データ転送量・リクエスト課金は含まない
- Pricing APIの結果は `.cache/pricing/` に24時間キャッシュ
- 対応: EC2, EBS, RDS, NAT GW, ALB/NLB, VPC Endpoint, EIP, ElastiCache, TGW, Route53, KMS, Secrets Manager, WAF, CloudWatch Alarms

## 対象サービス (40サービス)

`python main.py --list-services` で一覧表示可能。

## サービスの追加

`services.py` の `SERVICE_DEFINITIONS` にエントリを追加するだけで拡張可能。

## 将来対応

- タグベースのフィルタリング
- マルチアカウント (Organizations) 対応
