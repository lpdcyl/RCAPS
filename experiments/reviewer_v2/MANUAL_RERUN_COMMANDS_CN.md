# RCAPS 剩余失败键手工独立重跑命令

共 236 键：E2b 5；E3b 12；E5a 39；E5b 42；V5 68；V6 66；E6 4。

254 键独立重跑已审计：22 成功、232 失败。以下仅列本轮后仍失败的键；原正式结果与先前重放均保留。
E6 原正式失败 13 键，独立重放成功 9、仍失败 4。各段均从项目根目录执行、真正激活 conda gllm，并写入新的独立输出目录。
已有输出目录会拒绝覆盖；若需再试，请保留原件并指定另一新目录。重跑成功不能替换原正式失败。
结果见各输出目录的 index.json、worker.log、result.json 或 failure.json。
E5b 原 formal 冒烟门槛未达，因此其命令只针对预登记的修订边界诊断。

## E4：WSL2 网络微基准

150 次测量已审计：149 成功、1 次启动后中断，原件位于 E4_tcp_wsl/runs/12p5MBps/priority/repeat0；不属于上述 Windows gllm 键。
该中断键已在独立目录 E4_tcp_wsl/interrupted_replay_20261101 复测成功，原失败和原批 149/150 口径保持不变。
E4 独立补测不属于下面 Windows gllm 失败键。

## E2b：5 个未解决键

来源：experiments/reviewer_v2/E2b_parallax/failure_replay_round2/FINAL_AUDIT.json。

### E2b 001 · multi/load320/shared/seed4

原失败 SHA256：adc6c2c6b23e64bacc8a93020c8cc5e3a0fa45544b344fceac5871a0d4ba5f92；先前重放失败 SHA256：af9468941fd1b1761a16bd569b68cab99ae0182ef5cd39e08aba78051956f5ca；本轮独立重跑失败 SHA256：d30cb4e9f3f4fe4bd7c2aedc13c9d07b277a48c0d1f4ade424f2e974ccbfd244。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E2b' --key 'multi/load320/shared/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E2b/multi/load320/shared/seed4'
~~~

### E2b 002 · single/load700/fifo/seed0

原失败 SHA256：4e563c2a5edcf83944411ee86be723e6f79b83853a08d724378aa149e2af3362；先前重放失败 SHA256：aa9bbed7e2f8fc94ca94002d50150ddca4700c3a2161fe7ac3b1f05998db4274；本轮独立重跑失败 SHA256：e88634c75eb9b755a685aaef8231d3d36ab5e010d306d8c79439b8a7894c2660。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E2b' --key 'single/load700/fifo/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E2b/single/load700/fifo/seed0'
~~~

### E2b 003 · single/load700/fifo/seed1

原失败 SHA256：af6de9be94a91e5986d28e86f4c6c56e03e663687e7f49a6844bec6711853bf1；先前重放失败 SHA256：900aeff739c3cb63bc5f27af9e3fb4a05ba689a882e5496e684edc78c89ff3d4；本轮独立重跑失败 SHA256：97e12daa0248b82fbadc7408a11f7aa083c573663d1715130910aa790c53be78。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E2b' --key 'single/load700/fifo/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E2b/single/load700/fifo/seed1'
~~~

### E2b 004 · single/load700/fifo/seed4

原失败 SHA256：465c8d8e71a1ac6df4542c634cd7ef812c3d6bf50a2ac2ca0845c3a086490d43；先前重放失败 SHA256：f07ea8f06721bed2d2a89bcdb8dfec29d6f152a1a6db30532944a38f17500eb8；本轮独立重跑失败 SHA256：822fee0e05733186cfe5f6e26813bfdf39c7992ada68f93277d550982778c7fe。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E2b' --key 'single/load700/fifo/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E2b/single/load700/fifo/seed4'
~~~

### E2b 005 · single/load700/shared/seed4

原失败 SHA256：2da70fafdbaf12ca0847bd1932141717a67a78649656d003cfca2c5bba1eef0a；先前重放失败 SHA256：9d2559b3de928ff0419da3f0e52a6bda24d4d9d46af3729de9e2637e85d79f0f；本轮独立重跑失败 SHA256：99ace534ae3d519980974c52f71cc115b571c9b5710212061005e82f7542acf7。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E2b' --key 'single/load700/shared/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E2b/single/load700/shared/seed4'
~~~

## E3b：12 个未解决键

来源：experiments/reviewer_v2/E3b_goodput/FINAL_AUDIT.json。

### E3b 001 · multi/400/Helix+/seed0

原失败 SHA256：5a0b38d8bac42b4394923c143d71baf59905da76fed6f59f03e52bd73c02de4b；先前重放失败 SHA256：0ea3d2795f9ecfd784e08802f91e5f9b2ed5a90d42ae72d2bd108191eb4c50eb；本轮独立重跑失败 SHA256：3014e0c479e12be0a2e43bc67d7734931d048cbc075d0da8f7405a66e3e066b3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix+/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E3b/multi/400/Helix+/seed0'
~~~

### E3b 002 · multi/400/Helix+/seed1

原失败 SHA256：eacafddd9c2b704e1d823bbda115948a3772b1278215cc50c7b1385c751fb05f；先前重放失败 SHA256：d1f71cbf6dedef0b9def0e63199419b9880012c54b4fa4168eeee3a9f6ce890f；本轮独立重跑失败 SHA256：aff24825353b14bc69c7edd4c1bb49b406d55a66c7d342720c7ecf3b764080fd。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix+/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E3b/multi/400/Helix+/seed1'
~~~

### E3b 003 · multi/400/Helix+/seed2

原失败 SHA256：9328afc49345e923f80f78cf9d23806b0e94fd879ab04cd06144a5fad0572ea6；先前重放失败 SHA256：c12cae6d70c15b15ae19777ee9b1084b652bcd62d33880dcff25c8c29638a660；本轮独立重跑失败 SHA256：e6e7006027dbf796c02d5efef9aadc88d1a29ffb6dcf06fb72458091d97827b2。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix+/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E3b/multi/400/Helix+/seed2'
~~~

### E3b 004 · multi/400/Helix+/seed3

原失败 SHA256：c3b2afdb2046aff11ec9edd474f3e97a7df3f3c296323507add4b6d54ea43fa6；先前重放失败 SHA256：67be84ed013dc4231fd77f357a26ecdc9ec1ae72ec6c47d1fd1006495769feac；本轮独立重跑失败 SHA256：27b815eba5bde2fcb4ae031db511af5a64ae172ff31560fe3514a4d5386ef214。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix+/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E3b/multi/400/Helix+/seed3'
~~~

### E3b 005 · multi/400/Helix+/seed4

原失败 SHA256：bb0c5618905297fa92a04f828db2aabc64b393d21541260e94211366fa16a155；先前重放失败 SHA256：1a17d9422b931608b93be2721eea4214edb2fc86289a0b1ca98643782dbee7a3；本轮独立重跑失败 SHA256：026a7c91cb4e1064a95ab1c9a6d798e72bc4650a9d3636f0e6af184d9f8acfde。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix+/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E3b/multi/400/Helix+/seed4'
~~~

### E3b 006 · multi/400/Helix-tuned/seed0

原失败 SHA256：efdbb2f000c5dbb10f90bd1e33f3e8efbbf0583a8c2ed9bf10ed80092c409d74；先前重放失败 SHA256：dbf4c403bc2b71cc2980499285233347845f0765e273cc9584a5fbc36b2fb0b6；本轮独立重跑失败 SHA256：9d3f7d0a3a08c5137b3e113eed748756d3d2e33760e4e80fc2cab8e6b1bf6605。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix-tuned/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E3b/multi/400/Helix-tuned/seed0'
~~~

### E3b 007 · multi/400/Helix-tuned/seed3

原失败 SHA256：82c73d386123e44ba5b3f7532c20da7f9d1d4bacbc2cabc13a645c04899e2774；先前重放失败 SHA256：8a176c5756a776adc4278d2ab8ccce7e4ea0de5f5b03b31a6b42c276e9d454b5；本轮独立重跑失败 SHA256：6f9c3f654f4d001d184ed56c3e5b08b233407da7f5f097961b4008038c2df06b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix-tuned/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E3b/multi/400/Helix-tuned/seed3'
~~~

### E3b 008 · multi/400/Helix-tuned/seed4

原失败 SHA256：fd19f1c79f1865315dc047ae262f2ba08e506312fb1d545ca313d58e6c5fb177；先前重放失败 SHA256：f22ee290db74fda4617e56156a7e4e2d9650878b7fd01a9500be5b6c7edf2f91；本轮独立重跑失败 SHA256：03ca8a5cab495ea71ab2b76aea533aed7b2c34da0e4d3a7794c3208aac739e5f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix-tuned/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E3b/multi/400/Helix-tuned/seed4'
~~~

### E3b 009 · multi/400/Helix/seed0

原失败 SHA256：e6f70e680e40511618e52caa24f33728ecb397856ec061fce43223e40eb70cab；先前重放失败 SHA256：56c1e8a4ee7af169d677f4691c02b60968a3a2b77e65fa6568dc6b4992462c55；本轮独立重跑失败 SHA256：8db3b8171342f9f718c90af52da45a26f653d88f2baf0496d45a85e95787977c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E3b/multi/400/Helix/seed0'
~~~

### E3b 010 · multi/400/Helix/seed1

原失败 SHA256：7279dc0afc097610f9f085c3bc7a4f9314d110e13ddb9efe1e22a198d2a195a2；先前重放失败 SHA256：f6f809eb654c1ec5e19522741f963cabc5aea8b787a41169fafe22c0a909a7fb；本轮独立重跑失败 SHA256：2f0491e2d75470b39727826d895d67c6122c7fd34cbdc3debeda7d8c8ff850fa。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E3b/multi/400/Helix/seed1'
~~~

### E3b 011 · multi/400/Helix/seed3

原失败 SHA256：7e83aefdd96ca8781dd02816deef6d40b5edfe8a06b854c31658380b1b127330；先前重放失败 SHA256：3bee8171f082b142555e8ea59fe4c2a93e523eb8c159863312fee80553e3ee48；本轮独立重跑失败 SHA256：47bf8f95a768c8b266d6cd06056487a9f9367a1646b1a2bbcea38ff71f22a814。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E3b/multi/400/Helix/seed3'
~~~

### E3b 012 · multi/400/Helix/seed4

原失败 SHA256：34668a4d62ecbe93528bcfdfe8ca24f7545c6ebcddb19d99e72c7dd0492b39a7；先前重放失败 SHA256：3b78a0f939fbeff4687d3f0e4c073bfc3821f64ff67282740e125255c56dfa86；本轮独立重跑失败 SHA256：7ee7f17876fb70a25517eb8ff096980485c95433544f1c77d830418a554464fa。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E3b' --key 'multi/400/Helix/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E3b/multi/400/Helix/seed4'
~~~

## E5a：39 个未解决键

来源：experiments/reviewer_v2/E5_scale_kv/E5a_failure_replay/FINAL_AUDIT.json。

### E5a 001 · E5a/load1450/Helix+/seed1

原失败 SHA256：1f8edb1274a070bd05de9a4c2fb23d785257d660a42b9d51e32a9d3f41bcdfeb；先前重放失败 SHA256：4d0e71ec5c5b60001047da328d6d1dcaa182b7bd9caacc272bba483965a95e40；本轮独立重跑失败 SHA256：a095c81f13b4cbc9811894eb662504a986c529c2580cc340b981db064f922053。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix+/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1450/Helix+/seed1'
~~~

### E5a 002 · E5a/load1450/Helix+/seed2

原失败 SHA256：52e7ae62e3b9c22ed281ca54fc5ba15fdb52e9b8066791706cf462067eef9acf；先前重放失败 SHA256：84954a66c70ad7dcb4ece128c3038327558cb2bd5420292c512528bc8fd7fc35；本轮独立重跑失败 SHA256：a2f3e9f734117875f959b4353f19b32571a1cb146e883b709bde4bb294a9c0bf。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix+/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1450/Helix+/seed2'
~~~

### E5a 003 · E5a/load1450/Helix+/seed3

原失败 SHA256：2bb13e3e6bf4459b150d0d50495a13b8ea3adbfcc2a0f9a5fa07c6f560d7b313；先前重放失败 SHA256：062c6fa08bf91b67fe34cc601dea54fc1a982bcd6eac6babd1b3fac578e49919；本轮独立重跑失败 SHA256：ffd9dafe04c52115d35b9717fba86540da5fa39d9159c9317882f400aa5c1ac1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix+/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1450/Helix+/seed3'
~~~

### E5a 004 · E5a/load1450/Helix/seed0

原失败 SHA256：cbf743bcaa3f1740114885bc53cf34ccb05ccf745dabb97431e110d75930a291；先前重放失败 SHA256：0ed40a158ef03d58d91d90533f299a41f66e14b74e62f5969651787b1db6d4e2；本轮独立重跑失败 SHA256：c9e04a92b18176f86d6ccc2c12af7dffa07bd1b73684b4fd909256b2d2a1481f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1450/Helix/seed0'
~~~

### E5a 005 · E5a/load1450/Helix/seed1

原失败 SHA256：adf3a2da384777319cee42e71258d0b8d5c17187a334c9b012d0ab0c06d40013；先前重放失败 SHA256：c37d45e4fe2c9279c7bd10b5980b3935b9d6df102140246f1eaca1a477514b5b；本轮独立重跑失败 SHA256：905a3111d01a37940c0f4e2d237463cd74831129c108af576bdc1552d64f0e38。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1450/Helix/seed1'
~~~

### E5a 006 · E5a/load1450/Helix/seed2

原失败 SHA256：342477a8eecd1d89eeda3624e0508ca7d17cd3d237d2ef10905a735b66117c13；先前重放失败 SHA256：0aae9df4eb7cb34b93a51b48eef98601d3b75b9ae2addf3edbadabb7827989e2；本轮独立重跑失败 SHA256：14f0bb7ef2b2c4042268a57d988ea9b79f5230c3d2d3fa8255b94b5813a25a35。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1450/Helix/seed2'
~~~

### E5a 007 · E5a/load1450/Helix/seed3

原失败 SHA256：c5dd5954bad12a9708d248708581626266f53cbd2700bbec03a7f8af38ec0c70；先前重放失败 SHA256：3ce67520868fdca4cc4acb4950db13288b3f5c2df3f42180b69e6e4210f2bf26；本轮独立重跑失败 SHA256：43d0101ecdade2f258a97002554222aabc7913136d09dd4e75680dfa46d39283。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1450/Helix/seed3'
~~~

### E5a 008 · E5a/load1450/Helix/seed4

原失败 SHA256：eaada4a4c5e4636c3f0fe71c845e847801220a6f1cc8b921fa5db705c8704f15；先前重放失败 SHA256：d39cb41e884b4180ae490e9514d903aeb55c6185047e29acf4e259e437ce2311；本轮独立重跑失败 SHA256：68c198fa289f49ec8376ab5d9999f12b88773cebd9a2b91b9cf9a30dedeb10f3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/Helix/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1450/Helix/seed4'
~~~

### E5a 009 · E5a/load1450/RCAPS-KV/seed1

原失败 SHA256：b1b176bd28df09d455aed4a1797ed5ca595fea2b764859d59389c3233fabfbca；先前重放失败 SHA256：21e4313a23810f473c933f5722cc89e689b01b60a3df35dc627854340c07edd6；本轮独立重跑失败 SHA256：045dd9267c12a61fe0b2c3b4e519fec554c233ec7c5ba692ecb49dc67c0e47af。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/RCAPS-KV/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1450/RCAPS-KV/seed1'
~~~

### E5a 010 · E5a/load1450/RCAPS-KV/seed2

原失败 SHA256：ec453c99988830a1cfa2ca3332a0f3ba16ad4ac391c0f88d6cf5b056ea46160b；先前重放失败 SHA256：238836803b2646c5fde99a88fcba4b718c08634a7341c18ed66d4605fabe76d9；本轮独立重跑失败 SHA256：f7ef62a5ff4ba8ccb0bf7c12ee8973aa5ff13ab940437a40d226c5d07a49500a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/RCAPS-KV/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1450/RCAPS-KV/seed2'
~~~

### E5a 011 · E5a/load1450/RCAPS/seed0

