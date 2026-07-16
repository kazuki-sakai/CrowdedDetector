# CrowdedDetector

オープンキャンパスの校内自由見学で、各会場の推定人数と混雑度を表示するシステムです。

## 構成

- `edge/`: Raspberry Pi 3BとUSB Webカメラで定期撮影し、画像を送信
- `backend/`: FastAPIで画像を受信し、人物検出結果をロック付きCSVへ記録
- `frontend/`: バックエンドのJSONを最大5秒キャッシュし、PHPで混雑度を表示
- `docs/`: API、構成、導入方法の詳細

最大デバイスIDは1〜12です。バックエンドは初期状態では接続確認用の`mock`検出器を使い、人数を0人として記録します。実運用時に`yolo`へ切り替えます。

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

`config.php`のバックエンドURLとAPIキーを設定し、WebサーバのDocumentRootを`frontend/public`へ向けます。`frontend/var/cache`はPHP実行ユーザーが書き込める必要があります。

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

## テスト

外部パッケージを導入していない状態でも、CSVと設定読込の単体テストを実行できます。

```bash
PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -v
PYTHONPATH=edge/src python3 -m unittest discover -s edge/tests -v
```

FastAPIを含むAPI結合テストまで実行する場合は、`scripts/setup-backend.sh --dev`で開発依存を導入してから同じバックエンドテストを実行します。

詳細は[構成](docs/architecture.md)、[API](docs/api.md)、[導入](docs/deployment.md)を参照してください。
