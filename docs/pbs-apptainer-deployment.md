# PBS・Apptainerによるバックエンド構築

## 1. 採用する構成

NginxとPBS実行ノードが常に同一ホストであるため、次の構成にします。

```text
公式PHPサーバ / Raspberry Pi
            |
         HTTP/80
            |
   同一ホスト上のNginx
            |
      127.0.0.1:8000
            |
 PBSジョブ内のApptainer + Uvicorn
            |
       GPU 1枚 + CSV
```

NginxはホストOSの常駐サービスとして動かし、FastAPIだけをPBSジョブにします。Uvicornはホストのループバックアドレスだけで待ち受けるため、8000番を学内ネットワークへ公開する必要はありません。

現行バックエンドは、プロセス内に1個の処理キューと1個の推論器を持ちます。そのため、Uvicornのworker数は必ず1とし、まずGPU 1枚で運用します。

## 2. 事前確認

実行ノードで次を確認します。

```bash
hostname
apptainer --version
nvidia-smi
qstat --version
```

PBSサイトによって、GPU要求の書式、キュー名、環境変数の渡し方は異なります。本リポジトリのジョブファイルは次を前提にしています。

```text
#PBS -q gpu
#PBS -l select=1:ncpus=4:ngpus=1:mem=16gb
```

異なる場合は、管理者から指定された書式へ`deploy/pbs/crowded-backend.pbs`のPBSディレクティブだけを変更します。

ホストのNVIDIAドライバがCUDA 12.4を利用できること、PBSが割り当てたGPUだけを`CUDA_VISIBLE_DEVICES`へ設定すること、Apptainerの`--nv`が許可されていることも確認します。

## 3. 配置ディレクトリの準備

以下では、実行ノードから見える永続領域を`/shared/crowded-detector`とします。実際のパスが異なる場合は読み替えます。

```bash
export CROWDED_DEPLOY_ROOT=/shared/crowded-detector

mkdir -p \
  "${CROWDED_DEPLOY_ROOT}/source" \
  "${CROWDED_DEPLOY_ROOT}/containers" \
  "${CROWDED_DEPLOY_ROOT}/models" \
  "${CROWDED_DEPLOY_ROOT}/runtime/data" \
  "${CROWDED_DEPLOY_ROOT}/runtime/cache" \
  "${CROWDED_DEPLOY_ROOT}/secrets"

chmod 700 \
  "${CROWDED_DEPLOY_ROOT}/runtime" \
  "${CROWDED_DEPLOY_ROOT}/secrets"
```

リポジトリを次の位置へcloneまたはコピーします。

```text
/shared/crowded-detector/source/CrowdedDetector
```

以降はリポジトリ直下へ移動します。

```bash
cd "${CROWDED_DEPLOY_ROOT}/source/CrowdedDetector"
```

## 4. Apptainerイメージのビルド

`deploy/apptainer/crowded-backend.def`は、提示されたイメージと同じ
`pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime`を直接使用します。JupyterLabや開発用エディタは入れず、FastAPI、Uvicorn、Pillow、Ultralytics YOLOと、OpenCVの実行に必要なOSライブラリだけを追加します。

提示された定義ファイルから既に作成済みのSIFを親イメージとして再利用する場合は、`crowded-backend.def`の先頭2行だけを次のように置き換えます。`From`にはbuildホストから読める実際の絶対パスを指定し、以降のセクションは変更しません。

```text
Bootstrap: localimage
From: /shared/path/to/pytorch-2.5.1-cuda12.4.sif
```

直接Dockerイメージからbuildする方式は依存関係を明確にでき、既存SIFを使う方式は同じ基盤の再取得を省けます。どちらで作成しても、以降のPBS実行方法は同じです。

定義ファイルの`%files`はリポジトリ直下を基準にしているため、必ずリポジトリ直下でbuildします。

```bash
apptainer build --fakeroot \
  "${CROWDED_DEPLOY_ROOT}/containers/crowded-backend.sif" \
  deploy/apptainer/crowded-backend.def
```

サイトで`--fakeroot`が使えない場合は、管理者が許可したリモートビルド、rootビルド、または専用ビルドホストを使用します。DockerイメージとPythonパッケージを取得するため、初回build時は外向き通信も必要です。

ビルド後に、まずGPUを使わないimport確認を行います。

```bash
apptainer exec \
  "${CROWDED_DEPLOY_ROOT}/containers/crowded-backend.sif" \
  python -c "import crowded_backend, torch, ultralytics; print(torch.__version__); print(torch.version.cuda)"
```

次に、必ずPBSでGPUを割り当てた対話ジョブ内でGPU認識を確認します。要求書式はサイトに合わせます。

```bash
qsub -I -q gpu \
  -l select=1:ncpus=4:ngpus=1:mem=16gb \
  -l walltime=00:30:00
```

対話ジョブが開始したら実行します。

```bash
apptainer exec --cleanenv --nv \
  "${CROWDED_DEPLOY_ROOT}/containers/crowded-backend.sif" \
  python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.device_count()); print(torch.cuda.get_device_name(0))"
```

