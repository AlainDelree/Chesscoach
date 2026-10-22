import json,re,glob,os,unicodedata,collections
n=lambda s:unicodedata.normalize('NFD',s.lower()).encode('ascii','ignore').decode()
def v(d):
    try: return int(str((d.get('version_info') or {}).get('last_issue')).strip())
    except Exception: return 0
L=[]
for f in sorted(glob.glob(os.path.expanduser('~/ChessCoach/data/logs/coach_calls-*.log'))):
    L+=[json.loads(l) for l in open(f)]
L=[d for d in L if v(d)>=128 and d.get('mode_origine')=='exercice']
G=collections.defaultdict(list)
for d in L: G[v(d)].append(d)
for ver in sorted(G):
    al=0
    print('=== version #%d ==='%ver)
    for d in G[ver]:
        c=d['context']; r=d.get('reponse') or ''; e=c.get('eval_blancs_cp'); camp=c.get('camp_alain')
        m=re.search(r'gaffe|erreur|imprecision|bon coup|excellent|meilleur coup',n(r[:150]))
        off=n(str(c.get('verdict_qualite_officiel')))
        f=[]
        if m and m.group(0).replace('bon coup','bon') not in off: f.append('VERDICT %s au lieu de %s'%(m.group(0),off))
        if e is not None and abs(e)>=50 and (e>0)!=(camp=='blancs') and re.search(r'tu restes (\w+ )?mieux|pour toi|en ta faveur',n(r)): f.append('SENS A VERIFIER')
        if f: al+=1; print(d['id'],camp,e,f)
    ex={(d['context'].get('fen_depart_exercice'),d['context'].get('coup_propose')) for d in G[ver]}
    bl=len({(d['context'].get('fen_depart_exercice'),d['context'].get('coup_propose')) for d in G[ver] if d['context'].get('camp_alain')=='blancs'})
    print('exercices:',len(ex),'(dont Blancs:',bl,') | avis:',len(G[ver]),'| avis avec alerte:',al)
