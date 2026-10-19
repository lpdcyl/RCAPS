# Paper-ready M2 ablation text

## Experimental setup

To isolate the effect of M2's shared-prefix replica structure, we fixed the
single segment boundary at layer 48 and pruned a frozen three-branch parent
placement to one, two, or three complete suffix replicas. The one-branch
variant has exactly one copy of every model layer and one complete execution
path. Within each resource pool, the physical GPUs, shared-prefix assignment,
request trace, M1 compatibility construction, M3 live routing costs, and
1800-second fixed window were identical. The primary comparison restricts
prompt routes to the canonical complete replica paths, so increasing the
number of branches does not simultaneously introduce thousands of
cross-replica paths. We separately repeated selected windows with the full
M1-compatible DAG. All windows have zero warmup and do not drain the backlog
after the horizon.

## Results and interpretation

Across three paired seeds, increasing the number of suffix replicas from one
to three raised mean output throughput from 124.3 to 133.7 token/s at 600
offered token/s in the single-cluster pool and from 64.9 to 69.5 token/s at
320 offered token/s in the three-cluster pool. Completion fractions rose
from 0.849 to 0.939 and from 0.817 to 0.897, respectively, while end-of-window
backlogs fell by 97.0 and 46.3 requests. On requests completed by both
variants, the seed-mean P95 time per output token fell from 1.311 to 0.547 s
and from 1.540 to 0.841 s. Each of the three paired seeds showed the same
throughput ordering. The all-subset check at the key load found that every
two-branch combination outperformed every single-branch choice, and the
three-branch parent outperformed all two-branch combinations in both pools.

To control the number of active GPUs, we compared two and three suffix
replicas using the same 24 GPUs and the same shared prefix in the
single-cluster pool. At 700 offered token/s, the three-branch structure
increased three-seed mean throughput from 154.1 to 156.5 token/s, increased
completion fraction from 0.911 to 0.927, and reduced backlog from 113.7 to
93.3 requests. This is a modest 1.5% throughput gain. The number of deployed
layer copies changes from 112 to 144, so the comparison isolates active GPU
count, not the amount of replicated model state or the resulting layer
partition. The canonical and full-DAG seed-0 checks retained the ordering
between two and three branches in both pools.

The resource evidence points to increased **concurrent serving capacity**
rather than GPU arithmetic saturation. In the single-cluster seed-0 pressure
window, routed requests spread across three suffix branches (477/418/396),
and the largest per-exit GPU queue wait on those branches fell from 16.5 ms
for the single path to 3.7--5.3 ms. Maximum GPU busy fractions remained below
0.24. The static aggregate suffix KV-token upper bound grew from 1.12 million
for one branch to 3.37 million for three branches, close to the shared-prefix
upper bound. In the three-cluster pool, the busiest link's occupied fraction
fell from 0.371 to 0.160 as traffic spread across suffix links. We did not
sample time-varying KV occupancy directly; the KV explanation is supported by
the placement capacity audit and by capacity assertions under higher offered
loads, rather than a measured KV-utilization curve.

## Reporting boundary

At 700 offered token/s, the single-path single-cluster deployment triggered
the simulator's KV-cache capacity assertion in two of the three preselected
confirmatory seeds. These windows are reported as capacity failures and are
never entered as zero-throughput observations. The 600 offered token/s
comparison uses a separately declared, independent seed set (4/5/6) and is
labelled as an adaptive supplementary comparison. Exploratory load-scan and
all-subset results use seed 0; full-DAG transfer checks also use one seed.
With three confirmatory seeds, we report paired directions and ranges rather
than statistical significance. These are simulator findings and do not by
themselves establish production hardware throughput.

## Suggested figure caption

**Effect of M2 suffix replication.** Each point shows one independent
1800-second fixed-window trace, and the large marker and whiskers show the
three-seed mean and observed range. The single-cluster panel uses the
adaptive 600-token/s comparison; the three-cluster panel uses the preselected
320-token/s comparison. The same-GPU two-branch control is shown separately
in the single-cluster panel. Output throughput, completion fraction, and
end-of-window backlog are reported together because throughput alone can
obscure unfinished requests.
