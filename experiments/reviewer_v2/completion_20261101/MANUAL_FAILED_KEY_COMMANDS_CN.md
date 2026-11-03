# RCAPS 补全实验剩余失败键手工命令

这些命令只用于新增独立诊断目录；成功也不能回填正式五种子组。
每个键执行前都会核对原正式失败、最近独立失败和审计 SHA256。
已有输出目录会拒绝覆盖。每条命令均需要在 PowerShell 中单独运行。

## E5A：19 键

### E5a/load1800/Helix+/seed2

正式失败 SHA256：bfc75474e7e0ca860b25f453d9581ac3f3b29bd14166ea32c9033c6b4f37811b；最新独立失败 SHA256：d18dd01d822dd74acf52c801187681bbe91e4160f3bf591463d32a4cf4b37c7d。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load1800/Helix+/seed2' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load1800/Helix+/seed2'
~~~

### E5a/load1800/Helix+/seed3

正式失败 SHA256：4552235766da56427617095f1e8c8190a4bdd3687591c0a523f00418e6493ccf；最新独立失败 SHA256：b80c1f27bf23ce3f9024376c3c7d609f4461bb3dd33ea6565dacba7ab8d793d6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load1800/Helix+/seed3' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load1800/Helix+/seed3'
~~~

### E5a/load1800/Helix+/seed4

正式失败 SHA256：7a3b18abdc041b3b09d5d06d3109d0a86d07aed4956cfcd8eff8f14ccf8e1df7；最新独立失败 SHA256：7e57b4b213184398788e518bfd713d5dd581615f9606200041308603d6fbc06b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load1800/Helix+/seed4' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load1800/Helix+/seed4'
~~~

### E5a/load1800/Helix/seed2

正式失败 SHA256：ebc72b3655d44cad7ed50bdc17e3e7c862ce0f0d0f802cabb1aeaa0540e59aa2；最新独立失败 SHA256：68a2b8b0ae955ef483f543900dc3cbfc3f3f5941391f97e0a5f9781f0c6310ac。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load1800/Helix/seed2' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load1800/Helix/seed2'
~~~

### E5a/load1800/Helix/seed3

正式失败 SHA256：15f04407554ba7e5f78eac4d26d96add2fe616389cdc9ee6ca842841c2cdeba4；最新独立失败 SHA256：052cc39fd6de6f491404f1f37e6aac83014a1e3faa32415df452d9575dffd770。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load1800/Helix/seed3' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load1800/Helix/seed3'
~~~

### E5a/load1800/Helix/seed4

正式失败 SHA256：9bd4e015e35e45892d5218ace175654d272933e7c6093f294c79eb12179f6ec0；最新独立失败 SHA256：b0afc142fc25fb31965f9cbed6407eb46fe16d4ca07a14400c75042b6b6ad916。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load1800/Helix/seed4' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load1800/Helix/seed4'
~~~

### E5a/load2150/Helix/seed1

正式失败 SHA256：1319b819f8c43a1f390710991efe8c05fdc25a1a52f2cc25329ed28b594d7e8c；最新独立失败 SHA256：7100bd6b1f68b6fd641c09a595505148255fe4eed8f75276da000fa3efb63fb5。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/Helix/seed1' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/Helix/seed1'
~~~

### E5a/load2150/Helix/seed2

正式失败 SHA256：af5d77db581092bc3c9933fb90367af2deabfd0e4e598a3e7fc8c11747f49a7b；最新独立失败 SHA256：b696a310fecfde9385d601e82c063a30c23d864bc5cae25f04a7dc2351ac74ad。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/Helix/seed2' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/Helix/seed2'
~~~

### E5a/load2150/Helix/seed3

正式失败 SHA256：2b0290b5c16502a66af72227fc358e1882b439224aa5bb23c060b43ea0071201；最新独立失败 SHA256：04c6c8a627641065b24748d726bf5f90e397c034463ebe91a32c6edddbe49c33。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/Helix/seed3' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/Helix/seed3'
~~~

### E5a/load2150/RCAPS-KV/seed0

