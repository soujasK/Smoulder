"""DynamoDB and SNS implementations of the watch Repo/Notifier, plus table writers used by publish.

Table names come from env vars set by infra/template.yaml (TABLE_<NAME>).
"""
from __future__ import annotations

import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

_ddb = None


def ddb():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource("dynamodb")
    return _ddb


def table(name: str):
    return ddb().Table(os.environ[f"TABLE_{name.upper()}"])


def to_ddb(obj):
    """Floats -> Decimal (DynamoDB has no float type); drop None."""
    return json.loads(json.dumps(obj), parse_float=Decimal)


def from_ddb(obj):
    if isinstance(obj, list):
        return [from_ddb(x) for x in obj]
    if isinstance(obj, dict):
        return {k: from_ddb(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    return obj


class DynamoRepo:
    def put_detection_if_new(self, det: dict, first_seen_ts: str) -> bool:
        item = to_ddb({**det, "sk": f"{det['ts_utc']}#{det['det_id']}", "first_seen_ts": first_seen_ts})
        try:
            table("detections").put_item(Item=item, ConditionExpression="attribute_not_exists(sk)")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def subscribers(self) -> list[dict]:
        out, kw = [], {}
        while True:
            r = table("subscribers").scan(**kw)
            out += [from_ddb(i) for i in r["Items"] if i.get("status", "active") == "active"]
            if "LastEvaluatedKey" not in r:
                return out
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]

    def claim_alert(self, sub_id: str, det_id: str, record: dict) -> bool:
        try:
            table("alerts").put_item(Item=to_ddb({"sub_id": sub_id, "det_id": det_id, **record}), ConditionExpression="attribute_not_exists(det_id)")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def finish_alert(self, sub_id: str, det_id: str, fields: dict) -> None:
        names = {f"#{k}": k for k in fields}
        vals = {f":{k}": v for k, v in to_ddb(fields).items()}
        table("alerts").update_item(
            Key={"sub_id": sub_id, "det_id": det_id},
            UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in fields),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=vals,
        )

    def put_live(self, feed: dict) -> None:
        from pipeline.common import store

        store.put_json("public/live.json", feed)


class SnsNotifier:
    """One topic; each email subscription has a FilterPolicy on the sub_id message attribute."""

    def __init__(self, topic_arn: str | None = None):
        self.topic = topic_arn or os.environ["ALERT_TOPIC_ARN"]
        self.sns = boto3.client("sns")

    def send(self, sub: dict, subject: str, body: str) -> str:
        r = self.sns.publish(
            TopicArn=self.topic,
            Subject=subject[:99],
            Message=body,
            MessageAttributes={"sub_id": {"DataType": "String", "StringValue": sub["sub_id"]}},
        )
        return r["MessageId"]


def batch_put(name: str, items: list[dict]) -> int:
    t = table(name)
    with t.batch_writer(overwrite_by_pkeys=None) as w:
        for it in items:
            w.put_item(Item=to_ddb(it))
    return len(items)


def put_run(run: dict) -> None:
    table("runs").put_item(Item=to_ddb(run))


def recent_runs(limit: int = 6) -> list[dict]:
    r = table("runs").scan()
    runs = sorted((from_ddb(i) for i in r["Items"]), key=lambda x: x["started_at"], reverse=True)
    out, kinds = [], {}
    for x in runs:
        if kinds.get(x["kind"], 0) < 3:
            out.append(x)
            kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
        if len(out) >= limit:
            break
    return out


def recent_alerts(limit: int = 30) -> list[dict]:
    r = table("alerts").scan()
    items = [from_ddb(i) for i in r["Items"] if i.get("alert_sent_ts")]
    items.sort(key=lambda x: x["alert_sent_ts"], reverse=True)
    return [
        {"det_id": i["det_id"].split(":")[1] if i["det_id"].startswith("replay:") else i["det_id"], "site_id": i["site_id"], "acq_ts": i["acq_ts"],
         "first_seen_ts": i["first_seen_ts"], "alert_sent_ts": i["alert_sent_ts"], "replay": bool(i.get("replay"))}
        for i in items[:limit]
    ]


def subs_by_email_hash(h: str) -> list[dict]:
    r = table("subscribers").query(IndexName="by_email", KeyConditionExpression=Key("email_hash").eq(h))
    return [from_ddb(i) for i in r["Items"]]
