from datetime import date, datetime
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from etl.quality.demo import create_demo
from etl.transform.period_engine import FILTERS,run_preview

class Command(BaseCommand):
    help='Preview flexible period analytics from canonical V2; no DB writes.'
    requires_system_checks=[]
    def add_arguments(self,parser):
        group=parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--run-id'); group.add_argument('--demo',action='store_true')
        parser.add_argument('--period',choices=['month','quarter','semester','year','ytd','custom'],required=True)
        parser.add_argument('--year',type=int); parser.add_argument('--index',type=int)
        parser.add_argument('--start',type=date.fromisoformat); parser.add_argument('--end',type=date.fromisoformat)
        parser.add_argument('--compare',choices=['yoy','previous','none'],default='yoy')
        parser.add_argument('--mode',choices=['elapsed','full'],default='elapsed')
        parser.add_argument('--plan-cutoff',help='ISO 8601 with offset; plans only')
        for name in FILTERS: parser.add_argument('--'+name)
    def handle(self,*args,**o):
        base=settings.EXTRACT_ROOT.parent
        try:
            cutoff=datetime.fromisoformat(o['plan_cutoff']) if o['plan_cutoff'] else None
            if o['demo']:
                run=create_demo(base/'quality_demo'); canonical=base/'quality_demo'/'canonical_v2'; self.stdout.write(f'DEMO ONLY | run-id={run}')
            else:
                run=o['run_id']; canonical=base/'canonical_v2'
            query={k:o[k] for k in ('year','index','start','end','compare','mode')}
            query.update(kind=o['period'],filters={k:o[k] for k in FILTERS if o[k] is not None})
            r,path=run_preview(canonical,base/'transform_v3',run,demo=o['demo'],plan_cutoff=cutoff,**query)
        except Exception as exc:
            raise CommandError(f'Transform V3 ditolak: {exc}') from exc
        self.stdout.write('PREVIEW_ONLY | load_ready=false')
        self.stdout.write('source_coverage='+r['source_coverage'])
        c=r['current']; p=r['reference']
        self.stdout.write(f"current={c['start']}..{c['end']}")
        self.stdout.write(f"reference={p['start']}..{p['end']}" if p else 'reference=None')
        for m in ('pack','liter','rupiah'):
            self.stdout.write(f"actual_{m}={c['actual'][m]} | reference_{m}={p['actual'][m] if p else None} | growth_{m}_pct={r['growth_pct'][m]}")
        for kind,v in c['asp'].items():
            self.stdout.write(f"{kind.lower()}_prorata_pack={v['prorata_target']['pack']} | achievement_pack_pct={v['achievement_pct']['pack']}")
        self.stdout.write(f'output={path}')