正式失败 SHA256：cb1a2058565581f6982f6ee25bf544c3700d20082f4f0f0fd382e7297cf0dbc6；最新独立失败 SHA256：4507929feb97fd3c7bf09bbd5e54f0f01fc023a6b6c310acf654f260394c554e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/RCAPS-KV/seed0' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/RCAPS-KV/seed0'
~~~

### E5a/load2150/RCAPS-KV/seed1

正式失败 SHA256：7d4032fd3a36ac158100352d95a87ecc3cfec04df2493162f123261e284d0345；最新独立失败 SHA256：1445171b253ff0501bf95c49c0d610554c51d93a8612ca9c705c508105f04f29。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/RCAPS-KV/seed1' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/RCAPS-KV/seed1'
~~~

### E5a/load2150/RCAPS-KV/seed2

正式失败 SHA256：eb9271f9464cf7301ea2f3f37ff7137ffdf70f8a0560f4692bf328cf3c3def0b；最新独立失败 SHA256：233a1ae093ec653937fb563f1e43949c55ba705e4238080015dc6af65fdda343。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/RCAPS-KV/seed2' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/RCAPS-KV/seed2'
~~~

### E5a/load2150/RCAPS-KV/seed3

正式失败 SHA256：83cd4617a6ad321104ca3a9239a95d4cf80048aa8290a61d89d5efe36bed280a；最新独立失败 SHA256：85942c7b1fd6f8fd282802bd952d9350cf020eba0b51d027121ac22fb83bb592。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/RCAPS-KV/seed3' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/RCAPS-KV/seed3'
~~~

### E5a/load2150/RCAPS-KV/seed4

正式失败 SHA256：bd9a675eb20fcdd2df0fe0e6e1e33500f97da5018654d0817f9e68f3fef44006；最新独立失败 SHA256：e240388a532fabd1a68c442011a4f83e75725def756d72e1ae93bc12ca45c109。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/RCAPS-KV/seed4' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/RCAPS-KV/seed4'
~~~

### E5a/load2150/RCAPS/seed0

正式失败 SHA256：86d5a4e2af77333d6885846aa077901ea78ec27fc98662a8ad1a08e704c23e91；最新独立失败 SHA256：4b5e2c117d03e93641cf44b445a54d437f70f6447c04faddefb0c1d6c84863ce。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/RCAPS/seed0' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/RCAPS/seed0'
~~~

### E5a/load2150/RCAPS/seed1

正式失败 SHA256：70ee41ca51ffd1416db3b20312b704cf77786acdca7ba90e25112a64929d42f8；最新独立失败 SHA256：e46e39159fcf39ccbbacf8b21289596d616798712c2f7f840303910da0297476。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/RCAPS/seed1' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/RCAPS/seed1'
~~~

### E5a/load2150/RCAPS/seed2

正式失败 SHA256：e76abad7b0d77fee7db24d278683dc0048715cc5113e7c3849dbf6964ca023a7；最新独立失败 SHA256：9bc7a1c46170b827163ef8b98e3c574271bf6632b63a9c3377195226a57ff23b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/RCAPS/seed2' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/RCAPS/seed2'
~~~

### E5a/load2150/RCAPS/seed3

正式失败 SHA256：803297dc43c8963f0b411d503a003def9ee1aa8f8a30283a687f4497aa83f8d4；最新独立失败 SHA256：c6b540dbafd4c89c2412e3259901081ad9542b843beacdc3c842771876e1e1ec。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/RCAPS/seed3' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/RCAPS/seed3'
~~~

### E5a/load2150/RCAPS/seed4

正式失败 SHA256：13757e56a26dd9b62e8bf2b8bb35c0fde9e4d6d3793ed439aaa650e82d9c0221；最新独立失败 SHA256：7d25d53165d3005322d793a84a5218eb232b550d75a9f64e7febd609a1dce7a9。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e5a' --key 'E5a/load2150/RCAPS/seed4' --output 'experiments/manual_completion_after_audited_replay_20261103/e5a/E5a/load2150/RCAPS/seed4'
~~~

## E6：1 键

### single/load350/S3/seed3

正式失败 SHA256：355de57c50d161ff6aeaa056027d105be2a8a3da912122a720ed45c00d912bf1；最新独立失败 SHA256：f87017b4000c1d76a8a735afc6cbc2a339d2446d54cf1944f8bbac652b736001。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'e6' --key 'single/load350/S3/seed3' --output 'experiments/manual_completion_after_audited_replay_20261103/e6/single/load350/S3/seed3'
~~~

