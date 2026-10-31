# RCAPS 剩余失败键手工独立重跑命令

共 254 键：E2b 6；E3b 12；E5a 47；E5b 55；V5 68；V6 66。

每段均从项目根目录执行、真正激活 conda gllm，并写入新的 experiments/manual_reruns 子目录。
已有输出目录会拒绝覆盖；若需再试，请保留原件并指定另一新目录。重跑成功不能替换原正式失败。
结果见各输出目录的 index.json、worker.log、result.json 或 failure.json。
E5b 原 formal 冒烟门槛未达，因此其命令只针对预登记的修订边界诊断。

## E4：由用户在 WSL2 执行

E4 不属于上述 Windows gllm 逐键重跑；需 WSL2 的 python3、ip、tc 和 sudo 权限。

~~~bash
cd /mnt/d/PythonProject/Helix-GREEN
python3 experiments/reviewer_v2/E4_tcp_wsl/bench.py --prepare
sudo python3 experiments/reviewer_v2/E4_tcp_wsl/bench.py --preflight
sudo python3 experiments/reviewer_v2/E4_tcp_wsl/bench.py --run | tee experiments/reviewer_v2/E4_tcp_wsl/console.log
python3 experiments/reviewer_v2/E4_tcp_wsl/bench.py --report
~~~

E4 共 3 速率×5 模式×10 次测量。

## E2b：6 个未解决键

来源：experiments/reviewer_v2/E2b_parallax/failure_replay_round2/FINAL_AUDIT.json。

### E2b 001 · multi/load320/shared/seed1

原失败 SHA256：5828a2372721b785ab728358151e8ae5a864f9a9f15c3558f025422fc4f071e9；最后重放失败 SHA256：cd7f83ce3d1ca84b88846f5c43726c5165a7604f94e00410f4d6cb8361742de9。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E2b' --key 'multi/load320/shared/seed1' --output 'experiments/manual_reruns/E2b/multi/load320/shared/seed1'
~~~

### E2b 002 · multi/load320/shared/seed4

原失败 SHA256：adc6c2c6b23e64bacc8a93020c8cc5e3a0fa45544b344fceac5871a0d4ba5f92；最后重放失败 SHA256：af9468941fd1b1761a16bd569b68cab99ae0182ef5cd39e08aba78051956f5ca。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E2b' --key 'multi/load320/shared/seed4' --output 'experiments/manual_reruns/E2b/multi/load320/shared/seed4'
~~~

### E2b 003 · single/load700/fifo/seed0

原失败 SHA256：4e563c2a5edcf83944411ee86be723e6f79b83853a08d724378aa149e2af3362；最后重放失败 SHA256：aa9bbed7e2f8fc94ca94002d50150ddca4700c3a2161fe7ac3b1f05998db4274。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E2b' --key 'single/load700/fifo/seed0' --output 'experiments/manual_reruns/E2b/single/load700/fifo/seed0'
~~~

### E2b 004 · single/load700/fifo/seed1

原失败 SHA256：af6de9be94a91e5986d28e86f4c6c56e03e663687e7f49a6844bec6711853bf1；最后重放失败 SHA256：900aeff739c3cb63bc5f27af9e3fb4a05ba689a882e5496e684edc78c89ff3d4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E2b' --key 'single/load700/fifo/seed1' --output 'experiments/manual_reruns/E2b/single/load700/fifo/seed1'
~~~

### E2b 005 · single/load700/fifo/seed4

原失败 SHA256：465c8d8e71a1ac6df4542c634cd7ef812c3d6bf50a2ac2ca0845c3a086490d43；最后重放失败 SHA256：f07ea8f06721bed2d2a89bcdb8dfec29d6f152a1a6db30532944a38f17500eb8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E2b' --key 'single/load700/fifo/seed4' --output 'experiments/manual_reruns/E2b/single/load700/fifo/seed4'
~~~

### E2b 006 · single/load700/shared/seed4

原失败 SHA256：2da70fafdbaf12ca0847bd1932141717a67a78649656d003cfca2c5bba1eef0a；最后重放失败 SHA256：9d2559b3de928ff0419da3f0e52a6bda24d4d9d46af3729de9e2637e85d79f0f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E2b' --key 'single/load700/shared/seed4' --output 'experiments/manual_reruns/E2b/single/load700/shared/seed4'
~~~

## E3b：12 个未解决键

来源：experiments/reviewer_v2/E3b_goodput/FINAL_AUDIT.json。

### E3b 001 · multi/400/Helix+/seed0

原失败 SHA256：5a0b38d8bac42b4394923c143d71baf59905da76fed6f59f03e52bd73c02de4b；最后重放失败 SHA256：0ea3d2795f9ecfd784e08802f91e5f9b2ed5a90d42ae72d2bd108191eb4c50eb。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix+/seed0' --output 'experiments/manual_reruns/E3b/multi/400/Helix+/seed0'
~~~

### E3b 002 · multi/400/Helix+/seed1

原失败 SHA256：eacafddd9c2b704e1d823bbda115948a3772b1278215cc50c7b1385c751fb05f；最后重放失败 SHA256：d1f71cbf6dedef0b9def0e63199419b9880012c54b4fa4168eeee3a9f6ce890f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix+/seed1' --output 'experiments/manual_reruns/E3b/multi/400/Helix+/seed1'
~~~

### E3b 003 · multi/400/Helix+/seed2

原失败 SHA256：9328afc49345e923f80f78cf9d23806b0e94fd879ab04cd06144a5fad0572ea6；最后重放失败 SHA256：c12cae6d70c15b15ae19777ee9b1084b652bcd62d33880dcff25c8c29638a660。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix+/seed2' --output 'experiments/manual_reruns/E3b/multi/400/Helix+/seed2'
~~~

### E3b 004 · multi/400/Helix+/seed3

原失败 SHA256：c3b2afdb2046aff11ec9edd474f3e97a7df3f3c296323507add4b6d54ea43fa6；最后重放失败 SHA256：67be84ed013dc4231fd77f357a26ecdc9ec1ae72ec6c47d1fd1006495769feac。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix+/seed3' --output 'experiments/manual_reruns/E3b/multi/400/Helix+/seed3'
~~~

### E3b 005 · multi/400/Helix+/seed4

原失败 SHA256：bb0c5618905297fa92a04f828db2aabc64b393d21541260e94211366fa16a155；最后重放失败 SHA256：1a17d9422b931608b93be2721eea4214edb2fc86289a0b1ca98643782dbee7a3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix+/seed4' --output 'experiments/manual_reruns/E3b/multi/400/Helix+/seed4'
~~~

### E3b 006 · multi/400/Helix-tuned/seed0

原失败 SHA256：efdbb2f000c5dbb10f90bd1e33f3e8efbbf0583a8c2ed9bf10ed80092c409d74；最后重放失败 SHA256：dbf4c403bc2b71cc2980499285233347845f0765e273cc9584a5fbc36b2fb0b6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix-tuned/seed0' --output 'experiments/manual_reruns/E3b/multi/400/Helix-tuned/seed0'
~~~

### E3b 007 · multi/400/Helix-tuned/seed3

原失败 SHA256：82c73d386123e44ba5b3f7532c20da7f9d1d4bacbc2cabc13a645c04899e2774；最后重放失败 SHA256：8a176c5756a776adc4278d2ab8ccce7e4ea0de5f5b03b31a6b42c276e9d454b5。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix-tuned/seed3' --output 'experiments/manual_reruns/E3b/multi/400/Helix-tuned/seed3'
~~~

### E3b 008 · multi/400/Helix-tuned/seed4

原失败 SHA256：fd19f1c79f1865315dc047ae262f2ba08e506312fb1d545ca313d58e6c5fb177；最后重放失败 SHA256：f22ee290db74fda4617e56156a7e4e2d9650878b7fd01a9500be5b6c7edf2f91。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix-tuned/seed4' --output 'experiments/manual_reruns/E3b/multi/400/Helix-tuned/seed4'
~~~

### E3b 009 · multi/400/Helix/seed0

原失败 SHA256：e6f70e680e40511618e52caa24f33728ecb397856ec061fce43223e40eb70cab；最后重放失败 SHA256：56c1e8a4ee7af169d677f4691c02b60968a3a2b77e65fa6568dc6b4992462c55。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix/seed0' --output 'experiments/manual_reruns/E3b/multi/400/Helix/seed0'
~~~

### E3b 010 · multi/400/Helix/seed1

原失败 SHA256：7279dc0afc097610f9f085c3bc7a4f9314d110e13ddb9efe1e22a198d2a195a2；最后重放失败 SHA256：f6f809eb654c1ec5e19522741f963cabc5aea8b787a41169fafe22c0a909a7fb。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix/seed1' --output 'experiments/manual_reruns/E3b/multi/400/Helix/seed1'
~~~

### E3b 011 · multi/400/Helix/seed3

原失败 SHA256：7e83aefdd96ca8781dd02816deef6d40b5edfe8a06b854c31658380b1b127330；最后重放失败 SHA256：3bee8171f082b142555e8ea59fe4c2a93e523eb8c159863312fee80553e3ee48。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix/seed3' --output 'experiments/manual_reruns/E3b/multi/400/Helix/seed3'
~~~

### E3b 012 · multi/400/Helix/seed4

原失败 SHA256：34668a4d62ecbe93528bcfdfe8ca24f7545c6ebcddb19d99e72c7dd0492b39a7；最后重放失败 SHA256：3b78a0f939fbeff4687d3f0e4c073bfc3821f64ff67282740e125255c56dfa86。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix/seed4' --output 'experiments/manual_reruns/E3b/multi/400/Helix/seed4'
~~~

## E5a：47 个未解决键

来源：experiments/reviewer_v2/E5_scale_kv/E5a_failure_replay/FINAL_AUDIT.json。

### E5a 001 · E5a/load1450/Helix+/seed0

原失败 SHA256：886e9f05a8fa6952531f2706db31d8b9f6eef9b158253f2e312afd4c8523f41b；最后重放失败 SHA256：56670702e9b090c5b37a3977828651c38ffe8a4faf36fb499435381d3e50b813。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix+/seed0' --output 'experiments/manual_reruns/E5a/E5a/load1450/Helix+/seed0'
~~~

### E5a 002 · E5a/load1450/Helix+/seed1

原失败 SHA256：1f8edb1274a070bd05de9a4c2fb23d785257d660a42b9d51e32a9d3f41bcdfeb；最后重放失败 SHA256：4d0e71ec5c5b60001047da328d6d1dcaa182b7bd9caacc272bba483965a95e40。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix+/seed1' --output 'experiments/manual_reruns/E5a/E5a/load1450/Helix+/seed1'
~~~

### E5a 003 · E5a/load1450/Helix+/seed2

原失败 SHA256：52e7ae62e3b9c22ed281ca54fc5ba15fdb52e9b8066791706cf462067eef9acf；最后重放失败 SHA256：84954a66c70ad7dcb4ece128c3038327558cb2bd5420292c512528bc8fd7fc35。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix+/seed2' --output 'experiments/manual_reruns/E5a/E5a/load1450/Helix+/seed2'
~~~

### E5a 004 · E5a/load1450/Helix+/seed3

原失败 SHA256：2bb13e3e6bf4459b150d0d50495a13b8ea3adbfcc2a0f9a5fa07c6f560d7b313；最后重放失败 SHA256：062c6fa08bf91b67fe34cc601dea54fc1a982bcd6eac6babd1b3fac578e49919。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix+/seed3' --output 'experiments/manual_reruns/E5a/E5a/load1450/Helix+/seed3'
~~~

### E5a 005 · E5a/load1450/Helix+/seed4

原失败 SHA256：1bafc3f15eeb9d2f0f4339a30ecb17049daf36a4c96bd124953da30878792988；最后重放失败 SHA256：b3c4a7341339a43dbf97f1eaef826db31800d981227621ea82b261b8baff9580。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix+/seed4' --output 'experiments/manual_reruns/E5a/E5a/load1450/Helix+/seed4'
~~~

### E5a 006 · E5a/load1450/Helix/seed0

原失败 SHA256：cbf743bcaa3f1740114885bc53cf34ccb05ccf745dabb97431e110d75930a291；最后重放失败 SHA256：0ed40a158ef03d58d91d90533f299a41f66e14b74e62f5969651787b1db6d4e2。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix/seed0' --output 'experiments/manual_reruns/E5a/E5a/load1450/Helix/seed0'
~~~

### E5a 007 · E5a/load1450/Helix/seed1

原失败 SHA256：adf3a2da384777319cee42e71258d0b8d5c17187a334c9b012d0ab0c06d40013；最后重放失败 SHA256：c37d45e4fe2c9279c7bd10b5980b3935b9d6df102140246f1eaca1a477514b5b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix/seed1' --output 'experiments/manual_reruns/E5a/E5a/load1450/Helix/seed1'
~~~

### E5a 008 · E5a/load1450/Helix/seed2

原失败 SHA256：342477a8eecd1d89eeda3624e0508ca7d17cd3d237d2ef10905a735b66117c13；最后重放失败 SHA256：0aae9df4eb7cb34b93a51b48eef98601d3b75b9ae2addf3edbadabb7827989e2。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix/seed2' --output 'experiments/manual_reruns/E5a/E5a/load1450/Helix/seed2'
~~~

### E5a 009 · E5a/load1450/Helix/seed3

原失败 SHA256：c5dd5954bad12a9708d248708581626266f53cbd2700bbec03a7f8af38ec0c70；最后重放失败 SHA256：3ce67520868fdca4cc4acb4950db13288b3f5c2df3f42180b69e6e4210f2bf26。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix/seed3' --output 'experiments/manual_reruns/E5a/E5a/load1450/Helix/seed3'
~~~

### E5a 010 · E5a/load1450/Helix/seed4

原失败 SHA256：eaada4a4c5e4636c3f0fe71c845e847801220a6f1cc8b921fa5db705c8704f15；最后重放失败 SHA256：d39cb41e884b4180ae490e9514d903aeb55c6185047e29acf4e259e437ce2311。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix/seed4' --output 'experiments/manual_reruns/E5a/E5a/load1450/Helix/seed4'
~~~

