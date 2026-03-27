"""
Pricing APIを使用した月額概算の算出。
前提: リソースが1ヶ月(730h)フル稼働した場合の概算。データ転送量は含まない。
"""

import hashlib
import json
import os
import sys
import time

HOURS_PER_MONTH = 730
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache", "pricing")
CACHE_TTL = 86400  # 24時間


def _cache_key(service_code, filters):
    """フィルタからキャッシュキーを生成。"""
    raw = json.dumps({"s": service_code, "f": filters}, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def _read_cache(key):
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        if time.time() - data.get("ts", 0) > CACHE_TTL:
            return None
        return data.get("price")
    except Exception:
        return None


def _write_cache(key, price):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        with open(path, "w") as f:
            json.dump({"ts": time.time(), "price": price}, f)
    except Exception:
        pass


def _get_price(pricing_client, service_code, filters, use_cache=True):
    """Pricing APIから単価(USD)を取得。キャッシュ対応。"""
    if use_cache:
        key = _cache_key(service_code, filters)
        cached = _read_cache(key)
        if cached is not None:
            return cached

    try:
        resp = pricing_client.get_products(
            ServiceCode=service_code,
            Filters=filters,
            MaxResults=1,
        )
        if not resp["PriceList"]:
            return None
        price_item = json.loads(resp["PriceList"][0])
        terms = price_item.get("terms", {}).get("OnDemand", {})
        for term in terms.values():
            for dim in term.get("priceDimensions", {}).values():
                usd = dim.get("pricePerUnit", {}).get("USD")
                if usd:
                    price = float(usd)
                    if use_cache:
                        _write_cache(key, price)
                    return price
    except Exception as e:
        print(f"  [WARN] Pricing API ({service_code}): {e}", file=sys.stderr)
    return None


def _filter(field, value):
    return {"Type": "TERM_MATCH", "Field": field, "Value": value}


def _region_name(session, region_code):
    """ap-northeast-1 -> Asia Pacific (Tokyo) のような変換。"""
    resp = session.client("ssm", region_name="us-east-1").get_parameter(
        Name=f"/aws/service/global-infrastructure/regions/{region_code}/longName"
    )
    return resp["Parameter"]["Value"]


class CostEstimator:
    def __init__(self, session, use_cache=True):
        self.pricing = session.client("pricing", region_name="us-east-1")
        self.session = session
        self.use_cache = use_cache
        self._region_name_cache = {}

    def _get_region_name(self, region_code):
        if region_code not in self._region_name_cache:
            self._region_name_cache[region_code] = _region_name(self.session, region_code)
        return self._region_name_cache[region_code]

    def _price(self, service_code, filters):
        return _get_price(self.pricing, service_code, filters, self.use_cache)

    def estimate(self, svc_name, rows, raw_items):
        """サービス名とリソース行から月額概算リストを返す。"""
        handler = self._handlers.get(svc_name)
        if not handler:
            return []
        return handler(self, rows, raw_items)

    # --- 個別サービスの見積ロジック ---

    def _ec2(self, rows, raw_items):
        results = []
        for row, raw in zip(rows, raw_items):
            if row.get("State") != "running":
                continue
            region = row.get("Region", "us-east-1")
            loc = self._get_region_name(region)
            price = self._price("AmazonEC2", [
                _filter("instanceType", row["Type"]),
                _filter("location", loc),
                _filter("operatingSystem", "Linux"),
                _filter("tenancy", "Shared"),
                _filter("preInstalledSw", "NA"),
                _filter("capacitystatus", "Used"),
            ])
            if price:
                monthly = price * HOURS_PER_MONTH
                results.append({
                    "Resource": f"{row.get('Name', '')} ({row['InstanceId']})",
                    "Type": row["Type"],
                    "UnitPrice": f"${price:.4f}/hr",
                    "Monthly(USD)": f"${monthly:.2f}",
                })
        return results

    def _ebs(self, rows, raw_items):
        results = []
        for row in rows:
            region = row.get("Region", "us-east-1")
            loc = self._get_region_name(region)
            price = self._price("AmazonEC2", [
                _filter("location", loc),
                _filter("productFamily", "Storage"),
                _filter("volumeApiName", row.get("Type", "gp3")),
            ])
            if price:
                size = float(row.get("Size(GiB)", 0))
                monthly = price * size
                results.append({
                    "Resource": row["VolumeId"],
                    "Type": f"{row.get('Type', '')} / {size:.0f}GiB",
                    "UnitPrice": f"${price:.4f}/GiB-mo",
                    "Monthly(USD)": f"${monthly:.2f}",
                })
        return results

    def _rds(self, rows, raw_items):
        results = []
        for row in rows:
            region = row.get("Region", "us-east-1")
            loc = self._get_region_name(region)
            engine = row.get("Engine", "")
            db_engine_map = {
                "mysql": "MySQL",
                "postgres": "PostgreSQL",
                "mariadb": "MariaDB",
                "oracle-ee": "Oracle",
                "oracle-se2": "Oracle",
                "sqlserver-ee": "SQL Server",
                "sqlserver-se": "SQL Server",
                "aurora-mysql": "Aurora MySQL",
                "aurora-postgresql": "Aurora PostgreSQL",
            }
            pricing_engine = db_engine_map.get(engine, engine)
            price = self._price("AmazonRDS", [
                _filter("instanceType", row.get("Class", "")),
                _filter("location", loc),
                _filter("databaseEngine", pricing_engine),
                _filter("deploymentOption", "Single-AZ"),
            ])
            if price:
                monthly = price * HOURS_PER_MONTH
                results.append({
                    "Resource": row["DBInstanceId"],
                    "Type": f"{row.get('Class', '')} ({engine})",
                    "UnitPrice": f"${price:.4f}/hr",
                    "Monthly(USD)": f"${monthly:.2f}",
                })
        return results

    def _nat_gw(self, rows, raw_items):
        results = []
        for row in rows:
            if row.get("State") != "available":
                continue
            region = row.get("Region", "us-east-1")
            loc = self._get_region_name(region)
            price = self._price("AmazonEC2", [
                _filter("location", loc),
                _filter("productFamily", "NAT Gateway"),
                _filter("usagetype", f"{region}-NatGateway-Hours") if not region.startswith("us-east-1") else _filter("usagetype", "NatGateway-Hours"),
            ])
            if price:
                monthly = price * HOURS_PER_MONTH
                results.append({
                    "Resource": f"{row.get('Name', '')} ({row['NatGatewayId']})",
                    "Type": "NAT Gateway",
                    "UnitPrice": f"${price:.4f}/hr",
                    "Monthly(USD)": f"${monthly:.2f}",
                })
        return results

    def _elb(self, rows, raw_items):
        results = []
        for row in rows:
            region = row.get("Region", "us-east-1")
            loc = self._get_region_name(region)
            lb_type = row.get("Type", "application")
            product_family = "Load Balancer-Application" if lb_type == "application" else "Load Balancer-Network"
            price = self._price("AWSELB", [
                _filter("location", loc),
                _filter("productFamily", product_family),
            ])
            if price:
                monthly = price * HOURS_PER_MONTH
                results.append({
                    "Resource": row["Name"],
                    "Type": lb_type.upper(),
                    "UnitPrice": f"${price:.4f}/hr",
                    "Monthly(USD)": f"${monthly:.2f}",
                })
        return results

    def _vpc_endpoint(self, rows, raw_items):
        results = []
        for row in rows:
            if row.get("Type") != "Interface":
                continue
            region = row.get("Region", "us-east-1")
            loc = self._get_region_name(region)
            price = self._price("AmazonVPC", [
                _filter("location", loc),
                _filter("productFamily", "VpcEndpoint"),
            ])
            if price:
                monthly = price * HOURS_PER_MONTH
                results.append({
                    "Resource": f"{row['EndpointId']} ({row.get('ServiceName', '')})",
                    "Type": "Interface Endpoint",
                    "UnitPrice": f"${price:.4f}/hr",
                    "Monthly(USD)": f"${monthly:.2f}",
                })
        return results

    def _eip(self, rows, raw_items):
        results = []
        for row in rows:
            price = 0.005  # 2024年2月以降: $0.005/hr
            monthly = price * HOURS_PER_MONTH
            label = "未割当" if "(未割当)" in str(row.get("AssociationId", "")) else "割当済"
            results.append({
                "Resource": f"{row['PublicIp']} ({label})",
                "Type": "Elastic IP",
                "UnitPrice": f"${price:.4f}/hr",
                "Monthly(USD)": f"${monthly:.2f}",
            })
        return results

    def _elasticache(self, rows, raw_items):
        results = []
        for row in rows:
            region = row.get("Region", "us-east-1")
            loc = self._get_region_name(region)
            price = self._price("AmazonElastiCache", [
                _filter("instanceType", row.get("NodeType", "")),
                _filter("location", loc),
                _filter("cacheEngine", row.get("Engine", "redis")),
            ])
            if price:
                monthly = price * HOURS_PER_MONTH
                results.append({
                    "Resource": row["CacheClusterId"],
                    "Type": f"{row.get('NodeType', '')} ({row.get('Engine', '')})",
                    "UnitPrice": f"${price:.4f}/hr",
                    "Monthly(USD)": f"${monthly:.2f}",
                })
        return results

    def _transit_gw(self, rows, raw_items):
        results = []
        for row in rows:
            if row.get("State") != "available":
                continue
            region = row.get("Region", "us-east-1")
            loc = self._get_region_name(region)
            price = self._price("AmazonVPC", [
                _filter("location", loc),
                _filter("productFamily", "TransitGateway"),
            ])
            if price:
                monthly = price * HOURS_PER_MONTH
                results.append({
                    "Resource": f"{row.get('Name', '')} ({row['TgwId']})",
                    "Type": "Transit Gateway",
                    "UnitPrice": f"${price:.4f}/hr",
                    "Monthly(USD)": f"${monthly:.2f}",
                })
        return results

    def _route53(self, rows, raw_items):
        results = []
        for row in rows:
            price = 0.50
            results.append({
                "Resource": f"{row['Name']} ({row['Id']})",
                "Type": row.get("Type", ""),
                "UnitPrice": "$0.50/zone-mo",
                "Monthly(USD)": f"${price:.2f}",
            })
        return results

    def _kms(self, rows, raw_items):
        results = []
        for row in rows:
            # post_filterでCUSTOMERキーのみに絞られている
            results.append({
                "Resource": f"{row['KeyId']} ({row.get('Description', '') or 'no description'})",
                "Type": "CMK",
                "UnitPrice": "$1.00/key-mo",
                "Monthly(USD)": "$1.00",
            })
        return results

    def _secrets(self, rows, raw_items):
        results = []
        for row in rows:
            price = 0.40
            results.append({
                "Resource": row["Name"],
                "Type": "Secret",
                "UnitPrice": "$0.40/secret-mo",
                "Monthly(USD)": f"${price:.2f}",
            })
        return results

    def _waf(self, rows, raw_items):
        results = []
        for row in rows:
            price = 5.00
            results.append({
                "Resource": row["Name"],
                "Type": "Web ACL",
                "UnitPrice": "$5.00/ACL-mo",
                "Monthly(USD)": f"${price:.2f}",
            })
        return results

    def _cw_alarms(self, rows, raw_items):
        count = len(rows)
        billable = max(0, count - 10)
        if billable == 0:
            return []
        monthly = billable * 0.10
        return [{
            "Resource": f"CloudWatch Alarms x{count} (free tier: 10)",
            "Type": "Metric Alarm",
            "UnitPrice": "$0.10/alarm-mo",
            "Monthly(USD)": f"${monthly:.2f}",
        }]

    _handlers = {
        "EC2 Instances": _ec2,
        "EBS Volumes": _ebs,
        "RDS Instances": _rds,
        "NAT Gateways": _nat_gw,
        "ELBv2 (ALB/NLB)": _elb,
        "VPC Endpoints": _vpc_endpoint,
        "Elastic IPs": _eip,
        "ElastiCache Clusters": _elasticache,
        "Transit Gateways": _transit_gw,
        "Route53 Hosted Zones": _route53,
        "KMS Keys": _kms,
        "Secrets Manager": _secrets,
        "WAF Web ACLs": _waf,
        "CloudWatch Alarms": _cw_alarms,
    }
