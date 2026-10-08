"""Cross-platform task runner (the Makefile calls this). Usage: python scripts/tasks.py <task> [args]

Tasks:
  setup            Python venv deps + web deps
  gate             FIRMS backfill (cached) + validation gate -> docs/GATE.md
  backfill-local   full local pipeline -> web/public/data/snapshot.json
  test             Python tests + web type-check/tests
  preflight        check AWS identity and permissions needed to deploy
  deploy           SAM deploy, seed S3, run Backfill, build and deploy the web app to Amplify
  web-deploy       rebuild the web app in live mode and deploy it to Amplify
  replay <det_id> [<sub_id>]   re-run the alert path for a real past detection (labelled REPLAY)
  demo             print the Demo Mode URL
  local-up         open-source AWS stack on this machine: LocalStack (S3, DynamoDB, SNS, SSM) seeded from the template
  local-api        sam build + sam local start-api on :3000 (the real Lambda image and handler, against LocalStack)
  local-web        web app in live mode against the local API (:5180)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STACK = os.environ.get("SMOULDER_STACK", "smoulder")
REGION = os.environ.get("AWS_REGION", "ap-south-1")
PY = sys.executable
WIN = os.name == "nt"


def sh(cmd: list[str] | str, cwd: Path = ROOT, check: bool = True, capture: bool = False, env: dict | None = None) -> str:
    print("$", cmd if isinstance(cmd, str) else " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=capture, shell=isinstance(cmd, str), env={**os.environ, **(env or {})})
    return (r.stdout or "") if capture else ""


def boto(service: str):
    import boto3

    return boto3.client(service, region_name=REGION)


def npm() -> str:
    return "npm.cmd" if WIN else "npm"


def sam() -> str:
    local = ROOT / "cache" / "toolsvenv" / ("Scripts/sam.exe" if WIN else "bin/sam")
    return str(local) if local.exists() else "sam"


def env_file() -> dict:
    out = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------- local

def setup():
    sh([PY, "-m", "pip", "install", "-r", "requirements.txt"])
    sh([npm(), "ci"], cwd=ROOT / "web")


def gate():
    sh([PY, "-m", "pipeline.firms.backfill"])
    sh([PY, "-m", "pipeline.validate.gate"])


def backfill_local():
    gate()
    sh([PY, "-m", "pipeline.context.context"])
    sh([PY, "-m", "pipeline.imagery.burnscan"])
    sh([PY, "-m", "pipeline.publish.snapshot"])


def test():
    sh([PY, "-m", "pytest", "-q", "tests"])
    sh([npm(), "run", "typecheck"], cwd=ROOT / "web")
    sh([npm(), "test"], cwd=ROOT / "web")


# ---------------------------------------------------------------- AWS

NEEDED = [
    ("cloudformation", "list_stacks", {}),
    ("s3", "list_buckets", {}),
    ("lambda", "list_functions", {"MaxItems": 1}),
    ("stepfunctions", "list_state_machines", {"maxResults": 1}),
    ("dynamodb", "list_tables", {"Limit": 1}),
    ("sns", "list_topics", {}),
    ("ecr", "describe_repositories", {}),
    ("iam", "list_roles", {"MaxItems": 1}),
    ("ssm", "describe_parameters", {"MaxResults": 1}),
    ("amplify", "list_apps", {}),
    ("scheduler", "list_schedules", {"MaxResults": 1}),
    ("apigatewayv2", "get_apis", {}),
    ("bedrock", "list_foundation_models", {"byProvider": "anthropic"}),
]


def preflight() -> bool:
    from botocore.exceptions import ClientError

    ident = boto("sts").get_caller_identity()
    print(f"AWS identity: {ident['Arn']} (account {ident['Account']}), region {REGION}")
    ok = True
    for svc, op, kw in NEEDED:
        try:
            getattr(boto(svc), op)(**kw)
            print(f"  ok    {svc}")
        except ClientError as e:
            ok = False
            print(f"  DENY  {svc}: {e.response['Error']['Code']}")
    if not shutil.which("docker"):
        ok = False
        print("  MISSING docker (needed to build the Lambda container image)")
    else:
        r = subprocess.run(["docker", "info"], capture_output=True, text=True)
        if r.returncode != 0:
            ok = False
            print("  Docker is installed but not running: start Docker Desktop")
    if not ok:
        print("\nDeploy needs an IAM principal with permissions for the services above (e.g. AdministratorAccess on a sandbox account), and Docker running.")
    return ok


def stack_outputs() -> dict:
    r = boto("cloudformation").describe_stacks(StackName=STACK)["Stacks"][0]
    return {o["OutputKey"]: o["OutputValue"] for o in r.get("Outputs", [])}


def ensure_firms_param():
    from botocore.exceptions import ClientError

    name = "/smoulder/firms_map_key"
    ssm = boto("ssm")
    try:
        ssm.get_parameter(Name=name)
        print(f"SSM {name} exists")
    except ClientError:
        key = env_file().get("FIRMS_MAP_KEY") or os.environ.get("FIRMS_MAP_KEY")
        if not key:
            sys.exit("Set FIRMS_MAP_KEY in .env first")
        ssm.put_parameter(Name=name, Value=key, Type="SecureString", Description="NASA FIRMS MAP_KEY for Smoulder")
        print(f"SSM {name} created (SecureString)")


def sam_deploy(overrides: dict | None = None):
    params = {"SiteBaseUrl": "", "AllowedOrigin": "*", "BudgetEmail": os.environ.get("BUDGET_EMAIL", "")}
    params.update(overrides or {})
    sh([sam(), "build", "--template-file", "infra/template.yaml"])
    sh([sam(), "deploy", "--stack-name", STACK, "--region", REGION, "--resolve-s3", "--resolve-image-repos", "--capabilities", "CAPABILITY_IAM",
        "--no-confirm-changeset", "--no-fail-on-empty-changeset", "--parameter-overrides", *[f"{k}={v}" for k, v in params.items() if v != ""]])


def seed_bucket(bucket: str):
    """Upload the local open-data cache so the cloud run does not re-download years of FIRMS windows."""
    for sub in ("raw", "derived"):
        if (ROOT / "cache" / sub).exists():
            sh(["aws", "s3", "sync", f"cache/{sub}", f"s3://{bucket}/{sub}", "--region", REGION, "--only-show-errors"])
    if (ROOT / "web" / "public" / "imagery").exists():
        sh(["aws", "s3", "sync", "web/public/imagery", f"s3://{bucket}/imagery", "--region", REGION, "--only-show-errors"])


def run_state_machine(arn: str, name: str, timeout_s: int = 3600) -> dict:
    sf = boto("stepfunctions")
    ex = sf.start_execution(stateMachineArn=arn, name=name)
    print("started", ex["executionArn"])
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        d = sf.describe_execution(executionArn=ex["executionArn"])
        if d["status"] != "RUNNING":
            print("execution", d["status"])
            return d
        time.sleep(15)
    raise TimeoutError(name)


def build_web(api_url: str) -> Path:
    sh([npm(), "run", "build"], cwd=ROOT / "web", env={"VITE_DATA_MODE": "live", "VITE_API_BASE_URL": api_url})
    z = ROOT / "cache" / "web.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        for p in (ROOT / "web" / "dist").rglob("*"):
            if p.is_file():
                f.write(p, p.relative_to(ROOT / "web" / "dist").as_posix())
    return z


def amplify_deploy(zip_path: Path) -> str:
    import requests

    amp = boto("amplify")
    app = next((a for a in amp.list_apps()["apps"] if a["name"] == "smoulder"), None)
    if not app:
        app = amp.create_app(name="smoulder", platform="WEB", customRules=[{"source": "</^[^.]+$|\\.(?!(css|js|mjs|json|png|webp|svg|woff2|pmtiles|map|txt)$)([^.]+$)/>", "target": "/index.html", "status": "200"}])["app"]
    try:
        amp.get_branch(appId=app["appId"], branchName="main")
    except amp.exceptions.NotFoundException:
        amp.create_branch(appId=app["appId"], branchName="main", stage="PRODUCTION")
    dep = amp.create_deployment(appId=app["appId"], branchName="main")
    requests.put(dep["zipUploadUrl"], data=zip_path.read_bytes(), headers={"Content-Type": "application/zip"}, timeout=600).raise_for_status()
    amp.start_deployment(appId=app["appId"], branchName="main", jobId=dep["jobId"])
    url = f"https://main.{app['defaultDomain']}"
    print("Amplify deployment started:", url)
    return url


def deploy():
    if not preflight():
        sys.exit(1)
    ensure_firms_param()
    sam_deploy()
    out = stack_outputs()
    seed_bucket(out["DataBucketName"])
    run_state_machine(out["BackfillStateMachineArn"], "backfill-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    url = amplify_deploy(build_web(out["ApiUrl"]))
    sam_deploy({"SiteBaseUrl": url, "AllowedOrigin": url})
    run_state_machine(out["WatchStateMachineArn"], "watch-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), 900)
    print(f"\nLive URL: {url}\nAPI: {out['ApiUrl']}\nPipeline page: {url}/pipeline")


def web_deploy():
    out = stack_outputs()
    print(amplify_deploy(build_web(out["ApiUrl"])))


def replay(det_id: str, sub_id: str | None = None):
    fn = next(r["PhysicalResourceId"] for r in boto("cloudformation").describe_stack_resources(StackName=STACK)["StackResources"] if r["LogicalResourceId"] == "ReplayFunction")
    ev = {"routeKey": "POST /admin/replay", "body": json.dumps({"det_id": det_id, "sub_id": sub_id})}
    r = boto("lambda").invoke(FunctionName=fn, Payload=json.dumps(ev).encode())
    print(json.dumps(json.loads(json.loads(r["Payload"].read())["body"]), indent=1))


# ---------------------------------------------------------------- local AWS (open-source: SAM CLI + LocalStack)

LOCALSTACK_IMAGE = "localstack/localstack:4.4.0"
LOCAL_ENDPOINT = "http://localhost:4566"
LOCAL_BUCKET = "smoulder-local"
LOCAL_ENV = ROOT / "cache" / "sam-local-env.json"
LOCAL_CREDS = {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test", "AWS_DEFAULT_REGION": REGION}


def template_resources() -> dict:
    """infra/template.yaml resources, with CloudFormation intrinsics (!Ref, !Sub, ...) kept as plain values."""
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    return yaml.load((ROOT / "infra" / "template.yaml").read_text(encoding="utf-8"), Loader=Loader)["Resources"]


def local_boto(service: str):
    import boto3

    return boto3.client(service, endpoint_url=LOCAL_ENDPOINT, region_name=REGION, aws_access_key_id="test", aws_secret_access_key="test")


def local_up():
    """Start LocalStack, create the template's S3 bucket, DynamoDB tables, SNS topic and SSM key, seed the snapshot."""
    running = sh(["docker", "ps", "--filter", "name=smoulder-localstack", "--format", "{{.Names}}"], capture=True).strip()
    if not running:
        sh(["docker", "rm", "-f", "smoulder-localstack"], check=False)
        sh(["docker", "run", "-d", "--name", "smoulder-localstack", "-p", "4566:4566", "-e", "SERVICES=s3,dynamodb,sns,ssm,sts", LOCALSTACK_IMAGE])
    import requests

    for _ in range(60):
        try:
            if requests.get(f"{LOCAL_ENDPOINT}/_localstack/health", timeout=2).ok:
                break
        except requests.RequestException:
            pass
        time.sleep(2)
    s3, ddb, sns = local_boto("s3"), local_boto("dynamodb"), local_boto("sns")
    s3.create_bucket(Bucket=LOCAL_BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION})
    env = {"SMOULDER_BUCKET": LOCAL_BUCKET, "GEOCODER": "nominatim", "AWS_ENDPOINT_URL": "http://host.docker.internal:4566", **LOCAL_CREDS}
    existing = set(ddb.list_tables()["TableNames"])
    for logical, res in template_resources().items():
        if res["Type"] != "AWS::DynamoDB::Table":
            continue
        name = "smoulder-" + logical.removesuffix("Table").lower()
        env["TABLE_" + {"FireDays": "FIRE_DAYS", "BurnObs": "BURN_OBS"}.get(logical.removesuffix("Table"), logical.removesuffix("Table").upper())] = name
        if name in existing:
            continue
        p = res["Properties"]
        kw = {k: p[k] for k in ("AttributeDefinitions", "KeySchema") if k in p}
        if p.get("GlobalSecondaryIndexes"):
            kw["GlobalSecondaryIndexes"] = p["GlobalSecondaryIndexes"]
        ddb.create_table(TableName=name, BillingMode="PAY_PER_REQUEST", **kw)
    env["ALERT_TOPIC_ARN"] = sns.create_topic(Name="smoulder-alerts")["TopicArn"]
    key = env_file().get("FIRMS_MAP_KEY") or os.environ.get("FIRMS_MAP_KEY")
    if key:
        local_boto("ssm").put_parameter(Name="/smoulder/firms_map_key", Value=key, Type="SecureString", Overwrite=True)
        env["FIRMS_MAP_KEY_PARAM"] = "/smoulder/firms_map_key"
    s3.upload_file(str(ROOT / "web" / "public" / "data" / "snapshot.json"), LOCAL_BUCKET, "public/latest.json")
    fns = [k for k, r in template_resources().items() if r["Type"] == "AWS::Serverless::Function"]
    LOCAL_ENV.write_text(json.dumps({f: env for f in fns}, indent=1))
    print(f"LocalStack ready at {LOCAL_ENDPOINT}: bucket {LOCAL_BUCKET}, {sum(k.startswith('TABLE_') for k in env)} tables, topic {env['ALERT_TOPIC_ARN']}")
    print(f"SAM env vars: {LOCAL_ENV}")