### E5a 011 · E5a/load1450/RCAPS-KV/seed0

原失败 SHA256：ab0ead3be3c3c9cc9a1fb213e3810173c7711737de3068028acf21f3baa9de65；最后重放失败 SHA256：f0c1c71164186a9bf13a73adf12552214c293c2e5b467e1c0dd4bedd4de1cdb9。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/RCAPS-KV/seed0' --output 'experiments/manual_reruns/E5a/E5a/load1450/RCAPS-KV/seed0'
~~~

### E5a 012 · E5a/load1450/RCAPS-KV/seed1

原失败 SHA256：b1b176bd28df09d455aed4a1797ed5ca595fea2b764859d59389c3233fabfbca；最后重放失败 SHA256：21e4313a23810f473c933f5722cc89e689b01b60a3df35dc627854340c07edd6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/RCAPS-KV/seed1' --output 'experiments/manual_reruns/E5a/E5a/load1450/RCAPS-KV/seed1'
~~~

### E5a 013 · E5a/load1450/RCAPS-KV/seed2

原失败 SHA256：ec453c99988830a1cfa2ca3332a0f3ba16ad4ac391c0f88d6cf5b056ea46160b；最后重放失败 SHA256：238836803b2646c5fde99a88fcba4b718c08634a7341c18ed66d4605fabe76d9。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/RCAPS-KV/seed2' --output 'experiments/manual_reruns/E5a/E5a/load1450/RCAPS-KV/seed2'
~~~

### E5a 014 · E5a/load1450/RCAPS/seed0

原失败 SHA256：38cfefe408eb1eef280860036675dcd5b21003c93104cc09fcb10398555e6df7；最后重放失败 SHA256：e75c1c70d497fa1c1eb03fab6c263c55b25ca7f12b75ab56ffedddf8bca93a47。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/RCAPS/seed0' --output 'experiments/manual_reruns/E5a/E5a/load1450/RCAPS/seed0'
~~~

### E5a 015 · E5a/load1450/RCAPS/seed1

原失败 SHA256：e2ee8390c75e5facd2903c70738759d1fbe7e03a15f794e55aa3f49968c22e52；最后重放失败 SHA256：674dbea38485dfe7b429063f80d0ee338f438d2807d21ed5e7e6319f29ef893a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/RCAPS/seed1' --output 'experiments/manual_reruns/E5a/E5a/load1450/RCAPS/seed1'
~~~

### E5a 016 · E5a/load1450/RCAPS/seed2

原失败 SHA256：75c04cda8ce6d9dccb2566143294296e593ed7bbfd725674cf5d57bca3d2a615；最后重放失败 SHA256：764febdebc12f34c96db0a663124d210a17a773fd455baadb874cefca8bc5d5b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/RCAPS/seed2' --output 'experiments/manual_reruns/E5a/E5a/load1450/RCAPS/seed2'
~~~

### E5a 017 · E5a/load1450/RCAPS/seed3

原失败 SHA256：7aa111e7f21b3a1186b9f753ccd19a656d6a5693037ba8229353557bc03c9e51；最后重放失败 SHA256：1ff558d0b6cbcaf4c238be99d72889173f93e4dc3cc5425d8b8cb641738fb0d4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/RCAPS/seed3' --output 'experiments/manual_reruns/E5a/E5a/load1450/RCAPS/seed3'
~~~

### E5a 018 · E5a/load1800/Helix+/seed0

原失败 SHA256：cdd54b143d4fa8cc4e2a15b222e440c0b95a688ec559e1b8c581970167db46fe；最后重放失败 SHA256：6d7dde1b5735aafdf271f5bae075e288c4d94f13ce7d5295c877253e98153093。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix+/seed0' --output 'experiments/manual_reruns/E5a/E5a/load1800/Helix+/seed0'
~~~

### E5a 019 · E5a/load1800/Helix+/seed1

原失败 SHA256：81d819b7b995c66537e93eb3c5494bf0034d24772b67870e1bad54746fed582d；最后重放失败 SHA256：20c9921c200b31b1ca98aa68c9376915ea4562f88782e4115661b18fa185abd1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix+/seed1' --output 'experiments/manual_reruns/E5a/E5a/load1800/Helix+/seed1'
~~~

### E5a 020 · E5a/load1800/Helix+/seed2

原失败 SHA256：78895b0dfc8e41f993ac757d3204a77a6e73fd4f99984efec8cc700070f80011；最后重放失败 SHA256：8e5147c0a49e3fe678d3d6414ac2f25d4b3dfe1aed48d0b649ee68ccd541018f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix+/seed2' --output 'experiments/manual_reruns/E5a/E5a/load1800/Helix+/seed2'
~~~

### E5a 021 · E5a/load1800/Helix+/seed3

原失败 SHA256：6b5f1438f5ca7f037f621320357c43e597555a257be62c56091109adef799727；最后重放失败 SHA256：c57d321479a4dc21e91ddb2c173dca2c1e1b42567e5e405333d338fbb55d3be7。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix+/seed3' --output 'experiments/manual_reruns/E5a/E5a/load1800/Helix+/seed3'
~~~

### E5a 022 · E5a/load1800/Helix+/seed4

原失败 SHA256：f539158f22bbaf3e1cab7b76798e58ac777a14c04776a718fea65e35f03dd309；最后重放失败 SHA256：535a36a1825c78397df7216a0bec8a30166903e0fe0b81ef384309282e5e9344。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix+/seed4' --output 'experiments/manual_reruns/E5a/E5a/load1800/Helix+/seed4'
~~~

### E5a 023 · E5a/load1800/Helix/seed0

原失败 SHA256：eef8496ddb08c3f2c69ec7958bd5fb499ec0bb9e5c2422ed31a42446e57f8c49；最后重放失败 SHA256：8c492b1f0174612c5d005fecc32c8412922064bd09b821ed869a9b4c3eeb381e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix/seed0' --output 'experiments/manual_reruns/E5a/E5a/load1800/Helix/seed0'
~~~

### E5a 024 · E5a/load1800/Helix/seed1

原失败 SHA256：0f1265541991b8584ff9dc18ade84942c94879667145071f7533b02fbf5af896；最后重放失败 SHA256：98ab63405157bec9fd86c6fcdc3160a8093a422cad2e03b0d87c89cd4b2edea2。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix/seed1' --output 'experiments/manual_reruns/E5a/E5a/load1800/Helix/seed1'
~~~

### E5a 025 · E5a/load1800/Helix/seed2

原失败 SHA256：2a5462e94910679a91dfc75882507eb340674014944edfa84fd4a2875b4bee38；最后重放失败 SHA256：524e6a9e438d4498b1f3c70446d6367448ba7826d21aab3da0f1c7fbb1d1253e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix/seed2' --output 'experiments/manual_reruns/E5a/E5a/load1800/Helix/seed2'
~~~

### E5a 026 · E5a/load1800/Helix/seed3

原失败 SHA256：5dd88f7d925affb25bcaaa9fce459bbf1d0372146a66f884dbdb2d5fc167d298；最后重放失败 SHA256：96007360b1f0fbde2a5cdb50034a43e29b79f0c675175b4286a16b7a462a3ddb。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix/seed3' --output 'experiments/manual_reruns/E5a/E5a/load1800/Helix/seed3'
~~~

### E5a 027 · E5a/load1800/Helix/seed4

原失败 SHA256：f48f544fb3943101a7777577cbb4622dfc5a7527d269c11358dbf93a6e9996ad；最后重放失败 SHA256：df01eca7cc375853b4088d59a705f52e5da9db2c3dcdbc0ed5cc746d22566728。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix/seed4' --output 'experiments/manual_reruns/E5a/E5a/load1800/Helix/seed4'
~~~

### E5a 028 · E5a/load1800/RCAPS-KV/seed0

原失败 SHA256：04fe9b14e5f661232bea03de89dfa53c81f3120a4d92a94802426ddd939bf0d2；最后重放失败 SHA256：8434989eec049c8cb6d1d5f576edf3de7beeacc105d8fe57da6bb94ee52c668b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS-KV/seed0' --output 'experiments/manual_reruns/E5a/E5a/load1800/RCAPS-KV/seed0'
~~~

### E5a 029 · E5a/load1800/RCAPS-KV/seed1

原失败 SHA256：884587cccf0b089001d8594c25675614b292302858b27f58cb5f8e268090b2cc；最后重放失败 SHA256：d2aacc29c68959ede083d957e9e6c42e3292af321a098116cf4b708505bef2c4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS-KV/seed1' --output 'experiments/manual_reruns/E5a/E5a/load1800/RCAPS-KV/seed1'
~~~

### E5a 030 · E5a/load1800/RCAPS-KV/seed2

原失败 SHA256：7e86c3bffd341fdf58bc7a4952359e8e36da7df5d57251d916bea6ebf4293df4；最后重放失败 SHA256：9e26c18a9c20007a4ed16fd0c10fadf15161faea411d8cf824bd08d3905940a4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS-KV/seed2' --output 'experiments/manual_reruns/E5a/E5a/load1800/RCAPS-KV/seed2'
~~~

### E5a 031 · E5a/load1800/RCAPS-KV/seed3

原失败 SHA256：157c777320e3febf7b3dec2da0ee81ab554967333c0664bc56c673d64c7953c7；最后重放失败 SHA256：f65292ed95b2693a7e71290c56fd252677e532ab62b19518020f9d472fb2ecdc。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS-KV/seed3' --output 'experiments/manual_reruns/E5a/E5a/load1800/RCAPS-KV/seed3'
~~~

### E5a 032 · E5a/load1800/RCAPS-KV/seed4

原失败 SHA256：caea868c2b1ee3c60e22197a5600b1f030a58e5ecd59ea5aac0e667d4fa68768；最后重放失败 SHA256：f95e8c6a4febcec04292159c5b39243d63ebfd9bf81233a6cd6eb16c5abc52b7。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS-KV/seed4' --output 'experiments/manual_reruns/E5a/E5a/load1800/RCAPS-KV/seed4'
~~~

### E5a 033 · E5a/load1800/RCAPS/seed0

原失败 SHA256：d2fcc394c153da2e90f8b508bb5a4f2e45102347545a0a44c0906d77f330b536；最后重放失败 SHA256：da77ce3cb26f580fb1ccc17d742e4c56f5359c1e330d5c71f6b10a96fbc436eb。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS/seed0' --output 'experiments/manual_reruns/E5a/E5a/load1800/RCAPS/seed0'
~~~

### E5a 034 · E5a/load1800/RCAPS/seed1

原失败 SHA256：91d3a201bd1402708a95a09e53ee4b9c226f15e9cd1e92f19a40cef909b7e42b；最后重放失败 SHA256：0a74bb38200845f124a4ad274fb905438b466d6527a698ed2b70c96fd49a1a21。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS/seed1' --output 'experiments/manual_reruns/E5a/E5a/load1800/RCAPS/seed1'
~~~

### E5a 035 · E5a/load1800/RCAPS/seed2

原失败 SHA256：d6dfec175a00f5377ef265a794d2b1be666c2e574bc8354b85da93105c70951f；最后重放失败 SHA256：24db3e992e54fad3d282a77d02f5858fb69a0cf5049363b64ee46c2216ffed20。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS/seed2' --output 'experiments/manual_reruns/E5a/E5a/load1800/RCAPS/seed2'
~~~

### E5a 036 · E5a/load1800/RCAPS/seed3

原失败 SHA256：4613e09ee6884e107426f0be19315d9b539ff99fb3f202d72fc7895f64f3702e；最后重放失败 SHA256：af0b1aeb74fa83787e606e43ecbdace51d5ad829b26a570bc3d9717c298ec364。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS/seed3' --output 'experiments/manual_reruns/E5a/E5a/load1800/RCAPS/seed3'
~~~

### E5a 037 · E5a/load1800/RCAPS/seed4

原失败 SHA256：9aec03f06c6d98173eae8bfd3f19bdc2e72637d7f08349f59756c0d4fef16419；最后重放失败 SHA256：d862ec32545e7f7647c9db69f15c2c421c6ec4372387922b0aaa00ba701c5956。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS/seed4' --output 'experiments/manual_reruns/E5a/E5a/load1800/RCAPS/seed4'
~~~

### E5a 038 · E5a/load2150/Helix+/seed1

原失败 SHA256：ef57d5ed9c511d1353d11794d8e8e355d363ab8ddd8ad6493d3db2181b9a4ed3；最后重放失败 SHA256：9c024a845794536f4d72368b2a8308b7b302cb36ba37595ff69212a2b354da2e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/Helix+/seed1' --output 'experiments/manual_reruns/E5a/E5a/load2150/Helix+/seed1'
~~~

### E5a 039 · E5a/load2150/Helix+/seed2

原失败 SHA256：2a717431f4bfd4ceac80c79192e81b2af7151e79b6f58cd4857445c25d8a65cc；最后重放失败 SHA256：5b63e8647edcd57067ca86b921338df12e76742b7a353774f679d362a39224f7。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/Helix+/seed2' --output 'experiments/manual_reruns/E5a/E5a/load2150/Helix+/seed2'
~~~

### E5a 040 · E5a/load2150/Helix+/seed4

原失败 SHA256：c8cb438ca229770fde740377dac791e236953707106328e0d5b7d5ab809fd102；最后重放失败 SHA256：762e2844cdfe31bd317ecb7502d7f238af4cb2f461cdf3550cf131a003e240b2。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/Helix+/seed4' --output 'experiments/manual_reruns/E5a/E5a/load2150/Helix+/seed4'
~~~

### E5a 041 · E5a/load2150/Helix/seed3

原失败 SHA256：04a1f57343cf41189700857ce0591c6dc0a0c6e07bbbcd7cbee2124260a21a9f；最后重放失败 SHA256：7fda605cd85f92b7396749bbfa1af23f2c7a7de7e4204fd20b0e40b829361e1f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/Helix/seed3' --output 'experiments/manual_reruns/E5a/E5a/load2150/Helix/seed3'
~~~

