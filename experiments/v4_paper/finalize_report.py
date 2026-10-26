"""Build final Chinese conclusions and paired-effect figures from audited data."""
from statistics import mean, stdev
from .build_report import HERE, collect, campaign_complete, paired, group


def main():
    rows, _, states = collect()
    assert campaign_complete(states), "Final conclusions require all registered cells"
    total = sum(s["completed"]+len(s["failed"]) for s in states.values())
    assert total == 122 and sum(len(s["failed"]) for s in states.values()) == 2

    def table(configs):
        out = ["| 场景/负载 | 对照 | TPOT % | TTFT % | GPU 秒/token % | 输出吞吐 % |",
               "|---|---|---:|---:|---:|---:|"]
        for sc, load, left, right in configs:
            effect = paired(rows,sc,load,left,right)
            assert effect["complete"]
            cells = []
            for metric in ("tpot_p95_s","ttft_p95_s","gpu_seconds_per_output_token","output_throughput_tokens_per_s"):
                values = [p["relative"][metric]*100 for p in effect["seeds"]]
                cells.append(f"{mean(values):+.2f} ± {stdev(values):.2f}")
            out.append(f"| {sc}/{load} | {right} 相对 {left} | " + " | ".join(cells) + " |")
        return "\n".join(out)

    curve = [(sc,load,"v3","v4") for sc,loads in (("single",[100,200,350,500,700,900]),("multi",[50,100,160,240,320,400])) for load in loads]
    factorial = [("multi",load,a,b) for load in (160,320) for a,b in (("v3","spatial"),("v3","temporal"),("v3","v4"),("temporal","v4"),("spatial","v4"))]
    mechanism = [("multi",320,c,"v4") for c in ("canonical4","all4","chunk1","chunk2","chunk8")]
    components = [(sc,load,c,"v4") for sc,load in (("single",700),("multi",320)) for c in ("single_boundary","static")]
    pools = [("C2",160,"v3","v4"),("C3",400,"v3","v4")]
    external = [(sc,load,c,"v4") for sc,load in (("single",350),("multi",160)) for c in ("helix","swarm","separate")]
    text = f"""# RCAPS V4 正式三种子实验完成报告

完成日期：2026-10-26；最后一个正式窗口于北京时间 20:34:08 结束。

## 1. 完成范围与结论

**本次登记的 120 个窗口已全部获得成功结果，共 122 次尝试，2 次原生崩溃失败永久保留。**
主批次成功 70 格、外部批次成功 27 格、第一次授权恢复成功 15 格、第二次授权恢复成功 8 格。
旧队列 index 的 halted 是历史事实，不改写为 completed；去重后的有效窗口集合已补齐。
正式条件统一为 seed 0/1/2、1800 秒、零预热、不排空；默认 4 MiB 和慢链路阈值均未据结果调参。

V4 应作为集成方法呈现：保留冻结 V3 的合法图表示 M1、放置 M2 与实时路由 M3，加入静态稀疏边准入 S 和慢计算链路上的固定 Prompt 激活传输分块 T。现有实验支持**空间聚合与时间让出的互补控制**。在 C1 三集群 320，相对 V3，TPOT 逐种子平均降低 13.39%、GPU 秒/token 降低 27.36%。但 C2/C3 没有稳定的尾延迟收益，组件消融和块长实验也显示工作量与延迟折中。

本报告是已登记模拟实验的完成报告，**不等于所有稳健性、真实硬件或论文证据已经完成**。两次重跑由用户分别明确授权；成功不能证明原生崩溃或历史 TypeError 根因已解决。

## 2. 指标与审计口径

下面百分比为每个种子先算 `目标/对照−1`，再报告三种子的均值 ± 样本标准差（百分点）；负数表示该指标下降。不是均值之比，不是置信区间，不据此声称统计显著。种子 0/1/2 已被观察过，不称作未见测试种子。

TPOT 为请求平均 token 间隔的 P95，不是逐 token 间隔 P95。GPU 秒/token = 窗口内各物理 GPU 忙碌秒数总和 / 窗口输出 token 数，是工作量代理，不是实测能耗、GPU 部署数量或总容量。
绝对值、完成率和末端积压见 [自动数值表](RESULTS_CN.md)及 [逐种子 CSV](individual.csv)；逐请求共同完成子集的配对指标见 [analysis.json](analysis.json)。
在不排空协议下，更少的 GPU 工作可能伴随更多请求滞留，不能脱离完成率和延迟单独评价组件。

检查已覆盖所有成功文件哈希、冻结源码/输入与环境、种子与窗口协议、请求 trace/ID/长度/到达时间配对、GPU 与链路占用边界、GPU 分阶段求和和工作量换算。43 组可用 V4 对照中，42 组齐全三种子；唯一不完整的是历史 Helix 三集群 400 点，原 seed 0 失败继续保留，不填零、不补换种子。该历史失败不计入本次新运行的 122 次尝试。
历史曲线 71 个成功结果经过身份/执行等价性审核后复用，同条件新结果优先；因此图中并非所有对照都属于这次 120 格。
审计入口为 [integrity_audit.json](diagnostics/integrity_audit.json)。哈希和守恒通过确认记录自洽，不能排除存在原生崩溃的主机上未被检测到的数值问题；独立稳定环境复核仍是发布前证据缺口。

## 3. 整体结果与外部比较

### C1 主曲线：V4 相对冻结 V3

{table(curve)}

C1 两拓扑的负载点平均 TPOT 均改善，但部分 TTFT 点退化；输出吞吐变化较小，不能将本扫描写成最大服务容量验证。图见 [负载曲线](figures/v4_load_curves.png)和 [GPU 工作曲线](figures/v4_gpu_work_curves.png)。

### 共同较低负载的外部方法

{table(external)}

外部基线使用相同请求协议并补齐同口径 GPU 计量，SP 覆盖所有实际分区。低负载共同点与 700/320 锚点须分开陈述，不拼接不同负载的绝对比较。外部重计量与历史端到端结果/请求记录等价性检查通过。

## 4. 空间与时间两层机制

S 静态限制可选边，目标是减少执行分散、维持 Decode 聚合；M3 仍在准入图内实时选路。T 将符合阈值的慢计算链路上的 Prompt 激活传输分成块，在块边界释放资源并给就绪 Decode 发送机会。它不是计算层 chunked prefill，也不是重新发明 Decode 优先级。

{table(factorial)}

在三集群 320，V3/仅 S/仅 T/V4 的实际路径数均值为 33/8/31/8，token 加权 Decode batch 约为 6.80/9.66/6.58/9.21，Decode 网络等待总量约为 7547/8013/2593/2778 秒。S 单独改善聚合与工作量，却使该点 TPOT 上升；T 主要缓解传输等待；联合后同时改善相对 V3 的延迟和工作量。结果支持机制互补，不能把全部等待归因于 Prompt 占用重叠，发送/接收 NIC 重叠也不得相加。

320 的 TPOT 对数交互项三种子均为负，160 的符号不一致；不得将其写为普适或统计显著的超加性协同。图见 [四格消融](figures/v4_factorial_320.png)、[机制观测](figures/v4_mechanism_320.png)。

### 路径保留、分块作用范围与块长

{table(mechanism)}

相对“规范图+T”，稀疏 V4 改善延迟但增加约 70.2% GPU 工作，说明保留绕行存在代价。相对全链路分块，慢链路限定并非该点 TPOT 最优。4 MiB 相对 1/2 MiB 延迟更高、工作量更低，相对 8 MiB 则延迟更低、工作量略高。因此 4 MiB 只能定位为预先冻结的折中；本实验不支持“4 MiB 最优”“全指标最优”或“只分慢链路始终优于全链路”。该敏感性仅覆盖一个拓扑/负载。

## 5. 最终系统内的 M2/M3 与资源池泛化

{table(components+pools)}

单集群 M2 放置消融有约 31.5% TPOT 收益，但 GPU 工作增加约 173%；三集群相对单边界对照没有稳定改善，不能把单集群的多阶段收益推广过去。两拓扑的实时 M3 相对静态路由明显降低 TPOT，但 GPU 工作大幅增加。相同固定窗口内，单集群完成率均值从静态路由的 85.05% 提高到 V4 的 94.05%，末端积压从 192 降至 76.3；三集群从 89.07% 提高到 92.29%，积压从 63.3 降至 44.7。故不能只用静态路由较低的 GPU 秒/token 宣称它整体更优，也不能隐去 V4 的工作量代价。

C2 的 TPOT 变化按 seed 0/1/2 为约 −4.12%/+1.42%/+1.48%，没有一致延迟收益；C3 三个种子 TPOT 都略高于 V3，TTFT 平均增加 2.15%。C2/C3 的主要支持点是 GPU 工作分别下降约 73.15%/32.74%，不是广泛尾延迟改善。图见 [组件与泛化配对效应](figures/v4_components_pools.png)。当前资源池对照不能替代真实多硬件系统验证。

## 6. 失败、重跑与可追溯性

| 原失败窗口 | 首次失败记录 | 授权第二尝试 | 最终状态 |
|---|---|---|---|
| single/700/static/seed1 | v4_formal，0xC0000005，模型统计位置 | v4_recovery | 成功，旧失败保留 |
| C2/160/v4/seed1 | v4_recovery，0xC0000005，deepcopy 位置 | v4_recovery2 | 成功，旧失败保留 |

完整诊断和两次授权过程见 [执行审计](EXECUTION_AUDIT_CN.md)。没有静默替换窗口、删掉异常值、改变种子或用成功覆盖失败。不得将结果写成“120/120 首次运行成功”。运行环境稳定性与历史 TypeError 仍未闭环。
240 个去重冻结输入另有 [原始字节 ZIP](diagnostics/frozen_inputs_exact_bytes.zip)，用于避免跨平台 Git 换行转换造成哈希失配。不要覆盖旧运行现场；复核应在独立目录进行。

## 7. 论文可用表述与剩余证据

可用表述：**“RCAPS V4 通过静态稀疏路径准入保持执行聚合，并在慢链路上用固定粒度的 Prompt 激活分块提供传输让出机会。在 C1 的受测负载下，相比冻结 V3 改善 TPOT 与 GPU 忙碌工作量；空间与时间控制具有互补作用，但延迟收益及工作量代价依赖拓扑、资源池和组件配置。”**

| 证据项 | 本次状态 | 论文处理/后续需求 |
|---|---|---|
| 集成 V4 vs V3、共同负载外部比较 | 已完成受测条件 | 主表、曲线、失败说明同时呈现 |
| 两负载 2×2、规范/稀疏/完整图、全链路范围、1/2/4/8 MiB | 已完成受测条件 | 支持互补与折中，不支持普适最优 |
| M2/M3 条件消融、C2/C3 对照 | 已完成 | 保留资源池延迟退化与组件工作量代价 |
| 原生崩溃及历史 TypeError | 根因未解决 | 独立稳定环境复核，保留失败，不将重跑当修复 |
| 带宽/RTT/慢链路阈值、画像偏差 | 本次未覆盖 | 若声称跨网络/画像稳健，需额外受控实验 |
| 请求长度/突发性、窗口/预热敏感性 | 本次未覆盖 | 检验负载形态与窗口选择依赖 |
| 真实系统的块间让出及调度开销 | 本次未覆盖 | 不能用模拟暂停次数替代实测 CPU/网络开销 |
| 能量、部署规模与最大容量 | 本次不能推出 | 节能需功率积分，规模需更大/真实异构部署，容量需明确饱和或 SLO 扫描 |
| 更强空间反事实和因果分解 | 仍可补强 | 固定批量/路径聚合反事实或 matched-work 对照；现有观测不是全部等待的因果归属 |

上述缺口仅是下一阶段规划，本次未擅自增加实验或开发种子。历史单集群阶段干扰等其他本地目录不自动并入本报告；若正文引用，需单独完成来源与失败审计。

重建命令（使用原冻结环境变量）：

```powershell
python -m experiments.v4_paper.build_report --require-complete --plots
python -m experiments.v4_paper.finalize_report
python -m experiments.v4_paper.check_integrity
```
"""
    (HERE / "FINAL_RESULTS_CN.md").write_text(text,encoding="utf-8")
    figures(rows,components+pools)


