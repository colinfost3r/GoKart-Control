from pathlib import Path
from collections import Counter, defaultdict
import hashlib,json,math,struct,sys,zipfile,ast
p=Path(sys.argv[1]); report={'operation':'offline_export_verification','hardware_tested':False,'files':{}}
for f in sorted(p.glob('*')):
    if f.suffix not in ('.stl','.step','.f3d','.py'): continue
    data=f.read_bytes(); row={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    if f.suffix=='.stl':
        n=struct.unpack_from('<I',data,80)[0]; assert len(data)==84+50*n,(f,'length')
        edges=Counter(); oriented=Counter(); vertex_faces=defaultdict(list); bounds=[[math.inf,-math.inf] for _ in range(3)]
        for i in range(n):
            a=struct.unpack_from('<12fH',data,84+50*i)
            vv=[tuple(round(x,6) for x in a[j:j+3]) for j in (3,6,9)]
            assert all(math.isfinite(x) for v in vv for x in v),(f,i,'finite')
            u=[vv[1][j]-vv[0][j] for j in range(3)];v=[vv[2][j]-vv[0][j] for j in range(3)]
            cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            assert sum(x*x for x in cross)>1e-18,(f,i,'degenerate')
            for vertex in vv:
                vertex_faces[vertex].append(i)
                for j,x in enumerate(vertex): bounds[j]=[min(bounds[j][0],x),max(bounds[j][1],x)]
            for a,b in zip(vv,vv[1:]+vv[:1]):
                edges[tuple(sorted((a,b)))]+=1;oriented[(a,b)]+=1
        assert all(c==2 for c in edges.values()),(f,'open/nonmanifold')
        assert all(oriented[(b,a)]==c for (a,b),c in oriented.items()),(f,'winding')
        parent=list(range(n))
        def find(a):
            while parent[a]!=a: parent[a]=parent[parent[a]];a=parent[a]
            return a
        for faces in vertex_faces.values():
            a=find(faces[0])
            for b in faces[1:]: parent[find(b)]=a
        comps=len({find(i) for i in range(n)});assert comps==1,(f,'components',comps)
        row.update(triangles=n,closed_manifold=True,consistent_winding=True,connected_components=comps,bounds_mm=bounds,extent_mm=[round(b-a,6) for a,b in bounds])
    elif f.suffix=='.step':
        assert data.lstrip().startswith(b'ISO-10303-21;') and b'END-ISO-10303-21;' in data,(f,'STEP envelope')
        row['step_envelope_valid']=True
    elif f.suffix=='.f3d':
        with zipfile.ZipFile(f) as z: methods=sorted({i.compress_type for i in z.infolist()})
        row.update(zip_directory_readable=True,compression_methods=methods,crc_check='Not performed: Python zipfile does not support Fusion compression method 93; no round-trip reopen claimed.')
    else:
        ast.parse(data.decode());row['python_syntax_valid']=True
    report['files'][f.name]=row
assert sum(f.endswith('.stl') for f in report['files'])>=3,'Missing printable files'
(p/'export-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
