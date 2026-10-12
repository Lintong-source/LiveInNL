"""Optional cloud sync after a deliberate local V2 scan."""
import os

KEYS=('detail_hash','canonical_json','status','reason','source_posted_at','image_url','search_hash')

def choose_changed(local, remote):
    known={str(x[0]):tuple(x[1:]) for x in remote}
    return [r for r in local if str(r.get('url') or '') not in known or
            tuple(r.get(k) for k in KEYS)!=known[str(r['url'])]]

def sync_if_enabled():
    if os.getenv('SHORTSTAY_CLOUD_SYNC','')!='1':
        print('[cloud] sync disabled',flush=True)
        return 0,0
    url=os.getenv('SHORTSTAY_TURSO_DATABASE_URL','').strip()
    token=os.getenv('SHORTSTAY_TURSO_AUTH_TOKEN','').strip()
    if 'expatus-shortstay' not in url.lower():
        raise RuntimeError('Expected dedicated expatus-shortstay database')
    if not token or os.getenv('SHORTSTAY_DATABASE_CONFIRMED','')!='yes':
        raise RuntimeError('Missing cloud publishing confirmation or token')
    from config import ROOT
    from tools.shortstay_publish import load_local,publish,remote_connect
    path,rows=load_local(ROOT/'data'/'nl_shortstay.sqlite3')
    db=remote_connect(url,token)
    try:
        existing=db.execute('SELECT url,'+','.join(KEYS)+' FROM listings').fetchall()
    finally:
        db.close()
    changed=choose_changed(rows,existing)
    print(f'[cloud] {len(changed)} changed/new records',flush=True)
    if not changed:return 0,0
    count,images=publish(path,changed,images=False)
    print(f'[cloud] committed {count} records',flush=True)
    return count,images
