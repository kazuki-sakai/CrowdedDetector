<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/src/BackendClient.php';
require_once dirname(__DIR__) . '/src/CongestionLevel.php';

$configPath = dirname(__DIR__) . '/config/config.php';
$config = is_file($configPath) ? require $configPath : [
    'backend_url' => getenv('CROWDED_BACKEND_URL') ?: 'http://127.0.0.1:8000/api/v1/rooms/snapshot',
    'api_key' => getenv('CROWDED_API_KEY') ?: '',
    'backend_timeout_seconds' => 3,
];

$snapshot = ['rooms' => []];
$thresholds = [];
$pageError = null;
try {
    $backend = new BackendClient(
        $config['backend_url'],
        $config['api_key'],
        (int) $config['backend_timeout_seconds'],
    );
    $snapshot = $backend->fetchSnapshot();
    $thresholds = CongestionLevel::readThresholds(dirname(__DIR__) . '/config/ID_condition.csv');
} catch (Throwable $error) {
    $pageError = $error->getMessage();
}

function crowdedEscape(mixed $value): string
{
    return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function crowdedFormatObservedTime(?string $value): string
{
    if ($value === null || $value === '') {
        return '未取得';
    }
    try {
        return (new DateTimeImmutable($value))
            ->setTimezone(new DateTimeZone('Asia/Tokyo'))
            ->format('H:i:s');
    } catch (Throwable) {
        return '不明';
    }
}
?>
<!doctype html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>校内混雑状況</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
<main>
    <header class="page-header">
        <div>
            <p class="eyebrow">OPEN CAMPUS</p>
            <h1>校内混雑状況</h1>
            <p class="subtitle">各見学場所の現在の目安です。移動や見学順の参考にしてください。</p>
        </div>
        <button type="button" onclick="location.reload()">最新情報に更新</button>
    </header>

    <?php if ($pageError !== null): ?>
        <div class="notice error" role="alert">
            現在、混雑状況を取得できません。時間をおいて再度お試しください。
        </div>
    <?php endif; ?>

    <section class="legend" aria-label="混雑度の凡例">
        <span><i class="dot open"></i>空いている</span>
        <span><i class="dot moderate"></i>やや混雑</span>
        <span><i class="dot crowded"></i>混雑</span>
        <span><i class="dot unknown"></i>情報なし</span>
    </section>

    <section class="room-grid" aria-live="polite">
        <?php foreach ($snapshot['rooms'] as $room):
            $id = (int) ($room['id'] ?? 0);
            $count = isset($room['person_count']) ? (int) $room['person_count'] : null;
            $level = CongestionLevel::classify($count, $thresholds[$id] ?? null);
        ?>
            <article class="room-card <?= crowdedEscape($level['class']) ?>">
                <div class="room-card-top">
                    <span class="room-id">ID <?= crowdedEscape($id) ?></span>
                    <span class="status"><?= crowdedEscape($level['label']) ?></span>
                </div>
                <h2><?= crowdedEscape($room['room_name'] ?? '名称未設定') ?></h2>
                <p class="count">
                    <?php if ($count === null): ?>—<small>人</small><?php else: ?>
                        <?= crowdedEscape($count) ?><small>人</small>
                    <?php endif; ?>
                </p>
                <p class="observed">観測 <?= crowdedEscape(crowdedFormatObservedTime($room['observed_at'] ?? null)) ?></p>
            </article>
        <?php endforeach; ?>
    </section>

    <?php if (count($snapshot['rooms']) === 0 && $pageError === null): ?>
        <p class="empty">観測データはまだありません。</p>
    <?php endif; ?>

    <footer>
        <p>画面は10秒ごとに更新されます。人数は画像認識による推定値です。</p>
    </footer>
</main>
<script src="assets/app.js"></script>
</body>
</html>