期待値は`True`、`1`、割り当てられたGPU名です。`device_count()`が4になる場合は、他ジョブとの競合を防げていないため、運用を開始せずPBS管理者へGPU隔離設定を確認します。

## 5. 実行設定の作成

設定雛形を、リポジトリ外の非公開ディレクトリへコピーします。

```bash
cp backend/config/backend.apptainer.example.env \
  "${CROWDED_DEPLOY_ROOT}/secrets/backend.env"
chmod 600 "${CROWDED_DEPLOY_ROOT}/secrets/backend.env"
```

APIキーを生成します。表示された値を`CROWDED_API_KEY`へ設定し、エッジ端末とPHPの非公開設定にも同じ値を設定します。

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
vi "${CROWDED_DEPLOY_ROOT}/secrets/backend.env"
```

最初の結合試験では次を使用します。

```text
CROWDED_DETECTOR=random
CROWDED_RANDOM_MIN_COUNT=0
CROWDED_RANDOM_MAX_COUNT=30
```

会場とカメラの上限、停止判定は次を使用します。デバイスIDはカメラごと、会場IDは表示場所ごとに割り当てます。

```text
CROWDED_MAX_DEVICES=24
CROWDED_MAX_LOCATIONS=12
CROWDED_DEVICE_STALE_SECONDS=35
```

コンテナ内のパスは次のままにします。PBSジョブがホスト側の永続領域をbind mountします。

```text
CROWDED_DATA_DIR=/data
CROWDED_YOLO_MODEL=/models/yolo11n.pt
TORCH_HOME=/cache/torch
YOLO_CONFIG_DIR=/cache/ultralytics
```

設定値に空白を含めず、`KEY=value`形式で1行ずつ記述します。APIキーをリポジトリ、SIF、PBSスクリプト、ジョブログへ直接書かないでください。

## 6. YOLOモデルの準備

本番切替前に、モデルを永続領域へ配置します。計算ノード上での自動ダウンロードには依存しません。

既にモデルを持っている場合はコピーします。

```bash
cp /path/to/yolo11n.pt "${CROWDED_DEPLOY_ROOT}/models/yolo11n.pt"
chmod 644 "${CROWDED_DEPLOY_ROOT}/models/yolo11n.pt"
```

外向き通信が可能なログインノードで取得する場合は、次のようにコンテナを利用できます。

```bash
apptainer exec \
  --bind "${CROWDED_DEPLOY_ROOT}/models:/models" \
  --pwd /models \
  "${CROWDED_DEPLOY_ROOT}/containers/crowded-backend.sif" \
  python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"
```

配置を確認します。

```bash
test -r "${CROWDED_DEPLOY_ROOT}/models/yolo11n.pt"
sha256sum "${CROWDED_DEPLOY_ROOT}/models/yolo11n.pt"
```

ハッシュ値はモデル更新の記録として保存しておきます。

## 7. CSV領域の初期化

バックエンド自身も初回起動時に必要なファイルを作成しますが、事前に準備して権限を確認できます。

```bash
scripts/initialize-data.sh "${CROWDED_DEPLOY_ROOT}/runtime/data"
chmod -R u+rwX,go-rwx "${CROWDED_DEPLOY_ROOT}/runtime"
```

既に試験データや本番データがある場合、このディレクトリを消したり上書きしたりしないでください。SIFを再ビルドしても、bind mountされたCSVは保持されます。

## 8. ホスト側サービスとNginxの確認

同じ8000番を使うsystemd版バックエンドが動いている場合は停止します。

```bash
sudo systemctl disable --now crowded-backend
ss -ltnp | grep ':8000'
```

2行目が何も表示しなければ、8000番は空いています。Nginxは停止せず、既存の設定をそのまま使用します。

Nginxのupstreamは次である必要があります。`proxy_pass`の末尾に`/`を付けません。

```nginx
proxy_pass http://127.0.0.1:8000;
```

また、`server_name`には実際にフロントエンドとエッジが指定するHost名、またはアクセス先IPを含めます。8000/tcpは外部へ許可せず、80/tcpだけを必要な送信元ネットワークへ許可します。

## 9. PBSジョブの投入

`deploy/pbs/crowded-backend.pbs`のキュー名、GPU資源指定、walltimeをサイトに合わせて確認します。オープンキャンパスの開始前から終了後までを覆うwalltimeに、起動確認と片付けの余裕を加えます。

リポジトリ直下から投入します。

```bash
qsub \
  -v CROWDED_DEPLOY_ROOT="${CROWDED_DEPLOY_ROOT}" \
  deploy/pbs/crowded-backend.pbs
```

返されたジョブIDを記録し、状態と出力を確認します。

```bash
JOB_ID="qsubが返したジョブID"
qstat -u "$USER"
qstat -f "${JOB_ID}"
tail -f \
  "${CROWDED_DEPLOY_ROOT}/runtime/logs/crowded-backend-${JOB_ID}.log"