原失败 SHA256：38cfefe408eb1eef280860036675dcd5b21003c93104cc09fcb10398555e6df7；先前重放失败 SHA256：e75c1c70d497fa1c1eb03fab6c263c55b25ca7f12b75ab56ffedddf8bca93a47；本轮独立重跑失败 SHA256：6bb25941086f37e2155678ced88a26d9e6acf83e44b4d8868aa8787b058a16cd。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/RCAPS/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1450/RCAPS/seed0'
~~~

### E5a 012 · E5a/load1450/RCAPS/seed2

原失败 SHA256：75c04cda8ce6d9dccb2566143294296e593ed7bbfd725674cf5d57bca3d2a615；先前重放失败 SHA256：764febdebc12f34c96db0a663124d210a17a773fd455baadb874cefca8bc5d5b；本轮独立重跑失败 SHA256：179c67f865fcbb72158726a68432c6ff1f9797e7f6f84467b353bc9c986288b9。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1450/RCAPS/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1450/RCAPS/seed2'
~~~

### E5a 013 · E5a/load1800/Helix+/seed0

原失败 SHA256：cdd54b143d4fa8cc4e2a15b222e440c0b95a688ec559e1b8c581970167db46fe；先前重放失败 SHA256：6d7dde1b5735aafdf271f5bae075e288c4d94f13ce7d5295c877253e98153093；本轮独立重跑失败 SHA256：cd0fb7481f7d39547cb91f75279a9c2b84336d65418947c0ce0b06a2f84edebf。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix+/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/Helix+/seed0'
~~~

### E5a 014 · E5a/load1800/Helix+/seed1

原失败 SHA256：81d819b7b995c66537e93eb3c5494bf0034d24772b67870e1bad54746fed582d；先前重放失败 SHA256：20c9921c200b31b1ca98aa68c9376915ea4562f88782e4115661b18fa185abd1；本轮独立重跑失败 SHA256：990cd2cebe74c6e5a9a65c9bdb44922ff4479e898ee06351bafcaafa04621166。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix+/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/Helix+/seed1'
~~~

### E5a 015 · E5a/load1800/Helix+/seed2

原失败 SHA256：78895b0dfc8e41f993ac757d3204a77a6e73fd4f99984efec8cc700070f80011；先前重放失败 SHA256：8e5147c0a49e3fe678d3d6414ac2f25d4b3dfe1aed48d0b649ee68ccd541018f；本轮独立重跑失败 SHA256：74d39ff53d0209e740b66994ee652be5e60c1dc269e88fd65b93e3e06928aaf0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix+/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/Helix+/seed2'
~~~

### E5a 016 · E5a/load1800/Helix+/seed3

原失败 SHA256：6b5f1438f5ca7f037f621320357c43e597555a257be62c56091109adef799727；先前重放失败 SHA256：c57d321479a4dc21e91ddb2c173dca2c1e1b42567e5e405333d338fbb55d3be7；本轮独立重跑失败 SHA256：30c1a1e5a72b7b03660821c53e60bc7f0bcfc5da2b63a232e8e5d1a40e10496e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix+/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/Helix+/seed3'
~~~

### E5a 017 · E5a/load1800/Helix+/seed4

原失败 SHA256：f539158f22bbaf3e1cab7b76798e58ac777a14c04776a718fea65e35f03dd309；先前重放失败 SHA256：535a36a1825c78397df7216a0bec8a30166903e0fe0b81ef384309282e5e9344；本轮独立重跑失败 SHA256：0522d60c04e37c104075e7082a0167cd3c0f802d83dbaea8071449dd8780466a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix+/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/Helix+/seed4'
~~~

### E5a 018 · E5a/load1800/Helix/seed0

原失败 SHA256：eef8496ddb08c3f2c69ec7958bd5fb499ec0bb9e5c2422ed31a42446e57f8c49；先前重放失败 SHA256：8c492b1f0174612c5d005fecc32c8412922064bd09b821ed869a9b4c3eeb381e；本轮独立重跑失败 SHA256：b3aba615ca7b44a01a7341b9ad7acb4846a6886ab8411a50a0d913875ce5a815。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/Helix/seed0'
~~~

### E5a 019 · E5a/load1800/Helix/seed1

原失败 SHA256：0f1265541991b8584ff9dc18ade84942c94879667145071f7533b02fbf5af896；先前重放失败 SHA256：98ab63405157bec9fd86c6fcdc3160a8093a422cad2e03b0d87c89cd4b2edea2；本轮独立重跑失败 SHA256：bb727319f0fb1cb47ae79d60a5dec3f29d424157e513ebe6b1c06e1c2654945a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/Helix/seed1'
~~~

### E5a 020 · E5a/load1800/Helix/seed2

原失败 SHA256：2a5462e94910679a91dfc75882507eb340674014944edfa84fd4a2875b4bee38；先前重放失败 SHA256：524e6a9e438d4498b1f3c70446d6367448ba7826d21aab3da0f1c7fbb1d1253e；本轮独立重跑失败 SHA256：3f6bd624d2444e0389b3f7f13c41ccb38c86361da6ed75860871f8ee1966b397。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/Helix/seed2'
~~~

### E5a 021 · E5a/load1800/Helix/seed3

原失败 SHA256：5dd88f7d925affb25bcaaa9fce459bbf1d0372146a66f884dbdb2d5fc167d298；先前重放失败 SHA256：96007360b1f0fbde2a5cdb50034a43e29b79f0c675175b4286a16b7a462a3ddb；本轮独立重跑失败 SHA256：cb57dee7faa921ab63e07a62d552afad7151bb680164ae4398ad257c8bb7c3de。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/Helix/seed3'
~~~

### E5a 022 · E5a/load1800/Helix/seed4

原失败 SHA256：f48f544fb3943101a7777577cbb4622dfc5a7527d269c11358dbf93a6e9996ad；先前重放失败 SHA256：df01eca7cc375853b4088d59a705f52e5da9db2c3dcdbc0ed5cc746d22566728；本轮独立重跑失败 SHA256：b6e58a5f33af6f3103441e519b4ddecbe6326aefd59e07a459ac299fe7807ff5。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/Helix/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/Helix/seed4'
~~~

### E5a 023 · E5a/load1800/RCAPS-KV/seed1

原失败 SHA256：884587cccf0b089001d8594c25675614b292302858b27f58cb5f8e268090b2cc；先前重放失败 SHA256：d2aacc29c68959ede083d957e9e6c42e3292af321a098116cf4b708505bef2c4；本轮独立重跑失败 SHA256：4f172562283bbf4b669633a1a58d54ec609e7e87c4d2c0ca6a4eed05b99f54c6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS-KV/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/RCAPS-KV/seed1'
~~~

### E5a 024 · E5a/load1800/RCAPS-KV/seed2

原失败 SHA256：7e86c3bffd341fdf58bc7a4952359e8e36da7df5d57251d916bea6ebf4293df4；先前重放失败 SHA256：9e26c18a9c20007a4ed16fd0c10fadf15161faea411d8cf824bd08d3905940a4；本轮独立重跑失败 SHA256：131a248719fff567c6e19c2989e9008f2753c0c66ac52213fc3da993d8f8825a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS-KV/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/RCAPS-KV/seed2'
~~~

### E5a 025 · E5a/load1800/RCAPS-KV/seed3

原失败 SHA256：157c777320e3febf7b3dec2da0ee81ab554967333c0664bc56c673d64c7953c7；先前重放失败 SHA256：f65292ed95b2693a7e71290c56fd252677e532ab62b19518020f9d472fb2ecdc；本轮独立重跑失败 SHA256：30d962d19f6d702e0166c8caf1f38be1229c1b9631ae3244f2112bf0c4a46bd6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS-KV/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/RCAPS-KV/seed3'
~~~

### E5a 026 · E5a/load1800/RCAPS-KV/seed4

原失败 SHA256：caea868c2b1ee3c60e22197a5600b1f030a58e5ecd59ea5aac0e667d4fa68768；先前重放失败 SHA256：f95e8c6a4febcec04292159c5b39243d63ebfd9bf81233a6cd6eb16c5abc52b7；本轮独立重跑失败 SHA256：692669a9a8cd9089c9c1a8b4609ed36443a7e65d580923ddbf720a212dca7ff1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS-KV/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/RCAPS-KV/seed4'
~~~

### E5a 027 · E5a/load1800/RCAPS/seed0

原失败 SHA256：d2fcc394c153da2e90f8b508bb5a4f2e45102347545a0a44c0906d77f330b536；先前重放失败 SHA256：da77ce3cb26f580fb1ccc17d742e4c56f5359c1e330d5c71f6b10a96fbc436eb；本轮独立重跑失败 SHA256：bb5a7478406b7488b02fc0e77e28ae8efa002095c5ecca52cf24cbd084356dc3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/RCAPS/seed0'
~~~

### E5a 028 · E5a/load1800/RCAPS/seed1

原失败 SHA256：91d3a201bd1402708a95a09e53ee4b9c226f15e9cd1e92f19a40cef909b7e42b；先前重放失败 SHA256：0a74bb38200845f124a4ad274fb905438b466d6527a698ed2b70c96fd49a1a21；本轮独立重跑失败 SHA256：b49ed2a453de970a7a652ce3714d67af8c401e70c5e2a371a4a8e9a162184b5e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/RCAPS/seed1'
~~~

### E5a 029 · E5a/load1800/RCAPS/seed2

原失败 SHA256：d6dfec175a00f5377ef265a794d2b1be666c2e574bc8354b85da93105c70951f；先前重放失败 SHA256：24db3e992e54fad3d282a77d02f5858fb69a0cf5049363b64ee46c2216ffed20；本轮独立重跑失败 SHA256：a5c0a0ed0d29646520f4fff11f442e080f6903ca5f83feeb2cba4406b240e4eb。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/RCAPS/seed2'
~~~

### E5a 030 · E5a/load1800/RCAPS/seed3

原失败 SHA256：4613e09ee6884e107426f0be19315d9b539ff99fb3f202d72fc7895f64f3702e；先前重放失败 SHA256：af0b1aeb74fa83787e606e43ecbdace51d5ad829b26a570bc3d9717c298ec364；本轮独立重跑失败 SHA256：e9ea113e84ec5142c02863ba3418e290707e91ee0c918dd09d621006030d1560。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/RCAPS/seed3'
~~~

### E5a 031 · E5a/load1800/RCAPS/seed4

原失败 SHA256：9aec03f06c6d98173eae8bfd3f19bdc2e72637d7f08349f59756c0d4fef16419；先前重放失败 SHA256：d862ec32545e7f7647c9db69f15c2c421c6ec4372387922b0aaa00ba701c5956；本轮独立重跑失败 SHA256：b53bf7709a8466a38b3c23219a5866cd6fe71de154bed7e6785a409fa4c9b8c8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load1800/RCAPS/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load1800/RCAPS/seed4'
~~~

### E5a 032 · E5a/load2150/Helix+/seed4

原失败 SHA256：c8cb438ca229770fde740377dac791e236953707106328e0d5b7d5ab809fd102；先前重放失败 SHA256：762e2844cdfe31bd317ecb7502d7f238af4cb2f461cdf3550cf131a003e240b2；本轮独立重跑失败 SHA256：fb00bd86c8512ee017a60da015172b1907297b4719b448d30e9502117c2f3dcc。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/Helix+/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load2150/Helix+/seed4'
~~~

### E5a 033 · E5a/load2150/Helix/seed3

原失败 SHA256：04a1f57343cf41189700857ce0591c6dc0a0c6e07bbbcd7cbee2124260a21a9f；先前重放失败 SHA256：7fda605cd85f92b7396749bbfa1af23f2c7a7de7e4204fd20b0e40b829361e1f；本轮独立重跑失败 SHA256：123eb65ef60fa132c239f906a7599235be02144be6fd5bc26ae37885fa0b274e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/Helix/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load2150/Helix/seed3'
~~~

### E5a 034 · E5a/load2150/Helix/seed4

原失败 SHA256：d7240372225615d6f0af129d15a7d22dd60e903eaa566099fa5fa2d06eb170d8；先前重放失败 SHA256：5fe1f96a2581e77fd11b640e511dc2ffc6f32a59aec4be914944b4e51e2f63ce；本轮独立重跑失败 SHA256：9083c9b1015183edbc272d73caec4e60cc6833050728e039118f83280a91f5c0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/Helix/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load2150/Helix/seed4'
~~~

### E5a 035 · E5a/load2150/RCAPS/seed0

原失败 SHA256：5cf2944b402fb710ff1393df065bd9167f7e1aa355f04087d9f0a0b2eeef0f3b；先前重放失败 SHA256：c36b6ce5cf838622d7faa224430315162f2472f22fc814d83153560c406d9be1；本轮独立重跑失败 SHA256：5dc7d52b903b329e5d70c34a26c2460e39c2f791c7d5adf30021c83a39efb293。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/RCAPS/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load2150/RCAPS/seed0'
~~~

### E5a 036 · E5a/load2150/RCAPS/seed1

原失败 SHA256：615cfa8fc222849f076daed131c12fcf48e595b826926bd842b9ddbedc4b0157；先前重放失败 SHA256：c263aaaadb125a8a03d2f41e5d3291bb57803edd4585462b049c3790b04edfa3；本轮独立重跑失败 SHA256：9ce4749309358cb60a54b490637bc7deb3b127a77752f206a9f81def8ec1f7fb。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/RCAPS/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load2150/RCAPS/seed1'
~~~

### E5a 037 · E5a/load2150/RCAPS/seed2

原失败 SHA256：4ba146515c2b7a0c56538b398df09111e86f5562de1d2133fd63779c6271be2b；先前重放失败 SHA256：552a13aa98e38f479e51b32da19c12f92ef9d0e7ef59786725ed848c96c1089f；本轮独立重跑失败 SHA256：fccdd7f0cbe9e3bef4d3b2fa2571970d7c3f0229beac509c98c448ee994564f4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/RCAPS/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load2150/RCAPS/seed2'
~~~

### E5a 038 · E5a/load2150/RCAPS/seed3

原失败 SHA256：e8049d350bedc4da2fe96ea905073e5a356b8762fb66dbbe14e1c6ddc1463704；先前重放失败 SHA256：669fa0404b5fc09856412993594d830174ba4214a0f93bbf0d469d9e669e0992；本轮独立重跑失败 SHA256：ba4d01b3e3ab76b69fc9b475e95ca13990cc34fabf8d57d6f41fea9a633c1a17。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/RCAPS/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load2150/RCAPS/seed3'
~~~

### E5a 039 · E5a/load2150/RCAPS/seed4

原失败 SHA256：54b8dc4fb69ee214c6a3cc792a142063aa7b309dfc1db564729c80022920ef95；先前重放失败 SHA256：5d86abe392a9c1fa02c076eb780b7836aa599fd43883cb4c4481a72fea517202；本轮独立重跑失败 SHA256：d752077001a2dfb853abff617fba6d327dea361d7165daae4820fcf06da74797。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5a' --key 'E5a/load2150/RCAPS/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5a/E5a/load2150/RCAPS/seed4'
~~~

## E5b：42 个未解决键

来源：experiments/reviewer_v2/E5_scale_kv/E5b/boundary_failure_replay/FINAL_AUDIT.json。

### E5b 001 · E5b/half_kv/multi/load320/Helix+/seed0

原失败 SHA256：4020b7c323b9cb03113e104ecd7ad7618e0576e350d174284c6737358f0062be；先前重放失败 SHA256：173fc0ee8343115d698ff88a49a1aa0480f19884b1b5102b0d9b21634d1a2ad2；本轮独立重跑失败 SHA256：a3701bef35be706fe69a87103a640646f5ed43424b1d4e7eb5cf2c26a0a68db4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/Helix+/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/half_kv/multi/load320/Helix+/seed0'
~~~

### E5b 002 · E5b/half_kv/multi/load320/Helix+/seed1

原失败 SHA256：3d93c3415aeb12f9e65fd22b5f0c1e5eaab2e0fbb2fb8077ef6d2d86098ee4b2；先前重放失败 SHA256：8151c2c9e06efe3bff4d9c9f8611ca7be5756be56ab8edbe54a47c36aea9791e；本轮独立重跑失败 SHA256：af7fb39817449df0fce50d82bb67bd7bef186520926b434e7779c237b645f863。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/Helix+/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/half_kv/multi/load320/Helix+/seed1'
~~~

