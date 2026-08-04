# YOLO人数カウントの校正

`runtime/yolo-calibration/input`に評価画像を置き、正解人数を`runtime/yolo-calibration/manifest.csv`へ記録します。画像は個人情報を含む可能性があるため、リポジトリへ追加しません。

マニフェストはUTF-8のCSVで、次の2列を必須とします。

```csv
filename,expected_count
DSC02505.JPG,0
DSC02372.JPG,4
```

リポジトリ直下からPBSジョブを投入します。稼働中のバックエンドとは別にGPUを1枚要求するため、PBSによるGPU分離が有効ならバックエンドを停止する必要はありません。

```bash
JOB_ID=$(qsub \
  -v "CROWDED_DEPLOY_ROOT=${CROWDED_DEPLOY_ROOT}" \
  deploy/pbs/yolo-calibration.pbs)
echo "${JOB_ID}"
```

ジョブ完了後、結果を確認します。

```bash
cat \
  "${CROWDED_DEPLOY_ROOT}/runtime/yolo-calibration/output/results-${JOB_ID}.csv"
```

CSVには正解人数、検出人数、符号付き誤差、絶対誤差、画像ごとの処理時間を記録します。標準出力には完全一致数、平均絶対誤差、平均の符号付き誤差、最大絶対誤差も表示します。

既定値は本番バックエンドと同じ信頼度0.35、YOLO入力サイズ640です。比較試験だけ一時的に変更する場合は、ジョブ投入時に`CROWDED_CALIBRATION_CONFIDENCE`または`CROWDED_CALIBRATION_IMAGE_SIZE`を渡します。本番設定は評価結果を確認してから別途変更します。