### E5a 042 · E5a/load2150/Helix/seed4

原失败 SHA256：d7240372225615d6f0af129d15a7d22dd60e903eaa566099fa5fa2d06eb170d8；最后重放失败 SHA256：5fe1f96a2581e77fd11b640e511dc2ffc6f32a59aec4be914944b4e51e2f63ce。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/Helix/seed4' --output 'experiments/manual_reruns/E5a/E5a/load2150/Helix/seed4'
~~~

### E5a 043 · E5a/load2150/RCAPS/seed0

原失败 SHA256：5cf2944b402fb710ff1393df065bd9167f7e1aa355f04087d9f0a0b2eeef0f3b；最后重放失败 SHA256：c36b6ce5cf838622d7faa224430315162f2472f22fc814d83153560c406d9be1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/RCAPS/seed0' --output 'experiments/manual_reruns/E5a/E5a/load2150/RCAPS/seed0'
~~~

### E5a 044 · E5a/load2150/RCAPS/seed1

原失败 SHA256：615cfa8fc222849f076daed131c12fcf48e595b826926bd842b9ddbedc4b0157；最后重放失败 SHA256：c263aaaadb125a8a03d2f41e5d3291bb57803edd4585462b049c3790b04edfa3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/RCAPS/seed1' --output 'experiments/manual_reruns/E5a/E5a/load2150/RCAPS/seed1'
~~~

### E5a 045 · E5a/load2150/RCAPS/seed2

原失败 SHA256：4ba146515c2b7a0c56538b398df09111e86f5562de1d2133fd63779c6271be2b；最后重放失败 SHA256：552a13aa98e38f479e51b32da19c12f92ef9d0e7ef59786725ed848c96c1089f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/RCAPS/seed2' --output 'experiments/manual_reruns/E5a/E5a/load2150/RCAPS/seed2'
~~~

### E5a 046 · E5a/load2150/RCAPS/seed3

原失败 SHA256：e8049d350bedc4da2fe96ea905073e5a356b8762fb66dbbe14e1c6ddc1463704；最后重放失败 SHA256：669fa0404b5fc09856412993594d830174ba4214a0f93bbf0d469d9e669e0992。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/RCAPS/seed3' --output 'experiments/manual_reruns/E5a/E5a/load2150/RCAPS/seed3'
~~~

### E5a 047 · E5a/load2150/RCAPS/seed4

原失败 SHA256：54b8dc4fb69ee214c6a3cc792a142063aa7b309dfc1db564729c80022920ef95；最后重放失败 SHA256：5d86abe392a9c1fa02c076eb780b7836aa599fd43883cb4c4481a72fea517202。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/RCAPS/seed4' --output 'experiments/manual_reruns/E5a/E5a/load2150/RCAPS/seed4'
~~~

## E5b：55 个未解决键

来源：experiments/reviewer_v2/E5_scale_kv/E5b/boundary_failure_replay/FINAL_AUDIT.json。

### E5b 001 · E5b/half_kv/multi/load320/Helix+/seed0

原失败 SHA256：4020b7c323b9cb03113e104ecd7ad7618e0576e350d174284c6737358f0062be；最后重放失败 SHA256：173fc0ee8343115d698ff88a49a1aa0480f19884b1b5102b0d9b21634d1a2ad2。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/Helix+/seed0' --output 'experiments/manual_reruns/E5b/E5b/half_kv/multi/load320/Helix+/seed0'
~~~

### E5b 002 · E5b/half_kv/multi/load320/Helix+/seed1

原失败 SHA256：3d93c3415aeb12f9e65fd22b5f0c1e5eaab2e0fbb2fb8077ef6d2d86098ee4b2；最后重放失败 SHA256：8151c2c9e06efe3bff4d9c9f8611ca7be5756be56ab8edbe54a47c36aea9791e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/Helix+/seed1' --output 'experiments/manual_reruns/E5b/E5b/half_kv/multi/load320/Helix+/seed1'
~~~

### E5b 003 · E5b/half_kv/multi/load320/Helix+/seed2

原失败 SHA256：9376cf6f295f977e0b55063beccaf90cbfeed86ed774e126f328bbc357e7dba4；最后重放失败 SHA256：da7c39b5be915a1ae94a821969f8e8625135dd7d438f3e1e94065aff8f2d9b03。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/Helix+/seed2' --output 'experiments/manual_reruns/E5b/E5b/half_kv/multi/load320/Helix+/seed2'
~~~

### E5b 004 · E5b/half_kv/multi/load320/Helix+/seed3

原失败 SHA256：6025ac655b09825eac4563439fc241d9780d3c4161836add4d40c9ae5c4bc811；最后重放失败 SHA256：9ddb936340aa18ddf72089334951122892b869fe6848e6cd3cd3cea58e7d55d2。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/Helix+/seed3' --output 'experiments/manual_reruns/E5b/E5b/half_kv/multi/load320/Helix+/seed3'
~~~

### E5b 005 · E5b/half_kv/multi/load320/Helix+/seed4

原失败 SHA256：d24fdd6c90028a3fdd0ab02ac23652e3a6e66f12d694e29d5697c20c8e76ac3b；最后重放失败 SHA256：04858964fd812887a9c2a3c700353c3997b6465eb41dbed4e57769b354c772bc。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/Helix+/seed4' --output 'experiments/manual_reruns/E5b/E5b/half_kv/multi/load320/Helix+/seed4'
~~~

### E5b 006 · E5b/half_kv/multi/load320/RCAPS-KV/seed2

原失败 SHA256：444bfbad107f3b554f3b39e3c6bed059337d895cff7f1a08d69ebffd10d511ac；最后重放失败 SHA256：d594fff05a16f779359519597d47b3e56240fd7cc6fdfc16247f8ff084a13865。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/RCAPS-KV/seed2' --output 'experiments/manual_reruns/E5b/E5b/half_kv/multi/load320/RCAPS-KV/seed2'
~~~

### E5b 007 · E5b/half_kv/multi/load320/RCAPS-KV/seed3

原失败 SHA256：f17f8d5942ccb6700655db70d6e3586b7d2f3d54fa4af05a6be6952888c62c8b；最后重放失败 SHA256：c68115e1b1c81e19d9765f6fa7cdd840663f3b7d2e0fa877611e70ab1fd8067d。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/RCAPS-KV/seed3' --output 'experiments/manual_reruns/E5b/E5b/half_kv/multi/load320/RCAPS-KV/seed3'
~~~

### E5b 008 · E5b/half_kv/multi/load320/RCAPS-KV/seed4

原失败 SHA256：f92574b52023da5cf265502cbecb8db2590207b42ff643a292973290ad15fa21；最后重放失败 SHA256：5f5baa09261c849490e0938d59d1918b42f974bd377e73749bd1e77313d1c216。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/RCAPS-KV/seed4' --output 'experiments/manual_reruns/E5b/E5b/half_kv/multi/load320/RCAPS-KV/seed4'
~~~

### E5b 009 · E5b/half_kv/single/load700/Helix+/seed0

原失败 SHA256：e65525b97811f049b1ff149fb3ec839ecca8f1564d765ef508a359e9d2b87244；最后重放失败 SHA256：f9d9da24a2b967d22ab5d8eec090bf47cf923d36723b146992b68672bd9dd715。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/single/load700/Helix+/seed0' --output 'experiments/manual_reruns/E5b/E5b/half_kv/single/load700/Helix+/seed0'
~~~

### E5b 010 · E5b/half_kv/single/load700/Helix+/seed1

原失败 SHA256：be35e620650a61374d4db64470e3a458309d19b5837fb7dd756ef0f5cc5469c0；最后重放失败 SHA256：cfdd1c8236513ca5088a5066c7efd64e730006f9d2f1b08182d3106c0b61bcaa。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/single/load700/Helix+/seed1' --output 'experiments/manual_reruns/E5b/E5b/half_kv/single/load700/Helix+/seed1'
~~~

### E5b 011 · E5b/half_kv/single/load700/Helix+/seed2

原失败 SHA256：0d3fe60d98aa4189e9a20a8743b485d137e1764fb3a6e45c7a8eceaf35c45406；最后重放失败 SHA256：7160cdbd936eaf19beb501ffaa37ea4e90a4592e2550d368dda3f39374b0d833。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/single/load700/Helix+/seed2' --output 'experiments/manual_reruns/E5b/E5b/half_kv/single/load700/Helix+/seed2'
~~~

### E5b 012 · E5b/half_kv/single/load700/Helix+/seed3

原失败 SHA256：431268142322361d865c2ef810cbf03d54972841f8bd5a2e2b36d64135f9eb59；最后重放失败 SHA256：ee1d04f368daacc8a3c1ba7f83cd000c1055ebce55c3b00da16729a69a07138a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/single/load700/Helix+/seed3' --output 'experiments/manual_reruns/E5b/E5b/half_kv/single/load700/Helix+/seed3'
~~~

### E5b 013 · E5b/half_kv/single/load700/Helix+/seed4

原失败 SHA256：86a4c5db1a73b852a3b66465ab105eb2bbd4fa3ffd11e604408b159fc19dfcfb；最后重放失败 SHA256：dbc69c187cf7e112828cff6ed6640e3942ed43471c90d5036d33ebb0c12c0b5a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/single/load700/Helix+/seed4' --output 'experiments/manual_reruns/E5b/E5b/half_kv/single/load700/Helix+/seed4'
~~~

### E5b 014 · E5b/half_kv/single/load700/RCAPS-KV/seed2

原失败 SHA256：58b907be23d9a50031a43180ad50718a21bd3bac487202831a66a77e6917a90a；最后重放失败 SHA256：0dc7abe36a1af10726bf9b8abe00eaf72f27c6a3ea17a7dfe2250d6867529baa。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/single/load700/RCAPS-KV/seed2' --output 'experiments/manual_reruns/E5b/E5b/half_kv/single/load700/RCAPS-KV/seed2'
~~~

### E5b 015 · E5b/half_kv/single/load700/RCAPS-KV/seed4

原失败 SHA256：11d08dcf574e8f3adc7eacc8a8a21ec08e2f5a1b8b25df8ea10b22016f67ff95；最后重放失败 SHA256：8d2fc6e20c5a993af554e8f9e382d02a89268416646f14b9a06a1b369cb6eb0c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/single/load700/RCAPS-KV/seed4' --output 'experiments/manual_reruns/E5b/E5b/half_kv/single/load700/RCAPS-KV/seed4'
~~~

### E5b 016 · E5b/prompt_1.5/multi/load320/Helix+/seed0

原失败 SHA256：33a7a34e0e0827c0c2dc23170b55f4a47462c66afb6059f04e07522d8a3834e4；最后重放失败 SHA256：2f6f677d9751d8e84b5939f525333523aa69f249a86c2a7ea910ff54955cb653。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/Helix+/seed0' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/multi/load320/Helix+/seed0'
~~~

### E5b 017 · E5b/prompt_1.5/multi/load320/Helix+/seed1

原失败 SHA256：7a4f62f8abc15d0f665135f04bfe0492104ecdcb9e6784b8cd32b85c345cc3c1；最后重放失败 SHA256：58d4f96282d80183f85545e5c137a178081973225628ea64ad9c2f7223d62a00。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/Helix+/seed1' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/multi/load320/Helix+/seed1'
~~~

### E5b 018 · E5b/prompt_1.5/multi/load320/Helix+/seed2

原失败 SHA256：8124df4deec0004ddc0b2514a2b2741fe57b169b7d4eb144d454e23baa8ca39c；最后重放失败 SHA256：84ba6203e3bd3a187b8572d4efe98196fb974c969ba8bc9c35f15e3f35e8d4bb。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/Helix+/seed2' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/multi/load320/Helix+/seed2'
~~~

### E5b 019 · E5b/prompt_1.5/multi/load320/Helix+/seed3

原失败 SHA256：511b48cabb5a9cd2df06733a23f50e6963d1432a8947c76b5f16fa2822f96350；最后重放失败 SHA256：f4461cbc5be82b631c1018ed927b6d3ac3b3b296f43f23a4d92f3f04bc4e3e49。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/Helix+/seed3' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/multi/load320/Helix+/seed3'
~~~

### E5b 020 · E5b/prompt_1.5/multi/load320/Helix+/seed4

原失败 SHA256：edcf7db38f3b13d8b95c9da290a97153d69edf381d4389c34bc56afe29a8bcbf；最后重放失败 SHA256：088385c3692ee2cfbcedbd113085be512baf96769926ed4e1092cb7d2f6ab83c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/Helix+/seed4' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/multi/load320/Helix+/seed4'
~~~

### E5b 021 · E5b/prompt_1.5/multi/load320/RCAPS-KV/seed1

原失败 SHA256：fff79800e73c402fd77c961d9b0e4a0320c0e0656619c5ff24c9c3145ddc07e0；最后重放失败 SHA256：155201868780090df79100b3e3d77aaf667eb7f780ad4081137f2e23c588e301。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/RCAPS-KV/seed1' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/multi/load320/RCAPS-KV/seed1'
~~~

### E5b 022 · E5b/prompt_1.5/multi/load320/RCAPS/seed1

原失败 SHA256：927c8022fc2a8c3c394adb1821253ae5fc29327e8ae8f09d4b7a1181a896b2fa；最后重放失败 SHA256：399d5d47254f24ca62c2689b1029928dd2e9576a800a515a5810473f76a41a4f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/RCAPS/seed1' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/multi/load320/RCAPS/seed1'
~~~

### E5b 023 · E5b/prompt_1.5/multi/load320/RCAPS/seed4

原失败 SHA256：55839cc53bcff60c8da97ce7ea3a753c9b65e743c1d7edbad6f8eefdde1ce7f3；最后重放失败 SHA256：cf7c74b274686a469760fdf40f8759ccc40ea887ff6c3ca6e390ebc90ca0708f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/RCAPS/seed4' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/multi/load320/RCAPS/seed4'
~~~