### E5b 003 · E5b/half_kv/multi/load320/Helix+/seed2

原失败 SHA256：9376cf6f295f977e0b55063beccaf90cbfeed86ed774e126f328bbc357e7dba4；先前重放失败 SHA256：da7c39b5be915a1ae94a821969f8e8625135dd7d438f3e1e94065aff8f2d9b03；本轮独立重跑失败 SHA256：3d5ae27f7c6bf5cebb7c90647cf4599b344b2191ba25a13aba2163e24a06557f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/Helix+/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/half_kv/multi/load320/Helix+/seed2'
~~~

### E5b 004 · E5b/half_kv/multi/load320/Helix+/seed3

原失败 SHA256：6025ac655b09825eac4563439fc241d9780d3c4161836add4d40c9ae5c4bc811；先前重放失败 SHA256：9ddb936340aa18ddf72089334951122892b869fe6848e6cd3cd3cea58e7d55d2；本轮独立重跑失败 SHA256：531916550e6dfd7eb96790e140d3bc042b8a13860f389f78dac4de7f0e41c911。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/Helix+/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/half_kv/multi/load320/Helix+/seed3'
~~~

### E5b 005 · E5b/half_kv/multi/load320/Helix+/seed4

原失败 SHA256：d24fdd6c90028a3fdd0ab02ac23652e3a6e66f12d694e29d5697c20c8e76ac3b；先前重放失败 SHA256：04858964fd812887a9c2a3c700353c3997b6465eb41dbed4e57769b354c772bc；本轮独立重跑失败 SHA256：18539ef831ed38439811e3bac862e8438fef31b780f531e8f0786399f845f793。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/multi/load320/Helix+/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/half_kv/multi/load320/Helix+/seed4'
~~~

### E5b 006 · E5b/half_kv/single/load700/Helix+/seed1

原失败 SHA256：be35e620650a61374d4db64470e3a458309d19b5837fb7dd756ef0f5cc5469c0；先前重放失败 SHA256：cfdd1c8236513ca5088a5066c7efd64e730006f9d2f1b08182d3106c0b61bcaa；本轮独立重跑失败 SHA256：0ff4490ad2e6675da2291bb2b776ea4d19cb3db435eb5b1294c7b4592360e115。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/single/load700/Helix+/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/half_kv/single/load700/Helix+/seed1'
~~~

### E5b 007 · E5b/half_kv/single/load700/Helix+/seed2

原失败 SHA256：0d3fe60d98aa4189e9a20a8743b485d137e1764fb3a6e45c7a8eceaf35c45406；先前重放失败 SHA256：7160cdbd936eaf19beb501ffaa37ea4e90a4592e2550d368dda3f39374b0d833；本轮独立重跑失败 SHA256：662e35e76f994d054b653224d549adefcb5d1c25ce24b5bae6069bca1328632c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/single/load700/Helix+/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/half_kv/single/load700/Helix+/seed2'
~~~

### E5b 008 · E5b/half_kv/single/load700/Helix+/seed3

原失败 SHA256：431268142322361d865c2ef810cbf03d54972841f8bd5a2e2b36d64135f9eb59；先前重放失败 SHA256：ee1d04f368daacc8a3c1ba7f83cd000c1055ebce55c3b00da16729a69a07138a；本轮独立重跑失败 SHA256：c3976b79693ca9c493d776a68b2aecb430d4a9a7726e6c3a86578cf88f8fd6e4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/half_kv/single/load700/Helix+/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/half_kv/single/load700/Helix+/seed3'
~~~

### E5b 009 · E5b/prompt_1.5/multi/load320/Helix+/seed0

原失败 SHA256：33a7a34e0e0827c0c2dc23170b55f4a47462c66afb6059f04e07522d8a3834e4；先前重放失败 SHA256：2f6f677d9751d8e84b5939f525333523aa69f249a86c2a7ea910ff54955cb653；本轮独立重跑失败 SHA256：763f3fc50e701aff9dd9269e22fc7f6c29dadc3a87b6d5a73d41bdbb3eda8bfa。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/Helix+/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/multi/load320/Helix+/seed0'
~~~

### E5b 010 · E5b/prompt_1.5/multi/load320/Helix+/seed1

原失败 SHA256：7a4f62f8abc15d0f665135f04bfe0492104ecdcb9e6784b8cd32b85c345cc3c1；先前重放失败 SHA256：58d4f96282d80183f85545e5c137a178081973225628ea64ad9c2f7223d62a00；本轮独立重跑失败 SHA256：d293a1813de371d4b81ebd3b1784635ed114b45e1ca4d6ad9bbc84b7ea198995。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/Helix+/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/multi/load320/Helix+/seed1'
~~~

### E5b 011 · E5b/prompt_1.5/multi/load320/Helix+/seed2

原失败 SHA256：8124df4deec0004ddc0b2514a2b2741fe57b169b7d4eb144d454e23baa8ca39c；先前重放失败 SHA256：84ba6203e3bd3a187b8572d4efe98196fb974c969ba8bc9c35f15e3f35e8d4bb；本轮独立重跑失败 SHA256：0c3276ace65900a57a90e26b9f3e2de307c2aeb61ed2c6b6ee965dd4ee3af5f2。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/Helix+/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/multi/load320/Helix+/seed2'
~~~

### E5b 012 · E5b/prompt_1.5/multi/load320/Helix+/seed3

原失败 SHA256：511b48cabb5a9cd2df06733a23f50e6963d1432a8947c76b5f16fa2822f96350；先前重放失败 SHA256：f4461cbc5be82b631c1018ed927b6d3ac3b3b296f43f23a4d92f3f04bc4e3e49；本轮独立重跑失败 SHA256：ad7c7ed59045852ecc260ec7ec8552319287a89a26ccf674cef991bf2f31556e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/Helix+/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/multi/load320/Helix+/seed3'
~~~

### E5b 013 · E5b/prompt_1.5/multi/load320/Helix+/seed4

原失败 SHA256：edcf7db38f3b13d8b95c9da290a97153d69edf381d4389c34bc56afe29a8bcbf；先前重放失败 SHA256：088385c3692ee2cfbcedbd113085be512baf96769926ed4e1092cb7d2f6ab83c；本轮独立重跑失败 SHA256：255ac8851870db8214f629c7ebbe254ffe181bc04bace6ef0563c1cdaf8cf425。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/Helix+/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/multi/load320/Helix+/seed4'
~~~

### E5b 014 · E5b/prompt_1.5/multi/load320/RCAPS-KV/seed1

原失败 SHA256：fff79800e73c402fd77c961d9b0e4a0320c0e0656619c5ff24c9c3145ddc07e0；先前重放失败 SHA256：155201868780090df79100b3e3d77aaf667eb7f780ad4081137f2e23c588e301；本轮独立重跑失败 SHA256：559eea253017f144ef8acb2d16b8b7f808dde2ff24e0b94c7139ec51373f2906。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/multi/load320/RCAPS-KV/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/multi/load320/RCAPS-KV/seed1'
~~~

### E5b 015 · E5b/prompt_1.5/single/load700/Helix+/seed0

原失败 SHA256：0409211c927bf8c632130b471a83eee17eefbdf9f915da89cff733b09a484dec；先前重放失败 SHA256：e91a165cfbc50b85dfcd7bd7d77e0e472a519c4e36cbe7c44deb16eabb9b271a；本轮独立重跑失败 SHA256：6b5568f69b4239abee3e1e0d73c250907eb93a89284d89ec91bff30101e64e39。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/Helix+/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/single/load700/Helix+/seed0'
~~~

### E5b 016 · E5b/prompt_1.5/single/load700/Helix+/seed1

原失败 SHA256：069e3d132eaab9058e28d64350fea66f1752369d633551f522f9b925a41808d3；先前重放失败 SHA256：cd8725671049ef05e6cfa3464888c4edfe0bd1ac8edfc2f43f61657edd30c252；本轮独立重跑失败 SHA256：0396d17dda81e412d7abacf9a8c56894f6f0e1651a25d2d11548b18959511c02。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/Helix+/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/single/load700/Helix+/seed1'
~~~

### E5b 017 · E5b/prompt_1.5/single/load700/Helix+/seed2

原失败 SHA256：d3bc4584ac9b1ea4b9ac89d222a4fac7ce7ee41105f629f5940e31972aa56087；先前重放失败 SHA256：c9ec1246638a7c3c8cf10c4a80165779e3c0ddb6661f715157949c5870280ac7；本轮独立重跑失败 SHA256：c000a1e8cad5d12fdf29137c1efc183717fdcfc487142faef7745bcbfed1d27a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/Helix+/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/single/load700/Helix+/seed2'
~~~

### E5b 018 · E5b/prompt_1.5/single/load700/Helix+/seed3

原失败 SHA256：62cf4e26fc1cebb1ff79d10756058cab8d6b027e308c9498f039472558dc9caa；先前重放失败 SHA256：3f6973ddd947a19297c2c22b7223b859fad46b6b7142b68dcd6e692b3fde8b79；本轮独立重跑失败 SHA256：462de4ace375a3c35143acd2e6e452428f70b413481f22f088ca61627164c3e7。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/Helix+/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/single/load700/Helix+/seed3'
~~~

### E5b 019 · E5b/prompt_1.5/single/load700/Helix+/seed4

原失败 SHA256：90c586f41832791b9e0d53548b318fc926aba516a1bf18cff7c0ccef2e29a4fc；先前重放失败 SHA256：23d7d407475d8f7bd9fef263c406b3c4fd0949bb4ac0ba2218e6676fb20bf352；本轮独立重跑失败 SHA256：27c8cbcec793de2b85786b1885f85e563260922ddceeb18a3ccbb7f787256e1b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/Helix+/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/single/load700/Helix+/seed4'
~~~

### E5b 020 · E5b/prompt_1.5/single/load700/RCAPS-KV/seed1

原失败 SHA256：3395cf5078d14f0fa04d6b70ab9adf6a6190449cec15d8fb7dec12810aefc2e3；先前重放失败 SHA256：0f17c8fd43a15c5be98f767f90abd0eb63a99b06a1b6829dceaedef6b56ea76d；本轮独立重跑失败 SHA256：f93dbc615660b44a5c6d1f8e30cad9bb606e84802c94ebd843be46283d173df0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/RCAPS-KV/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/single/load700/RCAPS-KV/seed1'
~~~

### E5b 021 · E5b/prompt_1.5/single/load700/RCAPS-KV/seed2

原失败 SHA256：1531ace186d9a888cdde445041da19584678fbcb912306ce9596b305795080c9；先前重放失败 SHA256：764935cd89f6e2d65e4c45e4e10da9d2af1b9922e98db5953ea5f2c289baa81f；本轮独立重跑失败 SHA256：20076b5223703f3174910c9cc41ec7aa02c90e2404ca8a33a473577e34772fee。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_1.5/single/load700/RCAPS-KV/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_1.5/single/load700/RCAPS-KV/seed2'
~~~

### E5b 022 · E5b/prompt_2.0/multi/load320/Helix+/seed0

原失败 SHA256：a4edabcde0228a1ab1a6e851a2b0e094931a10a5e77c3ba755e73b04182fa8b5；先前重放失败 SHA256：4cec51990c43ad6750d1108d411547b10285c05ccf28a6abe9cdafde1e25409e；本轮独立重跑失败 SHA256：aae0a24ce20d847bb21ac466d247d771cd7ed50b563950e2796cc802e6285006。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/Helix+/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/multi/load320/Helix+/seed0'
~~~

### E5b 023 · E5b/prompt_2.0/multi/load320/Helix+/seed1

原失败 SHA256：d48ed75ebe4e9b772132489814e0a6fbe6e45466b9ef386058125b73f29b2bb1；先前重放失败 SHA256：37ca6461b48f9419002585a2c9604c214879602d72eac1b0e5f74c2510a0633b；本轮独立重跑失败 SHA256：5f019a76a76b54a14603c0d07eef46daaaa6b2e1568355b0c85cef2b58ca2da2。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/Helix+/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/multi/load320/Helix+/seed1'
~~~

### E5b 024 · E5b/prompt_2.0/multi/load320/Helix+/seed2

原失败 SHA256：d2080d029fac414314f9c9903a342a7918d811876991d0a9191352f0c5a211f4；先前重放失败 SHA256：2ca758fde35a5f625317bf92c61e0ae6e3e94130d52dbece6ea78701467ca047；本轮独立重跑失败 SHA256：748aabac612e06b503f0e194dd2415cc5746989af700d03e81d458a802697425。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/Helix+/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/multi/load320/Helix+/seed2'
~~~

### E5b 025 · E5b/prompt_2.0/multi/load320/Helix+/seed3

原失败 SHA256：74bf209b1aca0673f6f0683849e19f1bc1c500559429c96e7867a3535d47197b；先前重放失败 SHA256：f59c15b8f29617b53509f69af33bf4f2efcd0911297a543eff61410f37b09886；本轮独立重跑失败 SHA256：cdea7a6bb6b08dff07e640e43ca9b2d8329e73d83061c832bd25e357d8165b08。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/Helix+/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/multi/load320/Helix+/seed3'
~~~

### E5b 026 · E5b/prompt_2.0/multi/load320/Helix+/seed4

原失败 SHA256：c407bdb4f68c8e5f2e1b665a696d9b52a589d6af56dfbd24930fd69b046fb6b0；先前重放失败 SHA256：2f2643c2a750d5e7634ca53cd031cae694e99daf63ec471689aba36bc0bd4173；本轮独立重跑失败 SHA256：2c8edf18031a13b6a85d5c263f9e3cd30d03d74b8d31329f66690e8387bcfc33。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/Helix+/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/multi/load320/Helix+/seed4'
~~~

### E5b 027 · E5b/prompt_2.0/multi/load320/RCAPS/seed0

原失败 SHA256：7b928e8f19c2c7c7adcd9107c115cc77f0107e1ab781e3923bac110b57f540f2；先前重放失败 SHA256：65e567609c38d9a720c435c4eb97d05b325656c489570e9dffaa0ea86fc60179；本轮独立重跑失败 SHA256：cb1c2eb46f1e36f97cf2a3c54dc6b18b0d325b8f497fb05a8218e4004cd817bf。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/RCAPS/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/multi/load320/RCAPS/seed0'
~~~

### E5b 028 · E5b/prompt_2.0/multi/load320/RCAPS/seed1

原失败 SHA256：adb9f3af642fd06f0e2d6c94abacb041b8a1deb4d5ef30b22aa874a0b7e069dc；先前重放失败 SHA256：71bc63c5dd61a5b5c188327f4c07127a67c4175ac227026d7e724a0597f8a144；本轮独立重跑失败 SHA256：aace25f7702f592033989e5475c738f1fa59a45b0b75d700544c04ee34871cbf。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/RCAPS/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/multi/load320/RCAPS/seed1'
~~~

### E5b 029 · E5b/prompt_2.0/multi/load320/RCAPS/seed3

原失败 SHA256：f3f8be264676fda7f7eaccd1c29758e7f044c21c4b142a7f28147327c26f3aae；先前重放失败 SHA256：13a94909a4a414e7e7297eaf18e7322182bcf52bacaa68329b8544643256ce19；本轮独立重跑失败 SHA256：23441dda4c4c1ed0ed32be4af9657beba626b2c222d78a56776be9de66a64604。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/RCAPS/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/multi/load320/RCAPS/seed3'
~~~

### E5b 030 · E5b/prompt_2.0/multi/load320/RCAPS/seed4

原失败 SHA256：f627cde22ff42efbf485a7fe92bedcd52c98f1e4118d11cbe4d7faba34cf1beb；先前重放失败 SHA256：4b6eec9ea1a311a5be3b03aac188d12d5360854d9af60435d2a6ffb69cf84e25；本轮独立重跑失败 SHA256：3d8878ec992f54f40462bf0cdb3e66939b7808a38d4a3429b44c47cdafd6a8d8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/multi/load320/RCAPS/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/multi/load320/RCAPS/seed4'
~~~

### E5b 031 · E5b/prompt_2.0/single/load700/Helix+/seed0

