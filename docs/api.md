# API

すべての保護対象APIは`X-API-Key`ヘッダーを必要とします。

## 画像送信

`POST /api/v1/observations`

`multipart/form-data`フィールド:

- `device_id`: 1〜12の整数
- `room_name`: 1〜100文字、改行不可
- `image`: 最大5 MiBのJPEGまたはPNG

成功時はHTTP 202を返します。

```json
{
  "accepted": true,
  "device_id": 1,
  "queue_depth": 1
}
```

例:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/observations \
  -H 'X-API-Key: development-key-1234' \
  -F 'device_id=1' \
  -F 'room_name=情報工学科実習室' \
  -F 'image=@capture.jpg;type=image/jpeg'
```

## 最新スナップショット

`GET /api/v1/rooms/snapshot`

```json
{
  "generated_at": "2026-07-16T01:02:04Z",
  "rooms": [
    {
      "id": 1,
      "room_name": "情報工学科実習室",
      "person_count": 7,
      "observed_at": "2026-07-16T01:02:03Z"
    }
  ]
}
```

## ヘルスチェック

`GET /health`は認証不要です。検出器種別、キューの現在件数、上限を返します。インターネットへ直接公開せず、リバースプロキシや監視ネットワークからのみ利用してください。
