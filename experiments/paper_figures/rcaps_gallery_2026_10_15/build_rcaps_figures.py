"""RCAPS evidence figures, sourced from reports in lpdcyl/RCAPS (2026-10-15).
Generates one Matplotlib axes per figure (no subplots) and a multipage PDF.
All values are descriptive means or paired % changes, not inferential confidence intervals.
"""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import MaxNLocator, FuncFormatter
from zipfile import ZipFile, ZIP_DEFLATED
import textwrap, json, csv, re

OUT=Path(__file__).resolve().parent
PNG=OUT/'PNG'; SVG=OUT/'SVG'
PNG.mkdir(parents=True,exist_ok=True); SVG.mkdir(parents=True,exist_ok=True)
PDF=OUT/'RCAPS_V2_V1_实验图册_2026-10-15.pdf'
ZIP=OUT/'RCAPS_全部实验图_PNG_SVG_2026-10-15.zip'
INDEX=OUT/'INDEX.md'
REPO='https://github.com/lpdcyl/RCAPS/blob/main/'
plt.rcParams.update({'font.family':'Noto Sans CJK JP','font.size':11,'axes.titlesize':14,'axes.labelsize':11,
                     'xtick.labelsize':10,'ytick.labelsize':10,'legend.fontsize':10,'axes.unicode_minus':False,
                     'svg.fonttype':'none','pdf.fonttype':42,'figure.facecolor':'white','savefig.facecolor':'white'})
records=[]
book=PdfPages(PDF)

def split_text(text, n=82):
    # CJK full-width matters, keep 82 columns of halfwidth or 41 Han characters.
    out=[]; cur=''; width=0
    for ch in text:
        w=2 if ord(ch)>127 else 1
        if width+w>n and cur:out.append(cur);cur='';width=0
        cur+=ch;width+=w
    if cur:out.append(cur)
    return out

def canvas(key,title,brief,caption,src,kind='bar',xn=None):
    fig=plt.figure(figsize=(13.333,7.5))
    ax=fig.add_axes([.145,.265,.785,.56])
    fig.text(.05,.943,f'{key}   {title}',fontsize=19,weight='bold',va='top')
    fig.text(.05,.875,brief,fontsize=11,va='top')
    cap=split_text('结果说明：'+caption,112)
    for j,s in enumerate(cap[:3]):fig.text(.05,.177-.035*j,s,fontsize=10,va='top')
    if len(cap)>3: print('CAP WARN', key, len(cap))
    fig.text(.05,.033,'数据：'+src,fontsize=9,va='bottom')
    fig.text(.951,.033,'Helix 离散事件仿真  |  2026-10-15',fontsize=8,ha='right',va='bottom')
    ax.grid(axis='x' if kind=='barh' else 'y',alpha=.20,zorder=0)
    ax.set_axisbelow(True)
    for s in ['top','right']:ax.spines[s].set_visible(False)
    return fig,ax

def submit(key,title,brief,caption,src,drawer,plot_type='bar',x_label='',filekey=None):
    fig,ax=canvas(key,title,brief,caption,src,kind=plot_type)
    drawer(ax)
    if x_label:ax.set_xlabel(x_label)
    name=f'{key}_{filekey or re.sub(r"[^\w一-龥]+","_",title)[:40]}'
    fig.savefig(PNG/f'{name}.png',dpi=160)
    fig.savefig(SVG/f'{name}.svg')
    book.savefig(fig)
    plt.close(fig)
    records.append({'编号':key,'图名':title,'用途':brief,'解读':caption,'数据来源':REPO+src,'PNG':f'PNG/{name}.png','SVG':f'SVG/{name}.svg'})
    print('OK',len(records),key,title,flush=True)

# Standard plotting functions; one chart axis per page.
def multi_hbar(ax,categories,series,series_names,unit='%',bar_width=.35,lim=None,fmt='{:+.1f}'):
    pos=np.arange(len(categories)); cnt=len(series)
    for k,(data,label) in enumerate(zip(series,series_names)):
        ys=pos+(k-(cnt-1)/2)*bar_width
        bars=ax.barh(ys,data,height=bar_width*.86,label=label,zorder=3)
        for y,v in zip(ys,data):
            off=.012*(max([abs(x) for arr in series for x in arr])+1)
            ax.text(v+(off if v>=0 else -off),y,fmt.format(v),ha='left' if v>=0 else 'right',va='center',fontsize=9)
    ax.set_yticks(pos,categories);ax.invert_yaxis();ax.axvline(0,lw=1,alpha=.5)
    ax.set_xlabel(unit)
    if lim is None:
        vs=[float(v) for arr in series for v in arr];lo=min(0,min(vs));hi=max(0,max(vs));pad=(hi-lo or 1)*.20
        ax.set_xlim(lo-pad if lo<0 else 0,hi+pad)
    else:ax.set_xlim(*lim)
    if cnt>1:ax.legend(loc='best',frameon=False)