def local_api():
    """Build the Lambda image from infra/template.yaml and serve the HTTP API locally (sam local start-api) on :3000."""
    if not LOCAL_ENV.exists():
        local_up()
    sh([sam(), "build", "--template-file", "infra/template.yaml"])
    sh([sam(), "local", "start-api", "--env-vars", str(LOCAL_ENV), "--port", "3000", "--warm-containers", "LAZY"])


def local_web():
    """Web app in live mode against the local API."""
    sh([npm(), "run", "dev", "--", "--port", "5180"], cwd=ROOT / "web", env={"VITE_DATA_MODE": "live", "VITE_API_BASE_URL": "http://127.0.0.1:3000"})


def demo():
    print("Offline:  http://localhost:5173/?demo=1   (cd web && npm run dev)")
    try:
        print("Live:    ", stack_outputs().get("ApiUrl"), "-> open the Amplify URL with ?demo=1")
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    t, args = sys.argv[1], sys.argv[2:]
    fn = {"setup": setup, "gate": gate, "backfill-local": backfill_local, "test": test, "preflight": preflight, "deploy": deploy,
          "web-deploy": web_deploy, "replay": replay, "demo": demo, "local-up": local_up, "local-api": local_api, "local-web": local_web}.get(t)
    if not fn:
        sys.exit(__doc__)
    r = fn(*args)
    if r is False:
        sys.exit(1)
