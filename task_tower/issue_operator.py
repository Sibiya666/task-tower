"""Explicit setup helpers; never starts a worker, activates policy or changes accounts."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="action",required=True)
    check=sub.add_parser("check");check.add_argument("--config",required=True)
    probe=sub.add_parser("probe-runtime");probe.add_argument("--config",required=True);probe.add_argument("--receipt",required=True)
    manifest=sub.add_parser("manifest");manifest.add_argument("--receiver-url",required=True);manifest.add_argument("--out",required=True)
    args=parser.parse_args(argv)
    if args.action=="manifest":
        parsed=urlsplit(args.receiver_url)
        if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.query or parsed.fragment or parsed.path not in ("","/"):raise ValueError("public_receiver_origin_required")
        template=Path(__file__).resolve().parent.parent/"integrations/github_webhook/github-app-manifest.json"
        value=json.loads(template.read_text(encoding="utf-8"));value["hook_attributes"]["url"]=args.receiver_url.rstrip("/")+"/api/github/webhook"
        from .project_connections import safe_config_path
        with safe_config_path(Path(args.out).absolute()).open("x",encoding="utf-8") as stream:json.dump(value,stream,indent=2)
        print(json.dumps(dict(kind="app.manifest",repository="Sibiya666/task-tower",created_app=False)))
        return 0
    from .connector.cli import load_config
    config=load_config(args.config);connections=config.get("issue_connections",{})
    if args.action=="check":
        from .issue_bootstrap import _policy
        print(json.dumps(dict(kind="issue.binding.check",configured=len(connections),enabled=sum(_policy(c)["initially_enabled"] for c in connections.values()),started_workers=0)))
        return 0 if connections else 2
    from .issue_runtime import RuntimeProbe
    from .project_connections import safe_config_path
    probe=RuntimeProbe(config["app_server"])
    # Reserve the exact output before any command so a repeated receipt path
    # cannot silently execute the diagnostic again.
    with safe_config_path(Path(args.receipt).absolute()).open("x+",encoding="utf-8") as stream:
        json.dump(dict(kind="issue.runtime.probe",state="intent"),stream);stream.flush()
        try:
            receipt=probe.verify();report=dict(kind="issue.runtime.probe",verified=True,receipt=receipt)
        except Exception as error:
            report=dict(kind="issue.runtime.probe",verified=False,error_type=type(error).__name__,result=probe.last_result)
        stream.seek(0);json.dump(report,stream,indent=2);stream.truncate()
    print(json.dumps(dict(kind="issue.runtime.probe",verified=report["verified"],model_turns=0)))
    return 0 if report["verified"] else 1

if __name__=="__main__":raise SystemExit(main())