def hbar(ax,names,values,unit='',fmt='{:.2f}',log=False):
    ys=np.arange(len(names));bars=ax.barh(ys,values,zorder=3)
    ax.set_yticks(ys,names);ax.invert_yaxis();
    if log:
        ax.set_xscale('log');ax.set_xlim(max(1e-4,min(values)/2),max(values)*4)
        for y,v in zip(ys,values):ax.text(v*1.06,y,fmt.format(v),va='center',fontsize=10)
    else:
        lo=min(0,min(values));hi=max(0,max(values)); pad=(hi-lo or 1)*.22
        ax.set_xlim(lo-pad if lo<0 else 0,hi+pad)
        for y,v in zip(ys,values):
            ax.text(v+((hi-lo)*.015 if v>=0 else -(hi-lo)*.015),y,fmt.format(v),va='center',fontsize=10,ha='left' if v>=0 else 'right')
        ax.axvline(0,lw=.8,alpha=.45)
    ax.set_xlabel(unit)

def line(ax,x,series,names,xlabels=None,unit='',ymin=None,ylim=None):
    for v,label in zip(series,names):
        ax.plot(x,v,marker='o',markersize=7,lw=2,label=label)
        for xx,yy in zip(x,v):ax.annotate(f'{yy:g}',(xx,yy),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
    if xlabels:ax.set_xticks(x,xlabels)
    ax.set_xlim(min(x)-.15*(max(x)-min(x) or 1),max(x)+.15*(max(x)-min(x) or 1))
    if ymin is not None:ax.set_ylim(bottom=ymin)
    if ylim is not None:ax.set_ylim(*ylim)
    ax.set_ylabel(unit);ax.legend(frameon=False,loc='best')

def heat(ax,rows,cols,matrix,unit='%',fmt='{:+.1f}',bad=None):
    arr=np.array(matrix,dtype=float)
    im=ax.imshow(arr,aspect='auto')
    ax.set_xticks(range(len(cols)),cols);ax.set_yticks(range(len(rows)),rows)
    for i in range(len(rows)):
        for j in range(len(cols)):
            val=arr[i,j]
            text_val='—' if not np.isfinite(val) else fmt.format(val)
            ax.text(j,i,text_val,ha='center',va='center',fontsize=12,weight='bold',color='white' if np.isfinite(val) and val>np.nanmin(arr)+(np.nanmax(arr)-np.nanmin(arr))*.55 else 'black')
    ax.tick_params(length=0)
    ax.grid(False)
    cbar=ax.figure.colorbar(im,ax=ax,fraction=.028,pad=.025)
    cbar.set_label(unit)

SRC_MAIN='experiments/v2_method_ablation/ADVISOR_MAIN_TABLE_CN.md'
SRC_CORE='experiments/v2_core_ablations/RESULTS_CN.md'
SRC_STRONG='experiments/v2_method_comparisons/RESULTS_CN.md'
SRC_LADDER='experiments/v2_method_ablation/INCREMENTAL_REPORT_CN.md'
SRC_V1='experiments/ccfa_validation/RESULTS.md'
SRC_STRUCTURE='experiments/structure_ablation_2026/RESULTS.md'

# 01 End-to-end V2 vs Helix
submit('01','V2 vs Helix：端到端增益','同负载三种子配对改善；延迟列表示降低，越高越好',
'三集群相对 Helix 的吞吐增益为 21.26%，P95 TTFT / TPOT 分别降低 65.78% / 78.28%。这是系统级联合收益，不能拆分归因。',SRC_MAIN,
lambda ax:multi_hbar(ax,['吞吐量 ↑','P95 TTFT ↓','P95 TPOT ↓'],[[9.59,43.88,66.86],[21.26,65.78,78.28]],['单集群','三集群'],'改善（%）',fmt='{:+.1f}'))

# 02 V2 V1
submit('02','V2 vs V1：版本增量','保留 V1 的强基线；三种子配对变化',
'V2 的吞吐提升幅度较小，但两种拓扑的尾延迟改善较明显；它验证了 V2 相对于 V1 的进一步性能增量。','experiments/adaptive_v2/RESULTS.md',
lambda ax:multi_hbar(ax,['吞吐量 ↑','P95 TTFT ↓','P95 TPOT ↓'],[[.8448,14.6032,27.5948],[2.02,25.15,27.40]],['单集群','三集群'],'改善（%）',fmt='{:+.1f}'))

# 03a four-system low load output throughput
submit('03a','四系统共同低负载：吞吐量','相同物理资源、种子、请求轨迹；单集群 350、三集群 160 offered token/s',
'单集群 V2 与 SP 吞吐基本相同；三集群 V2 较高。单集群和三集群负载不同，图中不对两场景绝对吞吐做横向排序。',
'experiments/helix_additional_baselines/COMMON_LOW_SUMMARY_CN.md',
lambda ax:multi_hbar(ax,['Helix','Swarm','SP','RCAPS V2'],[[71.886,69.160,75.636,75.619],[33.548,29.971,31.650,35.945]],['单集群 350','三集群 160'],'输出 token/s',fmt='{:.1f}'))
# 03b four-system low load TPOT
submit('03b','四系统共同低负载：P95 TPOT','同负载同轨迹；越低越好',
'V2 在两类拓扑都取得更低的 P95 TPOT；尤其相对 SP，低负载下的延迟优势比吞吐优势更明确。',
'experiments/helix_additional_baselines/COMMON_LOW_SUMMARY_CN.md',
lambda ax:multi_hbar(ax,['Helix','Swarm','SP','RCAPS V2'],[[1.066,1.390,1.065,.455],[1.543,2.584,2.309,.549]],['单集群 350','三集群 160'],'P95 TPOT（秒/token）',fmt='{:.3f}'))

# 04 native offered load capacity, scatter

def own_load(ax):
    pts=[('单 Helix',112.5,23.697),('单 Swarm',75,16.694),('单 SP',300,66.120),('单 V2',675,149.609),('三 Helix',30,6.413),('三 SP',30,np.nan),('三 V2',300,65.041)]
    for ix,(name,x,y) in enumerate(pts):
        if not np.isfinite(y):continue
        ax.scatter(x,y,s=90,zorder=5);ax.annotate(name,(x,y),xytext=(7,4+ix%3*4),textcoords='offset points',fontsize=10)
    ax.set_xlabel('各方法独立选定的 offered token/s');ax.set_ylabel('已完成输出 token/s')
    ax.set_xlim(0,760);ax.set_ylim(0,175)
submit('04','各方法自行负载的运行点','横轴负载不同：展示运行容量探索，不是公平性能排名',
'V2 两类场景使用更高的运行点；但 L90 来自有限网格、负载不统一，不能用点间斜率或差值断言端到端优越性。三集群 SP 非完整窗口未绘出。',
'experiments/helix_additional_baselines/OWN_LOAD_RESULTS_CN.md',own_load)

# 05 modeling candidate TPOT
submit('05a','建模机制消融：候选选择的 TPOT','固定候选池，仅更换评分器；完整在线调度相同',
'Event DAG 选择的布局在两种拓扑下都带来更低 TPOT；单集群 Compute-only 和 Compute+Comm 选中同一布局。',SRC_CORE,
lambda ax:multi_hbar(ax,['Compute-only','Compute + Comm','Event DAG'],[[.600,.600,.565],[.866,.868,.694]],['单集群','三集群'],'P95 TPOT（秒/token）',fmt='{:.3f}'))
# 05b Spearman candidate rank, throughput
submit('05b','建模评分与真实吞吐排序一致性','6 个预定结构候选；开发种子 100/101；600 秒在线窗口',
'Event DAG 的候选吞吐排序 Spearman 单集群 0.943、三集群 0.886；在三集群，静态模型达到相近的一致性。仅代表当前候选样本。',SRC_CORE,
lambda ax:multi_hbar(ax,['Compute-only','Compute + Comm','Event DAG'],[[.829,.829,.943],[.870,.600,.886]],['单集群','三集群'],'Spearman ρ（越接近 +1 越一致）',fmt='{:.3f}',lim=(0,1.12)))

# 06 structure ablation
submit('06a','放置结构消融：P95 TPOT','Fixed Structure → Fixed Branches → Full Adaptive；在线调度相同',
'开放共享长度、GPU 分组和后缀数量使尾延迟下降；但同时改变层副本量和路径阶段数，属于结构联合效应。',SRC_CORE,
lambda ax:multi_hbar(ax,['Fixed Structure','Fixed Branches','Full Adaptive'],[[.818,.600,.565],[1.157,.877,.694]],['单集群','三集群'],'P95 TPOT（秒/token）',fmt='{:.3f}'))

def structural(ax):
    n=['Fixed Structure','Fixed Branches','Full Adaptive']
    pre=np.array([12,48,48]);suf=np.array([136,64,96]); x=np.arange(3)
    ax.bar(x,pre,label='共享前缀层（仅一份）',zorder=3)
    ax.bar(x,suf,bottom=pre,label='复制后缀层（所有副本合计）',zorder=3)
    for i in x:
        ax.text(i,pre[i]+suf[i]+3,f'{pre[i]+suf[i]} 份',ha='center',fontsize=11)
        ax.text(i,5,f'{pre[i]}',ha='center',fontsize=10)
        ax.text(i,pre[i]+suf[i]-8,f'{suf[i]}',ha='center',fontsize=10)
    ax.set_xticks(x,n);ax.set_ylabel('逻辑模型层副本总量');ax.set_ylim(0,176);ax.legend(frameon=False)
submit('06b','三种部署结构的模型层副本预算','共享层只存一份；复制后缀按所有后缀累加，80 层模型',
'Fixed Branches 使用 112 份层副本，Full Adaptive 使用 144 份：两者改变了副本预算，比较应解释为不同结构的综合效果，而不是单纯的选路收益。',SRC_CORE,structural)

# 07 dynamic scheduling
submit('07a','调度机制消融：P95 TPOT','相同 V2 布局 / DAG / Decode 传输；差别仅在路径状态代价',
'在当前实验中，加入队列估计和 KV 会话服务代价逐步降低 TPOT；三集群完整 V2 相比 Queue-Aware 再降低 33.18%。',SRC_CORE,
lambda ax:multi_hbar(ax,['Static DAG','Queue-Aware DAG','Full V2'],[[1.269,.641,.565],[1.209,1.039,.694]],['单集群','三集群'],'P95 TPOT（秒/token）',fmt='{:.3f}'))
submit('07b','调度机制消融：GPU 排队等待','同布局同执行机制；等待是 request-s / 到达请求数',
'三集群静态 DAG、队列感知、完整 V2 的等待分别为 49.00、36.07、22.03；等待与尾延迟下降方向一致，但不能直接充当因果百分比分解。',SRC_CORE,
lambda ax:multi_hbar(ax,['Static DAG','Queue-Aware DAG','Full V2'],[[73.969,45.943,41.814],[49.004,36.071,22.025]],['单集群','三集群'],'GPU 排队 request-s / 到达请求',fmt='{:.1f}'))

# 08 whole-method static model
submit('08','完整搜索：Event DAG 相对静态模型','相同共享复制决策空间，分别完整搜索；正值为 V2 更好',
'单集群 Event DAG 有有限增量；三集群吞吐略低、TTFT 基本持平。不能据冻结候选池的结果声称完整 Event DAG 搜索始终优于静态模型。',SRC_STRONG,
lambda ax:multi_hbar(ax,['吞吐量','P95 TTFT','P95 TPOT'],[[.349,4.452,5.831],[-.069,.472,2.942]],['单集群','三集群'],'V2 相对静态模型改善（%）',fmt='{:+.2f}'))

# 09 beam search relative
submit('09','放置搜索器：V2 vs Beam Search','同事件 DAG 评价和候选预算，Beam 宽度 4',
'两种算法均选出 48 层共享前缀、三后缀；整体指标差异接近零。可支持结构问题可求解，但不能支持 V2 搜索器显著优于 Beam。',SRC_STRONG,
lambda ax:multi_hbar(ax,['吞吐量','P95 TTFT','P95 TPOT'],[[.039,.066,.255],[-.051,0,2.745]],['单集群','三集群'],'V2 相对 Beam 改善（%）',fmt='{:+.2f}'))

# 10 complete scheduler alternative
submit('10','完整 DAG 路由 vs 规范完整流水线','相同放置；强替代基于实时负载选 3 条完整流水线之一',
'V2 在三集群吞吐 +7.81%，P95 TTFT -45.57%，TPOT -59.17%。这包含路径空间及传输合并的共同变化，不能完全归因于拼接选路。',SRC_STRONG,
lambda ax:multi_hbar(ax,['吞吐量 ↑','P95 TTFT ↓','P95 TPOT ↓'],[[3.969,17.528,48.160],[7.806,45.574,59.166]],['单集群','三集群'],'改善（%）',fmt='{:+.1f}'))

# 11 whole method removal
submit('11','三个完整模块替换后的 TTFT 增量','完整 V2 相对各简化模块；其他两个 V2 模块保留',
'三集群分别相对容量模型、固定结构和固定轮转降低 TTFT 51.83%、36.16%、25.12%；属于不同条件下的模块级收益，不能相加。',
'experiments/v2_method_ablation/REPORT_CN.md',
lambda ax:multi_hbar(ax,['容量与连通性放置','固定共享复制结构','固定合法路径轮转'],[[15.513,26.162,6.615],[51.834,36.158,25.116]],['单集群','三集群'],'P95 TTFT 降低（%）',fmt='{:.1f}'))

# 12 progressive ladder
submit('12a','四级递进：三集群的 TPOT 下降','基础 → A(资源感知) → A+B(自适应结构) → A+B+C(完整调度)',
'三集群每加入一组方法，TPOT 均进一步下降。注意四级并非严格的三个独立贡献加和；不同阶段有不同的条件。',SRC_LADDER,
lambda ax:line(ax,[0,1,2,3],[[3.410,1.711,1.011,.694]],['三集群 TPOT'],['基础','A','A+B','A+B+C'],'P95 TPOT（秒/token）',ymin=0))
submit('12b','四级递进：相对基础的吞吐指数','各场景基础方案均设为 100，展示系统构建过程',
'单集群基础吞吐 132.78→155.92；三集群 58.57→70.63 token/s。图是阶段均值的指数，仅作可视化；严格配对增益应见原报告。',SRC_LADDER,
lambda ax:line(ax,[0,1,2,3],[[100,139.448/132.779*100,153.146/132.779*100,155.918/132.779*100],[100,64.103/58.568*100,68.683/58.568*100,70.633/58.568*100]],['单集群','三集群'],['基础','A','A+B','A+B+C'],'吞吐指数（基础=100）',ymin=95))

# 13 structure vs shared waiting
submit('13','共享前缀排队：不同部署结构','共享 GPU 的累计排队 request-s / 到达请求',
'前缀更深导致共享段承载更多请求工作；不能把该共享等待值直接看成系统瓶颈排名。Full Adaptive 并非共享队列最小，却具有较好全系统尾延迟。',SRC_CORE,
lambda ax:multi_hbar(ax,['Fixed Structure：12 层','Fixed Branches：48 层','Full Adaptive：48 层'],[[1.752,10.854,10.205],[.744,4.132,4.657]],['单集群','三集群'],'共享 GPU 排队 request-s / 到达',fmt='{:.2f}'))

# 14 paths diversity
submit('14a','在线实际执行路径的多样性','相同 V2 放置下的三种子平均不同 GPU 执行序列数；对数横轴',
'单集群完整 V2 约 616 条实际执行路径，而完整流水线替代只用三条；三集群约 54 条。路径数是执行序列种类而不是吞吐。',SRC_STRONG,
lambda ax:hbar(ax,['单集群：完整路径轮转','单集群：V2','三集群：完整路径轮转','三集群：V2'],[3,(622+613+613)/3,3,(54+53+56)/3],'不同执行路径种类（log）',fmt='{:.1f}',log=True))
submit('14b','最大单一路径上的请求集中度','同 V2 部署，比较三条流水线选择与层兼容 DAG 选路',
'负载感知完整流水线在三集群将约 69.35% 请求集中于一条路径；V2 为 20.84%。可解释队列压力集中，但仍需结合其他机制。',SRC_STRONG,
lambda ax:multi_hbar(ax,['规范路径轮转','负载感知流水线','完整 V2'],[[33.351,55.003,.857],[33.410,69.351,20.839]],['单集群','三集群'],'最大单一路径占比（%）',fmt='{:.1f}'))

# 15 evaluation cost
submit('15a','离线候选打分开销：静态模型 vs 事件 DAG','同六份开发候选 × 5 次，单次打分中位耗时；对数横轴',
'Event DAG 候选打分约 31 ms，静态模型约 0.2 ms，存在数量级的计算成本。必须与完整搜索后的端到端收益共同报告。',SRC_STRONG,
lambda ax:hbar(ax,['单集群：静态模型','单集群：Event DAG','三集群：静态模型','三集群：Event DAG'],[.190,31.137,.198,30.653],'单候选打分中位毫秒（log）',fmt='{:.3f}',log=True))
submit('15b','完整布局搜索开销：V2 vs Beam','两个算法采用相同事件 DAG 与评价预算；离线规划秒数',
'单集群 V2 / Beam 约 6.88 / 7.06 秒，三集群约 15.48 / 15.74 秒，规划开销基本持平。',SRC_STRONG,
lambda ax:multi_hbar(ax,['单集群','三集群'],[[6.88,15.48],[7.06,15.74]],['V2 搜索','Beam Search'],'离线规划时间（秒）',fmt='{:.2f}'))

# 16 V1 load sweep
submit('16a','V1 负载敏感性：吞吐提升随压力变化','V1 相对 Helix 的三种子平均配对吞吐增益',
'在已测试的 0.7×、1.0×、1.1× 负载，V1 两种拓扑都保持正向吞吐优势；这是 V1 历史泛化，而非 V2 的已验证结果。',SRC_V1,
lambda ax:line(ax,[.7,1.,1.1],[[6.14,8.67,10.26],[10.29,18.85,20.98]],['单集群','三集群'],['0.7×','1.0×','1.1×'],'吞吐改善（%）',ymin=0))
submit('16b','V1 三指标 × 负载：性能改善全景','六组正式窗口；正值表示 V1 相对 Helix 更好',
'吞吐与尾延迟在六组配置中均呈改善；不同拓扑使用不同绝对 offered 负载，不做跨拓扑绝对指标的因果判断。',SRC_V1,
lambda ax:heat(ax,['单 490','单 700','单 770','三 224','三 320','三 352'],['吞吐 ↑','TTFT ↓','TPOT ↓'],[[6.14,30.76,48.69],[8.67,34.28,54.22],[10.26,35.09,56.06],[10.29,51.66,62.30],[18.85,54.26,70.06],[20.98,52.20,71.15]],fmt='{:.1f}'),plot_type='heat')

# 17 V1 RTT
submit('17a','V1 跨集群 RTT 敏感性：吞吐优势','只缩放跨区域链路 RTT，带宽/GPU 保持不变',
'RTT 增大时，相对 Helix 的吞吐改善从 16.26% 增至 24.66%。重新规划后 V1 布局并未随 RTT 改变，不能声称自适应层划分。',SRC_V1,
lambda ax:line(ax,[.5,1,2],[[16.26,18.85,24.66]],['V1 相对 Helix'],['0.5×','1×','2×'],'吞吐提升（%）',ymin=0))
submit('17b','V1 跨集群路由：平均跨区域跳数','同硬件、不同 RTT；每条被分配路径的平均跨区域跨越次数',
'Helix 约 3.57 次跨域，而 V1 约 1.02–1.05 次。跨区减少与 RTT 下的相对收益一致，但不等于单独控制“跨区次数”的因果实验。',SRC_V1,
lambda ax:line(ax,[.5,1,2],[[3.57,3.57,3.57],[1.05,1.04,1.02]],['Helix','V1'],['0.5×','1×','2×'],'每条路由跨区域次数',ymin=0))

# 18 offline common admission
submit('18','V1 离线：统一 KV 准入规则后的吞吐','20 初始请求、KV 门槛 0.8；60 秒预热 + 600 秒测量',
'共同准入下，单集群 V1 266.78 vs Helix 252.14；三集群 V1 159.73 vs 96.06 token/s。与原生准入结果分开报告。',SRC_V1,
lambda ax:multi_hbar(ax,['单集群','三集群'],[[252.14,96.06],[266.78,159.73]],['Helix','V1'],'离线输出 token/s',fmt='{:.1f}'))

# 19 native
submit('19','V1 离线：双方原生 KV 准入规则','不同准入方法下的端到端吞吐增益，不作纯调度归因',
'三集群原生准入下 V1 平均吞吐改善 64.29%，单集群 5.29%；由于两系统准入速度与准入规则不同，不能当作完全相同到达序列的微机制消融。',
'experiments/baseline_audit/RESULTS_OFFLINE.md',
lambda ax:hbar(ax,['单集群','三集群'],[5.29,64.29],'V1 相对 Helix 离线吞吐提升（%）',fmt='{:.2f}'))

# 20 cross factor
submit('20','V1 放置 × 调度 2×2：三集群吞吐','HH=Helix/Helix, HR=Helix放置/RCAPS调度；以此类推',
'HH/HR/RH/RR 吞吐逐级不同，但存在收益重叠，三集群四格交互项为 -4.399 token/s。单集群 RH 仅 2/3 完成，不画成完整因子结果。',
'experiments/validation_2026/CROSS_RESULTS.md',
lambda ax:hbar(ax,['HH：Helix+Helix','HR：Helix+V1调度','RH：V1放置+Helix','RR：V1+V1'],[58.255,64.560,67.328,69.234],'输出 token/s',fmt='{:.3f}'))

# 21 V1 path structure
submit('21a','V1 结构：共享前缀深度敏感性','固定双后缀设备分组与在线调度；越低越好',
'三集群从共享 10→12 层，TPOT 从 0.984 降至 0.956 秒/token，但共享 GPU 排队增加；只支持当前结构邻域的局部权衡。',SRC_STRUCTURE,
lambda ax:line(ax,[10,11,12],[[.984,.970,.956]],['三集群 P95 TPOT'],['10 层','11 层','12 层'],'P95 TPOT（秒/token）',ymin=.90))
submit('21b','V1 单路径与双后缀：主负载吞吐','9 张 GPU 精选单路径 vs 原 24 GPU 双后缀结构',
'双后缀吞吐两拓扑均更好，但单集群精选单路径 TTFT 反而较低。此对照同时改变复制量及活跃 GPU 数量，不应仅归因于多路径。',SRC_STRUCTURE,
lambda ax:multi_hbar(ax,['单集群','三集群'],[[151.153,65.612],[154.611,69.234]],['9 GPU 单路径','双后缀'],'输出 token/s',fmt='{:.3f}'))

# 22 V1 place internals
submit('22','V1 放置消融：拓扑与事件图细化','B/A 为增加拓扑感知；C/B 为在拓扑初始化后加入事件图细化',
'拓扑感知在三集群的收益明显；事件图局部细化在单集群较有帮助，但三集群 TPOT 退化 0.77%。不存在所有场景均正向的组件贡献。',
'paper/ABLATION_ATTRIBUTION_CN.md',
lambda ax:multi_hbar(ax,['吞吐量 ↑','P95 TTFT ↓','P95 TPOT ↓'],[[6.03,39.85,37.59],[1.30,13.96,5.32],[.20,.01,-.77]],['三集群 B/A：拓扑','单集群 C/B：事件','三集群 C/B：事件'],'改善（%）',bar_width=.24,fmt='{:+.1f}'))

# 23 micro component
submit('23','V1 在线组件消融：TPOT 增量','固定 V1 布局；分别测试传输合并及活跃 KV 会话代价',
'就绪 Decode 合并在两种拓扑均降低 TPOT；KV 会话代价在三集群有明显收益，但在单集群观察到 TPOT 回退，不能概括为普遍提升。',
'paper/STABLE_IMPROVEMENTS_CN.md',
lambda ax:multi_hbar(ax,['已就绪 Decode 传输合并','活跃 KV 会话代价'],[[17.75,-6.14],[16.42,31.48]],['单集群','三集群'],'P95 TPOT 改善（%）',fmt='{:+.2f}'))

# 24 pruning
submit('24','V1 关键资源剪枝：候选评分次数','相同最终放置的完整邻域 vs 关键资源筛选搜索',
'单集群候选评分从 115 降到 68（40.9%）；三集群均为 272，未节省工作。该图是搜索成本收益，不是运行时吞吐收益。',
'experiments/validation_2026/RESULTS.md',
lambda ax:multi_hbar(ax,['单集群','三集群'],[[115,272],[68,272]],['完整邻域','关键资源引导'],'候选评分次数',fmt='{:.0f}'))

# 25 runtime overhead
submit('25','V1 运行开销：传输调度 P95 调用耗时','同场景种子 0；不同系统事件调用次数不同',
'单集群 V1 传输调度调用 P95 约 20.0 μs，Helix 27.7 μs；三集群 V1 29.5 μs，Helix 23.9 μs。不能外推为 V2 的 CPU 开销。',SRC_V1,
lambda ax:multi_hbar(ax,['单集群','三集群'],[[27.7,23.9],[20.0,29.5]],['Helix','V1'],'传输调度单次调用 P95（μs）',fmt='{:.1f}'))

# 26 negative predictor
submit('26a','预测代理：GPU 排队排名相关性','在线热点 Spearman；固定原布局比较代理与在线观测的排序',
'新队列代理在三集群将 Spearman 从 0.587 提高到 0.788，但单集群由 0.648 降至 0.499；这是条件性预测改善。',
'experiments/queue_predictor_2026/RESULTS.md',
lambda ax:multi_hbar(ax,['单集群','三集群'],[[.648,.587],[.499,.788]],['原需求代理','新队列代理'],'Spearman ρ',fmt='{:.3f}',lim=(0,1.02)))
submit('26b','预测代理：最终在线吞吐并未改善','在新代理生成的放置上完整仿真，三种子均值',
'单集群新代理吞吐 152.633，低于原 V1 的 154.611；三集群 69.212 vs 69.234 基本持平。排序改善并不等于全系统改善。',
'experiments/queue_predictor_2026/RESULTS.md',
lambda ax:multi_hbar(ax,['单集群','三集群'],[[154.611,69.234],[152.633,69.212]],['原 V1 放置','新代理放置'],'输出 token/s',fmt='{:.3f}'))

# 27 failure rate
submit('27','实验审计：正式窗口完成比例','各项研究协议不同；完成率只反映所选运行配置的执行状态',
'V2 核心消融与强替代方法新增运行均完整；V1 单一路径高负载和特定跨调度组合存在 KV 容量/路由失败。不能把失败项当作吞吐为零。',
'experiments/structure_ablation_2026/RESULTS.md',
lambda ax:hbar(ax,['V2 核心消融（新增）','V2 强替代方法（新增）','V1 单集群 RH 交叉','V1 单集群 24GPU单路径','V1 三集群 24GPU单路径','三集群 SP 自选压力'],[100,100,66.7,0,33.3,66.7],'完成完整窗口的比例（%）',fmt='{:.1f}%'))

# 28 42 GPU original artifact
submit('28','42 GPU 高异构配置：原 Helix artifact','仓库中存在的物理 GPU 配置，不是 RCAPS V1/V2 泛化结果',
'包含 A100、V100、L4、T4 及多卡节点类型，共 42 个计算节点；没有核实到 V2 在该资源池上的正式对照，不能误标为 RCAPS 已验证结果。',
'artifact_evaluation/high_heterogeneity/step1_gen_cluster.py',
lambda ax:hbar(ax,['A100','V100','L4','L4×2','T4','T4×2','T4×4'],[4,6,8,4,10,6,4],'Helix artifact 计算节点数',fmt='{:.0f}'))

book.close()

intro=['# RCAPS V2 / V1 实验配图清单（2026-10-15）','','所有图为重新绘制的科研图表；一图一轴，不将不同单位放到同一坐标轴；统计结果取自仓库的结果文件及已审计汇总。',
'**重要限制：** V1 历史结果不能写作 V2 泛化；仅三个正式种子，不代表统计显著；少数开发窗口只用于相关性诊断；完成率/积压应配合 P95 解读。','',f'完整画册：`{PDF.name}`；单张图同时包含 PNG 与 SVG。','']
for k in records:
    intro += [f'## 图 {k["编号"]}｜{k["图名"]}',k['用途'],f'说明：{k["解读"]}',f'来源：{k["数据来源"]}',f'PNG：`{k["PNG"]}`；SVG：`{k["SVG"]}`','']
INDEX.write_text('\n'.join(intro),encoding='utf-8')
(OUT/'图表索引.md').write_text('\n'.join(intro),encoding='utf-8')
with (OUT/'图表索引.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
with ZipFile(ZIP,'w',compression=ZIP_DEFLATED,compresslevel=7) as z:
    for file in OUT.rglob('*'):
        if file.is_file():z.write(file,arcname=file.relative_to(OUT))
print('DONE',len(records),'figures','PDF',PDF,PDF.stat().st_size,'ZIP',ZIP,ZIP.stat().st_size,flush=True)