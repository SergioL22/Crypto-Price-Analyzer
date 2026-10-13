"""Offline Phase 4 evaluation and explicit manual prediction journal commands."""
import argparse
import json
from pathlib import Path
import sqlite3
from datasets import DatasetStore, canonical
from modeling import digest
from phase4_evaluation import evaluate_universe
from prediction_journal import Journal, issue, settle, summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store')
    commands=parser.add_subparsers(dest='command',required=True)
    evaluation=commands.add_parser('evaluate')
    evaluation.add_argument('--audit',required=True,type=Path)
    evaluation.add_argument('--output',required=True,type=Path)
    for name in ('issue','settle','journal'):
        command=commands.add_parser(name)
        command.add_argument('--journal',type=Path)
        if name!='journal': command.add_argument('--snapshot',required=True)
        if name=='settle': command.add_argument('--prediction',required=True)
    args=parser.parse_args(argv)
    try:
        store=DatasetStore(args.store) if args.store else DatasetStore()
        if args.command=='evaluate':
            report=evaluate_universe(store,json.loads(args.audit.read_text(encoding='utf-8')))
            args.output.mkdir(parents=True,exist_ok=True)
            destination=args.output/(digest(report)+'.json')
            payload=canonical(report)
            if destination.exists():
                if destination.read_text(encoding='utf-8')!=payload: raise ValueError('Report integrity failure')
            else:
                with destination.open('x',encoding='utf-8') as handle: handle.write(payload)
            result=dict(report=str(destination),report_sha256=digest(report),summaries=report['equal_weight_asset_summaries'],promoted=False)
        else:
            journal=Journal(args.journal) if args.journal else Journal()
            result=issue(store,journal,args.snapshot) if args.command=='issue' else settle(store,journal,args.prediction,args.snapshot) if args.command=='settle' else summary(journal)
        print(json.dumps(result,indent=2,allow_nan=False))
        return 0
    except (ValueError,KeyError,TypeError,OSError,sqlite3.Error):
        print('Phase 4 command rejected: check frozen inputs, fresh complete session coverage, target completion and journal integrity. No prediction/outcome success is claimed.')
        return 1


if __name__=='__main__': raise SystemExit(main())
