"""Small decisive unit checks; integration evidence comes from isolated runs."""
import unittest
from collections import Counter
from types import SimpleNamespace as NS
from unittest.mock import patch

from work3_control.scheduler import StableGate, RouteController
from work3_control.report import execution_metrics, decide
from experiments.v3_pathspace_ablation.run import CanonicalGraphDagScheduler


class ControlTests(unittest.TestCase):
    def test_generator_supports_registered_exact_stage_durations(self):
        from work3_control.run import trace_for
        for duration in (10,200):
            first=trace_for(106,duration)
            self.assertEqual(first,trace_for(106,duration))
            self.assertTrue(all(0<=t<3*duration and p>0 and 0<o<=1000 for t,p,o in first))

    def test_time_based_gate_and_dwell(self):
        gate=StableGate()
        self.assertFalse(gate.update(10, 1))
        self.assertFalse(gate.update(10.5, 1))
        self.assertTrue(gate.update(11, 1))
        self.assertTrue(gate.update(11.1, -10))
        self.assertFalse(gate.update(12, -10))
        self.assertEqual(gate.switches,2)

    def test_deadband_is_strict_and_time_cannot_reverse(self):
        gate=StableGate()
        self.assertFalse(gate.update(0,0.01))
        self.assertFalse(gate.update(100,0.01))
        with self.assertRaises(ValueError): gate.update(99,0)
        with self.assertRaises(ValueError): gate.update(101,float('nan'))

    def test_probe_restores_route_count_on_success_and_failure(self):
        obj=object.__new__(RouteController)
        obj.routes_assigned=2
        obj._capacity_veto=True
        def probe(self,req):
            self.routes_assigned+=1
            return ['route']
        with patch.object(CanonicalGraphDagScheduler,'_route',probe):
            self.assertEqual(obj._probe(None,frozenset()),['route'])
        self.assertEqual(obj.routes_assigned,2)
        with patch.object(CanonicalGraphDagScheduler,'_route',side_effect=RuntimeError('Placement has no source-to-sink layer route')):
            self.assertIsNone(obj._probe(None,frozenset()))
        self.assertEqual(obj.routes_assigned,2)

    def test_round_proxy_singleton_and_batch_limit(self):
        obj=object.__new__(RouteController)
        obj._layer_service=lambda n,l,p,b: 0.1+0.01*b
        node=NS(inference_settings=NS(decode_typical_tokens=2,decode_max_tokens=2),in_vram_model_layers={0:None,1:None})
        self.assertEqual(obj._round_work(node,0),0)
        self.assertAlmostEqual(obj._round_work(node,1),0.44)
        self.assertAlmostEqual(obj._round_work(node,2),0.24)
        self.assertAlmostEqual(obj._round_work(node,3),0.68)

    def test_exact_whole_path_score_uses_current_state(self):
        obj=object.__new__(RouteController)
        node=NS(node_uid=2)
        obj.simulator=NS(current_time=10,compute_nodes={2:node},links={4:object(),5:object()})
        obj._layer_service=lambda *a:2
        obj._decode_token_service=lambda *a:0.5
        obj._transfer_time=lambda *a:0.2
        route=[NS(link_uid=4,node_uid=2,layers_to_infer=[0,1]),NS(link_uid=5,layers_to_infer=None)]
        score,terms=obj._score(route,NS(token_seq_length=9),({2:13},{4:11,5:10}),Counter({2:2}))
        self.assertAlmostEqual(score,9.4)
        self.assertAlmostEqual(score,sum(terms.values()))

    def test_execution_work_clips_at_window_and_retains_lifecycle(self):
        events=[[1,2,2,0,2,0],[4,3,2,1,1,0],[6,1,3,0,0,1]]
        metric=execution_metrics(events,5)
        self.assertEqual(metric['gpu_seconds_window'],3)
        self.assertEqual(metric['gpu_seconds_lifecycle'],6)
        self.assertEqual(metric['mean_decode_batch'],1.5)
        self.assertEqual(metric['prompt_request_layer_executions'],1)

    def test_gate_rejects_only_beating_full_when_partial_is_stronger(self):
        def item(tpot,cost,action=0):
            return dict(tpot=tpot,gpu_per_token=cost,throughput=100,ttft=1,expanded_selected=action)
        data={str(s):dict(canonical=item(1.5,2),partial=item(1,1),full=item(1.2,2),
                         adaptive_link=item(1.1,1.5),route_control=item(1.05,1.1,3)) for s in [104,105]}
        self.assertFalse(decide(data,[104,105])['performance_gate_pass'])

    def test_gate_requires_real_actions(self):
        def item(tpot,cost,action=0):
            return dict(tpot=tpot,gpu_per_token=cost,throughput=100,ttft=1,expanded_selected=action)
        data={str(s):dict(canonical=item(1.5,2),partial=item(1,1),full=item(1.2,2),
                         adaptive_link=item(1.1,1.5),route_control=item(0.9,0.8)) for s in [104,105]}
        self.assertFalse(decide(data,[104,105])['performance_gate_pass'])


if __name__=='__main__': unittest.main()