```

サイトのPBS設定によっては、`crowded-backend.oJOB_NUMBER`がジョブ終了時まで作成されません。ジョブスクリプトはPBS標準出力と同じ内容を上記のジョブ専用ログへ開始直後から記録するため、実行中の監視にはこちらを使用します。ログは所有者だけが読み書きできるモード600で作成し、APIキーや受信画像は記録しません。

ジョブ出力には次が表示されます。

- コンテナ設定の検査結果
- `CUDA available: True`
- `Visible GPU count: 1`
- `YOLO warm-up complete`（YOLOモードの場合）
- `Uvicorn running on http://127.0.0.1:8000`を含むUvicornの起動ログ

PBSジョブはUvicornをforegroundで実行します。ジョブ内で`nohup`、`&`、systemdを使用しません。

## 10. ランダム人数での結合試験

まずバックエンドホスト内から直接確認します。

```bash
curl --fail --silent http://127.0.0.1:8000/health |
  python3 -m json.tool
```

`detector`が`random`、`queue_depth`が0なら起動しています。

次にNginx経由で確認します。`crowded-api.internal`は実際のHost名へ置き換えます。

```bash
curl --fail --silent \
  -H 'Host: crowded-api.internal' \
  http://127.0.0.1/health |
  python3 -m json.tool
```

snapshotはAPIキーが必要です。

```bash
read -rsp 'API key: ' CROWDED_API_KEY
echo

curl --fail --show-error \
  -H 'Host: crowded-api.internal' \
  -H "X-API-Key: ${CROWDED_API_KEY}" \
  http://127.0.0.1/api/v1/rooms/snapshot |
  python3 -m json.tool
```

続いて、Raspberry Piから画像を送ってPHP画面まで確認します。詳細は`docs/random-edge-test.md`に従います。

CSVはホスト側で確認できます。

```bash
find "${CROWDED_DEPLOY_ROOT}/runtime/data" -maxdepth 2 -type f -print
tail -n 10 "${CROWDED_DEPLOY_ROOT}/runtime/data/each/crowded_01.csv"
```

## 11. YOLOへの切替

切替時の未処理画像消失を避けるため、先に全エッジの送信を停止します。`/health`の`queue_depth`が0になるまで待ちます。

```bash
curl --fail --silent http://127.0.0.1:8000/health |
  python3 -m json.tool
```

ジョブを終了します。

```bash
qdel JOB_ID
```

ジョブが消え、8000番が空いたことを確認します。

```bash
qstat -u "$USER"
ss -ltnp | grep ':8000'
```

秘密設定を編集します。

```bash
vi "${CROWDED_DEPLOY_ROOT}/secrets/backend.env"
```

次の値へ変更します。

```text
CROWDED_DETECTOR=yolo
CROWDED_YOLO_MODEL=/models/yolo11n.pt
CROWDED_YOLO_DEVICE=0
CROWDED_YOLO_CONFIDENCE=0.35
```

ここでの`0`は、PBSがコンテナへ見せた1枚のGPUの論理番号です。ホストの物理GPU番号を直接指定しません。

同じコマンドでジョブを再投入し、`/health`の`detector`が`yolo`であることを確認してからエッジ送信を再開します。

## 12. 通常停止と再起動

通常停止時も、エッジ停止、`queue_depth=0`確認、`qdel`の順にします。現行キューはメモリ上にあるため、キューに画像が残った状態でジョブを停止すると、その画像は失われます。

SIFを更新する場合は、別名でbuildしてimport・GPU試験を終えてから、停止時間中にPBSスクリプトが参照するイメージを切り替えます。実行中のSIFを上書きしないでください。

## 13. PBS運用上の注意

- キュー待ち時間は保証されません。イベント本番は事前予約または開始前に十分な余裕を持ったジョブ投入を行います。
- walltime到達時は強制終了されます。開催時間全体と準備・撤収時間を含む値にします。
- 同じホストでも、既存systemdサービスや二重投入ジョブが8000番を奪う可能性があります。ジョブファイルはロックとポート検査で二重起動を拒否します。
- NginxはPBSジョブ停止中に`502 Bad Gateway`を返します。フロントエンド側の取得失敗表示が機能することも事前確認します。
- `CUDA_VISIBLE_DEVICES`が未設定、またはコンテナから複数GPUが見える場合、ジョブファイルは起動を中止します。
- CSV、履歴、キャッシュはSIF外の永続領域へ置きます。SIFは読み取り専用で運用します。
- 実行中のログは`runtime/logs/crowded-backend-<PBS_JOBID>.log`で確認します。ジョブごとに別ファイルになるため、イベント終了後に不要な古いログを整理します。
- 共有ファイルシステムで`flock`と同一ディレクトリ内の`os.replace`が正しく動作することを結合試験で確認します。
- HTTP通信ではAPIキーと画像が平文です。学内限定、送信元IP制限、8000番非公開を維持します。
- 開催前に、12台相当の10秒間隔送信を数時間継続し、`queue_depth`、GPUメモリ、処理時間、CSV増加量、Nginx/PBSログを確認します。
