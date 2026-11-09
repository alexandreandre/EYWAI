import json,glob,collections,sys,re
import importlib.util
import pathlib
spec=importlib.util.spec_from_file_location('c5',pathlib.Path(__file__).with_name('comparer5.py'));c5=importlib.util.module_from_spec(spec);spec.loader.exec_module(c5)
av,ap=c5.charger(sys.argv[1]),c5.charger(sys.argv[2])
tot=collections.Counter();ex={};soc=collections.Counter();mont=collections.Counter()
nb=0
for k in sorted(set(av)&set(ap)):
    a,b=av[k],ap[k]
    if a['statut']!='ok' or b['statut']!='ok': continue
    d=c5.diff(a['payslip_data'],b['payslip_data'],'.data')+c5.diff(a.get('vue'),b.get('vue'),'.vue')+c5.diff(a.get('enrichissement'),b.get('enrichissement'),'.enrichissement')
    if d: nb+=1
    for c,x,y in d:
        g=re.sub(r'\[\d+\]','[]',c)
        tot[g]+=1
        ex.setdefault(g,(k,x,y))
        s=k.split('|')[0]
        if isinstance(x,(int,float)) and isinstance(y,(int,float)) and not c.startswith('.vue') and not c.endswith('[len]'):
            mont[(s,g)]+=1
print('bulletins avec ecart',nb)
for g,n in tot.most_common():
    if g.startswith('.vue.lignes'): continue
    k,x,y=ex[g]
    print(n,g,'|',str(x)[:70],'->',str(y)[:70])
print('-- vue')
for g,n in tot.most_common():
    if g.startswith('.vue.lignes'): print(n,g)
print('-- numeriques hors vue',mont.most_common(30))
# vue: comparer les lignes a contenu, sans les notes retirees
diffs=collections.Counter();exs={}
for k in sorted(set(av)&set(ap)):
    a,b=av[k],ap[k]
    if a['statut']!='ok' or b['statut']!='ok': continue
    la=[l for l in (a.get('vue') or {}).get('lignes',[])]
    lb=[l for l in (b.get('vue') or {}).get('lignes',[])]
    def norm(ls):
        out=[]
        for l in ls:
            l=dict(l);lib=str(l.get('libelle'))
            lib=lib.replace("Réduction HS structurelles (jours d'absence)","Heures sup. du contrat non faites (absence)").replace("Réduction HS structurelles (événement familial)","Heures sup. du contrat non faites (événement familial)")
            l['libelle']=lib
            out.append(json.dumps(l,sort_keys=True,ensure_ascii=False))
        return out
    A,B=norm(la),norm(lb)
    ca,cb=collections.Counter(A),collections.Counter(B)
    for x in (ca-cb):
        j=json.loads(x);t=j.get('type');lib=j.get('libelle','')
        diffs[('retirée',t,lib[:28])]+=1
    for x in (cb-ca):
        j=json.loads(x);t=j.get('type');lib=j.get('libelle','')
        diffs[('ajoutée',t,lib[:28])]+=1
print('-- lignes de vue retirees/ajoutees')
for d,n in diffs.most_common(30): print(n,d)
# nets, bruts, imposable
n=0
for k in set(av)&set(ap):
    a,b=av[k],ap[k]
    if a['statut']!='ok' or b['statut']!='ok': continue
    A,B=a['payslip_data'],b['payslip_data']
    for v in ('net_a_payer','salaire_brut'):
        if abs((A.get(v) or 0)-(B.get(v) or 0))>0.005:n+=1
    if abs(((A.get('synthese_net') or {}).get('net_imposable') or 0)-((B.get('synthese_net') or {}).get('net_imposable') or 0))>0.005:n+=1
print('net brut imposable differents',n)
