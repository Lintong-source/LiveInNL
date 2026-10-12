from pathlib import Path
import shutil
import sys

def install(folder):
    root=Path(folder).resolve()
    script=root/'run.py'
    if not (root/'cloud_sync_hook.py').is_file():
        raise RuntimeError('cloud_sync_hook.py missing')
    if not (root/'tools'/'shortstay_publish.py').is_file():
        raise RuntimeError('shortstay_publish.py missing')
    before=script.read_text(encoding='utf-8')
    marker='        end_run(rid)'
    if 'sync_if_enabled()' in before:
        return
    if before.count(marker)!=1:
        raise RuntimeError('Unexpected V2 run.py')
    backup=root/'run.py.before_cloud_sync.bak'
    if not backup.exists():
        shutil.copy2(script, backup)
    change='        from cloud_sync_hook import sync_if_enabled\n        sync_if_enabled()\n'
    script.write_text(before.replace(marker,change+marker),encoding='utf-8')
    print('Installed. Original saved:',backup)

if __name__=='__main__':
    install(sys.argv[1] if len(sys.argv)>1 else '.')