原失败 SHA256：acf3d87239a7342e0d94206e032681ba9030d54a1e0143d72ff53e64640d646b；先前重放失败 SHA256：4324ee6847c3f2e7030411816461c235382948b84b860a7c1bb38f3d8bcc1de7；本轮独立重跑失败 SHA256：2066eb6a4c489fd49de881f11614d7d5323e051e6038354f568ab5b1711c31bc。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/Helix+/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/single/load700/Helix+/seed0'
~~~

### E5b 032 · E5b/prompt_2.0/single/load700/Helix+/seed1

原失败 SHA256：cd33fc75e792113ba565726d63f3c9dee5104dfe1d55c0499cee2a16f8398a7d；先前重放失败 SHA256：ab235b37bf6fb12617e4c909cd94cd3ef74d0431ba32ac83a2202ea65aaab0d9；本轮独立重跑失败 SHA256：09c04942cdeb82e87d976f029d7e3b0bfc6797bc7409ef14f0b827460efbe67b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/Helix+/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/single/load700/Helix+/seed1'
~~~

### E5b 033 · E5b/prompt_2.0/single/load700/Helix+/seed2

原失败 SHA256：6cdfd7af32fc14f2a9569b8f88cbc275dbb2e2273482bc0eba3f9601d5524b3a；先前重放失败 SHA256：fd0d2d4718505e268a4a5543ea18748c1af48cf9ae9d05fb31f2297dd02d75df；本轮独立重跑失败 SHA256：183564740d8afd72310da07a960302e6348e57269bcc2aae989d7dd0cdfd4378。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/Helix+/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/single/load700/Helix+/seed2'
~~~

### E5b 034 · E5b/prompt_2.0/single/load700/Helix+/seed3

原失败 SHA256：0d3884dfeac005287daaeef6c1caf6a588d575353b6b35872f584d7f97298ba6；先前重放失败 SHA256：2390aeb218a736306dd88eda3c7814a82978c94a0209599925293d620e4629c8；本轮独立重跑失败 SHA256：8754a6694907a7c088a30c1f165da31f5d55b7262f0fcefef61b05cf244e3612。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/Helix+/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/single/load700/Helix+/seed3'
~~~

### E5b 035 · E5b/prompt_2.0/single/load700/Helix+/seed4

原失败 SHA256：10ea7dd4c5c119007c0fb9df587de57adf0a3a5db5a5697a8461accd6627b4c5；先前重放失败 SHA256：4a7c91bab63a2657ed89d6de850f3be47f013027c63534867e96be7abe120ce0；本轮独立重跑失败 SHA256：0a1b5559e2c8f22c7abbb91b64ab19ac4754b33504d161a5df3b0022dd0c4912。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/Helix+/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/single/load700/Helix+/seed4'
~~~

### E5b 036 · E5b/prompt_2.0/single/load700/RCAPS-KV/seed1

原失败 SHA256：3a6b85456fb88bbb9d3fb29a4d7a45317e7342c09bf4039ea397cba9ba373e0b；先前重放失败 SHA256：130cd893d1277465b5e51817b00c56ba78e177b66855cd04dbbd96deae53a157；本轮独立重跑失败 SHA256：2c65f1f69e909ad8c0f86b2ba352bdd25b26a3ff262c465210fd59f19020d048。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS-KV/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/single/load700/RCAPS-KV/seed1'
~~~

### E5b 037 · E5b/prompt_2.0/single/load700/RCAPS-KV/seed4

原失败 SHA256：9d97a240ac9cbcd1372894e19f7cd73a8e17f6ebfe08d22f5c88964cb540ce1d；先前重放失败 SHA256：9705a0c8e4baacb1167b4d2201980f5190d909ce7f896fb640d8d19089605327；本轮独立重跑失败 SHA256：e8b950c75bf139d34b556e47e511750270cd08f7898011482614193fc1cbc754。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS-KV/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/single/load700/RCAPS-KV/seed4'
~~~

### E5b 038 · E5b/prompt_2.0/single/load700/RCAPS/seed0

原失败 SHA256：8f67a6cf4bc77e40ec9dcbaa86288e2886abaadcfda5739baa0c33a999ec9959；先前重放失败 SHA256：4312c8a46926fbb6050b2d2f7693702ad332606cd128b3ec334078f0d948d95e；本轮独立重跑失败 SHA256：ac4574dbb1335b0bd70e02764fc629a7496b225128b3426cbf882e6b46cdd4c7。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS/seed0' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/single/load700/RCAPS/seed0'
~~~

### E5b 039 · E5b/prompt_2.0/single/load700/RCAPS/seed1

原失败 SHA256：ee4c57b44d54b7c71904a0f90a6b4a2ff60698fb30d43bde36f13254f3c91436；先前重放失败 SHA256：7077f4142d09ac534b464dfea836c9f31001bc7596a543673bad28380a0a2020；本轮独立重跑失败 SHA256：b60c5d7a0b021984e7883f074718124d4fb718d4220807b4db94907ad80b1b1b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS/seed1' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/single/load700/RCAPS/seed1'
~~~

### E5b 040 · E5b/prompt_2.0/single/load700/RCAPS/seed2

原失败 SHA256：2b72bd46fd4076245a5eb9accdd73647e1416f81ff6403b3c0662ecd04a85639；先前重放失败 SHA256：42d3634ec201e42c33922d4222bf92c90e93273c235c1e974bd16232903531f6；本轮独立重跑失败 SHA256：0d6ee30a4a938a53f78db83d86864268d1136833de5df9e6b09e87ca02dd72b8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS/seed2' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/single/load700/RCAPS/seed2'
~~~

### E5b 041 · E5b/prompt_2.0/single/load700/RCAPS/seed3

原失败 SHA256：0a3cf836c4e3cfc2a9b7df6acd081199c951fd0fb885a3db7eb9db9788cd1bec；先前重放失败 SHA256：38aa464b5eb4b82379b00afc4bb3944372de5d5874aa6c4ca7aec0b40881e29e；本轮独立重跑失败 SHA256：b5e0fc530934e65ec4ea6b7753184be406c295aecf327e77ac9cf1a99df44916。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS/seed3' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/single/load700/RCAPS/seed3'
~~~

### E5b 042 · E5b/prompt_2.0/single/load700/RCAPS/seed4

原失败 SHA256：910f86bf056b0e5bddd15e5c42c71d5dea4dd50b710aed5c1cde00eb4460b5e6；先前重放失败 SHA256：a6662792c4656762c55ec79d417d949984d06330dbca5698ebfef4a45314505f；本轮独立重跑失败 SHA256：e78dbec20dcd4f482008a5866b2504969ca0644f05128cd0c5cc77a5858e1e61。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'E5b' --key 'E5b/prompt_2.0/single/load700/RCAPS/seed4' --output 'experiments/manual_reruns_after_auto_20261101/E5b/E5b/prompt_2.0/single/load700/RCAPS/seed4'
~~~

## V5：68 个未解决键

来源：experiments/v5_failure_replay/FINAL_AUDIT.json。

### V5 001 · v5_kv_stress/multi/load320/capacity0.125/V4/seed0

原失败 SHA256：b4c01fc6c2b40a9b76327f4ae7012c999567583c2c7a0016b303af163eff986d；先前重放失败 SHA256：2678c6aca99bf0eea16e40a23c9a9d820c508a8798a1e689acb6645edfe5b673；本轮独立重跑失败 SHA256：0afe9b56d6b251d95611f158c197d40a19e2c32c9ba9de7c996b74198c25dee1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/multi/load320/capacity0.125/V4/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/multi/load320/capacity0.125/V4/seed0'
~~~

### V5 002 · v5_kv_stress/multi/load320/capacity0.125/V4/seed1

原失败 SHA256：5c143914a234d0412d320ef79bc8fbe3329d61fac757daa2a0196034a57138b8；先前重放失败 SHA256：20899a10a8ecf0aa87e1abc983f798ec34d39a494422752bb11617493775e246；本轮独立重跑失败 SHA256：0af67f3cdb03f067ce3e86ec2291ef86d026dbfcd4bfd37a7bdec19d597984fb。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/multi/load320/capacity0.125/V4/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/multi/load320/capacity0.125/V4/seed1'
~~~

### V5 003 · v5_kv_stress/multi/load320/capacity0.125/V4/seed2

原失败 SHA256：94a79c7891eaf0431f13de850cf332a1e3b46705a6bfff9272d42a5768747a31；先前重放失败 SHA256：07d7a20634eb057a69e8343b3aa620cfbc68ddade9ae80f4824b7dabfabfe1d0；本轮独立重跑失败 SHA256：0258c13294cdfaa271c161fa8ff1cf5d5b73b946e4301632bc8d84622eda8872。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/multi/load320/capacity0.125/V4/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/multi/load320/capacity0.125/V4/seed2'
~~~

### V5 004 · v5_kv_stress/multi/load320/capacity0.125/V4/seed3

原失败 SHA256：871db564b5e345884060d6bdd49d66f5820ca6ed33d25ac4dd96df383ec623ca；先前重放失败 SHA256：d44d6329c171708ddba38d8fc0e7ee7a6847508a7dd1235d008e8fea0007c785；本轮独立重跑失败 SHA256：ef3259ac341e8bd6b37da460726db0034603f59e9ec64dfa3b179ba51a9f58a0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/multi/load320/capacity0.125/V4/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/multi/load320/capacity0.125/V4/seed3'
~~~

### V5 005 · v5_kv_stress/multi/load320/capacity0.125/V4/seed4

原失败 SHA256：9811517e786295fae374047ddde01fc859c41852424d6b11471e1c0ae049acc8；先前重放失败 SHA256：c8b94de79ff5bc2183a16e4b968e7e11a548eb43c381bd245c9eae8ad3e07781；本轮独立重跑失败 SHA256：04d124c935afe2d07cdfd2c713a561d78c0a7341b9a1fefa4b902b6efc427d64。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/multi/load320/capacity0.125/V4/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/multi/load320/capacity0.125/V4/seed4'
~~~

### V5 006 · v5_kv_stress/single/load700/capacity0.125/V4/seed0

原失败 SHA256：ef4ae43213336db954a96c98a8d9b4b65d42dcd61a778b5bda57b0ffafa9ca1e；先前重放失败 SHA256：6dac6ebe3d84c651ad9f8d34a821a89940c0085c0d26e060e102b7c350babc82；本轮独立重跑失败 SHA256：c00f40eaee9c44545580cc121f666e413f2f1eb6a5062940d835f5806ce13878。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.125/V4/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/single/load700/capacity0.125/V4/seed0'
~~~

### V5 007 · v5_kv_stress/single/load700/capacity0.125/V4/seed1

原失败 SHA256：ab79b9a4da29c236f6822a1e74879fbd5ef8f13b54e9559619b0e6294c58652e；先前重放失败 SHA256：4d9fea65b819b4a10a24922292d22ce728ee5682e91ae0ae40dec70f5ab371e5；本轮独立重跑失败 SHA256：0aaed7aa76bf0d9a7117b74344c534ec843452d1a107afaa5fc3cd1fb573dbd5。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.125/V4/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/single/load700/capacity0.125/V4/seed1'
~~~

### V5 008 · v5_kv_stress/single/load700/capacity0.125/V4/seed2

原失败 SHA256：920d2d4f6cb29bb6c8bf983ea010fb8271f800301481525bd2cf93366b1e2080；先前重放失败 SHA256：035b76a454185a0ecb92d414591dc79a0701dd9887b454eb1cb5a556597c17ae；本轮独立重跑失败 SHA256：4320272392cbe616c480f2fce562f92dd98e4e4ff08e6101151a8db533092055。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.125/V4/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/single/load700/capacity0.125/V4/seed2'
~~~

### V5 009 · v5_kv_stress/single/load700/capacity0.125/V4/seed3

原失败 SHA256：a4fcd333a6bede34daf26972eddfab7504f2f6ebc4ff11e3682b833dce00a819；先前重放失败 SHA256：b5161bad804ec50d860760856821b675392967635ec521ec590d8524583bbdd0；本轮独立重跑失败 SHA256：b998ee5dd61edd33328f94b048c4a8d817b4cbb4263464e76c472e3d68b45745。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.125/V4/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/single/load700/capacity0.125/V4/seed3'
~~~

### V5 010 · v5_kv_stress/single/load700/capacity0.125/V4/seed4

原失败 SHA256：9ee543eb98d30456252ec5a27d0ace0d4d1901386b35d721bcfd281f0ea01e99；先前重放失败 SHA256：594e326c8d012b770c7cce846cffc8e66f609e9e6203291027dfab5ba8d913d1；本轮独立重跑失败 SHA256：eecc443ac3fd3dd3c22ec5b9e7a30a84cad964882e4921d28d2ef1764b35800a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.125/V4/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/single/load700/capacity0.125/V4/seed4'
~~~

### V5 011 · v5_kv_stress/single/load700/capacity0.25/V4/seed0

原失败 SHA256：8e76d6ded77befca2600967a07d65050e1aff17cca45f39b6c45b0c9c922c004；先前重放失败 SHA256：b8fe7b2c51656b89a75c61b4eaa29348e44a846fbe3ca364eae590736ed8ade1；本轮独立重跑失败 SHA256：329be4dfe93de43f97c0afdee64e13f40a245757c0ee08e294d6ddfd7dae0236。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.25/V4/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/single/load700/capacity0.25/V4/seed0'
~~~

### V5 012 · v5_kv_stress/single/load700/capacity0.25/V4/seed1

原失败 SHA256：26afee2f740fe42307116c2baf8c001f9e8af42a4cb632cc0a7e2120acb34e48；先前重放失败 SHA256：af98578157cbd4d82b2a76f28e7f8349c18f4d182ab8b754a7585ea7406f67fb；本轮独立重跑失败 SHA256：099af438f667d6fc48c240ab163731b44b7aedc0d4b2d1c4114905ebd00f33af。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.25/V4/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/single/load700/capacity0.25/V4/seed1'
~~~

### V5 013 · v5_kv_stress/single/load700/capacity0.25/V4/seed2

原失败 SHA256：3e36db6c8e605181d67169c8078a528368a1f9c783bfd5861d62b2ce194b8f21；先前重放失败 SHA256：cf0e488034df0bca591d56a28570d4315510fe103ff13b61fa6fde10441707e0；本轮独立重跑失败 SHA256：461e79eee05e0bfe63382b5564cf14254951ea4392647fbf826f03201f366120。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.25/V4/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/single/load700/capacity0.25/V4/seed2'
~~~

### V5 014 · v5_kv_stress/single/load700/capacity0.25/V4/seed3

原失败 SHA256：db80fde639a42f9d78c09aba47932130a7d559f70666981934e35ab8349662cb；先前重放失败 SHA256：91441b75e881bddaf8c653a0aae2124b1cb4e104ff2e6fbbe91d5d568ee9755a；本轮独立重跑失败 SHA256：2a8b0b78da0cfeb7eb9121fddcbd05bc506ddb44541c985e756d6447984ab76a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.25/V4/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/single/load700/capacity0.25/V4/seed3'
~~~

### V5 015 · v5_kv_stress/single/load700/capacity0.25/V4/seed4

原失败 SHA256：f7bd2fdaeb5b60846d3a369b53d04a3085ea080982135563205fd9c9dfdcc458；先前重放失败 SHA256：5a14c58c00d6deac866ee105c42ecd34802a67432e05f19437f3f30c2ecfce6d；本轮独立重跑失败 SHA256：c8fe1dab68a05ab77151a184c25e05c024392423cd31b273cad52e4786be2558。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_kv_stress/single/load700/capacity0.25/V4/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_kv_stress/single/load700/capacity0.25/V4/seed4'
~~~

### V5 016 · v5_model30b/multi/load840/V4/seed0

原失败 SHA256：9a2481f3da6d9bbe362a6f547c72f0948f9be0f475bf93b57e891af94063c2bd；先前重放失败 SHA256：0a552291e5142d9d2a373a13c0421aa595a78a3426450a68891a508a3c4339e1；本轮独立重跑失败 SHA256：53b39390f5ed3953e0daca6eb29492db126ea47bd21e3971a6b07eaccf5ffefd。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b/multi/load840/V4/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_model30b/multi/load840/V4/seed0'
~~~

### V5 017 · v5_model30b/multi/load840/V4/seed1

