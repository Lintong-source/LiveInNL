import csv, json, sqlite3
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
db=BASE/'data'/'expatus.db'; out=BASE/'data'/'case_submissions.csv'
conn=sqlite3.connect(db); conn.row_factory=sqlite3.Row
rows=conn.execute('SELECT * FROM case_submissions ORDER BY created_at DESC').fetchall()
fields=['id','city','contract_date','rental_ended','moveout_date','base_rent','deposit','issues','checkin_report','deduction_spec','description','email','wechat','contact_ok','created_at']
with out.open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for r in rows:
  d=dict(r);d['issues']='、'.join(json.loads(d.pop('issues_json') or '[]'));d.pop('user_id',None);w.writerow({k:d.get(k,'') for k in fields})
print(out)
