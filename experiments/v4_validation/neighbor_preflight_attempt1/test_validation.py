"""Small engineering checks; none are publication performance evidence."""
from itertools import product
from types import SimpleNamespace as N
import unittest

from simulator.event_simulator.model import ModelLayer
from simulator.event_simulator.request import RequestPhase
from .diagnostics import singleton_profile
from .parallax_mechanism import ParallaxInspiredScheduler


class ValidationTests(unittest.TestCase):
    def test_singleton_intervention_preserves_prompt_and_multi_decode(self):
        layer=ModelLayer(0,1.)
        layer.prompt_bs2time={0:0.,10:10.};layer.prompt_bs2vram={0:0.,10:1.}
        layer.decode_bs2time={0:0.,1:2.,2:3.};layer.decode_bs2vram={0:0.,1:1.,2:2.}
        prompt=N(phase=RequestPhase.Initialization,token_seq_length=5)
        decode=N(phase=RequestPhase.Increment,token_seq_length=1)
        self.assertEqual(layer.get_inference_statistics([prompt,decode])[0],9.)
        with singleton_profile(1):
            self.assertEqual(layer.get_inference_statistics([prompt,decode])[0],7.)
            self.assertEqual(layer.get_inference_statistics([prompt])[0],5.)
            self.assertEqual(layer.get_inference_statistics([decode,decode])[0],3.)
        self.assertEqual(layer.get_inference_statistics([decode])[0],4.)

    def test_neighbor_layer_dp_matches_exhaustive_chain_cost(self):
        nodes={2:N(node_uid=2,in_vram_model_layers={0:None,1:None}),
               3:N(node_uid=3,in_vram_model_layers={0:None}),
               4:N(node_uid=4,in_vram_model_layers={1:None,2:None})}
        edges={(0,2):1.,(0,3):.2,(2,4):.4,(3,4):.3,(4,1):.1}
        links={i:N(node_in=N(node_uid=a),node_out=N(node_uid=b),latency=cost,link_uid=i)
               for i,((a,b),cost) in enumerate(edges.items())}
        services={2:1.,3:.5,4:.8}
        scheduler=object.__new__(ParallaxInspiredScheduler)
        scheduler.simulator=N(source_node=N(node_uid=0),sink_node=N(node_uid=1),
            compute_nodes=nodes,links=links,current_time=0.,model_manager=N(get_num_layers=lambda:3))
        scheduler.allowed_edges=set(edges);scheduler.routes_assigned=0
        scheduler._allow_placement_edge=lambda a,b:(a,b) in edges
        scheduler._release_snapshot=lambda:({2:2.,3:0.,4:0.},{})
        scheduler._layer_service=lambda node,layer,phase,tokens:services[node.node_uid]
        stages=scheduler._route(N(token_seq_length=10))
        actual=tuple(s.node_uid for s in stages[:-1] for _ in s.layers_to_infer)
        possible=[]
        for chain in product(nodes,repeat=3):
            if any(layer not in nodes[uid].in_vram_model_layers for layer,uid in enumerate(chain)):continue
            hops=[(0,chain[0]),*[(a,b) for a,b in zip(chain,chain[1:]) if a!=b],(chain[-1],1)]
            if any(h not in edges for h in hops):continue
            cost=sum(edges[h] for h in hops)+sum(services[u]+(1. if u==2 else 0.) for u in chain)
            possible.append((cost,chain))
        self.assertEqual(actual,min(possible)[1])
        self.assertEqual([l for s in stages[:-1] for l in s.layers_to_infer],[0,1,2])


if __name__=='__main__':unittest.main()
