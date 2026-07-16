<?php
declare(strict_types=1);

final class SnapshotCache
{
    public function __construct(
        private readonly string $backendUrl,
        private readonly string $apiKey,
        private readonly string $cachePath,
        private readonly int $ttlSeconds = 5,
        private readonly int $timeoutSeconds = 3,
    ) {
    }

    /** @return array<string, mixed> */
    public function get(): array
    {
        if ($this->isFresh()) {
            return $this->readCache(false);
        }

        $directory = dirname($this->cachePath);
        if (!is_dir($directory) && !mkdir($directory, 0770, true) && !is_dir($directory)) {
            throw new RuntimeException('キャッシュディレクトリを作成できません。');
        }
        $lock = fopen($this->cachePath . '.lock', 'c+');
        if ($lock === false) {
            throw new RuntimeException('キャッシュロックを開けません。');
        }

        try {
            if (!flock($lock, LOCK_EX)) {
                throw new RuntimeException('キャッシュロックを取得できません。');
            }
            clearstatcache(true, $this->cachePath);
            if ($this->isFresh()) {
                return $this->readCache(false);
            }

            try {
                $json = $this->fetchBackend();
                $decoded = $this->decode($json);
                $this->writeAtomically($json);
                $decoded['_cache_stale'] = false;
                return $decoded;
            } catch (Throwable $error) {
                if (is_file($this->cachePath)) {
                    $cached = $this->readCache(true);
                    $cached['_cache_error'] = $error->getMessage();
                    return $cached;
                }
                throw $error;
            }
        } finally {
            flock($lock, LOCK_UN);
            fclose($lock);
        }
    }

    private function isFresh(): bool
    {
        if (!is_file($this->cachePath)) {
            return false;
        }
        $modified = filemtime($this->cachePath);
        return $modified !== false && (time() - $modified) <= $this->ttlSeconds;
    }

    /** @return array<string, mixed> */
    private function readCache(bool $stale): array
    {
        $json = file_get_contents($this->cachePath);
        if ($json === false) {
            throw new RuntimeException('キャッシュを読み込めません。');
        }
        $decoded = $this->decode($json);
        $decoded['_cache_stale'] = $stale;
        return $decoded;
    }

    private function fetchBackend(): string
    {
        $context = stream_context_create([
            'http' => [
                'method' => 'GET',
                'header' => "Accept: application/json\r\nX-API-Key: {$this->apiKey}\r\n",
                'timeout' => $this->timeoutSeconds,
                'ignore_errors' => true,
            ],
        ]);
        $body = @file_get_contents($this->backendUrl, false, $context);
        $statusLine = $http_response_header[0] ?? '';
        if ($body === false || !preg_match('/\s2\d\d\s/', $statusLine)) {
            throw new RuntimeException('バックエンドから最新情報を取得できません。');
        }
        return $body;
    }

    /** @return array<string, mixed> */
    private function decode(string $json): array
    {
        $value = json_decode($json, true, 512, JSON_THROW_ON_ERROR);
        if (!is_array($value) || !isset($value['rooms']) || !is_array($value['rooms'])) {
            throw new RuntimeException('バックエンドの応答形式が不正です。');
        }
        return $value;
    }

    private function writeAtomically(string $json): void
    {
        $temporary = tempnam(dirname($this->cachePath), '.snapshot.');
        if ($temporary === false) {
            throw new RuntimeException('一時キャッシュを作成できません。');
        }
        try {
            if (file_put_contents($temporary, $json, LOCK_EX) === false) {
                throw new RuntimeException('一時キャッシュへ書き込めません。');
            }
            if (!rename($temporary, $this->cachePath)) {
                throw new RuntimeException('キャッシュを更新できません。');
            }
        } finally {
            if (is_file($temporary)) {
                unlink($temporary);
            }
        }
    }
}