### E5b 024 · E5b/prompt_1.5/single/load700/Helix+/seed0

原失败 SHA256：0409211c927bf8c632130b471a83eee17eefbdf9f915da89cff733b09a484dec；最后重放失败 SHA256：e91a165cfbc50b85dfcd7bd7d77e0e472a519c4e36cbe7c44deb16eabb9b271a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/Helix+/seed0' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/single/load700/Helix+/seed0'
~~~

### E5b 025 · E5b/prompt_1.5/single/load700/Helix+/seed1

原失败 SHA256：069e3d132eaab9058e28d64350fea66f1752369d633551f522f9b925a41808d3；最后重放失败 SHA256：cd8725671049ef05e6cfa3464888c4edfe0bd1ac8edfc2f43f61657edd30c252。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/Helix+/seed1' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/single/load700/Helix+/seed1'
~~~

### E5b 026 · E5b/prompt_1.5/single/load700/Helix+/seed2

原失败 SHA256：d3bc4584ac9b1ea4b9ac89d222a4fac7ce7ee41105f629f5940e31972aa56087；最后重放失败 SHA256：c9ec1246638a7c3c8cf10c4a80165779e3c0ddb6661f715157949c5870280ac7。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/Helix+/seed2' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/single/load700/Helix+/seed2'
~~~

### E5b 027 · E5b/prompt_1.5/single/load700/Helix+/seed3

原失败 SHA256：62cf4e26fc1cebb1ff79d10756058cab8d6b027e308c9498f039472558dc9caa；最后重放失败 SHA256：3f6973ddd947a19297c2c22b7223b859fad46b6b7142b68dcd6e692b3fde8b79。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/Helix+/seed3' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/single/load700/Helix+/seed3'
~~~

### E5b 028 · E5b/prompt_1.5/single/load700/Helix+/seed4

原失败 SHA256：90c586f41832791b9e0d53548b318fc926aba516a1bf18cff7c0ccef2e29a4fc；最后重放失败 SHA256：23d7d407475d8f7bd9fef263c406b3c4fd0949bb4ac0ba2218e6676fb20bf352。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/Helix+/seed4' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/single/load700/Helix+/seed4'
~~~

### E5b 029 · E5b/prompt_1.5/single/load700/RCAPS-KV/seed1

原失败 SHA256：3395cf5078d14f0fa04d6b70ab9adf6a6190449cec15d8fb7dec12810aefc2e3；最后重放失败 SHA256：0f17c8fd43a15c5be98f767f90abd0eb63a99b06a1b6829dceaedef6b56ea76d。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/RCAPS-KV/seed1' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/single/load700/RCAPS-KV/seed1'
~~~

### E5b 030 · E5b/prompt_1.5/single/load700/RCAPS-KV/seed2

原失败 SHA256：1531ace186d9a888cdde445041da19584678fbcb912306ce9596b305795080c9；最后重放失败 SHA256：764935cd89f6e2d65e4c45e4e10da9d2af1b9922e98db5953ea5f2c289baa81f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/RCAPS-KV/seed2' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/single/load700/RCAPS-KV/seed2'
~~~

### E5b 031 · E5b/prompt_1.5/single/load700/RCAPS-KV/seed3

原失败 SHA256：d09a1ffc09d154fdc810478cc29c9c094c720da7656cefd34532ec8d1c0ca1e8；最后重放失败 SHA256：f68cc5bf795d0fadf958b97ae7d6c53ff62c80cde5eec76632c076186933f226。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/RCAPS-KV/seed3' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/single/load700/RCAPS-KV/seed3'
~~~

### E5b 032 · E5b/prompt_1.5/single/load700/RCAPS-KV/seed4

原失败 SHA256：cdc18bcf5b1bda06cae6ea1c5f65eb169704c03fb09b9cef856fb91284b88524；最后重放失败 SHA256：b869e75aba78bf540a2cbfef1dd6ce2af1923e29430909cd2cbc5205cab2c48b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/RCAPS-KV/seed4' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/single/load700/RCAPS-KV/seed4'
~~~

### E5b 033 · E5b/prompt_1.5/single/load700/RCAPS/seed4

原失败 SHA256：408cfd516ecc8ab28007e674972b0d3fd74b55ed6f35bb00b213d5e5c3db5738；最后重放失败 SHA256：24896094ecb189732ea0e3e996bada2eb6021cc4cb272053ce84b25dda636a75。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/RCAPS/seed4' --output 'experiments/manual_reruns/E5b/E5b/prompt_1.5/single/load700/RCAPS/seed4'
~~~

### E5b 034 · E5b/prompt_2.0/multi/load320/Helix+/seed0

原失败 SHA256：a4edabcde0228a1ab1a6e851a2b0e094931a10a5e77c3ba755e73b04182fa8b5；最后重放失败 SHA256：4cec51990c43ad6750d1108d411547b10285c05ccf28a6abe9cdafde1e25409e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/Helix+/seed0' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/multi/load320/Helix+/seed0'
~~~

### E5b 035 · E5b/prompt_2.0/multi/load320/Helix+/seed1

原失败 SHA256：d48ed75ebe4e9b772132489814e0a6fbe6e45466b9ef386058125b73f29b2bb1；最后重放失败 SHA256：37ca6461b48f9419002585a2c9604c214879602d72eac1b0e5f74c2510a0633b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/Helix+/seed1' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/multi/load320/Helix+/seed1'
~~~

### E5b 036 · E5b/prompt_2.0/multi/load320/Helix+/seed2

原失败 SHA256：d2080d029fac414314f9c9903a342a7918d811876991d0a9191352f0c5a211f4；最后重放失败 SHA256：2ca758fde35a5f625317bf92c61e0ae6e3e94130d52dbece6ea78701467ca047。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/Helix+/seed2' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/multi/load320/Helix+/seed2'
~~~

### E5b 037 · E5b/prompt_2.0/multi/load320/Helix+/seed3

原失败 SHA256：74bf209b1aca0673f6f0683849e19f1bc1c500559429c96e7867a3535d47197b；最后重放失败 SHA256：f59c15b8f29617b53509f69af33bf4f2efcd0911297a543eff61410f37b09886。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/Helix+/seed3' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/multi/load320/Helix+/seed3'
~~~

### E5b 038 · E5b/prompt_2.0/multi/load320/Helix+/seed4

原失败 SHA256：c407bdb4f68c8e5f2e1b665a696d9b52a589d6af56dfbd24930fd69b046fb6b0；最后重放失败 SHA256：2f2643c2a750d5e7634ca53cd031cae694e99daf63ec471689aba36bc0bd4173。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/Helix+/seed4' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/multi/load320/Helix+/seed4'
~~~

### E5b 039 · E5b/prompt_2.0/multi/load320/RCAPS-KV/seed2

原失败 SHA256：717ca8669cb46c22daadf42664929895c0acac37101f7da64639828afe4a38d2；最后重放失败 SHA256：b130d5538faa0bf3eb7eea452d177b546e8f516458753133790c2ff36486e930。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/RCAPS-KV/seed2' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/multi/load320/RCAPS-KV/seed2'
~~~

### E5b 040 · E5b/prompt_2.0/multi/load320/RCAPS/seed0

原失败 SHA256：7b928e8f19c2c7c7adcd9107c115cc77f0107e1ab781e3923bac110b57f540f2；最后重放失败 SHA256：65e567609c38d9a720c435c4eb97d05b325656c489570e9dffaa0ea86fc60179。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/RCAPS/seed0' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/multi/load320/RCAPS/seed0'
~~~

### E5b 041 · E5b/prompt_2.0/multi/load320/RCAPS/seed1

原失败 SHA256：adb9f3af642fd06f0e2d6c94abacb041b8a1deb4d5ef30b22aa874a0b7e069dc；最后重放失败 SHA256：71bc63c5dd61a5b5c188327f4c07127a67c4175ac227026d7e724a0597f8a144。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/RCAPS/seed1' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/multi/load320/RCAPS/seed1'
~~~

### E5b 042 · E5b/prompt_2.0/multi/load320/RCAPS/seed3

原失败 SHA256：f3f8be264676fda7f7eaccd1c29758e7f044c21c4b142a7f28147327c26f3aae；最后重放失败 SHA256：13a94909a4a414e7e7297eaf18e7322182bcf52bacaa68329b8544643256ce19。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/RCAPS/seed3' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/multi/load320/RCAPS/seed3'
~~~

### E5b 043 · E5b/prompt_2.0/multi/load320/RCAPS/seed4

原失败 SHA256：f627cde22ff42efbf485a7fe92bedcd52c98f1e4118d11cbe4d7faba34cf1beb；最后重放失败 SHA256：4b6eec9ea1a311a5be3b03aac188d12d5360854d9af60435d2a6ffb69cf84e25。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/RCAPS/seed4' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/multi/load320/RCAPS/seed4'
~~~

### E5b 044 · E5b/prompt_2.0/single/load700/Helix+/seed0

原失败 SHA256：acf3d87239a7342e0d94206e032681ba9030d54a1e0143d72ff53e64640d646b；最后重放失败 SHA256：4324ee6847c3f2e7030411816461c235382948b84b860a7c1bb38f3d8bcc1de7。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/Helix+/seed0' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/single/load700/Helix+/seed0'
~~~

### E5b 045 · E5b/prompt_2.0/single/load700/Helix+/seed1

原失败 SHA256：cd33fc75e792113ba565726d63f3c9dee5104dfe1d55c0499cee2a16f8398a7d；最后重放失败 SHA256：ab235b37bf6fb12617e4c909cd94cd3ef74d0431ba32ac83a2202ea65aaab0d9。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/Helix+/seed1' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/single/load700/Helix+/seed1'
~~~

### E5b 046 · E5b/prompt_2.0/single/load700/Helix+/seed2

原失败 SHA256：6cdfd7af32fc14f2a9569b8f88cbc275dbb2e2273482bc0eba3f9601d5524b3a；最后重放失败 SHA256：fd0d2d4718505e268a4a5543ea18748c1af48cf9ae9d05fb31f2297dd02d75df。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/Helix+/seed2' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/single/load700/Helix+/seed2'
~~~

### E5b 047 · E5b/prompt_2.0/single/load700/Helix+/seed3

原失败 SHA256：0d3884dfeac005287daaeef6c1caf6a588d575353b6b35872f584d7f97298ba6；最后重放失败 SHA256：2390aeb218a736306dd88eda3c7814a82978c94a0209599925293d620e4629c8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/Helix+/seed3' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/single/load700/Helix+/seed3'
~~~

### E5b 048 · E5b/prompt_2.0/single/load700/Helix+/seed4

原失败 SHA256：10ea7dd4c5c119007c0fb9df587de57adf0a3a5db5a5697a8461accd6627b4c5；最后重放失败 SHA256：4a7c91bab63a2657ed89d6de850f3be47f013027c63534867e96be7abe120ce0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/Helix+/seed4' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/single/load700/Helix+/seed4'
~~~

### E5b 049 · E5b/prompt_2.0/single/load700/RCAPS-KV/seed1

原失败 SHA256：3a6b85456fb88bbb9d3fb29a4d7a45317e7342c09bf4039ea397cba9ba373e0b；最后重放失败 SHA256：130cd893d1277465b5e51817b00c56ba78e177b66855cd04dbbd96deae53a157。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS-KV/seed1' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/single/load700/RCAPS-KV/seed1'
~~~

### E5b 050 · E5b/prompt_2.0/single/load700/RCAPS-KV/seed4

原失败 SHA256：9d97a240ac9cbcd1372894e19f7cd73a8e17f6ebfe08d22f5c88964cb540ce1d；最后重放失败 SHA256：9705a0c8e4baacb1167b4d2201980f5190d909ce7f896fb640d8d19089605327。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS-KV/seed4' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/single/load700/RCAPS-KV/seed4'
~~~

### E5b 051 · E5b/prompt_2.0/single/load700/RCAPS/seed0

原失败 SHA256：8f67a6cf4bc77e40ec9dcbaa86288e2886abaadcfda5739baa0c33a999ec9959；最后重放失败 SHA256：4312c8a46926fbb6050b2d2f7693702ad332606cd128b3ec334078f0d948d95e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS/seed0' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/single/load700/RCAPS/seed0'
~~~

### E5b 052 · E5b/prompt_2.0/single/load700/RCAPS/seed1

原失败 SHA256：ee4c57b44d54b7c71904a0f90a6b4a2ff60698fb30d43bde36f13254f3c91436；最后重放失败 SHA256：7077f4142d09ac534b464dfea836c9f31001bc7596a543673bad28380a0a2020。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS/seed1' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/single/load700/RCAPS/seed1'
~~~

### E5b 053 · E5b/prompt_2.0/single/load700/RCAPS/seed2

原失败 SHA256：2b72bd46fd4076245a5eb9accdd73647e1416f81ff6403b3c0662ecd04a85639；最后重放失败 SHA256：42d3634ec201e42c33922d4222bf92c90e93273c235c1e974bd16232903531f6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS/seed2' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/single/load700/RCAPS/seed2'
~~~

### E5b 054 · E5b/prompt_2.0/single/load700/RCAPS/seed3

原失败 SHA256：0a3cf836c4e3cfc2a9b7df6acd081199c951fd0fb885a3db7eb9db9788cd1bec；最后重放失败 SHA256：38aa464b5eb4b82379b00afc4bb3944372de5d5874aa6c4ca7aec0b40881e29e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS/seed3' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/single/load700/RCAPS/seed3'
~~~

### E5b 055 · E5b/prompt_2.0/single/load700/RCAPS/seed4

原失败 SHA256：910f86bf056b0e5bddd15e5c42c71d5dea4dd50b710aed5c1cde00eb4460b5e6；最后重放失败 SHA256：a6662792c4656762c55ec79d417d949984d06330dbca5698ebfef4a45314505f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS/seed4' --output 'experiments/manual_reruns/E5b/E5b/prompt_2.0/single/load700/RCAPS/seed4'
~~~

## V5：68 个未解决键