## MILP：22 键

### multi/load160/official/seed1

正式失败 SHA256：0da25d0c57500e2ac8dc3fc093278a12f319ef1476a086afbc3ea4d416d31838；最新独立失败 SHA256：b763578350ea344f77d0ba02f6d5562a3e247e7e3d7530d036a4171333961680。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'multi/load160/official/seed1' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/multi/load160/official/seed1'
~~~

### multi/load160/official/seed2

正式失败 SHA256：9ec32a0157016b843f54dcfddbcae228d8aa7a5a24b76f354bad39210a9304ab；最新独立失败 SHA256：bf703f4716c0317c0fafa815c370d035f77d12e030882aff1433acc18a6a032b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'multi/load160/official/seed2' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/multi/load160/official/seed2'
~~~

### multi/load320/480/seed0

正式失败 SHA256：d702641daa1b72619931ade118f9bbcac9346c5e94244d3ae19237db5551be0b；最新独立失败 SHA256：0b3452b31554418df173e50b49047c6bbf8d9c26bbc1d2a9afbb4de6fa6c21d6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'multi/load320/480/seed0' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/multi/load320/480/seed0'
~~~

### multi/load320/480/seed1

正式失败 SHA256：8ac46d74df4416823dcb1ea00ce6beae16f8a0a093456c8250b832049a57cbdc；最新独立失败 SHA256：317ccc9de8d0870b997c352a9ffada148c4691af15c775c6c2286241aae269c7。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'multi/load320/480/seed1' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/multi/load320/480/seed1'
~~~

### multi/load320/480/seed2

正式失败 SHA256：6e80afcaefa8d8b37be66e92f2da87567fdf83003dc9382c2f6cf617d63c4a9b；最新独立失败 SHA256：dc813aadf291aacffef0d6618dcde503340bf8c99432d8f7fbe6e39253946161。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'multi/load320/480/seed2' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/multi/load320/480/seed2'
~~~

### multi/load320/480/seed3

正式失败 SHA256：95c23ad7b203719c72589984226480c68de7fcf1143429e38610e3f25f200580；最新独立失败 SHA256：87d8d335d9b3170479053072cd8520a5ba1bc283af18780bd7304df33403a69e。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'multi/load320/480/seed3' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/multi/load320/480/seed3'
~~~

### multi/load320/480/seed4

正式失败 SHA256：70207202641117b1546e011084a0c2bd7e4cd781cd25aa1c4c67aaf9a650a6fb；最新独立失败 SHA256：16700b0abb46c4bacf3ef0e0900709dc10cc8f3718a49d9c4f7bd9438fabe471。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'multi/load320/480/seed4' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/multi/load320/480/seed4'
~~~

### single/load350/480/seed2

正式失败 SHA256：b946af6ff4090100974f1e8569fc6c93ff300a6d7049170f3b7f1a1f1d81b0f6；最新独立失败 SHA256：fc8ac9f0da3122c954cc8c46ac7d97dd02defdb2a70ccc8be19ecd3a067b2df0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load350/480/seed2' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load350/480/seed2'
~~~

### single/load350/480/seed4

正式失败 SHA256：ec30bccddcce7ab4b109023dd0e28dbb9326257d0376fb021146902444dfc0f8；最新独立失败 SHA256：42a381de48c2cb6e786be52c5d52440e4eefe19b7a78b0d1470b0ab63766bab6。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load350/480/seed4' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load350/480/seed4'
~~~

### single/load700/120/seed0

正式失败 SHA256：44192e641e43a1fbb8ad7e8c283c5aeda9f5aec76454c41084265bbbe7ca8974；最新独立失败 SHA256：8351c3c254b15d4051636e3fbed8cd76f339254d3320085b1e59515747bcaa43。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/120/seed0' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/120/seed0'
~~~

### single/load700/120/seed1

正式失败 SHA256：1b77b7840d8d6e0986229209d2d417704aa5338e35958ed0ce8c2684dab0a0fa；最新独立失败 SHA256：62ef2a5745e948c878d93db05a130fbeaac49c86777440d63a74cffe264c54d0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/120/seed1' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/120/seed1'
~~~

