"""Audit executed routes against E2b's own frozen deployment."""
import ast
from configparser import ConfigParser
from benchmarks.layout import scenario
from rcaps.v3.topology import TopologyModel


def audit(row, solution_path, cluster_path, physical_path):
    solution, cluster = ConfigParser(), ConfigParser()
    if not solution.read(solution_path) or not cluster.read(cluster_path):
        raise FileNotFoundError('E2b deployment')
    spans = {}
    for name, encoded in solution['Solution'].items():
        layers = ast.literal_eval(encoded)
        if layers:
            spans[int(name.rsplit('_', 1)[-1])-2] = (layers[0], layers[-1]+1)
    def node(name):
        return name if name in ('source','sink') else int(name.rsplit('_',1)[-1])-2
    edges = {(node(cluster[name]['in']),node(cluster[name]['out']))
             for name in ast.literal_eval(cluster['Links']['names'])}
    layers = TopologyModel(physical_path).layers
    count = 0
    for encoded, times in row.get('route_counts',{}).items():
        route = [int(part)-2 for part in encoded.split('-')]
        previous, boundary = 'source', 0
        for current in route:
            if (previous,current) not in edges or current not in spans:
                raise ValueError('Executed edge absent from E2b deployment: '+encoded)
            start,end = spans[current]
            if start != boundary:
                raise ValueError('Executed path skips or overlaps layers: '+encoded)
            previous,boundary = current,end
        if boundary != layers or (previous,'sink') not in edges:
            raise ValueError('Executed path lacks complete coverage: '+encoded)
        count += times
    return {'actual_distinct_paths':len(row.get('route_counts',{})),
            'routed_requests':count,'checked':True}
