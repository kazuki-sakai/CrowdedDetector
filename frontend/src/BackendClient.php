<?php
declare(strict_types=1);

final class BackendClient
{
    public function __construct(
        private readonly string $backendUrl,
        private readonly string $apiKey,
        private readonly int $timeoutSeconds = 3,
    ) {
        if (!str_starts_with($this->backendUrl, 'http://')
            && !str_starts_with($this->backendUrl, 'https://')) {
            throw new InvalidArgumentException('バックエンドURLが不正です。');
        }
        if ($this->apiKey === '' || str_contains($this->apiKey, "\r")
            || str_contains($this->apiKey, "\n")) {
            throw new InvalidArgumentException('バックエンドAPIキーが不正です。');
        }
        if ($this->timeoutSeconds <= 0) {
            throw new InvalidArgumentException('通信タイムアウトは1秒以上にしてください。');
        }
    }

    /** @return array<string, mixed> */
    public function fetchSnapshot(): array
    {
        $context = stream_context_create([
            'http' => [
                'method' => 'GET',
                'header' => implode("\r\n", [
                    'Accept: application/json',
                    "X-API-Key: {$this->apiKey}",
                    'Connection: close',
                ]) . "\r\n",
                'timeout' => $this->timeoutSeconds,
                'ignore_errors' => true,
            ],
        ]);
        $body = @file_get_contents($this->backendUrl, false, $context);
        $statusLine = $http_response_header[0] ?? '';
        if ($body === false) {
            throw new RuntimeException('バックエンドから最新情報を取得できません。');
        }
        if (!preg_match('/\s2\d\d\s/', $statusLine)) {
            throw new RuntimeException('バックエンドが正常でない応答を返しました。');
        }
        return $this->decode($body);
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
}
