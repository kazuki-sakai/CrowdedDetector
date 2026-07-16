<?php
declare(strict_types=1);

final class CongestionLevel
{
    /** @return array<int, array{moderate: int, crowded: int}> */
    public static function readThresholds(string $path): array
    {
        $handle = fopen($path, 'r');
        if ($handle === false) {
            throw new RuntimeException('混雑基準CSVを読み込めません。');
        }
        try {
            $header = fgetcsv($handle);
            if ($header !== ['id', 'moderate_threshold', 'crowded_threshold']) {
                throw new RuntimeException('混雑基準CSVのヘッダーが不正です。');
            }
            $thresholds = [];
            while (($row = fgetcsv($handle)) !== false) {
                if (count($row) !== 3) {
                    continue;
                }
                $id = filter_var($row[0], FILTER_VALIDATE_INT);
                $moderate = filter_var($row[1], FILTER_VALIDATE_INT);
                $crowded = filter_var($row[2], FILTER_VALIDATE_INT);
                if ($id === false || $moderate === false || $crowded === false || $moderate < 0 || $crowded <= $moderate) {
                    throw new RuntimeException('混雑基準CSVに不正な値があります。');
                }
                $thresholds[$id] = ['moderate' => $moderate, 'crowded' => $crowded];
            }
            return $thresholds;
        } finally {
            fclose($handle);
        }
    }

    /** @param array{moderate: int, crowded: int}|null $threshold */
    public static function classify(?int $count, ?array $threshold): array
    {
        if ($count === null || $threshold === null) {
            return ['label' => '情報なし', 'class' => 'unknown'];
        }
        if ($count < $threshold['moderate']) {
            return ['label' => '空いている', 'class' => 'open'];
        }
        if ($count < $threshold['crowded']) {
            return ['label' => 'やや混雑', 'class' => 'moderate'];
        }
        return ['label' => '混雑', 'class' => 'crowded'];
    }
}