原失败 SHA256：8dd8b84f6f4ebeebdf3650b43d7cbe8e1a6210d818584e13634ec76cbd0b147d；先前重放失败 SHA256：e5481ae2a05d0d12599286deae6d2e634236624a5f47fcd39476a3d61a877c9e；本轮独立重跑失败 SHA256：13626fefd66e8fc68f0b30c5efff711e5056a539f812e89717d05eb9e4e91a1a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b/multi/load840/V4/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_model30b/multi/load840/V4/seed1'
~~~

### V5 018 · v5_model30b/multi/load840/V4/seed2

原失败 SHA256：d4c6d3432f107b65530a0259dd468e0f3e1f4e43e4876fe31d4b7c633f2ebba5；先前重放失败 SHA256：f846a90cd00c9d0d978bd0cc9cc393d85a0d0763e8d7003d8302f381e09fbd61；本轮独立重跑失败 SHA256：25655c04115b5ee3ba516947f0cd4a9abfdb07a6bc10e2ffd9402991888bbb39。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b/multi/load840/V4/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_model30b/multi/load840/V4/seed2'
~~~

### V5 019 · v5_model30b/multi/load840/V4/seed3

原失败 SHA256：3d356c821d5cfd85955ec53258738b10f519088d855faee72f7d2cf2a3ac0d09；先前重放失败 SHA256：382605d803ac08f90e716d1534d15d4446af623ab6da3d50478eeb5916e70017；本轮独立重跑失败 SHA256：e619b93bfa1cc73d71d231055028649cf99900aaa0da2b84e342e3121d920643。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b/multi/load840/V4/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_model30b/multi/load840/V4/seed3'
~~~

### V5 020 · v5_model30b/multi/load840/V4/seed4

原失败 SHA256：e1d76fd62fb881ec72d99f263168f6d1b086576f9dd494a230847c80eed70d0d；先前重放失败 SHA256：6b551a8cba804f07600efab433879c5b0590951fd684593d0c45d997cb7ff2a8；本轮独立重跑失败 SHA256：9d22721342a9c1d152cf80a3819276a81d243e1dfe4e8ad123666deaf0c2ae16。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b/multi/load840/V4/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_model30b/multi/load840/V4/seed4'
~~~

### V5 021 · v5_model30b_pools/multi/load840/HH/seed2

原失败 SHA256：0c52969c0c04a020788f4b2c1c1abba9c8d58dff609767e442ead239ab4e6ad5；先前重放失败 SHA256：d55d756a8d141428d4eed5c8e1b1df2fe066468128c37017bb0d6a5e9af07dee；本轮独立重跑失败 SHA256：bfc603501b9b752e2949a537a24290ace6947649dc8b5dd72b33112e3b7976ae。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b_pools/multi/load840/HH/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_model30b_pools/multi/load840/HH/seed2'
~~~

### V5 022 · v5_model30b_pools/multi/load840/HH/seed3

原失败 SHA256：fb6facce977850c9708dceb8ab240356b742df6a9edd5c73ce5123fdddd941a5；先前重放失败 SHA256：45f85a857532aa9a0af352c5f2a57a2b8441737378845f5d8672602fc3648535；本轮独立重跑失败 SHA256：2a6856d5cd9c4de29db100adc8b5a0ecece15a29693232e96fcc00c4d89be62c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b_pools/multi/load840/HH/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_model30b_pools/multi/load840/HH/seed3'
~~~

### V5 023 · v5_model30b_pools/multi/load840/HH/seed4

原失败 SHA256：bab27d311a7deea5abb19688b731d4ca8b821867a16a03d03f12af7930b96497；先前重放失败 SHA256：55233b167a3fd238b12cdc406805b21c4c61eb04ab62af08530e82b42874b16c；本轮独立重跑失败 SHA256：427e78ba14b09efe1efcac230e661df68f5316f3ed9a4a1a0a7f79fd597bf65c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b_pools/multi/load840/HH/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_model30b_pools/multi/load840/HH/seed4'
~~~

### V5 024 · v5_model30b_pools/multi/load840/HHplus/seed2

原失败 SHA256：12bdf5026a46e85123e484d6131a88ca23f259e90cddef0cff4159c0af0ea6c6；先前重放失败 SHA256：b8bec00a058bb35aa532753fb2044f4551fe5f251a4ceb05203a5cf7e59800b1；本轮独立重跑失败 SHA256：16c44055521e3280b9550ce15105dd9a4a0b6991be575be6d40c1a1c2af62cf1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b_pools/multi/load840/HHplus/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_model30b_pools/multi/load840/HHplus/seed2'
~~~

### V5 025 · v5_model30b_pools/multi/load840/HHplus/seed4

原失败 SHA256：90b0be0bcd36aa43ded3cf81052b36490c1056480bb2b473fadaf1bae9738a82；先前重放失败 SHA256：922fddb1aaf003a5a353b8372cf41ed381990cc5c86728519c003c73ec9f5bd5；本轮独立重跑失败 SHA256：b3c518ca803a1bcfb2ab8a4805c5acdbefe42c87d7c8570a8318458c4c6042a3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b_pools/multi/load840/HHplus/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_model30b_pools/multi/load840/HHplus/seed4'
~~~

### V5 026 · v5_model30b_pools/single/load970/HH/seed3

原失败 SHA256：3b55549e4947b967c0f53c845eb3f1924b22ea9219c663031d3694615157ef6a；先前重放失败 SHA256：914de60e49c0e004c3fb8ff01d5fad36c8fc784779b0d76f667023bcbffe3962；本轮独立重跑失败 SHA256：0638b25e389c051e46adac697fa5ae8bc9255d9d512005116729ecdff9766b68。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_model30b_pools/single/load970/HH/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_model30b_pools/single/load970/HH/seed3'
~~~

### V5 027 · v5_parallax/single/load700/helix_fifo/seed3

原失败 SHA256：45ce1c6e3faeb9e016a32cbc829e2275138697aa9271f5fb3c667ee70164bb45；先前重放失败 SHA256：de68a8dbee61fd602479a46ab180afc4f37bd463e0e8dae35c7180bedd2a2c12；本轮独立重跑失败 SHA256：18ae1d8b752789eaeef0fbfb0a3ca8d91a9ab7b8cadc73016952d4cc97d35f1e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_parallax/single/load700/helix_fifo/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_parallax/single/load700/helix_fifo/seed3'
~~~

### V5 028 · v5_seed_completion/multi/load240/separate/seed0

原失败 SHA256：d30ff0b1d94cc50599ad75d0fd918d31841d5f6c087927442424e25c3ef949f4；先前重放失败 SHA256：d5e56bd9712c84594b7cd924dc7f08647a8f2696681b7c17f80463a08a0bea82；本轮独立重跑失败 SHA256：9951c626adafa18e1a953dea65c2387beef3d3b65134e4227993e43c418194f1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load240/separate/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load240/separate/seed0'
~~~

### V5 029 · v5_seed_completion/multi/load240/separate/seed1

原失败 SHA256：ded329241ac626647989bf3c1aeba41d373d0b6e6203bc4aa4c9836fc50c6a09；先前重放失败 SHA256：0534b25763b543f68e6bbbad6feae8c280d6f2d2af5fb018d9d4b4e1e471a05e；本轮独立重跑失败 SHA256：d73678b0ac43076fc833593236b3f04de329f5dbb970499f14ba4f36bc803db3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load240/separate/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load240/separate/seed1'
~~~

### V5 030 · v5_seed_completion/multi/load240/separate/seed3

原失败 SHA256：c493d9e2346e1cf357d65f74f51f811b7af8ed7f735fe0d5ab97b798babfed35；先前重放失败 SHA256：187848ea20c48cc7e5b80f3d01ddeaaf03be3abbadd906c92d79d36be937b4e6；本轮独立重跑失败 SHA256：b1fee0b6479d84c3e2e745f91a711c9a0fdbc97ccb9daf331cdbbefb916db74e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load240/separate/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load240/separate/seed3'
~~~

### V5 031 · v5_seed_completion/multi/load240/separate/seed4

原失败 SHA256：92545c8f8a0f90a5c560f207b80862dc50a2048c233648b6e1cdded6046f5494；先前重放失败 SHA256：560dd7f34c40c567575f68feb828809834e1a710f8b56beffead77c7495a2c2e；本轮独立重跑失败 SHA256：3f0515ba22465542662cef140d9228670bc8f3cf096fecd4751589fe8a286f28。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load240/separate/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load240/separate/seed4'
~~~

### V5 032 · v5_seed_completion/multi/load320/separate/seed0

原失败 SHA256：445c4297d60d9b0bace64d2d788f6345df09c49f9856955209932781cbc6b231；先前重放失败 SHA256：d84cb93be41777ace14296993d2341261743720dd436a52364b60059a8ec3465；本轮独立重跑失败 SHA256：3c40ff2d83563c563dbd7472d08370438655cc8ee82cd519679382d007b5bae9。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/separate/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load320/separate/seed0'
~~~

### V5 033 · v5_seed_completion/multi/load320/separate/seed1

原失败 SHA256：a4efb04483a92c14f0e49c55e0e057bfb892877647913ce63be436a6a7a0950c；先前重放失败 SHA256：6ff5d472635daa48864558e5f83dfa461ae315d96e7a2b6d9ee21c2847cc0d8c；本轮独立重跑失败 SHA256：82c557ee667d4d7237ee331c9d6f7e8b3c5b7c6713cc9fabba4e62d477ec6d9d。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/separate/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load320/separate/seed1'
~~~

### V5 034 · v5_seed_completion/multi/load320/separate/seed2

原失败 SHA256：aa4cc27ff3e05b40cba81ff1a7cc04c84e2b2869ebafff74c18ff98d5adf0c9c；先前重放失败 SHA256：4c865d86bf0bb498d642db64da3b90331ebc310a21dc7d992818e1bfe3d509c0；本轮独立重跑失败 SHA256：601e1799c9e53ba887ed8cac823f09c8b9d98b2fdf2c888cfe9a3a9eaef20d33。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/separate/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load320/separate/seed2'
~~~

### V5 035 · v5_seed_completion/multi/load320/separate/seed3

原失败 SHA256：26193449def1f63e4a01fcda1e824b2c8f46d041c79821101d9bcc7a498775e7；先前重放失败 SHA256：0bae3a9f97d0cd55751ed78aa0a8906b5e9deec655079ba9eb4b2de788e0f2fe；本轮独立重跑失败 SHA256：5fcdf10ff120577e25beeeb31470c305bca02d53a34f2bed41fd1f7b2506abb6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/separate/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load320/separate/seed3'
~~~

### V5 036 · v5_seed_completion/multi/load320/separate/seed4

原失败 SHA256：2fcac2de0300a417c59ba95bda94b1ad8fa06de41c92d91ebf5704fb603615ab；先前重放失败 SHA256：896d20d1beaa081e0487f215ddd99b42ad6720b58b16e16b057a7bb120fad841；本轮独立重跑失败 SHA256：dd9d20532125fb4359e617d5e2d7b0878a5896ec61d7e81906bd6c7eaf00afa3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/separate/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load320/separate/seed4'
~~~

### V5 037 · v5_seed_completion/multi/load320/swarm/seed0

原失败 SHA256：39b942228a82536d96eea69e5fe0114502dcfb8a3878229c6fb0d144defc53ab；先前重放失败 SHA256：a23b2c2b5fde669add07f8afadfca6872b53b9998f41e1b6d8bb565759b59503；本轮独立重跑失败 SHA256：140962862bcfc2a5b40d010985aec422dcaf2b76e3f40774c4d68d7e2c4a96a6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/swarm/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load320/swarm/seed0'
~~~

### V5 038 · v5_seed_completion/multi/load320/swarm/seed1

原失败 SHA256：0b40e39c8eb72e61dbfa8d56de75838756079ac02df4ad8c959817b28254b8e1；先前重放失败 SHA256：56b5b85be26c010474e78e04fae579454a2b5e2e6509bdf2ca0c9d64362f10f1；本轮独立重跑失败 SHA256：0819ca31d680b30acee51fbac2fedfb2f46758ca03057792c3b072f7f1d3ef3b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/swarm/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load320/swarm/seed1'
~~~

### V5 039 · v5_seed_completion/multi/load320/swarm/seed3

原失败 SHA256：8170f606de1f73fa9e9f1c1c65cd8c661e8c57aef0e6015fdacd5d9e26f2b30d；先前重放失败 SHA256：be98af1c66e41d4f1a9d46a8e30c82404be8518e75013ce1fcb94669f129bca6；本轮独立重跑失败 SHA256：e73a660702400b58b70198f6f4ee03fe0c548c4f195a6e4942e21fbda91f0043。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/swarm/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load320/swarm/seed3'
~~~

### V5 040 · v5_seed_completion/multi/load320/swarm/seed4

原失败 SHA256：7accf1e13a86b5e299bef149507b0b5a93dc4e00559a36a274cf7be8fb791461；先前重放失败 SHA256：14cf0947a236e4dd6598bed268b58b0f210c3ef86396499ef1ddeeb16a5b7f82；本轮独立重跑失败 SHA256：71050631b4cd4bce830bd5a346d93d24af72b1401c8705e1b778d5bea798a9b7。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load320/swarm/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load320/swarm/seed4'
~~~

### V5 041 · v5_seed_completion/multi/load400/HH/seed0

原失败 SHA256：cbb79432c125a007ffda557e6e781c0c616182e7549810e79d720c16f28d3a90；先前重放失败 SHA256：091535987e92b2c23cd6b30d69187d880c33dc2297f3d5f61aee0335470387c0；本轮独立重跑失败 SHA256：f582d25b64933447539fe6e46c42b305122dc28f36d8e67c8d7a57f34bc906b4。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HH/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load400/HH/seed0'
~~~

### V5 042 · v5_seed_completion/multi/load400/HH/seed3

原失败 SHA256：baff918e1e41c90912f95247644ff0e3cd5e52b7b34854cba1da21d1768149b7；先前重放失败 SHA256：0c160f80ced1c24456c8bd60cc77ed0495bbedc1d388082de3858cc5e59d85ae；本轮独立重跑失败 SHA256：96b25a5ea855def8b4043818887689c94f2398f33164570fab8bcbd9767a490e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HH/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load400/HH/seed3'
~~~

### V5 043 · v5_seed_completion/multi/load400/HH/seed4

原失败 SHA256：352ff8e90a77611dd472373920df9c1f66bf1cd99211b2167752802f66e7f886；先前重放失败 SHA256：b4fefd42bf7135903e93142cb174d9ee102fae5e9462559cf2f6f4f4f976558f；本轮独立重跑失败 SHA256：73c0ed71c9e963dcc9353f7d0f436a53762a96ce1636b13e7d032786edea79a8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HH/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load400/HH/seed4'
~~~

### V5 044 · v5_seed_completion/multi/load400/HHplus/seed0

原失败 SHA256：e79d3c4b8a9659696a6d22a9f6da4ec527b04a6e68d8855c2d04a33669fed61a；先前重放失败 SHA256：4fcd1e7250bb1418bc472dc6c114381fa993948c898b369b65eecd51e0cca156；本轮独立重跑失败 SHA256：59f8832449678edd79f0fb099c6a493b5e3f1f1bd8baab07458cf674dbac1cdc。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HHplus/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load400/HHplus/seed0'
~~~

### V5 045 · v5_seed_completion/multi/load400/HHplus/seed1

原失败 SHA256：24612f74f6756329379b7387ea9da0dae20e078ebf3c3a9766a3795fdd925873；先前重放失败 SHA256：8c686c2e423739c3e7343d4d32e45d6e92341e77d5ba46813724f6b4505de719；本轮独立重跑失败 SHA256：551f68200aeab75345fff603e0b6c16de5b651f17f86314381cc9caf3a4776d2。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HHplus/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load400/HHplus/seed1'
~~~

### V5 046 · v5_seed_completion/multi/load400/HHplus/seed2

原失败 SHA256：dc0ec0c69b32b36baa5ef1761acde4a6dc38b673fa3874e97d92ff0b27eb1d16；先前重放失败 SHA256：366c5d071a43336f7df5b6ad68d34261b2b55db93ecbea0c6eac0336397723f6；本轮独立重跑失败 SHA256：7fe9b3cad8ac53ead9c0a0193f15536f06e21a59b90db11793b108b96d19784c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HHplus/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load400/HHplus/seed2'
~~~