来源：experiments/v5_failure_replay/FINAL_AUDIT.json。

### V5 001 · v5_kv_stress/multi/load320/capacity0.125/V4/seed0

原失败 SHA256：b4c01fc6c2b40a9b76327f4ae7012c999567583c2c7a0016b303af163eff986d；最后重放失败 SHA256：2678c6aca99bf0eea16e40a23c9a9d820c508a8798a1e689acb6645edfe5b673。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/multi/load320/capacity0.125/V4/seed0' --output 'experiments/manual_reruns/V5/v5_kv_stress/multi/load320/capacity0.125/V4/seed0'
~~~

### V5 002 · v5_kv_stress/multi/load320/capacity0.125/V4/seed1

原失败 SHA256：5c143914a234d0412d320ef79bc8fbe3329d61fac757daa2a0196034a57138b8；最后重放失败 SHA256：20899a10a8ecf0aa87e1abc983f798ec34d39a494422752bb11617493775e246。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/multi/load320/capacity0.125/V4/seed1' --output 'experiments/manual_reruns/V5/v5_kv_stress/multi/load320/capacity0.125/V4/seed1'
~~~

### V5 003 · v5_kv_stress/multi/load320/capacity0.125/V4/seed2

原失败 SHA256：94a79c7891eaf0431f13de850cf332a1e3b46705a6bfff9272d42a5768747a31；最后重放失败 SHA256：07d7a20634eb057a69e8343b3aa620cfbc68ddade9ae80f4824b7dabfabfe1d0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/multi/load320/capacity0.125/V4/seed2' --output 'experiments/manual_reruns/V5/v5_kv_stress/multi/load320/capacity0.125/V4/seed2'
~~~

### V5 004 · v5_kv_stress/multi/load320/capacity0.125/V4/seed3

原失败 SHA256：871db564b5e345884060d6bdd49d66f5820ca6ed33d25ac4dd96df383ec623ca；最后重放失败 SHA256：d44d6329c171708ddba38d8fc0e7ee7a6847508a7dd1235d008e8fea0007c785。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/multi/load320/capacity0.125/V4/seed3' --output 'experiments/manual_reruns/V5/v5_kv_stress/multi/load320/capacity0.125/V4/seed3'
~~~

### V5 005 · v5_kv_stress/multi/load320/capacity0.125/V4/seed4

原失败 SHA256：9811517e786295fae374047ddde01fc859c41852424d6b11471e1c0ae049acc8；最后重放失败 SHA256：c8b94de79ff5bc2183a16e4b968e7e11a548eb43c381bd245c9eae8ad3e07781。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/multi/load320/capacity0.125/V4/seed4' --output 'experiments/manual_reruns/V5/v5_kv_stress/multi/load320/capacity0.125/V4/seed4'
~~~

### V5 006 · v5_kv_stress/single/load700/capacity0.125/V4/seed0

原失败 SHA256：ef4ae43213336db954a96c98a8d9b4b65d42dcd61a778b5bda57b0ffafa9ca1e；最后重放失败 SHA256：6dac6ebe3d84c651ad9f8d34a821a89940c0085c0d26e060e102b7c350babc82。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.125/V4/seed0' --output 'experiments/manual_reruns/V5/v5_kv_stress/single/load700/capacity0.125/V4/seed0'
~~~

### V5 007 · v5_kv_stress/single/load700/capacity0.125/V4/seed1

原失败 SHA256：ab79b9a4da29c236f6822a1e74879fbd5ef8f13b54e9559619b0e6294c58652e；最后重放失败 SHA256：4d9fea65b819b4a10a24922292d22ce728ee5682e91ae0ae40dec70f5ab371e5。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.125/V4/seed1' --output 'experiments/manual_reruns/V5/v5_kv_stress/single/load700/capacity0.125/V4/seed1'
~~~

### V5 008 · v5_kv_stress/single/load700/capacity0.125/V4/seed2

原失败 SHA256：920d2d4f6cb29bb6c8bf983ea010fb8271f800301481525bd2cf93366b1e2080；最后重放失败 SHA256：035b76a454185a0ecb92d414591dc79a0701dd9887b454eb1cb5a556597c17ae。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.125/V4/seed2' --output 'experiments/manual_reruns/V5/v5_kv_stress/single/load700/capacity0.125/V4/seed2'
~~~

### V5 009 · v5_kv_stress/single/load700/capacity0.125/V4/seed3

原失败 SHA256：a4fcd333a6bede34daf26972eddfab7504f2f6ebc4ff11e3682b833dce00a819；最后重放失败 SHA256：b5161bad804ec50d860760856821b675392967635ec521ec590d8524583bbdd0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.125/V4/seed3' --output 'experiments/manual_reruns/V5/v5_kv_stress/single/load700/capacity0.125/V4/seed3'
~~~

### V5 010 · v5_kv_stress/single/load700/capacity0.125/V4/seed4

原失败 SHA256：9ee543eb98d30456252ec5a27d0ace0d4d1901386b35d721bcfd281f0ea01e99；最后重放失败 SHA256：594e326c8d012b770c7cce846cffc8e66f609e9e6203291027dfab5ba8d913d1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.125/V4/seed4' --output 'experiments/manual_reruns/V5/v5_kv_stress/single/load700/capacity0.125/V4/seed4'
~~~

### V5 011 · v5_kv_stress/single/load700/capacity0.25/V4/seed0

原失败 SHA256：8e76d6ded77befca2600967a07d65050e1aff17cca45f39b6c45b0c9c922c004；最后重放失败 SHA256：b8fe7b2c51656b89a75c61b4eaa29348e44a846fbe3ca364eae590736ed8ade1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.25/V4/seed0' --output 'experiments/manual_reruns/V5/v5_kv_stress/single/load700/capacity0.25/V4/seed0'
~~~

### V5 012 · v5_kv_stress/single/load700/capacity0.25/V4/seed1

原失败 SHA256：26afee2f740fe42307116c2baf8c001f9e8af42a4cb632cc0a7e2120acb34e48；最后重放失败 SHA256：af98578157cbd4d82b2a76f28e7f8349c18f4d182ab8b754a7585ea7406f67fb。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.25/V4/seed1' --output 'experiments/manual_reruns/V5/v5_kv_stress/single/load700/capacity0.25/V4/seed1'
~~~

### V5 013 · v5_kv_stress/single/load700/capacity0.25/V4/seed2

原失败 SHA256：3e36db6c8e605181d67169c8078a528368a1f9c783bfd5861d62b2ce194b8f21；最后重放失败 SHA256：cf0e488034df0bca591d56a28570d4315510fe103ff13b61fa6fde10441707e0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.25/V4/seed2' --output 'experiments/manual_reruns/V5/v5_kv_stress/single/load700/capacity0.25/V4/seed2'
~~~

### V5 014 · v5_kv_stress/single/load700/capacity0.25/V4/seed3

原失败 SHA256：db80fde639a42f9d78c09aba47932130a7d559f70666981934e35ab8349662cb；最后重放失败 SHA256：91441b75e881bddaf8c653a0aae2124b1cb4e104ff2e6fbbe91d5d568ee9755a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.25/V4/seed3' --output 'experiments/manual_reruns/V5/v5_kv_stress/single/load700/capacity0.25/V4/seed3'
~~~

### V5 015 · v5_kv_stress/single/load700/capacity0.25/V4/seed4

原失败 SHA256：f7bd2fdaeb5b60846d3a369b53d04a3085ea080982135563205fd9c9dfdcc458；最后重放失败 SHA256：5a14c58c00d6deac866ee105c42ecd34802a67432e05f19437f3f30c2ecfce6d。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.25/V4/seed4' --output 'experiments/manual_reruns/V5/v5_kv_stress/single/load700/capacity0.25/V4/seed4'
~~~

### V5 016 · v5_model30b/multi/load840/V4/seed0

原失败 SHA256：9a2481f3da6d9bbe362a6f547c72f0948f9be0f475bf93b57e891af94063c2bd；最后重放失败 SHA256：0a552291e5142d9d2a373a13c0421aa595a78a3426450a68891a508a3c4339e1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b/multi/load840/V4/seed0' --output 'experiments/manual_reruns/V5/v5_model30b/multi/load840/V4/seed0'
~~~

### V5 017 · v5_model30b/multi/load840/V4/seed1

原失败 SHA256：8dd8b84f6f4ebeebdf3650b43d7cbe8e1a6210d818584e13634ec76cbd0b147d；最后重放失败 SHA256：e5481ae2a05d0d12599286deae6d2e634236624a5f47fcd39476a3d61a877c9e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b/multi/load840/V4/seed1' --output 'experiments/manual_reruns/V5/v5_model30b/multi/load840/V4/seed1'
~~~

### V5 018 · v5_model30b/multi/load840/V4/seed2

原失败 SHA256：d4c6d3432f107b65530a0259dd468e0f3e1f4e43e4876fe31d4b7c633f2ebba5；最后重放失败 SHA256：f846a90cd00c9d0d978bd0cc9cc393d85a0d0763e8d7003d8302f381e09fbd61。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b/multi/load840/V4/seed2' --output 'experiments/manual_reruns/V5/v5_model30b/multi/load840/V4/seed2'
~~~

### V5 019 · v5_model30b/multi/load840/V4/seed3

原失败 SHA256：3d356c821d5cfd85955ec53258738b10f519088d855faee72f7d2cf2a3ac0d09；最后重放失败 SHA256：382605d803ac08f90e716d1534d15d4446af623ab6da3d50478eeb5916e70017。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b/multi/load840/V4/seed3' --output 'experiments/manual_reruns/V5/v5_model30b/multi/load840/V4/seed3'
~~~

### V5 020 · v5_model30b/multi/load840/V4/seed4

原失败 SHA256：e1d76fd62fb881ec72d99f263168f6d1b086576f9dd494a230847c80eed70d0d；最后重放失败 SHA256：6b551a8cba804f07600efab433879c5b0590951fd684593d0c45d997cb7ff2a8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b/multi/load840/V4/seed4' --output 'experiments/manual_reruns/V5/v5_model30b/multi/load840/V4/seed4'
~~~

### V5 021 · v5_model30b_pools/multi/load840/HH/seed2

原失败 SHA256：0c52969c0c04a020788f4b2c1c1abba9c8d58dff609767e442ead239ab4e6ad5；最后重放失败 SHA256：d55d756a8d141428d4eed5c8e1b1df2fe066468128c37017bb0d6a5e9af07dee。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b_pools/multi/load840/HH/seed2' --output 'experiments/manual_reruns/V5/v5_model30b_pools/multi/load840/HH/seed2'
~~~

### V5 022 · v5_model30b_pools/multi/load840/HH/seed3

原失败 SHA256：fb6facce977850c9708dceb8ab240356b742df6a9edd5c73ce5123fdddd941a5；最后重放失败 SHA256：45f85a857532aa9a0af352c5f2a57a2b8441737378845f5d8672602fc3648535。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b_pools/multi/load840/HH/seed3' --output 'experiments/manual_reruns/V5/v5_model30b_pools/multi/load840/HH/seed3'
~~~

### V5 023 · v5_model30b_pools/multi/load840/HH/seed4

原失败 SHA256：bab27d311a7deea5abb19688b731d4ca8b821867a16a03d03f12af7930b96497；最后重放失败 SHA256：55233b167a3fd238b12cdc406805b21c4c61eb04ab62af08530e82b42874b16c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b_pools/multi/load840/HH/seed4' --output 'experiments/manual_reruns/V5/v5_model30b_pools/multi/load840/HH/seed4'
~~~

### V5 024 · v5_model30b_pools/multi/load840/HHplus/seed2

原失败 SHA256：12bdf5026a46e85123e484d6131a88ca23f259e90cddef0cff4159c0af0ea6c6；最后重放失败 SHA256：b8bec00a058bb35aa532753fb2044f4551fe5f251a4ceb05203a5cf7e59800b1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b_pools/multi/load840/HHplus/seed2' --output 'experiments/manual_reruns/V5/v5_model30b_pools/multi/load840/HHplus/seed2'
~~~

### V5 025 · v5_model30b_pools/multi/load840/HHplus/seed4

原失败 SHA256：90b0be0bcd36aa43ded3cf81052b36490c1056480bb2b473fadaf1bae9738a82；最后重放失败 SHA256：922fddb1aaf003a5a353b8372cf41ed381990cc5c86728519c003c73ec9f5bd5。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b_pools/multi/load840/HHplus/seed4' --output 'experiments/manual_reruns/V5/v5_model30b_pools/multi/load840/HHplus/seed4'
~~~

### V5 026 · v5_model30b_pools/single/load970/HH/seed3

原失败 SHA256：3b55549e4947b967c0f53c845eb3f1924b22ea9219c663031d3694615157ef6a；最后重放失败 SHA256：914de60e49c0e004c3fb8ff01d5fad36c8fc784779b0d76f667023bcbffe3962。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b_pools/single/load970/HH/seed3' --output 'experiments/manual_reruns/V5/v5_model30b_pools/single/load970/HH/seed3'
~~~

### V5 027 · v5_parallax/single/load700/helix_fifo/seed3

原失败 SHA256：45ce1c6e3faeb9e016a32cbc829e2275138697aa9271f5fb3c667ee70164bb45；最后重放失败 SHA256：de68a8dbee61fd602479a46ab180afc4f37bd463e0e8dae35c7180bedd2a2c12。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_parallax/single/load700/helix_fifo/seed3' --output 'experiments/manual_reruns/V5/v5_parallax/single/load700/helix_fifo/seed3'
~~~

### V5 028 · v5_seed_completion/multi/load240/separate/seed0

原失败 SHA256：d30ff0b1d94cc50599ad75d0fd918d31841d5f6c087927442424e25c3ef949f4；最后重放失败 SHA256：d5e56bd9712c84594b7cd924dc7f08647a8f2696681b7c17f80463a08a0bea82。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load240/separate/seed0' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load240/separate/seed0'
~~~

### V5 029 · v5_seed_completion/multi/load240/separate/seed1

