# Raspberry Piの個別設定

ゴールデンSDはユーザー`nnct-pi`、リポジトリ`/home/nnct-pi/CrowdedDetector`、無効化した`crowded-edge.service`、共通のバックエンド・カメラ設定を持つものとします。複製後に端末ごとのID、会場、区域、ホスト名だけを個別設定します。

ホスト名はデバイスIDから`nnct-oc-rp-XX`形式で生成します。ID 1のゴールデンSDは`nnct-oc-rp-01`です。複製直後はホスト名が重複するため、複数の未設定端末を同時にネットワークへ接続せず、1台ずつ個別設定します。

## 直接指定

まず変更内容だけを確認します。

```bash
sudo /home/nnct-pi/CrowdedDetector/edge/.venv/bin/crowded-edge-provision \
  --device-id 13 \
  --location-id 3 \
  --room-name "大体育館" \
  --zone-name "左側" \
  --dry-run
```

内容が正しければ`--dry-run`を外して実行します。既定ではサービスを停止・無効のままにします。

## 設置台帳CSV

`edge/config/devices.example.csv`をリポジトリ外へコピーし、全端末を一意なデバイスIDで登録します。

```csv
device_id,location_id,room_name,zone_name
1,1,情報工学科実習室,
13,3,大体育館,左側
14,3,大体育館,右側
```

CSVから対象IDを選ぶ場合は次を実行します。

```bash
sudo /home/nnct-pi/CrowdedDetector/edge/.venv/bin/crowded-edge-provision \
  --device-id 13 \
  --inventory /path/to/devices.csv \
  --dry-run
```

スクリプトは既存`device.ini`のバックエンドURL、APIキー、タイムアウト、カメラ設定を保持し、次を更新します。

- デバイスID、会場ID、部屋名、区域名
- `/etc/hostname`相当のsystemdホスト名
- `/etc/hosts`の`127.0.1.1`
- `nnct-pi`と現在のリポジトリを参照するsystemdユニット
- 設定ファイルの所有者と権限
- Avahiの有効化

設定後に再起動し、`.local`名でSSH接続、設定読込、カメラ、バックエンド送信を確認します。本番当日までサービスを無効にする場合は`--enable-service`を指定しません。