### V5 047 · v5_seed_completion/multi/load400/HHplus/seed3

原失败 SHA256：7370008035237ef2418bf57ae5ddf239e262fe2951a36b596f449dd71c8fbcdf；先前重放失败 SHA256：2ac45a28cc61213d224af15e84d872a0743455d0628f0543bf0a7c3659ab48cd；本轮独立重跑失败 SHA256：b36f588b4d9d56f81ddf35fb07548c11acd7085c8fd9a0046e5fc15820d7ef17。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HHplus/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load400/HHplus/seed3'
~~~

### V5 048 · v5_seed_completion/multi/load400/HHplus/seed4

原失败 SHA256：bacf67037492447d9051aba51233e69a887c8565276055cf7e91a1e3aa7aa8e6；先前重放失败 SHA256：3ad2a5fbd880b9349f15882748ee8a331d2d60fe9eedd6ac22dee2fce8b690be；本轮独立重跑失败 SHA256：4a373027983f778cdc2114499f0f6088249c790bc965a0756a74848fc58c9ddb。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/multi/load400/HHplus/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/multi/load400/HHplus/seed4'
~~~

### V5 049 · v5_seed_completion/single/load700/separate/seed0

原失败 SHA256：c4de3cd7ff2c8cb95150a2f6b467841c0836b9292cc9aaaf87e35926f75c1397；先前重放失败 SHA256：4356550043ce5485ffe77d7133f4a2ee9522a3fde00cf791213a7e6061c74874；本轮独立重跑失败 SHA256：6ee34b80aa5772fb6d0827ae21178fe79719dd90a54b56cd6bf8c89e7ff01e8c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/separate/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load700/separate/seed0'
~~~

### V5 050 · v5_seed_completion/single/load700/separate/seed1

原失败 SHA256：8bfb2adc5bb80ab7868e8c04243486793008cbed420d6429173b6b439a44a55b；先前重放失败 SHA256：7fdc6afd942a66cef2d33d668a31505dd4e7dcd3570f7dbadb49fd6f65c6a80d；本轮独立重跑失败 SHA256：d14203093754b3007a7ab1226320e1ef6f87b62fa96cadf7a643893f1c303380。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/separate/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load700/separate/seed1'
~~~

### V5 051 · v5_seed_completion/single/load700/separate/seed2

原失败 SHA256：0324e86c90159ca314452446772b46fa4e6d7a47ab599badb0e7fa35fc4c828f；先前重放失败 SHA256：55bfff1f92330ec01f357fd2e82b6917effe4f026378c5ff718a0d385486563b；本轮独立重跑失败 SHA256：3d4d1e94ec587d16c7fa454433b83d72a6d94de28f6bc6f2f0648db479f9b51f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/separate/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load700/separate/seed2'
~~~

### V5 052 · v5_seed_completion/single/load700/separate/seed3

原失败 SHA256：dd143c791ee16dffdff3c929d09b584f9ed6611b07a81e5df39913429c52c165；先前重放失败 SHA256：0f483032c65f3bb05132d3bbe0adf3c5a280fb3af77a941a5d9d9e12f466a4b0；本轮独立重跑失败 SHA256：db500de30fa821ab3637cbcad7b80eed163d7cae6b74ddea5fb6520a67b6e3cf。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/separate/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load700/separate/seed3'
~~~

### V5 053 · v5_seed_completion/single/load700/separate/seed4

原失败 SHA256：a444230581541c9d95e2464fea0376013a6fcf5079a434be615fdc80cc5b1b0e；先前重放失败 SHA256：88140d7572aacbc86a898d10a6847946698e6be7937f2d9b0900c23a35b76e3c；本轮独立重跑失败 SHA256：a5c0ebe4ae0ab514afc86797f989d2a7097d53b9cabb602ed310b83acd7d587e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/separate/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load700/separate/seed4'
~~~

### V5 054 · v5_seed_completion/single/load700/swarm/seed0

原失败 SHA256：b3519865b9d7fedbb374f7649bc85bb9cf0f032012a2b35d1a7a3796cb0e2e48；先前重放失败 SHA256：05e54c4ed82c55b14b68c6c68992c879dc58c2d5420201afaff720e6fda42094；本轮独立重跑失败 SHA256：a7be39c2e7ffe148953b911bb4afd2ad4ac403573861d6d4fcee1d51c6359fea。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/swarm/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load700/swarm/seed0'
~~~

### V5 055 · v5_seed_completion/single/load700/swarm/seed1

原失败 SHA256：f19b80be8e7fa75f2142e33723d030d6f9e1d384b4d4f4d68d47461862805347；先前重放失败 SHA256：04a6ef301fc8ac509a7b6609740c389fd1558ea8831ad63fe5da6992c074643f；本轮独立重跑失败 SHA256：f71f6f49ad9466b2657ebd0878a12713e2439e16816aac939e40096d1d9043a3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/swarm/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load700/swarm/seed1'
~~~

### V5 056 · v5_seed_completion/single/load700/swarm/seed2

原失败 SHA256：40de5ead84f4a53c4e18bd2806eca90a3998a58fdb02dc4319fa69048be0e6ee；先前重放失败 SHA256：21e68e3da79a8ee2f8354303a6f696a09d5dda21a5f5174bb9f67bb9e7be3afe；本轮独立重跑失败 SHA256：6b172183174834bbe55815e6a5ce687504250404d1477d89b60469972cf32cea。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/swarm/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load700/swarm/seed2'
~~~

### V5 057 · v5_seed_completion/single/load700/swarm/seed3

原失败 SHA256：c17fd303601badc3cc9233e095671445f5ab69c378da12d3af8e54b9da5c0bd9；先前重放失败 SHA256：7f60ce44ca9d8b4e6faa28c6324856053bde2e889d96e8a5ca4a070ccafeade7；本轮独立重跑失败 SHA256：2843b844c8e544f7b2ee2a6bf199523bc4e02ec4639dbdd90b06c0672a60f778。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/swarm/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load700/swarm/seed3'
~~~

### V5 058 · v5_seed_completion/single/load700/swarm/seed4

原失败 SHA256：7413990f1239fa47c66d7b9f752516e7d4f4f6749f5d19048ed4e4919ebb7aac；先前重放失败 SHA256：4d0095a3f1149c0ce31e7c96c109f02fd0f45c0ac671fc8e7c5b3afc2a4034d9；本轮独立重跑失败 SHA256：d94e5160fc1bde790126879fe031d192ba5369fb32e0ea4cb9b337ed2d3c9e02。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load700/swarm/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load700/swarm/seed4'
~~~

### V5 059 · v5_seed_completion/single/load900/separate/seed0

原失败 SHA256：95ba39db2784e6ef70352fc63b3cbe305a0f4dd0e4e8980bead6e31f73d0aa71；先前重放失败 SHA256：b52397b281b4bca25bd34d7a9ea0b7f2aa1389099fb7ac9dd8704e7c35d5a237；本轮独立重跑失败 SHA256：44dde630a7164a69ac9845568fafc6ae2e0f7d3a5cd66bea0ad0983029335b79。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/separate/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load900/separate/seed0'
~~~

### V5 060 · v5_seed_completion/single/load900/separate/seed1

原失败 SHA256：1995a8e843162169695cc5c68d79c6d2be21a88fb8e2fa98654681696dbb37bb；先前重放失败 SHA256：9283b7d207284a6045227271c0f5fe97112d0160f45d507d0bfdecca69c0322b；本轮独立重跑失败 SHA256：56da06078549650113c5602da516b56dff6961280faf23e6c61f9b92b9b123bf。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/separate/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load900/separate/seed1'
~~~

### V5 061 · v5_seed_completion/single/load900/separate/seed2

原失败 SHA256：a113bb302c97b1eecba170bcc32ef2ea2b9ab680c11de5f6f5458e2bf26f9c70；先前重放失败 SHA256：9c23c52f3a9592f3b255f107b6f50ee74547f23a78b5ccfdd8b51d2144e69d76；本轮独立重跑失败 SHA256：f9ff47bf3d6e1dc48ac6911692635f9e513e054133d9aa794580629201d71d8f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/separate/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load900/separate/seed2'
~~~

### V5 062 · v5_seed_completion/single/load900/separate/seed3

原失败 SHA256：01c60cea667fad692abeaadb65069c210e8d3fb1550da2986f5a3d9e38077430；先前重放失败 SHA256：64e4e8cee287f1ecf8bb66323acbc81628422b444b6520550fcffa2b8f0c30bd；本轮独立重跑失败 SHA256：644a499df451d79a4a156f620c76fd7933ef462ffded72b3317521c784fd9428。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/separate/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load900/separate/seed3'
~~~

### V5 063 · v5_seed_completion/single/load900/separate/seed4

原失败 SHA256：1b5e4d226428619b9cb35dcf98fb99d48c229e098cc635cf631953060a669000；先前重放失败 SHA256：a81c70f214cbab18efc8236f5a2636f66a94b5222eaa8a0fa3455e47272dd780；本轮独立重跑失败 SHA256：6e79cf79aaf65d3bf52ad804cf2530ff66cac5e4c05f70fcaf05fe7342fa0e14。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/separate/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load900/separate/seed4'
~~~

### V5 064 · v5_seed_completion/single/load900/swarm/seed0

原失败 SHA256：a5eba36978d1a5734a79a80b9fc6880e1df1f2337bc199b25829960121736737；先前重放失败 SHA256：64b8c610119642ad2873c65f6fb790b877deb8cae30c73a920a351d0865ef722；本轮独立重跑失败 SHA256：60c2c8cdc415b924a73c9bad34b1ffefe8cd7d93569854f9e757c97b1750dc3e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/swarm/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load900/swarm/seed0'
~~~

### V5 065 · v5_seed_completion/single/load900/swarm/seed1

原失败 SHA256：babe3ec4be5f258aed3c6a210036c707f42d0723dddde6f0ff9e539d57dca136；先前重放失败 SHA256：2945f38135188c8bbfc80fb633601df6c85339901b2213196196604883bc51a6；本轮独立重跑失败 SHA256：59458e5cba565a1800647cb13e7e5e2cd489a2c4f76139f29a22892a9df61efc。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/swarm/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load900/swarm/seed1'
~~~

### V5 066 · v5_seed_completion/single/load900/swarm/seed2

原失败 SHA256：4f0b622c58ce0b45d36a8f44e7201d442c446e47e1e479b003df61fb77a8fe20；先前重放失败 SHA256：1cc02407d683d862a4ff50978f097d7eba17498a8cc3577ec875fc2d48a1a405；本轮独立重跑失败 SHA256：6b8441082834c702751c4683e7b71f66ab767246d92782f5705c38c2ae980c7c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/swarm/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load900/swarm/seed2'
~~~

### V5 067 · v5_seed_completion/single/load900/swarm/seed3

原失败 SHA256：fd929c8616bd562b504c2d2846c4ceb56356f805bd1ee3f9a7b46a0bd2901403；先前重放失败 SHA256：14e4335bfce62e54c25092870ec7f0e131d729386c7263df7a6229bb028482ff；本轮独立重跑失败 SHA256：9fee143680074cb5e8876fa54eb89ca1133f4787e06cbfa31296fd4a8da9f4f1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/swarm/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load900/swarm/seed3'
~~~

### V5 068 · v5_seed_completion/single/load900/swarm/seed4

原失败 SHA256：be7ad4be42f13e990e070c1381924cc8e70cf562e0be67043d3ae19fc06307d1；先前重放失败 SHA256：a12e32a34ddc6bef6a8da66c4ace371e60d50e2b7048bf4abeaf6ab35f622532；本轮独立重跑失败 SHA256：9405e58add306b1eddc69d923be3d8b245f6886b7216595f7a8bd02fe77fd24a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V5' --key 'v5_seed_completion/single/load900/swarm/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V5/v5_seed_completion/single/load900/swarm/seed4'
~~~

## V6：66 个未解决键

来源：experiments/v6_completion/failure_replay/FINAL_AUDIT.json。

### V6 001 · generalization/multi/prompt2/HH/seed0

原失败 SHA256：0429bc34971313499a8b97e8622476c040a61b2ed4cde9854504d43c92d787e5；先前重放失败 SHA256：071cd5e5814ca6772c43c1d3f07840c624830863015f22417995e01d08c3bd6b；本轮独立重跑失败 SHA256：33b9615053adbaf5ebdc18053307dde6ba9aad1eb7f4fa498362f06932c74209。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HH/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/HH/seed0'
~~~

### V6 002 · generalization/multi/prompt2/HH/seed1

原失败 SHA256：7ebc28508c99728a808520739028e4d1aff657182652b016fde5c01f9af090cc；先前重放失败 SHA256：94055558f336cca0a5c9f90ed7128d88790b38fb00c3d3df7e47fd034dae7869；本轮独立重跑失败 SHA256：25a234cc130be322f3daffd00797250beb01119c23acb4dbf1aca315ec3ace51。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HH/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/HH/seed1'
~~~

### V6 003 · generalization/multi/prompt2/HH/seed2

原失败 SHA256：8425e056aa7ac2eb3ee9bc53bee5ef322dacade9f0d49a6fe49bd36b4ee1482a；先前重放失败 SHA256：e6eb5b19980c94a9e68de9ea7bc891ec0f1b6d77aa113ab293e945f454bd5d65；本轮独立重跑失败 SHA256：6f0a22141a92b7a73c28f4306ef97878555d281288cc5a65dc8e6a5edc20441a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HH/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/HH/seed2'
~~~

### V6 004 · generalization/multi/prompt2/HH/seed3

原失败 SHA256：00ae15fc7bf0ee91b51002713fb396cceb66a082eb977d427851a6ea4894ef86；先前重放失败 SHA256：2ce700a8abbbf2c9942bfe244c65e73bfa856e019401a425633d4dfde7534ba1；本轮独立重跑失败 SHA256：7a5870b44b047b2bf6b869af5d1a46b4628f40e6564689788233fa4e60f5aa8c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HH/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/HH/seed3'
~~~

### V6 005 · generalization/multi/prompt2/HH/seed4

原失败 SHA256：8620f63154658b370f1ed9652b7c5b2881a2881a10e3bfacc878eebdd03e7988；先前重放失败 SHA256：50bbb74dd82dbffb529eb7d5e46fe8ea3fa239992819fbc9eabb50f7c1afdce4；本轮独立重跑失败 SHA256：7cbe7d201c4672719862427f06e18dc2d1d376ac1da6472394ede725680274d8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HH/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/HH/seed4'
~~~

### V6 006 · generalization/multi/prompt2/HHplus/seed0

原失败 SHA256：c140cf6dfb17a171e4350e5d3aad927a23323f017f014e8e96bc9b42d7469418；先前重放失败 SHA256：b85262f63045e710bc4733426a6ff5e3a59a87809fc3a81dbe1a05744572092a；本轮独立重跑失败 SHA256：5685d09da54722e756b3d67ce18041ee63b7fe0fa3314a32d8e802be1c3d176f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HHplus/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/HHplus/seed0'
~~~

### V6 007 · generalization/multi/prompt2/HHplus/seed1

原失败 SHA256：3613cf105fc591ca937a220a77c3e0a27f36e52b1f70d153c84ae0775b9fe538；先前重放失败 SHA256：059a3203ae6b1856e848b265bb6228f950e3cf20bf367f47f222b46c6e91c96a；本轮独立重跑失败 SHA256：c79583e19fb7102abd34a763484d0f919689b095c0be2ce7dcb67b54d711f651。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HHplus/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/HHplus/seed1'
~~~

### V6 008 · generalization/multi/prompt2/HHplus/seed2

原失败 SHA256：d7f7a8e1262926becadafdb0546fa45dee3b5d118366aeae90699b78598e6eb9；先前重放失败 SHA256：7891f170ba41c5c9320861db008dcfa2162523d30050fe3f02c5cc29e5ee35a3；本轮独立重跑失败 SHA256：889e7105f9f60420c8a53a53e2c82aee41544222da1571a2d49ae6b514848d1d。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HHplus/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/HHplus/seed2'
~~~

### V6 009 · generalization/multi/prompt2/HHplus/seed3