原失败 SHA256：ded329241ac626647989bf3c1aeba41d373d0b6e6203bc4aa4c9836fc50c6a09；最后重放失败 SHA256：0534b25763b543f68e6bbbad6feae8c280d6f2d2af5fb018d9d4b4e1e471a05e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load240/separate/seed1' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load240/separate/seed1'
~~~

### V5 030 · v5_seed_completion/multi/load240/separate/seed3

原失败 SHA256：c493d9e2346e1cf357d65f74f51f811b7af8ed7f735fe0d5ab97b798babfed35；最后重放失败 SHA256：187848ea20c48cc7e5b80f3d01ddeaaf03be3abbadd906c92d79d36be937b4e6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load240/separate/seed3' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load240/separate/seed3'
~~~

### V5 031 · v5_seed_completion/multi/load240/separate/seed4

原失败 SHA256：92545c8f8a0f90a5c560f207b80862dc50a2048c233648b6e1cdded6046f5494；最后重放失败 SHA256：560dd7f34c40c567575f68feb828809834e1a710f8b56beffead77c7495a2c2e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load240/separate/seed4' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load240/separate/seed4'
~~~

### V5 032 · v5_seed_completion/multi/load320/separate/seed0

原失败 SHA256：445c4297d60d9b0bace64d2d788f6345df09c49f9856955209932781cbc6b231；最后重放失败 SHA256：d84cb93be41777ace14296993d2341261743720dd436a52364b60059a8ec3465。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/separate/seed0' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load320/separate/seed0'
~~~

### V5 033 · v5_seed_completion/multi/load320/separate/seed1

原失败 SHA256：a4efb04483a92c14f0e49c55e0e057bfb892877647913ce63be436a6a7a0950c；最后重放失败 SHA256：6ff5d472635daa48864558e5f83dfa461ae315d96e7a2b6d9ee21c2847cc0d8c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/separate/seed1' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load320/separate/seed1'
~~~

### V5 034 · v5_seed_completion/multi/load320/separate/seed2

原失败 SHA256：aa4cc27ff3e05b40cba81ff1a7cc04c84e2b2869ebafff74c18ff98d5adf0c9c；最后重放失败 SHA256：4c865d86bf0bb498d642db64da3b90331ebc310a21dc7d992818e1bfe3d509c0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/separate/seed2' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load320/separate/seed2'
~~~

### V5 035 · v5_seed_completion/multi/load320/separate/seed3

原失败 SHA256：26193449def1f63e4a01fcda1e824b2c8f46d041c79821101d9bcc7a498775e7；最后重放失败 SHA256：0bae3a9f97d0cd55751ed78aa0a8906b5e9deec655079ba9eb4b2de788e0f2fe。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/separate/seed3' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load320/separate/seed3'
~~~

### V5 036 · v5_seed_completion/multi/load320/separate/seed4

原失败 SHA256：2fcac2de0300a417c59ba95bda94b1ad8fa06de41c92d91ebf5704fb603615ab；最后重放失败 SHA256：896d20d1beaa081e0487f215ddd99b42ad6720b58b16e16b057a7bb120fad841。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/separate/seed4' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load320/separate/seed4'
~~~

### V5 037 · v5_seed_completion/multi/load320/swarm/seed0

原失败 SHA256：39b942228a82536d96eea69e5fe0114502dcfb8a3878229c6fb0d144defc53ab；最后重放失败 SHA256：a23b2c2b5fde669add07f8afadfca6872b53b9998f41e1b6d8bb565759b59503。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/swarm/seed0' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load320/swarm/seed0'
~~~

### V5 038 · v5_seed_completion/multi/load320/swarm/seed1

原失败 SHA256：0b40e39c8eb72e61dbfa8d56de75838756079ac02df4ad8c959817b28254b8e1；最后重放失败 SHA256：56b5b85be26c010474e78e04fae579454a2b5e2e6509bdf2ca0c9d64362f10f1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/swarm/seed1' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load320/swarm/seed1'
~~~

### V5 039 · v5_seed_completion/multi/load320/swarm/seed3

原失败 SHA256：8170f606de1f73fa9e9f1c1c65cd8c661e8c57aef0e6015fdacd5d9e26f2b30d；最后重放失败 SHA256：be98af1c66e41d4f1a9d46a8e30c82404be8518e75013ce1fcb94669f129bca6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/swarm/seed3' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load320/swarm/seed3'
~~~

### V5 040 · v5_seed_completion/multi/load320/swarm/seed4

原失败 SHA256：7accf1e13a86b5e299bef149507b0b5a93dc4e00559a36a274cf7be8fb791461；最后重放失败 SHA256：14cf0947a236e4dd6598bed268b58b0f210c3ef86396499ef1ddeeb16a5b7f82。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/swarm/seed4' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load320/swarm/seed4'
~~~

### V5 041 · v5_seed_completion/multi/load400/HH/seed0

原失败 SHA256：cbb79432c125a007ffda557e6e781c0c616182e7549810e79d720c16f28d3a90；最后重放失败 SHA256：091535987e92b2c23cd6b30d69187d880c33dc2297f3d5f61aee0335470387c0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HH/seed0' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load400/HH/seed0'
~~~

### V5 042 · v5_seed_completion/multi/load400/HH/seed3

原失败 SHA256：baff918e1e41c90912f95247644ff0e3cd5e52b7b34854cba1da21d1768149b7；最后重放失败 SHA256：0c160f80ced1c24456c8bd60cc77ed0495bbedc1d388082de3858cc5e59d85ae。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HH/seed3' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load400/HH/seed3'
~~~

### V5 043 · v5_seed_completion/multi/load400/HH/seed4

原失败 SHA256：352ff8e90a77611dd472373920df9c1f66bf1cd99211b2167752802f66e7f886；最后重放失败 SHA256：b4fefd42bf7135903e93142cb174d9ee102fae5e9462559cf2f6f4f4f976558f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HH/seed4' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load400/HH/seed4'
~~~

### V5 044 · v5_seed_completion/multi/load400/HHplus/seed0

原失败 SHA256：e79d3c4b8a9659696a6d22a9f6da4ec527b04a6e68d8855c2d04a33669fed61a；最后重放失败 SHA256：4fcd1e7250bb1418bc472dc6c114381fa993948c898b369b65eecd51e0cca156。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HHplus/seed0' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load400/HHplus/seed0'
~~~

### V5 045 · v5_seed_completion/multi/load400/HHplus/seed1

原失败 SHA256：24612f74f6756329379b7387ea9da0dae20e078ebf3c3a9766a3795fdd925873；最后重放失败 SHA256：8c686c2e423739c3e7343d4d32e45d6e92341e77d5ba46813724f6b4505de719。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HHplus/seed1' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load400/HHplus/seed1'
~~~

### V5 046 · v5_seed_completion/multi/load400/HHplus/seed2

原失败 SHA256：dc0ec0c69b32b36baa5ef1761acde4a6dc38b673fa3874e97d92ff0b27eb1d16；最后重放失败 SHA256：366c5d071a43336f7df5b6ad68d34261b2b55db93ecbea0c6eac0336397723f6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HHplus/seed2' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load400/HHplus/seed2'
~~~

### V5 047 · v5_seed_completion/multi/load400/HHplus/seed3

原失败 SHA256：7370008035237ef2418bf57ae5ddf239e262fe2951a36b596f449dd71c8fbcdf；最后重放失败 SHA256：2ac45a28cc61213d224af15e84d872a0743455d0628f0543bf0a7c3659ab48cd。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HHplus/seed3' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load400/HHplus/seed3'
~~~

### V5 048 · v5_seed_completion/multi/load400/HHplus/seed4

原失败 SHA256：bacf67037492447d9051aba51233e69a887c8565276055cf7e91a1e3aa7aa8e6；最后重放失败 SHA256：3ad2a5fbd880b9349f15882748ee8a331d2d60fe9eedd6ac22dee2fce8b690be。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HHplus/seed4' --output 'experiments/manual_reruns/V5/v5_seed_completion/multi/load400/HHplus/seed4'
~~~

### V5 049 · v5_seed_completion/single/load700/separate/seed0

原失败 SHA256：c4de3cd7ff2c8cb95150a2f6b467841c0836b9292cc9aaaf87e35926f75c1397；最后重放失败 SHA256：4356550043ce5485ffe77d7133f4a2ee9522a3fde00cf791213a7e6061c74874。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/separate/seed0' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load700/separate/seed0'
~~~

### V5 050 · v5_seed_completion/single/load700/separate/seed1

原失败 SHA256：8bfb2adc5bb80ab7868e8c04243486793008cbed420d6429173b6b439a44a55b；最后重放失败 SHA256：7fdc6afd942a66cef2d33d668a31505dd4e7dcd3570f7dbadb49fd6f65c6a80d。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/separate/seed1' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load700/separate/seed1'
~~~

### V5 051 · v5_seed_completion/single/load700/separate/seed2

原失败 SHA256：0324e86c90159ca314452446772b46fa4e6d7a47ab599badb0e7fa35fc4c828f；最后重放失败 SHA256：55bfff1f92330ec01f357fd2e82b6917effe4f026378c5ff718a0d385486563b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/separate/seed2' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load700/separate/seed2'
~~~

### V5 052 · v5_seed_completion/single/load700/separate/seed3

原失败 SHA256：dd143c791ee16dffdff3c929d09b584f9ed6611b07a81e5df39913429c52c165；最后重放失败 SHA256：0f483032c65f3bb05132d3bbe0adf3c5a280fb3af77a941a5d9d9e12f466a4b0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/separate/seed3' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load700/separate/seed3'
~~~

### V5 053 · v5_seed_completion/single/load700/separate/seed4

原失败 SHA256：a444230581541c9d95e2464fea0376013a6fcf5079a434be615fdc80cc5b1b0e；最后重放失败 SHA256：88140d7572aacbc86a898d10a6847946698e6be7937f2d9b0900c23a35b76e3c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/separate/seed4' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load700/separate/seed4'
~~~

### V5 054 · v5_seed_completion/single/load700/swarm/seed0

原失败 SHA256：b3519865b9d7fedbb374f7649bc85bb9cf0f032012a2b35d1a7a3796cb0e2e48；最后重放失败 SHA256：05e54c4ed82c55b14b68c6c68992c879dc58c2d5420201afaff720e6fda42094。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/swarm/seed0' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load700/swarm/seed0'
~~~

### V5 055 · v5_seed_completion/single/load700/swarm/seed1

原失败 SHA256：f19b80be8e7fa75f2142e33723d030d6f9e1d384b4d4f4d68d47461862805347；最后重放失败 SHA256：04a6ef301fc8ac509a7b6609740c389fd1558ea8831ad63fe5da6992c074643f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/swarm/seed1' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load700/swarm/seed1'
~~~

### V5 056 · v5_seed_completion/single/load700/swarm/seed2

原失败 SHA256：40de5ead84f4a53c4e18bd2806eca90a3998a58fdb02dc4319fa69048be0e6ee；最后重放失败 SHA256：21e68e3da79a8ee2f8354303a6f696a09d5dda21a5f5174bb9f67bb9e7be3afe。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/swarm/seed2' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load700/swarm/seed2'
~~~

### V5 057 · v5_seed_completion/single/load700/swarm/seed3

原失败 SHA256：c17fd303601badc3cc9233e095671445f5ab69c378da12d3af8e54b9da5c0bd9；最后重放失败 SHA256：7f60ce44ca9d8b4e6faa28c6324856053bde2e889d96e8a5ca4a070ccafeade7。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/swarm/seed3' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load700/swarm/seed3'
~~~

### V5 058 · v5_seed_completion/single/load700/swarm/seed4

原失败 SHA256：7413990f1239fa47c66d7b9f752516e7d4f4f6749f5d19048ed4e4919ebb7aac；最后重放失败 SHA256：4d0095a3f1149c0ce31e7c96c109f02fd0f45c0ac671fc8e7c5b3afc2a4034d9。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/swarm/seed4' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load700/swarm/seed4'
~~~

### V5 059 · v5_seed_completion/single/load900/separate/seed0

原失败 SHA256：95ba39db2784e6ef70352fc63b3cbe305a0f4dd0e4e8980bead6e31f73d0aa71；最后重放失败 SHA256：b52397b281b4bca25bd34d7a9ea0b7f2aa1389099fb7ac9dd8704e7c35d5a237。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/separate/seed0' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load900/separate/seed0'
~~~

### V5 060 · v5_seed_completion/single/load900/separate/seed1

原失败 SHA256：1995a8e843162169695cc5c68d79c6d2be21a88fb8e2fa98654681696dbb37bb；最后重放失败 SHA256：9283b7d207284a6045227271c0f5fe97112d0160f45d507d0bfdecca69c0322b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/separate/seed1' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load900/separate/seed1'
~~~

### V5 061 · v5_seed_completion/single/load900/separate/seed2

原失败 SHA256：a113bb302c97b1eecba170bcc32ef2ea2b9ab680c11de5f6f5458e2bf26f9c70；最后重放失败 SHA256：9c23c52f3a9592f3b255f107b6f50ee74547f23a78b5ccfdd8b51d2144e69d76。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/separate/seed2' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load900/separate/seed2'
~~~

### V5 062 · v5_seed_completion/single/load900/separate/seed3

原失败 SHA256：01c60cea667fad692abeaadb65069c210e8d3fb1550da2986f5a3d9e38077430；最后重放失败 SHA256：64e4e8cee287f1ecf8bb66323acbc81628422b444b6520550fcffa2b8f0c30bd。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/separate/seed3' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load900/separate/seed3'
~~~

### V5 063 · v5_seed_completion/single/load900/separate/seed4

原失败 SHA256：1b5e4d226428619b9cb35dcf98fb99d48c229e098cc635cf631953060a669000；最后重放失败 SHA256：a81c70f214cbab18efc8236f5a2636f66a94b5222eaa8a0fa3455e47272dd780。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/separate/seed4' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load900/separate/seed4'
~~~

### V5 064 · v5_seed_completion/single/load900/swarm/seed0

