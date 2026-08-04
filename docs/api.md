# API

すべての保護対象APIは`X-API-Key`ヘッダーを必要とします。

## 画像送信

`POST /api/v1/observations`

`multipart/form-data`フィールド:

- `device_id`: 1〜24の整数。カメラごとに一意
- `location_id`: 省略可能な1〜12の整数。同じ会場のカメラで共通。省略時は`device_id`と同じ
- `zone_name`: 省略可能な100文字以内の撮影区域名
- `room_name`: 1〜100文字、改行不可
- `image`: 最大5 MiBのJPEGまたはPNG

成功時はHTTP 202を返します。

```json
{
  "accepted": true,
  "device_id": 1,
  "location_id": 1,
  "queue_depth": 1
}
```

例:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/observations \
  -H 'X-API-Key: development-key-1234' \
  -F 'device_id=7' \
  -F 'location_id=3' \
  -F 'zone_name=左側' \
  -F 'room_name=大体育館' \
  -F 'image=@capture.jpg;type=image/jpeg'
```

既存エッジとの互換性のため、`location_id`と`zone_name`を送らない場合は従来どおり1デバイスを1会場として処理します。

## 最新スナップショット

`GET /api/v1/rooms/snapshot`

```json
{
  "generated_at": "2026-07-16T01:02:04Z",
  "rooms": [
    {
      "id": 3,
      "location_id": 3,
      "room_name": "大体育館",
      "person_count": 11,
      "observed_at": "2026-07-16T01:02:03Z",
      "camera_status": "ok",
      "device_count": 2,
      "active_device_count": 2,
      "configuration_consistent": true,
      "devices": [
        {
          "id": 7,
          "zone_name": "左側",
          "person_count": 5,
          "observed_at": "2026-07-16T01:02:01Z",
          "status": "ok"
        },
        {
          "id": 8,
          "zone_name": "右側",
          "person_count": 6,
          "observed_at": "2026-07-16T01:02:03Z",
          "status": "ok"
        }
      ]
    }
  ]
}
```

`camera_status`は、全カメラが有効なら`ok`、一部だけ有効なら`partial`、すべて停止判定なら`offline`です。停止判定されたカメラの古い人数は会場合計から除外します。全カメラ停止時の`person_count`は`null`です。

## ヘルスチェック

`GET /health`は認証不要です。検出器種別、キューの現在件数、上限を返します。インターネットへ直接公開せず、リバースプロキシや監視ネットワークからのみ利用してください。