原失败 SHA256：75bddaa979308d9e7c7ed26da463b7c4007e82adec891895ca0f814ce65d18ac；先前重放失败 SHA256：86d4c63a55be3d6d15e2cd3dcd4e1431f8161484322258c2b5ddb7be4c8cba27；本轮独立重跑失败 SHA256：c1c269df1deb4e6898648b4ab5d2e94ee8c379a9285c18b9da3aece026b729e3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HHplus/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/HHplus/seed3'
~~~

### V6 010 · generalization/multi/prompt2/HHplus/seed4

原失败 SHA256：26a4cdfd8a3104717e3c6ec4864752f1b5efa31610957bf38cbf5b786a7ba49e；先前重放失败 SHA256：2b0dcddbdd8fcb75c4cc9d5abf643dba6b63b1ea9e3f4147a61ca051d9516cc0；本轮独立重跑失败 SHA256：9d07be8efe2d521fc65c1dd7d337f20150f401315e4a1ee93b0c452b179b1b84。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/HHplus/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/HHplus/seed4'
~~~

### V6 011 · generalization/multi/prompt2/V4/seed0

原失败 SHA256：20377109b161ce0b5b13187cccb33cecc7e5d7ae090693a452dfc56e35d57e96；先前重放失败 SHA256：ff7492190fd0bd814e44fe9aec46dcf44fe7cc59a448a316b2e8132798b86f69；本轮独立重跑失败 SHA256：89ae03eb8ecf12133b815f87675ac38f334752c57bba277fb392ce8bd8775720。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/V4/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/V4/seed0'
~~~

### V6 012 · generalization/multi/prompt2/V4/seed1

原失败 SHA256：32dd93ea8bbed3e3717c2b402df6c8aea93b7c625a95341d439ae966e24a46b8；先前重放失败 SHA256：8ed2277dd6410e307afc4534026aef10148a722d3b7e8d4692a1b634f4cd0a2d；本轮独立重跑失败 SHA256：d2cb9f3acb55f5c60d813636fe7ab40de5f0fd22eba55b34e340b080ccad88ca。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/V4/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/V4/seed1'
~~~

### V6 013 · generalization/multi/prompt2/V4/seed2

原失败 SHA256：687b567611bf7c77538bbbe61967c9c436b22883a9b0b0fd599f91f5a09bdada；先前重放失败 SHA256：9acccc47aab8f07dbf060f9b2b7b7bbfc5226eea9a3a1ed9cc123026e4d8d847；本轮独立重跑失败 SHA256：61132058b3ed91cd3c529729906f16e3cb27fee68164065026bff73295aeb724。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/V4/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/V4/seed2'
~~~

### V6 014 · generalization/multi/prompt2/V4/seed3

原失败 SHA256：3d51c72a14b73bca345468645c4df33aeeabadc6a26974b75c5d8432b88a4264；先前重放失败 SHA256：f5138a5914a73b49fdba91523d78f132ee0e316919eef8289f3b3d05c98a97e2；本轮独立重跑失败 SHA256：5d88ee000888a82a98683fa04f87e17d0329f1624a2c4acaab1b6901e16f92e8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/V4/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/V4/seed3'
~~~

### V6 015 · generalization/multi/prompt2/V4/seed4

原失败 SHA256：315c6d6c4476dcbdb1022d015c294847fa9b86025ac6f1eec0920eab0642a50c；先前重放失败 SHA256：58966c081aaeb261ce27d9c603fbe928bab63357bfa5ce44af8652b167c764bc；本轮独立重跑失败 SHA256：51f7c6df7d2e11a580d918e55bd55bbbbab3aadfa6c1a59ed0bb37a8dbe86e85。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt2/V4/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt2/V4/seed4'
~~~

### V6 016 · generalization/multi/prompt4/HH/seed0

原失败 SHA256：e314f3198b50aaa129256cb6d4af219d1323d5e32adc3f59f1128940889848fe；先前重放失败 SHA256：e3f13862f4660ee3d78d86d682c83d651ecb0889a48b4ecc7eea8f4970e01c5f；本轮独立重跑失败 SHA256：024ca8b0aa096b588f1166753b450a36516654acf4d1789fc581d96a66a05ef6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HH/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/HH/seed0'
~~~

### V6 017 · generalization/multi/prompt4/HH/seed1

原失败 SHA256：7db75ef373e21eb5f7563055ba83b6b231829f7eb9fc2730aa3d278fa0b6f742；先前重放失败 SHA256：0f25382aa1af104f45c16ebcb972df5a6d8daf6c0e44187a2f734b5983b3c8e4；本轮独立重跑失败 SHA256：cbf28a9da4732ac35c4f3a05026bf7b8bbcd276876b4d23a1f86dde5eca308af。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HH/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/HH/seed1'
~~~

### V6 018 · generalization/multi/prompt4/HH/seed2

原失败 SHA256：ed5c9780127e4a6bf5c66ed3c222323f03e5101345e3f6ce6a26b8da029effe4；先前重放失败 SHA256：e83241a8bd5dfb42bac9915edaf92b98aab0a17d817f7c44e9bf464233de461f；本轮独立重跑失败 SHA256：8e1af6c0ad7203cc37b760c98c966ac7686a8816eb057b309a67d6986e1b86a6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HH/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/HH/seed2'
~~~

### V6 019 · generalization/multi/prompt4/HH/seed3

原失败 SHA256：73985b5c315e66f0e0c33a7a60675a98ef8501d541ee23926cc200372af522f0；先前重放失败 SHA256：407adb4cb476812228cfb400eda3983a7ebe68539154f3a81d6cb4d7585de076；本轮独立重跑失败 SHA256：7a0d8f0f39e67ebb7f84ab970aadbe0c4a3c58e5a998094c05d858d21283c719。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HH/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/HH/seed3'
~~~

### V6 020 · generalization/multi/prompt4/HH/seed4

原失败 SHA256：fe350a0bf388dbaa0da02dd4ea66aa2410abe6df8ac5d92cd94c2ff2f743c663；先前重放失败 SHA256：e26695503f619234d702958f8172bab08288d0d26952198eaa1d69bda06457a1；本轮独立重跑失败 SHA256：bf36f84794331a8506ac586d5774b79e2f3c091fac9584383cc962d928426e49。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HH/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/HH/seed4'
~~~

### V6 021 · generalization/multi/prompt4/HHplus/seed0

原失败 SHA256：0f68b085f21d678045565f1d08a005ab4df9febe3a66fb949269d03ceef784e0；先前重放失败 SHA256：86367cd421b01fad8d6698e429762daa07677dececac5ef67da29fbb9e46bc61；本轮独立重跑失败 SHA256：8cd5c71713bce70fd532bd26a178620e596816fbadea0a86b2049974f31c130b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HHplus/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/HHplus/seed0'
~~~

### V6 022 · generalization/multi/prompt4/HHplus/seed1

原失败 SHA256：641bef93791d31ef0244e8e52b370b2064cdfd184f666159e086ac6ae46e2d11；先前重放失败 SHA256：1af714857a8533fbcbe217efbfc3566d675fc765b0b9dd34078f43c23993df83；本轮独立重跑失败 SHA256：e41683212244c044a5333caf8f629c7cc4facb94dfe1489fb4b0a7909d8ef5e8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HHplus/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/HHplus/seed1'
~~~

### V6 023 · generalization/multi/prompt4/HHplus/seed2

原失败 SHA256：2f0681c8c933f22c2f3b2c582f063e50ff8380db0e9a838ad4679514775c067b；先前重放失败 SHA256：e7755fa4e82f78a4a8f70fd80adbec8dc88fdcdcf617e43ad198666ebab15e6b；本轮独立重跑失败 SHA256：b0bfd9eb5366dc94a46610215c0f66e5a78dfc9d7a14aa0dc0158cc0cfef496a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HHplus/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/HHplus/seed2'
~~~

### V6 024 · generalization/multi/prompt4/HHplus/seed3

原失败 SHA256：ea4a292d83757b76336035db7f914ed3124755d0b327cdcec409d2323c855991；先前重放失败 SHA256：0c022b547e5fdb98dcb00fbc7a478042e9016dcf1da8064a24026ad85f699955；本轮独立重跑失败 SHA256：ad04dcdc175ad3d1742bfd82d49a80bcacb5dec07f7581e6b6ef99d5612345d5。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HHplus/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/HHplus/seed3'
~~~

### V6 025 · generalization/multi/prompt4/HHplus/seed4

原失败 SHA256：1c47c7a2f0759667b7707c1f01860f52b2df99f368a880534f88791e6bcbd14f；先前重放失败 SHA256：59baf8dc57da9bc21394d8979a17106a6425d5a440791f94239760e1ad0a0898；本轮独立重跑失败 SHA256：d30ad40dd2ae14b796e64cc0253e259f053d31fc820d70ff3df0abe21a50fccf。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/HHplus/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/HHplus/seed4'
~~~

### V6 026 · generalization/multi/prompt4/V4/seed0

原失败 SHA256：41470592b6896b5d00eb667b92a92ccd02208ac322e923af9f0c63274950a318；先前重放失败 SHA256：f0bad9e856308c70da2d41765fe2066b030fa2e10060eb5a9950187be576d133；本轮独立重跑失败 SHA256：7d3c15b5df6902290024b8fb3740d34d1c236b0244b14d044f20a5404f8d728b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/V4/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/V4/seed0'
~~~

### V6 027 · generalization/multi/prompt4/V4/seed1

原失败 SHA256：ccd741f5c1357c75e997caf5568dfce8a7ce0773f41f4799892ae61ec1dd67fd；先前重放失败 SHA256：9f1f09d994aef002c535543a5c36389a319897a6d3e5fafce1687fffe77b4e6b；本轮独立重跑失败 SHA256：2d87fed9ae6accfe6b8236ad0152d8eb28146a698df02c0926bf3b4901361fda。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/V4/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/V4/seed1'
~~~

### V6 028 · generalization/multi/prompt4/V4/seed2

原失败 SHA256：46b9289a921799da4c3f1bf0349ed4e5628cfd1eaad14369d9dbb82c42f9ce14；先前重放失败 SHA256：e4ad6ff0662372f20f7305ce570ecce298ddbd76d122f4282a2ee3dfa2619776；本轮独立重跑失败 SHA256：e7a89b4a0d1651cfd45bf1ce2edf600884a0894c9519ae790b89e8c3be24fc48。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/V4/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/V4/seed2'
~~~

### V6 029 · generalization/multi/prompt4/V4/seed3

原失败 SHA256：ca4d64d1ec5f9bdeb3bcb8067a2aa554bb3871123a0f101467b4cd3abc6d9049；先前重放失败 SHA256：88b864817073e6343a02a63a0ca4037d9839b62796a3151ee918965aebc34c11；本轮独立重跑失败 SHA256：998edcf952ba93d7acf6e703f00ced9fa6e77b9382d9bb90c05672049fb287ae。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/V4/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/V4/seed3'
~~~

### V6 030 · generalization/multi/prompt4/V4/seed4

原失败 SHA256：53bd39612bc831a3e52f62d38474c3869a28dc26245e1f5bde6ae500c866d3b5；先前重放失败 SHA256：ec13398463a1f47e4a142ae748167a1e9af96971fcde59b3bb06deed5e2c4b15；本轮独立重跑失败 SHA256：0dda8dcc01c0e0634aa4d252b9dc8a47e428c5db75d5236d8a059a5494f019bd。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/multi/prompt4/V4/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/multi/prompt4/V4/seed4'
~~~

### V6 031 · generalization/single/output2/HH/seed0

原失败 SHA256：9aa352aabd67e95f46c95d7218658edd7bef42ec4fbc016165204c354d9f1ce1；先前重放失败 SHA256：27ae043b43eb7257c4fa51b05ae5cad40ef4f318e6e00a0955c240ed462f1358；本轮独立重跑失败 SHA256：939bc8ffd46f8bab046e2c5b0c24548e00287caa95e8926ec01d0fa392726763。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/output2/HH/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/output2/HH/seed0'
~~~

### V6 032 · generalization/single/output2/HH/seed1

原失败 SHA256：d4761839536eea2333279278c6e98a59a0d3446b2021386fbd6bfb9fbd7897f3；先前重放失败 SHA256：c79d1a91ef2ed42ac575d3372b903657f555d298214d3122f5ad21b6b504bd50；本轮独立重跑失败 SHA256：a617b73f0f31e242065c67be27ded9cf0ee5f3710467d041ab1c21553fecb69a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/output2/HH/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/output2/HH/seed1'
~~~

### V6 033 · generalization/single/output2/HH/seed2

原失败 SHA256：d2738d076a6d90a3e96ac4d80cb64362e996b7bbee35c888c3c6670dc006578d；先前重放失败 SHA256：d9a07d927a67a136232ad5a0a99b6e032650ec87f6eaeda46064390f53149ed4；本轮独立重跑失败 SHA256：4f3a398888fa2a3654a6388795a50d191a4d8cc037ee3058902717d083f9e739。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/output2/HH/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/output2/HH/seed2'
~~~

### V6 034 · generalization/single/output2/HH/seed3

原失败 SHA256：3cf46840d8426793132d75e624b96a2a4d74575fb69017f4afa7f82f946448f6；先前重放失败 SHA256：f897fa2ce965e46f8803082eeacbebbe4a20610277118df428efa050837eb4aa；本轮独立重跑失败 SHA256：3b598f5fc8c95f7749efca46b39b21d95eeb2cc5828952cae9e5ea1bbb7c3f4a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/output2/HH/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/output2/HH/seed3'
~~~

### V6 035 · generalization/single/output2/HH/seed4

原失败 SHA256：0c0752e296e9d8a88581d9d604a0dbf27fcdbc89777a12d770b6609fd30fa4d0；先前重放失败 SHA256：8e342893242f18be0b77a43cd3a28072d6452c70699d233269cb5330f28dd99b；本轮独立重跑失败 SHA256：0e0467cd2778ff57c9a2bc61e8855ffe817dd9de14c8a98b84ea47daca0e1c8a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/output2/HH/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/output2/HH/seed4'
~~~

### V6 036 · generalization/single/prompt2/HH/seed0

原失败 SHA256：eeab340ef17a79c7a1460585c4d21311161e42baa6c55f6325add879d156cf2e；先前重放失败 SHA256：d3c17ecae8e8cdaa9eedf404ee05e353fc754707f241c000eee48bd4f5cf9e8e；本轮独立重跑失败 SHA256：871104fa0d1a3e48089cf8fb38ecd86cc9592b23f572cca85643b324a4c31386。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HH/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/HH/seed0'
~~~

### V6 037 · generalization/single/prompt2/HH/seed1

原失败 SHA256：8f1d1a7120b192520e1f0ca481e6c13cfa0cdc333c840ffb7bf729fa07f1088b；先前重放失败 SHA256：0847e19a0c25a0d828d8d8d4338a967938c3fa2983eebdcd6b929781d9dc54a2；本轮独立重跑失败 SHA256：5b7f4598eba4d096ce832a3db724b015d58a05172cb38caa21984eea4f58b8a3。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HH/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/HH/seed1'
~~~

### V6 038 · generalization/single/prompt2/HH/seed2

原失败 SHA256：a1614b72e4d3c714df49f4587e7b3216d9e449d082dfb1d1c5c1c8af93dbda8b；先前重放失败 SHA256：14a50a1b6268571a2ccf4fa1a87629bf10cb9249bcec3618e4ddb3c130a47b37；本轮独立重跑失败 SHA256：865501586ad9c9c599b4f1282213fbba711a35acb34d9c23fc7a2db0ed67d1ad。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HH/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/HH/seed2'
~~~

### V6 039 · generalization/single/prompt2/HH/seed3

原失败 SHA256：d28b1fd2f7271cd6f95e4b0d86e14a28ad79c7c178f2fb64829ec1ecc2f769f4；先前重放失败 SHA256：ceba2d89f0d26bcff4025624cefc34639a2094efc21625f1a433114973b89ab4；本轮独立重跑失败 SHA256：0b0d7de39d651bf31f97b268e933e0a84c3bd043324b9b59a329070122bdbc7b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HH/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/HH/seed3'
~~~

### V6 040 · generalization/single/prompt2/HH/seed4