原失败 SHA256：a5eba36978d1a5734a79a80b9fc6880e1df1f2337bc199b25829960121736737；最后重放失败 SHA256：64b8c610119642ad2873c65f6fb790b877deb8cae30c73a920a351d0865ef722。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/swarm/seed0' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load900/swarm/seed0'
~~~

### V5 065 · v5_seed_completion/single/load900/swarm/seed1

原失败 SHA256：babe3ec4be5f258aed3c6a210036c707f42d0723dddde6f0ff9e539d57dca136；最后重放失败 SHA256：2945f38135188c8bbfc80fb633601df6c85339901b2213196196604883bc51a6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/swarm/seed1' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load900/swarm/seed1'
~~~

### V5 066 · v5_seed_completion/single/load900/swarm/seed2

原失败 SHA256：4f0b622c58ce0b45d36a8f44e7201d442c446e47e1e479b003df61fb77a8fe20；最后重放失败 SHA256：1cc02407d683d862a4ff50978f097d7eba17498a8cc3577ec875fc2d48a1a405。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/swarm/seed2' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load900/swarm/seed2'
~~~

### V5 067 · v5_seed_completion/single/load900/swarm/seed3

原失败 SHA256：fd929c8616bd562b504c2d2846c4ceb56356f805bd1ee3f9a7b46a0bd2901403；最后重放失败 SHA256：14e4335bfce62e54c25092870ec7f0e131d729386c7263df7a6229bb028482ff。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/swarm/seed3' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load900/swarm/seed3'
~~~

### V5 068 · v5_seed_completion/single/load900/swarm/seed4

原失败 SHA256：be7ad4be42f13e990e070c1381924cc8e70cf562e0be67043d3ae19fc06307d1；最后重放失败 SHA256：a12e32a34ddc6bef6a8da66c4ace371e60d50e2b7048bf4abeaf6ab35f622532。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/swarm/seed4' --output 'experiments/manual_reruns/V5/v5_seed_completion/single/load900/swarm/seed4'
~~~

## V6：66 个未解决键

来源：experiments/v6_completion/failure_replay/FINAL_AUDIT.json。

### V6 001 · generalization/multi/prompt2/HH/seed0

原失败 SHA256：0429bc34971313499a8b97e8622476c040a61b2ed4cde9854504d43c92d787e5；最后重放失败 SHA256：071cd5e5814ca6772c43c1d3f07840c624830863015f22417995e01d08c3bd6b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HH/seed0' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/HH/seed0'
~~~

### V6 002 · generalization/multi/prompt2/HH/seed1

原失败 SHA256：7ebc28508c99728a808520739028e4d1aff657182652b016fde5c01f9af090cc；最后重放失败 SHA256：94055558f336cca0a5c9f90ed7128d88790b38fb00c3d3df7e47fd034dae7869。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HH/seed1' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/HH/seed1'
~~~

### V6 003 · generalization/multi/prompt2/HH/seed2

原失败 SHA256：8425e056aa7ac2eb3ee9bc53bee5ef322dacade9f0d49a6fe49bd36b4ee1482a；最后重放失败 SHA256：e6eb5b19980c94a9e68de9ea7bc891ec0f1b6d77aa113ab293e945f454bd5d65。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HH/seed2' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/HH/seed2'
~~~

### V6 004 · generalization/multi/prompt2/HH/seed3

原失败 SHA256：00ae15fc7bf0ee91b51002713fb396cceb66a082eb977d427851a6ea4894ef86；最后重放失败 SHA256：2ce700a8abbbf2c9942bfe244c65e73bfa856e019401a425633d4dfde7534ba1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HH/seed3' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/HH/seed3'
~~~

### V6 005 · generalization/multi/prompt2/HH/seed4

原失败 SHA256：8620f63154658b370f1ed9652b7c5b2881a2881a10e3bfacc878eebdd03e7988；最后重放失败 SHA256：50bbb74dd82dbffb529eb7d5e46fe8ea3fa239992819fbc9eabb50f7c1afdce4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HH/seed4' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/HH/seed4'
~~~

### V6 006 · generalization/multi/prompt2/HHplus/seed0

原失败 SHA256：c140cf6dfb17a171e4350e5d3aad927a23323f017f014e8e96bc9b42d7469418；最后重放失败 SHA256：b85262f63045e710bc4733426a6ff5e3a59a87809fc3a81dbe1a05744572092a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HHplus/seed0' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/HHplus/seed0'
~~~

### V6 007 · generalization/multi/prompt2/HHplus/seed1

原失败 SHA256：3613cf105fc591ca937a220a77c3e0a27f36e52b1f70d153c84ae0775b9fe538；最后重放失败 SHA256：059a3203ae6b1856e848b265bb6228f950e3cf20bf367f47f222b46c6e91c96a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HHplus/seed1' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/HHplus/seed1'
~~~

### V6 008 · generalization/multi/prompt2/HHplus/seed2

原失败 SHA256：d7f7a8e1262926becadafdb0546fa45dee3b5d118366aeae90699b78598e6eb9；最后重放失败 SHA256：7891f170ba41c5c9320861db008dcfa2162523d30050fe3f02c5cc29e5ee35a3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HHplus/seed2' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/HHplus/seed2'
~~~

### V6 009 · generalization/multi/prompt2/HHplus/seed3

原失败 SHA256：75bddaa979308d9e7c7ed26da463b7c4007e82adec891895ca0f814ce65d18ac；最后重放失败 SHA256：86d4c63a55be3d6d15e2cd3dcd4e1431f8161484322258c2b5ddb7be4c8cba27。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HHplus/seed3' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/HHplus/seed3'
~~~

### V6 010 · generalization/multi/prompt2/HHplus/seed4

原失败 SHA256：26a4cdfd8a3104717e3c6ec4864752f1b5efa31610957bf38cbf5b786a7ba49e；最后重放失败 SHA256：2b0dcddbdd8fcb75c4cc9d5abf643dba6b63b1ea9e3f4147a61ca051d9516cc0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HHplus/seed4' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/HHplus/seed4'
~~~

### V6 011 · generalization/multi/prompt2/V4/seed0

原失败 SHA256：20377109b161ce0b5b13187cccb33cecc7e5d7ae090693a452dfc56e35d57e96；最后重放失败 SHA256：ff7492190fd0bd814e44fe9aec46dcf44fe7cc59a448a316b2e8132798b86f69。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/V4/seed0' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/V4/seed0'
~~~

### V6 012 · generalization/multi/prompt2/V4/seed1

原失败 SHA256：32dd93ea8bbed3e3717c2b402df6c8aea93b7c625a95341d439ae966e24a46b8；最后重放失败 SHA256：8ed2277dd6410e307afc4534026aef10148a722d3b7e8d4692a1b634f4cd0a2d。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/V4/seed1' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/V4/seed1'
~~~

### V6 013 · generalization/multi/prompt2/V4/seed2

原失败 SHA256：687b567611bf7c77538bbbe61967c9c436b22883a9b0b0fd599f91f5a09bdada；最后重放失败 SHA256：9acccc47aab8f07dbf060f9b2b7b7bbfc5226eea9a3a1ed9cc123026e4d8d847。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/V4/seed2' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/V4/seed2'
~~~

### V6 014 · generalization/multi/prompt2/V4/seed3

原失败 SHA256：3d51c72a14b73bca345468645c4df33aeeabadc6a26974b75c5d8432b88a4264；最后重放失败 SHA256：f5138a5914a73b49fdba91523d78f132ee0e316919eef8289f3b3d05c98a97e2。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/V4/seed3' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/V4/seed3'
~~~

### V6 015 · generalization/multi/prompt2/V4/seed4

原失败 SHA256：315c6d6c4476dcbdb1022d015c294847fa9b86025ac6f1eec0920eab0642a50c；最后重放失败 SHA256：58966c081aaeb261ce27d9c603fbe928bab63357bfa5ce44af8652b167c764bc。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/V4/seed4' --output 'experiments/manual_reruns/V6/generalization/multi/prompt2/V4/seed4'
~~~

### V6 016 · generalization/multi/prompt4/HH/seed0

原失败 SHA256：e314f3198b50aaa129256cb6d4af219d1323d5e32adc3f59f1128940889848fe；最后重放失败 SHA256：e3f13862f4660ee3d78d86d682c83d651ecb0889a48b4ecc7eea8f4970e01c5f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HH/seed0' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/HH/seed0'
~~~

### V6 017 · generalization/multi/prompt4/HH/seed1

原失败 SHA256：7db75ef373e21eb5f7563055ba83b6b231829f7eb9fc2730aa3d278fa0b6f742；最后重放失败 SHA256：0f25382aa1af104f45c16ebcb972df5a6d8daf6c0e44187a2f734b5983b3c8e4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HH/seed1' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/HH/seed1'
~~~

### V6 018 · generalization/multi/prompt4/HH/seed2

原失败 SHA256：ed5c9780127e4a6bf5c66ed3c222323f03e5101345e3f6ce6a26b8da029effe4；最后重放失败 SHA256：e83241a8bd5dfb42bac9915edaf92b98aab0a17d817f7c44e9bf464233de461f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HH/seed2' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/HH/seed2'
~~~

### V6 019 · generalization/multi/prompt4/HH/seed3

原失败 SHA256：73985b5c315e66f0e0c33a7a60675a98ef8501d541ee23926cc200372af522f0；最后重放失败 SHA256：407adb4cb476812228cfb400eda3983a7ebe68539154f3a81d6cb4d7585de076。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HH/seed3' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/HH/seed3'
~~~

### V6 020 · generalization/multi/prompt4/HH/seed4

原失败 SHA256：fe350a0bf388dbaa0da02dd4ea66aa2410abe6df8ac5d92cd94c2ff2f743c663；最后重放失败 SHA256：e26695503f619234d702958f8172bab08288d0d26952198eaa1d69bda06457a1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HH/seed4' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/HH/seed4'
~~~

### V6 021 · generalization/multi/prompt4/HHplus/seed0

原失败 SHA256：0f68b085f21d678045565f1d08a005ab4df9febe3a66fb949269d03ceef784e0；最后重放失败 SHA256：86367cd421b01fad8d6698e429762daa07677dececac5ef67da29fbb9e46bc61。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HHplus/seed0' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/HHplus/seed0'
~~~

### V6 022 · generalization/multi/prompt4/HHplus/seed1

原失败 SHA256：641bef93791d31ef0244e8e52b370b2064cdfd184f666159e086ac6ae46e2d11；最后重放失败 SHA256：1af714857a8533fbcbe217efbfc3566d675fc765b0b9dd34078f43c23993df83。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HHplus/seed1' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/HHplus/seed1'
~~~

### V6 023 · generalization/multi/prompt4/HHplus/seed2

原失败 SHA256：2f0681c8c933f22c2f3b2c582f063e50ff8380db0e9a838ad4679514775c067b；最后重放失败 SHA256：e7755fa4e82f78a4a8f70fd80adbec8dc88fdcdcf617e43ad198666ebab15e6b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HHplus/seed2' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/HHplus/seed2'
~~~

### V6 024 · generalization/multi/prompt4/HHplus/seed3

原失败 SHA256：ea4a292d83757b76336035db7f914ed3124755d0b327cdcec409d2323c855991；最后重放失败 SHA256：0c022b547e5fdb98dcb00fbc7a478042e9016dcf1da8064a24026ad85f699955。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HHplus/seed3' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/HHplus/seed3'
~~~

### V6 025 · generalization/multi/prompt4/HHplus/seed4

原失败 SHA256：1c47c7a2f0759667b7707c1f01860f52b2df99f368a880534f88791e6bcbd14f；最后重放失败 SHA256：59baf8dc57da9bc21394d8979a17106a6425d5a440791f94239760e1ad0a0898。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HHplus/seed4' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/HHplus/seed4'
~~~

### V6 026 · generalization/multi/prompt4/V4/seed0

原失败 SHA256：41470592b6896b5d00eb667b92a92ccd02208ac322e923af9f0c63274950a318；最后重放失败 SHA256：f0bad9e856308c70da2d41765fe2066b030fa2e10060eb5a9950187be576d133。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/V4/seed0' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/V4/seed0'
~~~

### V6 027 · generalization/multi/prompt4/V4/seed1

原失败 SHA256：ccd741f5c1357c75e997caf5568dfce8a7ce0773f41f4799892ae61ec1dd67fd；最后重放失败 SHA256：9f1f09d994aef002c535543a5c36389a319897a6d3e5fafce1687fffe77b4e6b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/V4/seed1' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/V4/seed1'
~~~

### V6 028 · generalization/multi/prompt4/V4/seed2

原失败 SHA256：46b9289a921799da4c3f1bf0349ed4e5628cfd1eaad14369d9dbb82c42f9ce14；最后重放失败 SHA256：e4ad6ff0662372f20f7305ce570ecce298ddbd76d122f4282a2ee3dfa2619776。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/V4/seed2' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/V4/seed2'
~~~

### V6 029 · generalization/multi/prompt4/V4/seed3

原失败 SHA256：ca4d64d1ec5f9bdeb3bcb8067a2aa554bb3871123a0f101467b4cd3abc6d9049；最后重放失败 SHA256：88b864817073e6343a02a63a0ca4037d9839b62796a3151ee918965aebc34c11。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/V4/seed3' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/V4/seed3'
~~~

### V6 030 · generalization/multi/prompt4/V4/seed4

原失败 SHA256：53bd39612bc831a3e52f62d38474c3869a28dc26245e1f5bde6ae500c866d3b5；最后重放失败 SHA256：ec13398463a1f47e4a142ae748167a1e9af96971fcde59b3bb06deed5e2c4b15。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/V4/seed4' --output 'experiments/manual_reruns/V6/generalization/multi/prompt4/V4/seed4'
~~~

### V6 031 · generalization/single/output2/HH/seed0

原失败 SHA256：9aa352aabd67e95f46c95d7218658edd7bef42ec4fbc016165204c354d9f1ce1；最后重放失败 SHA256：27ae043b43eb7257c4fa51b05ae5cad40ef4f318e6e00a0955c240ed462f1358。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/output2/HH/seed0' --output 'experiments/manual_reruns/V6/generalization/single/output2/HH/seed0'
~~~