def figures(rows,configs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size":10,"pdf.fonttype":42})
    folder = HERE / "figures"
    fig,axes=plt.subplots(1,2,figsize=(12,4.3),constrained_layout=True)
    labels=[f"{sc}/{load}: V4 vs {left}" for sc,load,left,_ in configs]
    for ax,metric,title in zip(axes,("tpot_p95_s","gpu_seconds_per_output_token"),("P95 TPOT change (%)","GPU seconds / output token change (%)")):
        for i,(sc,load,left,right) in enumerate(configs):
            e=paired(rows,sc,load,left,right)
            vals=[p["relative"][metric]*100 for p in e["seeds"]]
            ax.errorbar(mean(vals),i,xerr=stdev(vals),fmt="D",capsize=3,color="#0072B2",markersize=5)
            ax.scatter(vals,[i-.12,i,i+.12],color="#333333",s=16,zorder=3)
        ax.axvline(0,color="gray",linestyle="--",linewidth=1)
        ax.set_yticks(range(len(labels)),labels)
        ax.invert_yaxis()
        ax.set_xlabel(title)
        ax.grid(axis="x",alpha=.2)
    fig.suptitle("Paired seed effects: individual seeds, mean and sample SD; lower is better")
    for ext in ("png","pdf"): fig.savefig(folder/f"v4_components_pools.{ext}",dpi=180)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(9,3.5),constrained_layout=True)
    for ax,(sc,loads) in zip(axes,(("single",[100,200,350,500,700,900]),("multi",[50,100,160,240,320,400]))):
        for cell,color in (("v3","#009E73"),("v4","#0072B2")):
            gs=[group(rows,sc,l,cell)["gpu_seconds_per_output_token"] for l in loads]
            ax.errorbar(loads,[g["mean"] for g in gs],yerr=[g["sd"] for g in gs],marker="o",capsize=3,color=color,label=cell.upper())
        ax.set_title("C1 single cluster" if sc=="single" else "C1 three clusters")
        ax.set_xlabel("Offered input + target output (tokens/s)")
        ax.set_ylabel("GPU seconds / output token")
        ax.grid(alpha=.2)
        ax.legend()
    fig.suptitle("Mean and sample SD across seeds 0/1/2; GPU work, not energy")
    for ext in ("png","pdf"): fig.savefig(folder/f"v4_gpu_work_curves.{ext}",dpi=180)
    plt.close(fig)


if __name__ == "__main__": main()