原失败 SHA256：46f8953420496bff99f88517e10936d1e54618056a1720b2a47a81a3892c7ecf；先前重放失败 SHA256：ed75dd510e0fc948fefadedbe94a3d6910191aac569dc5a0def73f2a9c976db9；本轮独立重跑失败 SHA256：f91e000f6ff77f4b58c808c22db1e76813d2e471bfbaba81cec26889b0f7bb07。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HH/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/HH/seed4'
~~~

### V6 041 · generalization/single/prompt2/HHplus/seed0

原失败 SHA256：68c75bdafd038b2d78d1a06874573502efba77b07a727ff203f0ba057cea4c59；先前重放失败 SHA256：affe298e20743701dd6b1a231e1ef2686e43116831451a1aab4c62f4d14709b4；本轮独立重跑失败 SHA256：e440b9df2912a8bd91b7ead614fd65b8591409f02748d269b22049b54aa92f17。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HHplus/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/HHplus/seed0'
~~~

### V6 042 · generalization/single/prompt2/HHplus/seed1

原失败 SHA256：76f9bd857a52c69058b9255ce7826d5a15adf34b15e8fd03ff7c24632abecdcc；先前重放失败 SHA256：7d436aa81095b9e5e20efd3aad4a4190273f7505dc3a158a125d966eb0762f68；本轮独立重跑失败 SHA256：8c773f5d047f6958606aacad129b52e17fc5ff78677d10355c386db56a0fdd91。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HHplus/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/HHplus/seed1'
~~~

### V6 043 · generalization/single/prompt2/HHplus/seed2

原失败 SHA256：b32f13fd7b3c6a6172ea1beb6606671043d74a54df9b96df31a4e48135aadc94；先前重放失败 SHA256：d55468749add9720c3cdf50e2d5c70d65702c64e64b105bfe72e90cee535b86a；本轮独立重跑失败 SHA256：16202975afd707d6c9ebbf2feaf0d233b63b76637ed0b928ffefa2cf6f16687a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HHplus/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/HHplus/seed2'
~~~

### V6 044 · generalization/single/prompt2/HHplus/seed3

原失败 SHA256：bde248f705682b98db8183191a00077ff068a91812c1ace4b1a4bf7c7570dba1；先前重放失败 SHA256：ee663ec3262b1495b6ebe7f7f88436e77022cafa794b2533a0cfccc3eb4572bc；本轮独立重跑失败 SHA256：5480cd17011382f9d5722b11f52d452e6e43f16a09cac7b35e9ce93948ece8e1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HHplus/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/HHplus/seed3'
~~~

### V6 045 · generalization/single/prompt2/HHplus/seed4

原失败 SHA256：88f49c23862f713e4d84849582316e4d4f54e4bfb7a8fa04031a55cbef7b9c5e；先前重放失败 SHA256：d745ad9947c127f950bf703ff672a722fb9df3b7d141a845b6f2b92dd438b3c4；本轮独立重跑失败 SHA256：22294c0937c659eb0b31381a628d9a5d3f2f2806295e1278998e8d735e078d68。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/HHplus/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/HHplus/seed4'
~~~

### V6 046 · generalization/single/prompt2/V4/seed0

原失败 SHA256：fafb91812da6b43a463faf1909949e7ef26a3626f66f5fbaf7e8322232b3c8bd；先前重放失败 SHA256：c1e4498d621ca396cbfc1226664784186637074ba5eb206122684d4d7399805f；本轮独立重跑失败 SHA256：ccfb9f17d58853092a38cfd1378fdb53b0e4e32cfa65e66d7cd54d01cc05978a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/V4/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/V4/seed0'
~~~

### V6 047 · generalization/single/prompt2/V4/seed1

原失败 SHA256：528fb27e4e4ef6e592a8725218e28b40b7bdb10995e62feb16952bcfe93ba0fb；先前重放失败 SHA256：b8a559eb0de9b56ccbad9ac0dd63b81e039e8f36ccc426806c6d7905d1d5f931；本轮独立重跑失败 SHA256：1d062bda39aa528c1a3d40b44e0caa54b1bc279ad52aebefe0c4380da5607b69。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/V4/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/V4/seed1'
~~~

### V6 048 · generalization/single/prompt2/V4/seed2

原失败 SHA256：bec26e09234eaaa495225f4e899afa6dc4100030b88288ce61720c76994ea07b；先前重放失败 SHA256：498a82f1901999ed720f350c85d48aae36aa82a75841b26699628660c5336af8；本轮独立重跑失败 SHA256：050baf10dcd675a2acbc99ec3f4ca6b69ee97ed6e1e91c0ff39c05f500ece933。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/V4/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/V4/seed2'
~~~

### V6 049 · generalization/single/prompt2/V4/seed3

原失败 SHA256：ddd0857b9779d3970e2eef64d439a2ad161ea666c2209ceb27c6c6e63eb1d2ec；先前重放失败 SHA256：bf82a44f14decac03eabb6366144b4d42f8b3bc4019280957889269f6d3bff9a；本轮独立重跑失败 SHA256：49d33495c98058806038bbc34347d9c6c959fe916202c9ecbc2995678e0e1ae0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/V4/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/V4/seed3'
~~~

### V6 050 · generalization/single/prompt2/V4/seed4

原失败 SHA256：40923a4fdcbf2f89ce28d9638d0d82a24291000053873d634fa99b3b712eb33c；先前重放失败 SHA256：5d76af3a55c30f4e012a00b9872fc8f16d52dc85bfef3587ccbdbb45c0ee6e54；本轮独立重跑失败 SHA256：89f451f5685054b0ac8fd6fb41722c27ee1fb857c552a09d2d31976fb8da3064。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt2/V4/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt2/V4/seed4'
~~~

### V6 051 · generalization/single/prompt4/HH/seed0

原失败 SHA256：2041bfa97a33e9dbfe77cc11baa6f2a5aa279e779cf6eeaa3ae1eb2b91282feb；先前重放失败 SHA256：b8335504efd521d2b64a862e672284f59b826ce40552e5749f8e86ec2645fec3；本轮独立重跑失败 SHA256：9fc0184b1dbc15fc8ce7bd3e5e9131f5c122ca2f651d8805997d9b59e5d5d07e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HH/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/HH/seed0'
~~~

### V6 052 · generalization/single/prompt4/HH/seed1

原失败 SHA256：6e4d379a3826bfe026a88eff85d43d1440c22963bcb99e522b38cec1569cbc25；先前重放失败 SHA256：d31991400578a7cea2a577b13da9f74cfdba32adb5bcadad46dfeac8611076c8；本轮独立重跑失败 SHA256：2daece46e622cb82e404dd0530549abf04dbcffd2bd88f9c3efd15b6dfadc06f。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HH/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/HH/seed1'
~~~

### V6 053 · generalization/single/prompt4/HH/seed2

原失败 SHA256：ceef65511ebf1dcbc383bfd4b589328e3e2d43767c264a619a4a84d871606ed3；先前重放失败 SHA256：106f19d9dcb4451af10d83e422459da5910ec3a819f172dc5e758be0535a904c；本轮独立重跑失败 SHA256：575e867b2e2d9646f1a5f8897164553db9c5c1262dbffaa36c0fdeeebc9df69c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HH/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/HH/seed2'
~~~

### V6 054 · generalization/single/prompt4/HH/seed3

原失败 SHA256：18c126909d34179b6ca89316d7912bd3ad526a0f0831ab5f38a90a6f76aff0ea；先前重放失败 SHA256：b6ec8d4a076927a19e00a7edcc63486124ca586db69b840b119caae398d6e81a；本轮独立重跑失败 SHA256：30887e00874928d078553ffd7943699564eeb6363280555a566854eb2d65727a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HH/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/HH/seed3'
~~~

### V6 055 · generalization/single/prompt4/HH/seed4

原失败 SHA256：b30a396972279d601e8fd26dad11436f4d6282a1f7691c2f00b3a5ab539a7287；先前重放失败 SHA256：0ba1de0aa27305a3ebed8d6f156654b029debb0bcfc10470e6b284f6c7c5d163；本轮独立重跑失败 SHA256：a9caff797dec1bfaeef10d7766bc97e1a0d11f9ac3c4803a8e084cfb4dc7e34b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HH/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/HH/seed4'
~~~

### V6 056 · generalization/single/prompt4/HHplus/seed0

原失败 SHA256：cd60888a84f40a98fab4f2bde17a91be5eb1ac74d405337ec74555b43640a45e；先前重放失败 SHA256：fd3dd86e645667a7c9c56c9ad7e1e5c3fb9ce44943cf8439b561bef50bab617c；本轮独立重跑失败 SHA256：2e12e61a1bc82f4856efdb42b19a139be651e87fa4c867664d16c4ed3001036b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HHplus/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/HHplus/seed0'
~~~

### V6 057 · generalization/single/prompt4/HHplus/seed1

原失败 SHA256：dab9bc2f99b8d1eb426163be61ae71f4680704d8e28459091303a32184d10547；先前重放失败 SHA256：3091d9f3a8280906bbc62ca1acdd41894b08681045df44dbbae03d67eaa2aede；本轮独立重跑失败 SHA256：694c999ac88f32268ee1b624ed7a85834ea5942d364c44504eec9305411ecf6b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HHplus/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/HHplus/seed1'
~~~

### V6 058 · generalization/single/prompt4/HHplus/seed2

原失败 SHA256：f2b3349990ac28c9de71017d7a376b9a09d76dad6fb32995b56bc9dcbcc8c86d；先前重放失败 SHA256：0b800a1ac8f039e56398f59373b717e082b8bc2138880f48a0af08978605efab；本轮独立重跑失败 SHA256：c5391f04d84218505f7665a32c743e2519dabc3a3d9b4c574a2187bc6a5c4e8a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HHplus/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/HHplus/seed2'
~~~

### V6 059 · generalization/single/prompt4/HHplus/seed3

原失败 SHA256：5108eb2a296524e80d708b0955b609f9d126f34c6c2e01ad9544aed47c569b15；先前重放失败 SHA256：72e4ce80855a65b2ca42345f25f19fe5b44efe2b4ebb6b4f433697c7962eff40；本轮独立重跑失败 SHA256：8a9158adb26eb713dcd6bd43d5a53ec537f3a85cf4ff9e19c6403c7e5dc2733e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HHplus/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/HHplus/seed3'
~~~

### V6 060 · generalization/single/prompt4/HHplus/seed4

原失败 SHA256：7c4454f0fc22de018c782851e7b9d497fd7a66983c71fb9d44bdc2c03d84b38a；先前重放失败 SHA256：268a460edba552c6a07bc35d3171e9bfe5dd30822f09a1a863de9825d707286e；本轮独立重跑失败 SHA256：9bce97758877b8d46864ea380f5d19952ea365e86ebe8c99c26f46f93a054b6b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/HHplus/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/HHplus/seed4'
~~~

### V6 061 · generalization/single/prompt4/V4/seed0

原失败 SHA256：292739139c7fb7f2c6a995445a15a6ab8d2ce61690dad66b2165a62296203e77；先前重放失败 SHA256：9abcd3e616b6b4949682b28c762a20f6ea1c01ca9fea8d0fef30462572081c06；本轮独立重跑失败 SHA256：463797cf4151eb66e4373a2e1d19bcc178a56dd3cfc7af0ce67f0981029e4866。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/V4/seed0' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/V4/seed0'
~~~

### V6 062 · generalization/single/prompt4/V4/seed1

原失败 SHA256：8c019cbeecf06d7666ec2d046f4a19b79a637d85e3da96b4926a39354c2c02f8；先前重放失败 SHA256：47699f2624d40c94db56f417fe3d85d3e85e8e819d671ef16885cdf302475d02；本轮独立重跑失败 SHA256：04ee23a636dde44bb6e2de57411b5df97810c4c82e4892929eccd2f4ebe45509。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/V4/seed1' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/V4/seed1'
~~~

### V6 063 · generalization/single/prompt4/V4/seed2

原失败 SHA256：4ba8db17959765b1eb15368e93de61d9f072888061f9aec944551ef975401bae；先前重放失败 SHA256：25dc5355a981db936d9e4a65409963d0f5cd77b5d54a41767c6831bb87a5c7f6；本轮独立重跑失败 SHA256：86b9abbb4075ae5220a269f099d8937787648a3e1088cf17af5f72fcdf8b4cb1。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/V4/seed2' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/V4/seed2'
~~~

### V6 064 · generalization/single/prompt4/V4/seed3

原失败 SHA256：42027d3fe73ce981c95efcc1e80b40026216e52edb95c51f63342dfd37e1b874；先前重放失败 SHA256：998bb8f6cdf66af97d0b2da684cbf24d30cefe0b113b305c96f50280b82459e3；本轮独立重跑失败 SHA256：42226432eed33760917a460c9250fa1b08dd9ac3f883502d6aafa9a66070ee9b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/V4/seed3' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/V4/seed3'
~~~

### V6 065 · generalization/single/prompt4/V4/seed4

原失败 SHA256：b35a4c0e232967cd2d44df239a299dd626b8a031ba857ad27c8c4162f4b767eb；先前重放失败 SHA256：2646552cfd5d6dc37750176db78aaa9a1e96268556ee1a66ed5ac2baf4cc417e；本轮独立重跑失败 SHA256：ede2ded6f62b238df9b63a16152efd8d1ad3dcb23960ac896cc0bedf211e6e06。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'generalization/single/prompt4/V4/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/generalization/single/prompt4/V4/seed4'
~~~

### V6 066 · robustness/multi/activation_kv_high20/HHplus/seed4

原失败 SHA256：da9cdc7472a41afa67b7ea3bf560b7b7423495e11fdbae13873d349838f1efe7；先前重放失败 SHA256：325f280bcce16773b367dfd993cc3bdc737a34d8e3c151b099ef79ab97cb50b8；本轮独立重跑失败 SHA256：a45cf70ba462c34b554cf94f9e8db8868239d4127612c8e2e18a08c64ba6a52c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.manual_rerun --group 'V6' --key 'robustness/multi/activation_kv_high20/HHplus/seed4' --output 'experiments/manual_reruns_after_auto_20261101/V6/robustness/multi/activation_kv_high20/HHplus/seed4'
~~~

## E6：4 个独立重放后仍失败键

E6 原正式 47/60、独立重放 9/13；下面四键仍失败。两批结果分别审计，不合并正式成功率。

### E6 001 · multi/load160/Q4/seed1

原正式失败 SHA256：6308ae6ca7c43695f1a50f77bd453673310866995d844fc0a2d218fdb47663be；独立重放失败 SHA256：7a92c6e5f08bd693b653a7b0cc76366de20dfd4f9670095b91fd63959bcb74cc。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.E6_cumulative.manual_rerun --key 'multi/load160/Q4/seed1' --output 'experiments/manual_e6_reruns_after_replay_20261101/multi/load160/Q4/seed1'
~~~

### E6 002 · multi/load320/Q4/seed2

原正式失败 SHA256：c86bd0f2f67dad2e814ee621d5baa01748c9aaaedb1f62ea46ad0d010e9005e2；独立重放失败 SHA256：42ec35bdd578c64305ff07dcbfcc3f6204d2a082c7d7b5b8d26917577e4f1b10。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.E6_cumulative.manual_rerun --key 'multi/load320/Q4/seed2' --output 'experiments/manual_e6_reruns_after_replay_20261101/multi/load320/Q4/seed2'
~~~

### E6 003 · single/load700/Q4/seed4

原正式失败 SHA256：f815abccf725206a40ffed1e9c9fabcd79639e254f9eb18270bcf6c4501ef44d；独立重放失败 SHA256：b7d2b6a1cd805e6ed807dd3803369e2f8160bc029f52ed604a59e12edad455d8。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.E6_cumulative.manual_rerun --key 'single/load700/Q4/seed4' --output 'experiments/manual_e6_reruns_after_replay_20261101/single/load700/Q4/seed4'
~~~

### E6 004 · single/load700/R2/seed4

原正式失败 SHA256：20f9dc607e28e449e37eb6b78cc94c5c05756977b34c4995caed92206bdfab03；独立重放失败 SHA256：30621bc5ad331dda030ff608e12612aaa673e492fc09f81367f3adf61cc73940。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }
python -u -m experiments.reviewer_v2.E6_cumulative.manual_rerun --key 'single/load700/R2/seed4' --output 'experiments/manual_e6_reruns_after_replay_20261101/single/load700/R2/seed4'
~~~

