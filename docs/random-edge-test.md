# ランダム人数によるエッジ結合テスト

YOLOを導入せず、Raspberry Piから画像を受信するたびにランダムな人数を記録して、Nginx、FastAPI、CSV、PHP表示までを確認する手順です。

## 1. バックエンド設定

実際にsystemdが読む`/etc/crowded-detector/backend.env`を編集します。

```text
CROWDED_DETECTOR=random
CROWDED_RANDOM_MIN_COUNT=0
CROWDED_RANDOM_MAX_COUNT=30
```

`CROWDED_RANDOM_SEED`は通常は設定しません。同じ疑似乱数列を再現したい試験だけ、次のように整数を設定します。

```text
CROWDED_RANDOM_SEED=12345
```

バックエンドを再起動します。

```bash
sudo systemctl restart crowded-backend
sudo systemctl status crowded-backend
```

ローカルで確認します。

```bash
curl --fail --silent http://127.0.0.1:8000/health |
  python3 -m json.tool
```

`detector`が`random`なら設定が反映されています。

## 2. Nginxで画像POSTを許可

`EDGE_NETWORK`をRaspberry PiのIPまたはカメラ用ネットワークへ置き換えます。例は`10.20.30.0/24`です。

```nginx
location = /api/v1/observations {
    allow 127.0.0.1;
    allow EDGE_NETWORK;
    deny all;

    client_max_body_size 8m;

    # 末尾に / を付けない
    proxy_pass http://127.0.0.1:8000;

    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-API-Key $http_x_api_key;

    proxy_connect_timeout 3s;
    proxy_send_timeout 30s;
    proxy_read_timeout 60s;
}
```

設定を検査して反映します。

```bash
sudo nginx -t
sudo systemctl reload nginx
```

UFWでもエッジネットワークからのTCP/80だけを許可します。

```bash
sudo ufw allow proto tcp from 10.20.30.0/24 to any port 80
sudo ufw status numbered
```

Nginxの`server_name`には、エッジがURLに使用するホスト名またはバックエンドIPを含めます。

```nginx
server_name crowded-api.internal 10.20.30.40;
```

内部DNSがない場合は、Raspberry Piの`/etc/hosts`へ次のように登録できます。

```text
10.20.30.40 crowded-api.internal
```

## 3. エッジ端末からHTTP疎通確認

Raspberry Piから80番へ接続できることを確認します。

```bash
nc -vz -w 5 crowded-api.internal 80
curl --verbose --connect-timeout 5 http://crowded-api.internal/health
```

403の場合、NginxまたはUFWが認識している送信元IPを確認します。

```bash
sudo tail -n 50 /var/log/nginx/access.log
```

## 4. 疑似JPEGでPOST確認

`random`検出器は画像内容を解析しませんが、受付APIはJPEGまたはPNGの識別子を検査します。次のファイルはこの試験専用です。

```bash
printf '\xff\xd8\xffmock-image' > /tmp/crowded-mock.jpg
```

APIキーを対話入力します。

```bash
read -rsp 'API key: ' CROWDED_API_KEY
echo
```

画像を送信します。

```bash
curl --include \
  -X POST \
  -H "X-API-Key: ${CROWDED_API_KEY}" \
  -F 'device_id=1' \
  -F 'room_name=エッジ送信テスト会場' \
  -F 'image=@/tmp/crowded-mock.jpg;type=image/jpeg' \
  http://crowded-api.internal/api/v1/observations
```

正常時は`202 Accepted`が返ります。推論・CSV更新は非同期なので、1秒程度待ってからsnapshotを確認します。

```bash
sleep 1
curl --fail --silent \
  -H "X-API-Key: ${CROWDED_API_KEY}" \
  http://crowded-api.internal/api/v1/rooms/snapshot |
  python3 -m json.tool
```

ID 1の`person_count`が0～30の範囲なら正常です。POSTを数回繰り返すと値が変化します。

## 5. Raspberry Piの設定

必要パッケージと仮想環境を準備します。

```bash
sudo apt install python3-venv python3-opencv
cd /path/to/CrowdedDetector/edge
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp config/device.example.ini config/device.ini
```

`config/device.ini`を編集します。

```ini
[device]
id = 1
room_name = 情報工学科実習室

[backend]
url = http://crowded-api.internal/api/v1/observations
token = バックエンドと同じAPIキー
timeout_seconds = 20
verify_tls = true

[camera]
device = 0
interval_seconds = 10
width = 1280
height = 720
jpeg_quality = 85
```

HTTPでは`verify_tls`は使用されません。

1回だけ撮影・送信します。

```bash
crowded-edge --config config/device.ini --once
```

成功したら連続運転します。

```bash
crowded-edge --config config/device.ini
```

停止は`Ctrl+C`です。systemdで運転する場合は`edge/systemd/crowded-edge.service`を実環境のパスへ合わせます。

## 6. 結果確認

バックエンドで履歴を確認します。

```bash
tail -n 10 /var/lib/crowded-detector/each/crowded_01.csv
```

約10秒ごとに時刻と0～30の人数が追加されます。既定の混雑閾値が10、20の場合、PHP画面では次の3段階を確認できます。

- 0～9人: 空いている
- 10～19人: やや混雑
- 20～30人: 混雑

## 7. 主なエラー

- HTTP 401: APIキーが一致していない。
- HTTP 403: NginxまたはUFWの送信元許可にエッジIPがない。
- HTTP 404: `server_name`不一致、または画像POSTのlocationがまだ`return 404`になっている。
- HTTP 413: Nginxの`client_max_body_size`が小さい。
- HTTP 415: JPEG/PNG以外、または画像識別子が不正。
- HTTP 422: デバイスIDが1～12の範囲外、または部屋名が不正。
- HTTP 503: 処理キューが満杯。
- 202だが更新されない: `journalctl -u crowded-backend`でワーカーエラーを確認する。
- カメラを開けない: `/dev/video0`、`video`グループ、OpenCVの導入を確認する。