### V6 032 · generalization/single/output2/HH/seed1

原失败 SHA256：d4761839536eea2333279278c6e98a59a0d3446b2021386fbd6bfb9fbd7897f3；最后重放失败 SHA256：c79d1a91ef2ed42ac575d3372b903657f555d298214d3122f5ad21b6b504bd50。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/output2/HH/seed1' --output 'experiments/manual_reruns/V6/generalization/single/output2/HH/seed1'
~~~

### V6 033 · generalization/single/output2/HH/seed2

原失败 SHA256：d2738d076a6d90a3e96ac4d80cb64362e996b7bbee35c888c3c6670dc006578d；最后重放失败 SHA256：d9a07d927a67a136232ad5a0a99b6e032650ec87f6eaeda46064390f53149ed4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/output2/HH/seed2' --output 'experiments/manual_reruns/V6/generalization/single/output2/HH/seed2'
~~~

### V6 034 · generalization/single/output2/HH/seed3

原失败 SHA256：3cf46840d8426793132d75e624b96a2a4d74575fb69017f4afa7f82f946448f6；最后重放失败 SHA256：f897fa2ce965e46f8803082eeacbebbe4a20610277118df428efa050837eb4aa。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/output2/HH/seed3' --output 'experiments/manual_reruns/V6/generalization/single/output2/HH/seed3'
~~~

### V6 035 · generalization/single/output2/HH/seed4

原失败 SHA256：0c0752e296e9d8a88581d9d604a0dbf27fcdbc89777a12d770b6609fd30fa4d0；最后重放失败 SHA256：8e342893242f18be0b77a43cd3a28072d6452c70699d233269cb5330f28dd99b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/output2/HH/seed4' --output 'experiments/manual_reruns/V6/generalization/single/output2/HH/seed4'
~~~

### V6 036 · generalization/single/prompt2/HH/seed0

原失败 SHA256：eeab340ef17a79c7a1460585c4d21311161e42baa6c55f6325add879d156cf2e；最后重放失败 SHA256：d3c17ecae8e8cdaa9eedf404ee05e353fc754707f241c000eee48bd4f5cf9e8e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HH/seed0' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/HH/seed0'
~~~

### V6 037 · generalization/single/prompt2/HH/seed1

原失败 SHA256：8f1d1a7120b192520e1f0ca481e6c13cfa0cdc333c840ffb7bf729fa07f1088b；最后重放失败 SHA256：0847e19a0c25a0d828d8d8d4338a967938c3fa2983eebdcd6b929781d9dc54a2。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HH/seed1' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/HH/seed1'
~~~

### V6 038 · generalization/single/prompt2/HH/seed2

原失败 SHA256：a1614b72e4d3c714df49f4587e7b3216d9e449d082dfb1d1c5c1c8af93dbda8b；最后重放失败 SHA256：14a50a1b6268571a2ccf4fa1a87629bf10cb9249bcec3618e4ddb3c130a47b37。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HH/seed2' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/HH/seed2'
~~~

### V6 039 · generalization/single/prompt2/HH/seed3

原失败 SHA256：d28b1fd2f7271cd6f95e4b0d86e14a28ad79c7c178f2fb64829ec1ecc2f769f4；最后重放失败 SHA256：ceba2d89f0d26bcff4025624cefc34639a2094efc21625f1a433114973b89ab4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HH/seed3' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/HH/seed3'
~~~

### V6 040 · generalization/single/prompt2/HH/seed4

原失败 SHA256：46f8953420496bff99f88517e10936d1e54618056a1720b2a47a81a3892c7ecf；最后重放失败 SHA256：ed75dd510e0fc948fefadedbe94a3d6910191aac569dc5a0def73f2a9c976db9。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HH/seed4' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/HH/seed4'
~~~

### V6 041 · generalization/single/prompt2/HHplus/seed0

原失败 SHA256：68c75bdafd038b2d78d1a06874573502efba77b07a727ff203f0ba057cea4c59；最后重放失败 SHA256：affe298e20743701dd6b1a231e1ef2686e43116831451a1aab4c62f4d14709b4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HHplus/seed0' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/HHplus/seed0'
~~~

### V6 042 · generalization/single/prompt2/HHplus/seed1

原失败 SHA256：76f9bd857a52c69058b9255ce7826d5a15adf34b15e8fd03ff7c24632abecdcc；最后重放失败 SHA256：7d436aa81095b9e5e20efd3aad4a4190273f7505dc3a158a125d966eb0762f68。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HHplus/seed1' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/HHplus/seed1'
~~~

### V6 043 · generalization/single/prompt2/HHplus/seed2

原失败 SHA256：b32f13fd7b3c6a6172ea1beb6606671043d74a54df9b96df31a4e48135aadc94；最后重放失败 SHA256：d55468749add9720c3cdf50e2d5c70d65702c64e64b105bfe72e90cee535b86a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HHplus/seed2' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/HHplus/seed2'
~~~

### V6 044 · generalization/single/prompt2/HHplus/seed3

原失败 SHA256：bde248f705682b98db8183191a00077ff068a91812c1ace4b1a4bf7c7570dba1；最后重放失败 SHA256：ee663ec3262b1495b6ebe7f7f88436e77022cafa794b2533a0cfccc3eb4572bc。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HHplus/seed3' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/HHplus/seed3'
~~~

### V6 045 · generalization/single/prompt2/HHplus/seed4

原失败 SHA256：88f49c23862f713e4d84849582316e4d4f54e4bfb7a8fa04031a55cbef7b9c5e；最后重放失败 SHA256：d745ad9947c127f950bf703ff672a722fb9df3b7d141a845b6f2b92dd438b3c4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HHplus/seed4' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/HHplus/seed4'
~~~

### V6 046 · generalization/single/prompt2/V4/seed0

原失败 SHA256：fafb91812da6b43a463faf1909949e7ef26a3626f66f5fbaf7e8322232b3c8bd；最后重放失败 SHA256：c1e4498d621ca396cbfc1226664784186637074ba5eb206122684d4d7399805f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/V4/seed0' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/V4/seed0'
~~~

### V6 047 · generalization/single/prompt2/V4/seed1

原失败 SHA256：528fb27e4e4ef6e592a8725218e28b40b7bdb10995e62feb16952bcfe93ba0fb；最后重放失败 SHA256：b8a559eb0de9b56ccbad9ac0dd63b81e039e8f36ccc426806c6d7905d1d5f931。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/V4/seed1' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/V4/seed1'
~~~

### V6 048 · generalization/single/prompt2/V4/seed2

原失败 SHA256：bec26e09234eaaa495225f4e899afa6dc4100030b88288ce61720c76994ea07b；最后重放失败 SHA256：498a82f1901999ed720f350c85d48aae36aa82a75841b26699628660c5336af8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/V4/seed2' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/V4/seed2'
~~~

### V6 049 · generalization/single/prompt2/V4/seed3

原失败 SHA256：ddd0857b9779d3970e2eef64d439a2ad161ea666c2209ceb27c6c6e63eb1d2ec；最后重放失败 SHA256：bf82a44f14decac03eabb6366144b4d42f8b3bc4019280957889269f6d3bff9a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/V4/seed3' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/V4/seed3'
~~~

### V6 050 · generalization/single/prompt2/V4/seed4

原失败 SHA256：40923a4fdcbf2f89ce28d9638d0d82a24291000053873d634fa99b3b712eb33c；最后重放失败 SHA256：5d76af3a55c30f4e012a00b9872fc8f16d52dc85bfef3587ccbdbb45c0ee6e54。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/V4/seed4' --output 'experiments/manual_reruns/V6/generalization/single/prompt2/V4/seed4'
~~~

### V6 051 · generalization/single/prompt4/HH/seed0

原失败 SHA256：2041bfa97a33e9dbfe77cc11baa6f2a5aa279e779cf6eeaa3ae1eb2b91282feb；最后重放失败 SHA256：b8335504efd521d2b64a862e672284f59b826ce40552e5749f8e86ec2645fec3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HH/seed0' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/HH/seed0'
~~~

### V6 052 · generalization/single/prompt4/HH/seed1

原失败 SHA256：6e4d379a3826bfe026a88eff85d43d1440c22963bcb99e522b38cec1569cbc25；最后重放失败 SHA256：d31991400578a7cea2a577b13da9f74cfdba32adb5bcadad46dfeac8611076c8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HH/seed1' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/HH/seed1'
~~~

### V6 053 · generalization/single/prompt4/HH/seed2

原失败 SHA256：ceef65511ebf1dcbc383bfd4b589328e3e2d43767c264a619a4a84d871606ed3；最后重放失败 SHA256：106f19d9dcb4451af10d83e422459da5910ec3a819f172dc5e758be0535a904c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HH/seed2' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/HH/seed2'
~~~

### V6 054 · generalization/single/prompt4/HH/seed3

原失败 SHA256：18c126909d34179b6ca89316d7912bd3ad526a0f0831ab5f38a90a6f76aff0ea；最后重放失败 SHA256：b6ec8d4a076927a19e00a7edcc63486124ca586db69b840b119caae398d6e81a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HH/seed3' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/HH/seed3'
~~~

### V6 055 · generalization/single/prompt4/HH/seed4

原失败 SHA256：b30a396972279d601e8fd26dad11436f4d6282a1f7691c2f00b3a5ab539a7287；最后重放失败 SHA256：0ba1de0aa27305a3ebed8d6f156654b029debb0bcfc10470e6b284f6c7c5d163。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HH/seed4' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/HH/seed4'
~~~

### V6 056 · generalization/single/prompt4/HHplus/seed0

原失败 SHA256：cd60888a84f40a98fab4f2bde17a91be5eb1ac74d405337ec74555b43640a45e；最后重放失败 SHA256：fd3dd86e645667a7c9c56c9ad7e1e5c3fb9ce44943cf8439b561bef50bab617c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HHplus/seed0' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/HHplus/seed0'
~~~

### V6 057 · generalization/single/prompt4/HHplus/seed1

原失败 SHA256：dab9bc2f99b8d1eb426163be61ae71f4680704d8e28459091303a32184d10547；最后重放失败 SHA256：3091d9f3a8280906bbc62ca1acdd41894b08681045df44dbbae03d67eaa2aede。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HHplus/seed1' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/HHplus/seed1'
~~~

### V6 058 · generalization/single/prompt4/HHplus/seed2

原失败 SHA256：f2b3349990ac28c9de71017d7a376b9a09d76dad6fb32995b56bc9dcbcc8c86d；最后重放失败 SHA256：0b800a1ac8f039e56398f59373b717e082b8bc2138880f48a0af08978605efab。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HHplus/seed2' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/HHplus/seed2'
~~~

### V6 059 · generalization/single/prompt4/HHplus/seed3

原失败 SHA256：5108eb2a296524e80d708b0955b609f9d126f34c6c2e01ad9544aed47c569b15；最后重放失败 SHA256：72e4ce80855a65b2ca42345f25f19fe5b44efe2b4ebb6b4f433697c7962eff40。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HHplus/seed3' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/HHplus/seed3'
~~~

### V6 060 · generalization/single/prompt4/HHplus/seed4

原失败 SHA256：7c4454f0fc22de018c782851e7b9d497fd7a66983c71fb9d44bdc2c03d84b38a；最后重放失败 SHA256：268a460edba552c6a07bc35d3171e9bfe5dd30822f09a1a863de9825d707286e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HHplus/seed4' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/HHplus/seed4'
~~~

### V6 061 · generalization/single/prompt4/V4/seed0

原失败 SHA256：292739139c7fb7f2c6a995445a15a6ab8d2ce61690dad66b2165a62296203e77；最后重放失败 SHA256：9abcd3e616b6b4949682b28c762a20f6ea1c01ca9fea8d0fef30462572081c06。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/V4/seed0' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/V4/seed0'
~~~

### V6 062 · generalization/single/prompt4/V4/seed1

原失败 SHA256：8c019cbeecf06d7666ec2d046f4a19b79a637d85e3da96b4926a39354c2c02f8；最后重放失败 SHA256：47699f2624d40c94db56f417fe3d85d3e85e8e819d671ef16885cdf302475d02。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/V4/seed1' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/V4/seed1'
~~~

### V6 063 · generalization/single/prompt4/V4/seed2

原失败 SHA256：4ba8db17959765b1eb15368e93de61d9f072888061f9aec944551ef975401bae；最后重放失败 SHA256：25dc5355a981db936d9e4a65409963d0f5cd77b5d54a41767c6831bb87a5c7f6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/V4/seed2' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/V4/seed2'
~~~

### V6 064 · generalization/single/prompt4/V4/seed3

原失败 SHA256：42027d3fe73ce981c95efcc1e80b40026216e52edb95c51f63342dfd37e1b874；最后重放失败 SHA256：998bb8f6cdf66af97d0b2da684cbf24d30cefe0b113b305c96f50280b82459e3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/V4/seed3' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/V4/seed3'
~~~

### V6 065 · generalization/single/prompt4/V4/seed4

原失败 SHA256：b35a4c0e232967cd2d44df239a299dd626b8a031ba857ad27c8c4162f4b767eb；最后重放失败 SHA256：2646552cfd5d6dc37750176db78aaa9a1e96268556ee1a66ed5ac2baf4cc417e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/V4/seed4' --output 'experiments/manual_reruns/V6/generalization/single/prompt4/V4/seed4'
~~~

### V6 066 · robustness/multi/activation_kv_high20/HHplus/seed4

原失败 SHA256：da9cdc7472a41afa67b7ea3bf560b7b7423495e11fdbae13873d349838f1efe7；最后重放失败 SHA256：325f280bcce16773b367dfd993cc3bdc737a34d8e3c151b099ef79ab97cb50b8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'robustness/multi/activation_kv_high20/HHplus/seed4' --output 'experiments/manual_reruns/V6/robustness/multi/activation_kv_high20/HHplus/seed4'
~~~

