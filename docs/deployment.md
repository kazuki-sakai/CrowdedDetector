# 導入と運用

## バックエンド

Ubuntu 22.04上で専用ユーザーを作り、アプリケーションを`/opt/crowded-detector`、実データを`/var/lib/crowded-detector`、秘密設定を`/etc/crowded-detector/backend.env`へ配置する想定です。

`backend/systemd/crowded-backend.service`はUvicornを`127.0.0.1:8000`で起動します。NginxまたはApacheを前段に置き、HTTPSを終端してください。サービスファイルのユーザー名とパスは実環境に合わせて調整します。

APIキーは十分に長いランダム値にし、エッジとPHPだけへ配布します。設定ファイルをWeb公開ディレクトリに置かないでください。

## エッジ

Raspberry Pi OSで`python3-opencv`を導入し、仮想環境を`--system-site-packages`付きで作成します。USBカメラが`/dev/video0`として認識され、サービスユーザーが`video`グループに所属していることを確認します。`edge/systemd/crowded-edge.service`のパスを調整し、実設定は`/etc/crowded-detector/device.ini`へ置きます。

同じIDを複数台へ設定すると、部屋名と履歴が交互に更新されるため禁止します。設置台帳でデバイスID、端末、部屋名を管理してください。

## フロントエンド

DocumentRootは`frontend/public`だけに向け、`frontend/config`と`frontend/var`を直接公開しないでください。PHP実行ユーザーには`frontend/var/cache`への書込権限を与えます。バックエンド取得にはPHPのHTTPSストリームを使うため、`allow_url_fopen`を有効にします。

本番ではフロントエンドからバックエンドへの名前解決、HTTPS証明書検証、ファイアウォール許可を事前確認してください。

## 運用前確認

- 全エッジのIDが1〜12の範囲で重複していない
- 部屋名変更時に`backup`へ旧履歴が作成される
- 画像がバックエンドのディスクへ保存されていない
- バックエンド停止時にフロントエンドが古い情報であることを表示する
- 会場ごとの誤検出率を確認してYOLO信頼度と混雑閾値を調整する
- ログに画像やAPIキーが記録されない
- 端末時刻がNTPで同期されている
