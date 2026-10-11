"""Parse OSM XML (optionally .gz) into simple dicts: nodes {id: (lon, lat, tags)}, ways {id: (node_ids, tags)}, relations."""
import gzip
from lxml import etree
def load(files):
    nodes={}; ways={}; rels={}
    for f in files:
        src = gzip.open(str(f), 'rb') if str(f).endswith('.gz') else open(str(f), 'rb')
        for ev, el in etree.iterparse(src, events=('end',), tag=('node','way','relation')):
            i=int(el.get('id'))
            if el.tag=='node':
                if i not in nodes:
                    tags={t.get('k'):t.get('v') for t in el.findall('tag')}
                    nodes[i]=(float(el.get('lon')),float(el.get('lat')),tags)
            elif el.tag=='way':
                if i not in ways:
                    ways[i]=([int(n.get('ref')) for n in el.findall('nd')],{t.get('k'):t.get('v') for t in el.findall('tag')})
            else:
                if i not in rels:
                    rels[i]=([(m.get('type'),int(m.get('ref')),m.get('role')) for m in el.findall('member')],{t.get('k'):t.get('v') for t in el.findall('tag')})
            el.clear()
    return nodes, ways, rels
