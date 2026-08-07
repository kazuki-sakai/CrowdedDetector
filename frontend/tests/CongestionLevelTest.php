<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/src/CongestionLevel.php';

$cases = [
    [null, '—'],
    [-1, '—'],
    [0, '0〜5人'],
    [4, '0〜5人'],
    [5, '5〜10人'],
    [9, '5〜10人'],
    [10, '10〜20人'],
    [19, '10〜20人'],
    [20, '20〜30人'],
    [29, '20〜30人'],
    [30, '30人以上'],
    [100, '30人以上'],
];

foreach ($cases as [$count, $expected]) {
    $actual = CongestionLevel::formatCountRange($count);
    if ($actual !== $expected) {
        throw new RuntimeException(
            sprintf(
                'count=%s: expected %s, got %s',
                var_export($count, true),
                $expected,
                $actual,
            ),
        );
    }
}

fwrite(STDOUT, "CongestionLevelTest: OK\n");