### single/load700/120/seed2

正式失败 SHA256：9fd9de751fb3d7d3a074b5ec3ba97da56c92041cc740d9df93719fb2fe86b69c；最新独立失败 SHA256：5b1591c9e2af7197c24c90004520594a684358ea13f651222cdc59b9bed2536a。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/120/seed2' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/120/seed2'
~~~

### single/load700/120/seed3

正式失败 SHA256：f6e7c388cd1ba4b2d3112e809400588b178063fc09218f538b46366a504722af；最新独立失败 SHA256：9d77edd71f771d8920513057093f0a12f2ba64236a8c688563beb82c9d183314。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/120/seed3' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/120/seed3'
~~~

### single/load700/120/seed4

正式失败 SHA256：e93e7ab82ffd4ca3eadaa9d545069b36c04331b641a295ea9f08e8f9804ae659；最新独立失败 SHA256：49b7da30845a0630d95ca983feb7650d605fdc5d077e5eae5c1b9ed53d00a83b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/120/seed4' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/120/seed4'
~~~

### single/load700/480/seed0

正式失败 SHA256：868e2bfc42bce4d8016993df0181f3db85300b90f684aba6a4981de6c7f3f43a；最新独立失败 SHA256：0f463e2693d16bc8d39d0069f89662c75d257d4e2f2edd07cff6857ff726a126。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/480/seed0' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/480/seed0'
~~~

### single/load700/480/seed1

正式失败 SHA256：45a06e9879cc5972344c836d94ae621ac46d7dfa829c58c3810a76c72e943efa；最新独立失败 SHA256：ec3a1061f560106430ac1bea9a8aeee5e88423ec7d81de309a735d3a197c3e2c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/480/seed1' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/480/seed1'
~~~

### single/load700/480/seed2

正式失败 SHA256：e2a628ae27587ccb871845398d3f9497ae14c67f4d0f7534e8e958f80c5c9c15；最新独立失败 SHA256：fc7f77576763ab6e349587d97d0cce8268a901596197362cc042ec615605ac9b。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/480/seed2' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/480/seed2'
~~~

### single/load700/480/seed3

正式失败 SHA256：b2a6114e85e324e9850fdd90ee89f47c08485035f6f6badfbda2d72f2509d85b；最新独立失败 SHA256：3781bd1b33ab66ea0ef0f6409831e1054b9ecc2465c703bed464b1cb362eb139。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/480/seed3' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/480/seed3'
~~~

### single/load700/480/seed4

正式失败 SHA256：1ce1df5ec98ca959a114cb07318474aef756ecd238f7f8c3a0bfe0486d6f7b0f；最新独立失败 SHA256：7be5dc4650eb0fb1e016e659c798a8c15e4302ddf32292262cfdac1bb2079fd0。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/480/seed4' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/480/seed4'
~~~

### single/load700/official/seed0

正式失败 SHA256：3d2dadb145c1dd5f47c1f2602fa21946909d53acc2f8b14e241a8023374bc5bd；最新独立失败 SHA256：d23596144e50df034983696c3cd85209936ef3c9244e71467b6b987c407b618d。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/official/seed0' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/official/seed0'
~~~

### single/load700/official/seed1

正式失败 SHA256：a6de85d5264759f7218dfad641d29e7a56d2650b282998ad27649045dfd62dc4；最新独立失败 SHA256：0f5460a055a54995a892a160efce1607c547fbc47275c3856926455127ba9a61。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/official/seed1' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/official/seed1'
~~~

### single/load700/official/seed2

正式失败 SHA256：d78f12b0cd564cb3722308a5f43c5bf552d7f50f2e12c9470f864205c382187f；最新独立失败 SHA256：5ab0271931977d212ee7a67d86205ca6bc656fb0ab6844489473f1f103cc7a5c。

~~~powershell
$ErrorActionPreference = 'Stop'
Set-Location 'D:/PythonProject/Helix-GREEN'
. 'D:/software/miniconda/shell/condabin/conda-hook.ps1'
conda activate gllm
python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign 'milp' --key 'single/load700/official/seed2' --output 'experiments/manual_completion_after_audited_replay_20261103/milp/single/load700/official/seed2'
~~~
