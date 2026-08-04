# CrowdedDetector

オープンキャンパスの校内自由見学で、各会場の推定人数と混雑度を表示するシステムです。

## 構成

- `edge/`: Raspberry Pi 3BとUSB Webカメラで定期撮影し、画像を送信
- `backend/`: FastAPIで画像を受信し、人物検出結果をロック付きCSVへ記録
- `frontend/`: PHPからバックエンドの最新JSONを取得し、混雑度を表示
- `docs/`: API、構成、導入方法の詳細

会場IDは1〜12、デバイスIDは1〜24を既定範囲とします。1会場を複数カメラで分割撮影する場合は、各カメラへ一意なデバイスIDと共通の会場IDを設定し、バックエンドが有効なカメラの人数を合算します。バックエンドは初期状態では接続確認用の`mock`検出器を使い、人数を0人として記録します。エッジ・Nginx・フロントエンドの結合試験には`random`検出器を利用でき、実運用時に`yolo`へ切り替えます。

## 開発環境での起動

### バックエンド

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp config/backend.example.env config/backend.env
set -a
. config/backend.env
set +a
uvicorn crowded_backend.main:app --host 127.0.0.1 --port 8000 --workers 1
```

`backend.env`の`CROWDED_DATA_DIR`は、開発時には絶対パスまたは`data`へ変更してください。API仕様は起動後の`http://127.0.0.1:8000/docs`でも確認できます。

### エッジ

Raspberry PiでOSのカメラ認識を確認してから実行します。

```bash
sudo apt install python3-venv python3-opencv
cd edge
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp config/device.example.ini config/device.ini
crowded-edge --config config/device.ini --once
```

通常運転では`--once`を外します。`device.ini`には設置場所ごとのID、部屋名、URL、APIキーを設定します。

Raspberry Pi OSではARM向けOpenCVをOSパッケージから利用します。64-bit OS等でPyPIのOpenCV wheelを使う場合は、代わりに`python -m pip install -e '.[camera-wheel]'`を実行できます。

### フロントエンド

```bash
cp frontend/config/config.example.php frontend/config/config.php
```

`config.php`のバックエンドURLとAPIキーを設定し、WebサーバのDocumentRootを`frontend/public`へ向けます。フロントエンドはキャッシュファイルを作成せず、ページ要求ごとにバックエンドからJSONを取得します。

## ランダム人数による結合テスト

YOLOを導入する前に、画像受信ごとに0～30人のランダムな人数を保存できます。

```text
CROWDED_DETECTOR=random
CROWDED_RANDOM_MIN_COUNT=0
CROWDED_RANDOM_MAX_COUNT=30
```

エッジ端末、Nginx、バックエンド、フロントエンドを通した詳しい確認方法は[ランダム人数によるエッジ結合テスト](docs/random-edge-test.md)を参照してください。

## YOLOの有効化

UbuntuバックエンドでNVIDIAドライバと対応するPyTorch/CUDA環境を準備した後、次を実行します。

```bash
cd backend
. .venv/bin/activate
python -m pip install -r requirements-yolo.txt
```

環境設定を次のように変更して再起動します。

```text
CROWDED_DETECTOR=yolo
CROWDED_YOLO_MODEL=yolo11n.pt
CROWDED_YOLO_DEVICE=0
```

まずGPU 1枚で実測し、処理待ちが継続的に増える場合にのみGPU増設・ワーカー分割を検討してください。現実装はメモリキューを使用するため、Uvicornは`--workers 1`で起動します。

PBSでGPUを割り当て、Apptainer内でバックエンドを運転する本番構築手順は[PBS・Apptainerによるバックエンド構築](docs/pbs-apptainer-deployment.md)を参照してください。バックエンド専用の定義ファイルは`deploy/apptainer/crowded-backend.def`、ジョブ雛形は`deploy/pbs/crowded-backend.pbs`です。

## テスト

外部パッケージを導入していない状態でも、CSVと設定読込の単体テストを実行できます。

```bash
PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -v
PYTHONPATH=edge/src python3 -m unittest discover -s edge/tests -v
```

FastAPIを含むAPI結合テストまで実行する場合は、`scripts/setup-backend.sh --dev`で開発依存を導入してから同じバックエンドテストを実行します。

詳細は[構成](docs/architecture.md)、[API](docs/api.md)、[導入](docs/deployment.md)を参照してください。
